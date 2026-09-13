#!/usr/bin/env python3
"""
ingest.py — borsapy -> Supabase (PostgREST upsert)

GitHub Actions cron icinde calisir. Hicbir z-score / normalizasyon /
esik hesabi yapmaz; ham veriyi Supabase'e yazar.

Env (GitHub Secrets):
    SUPABASE_URL          https://xxxx.supabase.co
    SUPABASE_SERVICE_KEY  service_role key (anon DEGIL — RLS kapali)
    SYMBOL                varsayilan ASELS
    INTRADAY              varsayilan 15m
    TV_SESSION            (opsiyonel) TradingView sessionid cookie
    TV_SESSION_SIGN       (opsiyonel) sessionid_sign cookie
    BAR_TZ                varsayilan Europe/Istanbul  (asagidaki nota bak)

Kullanim:
    python ingest.py poll
    python ingest.py backfill --daily-period 5y --intraday-period 3mo

-------------------------------------------------------------------
ZAMAN DAMGASI VARSAYIMI (senin onaylaman gereken tek donusum):
TradingView bazen tz-AWARE, bazen tz-NAIVE index donduruyor.
  - aware ise  -> UTC'ye cevriliyor, sorun yok.
  - naive ise  -> BAR_TZ (Europe/Istanbul) kabul edilip UTC'ye ceviriliyor.
Ilk backfill ciktisinda hangi durumda oldugu ekrana basiliyor.
Naive cikarsa ve bar zamanlari sana 3 saat kaymis gorunuyorsa
BAR_TZ=UTC yap. Bu varsayimi degistirmeden once haber ver.
-------------------------------------------------------------------
"""

import argparse
import math
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
SYMBOL = os.environ.get("SYMBOL", "ASELS")
INTRADAY = os.environ.get("INTRADAY", "15m")
BAR_TZ = os.environ.get("BAR_TZ", "Europe/Istanbul")

CHUNK = 500
_tz_reported = False


# ---------------------------------------------------------------- helpers
def _num(v):
    """NaN/Inf -> None (JSON'a NaN yazilamaz)."""
    try:
        if v is None:
            return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _txt(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s and s.lower() != "nan" else None


def to_utc_iso(ts):
    """pandas Timestamp -> ISO8601 UTC. Bkz. ZAMAN DAMGASI VARSAYIMI."""
    global _tz_reported
    if ts.tzinfo is None:
        if not _tz_reported:
            print(f"[tz] index tz-NAIVE -> {BAR_TZ} kabul edilip UTC'ye ceviriliyor")
            _tz_reported = True
        ts = ts.tz_localize(ZoneInfo(BAR_TZ))
    elif not _tz_reported:
        print(f"[tz] index tz-AWARE ({ts.tzinfo}) -> UTC'ye ceviriliyor")
        _tz_reported = True
    return ts.tz_convert(timezone.utc).isoformat()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def upsert(table, rows, on_conflict):
    """PostgREST upsert. Basarisiz olursa exception atar (job kirmizi olsun)."""
    if not rows:
        return 0
    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("[fatal] SUPABASE_URL / SUPABASE_SERVICE_KEY yok")

    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    total = 0
    for i in range(0, len(rows), CHUNK):
        batch = rows[i:i + CHUNK]
        r = requests.post(url, headers=headers, json=batch, timeout=60)
        if r.status_code >= 300:
            # r.text key icermez; log'a secret sizmaz
            raise RuntimeError(f"{table} upsert {r.status_code}: {r.text[:300]}")
        total += len(batch)
    return total


# ---------------------------------------------------------------- builders
def bar_rows(symbol, interval, df):
    fetched = now_iso()
    out = []
    for ts, r in df.iterrows():
        out.append({
            "symbol": symbol, "interval": interval, "ts": to_utc_iso(ts),
            "open": _num(r.get("Open")), "high": _num(r.get("High")),
            "low": _num(r.get("Low")), "close": _num(r.get("Close")),
            "volume": _num(r.get("Volume")), "fetched_at": fetched,
        })
    return out


def quote_row(symbol, info):
    def g(*keys):
        for k in keys:
            try:
                v = info[k]
            except Exception:
                v = None
            if v is not None:
                return v
        return None

    return {
        "symbol": symbol, "fetched_at": now_iso(),
        "last": _num(g("last")), "open": _num(g("open")),
        "high": _num(g("high")), "low": _num(g("low")),
        "prev_close": _num(g("close", "previous_close")),
        "volume": _num(g("volume")),
        "change_percent": _num(g("change_percent")),
        "update_time": _txt(g("update_time")),
    }


def viop_rows(underlying, df):
    fetched = now_iso()
    out = []
    for _, r in df.iterrows():
        code = _txt(r.get("code"))
        if not code:
            continue
        out.append({
            "underlying": underlying, "fetched_at": fetched, "code": code,
            "contract": _txt(r.get("contract")), "price": _num(r.get("price")),
            "change": _num(r.get("change")), "volume_tl": _num(r.get("volume_tl")),
            "volume_qty": _num(r.get("volume_qty")),
            "category": _txt(r.get("category")),
        })
    return out


# ---------------------------------------------------------------- commands
def tv_auth():
    import borsapy as bp
    s, ss = os.environ.get("TV_SESSION"), os.environ.get("TV_SESSION_SIGN")
    if s and ss:
        bp.set_tradingview_auth(session=s, session_sign=ss)
        print("[auth] TradingView oturumu ayarlandi")
    else:
        print("[auth] TV oturumu yok — BIST verisi ~15 dk gecikmeli")


def cmd_backfill(args):
    import borsapy as bp
    tv_auth()
    t = bp.Ticker(SYMBOL)

    d = t.history(period=args.daily_period, interval="1d")
    n = upsert("bars", bar_rows(SYMBOL, "1d", d), "symbol,interval,ts")
    print(f"[1d]  {n} mum | {d.index.min()} -> {d.index.max()}")

    i = t.history(period=args.intraday_period, interval=INTRADAY)
    n = upsert("bars", bar_rows(SYMBOL, INTRADAY, i), "symbol,interval,ts")
    rng = f"{i.index.min()} -> {i.index.max()}" if len(i) else "(bos)"
    print(f"[{INTRADAY}] {n} mum | {rng}")
    print("      ^ TV'nin gun-ici gecmis derinligi bu araliktan okunur")


def cmd_poll(args):
    import borsapy as bp
    tv_auth()
    t = bp.Ticker(SYMBOL)
    failures = []

    try:
        i = t.history(period=args.poll_period, interval=INTRADAY)
        print(f"[{INTRADAY}] {upsert('bars', bar_rows(SYMBOL, INTRADAY, i), 'symbol,interval,ts')} mum")
    except Exception as e:
        failures.append(f"bars: {type(e).__name__}: {e}")

    try:
        upsert("quotes", [quote_row(SYMBOL, t.info)], "symbol,fetched_at")
        print("[quote] ok")
    except Exception as e:
        failures.append(f"quote: {type(e).__name__}: {e}")

    try:
        v = bp.VIOP().get_by_symbol(SYMBOL)
        print(f"[viop] {upsert('viop_snapshots', viop_rows(SYMBOL, v), 'underlying,fetched_at,code')} kontrat")
    except Exception as e:
        failures.append(f"viop: {type(e).__name__}: {e}")

    if failures:
        # kismi basarisizlik job'u kirmizi yapsin ama diger kaynaklar yazilmis olsun
        for f in failures:
            print(f"[hata] {f}", file=sys.stderr)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backfill")
    b.add_argument("--daily-period", default="5y")
    b.add_argument("--intraday-period", default="3mo")
    b.set_defaults(func=cmd_backfill)

    q = sub.add_parser("poll")
    q.add_argument("--poll-period", default="5d")
    q.set_defaults(func=cmd_poll)

    args = p.parse_args()
    print(f"[cfg] symbol={SYMBOL} intraday={INTRADAY} bar_tz={BAR_TZ}")
    args.func(args)


if __name__ == "__main__":
    main()
