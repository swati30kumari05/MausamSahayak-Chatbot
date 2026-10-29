# MausamSahayak (मौसमसहायक) 🌱
### Bilingual IoT Smart Agriculture Telegram Chatbot

[![Chatbot Test Suite](https://github.com/swati30kumari05/MausamSahayak-Chatbot/actions/workflows/ci.yml/badge.svg)](https://github.com/swati30kumari05/MausamSahayak-Chatbot/actions)
[![Telegram Bot](https://img.shields.io/badge/Telegram-MausamSahayak__bot-blue?logo=telegram)](https://t.me/MausamSahayak_bot)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-brightgreen)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Live%20%26%20Verified-success)]()

> **Live Telegram Bot:** [@MausamSahayak_bot](https://t.me/MausamSahayak_bot)  
> **Author & Developer:** Swati Kumari  
> **Project Role:** Farmer-Facing Conversational Layer, Bilingual NLP, Alert Mechanism & Advisory Delivery

---

## 📖 Executive Summary

**MausamSahayak** is an agricultural conversational assistant developed by **Swati Kumari** as the central user interface of an IoT smart agriculture capstone project:  
*“IoT-Based Temperature and Humidity Monitoring System with Real-Time Data Transmission and Automatic Alert Mechanism.”*

The chatbot bridges complex backend data pipelines and rural farmers by translating live sensor streams, rainfall metrics, flood risks, and agricultural normals into simple, actionable guidance in **Hindi** (हिंदी) and **English**.

---

## 👥 Five-Member Team Architecture & Boundaries

```
[ AGRICULTURAL FIELD ]
         │
         ▼
[ Nishant ] ──► IoT Sensors (DHT22/BME280, Soil Moisture, Rain Gauge, Ultrasonic Water Level) + ESP32
         │
         ▼ (Wi-Fi / GSM / LoRa via MQTT)
[ Manas ]   ──► Backend Server, MQTT Broker, Database & REST APIs (/api/nodes, /api/risk, /api/crop-advice)
         │
         ▼ (Analytical Engines)
[ Parul ]   ──► Risk & Crop Engine (Heat Risk, Flood/Waterlogging Risk, Crop Suitability Scoring)
         │
         ▼ (External Data Sources & Validation)
[ Anil ]    ──► External Weather APIs, IMD/CWC Normals, Field Site Validation & Case Studies
         │
         ▼ (REST API Interface)
[ Swati ]   ──► MausamSahayak Telegram Chatbot (Bilingual NLP, Alerts, Advisories & Farmer Menu)
         │
         ▼
     [ FARMER ]
```

### 🛡️ Architectural Boundary:
The chatbot **never** communicates directly with ESP32 hardware. Following clean distributed system design, it interacts exclusively with backend REST APIs (`/api/nearest`, `/api/nodes/<id>/risk`, `/api/crop-advice`, `/api/alerts`), ensuring loose coupling, fault tolerance, and independent testability.

---

## ✨ Key Features & Capabilities

1. **🌐 Bilingual Conversational AI (Hindi & English)**:
   - Understands queries in Devanagari Hindi, Roman Hinglish, and English.
   - Automatically detects the user's query language and responds in the same language.

2. **📱 One-Tap Persistent Farmer Menu**:
   - An interactive reply keyboard with large, clear buttons eliminating the need for typing:
     - 🌦 **Current Weather** (*ताज़ा मौसम*)
     - 🔮 **Weather Forecast** (*पूर्वानुमान*)
     - 🌱 **Field Sensors** (*खेत की स्थिति*)
     - 🌾 **Crop Advice** (*फसल सलाह*)
     - ⚠️ **Risk Alerts** (*जोखिम स्थिति*)
     - 📍 **Share Location** (*लोकेशन साझा करें*)
     - 🔔 **Alerts / Subscribe** (*स्वचालित अलर्ट*)
     - ℹ️ **Help Guide** (*सहायता*)

3. **🌡 Live Field IoT Telemetry**:
   - Fetches and displays real-time field measurements:
     - Ambient Temperature (°C)
     - Relative Humidity (%)
     - 24-hour Rainfall Accumulation (mm)
     - Soil Moisture Percentage (%)
     - River / Drain Water Level (cm)

4. **⚠️ Multi-Tier Risk Advisories & Safety Rules**:
   - `GREEN`: Nominal conditions.
   - `UNKNOWN`: Sensor silent or offline (>30 min) — **strictly never presented as safe**.
   - `YELLOW`: Be aware.
   - `ORANGE`: Be prepared.
   - `RED`: Critical threat level — incorporates national emergency helplines (**112**, **1078**) and State Disaster Management Authority guidelines.

5. **🌾 Intelligent Crop Recommendation**:
   - Recommends suitable crops based on season (Kharif, Rabi, Zaid), irrigation type, and environmental thresholds with explicit local KVK disclaimers.

6. **🔔 Automated Proactive Alerts & SMS Fallback**:
   - Background polling task runs every 60 seconds to detect risk escalations.
   - Safe `DryRunSender` validates Indian mobile numbers (`+91XXXXXXXXXX`) and prepares SMS payloads for critical RED alerts.

7. **🧪 Dual-Mode Engine (Mock Mode & Live Mode)**:
   - **Mock Mode (`MOCK_API=true`)**: High-fidelity offline simulation with switchable viva scenarios (`normal`, `red_alert`, `stale_sensor`, `backend_down`).
   - **Live Mode (`MOCK_API=false`)**: Directly connects to the live Flask REST server.

---

## 📂 Repository Structure

```text
MausamSahayak-Chatbot/
├── main.py                  # Application entry point
├── requirements.txt         # Dependencies (python-telegram-bot, python-dotenv, requests)
├── .env.example             # Environment configuration template
├── .gitignore               # Protects secrets and databases from commits
├── README.md                # Comprehensive project documentation
├── .github/
│   └── workflows/
│       └── ci.yml           # Automated GitHub Actions test runner
└── swati_bot/
    ├── __init__.py          # Package initialization
    ├── bot.py               # Telegram bot handlers & polling engine
    ├── logic.py             # Pure conversation & business logic
    ├── api_client.py        # Centralized REST API client + mock engine
    ├── intents.py           # NLP intent matching & language detector
    ├── formatters.py        # Natural language advisory formatters
    ├── i18n.py              # Bilingual translation dictionaries & alert templates
    ├── alerts.py            # Alert transition logic & anti-spam planner
    ├── sms.py               # SMS fallback dispatcher (dry-run safe)
    ├── store.py             # SQLite storage for user states & subscriptions
    ├── config.py            # Configuration loader
    └── tests/
        └── test_bot.py      # 16 comprehensive standalone unit tests
```

---

## 🚀 Quickstart Guide

### 1. Clone the Repository
```bash
git clone https://github.com/swati30kumari05/MausamSahayak-Chatbot.git
cd MausamSahayak-Chatbot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure `.env`
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your Telegram bot token from `@BotFather`:
```ini
TELEGRAM_TOKEN=your_telegram_bot_token_here
MOCK_API=true
DEMO_SCENARIO=normal
```

### 4. Run the Chatbot
```bash
python main.py
```
Open Telegram, search for your bot, and send **`/start`**!

---

## 🧪 Unit Testing

A comprehensive, 100% standalone test suite validates all features without external network calls:

```bash
python -m unittest swati_bot.tests.test_bot
```

*Expected Output:*
```text
Ran 16 tests in 0.025s
OK
```

---

## 🎓 Common Queries & Answers

**Q1: What was your specific responsibility in the capstone project?**  
> *A:* I developed **MausamSahayak**, the farmer-facing conversational layer. My module consumes backend REST APIs to deliver live IoT sensor data, weather forecasts, flood/heat risk advisories, and crop recommendations in Hindi and English via an interactive Telegram chatbot.

**Q2: Why choose Telegram instead of WhatsApp?**  
> *A:* Telegram provides an open, cost-free Bot API with native support for persistent reply keyboards, location sharing, inline callback buttons, and automated polling. WhatsApp Cloud API requires Meta Business verification, paid webhooks, and complex server registration, which is unfeasible for an academic prototype.

**Q3: How does your chatbot ensure that offline sensors don't give farmers a false sense of safety?**  
> *A:* If a field sensor fails or stops reporting for more than 30–60 minutes, the status escalates to `UNKNOWN`. Our bot strictly adheres to the rule: **UNKNOWN risk is never treated as SAFE**. The bot warns the farmer that data is unconfirmed and directs them to official IMD/CWC updates.

**Q4: How does the bot switch between mock evaluation and the real backend?**  
> *A:* The `ApiClient` contains a centralized switch controlled by `MOCK_API` in `.env`. When `true`, it generates scientifically plausible agricultural data and switchable viva scenarios (`red_alert`, `stale_sensor`, `backend_down`). When `false`, it connects seamlessly to the backend REST API.

**Q5: How are critical emergency alerts handled?**  
> *A:* On high-risk escalations (such as river levels exceeding the danger mark), the bot pushes an immediate Telegram alert with official helpline numbers (**112**, **1078**). If the farmer has registered an Indian mobile number, an SMS fallback payload is prepared to ensure delivery even without mobile data.

---

## 📄 License
This project is licensed under the MIT License.
