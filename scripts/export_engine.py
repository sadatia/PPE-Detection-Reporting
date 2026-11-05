#!/usr/bin/env python3
import os
import sys
import torch
from ultralytics import YOLO

def export_pascal_engine(weights_path="yolov8s.pt", imgsz=640, batch=1):
    print("=" * 60)
    print("AI-CCTV: EXPORTING TENSORRT ENGINE FOR PASCAL (GTX 1080 Ti)")
    print(f"Base Weights : {weights_path}")
    print(f"Target ImgSz : {imgsz}x{imgsz}")
    print(f"Batch Size   : {batch}")
    print("Precision    : FP32 (Pascal-optimized, sm_61)")
    print("=" * 60)

    if not torch.cuda.is_available():
        print("[!] ERROR: CUDA is not available.")
        sys.exit(1)

    print(f"[*] Target GPU: {torch.cuda.get_device_name(0)}")

    model = YOLO(weights_path)

    # Export to TensorRT engine in FP32
    exported_path = model.export(
        format="engine",
        imgsz=imgsz,
        batch=batch,
        device=0,
        half=False,
        workspace=4,
        verbose=True
    )

    print("\n" + "=" * 60)
    print(f"✅ Export completed successfully!")
    print(f"Engine Artifact: {exported_path}")
    print("=" * 60)

if __name__ == "__main__":
    target_weights = sys.argv[1] if len(sys.argv) > 1 else "yolov8s.pt"
    export_pascal_engine(weights_path=target_weights, imgsz=640, batch=1)
