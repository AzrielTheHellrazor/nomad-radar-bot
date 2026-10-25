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
USD_TO_TRY_FALLBACK = float(os.getenv("USD_TO_TRY", "49.68"))
EUR_TO_USD_FALLBACK = float(os.getenv("EUR_TO_USD", "1.12"))
_CACHED_FX: dict | None = None


def get_fx_rates() -> dict:
    """
    Canlı EUR -> TRY, USD -> TRY ve EUR -> USD döviz kurlarını ücretsiz açık API'den
    (open.er-api.com) çeker ve önbellekte tutar.
    """
    global _CACHED_FX
    if _CACHED_FX is not None:
        return _CACHED_FX
    try:
        import httpx

        resp = httpx.get("https://open.er-api.com/v6/latest/EUR", timeout=3.5)
        if resp.status_code == 200:
            rates = resp.json().get("rates", {})
            eur_try = float(rates.get("TRY", EUR_TO_TRY_FALLBACK))
            eur_usd = float(rates.get("USD", EUR_TO_USD_FALLBACK))
            usd_try = round(eur_try / max(0.01, eur_usd), 2)
            if eur_try > 40.0:
                _CACHED_FX = {
                    "EUR_TRY": round(eur_try, 2),
                    "USD_TRY": usd_try,
                    "EUR_USD": round(eur_usd, 2),
                }
                return _CACHED_FX
    except Exception:
        pass
    _CACHED_FX = {
        "EUR_TRY": EUR_TO_TRY_FALLBACK,
        "USD_TRY": USD_TO_TRY_FALLBACK,
        "EUR_USD": EUR_TO_USD_FALLBACK,
    }
    return _CACHED_FX


def get_eur_to_try_rate() -> float:
    return get_fx_rates()["EUR_TRY"]


def get_usd_to_try_rate() -> float:
    return get_fx_rates()["USD_TRY"]

# Optional External Flight APIs (Kiwi Tequila, Amadeus, SerpApi, Travelpayouts)
TEQUILA_API_KEY = os.getenv("TEQUILA_API_KEY", "")
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET", "")
SERPAPI_API_KEY: str = os.getenv("SERPAPI_API_KEY", "").strip()
SERPAPI_KEY = SERPAPI_API_KEY or os.getenv("SERPAPI_KEY", "")
TRAVELPAYOUTS_TOKEN: str = os.getenv("TRAVELPAYOUTS_TOKEN", "").strip()

DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "nomad_radar.db"))
SCAN_INTERVAL_MINUTES = int(os.getenv("SCAN_INTERVAL_MINUTES", "30"))
