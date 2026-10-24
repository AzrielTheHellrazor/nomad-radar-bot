import pytest
from datetime import datetime
from models import TravelMode, TravelWindow
from transport.aggregator import TransportAggregator


@pytest.mark.asyncio
async def test_solo_mode_includes_balkan_border_hack_and_night_transit():
    """
    Solo Modda (Yeşil Pasaport):
    - Direkt uçuşların yanında İstanbul -> Sofya/Selanik gece otobüsü/treni + Ryanair/WizzAir
      'Balkan Sınır Hack' rotası üretilmeli ve eğer gece otobüsü/treni varsa
      saves_accommodation_night=True olmalı!
    """
    agg = TransportAggregator()
    window = TravelWindow(
        title="29 Ekim Cumhuriyet Bayramı Köprü Tatili",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )

    routes = await agg.find_best_routes(window=window, city_code="OPO", mode=TravelMode.SOLO)
    assert len(routes) >= 2

    hack_routes = [r for r in routes if r.is_border_hack]
    assert len(hack_routes) >= 1
    best_hack = hack_routes[0]
    assert best_hack.saved_nights_count >= 1
    # Balkan hack rotası resmi tatilde şişen direkt İstanbul uçuşundan daha ucuz olmalı
    direct_routes = [r for r in routes if not r.is_border_hack]
    assert best_hack.roundtrip_price_per_person_eur < direct_routes[0].roundtrip_price_per_person_eur


@pytest.mark.asyncio
async def test_couple_mode_excludes_border_hack_and_enforces_low_stops_comfort():
    """
    Çift Modunda (Siz + Kız Arkadaşınız):
    - Yorucu gece otobüsü sınır hack'leri KAPALI (is_border_hack=False).
    - Sadece direkt veya maksimum 1 rahat aktarmalı (max_stops <= 1) konforlu ulaşım dönmeli.
    """
    agg = TransportAggregator()
    window = TravelWindow(
        title="29 Ekim Cumhuriyet Bayramı Köprü Tatili",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )

    routes = await agg.find_best_routes(window=window, city_code="TIV", mode=TravelMode.COUPLE)
    assert len(routes) >= 1
    for r in routes:
        assert r.is_border_hack is False
        assert r.max_stops <= 1
        assert r.saved_nights_count == 0


def test_get_typical_rt_flight_eur_calculation_and_fallbacks():
    """
    Verifies typical roundtrip flight baseline calculations:
    - Profiled cities: base_one_way * 2.0
    - Case insensitivity & whitespace trimming
    - Unprofiled / empty fallbacks return 180.0 EUR
    """
    from transport.direct_flights import get_typical_rt_flight_eur

    # Profiled cities
    assert get_typical_rt_flight_eur("FCO") == 176.0   # 88.0 * 2.0
    assert get_typical_rt_flight_eur("BLQ") == 148.0   # 74.0 * 2.0
    assert get_typical_rt_flight_eur("VCE") == 192.0   # 96.0 * 2.0
    assert get_typical_rt_flight_eur("LIS") == 370.0   # 185.0 * 2.0
    assert get_typical_rt_flight_eur("OPO") == 390.0   # 195.0 * 2.0
    assert get_typical_rt_flight_eur("ATH") == 136.0   # 68.0 * 2.0

    # Case insensitivity and whitespace handling
    assert get_typical_rt_flight_eur("fco") == 176.0
    assert get_typical_rt_flight_eur("  blq  ") == 148.0

    # Unprofiled city codes or invalid inputs fallback to 180.0
    assert get_typical_rt_flight_eur("XYZ") == 180.0
    assert get_typical_rt_flight_eur("") == 180.0
    assert get_typical_rt_flight_eur(None) == 180.0


def test_transport_aggregator_delegates_typical_baseline():
    """
    Verifies that TransportAggregator exposes get_typical_rt_flight_eur
    and delegates to get_typical_rt_flight_eur correctly.
    """
    agg = TransportAggregator()
    assert agg.get_typical_rt_flight_eur("FCO") == 176.0
    assert agg.get_typical_rt_flight_eur("XYZ") == 180.0


def test_direct_route_profiles_expansion_and_new_city_baselines():
    from transport.direct_flights import DIRECT_ROUTE_PROFILES, get_typical_rt_flight_eur

    assert len(DIRECT_ROUTE_PROFILES) >= 60

    # New city baseline checks
    assert get_typical_rt_flight_eur("SOF") == 110.0   # 55.0 * 2.0
    assert get_typical_rt_flight_eur("ZRH") == 178.0   # 89.0 * 2.0
    assert get_typical_rt_flight_eur("BGY") == 156.0   # 78.0 * 2.0
    assert get_typical_rt_flight_eur("STN") == 150.0   # 75.0 * 2.0
    assert get_typical_rt_flight_eur("CPH") == 172.0   # 86.0 * 2.0
    assert get_typical_rt_flight_eur("PUS") == 860.0   # 430.0 * 2.0


@pytest.mark.asyncio
async def test_balkan_border_hop_live_dual_leg_success_and_discard():
    import os
    from unittest.mock import patch
    from transport.border_hop import BorderHopEngine

    engine = BorderHopEngine()
    window = TravelWindow(
        title="Balkan Test Window",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )

    # 1. Successful dual-leg live querying
    with patch.dict(os.environ, {"LIVE_RYANAIR_HTTP": "1"}):
        async def mock_ryanair_both(origin, dest, *args, **kwargs):
            if origin == "SOF" and dest == "OPO":
                return 22.0  # Outbound live fare
            elif origin == "OPO" and dest == "SOF":
                return 29.0  # Inbound live fare
            return None

        with patch.object(engine, "_try_fetch_ryanair_fare", side_effect=mock_ryanair_both):
            routes = await engine.build_balkan_hack_routes(window, "OPO")

        assert len(routes) == 1
        route = routes[0]
        # Leg 2 is outbound flight (SOF -> OPO)
        assert route.outbound_legs[1].price_eur_per_person == 22.0
        # Leg 1 is inbound flight (OPO -> SOF)
        assert route.inbound_legs[0].price_eur_per_person == 29.0
        assert route.inbound_legs[0].price_eur_per_person != round(22.0 * 1.05, 2)

    # 2. Inbound live fare missing -> discard route
    with patch.dict(os.environ, {"LIVE_RYANAIR_HTTP": "1"}):
        async def mock_ryanair_missing_inbound(origin, dest, *args, **kwargs):
            if origin == "SOF" and dest == "OPO":
                return 22.0
            return None

        with patch.object(engine, "_try_fetch_ryanair_fare", side_effect=mock_ryanair_missing_inbound):
            routes_missing_in = await engine.build_balkan_hack_routes(window, "OPO")
        assert len(routes_missing_in) == 0

    # 3. Outbound live fare missing -> discard route
    with patch.dict(os.environ, {"LIVE_RYANAIR_HTTP": "1"}):
        async def mock_ryanair_missing_outbound(origin, dest, *args, **kwargs):
            if origin == "OPO" and dest == "SOF":
                return 29.0
            return None

        with patch.object(engine, "_try_fetch_ryanair_fare", side_effect=mock_ryanair_missing_outbound):
            routes_missing_out = await engine.build_balkan_hack_routes(window, "OPO")
        assert len(routes_missing_out) == 0


@pytest.mark.asyncio
async def test_direct_flight_scanner_saw_ist_concurrent_query_and_cache_isolation():
    from unittest.mock import patch, MagicMock
    from transport.direct_flights import DirectFlightScanner, _LIVE_FLIGHT_CACHE

    _LIVE_FLIGHT_CACHE.clear()
    scanner = DirectFlightScanner()
    window = TravelWindow(
        title="Dual Origin Test Window",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )

    class MockFlight:
        def __init__(self, price: float, airline: str):
            self.price = price
            self.airlines = [airline]
            flight_obj = MagicMock()
            flight_obj.departure.date = (2026, 10, 28)
            flight_obj.departure.time = (14, 0)
            flight_obj.arrival.date = (2026, 10, 28)
            flight_obj.arrival.time = (17, 0)
            self.flights = [flight_obj]

    # Mock _fetch_sync returning different prices for SAW (expensive) vs IST (cheaper)
    def mock_fetch(orig: str):
        if orig == "SAW":
            return [MockFlight(120.0, "Pegasus")], [MockFlight(110.0, "Pegasus")]
        elif orig == "IST":
            return [MockFlight(45.0, "Turkish Airlines")], [MockFlight(40.0, "Turkish Airlines")]
        return None, None

    d_out = window.start_dt.strftime("%Y-%m-%d")
    d_in = window.end_dt.strftime("%Y-%m-%d")

    with patch("fast_flights.create_query") as mock_cq, \
         patch("fast_flights.get_flights") as mock_gf:
        def cq_impl(flights, **kwargs):
            query = MagicMock()
            query.flights = flights
            return query
        mock_cq.side_effect = cq_impl

        def gf_impl(query):
            orig = query.flights[0].from_airport
            dest = query.flights[0].to_airport
            if orig in ("SAW", "IST"):
                # outbound
                return mock_fetch(orig)[0]
            else:
                # inbound
                return mock_fetch(dest)[1]
        mock_gf.side_effect = gf_impl

        routes = await scanner._query_keyless_google_or_kiwi(window, "FCO")

    assert len(routes) == 1
    best_route = routes[0]
    # IST total roundtrip (45 + 40 = 85€) should win over SAW (120 + 110 = 230€)
    assert best_route.roundtrip_price_per_person_eur == 85.0
    assert "IST" in best_route.strategy_name

    # Verify cache isolation between SAW and IST
    saw_key = f"SAW:FCO:{d_out}:{d_in}"
    ist_key = f"IST:FCO:{d_out}:{d_in}"
    assert saw_key in _LIVE_FLIGHT_CACHE
    assert ist_key in _LIVE_FLIGHT_CACHE
    assert _LIVE_FLIGHT_CACHE[saw_key][0].roundtrip_price_per_person_eur == 230.0
    assert _LIVE_FLIGHT_CACHE[ist_key][0].roundtrip_price_per_person_eur == 85.0

