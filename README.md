# 🧭 NomadRadar: Akıllı Köprü Tatil & Çift Modlu Ucuz Seyahat Telegram Botu

Türkiye'deki **resmi tatilleri**, **yarım günleri (28 Ekim öğleden sonra, bayram arefeleri)**, **haftasonlarını** ve **köprü izin** fırsatlarını otomatik hesaplayan; hem **Solo (Yeşil Pasaport - Maksimum Tasarruf/Macera)** hem de **Çift (Yeşil + Bordo Pasaport - Vizesiz/Sorunsuz & Konforlu)** modlarında en ucuz ulaşım + konaklama paketlerini yakalayıp **Gemini AI** yorumuyla Telegram'dan bildiren akıllı seyahat asistanı.

---

## ✨ Temel Özellikler

### 1. 🎒 Mod 1: Solo / Gezgin Modu (1 Kişi — Yeşil Pasaport)
- **Yeşil Pasaport Vize Zekası:** Schengen ve Balkan ülkelerini **0€ vize maliyetiyle** son dakika dahil tarar. İngiltere/İrlanda gibi yeşil pasaporta da vize isteyen ülkeleri yalnızca randevu yetişecek ileri tarihli tatillerde tarar ve **vize başvuru ücretini (örn. 135€)** toplam bütçeye dahil eder (`/vize_ekle UK` ile muafiyet tanımlanabilir).
- **Balkan Sınır Hack Motoru (`BorderHopEngine`):** Resmi tatillerde İstanbul direkt uçuşları pahalandığında; **İstanbul → Sofya (`SOF`) / Selanik (`SKG`) Gece Treni veya Gece Otobüsü (25€) + Ryanair / WizzAir (15€-27€)** kombinasyonunu kurar. Gece yolculuğu sayesinde **1 gece konaklama maliyetini sıfırlar!**
- **0€ Bedava & Ultra-Ucuz Konaklama:** **TrustedHousesitters / Nomador** (ev/kedi bakımı ile 0€ konaklama), **Couchsurfing / BeWelcome**, **HomeExchange** ve **8.0+ puanlı Hostelworld** fırsatlarını birleştirir.

### 2. 💑 Mod 2: Çift & Konfor Modu (2 Kişi — Siz + Kız Arkadaşınız: Yeşil + Bordo Pasaport)
- **Vize Sorunu Yaşanmayacak Ortak Küme:** Bordo pasaport için randevu stresi olmayan **Vizesiz Balkanlar (Karadağ, Sırbistan, Bosna, Arnavutluk, Makedonya)**, **Kapıda Ekspres Vizeli Yunan Adaları (Rodos, Midilli, Sakız, Kos - Bordo'ya +80€, Yeşil'e 0€)**, **Gürcistan, Şarm El-Şeyh, Fas, Tayland, Japonya** rotalarını tarar.
- **Kız Arkadaşınız Vize Aldığında Tek Komutla Avrupa Açılır:** `/cift_vize_ekle SCHENGEN` yazdığınız anda İtalya, Portekiz, İspanya, Fransa gibi tüm Schengen ülkeleri Çift Moduna da 0€ ek vize maliyetiyle dahil olur!
- **Az Aktarma & Mesai Uyumu:** Yorucu gece otobüsü hack'leri **kapalıdır**. Sadece İstanbul (`IST`/`SAW`) direkt veya tek rahat aktarmalı, mesai çıkış saatlerine uyumlu uçuşlar seçilir.
- **Özel & Konforlu Konaklama (Hostel/Bedava Yok):** Sadece **8.0+ puanlı** **Çift Kişilik Özel Otel Odaları (Butik / 4★)** veya **Tam Daire (Entire Place) Airbnb** (%35+ indirimli) fırsatları hesaplanır.

---

## 🚀 Hızlı Kurulum ve Çalıştırma

### 1. Terminalde Anında Canlı Önizleme (Token Gerekmeden Test Edin)
```bash
cd /Users/goktus/nomad-radar-bot
PYTHONPATH=. .venv/bin/python main.py --demo
```

### 2. Telegram Botunu Canlıya Alma
1. Telegram'da `@BotFather` üzerinden yeni bir bot oluşturup token alın.
2. `.env` dosyasını oluşturun:
   ```bash
   cp .env.example .env
   ```
3. `.env` içine `TELEGRAM_BOT_TOKEN` ve (isteğe bağlı) `GEMINI_API_KEY` değerlerinizi girin.
4. Botu başlatın:
   ```bash
   .venv/bin/python main.py
   ```
   *(Veya Docker ile 7/24 arka planda çalıştırmak için: `docker compose up -d --build`)*

---

## 📱 Telegram Komutları
- `/start` veya `/durum` — Aktif modu, bütçeleri, izlenen ülkeleri ve hızlı butonları gösterir.
- `/tara` — Yaklaşan tatiller (örn. **28 Ekim öğleden sonra → 1 Kasım**) için anında tarama yapar.
- `/tara PT` veya `/tara ME` — Belirli bir ülke için anında paket çıkarır.
- `/mod solo` | `/mod cift` | `/mod ikisi_de` — Çalışma modunu değiştirir.
- `/tatiller` — Önümüzdeki resmi tatilleri ve "kaç gün izinle kaç gün tatil" yapabileceğinizi listeler.
- `/cift_vize_ekle SCHENGEN` — Kız arkadaşınızın aldığı vizeyi Çift Moduna tanımlar.
- `/vize_ekle UK` — Sizin aldığınız vizeyi Solo Moda tanımlar.
- `/hedef_ekle PT` veya `/hedef_ekle cift ME` — İzleme listesine yeni ülke ekler.
- `/butce solo 220` veya `/butce cift 600` — Maksimum paket bütçesini günceller.
- `/kampanyalar` — SecretFlying, Fly4Free ve havayolu anlık indirim/Error Fare radarını gösterir.
- `/sor [sorunuz]` — Gemini AI seyahat asistanına özel rota/konaklama sorusu sorar.
