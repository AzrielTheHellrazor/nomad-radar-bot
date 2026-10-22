from datetime import date
from typing import List, Optional
from database import Database
from intelligence.deal_scorer import DealScorer
from intelligence.gemini_advisor import GeminiAdvisor
from models import DealPackage, TravelMode


class DealScanOrchestrator:
    """
    Kullanıcının aktif moduna (SOLO, COUPLE veya BOTH) göre izlenen ülkeleri tarar,
    Gemini AI yorumlarını ekler ve daha önce bildirilmemiş fırsatları döndürür.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self.scorer = DealScorer()
        self.advisor = GeminiAdvisor()

    async def run_scan_for_user(
        self,
        chat_id: int,
        reference_date: date | None = None,
        days_ahead: int = 45,
        specific_country: Optional[str] = None,
        max_results_per_mode: int = 3,
        force_notify: bool = False,
    ) -> List[DealPackage]:
        settings = self.db.get_user_settings(chat_id)
        ref = reference_date or date.today()

        modes_to_run: List[TravelMode] = []
        if settings.active_mode == TravelMode.BOTH:
            modes_to_run = [TravelMode.SOLO, TravelMode.COUPLE]
        else:
            modes_to_run = [settings.active_mode]

        final_deals: List[DealPackage] = []

        for mode in modes_to_run:
            watchlist = (
                [specific_country.upper()]
                if specific_country
                else (
                    settings.solo_watchlist
                    if mode == TravelMode.SOLO
                    else settings.couple_watchlist
                )
            )
            budget = (
                settings.solo_max_budget_eur
                if mode == TravelMode.SOLO
                else settings.couple_max_budget_eur
            )

            mode_candidates: List[DealPackage] = []
            for code in watchlist:
                deals = await self.scorer.scan_and_score_country(
                    country_code=code,
                    mode=mode,
                    reference_date=ref,
                    days_ahead=days_ahead,
                    solo_visas=settings.solo_visas,
                    couple_visas=settings.couple_visas,
                    max_budget_eur=budget,
                )
                for d in deals:
                    if force_notify or self.db.should_notify_deal(
                        d.deal_key, d.grand_total_eur
                    ):
                        mode_candidates.append(d)

            mode_candidates.sort(
                key=lambda d: (
                    not d.window.is_bridge_holiday,
                    d.per_person_total_eur,
                )
            )

            selected = mode_candidates[:max_results_per_mode]
            for deal in selected:
                await self.advisor.generate_commentary(deal)
                self.db.record_notified_deal(deal.deal_key, deal.grand_total_eur)
                final_deals.append(deal)

        return final_deals
