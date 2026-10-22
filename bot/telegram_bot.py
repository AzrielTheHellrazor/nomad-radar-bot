from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from bot.formatter import (
    format_deal_telegram_message,
    format_holidays_summary,
    format_user_status,
)
from bot.scheduler import DealScanOrchestrator
from calendar_visa.holidays_tr import HolidayWindowCalculator
from database import Database
from intelligence.campaign_radar import CampaignRadar
from intelligence.gemini_advisor import GeminiAdvisor
from models import TravelMode


class NomadTelegramBot:
    def __init__(self, token: str, db: Database) -> None:
        self.token = token
        self.db = db
        self.orchestrator = DealScanOrchestrator(db=db)
        self.holiday_calc = HolidayWindowCalculator()
        self.campaign_radar = CampaignRadar()
        self.advisor = GeminiAdvisor()

    def _main_keyboard(self) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔍 Şimdi Fırsat Tara", callback_data="scan_now"),
                    InlineKeyboardButton("🗓️ Köprü Tatiller", callback_data="show_holidays"),
                ],
                [
                    InlineKeyboardButton("🎒 Mod: Solo", callback_data="mode_solo"),
                    InlineKeyboardButton("💑 Mod: Çift", callback_data="mode_couple"),
                    InlineKeyboardButton("🎒+💑 İkisi De", callback_data="mode_both"),
                ],
                [
                    InlineKeyboardButton("🔥 Anlık Kampanyalar", callback_data="show_campaigns"),
                ],
            ]
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        settings = self.db.get_user_settings(update.effective_chat.id)
        text = (
            "👋 **NomadRadar: Akıllı Köprü Tatil & Ucuz Seyahat Botuna Hoş Geldiniz!**\n\n"
            "Bu bot hem **Solo (Yeşil Pasaport + Sofya/Selanik Ryanair Hack + 0€ Bedava/Hostel Konaklama)** "
            "hem de **Çift Modu (Siz + Kız Arkadaşınız: Yeşil+Bordo Pasaport Vizesiz, Az Aktarmalı & 8.0+ Özel Otel/Airbnb)** "
            "için yaklaşan tatilleri (örn. **28 Ekim öğleden sonra → 1 Kasım**) ve anlık indirimleri tarar.\n\n"
            + format_user_status(settings)
        )
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=self._main_keyboard()
        )

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        settings = self.db.get_user_settings(update.effective_chat.id)
        await update.message.reply_text(
            format_user_status(settings),
            parse_mode="Markdown",
            reply_markup=self._main_keyboard(),
        )

    async def cmd_tatiller(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        windows = self.holiday_calc.get_upcoming_windows(days_ahead=120)
        await update.message.reply_text(
            format_holidays_summary(windows), parse_mode="Markdown"
        )

    async def cmd_mod(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        arg = (context.args[0].lower() if context.args else "ikisi_de").strip()
        if arg in ("solo", "tek"):
            mode = TravelMode.SOLO
        elif arg in ("cift", "çift", "couple"):
            mode = TravelMode.COUPLE
        else:
            mode = TravelMode.BOTH

        settings = self.db.set_active_mode(update.effective_chat.id, mode)
        await update.message.reply_text(
            f"✅ Çalışma modu güncellendi!\n\n{format_user_status(settings)}",
            parse_mode="Markdown",
        )

    async def cmd_tara(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        country_arg = context.args[0].upper() if context.args else None
        await update.message.reply_text(
            "🔎 **Tatil pencereleri, uçuş/otobüs kombinasyonları ve konaklama fırsatları taranıyor...**",
            parse_mode="Markdown",
        )
        deals = await self.orchestrator.run_scan_for_user(
            chat_id=update.effective_chat.id,
            days_ahead=60,
            specific_country=country_arg,
            max_results_per_mode=2,
            force_notify=True,
        )
        if not deals:
            await update.message.reply_text(
                "⚠️ Belirttiğiniz kriter ve bütçe sınırında uygun fırsat bulunamadı. `/butce` veya `/cift_vize_ekle` ile ayarlarınızı genişletebilirsiniz."
            )
            return

        for deal in deals:
            await update.message.reply_text(
                format_deal_telegram_message(deal),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    async def cmd_hedef_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        if not context.args:
            await update.message.reply_text("Kullanım: `/hedef_ekle PT` veya `/hedef_ekle cift ME`", parse_mode="Markdown")
            return
        if len(context.args) >= 2 and context.args[0].lower() in ("cift", "çift", "couple"):
            mode = TravelMode.COUPLE
            code = context.args[1].upper()
        else:
            mode = TravelMode.SOLO
            code = context.args[0].upper()

        settings = self.db.add_destination(update.effective_chat.id, mode, code)
        await update.message.reply_text(
            f"✅ `{code}` hedef listesine eklendi!\n\n{format_user_status(settings)}",
            parse_mode="Markdown",
        )

    async def cmd_cift_vize_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        visa = context.args[0].upper() if context.args else "SCHENGEN"
        settings = self.db.add_visa(update.effective_chat.id, TravelMode.COUPLE, visa)
        await update.message.reply_text(
            f"🎉 Kız arkadaşınız için `{visa}` vizesi eklendi! Artık Çift Modunda da {visa} ülkeleri 0€ ek vize maliyetiyle taranacak.\n\n"
            + format_user_status(settings),
            parse_mode="Markdown",
        )

    async def cmd_vize_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        visa = context.args[0].upper() if context.args else "UK"
        settings = self.db.add_visa(update.effective_chat.id, TravelMode.SOLO, visa)
        await update.message.reply_text(
            f"✅ Solo Mod için `{visa}` vizesi eklendi!\n\n{format_user_status(settings)}",
            parse_mode="Markdown",
        )

    async def cmd_butce(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        if len(context.args) < 2:
            await update.message.reply_text(
                "Kullanım: `/butce solo 250` veya `/butce cift 600`",
                parse_mode="Markdown",
            )
            return
        mode_arg = context.args[0].lower()
        amount = float(context.args[1])
        mode = TravelMode.COUPLE if mode_arg in ("cift", "çift", "couple") else TravelMode.SOLO
        settings = self.db.set_budget(update.effective_chat.id, mode, amount)
        await update.message.reply_text(
            f"✅ Maksimum bütçe güncellendi!\n\n{format_user_status(settings)}",
            parse_mode="Markdown",
        )

    async def cmd_kampanyalar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        promos = await self.campaign_radar.fetch_live_error_fares(limit=6)
        lines = ["🔥 **Anlık Havayolu Kampanyaları & Error Fare Radarları:**\n"]
        for p in promos:
            lines.append(f"• **[{p['source']}]** {p['title']}\n  🔗 {p['link']}")
        await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)

    async def cmd_sor(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        question = " ".join(context.args) if context.args else "28 Ekim öğleden sonra Portekiz'e en ucuza nasıl giderim?"
        answer = await self.advisor.answer_freeform_question(question)
        await update.message.reply_text(answer, parse_mode="Markdown")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_chat:
            return
        await query.answer()
        data = query.data or ""
        chat_id = update.effective_chat.id

        if data == "scan_now":
            deals = await self.orchestrator.run_scan_for_user(
                chat_id=chat_id, days_ahead=60, max_results_per_mode=2, force_notify=True
            )
            for deal in deals:
                await query.message.reply_text(
                    format_deal_telegram_message(deal),
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
        elif data == "show_holidays":
            windows = self.holiday_calc.get_upcoming_windows(days_ahead=120)
            await query.message.reply_text(
                format_holidays_summary(windows), parse_mode="Markdown"
            )
        elif data in ("mode_solo", "mode_couple", "mode_both"):
            mode_map = {
                "mode_solo": TravelMode.SOLO,
                "mode_couple": TravelMode.COUPLE,
                "mode_both": TravelMode.BOTH,
            }
            settings = self.db.set_active_mode(chat_id, mode_map[data])
            await query.message.reply_text(
                f"✅ Mod değiştirildi!\n\n{format_user_status(settings)}",
                parse_mode="Markdown",
            )
        elif data == "show_campaigns":
            promos = await self.campaign_radar.fetch_live_error_fares(limit=5)
            lines = ["🔥 **Anlık Kampanya & Hatalı Fiyat (Error Fare) Akışı:**\n"]
            for p in promos:
                lines.append(f"• **[{p['source']}]** {p['title']}\n  🔗 {p['link']}")
            await query.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)

    def build_application(self) -> Application:
        app = Application.builder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("durum", self.cmd_durum))
        app.add_handler(CommandHandler("tatiller", self.cmd_tatiller))
        app.add_handler(CommandHandler("mod", self.cmd_mod))
        app.add_handler(CommandHandler("tara", self.cmd_tara))
        app.add_handler(CommandHandler("hedef_ekle", self.cmd_hedef_ekle))
        app.add_handler(CommandHandler("cift_vize_ekle", self.cmd_cift_vize_ekle))
        app.add_handler(CommandHandler("vize_ekle", self.cmd_vize_ekle))
        app.add_handler(CommandHandler("butce", self.cmd_butce))
        app.add_handler(CommandHandler("kampanyalar", self.cmd_kampanyalar))
        app.add_handler(CommandHandler("sor", self.cmd_sor))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        return app
