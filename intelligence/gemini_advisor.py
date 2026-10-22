from config import GEMINI_API_KEY, GEMINI_MODEL
from models import DealPackage, TravelMode


class GeminiAdvisor:
    """
    Yakalanan seyahat paketini Gemini AI ile yorumlar;
    kullanıcıya kaç gün izinle kaç gün tatil yapacağını, neden bu rotanın ucuz olduğunu
    ve bedava/konforlu konaklama stratejisini açıklar.
    GEMINI_API_KEY tanımlı değilse veya kota doluysa akıllı kural tabanlı Türkçe analiz üretir.
    """

    async def generate_commentary(self, deal: DealPackage) -> str:
        if GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=GEMINI_API_KEY)
                prompt = (
                    f"Sen uzman bir ucuz seyahat ve tatil optimizasyon asistanısın. "
                    f"Aşağıdaki fırsatı Türkçe olarak 3-4 cümlede çok vurucu ve samimi şekilde yorumla:\n"
                    f"- Mod: {'SOLO (1 Kişi Yeşil Pasaport)' if deal.mode == TravelMode.SOLO else 'ÇİFT MODU (2 Kişi: Yeşil + Bordo Pasaport, Konforlu & Vize Sorunsuz)'}\n"
                    f"- Hedef: {deal.country.name_tr} / {deal.city_name_tr}\n"
                    f"- Tatil Penceresi: {deal.window.title} ({deal.window.leave_days_required} gün izinle {deal.window.total_days} gün tatil)\n"
                    f"- Ulaşım: {deal.route.strategy_name} (Kişi başı Gidiş-Dönüş {deal.route.roundtrip_price_per_person_eur}€)\n"
                    f"- Konaklama: {deal.stay.title} ({deal.stay.nights_charged} gece toplam {deal.stay.total_stay_cost_eur}€)\n"
                    f"- Vize Durumu: {deal.visa_note}\n"
                    f"- Toplam Paket Maliyeti: {deal.grand_total_eur}€ (Piyasa ortalamasına göre %{deal.discount_vs_baseline_pct} daha ucuz)"
                )
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                if response and response.text:
                    deal.ai_commentary = response.text.strip()
                    return deal.ai_commentary
            except Exception:
                pass

        # Akıllı Yerel Yorum Üretici (Offline / Zero-Cost Fallback)
        if deal.mode == TravelMode.SOLO:
            free_stays = [s for s in deal.alternative_stays if s.is_free_stay]
            free_total = round(deal.transport_total_eur + deal.visa_cost_total_eur, 2)
            night_save_msg = (
                f"Üstelik gece yolculuğu sayesinde {deal.window.nights} gece yerine sadece {deal.stay.nights_charged} gece konaklama ödüyorsun! "
                if deal.route.saved_nights_count > 0
                else ""
            )
            free_msg = (
                f"Eğer {free_stays[0].provider} üzerinden 0€ bedava konaklama tercih edersen tüm seyahat cebinden sadece **{free_total:.0f}€**'ya çıkıyor!"
                if free_stays
                else ""
            )
            commentary = (
                f"💡 **AI Seyahat Analizi (Solo Mod):** Sadece **{deal.window.leave_days_required:g} gün izin** kullanarak "
                f"tam **{deal.window.total_days:g} gün** {deal.country.name_tr} ({deal.city_name_tr}) tatili yapabiliyorsun. "
                f"Direkt uçuşların pahalı olduğu bu dönemde **{deal.route.strategy_name}** kullanarak ulaşımı kişi başı "
                f"**{deal.route.roundtrip_price_per_person_eur:.0f}€**'ya düşürdük. {night_save_msg}{free_msg}"
            )
        else:
            commentary = (
                f"💑 **AI Seyahat Analizi (Çift & Konfor Modu):** Kız arkadaşınla birlikte **hiçbir vize randevusu stresi yaşamadan** "
                f"ve yorucu otobüs aktarmalarıyla uğraşmadan **{deal.window.leave_days_required:g} gün izinle {deal.window.total_days:g} gün** "
                f"{deal.country.name_tr} ({deal.city_name_tr}) kaçamağı! Mesai saatlerine uyumlu direkt uçuşlar ve "
                f"**{deal.stay.rating} puanlı özel konaklama** dahil **2 kişi her şey dahil toplam {deal.grand_total_eur:.0f}€** "
                f"(kişi başı sadece **{deal.per_person_total_eur:.0f}€**, normal fiyattan **%{deal.discount_vs_baseline_pct} indirimli**)."
            )

        deal.ai_commentary = commentary
        return commentary

    async def answer_freeform_question(self, question: str) -> str:
        if GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=GEMINI_API_KEY)
                sys_prompt = (
                    "Sen NomadRadar adında, Türkiye'den (İstanbul çıkışlı) seyahat eden "
                    "bir kullanıcıya (Yeşil pasaportlu Solo mod ve Yeşil+Bordo pasaportlu Çift modu olan) "
                    "köprü izinler, Sofya/Selanik üzerinden Ryanair/WizzAir sınır hack'leri, "
                    "bedava konaklama (TrustedHousesitters, Couchsurfing, gece treni) ve vizesiz çift rotaları "
                    "konusunda nokta atışı tavsiyeler veren bir uzmansın. Kısa, net ve eyleme dönük cevap ver.\n\n"
                    f"Kullanıcı Sorusu: {question}"
                )
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=sys_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception:
                pass

        return (
            f"🤖 **NomadRadar AI Tavsiyesi (`{question}`):**\n"
            "• **Solo (Yeşil Pasaport) İçin:** Resmi tatillerde (örn. 28 Ekim öğleden sonra -> 1 Kasım) İstanbul direkt uçuşları şiştiğinde "
            "Salı/Çarşamba akşamı **Halkalı-Sofya Ekspresi** veya **Esenler-Sofya/Selanik gece otobüsü (25€)** ile çıkıp sabah **Ryanair/WizzAir (15-25€)** ile "
            "Portekiz, İtalya veya İspanya'ya uçmak maliyeti %60 düşürür ve 1 gece otel parasını sıfırlar.\n"
            "• **Çift Modu (Yeşil + Bordo Pasaport) İçin:** Vize stresi olmadan direkt uçuşla **Karadağ (Tivat/Podgorica), Sırbistan (Belgrad), Bosna (Saraybosna)** "
            "veya kapıda ekspres vizeyle **Rodos / Sakız / Midilli** en yüksek konfor/fiyat oranını sunar."
        )
