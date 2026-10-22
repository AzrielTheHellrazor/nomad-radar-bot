from typing import List
from models import DealPackage, TravelMode, TravelWindow, UserSettings


def format_deal_telegram_message(deal: DealPackage) -> str:
    mode_header = (
        "🎒 **[SOLO / GEZGİN MODU — YEŞİL PASAPORT]**"
        if deal.mode == TravelMode.SOLO
        else "💑 **[ÇİFT & KONFOR MODU — 2 KİŞİ (YEŞİL + BORDO)]**"
    )
    badge_line = f"{deal.campaign_badge}\n" if deal.campaign_badge else ""

    out_legs_text = "\n".join(
        f"  • `{leg.departure_str}` → `{leg.arrival_str}` | **{leg.origin} → {leg.destination}** ({leg.carrier}) — **{leg.price_eur_per_person:.0f}€/kişi**"
        for leg in deal.route.outbound_legs
    )
    in_legs_text = "\n".join(
        f"  • `{leg.departure_str}` → `{leg.arrival_str}` | **{leg.origin} → {leg.destination}** ({leg.carrier}) — **{leg.price_eur_per_person:.0f}€/kişi**"
        for leg in deal.route.inbound_legs
    )

    stay_block = (
        f"🏨 **Konaklama ({deal.stay.nights_charged} Gece):** {deal.stay.title}\n"
        f"  • Puan: ⭐ **{deal.stay.rating}/10** | Gecelik: **{deal.stay.price_per_night_total_eur:.0f}€** "
        f"(Toplam: **{deal.stay.total_stay_cost_eur:.0f}€**, %{deal.stay.discount_pct} İndirim)"
    )

    free_stays_block = ""
    if deal.mode == TravelMode.SOLO:
        free_options = [s for s in deal.alternative_stays if s.is_free_stay]
        if free_options:
            free_lines = "\n".join(
                f"  • 🆓 **{fs.provider}:** {fs.title}" for fs in free_options[:2]
            )
            free_only_cost = round(deal.transport_total_eur + deal.visa_cost_total_eur, 2)
            free_stays_block = (
                f"\n\n🏡 **Bedava (0€) Konaklama Alternatifleri:**\n{free_lines}\n"
                f"  👉 *Bedava konaklama seçerseniz tüm seyahat toplamı sadece **{free_only_cost:.0f}€**!*"
            )

    price_summary = (
        f"💰 **TOPLAM PAKET (1 Kişi Her Şey Dahil): {deal.grand_total_eur:.0f}€** "
        f"*(Piyasa ortalamasından %{deal.discount_vs_baseline_pct} daha ucuz!)*"
        if deal.mode == TravelMode.SOLO
        else f"💰 **2 KİŞİ TOPLAM PAKET (2 Kişi: Uçak x2 + Özel Oda + Vize): {deal.grand_total_eur:.0f}€** "
        f"*(Kişi Başı: **{deal.per_person_total_eur:.0f}€** — Normal fiyattan %{deal.discount_vs_baseline_pct} indirimli!)*"
    )

    return (
        f"{mode_header}\n"
        f"{badge_line}"
        f"🌍 **{deal.country.name_tr} — {deal.city_name_tr} ({deal.city_code})**\n"
        f"🗓️ **{deal.window.title}**\n"
        f"⏱️ **Tatil Süresi:** {deal.window.total_days:g} Gün | **Harcanacak İzin:** Sadece **{deal.window.leave_days_required:g} Gün!**\n"
        f"🛂 **Vize:** {deal.visa_note}\n\n"
        f"✈️ **Ulaşım Stratejisi:** {deal.route.strategy_name}\n"
        f"**Gidiş:**\n{out_legs_text}\n"
        f"**Dönüş:**\n{in_legs_text}\n"
        f"*(Ulaşım Toplamı: {deal.transport_total_eur:.0f}€)*\n\n"
        f"{stay_block}"
        f"{free_stays_block}\n\n"
        f"{price_summary}\n\n"
        f"{deal.ai_commentary}\n\n"
        f"🔗 [Ulaşım Linki]({deal.route.booking_hint_url}) | [Konaklama Linki]({deal.stay.booking_url})"
    )


def format_holidays_summary(windows: List[TravelWindow]) -> str:
    lines = ["🗓️ **Yaklaşan Resmi Tatil, Köprü İzin ve Kaçamak Pencereleri:**\n"]
    for idx, w in enumerate(windows, start=1):
        tag = "🌉 [KÖPRÜ TATİL]" if w.is_bridge_holiday else ("🔥 [HAFTA İÇİ FIRSAT]" if w.is_weekday_flash else "🌴 [HAFTASONU]")
        lines.append(
            f"{idx}. {tag} **{w.title}**\n"
            f"   • Çıkış: `{w.start_dt.strftime('%d.%m.%Y %H:%M')}` → Dönüş: `{w.end_dt.strftime('%d.%m.%Y %H:%M')}`\n"
            f"   • Harcanan Yıllık İzin (izin): **{w.leave_days_required:g} Gün** ➡️ Kazanılan Tatil: **{w.total_days:g} Gün ({w.nights} Gece)**"
        )
    return "\n\n".join(lines)


def format_user_status(settings: UserSettings) -> str:
    mode_map = {
        TravelMode.SOLO: "🎒 Sadece Solo Mod (Yeşil Pasaport - Gezgin/Hack)",
        TravelMode.COUPLE: "💑 Sadece Çift Modu (Yeşil + Bordo - Konfor & Vizesiz)",
        TravelMode.BOTH: "🎒+💑 Her İki Mod Aktif (Solo + Çift Birlikte Taranıyor)",
    }
    solo_visas_str = ", ".join(settings.solo_visas) if settings.solo_visas else "Yok (Yeşil Pasaport Vizesizler + İleri Tarihli Randevulular)"
    couple_visas_str = ", ".join(settings.couple_visas) if settings.couple_visas else "Yok (Bordo Pasaporta Vizesiz & Kapıda Vize Ülkeleri)"

    return (
        "🧭 **NomadRadar Seyahat Asistanı Durumu**\n\n"
        f"• **Aktif Çalışma Modu:** {mode_map[settings.active_mode]}\n"
        f"• **Solo Mod Maks. Bütçe:** {settings.solo_max_budget_eur:.0f}€ (1 Kişi)\n"
        f"• **Çift Modu Maks. Bütçe:** {settings.couple_max_budget_eur:.0f}€ (2 Kişi Toplam)\n"
        f"• **Solo Takip Edilen Ülkeler ({len(settings.solo_watchlist)}):** `{', '.join(settings.solo_watchlist)}`\n"
        f"• **Çift Takip Edilen Ülkeler ({len(settings.couple_watchlist)}):** `{', '.join(settings.couple_watchlist)}`\n"
        f"• **Solo Ek Vizeleriniz:** `{solo_visas_str}`\n"
        f"• **Çift (Partner) Ek Vizeleri:** `{couple_visas_str}`\n\n"
        "💡 **Hızlı Komutlar:**\n"
        "• `/tara` — Yaklaşan tatiller (örn. 29 Ekim) için anında fırsat taraması yap\n"
        "• `/tara PT` veya `/tara ME` — Belirli bir ülke için anında paket çıkar\n"
        "• `/mod solo` | `/mod cift` | `/mod ikisi_de` — Mod değiştir\n"
        "• `/tatiller` — Köprü izin ve tatil takvimini gör\n"
        "• `/cift_vize_ekle SCHENGEN` — Kız arkadaşınız vize aldığında Çift Moduna Avrupa'yı aç\n"
        "• `/butce solo 200` veya `/butce cift 600` — Bütçe sınırını güncelle\n"
        "• `/sor [sorunuz]` — Gemini AI seyahat asistanına rota/konaklama sor"
    )
