#!/usr/bin/env python3
import os
import sqlite3
import datetime
import requests
import yaml
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH = "/home/zeus/ai-cctv/data/cctv_audit.db"
CAMERAS_CFG = "/home/zeus/ai-cctv/config/cameras.yaml"

TG_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8452949681:AAHBwX0jLW_T9YQKQeoFVeg9gCVvlBEvxmw")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-5463461340")
WAHA_ENDPOINT = os.getenv("WAHA_ENDPOINT", "http://127.0.0.1:3000/api/sendText")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "ptjv4455")
WA_CHAT_ID = os.getenv("WHATSAPP_CHAT_ID", "120363432286181800@g.us")

def generate_report():
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Query daily total
    cursor.execute("""
        SELECT COUNT(*) FROM violations 
        WHERE DATE(timestamp) = ?
    """, (today_str,))
    total_violations = cursor.fetchone()[0]

    # Query breakdown by violation type
    cursor.execute("""
        SELECT violation_type, COUNT(*) 
        FROM violations 
        WHERE DATE(timestamp) = ?
        GROUP BY violation_type 
        ORDER BY COUNT(*) DESC
    """, (today_str,))
    type_stats = cursor.fetchall()

    # Query breakdown by camera
    cursor.execute("""
        SELECT camera_id, COUNT(*) 
        FROM violations 
        WHERE DATE(timestamp) = ?
        GROUP BY camera_id 
        ORDER BY COUNT(*) DESC
    """, (today_str,))
    cam_stats = cursor.fetchall()
    conn.close()

    # Format Report Message
    type_rows = "\n".join([f"• *{vtype.upper()}:* {count} incident(s)" for vtype, count in type_stats]) or "• None recorded"
    cam_rows = "\n".join([f"• `{cam}`: {count} incident(s)" for cam, count in cam_stats]) or "• None recorded"

    report_text = (
        f"📊 *PTJV DAILY SAFETY COMPLIANCE REPORT*\n"
        f"📅 *Date:* {today_str}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🚨 *Total Non-Compliance Events:* *{total_violations}*\n\n"
        f"🔍 *Breakdown by Violation:*\n{type_rows}\n\n"
        f"📍 *Top Non-Compliant Zones:*\n{cam_rows}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ _Generated automatically by PTJV Surveillance AI Core_"
    )

    return report_text

def dispatch_report(text):
    # 1. Dispatch to Telegram
    try:
        tg_url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
        resp = requests.post(tg_url, json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if resp.status_code == 200:
            logging.info("[+] Daily report sent to Telegram.")
        else:
            logging.warning(f"[-] Telegram dispatch error ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"[!] Telegram report error: {e}")

    # 2. Dispatch to WhatsApp
    try:
        wa_url = "http://127.0.0.1:3000/api/sendText"
        payload = {
            "session": "default",
            "chatId": WA_CHAT_ID,
            "text": text
        }
        headers = {"X-Api-Key": WAHA_API_KEY, "Content-Type": "application/json"}
        resp = requests.post(wa_url, json=payload, headers=headers, timeout=10)
        if resp.status_code in [200, 201]:
            logging.info("[+] Daily report sent to WhatsApp.")
        else:
            logging.warning(f"[-] WhatsApp dispatch error ({resp.status_code}): {resp.text}")
    except Exception as e:
        logging.error(f"[!] WhatsApp report error: {e}")

if __name__ == "__main__":
    report = generate_report()
    dispatch_report(report)
