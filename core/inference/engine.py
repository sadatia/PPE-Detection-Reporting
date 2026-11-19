from datetime import datetime
import os
import logging
import yaml
import torch
import numpy as np
from ultralytics import YOLO

LABEL_NORMALIZATION = {
    "person": "person",
    "worker": "person",
    "helmet": "helmet",
    "hardhat": "helmet",
    "hard-hat": "helmet",
    "hard_hat": "helmet",
    "no-helmet": "no_helmet",
    "no_helmet": "no_helmet",
    "no-hardhat": "no_helmet",
    "no_hardhat": "no_helmet",
    "head": "no_helmet",
    "vest": "vest",
    "safety vest": "vest",
    "safety-vest": "vest",
    "safety_vest": "vest",
    "no-safety vest": "no_vest",
    "no safety vest": "no_vest",
    "high-vis": "vest",
    "no-vest": "no_vest",
    "no_vest": "no_vest",
    "no-safety-vest": "no_vest",
    "no_safety_vest": "no_vest",
    "boot": "boot",
    "boots": "boot",
    "safety-boot": "boot",
    "safety-boots": "boot",
    "shoes": "boot",
    "fire": "fire",
    "smoke": "smoke",
}


class SafetyInferenceEngine:
    def __init__(
        self,
        model_path="yolo11l.pt",
        ppe_model_path="models/ppe_detector.pt",
        config_path="config/rules.yaml",
    ):
        self.model_path = model_path
        self.ppe_model_path = ppe_model_path
        self.config_path = config_path
        self._last_rules_mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else 0

        with open(config_path, "r") as f:
            self.rules = yaml.safe_load(f)["detection_rules"]

        self.thresholds = self.rules.get("thresholds", {}).get("confidence", {})

        print(f"[*] Initializing Primary Detector: {self.model_path} on GPU:0")
        self.model = YOLO(self.model_path)

        self.ppe_model = None
        self.ppe_classes = set()
        if self.ppe_model_path and os.path.exists(self.ppe_model_path):
            print(f"[*] Initializing Dedicated PPE Detector: {self.ppe_model_path} on GPU:0")
            self.ppe_model = YOLO(self.ppe_model_path)
            self.ppe_classes = {
                LABEL_NORMALIZATION.get(v.lower(), v.lower())
                for v in self.ppe_model.names.values()
            }
            print(f"[*] Active Deep-Learning PPE Classes: {sorted(self.ppe_classes)}")
        else:
            logging.warning(f"[!] PPE weights not found at {self.ppe_model_path}; running primary detector only.")

        dummy_img = np.zeros((1280, 1280, 3), dtype=np.uint8)
        self.model.predict(source=dummy_img, imgsz=1280, device=0, verbose=False)
        if self.ppe_model is not None:
            self.ppe_model.predict(source=dummy_img, imgsz=1280, device=0, verbose=False)
        print("[*] Pascal GPU Dual-Model warm-up complete.")

    def _parse_results(self, results, shift_thresholds, allowed_labels=None):
        parsed = []
        if not results or len(results[0].boxes) == 0:
            return parsed

        boxes = results[0].boxes
        class_names = results[0].names

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            raw_label = class_names.get(cls_id, str(cls_id)).lower().strip()
            label = LABEL_NORMALIZATION.get(raw_label, raw_label)

            if allowed_labels and label not in allowed_labels:
                continue

            base_key = label.replace("no_", "")
            min_conf = shift_thresholds.get(label, shift_thresholds.get(base_key, 0.38))
            if conf < min_conf:
                continue

            xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
            parsed.append({
                "class_id": cls_id,
                "label": label,
                "confidence": round(conf, 3),
                "bbox": xyxy,
            })
        return parsed

    def infer_frame(self, frame, imgsz=1280):
        current_hour = datetime.now().hour
        is_night = (current_hour >= 17 or current_hour < 8)
        shift_key = "night" if is_night else "day"
        shift_thresholds = self.thresholds.get(shift_key, self.thresholds)

        primary_res = self.model.predict(
            source=frame,
            imgsz=imgsz,
            device=0,
            verbose=False,
            conf=0.25,
        )
        detections = self._parse_results(
            primary_res,
            shift_thresholds,
            allowed_labels={"person", "fire", "smoke"},
        )

        if self.ppe_model is not None:
            ppe_res = self.ppe_model.predict(
                source=frame,
                imgsz=imgsz,
                device=0,
                verbose=False,
                conf=0.25,
            )
            ppe_detections = self._parse_results(
                ppe_res,
                shift_thresholds,
                allowed_labels={"helmet", "no_helmet", "vest", "no_vest", "boot", "fire", "smoke"},
            )
            detections.extend(ppe_detections)

        return detections

    def check_and_reload_rules(self):
        try:
            mtime = os.path.getmtime(self.config_path)
            if mtime > self._last_rules_mtime:
                with open(self.config_path, "r") as f:
                    updated = yaml.safe_load(f)
                if updated and "detection_rules" in updated:
                    self.rules = updated["detection_rules"]
                    self._last_rules_mtime = mtime
                    logging.info("[RulesHotReload] Successfully reloaded updated thresholds from rules.yaml")
        except Exception:
            pass
