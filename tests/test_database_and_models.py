import os
import tempfile
import pytest
from datetime import datetime
from models import (
    TravelMode,
    VisaCategory,
    TravelWindow,
    TransportLeg,
    RouteOption,
    StayOption,
    DealPackage,
)
from database import Database


def test_user_settings_and_dual_mode_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_nomad.db")
        db = Database(db_path)
        db.init_db()

        settings = db.get_user_settings(chat_id=12345)
        assert settings.chat_id == 12345
        assert settings.active_mode == TravelMode.BOTH
        assert "PT" in settings.solo_watchlist
        assert "ME" in settings.couple_watchlist

        # Switch mode to COUPLE
        db.set_active_mode(12345, TravelMode.COUPLE)
        updated = db.get_user_settings(12345)
        assert updated.active_mode == TravelMode.COUPLE

        # Add visa for couple (e.g., partner gets Schengen visa)
        db.add_visa(12345, mode=TravelMode.COUPLE, visa_code="SCHENGEN")
        updated = db.get_user_settings(12345)
        assert "SCHENGEN" in updated.couple_visas

        # Add solo visa (e.g., UK)
        db.add_visa(12345, mode=TravelMode.SOLO, visa_code="UK")
        updated = db.get_user_settings(12345)
        assert "UK" in updated.solo_visas


def test_deal_deduplication_and_price_drop_retrigger():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_nomad.db")
        db = Database(db_path)
        db.init_db()

        deal_key = "SOLO:PT:LIS:2026-10-28:2026-11-01"
        assert db.should_notify_deal(deal_key, total_price_eur=140.0) is True
        db.record_notified_deal(deal_key, total_price_eur=140.0)

        # Same price or small drop (<10%) -> should NOT spam
        assert db.should_notify_deal(deal_key, total_price_eur=135.0) is False

        # Significant further price drop (>=10% cheaper) -> SHOULD notify again!
        assert db.should_notify_deal(deal_key, total_price_eur=115.0) is True


def test_deal_package_baseline_and_discount_fields_sync():
    """Verify DealPackage exposes baseline_flight_per_person_eur, flight_discount_pct, and syncs discount_vs_baseline_pct."""
    import dataclasses
    from models import CountryRule

    field_names = [f.name for f in dataclasses.fields(DealPackage)]
    assert "baseline_flight_per_person_eur" in field_names
    assert "flight_discount_pct" in field_names
    assert "discount_vs_baseline_pct" in field_names

    window = TravelWindow(
        title="29 Ekim", start_dt=datetime(2026, 10, 28, 13, 0), end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5, leave_days_required=1.0, nights=4
    )
    country = CountryRule(
        code="IT", name_tr="İtalya", main_cities=["FCO"],
        solo_visa=VisaCategory.VISA_FREE, solo_visa_fee_eur=0.0, solo_min_lead_days=0,
        couple_visa=VisaCategory.VISA_REQUIRED, couple_visa_fee_eur=120.0, couple_min_lead_days=45
    )
    route = RouteOption(strategy_name="Direkt", outbound_legs=[], inbound_legs=[])
    stay = StayOption(provider="Hostelworld", title="Hostel", stay_type="hostel", city="Roma", rating=8.5, price_per_night_total_eur=20.0, nights_charged=4)

    # 1. Defaults
    pkg_default = DealPackage(
        mode=TravelMode.SOLO, country=country, city_code="FCO", city_name_tr="Roma",
        window=window, route=route, stay=stay
    )
    assert pkg_default.baseline_flight_per_person_eur == 0.0
    assert pkg_default.flight_discount_pct == 0
    assert pkg_default.discount_vs_baseline_pct == 0

    # 2. Init with flight_discount_pct -> syncs to discount_vs_baseline_pct
    pkg_flight = DealPackage(
        mode=TravelMode.SOLO, country=country, city_code="FCO", city_name_tr="Roma",
        window=window, route=route, stay=stay,
        baseline_flight_per_person_eur=180.0,
        flight_discount_pct=42
    )
    assert pkg_flight.baseline_flight_per_person_eur == 180.0
    assert pkg_flight.flight_discount_pct == 42
    assert pkg_flight.discount_vs_baseline_pct == 42

    # 3. Init with legacy discount_vs_baseline_pct -> syncs to flight_discount_pct
    pkg_legacy = DealPackage(
        mode=TravelMode.SOLO, country=country, city_code="FCO", city_name_tr="Roma",
        window=window, route=route, stay=stay,
        discount_vs_baseline_pct=38
    )
    assert pkg_legacy.flight_discount_pct == 38
    assert pkg_legacy.discount_vs_baseline_pct == 38

    # 4. Mutation synchronization
    pkg_flight.flight_discount_pct = 50
    assert pkg_flight.flight_discount_pct == 50
    assert pkg_flight.discount_vs_baseline_pct == 50

    pkg_flight.discount_vs_baseline_pct = 25
    assert pkg_flight.flight_discount_pct == 25
    assert pkg_flight.discount_vs_baseline_pct == 25


def test_user_settings_solo_watchlist_defaults_include_visa_free():
    """Verify UserSettings.solo_watchlist default includes all visa-free countries."""
    from models import UserSettings
    defaults = UserSettings(chat_id=99999)
    required_visa_free = {"AL", "MK", "GE", "GR_ISLANDS", "EG_SHARM", "MA", "IE"}
    watchlist_set = set(defaults.solo_watchlist)
    assert required_visa_free.issubset(watchlist_set)
    assert len(defaults.solo_watchlist) == 22
