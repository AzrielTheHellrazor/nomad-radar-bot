import pytest
from datetime import datetime
from models import RouteOption, TransportLeg, TravelMode, TravelWindow
from accommodation.aggregator import AccommodationAggregator


def _sample_window() -> TravelWindow:
    return TravelWindow(
        title="29 Ekim Cumhuriyet Bayramı Köprü Tatili",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )


def test_solo_mode_gets_free_stays_night_transit_reduction_and_hostels():
    """
    Solo Modda:
    - Eğer rotada 1 gece otobüs/tren yolculuğu varsa (saves_accommodation_night=True),
      4 gecelik tatilde sadece 3 gece konaklama parası ödenmeli!
    - Ayrıca 0€ Bedava konaklama (TrustedHousesitters, Couchsurfing, HomeExchange) ve
      8.0+ puanlı Hostelworld / Airbnb özel oda seçenekleri dönmeli.
    """
    agg = AccommodationAggregator()
    window = _sample_window()
    hack_route = RouteOption(
        strategy_name="Balkan Hack",
        outbound_legs=[
            TransportLeg(
                mode="night_train",
                carrier="Sofya Ekspresi",
                origin="IST",
                destination="SOF",
                departure_str="27.10 22:00",
                arrival_str="28.10 06:45",
                price_eur_per_person=25.0,
                saves_accommodation_night=True,
            )
        ],
        inbound_legs=[],
        is_border_hack=True,
    )

    stays = agg.find_best_stays(
        window=window, city_code="OPO", mode=TravelMode.SOLO, route=hack_route
    )
    assert len(stays) >= 3

    # Gece treni sayesinde 4 gece yerine 3 gece üzerinden hesaplanmalı
    paid_stays = [s for s in stays if not s.is_free_stay]
    assert len(paid_stays) >= 1
    assert paid_stays[0].nights_charged == 3
    assert paid_stays[0].rating >= 8.0

    # Bedava konaklama alternatifleri de listede yer almalı
    free_stays = [s for s in stays if s.is_free_stay]
    assert len(free_stays) >= 1
    assert free_stays[0].total_stay_cost_eur == 0.0


def test_couple_mode_excludes_free_stays_and_hostels_and_returns_high_rated_private_stays():
    """
    Çift Modunda (Siz + Kız Arkadaşınız):
    - Bedava konaklama (Couchsurfing/Ev bakımı) ve Hostel ranzası KESİNLİKLE OLMAMALI!
    - Sadece 8.0+ puanlı Özel Otel (Butik/3-5★) veya Tam Daire Airbnb (%35+ indirimli) olmalı.
    """
    agg = AccommodationAggregator()
    window = _sample_window()
    direct_route = RouteOption(
        strategy_name="Direkt Uçuş",
        outbound_legs=[],
        inbound_legs=[],
        is_border_hack=False,
    )

    stays = agg.find_best_stays(
        window=window, city_code="TIV", mode=TravelMode.COUPLE, route=direct_route
    )
    assert len(stays) >= 2
    for s in stays:
        assert s.is_free_stay is False
        assert "hostel" not in s.stay_type.lower()
        assert s.rating >= 8.0
        assert s.nights_charged == 4
        assert s.discount_pct == 0
