#!/bin/bash
# Dahua Camera RTSP Endpoints
CAM_URLS=(
  "rtsp://admin:aqashi888@10.220.147.135:554/cam/realmonitor?channel=1&subtype=0"
  "rtsp://admin:aqashi888@10.220.147.88:554/cam/realmonitor?channel=1&subtype=0"
  "rtsp://admin:aqashi888@10.220.147.117:554/cam/realmonitor?channel=1&subtype=0"
  "rtsp://admin:aqashi888@10.220.125.12:554/cam/realmonitor?channel=1&subtype=0"
  "rtsp://admin:aqashi888@10.220.147.89:554/cam/realmonitor?channel=1&subtype=0"
  "rtsp://admin:aqashi888@10.220.147.60:554/cam/realmonitor?channel=1&subtype=0"
)

BASE_DIR="/mnt/synology_cctv/recordings"

for i in "${!CAM_URLS[@]}"; do
  CAM_NUM=$((i+1))
  CAM_DIR="${BASE_DIR}/CAM_0${CAM_NUM}"
  mkdir -p "${CAM_DIR}"

  # Direct stream copy with TCP transport, segmented every 15 minutes (900s)
  ffmpeg -rtsp_transport tcp \
    -i "${CAM_URLS[$i]}" \
    -c copy \
    -f segment \
    -segment_time 900 \
    -reset_timestamps 1 \
    -strftime 1 \
    "${CAM_DIR}/%Y-%m-%d_%H-%M-%S.mp4" &
done

wait
