from typing import List
from models import RouteOption, TravelMode, TravelWindow
from transport.direct_flights import DirectFlightScanner, get_typical_rt_flight_eur
from transport.border_hop import BorderHopEngine
from transport.euro_hop import EuroHopEngine


class TransportAggregator:
    """
    Moda göre (Solo vs Çift) tüm ulaşım alternatiflerini toplar ve en ucuzdan pahalıya sıralar.
    - SOLO MOD: Direkt Uçuş + Balkan Gece Treni/Otobüsü + Ryanair Hack + Avrupa İçi FlixBus/Tren Combo.
    - ÇİFT MODU: Sadece konforlu Direkt Uçuşlar (veya maksimum 1 rahat aktarma), sınır ötesi gece otobüsü hack'i KAPALI.
    """

    def __init__(self) -> None:
        self.direct_scanner = DirectFlightScanner()
        self.border_hop = BorderHopEngine()
        self.euro_hop = EuroHopEngine()

    def get_typical_rt_flight_eur(self, city_code: str) -> float:
        """
        Returns the reference roundtrip flight baseline in EUR for the given city code.
        Delegates to get_typical_rt_flight_eur in transport.direct_flights.
        """
        return get_typical_rt_flight_eur(city_code)

    async def find_best_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []

        # Her iki modda da direkt / konforlu uçuşları al
        direct_options = await self.direct_scanner.search_direct_or_one_stop(
            window=window, city_code=city_code, mode=mode
        )
        routes.extend(direct_options)

        if mode == TravelMode.SOLO:
            # Solo modda Balkan sınır hack'i (Sofya/Selanik gece otobüsü/treni + Ryanair/WizzAir) açık!
            balkan_options = await self.border_hop.build_balkan_hack_routes(
                window=window, city_code=city_code
            )
            routes.extend(balkan_options)

            # Solo modda Avrupa içi FlixBus/tren kombinasyonları açık!
            euro_options = self.euro_hop.build_euro_hop_routes(
                window=window, city_code=city_code
            )
            routes.extend(euro_options)
        else:
            # Çift modunda sınır hack'leri ve çoklu yorucu aktarmaları kesinlikle filtrele
            routes = [
                r
                for r in routes
                if not r.is_border_hack and r.max_stops <= 1 and r.saved_nights_count == 0
            ]

        routes.sort(key=lambda r: r.roundtrip_price_per_person_eur)
        return routes
