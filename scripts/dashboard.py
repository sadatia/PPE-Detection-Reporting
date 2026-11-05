#!/usr/bin/env python3
import os
import sqlite3
import subprocess
import shutil

DB_PATH = "/home/zeus/ai-cctv/data/cctv_audit.db"
NAS_PATH = "/mnt/synology_cctv"

def get_disk_info(path):
    if not os.path.exists(path):
        return "OFFLINE / UNMOUNTED"
    total, used, free = shutil.disk_usage(path)
    return f"{used // (2**30)} GB used / {free // (2**30)} GB free ({total // (2**30)} GB total)"

def show_dashboard():
    print("=" * 80)
    print("                     AI CCTV SURVEILLANCE SYSTEM STATUS")
    print("=" * 80)

    # 1. Check systemd services
    print("[SERVICE STATUS]")
    for s in ["mnt-synology_cctv.mount", "cctv-recorder.service", "cctv-analytics.service"]:
        res = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True)
        status = res.stdout.strip()
        icon = "🟢" if status == "active" else "🔴"
        print(f"  {icon} {s:<25}: {status.upper()}")

    # 2. NAS Storage
    print("\n[SYNOLOGY NAS STORAGE]")
    print(f"  Mount Point: {NAS_PATH}")
    print(f"  Capacity   : {get_disk_info(NAS_PATH)}")
    
    snap_count = len(os.listdir(f"{NAS_PATH}/snapshots")) if os.path.exists(f"{NAS_PATH}/snapshots") else 0
    print(f"  Violation Snapshots Stored: {snap_count} images")

    # 3. Incident Counts by Camera
    print("\n[SAFETY INCIDENTS BREAKDOWN]")
    if os.path.exists(DB_PATH):
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT camera_id, COUNT(*) FROM violations GROUP BY camera_id ORDER BY COUNT(*) DESC")
            rows = cursor.fetchall()
            if rows:
                for cid, cnt in rows:
                    print(f"  Camera {cid:<8}: {cnt:>4} violations logged")
            else:
                print("  No incidents recorded yet.")

            cursor.execute("SELECT violation_type, COUNT(*) FROM violations GROUP BY violation_type")
            v_rows = cursor.fetchall()
            print("\n[VIOLATIONS BY TYPE]")
            for vtype, cnt in v_rows:
                print(f"  {vtype:<20}: {cnt:>4} incidents")
    print("=" * 80)

if __name__ == "__main__":
    show_dashboard()
