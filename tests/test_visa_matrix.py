from models import TravelMode, VisaCategory
from calendar_visa.visa_matrix import VisaEngine


def test_solo_green_passport_visa_rules():
    engine = VisaEngine()

    # 1. Portekiz (Schengen) -> Yeşil Pasaporta VİZESİZ (0€), son dakika (6 gün sonra) bile gidilebilir!
    pt_eval = engine.evaluate_destination(
        country_code="PT",
        mode=TravelMode.SOLO,
        days_until_trip=6,
        solo_visas=[],
        couple_visas=[],
    )
    assert pt_eval["eligible"] is True
    assert pt_eval["visa_cost_eur"] == 0.0
    assert "Vizesiz" in pt_eval["visa_note"]

    # 2. İngiltere (GB) -> Yeşil Pasaporta VİZELİ (~135€).
    # Eğer seyahat 6 gün sonraysa ve İngiltere vizesi yoksa -> Randevu yetişmez, eligible=False!
    gb_short = engine.evaluate_destination(
        country_code="GB",
        mode=TravelMode.SOLO,
        days_until_trip=6,
        solo_visas=[],
        couple_visas=[],
    )
    assert gb_short["eligible"] is False

    # Ama seyahat 60 gün sonraysa -> Vize randevusu alınabilir, 135€ vize ücreti maliyete eklenir!
    gb_far = engine.evaluate_destination(
        country_code="GB",
        mode=TravelMode.SOLO,
        days_until_trip=60,
        solo_visas=[],
        couple_visas=[],
    )
    assert gb_far["eligible"] is True
    assert gb_far["visa_cost_eur"] == 135.0
    assert "135" in gb_far["visa_note"]

    # Eğer kullanıcının halihazırda UK vizesi varsa -> 6 gün sonra da gidebilir ve vize maliyeti 0€!
    gb_has_visa = engine.evaluate_destination(
        country_code="GB",
        mode=TravelMode.SOLO,
        days_until_trip=6,
        solo_visas=["UK"],
        couple_visas=[],
    )
    assert gb_has_visa["eligible"] is True
    assert gb_has_visa["visa_cost_eur"] == 0.0


def test_couple_green_plus_burgundy_visa_rules():
    engine = VisaEngine()

    # 1. Karadağ (ME) veya Sırbistan (RS) -> Hem Yeşil hem Bordo pasaporta VİZESİZ (0€)!
    me_eval = engine.evaluate_destination(
        country_code="ME",
        mode=TravelMode.COUPLE,
        days_until_trip=6,
        solo_visas=[],
        couple_visas=[],
    )
    assert me_eval["eligible"] is True
    assert me_eval["visa_cost_eur"] == 0.0

    # 2. Yunan Adaları (GR_ISLANDS) -> Yeşil pasaporta 0€, Bordo pasaporta Kapıda Ekspres Vize (80€) -> Toplam 80€
    gr_eval = engine.evaluate_destination(
        country_code="GR_ISLANDS",
        mode=TravelMode.COUPLE,
        days_until_trip=10,
        solo_visas=[],
        couple_visas=[],
    )
    assert gr_eval["eligible"] is True
    assert gr_eval["visa_cost_eur"] == 80.0

    # 3. Portekiz / İtalya (Schengen) -> Çift Modunda kız arkadaşın Schengen vizesi yoksa varsayılan olarak "vize sorunu yaşamayacağımız" modda elenir
    pt_couple_no_visa = engine.evaluate_destination(
        country_code="PT",
        mode=TravelMode.COUPLE,
        days_until_trip=10,
        solo_visas=[],
        couple_visas=[],
    )
    assert pt_couple_no_visa["eligible"] is False

    # Ama kız arkadaşın Schengen vizesi varsa (/cift_vize_ekle SCHENGEN) -> 0€ ek vize maliyetiyle Çift Modunda da açılır!
    pt_couple_with_visa = engine.evaluate_destination(
        country_code="PT",
        mode=TravelMode.COUPLE,
        days_until_trip=10,
        solo_visas=[],
        couple_visas=["SCHENGEN"],
    )
    assert pt_couple_with_visa["eligible"] is True
    assert pt_couple_with_visa["visa_cost_eur"] == 0.0


def test_expanded_matrix_counts_and_destinations():
    from calendar_visa.visa_matrix import CITY_NAMES_TR
    engine = VisaEngine()

    assert len(engine._countries) >= 32
    assert len(CITY_NAMES_TR) >= 60

    required_countries = {"BG", "RO", "HR", "CH", "BE", "DK", "SE", "KR"}
    for code in required_countries:
        country = engine.get_country(code)
        assert country is not None, f"Missing country: {code}"
        assert len(country.main_cities) >= 2, f"Expected at least 2 cities for {code}"
        for city in country.main_cities:
            assert city in CITY_NAMES_TR, f"City {city} missing from CITY_NAMES_TR"

    # Regional hub expansions
    it = engine.get_country("IT")
    assert "BGY" in it.main_cities
    es = engine.get_country("ES")
    assert "AGP" in es.main_cities
    fr = engine.get_country("FR")
    assert "ORY" in fr.main_cities
    de = engine.get_country("DE")
    assert "DUS" in de.main_cities and "STR" in de.main_cities
    gb = engine.get_country("GB")
    assert "STN" in gb.main_cities


def test_new_countries_visa_evaluation():
    engine = VisaEngine()

    # Solo mode: all Schengen (BG, RO, HR, CH, BE, DK, SE) and KR are visa-free
    for code in ["BG", "RO", "HR", "CH", "BE", "DK", "SE", "KR"]:
        res = engine.evaluate_destination(
            country_code=code,
            mode=TravelMode.SOLO,
            days_until_trip=5,
            solo_visas=[],
            couple_visas=[],
        )
        assert res["eligible"] is True, f"Solo {code} should be eligible"
        assert res["visa_cost_eur"] == 0.0

    # Couple mode: Schengen requires Schengen visa for partner
    for code in ["BG", "RO", "HR", "CH", "BE", "DK", "SE"]:
        no_visa = engine.evaluate_destination(
            country_code=code,
            mode=TravelMode.COUPLE,
            days_until_trip=5,
            solo_visas=[],
            couple_visas=[],
        )
        assert no_visa["eligible"] is False, f"Couple {code} without visa should not be eligible"

        with_visa = engine.evaluate_destination(
            country_code=code,
            mode=TravelMode.COUPLE,
            days_until_trip=5,
            solo_visas=[],
            couple_visas=["SCHENGEN"],
        )
        assert with_visa["eligible"] is True, f"Couple {code} with SCHENGEN visa should be eligible"
        assert with_visa["visa_cost_eur"] == 0.0

    # Couple mode: KR is visa-free for both
    kr_couple = engine.evaluate_destination(
        country_code="KR",
        mode=TravelMode.COUPLE,
        days_until_trip=5,
        solo_visas=[],
        couple_visas=[],
    )
    assert kr_couple["eligible"] is True
    assert kr_couple["visa_cost_eur"] == 0.0

