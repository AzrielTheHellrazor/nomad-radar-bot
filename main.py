import argparse
import asyncio
from datetime import date
from telegram.ext import ContextTypes
from bot.formatter import format_deal_telegram_message, format_holidays_summary
from bot.scheduler import DealScanOrchestrator
from bot.telegram_bot import NomadTelegramBot
from calendar_visa.holidays_tr import HolidayWindowCalculator
from config import (
    DATABASE_PATH,
    DEFAULT_ADMIN_CHAT_ID,
    SCAN_INTERVAL_MINUTES,
    TELEGRAM_BOT_TOKEN,
)
from database import Database


async def run_demo_preview() -> None:
    """
    Telegram token girmeden bile terminalden hem Solo (Yeşil Pasaport)
    hem de Çift (Yeşil + Bordo Pasaport) modlarının canlı çıktısını gösterir.
    """
    db = Database(DATABASE_PATH)
    db.init_db()
    orchestrator = DealScanOrchestrator(db=db)
    calc = HolidayWindowCalculator()

    print("=" * 80)
    print("🧭 NOMAD RADAR — TATİL, KÖPRÜ İZİN & ÇİFT MODLU UCUZ SEYAHAT MOTORU (CANLI ÖNİZLEME)")
    print("=" * 80)
    windows = calc.get_upcoming_windows(reference_date=date(2026, 10, 22), days_ahead=60)
    print(format_holidays_summary(windows[:4]))
    print("\n" + "=" * 80)

    deals = await orchestrator.run_scan_for_user(
        chat_id=1,
        reference_date=date(2026, 10, 22),
        days_ahead=30,
        max_results_per_mode=2,
        force_notify=True,
    )
    for idx, deal in enumerate(deals, start=1):
        print(f"\n🔔 ÖRNEK TELEGRAM BİLDİRİMİ #{idx}:")
        print("-" * 80)
        print(format_deal_telegram_message(deal))
        print("-" * 80)


async def periodic_scan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.job.data["db"]
    orchestrator: DealScanOrchestrator = context.job.data["orchestrator"]

    users = db.get_all_users()
    if not users and DEFAULT_ADMIN_CHAT_ID:
        users = [db.get_user_settings(DEFAULT_ADMIN_CHAT_ID)]

    for user in users:
        deals = await orchestrator.run_scan_for_user(
            chat_id=user.chat_id,
            days_ahead=60,
            max_results_per_mode=2,
            force_notify=False,
        )
        for deal in deals:
            await context.bot.send_message(
                chat_id=user.chat_id,
                text=format_deal_telegram_message(deal),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="NomadRadar Dual-Mode Smart Travel Telegram Bot")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Telegram token gerekmeden terminalde canlı Solo ve Çift Modu fırsat taraması çalıştırır",
    )
    args = parser.parse_args()

    if args.demo or not TELEGRAM_BOT_TOKEN:
        if not TELEGRAM_BOT_TOKEN and not args.demo:
            print("⚠️ TELEGRAM_BOT_TOKEN bulunamadı (.env dosyasını doldurun). Canlı Önizleme (Demo) modu çalıştırılıyor...\n")
        asyncio.run(run_demo_preview())
        return

    db = Database(DATABASE_PATH)
    db.init_db()
    if DEFAULT_ADMIN_CHAT_ID:
        db.get_user_settings(DEFAULT_ADMIN_CHAT_ID)

    bot_service = NomadTelegramBot(token=TELEGRAM_BOT_TOKEN, db=db)
    app = bot_service.build_application()

    if app.job_queue:
        app.job_queue.run_repeating(
            periodic_scan_job,
            interval=SCAN_INTERVAL_MINUTES * 60,
            first=15,
            data={"db": db, "orchestrator": bot_service.orchestrator},
        )

    print(f"🚀 NomadRadar Telegram Botu aktif! (Periyodik tarama: her {SCAN_INTERVAL_MINUTES} dakikada bir)")
    app.run_polling()


if __name__ == "__main__":
    main()
