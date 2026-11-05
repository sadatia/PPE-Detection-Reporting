#!/usr/bin/env python3
import sqlite3
import os
import shutil
import json
from datetime import datetime

DB_PATH = "/home/zeus/ai-cctv/data/cctv_audit.db"
DEST_BASE = "/mnt/synology_cctv/dataset/hard_negatives"
SNAPSHOT_SEARCH_DIRS = [
    "/mnt/synology_cctv/snapshots",
    "/home/zeus/ai-cctv/data/snapshots",
    "/tmp"
]

def harvest_false_positives():
    if not os.path.exists(DB_PATH):
        print(f"[-] Database not found at {DB_PATH}")
        return

    os.makedirs(DEST_BASE, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Query all false positive records
    cur.execute("""
        SELECT id, timestamp, camera_id, violation_type, snapshot_path, supervisor_notes 
        FROM violations 
        WHERE audit_status = 'FALSE_POSITIVE'
        ORDER BY id ASC;
    """)
    records = cur.fetchall()
    conn.close()

    if not records:
        print("[*] No records marked as FALSE_POSITIVE found in cctv_audit.db.")
        return

    print(f"[+] Found {len(records)} record(s) marked as FALSE_POSITIVE. Processing export...")

    copied_count = 0
    skipped_count = 0
    missing_count = 0

    manifest = []

    for r in records:
        rec_id, ts, cam_id, vtype, snap_path, notes = r
        clean_vtype = vtype.replace("MISSING PPE: ", "").replace(", ", "_").replace(" ", "_")
        date_str = ts.split()[0].replace("-", "")
        
        # Subdirectory structured by violation class for direct YOLO annotation
        target_dir = os.path.join(DEST_BASE, clean_vtype)
        os.makedirs(target_dir, exist_ok=True)

        target_filename = f"FP_{rec_id}_{cam_id}_{date_str}.jpg"
        dest_filepath = os.path.join(target_dir, target_filename)

        # Skip if already exported
        if os.path.exists(dest_filepath):
            skipped_count += 1
            manifest.append({
                "id": rec_id,
                "camera_id": cam_id,
                "timestamp": ts,
                "violation_type": vtype,
                "notes": notes,
                "export_path": dest_filepath,
                "status": "already_exported"
            })
            continue

        # Locate source snapshot
        found_src = None
        if snap_path and os.path.exists(snap_path):
            found_src = snap_path
        else:
            # Fallback search if path was relative or changed
            for sdir in SNAPSHOT_SEARCH_DIRS:
                if not os.path.exists(sdir):
                    continue
                # Match by record id or pattern
                candidate = os.path.join(sdir, f"{cam_id}_{rec_id}.jpg")
                if os.path.exists(candidate):
                    found_src = candidate
                    break

        if found_src and os.path.exists(found_src):
            try:
                shutil.copy2(found_src, dest_filepath)
                copied_count += 1
                manifest.append({
                    "id": rec_id,
                    "camera_id": cam_id,
                    "timestamp": ts,
                    "violation_type": vtype,
                    "notes": notes,
                    "source_path": found_src,
                    "export_path": dest_filepath,
                    "status": "copied"
                })
            except Exception as e:
                print(f"[-] Error copying {found_src}: {e}")
        else:
            missing_count += 1
            manifest.append({
                "id": rec_id,
                "camera_id": cam_id,
                "timestamp": ts,
                "violation_type": vtype,
                "notes": notes,
                "status": "source_snapshot_missing"
            })

    # Save dataset manifest
    manifest_file = os.path.join(DEST_BASE, "manifest.json")
    with open(manifest_file, "w") as f:
        json.dump({
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_records": len(records),
            "copied": copied_count,
            "skipped_already_present": skipped_count,
            "source_missing": missing_count,
            "records": manifest
        }, f, indent=2)

    print("-" * 65)
    print(f"[✓] Harvest Completed:")
    print(f"    • Newly Copied:     {copied_count}")
    print(f"    • Already Present:  {skipped_count}")
    print(f"    • Missing Snapshots: {missing_count}")
    print(f"    • Manifest Saved:   {manifest_file}")
    print(f"    • Target Root:      {DEST_BASE}")
    print("-" * 65)

if __name__ == "__main__":
    harvest_false_positives()
