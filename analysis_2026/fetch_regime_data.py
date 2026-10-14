"""
Rebuild the gitignored data used by analysis_2026/regime_switch.py, from hosts reachable in
the Claude cloud sandbox (GitHub raw/releases and Binance's S3 archive).

    python -m analysis_2026.fetch_regime_data            # everything (~200 MB, a few minutes)
    python -m analysis_2026.fetch_regime_data --skip-pit # if data/raw_pit and data/universe_pit_all exist

Writes:
  data/macro/gspc_1950_2018.csv   ^GSPC daily OHLC (github.com/vijinho/sp500, Yahoo)
  data/macro/us_market_data.csv   S&P with dividends + 3-month T-bill, daily (SteelCerberus)
  data/macro/{UNRATE,VIXCLS,T10Y2Y,PAYEMS}.csv   FRED mirror (github.com/cyby2000/fred-relay)
  data/raw_pit/{prices,membership_intervals}.parquet   Johnbrick123/sp500-data release
  data/universe_pit_all/          screener.data.from_sp500_pit output (total-return OHLC)
  data/crypto_binance_regime/<SYM>USDT.csv   Binance spot daily klines (S3 archive)
All sources are third-party mirrors: spot-check them before relying on a new download.
"""
from __future__ import annotations

import concurrent.futures as cf
import io
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = "https://raw.githubusercontent.com"
MACRO = {
    "gspc_1950_2018.csv": f"{RAW}/vijinho/sp500/master/csv/sp500.csv",
    "us_market_data.csv": f"{RAW}/SteelCerberus/us-market-data/main/data/us_market_data.csv",
    **{f"{s}.csv": f"{RAW}/cyby2000/fred-relay/main/data/{s}.csv" for s in ("UNRATE", "VIXCLS", "T10Y2Y", "PAYEMS")},
}
PIT = "https://github.com/Johnbrick123/sp500-data/releases/download/data"
BINANCE = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
COINS = ("BTC ETH SOL BNB XRP ADA DOGE LINK AVAX DOT LTC TRX BCH ATOM ETC XLM NEAR FIL UNI MATIC POL LUNA FTT "
         "EOS XMR ZEC DASH NEO ALGO VET ICP AAVE XTZ THETA SAND MANA AXS SHIB HBAR EGLD").split()


def get(url: str, timeout=120) -> bytes:
    for k in range(4):
        try:
            return urllib.request.urlopen(url, timeout=timeout).read()
        except Exception:
            if k == 3:
                raise
    raise RuntimeError(url)


def fetch_macro():
    out = DATA / "macro"; out.mkdir(parents=True, exist_ok=True)
    for name, url in MACRO.items():
        (out / name).write_bytes(get(url))
        print("macro", name)


def fetch_pit():
    out = DATA / "raw_pit"; out.mkdir(parents=True, exist_ok=True)
    for name in ("prices.parquet", "membership_intervals.parquet"):
        (out / name).write_bytes(get(f"{PIT}/{name}", timeout=600))
        print("pit", name)
    sys.path.insert(0, str(ROOT))
    from screener.data import from_sp500_pit
    d, _ = from_sp500_pit(out / "prices.parquet", out / "membership_intervals.parquet", DATA / "universe_pit_all",
                          max_close_only=1.0)
    print("universe_pit_all", len(d))


def _klines(key: str):
    z = zipfile.ZipFile(io.BytesIO(get(f"{BINANCE}/{key}")))
    return pd.read_csv(z.open(z.namelist()[0]), header=None)


def fetch_binance(coins=COINS):
    out = DATA / "crypto_binance_regime"; out.mkdir(parents=True, exist_ok=True)
    for s in coins:
        listing = get(f"{BINANCE}?prefix=data/spot/monthly/klines/{s}USDT/1d/&delimiter=/").decode()
        keys = re.findall(r"<Key>([^<]+\.zip)</Key>", listing)
        with cf.ThreadPoolExecutor(16) as ex:
            parts = list(ex.map(_klines, keys))
        if not parts:
            print("no data", s); continue
        d = pd.concat(parts)
        t = d[0].astype("int64")
        t = t.where(t < 1e14, t // 1000)                 # Binance switched to microseconds in 2025
        idx = pd.DatetimeIndex(pd.to_datetime(t, unit="ms").dt.normalize(), name="date")
        f = pd.DataFrame({"open": d[1].values, "high": d[2].values, "low": d[3].values, "close": d[4].values,
                          "quote_volume": d[7].values}, index=idx).sort_index()
        f = f[~f.index.duplicated(keep="last")]
        f.to_csv(out / f"{s}USDT.csv")
        print("binance", s, len(f), f.index[0].date(), f.index[-1].date())


if __name__ == "__main__":
    fetch_macro()
    if "--skip-pit" not in sys.argv:
        fetch_pit()
    fetch_binance()
