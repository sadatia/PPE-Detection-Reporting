import os
import glob
import shutil
import random
import cv2
import yaml
from core.inference.engine import SafetyInferenceEngine

# Canonical class mapping for fine-tuning
CLASS_MAP = {
    "person": 0,
    "helmet": 1,
    "no_helmet": 2,
    "vest": 3,
    "no_vest": 4,
}

SNAP_DIR = "/mnt/synology_cctv/snapshots"
OUT_DIR = "/home/zeus/ai-cctv/datasets/matarbari_ppe"
MAX_IMAGES = 600  # Adjust based on available snapshots
VAL_RATIO = 0.15


def xyxy_to_yolo(bbox, img_w, img_h):
    x1, y1, x2, y2 = bbox
    xc = max(0.0, min(1.0, ((x1 + x2) / 2.0) / img_w))
    yc = max(0.0, min(1.0, ((y1 + y2) / 2.0) / img_h))
    w = max(0.001, min(1.0, (x2 - x1) / float(img_w)))
    h = max(0.001, min(1.0, (y2 - y1) / float(img_h)))
    return f"{xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"


def main():
    snaps = sorted(glob.glob(os.path.join(SNAP_DIR, "*.[jJ][pP]*[gG]")), key=os.path.getmtime)
    if not snaps:
        print("[!] No snapshots found in", SNAP_DIR)
        return

    # Take the newest snapshots up to MAX_IMAGES and shuffle for train/val split
    selected = snaps[-MAX_IMAGES:]
    random.seed(42)
    random.shuffle(selected)

    for split in ["train", "val"]:
        os.makedirs(os.path.join(OUT_DIR, "images", split), exist_ok=True)
        os.makedirs(os.path.join(OUT_DIR, "labels", split), exist_ok=True)

    print(f"[*] Initializing Dual-Model Engine to pre-label {len(selected)} snapshots...")
    engine = SafetyInferenceEngine(
        model_path="yolo11l.pt",
        ppe_model_path="models/ppe_detector.pt",
        config_path="config/rules.yaml",
    )

    val_cutoff = int(len(selected) * (1.0 - VAL_RATIO))
    labeled_count = 0

    for idx, img_path in enumerate(selected):
        frame = cv2.imread(img_path)
        if frame is None:
            continue

        h, w = frame.shape[:2]
        detections = engine.infer_frame(frame, imgsz=1280)

        yolo_lines = []
        for det in detections:
            lbl = det["label"]
            if lbl not in CLASS_MAP:
                continue
            cls_id = CLASS_MAP[lbl]
            yolo_lines.append(f"{cls_id} {xyxy_to_yolo(det['bbox'], w, h)}")

        split = "train" if idx < val_cutoff else "val"
        base_name = f"site_{idx:05d}"
        dst_img = os.path.join(OUT_DIR, "images", split, f"{base_name}.jpg")
        dst_lbl = os.path.join(OUT_DIR, "labels", split, f"{base_name}.txt")

        shutil.copy2(img_path, dst_img)
        with open(dst_lbl, "w") as f:
            f.write("\n".join(yolo_lines))

        labeled_count += 1
        if labeled_count % 50 == 0:
            print(f"    Processed {labeled_count}/{len(selected)} frames...")

    dataset_yaml = {
        "path": OUT_DIR,
        "train": "images/train",
        "val": "images/val",
        "names": {v: k for k, v in CLASS_MAP.items()},
    }
    yaml_path = os.path.join(OUT_DIR, "dataset.yaml")
    with open(yaml_path, "w") as f:
        yaml.safe_dump(dataset_yaml, f, sort_keys=False)

    print(f"\n[+] Dataset ready at: {OUT_DIR}")
    print(f"[+] Total pre-labeled images: {labeled_count} (Train: {val_cutoff}, Val: {labeled_count - val_cutoff})")
    print(f"[+] Config written to: {yaml_path}")


if __name__ == "__main__":
    main()
