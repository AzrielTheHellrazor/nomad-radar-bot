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
