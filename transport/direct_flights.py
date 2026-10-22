import httpx
from typing import Dict, List, Tuple
from config import TEQUILA_API_KEY
from models import RouteOption, TransportLeg, TravelMode, TravelWindow


# İstanbul (IST/SAW) çıkışlı rotalar için gerçekçi baz fiyat ve havayolu haritası
DIRECT_ROUTE_PROFILES: Dict[str, Tuple[str, str, float]] = {
    "LIS": ("TAP / THY / Pegasus (Aktarmalı/Direkt)", "IST", 185.0),
    "OPO": ("THY / Lufthansa", "IST", 195.0),
    "FCO": ("Pegasus / AJet", "SAW", 88.0),
    "MXP": ("Pegasus / AJet", "SAW", 79.0),
    "BLQ": ("Pegasus", "SAW", 74.0),
    "VCE": ("THY / Pegasus", "SAW", 96.0),
    "NAP": ("THY", "IST", 118.0),
    "BCN": ("Pegasus / Vueling", "SAW", 98.0),
    "MAD": ("Pegasus / Air Europa", "SAW", 112.0),
    "SVQ": ("Pegasus", "SAW", 94.0),
    "CDG": ("Pegasus / Transavia", "SAW", 104.0),
    "LYS": ("Pegasus / Transavia", "SAW", 86.0),
    "NCE": ("THY / EasyJet", "IST", 125.0),
    "AMS": ("Pegasus / AJet", "SAW", 108.0),
    "EIN": ("Pegasus / Transavia", "SAW", 84.0),
    "BER": ("Pegasus / AJet", "SAW", 82.0),
    "MUC": ("Pegasus / AJet", "SAW", 89.0),
    "CGN": ("Pegasus / AJet", "SAW", 72.0),
    "VIE": ("Pegasus / AJet", "SAW", 76.0),
    "BUD": ("WizzAir / Pegasus", "IST", 64.0),
    "PRG": ("Pegasus", "SAW", 84.0),
    "WAW": ("LOT / Pegasus", "IST", 95.0),
    "KRK": ("LOT / Pegasus", "SAW", 89.0),
    "ATH": ("Pegasus / Aegean", "SAW", 68.0),
    "SKG": ("THY / Aegean", "IST", 78.0),
    "RHO": ("Hızlı Feribot (Marmaris/Fethiye) + Dalaman Uçuşu", "SAW", 69.0),
    "JMK": ("Çeşme/Ayvalık Feribot + İzmir Bağlantısı", "SAW", 64.0),
    "SJJ": ("Pegasus / AJet (Direkt)", "SAW", 62.0),
    "BEG": ("Pegasus / AirSerbia (Direkt)", "SAW", 69.0),
    "TGD": ("Pegasus / AirMontenegro (Direkt)", "SAW", 66.0),
    "TIV": ("AirMontenegro / THY (Direkt)", "IST", 74.0),
    "TIA": ("Pegasus / AirAlbania (Direkt)", "SAW", 58.0),
    "SKP": ("Pegasus / AJet (Direkt)", "SAW", 56.0),
    "OHD": ("THY / AirSerbia (1 Rahat Aktarma)", "IST", 82.0),
    "TBS": ("Pegasus / AJet (Direkt)", "SAW", 54.0),
    "BUS": ("Pegasus / THY (Direkt)", "SAW", 52.0),
    "SSH": ("Pegasus / AJet (Direkt)", "SAW", 78.0),
    "RAK": ("Pegasus / Royal Air Maroc", "SAW", 118.0),
    "CMN": ("Pegasus / Air Arabia", "SAW", 108.0),
    "BKK": ("THY / Gulf Air / SalamAir", "IST", 365.0),
    "HKT": ("THY / Etihad (1 Aktarma)", "IST", 390.0),
    "NRT": ("ANA / THY / AirChina", "IST", 445.0),
    "ICN": ("Asiana / THY", "IST", 415.0),
    "LHR": ("WizzAir / Pegasus / British Airways", "IST", 78.0),
    "DUB": ("Pegasus / Turkish Airlines", "SAW", 115.0),
}


class DirectFlightScanner:
    """
    İstanbul (IST / SAW) çıkışlı direkt veya 1 konforlu aktarmalı uçuşları tarar.
    Eğer TEQUILA_API_KEY tanımlıysa canlı Kiwi/Tequila API sorgular; aksi halde
    gerçekçi kampanya/sezon katsayılı uçuş modeli üretir.
    """

    async def search_direct_or_one_stop(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        code = city_code.upper()
        if TEQUILA_API_KEY:
            live = await self._query_tequila_live(window, code)
            if live:
                return live

        carrier, origin_airport, base_one_way = DIRECT_ROUTE_PROFILES.get(
            code, ("Pegasus / AJet", "SAW", 95.0)
        )

        # Resmi tatillerde Türkiye çıkışlı direkt biletler (özellikle Batı Avrupa'ya) şişer,
        # ama hafta içi flash indirimlerde veya Balkan/Kafkas rotalarında kampanya yakalanır.
        if window.is_weekday_flash:
            multiplier = 0.62
        elif window.is_bridge_holiday and code in ("LIS", "OPO", "BCN", "CDG", "AMS", "FCO"):
            multiplier = 1.25  # Türkiye tatilinde direkt Avrupa uçuşu pahalılaşır (Balkan Hack burada fark yaratır!)
        else:
            multiplier = 0.82

        out_price = round(base_one_way * multiplier, 2)
        in_price = round(base_one_way * (multiplier * 0.95), 2)

        dep_time = "14:40" if window.start_dt.hour == 13 else "19:45"
        arr_time = "17:30" if window.start_dt.hour == 13 else "22:15"

        out_leg = TransportLeg(
            mode="ferry" if "Feribot" in carrier else "flight",
            carrier=carrier,
            origin=origin_airport,
            destination=code,
            departure_str=f"{window.start_dt.strftime('%d.%m')} {dep_time}",
            arrival_str=f"{window.start_dt.strftime('%d.%m')} {arr_time}",
            price_eur_per_person=out_price,
            saves_accommodation_night=False,
        )
        in_leg = TransportLeg(
            mode="ferry" if "Feribot" in carrier else "flight",
            carrier=carrier,
            origin=code,
            destination=origin_airport,
            departure_str=f"{window.end_dt.strftime('%d.%m')} 20:30",
            arrival_str=f"{window.end_dt.strftime('%d.%m')} 23:45",
            price_eur_per_person=in_price,
            saves_accommodation_night=False,
        )

        booking_url = (
            f"https://www.google.com/travel/flights?q=Flights%20to%20{code}%20from%20{origin_airport}%20on%20"
            f"{window.start_dt.strftime('%Y-%m-%d')}%20through%20{window.end_dt.strftime('%Y-%m-%d')}"
        )

        return [
            RouteOption(
                strategy_name=f"Direkt / Konforlu Uçuş ({origin_airport} ↔ {code})",
                outbound_legs=[out_leg],
                inbound_legs=[in_leg],
                is_border_hack=False,
                max_stops=0 if "Direkt" in carrier or base_one_way < 120 else 1,
                booking_hint_url=booking_url,
            )
        ]

    async def _query_tequila_live(
        self, window: TravelWindow, city_code: str
    ) -> List[RouteOption]:
        url = "https://api.tequila.kiwi.com/v2/search"
        headers = {"apikey": TEQUILA_API_KEY}
        params = {
            "fly_from": "city:IST",
            "fly_to": city_code,
            "date_from": window.start_dt.strftime("%d/%m/%Y"),
            "date_to": window.start_dt.strftime("%d/%m/%Y"),
            "return_from": window.end_dt.strftime("%d/%m/%Y"),
            "return_to": window.end_dt.strftime("%d/%m/%Y"),
            "curr": "EUR",
            "max_stopovers": 1,
            "limit": 2,
        }
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                resp = await client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    return []
                data = resp.json().get("data", [])
                routes: List[RouteOption] = []
                for item in data[:1]:
                    total_price = float(item.get("price", 150.0))
                    deep_link = item.get("deep_link", "")
                    half = round(total_price / 2.0, 2)
                    routes.append(
                        RouteOption(
                            strategy_name=f"Kiwi Canlı Uçuş (IST ↔ {city_code})",
                            outbound_legs=[
                                TransportLeg(
                                    mode="flight",
                                    carrier="Kiwi Verified",
                                    origin="IST",
                                    destination=city_code,
                                    departure_str=window.start_dt.strftime("%d.%m %H:%M"),
                                    arrival_str=window.start_dt.strftime("%d.%m"),
                                    price_eur_per_person=half,
                                )
                            ],
                            inbound_legs=[
                                TransportLeg(
                                    mode="flight",
                                    carrier="Kiwi Verified",
                                    origin=city_code,
                                    destination="IST",
                                    departure_str=window.end_dt.strftime("%d.%m 20:00"),
                                    arrival_str=window.end_dt.strftime("%d.%m 23:30"),
                                    price_eur_per_person=half,
                                )
                            ],
                            is_border_hack=False,
                            max_stops=0,
                            booking_hint_url=deep_link,
                        )
                    )
                return routes
        except Exception:
            return []
