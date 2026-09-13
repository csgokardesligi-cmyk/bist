-- ============================================================
-- 0005 — kova numarasini panele tasi + islem listesi icin view
-- Supabase SQL Editor'de calistir (0004'ten SONRA).
-- ============================================================

-- forecast_today'e kova numarasi ekleniyor (panel bununla listeyi ceker).
-- create or replace yalnizca SONA sutun eklemeye izin verir.
create or replace view forecast_today as
select
    m.symbol,
    m.date                                   as son_gun,
    m.close                                  as son_kapanis,
    m.z_score,
    s.kova,
    s.n                                      as ornek_sayisi,
    s.gap_medyan,
    s.icgun_medyan,
    s.icgun_p25,
    s.icgun_p75,
    s.icgun_yukari_pct,
    s.aralik_ort,
    round((m.close * (1 + s.gap_medyan / 100))::numeric, 2) as acilis_medyan_tahmin,
    s.sira                                   as kova_no
from latest_metrics m
join zbucket_stats s on s.kova = z_bucket(m.z_score);


-- Tek tek gunler: "bu kovaya dusmus butun gunler ve ertesi gun ne oldu".
-- Panelde tiklayinca acilan liste bunu okuyor.
create or replace view zbucket_cases as
select
    symbol,
    date                as gun,
    next_date           as ertesi_gun,
    z_score,
    close               as kapanis,
    gap_pct,
    intraday_pct,
    cc_pct,
    range_pct,
    bucket              as kova,
    bucket_no           as kova_no
from daily_forward;

-- KONTROL:
--   select * from zbucket_cases where kova_no = 1 order by gun desc;
