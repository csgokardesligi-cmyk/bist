#!/usr/bin/env python3
"""
bist_store.py — KATMAN 0: ham veri deposu (ASELS ve diger BIST sembolleri)

Amac: borsapy'den gelen veriyi OLDUGU GIBI SQLite'a yazmak.
Bu dosyada hicbir z-score / normalizasyon / esik hesabi YOK; sapma
hesaplari ayri bir katmanda bu DB'yi okuyarak yapilacak.

Kurulum:
    pip install borsapy

Kullanim:
    python bist_store.py init
    python bist_store.py backfill --symbol ASELS --daily-period 5y \
        --intraday 15m --intraday-period 3mo
    python bist_store.py poll --symbol ASELS --intraday 15m --once
    python bist_store.py poll --symbol ASELS --intraday 15m --every 300
    python bist_store.py status

Notlar:
  - Gunluk/gun-ici mumlar TradingView provider'i uzerinden geliyor.
    TV hesabi baglanmazsa BIST verisi ~15 dk gecikmelidir.
    Gercek zamanli icin: bp.set_tradingview_auth(...) (bkz. --tv-auth).
  - VIOP verisi Is Yatirim scraping'i, ~15 dk gecikmeli ve SNAPSHOT'tir;
    gecmisi yoktur. Gecmis ancak bugunden itibaren poll ile birikir.
"""

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timezone

DB_PATH = "bist.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS bars (
    symbol   TEXT NOT NULL,
    interval TEXT NOT NULL,
    ts       TEXT NOT NULL,          -- ISO8601, mum acilis zamani
    open     REAL, high REAL, low REAL, close REAL, volume REAL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (symbol, interval, ts)
);

CREATE TABLE IF NOT EXISTS quotes (
    symbol     TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    last REAL, open REAL, high REAL, low REAL,
    prev_close REAL, volume REAL, change_percent REAL,
    update_time TEXT,
    PRIMARY KEY (symbol, fetched_at)
);

CREATE TABLE IF NOT EXISTS viop_snapshots (
    underlying TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    code       TEXT NOT NULL,
    contract   TEXT,
    price REAL, change REAL, volume_tl REAL, volume_qty REAL,
    category   TEXT,
    PRIMARY KEY (underlying, fetched_at, code)
);

CREATE INDEX IF NOT EXISTS idx_bars_sym_int_ts ON bars(symbol, interval, ts);
CREATE INDEX IF NOT EXISTS idx_viop_code_ts   ON viop_snapshots(code, fetched_at);
"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    return con


def cmd_init(args):
    con = connect(args.db)
    con.executescript(SCHEMA)
    con.commit()
    print(f"[ok] sema hazir -> {args.db}")


# --------------------------------------------------------------------------
# yazma yardimcilari
# --------------------------------------------------------------------------

def store_bars(con, symbol, interval, df):
    """DataFrame (Open/High/Low/Close/Volume, DatetimeIndex) -> bars tablosu.
    INSERT OR REPLACE: olusmakta olan son mum her poll'da guncellenir."""
    if df is None or len(df) == 0:
        return 0
    fetched = now_iso()
    rows = []
    for ts, r in df.iterrows():
        rows.append((
            symbol, interval,
            ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            _f(r.get("Open")), _f(r.get("High")), _f(r.get("Low")),
            _f(r.get("Close")), _f(r.get("Volume")), fetched,
        ))
    con.executemany(
        "INSERT OR REPLACE INTO bars "
        "(symbol,interval,ts,open,high,low,close,volume,fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def store_quote(con, symbol, info):
    def g(*keys):
        for k in keys:
            try:
                v = info[k]
            except Exception:
                v = None
            if v is not None:
                return _f(v) if k != "update_time" else str(v)
        return None

    con.execute(
        "INSERT OR REPLACE INTO quotes "
        "(symbol,fetched_at,last,open,high,low,prev_close,volume,"
        "change_percent,update_time) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (symbol, now_iso(), g("last"), g("open"), g("high"), g("low"),
         g("close", "previous_close"), g("volume"), g("change_percent"),
         g("update_time")))
    con.commit()


def store_viop(con, underlying, df):
    if df is None or len(df) == 0:
        return 0
    fetched = now_iso()
    rows = []
    for _, r in df.iterrows():
        rows.append((
            underlying, fetched, str(r.get("code")), str(r.get("contract")),
            _f(r.get("price")), _f(r.get("change")),
            _f(r.get("volume_tl")), _f(r.get("volume_qty")),
            str(r.get("category")) if r.get("category") is not None else None,
        ))
    con.executemany(
        "INSERT OR REPLACE INTO viop_snapshots "
        "(underlying,fetched_at,code,contract,price,change,volume_tl,"
        "volume_qty,category) VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def _f(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # NaN -> None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# komutlar
# --------------------------------------------------------------------------

def _auth(args):
    import borsapy as bp
    if args.tv_session and args.tv_session_sign:
        bp.set_tradingview_auth(session=args.tv_session,
                                session_sign=args.tv_session_sign)
        print("[ok] TradingView auth set (gecikmesiz veri denenecek)")


def cmd_backfill(args):
    import borsapy as bp
    _auth(args)
    con = connect(args.db)
    con.executescript(SCHEMA)
    t = bp.Ticker(args.symbol)

    d = t.history(period=args.daily_period, interval="1d")
    n = store_bars(con, args.symbol, "1d", d)
    print(f"[ok] 1d  : {n} mum  ({d.index.min()} -> {d.index.max()})")

    if args.intraday:
        i = t.history(period=args.intraday_period, interval=args.intraday)
        n = store_bars(con, args.symbol, args.intraday, i)
        rng = f"({i.index.min()} -> {i.index.max()})" if len(i) else ""
        print(f"[ok] {args.intraday:<4}: {n} mum  {rng}")
        print("     NOT: TV'nin gun-ici gecmis derinligi sinirli; gercekte")
        print("     kac gun geri gittigini yukaridaki araliktan dogrula.")


def poll_once(con, args):
    import borsapy as bp
    t = bp.Ticker(args.symbol)
    stamp = datetime.now().strftime("%H:%M:%S")
    out = [stamp]

    try:
        i = t.history(period=args.poll_period, interval=args.intraday)
        out.append(f"{args.intraday}:{store_bars(con, args.symbol, args.intraday, i)}")
    except Exception as e:
        out.append(f"{args.intraday}:ERR({type(e).__name__})")

    try:
        store_quote(con, args.symbol, t.info)
        out.append("quote:ok")
    except Exception as e:
        out.append(f"quote:ERR({type(e).__name__})")

    if not args.no_viop:
        try:
            v = bp.VIOP().get_by_symbol(args.symbol)
            out.append(f"viop:{store_viop(con, args.symbol, v)}")
        except Exception as e:
            out.append(f"viop:ERR({type(e).__name__})")

    print("  ".join(out), flush=True)


def cmd_poll(args):
    _auth(args)
    con = connect(args.db)
    con.executescript(SCHEMA)
    if args.once:
        poll_once(con, args)
        return
    print(f"[poll] her {args.every}s — Ctrl+C ile dur")
    try:
        while True:
            poll_once(con, args)
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("\n[stop]")


def cmd_status(args):
    con = connect(args.db)
    con.executescript(SCHEMA)
    print("bars:")
    for r in con.execute(
            "SELECT symbol,interval,COUNT(*),MIN(ts),MAX(ts) FROM bars "
            "GROUP BY symbol,interval ORDER BY symbol,interval"):
        print(f"  {r[0]:<6} {r[1]:<4} n={r[2]:<6} {r[3]} -> {r[4]}")
    print("quotes:")
    for r in con.execute("SELECT symbol,COUNT(*),MAX(fetched_at) FROM quotes "
                         "GROUP BY symbol"):
        print(f"  {r[0]:<6} n={r[1]:<6} son={r[2]}")
    print("viop:")
    for r in con.execute(
            "SELECT underlying,COUNT(DISTINCT fetched_at),COUNT(DISTINCT code),"
            "MAX(fetched_at) FROM viop_snapshots GROUP BY underlying"):
        print(f"  {r[0]:<6} snapshot={r[1]:<5} kontrat={r[2]:<4} son={r[3]}")


def main():
    p = argparse.ArgumentParser(description="BIST ham veri deposu")
    p.add_argument("--db", default=DB_PATH)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--symbol", default="ASELS")
        sp.add_argument("--intraday", default="15m",
                        choices=["1m", "5m", "15m", "30m", "1h"])
        sp.add_argument("--tv-session", default=None)
        sp.add_argument("--tv-session-sign", default=None)

    sub.add_parser("init").set_defaults(func=cmd_init)

    b = sub.add_parser("backfill"); common(b)
    b.add_argument("--daily-period", default="5y")
    b.add_argument("--intraday-period", default="3mo")
    b.set_defaults(func=cmd_backfill)

    q = sub.add_parser("poll"); common(q)
    q.add_argument("--poll-period", default="5d",
                   help="her poll'da cekilecek gun-ici pencere")
    q.add_argument("--every", type=int, default=300)
    q.add_argument("--once", action="store_true")
    q.add_argument("--no-viop", action="store_true")
    q.set_defaults(func=cmd_poll)

    sub.add_parser("status").set_defaults(func=cmd_status)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
