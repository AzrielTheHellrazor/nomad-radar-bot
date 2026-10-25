from datetime import date, datetime
from calendar_visa.holidays_tr import HolidayWindowCalculator


def test_october_28_29_bridge_holiday_window():
    """
    Kullanıcının verdiği örnek:
    22 Ekim 2026'dayız -> Haftaya 29 Ekim (Perşembe) Cumhuriyet Bayramı, 28 Ekim (Çarşamba) öğleden sonra yarım gün tatil.
    28 Ekim 13:00'ten sonra çıkıp 30 Ekim Cuma'yı (1 gün izin) bağlayıp 1 Kasım Pazar dönünce
    sadece 1.0 - 1.5 gün izinle toplam 4.5 - 5 gün tatil yapılmış oluyor!
    """
    calc = HolidayWindowCalculator()
    windows = calc.get_upcoming_windows(reference_date=date(2026, 10, 22), days_ahead=30)

    oct29_windows = [w for w in windows if "29 Ekim" in w.title]
    assert len(oct29_windows) >= 1

    bridge_win = oct29_windows[0]
    assert bridge_win.is_bridge_holiday is True
    assert bridge_win.start_dt == datetime(2026, 10, 28, 13, 0)
    assert bridge_win.end_dt == datetime(2026, 11, 1, 23, 59)
    assert bridge_win.total_days == 4.5
    assert bridge_win.leave_days_required == 1.0  # 28 Ekim öğleden sonra zaten resmi tatil, sadece 30 Ekim Cuma izin!
    assert bridge_win.nights == 4


def test_weekend_and_new_year_bridge_windows():
    calc = HolidayWindowCalculator()
    windows = calc.get_upcoming_windows(reference_date=date(2026, 10, 22), days_ahead=90)

    # Standart haftasonu kaçamakları da olmalı (Cuma 19:00 -> Pazar 23:59)
    weekend_windows = [w for w in windows if w.is_weekend_only]
    assert len(weekend_windows) >= 2
    assert weekend_windows[0].leave_days_required == 0.0

    # 1 Ocak 2027 (Cuma) Yılbaşı tatili (Perşembe akşam 31 Aralık 19:00 -> 3 Ocak Pazar = 0 izinle 3 gün!)
    ny_windows = [w for w in windows if "Yılbaşı" in w.title or "1 Ocak" in w.title]
    assert len(ny_windows) >= 1


def test_two_week_long_haul_holiday_bridges():
    """
    2 haftalık (~15-16 gece) uzun rota tatil köprüleri (Japonya, Güney Kore vb. için) testi:
    - 2027 Ramazan Bayramı 2 Haftalık Uzak Rota Köprüsü (16 gece, 6.5 gün izinle 16 gün)
    - 2027 Post-Golden Week + Kurban Bayramı 2 Haftalık Uzak Rota Köprüsü (15 gece, 6 gün izinle 16 gün)
    """
    calc = HolidayWindowCalculator()
    windows = calc.get_upcoming_windows(reference_date=date(2027, 2, 15), days_ahead=120)

    long_haul_windows = [w for w in windows if w.is_bridge_holiday and w.nights in (15, 16)]
    assert len(long_haul_windows) == 2

    ramazan_long = next((w for w in long_haul_windows if "Ramazan" in w.title), None)
    assert ramazan_long is not None
    assert ramazan_long.start_dt == datetime(2027, 3, 5, 19, 0)
    assert ramazan_long.end_dt == datetime(2027, 3, 21, 23, 59)
    assert ramazan_long.total_days == 16.0
    assert ramazan_long.leave_days_required == 6.5
    assert ramazan_long.nights == 16
    assert ramazan_long.is_bridge_holiday is True

    kurban_long = next((w for w in long_haul_windows if "Kurban" in w.title), None)
    assert kurban_long is not None
    assert kurban_long.start_dt == datetime(2027, 5, 8, 10, 0)
    assert kurban_long.end_dt == datetime(2027, 5, 23, 23, 59)
    assert kurban_long.total_days == 16.0
    assert kurban_long.leave_days_required == 6.0
    assert kurban_long.nights == 15
    assert kurban_long.is_bridge_holiday is True

