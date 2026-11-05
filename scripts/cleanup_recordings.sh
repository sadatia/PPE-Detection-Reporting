#!/bin/bash
# ==============================================================================
# Automated Retention Purge Script: 30-Day Video Cleanup
# ==============================================================================
# Targets: ONLY /mnt/synology_cctv/recordings/
# Preserves: /mnt/synology_cctv/snapshots/ and any other root directories
# ==============================================================================

MOUNT_DIR="/mnt/synology_cctv"
RECORDINGS_DIR="${MOUNT_DIR}/recordings"
LOG_FILE="/home/zeus/ai-cctv/data/cleanup.log"
RETENTION_DAYS=30

mkdir -p "$(dirname "$LOG_FILE")"

# Safety Check: Verify SMB mount is active before executing any deletes
if ! mountpoint -q "$MOUNT_DIR"; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Mount point $MOUNT_DIR is offline. Aborting purge to protect local root filesystem." >> "$LOG_FILE"
    exit 1
fi

# Safety Check: Verify recordings directory exists
if [ ! -d "$RECORDINGS_DIR" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Target directory $RECORDINGS_DIR does not exist. Aborting." >> "$LOG_FILE"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] START: Purging video segments older than ${RETENTION_DAYS} days from ${RECORDINGS_DIR}..." >> "$LOG_FILE"

# 1. Purge .mp4 / .mkv / .ts video chunks older than 30 days
# -mindepth 2 ensures it targets /recordings/CAM_XX/*.mp4, not top-level dirs
DELETED_FILES_COUNT=$(find "$RECORDINGS_DIR" -mindepth 2 -type f \( -name "*.mp4" -o -name "*.mkv" -o -name "*.ts" \) -mtime +"$RETENTION_DAYS" -print -delete | wc -l)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] COMPLETED: Deleted ${DELETED_FILES_COUNT} expired video file(s)." >> "$LOG_FILE"

# 2. Prune empty date/hour subdirectories inside camera folders (if any are created)
find "$RECORDINGS_DIR" -mindepth 2 -type d -empty -delete 2>/dev/null

exit 0
