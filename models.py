from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import List, Optional


class TravelMode(str, Enum):
    SOLO = "solo"          # 1 Kişi: Yeşil Pasaport, Balkan Hack + Bedava/Hostel Konaklama
    COUPLE = "couple"      # 2 Kişi: Yeşil + Bordo Pasaport, Vizesiz/Kapıda Vize, Direkt Uçuş + 8.0+ Özel Otel/Airbnb
    BOTH = "both"          # Her iki modu da tarar ve etiketleyerek bildirir


class VisaCategory(str, Enum):
    VISA_FREE = "visa_free"              # Vizesiz (0€)
    VISA_ON_ARRIVAL_OR_E_VISA = "e_visa" # Kapıda Vize veya Kolay E-Vize (Ücret eklenir)
    VISA_REQUIRED = "visa_required"      # Randevulu Vize (İleri tarih kontrolü + vize ücreti eklenir)


@dataclass
class CountryRule:
    code: str                            # ISO Ülke kodu, örn: "PT", "IT", "ME", "GR_ISLANDS", "GB"
    name_tr: str                         # Türkçe ad, örn: "Portekiz", "Karadağ"
    main_cities: List[str]               # Şehir/Havalimanı kodları, örn: ["LIS", "OPO"]
    solo_visa: VisaCategory              # Yeşil Pasaport vize durumu
    solo_visa_fee_eur: float             # Yeşil Pasaport vize ücreti (€)
    solo_min_lead_days: int              # Vize randevusu/işlemi için gereken minimum gün
    couple_visa: VisaCategory            # Bordo Pasaport (Çift modu) vize durumu
    couple_visa_fee_eur: float           # Çift toplam vize ücreti (Yeşil + Bordo toplam €)
    couple_min_lead_days: int            # Çift modu vize hazırlık süresi (gün)
    visa_group: str = "NONE"             # Örn: "SCHENGEN", "UK", "USA" (Kullanıcı vizesi varsa muafiyet için)
    typical_package_Baseline_eur: float = 420.0  # Kişi başı normal piyasa ortalaması (indirim % hesabı için)


@dataclass
class TravelWindow:
    title: str                           # Örn: "29 Ekim Cumhuriyet Bayramı Köprü Tatili"
    start_dt: datetime                   # Çıkış tarih/saati (örn. 2026-10-28 13:00)
    end_dt: datetime                     # Dönüş tarih/saati (örn. 2026-11-01 23:59)
    total_days: float                    # Toplam tatil süresi (örn. 4.5 gün)
    leave_days_required: float           # Harcanacak yıllık izin (örn. 1.0 veya 1.5 gün)
    nights: int                          # Konaklama gece sayısı (örn. 4 gece)
    is_bridge_holiday: bool = False      # Resmi tatil / köprü izin mi?
    is_weekend_only: bool = False        # Standart Cuma akşam - Pazar gece haftasonu mu?
    is_weekday_flash: bool = False       # Hafta içi ekstrem indirim penceresi mi?

    @property
    def efficiency_ratio(self) -> float:
        """Harcanan 1 gün izne karşılık kazanılan toplam tatil günü."""
        if self.leave_days_required <= 0:
            return self.total_days * 5.0
        return round(self.total_days / self.leave_days_required, 2)


@dataclass
class TransportLeg:
    mode: str                            # "flight", "night_bus", "night_train", "bus", "train", "ferry"
    carrier: str                         # Örn: "Ryanair", "Pegasus", "Sofya Ekspresi", "FlixBus"
    origin: str                          # Örn: "IST", "SOF", "LIS"
    destination: str                     # Örn: "SOF", "OPO", "LIS"
    departure_str: str                   # Örn: "28 Eki 14:30"
    arrival_str: str                     # Örn: "28 Eki 17:45"
    price_eur_per_person: float          # Kişi başı ücret (€)
    saves_accommodation_night: bool = False  # Gece otobüsü/treni ise 1 gece konaklama bedavaya gelir


@dataclass
class RouteOption:
    strategy_name: str                   # Örn: "Direkt Uçuş (IST -> LIS)" veya "Balkan Hack (Otobüsle Sofya + Ryanair)"
    outbound_legs: List[TransportLeg]
    inbound_legs: List[TransportLeg]
    is_border_hack: bool = False
    max_stops: int = 0
    booking_hint_url: str = ""

    @property
    def roundtrip_price_per_person_eur(self) -> float:
        out_cost = sum(leg.price_eur_per_person for leg in self.outbound_legs)
        in_cost = sum(leg.price_eur_per_person for leg in self.inbound_legs)
        return round(out_cost + in_cost, 2)

    @property
    def saved_nights_count(self) -> int:
        all_legs = self.outbound_legs + self.inbound_legs
        return sum(1 for leg in all_legs if leg.saves_accommodation_night)


@dataclass
class StayOption:
    provider: str                        # "TrustedHousesitters", "Couchsurfing", "Hostelworld", "Booking.com", "Airbnb"
    title: str                           # İlan / Otel adı
    stay_type: str                       # "free_housesit", "free_couch", "hostel_8plus", "private_hotel_8plus", "entire_airbnb"
    city: str
    rating: float                        # 8.0+ puan
    price_per_night_total_eur: float     # Oda/yatak gecelik toplam fiyat (Solo için 1 kişi, Çift için 2 kişilik oda)
    nights_charged: int                  # Gece yolculuğu düşüldükten sonra ödenen gece sayısı
    discount_pct: int = 0                # Son dakika / kampanya indirim yüzdesi
    is_free_stay: bool = False
    booking_url: str = ""

    @property
    def total_stay_cost_eur(self) -> float:
        return round(self.price_per_night_total_eur * self.nights_charged, 2)


@dataclass
class DealPackage:
    mode: TravelMode
    country: CountryRule
    city_code: str
    city_name_tr: str
    window: TravelWindow
    route: RouteOption
    stay: StayOption
    alternative_stays: List[StayOption] = field(default_factory=list)
    passengers: int = 1
    visa_cost_total_eur: float = 0.0
    visa_note: str = ""
    campaign_badge: Optional[str] = None
    discount_vs_baseline_pct: int = 0
    ai_commentary: str = ""

    @property
    def transport_total_eur(self) -> float:
        return round(self.route.roundtrip_price_per_person_eur * self.passengers, 2)

    @property
    def grand_total_eur(self) -> float:
        return round(self.transport_total_eur + self.stay.total_stay_cost_eur + self.visa_cost_total_eur, 2)

    @property
    def per_person_total_eur(self) -> float:
        return round(self.grand_total_eur / max(1, self.passengers), 2)

    @property
    def deal_key(self) -> str:
        return f"{self.mode.value.upper()}:{self.country.code}:{self.city_code}:{self.window.start_dt.strftime('%Y-%m-%d')}:{self.window.end_dt.strftime('%Y-%m-%d')}"


@dataclass
class UserSettings:
    chat_id: int
    active_mode: TravelMode = TravelMode.BOTH
    solo_max_budget_eur: float = 220.0
    couple_max_budget_eur: float = 550.0  # 2 Kişi toplam bütçe
    solo_watchlist: List[str] = field(default_factory=lambda: ["PT", "IT", "ES", "FR", "NL", "DE", "AT", "HU", "CZ", "PL", "GR", "BA", "RS", "ME", "GB"])
    couple_watchlist: List[str] = field(default_factory=lambda: ["ME", "RS", "BA", "AL", "MK", "GR_ISLANDS", "GE", "EG_SHARM", "MA", "TH", "JP"])
    solo_visas: List[str] = field(default_factory=list)      # Örn: ["UK", "USA"]
    couple_visas: List[str] = field(default_factory=list)    # Örn: ["SCHENGEN", "UK"] (Kız arkadaşınızın aldığı vizeler)
