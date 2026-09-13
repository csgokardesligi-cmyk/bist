#!/usr/bin/env python3
"""
probe_viop.py — VIOP vadeli kontratlarinin GECMIS verisi cekilebiliyor mu?

Spot tarafinda TradingView 2019'a kadar veri veriyor. Ayni sey vadeli
kontratlar icin de gecerli mi, bilmiyoruz. Bu script tahmin etmek yerine
deneyip sonucu raporluyor.

Hicbir sey YAZMAZ — Supabase'e dokunmaz, sadece ekrana basar.

Calistirma: GitHub Actions -> Run workflow -> mode: probe
"""

import os
import sys
import traceback

SYMBOL = os.environ.get("SYMBOL", "ASELS")


def line(c="-"):
    print(c * 64)


def canli_kontratlar():
    """Is Yatirim'dan su an islem goren kontrat kodlarini al."""
    import borsapy as bp
    print("\n[1] Su an islem goren VIOP kontratlari (Is Yatirim)")
    line()
    try:
        df = bp.VIOP().get_by_symbol(SYMBOL)
    except Exception as e:
        print(f"  HATA: {type(e).__name__}: {e}")
        return []

    if df is None or len(df) == 0:
        print("  Bos dondu.")
        return []

    fut = df[df["code"].astype(str).str.startswith("F_")]
    print(f"  toplam {len(df)} kayit, {len(fut)} vadeli (F_) kontrat\n")
    for _, r in fut.iterrows():
        print(f"  {str(r['code']):<20} {str(r.get('contract','')):<32} "
              f"fiyat={r.get('price')}")
    return [str(c) for c in fut["code"].tolist()]


def gecmis_dene(symbol, exchange):
    """Tek bir sembol/borsa kombinasyonunu dene."""
    import borsapy as bp
    from borsapy._providers.tradingview import TradingViewProvider
    try:
        df = TradingViewProvider().get_history(
            symbol=symbol, period="1y", interval="1d", exchange=exchange
        )
        if df is None or len(df) == 0:
            return "bos"
        return f"OK  {len(df)} bar  {df.index.min().date()} -> {df.index.max().date()}"
    except Exception as e:
        return f"{type(e).__name__}"


def gecmis_tara(kodlar):
    print("\n[2] TradingView vadeli gecmis denemeleri")
    line()

    adaylar = []
    for k in kodlar[:3]:                       # en fazla 3 gercek kontrat
        adaylar += [(k, "BIST"), (k, "VIOP")]
    # surekli (continuous) sembol bicimleri — TradingView'de "1!" on aydir
    adaylar += [
        (f"F_{SYMBOL}1!", "BIST"),
        (f"F_{SYMBOL}1!", "VIOP"),
        (f"{SYMBOL}1!",   "BIST"),
        (f"F_{SYMBOL}",   "BIST"),
    ]

    basarili = []
    for sym, exc in adaylar:
        sonuc = gecmis_dene(sym, exc)
        isaret = "+" if sonuc.startswith("OK") else " "
        print(f" {isaret} {exc}:{sym:<22} {sonuc}")
        if sonuc.startswith("OK"):
            basarili.append((exc, sym))
    return basarili


def main():
    print(f"VIOP gecmis veri arastirmasi — {SYMBOL}")
    line("=")
    try:
        kodlar = canli_kontratlar()
        basarili = gecmis_tara(kodlar)
    except Exception:
        traceback.print_exc()
        sys.exit(1)

    print("\n[3] SONUC")
    line()
    if basarili:
        print("  Vadeli gecmis CEKILEBILIYOR. Calisanlar:")
        for exc, sym in basarili:
            print(f"    {exc}:{sym}")
        print("\n  Sonraki karar: kontratlar vadeli bittigi icin surekli bir")
        print("  seri kurmak gerekiyor. Roll tarihi ve fiyat duzeltmesi")
        print("  secilmeli — bu ciktiyi paylas, birlikte karar verelim.")
    else:
        print("  Vadeli gecmis CEKILEMIYOR.")
        print("  Vadeli katman ancak viop_snapshots biriktikce acilabilir;")
        print("  bugunden geriye donuk bir analiz mumkun degil.")
        print("  Bu durumda spot ile vadeli arasindaki FARKI (baz/prim)")
        print("  bugunden itibaren izlemek en mantikli yol.")


if __name__ == "__main__":
    main()
