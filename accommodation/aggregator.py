from typing import List
from accommodation.free_stays import FreeStayFinder
from accommodation.paid_stays import PaidStayFinder
from models import RouteOption, StayOption, TravelMode, TravelWindow


class AccommodationAggregator:
    """
    Ulaşım rotasına ve moda (Solo vs Çift) göre konaklama seçeneklerini birleştirir.
    - SOLO MOD:
      1. Eğer rotada gece otobüsü/treni (saves_accommodation_night=True) varsa
         ödenecek gece sayısını (nights_charged) otomatik düşürür!
      2. En uygun 8.0+ Hostel/Özel Oda seçeneklerini ve 0€ Bedava (TrustedHousesitters,
         Couchsurfing, HomeExchange) alternatiflerini birlikte döndürür.
    - ÇİFT MODU:
      1. Bedava konaklama ve Hostel ranzalarını tamamen hariç tutar.
      2. Sadece 8.0+ puanlı 2 kişilik özel otel ve tam daire Airbnb fırsatlarını döndürür.
    """

    def __init__(self) -> None:
        self.free_finder = FreeStayFinder()
        self.paid_finder = PaidStayFinder()

    def find_best_stays(
        self,
        window: TravelWindow,
        city_code: str,
        mode: TravelMode,
        route: RouteOption,
    ) -> List[StayOption]:
        if mode == TravelMode.SOLO:
            nights_needed = max(1, window.nights - route.saved_nights_count)
            paid = self.paid_finder.find_paid_options(
                window=window,
                city_code=city_code,
                mode=TravelMode.SOLO,
                nights_needed=nights_needed,
            )
            free = self.free_finder.find_free_options(
                window=window,
                city_code=city_code,
                nights_needed=nights_needed,
            )
            # İlk sırada gerçekçi bütçe hesabı için 8.0+ Hostel, hemen altında 0€ Bedava konaklamalar yer alır
            return paid + free

        # COUPLE MODE
        return self.paid_finder.find_paid_options(
            window=window,
            city_code=city_code,
            mode=TravelMode.COUPLE,
            nights_needed=window.nights,
        )
