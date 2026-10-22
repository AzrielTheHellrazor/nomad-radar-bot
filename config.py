import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_ADMIN_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0") or "0")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
ENABLE_AI = os.getenv("ENABLE_AI", "0") == "1"
MIN_DISCOUNT_PCT = int(os.getenv("MIN_DISCOUNT_PCT", "35"))
EUR_TO_TRY = float(os.getenv("EUR_TO_TRY", "38.0"))

# Optional External Flight APIs (Kiwi Tequila, Amadeus, SerpApi)
TEQUILA_API_KEY = os.getenv("TEQUILA_API_KEY", "")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "nomad_radar.db"))
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
