import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///steam_deals.db").strip()
CHECK_INTERVAL_HOURS: float = float(os.getenv("CHECK_INTERVAL_HOURS", "1.0"))
DEFAULT_CURRENCY: str = os.getenv("DEFAULT_CURRENCY", "us").strip().lower()
DEFAULT_COUNTRY: str = os.getenv("DEFAULT_COUNTRY", "US").strip().upper()
