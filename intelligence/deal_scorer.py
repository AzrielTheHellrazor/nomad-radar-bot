import statistics
from datetime import date
from typing import List, Tuple
from accommodation.aggregator import AccommodationAggregator
from calendar_visa.holidays_tr import HolidayWindowCalculator
from calendar_visa.visa_matrix import VisaEngine
from config import MIN_DISCOUNT_PCT
from intelligence.campaign_radar import CampaignRadar
from models import DealPackage, RouteOption, StayOption, TravelMode, TravelWindow
from transport.aggregator import TransportAggregator


class DealScorer:
    """
    Tatil pencerelerini, vize kurallarını, çok modlu ulaşımı ve konaklamayı birleştirip
    Solo (1 Kişi - Yeşil Pasaport) ve Çift (2 Kişi - Yeşil + Bordo Pasaport) modları için
    en yüksek fiyat/performanslı paketleri üretir ve puanlar.
    """

    def __init__(self) -> None:
        self.holiday_calc = HolidayWindowCalculator()
        self.visa_engine = VisaEngine()
        self.transport_agg = TransportAggregator()
        self.stay_agg = AccommodationAggregator()
        self.campaign_radar = CampaignRadar()

    async def scan_and_score_country(
        self,
        country_code: str,
        mode: TravelMode,
        reference_date: date | None = None,
        days_ahead: int = 60,
        solo_visas: List[str] | None = None,
        couple_visas: List[str] | None = None,
        max_budget_eur: float = 500.0,
    ) -> List[DealPackage]:
        ref = reference_date or date.today()
        solo_v = solo_visas or []
        couple_v = couple_visas or []

        country = self.visa_engine.get_country(country_code)
        if not country:
            return []

        windows = self.holiday_calc.get_upcoming_windows(
            reference_date=ref, days_ahead=days_ahead
        )
        if not windows:
            return []

        # 1. Vize uygunluğu ve hazırlık süresi kriterini sağlayan pencereleri filtrele
        eligible_windows: List[Tuple[TravelWindow, dict]] = []
        for window in windows:
            days_until = max(0, (window.start_dt.date() - ref).days)
            visa_eval = self.visa_engine.evaluate_destination(
                country_code=country.code,
                mode=mode,
                days_until_trip=days_until,
                solo_visas=solo_v,
                couple_visas=couple_v,
            )
            if visa_eval["eligible"]:
                eligible_windows.append((window, visa_eval))

        if not eligible_windows:
            return []

        import asyncio
        passengers = 2 if mode == TravelMode.COUPLE else 1
        packages: List[DealPackage] = []
        sem = asyncio.Semaphore(6)

        # 2. Şehir bazlı gruplama: Her şehir için tüm uygun pencereler taranarak canlı medyan hesaplanır
        for city_code in country.main_cities:
            window_candidates: List[Tuple[TravelWindow, dict, RouteOption]] = []
            route_prices: List[float] = []

            async def _fetch_window(w: TravelWindow, ve: dict):
                async with sem:
                    r_list = await self.transport_agg.find_best_routes(
                        window=w, city_code=city_code, mode=mode
                    )
                    return w, ve, r_list

            window_results = await asyncio.gather(
                *[_fetch_window(window, visa_eval) for window, visa_eval in eligible_windows]
            )

            for window, visa_eval, routes in window_results:
                if not routes:
                    continue

                best_route = routes[0]
                # Validate route destination matches scanned city if route specifies destination
                route_dest = (
                    best_route.outbound_legs[-1].destination
                    if (best_route.outbound_legs and hasattr(best_route.outbound_legs[-1], "destination"))
                    else None
                )
                if route_dest and route_dest != city_code:
                    continue

                window_candidates.append((window, visa_eval, best_route))
                route_prices.append(best_route.roundtrip_price_per_person_eur)

            if not route_prices:
                continue

            # Rota bazlı tipik uçuş referansı ve taranan pencerelerdeki canlı medyan fiyatı
            if hasattr(self.transport_agg, "get_typical_rt_flight_eur"):
                typical_rt_flight_eur = self.transport_agg.get_typical_rt_flight_eur(city_code)
            else:
                typical_rt_flight_eur = 180.0

            live_median_rt_eur = float(statistics.median(route_prices))
            effective_flight_baseline = max(typical_rt_flight_eur, live_median_rt_eur)

            # 3. İki Aşamalı (2-Gate) Fırsat Eleme Süreci
            for window, visa_eval, best_route in window_candidates:
                flight_price = best_route.roundtrip_price_per_person_eur

                # --- GATE 1: Sadece Uçuş İndirim Oranı Doğrulaması ---
                flight_discount_pct = int(
                    round(
                        max(
                            0.0,
                            (1.0 - (flight_price / max(1.0, effective_flight_baseline)))
                            * 100,
                        )
                    )
                )

                # Uçuş indirimi %35'in altındaysa konaklama hiç sorgulanmadan elenir!
                if flight_discount_pct < MIN_DISCOUNT_PCT:
                    continue

                # --- GATE 2: Gerçekçi Ücretli Konaklama ve Bütçe Kontrolü ---
                stays = self.stay_agg.find_best_stays(
                    window=window,
                    city_code=city_code,
                    mode=mode,
                    route=best_route,
                )
                if not stays:
                    continue

                # Birincil konaklama mutlaka ücretli (Hostel veya Otel) olmalı, 0€ stays alternatifte kalmalı
                primary_stay = next(
                    (
                        s for s in stays
                        if not getattr(s, "is_free_stay", False) and s.price_per_night_total_eur > 0
                    ),
                    None,
                )
                if not primary_stay:
                    continue

                alt_stays = [s for s in stays if s is not primary_stay]

                pkg = DealPackage(
                    mode=mode,
                    country=country,
                    city_code=city_code,
                    city_name_tr=self.visa_engine.get_city_name_tr(city_code),
                    window=window,
                    route=best_route,
                    stay=primary_stay,
                    alternative_stays=alt_stays,
                    passengers=passengers,
                    visa_cost_total_eur=float(visa_eval["visa_cost_eur"]),
                    visa_note=str(visa_eval["visa_note"]),
                    campaign_badge=self.campaign_radar.get_campaign_badge_for_country(
                        country.code
                    ),
                    baseline_flight_per_person_eur=effective_flight_baseline,
                    flight_discount_pct=flight_discount_pct,
                    discount_vs_baseline_pct=flight_discount_pct,
                )

                # Kullanıcının belirlediği toplam bütçe kontrolü
                if pkg.grand_total_eur <= max_budget_eur:
                    packages.append(pkg)

        # Önce köprü tatilleri, sonra en yüksek uçuş indirimi ve en uygun kişi başı fiyat
        packages.sort(
            key=lambda p: (
                not p.window.is_bridge_holiday,
                -p.flight_discount_pct,
                p.per_person_total_eur,
            )
        )
        return packages
