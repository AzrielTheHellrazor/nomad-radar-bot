from typing import List
from calendar_visa.visa_matrix import CITY_NAMES_TR
from models import StayOption, TravelWindow


class FreeStayFinder:
    """
    SOLO MOD BEDAVA (0€) KONAKLAMA RADARI:
    - TrustedHousesitters / Nomador (Ev & Evcil Hayvan Bakımı karşılığı lüks evlerde 0€ konaklama)
    - Couchsurfing / BeWelcome / Trustroots (Yerel ev sahiplerinde 0€ misafir olma)
    - HomeExchange / Kindred (Ev takası / puanla 0€ konaklama)
    """

    def find_free_options(
        self, window: TravelWindow, city_code: str, nights_needed: int
    ) -> List[StayOption]:
        city_tr = CITY_NAMES_TR.get(city_code.upper(), city_code.upper())
        checkin = window.start_dt.strftime("%Y-%m-%d")
        checkout = window.end_dt.strftime("%Y-%m-%d")

        return [
            StayOption(
                provider="TrustedHousesitters / Nomador",
                title=f"{city_tr} Merkezde Ev & Kedi Bakımı Karşılığı Tam Daire (0€)",
                stay_type="free_housesit",
                city=city_tr,
                rating=9.5,
                price_per_night_total_eur=0.0,
                nights_charged=nights_needed,
                discount_pct=100,
                is_free_stay=True,
                booking_url=f"https://www.trustedhousesitters.com/house-and-pet-sitting-assignments/",
            ),
            StayOption(
                provider="Couchsurfing / BeWelcome",
                title=f"{city_tr} Doğrulanmış (Verified) Ev Sahipleri & Haftasonu Buluşması (0€)",
                stay_type="free_couch",
                city=city_tr,
                rating=9.0,
                price_per_night_total_eur=0.0,
                nights_charged=nights_needed,
                discount_pct=100,
                is_free_stay=True,
                booking_url=f"https://www.couchsurfing.com/",
            ),
            StayOption(
                provider="HomeExchange / PeopleLikeUs",
                title=f"{city_tr} GuestPoints ile Ücretsiz Ev Değişimi ({checkin} - {checkout})",
                stay_type="free_homeexchange",
                city=city_tr,
                rating=9.2,
                price_per_night_total_eur=0.0,
                nights_charged=nights_needed,
                discount_pct=100,
                is_free_stay=True,
                booking_url="https://www.homeexchange.com/",
            ),
        ]
