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
            msg = format_deal_telegram_message(deal)
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
        assert "izin" in summary_text.lower()
