import json
import logging
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

import config
from models import TravelMode, TravelWindow
from transport.direct_flights import DirectFlightScanner
from transport.external_mcp_apis import (
    FerryhopperMCPClient,
    KiwiMCPClient,
    SerpApiClient,
    TravelpayoutsClient,
    iso_to_ddmmyyyy,
    redact_secrets,
)
from transport.multimodal_ferry_bus import MultiModalFerryBusEngine


def test_iso_to_ddmmyyyy_conversion():
    assert iso_to_ddmmyyyy("2026-10-28") == "28/10/2026"
    assert iso_to_ddmmyyyy("2026-05-01") == "01/05/2026"
    assert iso_to_ddmmyyyy("15/06/2026") == "15/06/2026"
    assert iso_to_ddmmyyyy("") == ""


def test_kiwi_mcp_sse_and_json_parsing():
    """
    1. KiwiMCPClient SSE response parsing:
    Extracts price in EUR, carrier names, intermediate route[1:-1] stops, and bookingUrl.
    """
    sample_sse_payload = (
        "event: message\n"
        'data: {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": '
        + json.dumps(
            json.dumps(
                {
                    "query": {},
                    "currency": "EUR",
                    "itineraries": [
                        {
                            "price": 142.50,
                            "bookingUrl": "https://www.kiwi.com/booking/test-itinerary-123",
                            "outbound": {
                                "route": ["SAW", "ATH", "FCO"],
                                "stops": 1,
                                "departureTime": "2026-10-28T09:15:00",
                                "arrivalTime": "2026-10-28T14:45:00",
                                "segments": [
                                    {"carrierName": "Pegasus", "carrier": "PC"},
                                    {"carrierName": "Aegean", "carrier": "A3"},
                                ],
                            },
                            "inbound": {
                                "route": ["FCO", "SAW"],
                                "stops": 0,
                                "departureTime": "2026-11-01T18:30:00",
                                "arrivalTime": "2026-11-01T22:45:00",
                                "segments": [
                                    {"carrierName": "Pegasus", "carrier": "PC"}
                                ],
                            },
                        }
                    ],
                }
            )
        )
        + "}]}}\n\n"
    )

    results = KiwiMCPClient.parse_response_payload(sample_sse_payload)
    assert len(results) == 1
    it = results[0]
    assert it["price_eur"] == 142.50
    assert "Pegasus" in it["carrier"]
    assert "Aegean" in it["carrier"]
    assert it["outbound_stops"] == ["ATH"]
    assert it["stops"] == 1
    assert it["booking_url"] == "https://www.kiwi.com/booking/test-itinerary-123"


def test_ferryhopper_mcp_cents_and_deeplink_parsing():
    """
    2. FerryhopperMCPClient totalPriceInCents (6000 -> 60.0€) & deepLink parsing.
    """
    sample_response = {
        "jsonrpc": "2.0",
        "result": {
            "structuredContent": {
                "foundDirectItinerariesForTrip": [
                    {
                        "totalPriceInCents": 6000,
                        "companyName": "Yeşil Marmaris Lines",
                        "vesselName": "Akçakoca",
                        "deepLink": "https://www.ferryhopper.com/en/booking/marmaris-rhodes-6000",
                    },
                    {
                        "totalPriceInCents": 8500,
                        "companyName": "Sea Dreams",
                        "vesselName": "King Saron",
                        "deepLink": "https://www.ferryhopper.com/en/booking/marmaris-rhodes-8500",
                    },
                ]
            }
        },
    }

    parsed = FerryhopperMCPClient.parse_ferry_response(sample_response)
    assert parsed is not None
    price_eur, company, deep_link = parsed
    assert price_eur == 60.0
    assert company == "Yeşil Marmaris Lines"
    assert (
        deep_link
        == "https://www.ferryhopper.com/en/booking/marmaris-rhodes-6000"
    )


@pytest.mark.asyncio
async def test_serpapi_quota_cap_and_secret_redaction(monkeypatch, caplog):
    """
    3. SerpApiClient quota cap (MAX_CALLS_PER_RUN = 3) & secret redaction in logs.
    """
    fake_secret = "secret_serp_key_987654321"
    monkeypatch.setattr(config, "SERPAPI_API_KEY", fake_secret)
    monkeypatch.setenv("LIVE_FLIGHTS_HTTP", "1")

    client = SerpApiClient()
    assert client.MAX_CALLS_PER_RUN == 3

    mock_resp_json = {
        "best_flights": [
            {
                "price": 135,
                "flights": [
                    {"airline": "Pegasus"},
                    {"airline": "AJet"},
                ],
                "booking_token": "https://www.google.com/travel/flights/booking-token-123",
            }
        ]
    }

    mock_get = AsyncMock()
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = lambda: mock_resp_json
    mock_get.return_value = mock_resp

    with patch("httpx.AsyncClient.get", mock_get):
        # 3 calls succeed
        res1 = await client.search_flights_fallback(
            "SAW", "FCO", "2026-10-28", "2026-11-01"
        )
        assert res1 is not None
        assert res1["price_eur"] == 135.0
        assert client.call_count == 1

        res2 = await client.search_flights_fallback(
            "SAW", "MXP", "2026-10-28", "2026-11-01"
        )
        assert res2 is not None
        assert client.call_count == 2

        res3 = await client.search_flights_fallback(
            "SAW", "BLQ", "2026-10-28", "2026-11-01"
        )
        assert res3 is not None
        assert client.call_count == 3

        # 4th call is blocked by quota cap
        with caplog.at_level(logging.ERROR):
            res4 = await client.search_flights_fallback(
                "SAW", "NAP", "2026-10-28", "2026-11-01"
            )
            assert res4 is None
            assert client.call_count == 3
            assert mock_get.call_count == 3

    # Test secret redaction
    log_text = (
        f"Request failed with url https://serpapi.com/search.json?api_key={fake_secret}&q=flights"
    )
    redacted = redact_secrets(log_text)
    assert fake_secret not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.asyncio
async def test_travelpayouts_client_parsing_and_secret_redaction(monkeypatch):
    """
    4. TravelpayoutsClient parsing & secret redaction.
    """
    fake_tp_token = "secret_travelpayouts_token_abc123"
    monkeypatch.setattr(config, "TRAVELPAYOUTS_TOKEN", fake_tp_token)
    monkeypatch.setenv("LIVE_FLIGHTS_HTTP", "1")

    client = TravelpayoutsClient()
    sample_data = {
        "success": True,
        "data": [
            {
                "price": 118,
                "airline": "Pegasus",
                "transfers": 0,
                "link": "/search/SAWFCO2810",
            }
        ],
    }

    parsed = TravelpayoutsClient.parse_travelpayouts_response(sample_data)
    assert parsed is not None
    assert parsed["price_eur"] == 118.0
    assert parsed["carrier"] == "Pegasus"
    assert parsed["stops"] == 0
    assert parsed["booking_url"] == "https://www.aviasales.com/search/SAWFCO2810"

    # Redaction test
    url_with_token = (
        f"https://api.travelpayouts.com/v3?token={fake_tp_token}&curr=EUR"
    )
    redacted = redact_secrets(url_with_token)
    assert fake_tp_token not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.asyncio
async def test_clients_disabled_when_offline(monkeypatch):
    """
    All external API and MCP clients must return empty/None when LIVE_FLIGHTS_HTTP=0.
    """
    monkeypatch.setenv("LIVE_FLIGHTS_HTTP", "0")

    kiwi = KiwiMCPClient()
    kiwi_res = await kiwi.search_roundtrip("IST", "FCO", "2026-10-28", "2026-11-01")
    assert kiwi_res == []

    ferry = FerryhopperMCPClient()
    ferry_res = await ferry.search_ferry_price_eur("Marmaris", "Rhodes", "2026-10-28")
    assert ferry_res is None

    serp = SerpApiClient()
    serp_res = await serp.search_flights_fallback("SAW", "FCO", "2026-10-28", "2026-11-01")
    assert serp_res is None

    tp = TravelpayoutsClient()
    tp_res = await tp.search_prices("SAW", "FCO", "2026-10-28", "2026-11-01")
    assert tp_res is None


@pytest.mark.asyncio
async def test_direct_flight_scanner_mcp_fallback_integration(monkeypatch):
    """
    DirectFlightScanner falls back cleanly to KiwiMCPClient when live scraping returns empty.
    """
    monkeypatch.setenv("LIVE_FLIGHTS_HTTP", "1")
    scanner = DirectFlightScanner(use_live_http=True)

    window = TravelWindow(
        title="Test Window",
        start_dt=datetime(2026, 10, 28, 14, 0),
        end_dt=datetime(2026, 11, 1, 22, 0),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=False,
    )

    # Mock fast_flights scraping to return empty list
    with patch.object(scanner, "_query_keyless_google_or_kiwi", AsyncMock(return_value=[])):
        with patch.object(
            scanner._kiwi_client,
            "search_roundtrip",
            AsyncMock(
                return_value=[
                    {
                        "price_eur": 128.0,
                        "carrier": "Kiwi Verified Partner",
                        "stops": 1,
                        "booking_url": "https://www.kiwi.com/verified-link",
                    }
                ]
            ),
        ):
            routes = await scanner.search_direct_or_one_stop(window, "BUD")
            assert len(routes) == 1
            route = routes[0]
            assert "Kiwi MCP Canlı" in route.strategy_name
            assert route.roundtrip_price_per_person_eur == 128.0
            assert route.booking_hint_url == "https://www.kiwi.com/verified-link"


@pytest.mark.asyncio
async def test_ferryhopper_live_enrichment_in_multimodal_engine(monkeypatch):
    """
    When LIVE_FLIGHTS_HTTP=1, Aegean ferries enrich price & link from FerryhopperMCPClient.
    """
    monkeypatch.setenv("LIVE_FLIGHTS_HTTP", "1")
    engine = MultiModalFerryBusEngine()

    window = TravelWindow(
        title="29 Ekim Test Window",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )

    with patch.object(
        engine._ferryhopper_client,
        "search_ferry_price_eur",
        AsyncMock(return_value=(55.0, "Dodekanisos Seaways", "https://ferryhopper.com/dodekanisos")),
    ):
        routes = await engine.build_multimodal_routes(window, "RHO", mode=TravelMode.SOLO)
        assert len(routes) >= 1
        best_rho = routes[0]
        ferry_legs = [l for l in best_rho.outbound_legs + best_rho.inbound_legs if l.mode == "ferry"]
        assert len(ferry_legs) >= 2
        assert ferry_legs[0].price_eur_per_person == 55.0
        assert "Dodekanisos Seaways" in ferry_legs[0].carrier
        assert best_rho.booking_hint_url == "https://ferryhopper.com/dodekanisos"
