import os
import httpx
from datetime import timedelta
from typing import Dict, List, Optional, Tuple
from models import RouteOption, TransportLeg, TravelWindow


# Sofya (SOF), Selanik (SKG) ve Bükreş (OTP) çıkışlı Ryanair / WizzAir / EasyJet ultra-ucuz hatlar
BALKAN_LOWCOST_HUBS: Dict[str, Tuple[str, str, float]] = {
    "OPO": ("SOF", "Ryanair / WizzAir (Sofya Aktarmalı)", 24.0),
    "LIS": ("SOF", "WizzAir / Ryanair (Sofya -> Lizbon/Porto + FlixBus)", 27.0),
    "FCO": ("SOF", "Ryanair / WizzAir (Sofya -> Roma)", 16.0),
    "MXP": ("SOF", "Ryanair (Sofya -> Milano Bergamo)", 15.0),
    "BLQ": ("SOF", "Ryanair (Sofya -> Bologna)", 17.0),
    "VCE": ("SOF", "Ryanair (Sofya -> Venedik Treviso)", 18.0),
    "NAP": ("SOF", "Ryanair (Sofya -> Napoli)", 19.0),
    "BCN": ("SOF", "Ryanair / WizzAir (Sofya -> Barselona)", 22.0),
    "MAD": ("SOF", "Ryanair / WizzAir (Sofya -> Madrid)", 24.0),
    "CDG": ("SOF", "Ryanair (Sofya -> Paris Beauvais)", 21.0),
    "EIN": ("SOF", "Ryanair / WizzAir (Sofya -> Eindhoven/Amsterdam)", 19.0),
    "AMS": ("SOF", "Ryanair (Sofya -> Eindhoven + Tren)", 26.0),
    "BER": ("SKG", "Ryanair (Selanik -> Berlin)", 18.0),
    "MUC": ("SOF", "Ryanair (Sofya -> Memmingen/Münih)", 17.0),
    "CGN": ("SOF", "Ryanair (Sofya -> Köln)", 16.0),
    "VIE": ("SOF", "Ryanair (Sofya -> Viyana)", 15.0),
    "BUD": ("SOF", "Ryanair / WizzAir (Sofya -> Budapeşte)", 14.0),
    "PRG": ("SOF", "Ryanair (Sofya -> Prag)", 18.0),
    "WAW": ("SOF", "WizzAir / Ryanair (Sofya -> Varşova)", 19.0),
    "KRK": ("SKG", "Ryanair (Selanik -> Krakow)", 18.0),
    "LHR": ("SOF", "Ryanair / WizzAir (Sofya -> Londra Luton/Stansted)", 17.0),
    "DUB": ("SOF", "Ryanair (Sofya -> Dublin)", 23.0),
}


_RYANAIR_FARE_CACHE: Dict[str, Optional[float]] = {}


class BorderHopEngine:
    """
    SOLO MOD ÖZEL HACK MOTORU:
    Türkiye'de resmi tatillerde (örn. 29 Ekim veya Bayramlar) İstanbul uçuşları 200-350€'ya fırladığında,
    İstanbul (Halkalı / Esenler) -> Gece Treni (Sofya Ekspresi) veya Gece Otobüsü (Metro / ArdaTur / Huntur)
    ile Bulgaristan (Sofya - SOF) veya Yunanistan (Selanik - SKG) sınırını geçip
    oradan Ryanair / WizzAir ile 15€-27€'ya Avrupa'ya uçma kombinasyonlarını kurar.
    Ayrıca gece treni/otobüsü sayesinde 1 gece otel konaklama maliyetini sıfırlar!
    """

    async def build_balkan_hack_routes(
        self, window: TravelWindow, city_code: str
    ) -> List[RouteOption]:
        code = city_code.upper()
        if code not in BALKAN_LOWCOST_HUBS:
            return []

        hub_code, lowcost_carrier, base_flight_eur = BALKAN_LOWCOST_HUBS[code]

        # Canlı modda (%100 gerçek fiyat) Ryanair'de uçuş yoksa uydurma fiyat döndürme!
        live_mode = os.getenv("LIVE_RYANAIR_HTTP", "1") == "1"
        live_price = await self._try_fetch_ryanair_fare(hub_code, code, window)
        if live_mode and live_price is None:
            return []
        one_way_flight_eur = live_price if live_price is not None else base_flight_eur

        hub_name = "Sofya (SOF)" if hub_code == "SOF" else "Selanik (SKG)"
        overland_carrier = (
            "TCDD Sofya Ekspresi (Gece Treni) / ArdaTur Gece Otobüsü"
            if hub_code == "SOF"
            else "İstanbul -> Selanik Gece Otobüsü (Crazy Holidays / Metro)"
        )
        overland_price_eur = 25.0 if hub_code == "SOF" else 28.0

        # Çıkıştan bir önceki akşam 22:00'de İstanbul'dan gece treni/otobüsüyle yola çıkılır -> 1 gece konaklama bedava!
        eve_dt = window.start_dt - timedelta(hours=15)
        out_leg_1 = TransportLeg(
            mode="night_train" if hub_code == "SOF" else "night_bus",
            carrier=overland_carrier,
            origin="IST (Halkalı/Esenler)",
            destination=hub_code,
            departure_str=f"{eve_dt.strftime('%d.%m')} 22:00 (Gece Yolculuğu = 0€ Otel!)",
            arrival_str=f"{window.start_dt.strftime('%d.%m')} 06:45",
            price_eur_per_person=overland_price_eur,
            saves_accommodation_night=True,
        )
        out_leg_2 = TransportLeg(
            mode="flight",
            carrier=lowcost_carrier,
            origin=hub_code,
            destination=code,
            departure_str=f"{window.start_dt.strftime('%d.%m')} 10:15",
            arrival_str=f"{window.start_dt.strftime('%d.%m')} 12:30",
            price_eur_per_person=one_way_flight_eur,
            saves_accommodation_night=False,
        )

        # Dönüş: Hedef şehirden Sofya/Selanik'e uçuş + İstanbul'a otobüs/tren
        in_leg_1 = TransportLeg(
            mode="flight",
            carrier=lowcost_carrier,
            origin=code,
            destination=hub_code,
            departure_str=f"{window.end_dt.strftime('%d.%m')} 13:20",
            arrival_str=f"{window.end_dt.strftime('%d.%m')} 17:10",
            price_eur_per_person=round(one_way_flight_eur * 1.05, 2),
            saves_accommodation_night=False,
        )
        in_leg_2 = TransportLeg(
            mode="bus",
            carrier=f"{hub_name} -> İstanbul Ekspres Otobüs",
            origin=hub_code,
            destination="IST (Esenler)",
            departure_str=f"{window.end_dt.strftime('%d.%m')} 18:30",
            arrival_str=f"{window.end_dt.strftime('%d.%m')} 23:55",
            price_eur_per_person=overland_price_eur,
            saves_accommodation_night=False,
        )

        ryanair_url = (
            f"https://www.ryanair.com/gb/en/trip/flights/select?adults=1&originIata={hub_code}"
            f"&destinationIata={code}&dateOut={window.start_dt.strftime('%Y-%m-%d')}"
        )

        return [
            RouteOption(
                strategy_name=f"🔥 Balkan Sınır Hack: {hub_name} Gece Treni/Otobüsü + {lowcost_carrier}",
                outbound_legs=[out_leg_1, out_leg_2],
                inbound_legs=[in_leg_1, in_leg_2],
                is_border_hack=True,
                max_stops=1,
                booking_hint_url=ryanair_url,
            )
        ]

    async def _try_fetch_ryanair_fare(
        self, origin_iata: str, dest_iata: str, window: TravelWindow
    ) -> Optional[float]:
        """Ryanair açık JSON endpoint'inden gerçek anlık fiyat sorgulamayı dener."""
        if os.getenv("LIVE_RYANAIR_HTTP", "1") != "1":
            return None
        d_from = (window.start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        d_to = (window.start_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        cache_key = f"{origin_iata}:{dest_iata}:{d_from}:{d_to}"
        if cache_key in _RYANAIR_FARE_CACHE:
            return _RYANAIR_FARE_CACHE[cache_key]

        url = (
            "https://services-api.ryanair.com/farfnd/v4/oneWayFares"
            f"?departureAirportIataCode={origin_iata}&arrivalAirportIataCode={dest_iata}"
            f"&outboundDepartureDateFrom={d_from}"
            f"&outboundDepartureDateTo={d_to}&currency=EUR"
        )
        try:
            async with httpx.AsyncClient(timeout=3.5) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    fares = resp.json().get("fares", [])
                    if fares:
                        val = fares[0].get("outbound", {}).get("price", {}).get("value")
                        if val:
                            price_val = float(val)
                            _RYANAIR_FARE_CACHE[cache_key] = price_val
                            return price_val
        except Exception:
            pass
        _RYANAIR_FARE_CACHE[cache_key] = None
        return None
