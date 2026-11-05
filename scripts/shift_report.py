#!/usr/bin/env python3
import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = "/home/zeus/ai-cctv/data/cctv_audit.db"

def generate_shift_report(shift_type="AUTO"):
    now = datetime.now()
    hour = now.hour

    if shift_type == "AUTO":
        # If running near 17:00, it's end of Day shift (08:00 - 17:00 -> 9 hrs)
        # If running near 08:00, it's end of Night shift (17:00 - 08:00 -> 15 hrs)
        if 16 <= hour <= 18:
            shift_name = "DAY SHIFT (08:00 - 17:00)"
            hours_window = 9
        else:
            shift_name = "NIGHT SHIFT (17:00 - 08:00)"
            hours_window = 15
    elif shift_type.upper() == "DAY":
        shift_name = "DAY SHIFT (08:00 - 17:00)"
        hours_window = 9
    else:
        shift_name = "NIGHT SHIFT (17:00 - 08:00)"
        hours_window = 15

    if not os.path.exists(DB_PATH):
        print(f"[-] Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    time_threshold = (now - timedelta(hours=hours_window)).strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("SELECT COUNT(*) FROM violations WHERE timestamp >= ?", (time_threshold,))
    total_infractions = cur.fetchone()[0]

    cur.execute("""
        SELECT violation_type, COUNT(*) 
        FROM violations 
        WHERE timestamp >= ? 
        GROUP BY violation_type 
        ORDER BY COUNT(*) DESC
    """, (time_threshold,))
    breakdown = cur.fetchall()

    cur.execute("""
        SELECT camera_id, COUNT(*) 
        FROM violations 
        WHERE timestamp >= ? 
        GROUP BY camera_id 
        ORDER BY camera_id ASC
    """, (time_threshold,))
    cam_breakdown = cur.fetchall()

    cur.execute("""
        SELECT audit_status, COUNT(*) 
        FROM violations 
        WHERE timestamp >= ? 
        GROUP BY audit_status
    """, (time_threshold,))
    status_counts = dict(cur.fetchall())

    conn.close()

    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    report = [
        "==================================================",
        f"  PTJV MPDP-PK1 — HSE SHIFT AUDIT REPORT",
        f"  Shift: {shift_name}",
        f"  Report Time: {now_str} (Window: Last {hours_window} Hours)",
        "==================================================",
        f"Total Non-Compliance Events: {total_infractions}",
        f"Pending HSE Review:          {status_counts.get('PENDING', 0)}",
        f"Acknowledged / Approved:     {status_counts.get('APPROVED', 0)}",
        "-" * 50,
        "INFRACTIONS BY VIOLATION TYPE:"
    ]
    for vtype, count in breakdown:
        report.append(f"  • {vtype:<28}: {count:>4}")
    report.append("-" * 50)
    report.append("INFRACTIONS BY CAMERA ZONE:")
    for cam, count in cam_breakdown:
        report.append(f"  • {cam:<12}: {count:>4} events")
    report.append("==================================================")

    output = "\n".join(report)
    print(output)

    reports_dir = "/home/zeus/ai-cctv/reports"
    os.makedirs(reports_dir, exist_ok=True)
    report_file = os.path.join(reports_dir, f"shift_{shift_name[:3]}_{now.strftime('%Y%m%d_%H%M%S')}.txt")
    with open(report_file, "w") as f:
        f.write(output)

    print(f"\n[+] Report saved locally to: {report_file}")

if __name__ == "__main__":
    stype = sys.argv[1] if len(sys.argv) > 1 else "AUTO"
    generate_shift_report(stype)
