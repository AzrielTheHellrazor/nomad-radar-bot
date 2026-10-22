import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from bot.formatter import (
    clean_to_telegram_html,
    format_deal_telegram_message,
    format_holidays_summary,
    format_user_status,
)
from bot.scheduler import DealScanOrchestrator
from calendar_visa.holidays_tr import HolidayWindowCalculator
from database import Database
from intelligence.campaign_radar import CampaignRadar
from intelligence.gemini_advisor import GeminiAdvisor
from models import DealPackage, TravelMode


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

    def _deal_buttons(self, deal: DealPackage) -> InlineKeyboardMarkup:
        buttons = []
        if deal.route.booking_hint_url.startswith("http"):
            buttons.append(InlineKeyboardButton("✈️ Ulaşımı İncele", url=deal.route.booking_hint_url))
        if deal.stay.booking_url.startswith("http"):
            buttons.append(InlineKeyboardButton("🏨 Konaklamayı İncele", url=deal.stay.booking_url))
        return InlineKeyboardMarkup([buttons]) if buttons else self._main_keyboard()

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        settings = self.db.get_user_settings(update.effective_chat.id)
        text = (
            "👋 <b>NomadRadar: Akıllı Köprü Tatil &amp; Ucuz Seyahat Botuna Hoş Geldiniz!</b>\n\n"
            "Bu bot hem <b>Solo (Yeşil Pasaport + Sofya/Selanik Ryanair Hack + 0€ Bedava/Hostel Konaklama)</b> "
            "hem de <b>Çift Modu (Siz + Kız Arkadaşınız: Yeşil+Bordo Pasaport Vizesiz, Az Aktarmalı &amp; 8.0+ Özel Otel/Airbnb)</b> "
            "için yaklaşan tatilleri (örn. <b>28 Ekim öğleden sonra → 1 Kasım</b>) ve anlık indirimleri tarar.\n\n"
            + format_user_status(settings)
        )
        await update.message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=self._main_keyboard()
        )

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        settings = self.db.get_user_settings(update.effective_chat.id)
        await update.message.reply_text(
            format_user_status(settings),
            parse_mode=ParseMode.HTML,
            reply_markup=self._main_keyboard(),
        )

    async def cmd_tatiller(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        windows = self.holiday_calc.get_upcoming_windows(days_ahead=120)
        await update.message.reply_text(
            format_holidays_summary(windows), parse_mode=ParseMode.HTML
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
            f"✅ <b>Çalışma modu güncellendi!</b>\n\n{format_user_status(settings)}",
            parse_mode=ParseMode.HTML,
            reply_markup=self._main_keyboard(),
        )

    async def cmd_tara(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        country_arg = context.args[0].upper() if context.args else None
        await update.message.reply_text(
            "🔎 <b>Tatil pencereleri, uçuş/otobüs kombinasyonları ve konaklama fırsatları taranıyor...</b>",
            parse_mode=ParseMode.HTML,
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
                "⚠️ Belirttiğiniz kriter ve bütçe sınırında uygun fırsat bulunamadı. <code>/butce</code> veya <code>/cift_vize_ekle</code> ile ayarlarınızı genişletebilirsiniz.",
                parse_mode=ParseMode.HTML,
            )
            return

        for deal in deals:
            msg_text = format_deal_telegram_message(deal)
            try:
                await update.message.reply_text(
                    msg_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=self._deal_buttons(deal),
                    disable_web_page_preview=True,
                )
            except BadRequest:
                await update.message.reply_text(
                    msg_text,
                    disable_web_page_preview=True,
                )

    async def cmd_hedef_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        if not context.args:
            await update.message.reply_text(
                "Kullanım: <code>/hedef_ekle PT</code> veya <code>/hedef_ekle cift ME</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        if len(context.args) >= 2 and context.args[0].lower() in ("cift", "çift", "couple"):
            mode = TravelMode.COUPLE
            code = context.args[1].upper()
        else:
            mode = TravelMode.SOLO
            code = context.args[0].upper()

        settings = self.db.add_destination(update.effective_chat.id, mode, code)
        await update.message.reply_text(
            f"✅ <code>{html.escape(code)}</code> hedef listesine eklendi!\n\n{format_user_status(settings)}",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_cift_vize_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        visa = context.args[0].upper() if context.args else "SCHENGEN"
        settings = self.db.add_visa(update.effective_chat.id, TravelMode.COUPLE, visa)
        await update.message.reply_text(
            f"🎉 Kız arkadaşınız için <code>{html.escape(visa)}</code> vizesi eklendi! Artık Çift Modunda da {html.escape(visa)} ülkeleri 0€ ek vize maliyetiyle taranacak.\n\n"
            + format_user_status(settings),
            parse_mode=ParseMode.HTML,
        )

    async def cmd_vize_ekle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        visa = context.args[0].upper() if context.args else "UK"
        settings = self.db.add_visa(update.effective_chat.id, TravelMode.SOLO, visa)
        await update.message.reply_text(
            f"✅ Solo Mod için <code>{html.escape(visa)}</code> vizesi eklendi!\n\n{format_user_status(settings)}",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_butce(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.effective_chat or not update.message:
            return
        if len(context.args) < 2:
            await update.message.reply_text(
                "Kullanım: <code>/butce solo 250</code> veya <code>/butce cift 600</code>",
                parse_mode=ParseMode.HTML,
            )
            return
        mode_arg = context.args[0].lower()
        amount = float(context.args[1])
        mode = TravelMode.COUPLE if mode_arg in ("cift", "çift", "couple") else TravelMode.SOLO
        settings = self.db.set_budget(update.effective_chat.id, mode, amount)
        await update.message.reply_text(
            f"✅ <b>Maksimum bütçe güncellendi!</b>\n\n{format_user_status(settings)}",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_kampanyalar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        promos = await self.campaign_radar.fetch_live_error_fares(limit=6)
        lines = ["🔥 <b>Anlık Havayolu Kampanyaları &amp; Error Fare Radarları</b>\n━━━━━━━━━━━━━━━━━━━━━━"]
        for p in promos:
            title = html.escape(p["title"])
            src = html.escape(p["source"])
            link = html.escape(p["link"], quote=True)
            lines.append(f"▫️ <b>[{src}]</b> {title}\n   🔗 <a href=\"{link}\">Kampanyaya Git</a>")
        await update.message.reply_text(
            "\n\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )

    async def cmd_sor(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message:
            return
        question = " ".join(context.args) if context.args else "28 Ekim öğleden sonra Portekiz'e en ucuza nasıl giderim?"
        answer = await self.advisor.answer_freeform_question(question)
        await update.message.reply_text(
            clean_to_telegram_html(answer), parse_mode=ParseMode.HTML
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query or not update.effective_chat:
            return
        await query.answer()
        data = query.data or ""
        chat_id = update.effective_chat.id

        if data == "scan_now":
            await query.message.reply_text(
                "🔎 <b>Fırsatlar taranıyor, lütfen bekleyin...</b>",
                parse_mode=ParseMode.HTML,
            )
            deals = await self.orchestrator.run_scan_for_user(
                chat_id=chat_id, days_ahead=60, max_results_per_mode=2, force_notify=True
            )
            for deal in deals:
                msg_text = format_deal_telegram_message(deal)
                try:
                    await query.message.reply_text(
                        msg_text,
                        parse_mode=ParseMode.HTML,
                        reply_markup=self._deal_buttons(deal),
                        disable_web_page_preview=True,
                    )
                except BadRequest:
                    await query.message.reply_text(
                        msg_text,
                        disable_web_page_preview=True,
                    )
        elif data == "show_holidays":
            windows = self.holiday_calc.get_upcoming_windows(days_ahead=120)
            await query.message.reply_text(
                format_holidays_summary(windows), parse_mode=ParseMode.HTML
            )
        elif data in ("mode_solo", "mode_couple", "mode_both"):
            mode_map = {
                "mode_solo": TravelMode.SOLO,
                "mode_couple": TravelMode.COUPLE,
                "mode_both": TravelMode.BOTH,
            }
            settings = self.db.set_active_mode(chat_id, mode_map[data])
            await query.message.reply_text(
                f"✅ <b>Mod değiştirildi!</b>\n\n{format_user_status(settings)}",
                parse_mode=ParseMode.HTML,
                reply_markup=self._main_keyboard(),
            )
        elif data == "show_campaigns":
            promos = await self.campaign_radar.fetch_live_error_fares(limit=5)
            lines = ["🔥 <b>Anlık Kampanya &amp; Hatalı Fiyat (Error Fare) Akışı</b>\n━━━━━━━━━━━━━━━━━━━━━━"]
            for p in promos:
                title = html.escape(p["title"])
                src = html.escape(p["source"])
                link = html.escape(p["link"], quote=True)
                lines.append(f"▫️ <b>[{src}]</b> {title}\n   🔗 <a href=\"{link}\">İncele</a>")
            await query.message.reply_text(
                "\n\n".join(lines), parse_mode=ParseMode.HTML, disable_web_page_preview=True
            )

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
