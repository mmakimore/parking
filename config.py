"""
Конфигурация ParkingBot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Database
DATABASE_PATH = os.getenv("DATABASE_PATH", "parking.db")

# Admin settings
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "qwerty123")
ADMIN_SESSION_HOURS = 24

# Limits
MAX_SPOTS_PER_USER = 10
MAX_ACTIVE_BOOKINGS = 5
MIN_ACTION_INTERVAL = 1  # секунды между действиями

# Pricing limits
MIN_PRICE_PER_HOUR = 1
MAX_PRICE_PER_HOUR = 10000

# Banks list
BANKS = [
    "Сбербанк",
    "Тинькофф",
    "ВТБ",
    "Альфа-Банк",
    "Газпромбанк",
    "Райффайзен",
    "Открытие",
    "Другой"
]

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
