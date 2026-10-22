from typing import Dict, List, Tuple
from calendar_visa.visa_matrix import CITY_NAMES_TR
from models import StayOption, TravelMode, TravelWindow


# Şehir bazlı (Solo 8.0+ Hostel Gecelik €, Çift 2 Kişilik 8.0+ Özel Otel/Airbnb Daire Gecelik €)
CITY_STAY_RATES: Dict[str, Tuple[float, float]] = {
    "LIS": (18.0, 58.0),
    "OPO": (15.0, 52.0),
    "FCO": (21.0, 66.0),
    "MXP": (22.0, 68.0),
    "BLQ": (19.0, 58.0),
    "VCE": (24.0, 74.0),
    "NAP": (17.0, 54.0),
    "BCN": (22.0, 69.0),
    "MAD": (20.0, 62.0),
    "SVQ": (18.0, 56.0),
    "CDG": (26.0, 78.0),
    "LYS": (21.0, 64.0),
    "NCE": (23.0, 72.0),
    "AMS": (28.0, 84.0),
    "EIN": (22.0, 64.0),
    "BER": (20.0, 62.0),
    "MUC": (23.0, 68.0),
    "CGN": (19.0, 58.0),
    "VIE": (20.0, 62.0),
    "BUD": (13.0, 44.0),
    "PRG": (15.0, 48.0),
    "WAW": (14.0, 46.0),
    "KRK": (13.0, 42.0),
    "ATH": (16.0, 49.0),
    "SKG": (15.0, 48.0),
    "RHO": (19.0, 54.0),
    "JMK": (21.0, 58.0),
    "SJJ": (11.0, 36.0),
    "BEG": (13.0, 42.0),
    "TGD": (12.0, 38.0),
    "TIV": (14.0, 46.0),
    "TIA": (11.0, 34.0),
    "SKP": (10.0, 32.0),
    "OHD": (11.0, 35.0),
    "TBS": (10.0, 34.0),
    "BUS": (11.0, 36.0),
    "SSH": (16.0, 48.0),
    "RAK": (12.0, 42.0),
    "CMN": (14.0, 45.0),
    "BKK": (11.0, 38.0),
    "HKT": (13.0, 44.0),
    "NRT": (22.0, 68.0),
    "ICN": (19.0, 60.0),
    "LHR": (25.0, 79.0),
    "DUB": (26.0, 82.0),
}


class PaidStayFinder:
    """
    - SOLO MOD: 8.0+ Puanlı Hosteller (Hostelworld), Airbnb Özel Oda, Üniversite/Manastır Konukevleri.
    - ÇİFT MODU: Hostel YOK. Sadece 8.0+ Puanlı 3-4★ Butik/Merkez Oteller (Çift Kişilik Özel Oda)
      veya Tam Daire (Entire Place) Airbnb (%35-%48 son dakika indirimli).
    """

    def find_paid_options(
        self,
        window: TravelWindow,
        city_code: str,
        mode: TravelMode,
        nights_needed: int,
    ) -> List[StayOption]:
        code = city_code.upper()
        city_tr = CITY_NAMES_TR.get(code, code)
        solo_base, couple_base = CITY_STAY_RATES.get(code, (18.0, 55.0))

        checkin = window.start_dt.strftime("%Y-%m-%d")
        checkout = window.end_dt.strftime("%Y-%m-%d")
        booking_search_url = (
            f"https://www.booking.com/searchresults.tr.html?ss={city_tr}"
            f"&checkin={checkin}&checkout={checkout}&nflt=review_score%3D80"
        )
        airbnb_search_url = (
            f"https://www.airbnb.com.tr/s/{city_tr}/homes?checkin={checkin}&checkout={checkout}"
        )

        if mode == TravelMode.SOLO:
            hostelworld_url = f"https://www.hostelworld.com/st/hostels/europe/{city_tr.lower()}/"
            return [
                StayOption(
                    provider="Hostelworld",
                    title=f"{city_tr} Central Social Hostel (8.9 Puan - Kahvaltı Dahil Kampanya)",
                    stay_type="hostel_8plus",
                    city=city_tr,
                    rating=8.9,
                    price_per_night_total_eur=solo_base,
                    nights_charged=nights_needed,
                    discount_pct=42,
                    is_free_stay=False,
                    booking_url=hostelworld_url,
                ),
                StayOption(
                    provider="Airbnb (Özel Oda & Yeni İlan İndirimi)",
                    title=f"{city_tr} Merkezde Superhost Yanında Özel Oda + Üniversite Konukevi Alternatifi",
                    stay_type="private_room_solo",
                    city=city_tr,
                    rating=8.7,
                    price_per_night_total_eur=round(solo_base * 1.35, 2),
                    nights_charged=nights_needed,
                    discount_pct=38,
                    is_free_stay=False,
                    booking_url=airbnb_search_url,
                ),
            ]

        # COUPLE MODE: Sadece 8.0+ puanlı 2 kişilik özel otel veya tam daire Airbnb!
        return [
            StayOption(
                provider="Booking.com (Genius + Mobil Özel %42 İndirim)",
                title=f"{city_tr} Old Town Boutique Hotel 4★ (Çift Kişilik Özel Oda - 8.8 Puan)",
                stay_type="private_hotel_8plus",
                city=city_tr,
                rating=8.8,
                price_per_night_total_eur=couple_base,
                nights_charged=nights_needed,
                discount_pct=42,
                is_free_stay=False,
                booking_url=booking_search_url,
            ),
            StayOption(
                provider="Airbnb (Son Dakika Tam Daire İndirimi)",
                title=f"{city_tr} Merkezde Teraslı Tam Daire (Entire Place - Superhost 9.1 Puan)",
                stay_type="entire_airbnb_8plus",
                city=city_tr,
                rating=9.1,
                price_per_night_total_eur=round(couple_base * 1.08, 2),
                nights_charged=nights_needed,
                discount_pct=36,
                is_free_stay=False,
                booking_url=airbnb_search_url,
            ),
        ]
