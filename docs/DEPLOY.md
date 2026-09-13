# Cloudflare Kurulumu

Iki parca: **Worker** (veriyi Supabase'den okuyan API) ve **Pages** (panelin kendisi).
Panel dogrudan Supabase'e konusmuyor; arada Worker var, boylece gizli anahtar
tarayiciya hic inmiyor.

## 0. Once Supabase

`supabase/migrations/0002_metrics.sql` dosyasinin icerigini Supabase ->
SQL Editor -> New query'ye yapistir, Run. Uc view olusur.

Kontrol et:

```sql
select date, close, ret_pct, z_score, atr14, vol_percentile
from daily_metrics_ext where symbol='ASELS'
order by date desc limit 20;
```

z_score sutunu cogunlukla -2 ile +2 arasinda olmali.

## 1. Worker

Bilgisayarinda Node.js kurulu olmali (nodejs.org -> LTS).
Terminali `worker` klasorunde ac:

```bash
npx wrangler login          # tarayici acilir, izin ver
npx wrangler secret put SUPABASE_URL
npx wrangler secret put SUPABASE_SERVICE_KEY
npx wrangler deploy
```

Her `secret put` komutundan sonra degeri yapistirip Enter'a bas. Yazarken
ekranda gorunmez, normal.

Deploy bitince `https://bist-api.KULLANICI-ADIN.workers.dev` gibi bir adres verir.
Tarayicida `ADRES/api/snapshot?symbol=ASELS` ac — JSON gormen lazim.

## 2. Panel

`web/index.html` dosyasini ac, en alttaki satiri kendi Worker adresinle degistir:

```js
const API = "https://bist-api.KULLANICI-ADIN.workers.dev";
```

Sonra Cloudflare paneli -> Workers & Pages -> Create -> Pages ->
Upload assets. `web` klasorunun icerigini surukle, Deploy.

`https://bist-panel.pages.dev` gibi bir adres verir.

## 3. API'yi kilitle

Simdilik Worker'i herkes cagirabiliyor. Panel adresi belli olunca
`worker/wrangler.toml` icindeki satiri degistir:

```toml
ALLOWED_ORIGIN = "https://bist-panel.pages.dev"
```

Sonra `npx wrangler deploy` ile tekrar yayinla.

## Sorun cikarsa

| Belirti | Sebep |
|---|---|
| Panelde "Veri alinamadi" | API sabiti yanlis ya da Worker deploy edilmemis |
| `/api/snapshot` 502 donuyor | Worker secret'lari eksik/yanlis |
| JSON geliyor ama `metrics: null` | 0002_metrics.sql calistirilmamis |
| Gauge bos, digerleri dolu | z_score null — referans dagilimi icin yeterli gun yok |
