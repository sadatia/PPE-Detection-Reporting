import os
import sqlite3
import datetime
import cv2
import logging

class IncidentLogger:
    """Persists violation records and stores annotated snapshots to Synology NAS."""
    def __init__(self, db_path="/home/zeus/ai-cctv/data/cctv_audit.db", snapshot_dir="/mnt/synology_cctv/snapshots"):
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    camera_id TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    persistence_seconds REAL NOT NULL,
                    snapshot_path TEXT
                )
            """)
            conn.commit()

    def log_incident(self, cam_id, zone, alert_info, frame, workers, hazards):
        now_dt = datetime.datetime.now()
        timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        file_timestamp = now_dt.strftime("%Y%m%d_%H%M%S")

        # 1. Annotate Frame with Bounding Boxes
        annotated_frame = frame.copy()

        # Draw Workers and PPE status
        for w in workers:
            x1, y1, x2, y2 = w["person_bbox"]
            color = (0, 255, 0) if w["compliant"] else (0, 0, 255)
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)

            label = "COMPLIANT" if w["compliant"] else f"MISSING: {','.join(w['missing_gear'])}"
            cv2.putText(annotated_frame, label, (x1, max(y1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        # Draw Hazards (Fire / Smoke)
        for h in hazards:
            hx1, hy1, hx2, hy2 = h["bbox"]
            cv2.rectangle(annotated_frame, (hx1, hy1), (hx2, hy2), (0, 69, 255), 3)
            cv2.putText(annotated_frame, f"HAZARD: {h['label'].upper()}", (hx1, max(hy1 - 10, 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 69, 255), 2)

        # 2. Save Snapshot to Synology NAS
        filename = f"{cam_id}_{alert_info['type']}_{file_timestamp}.jpg"
        save_path = os.path.join(self.snapshot_dir, filename)
        cv2.imwrite(save_path, annotated_frame)

        # 3. Insert Audit Record into Database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO violations (timestamp, camera_id, zone, violation_type, severity, persistence_seconds, snapshot_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp_str,
                cam_id,
                zone,
                alert_info["type"],
                alert_info["severity"],
                alert_info["duration"],
                save_path
            ))
            conn.commit()

        logging.info(f"[DB] Logged violation to audit database and saved snapshot: {save_path}")
        return save_path
