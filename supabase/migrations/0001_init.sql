-- ============================================================
-- KATMAN 0 — ham veri deposu (Supabase / Postgres)
-- bist_store.py'daki SQLite semasinin Postgres karsiligi.
-- Icinde hicbir z-score / normalizasyon / esik YOK — ham veri.
-- Supabase SQL Editor'de calistir.
-- ============================================================

-- ---------- mumlar (gunluk + gun ici, tek tablo) ----------
create table if not exists bars (
    symbol      text        not null,
    interval    text        not null,          -- '1d','15m','5m',...
    ts          timestamptz not null,          -- mum ACILIS zamani (UTC)
    open        double precision,
    high        double precision,
    low         double precision,
    close       double precision,
    volume      double precision,
    fetched_at  timestamptz not null default now(),
    primary key (symbol, interval, ts)
);

create index if not exists idx_bars_lookup
    on bars (symbol, interval, ts desc);

-- ---------- anlik fiyat snapshot'lari ----------
create table if not exists quotes (
    symbol         text        not null,
    fetched_at     timestamptz not null default now(),
    last           double precision,
    open           double precision,
    high           double precision,
    low            double precision,
    prev_close     double precision,
    volume         double precision,
    change_percent double precision,
    update_time    text,                       -- kaynagin verdigi zaman damgasi
    primary key (symbol, fetched_at)
);

create index if not exists idx_quotes_lookup
    on quotes (symbol, fetched_at desc);

-- ---------- VIOP snapshot'lari ----------
-- ONEMLI: kaynakta gecmis YOK. Bu tablo ancak bugunden itibaren birikir.
create table if not exists viop_snapshots (
    underlying  text        not null,          -- 'ASELS'
    fetched_at  timestamptz not null default now(),
    code        text        not null,          -- 'F_ASELS0226'
    contract    text,
    price       double precision,
    change      double precision,
    volume_tl   double precision,
    volume_qty  double precision,
    category    text,                          -- stock/index/currency/commodity
    primary key (underlying, fetched_at, code)
);

create index if not exists idx_viop_code_ts
    on viop_snapshots (code, fetched_at desc);

create index if not exists idx_viop_underlying_ts
    on viop_snapshots (underlying, fetched_at desc);

-- ---------- okuma kolayligi icin view'lar ----------
create or replace view latest_quote as
select distinct on (symbol) *
from quotes
order by symbol, fetched_at desc;

create or replace view latest_viop as
select distinct on (underlying, code) *
from viop_snapshots
order by underlying, code, fetched_at desc;

-- ============================================================
-- RLS — uc tablo da kapali kalsin.
-- Policy tanimlanmadigi icin anon/authenticated HICBIR SEY goremez;
-- yalnizca service_role (ingest job + Cloudflare Worker secret'i) yazar/okur.
-- Frontend Supabase'e dogrudan konusmuyor, Worker uzerinden geciyor.
-- ============================================================
alter table bars            enable row level security;
alter table quotes          enable row level security;
alter table viop_snapshots  enable row level security;

-- ============================================================
-- SAKLAMA NOTU
-- quotes ve viop_snapshots seans boyunca 5 dk'da bir yaziliyor:
--   viop ~100 kontrat x ~100 poll/gun  = ~10k satir/gun
-- Free tier 500 MB'i bir sure idare eder ama sinirsiz degil.
-- Retention politikasini SEN karara baglayacaksin — ornegin ham
-- snapshot'lari 90 gun tutup oncesini saatlik ozete indirmek.
-- Bunu simdiden yazmadim, cunku hangi cozunurlugu kaybetmeyi
-- kabul ettigin sinyal tasarimina bagli.
-- ============================================================
