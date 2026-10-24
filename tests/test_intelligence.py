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


@pytest.mark.asyncio
async def test_deal_scorer_rejects_rack_rate_flight_with_free_or_cheap_stay():
    """
    R1 Requirement: A flight at rack rate (<35% discount vs baseline) paired with 0€ stay
    or cheap hostel must be REJECTED by DealScorer and produce 0 packages.
    Example: FCO baseline is 176.0€ (88€ * 2). Flight price 150€ has discount 14.8% < 35%.
    Even with 0€ stay, it must NEVER qualify as a deal package.
    """
    from unittest.mock import AsyncMock, patch
    from models import RouteOption, TransportLeg, StayOption

    scorer = DealScorer()

    # 150€ roundtrip flight (75€ out + 75€ in) for FCO
    rack_route = RouteOption(
        strategy_name="Rack Rate Flight (IST ↔ FCO)",
        outbound_legs=[
            TransportLeg(
                mode="flight",
                carrier="Pegasus",
                origin="SAW",
                destination="FCO",
                departure_str="28.10 14:00",
                arrival_str="28.10 16:00",
                price_eur_per_person=75.0,
            )
        ],
        inbound_legs=[
            TransportLeg(
                mode="flight",
                carrier="Pegasus",
                origin="FCO",
                destination="SAW",
                departure_str="01.11 18:00",
                arrival_str="01.11 20:00",
                price_eur_per_person=75.0,
            )
        ],
        is_border_hack=False,
        max_stops=0,
    )
    free_stay = StayOption(
        provider="Couchsurfing",
        title="Free Couchsurfing Stay",
        stay_type="free_couch",
        city="Roma",
        rating=9.5,
        price_per_night_total_eur=0.0,
        nights_charged=4,
        is_free_stay=True,
    )

    with patch.object(scorer.transport_agg, "find_best_routes", new=AsyncMock(return_value=[rack_route])):
        with patch.object(scorer.stay_agg, "find_best_stays", return_value=[free_stay]) as mock_stay:
            deals = await scorer.scan_and_score_country(
                country_code="IT",
                mode=TravelMode.SOLO,
                reference_date=date(2026, 10, 22),
                days_ahead=15,
                solo_visas=[],
                couple_visas=[],
                max_budget_eur=300.0,
            )
            fco_deals = [d for d in deals if d.city_code == "FCO"]
            assert len(fco_deals) == 0
            assert mock_stay.call_count == 0, "Gate 1 must reject before querying accommodation!"


@pytest.mark.asyncio
async def test_deal_scorer_accepts_genuine_flight_deal_and_populates_fields():
    """
    R1 Requirement: A genuine deal flight (>=35% discount vs baseline) must be ACCEPTED
    and expose baseline_flight_per_person_eur and flight_discount_pct on DealPackage.
    Example: FCO baseline is 176.0€. Deal flight price 80€ (40€ out + 40€ in) has discount 54.5% >= 35%.
    """
    from unittest.mock import AsyncMock, patch
    from models import RouteOption, TransportLeg, StayOption

    scorer = DealScorer()

    deal_route = RouteOption(
        strategy_name="Super Deal Flight (SAW ↔ FCO)",
        outbound_legs=[
            TransportLeg(
                mode="flight",
                carrier="Pegasus Flash",
                origin="SAW",
                destination="FCO",
                departure_str="28.10 14:00",
                arrival_str="28.10 16:00",
                price_eur_per_person=40.0,
            )
        ],
        inbound_legs=[
            TransportLeg(
                mode="flight",
                carrier="Pegasus Flash",
                origin="FCO",
                destination="SAW",
                departure_str="01.11 18:00",
                arrival_str="01.11 20:00",
                price_eur_per_person=40.0,
            )
        ],
        is_border_hack=False,
        max_stops=0,
    )
    paid_stay = StayOption(
        provider="Hostelworld",
        title="Hostel Roma",
        stay_type="hostel_8plus",
        city="Roma",
        rating=8.8,
        price_per_night_total_eur=20.0,
        nights_charged=4,
        is_free_stay=False,
    )

    with patch.object(scorer.transport_agg, "find_best_routes", new=AsyncMock(return_value=[deal_route])):
        with patch.object(scorer.stay_agg, "find_best_stays", return_value=[paid_stay]):
            deals = await scorer.scan_and_score_country(
                country_code="IT",
                mode=TravelMode.SOLO,
                reference_date=date(2026, 10, 22),
                days_ahead=15,
                solo_visas=[],
                couple_visas=[],
                max_budget_eur=300.0,
            )
            fco_deals = [d for d in deals if d.city_code == "FCO"]
            assert len(fco_deals) >= 1
            deal = fco_deals[0]
            assert deal.city_code == "FCO"
            assert deal.baseline_flight_per_person_eur == 176.0
            assert deal.flight_discount_pct == 55
            assert deal.discount_vs_baseline_pct == deal.flight_discount_pct
            assert deal.transport_total_eur == 80.0
            assert deal.grand_total_eur <= 300.0


@pytest.mark.asyncio
async def test_deal_scorer_effective_baseline_uses_live_median_when_higher():
    """
    R1 Requirement: effective_flight_baseline = max(typical_rt_flight_eur, live_median_rt_eur).
    If live multi-window median is 200€ and typical baseline is 176€, effective baseline is 200€.
    A deal at 90€ has discount (1 - 90/200) = 55% vs the 200€ baseline.
    """
    from unittest.mock import patch
    from models import RouteOption, TransportLeg, StayOption

    scorer = DealScorer()

    routes_by_call = [
        [RouteOption("Deal", [TransportLeg("flight", "P", "SAW", "FCO", "d", "a", 45.0)], [TransportLeg("flight", "P", "FCO", "SAW", "d", "a", 45.0)])],
        [RouteOption("Normal1", [TransportLeg("flight", "P", "SAW", "FCO", "d", "a", 100.0)], [TransportLeg("flight", "P", "FCO", "SAW", "d", "a", 100.0)])],
        [RouteOption("Normal2", [TransportLeg("flight", "P", "SAW", "FCO", "d", "a", 100.0)], [TransportLeg("flight", "P", "FCO", "SAW", "d", "a", 100.0)])],
        [RouteOption("High", [TransportLeg("flight", "P", "SAW", "FCO", "d", "a", 110.0)], [TransportLeg("flight", "P", "FCO", "SAW", "d", "a", 110.0)])],
    ]

    call_idx = 0
    async def mock_find_routes(window, city_code, mode):
        nonlocal call_idx
        if city_code != "FCO":
            return []
        res = routes_by_call[call_idx % len(routes_by_call)]
        call_idx += 1
        return res

    paid_stay = StayOption(
        provider="Hostelworld",
        title="Hostel Roma",
        stay_type="hostel_8plus",
        city="Roma",
        rating=8.8,
        price_per_night_total_eur=20.0,
        nights_charged=4,
        is_free_stay=False,
    )

    with patch.object(scorer.transport_agg, "find_best_routes", side_effect=mock_find_routes):
        with patch.object(scorer.stay_agg, "find_best_stays", return_value=[paid_stay]):
            deals = await scorer.scan_and_score_country(
                country_code="IT",
                mode=TravelMode.SOLO,
                reference_date=date(2026, 10, 22),
                days_ahead=20,
                solo_visas=[],
                couple_visas=[],
                max_budget_eur=300.0,
            )
            fco_deals = [d for d in deals if d.city_code == "FCO"]
            assert len(fco_deals) >= 1
            deal = fco_deals[0]
            assert deal.baseline_flight_per_person_eur == 200.0
            assert deal.flight_discount_pct == 55
