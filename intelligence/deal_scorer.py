from datetime import date
from typing import List
from accommodation.aggregator import AccommodationAggregator
from calendar_visa.holidays_tr import HolidayWindowCalculator
from calendar_visa.visa_matrix import VisaEngine
from config import MIN_DISCOUNT_PCT
from intelligence.campaign_radar import CampaignRadar
from models import DealPackage, TravelMode, TravelWindow
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
        packages: List[DealPackage] = []

        for window in windows:
            days_until = max(0, (window.start_dt.date() - ref).days)
            visa_eval = self.visa_engine.evaluate_destination(
                country_code=country.code,
                mode=mode,
                days_until_trip=days_until,
                solo_visas=solo_v,
                couple_visas=couple_v,
            )
            if not visa_eval["eligible"]:
                continue

            for city_code in country.main_cities[:2]:
                routes = await self.transport_agg.find_best_routes(
                    window=window, city_code=city_code, mode=mode
                )
                if not routes:
                    continue

                best_route = routes[0]
                stays = self.stay_agg.find_best_stays(
                    window=window,
                    city_code=city_code,
                    mode=mode,
                    route=best_route,
                )
                if not stays:
                    continue

                primary_stay = stays[0]
                alt_stays = stays[1:]
                passengers = 2 if mode == TravelMode.COUPLE else 1

                baseline_total = country.typical_package_Baseline_eur * passengers
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
                )

                discount_pct = int(
                    round(
                        max(
                            0.0,
                            (1.0 - (pkg.grand_total_eur / max(1.0, baseline_total)))
                            * 100,
                        )
                    )
                )
                pkg.discount_vs_baseline_pct = discount_pct

                # Sadece diğer zamanlardan EKSTRA UCUZ (%35+ indirimli) ve bütçe dahilindeki fırsatları kabul et!
                if pkg.grand_total_eur <= max_budget_eur and discount_pct >= MIN_DISCOUNT_PCT:
                    packages.append(pkg)

        # Önce köprü tatilleri ve normal zamana göre EN YÜKSEK İNDİRİM ORANINI öne çıkararak sırala
        packages.sort(
            key=lambda p: (
                not p.window.is_bridge_holiday,
                -p.discount_vs_baseline_pct,
                p.per_person_total_eur,
            )
        )
        return packages
