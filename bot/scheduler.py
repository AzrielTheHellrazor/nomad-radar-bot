from datetime import date
from typing import List, Optional
from config import ENABLE_AI
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
        days_ahead: int = 60,
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
            if specific_country:
                watchlist = [specific_country.upper()]
            elif mode == TravelMode.SOLO:
                watchlist = list(settings.solo_watchlist)
            else:
                watchlist = list(settings.couple_watchlist)
                couple_visas_norm = {v.upper() for v in settings.couple_visas}
                if couple_visas_norm:
                    for c in self.scorer.visa_engine.list_all_countries():
                        if c.visa_group.upper() in couple_visas_norm or c.code.upper() in couple_visas_norm:
                            if c.code not in watchlist:
                                watchlist.append(c.code)
            budget = (
                settings.solo_max_budget_eur
                if mode == TravelMode.SOLO
                else settings.couple_max_budget_eur
            )

            import asyncio
            sem = asyncio.Semaphore(4)

            async def _scan_code(c_code: str) -> List[DealPackage]:
                async with sem:
                    return await self.scorer.scan_and_score_country(
                        country_code=c_code,
                        mode=mode,
                        reference_date=ref,
                        days_ahead=days_ahead,
                        solo_visas=settings.solo_visas,
                        couple_visas=settings.couple_visas,
                        max_budget_eur=budget,
                    )

            country_deal_lists = await asyncio.gather(*[_scan_code(code) for code in watchlist])
            mode_candidates: List[DealPackage] = []
            for deals in country_deal_lists:
                for d in deals:
                    if force_notify or self.db.should_notify_deal(
                        d.deal_key, d.grand_total_eur
                    ):
                        mode_candidates.append(d)

            mode_candidates.sort(
                key=lambda d: (
                    not d.window.is_bridge_holiday,
                    -d.discount_vs_baseline_pct,
                    d.per_person_total_eur,
                )
            )

            selected = mode_candidates[:max_results_per_mode]
            for deal in selected:
                if ENABLE_AI:
                    await self.advisor.generate_commentary(deal)
                self.db.record_notified_deal(deal.deal_key, deal.grand_total_eur)
                final_deals.append(deal)

        return final_deals
