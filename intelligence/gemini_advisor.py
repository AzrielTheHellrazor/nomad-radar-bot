import httpx
from config import GEMINI_API_KEY, GEMINI_MODEL, OPENROUTER_KEY, OPENROUTER_MODEL
from models import DealPackage, TravelMode


class GeminiAdvisor:
    """
    Yakalanan seyahat paketini Gemini AI veya OpenRouter AI ile yorumlar;
    kullanıcıya kaç gün izinle kaç gün tatil yapacağını, neden bu rotanın ucuz olduğunu
    ve bedava/konforlu konaklama stratejisini açıklar.
    Sırasıyla:
      1. GEMINI_API_KEY (Google AI Studio resmi SDK)
      2. OPENROUTER_KEY (OpenRouter REST API yedek/alternatif motoru)
      3. Akıllı Yerel Kural Tabanlı Türkçe Analiz (Offline / Sıfır Maliyet Yedeği)
    """

    async def _call_openrouter(self, prompt: str) -> str | None:
        if not OPENROUTER_KEY:
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENROUTER_MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
        except Exception:
            pass
        return None

    async def generate_commentary(self, deal: DealPackage) -> str:
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

        # 1. Öncelik: Google Gemini Resmi SDK
        if GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
                if response and response.text:
                    deal.ai_commentary = response.text.strip()
                    return deal.ai_commentary
            except Exception:
                pass

        # 2. Öncelik: OpenRouter API (OPENROUTER_KEY)
        or_text = await self._call_openrouter(prompt)
        if or_text:
            deal.ai_commentary = or_text
            return deal.ai_commentary

        # 3. Öncelik: Akıllı Yerel Yorum Üretici (Offline / Zero-Cost Fallback)
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
        sys_prompt = (
            "Sen NomadRadar adında, Türkiye'den (İstanbul çıkışlı) seyahat eden "
            "bir kullanıcıya (Yeşil pasaportlu Solo mod ve Yeşil+Bordo pasaportlu Çift modu olan) "
            "köprü izinler, Sofya/Selanik üzerinden Ryanair/WizzAir sınır hack'leri, "
            "bedava konaklama (TrustedHousesitters, Couchsurfing, gece treni) ve vizesiz çift rotaları "
            "konusunda nokta atışı tavsiyeler veren bir uzmansın. Kısa, net ve eyleme dönük cevap ver.\n\n"
            f"Kullanıcı Sorusu: {question}"
        )

        if GEMINI_API_KEY:
            try:
                from google import genai

                client = genai.Client(api_key=GEMINI_API_KEY)
                response = client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=sys_prompt,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception:
                pass

        or_text = await self._call_openrouter(sys_prompt)
        if or_text:
            return or_text

        return (
            f"🤖 **NomadRadar AI Tavsiyesi (`{question}`):**\n"
            "• **Solo (Yeşil Pasaport) İçin:** Resmi tatillerde (örn. 28 Ekim öğleden sonra -> 1 Kasım) İstanbul direkt uçuşları şiştiğinde "
            "Salı/Çarşamba akşamı **Halkalı-Sofya Ekspresi** veya **Esenler-Sofya/Selanik gece otobüsü (25€)** ile çıkıp sabah **Ryanair/WizzAir (15-25€)** ile "
            "Portekiz, İtalya veya İspanya'ya uçmak maliyeti %60 düşürür ve 1 gece otel parasını sıfırlar.\n"
            "• **Çift Modu (Yeşil + Bordo Pasaport) İçin:** Vize stresi olmadan direkt uçuşla **Karadağ (Tivat/Podgorica), Sırbistan (Belgrad), Bosna (Saraybosna)** "
            "veya kapıda ekspres vizeyle **Rodos / Sakız / Midilli** en yüksek konfor/fiyat oranını sunar."
        )
