# NomadRadar: Akıllı Tatil, Köprü İzin ve Ucuz Seyahat Telegram Botu Tasarım Dokümanı

**Tarih:** 2026-10-22  
**Proje Dizini:** `/Users/goktus/nomad-radar-bot`  
**Mimari:** Modüler Python (`asyncio`, `python-telegram-bot`, `APScheduler`, `SQLite`, `Playwright`/`httpx`, `google-genai` Gemini SDK)

---

## 1. Amaç ve Kapsam

Kullanıcının Türkiye resmi tatillerini, yarım gün tatilleri (28 Ekim öğleden sonra, dini bayram arefeleri vb.), haftasonlarını ve 1-2 günlük "köprü izin" fırsatlarını otomatik analiz ederek; hem **Solo (Tek Kişi - Yeşil Pasaport - Maksimum Tasarruf/Macera)** hem de **Çift (2 Kişi - Yeşil + Bordo Pasaport - Vizesiz/Sorunsuz & Konforlu)** modlarında en ucuz ulaşım ve konaklama paketlerini yakalayıp Gemini AI yorumuyla Telegram üzerinden bildiren akıllı seyahat asistanı.

---

## 2. Çift Profilli (Dual-Mode) Çalışma Mantığı

Bot aynı anda veya seçime bağlı olarak (`/mod solo`, `/mod cift`, `/mod ikisi_de`) iki farklı seyahat profilini destekler:

### 🎒 Mod 1: Solo / Gezgin Modu (Tek Kişi - Yeşil Pasaport)
- **Yolcu Profili:** 1 Yetişkin, Türk Yeşil (Hususi) Pasaport sahibi.
- **Vize Kuralları:**
  - **Vizesiz (0€):** Tüm Schengen ülkeleri, Balkanlar, vizesiz Asya/Güney Amerika. Son dakika dahil tüm pencerelerde taranır.
  - **E-Vize / Kapıda Vize:** Ücret toplam maliyete eklenir.
  - **Randevulu Vize (İngiltere, ABD, İrlanda vb.):** Yalnızca seyahat tarihi vize randevu süresine (varsayılan >= 45 gün) yetiyorsa taranır ve vize ücreti (örn. İngiltere ~135€) toplam maliyete dahil edilir. Kullanıcının halihazırda vizesi varsa (`/vizelerim`) maliyet 0€ sayılır.
- **Ulaşım Stratejisi:**
  - `IST` / `SAW` direkt ve aktarmalı uçuşlar.
  - **Balkan Kara/Tren Sınır Hack'i:** İstanbul'dan gece otobüsü veya Sofya Ekspresi treni ile Sofya (`SOF`), Selanik (`SKG`) veya Bükreş'e (`OTP`) geçip oradan Ryanair / WizzAir / EasyJet ile 10€-29€'ya Avrupa'ya uçma kombinasyonları.
  - **Avrupa İçi Bağlantı:** İndikten sonra FlixBus / BlaBlaCar Bus / Tren ile komşu şehirlere geçiş.
- **Konaklama Stratejisi:**
  - **0€ (Bedava) Seçenekler:** Gece otobüsü/treni ile yolda konaklama (otel gün sayısından 1 gece düşer), TrustedHousesitters / Nomador (ev & evcil hayvan bakımı), Couchsurfing / BeWelcome, HomeExchange.
  - **Ultra-Ucuz Seçenekler:** Hostelworld (8.0+ puanlı hosteller), Airbnb özel oda, Booking son dakika fırsatları.

### 💑 Mod 2: Çift / Konfor Modu (Siz + Kız Arkadaşınız - Yeşil + Bordo Pasaport)
- **Yolcu Profili:** 2 Yetişkin (1 Yeşil Pasaport + 1 Bordo/Umuma Mahsus Pasaport), ikisi de hafta içi mesaili çalışıyor.
- **Vize Kuralları (Vize Sorunu Yaşanmayacak Ortak Küme):**
  - **Varsayılan Hedefler (Bordo Pasaporta Vizesiz veya Kolay Kapıda/E-Vize):**
    - **Avrupa / Balkanlar (Vizesiz - 0€):** Karadağ (Podgorica/Tivat), Sırbistan (Belgrad), Bosna-Hersek (Saraybosna), Arnavutluk (Tiran), Kuzey Makedonya (Üsküp/Ohrid), Kosova (Priştine).
    - **Yunan Adaları (Kapıda Ekspres Vize - 80€ Bordo / 0€ Yeşil):** Sakız (Chios), Midilli (Lesbos), Rodos, Kos, Samos, Simi.
    - **Yakın Coğrafya & Kuzey Afrika:** Gürcistan (Tiflis/Batum - Kimlikle/Vizesiz), KKTC (Ercan), Mısır (Şarm El-Şeyh vizesiz / Kahire-Hurgada kapıda vize 25$), Fas (Marakeş/Kazablanka - Vizesiz), Tunus (Vizesiz).
    - **Orta/Uzak Mesafe Vizesiz (Uzun Tatiller İçin):** Tayland, Japonya, Güney Kore (K-ETA), Brezilya, Kolombiya, Maldivler.
  - **Dinamik Vize Durumu:** Eğer kız arkadaşınız Schengen/İngiltere vizesi alırsa `/cift_vize_ekle schengen` komutuyla tüm Avrupa (İtalya, Portekiz, İspanya, Fransa vb.) Çift Modu'na da otomatik açılır.
- **Ulaşım Stratejisi (Az Aktarma & Konfor):**
  - **Yorucu sınır ötesi gece otobüsü hack'leri KAPALI.**
  - Sadece İstanbul (`IST` / `SAW`) çıkışlı **direkt uçuşlar** (veya uzak rotalarda maksimum 1 konforlu/kısa aktarma) ve Yunan adaları için direkt/kısa feribot bağlantıları.
  - **Mesai Saati Uyumu:** İki çalışan olduğu için hafta içi mesai bitimi (Cuma veya tatil arifesi 18:30/19:00 sonrası kalkış) veya resmi tatil sabahı çıkışlı, tatil sonu akşam/gece dönüşlü saatler seçilir.
- **Konaklama Stratejisi (Bedava/Hostel Yok - Özel & Konforlu):**
  - Hostel ranzası, Couchsurfing, ev/evcil hayvan bakımı **KAPALI**.
  - Sadece **2 kişilik özel konaklama**: En az **8.0+ puanlı** 3-4-5 yıldızlı Oteller, Butik Oteller veya **Tam Daire (Entire Place) Airbnb** fırsatları (kampanyalı veya son dakika %35+ indirimli olanlar).
  - Fiyatlar **2 Kişi Toplam Paket (2x Uçak + Çift Kişilik Oda + Varsa Bordo Kapıda Vize)** olarak hesaplanır.

---

## 3. Sistem Modülleri ve Dosya Yapısı

```text
/Users/goktus/nomad-radar-bot/
├── config.py                     # Ortam değişkenleri, varsayılan bütçe ve çalışma ayarları
├── database.py                   # SQLite şeması (kullanıcı tercihleri, vize durumu, bildirim geçmişi)
├── models.py                     # Pydantic/Dataclass veri modelleri (TravelWindow, RouteOption, StayOption, DealPackage)
├── calendar_visa/
│   ├── holidays_tr.py            # TR resmi tatiller, yarım günler (28 Ekim, Arefe) ve Köprü İzin hesaplayıcı
│   └── visa_matrix.py            # Yeşil Pasaport (Solo) ve Yeşil+Bordo (Çift) ülke/vize/maliyet kuralları
├── transport/
│   ├── direct_flights.py         # IST/SAW direkt ve 1 aktarmalı uçuş tarayıcı (Google Flights / Kiwi / Pegasus / AJet / Wizz)
│   ├── border_hop.py             # Solo Mod için: İstanbul -> Sofya/Selanik/Bükreş (Otobüs/Tren) + Ryanair/WizzAir birleştirici
│   └── euro_hop.py               # Avrupa içi FlixBus / Tren bağlantı hesaplayıcı
├── accommodation/
│   ├── free_stays.py             # Solo Mod için: Gece yolculuğu (0€), TrustedHousesitters, Couchsurfing, HomeExchange
│   └── paid_stays.py             # Solo (Hostel 8.0+) ve Çift Modu (8.0+ Otel / Tam Daire Airbnb %35+ indirimli) tarayıcı
├── intelligence/
│   ├── campaign_radar.py         # SecretFlying, Fly4Free, HolidayPirates ve Havayolu kampanya RSS/Web takipçisi
│   ├── deal_scorer.py            # Toplam maliyet, izin verimliliği ve indirim oranı skorlayıcı
│   └── gemini_advisor.py         # Gemini AI ile Türkçe akıllı seyahat planı ve karşılaştırmalı yorum üretici
├── bot/
│   ├── telegram_bot.py           # Telegram komutları (/start, /mod, /tatiller, /tara, /hedefler, /vizelerim, /sor)
│   └── scheduler.py              # APScheduler ile periyodik tarama ve anlık bildirim tetikleyici
├── main.py                       # Uygulama giriş noktası
├── requirements.txt              # Python bağımlılıkları
├── Dockerfile & docker-compose.yml # Hem Mac'te hem bulutta tek komutla çalıştırma
└── tests/                        # Pytest birim ve entegrasyon testleri
    ├── test_holidays.py
    ├── test_visa_matrix.py
    ├── test_deal_scorer.py
    └── test_modes.py
```

---

## 4. Veri Akışı ve Skorlama Formülü

1. **Pencere Üretimi (`HolidayWindowCalculator`):**
   - Önümüzdeki 90 gün içindeki tüm resmi tatil + köprü izin kombinasyonlarını (örn. *28 Ekim 13:00 -> 1 Kasım 23:59: 1.5 gün izinle 4.5 gün tatil*), haftasonu kaçamaklarını (*Cuma 19:00 -> Pazar 23:59*) ve hafta içi ekstra ucuz fırsat pencerelerini çıkarır.
2. **Mod Bazlı Rota Filtreleme (`VisaMatrix`):**
   - **Solo Mod** için vizesiz Schengen + Balkanlar + ileri tarihli vizeli ülkeleri;
   - **Çift Modu** için Bordo pasaporta vizesiz/kapıda vizeli ülkeleri (veya eklenmiş vizeleri) seçer.
3. **Ulaşım + Konaklama Paketleme:**
   - Solo Mod: `Min(Direkt Uçuş, Balkan Kara Hack + Ryanair)` + `Min(0€ Bedava Konaklama, 8.0+ Hostel)`.
   - Çift Modu: `2 x Direkt/Konforlu Uçuş` + `Çift Kişilik 8.0+ Otel/Airbnb Daire` + `Varsa Kapıda Vize Ücreti`.
4. **Fırsat Eşiği & Gemini Yorumu:**
   - Paket maliyeti normal piyasa fiyatının %30+ altındaysa veya belirlenen bütçe limitinin altındaysa `DealScorer` fırsatı onaylar, `SQLite` üzerinden daha önce bildirilmediğini doğrular ve `GeminiAdvisor` ile zenginleştirilmiş Telegram mesajını gönderir.

---

## 5. Hata Yönetimi ve Güvenilirlik
- **Kaynak Yedekliliği:** Canlı scraper/API adaptörlerinden biri zaman aşımına uğrarsa veya rate-limit'e takılırsa diğer adaptörler çalışmaya devam eder.
- **Anti-Spam (Deduplication):** Aynı rota + tarih + mod kombinasyonu için fiyat en az %10 daha düşmedikçe tekrar bildirim gönderilmez.
- **Yapılandırılabilir API Anahtarları:** Sadece `TELEGRAM_BOT_TOKEN` ve `GEMINI_API_KEY` ile anında çalışır; isteğe bağlı `TEQUILA_API_KEY`, `AMADEUS_API_KEY`, `SERPAPI_KEY` eklendiğinde ek resmi veri kaynaklarını otomatik devreye alır.
