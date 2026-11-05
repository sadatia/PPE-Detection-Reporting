import os
import time
import queue
import logging
import threading
import requests
import base64
import cv2
from concurrent.futures import ThreadPoolExecutor

class AlertDispatcher:
    """Dispatches photo alerts to Telegram and WhatsApp, plus Barix audio triggers."""

    def __init__(self, cameras_cfg, rules_cfg):
        self.camera_map = {c["id"]: c for c in cameras_cfg.get("cameras", [])}
        self.messages = rules_cfg.get("detection_rules", {}).get("barix_messages", {})

        # Telegram Configuration
        self.tg_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "8452949681:AAHBwX0jLW_T9YQKQeoFVeg9gCVvlBEvxmw").strip()
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID", "-5463461340").strip()

        # WAHA WhatsApp Configuration
        self.waha_endpoint = os.getenv("WAHA_ENDPOINT", "http://127.0.0.1:3000/api/sendImage").strip()
        self.wa_api_key = os.getenv("WAHA_API_KEY", "ptjv4455").strip()
        self.wa_chat_id = os.getenv("WHATSAPP_CHAT_ID", "120363432286181800@g.us").strip()

        # Barix Control Room Audio
        self.barix_user = os.getenv("BARIX_USER", "admin").strip()
        self.barix_pass = os.getenv("BARIX_PASSWORD", "ptjv4455").strip()

        self.last_horn_times = {}
        self.horn_cooldown = 15.0

        self.session = requests.Session()
        self.notify_queue = queue.Queue(maxsize=150)
        self.dispatch_pool = ThreadPoolExecutor(max_workers=8)

        # Background worker thread
        self.worker_thread = threading.Thread(target=self._notification_worker, daemon=True)
        self.worker_thread.start()

    def trigger_toa_speaker(self, cam_id, violation_type):
        """Actuates Barix horn relay / chime."""
        now = time.time()
        if now - self.last_horn_times.get(cam_id, 0) < self.horn_cooldown:
            return

        cam_info = self.camera_map.get(cam_id, {})
        barix_ip = cam_info.get("barix_ip", "10.220.148.13")
        self.last_horn_times[cam_id] = now

        def _broadcast():
            try:
                url = f"http://{barix_ip}/rc.cgi?c=play,1"
                self.session.get(url, auth=(self.barix_user, self.barix_pass), timeout=2.0)
                logging.info(f"[HORN] Actuated Barix horn for {cam_id} at {barix_ip}")
            except Exception as e:
                logging.debug(f"[HORN] Barix audio trigger failed: {e}")

        self.dispatch_pool.submit(_broadcast)

    def send_telegram_alert(self, cam_id, violation_type, snapshot_frame=None):
        """Pushes alert frame into dispatch queue."""
        try:
            img_bytes = None
            if snapshot_frame is not None:
                ret, buf = cv2.imencode(".jpg", snapshot_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if ret:
                    img_bytes = buf.tobytes()

            self.notify_queue.put((cam_id, violation_type, img_bytes))
        except Exception as e:
            logging.error(f"[!] Error enqueuing alert: {e}")

    def _notification_worker(self):
        while True:
            try:
                task = self.notify_queue.get()
                if task is None:
                    break

                cam_id, violation_type, img_bytes = task
                cam_info = self.camera_map.get(cam_id, {})
                zone_name = cam_info.get("zone", "Safety Zone")

                # HTML for Telegram
                caption_tg = (
                    f"🚨 <b>PTJV SAFETY COMPLIANCE ALERT</b>\n\n"
                    f"📍 <b>Camera:</b> {cam_id}\n"
                    f"🏗 <b>Zone:</b> {zone_name}\n"
                    f"⚠️ <b>Violation:</b> {violation_type}\n"
                    f"⏰ <b>Time:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # WhatsApp native markdown (*bold*)
                caption_wa = (
                    f"🚨 *PTJV SAFETY COMPLIANCE ALERT*\n\n"
                    f"📍 *Camera:* {cam_id}\n"
                    f"🏗 *Zone:* {zone_name}\n"
                    f"⚠️ *Violation:* {violation_type}\n"
                    f"⏰ *Time:* {time.strftime('%Y-%m-%d %H:%M:%S')}"
                )

                # Dispatch Telegram in pool
                if self.tg_bot_token and self.tg_chat_id:
                    self.dispatch_pool.submit(self._dispatch_telegram, caption_tg, img_bytes)

                # Dispatch WAHA in pool
                if self.waha_endpoint and self.wa_chat_id:
                    self.dispatch_pool.submit(self._dispatch_waha, caption_wa, img_bytes)

                self.notify_queue.task_done()
            except Exception as e:
                logging.error(f"[!] Notification worker exception: {e}")

    def _dispatch_telegram(self, caption, img_bytes):
        url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendPhoto"
        try:
            if img_bytes and len(img_bytes) > 100:
                files = {"photo": ("violation.jpg", img_bytes, "image/jpeg")}
                data = {
                    "chat_id": self.tg_chat_id,
                    "caption": caption,
                    "parse_mode": "HTML"
                }
                resp = self.session.post(url, data=data, files=files, timeout=20.0)
                if resp.status_code == 200:
                    logging.info(f"[+] Telegram alert photo delivered to chat {self.tg_chat_id}")
                    return
                else:
                    logging.warning(f"[-] Telegram sendPhoto rejected ({resp.status_code}): {resp.text}")

            msg_url = f"https://api.telegram.org/bot{self.tg_bot_token}/sendMessage"
            resp = self.session.post(msg_url, json={
                "chat_id": self.tg_chat_id,
                "text": caption,
                "parse_mode": "HTML"
            }, timeout=5.0)

            if resp.status_code == 200:
                logging.info(f"[+] Telegram text alert delivered to {self.tg_chat_id}")
            else:
                logging.error(f"[!] Telegram sendMessage rejected ({resp.status_code}): {resp.text}")

        except Exception as e:
            logging.error(f"[!] Telegram network error: {e}")

    def _dispatch_waha(self, caption, img_bytes):
        """Sends base64 encoded photo alert to WhatsApp via WAHA container."""
        try:
            if not img_bytes:
                return

            b64_data = base64.b64encode(img_bytes).decode("utf-8")
            payload = {
                "session": "default",
                "chatId": self.wa_chat_id,
                "caption": caption,
                "file": {
                    "mimetype": "image/jpeg",
                    "filename": "violation.jpg",
                    "data": b64_data
                }
            }
            headers = {
                "Content-Type": "application/json",
                "X-Api-Key": self.wa_api_key
            }
            resp = self.session.post(self.waha_endpoint, json=payload, headers=headers, timeout=12.0)
            if resp.status_code in [200, 201]:
                logging.info(f"[+] WhatsApp photo alert delivered to {self.wa_chat_id}")
            else:
                logging.warning(f"[-] WAHA response error ({resp.status_code}): {resp.text}")
        except Exception as e:
            logging.error(f"[!] WhatsApp dispatch exception: {e}")
