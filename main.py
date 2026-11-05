import cv2
#!/usr/bin/env python3
import sys
import os
import time
import signal
import yaml
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from core.ingestion.stream_manager import MultiCameraManager
from core.inference.engine import SafetyInferenceEngine
from core.inference.tracker import PersonSafetyTracker
from core.alerting.debouncer import ViolationDebouncer
from core.alerting.dispatcher import AlertDispatcher
from core.storage.incident_logger import IncidentLogger

class SurveillanceDaemon:
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

        with open("config/cameras.yaml") as f:
            self.cameras_cfg = yaml.safe_load(f)
        c_list = self.cameras_cfg.get("cameras", self.cameras_cfg) if isinstance(self.cameras_cfg, dict) else self.cameras_cfg
        self.cam_configs = {c["id"]: c for c in c_list if isinstance(c, dict) and "id" in c}

        with open("config/rules.yaml") as f:
            self.rules_cfg = yaml.safe_load(f)

        self.manager = MultiCameraManager(config_path="config/cameras.yaml")
        self.engine = SafetyInferenceEngine(model_path="yolov8s.pt", config_path="config/rules.yaml")
        self.tracker = PersonSafetyTracker(containment_threshold=0.55)
        timing_cfg = self.rules_cfg.get("detection_rules", {}).get("timing", {})
        self.debouncer = ViolationDebouncer(
            ppe_persist=timing_cfg.get("ppe_persistence_seconds", 3.0),
            fire_persist=timing_cfg.get("fire_persistence_seconds", 1.0),
            cooldown_seconds=timing_cfg.get("cooldown_seconds", 120.0)
        )
        self.dispatcher = AlertDispatcher(self.cameras_cfg, self.rules_cfg)
        self.logger = IncidentLogger(
            db_path="/home/zeus/ai-cctv/data/cctv_audit.db",
            snapshot_dir="/mnt/synology_cctv/snapshots"
        )

        self.cam_zones = {c["id"]: c.get("zone", "Site Zone") for c in self.cameras_cfg.get("cameras", [])}

    def _handle_exit(self, signum, frame):
        logging.info(f"Signal {signum} received. Initiating graceful shutdown...")
        self.running = False

    def run(self):
        logging.info("Starting RTSP Ingestion Threads across 6 cameras...")
        self.manager.start_all()

        logging.info("Waiting 4 seconds for camera network streams to lock...")
        time.sleep(4)

        logging.info("AI Surveillance Pipeline is ONLINE.")

        loop_count = 0
        try:
            while self.running:
                # Throttle loop to ~5 FPS to prevent CPU core saturation
                time.sleep(0.18)
                loop_count += 1
                frames = self.manager.get_active_frames()
                if not frames:
                    time.sleep(0.04)
                    continue

                for cam_id, data in frames.items():
                    frame = data["frame"]
                    detections = self.engine.infer_frame(frame)
                    cam_cfg = getattr(self, 'cam_configs', {}).get(cam_id) or {}
                    cam_roi = cam_cfg.get('roi', []) if isinstance(cam_cfg, dict) else []
                    workers, hazards = self.tracker.evaluate_frame(detections, raw_frame=frame, roi_polygon=cam_roi)

                    # Check persistent safety violations
                    verified_alerts = self.debouncer.process_events(cam_id, workers, hazards)

                    for alert in verified_alerts:
                        zone = self.cam_zones.get(cam_id, "Unknown Zone")
                        logging.warning(f"🚨 ALARM: {cam_id} ({zone}) -> {alert['type']} ({alert['duration']}s)")

                        # 1. Log incident and save annotated frame to Synology NAS
                        snapshot_path = self.logger.log_incident(cam_id, zone, alert, frame, workers, hazards)

                        # 2. Trigger On-site TOA Horn Speaker
                        self.dispatcher.trigger_toa_speaker(cam_id, alert["type"])

                        # 3. Send Telegram Notification with Snapshot
                        # Pass the annotated snapshot frame drawn by IncidentLogger
                        annotated_frame = cv2.imread(snapshot_path) if snapshot_path and os.path.exists(snapshot_path) else frame
                        self.dispatcher.send_telegram_alert(cam_id, alert["type"], snapshot_frame=annotated_frame)

                time.sleep(0.03)

        finally:
            logging.info("Stopping stream manager and worker threads...")
            self.manager.stop_all()
            logging.info("Surveillance engine stopped cleanly.")

if __name__ == "__main__":
    daemon = SurveillanceDaemon()
    daemon.run()
