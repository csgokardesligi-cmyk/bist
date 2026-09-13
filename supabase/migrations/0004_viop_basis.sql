-- ============================================================
-- KATMAN 3 — VIOP vadeli: baz / prim izleme
-- Supabase SQL Editor'de calistir (0003'ten SONRA).
--
-- NEDEN BU: vadeli kontratlarin GECMIS OHLCV verisi elimizde yok
-- (kaynak sadece anlik durum veriyor). Dolayisiyla vadelide
-- z-skoru / ertesi gun analizi BUGUN YAPILAMAZ.
--
-- Ama yapilabilecek bir sey var: vadeli ile spot arasindaki fark.
-- Iki fiyat da ayni anda toplaniyor, uzun gecmise ihtiyac yok.
-- Bu tablolar bugunden itibaren dolar.
--
-- VERILEN KARARLAR (itiraz edersen soyle):
--   1. Kontrat kodunun son 4 hanesi vade ayi kabul ediliyor
--      (F_ASELS1126 -> Kasim 2026). Bu, gordugumuz kodlarla uyumlu.
--   2. Vade gunu, vade ayinin son takvim gunu kabul ediliyor.
--      Gercekte VIOP'ta son isun gunu; birkac gunluk fark yillik
--      orani bir miktar oynatir, prim yuzdesini etkilemez.
--   3. "On ay" (front) = o anda islem goren en yakin vadeli kontrat.
--   4. Yillik oran = prim% x 365 / kalan gun. Basit orantı,
--      bilesik degil.
-- ============================================================

-- ---------- sadece vadeli kontratlar, vade ayi ayristirilmis ----------
create or replace view viop_futures as
select
    underlying,
    fetched_at,
    code,
    contract,
    price,
    volume_qty,
    to_date(right(code, 4), 'MMYY')                                as vade_ay,
    (date_trunc('month', to_date(right(code, 4), 'MMYY'))
        + interval '1 month' - interval '1 day')::date             as vade_son
from viop_snapshots
where code like 'F\_%'
  and price is not null
  and price > 0;


-- ---------- her olcumde on ay kontrati ----------
create or replace view viop_front as
select distinct on (underlying, fetched_at) *
from viop_futures
order by underlying, fetched_at, vade_ay;


-- ---------- baz / prim ----------
create or replace view viop_basis as
select
    f.underlying,
    f.fetched_at,
    f.code,
    f.contract,
    f.price                                                    as vadeli,
    s.spot,
    f.vade_son,
    greatest((f.vade_son - (f.fetched_at at time zone 'Europe/Istanbul')::date), 1)
                                                               as kalan_gun,
    round((f.price - s.spot)::numeric, 2)                      as baz_tl,
    round(((f.price / s.spot - 1) * 100)::numeric, 3)          as prim_pct,
    round((((f.price / s.spot - 1) * 100) * 365.0
           / greatest((f.vade_son - (f.fetched_at at time zone 'Europe/Istanbul')::date), 1)
          )::numeric, 2)                                       as yillik_pct,
    f.volume_qty
from viop_front f
join lateral (
    -- olcum anindaki en guncel spot fiyat
    select q.last as spot
    from quotes q
    where q.symbol = f.underlying
      and q.last is not null
      and q.last > 0
      and q.fetched_at <= f.fetched_at
    order by q.fetched_at desc
    limit 1
) s on true;


-- ---------- gunluk ozet (grafik icin) ----------
create or replace view viop_basis_daily as
select
    underlying,
    (fetched_at at time zone 'Europe/Istanbul')::date      as date,
    count(*)                                               as olcum,
    round(avg(prim_pct)::numeric, 3)                       as prim_ort,
    round(min(prim_pct)::numeric, 3)                       as prim_min,
    round(max(prim_pct)::numeric, 3)                       as prim_max,
    round((array_agg(prim_pct order by fetched_at desc))[1]::numeric, 3)
                                                           as prim_kapanis,
    round(avg(yillik_pct)::numeric, 2)                     as yillik_ort,
    round(avg(spot)::numeric, 2)                           as spot_ort,
    max(code)                                              as kontrat
from viop_basis
group by underlying, (fetched_at at time zone 'Europe/Istanbul')::date;


-- ---------- panelin okuyacagi tek satir ----------
-- Primin kendi gecmisine gore nerede durdugunu da veriyor.
-- Yeterli gozlem birikene kadar z_prim null doner — bu dogru davranis.
create or replace view latest_basis as
with son as (
    select distinct on (underlying) *
    from viop_basis
    order by underlying, fetched_at desc
),
gecmis as (
    select underlying,
           avg(prim_kapanis)         as ort,
           stddev_samp(prim_kapanis) as sd,
           count(*)                  as n
    from viop_basis_daily
    group by underlying
)
select
    s.underlying,
    s.fetched_at,
    s.code,
    s.contract,
    s.vadeli,
    s.spot,
    s.baz_tl,
    s.prim_pct,
    s.yillik_pct,
    s.kalan_gun,
    g.n                                                        as gun_sayisi,
    round(g.ort::numeric, 3)                                   as prim_ort,
    case when g.n >= 15 and g.sd > 0
         then round(((s.prim_pct - g.ort) / g.sd)::numeric, 2)
    end                                                        as z_prim
from son s
left join gecmis g on g.underlying = s.underlying;


-- ============================================================
-- KONTROL:
--   select * from viop_basis order by fetched_at desc limit 10;
--   select * from latest_basis;
--
-- Ilk gunlerde viop_basis_daily'de birkac satir olacak, z_prim null
-- donecek. Normal — prim dagilimini olcmek icin en az 15 gun lazim.
--
-- SINIR: bu tablolarin hicbiri geriye donuk degil. Toplayici ne zaman
-- calismaya basladiysa seri oradan baslar. Vadelide gercek bir
-- geriye donuk analiz, ancak TradingView vadeli gecmisi veriyorsa
-- mumkun — probe_viop.py tam olarak bunu olcuyor.
-- ============================================================
