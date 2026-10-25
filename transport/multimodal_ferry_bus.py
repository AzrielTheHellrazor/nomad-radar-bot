import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from models import RouteOption, TransportLeg, TravelMode, TravelWindow


class MultiModalFerryBusEngine:
    """
    Çok Modlu Feribot, Uluslararası Otobüs, Gece Treni ve Vizesiz Köprü Motoru.
    - Ege Adaları Katamaran Feribotları (RHO, JMK)
    - Kore ↔ Japonya Deniz Feribotu + Karayolu/Demiryolu Köprüsü (FUK, KIX)
    - Adriyatik & Akdeniz Gece Feribotları (DBV, SPU)
    - Vizesiz Kara Otobüsü & Gece Treni Sınır Rotaları (TBS, BUS, SOF, SKG, ATH, OTP, SKP, BEG, SJJ, TIA)
    - Orta Asya Vizesiz Köprüsü (SAW ↔ ALA Almatı + Eastar Jet ↔ ICN Seul)
    """

    def __init__(self):
        from transport.external_mcp_apis import FerryhopperMCPClient
        self._ferryhopper_client = FerryhopperMCPClient()

    async def build_multimodal_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode = TravelMode.SOLO
    ) -> List[RouteOption]:
        code = city_code.strip().upper()
        routes: List[RouteOption] = []

        # 1. Ege Adaları Feribotları (RHO, JMK) - Solo & Couple uyumlu
        if code in ("RHO", "JMK"):
            routes.extend(await self._build_aegean_ferry_routes(window, code, mode))

        # 2. Kore ↔ Japonya Feribot Köprüsü (FUK, KIX) - Solo & Couple uyumlu
        if code in ("FUK", "KIX"):
            routes.extend(await self._build_korea_japan_ferry_routes(window, code, mode))

        # 3. Orta Asya Vizesiz Köprüsü (ICN, FUK, KIX) - Solo & Couple uyumlu
        if code in ("ICN", "FUK", "KIX"):
            routes.extend(self._build_central_asia_bridge_routes(window, code, mode))

        # 4. Adriyatik Feribotları (DBV, SPU) - Solo mod
        if code in ("DBV", "SPU") and mode == TravelMode.SOLO:
            routes.extend(self._build_adriatic_ferry_routes(window, code, mode))

        # 5. Vizesiz ve Sınır Ötesi Kara Otobüsü / Gece Treni Rotaları
        routes.extend(self._build_overland_routes(window, code, mode))

        return routes

    async def _build_aegean_ferry_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        d_out = window.start_dt.strftime("%d.%m")
        d_in = window.end_dt.strftime("%d.%m")
        d_out_iso = window.start_dt.strftime("%Y-%m-%d")

        if city_code == "RHO":
            # Rodos: Dalaman Uçuşu + Marmaris/Fethiye Hızlı Katamaran Feribot
            ferry_carrier = "Yeşil Marmaris / Tilos Hızlı Katamaran Feribot"
            ferry_price = 42.0
            ferry_link = "https://www.yesilmarmaris.com/"

            if os.getenv("LIVE_FLIGHTS_HTTP", "1") == "1":
                try:
                    live_ferry = await self._ferryhopper_client.search_ferry_price_eur(
                        "Marmaris", "Rhodes", d_out_iso
                    )
                    if live_ferry:
                        ferry_price = live_ferry[0]
                        ferry_carrier = f"{live_ferry[1]} Hızlı Katamaran Feribot"
                        if live_ferry[2]:
                            ferry_link = live_ferry[2]
                except Exception:
                    pass

            out_leg_1 = TransportLeg(
                mode="flight",
                carrier="Pegasus / AJet (İstanbul ↔ Dalaman)",
                origin="SAW",
                destination="DLM",
                departure_str=f"{d_out} 08:15",
                arrival_str=f"{d_out} 09:35",
                price_eur_per_person=28.0,
                saves_accommodation_night=False,
            )
            out_leg_2 = TransportLeg(
                mode="ferry",
                carrier=ferry_carrier,
                origin="Marmaris Port",
                destination="RHO",
                departure_str=f"{d_out} 11:30",
                arrival_str=f"{d_out} 12:30",
                price_eur_per_person=ferry_price,
                saves_accommodation_night=False,
            )
            in_leg_1 = TransportLeg(
                mode="ferry",
                carrier=ferry_carrier,
                origin="RHO",
                destination="Marmaris Port",
                departure_str=f"{d_in} 17:00",
                arrival_str=f"{d_in} 18:00",
                price_eur_per_person=ferry_price,
                saves_accommodation_night=False,
            )
            in_leg_2 = TransportLeg(
                mode="flight",
                carrier="Pegasus / AJet (Dalaman ↔ İstanbul)",
                origin="DLM",
                destination="SAW",
                departure_str=f"{d_in} 20:45",
                arrival_str=f"{d_in} 22:05",
                price_eur_per_person=28.0,
                saves_accommodation_night=False,
            )

            routes.append(
                RouteOption(
                    strategy_name="Ege Katamaran Feribot Köprüsü: Dalaman Uçuşu + Marmaris ↔ Rodos Hızlı Feribot",
                    outbound_legs=[out_leg_1, out_leg_2],
                    inbound_legs=[in_leg_1, in_leg_2],
                    is_border_hack=False,
                    max_stops=1,
                    booking_hint_url=ferry_link,
                )
            )

        elif city_code == "JMK":
            # Sakız / Midilli / Mikonos: İzmir Uçuşu + Çeşme/Ayvalık Hızlı Feribot
            ferry_carrier_out = "Turyol / Jalem Tur Hızlı Feribot (Çeşme ↔ Sakız / Ayvalık ↔ Midilli)"
            ferry_carrier_in = "Turyol / Jalem Tur Hızlı Feribot"
            ferry_price = 32.0
            ferry_link = "https://www.turyol.com/"

            if os.getenv("LIVE_FLIGHTS_HTTP", "1") == "1":
                try:
                    live_ferry = await self._ferryhopper_client.search_ferry_price_eur(
                        "Cesme", "Chios", d_out_iso
                    )
                    if live_ferry:
                        ferry_price = live_ferry[0]
                        ferry_carrier_out = f"{live_ferry[1]} Hızlı Feribot"
                        ferry_carrier_in = f"{live_ferry[1]} Hızlı Feribot"
                        if live_ferry[2]:
                            ferry_link = live_ferry[2]
                except Exception:
                    pass

            out_leg_1 = TransportLeg(
                mode="flight",
                carrier="Pegasus / AJet (İstanbul ↔ İzmir ADB)",
                origin="SAW",
                destination="ADB",
                departure_str=f"{d_out} 08:30",
                arrival_str=f"{d_out} 09:40",
                price_eur_per_person=24.0,
                saves_accommodation_night=False,
            )
            out_leg_2 = TransportLeg(
                mode="ferry",
                carrier=ferry_carrier_out,
                origin="Çeşme Port",
                destination="JMK",
                departure_str=f"{d_out} 11:30",
                arrival_str=f"{d_out} 12:15",
                price_eur_per_person=ferry_price,
                saves_accommodation_night=False,
            )
            in_leg_1 = TransportLeg(
                mode="ferry",
                carrier=ferry_carrier_in,
                origin="JMK",
                destination="Çeşme Port",
                departure_str=f"{d_in} 17:30",
                arrival_str=f"{d_in} 18:15",
                price_eur_per_person=ferry_price,
                saves_accommodation_night=False,
            )
            in_leg_2 = TransportLeg(
                mode="flight",
                carrier="Pegasus / AJet (İzmir ADB ↔ İstanbul)",
                origin="ADB",
                destination="SAW",
                departure_str=f"{d_in} 21:00",
                arrival_str=f"{d_in} 22:15",
                price_eur_per_person=24.0,
                saves_accommodation_night=False,
            )

            routes.append(
                RouteOption(
                    strategy_name="Ege Adaları Feribotu: İzmir Bağlantısı + Çeşme/Ayvalık ↔ Sakız/Midilli Feribot",
                    outbound_legs=[out_leg_1, out_leg_2],
                    inbound_legs=[in_leg_1, in_leg_2],
                    is_border_hack=False,
                    max_stops=1,
                    booking_hint_url=ferry_link,
                )
            )

        return routes

    async def _build_korea_japan_ferry_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        d_out = window.start_dt.strftime("%d.%m")
        d_out_next = (window.start_dt + timedelta(days=1)).strftime("%d.%m")
        d_in = window.end_dt.strftime("%d.%m")
        d_in_next = (window.end_dt + timedelta(days=1)).strftime("%d.%m")

        # İstanbul ↔ Seul (ICN) uçuş fiyatı (Canlı veya çevrimdışı fixture)
        flight_price = 220.0
        if os.getenv("LIVE_FLIGHTS_HTTP", "1") == "1":
            try:
                from transport.direct_flights import DirectFlightScanner
                scanner = DirectFlightScanner()
                icn_res = await scanner.search_direct_or_one_stop(window, "ICN", mode=mode)
                if icn_res:
                    flight_price = round(icn_res[0].roundtrip_price_per_person_eur / 2.0, 2)
            except Exception:
                flight_price = 220.0

        if city_code == "FUK":
            # IST/SAW ↔ ICN Uçuş + Seul ↔ Busan Express Otobüs (17€) + Busan ↔ Fukuoka Camellia Line Gece Feribotu (52€)
            out_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Asiana / THY / Korean Air",
                    origin="IST",
                    destination="ICN",
                    departure_str=f"{d_out} 01:45",
                    arrival_str=f"{d_out} 16:55",
                    price_eur_per_person=flight_price,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="bus",
                    carrier="KoBUS Seul ↔ Busan Express Otobüs",
                    origin="ICN",
                    destination="PUS",
                    departure_str=f"{d_out} 18:15",
                    arrival_str=f"{d_out} 21:30",
                    price_eur_per_person=17.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="ferry",
                    carrier="Camellia Line Gece Feribotu (Busan ↔ Fukuoka)",
                    origin="PUS",
                    destination="FUK",
                    departure_str=f"{d_out} 22:30 (Gece Feribotu = 0€ Otel!)",
                    arrival_str=f"{d_out_next} 07:30",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=True,
                ),
            ]
            in_legs = [
                TransportLeg(
                    mode="ferry",
                    carrier="Camellia Line Feribotu (Fukuoka ↔ Busan)",
                    origin="FUK",
                    destination="PUS",
                    departure_str=f"{d_in} 11:30",
                    arrival_str=f"{d_in} 18:00",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="bus",
                    carrier="KoBUS Busan ↔ Seul Express Otobüs",
                    origin="PUS",
                    destination="ICN",
                    departure_str=f"{d_in} 19:00",
                    arrival_str=f"{d_in} 22:15",
                    price_eur_per_person=17.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Asiana / THY / Korean Air",
                    origin="ICN",
                    destination="IST",
                    departure_str=f"{d_in_next} 00:15",
                    arrival_str=f"{d_in_next} 06:20",
                    price_eur_per_person=flight_price,
                    saves_accommodation_night=False,
                ),
            ]

            routes.append(
                RouteOption(
                    strategy_name="Kore-Japonya Feribot Köprüsü: Seul Uçuşu + Busan Camellia Line Gece Feribotu (FUK)",
                    outbound_legs=out_legs,
                    inbound_legs=in_legs,
                    is_border_hack=False,
                    max_stops=1,
                    booking_hint_url="https://www.camellia-line.co.jp/en/",
                )
            )

        elif city_code == "KIX":
            # Osaka için Fukuoka'dan Willer Express Otobüsü (28€) eklenir
            out_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Asiana / THY / Korean Air",
                    origin="IST",
                    destination="ICN",
                    departure_str=f"{d_out} 01:45",
                    arrival_str=f"{d_out} 16:55",
                    price_eur_per_person=flight_price,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="bus",
                    carrier="KoBUS Seul ↔ Busan Express Otobüs",
                    origin="ICN",
                    destination="PUS",
                    departure_str=f"{d_out} 18:15",
                    arrival_str=f"{d_out} 21:30",
                    price_eur_per_person=17.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="ferry",
                    carrier="Camellia Line Gece Feribotu (Busan ↔ Fukuoka)",
                    origin="PUS",
                    destination="FUK",
                    departure_str=f"{d_out} 22:30 (Gece Feribotu = 0€ Otel!)",
                    arrival_str=f"{d_out_next} 07:30",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=True,
                ),
                TransportLeg(
                    mode="bus",
                    carrier="Willer Express (Fukuoka ↔ Osaka)",
                    origin="FUK",
                    destination="KIX",
                    departure_str=f"{d_out_next} 09:00",
                    arrival_str=f"{d_out_next} 15:30",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=False,
                ),
            ]
            d_in_prev = (window.end_dt - timedelta(days=1)).strftime("%d.%m")
            in_legs = [
                TransportLeg(
                    mode="bus",
                    carrier="Willer Express (Osaka ↔ Fukuoka)",
                    origin="KIX",
                    destination="FUK",
                    departure_str=f"{d_in_prev} 22:00",
                    arrival_str=f"{d_in} 07:00",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="ferry",
                    carrier="Camellia Line Feribotu (Fukuoka ↔ Busan)",
                    origin="FUK",
                    destination="PUS",
                    departure_str=f"{d_in} 11:30",
                    arrival_str=f"{d_in} 18:00",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="bus",
                    carrier="KoBUS Busan ↔ Seul Express Otobüs",
                    origin="PUS",
                    destination="ICN",
                    departure_str=f"{d_in} 19:00",
                    arrival_str=f"{d_in} 22:15",
                    price_eur_per_person=17.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Asiana / THY / Korean Air",
                    origin="ICN",
                    destination="IST",
                    departure_str=f"{d_in_next} 00:15",
                    arrival_str=f"{d_in_next} 06:20",
                    price_eur_per_person=flight_price,
                    saves_accommodation_night=False,
                ),
            ]

            routes.append(
                RouteOption(
                    strategy_name="Kore-Japonya Feribot Köprüsü: Seul Uçuşu + Camellia Line Feribotu + Willer Express (KIX)",
                    outbound_legs=out_legs,
                    inbound_legs=in_legs,
                    is_border_hack=False,
                    max_stops=1,
                    booking_hint_url="https://willer-travel.com/en/",
                )
            )

        return routes

    def _build_central_asia_bridge_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        d_out = window.start_dt.strftime("%d.%m")
        d_out_next = (window.start_dt + timedelta(days=1)).strftime("%d.%m")
        d_in = window.end_dt.strftime("%d.%m")

        if city_code == "ICN":
            # SAW ↔ ALA Almatı (125€) + ALA ↔ ICN Seul Eastar Jet (165€)
            out_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus Airlines (İstanbul ↔ Almatı ALA)",
                    origin="SAW",
                    destination="ALA",
                    departure_str=f"{d_out} 10:15",
                    arrival_str=f"{d_out} 18:30",
                    price_eur_per_person=125.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Eastar Jet / Air Astana (Almatı ALA ↔ Seul ICN)",
                    origin="ALA",
                    destination="ICN",
                    departure_str=f"{d_out} 20:30",
                    arrival_str=f"{d_out_next} 05:40",
                    price_eur_per_person=165.0,
                    saves_accommodation_night=False,
                ),
            ]
            in_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Eastar Jet / Air Astana (Seul ICN ↔ Almatı ALA)",
                    origin="ICN",
                    destination="ALA",
                    departure_str=f"{d_in} 11:00",
                    arrival_str=f"{d_in} 15:30",
                    price_eur_per_person=165.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus Airlines (Almatı ALA ↔ İstanbul)",
                    origin="ALA",
                    destination="SAW",
                    departure_str=f"{d_in} 18:00",
                    arrival_str=f"{d_in} 21:15",
                    price_eur_per_person=125.0,
                    saves_accommodation_night=False,
                ),
            ]

            routes.append(
                RouteOption(
                    strategy_name="Orta Asya Vizesiz Köprüsü: Almatı (ALA) Aktarmalı Eastar Jet + Seul (ICN)",
                    outbound_legs=out_legs,
                    inbound_legs=in_legs,
                    is_border_hack=False,
                    max_stops=1,
                    booking_hint_url="https://www.eastarjet.com/",
                )
            )

        return routes

    def _build_adriatic_ferry_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        d_out = window.start_dt.strftime("%d.%m")
        d_out_next = (window.start_dt + timedelta(days=1)).strftime("%d.%m")
        d_in = window.end_dt.strftime("%d.%m")
        d_in_next = (window.end_dt + timedelta(days=1)).strftime("%d.%m")

        if city_code == "DBV":
            # SAW ↔ Bari (BRI) Uçuş (45€) + Bari ↔ Dubrovnik Gece Feribotu (48€)
            out_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus / WizzAir (İstanbul ↔ Bari BRI)",
                    origin="SAW",
                    destination="BRI",
                    departure_str=f"{d_out} 12:30",
                    arrival_str=f"{d_out} 14:15",
                    price_eur_per_person=45.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="ferry",
                    carrier="Jadrolinija Gece Feribotu (Bari ↔ Dubrovnik)",
                    origin="BRI",
                    destination="DBV",
                    departure_str=f"{d_out} 21:00 (Gece Feribotu = 0€ Otel!)",
                    arrival_str=f"{d_out_next} 07:00",
                    price_eur_per_person=48.0,
                    saves_accommodation_night=True,
                ),
            ]
            in_legs = [
                TransportLeg(
                    mode="ferry",
                    carrier="Jadrolinija Gece Feribotu (Dubrovnik ↔ Bari)",
                    origin="DBV",
                    destination="BRI",
                    departure_str=f"{d_in} 22:00",
                    arrival_str=f"{d_in_next} 07:00",
                    price_eur_per_person=48.0,
                    saves_accommodation_night=True,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus / WizzAir (Bari BRI ↔ İstanbul)",
                    origin="BRI",
                    destination="SAW",
                    departure_str=f"{d_in_next} 15:00",
                    arrival_str=f"{d_in_next} 18:45",
                    price_eur_per_person=45.0,
                    saves_accommodation_night=False,
                ),
            ]

            routes.append(
                RouteOption(
                    strategy_name="Adriyatik Feribot Köprüsü: İtalya (Bari) Uçuşu + Jadrolinija Gece Feribotu (DBV)",
                    outbound_legs=out_legs,
                    inbound_legs=in_legs,
                    is_border_hack=True,
                    max_stops=1,
                    booking_hint_url="https://www.jadrolinija.hr/en",
                )
            )

        elif city_code == "SPU":
            # SAW ↔ Ancona/Bari Uçuş (48€) + Gece Feribotu ↔ Split (52€)
            out_legs = [
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus / WizzAir (İstanbul ↔ Ancona AOI)",
                    origin="SAW",
                    destination="AOI",
                    departure_str=f"{d_out} 13:00",
                    arrival_str=f"{d_out} 14:50",
                    price_eur_per_person=48.0,
                    saves_accommodation_night=False,
                ),
                TransportLeg(
                    mode="ferry",
                    carrier="Jadrolinija Gece Feribotu (Ancona ↔ Split)",
                    origin="AOI",
                    destination="SPU",
                    departure_str=f"{d_out} 20:30 (Gece Feribotu = 0€ Otel!)",
                    arrival_str=f"{d_out_next} 07:00",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=True,
                ),
            ]
            in_legs = [
                TransportLeg(
                    mode="ferry",
                    carrier="Jadrolinija Gece Feribotu (Split ↔ Ancona)",
                    origin="SPU",
                    destination="AOI",
                    departure_str=f"{d_in} 21:00",
                    arrival_str=f"{d_in_next} 07:00",
                    price_eur_per_person=52.0,
                    saves_accommodation_night=True,
                ),
                TransportLeg(
                    mode="flight",
                    carrier="Pegasus / WizzAir (Ancona AOI ↔ İstanbul)",
                    origin="AOI",
                    destination="SAW",
                    departure_str=f"{d_in_next} 14:30",
                    arrival_str=f"{d_in_next} 18:15",
                    price_eur_per_person=48.0,
                    saves_accommodation_night=False,
                ),
            ]

            routes.append(
                RouteOption(
                    strategy_name="Adriyatik Feribot Köprüsü: İtalya (Ancona) Uçuşu + Jadrolinija Gece Feribotu (SPU)",
                    outbound_legs=out_legs,
                    inbound_legs=in_legs,
                    is_border_hack=True,
                    max_stops=1,
                    booking_hint_url="https://www.jadrolinija.hr/en",
                )
            )

        return routes

    def _build_overland_routes(
        self, window: TravelWindow, city_code: str, mode: TravelMode
    ) -> List[RouteOption]:
        routes: List[RouteOption] = []
        d_out = window.start_dt.strftime("%d.%m")
        d_out_eve = (window.start_dt - timedelta(days=1)).strftime("%d.%m")
        d_in = window.end_dt.strftime("%d.%m")
        d_in_next = (window.end_dt + timedelta(days=1)).strftime("%d.%m")

        # 1. Gürcistan Rotaları (TBS & BUS) - Kimlikle Vizesiz (Solo & Couple Uyumlu)
        if city_code in ("TBS", "BUS"):
            # Direkt Otobüs (Metro / Lüks Karadeniz: 34€)
            saves_night = mode == TravelMode.SOLO
            out_leg = TransportLeg(
                mode="night_bus" if saves_night else "bus",
                carrier="Metro Turizm / Lüks Karadeniz (Direkt Otobüs)",
                origin="IST (Esenler)",
                destination=city_code,
                departure_str=f"{d_out_eve} 18:00" if saves_night else f"{d_out} 08:00",
                arrival_str=f"{d_out} 12:30" if saves_night else f"{d_out} 23:45",
                price_eur_per_person=34.0,
                saves_accommodation_night=saves_night,
            )
            in_leg = TransportLeg(
                mode="night_bus" if saves_night else "bus",
                carrier="Metro Turizm / Lüks Karadeniz (Direkt Otobüs)",
                origin=city_code,
                destination="IST (Esenler)",
                departure_str=f"{d_in} 16:00",
                arrival_str=f"{d_in_next} 10:30" if saves_night else f"{d_in} 23:30",
                price_eur_per_person=34.0,
                saves_accommodation_night=saves_night,
            )

            routes.append(
                RouteOption(
                    strategy_name=f"Vizesiz Direkt Otobüs: İstanbul ↔ {city_code} (Kimlikle Giriş)",
                    outbound_legs=[out_leg],
                    inbound_legs=[in_leg],
                    is_border_hack=False,
                    max_stops=0,
                    booking_hint_url="https://www.metroturizm.com.tr/",
                )
            )

            # Çift modu için konforlu alternatif: Rize-Artvin Uçuşu + Sarp Sınır Transferi
            if mode == TravelMode.COUPLE:
                hopa_out_1 = TransportLeg(
                    mode="flight",
                    carrier="AJet / Pegasus (İstanbul ↔ Rize-Artvin RZV)",
                    origin="SAW",
                    destination="RZV",
                    departure_str=f"{d_out} 08:30",
                    arrival_str=f"{d_out} 10:25",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=False,
                )
                hopa_out_2 = TransportLeg(
                    mode="bus",
                    carrier="HAVAŞ / Hopa-Sarp Sınır Servisi",
                    origin="RZV",
                    destination=city_code,
                    departure_str=f"{d_out} 11:00",
                    arrival_str=f"{d_out} 12:30",
                    price_eur_per_person=6.0 if city_code == "BUS" else 14.0,
                    saves_accommodation_night=False,
                )
                hopa_in_1 = TransportLeg(
                    mode="bus",
                    carrier="HAVAŞ / Hopa-Sarp Sınır Servisi",
                    origin=city_code,
                    destination="RZV",
                    departure_str=f"{d_in} 15:30",
                    arrival_str=f"{d_in} 17:00",
                    price_eur_per_person=6.0 if city_code == "BUS" else 14.0,
                    saves_accommodation_night=False,
                )
                hopa_in_2 = TransportLeg(
                    mode="flight",
                    carrier="AJet / Pegasus (Rize-Artvin RZV ↔ İstanbul)",
                    origin="RZV",
                    destination="SAW",
                    departure_str=f"{d_in} 19:30",
                    arrival_str=f"{d_in} 21:25",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=False,
                )

                routes.append(
                    RouteOption(
                        strategy_name=f"Vizesiz Sınır Köprüsü: Rize-Artvin Uçuşu + Sarp Sınır Transferi ({city_code})",
                        outbound_legs=[hopa_out_1, hopa_out_2],
                        inbound_legs=[hopa_in_1, hopa_in_2],
                        is_border_hack=False,
                        max_stops=1,
                        booking_hint_url="https://havas.net/",
                    )
                )

        # 2. Balkan Başkentleri & Şehirleri Gece Treni / Otobüs Hatları (Solo Mod)
        if mode == TravelMode.SOLO:
            overland_balkan_specs: Dict[str, tuple[str, str, str, float]] = {
                "SOF": ("night_train", "TCDD Halkalı-Sofya Ekspresi (Yataklı Gece Treni)", "IST (Halkalı)", 25.0),
                "SKG": ("night_bus", "Crazy Holidays / Alpar (İstanbul ↔ Selanik Gece Seferi)", "IST (Esenler)", 28.0),
                "OTP": ("night_bus", "Lüks Yonca / Toros Turizm (İstanbul ↔ Bükreş Gece Seferi)", "IST (Esenler)", 32.0),
                "SKP": ("night_bus", "Huntur / Alpar Turizm (İstanbul ↔ Üsküp Gece Seferi)", "IST (Esenler)", 30.0),
                "BEG": ("bus", "Kavim / Alpar Uluslararası Otobüs (İstanbul ↔ Belgrad)", "IST (Esenler)", 38.0),
                "SJJ": ("bus", "Centrotrans / Alpar (İstanbul ↔ Saraybosna)", "IST (Esenler)", 42.0),
                "TIA": ("bus", "Alpar Turizm (İstanbul ↔ Tiran Ekspres)", "IST (Esenler)", 35.0),
            }

            if city_code in overland_balkan_specs:
                m_type, carrier, origin_station, fare = overland_balkan_specs[city_code]
                out_leg = TransportLeg(
                    mode=m_type,
                    carrier=carrier,
                    origin=origin_station,
                    destination=city_code,
                    departure_str=f"{d_out_eve} 22:00 (Gece Yolculuğu = 0€ Otel!)",
                    arrival_str=f"{d_out} 06:45",
                    price_eur_per_person=fare,
                    saves_accommodation_night=True,
                )
                in_leg = TransportLeg(
                    mode=m_type,
                    carrier=carrier,
                    origin=city_code,
                    destination=origin_station,
                    departure_str=f"{d_in} 21:00",
                    arrival_str=f"{d_in_next} 06:30",
                    price_eur_per_person=fare,
                    saves_accommodation_night=True,
                )

                strategy = (
                    f"TCDD Yataklı Gece Treni: İstanbul ↔ {city_code}"
                    if m_type == "night_train"
                    else f"Uluslararası Gece Otobüsü: İstanbul ↔ {city_code}"
                )
                hint = (
                    "https://ebilet.tcddtasimacilik.gov.tr/"
                    if m_type == "night_train"
                    else "https://www.metroturizm.com.tr/"
                )

                routes.append(
                    RouteOption(
                        strategy_name=strategy,
                        outbound_legs=[out_leg],
                        inbound_legs=[in_leg],
                        is_border_hack=True,
                        max_stops=0,
                        booking_hint_url=hint,
                    )
                )

            elif city_code == "ATH":
                # Atina: Selanik Gece Otobüsü + Hellenic Train Hızlı Treni
                out_leg_1 = TransportLeg(
                    mode="night_bus",
                    carrier="Crazy Holidays (İstanbul ↔ Selanik Gece Seferi)",
                    origin="IST (Esenler)",
                    destination="SKG",
                    departure_str=f"{d_out_eve} 21:00",
                    arrival_str=f"{d_out} 06:30",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=True,
                )
                out_leg_2 = TransportLeg(
                    mode="train",
                    carrier="Hellenic Train (Selanik ↔ Atina Hızlı Tren)",
                    origin="SKG",
                    destination="ATH",
                    departure_str=f"{d_out} 08:00",
                    arrival_str=f"{d_out} 12:15",
                    price_eur_per_person=19.0,
                    saves_accommodation_night=False,
                )
                in_leg_1 = TransportLeg(
                    mode="train",
                    carrier="Hellenic Train (Atina ↔ Selanik Hızlı Tren)",
                    origin="ATH",
                    destination="SKG",
                    departure_str=f"{d_in} 15:00",
                    arrival_str=f"{d_in} 19:15",
                    price_eur_per_person=19.0,
                    saves_accommodation_night=False,
                )
                in_leg_2 = TransportLeg(
                    mode="night_bus",
                    carrier="Crazy Holidays (Selanik ↔ İstanbul Gece Seferi)",
                    origin="SKG",
                    destination="IST (Esenler)",
                    departure_str=f"{d_in} 21:30",
                    arrival_str=f"{d_in_next} 07:00",
                    price_eur_per_person=28.0,
                    saves_accommodation_night=True,
                )

                routes.append(
                    RouteOption(
                        strategy_name="Balkan Kara/Demiryolu Köprüsü: Selanik Gece Otobüsü + Hellenic Train (ATH)",
                        outbound_legs=[out_leg_1, out_leg_2],
                        inbound_legs=[in_leg_1, in_leg_2],
                        is_border_hack=True,
                        max_stops=1,
                        booking_hint_url="https://www.hellenictrain.gr/en",
                    )
                )

        return routes
