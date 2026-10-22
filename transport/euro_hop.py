from typing import Dict, List, Tuple
from models import RouteOption, TransportLeg, TravelWindow


# Avrupa içine ucuza inip FlixBus / Tren ile hedef şehre geçilen kombinasyonlar
EURO_HOP_CONNECTIONS: Dict[str, Tuple[str, str, str, float, float]] = {
    # Hedef -> (İnilen Ucuz Havalimanı, Uçuş Havayolu, Kara Bağlantısı, Uçuş Tek Yön €, Otobüs/Tren Tek Yön €)
    "LIS": ("OPO", "Ryanair/Pegasus (Porto İnişli)", "FlixBus / Alfa Pendular Hızlı Tren (Porto -> Lizbon)", 52.0, 9.0),
    "AMS": ("EIN", "Pegasus / WizzAir (Eindhoven İnişli)", "FlixBus / NS Tren (Eindhoven -> Amsterdam)", 54.0, 11.0),
    "VCE": ("MXP", "Pegasus / WizzAir (Milano İnişli)", "FlixBus / Trenitalia (Milano -> Venedik)", 48.0, 12.0),
    "CDG": ("CGN", "Pegasus (Köln İnişli)", "FlixBus Gece Seferi / Eurostar (Köln -> Paris)", 49.0, 16.0),
}


class EuroHopEngine:
    """
    SOLO MOD AVRUPA İÇİ FLIXBUS / TREN COMBO MOTORU:
    Hedef şehrin kendi havalimanı pahalı olduğunda yakın ucuz hub'a (örn. Porto, Eindhoven, Milano Bergamo, Köln)
    inip FlixBus veya hızlı trenle 9€-16€'ya hedefe geçme kombinasyonlarını üretir.
    """

    def build_euro_hop_routes(
        self, window: TravelWindow, city_code: str
    ) -> List[RouteOption]:
        code = city_code.upper()
        if code not in EURO_HOP_CONNECTIONS:
            return []

        hub_iata, flight_carrier, bus_train_carrier, flight_one_way, ground_one_way = EURO_HOP_CONNECTIONS[code]

        out_flight = TransportLeg(
            mode="flight",
            carrier=flight_carrier,
            origin="SAW",
            destination=hub_iata,
            departure_str=f"{window.start_dt.strftime('%d.%m')} 14:15",
            arrival_str=f"{window.start_dt.strftime('%d.%m')} 17:00",
            price_eur_per_person=flight_one_way,
        )
        out_ground = TransportLeg(
            mode="bus",
            carrier=bus_train_carrier,
            origin=hub_iata,
            destination=code,
            departure_str=f"{window.start_dt.strftime('%d.%m')} 18:00",
            arrival_str=f"{window.start_dt.strftime('%d.%m')} 20:30",
            price_eur_per_person=ground_one_way,
        )

        in_ground = TransportLeg(
            mode="bus",
            carrier=bus_train_carrier,
            origin=code,
            destination=hub_iata,
            departure_str=f"{window.end_dt.strftime('%d.%m')} 14:00",
            arrival_str=f"{window.end_dt.strftime('%d.%m')} 16:30",
            price_eur_per_person=ground_one_way,
        )
        in_flight = TransportLeg(
            mode="flight",
            carrier=flight_carrier,
            origin=hub_iata,
            destination="SAW",
            departure_str=f"{window.end_dt.strftime('%d.%m')} 18:30",
            arrival_str=f"{window.end_dt.strftime('%d.%m')} 22:50",
            price_eur_per_person=flight_one_way,
        )

        return [
            RouteOption(
                strategy_name=f"🚄 Avrupa İçi Combo: {hub_iata} Uçuşu + {bus_train_carrier}",
                outbound_legs=[out_flight, out_ground],
                inbound_legs=[in_ground, in_flight],
                is_border_hack=False,
                max_stops=1,
                booking_hint_url=f"https://global.flixbus.com/",
            )
        ]
