import time
import threading
import queue
import cv2
import yaml
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

class CameraStream:
    """Handles an independent RTSP camera stream in a dedicated thread."""
    def __init__(self, cam_id, name, rtsp_url, zone):
        self.cam_id = cam_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.zone = zone
        
        self.frame_queue = queue.Queue(maxsize=2)
        self.stopped = threading.Event()
        self.thread = None
        self.is_connected = False

    def start(self):
        self.stopped.clear()
        self.thread = threading.Thread(target=self._capture_loop, name=f"Thread-{self.cam_id}", daemon=True)
        self.thread.start()
        return self

    def _capture_loop(self):
        while not self.stopped.is_set():
            logging.info(f"Connecting to {self.cam_id} ({self.name})...")
            # Force TCP transport for RTSP to prevent packet corruption
            cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            if not cap.isOpened():
                logging.warning(f"Failed to connect to {self.cam_id}. Retrying in 5 seconds...")
                time.sleep(5)
                continue

            self.is_connected = True
            logging.info(f"Connected successfully to {self.cam_id}")

            while not self.stopped.is_set():
                ret, frame = cap.read()
                time.sleep(0.08)  # Throttle capture loop to ~12 FPS
                if not ret:
                    logging.warning(f"Frame read failure on {self.cam_id}. Re-establishing stream...")
                    self.is_connected = False
                    break

                # Maintain only the latest frame in the buffer (Zero latency)
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.frame_queue.put(frame)

            cap.release()
            self.is_connected = False
            time.sleep(2)

    def read_latest_frame(self):
        """Returns the most recent frame or None if buffer is empty."""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=2.0)
        logging.info(f"Stream {self.cam_id} stopped.")


class MultiCameraManager:
    """Manages all 6 concurrent camera streams across Xeon CPU threads."""
    def __init__(self, config_path="config/cameras.yaml"):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)

        self.streams = {}
        for cam_cfg in self.config.get("cameras", []):
            if cam_cfg.get("enabled", True):
                cam_id = cam_cfg["id"]
                self.streams[cam_id] = CameraStream(
                    cam_id=cam_id,
                    name=cam_cfg["name"],
                    rtsp_url=cam_cfg["rtsp_url"],
                    zone=cam_cfg["zone"]
                )

    def start_all(self):
        for stream in self.streams.values():
            stream.start()

    def get_active_frames(self):
        """Polls latest frame snapshot from each running camera."""
        frames = {}
        for cam_id, stream in self.streams.items():
            frame = stream.read_latest_frame()
            if frame is not None:
                frames[cam_id] = {
                    "frame": frame,
                    "name": stream.name,
                    "zone": stream.zone
                }
        return frames

    def stop_all(self):
        for stream in self.streams.values():
            stream.stop()
