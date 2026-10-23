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
EUR_TO_TRY_FALLBACK = float(os.getenv("EUR_TO_TRY", "55.76"))
_CACHED_EUR_TO_TRY: float | None = None


def get_eur_to_try_rate() -> float:
    """
    Canlı EUR -> TRY döviz kurunu ücretsiz açık API'den (open.er-api.com) çeker
    ve çalışma süresince önbellekte tutar. Çevrimdışıysa güncel 55.76 TL baz kurunu kullanır.
    """
    global _CACHED_EUR_TO_TRY
    if _CACHED_EUR_TO_TRY is not None:
        return _CACHED_EUR_TO_TRY
    if os.getenv("EUR_TO_TRY"):
        _CACHED_EUR_TO_TRY = float(os.getenv("EUR_TO_TRY", "55.76"))
        return _CACHED_EUR_TO_TRY
    try:
        import httpx

        resp = httpx.get("https://open.er-api.com/v6/latest/EUR", timeout=3.5)
        if resp.status_code == 200:
            try_rate = resp.json().get("rates", {}).get("TRY")
            if try_rate and float(try_rate) > 40.0:
                _CACHED_EUR_TO_TRY = round(float(try_rate), 2)
                return _CACHED_EUR_TO_TRY
    except Exception:
        pass
    _CACHED_EUR_TO_TRY = EUR_TO_TRY_FALLBACK
    return _CACHED_EUR_TO_TRY

# Optional External Flight APIs (Kiwi Tequila, Amadeus, SerpApi)
TEQUILA_API_KEY = os.getenv("TEQUILA_API_KEY", "")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "nomad_radar.db"))
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
