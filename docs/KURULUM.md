# Sıfırdan Kurulum Kılavuzu — BIST Veri Toplayıcı

Bu kılavuz hiç GitHub ya da Supabase kullanmamış birine göre yazıldı.
Baştan sona takip edersen sonunda, sen hiçbir şey yapmadan, hafta içi her
15 dakikada bir ASELSAN verisini toplayıp veritabanına yazan bir sistemin olur.

**Süre:** ilk kurulum 30–45 dakika. Program yüklemene gerek yok, her şey tarayıcıda.

---

## Ne kuruyoruz? (1 dakikalık arka plan)

Üç parça var:

| Parça | Ne işe yarıyor | Nerede |
|---|---|---|
| **Supabase** | Verinin depolandığı yer. Bulutta duran bir Excel gibi düşün, ama milyonlarca satır tutabilen cinsi. | supabase.com |
| **GitHub** | Kodun durduğu yer. Ayrıca bizim için kodu belirli saatlerde otomatik çalıştırıyor. | github.com |
| **ingest.py** | Borsa verisini çekip Supabase'e yazan Python kodu. Sen yazmayacaksın, hazır. | GitHub'a yükleyeceğiz |

Akış şu: GitHub her 15 dakikada bir `ingest.py`'ı çalıştırıyor → kod borsa
verisini internetten çekiyor → Supabase'e yazıyor. Bilgisayarının açık
olmasına gerek yok, her şey bulutta.

İkisi de ücretsiz, kredi kartı istemiyor.

---

## BÖLÜM 1 — Supabase (veritabanı)

### 1.1 Hesap aç

1. Tarayıcıda `supabase.com` adresine git.
2. Sağ üstteki **Start your project** düğmesine bas.
3. **Continue with GitHub** ile giriş yap. (GitHub hesabın yoksa önce Bölüm 2.1'i
   yapıp buraya dön — nasılsa GitHub hesabı da lazım olacak.)

### 1.2 Proje oluştur

1. Karşına gelen ekranda **New project** de.
2. Organization seçilmesi istenirse, kendi adınla gelen organizasyonu seç.
3. Formu doldur:
   - **Name:** `bist-data` (istediğini yazabilirsin, sadece senin göreceğin bir isim)
   - **Database Password:** **Generate a password** düğmesine bas, çıkan şifreyi
     kopyalayıp bir yere kaydet. Bu şifreyi bu kurulumda kullanmayacağız ama
     kaybedersen sonradan geri alamazsın.
   - **Region:** `Central EU (Frankfurt)` seç. Türkiye'ye en yakın olan bu,
     veri daha hızlı gelip gider.
4. **Create new project** de.
5. Proje kurulurken 1–2 dakika bekleyeceksin. Sayfa kendi kendine yenilenir.

### 1.3 Tabloları oluştur

Şu an veritabanın boş — içinde hiç tablo yok. Tabloları tek tek elle açmak
yerine hazır bir komut dosyası çalıştıracağız.

1. Sol taraftaki menüden **SQL Editor** simgesine tıkla.
2. **New query** de (yeni boş bir metin alanı açılır).
3. Sana verdiğim `supabase_schema.sql` dosyasını bir metin editöründe aç
   (Not Defteri / TextEdit yeter), **içeriğinin tamamını** kopyala.
4. Supabase'deki boş alana yapıştır.
5. Sağ alttaki **Run** düğmesine bas. (Kısayol: Ctrl+Enter / Cmd+Enter)
6. Altta yeşil bir "Success" mesajı görmelisin.

**Kontrol:** Sol menüden **Table Editor**'e geç. Şu üç tabloyu boş olarak
görüyor olman lazım: `bars`, `quotes`, `viop_snapshots`. Görüyorsan bu bölüm bitti.

### 1.4 Bağlantı bilgilerini al

Kodun bu veritabanına yazabilmesi için iki bilgiye ihtiyacı var: adresi ve anahtarı.

1. Sol menünün en altındaki **Project Settings** (dişli çark) → **API Keys**.
   (Menü adı sürüme göre "API" ya da "API Keys" olabilir, aradığın yer aynı.)
2. Burada iki şeyi kopyalayıp bir yere kaydet:
   - **Project URL** — `https://xxxxx.supabase.co` şeklinde bir adres.
   - **Gizli anahtar** — arayüzde **`service_role`** ya da yeni sürümde
     **Secret key** (`sb_secret_...` ile başlar) olarak geçiyor. Yanındaki
     göz simgesine basınca görünür hale gelir, kopyala.

> **ÖNEMLİ:** Sayfada bir de `anon` / **Publishable key** var. **Onu ALMA.**
> Güvenlik ayarlarını öyle yaptık ki o anahtarla hiçbir veri okunamaz/yazılamaz.
> Yanlış anahtarı koyarsan kod çalışmaz.

> **Bu gizli anahtar bir şifre gibidir.** Kimseyle paylaşma, kod dosyasının
> içine yazma, ekran görüntüsüne alma. Birazdan GitHub'ın "kasa" bölümüne
> koyacağız, orası güvenli.

---

## BÖLÜM 2 — GitHub (kodun evi + otomatik çalıştırıcı)

### 2.1 Hesap aç

1. `github.com` → **Sign up**.
2. E-posta, şifre, kullanıcı adı gir, e-postanı doğrula. Ücretsiz plan yeterli.

### 2.2 Repo (kod deposu) oluştur

"Repository" = bir projenin dosyalarının durduğu klasör.

1. Sağ üstteki **+** işaretine bas → **New repository**.
2. **Repository name:** `bist-ingest`
3. **Private** seç. (Kimse göremez. Bizim kullanım yoğunluğumuz GitHub'ın
   ücretsiz limitine rahat sığıyor.)
4. **Add a README file** kutusunu işaretle. (Boş repo'da bazı menüler çıkmıyor,
   bu kutu onu çözüyor.)
5. **Create repository** de.

### 2.3 İki dosyayı yükle

1. Açılan repo sayfasında **Add file** → **Upload files**.
2. Sana verdiğim `ingest.py` ve `requirements.txt` dosyalarını sürükleyip bırak.
3. Sayfanın altındaki yeşil **Commit changes** düğmesine bas.

("Commit" = kaydet demek. GitHub her kaydetmeyi kayıt altına alıyor.)

### 2.4 Workflow dosyasını oluştur

Bu dosya GitHub'a "şu kodu şu saatlerde çalıştır" diyen talimat. Özel bir
klasörde durmak zorunda, o yüzden yükleme yerine elle oluşturacağız.

1. **Add file** → **Create new file**.
2. Dosya adı kutusuna **tam olarak** şunu yaz:

   ```
   .github/workflows/bist-ingest.yml
   ```

   **İpucu:** Yazarken her `/` işaretinde GitHub otomatik olarak yeni bir klasör
   oluşturur — bunu görürsün, normaldir. Baştaki noktayı unutma.
3. Sana verdiğim `bist-ingest.yml` dosyasını metin editöründe aç, içeriğinin
   tamamını kopyala, GitHub'daki büyük metin alanına yapıştır.
4. **Commit changes** → açılan pencerede tekrar **Commit changes**.

**Kontrol:** Üst menüde **Actions** sekmesine tıkla. Solda **bist-ingest** adında
bir iş görüyorsan dosya doğru yere gitmiş demektir. Görmüyorsan dosya adını
yanlış yazmışsındır, 2.4'ü tekrarla.

### 2.5 Gizli bilgileri gir

Şimdi Supabase bilgilerini GitHub'ın kasasına koyacağız. Buraya konan değerler
şifrelenir; sen bile bir daha okuyamazsın, sadece kod kullanabilir.

1. Repo'da üst menüden **Settings** (repo'nun kendi Settings'i, hesabınki değil).
2. Sol menüden **Secrets and variables** → **Actions**.
3. Yeşil **New repository secret** düğmesine bas.
4. İlkini gir:
   - **Name:** `SUPABASE_URL`
   - **Secret:** Adım 1.4'te kopyaladığın `https://xxxxx.supabase.co` adresi
   - **Add secret**
5. Tekrar **New repository secret**, ikincisini gir:
   - **Name:** `SUPABASE_SERVICE_KEY`
   - **Secret:** Adım 1.4'teki gizli anahtar (`service_role` / Secret key)
   - **Add secret**

İsimleri harfi harfine, büyük harfle yaz. Yazım hatası olursa kod bulamaz.

**İsteğe bağlı:** TradingView hesabın varsa veriyi gecikmesiz çekebilirsin.
Yoksa bu adımı atla, sistem yine çalışır — sadece veri 15 dakika gecikmeli olur.
TradingView'e giriş yaptıktan sonra klavyeden F12 → **Application** sekmesi →
sol menüde **Cookies** → `tradingview.com`. Listede `sessionid` ve
`sessionid_sign` satırlarını bul, değerlerini sırasıyla `TV_SESSION` ve
`TV_SESSION_SIGN` adlı iki secret olarak ekle.

---

## BÖLÜM 3 — İlk çalıştırma

Şu ana kadar her şeyi kurduk ama veritabanı hâlâ boş. Şimdi geçmiş veriyi
bir kereliğine toplu halde çekeceğiz. Buna "backfill" diyoruz.

1. Repo'da **Actions** sekmesine git.
2. Soldan **bist-ingest**'e tıkla.
3. Sağ tarafta **Run workflow** düğmesi çıkar, ona bas.
4. Açılan küçük pencerede **mode** kutusunu `poll`'dan **`backfill`** yap.
5. Yeşil **Run workflow** düğmesine bas.
6. Sayfayı yenile. Listede sarı nokta ile yeni bir satır belirir (çalışıyor).

**Ne olduğunu izlemek için:** o satıra tıkla → **ingest** kutusuna tıkla.
Canlı olarak kodun çıktısını görürsün. 1–3 dakika sürer. Sonunda nokta
yeşile dönerse başarılı, kırmızıya dönerse bir sorun var.

### Log'da bakman gereken iki satır

Çıktıyı okurken şu ikisini bul ve bana ilet:

1. `[tz]` ile başlayan satır — saat diliminin doğru yorumlanıp yorumlanmadığını
   söylüyor. Yanlışsa tüm zamanlar 3 saat kayar.
2. `[15m]` ile başlayan satır — sonunda bir tarih aralığı var. Gün içi verinin
   geçmişte nereye kadar gidebildiğini gösteriyor.

---

## BÖLÜM 4 — Veri geldi mi, kontrol et

1. Supabase'e dön → sol menüden **Table Editor** → `bars` tablosuna tıkla.
   Artık dolu olmalı.
2. Daha net görmek için **SQL Editor** → **New query** → şunu yapıştır ve **Run**:

   ```sql
   select interval, count(*) as satir, min(ts) as ilk, max(ts) as son
   from bars
   group by interval;
   ```

   İki satır dönmeli: `1d` (günlük) ve `15m` (gün içi), her birinde binlerce kayıt.

3. Son barların saatine bak:

   ```sql
   select ts, close, volume from bars
   where interval = '15m'
   order by ts desc limit 5;
   ```

   **Saatler UTC olarak saklanıyor**, Türkiye saati değil. Borsa 18:00'de
   kapandığı için en son barın **15:00 civarı** görünmesi doğrudur.
   18:00 görünüyorsa saat dilimi ayarı ters gitmiş, bana haber ver.

---

## BÖLÜM 5 — Artık otomatik

Bundan sonra hiçbir şey yapmana gerek yok. Hafta içi her gün, borsa açıkken,
her 15 dakikada bir sistem kendi kendine çalışıp yeni veriyi ekliyor.

İlk gün **Actions** sekmesinden birkaç çalıştırmanın yeşil olduğunu kontrol et,
sonra unutabilirsin.

**Aklında bulunsun:** GitHub, 60 gün boyunca repo'ya hiç dokunulmazsa otomatik
çalıştırmaları durduruyor ve sana bildirmiyor. Ayda bir Actions sekmesine göz
atmak yeterli.

---

## Bir şeyler ters giderse

| Ne görüyorsun | Sebebi | Çözüm |
|---|---|---|
| Actions'ta **bist-ingest** görünmüyor | Workflow dosyası yanlış klasörde | Adım 2.4'ü tekrarla, dosya adını harfi harfine yaz |
| **Run workflow** düğmesi yok | Dosya henüz ana dala kaydedilmemiş | Sayfayı yenile; olmuyorsa 2.4'ü tekrar et |
| Log'da `SUPABASE_URL / SUPABASE_SERVICE_KEY yok` | Secret isimleri hatalı | Adım 2.5, isimleri büyük harfle ve tam yaz |
| Log'da `upsert 401` veya `403` | Yanlış anahtar (muhtemelen anon/publishable) | Adım 1.4, `service_role` / Secret key'i al |
| Log'da `upsert 404` | Tablolar oluşmamış | Adım 1.3'ü tekrarla |
| `bars: RuntimeError` ya da 0 mum | TradingView bağlantısı ilk denemede boş döndü | Workflow'u bir kez daha çalıştır, genelde ikincide gelir |
| Her şey yeşil ama tablo boş | Farklı bir Supabase projesine yazıyor olabilir | Adım 1.4'teki URL ile secret'taki URL'i karşılaştır |

Takıldığın yerde log ekranının ekran görüntüsünü at, bakarım.
