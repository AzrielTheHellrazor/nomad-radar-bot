# NomadRadar Dual-Mode Smart Travel Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dual-mode (`Solo / Yeşil Pasaport` and `Couple / Yeşil + Bordo Pasaport`) Telegram bot that detects Turkish holidays, half-days (e.g., Oct 28 afternoon), bridge-leave windows, weekend getaways, cheap multi-modal transport (direct flights + Sofia/Thessaloniki overland border-hack + Ryanair/WizzAir + FlixBus/train), free/cheap accommodation (night transit, house-sitting, Couchsurfing, 8.0+ hostels, or 8.0+ private hotels/Airbnbs for couples), and uses Gemini AI to evaluate and notify the user on Telegram.

**Architecture:** Modular async Python application with isolated domain packages (`calendar_visa`, `transport`, `accommodation`, `intelligence`, `bot`), SQLite persistence for user preferences/visas/deduplication, APScheduler for periodic scanning, and `python-telegram-bot` for interactive Telegram control.

**Tech Stack:** Python 3.11+, `python-telegram-bot` v21+, `httpx`, `feedparser`, `beautifulsoup4`, `google-genai`, `APScheduler`, `SQLite3`, `pytest`, `pytest-asyncio`.

## Global Constraints
- Must use `.venv/bin/python` and `.venv/bin/pip` for all Python execution and dependency management.
- Must support two distinct modes (`TravelMode.SOLO` and `TravelMode.COUPLE`, plus `BOTH` for simultaneous scanning).
- In `SOLO` mode: 1 adult, Green Passport (visa-free Schengen/Balkans/etc., or visa-required countries if lead time >= 45 days with visa fee added), overland Balkan border-hack (`IST -> SOF/SKG/OTP` + low-cost carrier) enabled, free stays (0€ night transit, TrustedHousesitters, Couchsurfing, HomeExchange) and 8.0+ Hostels enabled.
- In `COUPLE` mode: 2 adults (1 Green + 1 Burgundy passport), only visa-free / express-visa-on-arrival countries for Burgundy passport unless the partner holds a valid visa in DB (`/cift_vize_ekle`), no overland night-bus border hacks (direct flights or max 1 comfortable connection), work-hours friendly departure times, no hostels/free stays (only 8.0+ private hotel rooms or entire-place Airbnbs).

---

### Task 1: Core Data Models (`models.py`), Config (`config.py`) & SQLite Database (`database.py`)

**Files:**
- Create: `models.py`
- Create: `config.py`
- Create: `database.py`
- Test: `tests/test_database_and_models.py`

**Interfaces:**
- Produces: `TravelMode`, `VisaCategory`, `CountryRule`, `TravelWindow`, `TransportLeg`, `RouteOption`, `StayOption`, `DealPackage`, `UserSettings`, `Database`

- [ ] **Step 1: Write the failing test in `tests/test_database_and_models.py`**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `models.py`, `config.py`, and `database.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 2: Turkish Holiday, Half-Day (28 Oct / Arefe) & Bridge-Leave Calculator (`calendar_visa/holidays_tr.py`)

**Files:**
- Create: `calendar_visa/__init__.py`
- Create: `calendar_visa/holidays_tr.py`
- Test: `tests/test_holidays.py`

**Interfaces:**
- Consumes: `TravelWindow` from `models.py`
- Produces: `HolidayWindowCalculator.get_upcoming_windows(reference_date, days_ahead, include_weekends, include_weekday_deals)`

- [ ] **Step 1: Write the failing test in `tests/test_holidays.py` verifying Oct 28 afternoon (13:00) -> Nov 1 bridge window (1.5 leave days for 4.5 total days off)**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `calendar_visa/holidays_tr.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 3: Dual-Mode Visa & Cost Engine (`calendar_visa/visa_matrix.py`)

**Files:**
- Create: `calendar_visa/visa_matrix.py`
- Test: `tests/test_visa_matrix.py`

**Interfaces:**
- Consumes: `TravelMode`, `VisaCategory`, `CountryRule` from `models.py`
- Produces: `VisaEngine.evaluate_destination(country_code, mode, days_until_trip, solo_visas, couple_visas)`

- [ ] **Step 1: Write the failing test in `tests/test_visa_matrix.py` for Green Passport vs Couple (Green + Burgundy) rules and visa fee calculations**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `calendar_visa/visa_matrix.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 4: Multi-Modal Transport Engine (`transport/`)

**Files:**
- Create: `transport/__init__.py`
- Create: `transport/direct_flights.py`
- Create: `transport/border_hop.py`
- Create: `transport/euro_hop.py`
- Create: `transport/aggregator.py`
- Test: `tests/test_transport.py`

**Interfaces:**
- Consumes: `TravelWindow`, `TravelMode`, `RouteOption`, `TransportLeg` from `models.py`
- Produces: `TransportAggregator.find_best_routes(window, destination_code, mode)`

- [ ] **Step 1: Write the failing test in `tests/test_transport.py` testing Solo border-hop (Istanbul -> Sofia bus/train + Ryanair) vs Couple direct flights**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `transport/` modules**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 5: Dual-Mode Accommodation Engine (`accommodation/`)

**Files:**
- Create: `accommodation/__init__.py`
- Create: `accommodation/free_stays.py`
- Create: `accommodation/paid_stays.py`
- Create: `accommodation/aggregator.py`
- Test: `tests/test_accommodation.py`

**Interfaces:**
- Consumes: `TravelWindow`, `TravelMode`, `RouteOption`, `StayOption` from `models.py`
- Produces: `AccommodationAggregator.find_best_stays(window, destination_code, mode, route)`

- [ ] **Step 1: Write the failing test in `tests/test_accommodation.py` verifying Solo gets 0€ night-transit reduction + house-sitting/Couchsurfing/Hostel 8.0+ while Couple gets ONLY 8.0+ private Hotel/Airbnb deals**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `accommodation/` modules**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 6: Campaign Radar, Deal Scorer & Gemini AI Advisor (`intelligence/`)

**Files:**
- Create: `intelligence/__init__.py`
- Create: `intelligence/campaign_radar.py`
- Create: `intelligence/deal_scorer.py`
- Create: `intelligence/gemini_advisor.py`
- Test: `tests/test_intelligence.py`

**Interfaces:**
- Consumes: `TravelWindow`, `RouteOption`, `StayOption`, `DealPackage`, `TravelMode` from `models.py`
- Produces: `DealScorer.build_and_score_package(...)`, `CampaignRadar.fetch_latest_campaigns()`, `GeminiAdvisor.explain_deal(deal)`

- [ ] **Step 1: Write the failing test in `tests/test_intelligence.py` for total package cost (including visa fees and 2x passenger scaling in Couple Mode) and Gemini advisor fallback/formatting**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `intelligence/` modules**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 7: Telegram Bot, Scheduler & Main Entrypoint (`bot/`, `main.py`)

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/formatter.py`
- Create: `bot/telegram_bot.py`
- Create: `bot/scheduler.py`
- Create: `main.py`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`
- Test: `tests/test_bot_flow.py`

**Interfaces:**
- Consumes: All domain modules
- Produces: End-to-end Telegram bot and CLI scan runner

- [ ] **Step 1: Write the failing test in `tests/test_bot_flow.py` testing end-to-end scan & Telegram message formatting for both Solo (Portugal Oct 28-Nov 1) and Couple (Montenegro/Balkans/Greek Islands) modes**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `bot/`, `main.py`, `.env.example`, `Dockerfile`, `docker-compose.yml`, and `README.md`**
- [ ] **Step 4: Run full test suite (`pytest -v`) and verify all tests pass**
- [ ] **Step 5: Commit**
