import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx

import config

logger = logging.getLogger(__name__)


def redact_secrets(text: str) -> str:
    """
    Redacts api keys, tokens, and credentials from log strings and URLs.
    Never exposes sensitive tokens or user-specific secrets in logs.
    """
    if not text:
        return ""
    # Redact query parameters matching api_key=..., token=..., key=..., secret=...
    sanitized = re.sub(
        r"([?&](?:api_key|apikey|token|access_token|key|secret)=)[^&\s\"']+",
        r"\1[REDACTED]",
        str(text),
    )
    # Redact configured known secrets if non-empty
    for secret in (
        getattr(config, "SERPAPI_API_KEY", ""),
        getattr(config, "SERPAPI_KEY", ""),
        getattr(config, "TRAVELPAYOUTS_TOKEN", ""),
        getattr(config, "TELEGRAM_BOT_TOKEN", ""),
        getattr(config, "GEMINI_API_KEY", ""),
        getattr(config, "OPENROUTER_KEY", ""),
        getattr(config, "TEQUILA_API_KEY", ""),
    ):
        if secret and len(secret) >= 4:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    return sanitized


def _log_err(msg: str, exc: Optional[Exception] = None) -> None:
    safe_msg = redact_secrets(msg)
    if exc is not None:
        safe_exc = redact_secrets(str(exc))
        logger.error(f"{safe_msg}: {safe_exc}")
    else:
        logger.error(safe_msg)


def iso_to_ddmmyyyy(date_iso: str) -> str:
    """
    Converts YYYY-MM-DD to dd/mm/yyyy for Kiwi search.
    If already formatted, returns cleaned string.
    """
    if not date_iso:
        return ""
    date_clean = date_iso.strip()
    if "-" in date_clean:
        parts = date_clean.split("-")
        if len(parts) == 3 and len(parts[0]) == 4:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return date_clean


class KiwiMCPClient:
    """
    Kiwi Official Keyless MCP client (https://mcp.kiwi.com — JSON-RPC 2.0).
    Provides live flight search over keyless MCP tools/call interface.
    Disabled automatically when LIVE_FLIGHTS_HTTP != 1.
    """

    def __init__(self, base_url: str = "https://mcp.kiwi.com", timeout: float = 9.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def parse_response_payload(raw_text: Any) -> List[Dict[str, Any]]:
        """
        Parses JSON-RPC 2.0 SSE or direct JSON response from Kiwi MCP tool call `search-flight`.
        Extracts price in EUR, carrier names, intermediate stops, and bookingUrl.
        """
        if isinstance(raw_text, dict):
            data = raw_text
        else:
            data = None
            text_str = str(raw_text)
            # Check SSE format (lines starting with 'data:')
            data_lines = [
                line[5:].strip()
                for line in text_str.splitlines()
                if line.strip().startswith("data:")
            ]
            if data_lines:
                for line in reversed(data_lines):
                    try:
                        candidate = json.loads(line)
                        if "result" in candidate or "itineraries" in candidate:
                            data = candidate
                            break
                    except Exception:
                        continue
            if data is None:
                try:
                    data = json.loads(text_str)
                except Exception:
                    return []

        result = data.get("result", data) if isinstance(data, dict) else {}
        content = result.get("content", []) if isinstance(result, dict) else []
        inner: Dict[str, Any] = {}
        if content and isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict):
                txt = first_item.get("text", "")
                if isinstance(txt, str) and txt.strip().startswith("{"):
                    try:
                        inner = json.loads(txt)
                    except Exception:
                        inner = {}
                elif isinstance(txt, dict):
                    inner = txt
        if not inner and isinstance(result, dict):
            inner = result

        itineraries = inner.get("itineraries", []) if isinstance(inner, dict) else []
        parsed_results: List[Dict[str, Any]] = []

        for it in itineraries:
            try:
                price = float(it.get("price", 0.0))
                booking_url = it.get("bookingUrl", "")
                outbound = it.get("outbound", {}) or {}
                inbound = it.get("inbound", {}) or {}

                carriers: List[str] = []
                for seg in outbound.get("segments", []) + inbound.get("segments", []):
                    c_name = seg.get("carrierName") or seg.get("carrier")
                    if c_name and c_name not in carriers:
                        carriers.append(c_name)
                carrier_str = " / ".join(carriers) if carriers else "Kiwi.com"

                out_route = outbound.get("route", []) or []
                in_route = inbound.get("route", []) or []

                out_stops = out_route[1:-1] if len(out_route) > 2 else []
                in_stops = in_route[1:-1] if len(in_route) > 2 else []
                intermediate_stops = list(dict.fromkeys(out_stops + in_stops))

                stops_count = max(
                    outbound.get("stops", len(out_stops)),
                    inbound.get("stops", len(in_stops)),
                    0,
                )

                parsed_results.append(
                    {
                        "price_eur": price,
                        "carrier": carrier_str,
                        "stops": stops_count,
                        "intermediate_stops": intermediate_stops,
                        "outbound_stops": out_stops,
                        "inbound_stops": in_stops,
                        "booking_url": booking_url,
                        "outbound_departure": outbound.get("departureTime", ""),
                        "outbound_arrival": outbound.get("arrivalTime", ""),
                        "inbound_departure": inbound.get("departureTime", ""),
                        "inbound_arrival": inbound.get("arrivalTime", ""),
                    }
                )
            except Exception:
                continue

        parsed_results.sort(key=lambda x: x["price_eur"])
        return parsed_results

    async def search_roundtrip(
        self,
        fly_from: str,
        fly_to: str,
        d_out_iso: str,
        d_in_iso: str,
        flex_days: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Executes keyless round-trip flight search via Kiwi MCP JSON-RPC 2.0 tools/call.
        """
        if os.getenv("LIVE_FLIGHTS_HTTP", "1") != "1":
            return []

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search-flight",
                "arguments": {
                    "flyFrom": fly_from,
                    "flyTo": fly_to,
                    "departureDate": iso_to_ddmmyyyy(d_out_iso),
                    "departureDateFlexDays": flex_days,
                    "returnDate": iso_to_ddmmyyyy(d_in_iso),
                    "returnDateFlexDays": flex_days,
                    "currency": "EUR",
                    "adults": 1,
                },
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.base_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return self.parse_response_payload(resp.text)
                _log_err(f"Kiwi MCP error: HTTP {resp.status_code}")
                return []
        except Exception as e:
            _log_err("Kiwi MCP search failed", e)
            return []


class FerryhopperMCPClient:
    """
    Ferryhopper Official Keyless MCP client (https://mcp.ferryhopper.com/mcp — JSON-RPC 2.0).
    Provides live ferry price and deepLink enrichment via `search_trips` tool call.
    Disabled automatically when LIVE_FLIGHTS_HTTP != 1.
    """

    def __init__(
        self,
        base_url: str = "https://mcp.ferryhopper.com/mcp",
        timeout: float = 8.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def parse_ferry_response(raw_text: Any) -> Optional[Tuple[float, str, str]]:
        """
        Parses Ferryhopper MCP `search_trips` JSON-RPC response.
        Extracts lowest `totalPriceInCents / 100.0`, company/vessel name, and `deepLink`.
        Returns (lowest_price_eur, company_name, deep_link) or None.
        """
        if isinstance(raw_text, dict):
            data = raw_text
        else:
            data = None
            text_str = str(raw_text)
            data_lines = [
                line[5:].strip()
                for line in text_str.splitlines()
                if line.strip().startswith("data:")
            ]
            if data_lines:
                for line in reversed(data_lines):
                    try:
                        candidate = json.loads(line)
                        if "result" in candidate or "structuredContent" in candidate:
                            data = candidate
                            break
                    except Exception:
                        continue
            if data is None:
                try:
                    data = json.loads(text_str)
                except Exception:
                    return None

        result = data.get("result", data) if isinstance(data, dict) else {}
        struct: Dict[str, Any] = {}
        if isinstance(result, dict):
            struct = result.get("structuredContent") or {}

        if not struct and isinstance(result, dict) and "content" in result:
            content = result.get("content", [])
            if content and isinstance(content, list) and len(content) > 0:
                first_item = content[0]
                if isinstance(first_item, dict):
                    txt = first_item.get("text", "")
                    if isinstance(txt, str) and txt.strip().startswith("{"):
                        try:
                            inner = json.loads(txt)
                            struct = inner.get("structuredContent", inner)
                        except Exception:
                            pass
                    elif isinstance(txt, dict):
                        struct = txt.get("structuredContent", txt)

        if not struct and isinstance(result, dict):
            struct = result

        itineraries = (
            struct.get("foundDirectItinerariesForTrip", [])
            if isinstance(struct, dict)
            else []
        )
        if not itineraries and isinstance(struct, dict):
            itineraries = struct.get("itineraries", [])

        candidates: List[Tuple[float, str, str]] = []
        for it in itineraries:
            try:
                price_cents = it.get("totalPriceInCents")
                if price_cents is not None:
                    price_eur = round(float(price_cents) / 100.0, 2)
                else:
                    price_eur = round(
                        float(it.get("totalPrice", it.get("price", 0.0))), 2
                    )

                if price_eur <= 0.0:
                    continue

                company = (
                    it.get("companyName")
                    or it.get("vesselName")
                    or it.get("company")
                    or it.get("operator")
                    or "Ferryhopper"
                )
                deep_link = (
                    it.get("deepLink")
                    or it.get("bookingUrl")
                    or it.get("url")
                    or "https://www.ferryhopper.com/"
                )
                candidates.append((price_eur, str(company), str(deep_link)))
            except Exception:
                continue

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        return candidates[0]

    async def search_ferry_price_eur(
        self, dep_port_name: str, arr_port_name: str, date_iso: str
    ) -> Optional[Tuple[float, str, str]]:
        """
        Calls Ferryhopper MCP `tools/call` `search_trips` to get live ferry prices.
        """
        if os.getenv("LIVE_FLIGHTS_HTTP", "1") != "1":
            return None

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "search_trips",
                "arguments": {
                    "departureLocation": dep_port_name,
                    "arrivalLocation": arr_port_name,
                    "date": date_iso,
                },
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.base_url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return self.parse_ferry_response(resp.text)
                _log_err(f"Ferryhopper MCP error: HTTP {resp.status_code}")
                return None
        except Exception as e:
            _log_err("Ferryhopper MCP search failed", e)
            return None


class SerpApiClient:
    """
    SerpApi Google Flights fallback client (https://serpapi.com/search.json).
    Strictly quota-conserving (MAX_CALLS_PER_RUN = 3).
    Strictly redacts API key from all logs and error messages.
    """

    MAX_CALLS_PER_RUN: int = 3

    def __init__(
        self,
        base_url: str = "https://serpapi.com/search.json",
        timeout: float = 10.0,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.call_count: int = 0

    @staticmethod
    def parse_serpapi_flights(data: Any) -> Optional[Dict[str, Any]]:
        """
        Parses SerpApi google_flights response payload.
        """
        if not isinstance(data, dict):
            return None

        candidates = data.get("best_flights", []) + data.get("other_flights", [])
        if not candidates:
            return None

        parsed: List[Dict[str, Any]] = []
        for c in candidates:
            try:
                price = c.get("price")
                if price is None:
                    continue
                flights = c.get("flights", [])
                airlines = [f.get("airline") for f in flights if f.get("airline")]
                carrier = (
                    " / ".join(dict.fromkeys(airlines))
                    if airlines
                    else "Google Flights"
                )
                booking_url = (
                    c.get("booking_token")
                    or c.get("link")
                    or "https://www.google.com/travel/flights"
                )
                stops = max(0, len(flights) - 1)
                parsed.append(
                    {
                        "price_eur": float(price),
                        "carrier": carrier,
                        "stops": stops,
                        "booking_url": booking_url,
                    }
                )
            except Exception:
                continue

        if not parsed:
            return None

        parsed.sort(key=lambda x: x["price_eur"])
        return parsed[0]

    async def search_flights_fallback(
        self, orig: str, dest: str, d_out: str, d_in: str
    ) -> Optional[Dict[str, Any]]:
        """
        Queries engine='google_flights' only when SERPAPI_API_KEY is configured,
        LIVE_FLIGHTS_HTTP == 1, and call limit <= MAX_CALLS_PER_RUN.
        """
        api_key = config.SERPAPI_API_KEY or getattr(config, "SERPAPI_KEY", "")
        if not api_key:
            return None

        if os.getenv("LIVE_FLIGHTS_HTTP", "1") != "1":
            return None

        if self.call_count >= self.MAX_CALLS_PER_RUN:
            _log_err(
                f"SerpApiClient cap reached ({self.MAX_CALLS_PER_RUN} calls). Quota preserved."
            )
            return None

        self.call_count += 1
        params = {
            "engine": "google_flights",
            "departure_id": orig,
            "arrival_id": dest,
            "outbound_date": d_out,
            "return_date": d_in,
            "currency": "EUR",
            "hl": "en",
            "api_key": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    return self.parse_serpapi_flights(resp.json())
                _log_err(f"SerpApi HTTP {resp.status_code}")
                return None
        except Exception as e:
            _log_err("SerpApi search request failed", e)
            return None


class TravelpayoutsClient:
    """
    Travelpayouts Aviasales Data API client (https://api.travelpayouts.com/aviasales/v3/prices_for_dates).
    Active when TRAVELPAYOUTS_TOKEN is configured and LIVE_FLIGHTS_HTTP == 1.
    Strictly redacts token in all logs and error messages.
    """

    def __init__(
        self,
        base_url: str = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates",
        timeout: float = 8.0,
    ):
        self.base_url = base_url
        self.timeout = timeout

    @staticmethod
    def parse_travelpayouts_response(data: Any) -> Optional[Dict[str, Any]]:
        """
        Parses Aviasales / Travelpayouts prices_for_dates response payload.
        """
        if not isinstance(data, dict):
            return None

        items = data.get("data", [])
        if not items or not isinstance(items, list):
            return None

        parsed: List[Dict[str, Any]] = []
        for it in items:
            try:
                price = it.get("price")
                if price is None:
                    continue
                carrier = it.get("airline") or "Aviasales"
                transfers = int(it.get("transfers", 0))
                link = it.get("link", "")
                if link and not link.startswith("http"):
                    link = f"https://www.aviasales.com{link}"
                parsed.append(
                    {
                        "price_eur": float(price),
                        "carrier": carrier,
                        "stops": transfers,
                        "booking_url": link or "https://www.aviasales.com/",
                    }
                )
            except Exception:
                continue

        if not parsed:
            return None

        parsed.sort(key=lambda x: x["price_eur"])
        return parsed[0]

    async def search_prices(
        self, orig: str, dest: str, d_out: str, d_in: str
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches live flight prices via Travelpayouts Data API.
        """
        token = config.TRAVELPAYOUTS_TOKEN
        if not token or os.getenv("LIVE_FLIGHTS_HTTP", "1") != "1":
            return None

        params = {
            "origin": orig,
            "destination": dest,
            "departure_at": d_out,
            "return_at": d_in,
            "currency": "EUR",
            "token": token,
        }
        headers = {
            "x-access-token": token,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(self.base_url, params=params, headers=headers)
                if resp.status_code == 200:
                    return self.parse_travelpayouts_response(resp.json())
                _log_err(f"Travelpayouts API returned status {resp.status_code}")
                return None
        except Exception as e:
            _log_err("Travelpayouts search failed", e)
            return None
