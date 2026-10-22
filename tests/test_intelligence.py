import pytest
from datetime import date
from models import TravelMode
from intelligence.deal_scorer import DealScorer
from intelligence.gemini_advisor import GeminiAdvisor


@pytest.mark.asyncio
async def test_deal_scorer_builds_solo_and_couple_packages_accurately():
    scorer = DealScorer()
    advisor = GeminiAdvisor()

    # 1. SOLO MOD: 28 Ekim - 1 Kasım Portekiz (PT) paketi
    solo_deals = await scorer.scan_and_score_country(
        country_code="PT",
        mode=TravelMode.SOLO,
        reference_date=date(2026, 10, 22),
        days_ahead=15,
        solo_visas=[],
        couple_visas=[],
        max_budget_eur=250.0,
    )
    assert len(solo_deals) >= 1
    pt_deal = solo_deals[0]
    assert pt_deal.mode == TravelMode.SOLO
    assert pt_deal.passengers == 1
    assert pt_deal.visa_cost_total_eur == 0.0
    assert pt_deal.route.is_border_hack is True
    # Gece treni/otobüsü sayesinde 4 gece yerine 3 gece konaklama ödenmeli
    assert pt_deal.stay.nights_charged == 3
    # Ayrıca 0€ Bedava konaklama alternatifleri (TrustedHousesitters/Couchsurfing) pakette yer almalı
    assert any(s.is_free_stay for s in pt_deal.alternative_stays)

    commentary = await advisor.generate_commentary(pt_deal)
    assert "Portekiz" in commentary or "Porto" in commentary or "Lizbon" in commentary
    assert "izin" in commentary.lower()

    # 2. ÇİFT MODU: 28 Ekim - 1 Kasım Karadağ (ME) veya Yunan Adaları (GR_ISLANDS)
    couple_deals = await scorer.scan_and_score_country(
        country_code="ME",
        mode=TravelMode.COUPLE,
        reference_date=date(2026, 10, 22),
        days_ahead=15,
        solo_visas=[],
        couple_visas=[],
        max_budget_eur=650.0,
    )
    assert len(couple_deals) >= 1
    me_deal = couple_deals[0]
    assert me_deal.mode == TravelMode.COUPLE
    assert me_deal.passengers == 2
    assert me_deal.route.is_border_hack is False
    assert me_deal.stay.is_free_stay is False
    assert me_deal.stay.rating >= 8.0
    # 2 Kişilik ulaşım toplamı = 2 x kişi başı bilet
    assert me_deal.transport_total_eur == round(me_deal.route.roundtrip_price_per_person_eur * 2, 2)
