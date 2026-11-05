from datetime import datetime
import os
import cv2
import yaml
import torch
import numpy as np
from ultralytics import YOLO

class SafetyInferenceEngine:
    def __init__(self, model_path="yolov8s.pt", config_path="config/rules.yaml"):
        self.model_path = model_path
        self.config_path = config_path
        import os
        self._last_rules_mtime = os.path.getmtime(config_path) if os.path.exists(config_path) else 0
        
        # Load rule parameters
        with open(config_path, "r") as f:
            self.rules = yaml.safe_load(f)["detection_rules"]

        self.thresholds = self.rules.get("thresholds", {}).get("confidence", {})
        
        print(f"[*] Initializing Inference Engine with model: {self.model_path} on GPU:0")
        self.model = YOLO(self.model_path)
        
        # Warm up the Pascal GPU
        dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
        self.model.predict(source=dummy_img, device=0, verbose=False)
        print("[*] Pascal GPU warm-up complete.")

    def infer_frame(self, frame, imgsz=640):
        """
        Runs inference on a single BGR frame from OpenCV on GTX 1080 Ti.
        Returns parsed detections categorized by safety class.
        """
        results = self.model.predict(
            source=frame,
            imgsz=imgsz,
            device=0,
            verbose=False,
            conf=0.25
        )

        detections = []
        if not results or len(results[0].boxes) == 0:
            return detections

        boxes = results[0].boxes
        class_names = results[0].names

        for box in boxes:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            label = class_names.get(cls_id, str(cls_id)).lower()

            # Filter against per-class thresholds
            # Dynamic Night/Day threshold switch
            current_hour = datetime.now().hour
            is_night = (current_hour >= 17 or current_hour < 8)
            shift_key = "night" if is_night else "day"
            
            shift_thresholds = self.thresholds.get(shift_key, self.thresholds)
            min_conf = shift_thresholds.get(label, 0.40)
            if conf < min_conf:
                continue

            xyxy = box.xyxy[0].cpu().numpy().astype(int).tolist()
            detections.append({
                "class_id": cls_id,
                "label": label,
                "confidence": round(conf, 3),
                "bbox": xyxy  # [x1, y1, x2, y2]
            })

        return detections

    def check_and_reload_rules(self):
        """Hot-reloads rules.yaml if modified on disk without dropping stream buffers."""
        import os, yaml
        try:
            mtime = os.path.getmtime(self.config_path)
            if mtime > self._last_rules_mtime:
                with open(self.config_path, "r") as f:
                    updated = yaml.safe_load(f)
                if updated and "detection_rules" in updated:
                    self.rules = updated["detection_rules"]
                    self._last_rules_mtime = mtime
                    import logging
                    logging.info("[RulesHotReload] Successfully reloaded updated thresholds from rules.yaml")
        except Exception:
            pass
