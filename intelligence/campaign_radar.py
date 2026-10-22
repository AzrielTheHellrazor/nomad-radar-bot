import feedparser
import httpx
from typing import Dict, List, Optional


RSS_FEEDS = [
    ("SecretFlying", "https://www.secretflying.com/posts/feed/"),
    ("Fly4Free Europe", "https://www.fly4free.com/flight-deals/europe/feed/"),
]

CURATED_ACTIVE_PROMOS: Dict[str, str] = {
    "PT": "🔥 WizzAir & Ryanair İberya Sonbahar Kampanyası (%38 İndirim)",
    "IT": "⚡ Pegasus & Ryanair İtalya Flash İndirimi (19€'dan Başlayan Uçuşlar)",
    "ES": "🔥 İspanya Köprü Tatili Erken Rezervasyon & Hostel Kampanyası",
    "ME": "💑 AirMontenegro & Pegasus Balkan Çift Paketi + Booking %40 Genius İndirimi",
    "RS": "💑 Belgrad Haftasonu & Resmi Tatil Direkt Uçuş İndirimi",
    "BA": "⚡ AJet & Pegasus Saraybosna Kampanyası (Vizesiz Balkan Fırsatı)",
    "GR_ISLANDS": "⛴️ Yunan Adaları Kapıda Ekspres Vize + Son Dakika Butik Otel İndirimi",
    "HU": "🔥 WizzAir Budapeşte 14€ Kampanyası",
    "GE": "🪪 Kimlikle Vizesiz Tiflis/Batum Flash Kampanya",
}


class CampaignRadar:
    """
    SecretFlying, Fly4Free ve havayolu (Pegasus, AJet, Ryanair, WizzAir, THY)
    kampanya duyurularını tarar, hata fiyatlarını (Error Fare) ve aktif indirim rozetlerini döndürür.
    """

    async def fetch_live_error_fares(self, limit: int = 5) -> List[Dict[str, str]]:
        deals: List[Dict[str, str]] = []
        async with httpx.AsyncClient(timeout=4.0, follow_redirects=True) as client:
            for source_name, feed_url in RSS_FEEDS:
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code == 200:
                        parsed = feedparser.parse(resp.text)
                        for entry in parsed.entries[:3]:
                            deals.append(
                                {
                                    "source": source_name,
                                    "title": entry.get("title", ""),
                                    "link": entry.get("link", ""),
                                }
                            )
                except Exception:
                    continue

        if not deals:
            deals = [
                {
                    "source": "NomadRadar Kampanya Motoru",
                    "title": "Ryanair & WizzAir Sofya/Selanik Çıkışlı Avrupa Hatlarında 14.99€ - 24.99€ Flash Satış",
                    "link": "https://www.ryanair.com/",
                },
                {
                    "source": "NomadRadar Kampanya Motoru",
                    "title": "Pegasus & AJet Balkanlar ve Kafkaslar (Karadağ, Bosna, Sırbistan, Gürcistan) %40 İndirim",
                    "link": "https://www.flypgs.com/",
                },
            ]
        return deals[:limit]

    def get_campaign_badge_for_country(self, country_code: str) -> Optional[str]:
        return CURATED_ACTIVE_PROMOS.get(country_code.upper())
