#!/usr/bin/env python3
import sys
import os
import time
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ingestion.stream_manager import MultiCameraManager
from core.inference.engine import SafetyInferenceEngine
from core.inference.tracker import PersonSafetyTracker
from core.alerting.debouncer import ViolationDebouncer
from core.alerting.dispatcher import AlertDispatcher

def main():
    print("=" * 70)
    print("AI-CCTV: INTEGRATED PIPELINE (INGESTION -> INFERENCE -> DEBOUNCE -> ALERT)")
    print("=" * 70)

    with open("config/cameras.yaml") as f:
        cameras_cfg = yaml.safe_load(f)
    with open("config/rules.yaml") as f:
        rules_cfg = yaml.safe_load(f)

    manager = MultiCameraManager(config_path="config/cameras.yaml")
    engine = SafetyInferenceEngine(model_path="yolov8s.pt", config_path="config/rules.yaml")
    tracker = PersonSafetyTracker(containment_threshold=0.55)
    debouncer = ViolationDebouncer(ppe_persist=3.0, fire_persist=1.0, cooldown_seconds=30.0)
    dispatcher = AlertDispatcher(cameras_cfg, rules_cfg)

    print("[*] Starting RTSP stream ingest threads...")
    manager.start_all()
    print("[*] Warming up streams for 5 seconds...")
    time.sleep(5)

    print("\n[*] Surveillance loop running (Press Ctrl+C to stop)...")
    try:
        loop_count = 0
        while True:
            loop_count += 1
            frames = manager.get_active_frames()
            if not frames:
                time.sleep(0.05)
                continue

            for cam_id, data in frames.items():
                frame = data["frame"]
                detections = engine.infer_frame(frame)
                workers, hazards = tracker.evaluate_frame(detections)

                # Debounce and evaluate state
                verified_alerts = debouncer.process_events(cam_id, workers, hazards)

                for alert in verified_alerts:
                    print(f"\n[🚨 ALARM TRIGGERED] {cam_id} -> {alert['type']} (Duration: {alert['duration']}s)")
                    dispatcher.trigger_toa_speaker(cam_id, alert["type"])
                    dispatcher.send_telegram_alert(cam_id, alert["type"], snapshot_frame=frame)

            if loop_count % 25 == 0:
                print(f"[*] Loop {loop_count} active | Processed {len(frames)} camera channels smoothly.")

            time.sleep(0.04)

    except KeyboardInterrupt:
        print("\n[*] Stopping pipeline...")
    finally:
        manager.stop_all()
        print("[*] Pipeline stopped cleanly.")

if __name__ == "__main__":
    main()
