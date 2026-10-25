from datetime import date, datetime, time, timedelta
from typing import List
from models import TravelWindow


class HolidayWindowCalculator:
    """
    Türkiye resmi tatillerini, yarım günleri (28 Ekim öğleden sonra, Arefe günleri),
    haftasonu ile birleştirilen 'Köprü İzin' pencerelerini ve haftasonu kaçamaklarını hesaplar.
    """

    def _curated_bridge_windows(self) -> List[TravelWindow]:
        """2026 - 2027 dönemi resmi tatil ve köprü izin pencereleri."""
        return [
            # 29 Ekim 2026 (Perşembe) + 28 Ekim (Çarşamba) Öğleden Sonra Yarım Gün
            # 28 Ekim 13:00 çıkış -> 30 Ekim Cuma (1 gün izin) -> 1 Kasım Pazar dönüş = 4.5 gün tatil!
            TravelWindow(
                title="29 Ekim Cumhuriyet Bayramı Köprü Tatili (Çarşamba Öğleden Sonra Çıkışlı)",
                start_dt=datetime(2026, 10, 28, 13, 0),
                end_dt=datetime(2026, 11, 1, 23, 59),
                total_days=4.5,
                leave_days_required=1.0,
                nights=4,
                is_bridge_holiday=True,
            ),
            # Alternatif: 28 Ekim 13:00 -> 29 Ekim 23:59 (0 izinle 1.5 gün) veya Cuma izin alamayanlar için
            # Yılbaşı 2027: 1 Ocak 2027 Cuma resmi tatil -> 31 Aralık Perşembe 19:00 çıkış -> 3 Ocak Pazar dönüş (0 izinle 3 tam gün)
            TravelWindow(
                title="1 Ocak 2027 Yılbaşı Tatili (0 Gün İzinle 3 Gün!)",
                start_dt=datetime(2026, 12, 31, 19, 0),
                end_dt=datetime(2027, 1, 3, 23, 59),
                total_days=3.0,
                leave_days_required=0.0,
                nights=3,
                is_bridge_holiday=True,
            ),
            # 2027 Ramazan Bayramı: Arefe 8 Mart 2027 Pazartesi (Yarım gün) + 9-10-11 Mart (Sal-Çar-Per)
            # Cuma 12 Mart (1 gün izin) + Pazartesi sabah (0.5 gün izin) = 1.5 gün izinle 5 Mart Cuma akşam -> 14 Mart Pazar (9 Gün Tatil!)
            TravelWindow(
                title="2027 Ramazan Bayramı Büyük Köprü Tatili (1.5 Gün İzinle 9 Gün!)",
                start_dt=datetime(2027, 3, 5, 19, 0),
                end_dt=datetime(2027, 3, 14, 23, 59),
                total_days=9.0,
                leave_days_required=1.5,
                nights=9,
                is_bridge_holiday=True,
            ),
            # 2027 Ramazan Bayramı 2 Haftalık Uzak Rota Köprüsü (Uzak rota / Japonya & Güney Kore vb. için)
            # 5 Mart Cuma 19:00 -> 21 Mart Pazar 23:59 (6.5 gün izinle 16 gün / 16 gece!)
            TravelWindow(
                title="2027 Ramazan Bayramı 2 Haftalık Uzak Rota Köprüsü (6.5 Gün İzinle 16 Gün!)",
                start_dt=datetime(2027, 3, 5, 19, 0),
                end_dt=datetime(2027, 3, 21, 23, 59),
                total_days=16.0,
                leave_days_required=6.5,
                nights=16,
                is_bridge_holiday=True,
            ),
            # 23 Nisan 2027 Cuma -> 22 Nisan Perşembe 19:00 çıkış -> 25 Nisan Pazar dönüş (0 izinle 3 gün!)
            TravelWindow(
                title="23 Nisan 2027 Ulusal Egemenlik Tatili (0 Gün İzinle 3 Gün!)",
                start_dt=datetime(2027, 4, 22, 19, 0),
                end_dt=datetime(2027, 4, 25, 23, 59),
                total_days=3.0,
                leave_days_required=0.0,
                nights=3,
                is_bridge_holiday=True,
            ),
            # 1 Mayıs 2027 Emek ve Dayanışma Günü Hafta Sonu
            TravelWindow(
                title="1 Mayıs 2027 Emek ve Dayanışma Günü Hafta Sonu",
                start_dt=datetime(2027, 4, 30, 19, 0),
                end_dt=datetime(2027, 5, 2, 23, 59),
                total_days=2.5,
                leave_days_required=0.0,
                nights=2,
                is_bridge_holiday=True,
            ),
            # 2027 Kurban Bayramı: Arefe 15 Mayıs Cumartesi, 16-19 Mayıs (Paz-Çar) -> Perşembe-Cuma 2 gün izinle 9 gün tatil
            TravelWindow(
                title="2027 Kurban Bayramı & 19 Mayıs Birleşik Tatili (2 Gün İzinle 9 Gün!)",
                start_dt=datetime(2027, 5, 14, 19, 0),
                end_dt=datetime(2027, 5, 23, 23, 59),
                total_days=9.0,
                leave_days_required=2.0,
                nights=9,
                is_bridge_holiday=True,
            ),
            # 2027 Post-Golden Week + Kurban Bayramı 2 Haftalık Uzak Rota Köprüsü (Uzak rota / Japonya & Güney Kore vb. için)
            # 8 Mayıs Cumartesi 10:00 -> 23 Mayıs Pazar 23:59 (6 gün izinle 16 gün / 15 gece!)
            TravelWindow(
                title="2027 Post-Golden Week + Kurban Bayramı 2 Haftalık Uzak Rota Köprüsü (6 Gün İzinle 16 Gün!)",
                start_dt=datetime(2027, 5, 8, 10, 0),
                end_dt=datetime(2027, 5, 23, 23, 59),
                total_days=16.0,
                leave_days_required=6.0,
                nights=15,
                is_bridge_holiday=True,
            ),
            # 15 Temmuz 2027 Perşembe -> Cuma 1 gün izinle 4 gün tatil
            TravelWindow(
                title="15 Temmuz 2027 Köprü Tatili (1 Gün İzinle 4 Gün!)",
                start_dt=datetime(2027, 7, 14, 19, 0),
                end_dt=datetime(2027, 7, 18, 23, 59),
                total_days=4.0,
                leave_days_required=1.0,
                nights=4,
                is_bridge_holiday=True,
            ),
            # 30 Ağustos 2027 Pazartesi -> 0 izinle 3 gün tatil
            TravelWindow(
                title="30 Ağustos 2027 Zafer Bayramı (0 Gün İzinle 3 Gün!)",
                start_dt=datetime(2027, 8, 27, 19, 0),
                end_dt=datetime(2027, 8, 30, 23, 59),
                total_days=3.0,
                leave_days_required=0.0,
                nights=3,
                is_bridge_holiday=True,
            ),
            # 29 Ekim 2027 Cuma + 28 Ekim Perşembe 13:00 yarım gün -> 0 izinle 3.5 gün tatil!
            TravelWindow(
                title="29 Ekim 2027 Cumhuriyet Bayramı (0 Gün İzinle 3.5 Gün!)",
                start_dt=datetime(2027, 10, 28, 13, 0),
                end_dt=datetime(2027, 10, 31, 23, 59),
                total_days=3.5,
                leave_days_required=0.0,
                nights=3,
                is_bridge_holiday=True,
            ),
        ]

    def get_upcoming_windows(
        self,
        reference_date: date | None = None,
        days_ahead: int = 60,
        include_weekends: bool = True,
        include_weekday_deals: bool = True,
    ) -> List[TravelWindow]:
        ref = reference_date or date.today()
        ref_dt = datetime.combine(ref, time(0, 0))
        horizon_dt = datetime.combine(ref + timedelta(days=days_ahead), time(23, 59))

        results: List[TravelWindow] = []

        # 1. Öncelik: Resmi Tatil & Köprü İzin Pencereleri
        for win in self._curated_bridge_windows():
            if ref_dt <= win.start_dt <= horizon_dt:
                results.append(win)

        # 2. Öncelik: Yaklaşan Haftasonu Kaçamakları (Cuma 19:00 -> Pazar 23:59, 0 gün izin)
        # ve Uzatılmış Hafta Sonu Kaçamakları (Cuma 19:00 -> Pazartesi 23:59, 1 gün izin)
        if include_weekends:
            cursor = ref
            weekend_count = 0
            standard_weekends: List[TravelWindow] = []
            extended_weekends: List[TravelWindow] = []
            while cursor <= ref + timedelta(days=min(days_ahead, 45)) and weekend_count < 4:
                # 4 = Friday
                if cursor.weekday() == 4:
                    fri_start = datetime.combine(cursor, time(19, 0))
                    sun_end = datetime.combine(cursor + timedelta(days=2), time(23, 59))
                    mon_end = datetime.combine(cursor + timedelta(days=3), time(23, 59))

                    # Standart haftasonu: Cuma 19:00 -> Pazar 23:59 (0 gün izin)
                    overlaps_std = any(
                        w.is_bridge_holiday and not (sun_end < w.start_dt or w.end_dt < fri_start)
                        for w in results
                    )
                    if not overlaps_std and fri_start >= ref_dt:
                        standard_weekends.append(
                            TravelWindow(
                                title=f"Haftasonu Kaçamağı ({cursor.strftime('%d.%m')} Cuma Akşam - Pazar)",
                                start_dt=fri_start,
                                end_dt=sun_end,
                                total_days=2.5,
                                leave_days_required=0.0,
                                nights=2,
                                is_weekend_only=True,
                            )
                        )
                        weekend_count += 1

                    # Uzatılmış haftasonu: Cuma 19:00 -> Pazartesi 23:59 (1 gün izin, 3 gece)
                    overlaps_ext = any(
                        w.is_bridge_holiday and not (mon_end < w.start_dt or w.end_dt < fri_start)
                        for w in results
                    )
                    if not overlaps_ext and fri_start >= ref_dt:
                        extended_weekends.append(
                            TravelWindow(
                                title=f"Uzatılmış Hafta Sonu ({cursor.strftime('%d.%m')} Cuma Akşam - Pazartesi)",
                                start_dt=fri_start,
                                end_dt=mon_end,
                                total_days=3.5,
                                leave_days_required=1.0,
                                nights=3,
                                is_weekend_only=True,
                            )
                        )
                cursor += timedelta(days=1)

            results.extend(standard_weekends)
            results.extend(extended_weekends)

        # 3. Öncelik: Hafta İçi Ekstrem Fırsat / Error-Fare Penceresi (Örn: Salı -> Perşembe 2 gece)
        if include_weekday_deals:
            cursor = ref + timedelta(days=10)
            while cursor.weekday() != 1:  # 1 = Tuesday
                cursor += timedelta(days=1)
            if datetime.combine(cursor, time(9, 0)) <= horizon_dt:
                results.append(
                    TravelWindow(
                        title=f"🔥 Hafta İçi Süper İndirim Penceresi ({cursor.strftime('%d.%m')} Salı - Perşembe)",
                        start_dt=datetime.combine(cursor, time(9, 0)),
                        end_dt=datetime.combine(cursor + timedelta(days=2), time(22, 0)),
                        total_days=3.0,
                        leave_days_required=3.0,
                        nights=2,
                        is_weekday_flash=True,
                    )
                )

        return results
