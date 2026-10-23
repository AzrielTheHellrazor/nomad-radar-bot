import os
import tempfile
import pytest
from datetime import date
from database import Database
from models import TravelMode
from bot.formatter import format_deal_telegram_message, format_holidays_summary
from bot.scheduler import DealScanOrchestrator
from calendar_visa.holidays_tr import HolidayWindowCalculator


@pytest.mark.asyncio
async def test_end_to_end_orchestrator_scan_and_telegram_formatting():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_flow.db")
        db = Database(db_path)
        db.init_db()

        # Kullanıcı ayarlarını oluştur (Hem Solo hem Çift modu açık = BOTH)
        settings = db.get_user_settings(chat_id=99999)
        assert settings.active_mode == TravelMode.BOTH

        orchestrator = DealScanOrchestrator(db=db)
        found_deals = await orchestrator.run_scan_for_user(
            chat_id=99999,
            reference_date=date(2026, 10, 22),
            days_ahead=20,
            max_results_per_mode=2,
        )

        # Hem Solo (örn. Portekiz/İtalya) hem de Çift (örn. Karadağ/Sırbistan) fırsatları bulunmalı
        modes_found = {d.mode for d in found_deals}
        assert TravelMode.SOLO in modes_found
        assert TravelMode.COUPLE in modes_found

        for deal in found_deals:
            # Sadece normal zamandan ekstra ucuz (%35+ indirimli) fırsatlar gelmeli
            assert deal.discount_vs_baseline_pct >= 35
            msg = format_deal_telegram_message(deal)
            # Telegram HTML formatında olmalı, AI modu kapalıyken blockquote olmamalı!
            assert "<b>" in msg
            assert "</b>" in msg
            assert "<blockquote>" not in msg
            assert "Normal Dönem Ortalaması:" in msg
            assert "**" not in msg
            assert "](" not in msg
            if deal.mode == TravelMode.SOLO:
                assert "SOLO" in msg
                assert "0€" in msg
            else:
                assert "ÇİFT" in msg
                assert "2 Kişi" in msg

        # Tatil takvimi özeti formatlama kontrolü
        windows = HolidayWindowCalculator().get_upcoming_windows(
            reference_date=date(2026, 10, 22), days_ahead=90
        )
        summary_text = format_holidays_summary(windows)
        assert "29 Ekim" in summary_text
        assert "<b>" in summary_text
        assert "**" not in summary_text
        assert "izin" in summary_text.lower()


def test_purge_demo_chat_ids_on_init():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_purge.db")
        db = Database(db_path)
        db.init_db()
        # Simulate leftover demo user chat_id=1 and real user chat_id=100001
        db.get_user_settings(1)
        db.get_user_settings(100001)
        db.init_db()
        users = db.get_all_users()
        chat_ids = [u.chat_id for u in users]
        assert 1 not in chat_ids
        assert 100001 in chat_ids


def test_live_eur_to_try_rate_is_realistic():
    from config import get_eur_to_try_rate, get_usd_to_try_rate

    eur_rate = get_eur_to_try_rate()
    usd_rate = get_usd_to_try_rate()
    assert 48.0 <= eur_rate <= 75.0
    assert 42.0 <= usd_rate <= 68.0



