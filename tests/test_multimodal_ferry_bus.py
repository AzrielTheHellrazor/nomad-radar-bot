import pytest
from datetime import datetime
from models import CountryRule, DealPackage, RouteOption, StayOption, TransportLeg, TravelMode, TravelWindow, VisaCategory
from transport.aggregator import TransportAggregator
from transport.multimodal_ferry_bus import MultiModalFerryBusEngine
from transport.direct_flights import _parse_all_flight_buckets, DirectFlightScanner
from bot.formatter import format_deal_telegram_message


@pytest.fixture
def sample_window():
    return TravelWindow(
        title="29 Ekim Cumhuriyet Bayramı Köprü Tatili",
        start_dt=datetime(2026, 10, 28, 13, 0),
        end_dt=datetime(2026, 11, 1, 23, 59),
        total_days=4.5,
        leave_days_required=1.0,
        nights=4,
        is_bridge_holiday=True,
    )


@pytest.mark.asyncio
async def test_aegean_greek_islands_ferries_solo_and_couple(sample_window):
    """
    RHO (Rodos) ve JMK (Sakız / Midilli):
    - Marmaris/Fethiye ↔ Rodos Hızlı Katamaran Feribot
    - Çeşme ↔ Sakız / Ayvalık ↔ Midilli Feribotu
    Solo ve Çift modlarında sorunsuz çalışmalı ve feribot bacakları mode='ferry' olmalı.
    """
    engine = MultiModalFerryBusEngine()

    for mode in (TravelMode.SOLO, TravelMode.COUPLE):
        rho_routes = await engine.build_multimodal_routes(sample_window, "RHO", mode=mode)
        assert len(rho_routes) >= 1
        best_rho = rho_routes[0]
        assert best_rho.outbound_legs[-1].destination == "RHO"
        assert best_rho.inbound_legs[0].origin == "RHO"
        ferry_legs = [leg for leg in best_rho.outbound_legs + best_rho.inbound_legs if leg.mode == "ferry"]
        assert len(ferry_legs) >= 2
        assert "Feribot" in ferry_legs[0].carrier or "Katamaran" in ferry_legs[0].carrier
        assert best_rho.is_border_hack is False
        assert best_rho.max_stops <= 1

        jmk_routes = await engine.build_multimodal_routes(sample_window, "JMK", mode=mode)
        assert len(jmk_routes) >= 1
        best_jmk = jmk_routes[0]
        assert best_jmk.outbound_legs[-1].destination == "JMK"
        assert best_jmk.inbound_legs[0].origin == "JMK"
        jmk_ferry_legs = [leg for leg in best_jmk.outbound_legs + best_jmk.inbound_legs if leg.mode == "ferry"]
        assert len(jmk_ferry_legs) >= 2
        assert "Feribot" in jmk_ferry_legs[0].carrier


@pytest.mark.asyncio
async def test_korea_japan_sea_ferry_and_rail_bus_bridge(sample_window):
    """
    FUK (Fukuoka) ve KIX (Osaka):
    - IST/SAW ↔ ICN Uçuş + Seul ↔ Busan KoBUS (17€) + Busan ↔ Fukuoka Camellia Line Gece Feribotu (52€, saves_accommodation_night=True)
    - KIX için ek olarak Willer Express (28€)
    Solo ve Çift modlarının her ikisinde de geçerli olmalı.
    """
    engine = MultiModalFerryBusEngine()

    for mode in (TravelMode.SOLO, TravelMode.COUPLE):
        fuk_routes = await engine.build_multimodal_routes(sample_window, "FUK", mode=mode)
        assert len(fuk_routes) >= 1
        best_fuk = fuk_routes[0]
        assert best_fuk.outbound_legs[-1].destination == "FUK"
        assert best_fuk.inbound_legs[0].origin == "FUK"

        modes = [leg.mode for leg in best_fuk.outbound_legs]
        assert "flight" in modes
        assert "bus" in modes
        assert "ferry" in modes

        # Camellia Line gece feribotu konaklama gecesi kurtarır
        camellia_out = [leg for leg in best_fuk.outbound_legs if leg.mode == "ferry"][0]
        assert camellia_out.price_eur_per_person == 52.0
        assert camellia_out.saves_accommodation_night is True
        assert "Camellia Line" in camellia_out.carrier

        kobus_out = [leg for leg in best_fuk.outbound_legs if leg.mode == "bus"][0]
        assert kobus_out.price_eur_per_person == 17.0

        assert best_fuk.is_border_hack is False
        assert best_fuk.max_stops <= 1

        # KIX (Osaka) rotası
        kix_routes = await engine.build_multimodal_routes(sample_window, "KIX", mode=mode)
        assert len(kix_routes) >= 1
        best_kix = kix_routes[0]
        assert best_kix.outbound_legs[-1].destination == "KIX"
        assert best_kix.inbound_legs[0].origin == "KIX"
        willer_legs = [leg for leg in best_kix.outbound_legs if "Willer Express" in leg.carrier]
        assert len(willer_legs) >= 1
        assert willer_legs[0].price_eur_per_person == 28.0


@pytest.mark.asyncio
async def test_adriatic_mediterranean_ferries_solo_mode(sample_window):
    """
    DBV (Dubrovnik) & SPU (Split):
    - İtalya (Bari/Ancona) uçuşu + Jadrolinija Gece Feribotu
    Solo modda sunulmalı ve saves_accommodation_night=True olmalı.
    """
    engine = MultiModalFerryBusEngine()

    dbv_routes = await engine.build_multimodal_routes(sample_window, "DBV", mode=TravelMode.SOLO)
    assert len(dbv_routes) >= 1
    best_dbv = dbv_routes[0]
    assert best_dbv.outbound_legs[-1].destination == "DBV"
    assert best_dbv.inbound_legs[0].origin == "DBV"
    ferry_legs = [l for l in best_dbv.outbound_legs if l.mode == "ferry"]
    assert len(ferry_legs) >= 1
    assert "Jadrolinija" in ferry_legs[0].carrier
    assert ferry_legs[0].saves_accommodation_night is True
    assert best_dbv.saved_nights_count >= 1

    spu_routes = await engine.build_multimodal_routes(sample_window, "SPU", mode=TravelMode.SOLO)
    assert len(spu_routes) >= 1
    assert spu_routes[0].outbound_legs[-1].destination == "SPU"


@pytest.mark.asyncio
async def test_overland_bus_and_train_routes(sample_window):
    """
    Vizesiz ve Sınır Ötesi Kara/Demiryolu Rotaları:
    - TBS / BUS: Metro Turizm (34€) / Rize-Artvin uçuşu + Sarp transferi
    - SOF: TCDD Halkalı-Sofya Ekspresi (25€, night_train)
    - SKG, ATH, OTP, SKP, BEG, SJJ, TIA uluslararası otobüs hatları
    """
    engine = MultiModalFerryBusEngine()

    # BUS (Batum) Solo
    bus_solo = await engine.build_multimodal_routes(sample_window, "BUS", mode=TravelMode.SOLO)
    assert len(bus_solo) >= 1
    assert bus_solo[0].outbound_legs[-1].destination == "BUS"
    assert bus_solo[0].outbound_legs[0].price_eur_per_person == 34.0
    assert bus_solo[0].saved_nights_count >= 1

    # TBS (Tiflis) Couple
    tbs_couple = await engine.build_multimodal_routes(sample_window, "TBS", mode=TravelMode.COUPLE)
    assert len(tbs_couple) >= 1
    assert tbs_couple[0].outbound_legs[-1].destination == "TBS"
    assert tbs_couple[0].is_border_hack is False
    assert tbs_couple[0].max_stops <= 1

    # SOF (Sofya) Gece Treni
    sof_routes = await engine.build_multimodal_routes(sample_window, "SOF", mode=TravelMode.SOLO)
    assert len(sof_routes) >= 1
    sof_train = [r for r in sof_routes if any(l.mode == "night_train" for l in r.outbound_legs)][0]
    assert "Sofya Ekspresi" in sof_train.outbound_legs[0].carrier
    assert sof_train.outbound_legs[0].price_eur_per_person == 25.0
    assert sof_train.outbound_legs[0].saves_accommodation_night is True

    # SKP, BEG, SJJ, TIA
    for code in ("SKP", "BEG", "SJJ", "TIA"):
        routes = await engine.build_multimodal_routes(sample_window, code, mode=TravelMode.SOLO)
        assert len(routes) >= 1
        assert routes[0].outbound_legs[-1].destination == code


@pytest.mark.asyncio
async def test_central_asia_visa_free_bridge(sample_window):
    """
    ICN (Seul): SAW ↔ ALA Almatı (Pegasus 125€) + ALA ↔ ICN Seul (Eastar Jet 165€)
    """
    engine = MultiModalFerryBusEngine()
    icn_routes = await engine.build_multimodal_routes(sample_window, "ICN", mode=TravelMode.SOLO)
    bridge_routes = [r for r in icn_routes if "Orta Asya" in r.strategy_name]
    assert len(bridge_routes) >= 1
    best_bridge = bridge_routes[0]
    assert best_bridge.outbound_legs[-1].destination == "ICN"
    assert best_bridge.inbound_legs[0].origin == "ICN"
    assert best_bridge.outbound_legs[0].destination == "ALA"
    assert best_bridge.outbound_legs[1].origin == "ALA"
    assert best_bridge.outbound_legs[0].price_eur_per_person == 125.0
    assert best_bridge.outbound_legs[1].price_eur_per_person == 165.0


@pytest.mark.asyncio
async def test_transport_aggregator_couple_mode_invariants_and_ferry_inclusion(sample_window):
    """
    TransportAggregator:
    - TIV için Çift modunda: is_border_hack=False, max_stops<=1, saved_nights_count=0 kesinlikle korunmalı!
    - FUK için Çift modunda: Kore-Japonya Camellia Line feribot rotası başarıyla dahil edilmeli!
    - RHO için Çift modunda: Marmaris Katamaran feribot rotası dahil edilmeli!
    """
    agg = TransportAggregator()

    # 1. TIV Çift Modu Kesin Koruma
    tiv_routes = await agg.find_best_routes(sample_window, "TIV", mode=TravelMode.COUPLE)
    assert len(tiv_routes) >= 1
    for r in tiv_routes:
        assert r.is_border_hack is False
        assert r.max_stops <= 1
        assert r.saved_nights_count == 0

    # 2. FUK Çift Modu Feribot Dahil Edilmesi
    fuk_routes = await agg.find_best_routes(sample_window, "FUK", mode=TravelMode.COUPLE)
    assert len(fuk_routes) >= 1
    ferry_routes = [r for r in fuk_routes if any(l.mode == "ferry" for l in r.outbound_legs)]
    assert len(ferry_routes) >= 1
    best_ferry = ferry_routes[0]
    assert best_ferry.is_border_hack is False
    assert best_ferry.max_stops <= 1

    # 3. RHO Çift Modu Katamaran Dahil Edilmesi
    rho_routes = await agg.find_best_routes(sample_window, "RHO", mode=TravelMode.COUPLE)
    assert len(rho_routes) >= 1
    rho_ferry = [r for r in rho_routes if any(l.mode == "ferry" for l in r.outbound_legs)]
    assert len(rho_ferry) >= 1


def test_bot_formatter_multimodal_icons(sample_window):
    """
    Formatter içinde leg modlarına göre doğru emojiler gösterilmeli:
    - ferry -> ⛴️
    - bus / night_bus -> 🚌
    - train / night_train -> 🚆
    - flight -> ✈️
    """
    out_legs = [
        TransportLeg(
            mode="flight",
            carrier="THY",
            origin="IST",
            destination="ICN",
            departure_str="28.10 01:45",
            arrival_str="28.10 16:55",
            price_eur_per_person=200.0,
        ),
        TransportLeg(
            mode="bus",
            carrier="KoBUS",
            origin="ICN",
            destination="PUS",
            departure_str="28.10 18:00",
            arrival_str="28.10 21:30",
            price_eur_per_person=17.0,
        ),
        TransportLeg(
            mode="ferry",
            carrier="Camellia Line",
            origin="PUS",
            destination="FUK",
            departure_str="28.10 22:30",
            arrival_str="29.10 07:30",
            price_eur_per_person=52.0,
            saves_accommodation_night=True,
        ),
    ]
    in_legs = [
        TransportLeg(
            mode="ferry",
            carrier="Camellia Line",
            origin="FUK",
            destination="PUS",
            departure_str="01.11 11:30",
            arrival_str="01.11 18:00",
            price_eur_per_person=52.0,
        ),
        TransportLeg(
            mode="night_train",
            carrier="KTX Gece Treni",
            origin="PUS",
            destination="ICN",
            departure_str="01.11 20:00",
            arrival_str="02.11 00:30",
            price_eur_per_person=25.0,
        ),
        TransportLeg(
            mode="flight",
            carrier="THY",
            origin="ICN",
            destination="IST",
            departure_str="02.11 02:00",
            arrival_str="02.11 08:30",
            price_eur_per_person=200.0,
        ),
    ]

    route = RouteOption(
        strategy_name="Kore-Japonya Feribot Köprüsü",
        outbound_legs=out_legs,
        inbound_legs=in_legs,
        is_border_hack=False,
        max_stops=1,
    )
    stay = StayOption(
        provider="Booking.com",
        title="Fukuoka Central Hotel",
        stay_type="private_hotel_8plus",
        city="Fukuoka",
        rating=8.6,
        price_per_night_total_eur=45.0,
        nights_charged=3,
        booking_url="https://booking.com/example",
    )
    country = CountryRule(
        code="JP",
        name_tr="Japonya",
        main_cities=["FUK", "KIX", "NRT"],
        solo_visa=VisaCategory.VISA_FREE,
        solo_visa_fee_eur=0.0,
        solo_min_lead_days=0,
        couple_visa=VisaCategory.VISA_FREE,
        couple_visa_fee_eur=0.0,
        couple_min_lead_days=0,
        visa_group="NONE",
        typical_package_Baseline_eur=850.0,
    )

    pkg = DealPackage(
        mode=TravelMode.SOLO,
        country=country,
        city_code="FUK",
        city_name_tr="Fukuoka",
        window=sample_window,
        route=route,
        stay=stay,
        passengers=1,
        discount_vs_baseline_pct=40,
    )

    msg = format_deal_telegram_message(pkg)
    assert "⛴️" in msg
    assert "🚌" in msg
    assert "🚆" in msg
    assert "✈️" in msg
    assert "Camellia Line" in msg
    assert "KoBUS" in msg


def test_direct_flights_parser_parses_both_payload_buckets():
    """
    _parse_all_flight_buckets HTML içindeki hem payload[2][0] ('Best flights')
    hem de payload[3][0] ('Other flights') biletlerini eksiksiz parse etmeli.
    """
    import json
    flight_item_1 = [["type", ["AJet"], [[None, None, None, "SAW", "Sabiha", "FCO", "Rome", None, [10, 30], None, [12, 45], 135, None, None, None, None, None, "320", None, None, [2026, 10, 28], [2026, 10, 28]]]], [[None, 55]]]
    flight_item_2 = [["type", ["Pegasus"], [[None, None, None, "SAW", "Sabiha", "FCO", "Rome", None, [14, 0], None, [16, 15], 135, None, None, None, None, None, "320", None, None, [2026, 10, 28], [2026, 10, 28]]]], [[None, 75]]]

    payload = [None, None, [[flight_item_1]], [[flight_item_2]], None, None, None, [None, [[["STAR", "Star Alliance"]], [["PC", "Pegasus"]]]]]
    data_str = json.dumps(payload)
    html_sample = f'<html><body><script class="ds:1">/* data:{data_str},</script></body></html>'

    results = _parse_all_flight_buckets(html_sample)
    assert results is not None
    assert len(results) == 2
    prices = [f.price for f in results]
    assert 55 in prices  # From payload[2][0]
    assert 75 in prices  # From payload[3][0]


@pytest.mark.asyncio
async def test_direct_flights_long_haul_round_trip_cheaper_selected(sample_window):
    """
    Uzun menzilli tam hizmet destinasyonlarında (NRT, ICN vb.) gidiş-dönüş (round-trip)
    biletinin iki tek yönden daha ucuz olduğu durumda round-trip seçilmeli ve 50/50 bölünmeli.
    """
    from unittest.mock import patch, MagicMock
    from transport.direct_flights import DirectFlightScanner, _LIVE_FLIGHT_CACHE

    _LIVE_FLIGHT_CACHE.clear()
    scanner = DirectFlightScanner()

    class MockFlight:
        def __init__(self, price: float, airline: str):
            self.price = price
            self.airlines = [airline]
            flight_obj = MagicMock()
            flight_obj.departure.date = (2026, 10, 28)
            flight_obj.departure.time = (14, 0)
            flight_obj.arrival.date = (2026, 10, 28)
            flight_obj.arrival.time = (22, 0)
            flight_obj.from_airport.code = "IST"
            flight_obj.to_airport.code = "NRT"
            self.flights = [flight_obj]

    with patch("fast_flights.create_query") as mock_cq, \
         patch("fast_flights.get_flights") as mock_gf:

        def cq_impl(flights, trip="one-way", **kwargs):
            query = MagicMock()
            query.flights = flights
            query.trip = trip
            return query
        mock_cq.side_effect = cq_impl

        def gf_impl(query):
            if getattr(query, "trip", "") == "round-trip":
                # Full service round-trip is 597€
                return [MockFlight(597.0, "ANA")]
            else:
                # Two one-ways are 600€ + 570€ = 1170€
                return [MockFlight(600.0, "ANA")]
        mock_gf.side_effect = gf_impl

        routes = await scanner._query_keyless_google_or_kiwi(sample_window, "NRT", origin_preference="IST")

    assert len(routes) == 1
    best_route = routes[0]
    # Round-trip (597€) must be chosen over two one-ways (1170€)
    assert best_route.roundtrip_price_per_person_eur == 597.0
    # Split 50/50 across legs
    assert best_route.outbound_legs[0].price_eur_per_person == 298.50
    assert best_route.inbound_legs[0].price_eur_per_person == 298.50
    assert "ANA" in best_route.strategy_name

