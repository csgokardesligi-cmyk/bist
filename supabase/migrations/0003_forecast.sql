-- ============================================================
-- KATMAN 2 — kosullu ertesi gun istatistikleri
-- Supabase SQL Editor'de calistir (0002'den SONRA).
--
-- SORU: "Bugun z-skoru X cikti. Yarin acilista ne oldu, gun
--        icinde ne oldu?" — tarihsel olarak, 2019'dan bu yana.
--
-- Bu bir TAHMIN MODELI DEGIL. Gecmiste benzer gunlerin ertesinde
-- ne oldugunun ampirik dagilimi. Fark onemli: dagilim genis olabilir,
-- ortalama sifira yakin cikabilir, orneklem kucuk olabilir. Sayilar
-- ne diyorsa o.
-- ============================================================

-- ---------- z-skoru kovasi ----------
create or replace function z_bucket(z double precision)
returns text language sql immutable as $$
  select case
    when z is null then null
    when z <= -2 then 'z <= -2'
    when z <= -1 then '-2 < z <= -1'
    when z <=  1 then '-1 < z <= 1'
    when z <=  2 then '1 < z <= 2'
    else 'z > 2'
  end
$$;

create or replace function z_bucket_order(z double precision)
returns int language sql immutable as $$
  select case
    when z is null then null
    when z <= -2 then 1
    when z <= -1 then 2
    when z <=  1 then 3
    when z <=  2 then 4
    else 5
  end
$$;


-- ---------- her gune ertesi gunun sonucunu ekle ----------
create or replace view daily_forward as
with f as (
    select
        m.symbol, m.date, m.close, m.z_score, m.ret_pct,
        m.atr14, m.vol_percentile,
        lead(m.date)  over w as next_date,
        lead(m.open)  over w as next_open,
        lead(m.high)  over w as next_high,
        lead(m.low)   over w as next_low,
        lead(m.close) over w as next_close
    from daily_metrics_ext m
    window w as (partition by m.symbol order by m.date)
)
select
    symbol, date, close, z_score, ret_pct, atr14, vol_percentile,
    next_date,
    -- gece boslugu: dun kapanistan bugun acilisa
    round(((next_open / close - 1) * 100)::numeric, 3)              as gap_pct,
    -- gun ici: acilistan kapanisa  ("gun icinde ne olabilir")
    round(((next_close / next_open - 1) * 100)::numeric, 3)         as intraday_pct,
    -- toplam: kapanistan kapanisa
    round(((next_close / close - 1) * 100)::numeric, 3)             as cc_pct,
    -- gun ici salinim genisligi
    round((((next_high - next_low) / next_open) * 100)::numeric, 3) as range_pct,
    z_bucket(z_score)       as bucket,
    z_bucket_order(z_score) as bucket_no
from f
where z_score is not null
  and next_open is not null
  and close > 0;


-- ---------- ANA SONUC: kova bazinda ertesi gun ----------
create or replace view zbucket_stats as
select
    bucket_no                                                          as sira,
    bucket                                                             as kova,
    count(*)                                                           as n,

    -- acilis boslugu
    round(avg(gap_pct)::numeric, 3)                                    as gap_ort,
    round(percentile_cont(0.5) within group (order by gap_pct)::numeric, 3)
                                                                       as gap_medyan,

    -- gun ici (acilis -> kapanis)
    round(avg(intraday_pct)::numeric, 3)                               as icgun_ort,
    round(percentile_cont(0.5) within group (order by intraday_pct)::numeric, 3)
                                                                       as icgun_medyan,
    round(percentile_cont(0.25) within group (order by intraday_pct)::numeric, 2)
                                                                       as icgun_p25,
    round(percentile_cont(0.75) within group (order by intraday_pct)::numeric, 2)
                                                                       as icgun_p75,
    round((100.0 * avg(case when intraday_pct > 0 then 1 else 0 end))::numeric, 1)
                                                                       as icgun_yukari_pct,

    -- kapanis -> kapanis
    round(avg(cc_pct)::numeric, 3)                                     as cc_ort,
    round((100.0 * avg(case when cc_pct > 0 then 1 else 0 end))::numeric, 1)
                                                                       as cc_yukari_pct,

    round(avg(range_pct)::numeric, 2)                                  as aralik_ort
from daily_forward
group by bucket_no, bucket

union all

-- karsilastirma tabani: kosulsuz tum gunler
select
    0, 'TUM GUNLER (taban)', count(*),
    round(avg(gap_pct)::numeric, 3),
    round(percentile_cont(0.5) within group (order by gap_pct)::numeric, 3),
    round(avg(intraday_pct)::numeric, 3),
    round(percentile_cont(0.5) within group (order by intraday_pct)::numeric, 3),
    round(percentile_cont(0.25) within group (order by intraday_pct)::numeric, 2),
    round(percentile_cont(0.75) within group (order by intraday_pct)::numeric, 2),
    round((100.0 * avg(case when intraday_pct > 0 then 1 else 0 end))::numeric, 1),
    round(avg(cc_pct)::numeric, 3),
    round((100.0 * avg(case when cc_pct > 0 then 1 else 0 end))::numeric, 1),
    round(avg(range_pct)::numeric, 2)
from daily_forward;


-- ---------- WALK-FORWARD: ayni sey, iki ayri donemde ----------
-- Bir kovanin sayilari iki donemde de ayni yone bakmiyorsa,
-- o bulgu gurultudur. En onemli kontrol bu.
create or replace view zbucket_stats_split as
with era as (
    select *,
           case when date < date '2023-01-01' then 'I. donem (2019-2022)'
                else 'II. donem (2023+)' end as donem
    from daily_forward
)
select
    donem,
    bucket_no as sira,
    bucket    as kova,
    count(*)  as n,
    round(avg(gap_pct)::numeric, 3)                        as gap_ort,
    round(avg(intraday_pct)::numeric, 3)                   as icgun_ort,
    round((100.0 * avg(case when intraday_pct > 0 then 1 else 0 end))::numeric, 1)
                                                           as icgun_yukari_pct,
    round(avg(cc_pct)::numeric, 3)                         as cc_ort
from era
group by donem, bucket_no, bucket;


-- ---------- panelin okuyacagi tek satir ----------
-- Bugunku z hangi kovaya dusuyorsa, o kovanin tarihsel dagilimi.
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
    round((m.close * (1 + s.gap_medyan / 100))::numeric, 2) as acilis_medyan_tahmin
from latest_metrics m
join zbucket_stats s on s.kova = z_bucket(m.z_score);


-- ============================================================
-- SIMDI SUNU CALISTIR VE SONUCU PAYLAS:
--
--   select * from zbucket_stats order by sira;
--   select * from zbucket_stats_split order by sira, donem;
--
-- OKURKEN DIKKAT:
--  * n sutunu her seyden onemli. Uc kovalarda 30'un altindaysa
--    oradaki ortalamalar rastlantiya acik.
--  * "TUM GUNLER" satiri karsilastirma tabani. Bir kovanin sayisi
--    tabandan farkli degilse, z-skoru o kovada bilgi tasimiyor.
--  * icgun_yukari_pct %50'ye yakinsa yon bilgisi yok demektir.
--    %55-60 bandi bile tek basina islem kurmaya yetmez.
--  * zbucket_stats_split'te iki donem zit yone bakiyorsa bulgu
--    gurultudur — donem ortalamasina bakip karar verme.
--  * Hicbir sey islem maliyeti, spread veya kayma icermiyor.
-- ============================================================
