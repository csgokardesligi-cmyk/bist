-- ============================================================
-- KATMAN 1 — hesaplama (Supabase / Postgres view)
-- Ham veriye dokunmaz; bars tablosunun uzerine okuma katmani.
-- Supabase SQL Editor'de calistir (0001_init.sql'den SONRA).
-- ============================================================
--
-- VERILEN KARARLAR (degistirmek istersen soyle, tek yerden donuyor):
--   1. Gunluk barin zaman damgasi Europe/Istanbul'a gore tarihe
--      indirgeniyor. Barlar sabah saatlerinde oldugu icin pratikte
--      fark yaratmiyor, ama acik olsun diye yaziyorum.
--   2. z-score referans dagilimi SON 20 GUN, BUGUN HARIC
--      (rows between 20 preceding and 1 preceding).
--      Bugunu dahil etmek skoru kendi kendine seyreltir ve
--      backtest'te look-ahead yaratir.
--   3. ATR = 14 gun, basit ortalama (Wilder degil).
--   4. Volatilite persentili = bugunun ATR14'u, son 252 islem
--      gununun ATR14 dagiliminda hangi yuzdede.
--   5. 20/14/252 sayilari endustri varsayilani — ASELSAN'a
--      optimize EDILMEDI. Parametre taramasi ayri is.
-- ============================================================

-- ---------- gunluk metrikler ----------
create or replace view daily_metrics as
with base as (
    select symbol,
           (ts at time zone 'Europe/Istanbul')::date as date,
           open, high, low, close, volume
    from bars
    where interval = '1d'
),
prev as (
    select *,
           lag(close) over (partition by symbol order by date) as prev_close
    from base
),
calc as (
    select *,
           case when prev_close is null or prev_close = 0 then null
                else (close / prev_close - 1) * 100 end as ret_pct,
           case when prev_close is null then null
                else greatest(high - low,
                              abs(high - prev_close),
                              abs(low  - prev_close)) end as true_range
    from prev
),
roll as (
    select *,
           avg(true_range) over w14  as atr14_raw,
           count(true_range) over w14 as atr_n,
           avg(ret_pct)      over w20 as ret_mean_20,
           stddev_samp(ret_pct) over w20 as ret_sd_20,
           count(ret_pct)    over w20 as ref_n
    from calc
    window
        w14 as (partition by symbol order by date
                rows between 13 preceding and current row),
        w20 as (partition by symbol order by date
                rows between 20 preceding and 1 preceding)
)
select
    symbol,
    date,
    open, high, low, close, volume, prev_close,
    round(ret_pct::numeric, 3)                       as ret_pct,
    -- 14 bar dolmadan ATR anlamsiz
    case when atr_n >= 14 then round(atr14_raw::numeric, 4) end as atr14,
    round(ret_mean_20::numeric, 3)                   as ret_mean_20,
    round(ret_sd_20::numeric, 3)                     as ret_sd_20,
    -- referans dagiliminda en az 15 gozlem yoksa skor uretme
    case when ref_n >= 15 and ret_sd_20 > 0
         then round(((ret_pct - ret_mean_20) / ret_sd_20)::numeric, 3)
    end                                              as z_score,
    ref_n
from roll;


-- ---------- volatilite persentili eklenmis hali ----------
-- Bugunun ATR14'u son 252 islem gununun ATR dagiliminda nerede?
create or replace view daily_metrics_ext as
select
    m.*,
    (
        select round(avg(case when x.atr14 <= m.atr14 then 100.0 else 0 end)::numeric, 1)
        from daily_metrics x
        where x.symbol = m.symbol
          and x.atr14 is not null
          and x.date <= m.date
          and x.date >  m.date - interval '365 days'
    ) as vol_percentile
from daily_metrics m;


-- ---------- panelin okuyacagi tek satir ----------
create or replace view latest_metrics as
select distinct on (symbol) *
from daily_metrics_ext
order by symbol, date desc;


-- ============================================================
-- HIZLI KONTROL — asagidakini ayrica calistirip goz at:
--
--   select date, close, ret_pct, z_score, atr14, vol_percentile
--   from daily_metrics_ext
--   where symbol = 'ASELS'
--   order by date desc limit 20;
--
-- Beklenen: z_score cogunlukla -2 ile +2 arasinda, ara sira disari
-- tasiyor. Surekli 5-10 gibi degerler goruyorsan veri veya formul
-- tarafinda bir sorun var demektir.
-- ============================================================
