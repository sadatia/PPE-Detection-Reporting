#!/usr/bin/env python3
import sqlite3
import os
import sys

DB_PATH = "/home/zeus/ai-cctv/data/cctv_audit.db"

def display_recent_violations(limit=15):
    if not os.path.exists(DB_PATH):
        print(f"Audit database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM violations")
    total_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, timestamp, camera_id, zone, violation_type, severity, persistence_seconds, snapshot_path
        FROM violations
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    print("=" * 95)
    print(f"AI CCTV INCIDENT AUDIT LOG (Total Recorded: {total_count})")
    print("=" * 95)
    print(f"{'ID':<5} | {'Timestamp':<19} | {'Camera':<7} | {'Violation':<15} | {'Duration':<9} | {'Zone'}")
    print("-" * 95)

    for r in rows:
        print(f"{r[0]:<5} | {r[1]:<19} | {r[2]:<7} | {r[4]:<15} | {r[6]:<6.1f}s  | {r[3]}")

    print("=" * 95)

if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    display_recent_violations(limit)
