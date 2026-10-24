import os
import httpx
from typing import Dict, List, Optional, Tuple
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
    "BGY": ("Pegasus / AJet", "SAW", 78.0),
    "AGP": ("Pegasus / THY", "SAW", 105.0),
    "ORY": ("Pegasus / Transavia", "SAW", 102.0),
    "DUS": ("Pegasus / SunExpress", "SAW", 84.0),
    "STR": ("Pegasus / SunExpress", "SAW", 82.0),
    "STN": ("Pegasus / AJet", "SAW", 75.0),
    "LGW": ("WizzAir / EasyJet / British Airways", "IST", 85.0),
    "MAN": ("Pegasus / EasyJet", "SAW", 88.0),
    "EDI": ("EasyJet / Turkish Airlines", "IST", 98.0),
    "SOF": ("Pegasus / THY", "SAW", 55.0),
    "VAR": ("THY", "IST", 68.0),
    "BOJ": ("THY", "IST", 72.0),
    "OTP": ("Pegasus / Tarom", "SAW", 58.0),
    "CLJ": ("WizzAir / Tarom", "IST", 76.0),
    "ZAG": ("Pegasus / Croatia Airlines", "SAW", 72.0),
    "DBV": ("THY / Freebird", "IST", 88.0),
    "SPU": ("THY / Croatia Airlines", "IST", 85.0),
    "ZRH": ("Pegasus / AJet / Swiss", "SAW", 89.0),
    "GVA": ("Pegasus / EasyJet", "SAW", 92.0),
    "BSL": ("Pegasus / AJet", "SAW", 84.0),
    "BRU": ("THY / Brussels Airlines", "IST", 96.0),
    "CRL": ("Pegasus", "SAW", 79.0),
    "CPH": ("Pegasus / SAS", "SAW", 86.0),
    "BLL": ("Pegasus", "SAW", 82.0),
    "ARN": ("Pegasus / AJet / SAS", "SAW", 88.0),
    "GOT": ("Pegasus / SAS", "SAW", 85.0),
    "PUS": ("Korean Air / Asiana (Seul Aktarmalı)", "IST", 430.0),
}


def get_typical_rt_flight_eur(city_code: str) -> float:
    """
    Returns the typical roundtrip flight price baseline in EUR for a given destination city.
    Calculated as base_one_way * 2.0 from DIRECT_ROUTE_PROFILES.
    Defaults to 180.0 EUR if the city is not profiled or city_code is empty.
    """
    if not city_code:
        return 180.0
    code = city_code.strip().upper()
    profile = DIRECT_ROUTE_PROFILES.get(code)
    if profile:
        return round(float(profile[2]) * 2.0, 2)
    return 180.0


_LIVE_FLIGHT_CACHE: Dict[str, List[RouteOption]] = {}


class DirectFlightScanner:
    """
    İstanbul (IST / SAW) çıkışlı direkt veya 1 konforlu aktarmalı uçuşları tarar.
    Varsayılan olarak (`LIVE_FLIGHTS_HTTP=1`) doğrudan Google Flights (`fast-flights`)
    üzerinden %100 gerçek anlık fiyatları çeker ve uydurma/sabit fiyat DÖNDÜRMEZ.
    Sadece birim testlerinde (`LIVE_FLIGHTS_HTTP=0`) çevrimdışı test verisi kullanır.
    """

    def get_typical_rt_flight_eur(self, city_code: str) -> float:
        """Helper delegation to get_typical_rt_flight_eur."""
        return get_typical_rt_flight_eur(city_code)

    async def search_direct_or_one_stop(
        self,
        window: TravelWindow,
        city_code: str,
        mode: TravelMode = TravelMode.SOLO,
        origin_preference: str = "CHEAPEST",
    ) -> List[RouteOption]:
        code = city_code.upper()
        if TEQUILA_API_KEY:
            live = await self._query_tequila_live(window, code)
            if live:
                return live

        # Varsayılan olarak (%100 Canlı Mod): Google Flights (fast-flights) üzerinden gerçek fiyatları çek!
        if os.getenv("LIVE_FLIGHTS_HTTP", "1") == "1":
            return await self._query_keyless_google_or_kiwi(
                window, code, origin_preference=origin_preference
            )

        carrier, origin_airport, base_one_way = DIRECT_ROUTE_PROFILES.get(
            code, ("Pegasus / AJet", "SAW", 95.0)
        )
        if origin_preference.upper() in ("SAW", "IST"):
            origin_airport = origin_preference.upper()

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

    async def _query_keyless_google_or_kiwi(
        self, window: TravelWindow, city_code: str, origin_preference: str = "CHEAPEST"
    ) -> List[RouteOption]:
        """
        Tequila veya Skyscanner API anahtarına gerek duymadan doğrudan
        Google Flights (`fast-flights` v3.1+ protobuf motoru) üzerinden
        canlı uçuş saatlerini, havayolunu ve gerçek EUR fiyatını çeker.
        SAW ve IST havalimanlarını eşzamanlı sorgular ve en ucuz rotayı seçer.
        """
        try:
            import asyncio
            import fast_flights

            d_out_str = window.start_dt.strftime("%Y-%m-%d")
            d_in_str = window.end_dt.strftime("%Y-%m-%d")
            earliest_hr = 13 if window.start_dt.hour == 13 else None

            def _fetch_sync(orig: str):
                try:
                    q_out = fast_flights.create_query(
                        flights=[
                            fast_flights.FlightQuery(
                                date=d_out_str,
                                from_airport=orig,
                                to_airport=city_code,
                                max_stops=1,
                                earliest_departure_hour=earliest_hr,
                            )
                        ],
                        trip="one-way",
                        seat="economy",
                        passengers=fast_flights.Passengers(adults=1),
                        currency="EUR",
                    )
                    q_in = fast_flights.create_query(
                        flights=[
                            fast_flights.FlightQuery(
                                date=d_in_str,
                                from_airport=city_code,
                                to_airport=orig,
                                max_stops=1,
                            )
                        ],
                        trip="one-way",
                        seat="economy",
                        passengers=fast_flights.Passengers(adults=1),
                        currency="EUR",
                    )
                    return fast_flights.get_flights(q_out), fast_flights.get_flights(q_in)
                except Exception:
                    return None, None

            def _parse_routes(orig: str, res_out, res_in) -> List[RouteOption]:
                valid_out = [x for x in (res_out or []) if getattr(x, "price", 0) and getattr(x, "flights", None)]
                valid_in = [x for x in (res_in or []) if getattr(x, "price", 0) and getattr(x, "flights", None)]

                if valid_out and valid_in:
                    best_out = sorted(valid_out, key=lambda x: x.price)[0]
                    best_in = sorted(valid_in, key=lambda x: x.price)[0]

                    f_out = best_out.flights[0]
                    f_in = best_in.flights[0]
                    out_dep = f"{f_out.departure.date[2]:02d}.{f_out.departure.date[1]:02d} {f_out.departure.time[0]:02d}:{f_out.departure.time[1]:02d}"
                    out_arr = f"{f_out.arrival.date[2]:02d}.{f_out.arrival.date[1]:02d} {f_out.arrival.time[0]:02d}:{f_out.arrival.time[1]:02d}"
                    in_dep = f"{f_in.departure.date[2]:02d}.{f_in.departure.date[1]:02d} {f_in.departure.time[0]:02d}:{f_in.departure.time[1]:02d}"
                    in_arr = f"{f_in.arrival.date[2]:02d}.{f_in.arrival.date[1]:02d} {f_in.arrival.time[0]:02d}:{f_in.arrival.time[1]:02d}"

                    carrier_out = " / ".join(best_out.airlines) if best_out.airlines else "Google Flights"
                    carrier_in = " / ".join(best_in.airlines) if best_in.airlines else "Google Flights"
                    stops = max(len(best_out.flights) - 1, len(best_in.flights) - 1)

                    return [
                        RouteOption(
                            strategy_name=f"Google Flights Canlı ({carrier_out}: {orig} ↔ {city_code})",
                            outbound_legs=[
                                TransportLeg(
                                    mode="flight",
                                    carrier=carrier_out,
                                    origin=orig,
                                    destination=city_code,
                                    departure_str=out_dep,
                                    arrival_str=out_arr,
                                    price_eur_per_person=float(best_out.price),
                                )
                            ],
                            inbound_legs=[
                                TransportLeg(
                                    mode="flight",
                                    carrier=carrier_in,
                                    origin=city_code,
                                    destination=orig,
                                    departure_str=in_dep,
                                    arrival_str=in_arr,
                                    price_eur_per_person=float(best_in.price),
                                )
                            ],
                            is_border_hack=False,
                            max_stops=stops,
                            booking_hint_url=(
                                f"https://www.google.com/travel/flights?q=Flights%20to%20{city_code}%20from%20{orig}%20on%20"
                                f"{d_out_str}%20through%20{d_in_str}"
                            ),
                        )
                    ]
                return []

            async def _fetch_airport_routes(orig: str) -> List[RouteOption]:
                cache_key = f"{orig}:{city_code}:{d_out_str}:{d_in_str}"
                if cache_key in _LIVE_FLIGHT_CACHE:
                    return _LIVE_FLIGHT_CACHE[cache_key]
                try:
                    res_out, res_in = await asyncio.to_thread(_fetch_sync, orig)
                    routes = _parse_routes(orig, res_out, res_in)
                    _LIVE_FLIGHT_CACHE[cache_key] = routes
                    return routes
                except Exception:
                    _LIVE_FLIGHT_CACHE[cache_key] = []
                    return []

            if origin_preference.upper() == "SAW":
                airports = ["SAW"]
            elif origin_preference.upper() == "IST":
                airports = ["IST"]
            else:
                airports = ["SAW", "IST"]

            results = await asyncio.gather(
                *[_fetch_airport_routes(apt) for apt in airports],
                return_exceptions=True,
            )

            candidates: List[RouteOption] = []
            for r in results:
                if isinstance(r, list):
                    candidates.extend(r)

            if candidates:
                best = min(candidates, key=lambda r: r.roundtrip_price_per_person_eur)
                return [best]
            return []
        except Exception:
            return []

