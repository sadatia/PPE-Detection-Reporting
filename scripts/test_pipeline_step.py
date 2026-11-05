#!/usr/bin/env python3
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.ingestion.stream_manager import MultiCameraManager
from core.inference.engine import SafetyInferenceEngine

def main():
    print("=" * 65)
    print("AI-CCTV: MULTI-CAMERA LIVE GPU INFERENCE BENCHMARK")
    print("=" * 65)

    manager = MultiCameraManager(config_path="config/cameras.yaml")
    engine = SafetyInferenceEngine(model_path="yolov8s.pt", config_path="config/rules.yaml")

    print("[*] Spawning camera worker threads...")
    manager.start_all()

    # Wait for at least one active frame or timeout after 15s
    print("[*] Synchronizing camera connections over network link...")
    max_wait = 15
    start_wait = time.perf_counter()
    ready = False

    while (time.perf_counter() - start_wait) < max_wait:
        frames = manager.get_active_frames()
        if len(frames) >= len(manager.streams) // 2:  # At least half online
            ready = True
            print(f"[*] Streams locked: {len(frames)}/{len(manager.streams)} cameras streaming.")
            break
        time.sleep(0.5)

    if not ready:
        print("[!] Warning: Timed out waiting for full stream synchronization.")

    print("\n[*] Starting 30-cycle live inference benchmark...")
    latencies = []
    total_detections_count = 0
    cycles_to_run = 30
    completed_cycles = 0

    while completed_cycles < cycles_to_run:
        frames = manager.get_active_frames()
        if not frames:
            time.sleep(0.05)
            continue

        t0 = time.perf_counter()
        cycle_detections = {}

        for cam_id, data in frames.items():
            frame = data["frame"]
            detections = engine.infer_frame(frame)
            cycle_detections[cam_id] = [f"{d['label']}:{d['confidence']:.2f}" for d in detections]
            total_detections_count += len(detections)

        t1 = time.perf_counter()
        cycle_ms = (t1 - t0) * 1000.0
        latencies.append(cycle_ms)
        completed_cycles += 1

        summary = " | ".join([f"{cid}: {len(dets)} det" for cid, dets in cycle_detections.items()])
        print(f"Cycle {completed_cycles:02d}/{cycles_to_run} ({cycle_ms:5.1f} ms) -> {summary}")

        # Target ~15 FPS pipeline polling
        time.sleep(0.04)

    manager.stop_all()

    avg_cycle = sum(latencies) / len(latencies) if latencies else 0.0
    avg_per_cam = avg_cycle / len(manager.streams) if manager.streams else 0.0
    effective_fps = 1000.0 / avg_cycle if avg_cycle > 0 else 0.0

    print("\n" + "=" * 65)
    print("BENCHMARK RESULTS (GTX 1080 Ti - Pascal)")
    print("=" * 65)
    print(f"Active Channels Tested     : {len(manager.streams)}")
    print(f"Average Batch Cycle Time   : {avg_cycle:.2f} ms")
    print(f"Average Per-Camera Latency : {avg_per_cam:.2f} ms")
    print(f"Pipeline Processing Rate   : {effective_fps:.1f} cycles/sec")
    print(f"Total Objects Detected     : {total_detections_count}")
    print("=" * 65)

if __name__ == "__main__":
    main()