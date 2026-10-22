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
