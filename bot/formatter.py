import html
import re
from typing import List
from config import EUR_TO_TRY
from models import DealPackage, TravelMode, TravelWindow, UserSettings


def clean_to_telegram_html(raw_text: str) -> str:
    """
    AI (Gemini / OpenRouter) veya sistem tarafından üretilen metinlerdeki
    Markdown (**kalın**, *italik*, `kod`) işaretlerini Telegram'ın yerel HTML
    formatına (<b>, <i>, <code>) güvenli şekilde dönüştürür.
    """
    if not raw_text:
        return ""
    escaped = html.escape(raw_text)
    # **bold** -> <b>bold</b>
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped, flags=re.DOTALL)
    # `code` -> <code>code</code>
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    # Kalan tekli ** varsa temizle
    escaped = escaped.replace("**", "")
    return escaped


def format_deal_telegram_message(deal: DealPackage) -> str:
    mode_header = (
        "🎒 <b>[SOLO / GEZGİN MODU — YEŞİL PASAPORT]</b>"
        if deal.mode == TravelMode.SOLO
        else "💑 <b>[ÇİFT &amp; KONFOR MODU — 2 KİŞİ (YEŞİL + BORDO)]</b>"
    )
    badge_line = (
        f"🏷️ <i>{html.escape(deal.campaign_badge)}</i>\n"
        if deal.campaign_badge
        else ""
    )

    out_legs_text = "\n".join(
        f"  ▫️ <code>{html.escape(leg.departure_str)}</code> → <code>{html.escape(leg.arrival_str)}</code>\n"
        f"     <b>{html.escape(leg.origin)} → {html.escape(leg.destination)}</b> ({html.escape(leg.carrier)}) — <b>{leg.price_eur_per_person:.0f}€/kişi</b>"
        for leg in deal.route.outbound_legs
    )
    in_legs_text = "\n".join(
        f"  ▫️ <code>{html.escape(leg.departure_str)}</code> → <code>{html.escape(leg.arrival_str)}</code>\n"
        f"     <b>{html.escape(leg.origin)} → {html.escape(leg.destination)}</b> ({html.escape(leg.carrier)}) — <b>{leg.price_eur_per_person:.0f}€/kişi</b>"
        for leg in deal.route.inbound_legs
    )

    stay_block = (
        f"🏨 <b>Konaklama ({deal.stay.nights_charged} Gece):</b> {html.escape(deal.stay.title)}\n"
        f"  ▫️ Puan: ⭐ <b>{deal.stay.rating}/10</b> | Gecelik: <b>{deal.stay.price_per_night_total_eur:.0f}€</b> "
        f"(Toplam: <b>{deal.stay.total_stay_cost_eur:.0f}€</b> • <i>%{deal.stay.discount_pct} İndirim</i>)"
    )

    free_stays_block = ""
    if deal.mode == TravelMode.SOLO:
        free_options = [s for s in deal.alternative_stays if s.is_free_stay]
        if free_options:
            free_lines = "\n".join(
                f"  ▫️ 🆓 <b>{html.escape(fs.provider)}:</b> {html.escape(fs.title)}"
                for fs in free_options[:2]
            )
            free_only_cost = round(deal.transport_total_eur + deal.visa_cost_total_eur, 2)
            free_stays_block = (
                f"\n\n🏡 <b>Bedava (0€) Konaklama Alternatifleri:</b>\n{free_lines}\n"
                f"  👉 <i>Bedava konaklama seçerseniz tüm seyahat toplamı sadece <b>{free_only_cost:.0f}€</b>!</i>"
            )

    baseline_total = deal.country.typical_package_Baseline_eur * deal.passengers
    saved_eur = max(0.0, baseline_total - deal.grand_total_eur)
    transport_tl = deal.transport_total_eur * EUR_TO_TRY
    grand_tl = deal.grand_total_eur * EUR_TO_TRY

    price_summary = (
        f"📊 <b>Normal Dönem Ortalaması:</b> <s>{baseline_total:.0f}€</s> ➡️ <b>Şu An: {deal.grand_total_eur:.0f}€ (~{grand_tl:,.0f} TL)</b>\n"
        f"🔥 <b>Normal Zamandan %{deal.discount_vs_baseline_pct} DAHA UCUZ! ({saved_eur:.0f}€ Net İndirim)</b>\n"
        f"💰 <b>TOPLAM PAKET (1 Kişi Her Şey Dahil): {deal.grand_total_eur:.0f}€ (~{grand_tl:,.0f} TL)</b>"
        if deal.mode == TravelMode.SOLO
        else f"📊 <b>Normal Dönem Ortalaması:</b> <s>{baseline_total:.0f}€</s> (2 Kişi) ➡️ <b>Şu An: {deal.grand_total_eur:.0f}€ (~{grand_tl:,.0f} TL)</b>\n"
        f"🔥 <b>Normal Zamandan %{deal.discount_vs_baseline_pct} DAHA UCUZ! ({saved_eur:.0f}€ Net İndirim)</b>\n"
        f"💰 <b>2 KİŞİ TOPLAM PAKET (2 Kişi: Uçak x2 + Özel Oda + Vize): {deal.grand_total_eur:.0f}€ (~{grand_tl:,.0f} TL)</b> <i>(Kişi Başı: <b>{deal.per_person_total_eur:.0f}€</b>)</i>"
    )

    ai_block = ""
    if deal.ai_commentary:
        ai_html = clean_to_telegram_html(deal.ai_commentary)
        ai_block = f"\n<blockquote>{ai_html}</blockquote>\n"

    route_url = html.escape(deal.route.booking_hint_url, quote=True)
    stay_url = html.escape(deal.stay.booking_url, quote=True)

    return (
        f"{mode_header}\n"
        f"{badge_line}"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌍 <b>{html.escape(deal.country.name_tr)} — {html.escape(deal.city_name_tr)} ({html.escape(deal.city_code)})</b>\n"
        f"🗓️ <b>{html.escape(deal.window.title)}</b>\n"
        f"⏱️ <b>Süre:</b> {deal.window.total_days:g} Gün  |  🎯 <b>Harcanacak İzin:</b> Sadece <b>{deal.window.leave_days_required:g} Gün!</b>\n"
        f"🛂 <b>Vize:</b> {html.escape(deal.visa_note)}\n\n"
        f"✈️ <b>Ulaşım:</b> {html.escape(deal.route.strategy_name)}\n"
        f"<b>Gidiş:</b>\n{out_legs_text}\n"
        f"<b>Dönüş:</b>\n{in_legs_text}\n"
        f"<i>(Ulaşım Toplamı: {deal.transport_total_eur:.0f}€ / ~{transport_tl:,.0f} TL)</i>\n\n"
        f"{stay_block}"
        f"{free_stays_block}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{price_summary}\n"
        f"{ai_block}"
        f"\n🔗 <a href=\"{route_url}\">✈️ Ulaşım / Bilet Linki</a>   |   <a href=\"{stay_url}\">🏨 Konaklama Linki</a>"
    )


def format_holidays_summary(windows: List[TravelWindow]) -> str:
    lines = ["🗓️ <b>Yaklaşan Resmi Tatil, Köprü İzin ve Kaçamak Pencereleri</b>\n━━━━━━━━━━━━━━━━━━━━━━"]
    for idx, w in enumerate(windows, start=1):
        tag = (
            "🌉 <b>[KÖPRÜ TATİL]</b>"
            if w.is_bridge_holiday
            else ("🔥 <b>[HAFTA İÇİ FIRSAT]</b>" if w.is_weekday_flash else "🌴 <b>[HAFTASONU]</b>")
        )
        lines.append(
            f"{idx}. {tag} <b>{html.escape(w.title)}</b>\n"
            f"   ▫️ Çıkış: <code>{w.start_dt.strftime('%d.%m.%Y %H:%M')}</code> → Dönüş: <code>{w.end_dt.strftime('%d.%m.%Y %H:%M')}</code>\n"
            f"   ▫️ Harcanan Yıllık İzin (izin): <b>{w.leave_days_required:g} Gün</b> ➡️ Kazanılan Tatil: <b>{w.total_days:g} Gün ({w.nights} Gece)</b>"
        )
    return "\n\n".join(lines)


def format_user_status(settings: UserSettings) -> str:
    mode_map = {
        TravelMode.SOLO: "🎒 Sadece Solo Mod (Yeşil Pasaport - Gezgin/Hack)",
        TravelMode.COUPLE: "💑 Sadece Çift Modu (Yeşil + Bordo - Konfor &amp; Vizesiz)",
        TravelMode.BOTH: "🎒+💑 Her İki Mod Aktif (Solo + Çift Birlikte Taranıyor)",
    }
    solo_visas_str = (
        ", ".join(settings.solo_visas)
        if settings.solo_visas
        else "Yok (Yeşil Pasaport Vizesizler + İleri Tarihli Randevulular)"
    )
    couple_visas_str = (
        ", ".join(settings.couple_visas)
        if settings.couple_visas
        else "Yok (Bordo Pasaporta Vizesiz &amp; Kapıda Vize Ülkeleri)"
    )

    return (
        "🧭 <b>NomadRadar Seyahat Asistanı Durumu</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"▫️ <b>Aktif Mod:</b> {mode_map[settings.active_mode]}\n"
        f"▫️ <b>Solo Maks. Bütçe:</b> <b>{settings.solo_max_budget_eur:.0f}€</b> (1 Kişi)\n"
        f"▫️ <b>Çift Maks. Bütçe:</b> <b>{settings.couple_max_budget_eur:.0f}€</b> (2 Kişi Toplam)\n"
        f"▫️ <b>Solo Ülkeler ({len(settings.solo_watchlist)}):</b> <code>{', '.join(settings.solo_watchlist)}</code>\n"
        f"▫️ <b>Çift Ülkeler ({len(settings.couple_watchlist)}):</b> <code>{', '.join(settings.couple_watchlist)}</code>\n"
        f"▫️ <b>Solo Ek Vizeler:</b> <code>{html.escape(solo_visas_str)}</code>\n"
        f"▫️ <b>Çift (Partner) Ek Vizeleri:</b> <code>{html.escape(couple_visas_str)}</code>\n\n"
        "💡 <b>Komut Rehberi:</b>\n"
        "▫️ <code>/tara</code> — Yaklaşan tatiller (örn. 29 Ekim) için anında fırsat tara\n"
        "▫️ <code>/tara PT</code> veya <code>/tara ME</code> — Tek bir ülke için paket çıkar\n"
        "▫️ <code>/mod solo</code> | <code>/mod cift</code> | <code>/mod ikisi_de</code> — Mod değiştir\n"
        "▫️ <code>/tatiller</code> — Köprü izin ve tatil takvimini gör\n"
        "▫️ <code>/cift_vize_ekle SCHENGEN</code> — Partner vize aldığında Çift Moduna Avrupa'yı aç\n"
        "▫️ <code>/butce solo 220</code> veya <code>/butce cift 600</code> — Bütçe sınırını güncelle\n"
        "▫️ <code>/sor [sorunuz]</code> — AI seyahat asistanına özel soru sor"
    )
