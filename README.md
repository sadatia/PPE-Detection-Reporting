# PTJV MPDP-PK1 AI-CCTV PPE Detection & Surveillance System

An enterprise-grade, edge-deployed AI surveillance and automated safety enforcement system built for the **Matarbari Port Development Project (PTJV MPDP-PK1)**. 

The system provides real-time multi-camera PPE compliance tracking, smoke/fire optical detection, edge hardware audio alerts via IP horn speakers, incident logging to network-attached storage, and multi-channel instant notifications (Telegram & WhatsApp).

---

## 🏗️ System Architecture

[ 6x Dahua / Hikvision Cameras ]
│ (RTSP Hardware Sub-streams: H.264/H.265)
▼
[ AI Ingestion Engine ] ── (Python 3 / OpenCV / CUDA)
│
[ Safety Inference Core ] ── (YOLOv8s FP16 on GTX 1080 Ti ~2.1ms)
│
┌─────────┴─────────────────────────────────────────┐
│                                                   │
▼                                                   ▼
[ Automated Alerting Pipeline ]             [ Web Dashboard & Telemetry ]
• Barix IP Horns (10.220.148.13/.16)        • Flask UI (Port 5050 / Reverse Proxy)
• Telegram Bot API Alert Dispatch           • Low-Res Real-Time Video Grid
• WhatsApp Instant Media Dispatch           • Real-time Rules Hot-Reloading
• Synology CIFS Audit Archive               • Hardware Performance & NVDEC Matrix


---

## 🚀 Key Features

* **Real-Time Edge Inference**: Accelerated YOLOv8s object detection running on an NVIDIA GeForce GTX 1080 Ti (~2.1ms inference latency per frame).
* **Multi-Class PPE Tracking**:
  * Hard Hats / Safety Helmets (`helmet`)
  * High-Visibility Reflective Vests (`vest`)
  * Steel-Toe Safety Boots (`boot`)
  * Fire & Smoke Plumes (`fire`)
  * Exclusion Geofence Intrusion
* **Optimized Bandwidth & Resource Consumption**:
  * Direct hardware sub-stream fetching (`subtype=1` / Hikvision ISAPI channel `102`) to ensure lightweight multi-stream ingestion (<25 KB per live frame).
* **Physical & Digital Alerting**:
  * **Barix IP Speakers**: Automated voice chime/warning actuation over the site PA network.
  * **Instant Messengers**: Telegram and WhatsApp alerts containing timestamped violation snapshots and zone identification.
  * **Synology CIFS Storage**: Long-term snapshot archival mounted at `/mnt/synology_cctv` with auto-purge retention policies.
* **Interactive Configuration**: Real-time configuration drawer in the web interface for adjusting confidence thresholds and toggling classes on the fly with persistent synchronization to `config/rules.yaml`.

---

## 📹 Monitored Camera Zones

| Camera ID | Zone Name | Camera Make / Type | Sub-Stream Resolution | Associated Barix IP |
| :--- | :--- | :--- | :--- | :--- |
| **CAM_01** | Zone A - Access Control | Dahua 4MP | $640 \times 360$ | `10.220.148.13` |
| **CAM_02** | Zone B - Hostel Area | Dahua 4MP | $640 \times 360$ | `10.220.148.13` |
| **CAM_03** | Zone PLA1 - PTJV Gate | Dahua 4MP | $640 \times 360$ | `10.220.148.13` |
| **CAM_04** | Zone D - MPDP Main Gate Area | Dahua 4MP | $640 \times 360$ | `10.220.148.13` |
| **CAM_05** | Zone A - Pumping Station Area | Hikvision 4MP | $640 \times 360$ | `10.220.148.13` |
| **CAM_06** | Hostel Area / Kamachan Gate | Dahua 4MP | $640 \times 360$ | `10.220.148.16` |

---

## 📂 Repository Structure

├── config/
│   ├── cameras.yaml            # RTSP streams, IP addresses, zones, and ROI definitions
│   └── rules.yaml              # Detection thresholds, debounce timings, and speaker assignments
├── core/
│   ├── alerting/               # Debouncers, Barix horn controllers, and message dispatchers
│   ├── inference/              # YOLOv8 engine wrapper, tracker, and rule reloaders
│   ├── ingestion/              # OpenCV multi-threaded stream managers
│   └── storage/                # SQLite audit logger and Synology snapshot handler
├── data/
│   ├── cctv_audit.db           # SQLite database for infractions and event history
│   └── warning.wav             # Alert audio files for broadcast
├── scripts/
│   ├── daily_safety_report.py  # Shift and compliance reporting scripts
│   └── cleanup_recordings.sh   # Storage disk retention scripts
├── web/
│   ├── app.py                  # Flask application serving APIs and camera feeds
│   └── templates/
│       └── index.html          # Real-time dashboard, matrix grid, and config drawer
├── main.py                     # Main execution loop for inference daemon
└── requirements.txt            # Python dependencies


---

## ⚙️ Installation & Setup

### 1. Prerequisites
* Ubuntu 22.04 / 24.04 LTS
* NVIDIA CUDA Drivers & cuDNN installed
* FFmpeg & OpenCV system libraries

### 2. Python Environment
```bash
git clone git@github.com:sadatia/PPE-Detection-Reporting.git /home/zeus/ai-cctv
cd /home/zeus/ai-cctv

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
3. Systemd Service Management
The platform runs as two decoupled systemd services:

Inference Engine Daemon:

Bash
sudo systemctl restart cctv-analytics.service
sudo journalctl -u cctv-analytics.service -f
Web UI Dashboard:

Bash
sudo systemctl restart cctv-dashboard.service
sudo journalctl -u cctv-dashboard.service -f
🔒 Security & Environment Considerations
Excluded Binaries: Model weights (.pt), raw video recordings (.mp4), and snapshot caches are ignored via .gitignore to keep the repository lightweight.

Credentials: Never commit .env or production credentials. Store sensitive webhook URLs and camera passwords in environment variables or uncommitted configuration overlays.

📜 License
Internal operations software for the Matarbari Port Development Project (PTJV MPDP-PK1). All rights reserved.
EOF


---

### Step 2: Commit and Push the `README.md` to GitHub

Once the file is generated, push it directly to your repository:

```bash
cd /home/zeus/ai-cctv
git add README.md
git commit -m "docs: add comprehensive system architecture and operations README"
git push origin main