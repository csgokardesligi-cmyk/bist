# bist-ingest

ASELSAN (ASELS) için ham piyasa verisi toplayıcı.
GitHub Actions her 15 dakikada bir borsa verisini çekip Supabase'e yazar.

Kurulumu hiç yapmadıysan: **`docs/KURULUM.md`** dosyasını aç, sıfırdan anlatıyor.

## Klasör yapısı

```
bist-ingest/
├── .github/
│   └── workflows/
│       └── bist-ingest.yml      # zamanlanmış çalıştırma talimatı (cron)
├── supabase/
│   └── migrations/
│       └── 0001_init.sql        # veritabanı şeması — Supabase SQL Editor'de çalıştır
├── local/
│   └── bist_store.py            # aynı işi SQLite ile yapan yerel sürüm (opsiyonel)
├── docs/
│   └── KURULUM.md               # sıfırdan kurulum kılavuzu
├── ingest.py                    # asıl toplayıcı: borsapy -> Supabase
├── requirements.txt             # Python bağımlılıkları
├── .env.example                 # yerelde çalıştırmak için ortam değişkeni şablonu
└── .gitignore
```

## Hangi dosya ne zaman çalışır

| Dosya | Nerede çalışır | Ne zaman |
|---|---|---|
| `supabase/migrations/0001_init.sql` | Supabase SQL Editor | Bir kez, kurulumda |
| `ingest.py backfill` | GitHub Actions (elle tetikle) | Bir kez, geçmiş veriyi doldurmak için |
| `ingest.py poll` | GitHub Actions (cron) | Hafta içi 07:00–15:15 UTC, 15 dk'da bir |
| `local/bist_store.py` | Kendi bilgisayarın | İstersen; Supabase'e dokunmadan denemek için |

## Ortam değişkenleri

GitHub'da **Settings → Secrets and variables → Actions** altına girilir.
Yerelde çalıştıracaksan `.env.example`'ı `.env` olarak kopyalayıp doldur ve
kabuğa `export` et.

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `SUPABASE_URL` | evet | `https://xxxxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | evet | service_role / Secret key — anon DEĞİL |
| `TV_SESSION` | hayır | TradingView `sessionid` cookie'si (gecikmesiz veri için) |
| `TV_SESSION_SIGN` | hayır | TradingView `sessionid_sign` cookie'si |
| `SYMBOL` | hayır | Varsayılan `ASELS` |
| `INTRADAY` | hayır | Varsayılan `15m` (`1m,5m,15m,30m,1h`) |
| `BAR_TZ` | hayır | Varsayılan `Europe/Istanbul` — aşağıdaki nota bak |

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
cp .env.example .env          # doldur
set -a && source .env && set +a
python ingest.py backfill
python ingest.py poll
```

## Bilinmesi gereken iki şey

**Zaman damgası.** TradingView bazen saat dilimi bilgisi olan, bazen olmayan
veri dönüyor. Bilgi yoksa `BAR_TZ` (varsayılan İstanbul) kabul edilip UTC'ye
çevriliyor. İlk çalıştırmada log'daki `[tz]` satırı hangisi olduğunu yazar.
Yanlış tarafa düşerse tüm bar zamanları 3 saat kayar ve gün içi hesapların
tamamı bozulur — bu yüzden ilk log mutlaka okunmalı.

**VİOP'un geçmişi yok.** Kaynak (İş Yatırım) sadece o anki durumu veriyor,
geriye dönük sorgulanamıyor. `viop_snapshots` tablosu ancak toplayıcı
çalışmaya başladığı andan itibaren birikir. Yani VİOP'a dayalı bir sinyali
geçmişe dönük test etmek mümkün değil; veri biriktikçe mümkün hale gelecek.

## Bu depoda ne YOK

Bilerek: z-score, normalizasyon, eşik, sinyal üretimi. Buradaki her şey ham
veriyi olduğu gibi saklamakla sınırlı. Hesaplama katmanı ayrı duruyor ki
parametre değiştiğinde veriyi baştan çekmek gerekmesin.
