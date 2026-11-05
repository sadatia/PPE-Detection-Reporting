#!/usr/bin/env python3
import sys
import time
import os
import cv2
import numpy as np

# Ensure project root is in the Python module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ingestion.stream_manager import MultiCameraManager

TEST_DURATION_SECONDS = 15  # Benchmark duration
CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config/cameras.yaml"))
SNAPSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/snapshots/test_runs"))

os.makedirs(SNAPSHOT_DIR, exist_ok=True)

def run_ingestion_test():
    print("=" * 70)
    print("AI-CCTV: 6-CAMERA RTSP INGESTION DIAGNOSTIC TEST")
    print(f"Target Configuration: {CONFIG_PATH}")
    print(f"Benchmark Duration  : {TEST_DURATION_SECONDS} seconds")
    print("=" * 70)

    manager = MultiCameraManager(config_path=CONFIG_PATH)
    
    print("[*] Spawning camera ingestion worker threads on Xeon CPU...")
    manager.start_all()

    # Allow threads 3 seconds to establish TCP handshakes with RTSP endpoints
    warmup_period = 3
    print(f"[*] Waiting {warmup_period}s for network stream handshakes to settle...")
    time.sleep(warmup_period)

    frame_counters = {cam_id: 0 for cam_id in manager.streams.keys()}
    resolutions = {cam_id: "N/A" for cam_id in manager.streams.keys()}
    first_frame_saved = {cam_id: False for cam_id in manager.streams.keys()}

    start_time = time.perf_counter()
    last_report_time = start_time

    try:
        while (time.perf_counter() - start_time) < TEST_DURATION_SECONDS:
            active_frames = manager.get_active_frames()

            for cam_id, data in active_frames.items():
                frame = data["frame"]
                if frame is not None and frame.size > 0:
                    frame_counters[cam_id] += 1

                    if not first_frame_saved[cam_id]:
                        h, w, c = frame.shape
                        resolutions[cam_id] = f"{w}x{h} ({c}ch)"
                        # Save sample initial frame to verify image color and decoding
                        snapshot_path = os.path.join(SNAPSHOT_DIR, f"{cam_id}_test.jpg")
                        cv2.imwrite(snapshot_path, frame)
                        first_frame_saved[cam_id] = True

            # Periodic status line every 3 seconds
            current_time = time.perf_counter()
            if current_time - last_report_time >= 3.0:
                elapsed = current_time - start_time
                fps_summary = [f"{cid}: {cnt/elapsed:.1f} fps" for cid, cnt in frame_counters.items()]
                print(f"[{elapsed:4.1f}s elapsed] Ingest Rate -> " + " | ".join(fps_summary))
                last_report_time = current_time

            # Small sleep to yield CPU slice
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n[!] User interrupted test early.")
    finally:
        total_elapsed = time.perf_counter() - start_time
        print("\n[*] Stopping all camera threads and terminating sockets...")
        manager.stop_all()

    # Final Diagnostic Report
    print("\n" + "=" * 70)
    print("CAMERA STREAM PERFORMANCE & HEALTH REPORT")
    print("=" * 70)
    print(f"{'Camera ID':<10} | {'Status':<12} | {'Resolution':<14} | {'Frames':<8} | {'Avg Ingest FPS'}")
    print("-" * 70)

    all_healthy = True
    for cam_id, stream in manager.streams.items():
        received = frame_counters[cam_id]
        fps = received / total_elapsed if total_elapsed > 0 else 0.0
        status = "ONLINE" if received > 0 else "OFFLINE/ERR"
        
        if received == 0:
            all_healthy = False

        print(f"{cam_id:<10} | {status:<12} | {resolutions[cam_id]:<14} | {received:<8} | {fps:.2f} FPS")

    print("-" * 70)
    if all_healthy:
        print("✅ SUCCESS: All 6 cameras ingested concurrently with zero lockup.")
        print(f"Sample test frames written to: {SNAPSHOT_DIR}")
    else:
        print("⚠️ WARNING: One or more camera streams failed to deliver valid frames.")
        print("Check RTSP URLs, Dahua camera credentials, or network routing.")
    print("=" * 70)

if __name__ == "__main__":
    run_ingestion_test()
