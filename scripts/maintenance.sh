#!/bin/bash
set -e

LOG_FILE="/home/zeus/ai-cctv/logs/maintenance.log"
mkdir -p /home/zeus/ai-cctv/logs

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting automated site maintenance..." >> "$LOG_FILE"

# 1. Prune Synology NAS snapshots older than 90 days
if [ -d "/mnt/synology_cctv/snapshots" ]; then
    DELETED_COUNT=$(find /mnt/synology_cctv/snapshots/ -type f -name "*.jpg" -mtime +90 -print -delete | wc -l)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Purged $DELETED_COUNT snapshots older than 90 days." >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: /mnt/synology_cctv/snapshots not mounted." >> "$LOG_FILE"
fi

# 2. SQLite optimization (WAL checkpoint + VACUUM)
DB_PATH="/home/zeus/ai-cctv/data/cctv_audit.db"
if [ -f "$DB_PATH" ]; then
    sqlite3 "$DB_PATH" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SQLite maintenance completed successfully on $DB_PATH." >> "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Maintenance complete." >> "$LOG_FILE"
