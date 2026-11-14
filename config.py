import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# O'zbekiston (Farg'ona) vaqt zonasi
UZB_TZ = ZoneInfo("Asia/Tashkent")

def get_now() -> datetime:
    """O'zbekiston bo'yicha aniq hozirgi vaqt"""
    return datetime.now(UZB_TZ)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Farg'ona koordinatalari
CITY = os.getenv("CITY", "Fergana")
COUNTRY = os.getenv("COUNTRY", "Uzbekistan")
LATITUDE = float(os.getenv("LATITUDE", "40.3864"))
LONGITUDE = float(os.getenv("LONGITUDE", "71.7864"))

# Namoz nomlari (o'zbekcha)
PRAYER_NAMES = {
    "Fajr": "🌅 Bomdod",
    "Sunrise": "🌄 Quyosh chiqishi",
    "Dhuhr": "☀️ Peshin",
    "Asr": "🌤 Asr",
    "Maghrib": "🌅 Shom",
    "Isha": "🌙 Xufton",
}

# Tahajjud vaqti (Bomdoddan 1 soat oldin)
TAHAJJUD_MINUTES_BEFORE_FAJR = 60

# Ogohlantirish intervali (soniyada)
ALERT_INTERVAL_SECONDS = 30
