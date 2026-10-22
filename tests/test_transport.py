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
