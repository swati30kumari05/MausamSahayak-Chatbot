"""Configuration management for MausamSahayak (Swati's Bot).

Loads settings from environment variables and an optional .env file.
Validates necessary variables and provides safe defaults for development/mock mode.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically load .env from current working directory or package root
_env_path = Path(".env")
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()


class Config:
    """Application settings with clean defaults for student development & viva."""

    # Telegram Bot Token from BotFather
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

    # Backend API URL (Manas's REST server)
    API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")

    # Development Mock API flag: if True, bot returns realistic mock data without requiring running backend
    MOCK_API = os.environ.get("MOCK_API", "true").lower() in ("true", "1", "yes")

    # SQLite Database for storing user preferences, location, and alert subscriptions
    BOT_DB = os.environ.get("BOT_DB", "bot.db")

    # Alert Polling Interval in seconds
    ALERT_POLL_S = int(os.environ.get("ALERT_POLL_S", "60"))

    # SMS Fallback Configuration
    # Options: "dryrun" (default, logs only) or "twilio"
    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "dryrun").lower()
    TWILIO_SID = os.environ.get("TWILIO_SID", "")
    TWILIO_TOKEN = os.environ.get("TWILIO_TOKEN", "")
    TWILIO_FROM = os.environ.get("TWILIO_FROM", "")

    # Viva Demo Scenario: 'normal', 'red_alert', 'stale_sensor', 'backend_down'
    DEMO_SCENARIO = os.environ.get("DEMO_SCENARIO", "normal").lower()

    @classmethod
    def validate_for_live(cls) -> list[str]:
        """Check for configuration issues when running live with Telegram."""
        issues = []
        if not cls.TELEGRAM_TOKEN:
            issues.append("TELEGRAM_TOKEN is missing. Set it in .env or environment.")
        if not cls.MOCK_API and not cls.API_BASE_URL:
            issues.append("API_BASE_URL is missing while MOCK_API is false.")
        if cls.SMS_PROVIDER == "twilio":
            if not cls.TWILIO_SID or not cls.TWILIO_TOKEN or not cls.TWILIO_FROM:
                issues.append("Twilio SMS credentials incomplete (TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM).")
        return issues
