"""
Data layer for the Bollinger-breakout replication (analysis_2026/BB_REPLICATION_PREREG.md, "Data", "Windows",
the R0 table's Signal, Liquidation and Costs rows, and S12). Reads the gitignored files that
`analysis_2026/fetch_bb_data.py` built under data/bbreplica/ (research_notes/Bollinger breakout
replication/data_inventory.md) and adds the S12 all-contract volume ranking.

    python3 -m analysis_2026.bb_data selftest      # invariants and known answers (no strategy is run)
    python3 -m analysis_2026.bb_data fetch-all     # S12: daily USD-M klines of every USDT perpetual -> d1_um_all/
    python3 -m analysis_2026.bb_data entrants      # S12: hourly, mark, funding (+ spot) files of top-10 entrants not in the 40
    python3 -m analysis_2026.bb_data entrant-spot  # S12: only the entrants' spot hourly / daily files
    python3 -m analysis_2026.bb_data ranks         # print the monthly top-10 tables (pool 40 and all)
  options: --workers 16 (at most 16 download workers)  --force

Public API (contract: scratchpad bb_engine_spec.md, "bb_data.py")
  COINS, PRIMARY, RH_TRADABLE, M1_COINS, MMR, TICK (+ M1_GRID, S12_ENTRANTS, S12_ENTRANTS_SPOT)
  coin_hours(sym, start=None, end=None)      hourly frame: traded series, signal series, mark, funding, flags
  bars(sym, freq, series="sig")              1d / 4h / 1h / 1w bars from coin_hours (via bars_from_hours)
  bars_from_hours(hours, freq, series="sig") the same from an injected coin_hours-shaped frame
  minutes(sym, start, end)                   1-minute perpetual bars, prices rounded to M1_GRID
  ny_clock(index)                            New York clock fields for UTC timestamps
  tbill_daily(index), tbill_session(index)   simple T-bill rate per UTC day (365) / per session (252)
  volume_ranks(pool="40" | "all", tradfi=True)  monthly point-in-time top-10 by 90-day quote volume (S12)
  s12_entrants(tradfi=None), all_contracts_table(), fetch_d1_all(), fetch_entrants(), fetch_entrant_spot(),
  spot_basis(coin), infer_tick(sym)

S12 data built 2026-10-19: d1_um_all/{CONTRACT}.parquet for all 909 USDT perpetuals in the archive listing
(36,231 checksummed zips, none failed; 318 bars filled from daily zips) with d1_um_all/_status.json; the 50
coins outside the 40 that enter a monthly top 10 (S12_ENTRANTS) got h1_um / d1_um / h1_mark / funding files
named {COIN}USDT.parquet (1000PEPE, 1000SATS rescaled to one coin) with fetch_bb_data's own code, and the 35 of
them with a Binance spot market (S12_ENTRANTS_SPOT; spot 1000SATSUSDT rescaled to one coin) got h1_spot /
d1_spot files too, so that their signal series follows the R0 Signal row like the 40's.

Series (R0 Signal row; "Windows": spot hours stand in where a perpetual did not yet exist)
- TRADED series (open/high/low/close/trades/quote_volume): the USD-M perpetual inside a perpetual contract's
  window [first, last hourly bar of h1_um]; else Binance spot where spot STANDS IN; else a filler row.
  Spot stands in at hour t (column spot_only) iff t is inside a spot segment, a perpetual of the coin lists
  after t, and no perpetual window ended between the start of t's spot segment and t. So spot stands in
  before the coin's first perpetual and, for LUNA, in the Terra 2.0 spot segment (2022-05-31 06:00 ..
  2022-09-10, before LUNA2USDT listed); it never stands in after a perpetual ended (old LUNA spot
  2022-05-12 16:00 .. 2022-05-13 00:00) or after the coin's last perpetual (FTT from 2022-11-14 05:00, MATIC
  from 2024-09-04 09:00, EOS from 2025-05-21 09:00, and delisted entrants): those hours are filler rows with
  trades == 0, tradable = False, carried flat at the perpetual's last close.
- `perp_end` marks the last hourly bar of a perpetual that ended before 2026-10-16 23:00 (EOS, FTT, old LUNA,
  MATIC; delisted entrants). It is a FORCED CLOSE for the engine: a position still open at that bar's close is
  closed at that close (Binance settles a delisted contract's open positions [U]; the stock rule "a position whose prices end is
  closed at the last close"), since no later row of that contract can fill.
- SIGNAL series (sig_*): spot inside a spot segment, else the perpetual inside a contract window, else filler
  (unchanged by the stand-in rule: FTT's spot signal runs to 2026 while nothing can be traded).
- A spot SEGMENT is a run of spot bars with no hole of 72 h or more (the inventory's segment-break rule): spot
  LUNAUSDT has two (old Terra to 2022-05-13 00:00, Terra 2.0 from 2022-05-31 06:00) and spot FTTUSDT two
  (to 2022-11-15 04:00, from 2023-09-22 08:00); every other coin of the 40 has one. Perpetual windows: one per
  contract; LUNA has two (LUNAUSDT 2021-01-28..2022-05-12 15:00, then LUNA2USDT from 2022-09-10, the Terra 2.0
  perpetual).
- Filler rows (no bar in the market the row reads, including hours inside a market's window that the archive
  leaves out): OHLC = the previous close of that series, trades = 0, quote_volume = 0, *_live = False.
- Mark: h1_mark trimmed to each contract's h1_um window (inventory 1.1: placeholder mark bars after EOS, FTT,
  LUNA and MATIC delisted; bars before the first traded hour); NaN elsewhere and on spot-traded rows.

Funding (Costs row): `funding[t]` = sum of the rates of the prints whose calc_time floored to the minute equals
open_time t (every print in the archive floors to a whole hour, checked), i.e. what a long open before t and
still open at t owes, per unit of mark value.
- Spot stand-in hours (spot_only; "before a coin's perpetual listed"): synthetic 0.0001 at every 00/08/16 UTC
  hour (as leverage_breakout.py). For LUNA that is before LUNAUSDT and the Terra 2.0 spot segment before
  LUNA2USDT; old LUNA spot after LUNAUSDT ended and the 2022-05-13 .. 05-31 gap owe nothing (nothing tradable).
- ICP before 2022-09-01 (its funding archive starts then): synthetic 0.0001 at 00/08/16 UTC.
- 2026-10-01 00:00 .. 2026-10-16 23:00 (no archive funding yet): September 2026's median per-interval rate,
  at the coin's last cadence (last September print + k * its interval_h).
- Inside a perpetual window an hour without a print owes 0 (the archive misses at most 4 prints per contract).
- Non-tradable hours (after a perpetual ended, until spot of a new asset stands in or the next perpetual): 0.

Coding choices the pre-registration leaves open (most literal reading taken; also in the build report)
1. "Perpetual where it exists" is decided per contract window, not per hour: an hour the archive leaves out
   inside a perpetual's window is a filler row with trades == 0 (no fills), not a switch to spot. Likewise for
   spot inside a spot segment (signal series). Daily bars are aggregated from live rows only, so a spot daily
   bar equals Binance's own 1d kline.
2. Series breaks (LUNA 2022-05-13/31, FTT 2022-11-15 .. 2023-09-22): extra column `seg` (0, 1, ...) increments
   at the first live hour after a gap of 72 h or more in the signal series; bars() carries it. Indicators must
   not run across a change of `seg` (inventory section 9: "treat them as series breaks").
3. "Where a perpetual did not yet exist" is read per asset: spot stands in only before a perpetual of the
   asset the spot segment trades lists (rule above), so a delisted perpetual is never replaced by spot (FTT
   would otherwise trade spot from 2022-11 to 2026-10). Synthetic funding follows the stand-in hours exactly
   (it is charged where spot stands in for a not-yet-listed perpetual, and nowhere else outside ICP's rule).
   The engine must close a position at a `perp_end` bar's close; the hours after it are filler.
4. bars(): a bar with no live hour is dropped (no flat carried bars, which would put a zero-width band on a
   dead series). 4h bars are aligned to 00/04/08/12/16/20 UTC; "1w" = Monday-labelled weeks of the daily bars
   (moneyline_ref.to_weekly: label left, closed left, Monday 00:00 UTC). A bar's known_at is its nominal end
   (open + period), the first hour at which its close may be used.
5. Volume ranks: sum of daily quote volume over the 90 UTC days [M - 90 d, M - 1 d] for month start M (a coin
   listed for fewer days sums what it has); a coin must have traded (trades > 0) on day M - 1 to be ranked;
   ties broken alphabetically. pool "40": the coin_hours traded series (perpetual where it trades, spot
   before: only where spot stands in, so FTT is not ranked after its perpetual delisted; no 2017-09 .. 2026-10
   top 10 changed by that), counted only inside the series segment live on day M - 1 (so Terra 2.0 does not
   inherit old LUNA's volume). pool "all": the archive's USD-M daily klines only (no spot volume for coins outside the 40, so no
   "spot before" for them, nor for the 40 in that pool), contracts mapped to coins (1000 / 1000000 / 1M
   prefixes; LUNA2USDT -> LUNA; concurrent contracts of one coin summed; a multiplier contract whose base also
   trades as a plain contract keeps its own name, e.g. 1000CAT, because those are different assets). Only
   stablecoin and Binance index contracts are excluded (STABLE_EXCLUDE, INDEX_EXCLUDE), so TradFi perpetuals
   (stocks, ETFs, pre-IPO shares, metals, oil; listed from 2025-12) stay in the pool, as the pre-registration's
   exclusion list reads; volume_ranks("all", tradfi=False) is the crypto-only variant. From 2026-03 the
   literal top 10 holds XAU and XAG, and from 2026-08 SNDK, SKHYNIX, SOXL, SPCX and MU (SNDK is third in
   2026-09 and 2026-10, so it enters S12's top 3).
6. MMR: Binance's tier-1 maintenance margin rate per contract from an October 2026 snapshot (see MMR below for
   the source of each value); EOS, MATIC and YFII are not in it and carry a labelled assumption.
7. TICK: the largest power of ten whose grid holds every price of the perpetual's hourly file from 2024-07-01
   (the whole file if the contract ended before); this is the smallest increment observed rounded to a power
   of ten, except that a contract whose tick Binance refined during the span gets the finer tick (DOT, FIL).
8. minutes() rounds to M1_GRID, which is TICK except BTC (0.01): the BTC 1m archive has four prices off its
   0.1 tick, and rounding them to the tick would alter archive values.
9. Market windows are known in advance (listings and delistings are announced): the signal series switches to
   the perpetual at the first hour after spot's last bar. Among the 40 this matters only for XMR (spot
   delisted 2024-02-20 02:00, announced about two weeks earlier [U]); the other spot series of the 40 that end
   (EOS, MATIC, old LUNA, FTT's first segment) end after their perpetual did. Likewise `perp_end` is known in
   advance (delistings are announced).
10. S12 entrants get the 40's signal rule: spot where Binance spot trades the coin ({COIN}USDT, or 1000SATSUSDT
   for SATS; S12_ENTRANTS_SPOT), else the perpetual; their history and ATH start at the earlier of the two
   listings. The pre-registration's Data section names only the entrants' "hourly, mark and funding files";
   the Signal row ("spot where spot trades", ATH over "the Binance history") decides. Every entrant spot
   series was checked to be the same asset as its perpetual (median |spot / perp - 1| over common hours).
11. `start` / `end` of coin_hours() and minutes() are inclusive bounds on open_time. A date given without a time
   (a 'YYYY-MM-DD', 'YYYY-MM' or 'YYYY' string, or a datetime.date) means that whole period, as pandas'
   partial-string slicing reads it: end='2026-10-16' keeps the bars through 2026-10-16 23:00 (23:59 for
   minutes). A Timestamp, datetime or string with a time is exact.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis_2026 import fetch_bb_data as fbd  # noqa: E402

DATA = ROOT / "data" / "bbreplica"
END = pd.Timestamp("2026-10-16 23:00", tz="UTC")           # last hourly bar of every live series
END_DAY = "2026-10-16"
NY = ZoneInfo("America/New_York")
H = pd.Timedelta("1h")
BREAK_H = 72                                               # a hole this long splits a spot series (inventory)
MAX_WORKERS = 16

# ---------------------------------------------------------------- universes
COINS: list[str] = list(fbd.SYMS)                          # the 40 coins
PRIMARY = ["BTC", "ETH", "SOL"]
RH_TRADABLE: list[str] = ("AAVE ADA ALGO ATOM AVAX AXS BCH BNB BTC DOGE DOT ETC ETH HBAR LINK LTC NEAR SHIB SOL "
                          "UNI XLM XRP XTZ ZEC").split()   # pre-registration "Data": 24 coins, 2026-10-18
M1_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE"]
assert len(COINS) == 40 and len(RH_TRADABLE) == 24 and set(RH_TRADABLE) <= set(COINS)

# perpetual contract files per coin, in time order: (file stem under h1_um/, funding/, h1_mark/)
_PERP_FILES = {"LUNA": ["LUNA", "LUNA2"]}

# Price tick per perpetual (one coin = one unit; SHIB is 1000SHIBUSDT / 1000): output of infer_tick(), checked
# by the self-test. DOT and FIL: Binance refined the tick in 2026 as their prices fell below 1; the finer tick
# holds every price since 2024-07-01.
TICK: dict[str, float] = {
    "BTC": 0.1, "ETH": 0.01, "SOL": 0.001, "BNB": 0.01, "XRP": 1e-4, "DOGE": 1e-5, "ADA": 1e-4, "AVAX": 0.001,
    "LINK": 0.001, "LTC": 0.01, "TRX": 1e-5, "DOT": 1e-6, "BCH": 0.01, "ATOM": 0.001, "ETC": 0.001, "XLM": 1e-5,
    "NEAR": 0.001, "FIL": 1e-6, "UNI": 0.001, "MATIC": 1e-4, "POL": 1e-5, "LUNA": 1e-5, "FTT": 1e-4,
    "EOS": 0.001, "XMR": 0.01, "ZEC": 0.01, "DASH": 0.01, "NEO": 0.001, "ALGO": 1e-5, "VET": 1e-6, "ICP": 0.001,
    "AAVE": 0.01, "XTZ": 1e-4, "THETA": 1e-4, "SAND": 1e-5, "MANA": 1e-5, "AXS": 1e-4, "SHIB": 1e-9,
    "HBAR": 1e-5, "EGLD": 0.001,
}
# S12 entrants outside the 40 (1000PEPEUSDT and 1000SATSUSDT per one coin), same inference.
TICK.update({
    "AKE": 1e-7, "APE": 1e-4, "APT": 1e-4, "ARB": 1e-5, "ASTER": 1e-4, "BLZ": 1e-5, "CFX": 1e-5, "CHZ": 1e-5,
    "CL": 0.01, "ENA": 1e-5, "FARTCOIN": 1e-4, "FTM": 1e-4, "GALA": 1e-6, "GAS": 0.001, "GMT": 1e-6,
    "HYPE": 0.001, "LAB": 1e-5, "LINA": 1e-6, "MASK": 1e-4, "MU": 0.01, "MYX": 1e-5, "NEIRO": 1e-8, "NOT": 1e-7,
    "OP": 1e-5, "ORDI": 0.001, "PEOPLE": 1e-6, "PEPE": 1e-10, "PIPPIN": 1e-5, "PNUT": 1e-5, "RAVE": 1e-5,
    "RIVER": 0.001, "SATS": 1e-11, "SKHYNIX": 0.01, "SNDK": 0.01, "SOXL": 0.01, "SPCX": 0.01, "SUI": 1e-4,
    "SUSHI": 1e-4, "TIA": 1e-4, "TRB": 0.001, "TRUMP": 0.001, "WAVES": 1e-4, "WIF": 1e-4, "WLD": 1e-4,
    "XAG": 0.01, "XAU": 0.01, "XPL": 1e-5, "YFI": 1.0, "YFII": 0.1, "ZIL": 1e-6,
})
# S12 all-contract entrants: coins outside the 40 that enter a monthly top 10 of volume_ranks("all") in the
# literal pool (TradFi kept) or the crypto-only variant; each has h1_um / h1_mark / funding files (fetch_entrants).
S12_ENTRANTS_TRADFI = ["CL", "MU", "SKHYNIX", "SNDK", "SOXL", "SPCX", "XAG", "XAU"]     # literal pool only
S12_ENTRANTS_CRYPTO_ONLY = ["AKE", "LAB", "PIPPIN", "RAVE"]                            # crypto-only pool only
S12_ENTRANTS = sorted(
    "APE APT ARB ASTER BLZ CFX CHZ ENA FARTCOIN FTM GALA GAS GMT HYPE LINA MASK MYX NEIRO NOT OP ORDI PEOPLE "
    "PEPE PNUT RIVER SATS SUI SUSHI TIA TRB TRUMP WAVES WIF WLD XPL YFI YFII ZIL".split()
    + S12_ENTRANTS_TRADFI + S12_ENTRANTS_CRYPTO_ONLY)
# Entrants with a Binance spot market (archive listing data/spot/{monthly,daily}/klines/, 2026-10-19): spot pair
# {COIN}USDT, except SATS, whose spot pair is 1000SATSUSDT (rescaled to one coin like its perpetual). The other
# 15 entrants (AKE CL FARTCOIN LAB MU MYX PIPPIN RAVE RIVER SKHYNIX SNDK SOXL SPCX XAG XAU) have no spot pair.
S12_ENTRANTS_SPOT = sorted(
    "APE APT ARB ASTER BLZ CFX CHZ ENA FTM GALA GAS GMT HYPE LINA MASK NEIRO NOT OP ORDI PEOPLE PEPE PNUT SATS "
    "SUI SUSHI TIA TRB TRUMP WAVES WIF WLD XPL YFI YFII ZIL".split())
SPOT_PAIR: dict[str, tuple[str, int]] = {"SATS": ("1000SATSUSDT", 1000)}   # coin -> (spot pair, units per price)
# Grid that minutes() rounds the float32 1-minute prices to: the tick, except BTC, whose 1m archive prints four
# prices off the 0.1 tick in August 2024 (infer_tick); 0.01 recovers every archive price exactly.
M1_GRID: dict[str, float] = {"BTC": 0.01, "ETH": 0.01, "SOL": 0.001, "BNB": 0.01, "XRP": 1e-4, "DOGE": 1e-5}
# Maintenance margin rate of Binance's lowest tier (tier 1) per USDT perpetual (R0 Liquidation row: "mmr from
# Binance's lowest tier"). Source [S]: freqtrade's dump of Binance's /fapi/v1/leverageBracket
# (raw.githubusercontent.com/freqtrade/freqtrade/develop/freqtrade/exchange/binance_leverage_tiers.json,
# downloaded 2026-10-19, sha256 0d15c20e..., includes contracts listed 2026-10-06, so it is an October 2026
# snapshot; tiers change over time, so these are today's values applied to 2020-2026). Every value below is
# that snapshot's tier-1 rate of the coin's contract (BTC and ETH 0.004, notional to 300,000 USDT), except:
# - LUNA 0.015 is LUNA2USDT's tier (the old LUNAUSDT contract is not in the snapshot);
# - FTT 0.025 is today's FTTUSDT tier (max 8x), not its 2022 one;
# - ASSUMPTION (delisted, not in the snapshot): EOS 0.01 = its successor contract AUSDT (Vaulta), MATIC 0.01 =
#   its successor POLUSDT, YFII 0.01 = its sibling YFIUSDT (all three tier 1 = 0.01 in the snapshot).
MMR: dict[str, float] = {
    "BTC": 0.004, "ETH": 0.004, "SOL": 0.005, "BNB": 0.005, "XRP": 0.005, "DOGE": 0.0065, "ADA": 0.005,
    "AVAX": 0.005, "LINK": 0.005, "LTC": 0.005, "TRX": 0.0065, "DOT": 0.0065, "BCH": 0.005, "AAVE": 0.01,
    "ALGO": 0.01, "ATOM": 0.006, "AXS": 0.01, "DASH": 0.01, "EGLD": 0.01, "EOS": 0.01, "ETC": 0.005,
    "FIL": 0.01, "FTT": 0.025, "HBAR": 0.01, "ICP": 0.01, "LUNA": 0.015, "MANA": 0.01, "MATIC": 0.01,
    "NEAR": 0.01, "NEO": 0.01, "POL": 0.01, "SAND": 0.01, "SHIB": 0.0065, "THETA": 0.01, "UNI": 0.006,
    "VET": 0.006, "XLM": 0.01, "XMR": 0.01, "XTZ": 0.01, "ZEC": 0.01,
}
# S12 entrants outside the 40 (s12_entrants(): either pool variant), same snapshot (YFII: the assumption above).
# Several post-pump contracts are capped at 7-10x today, hence their 2-5% tiers.
MMR.update({
    "AKE": 0.05, "APE": 0.015, "APT": 0.01, "ARB": 0.006, "ASTER": 0.01, "BLZ": 0.025, "CFX": 0.01, "CHZ": 0.01,
    "CL": 0.005, "ENA": 0.01, "FARTCOIN": 0.01, "FTM": 0.006, "GALA": 0.01, "GAS": 0.015, "GMT": 0.015,
    "HYPE": 0.01, "LAB": 0.05, "LINA": 0.025, "MASK": 0.015, "MU": 0.01, "MYX": 0.05, "NEIRO": 0.015,
    "NOT": 0.015, "OP": 0.006, "ORDI": 0.015, "PEOPLE": 0.015, "PEPE": 0.0065, "PIPPIN": 0.02, "PNUT": 0.015,
    "RAVE": 0.05, "RIVER": 0.015, "SATS": 0.02, "SKHYNIX": 0.01, "SNDK": 0.0065, "SOXL": 0.01, "SPCX": 0.0065,
    "SUI": 0.01, "SUSHI": 0.01, "TIA": 0.01, "TRB": 0.015, "TRUMP": 0.01, "WAVES": 0.015, "WIF": 0.01,
    "WLD": 0.01, "XAG": 0.005, "XAU": 0.005, "XPL": 0.01, "YFI": 0.01, "YFII": 0.01, "ZIL": 0.02,
})


# ================================================================ files
def _read(kind: str, stem: str, columns=None) -> pd.DataFrame | None:
    """data/bbreplica/{kind}/{stem}USDT.parquet with open_time / calc_time as datetime64[ns, UTC]; None if absent."""
    p = DATA / kind / f"{stem}USDT.parquet"
    if not p.exists():
        return None
    x = pd.read_parquet(p, columns=columns)
    for c in ("open_time", "calc_time"):
        if c in x:
            x[c] = x[c].dt.as_unit("ns")
    return x


def perp_files(sym: str) -> list[str]:
    """File stems of the coin's USD-M perpetual contracts in time order (h1_um / h1_mark / funding)."""
    return [s for s in _PERP_FILES.get(sym, [sym]) if (DATA / "h1_um" / f"{s}USDT.parquet").exists()]


def _segments(t: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """[first, last] bar of each run of bars with no hole of BREAK_H hours or more."""
    t = pd.DatetimeIndex(t)
    brk = np.flatnonzero(np.diff(t.asi8) >= (BREAK_H + 1) * H.value)
    starts = np.r_[0, brk + 1]
    ends = np.r_[brk, len(t) - 1]
    return [(t[a], t[b]) for a, b in zip(starts, ends)]


def _pos(idx: pd.DatetimeIndex, t) -> np.ndarray:
    """Row numbers of hourly timestamps t in the hourly index idx (t must lie on the grid)."""
    p = (pd.DatetimeIndex(t).asi8 - idx.asi8[0]) // H.value
    return p.astype(np.int64)


PX = ["open", "high", "low", "close"]
SIG = ["sig_open", "sig_high", "sig_low", "sig_close"]
FUND_SYN = 0.0001                      # per 8 h at 00/08/16 UTC (leverage_breakout.DEFAULT_FUND_8H)
ICP_FUNDING_FROM = pd.Timestamp("2022-09-01", tz="UTC")
OCT_FROM = pd.Timestamp("2026-10-01", tz="UTC")


@lru_cache(maxsize=16)
def _coin_hours_full(sym: str) -> pd.DataFrame:
    spot = _read("h1_spot", sym)
    perps = [(stem, _read("h1_um", stem)) for stem in perp_files(sym)]
    if spot is None and not perps:
        raise FileNotFoundError(f"no hourly files for {sym} under {DATA}")
    t0 = min(([spot.open_time.iloc[0]] if spot is not None else []) + [p.open_time.iloc[0] for _, p in perps])
    idx = pd.date_range(t0, END, freq="h", name="open_time").as_unit("ns")
    n = len(idx)
    cols = PX + ["quote_volume", "trades"]

    # spot: segments and values
    sp_in, sp_has = np.zeros(n, bool), np.zeros(n, bool)
    seg_start = np.full(n, -1, np.int64)                     # row of the first bar of the hour's spot segment
    sp = {c: np.full(n, np.nan) for c in cols}
    if spot is not None:
        spot = spot[spot.open_time <= END]
        for a, b in _segments(spot.open_time):
            ia, ib = _pos(idx, [a, b])
            sp_in[ia:ib + 1] = True
            seg_start[ia:ib + 1] = ia
        p = _pos(idx, spot.open_time)
        sp_has[p] = True
        for c in cols:
            sp[c][p] = spot[c].to_numpy(float)

    # perpetual contracts: windows, values, mark
    pp_in, pp_has = np.zeros(n, bool), np.zeros(n, bool)
    pp = {c: np.full(n, np.nan) for c in cols}
    mk = {c: np.full(n, np.nan) for c in PX}
    windows = []
    for stem, k in perps:
        k = k[k.open_time <= END]
        w0, w1 = k.open_time.iloc[0], k.open_time.iloc[-1]
        windows.append((stem, w0, w1))
        i0, i1 = _pos(idx, [w0, w1])
        pp_in[i0:i1 + 1] = True
        p = _pos(idx, k.open_time)
        pp_has[p] = True
        for c in cols:
            pp[c][p] = k[c].to_numpy(float)
        m = _read("h1_mark", stem)
        if m is not None:                                    # trimmed to the contract's traded window (inv. 1.1)
            m = m[(m.open_time >= w0) & (m.open_time <= w1)]
            pm = _pos(idx, m.open_time)
            for c in PX:
                mk[c][pm] = m[c].to_numpy(float)

    def series(src_a, has_a, in_a, src_b, has_b, in_b):
        """values from market a inside its windows, else market b inside its windows, else filler."""
        use_a, use_b = in_a, ~in_a & in_b
        live = (use_a & has_a) | (use_b & has_b)
        out = {c: np.where(use_a, src_a[c], np.where(use_b, src_b[c], np.nan)) for c in cols}
        close = pd.Series(np.where(live, out["close"], np.nan)).ffill().to_numpy()
        for c in PX:
            out[c] = np.where(live, out[c], close)
        out["quote_volume"] = np.where(live, out["quote_volume"], 0.0)
        out["trades"] = np.where(live, out["trades"], 0.0)
        return out, live

    # Spot stands in for the traded series ("where a perpetual did not yet exist", per asset): inside a spot
    # segment, before a perpetual of the coin lists, and with no perpetual window ended since the segment began
    # (old LUNA spot after LUNAUSDT ended, FTT / EOS / MATIC spot after their last perpetual: not tradable).
    row = np.arange(n)
    perp_end = np.zeros(n, bool)
    if windows:
        w = np.array([_pos(idx, [a, b]) for _, a, b in windows])     # (k, 2) rows of [first, last] bar
        ends = np.sort(w[:, 1])
        k = np.searchsorted(ends, row, side="left")                   # windows ended strictly before the hour
        prev_end = np.where(k > 0, ends[np.maximum(k - 1, 0)], -1)
        stand_in = sp_in & ~pp_in & (row < w[:, 0].max()) & ((prev_end < 0) | (seg_start > prev_end))
        for _, _, b in windows:
            if b < END:
                perp_end[_pos(idx, [b])[0]] = True                    # contract delisted: forced close here
    else:
        stand_in = sp_in.copy()                                       # no perpetual at all (none in the data)

    tr, live = series(pp, pp_has, pp_in, sp, sp_has, stand_in)       # TRADED: perpetual, else spot stand-in
    sg, sig_live = series(sp, sp_has, sp_in, pp, pp_has, pp_in)      # SIGNAL: spot first
    df = pd.DataFrame({c: tr[c] for c in PX}, index=idx)
    df["trades"] = tr["trades"].astype(np.int64)
    df["quote_volume"] = tr["quote_volume"]
    df["is_perp"] = pp_in
    for c in PX:
        df["sig_" + c] = sg[c]
    df["sig_quote_volume"] = sg["quote_volume"]
    df["mark_open"], df["mark_high"], df["mark_low"], df["mark_close"] = mk["open"], mk["high"], mk["low"], mk["close"]

    # funding owed by a long held through the start of each hour
    fund = np.zeros(n)
    syn = stand_in.copy()                                             # spot stands in for a perpetual not yet listed
    if sym == "ICP":
        syn |= pp_in & (idx < ICP_FUNDING_FROM)                       # perpetual traded, funding archive starts later
    syn &= np.isin(idx.hour, (0, 8, 16))
    fund[syn] = FUND_SYN
    oct_fill = np.zeros(n, bool)
    for stem, w0, w1 in windows:
        f = _read("funding", stem)
        if f is None or f.empty:
            continue
        ft = f.calc_time.dt.floor("min")
        if (ft != ft.dt.floor("h")).any():
            raise ValueError(f"{stem}: funding print off the hour after flooring to the minute")
        keep = ((ft >= w0) & (ft <= w1)).to_numpy().copy()
        if sym == "ICP":
            keep &= (ft >= ICP_FUNDING_FROM).to_numpy()
        np.add.at(fund, _pos(idx, ft[keep]), f.rate.to_numpy(float)[keep])
        last = ft.iloc[-1]
        if w1 >= OCT_FROM and last < OCT_FROM:                        # no October 2026 prints in the archive
            sept = f.rate[((ft >= OCT_FROM - pd.DateOffset(months=1)) & (ft < OCT_FROM)).to_numpy()]
            iv = float(f.interval_h.iloc[-1])
            if len(sept) and np.isfinite(iv) and iv > 0:
                ts = pd.date_range(last + pd.Timedelta(hours=iv), w1, freq=pd.Timedelta(hours=iv)).as_unit("ns")
                ts = ts[ts >= OCT_FROM]
                p = _pos(idx, ts)
                fund[p] += float(np.median(sept.to_numpy(float)))
                oct_fill[p] = True
    df["funding"] = fund
    df["spot_only"] = stand_in
    df["tradable"] = pp_in | stand_in
    df["perp_end"] = perp_end
    df["live"] = live
    df["sig_live"] = sig_live
    # series breaks: a new segment at the first live signal hour after a hole of BREAK_H hours or more
    lp = np.flatnonzero(sig_live)
    start = np.zeros(n, np.int64)
    start[lp[1:][np.diff(lp) >= BREAK_H + 1]] = 1
    df["seg"] = np.cumsum(start).astype(np.int16)
    df["fund_synthetic"] = syn | oct_fill
    df.attrs = {}
    return df


def coin_hours(sym: str, start=None, end=None) -> pd.DataFrame:
    """One row per UTC hour (index open_time, datetime64[ns, UTC]) from the coin's first spot or perpetual hour to
    2026-10-16 23:00 UTC. Contract columns: open, high, low, close, trades (traded series), is_perp, sig_open,
    sig_high, sig_low, sig_close (signal series), mark_low, mark_high, funding, spot_only (spot stands in for a
    perpetual not yet listed: spot costs, synthetic funding). Extra columns: quote_volume, sig_quote_volume
    (USDT), mark_open, mark_close, tradable (= is_perp | spot_only: the traded series has a vehicle; False after
    a perpetual ended, where rows are filler with trades == 0), perp_end (last bar of a perpetual that delisted
    before 2026-10-16 23:00: the engine closes any open position at its close), live / sig_live (the row is a
    real bar of the market it reads; False = filler), seg (series segment, see the module docstring),
    fund_synthetic (the funding value is the 0.01%/8 h stand-in or the October 2026 carry-forward). See the
    module docstring for the series and funding rules. start / end: inclusive bounds on open_time; a date
    without a time means the whole day ('2026-10-16' ends at 2026-10-16 23:00), as pandas' string slicing."""
    df = _coin_hours_full(sym.upper())
    if start is not None or end is not None:
        df = df.loc[_utc(start):_utc_end(end)]
    return df.copy()


def _utc(t):
    """None, or a UTC Timestamp (naive input is read as UTC)."""
    if t is None:
        return None
    t = pd.Timestamp(t)
    return t.tz_localize("UTC") if t.tz is None else t.tz_convert("UTC")


_DATE_ONLY = {re.compile(r"^\d{4}-\d{2}-\d{2}$"): pd.DateOffset(days=1), re.compile(r"^\d{4}-\d{2}$"):
              pd.DateOffset(months=1), re.compile(r"^\d{4}$"): pd.DateOffset(years=1)}


def _utc_end(t):
    """Inclusive upper bound for an `end` argument: as _utc, except that a date without a time ('YYYY-MM-DD',
    'YYYY-MM', 'YYYY' strings, or a datetime.date that is not a datetime) covers that whole period, i.e. the
    bound is the period's end minus 1 ns (pandas' partial-string slicing)."""
    import datetime as _dt
    if t is None:
        return None
    if isinstance(t, str):
        s = t.strip()
        for rx, step in _DATE_ONLY.items():
            if rx.match(s):
                return _utc(s) + step - pd.Timedelta(1, "ns")
    elif isinstance(t, _dt.date) and not isinstance(t, _dt.datetime):
        return _utc(t) + pd.DateOffset(days=1) - pd.Timedelta(1, "ns")
    return _utc(t)


# ================================================================ bars
FREQ = {"1h": pd.Timedelta("1h"), "4h": pd.Timedelta("4h"), "1d": pd.Timedelta("1D"), "1w": pd.Timedelta("7D")}
_SERIES = {"sig": (SIG, "sig_quote_volume", "sig_live"), "traded": (PX, "quote_volume", "live")}


def _bar_key(t: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    if freq == "1h":
        return t
    if freq in ("4h", "1d"):
        return t.floor(freq.upper() if freq == "1d" else freq)      # UTC-aligned: 00/04/08/... and 00:00
    if freq == "1w":                                                 # Monday-labelled weeks (to_weekly)
        d = t.floor("D")
        return d - pd.to_timedelta(d.weekday, unit="D")
    raise ValueError(f"freq must be one of {list(FREQ)}")


def bars_from_hours(hours: pd.DataFrame, freq: str, series: str = "sig") -> pd.DataFrame:
    """Bars of `freq` ("1h", "4h", "1d", "1w") from a coin_hours-shaped frame (injected frames work too: missing
    live / volume / seg columns default to all-live, zero volume and one segment).
    Index = bar open time (UTC). Columns: open, high, low, close, quote_volume, n_hours (live hours in the bar),
    known_at (= open + period: the first hour at which the completed bar may be used), seg.
    Only live rows are aggregated (filler rows never move a bar), a bar with no live hour is dropped, and a bar
    straddling a series break keeps only the hours of its last segment."""
    if series not in _SERIES:
        raise ValueError("series must be 'sig' or 'traded'")
    if freq not in FREQ:
        raise ValueError(f"freq must be one of {list(FREQ)}")
    px, qv, lv = _SERIES[series]
    idx = pd.DatetimeIndex(hours.index)
    live = hours[lv].to_numpy(bool) if lv in hours else np.ones(len(hours), bool)
    x = pd.DataFrame({"open": hours[px[0]].to_numpy(float), "high": hours[px[1]].to_numpy(float),
                      "low": hours[px[2]].to_numpy(float), "close": hours[px[3]].to_numpy(float),
                      "quote_volume": hours[qv].to_numpy(float) if qv in hours else 0.0,
                      "seg": hours["seg"].to_numpy(np.int64) if "seg" in hours else 0}, index=idx)[live]
    key = _bar_key(pd.DatetimeIndex(x.index), freq)
    seg_last = x.seg.groupby(key).transform("last").to_numpy()
    keep = x.seg.to_numpy() == seg_last
    x, key = x[keep], key[keep]
    g = x.groupby(key)
    out = pd.DataFrame({"open": g.open.first(), "high": g.high.max(), "low": g.low.min(), "close": g.close.last(),
                        "quote_volume": g.quote_volume.sum(), "n_hours": g.size().astype(np.int64)})
    out.index = pd.DatetimeIndex(out.index).as_unit("ns")
    out.index.name = "open_time"
    out["known_at"] = out.index + FREQ[freq]
    out["seg"] = g.seg.last().to_numpy().astype(np.int16)
    return out


@lru_cache(maxsize=64)
def _bars_cached(sym: str, freq: str, series: str) -> pd.DataFrame:
    return bars_from_hours(_coin_hours_full(sym), freq, series)


def bars(sym: str, freq: str, series: str = "sig") -> pd.DataFrame:
    """bars_from_hours(coin_hours(sym), freq, series), cached. series "sig" (spot where spot trades, else the
    perpetual) or "traded" (the perpetual where it exists, else spot where it stands in; no bars after a
    delisted perpetual's last bar)."""
    return _bars_cached(sym.upper(), freq, series).copy()


# ================================================================ one-minute bars
def _decimals(tick: float) -> int:
    return int(round(-np.log10(tick)))


@lru_cache(maxsize=6)
def _minutes_full(sym: str) -> pd.DataFrame:
    if sym not in M1_COINS:
        raise ValueError(f"no 1-minute file for {sym}; M1_COINS = {M1_COINS}")
    m = _read("m1_um", sym)
    d = _decimals(M1_GRID[sym])
    out = pd.DataFrame({c: np.round(m[c].to_numpy(np.float64), d) for c in PX}, index=pd.DatetimeIndex(m.open_time))
    for c in ("volume", "quote_volume", "taker_buy_quote"):
        out[c] = m[c].to_numpy(np.float64)
    out["trades"] = m.trades.to_numpy(np.int64)
    out.index.name = "open_time"
    return out


def minutes(sym: str, start, end) -> pd.DataFrame:
    """1-minute USD-M bars of an M1 coin (2024-07-01 .. 2026-10-16 23:59 UTC), open_time in [start, end], prices
    rounded to M1_GRID (= TICK, except BTC at 0.01), which recovers every archive price exactly from the float32
    files (half a float32 step is below half the grid step at every price observed). start / end as in
    coin_hours (a date without a time covers the whole day: end='2026-10-16' keeps 23:59).
    Columns: open, high, low, close, volume, quote_volume, taker_buy_quote, trades (0 = outage minute)."""
    m = _minutes_full(sym.upper())
    a, b = _utc(start), _utc_end(end)
    i0, i1 = m.index.searchsorted(a, "left"), m.index.searchsorted(b, "right")
    return m.iloc[i0:i1].copy()


# ================================================================ New York clock, T-bills
def ny_clock(index) -> pd.DataFrame:
    """For each UTC timestamp: ny_hour (0-23 local), ny_date (local calendar date, tz-naive midnight), ny_weekday
    (Mon = 0), is_dst (US daylight time in force), us_open_utc (09:30 New York of that ny_date in UTC: 13:30 in
    EDT, 14:30 in EST). Conversions use the America/New_York tz database."""
    idx = pd.DatetimeIndex(index)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    loc = idx.tz_convert(NY)
    off = loc.tz_localize(None) - idx.tz_localize(None)
    ny_date = loc.tz_localize(None).normalize()
    us_open = (ny_date + pd.Timedelta(hours=9, minutes=30)).tz_localize(NY).tz_convert("UTC")
    return pd.DataFrame({"ny_hour": loc.hour.to_numpy(np.int64), "ny_date": ny_date,
                         "ny_weekday": loc.weekday.to_numpy(np.int64),
                         "is_dst": np.asarray(off == pd.Timedelta(hours=-4), dtype=bool),
                         "us_open_utc": us_open}, index=index)


def _rf_pct(index) -> np.ndarray:
    from analysis_2026.regime_switch import rf_annual_pct
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    return rf_annual_pct(idx.normalize().as_unit("ns"))


def tbill_daily(index) -> np.ndarray:
    """Simple T-bill interest per UTC calendar day (365-day basis) from regime_switch.rf_annual_pct: the 3-month
    T-bill in force on each day's UTC date / 100 / 365."""
    return _rf_pct(index) / 100.0 / 365.0


def tbill_session(index) -> np.ndarray:
    """Simple T-bill interest per stock session (252 basis): rf_annual_pct of the session date / 100 / 252."""
    return _rf_pct(index) / 100.0 / 252.0


# ================================================================ S12: every USDT perpetual (daily klines)
ALL_DIR = DATA / "d1_um_all"
ALL_START_MONTH = "2020-01"
_MULT_RE = re.compile(r"^(1000000|1000|1M)(?=[A-Z])")
_MULT = {"1000000": 1_000_000, "1000": 1000, "1M": 1_000_000}
# Excluded from the ranking pool (pre-registration S12): stablecoin-vs-stablecoin and Binance index contracts.
# (USTC, TerraClassicUSD, is a depegged stablecoin; the others in the set are not listed as USDT perpetuals in
# the archive but are kept for completeness.)
STABLE_EXCLUDE = {"USDC", "USTC", "BUSD", "TUSD", "FDUSD", "USDP", "DAI", "USDE", "PYUSD", "USD1", "RLUSD", "EUR",
                  "AEUR", "EURI"}
INDEX_EXCLUDE = {"BTCDOM", "DEFI", "BLUEBIRD", "FOOTBALL", "DOTECO"}  # Binance's composite-index perpetuals
# TradFi perpetuals (stocks, ETFs, pre-IPO shares, metals, energy, FX), all listed from 2025-12 on; classified by
# name and listing date [U]. They are USDT-margined USD-M perpetuals and are neither stablecoin nor index
# contracts, so the literal S12 pool keeps them (default); volume_ranks("all", tradfi=False) drops them.
TRADFI = set("""
AAOI AAPL ACN ADBE AKAM ALAB AMAT AMC AMD AMZN ANET APLD APP ARM ASML ASTS AVGO AXTI BABA BE BMNR BRKB BYD CBRS
CIEN COHR COIN COST CRCL CRDO CRM CRML CRWD CRWV CSCO CVNA DDOG DELL DIS DJT DKNG EBAY FLNC FWDI GEV GLW GME
GOOGL GPRO GS GTLB HD HIMS HOOD HPE HUT IBM INTC INTW IONQ IREN JPM KLAC KO LITE LLY LRCX MARA MCD MDB META MP
MRK MRNA MRVL MSFT MSTR MU NBIS NET NFLX NKE NOK NOW NVDA NVO OKLO ONDS ORCL PANW PATH PDD PLTR PYPL QCOM RDDT
RDW RIVN RKLB SHOP SMCI SNDK SNOW SNPS SOFI SONY TEM TSLA TSM TTWO TWST TXN UBER UNH USAR VKTX WDC WMT XOM ZM ZS
SAMSUNG SAMSUNGEM SKHYNIX HYUNDAI NAVER HANMI LGELECTRONICS KODEX200 HK0625 HK0700 HK0992 HK1810 MEITUAN TENCENT
KUAISHOU POPMART CXMT ZHIPU MINIMAX UNITREE ZHONGJI ANTHROPIC OPENAI SPCX SKHY
SPY QQQ IWM SMH XBI XLE EWJ EWY EWZ GDX URNM SOXL SOXS TQQQ SQQQ TZA TMF TBT UVXY TSLL NVDL MSTU KORU
CSOPSAMSUNG2L CSOPSKHYNIX2L BITO SKUU SNXX STXX MUU DRAM
XAU XAG XPD XPT NATGAS COPPER CL BZ USDBRL
""".split())
COIN_OF_CONTRACT = {"LUNA2USDT": "LUNA"}                  # Terra 2.0 perpetual = the 40's LUNA after 2022-05-31


def contract_coin(contract: str) -> tuple[str, int]:
    """(coin, units per contract price) for a USDT perpetual: 1000PEPEUSDT -> ("PEPE", 1000),
    1MBABYDOGEUSDT -> ("BABYDOGE", 10**6), LUNA2USDT -> ("LUNA", 1), BTCUSDT -> ("BTC", 1)."""
    if contract in COIN_OF_CONTRACT:
        return COIN_OF_CONTRACT[contract], 1
    base = contract.removesuffix("USDT")
    m = _MULT_RE.match(base)
    if m:
        return base[m.end():], _MULT[m.group(1)]
    return base, 1


# Keep-alive HTTP (one requests.Session per thread): about 0.2 s per archive request instead of 0.6 s with
# fetch_scalping_data.get, which opens a new proxy tunnel each time. Same checksum rules as fetch_bb_data.
_TLS = threading.local()


def _session():
    if not hasattr(_TLS, "s"):
        import requests
        _TLS.s = requests.Session()
    return _TLS.s


def _http_get(url: str, timeout=120) -> bytes | None:
    err = None
    for k in range(4):
        try:
            r = _session().get(url, timeout=timeout)
            if r.status_code in (403, 404):
                return None
            r.raise_for_status()
            return r.content
        except Exception as e:                                # network error: back off and retry
            err = e
            time.sleep(1 + 2 * k)
    raise IOError(f"GET failed {url}: {err!r}")


def _ls(prefix: str, delimiter: str = "/"):
    """fetch_scalping_data.s3_ls over the keep-alive session."""
    import urllib.parse
    import xml.etree.ElementTree as ET
    from analysis_2026.fetch_scalping_data import NS, S3
    marker, prefixes, keys = "", [], []
    while True:
        q = {"prefix": prefix, "delimiter": delimiter}
        if marker:
            q["marker"] = marker
        root = ET.fromstring(_http_get(S3 + "?" + urllib.parse.urlencode(q), 60))
        cp = [e.find(NS + "Prefix").text for e in root.findall(NS + "CommonPrefixes")]
        ks = [(e.find(NS + "Key").text, int(e.find(NS + "Size").text)) for e in root.findall(NS + "Contents")]
        prefixes += cp; keys += ks
        if root.find(NS + "IsTruncated").text != "true":
            return prefixes, keys
        nm = root.find(NS + "NextMarker")
        marker = nm.text if nm is not None else (ks[-1][0] if ks else cp[-1])


def _fetch_zip(job):
    """fetch_bb_data._fetch over the keep-alive session: (key, has_sum, csv bytes | None, sha256 compared, error).
    A checksum mismatch, or an unreadable .CHECKSUM that the listing shows, is retried and then reported."""
    import hashlib
    import io
    import urllib.parse
    import zipfile
    from analysis_2026.fetch_scalping_data import S3
    key, need_sum = job
    err = None
    for _ in range(3):
        try:
            q = urllib.parse.quote(key)
            b = _http_get(f"{S3}/{q}")
            if b is None:
                return key, need_sum, None, False, None
            c = _http_get(f"{S3}/{q}.CHECKSUM", 60)
            if c is None and need_sum:
                raise IOError(f"checksum file unreadable {key}")
            if c is not None and c.decode().split()[0] != hashlib.sha256(b).hexdigest():
                raise IOError(f"checksum mismatch {key}")
            z = zipfile.ZipFile(io.BytesIO(b))
            return key, need_sum, z.read(z.namelist()[0]), c is not None, None
        except Exception as e:
            err = repr(e)
    return key, need_sum, None, False, err


def coin_map(contracts) -> dict[str, tuple[str, int]]:
    """contract -> (coin, mult) for a set of contracts: contract_coin, except that a multiplier contract whose
    base is also traded as a plain contract keeps its own name, because the two are different assets in the
    archive (1000CATUSDT, Simon's Cat, vs CATUSDT, from 2026-07, 4e8 x the price per unit; 1000000BOBUSDT vs
    BOBUSDT likewise)."""
    contracts = list(contracts)
    plain = {c.removesuffix("USDT") for c in contracts if contract_coin(c)[1] == 1}
    out = {}
    for c in contracts:
        coin, mult = contract_coin(c)
        if mult != 1 and coin in plain:
            coin = c.removesuffix("USDT")
        out[c] = (coin, mult)
    return out


def um_contracts() -> list[str]:
    """Every USDT-margined perpetual in the archive's USD-M kline listings (monthly or daily), delivery contracts
    (names with '_') and USDC-margined contracts left out."""
    names = set()
    for freq in ("monthly", "daily"):
        p, _ = _ls(f"data/futures/um/{freq}/klines/")
        names |= {x.rstrip("/").split("/")[-1] for x in p}
    return sorted(s for s in names if s.endswith("USDT") and "_" not in s)


def _keys_any(contract: str, interval: str, end: str = END_DAY, start_month: str | None = ALL_START_MONTH):
    """Like fetch_bb_data._keys for klines, but also covers a contract with no monthly file yet (listed in the
    last two months): its daily files for END's month and the month before."""
    sub = f"klines/{contract}/{interval}/"
    _, mk = _ls(f"data/futures/um/monthly/{sub}")
    names = {k for k, _ in mk}
    em = end[:7]
    out = [(k, k + ".CHECKSUM" in names) for k in sorted(names) if k.endswith(".zip")
           and k[-11:-4] < em and (start_month is None or k[-11:-4] >= start_month)]
    monthly_any = any(k.endswith(".zip") for k in names)
    if out:
        months, m = [], fbd._next_month(max(k[-11:-4] for k, _ in out))
        while m <= em:
            months.append(m); m = fbd._next_month(m)
        months = months if len(months) <= 2 else []
    elif not monthly_any:
        y, mo = int(em[:4]), int(em[5:7])
        months = [f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}", em]
    else:
        months = []                                           # monthly files exist but all before start_month
    for mo in months:
        _, dk = _ls(f"data/futures/um/daily/{sub}{contract}-{interval}-{mo}")
        dn = {k for k, _ in dk}
        out += [(k, k + ".CHECKSUM" in dn) for k in sorted(dn) if k.endswith(".zip") and k[-14:-4] <= end]
    return out


def _klines_one(contract: str, interval: str, end: str = END_DAY, start_month=ALL_START_MONTH,
                max_hole_days: int = 31) -> tuple[pd.DataFrame | None, dict]:
    """One USD-M kline series, sequential downloads (the caller parallelises across contracts): checksummed
    zips, off-grid bars dropped, holes filled from daily zips when at most `max_hole_days` days are missing,
    duplicates dropped, leading / trailing zero-trade placeholder bars trimmed. Prices unscaled."""
    st = {"contract": contract}
    jobs = _keys_any(contract, interval, end, start_month)
    st["zips"], st["with_checksum"] = len(jobs), sum(h for _, h in jobs)
    res = [_fetch_zip(j) for j in jobs]
    st["failed"] = [f"{k}: {e or 'missing'}" for k, _, b, _, e in res if b is None]
    st["verified"] = sum(ok for _, _, b, ok, _ in res if b is not None)
    blobs = [(k, b) for k, _, b, _, _ in res if b is not None]
    if not blobs:
        return None, st
    k = fbd._frame(blobs)
    on = (k.open_time.dt.floor(fbd.STEP[interval]) == k.open_time).to_numpy()
    st["off_grid_dropped"] = int((~on).sum())
    k = k[on]
    full = pd.date_range(k.open_time.min(), k.open_time.max(), freq=fbd.STEP[interval])
    miss = full.difference(pd.DatetimeIndex(k.open_time))
    days = sorted(set(miss.normalize()))
    st["hole_days"] = len(days)
    if 0 < len(days) <= max_hole_days:
        keys = [f"data/futures/um/daily/klines/{contract}/{interval}/{contract}-{interval}-{d:%Y-%m-%d}.zip"
                for d in days]
        got = [_fetch_zip((key, False)) for key in keys]
        add = [(key, b) for key, _, b, _, _ in got if b is not None]
        st["hole_days_found"] = len(add)
        if add:
            a = fbd._frame(add)
            a = a[a.open_time.isin(miss)]
            st["hole_bars_filled"] = len(a)
            k = pd.concat([k, a], ignore_index=True)
    elif len(days) > max_hole_days:
        st["holes_not_filled"] = len(days)
    k = k.sort_values("open_time", kind="stable")
    st["duplicates_dropped"] = int(k.open_time.duplicated().sum())
    k = fbd._typed(k.drop_duplicates("open_time", keep="last").reset_index(drop=True))
    live = (k.trades > 0).to_numpy()
    if not live.any():
        st["all_zero_trade"] = True
        return None, st
    i0, i1 = int(live.argmax()), len(live) - int(live[::-1].argmax())
    st["placeholder_trimmed_head"], st["placeholder_trimmed_tail"] = i0, len(k) - i1
    k = k.iloc[i0:i1].reset_index(drop=True)
    st.update(rows=len(k), first=str(k.open_time.iloc[0]), last=str(k.open_time.iloc[-1]))
    return k, st


_LOCK = threading.Lock()


def _status(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def fetch_d1_all(workers: int = MAX_WORKERS, force: bool = False, contracts: list[str] | None = None) -> dict:
    """S12 data: the archive's 1d klines (2020-01 .. 2026-10-16; monthly zips, daily zips for October 2026) of
    every USDT perpetual, to data/bbreplica/d1_um_all/{CONTRACT}.parquet (raw contract prices; quote volume in
    USDT). Resumable: a contract with a parquet file or a recorded 'no data' status is skipped unless force.
    Status per contract in d1_um_all/_status.json."""
    workers = min(workers, MAX_WORKERS)
    ALL_DIR.mkdir(parents=True, exist_ok=True)
    sp = ALL_DIR / "_status.json"
    status = _status(sp)
    if contracts is None:                                     # a full run records the archive listing
        contracts = um_contracts()
        status["_listing"] = {"contracts": len(contracts), "names": contracts,
                              "listed_at": str(pd.Timestamp.now(tz="UTC"))}
    todo = [c for c in contracts if force or not ((ALL_DIR / f"{c}.parquet").exists()
                                                   or status.get(c, {}).get("result") == "no data")]
    print(f"d1_um_all: {len(contracts)} contracts, {len(todo)} to fetch", flush=True)
    done = [0]
    t0 = time.time()

    def one(c):
        try:
            k, st = _klines_one(c, "1d")
        except Exception as e:                                # network error after retries: record, retry later
            k, st = None, {"contract": c, "error": repr(e)}
        if k is not None:
            k.to_parquet(ALL_DIR / f"{c}.parquet", index=False)
            st["result"] = "ok"
        elif "error" not in st and not st.get("failed"):
            st["result"] = "no data"
        else:
            st["result"] = "failed"
        with _LOCK:
            status[c] = st
            done[0] += 1
            if done[0] % 50 == 0 or done[0] == len(todo):
                sp.write_text(json.dumps(status, indent=1, default=str))
                print(f"  {done[0]}/{len(todo)} contracts, {time.time() - t0:.0f}s", flush=True)

    with cf.ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    sp.write_text(json.dumps(status, indent=1, default=str))
    return status


# ================================================================ S12 volume ranks
RANK_DAYS = 90
TOP_N = 10
DAY = pd.Timedelta("1D")


def _rank_months(qv: pd.DataFrame, live: pd.DataFrame, months, seg: pd.DataFrame | None = None,
                 top: int = TOP_N) -> pd.DataFrame:
    """Point-in-time ranks. qv, live (and seg): UTC day x coin. For month start M, the coins with live[M - 1 day]
    are ranked by the sum of qv over the RANK_DAYS days M - 90 d .. M - 1 d (only days in the same segment as
    day M - 1 when seg is given), largest first, ties alphabetical. Rows: months; columns 1..top (missing, i.e.
    NaN in pandas 3's str dtype, when fewer coins are live)."""
    days = pd.DatetimeIndex(qv.index)
    q_all = qv.to_numpy(float)
    lv_all = live.to_numpy(bool)
    sg_all = None if seg is None else seg.to_numpy(float)
    names = np.array(qv.columns, dtype=object)
    rows = []
    for M in pd.DatetimeIndex(months):
        prior = M - DAY
        j = days.searchsorted(prior)
        if j >= len(days) or days[j] != prior:
            rows.append([None] * top); continue
        i0 = days.searchsorted(M - RANK_DAYS * DAY)
        q = np.nan_to_num(q_all[i0:j + 1])
        if sg_all is not None:
            q = np.where(sg_all[i0:j + 1] == sg_all[j], q, 0.0)
        tot = q.sum(axis=0)
        ok = np.flatnonzero(lv_all[j])
        order = sorted(ok, key=lambda c: (-tot[c], names[c]))[:top]
        rows.append([names[c] for c in order] + [None] * (top - len(order)))
    out = pd.DataFrame(rows, index=pd.DatetimeIndex(months, name="month"), columns=range(1, top + 1))
    return out


def _months(first_day: pd.Timestamp, last_month="2026-10-01") -> pd.DatetimeIndex:
    """Month starts after the month of first_day, to last_month."""
    m0 = pd.Timestamp(year=first_day.year, month=first_day.month, day=1, tz="UTC") + pd.DateOffset(months=1)
    return pd.date_range(m0, pd.Timestamp(last_month, tz="UTC"), freq="MS").as_unit("ns")


@lru_cache(maxsize=1)
def _pool40_daily():
    """Daily traded-series quote volume (perpetual where it trades, spot before), trades and segment per coin."""
    qv, tr, sg = {}, {}, {}
    for c in COINS:
        h = _coin_hours_full.__wrapped__(c)                    # not cached: 40 full frames would hold ~0.6 GB
        x = h[h.live]
        d = x.index.floor("D")
        g = x.groupby(d)
        qv[c], tr[c], sg[c] = g.quote_volume.sum(), g.trades.sum(), g.seg.last()
    qv, tr, sg = pd.DataFrame(qv).sort_index(), pd.DataFrame(tr).sort_index(), pd.DataFrame(sg).sort_index()
    full = pd.date_range(qv.index[0], qv.index[-1], freq="D").as_unit("ns")
    return qv.reindex(full), tr.reindex(full).fillna(0) > 0, sg.reindex(full)


def all_contracts_table() -> pd.DataFrame:
    """One row per USDT perpetual found in the archive listing: contract, coin, mult, excluded (reason or ''),
    fetch result, rows, first, last (from d1_um_all/_status.json and the parquet files)."""
    st = _status(ALL_DIR / "_status.json")
    rows = []
    cmap = coin_map(k for k in st if not k.startswith("_"))
    for c in sorted(cmap):
        coin, mult = cmap[c]
        ex = "stablecoin" if coin in STABLE_EXCLUDE else "index" if coin in INDEX_EXCLUDE else ""
        s = st[c]
        rows.append({"contract": c, "coin": coin, "mult": mult, "excluded": ex, "tradfi": coin in TRADFI,
                     "result": s.get("result"),
                     "rows": s.get("rows", 0), "first": s.get("first"), "last": s.get("last"),
                     "failed": len(s.get("failed", [])) + ("error" in s)})
    return pd.DataFrame(rows)


@lru_cache(maxsize=2)
def _poolall_daily(tradfi: bool = True):
    st = _status(ALL_DIR / "_status.json")
    if not st or "_listing" not in st:
        raise RuntimeError(f"S12 all-contract ranking cannot be built: {ALL_DIR}/_status.json missing; run "
                           "`python3 -m analysis_2026.bb_data fetch-all`")
    listed = st["_listing"].get("names", [])
    have = [k for k in st if not k.startswith("_")]
    bad = sorted(set(k for k in have if st[k].get("result") not in ("ok", "no data")) | (set(listed) - set(have)))
    if not listed or bad:
        raise RuntimeError(f"S12 all-contract ranking cannot be built: {len(have)} of {len(listed)} listed "
                           f"contracts fetched; missing or failed: {bad[:20]}{' ...' if len(bad) > 20 else ''}")
    qv, tr = {}, {}
    cmap = coin_map(have)
    for c in sorted(have):
        if st[c].get("result") != "ok":
            continue
        coin, _ = cmap[c]
        if coin in STABLE_EXCLUDE or coin in INDEX_EXCLUDE or (not tradfi and coin in TRADFI):
            continue
        k = pd.read_parquet(ALL_DIR / f"{c}.parquet", columns=["open_time", "quote_volume", "trades"])
        s_q = pd.Series(k.quote_volume.to_numpy(float), index=pd.DatetimeIndex(k.open_time).as_unit("ns"))
        s_t = pd.Series(k.trades.to_numpy(float), index=s_q.index)
        qv[coin] = s_q if coin not in qv else qv[coin].add(s_q, fill_value=0.0)   # concurrent contracts summed
        tr[coin] = s_t if coin not in tr else tr[coin].add(s_t, fill_value=0.0)
    qv, tr = pd.DataFrame(qv).sort_index(), pd.DataFrame(tr).sort_index()
    full = pd.date_range(qv.index[0], qv.index[-1], freq="D").as_unit("ns")
    return qv.reindex(full), tr.reindex(full).fillna(0) > 0


def volume_ranks(pool: str = "40", tradfi: bool = True) -> pd.DataFrame:
    """S12 monthly point-in-time top 10. Rows = month start (1st of the month, 00:00 UTC); columns 1..10 = coin
    names (missing where fewer coins were live), ranked by quote volume over the 90 days to the prior day.
    pool "40": the 40 coins, coin_hours' traded series (perpetual where it trades, spot before), months
    2017-09 .. 2026-10, volume counted only within the series segment live on the prior day (LUNA, FTT).
    pool "all": every Binance USDT perpetual in the archive's daily USD-M klines (d1_um_all/), stablecoin and
    index contracts excluded, contracts mapped to coins (contract_coin), months 2020-02 .. 2026-10; TradFi
    perpetuals are kept (the literal pool) unless tradfi=False. Raises a RuntimeError saying why if the
    all-contract data are incomplete."""
    if pool == "40":
        qv, live, sg = _pool40_daily()
        return _rank_months(qv, live, _months(qv.index[0]), seg=sg)
    if pool == "all":
        qv, live = _poolall_daily(bool(tradfi))
        return _rank_months(qv, live, _months(qv.index[0]))
    raise ValueError("pool must be '40' or 'all'")


def s12_entrants(tradfi: bool | None = None) -> list[str]:
    """Coins that enter a monthly all-contract top 10 and are outside the 40 (they get hourly, mark and funding
    files under the same layout via fetch_entrants). tradfi True / False: that variant of the pool; None: the
    union of both."""
    variants = (True, False) if tradfi is None else (bool(tradfi),)
    seen = set()
    for v in variants:
        seen |= {x for x in volume_ranks("all", v).to_numpy().ravel() if isinstance(x, str)}
    return sorted(c for c in seen if c not in COINS)


def entrant_contracts(coin: str) -> list[tuple[str, int]]:
    """(contract, mult) of every USDT perpetual mapped to `coin`, in listing order."""
    t = all_contracts_table()
    t = t[(t.coin == coin) & (t.result == "ok")].sort_values("first")
    return list(zip(t.contract, t.mult))


def fetch_entrants(workers: int = MAX_WORKERS, force: bool = False) -> dict:
    """Hourly perpetual klines (h1_um/ and the d1_um/ reference), mark-price klines (h1_mark/) and funding
    (funding/) for every S12 entrant outside the 40, written as {COIN}USDT.parquet with fetch_bb_data's own
    h1 / mark / funding code (1000x contracts rescaled to one coin, as SHIB). fetch_bb_data.py is imported, not
    edited: its contract map is extended in this process only."""
    workers = min(workers, MAX_WORKERS)
    ent = s12_entrants()                                      # both pool variants (TradFi kept / dropped)
    report = {"entrants": ent, "multi_contract": {}, "missing": []}
    fbd.get, fbd.s3_ls = _http_get, _ls                       # keep-alive HTTP for fetch_bb_data, this process only
    for coin in ent:
        cs = entrant_contracts(coin)
        if len(cs) > 1:
            report["multi_contract"][coin] = cs
        contract, mult = cs[-1] if cs else (f"{coin}USDT", 1)
        fbd.UM_CONTRACT[coin] = (contract, mult)
    fbd.h1(ent, END_DAY, force, workers, markets=("um",))
    fbd.funding(ent, END_DAY, force, workers)
    fbd.mark(ent, END_DAY, force, workers)
    report["spot"] = fetch_entrant_spot(ent, workers, force)
    for coin in ent:
        for kind in ("h1_um", "funding", "h1_mark"):
            if not (DATA / kind / f"{coin}USDT.parquet").exists():
                report["missing"].append(f"{kind}/{coin}")
        if coin in report["spot"]["pairs"] and not (DATA / "h1_spot" / f"{coin}USDT.parquet").exists():
            report["missing"].append(f"h1_spot/{coin}")
    (ALL_DIR / "_entrants.json").write_text(json.dumps(report, indent=1, default=str))
    return report


def spot_basis(coin: str) -> dict:
    """Same-asset check of a coin's spot and perpetual hourly files: median and 99th percentile of
    |spot close / perp close - 1| over the hours both trade (trades > 0), and the number of such hours."""
    s, p = _read("h1_spot", coin), _read("h1_um", perp_files(coin)[-1])
    j = s[s.trades > 0].set_index("open_time").close.to_frame("s").join(
        p[p.trades > 0].set_index("open_time").close.rename("p"), how="inner")
    r = (j.s / j.p - 1).abs()
    return {"hours": len(j), "median": float(r.median()) if len(j) else np.nan,
            "p99": float(r.quantile(0.99)) if len(j) else np.nan}


def fetch_entrant_spot(ent=None, workers: int = MAX_WORKERS, force: bool = False) -> dict:
    """h1_spot/ and d1_spot/ {COIN}USDT.parquet for the S12 entrants that Binance spot lists (R0 Signal row:
    signals on spot where spot trades): the spot pair is {COIN}USDT or SPOT_PAIR[coin] (1000SATSUSDT, rescaled
    to one coin), found in the archive's spot kline listing (monthly or daily). Same code as fetch_bb_data.h1:
    the 1d series first as the reference, then the 1h series cross-checked against it. Each fetched pair is
    checked against the coin's perpetual (spot_basis); a pair whose median basis exceeds 1% is not the same
    asset and its files are removed."""
    workers = min(workers, MAX_WORKERS)
    ent = s12_entrants() if ent is None else list(ent)
    fbd.get, fbd.s3_ls = _http_get, _ls
    listed = set()
    for freq in ("monthly", "daily"):
        p, _ = _ls(f"data/spot/{freq}/klines/")
        listed |= {x.rstrip("/").split("/")[-1] for x in p}
    pairs = {c: SPOT_PAIR.get(c, (f"{c}USDT", 1)) for c in ent if SPOT_PAIR.get(c, (f"{c}USDT", 1))[0] in listed}
    out = {"pairs": {c: v[0] for c, v in pairs.items()}, "basis": {}, "rejected": [], "no_data": []}
    stats = {}
    for d in ("h1_spot", "d1_spot"):
        (DATA / d).mkdir(parents=True, exist_ok=True)
    for coin, (pair, mult) in sorted(pairs.items()):
        f, fd = DATA / "h1_spot" / f"{coin}USDT.parquet", DATA / "d1_spot" / f"{coin}USDT.parquet"
        if not f.exists() or force:
            d1, st1 = fbd.klines("spot", pair, "1d", END_DAY, workers=workers)       # reference, unscaled
            st1["contract"], st1["mult"] = pair, mult
            stats[f"d1/spot/{coin}"] = st1
            ref = None
            if d1 is not None:
                fbd._scale(d1, mult).to_parquet(fd, index=False)
                ref = d1.set_index("open_time")
            k, st = fbd.klines("spot", pair, "1h", END_DAY, workers=workers, mult=mult, ref=ref)
            st["contract"], st["mult"] = pair, mult
            stats[f"spot/{coin}"] = st
            if k is None:
                out["no_data"].append(coin); continue
            k.to_parquet(f, index=False)
            print(f"h1 spot {coin:6s} ({pair}) {len(k):7,d} bars {st['first'][:10]}..{st['last'][:16]} zips "
                  f"{st['zips']} verified {st['verified']} failed {len(st['failed'])} repaired "
                  f"{st['ref_days_repaired']} unresolved {st['ref_days_unresolved']}", flush=True)
        b = spot_basis(coin)
        out["basis"][coin] = b
        if not b["hours"] or b["median"] > 0.01:
            out["rejected"].append(coin)
            f.unlink(missing_ok=True); fd.unlink(missing_ok=True)
    if stats:
        old = fbd._load_stats("h1"); old.update(stats); fbd._save_stats("h1", old)
    _coin_hours_full.cache_clear(); _bars_cached.cache_clear()
    return out


# ================================================================ TICK inference (the literal TICK dict is its output)
TICK_FROM = pd.Timestamp("2024-07-01", tz="UTC")


def _coarsest_grid(p: np.ndarray, tol: np.ndarray) -> float:
    """The largest power of ten g with |p - round(p / g) * g| <= tol for every price p."""
    for k in range(4, -13, -1):
        g = 10.0 ** k
        if np.all(np.abs(p - np.round(p / g) * g) <= tol):
            return g
    return 1e-12


def infer_tick(sym: str) -> dict:
    """The perpetual's price tick from its own bars (no exchangeInfo is reachable from here). Prices of the coin's
    last contract's hourly file from 2024-07-01 (the whole file if the contract ended before): tick = the
    largest power of ten whose grid holds every one of them, i.e. the smallest increment observed rounded to a
    power of ten (min_gap is reported beside it; a contract whose tick was refined as its price fell, such as
    DOT and FIL in 2026, gets the finer tick). For an M1 coin also the coarsest power-of-ten grid that recovers
    every float32 1-minute price exactly (m1_grid; minutes() rounds to it). It equals the tick except for BTC:
    the 1m archive prints four prices off BTC's 0.1 tick (2024-08-06 03:45 high 55674.17, 17:49 low 56581.51,
    23:42 high 55944.83, 2024-08-07 22:46 close 55181.35; three checked against the raw monthly zip), so BTC's
    minutes are rounded to 0.01."""
    k = _read("h1_um", perp_files(sym)[-1])
    span = k[k.open_time >= TICK_FROM]
    if len(span) < 1000:
        span = k
    p = np.unique(span[PX].to_numpy(np.float64).ravel())
    tick = _coarsest_grid(p, 1e-9 * np.abs(p))                # float64 parse error is ~1e-16 relative
    out = {"sym": sym, "from": str(span.open_time.iloc[0])[:10], "min_gap": float(np.min(np.diff(p))),
           "tick": tick, "prices": len(p)}
    if sym in M1_COINS:
        m = _read("m1_um", sym, columns=PX)
        q32 = np.unique(m.to_numpy(np.float32).ravel())
        q = q32.astype(np.float64)
        tol = np.spacing(q32).astype(np.float64) / 2 + 1e-12 * q      # half a float32 step
        out["m1_grid"] = _coarsest_grid(q, tol)
        out["m1_off_tick"] = int(np.sum(np.abs(q - np.round(q / tick) * tick) > tol))
    return out


# ================================================================ self-test
def _check_coin_hours(sym: str, say) -> None:
    h = coin_hours(sym)
    idx = h.index
    spot = _read("h1_spot", sym)
    perps = [(s, _read("h1_um", s)) for s in perp_files(sym)]
    first = min(([spot.open_time.iloc[0]] if spot is not None else []) + [k.open_time.iloc[0] for _, k in perps])
    assert idx.is_monotonic_increasing and idx.is_unique, sym
    assert (np.diff(idx.asi8) == H.value).all() and idx[0] == first and idx[-1] == END, sym
    assert str(idx.dtype) == "datetime64[ns, UTC]", idx.dtype
    for c in PX + SIG:
        assert h[c].notna().all(), (sym, c)
    for a, b, lo, hi in ((h.open, h.close, h.low, h.high), (h.sig_open, h.sig_close, h.sig_low, h.sig_high)):
        assert ((hi >= np.maximum(a, b) - 1e-12) & (lo <= np.minimum(a, b) + 1e-12)).all(), sym
    # filler rows: no trades, flat at the previous close of the same series
    for px, lv in ((PX, "live"), (SIG, "sig_live")):
        f = ~h[lv].to_numpy()
        prev = h[px[3]].shift(1).to_numpy()
        for c in px:
            assert np.allclose(h[c].to_numpy()[f][1:], prev[f][1:], rtol=0, atol=0) or not f[1:].any(), (sym, c)
    assert (h.trades[~h.live] == 0).all() and (h.quote_volume[~h.live] == 0).all()
    # traded series = perpetual inside its windows, spot elsewhere; values equal the files
    win = np.zeros(len(h), bool)
    for stem, k in perps:
        w = (idx >= k.open_time.iloc[0]) & (idx <= k.open_time.iloc[-1])
        win |= w
        j = h.loc[pd.DatetimeIndex(k.open_time)]
        assert j.is_perp.all() and j.live.all(), sym
        for c in PX + ["trades", "quote_volume"]:
            assert np.array_equal(j[c].to_numpy(float), k[c].to_numpy(float)), (sym, stem, c)
        m = _read("h1_mark", stem)
        inside = m[(m.open_time >= k.open_time.iloc[0]) & (m.open_time <= k.open_time.iloc[-1])]
        hm = h.loc[w, "mark_low"]
        assert hm.notna().sum() == len(inside), (sym, "mark rows")
        assert np.array_equal(h.loc[pd.DatetimeIndex(inside.open_time), "mark_low"].to_numpy(), inside.low.to_numpy())
        outside = len(m) - len(inside)
        say(f"  {sym}/{stem}: perp {k.open_time.iloc[0]:%Y-%m-%d %H}h..{k.open_time.iloc[-1]:%Y-%m-%d %H}h, "
            f"{(w & ~h.live.to_numpy()).sum()} filler hours inside; mark rows kept {len(inside)}, trimmed {outside}")
    assert np.array_equal(h.is_perp.to_numpy(), win), sym
    sp_only = h.spot_only.to_numpy()
    assert not (sp_only & win).any() and np.array_equal(h.tradable.to_numpy(), win | sp_only), sym
    starts = [k.open_time.iloc[0] for _, k in perps]
    assert (idx[sp_only] < max(starts)).all(), (sym, "spot stands in only before a perpetual lists")
    assert (h.trades[~h.tradable] == 0).all() and not h.live[~h.tradable].any(), sym
    assert h.mark_low[~h.is_perp].isna().all() and h.mark_high[~h.is_perp].isna().all(), sym
    if spot is not None:
        segs = _segments(spot.open_time)
        sin = np.zeros(len(h), bool)
        for a, b in segs:
            sin |= (idx >= a) & (idx <= b)
        js = h.loc[pd.DatetimeIndex(spot.open_time)]
        for c in PX:
            assert np.array_equal(js["sig_" + c].to_numpy(), spot[c].to_numpy()), (sym, "sig", c)
        ts = js[js.spot_only]
        sp_ts = spot.set_index("open_time").loc[ts.index]
        assert np.array_equal(ts.close.to_numpy(), sp_ts.close.to_numpy()), (sym, "spot traded")
        assert h.sig_live.sum() == len(spot) + sum(int(((k.open_time.isin(idx[~sin])).sum())) for _, k in perps)
        assert h.seg.max() == len(segs) - 1, (sym, "segments")
    # funding: real prints, synthetic stand-ins, October 2026
    real = np.zeros(len(h))
    for stem, k in perps:
        f = _read("funding", stem)
        ft = f.calc_time.dt.floor("min")
        keep = (ft >= k.open_time.iloc[0]) & (ft <= k.open_time.iloc[-1])
        if sym == "ICP":
            keep &= ft >= ICP_FUNDING_FROM
        np.add.at(real, _pos(idx, ft[keep]), f.rate[keep].to_numpy())
        dropped = int((~keep).sum())
        say(f"  {sym}/{stem}: funding prints used {int(keep.sum())}, outside the window {dropped}, "
            f"sum {f.rate[keep].sum():+.6f}")
    syn = h.fund_synthetic.to_numpy()
    assert np.allclose(h.funding.to_numpy()[~syn], real[~syn], rtol=0, atol=1e-15), (sym, "real funding")
    assert np.all(real[syn] == 0), (sym, "synthetic hour also has a print")
    first_perp = perps[0][1].open_time.iloc[0]
    pre = idx < (ICP_FUNDING_FROM if sym == "ICP" else first_perp)
    hrs = np.isin(idx.hour, (0, 8, 16))
    assert np.all(h.funding.to_numpy()[pre & hrs] == FUND_SYN) and np.all(h.funding.to_numpy()[pre & ~hrs] == 0)
    assert syn[pre].sum() == (pre & hrs).sum() and h.spot_only[idx < first_perp].all()
    last_perp = perps[-1][1].open_time.iloc[-1]
    after = idx > last_perp
    # after the coin's last perpetual nothing is tradable (spot never replaces a delisted perpetual): filler
    # rows flat at the perpetual's last close, no funding; the signal series is left as it is
    assert not (h.tradable[after] | (h.trades[after] > 0) | h.live[after] | h.spot_only[after]).any(), sym
    assert np.all(h.funding.to_numpy()[after] == 0) and (h.close[after] == h.close.at[last_perp]).all(), sym
    ends = [k.open_time.iloc[-1] for _, k in perps]
    assert list(idx[h.perp_end.to_numpy()]) == [e for e in ends if e < END], (sym, "perp_end")
    if after.any():
        say(f"  {sym}: after the last perpetual bar {last_perp:%Y-%m-%d %H}h (perp_end): {int(after.sum()):,} "
            f"hours, none tradable; signal series live on {int(h.sig_live[after].sum()):,} of them")
    octr = (idx >= OCT_FROM) & syn
    if last_perp == END:
        f = _read("funding", perps[-1][0])
        ft = f.calc_time.dt.floor("min")
        med = float(np.median(f.rate[(ft >= "2026-09-01") & (ft < "2026-10-01")]))
        iv = float(f.interval_h.iloc[-1])
        assert octr.sum() == int(16 * 24 / iv) and np.all(h.funding.to_numpy()[octr] == med), (sym, "October")
        assert np.all(h.funding.to_numpy()[(idx >= OCT_FROM) & ~syn] == 0)
        say(f"  {sym}: October 2026 carry-forward {octr.sum()} prints at {med:+.6f} (Sept median, {iv:g} h cadence)")
    say(f"  {sym}: {len(h):,} hours {idx[0]:%Y-%m-%d %H}h..{idx[-1]:%Y-%m-%d %H}h; perp {h.is_perp.sum():,}, "
        f"spot stand-in {int(sp_only.sum()):,}, not tradable {int((~h.tradable).sum()):,}, filler traded "
        f"{(~h.live).sum():,}, filler signal {(~h.sig_live).sum():,}, segments {h.seg.max() + 1}; "
        f"funding synthetic {int(syn.sum())} prints ({int((pre & hrs).sum())} before {'2022-09-01' if sym == 'ICP' else 'listing'})")


def _synthetic_hours(start="2025-03-03", days=21, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz="UTC").as_unit("ns")
    c = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
    o = np.r_[100.0, c[:-1]]
    hi = np.maximum(o, c) * (1 + rng.uniform(0, 0.005, len(idx)))
    lo = np.minimum(o, c) * (1 - rng.uniform(0, 0.005, len(idx)))
    df = pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "trades": 1}, index=idx)
    for a in PX:
        df["sig_" + a] = df[a]
    df["quote_volume"] = df["sig_quote_volume"] = rng.uniform(1, 2, len(idx))
    df["live"] = df["sig_live"] = True
    df["seg"] = 0
    return df


def _kl(t0, t1, px0, seed, drop=(), zero=()) -> pd.DataFrame:
    """Synthetic hourly klines in the archive's file layout (open_time datetime64[ms, UTC])."""
    idx = pd.date_range(_utc(t0), _utc(t1), freq="h")
    rng = np.random.default_rng(seed)
    c = px0 * np.exp(np.cumsum(rng.normal(0, 0.003, len(idx))))
    o = np.r_[px0, c[:-1]]
    k = pd.DataFrame({"open_time": idx.as_unit("ms"), "open": o, "high": np.maximum(o, c) * 1.001,
                      "low": np.minimum(o, c) * 0.999, "close": c, "volume": 1.0, "quote_volume": 1000.0,
                      "trades": np.int64(10), "taker_buy_quote": 500.0})
    z = k.open_time.isin(pd.DatetimeIndex(zero, tz="UTC") if len(zero) else [])
    k.loc[z, ["trades", "quote_volume", "volume", "taker_buy_quote"]] = 0
    return k[~k.open_time.isin(pd.DatetimeIndex(drop, tz="UTC") if len(drop) else [])].reset_index(drop=True)


def _fund(t0, t1, freq, rate, iv=8) -> pd.DataFrame:
    """Synthetic funding prints (calc_time with 5 ms jitter, as the archive's)."""
    t = pd.date_range(_utc(t0), _utc(t1), freq=freq)
    r = rate(np.arange(len(t))) if callable(rate) else np.full(len(t), float(rate))
    return pd.DataFrame({"calc_time": (t + pd.Timedelta(milliseconds=5)).as_unit("ms"), "rate": r,
                         "interval_h": float(iv)})


def _check_coin_hours_synthetic(say) -> None:
    """coin_hours on synthetic files in a temporary DATA directory, one coin per branch, with known answers:
    ZA pre-listing spot stand-in, perpetual window with holes / zero-trade bars / out-of-window prints / mark
    trimming, delisting (perp_end) and spot afterwards (never tradable); ZB spot delisted while the perpetual
    trades (signal switch, XMR) and the October 2026 carry at a 4 h cadence; ZC perpetual listed before spot;
    ZD two contracts of one coin with a new asset's spot segment between them (LUNA); ZE spot relisted after the
    last perpetual (FTT); ICP's funding rule; and date-only `end` slicing."""
    import datetime as _dt
    import tempfile
    global DATA
    U = lambda s: pd.Timestamp(s, tz="UTC")
    old_data, old_pf = DATA, dict(_PERP_FILES)
    hrs8 = lambda ix: np.isin(ix.hour, (0, 8, 16))

    def put(kind, stem, df):
        (DATA / kind).mkdir(parents=True, exist_ok=True)
        df.to_parquet(DATA / kind / f"{stem}USDT.parquet", index=False)

    def at(h, t, c):
        return h.at[U(t), c]

    with tempfile.TemporaryDirectory(prefix="bb_data_selftest_") as tmp:
        try:
            DATA = Path(tmp)
            _PERP_FILES["ZD"] = ["ZD", "ZD2"]
            _coin_hours_full.cache_clear(); _bars_cached.cache_clear()
            # ---------------- ZA: spot stand-in, perpetual window, delisting, spot afterwards
            spot = _kl("2026-07-01", END, 100, 1, drop=["2026-07-03 08:00"])
            perp = _kl("2026-07-10", "2026-09-10 12:00", 101, 2, drop=["2026-08-01 10:00"], zero=["2026-08-02 03:00"])
            mark = _kl("2026-07-05", END, 101, 3, drop=["2026-08-05 07:00"])[["open_time"] + PX]
            fz = _fund("2026-07-09 16:00", "2026-09-10 16:00", "8h", lambda i: 1e-5 * (i + 1))
            put("h1_spot", "ZA", spot); put("h1_um", "ZA", perp); put("h1_mark", "ZA", mark); put("funding", "ZA", fz)
            h = coin_hours("ZA")
            ix = h.index
            w0, w1 = U("2026-07-10"), U("2026-09-10 12:00")
            pre, win, aft = ix < w0, (ix >= w0) & (ix <= w1), ix > w1
            assert ix[0] == U("2026-07-01") and ix[-1] == END and (np.diff(ix.asi8) == H.value).all()
            assert h.spot_only[pre].all() and h.tradable[pre].all() and not h.is_perp[pre].any()
            assert h.is_perp[win].all() and h.tradable[win].all() and not h.spot_only[win].any()
            sp = spot.set_index(pd.DatetimeIndex(spot.open_time).as_unit("ns"))
            pp = perp.set_index(pd.DatetimeIndex(perp.open_time).as_unit("ns"))
            assert np.array_equal(h.sig_close.loc[sp.index].to_numpy(), sp.close.to_numpy())      # signal = spot
            tp = sp.index[sp.index < w0]
            assert np.array_equal(h.close.loc[tp].to_numpy(), sp.close.loc[tp].to_numpy())     # traded = spot before
            assert np.array_equal(h.close.loc[pp.index].to_numpy(), pp.close.to_numpy())       # traded = perp inside
            t = U("2026-07-03 08:00")                                                             # spot hole, pre-listing
            assert not h.live[t] and h.trades[t] == 0 and h.close[t] == sp.close[t - H] and h.spot_only[t]
            assert h.funding[t] == FUND_SYN and not h.sig_live[t]
            t = U("2026-08-01 10:00")                                                             # perp hole
            assert h.is_perp[t] and not h.live[t] and h.trades[t] == 0 and h.close[t] == pp.close[t - H]
            assert h.sig_live[t] and h.sig_close[t] == sp.close[t]
            t = U("2026-08-02 03:00")                                                             # zero-trade bar
            assert h.live[t] and h.trades[t] == 0 and h.close[t] == pp.close[t]
            exp = np.where(pre & hrs8(ix), FUND_SYN, 0.0)                                         # funding known answer
            for ct, r in zip(fz.calc_time, fz.rate):
                ct = pd.Timestamp(ct).floor("min")
                if w0 <= ct <= w1:
                    exp[ix.get_loc(ct)] = r
            assert np.array_equal(h.funding.to_numpy(), exp)
            assert at(h, "2026-07-09 16:00", "funding") == FUND_SYN and at(h, "2026-09-10 16:00", "funding") == 0
            assert at(h, "2026-07-10 00:00", "funding") == 2e-5 and not at(h, "2026-07-10 00:00", "fund_synthetic")
            assert list(ix[h.perp_end]) == [w1]
            assert not (h.tradable[aft] | h.spot_only[aft] | h.is_perp[aft] | h.live[aft] | h.fund_synthetic[aft]).any()
            assert (h.trades[aft] == 0).all() and (h.quote_volume[aft] == 0).all() and (h.funding[aft] == 0).all()
            assert (h.close[aft] == pp.close[w1]).all() and (h.high[aft] == pp.close[w1]).all()
            assert int((aft & (h.tradable | (h.trades > 0))).sum()) == 0 and h.sig_live[aft].all()
            mk = mark.set_index(pd.DatetimeIndex(mark.open_time).as_unit("ns"))
            mk = mk[(mk.index >= w0) & (mk.index <= w1)]
            assert h.mark_low.notna().sum() == len(mk) == win.sum() - 1 and h.mark_low[~win].isna().all()
            assert np.array_equal(h.mark_low.loc[mk.index].to_numpy(), mk.low.to_numpy())
            assert bars_from_hours(h, "1d", "traded").index[-1] == U("2026-09-10")
            assert bars_from_hours(h, "1d", "sig").index[-1] == U("2026-10-16") and (h.seg == 0).all()
            # ---------------- ZB: spot delisted while the perpetual trades; October carry at 4 h
            spot = _kl("2026-08-01", "2026-09-20 02:00", 100, 4)
            perp = _kl("2026-08-05", END, 99, 5)
            fb = _fund("2026-08-05", "2026-09-30 20:00", "4h", lambda i: 1e-6 * (i + 1), iv=4)
            put("h1_spot", "ZB", spot); put("h1_um", "ZB", perp); put("funding", "ZB", fb)
            h = coin_hours("ZB")
            ix = h.index
            assert at(h, "2026-09-20 02:00", "sig_close") == spot.close.iloc[-1]
            assert at(h, "2026-09-20 03:00", "sig_close") == perp.set_index("open_time").close[U("2026-09-20 03:00")]
            assert h.sig_live.all() and (h.seg == 0).all() and h.tradable.all() and not h.perp_end.any()
            pre = ix < U("2026-08-05")
            assert h.spot_only[pre].all() and np.array_equal(h.funding[pre].to_numpy(),
                                                             np.where(hrs8(ix[pre]), FUND_SYN, 0.0))
            o = h[ix >= OCT_FROM]
            sept = fb.rate[(fb.calc_time >= U("2026-09-01")) & (fb.calc_time < U("2026-10-01"))]
            on = o.index.hour % 4 == 0
            assert len(sept) == 180 and on.sum() == 96 and (o.funding[on] == float(np.median(sept))).all()
            assert o.fund_synthetic[on].all() and (o.funding[~on] == 0).all() and not o.fund_synthetic[~on].any()
            # date-only `end` covers the whole period (pandas' partial-string slicing); timestamps are exact
            a = coin_hours("ZB", "2026-10-12", "2026-10-16")
            assert a.index[0] == U("2026-10-12") and a.index[-1] == END and len(a) == 120
            assert a.equals(h.loc["2026-10-12":"2026-10-16"])
            assert coin_hours("ZB", "2026-10-12", U("2026-10-16 00:00")).index[-1] == U("2026-10-16 00:00")
            assert coin_hours("ZB", "2026-10-12", "2026-10-16 05:00").index[-1] == U("2026-10-16 05:00")
            assert coin_hours("ZB", "2026-10-12", _dt.date(2026, 10, 16)).index[-1] == END
            m = coin_hours("ZB", "2026-09", "2026-09")
            assert m.index[0] == U("2026-09-01") and m.index[-1] == U("2026-09-30 23:00") and len(m) == 720
            # ---------------- ZC: perpetual listed before spot
            perp = _kl("2026-08-01 00:00", END, 99, 6)
            spot = _kl("2026-08-01 05:00", END, 100, 7)
            put("h1_spot", "ZC", spot); put("h1_um", "ZC", perp)
            put("funding", "ZC", _fund("2026-08-01", "2026-09-30 16:00", "8h", 2e-4))
            h = coin_hours("ZC")
            assert h.index[0] == U("2026-08-01") and not h.spot_only.any() and h.is_perp.all()
            assert at(h, "2026-08-01 04:00", "sig_close") == perp.close.iloc[4]
            assert at(h, "2026-08-01 05:00", "sig_close") == spot.close.iloc[0]
            assert not h.fund_synthetic[h.index < OCT_FROM].any()
            # ---------------- ZD: LUNA-like, two contracts with a new asset's spot segment between them
            e1, s1, p2 = U("2026-07-19 15:00"), U("2026-08-01 06:00"), U("2026-08-20")
            spot0, spot1 = _kl("2026-06-01", "2026-07-20 00:00", 100, 8), _kl(s1, END, 0.1, 9)
            put("h1_spot", "ZD", pd.concat([spot0, spot1], ignore_index=True))
            put("h1_um", "ZD", _kl("2026-06-10", e1, 100.5, 10)); put("h1_um", "ZD2", _kl(p2, END, 0.1, 11))
            put("funding", "ZD", _fund("2026-06-10", "2026-07-19 08:00", "8h", 3e-4))
            put("funding", "ZD2", _fund(p2, "2026-09-30 16:00", "8h", 5e-4))
            h = coin_hours("ZD")
            ix = h.index
            pre, c1 = ix < U("2026-06-10"), (ix >= U("2026-06-10")) & (ix <= e1)
            dead, stand, c2 = (ix > e1) & (ix < s1), (ix >= s1) & (ix < p2), ix >= p2
            assert h.spot_only[pre].all() and np.array_equal(h.funding[pre].to_numpy(),
                                                             np.where(hrs8(ix[pre]), FUND_SYN, 0.0))
            assert h.is_perp[c1].all() and np.array_equal(h.funding[c1].to_numpy(), np.where(hrs8(ix[c1]), 3e-4, 0.0))
            assert list(ix[h.perp_end]) == [e1]
            assert not (h.tradable[dead] | h.live[dead] | h.fund_synthetic[dead]).any() and (h.funding[dead] == 0).all()
            assert (h.trades[dead] == 0).all() and (h.close[dead] == at(h, "2026-07-19 15:00", "close")).all()
            assert h.sig_live[(ix > e1) & (ix <= U("2026-07-20 00:00"))].all()        # old asset's signal unchanged
            assert not h.sig_live[(ix > U("2026-07-20 00:00")) & (ix < s1)].any()
            assert h.spot_only[stand].all() and h.tradable[stand].all() and h.live[stand].all()
            assert np.array_equal(h.close[stand].to_numpy(), spot1.close.to_numpy()[:stand.sum()])
            assert np.array_equal(h.funding[stand].to_numpy(), np.where(hrs8(ix[stand]), FUND_SYN, 0.0))
            assert h.fund_synthetic[stand].sum() == hrs8(ix[stand]).sum()
            o = c2 & (ix < OCT_FROM)
            assert h.is_perp[c2].all() and np.array_equal(h.funding[o].to_numpy(), np.where(hrs8(ix[o]), 5e-4, 0.0))
            assert (h.funding[c2 & (ix >= OCT_FROM) & hrs8(ix)] == 5e-4).all() and h.fund_synthetic[ix >= OCT_FROM].sum() == 48
            assert (h.seg[ix < s1] == 0).all() and (h.seg[ix >= s1] == 1).all()
            # ---------------- ZE: FTT-like, spot relisted after the last perpetual
            e1, r1 = U("2026-07-14 04:00"), U("2026-08-20 08:00")
            put("h1_spot", "ZE", pd.concat([_kl("2026-06-01", "2026-07-15 04:00", 2, 12), _kl(r1, END, 1, 13)],
                                           ignore_index=True))
            put("h1_um", "ZE", _kl("2026-06-10", e1, 2.01, 14))
            put("funding", "ZE", _fund("2026-06-10", "2026-07-14 00:00", "8h", -5e-4))
            h = coin_hours("ZE")
            aft = h.index > e1
            assert list(h.index[h.perp_end]) == [e1] and not (h.tradable[aft] | h.live[aft]).any()
            assert (h.trades[aft] == 0).all() and (h.funding[aft] == 0).all() and h.sig_live[h.index >= r1].all()
            assert at(h, "2026-08-20 08:00", "seg") == 1 and at(h, "2026-08-20 07:00", "seg") == 0
            # ---------------- ICP: funding archive from 2022-09-01, synthetic before (also in a halt)
            put("h1_spot", "ICP", _kl("2022-08-20 00:00", "2022-09-10 23:00", 5, 15))
            halt = pd.date_range("2022-08-25", "2022-08-25 23:00", freq="h")
            put("h1_um", "ICP", _kl("2022-08-20 02:00", "2022-09-10 23:00", 5.01, 16, zero=halt))
            put("funding", "ICP", _fund("2022-08-20 08:00", "2022-09-10 16:00", "8h", 2e-4))
            _coin_hours_full.cache_clear()
            h = coin_hours("ICP")
            assert at(h, "2022-08-20 00:00", "spot_only") and at(h, "2022-08-20 00:00", "funding") == FUND_SYN
            assert at(h, "2022-08-24 08:00", "funding") == FUND_SYN and at(h, "2022-08-24 08:00", "fund_synthetic")
            assert at(h, "2022-08-25 16:00", "funding") == FUND_SYN and at(h, "2022-08-25 16:00", "trades") == 0
            assert at(h, "2022-09-01 00:00", "funding") == 2e-4 and not at(h, "2022-09-01 00:00", "fund_synthetic")
            assert not h.fund_synthetic[h.index >= ICP_FUNDING_FROM].any()
            assert list(h.index[h.perp_end]) == [U("2022-09-10 23:00")]
        finally:
            DATA = old_data
            _PERP_FILES.clear(); _PERP_FILES.update(old_pf)
            _coin_hours_full.cache_clear(); _bars_cached.cache_clear()
    say("  synthetic coin_hours (temporary DATA): spot stand-in before listing with 0.01%/8 h; perpetual window "
        "(holes, zero-trade bars, out-of-window prints dropped, ms jitter floored, mark trimmed); delisting: "
        "perp_end at the last bar, no tradable hour after it (spot or relisted spot), flat at the last close, no "
        "funding; XMR-like signal switch; perp-before-spot; LUNA-like gap (old asset's spot not tradable, new "
        "asset's spot stands in with synthetic funding, second contract's prints); FTT-like relisting; ICP "
        "funding rule; October carry at a 4 h cadence; date-only `end` covers the whole day / month")


def _check_bars(say) -> None:
    hrs = _synthetic_hours()
    for freq, per in FREQ.items():
        b = bars_from_hours(hrs, freq)
        assert (b.known_at == b.index + per).all() and (b.index[1:] - b.index[:-1] == per).all(), freq
        for t, r in b.iloc[[0, len(b) // 2, -1]].iterrows():
            x = hrs[(hrs.index >= t) & (hrs.index < t + per)]
            assert len(x) == r.n_hours and x.sig_open.iloc[0] == r.open and x.sig_close.iloc[-1] == r.close
            assert x.sig_high.max() == r.high and x.sig_low.min() == r.low
            assert abs(x.sig_quote_volume.sum() - r.quote_volume) < 1e-9
    b4 = bars_from_hours(hrs, "4h")
    assert set(b4.index.hour) == {0, 4, 8, 12, 16, 20}
    d = bars_from_hours(hrs, "1d")
    assert (d.index.hour == 0).all() and (d.n_hours == 24).all()
    w = bars_from_hours(hrs, "1w")
    from analysis_2026.moneyline_ref import to_weekly
    tw = to_weekly(d[["open", "high", "low", "close"]])
    assert (w.index.weekday == 0).all() and np.allclose(w[["open", "high", "low", "close"]].to_numpy(), tw.to_numpy())
    assert (w.index == tw.index).all()
    # look-ahead: cuts at minutes off every hour and day boundary (the pre-registration's control); every hourly
    # bar that ends after the cut (including the one the cut falls in, whose close is after it) is scaled, and
    # every bar known by the cut must stay unchanged
    n_known = dict.fromkeys(FREQ, 0)
    for cut in ("2025-03-12 13:17", "2025-03-09 23:41", "2025-03-17 00:29"):
        cut = pd.Timestamp(cut, tz="UTC")
        assert cut != cut.floor("h")
        z = hrs.copy()
        after = z.index + H > cut
        z.loc[after, PX + SIG] *= 1.5
        z.loc[after, ["quote_volume", "sig_quote_volume"]] *= 0.5
        for freq in FREQ:
            a, c = bars_from_hours(hrs, freq), bars_from_hours(z, freq)
            k = a.known_at <= cut
            assert a[k].equals(c[k]) and not a[~k].equals(c[~k]), (freq, cut)
            n_known[freq] += int(k.sum())
    assert min(n_known.values()) > 0, n_known
    # filler rows never move a bar; a bar with no live hour is dropped
    z = hrs.copy()
    dead = (z.index >= "2025-03-05 06:00") & (z.index < "2025-03-07 00:00")
    z.loc[dead, SIG] = 1e9
    z.loc[dead, "sig_live"] = False
    a, c = bars_from_hours(hrs[~dead], "1d"), bars_from_hours(z, "1d")
    assert a.equals(c) and pd.Timestamp("2025-03-06", tz="UTC") not in c.index
    # a bar straddling a series break keeps the hours of its last segment only
    z = hrs.copy()
    z.loc[z.index >= "2025-03-12 05:00", "seg"] = 1
    wk = bars_from_hours(z, "1w").loc[pd.Timestamp("2025-03-10", tz="UTC")]
    x = z[(z.index >= "2025-03-12 05:00") & (z.index < "2025-03-17")]
    assert wk.seg == 1 and wk.n_hours == len(x) and wk.open == x.sig_open.iloc[0] and wk.low == x.sig_low.min()
    # injected frame with contract columns only
    bare = hrs[PX + ["trades"] + SIG].copy()
    assert bars_from_hours(bare, "1d", "traded")[["open", "high", "low", "close"]].equals(
        bars_from_hours(hrs, "1d", "traded")[["open", "high", "low", "close"]])
    say("  bars_from_hours: known_at = open + period for 1h/4h/1d/1w; 4h aligned to 00/04/../20 UTC; weekly = "
        "moneyline_ref.to_weekly; 3 cuts at off-hour minutes (13:17, 23:41, 00:29) leave every bar known by the "
        "cut unchanged; filler rows ignored; series-break split; contract-only injected frame works")
    # real data: the spot signal daily bars equal Binance's own 1d klines; the perpetual's traded bars likewise
    for sym in ("BTC", "SOL"):
        for series, kind in (("sig", "d1_spot"), ("traded", "d1_um")):
            b = bars(sym, "1d", series)
            ref = _read(kind, sym).set_index("open_time")
            if series == "traded":
                b = b[b.index >= ref.index[0] + DAY]               # days wholly inside the perpetual window
            j = b.join(ref[PX], rsuffix="_r", how="inner")
            assert len(j) > 0.95 * len(b), (sym, series)
            bad = np.zeros(len(j), bool)
            for c in PX:
                bad |= np.abs(j[c] / j[c + "_r"] - 1).to_numpy() > 1e-12
            which = f" ({', '.join(str(t.date()) for t in j.index[bad][:4])})" if bad.any() else ""
            say(f"  bars({sym}, '1d', '{series}') vs the archive's {kind} 1d klines: {len(j):,} days, "
                f"{int(bad.sum())} differ{which}")
            assert bad.sum() <= 2, (sym, series)


def _check_ny_clock(say) -> None:
    t = pd.DatetimeIndex(["2025-03-09 03:00", "2025-03-09 06:00", "2025-03-09 07:00", "2025-03-09 14:00",
                          "2025-03-08 14:00", "2025-11-02 04:00", "2025-11-02 05:00", "2025-11-02 06:00",
                          "2025-11-02 15:00", "2025-11-01 13:00"], tz="UTC")
    c = ny_clock(t)
    exp_hour = [22, 1, 3, 10, 9, 0, 1, 1, 10, 9]
    exp_date = ["2025-03-08", "2025-03-09", "2025-03-09", "2025-03-09", "2025-03-08", "2025-11-02", "2025-11-02",
                "2025-11-02", "2025-11-02", "2025-11-01"]
    exp_dst = [False, False, True, True, False, True, True, False, False, True]
    exp_open = ["2025-03-08 14:30", "2025-03-09 13:30", "2025-03-09 13:30", "2025-03-09 13:30", "2025-03-08 14:30",
                "2025-11-02 14:30", "2025-11-02 14:30", "2025-11-02 14:30", "2025-11-02 14:30", "2025-11-01 13:30"]
    assert c.ny_hour.tolist() == exp_hour, c.ny_hour.tolist()
    assert [str(d.date()) for d in c.ny_date] == exp_date
    assert c.is_dst.tolist() == exp_dst, c.is_dst.tolist()
    assert list(c.us_open_utc) == list(pd.DatetimeIndex(exp_open, tz="UTC"))
    assert c.ny_weekday.tolist() == [5, 6, 6, 6, 5, 6, 6, 6, 6, 5]
    # every hour of both transition days: the local hour sequence skips 02:00 (March) and repeats 01:00 (November)
    m = ny_clock(pd.date_range("2025-03-09 05:00", "2025-03-09 08:00", freq="h", tz="UTC"))
    nv = ny_clock(pd.date_range("2025-11-02 04:00", "2025-11-02 07:00", freq="h", tz="UTC"))
    assert m.ny_hour.tolist() == [0, 1, 3, 4] and nv.ny_hour.tolist() == [0, 1, 1, 2]
    say("  ny_clock: 2025-03-09 (02:00 skipped, open 13:30 UTC; 14:30 the day before) and 2025-11-02 (01:00 "
        "repeated, open 14:30 UTC; 13:30 the day before) as expected")


def _check_ranks(say) -> None:
    days = pd.date_range("2024-01-01", "2024-06-30", freq="D", tz="UTC").as_unit("ns")
    qv = pd.DataFrame(1.0, index=days, columns=["AAA", "BBB", "CCC", "DDD", "EEE"])
    qv["BBB"] = 2.0
    qv["CCC"] = 3.0
    qv.loc["2024-03-02", "AAA"] = 1e6                          # 91 days before 2024-06-01 (outside the window)
    qv.loc["2024-05-31", "EEE"] = 300.0                        # the prior day (inside)
    qv.loc["2024-06-01", "DDD"] = 1e6                          # the rank day itself (outside)
    live = pd.DataFrame(True, index=days, columns=qv.columns)
    live.loc["2024-05-31", "CCC"] = False                      # not trading on the prior day: not ranked
    r = _rank_months(qv, live, pd.DatetimeIndex(["2024-06-01"], tz="UTC"), top=4)
    assert r.iloc[0].tolist() == ["EEE", "BBB", "AAA", "DDD"], r.iloc[0].tolist()
    seg = pd.DataFrame(0, index=days, columns=qv.columns)
    seg.loc[seg.index >= "2024-05-20", "AAA"] = 1                 # AAA relisted: only 12 days of its new segment
    qv2 = qv.copy(); qv2["AAA"] = 2.5
    r2 = _rank_months(qv2, live, pd.DatetimeIndex(["2024-06-01"], tz="UTC"), seg=seg, top=4)
    assert r2.iloc[0].tolist() == ["EEE", "BBB", "DDD", "AAA"], r2.iloc[0].tolist()
    # look-ahead: volumes changed from day M on never move the ranks of month M or earlier
    rng = np.random.default_rng(3)
    big = pd.DataFrame(rng.lognormal(0, 1, (len(days), 8)), index=days, columns=list("ABCDEFGH"))
    lv8 = pd.DataFrame(rng.uniform(size=big.shape) > 0.05, index=days, columns=big.columns)
    months = pd.date_range("2024-02-01", "2024-06-01", freq="MS", tz="UTC").as_unit("ns")
    base = _rank_months(big, lv8, months, top=5)
    for cut in months[1:-1]:
        z = big.copy(); z.loc[z.index >= cut] *= rng.uniform(0.1, 10, (int((z.index >= cut).sum()), 8))
        zl = lv8.copy(); zl.loc[zl.index >= cut] = ~zl.loc[zl.index >= cut]
        r3 = _rank_months(z, zl, months, top=5)
        assert r3.loc[:cut].equals(base.loc[:cut]) and not r3.loc[cut + DAY:].equals(base.loc[cut + DAY:]), cut
    say("  ranks (synthetic): 90-day window M-90..M-1, prior-day liveness, ties alphabetical, segment rule ok; "
        "volumes and liveness changed from day M on leave the ranks of month M and earlier unchanged")
    allowed = {"BTC", "ETH", "SOL", "XRP", "BNB", "DOGE"}
    r40 = volume_ranks("40")
    top = r40.loc["2025-01-01":"2025-12-01", [1, 2, 3]]
    assert len(top) == 12 and set(top.to_numpy().ravel()) <= allowed, top
    say(f"  volume_ranks('40'): {len(r40)} months {r40.index[0]:%Y-%m}..{r40.index[-1]:%Y-%m}; 2025 top 3 drawn "
        f"from {sorted(set(top.to_numpy().ravel()))}")
    try:
        ra = volume_ranks("all")
    except RuntimeError as e:
        say(f"  volume_ranks('all'): NOT AVAILABLE: {e}")
        return
    topa = ra.loc["2025-01-01":"2025-12-01", [1, 2, 3]]
    say(f"  volume_ranks('all'): {len(ra)} months {ra.index[0]:%Y-%m}..{ra.index[-1]:%Y-%m}; 2025 top 3 drawn "
        f"from {sorted(set(topa.to_numpy().ravel()))}")
    assert set(topa.to_numpy().ravel()) <= allowed, topa
    ent = s12_entrants()
    lit, cry = set(s12_entrants(True)), set(s12_entrants(False))
    assert ent == S12_ENTRANTS, sorted(set(ent) ^ set(S12_ENTRANTS))
    assert sorted(lit - cry) == S12_ENTRANTS_TRADFI and sorted(cry - lit) == S12_ENTRANTS_CRYPTO_ONLY
    assert set(S12_ENTRANTS_TRADFI) <= TRADFI and not (set(S12_ENTRANTS) - set(S12_ENTRANTS_TRADFI)) & TRADFI
    ra0 = volume_ranks("all", tradfi=False)
    assert not ({x for x in ra0.to_numpy().ravel() if isinstance(x, str)} & TRADFI)
    tab = all_contracts_table()
    say(f"  all-contract pool: {len(tab)} USDT perpetuals in the archive listing, {int((tab.result == 'ok').sum())} "
        f"fetched, {tab.coin.nunique()} coins; excluded {sorted(tab.contract[tab.excluded != ''])}; "
        f"{int(tab.tradfi.sum())} TradFi contracts (kept in the literal pool)")
    miss = [f"{k}/{c}" for c in ent for k in ("h1_um", "h1_mark", "funding")
            if not (DATA / k / f"{c}USDT.parquet").exists()]
    say(f"  S12 entrants outside the 40: {len(ent)} ({' '.join(ent)}); literal pool only (TradFi): "
        f"{' '.join(S12_ENTRANTS_TRADFI)}; crypto-only pool only: {' '.join(S12_ENTRANTS_CRYPTO_ONLY)}; "
        f"files missing: {miss or 'none'}")
    assert not miss
    has_spot = sorted(c for c in ent if (DATA / "h1_spot" / f"{c}USDT.parquet").exists())
    assert has_spot == S12_ENTRANTS_SPOT, sorted(set(has_spot) ^ set(S12_ENTRANTS_SPOT))
    basis, earlier, after_n = {}, [], 0
    for c in ent:
        assert c in TICK and c in MMR, c
        h = coin_hours(c)
        perp = _read("h1_um", perp_files(c)[-1])
        w0, w1 = perp.open_time.iloc[0], perp.open_time.iloc[-1]
        inside = (h.index >= w0) & (h.index <= w1)
        assert np.array_equal(h.is_perp.to_numpy(), inside) and (h.index[h.spot_only] < w0).all(), c
        assert not (h.tradable | h.live)[h.index > w1].any() and (h.trades[h.index > w1] == 0).all(), c
        assert list(h.index[h.perp_end]) == ([w1] if w1 < END else []), c
        after_n += int((h.index > w1).sum())
        if c in S12_ENTRANTS_SPOT:                                 # signal on spot where spot trades (R0 Signal)
            s = _read("h1_spot", c)
            js = h.loc[pd.DatetimeIndex(s.open_time)]
            assert np.array_equal(js.sig_close.to_numpy(), s.close.to_numpy()), c
            b = spot_basis(c)
            assert b["hours"] > 0 and b["median"] < 0.01, (c, b)
            basis[c] = b["median"]
            if s.open_time.iloc[0] < w0:
                earlier.append(f"{c} {(w0 - s.open_time.iloc[0]).days}d")
        else:
            assert h.is_perp[h.live].all() and h.sig_live.equals(h.live) and (h.sig_close == h.close).all(), c
    say(f"  S12 entrants with Binance spot: {len(basis)} (signal on spot where it trades); median |spot/perp - 1| "
        f"{min(basis.values()):.5f}..{max(basis.values()):.5f}; spot history before the perpetual: "
        f"{', '.join(earlier)}; {after_n:,} hours after delisted entrants' last perpetual bar, none tradable")


def _check_minutes_ticks(say) -> None:
    for s in COINS + [c for c in TICK if c not in COINS]:
        r = infer_tick(s)
        assert r["tick"] == TICK[s], (s, r, TICK[s])
        if s in M1_COINS:
            assert r["m1_grid"] == M1_GRID[s], (s, r)
    m = minutes("BTC", "2024-08-07 22:40", "2024-08-07 22:50")
    assert len(m) == 11 and m.loc[pd.Timestamp("2024-08-07 22:46", tz="UTC"), "close"] == 55181.35
    m = minutes("BTC", "2026-10-16", "2026-10-16")                # a date-only end covers the whole day
    assert len(m) == 1440 and m.index[-1] == pd.Timestamp("2026-10-16 23:59", tz="UTC"), (len(m), m.index[-1])
    m = minutes("BTC", "2026-10-16 23:00", pd.Timestamp("2026-10-16 23:00", tz="UTC"))
    assert len(m) == 1                                             # a Timestamp end is exact
    rng = np.random.default_rng(1)
    for s in M1_COINS:
        mm = minutes(s, "2024-07-01", "2026-10-16 23:59")
        assert len(mm) == 1_206_720 and mm.index.is_monotonic_increasing and mm.index.is_unique, s
        g = M1_GRID[s]
        for c in PX:
            x = mm[c].to_numpy()
            assert np.all(np.abs(x / g - np.round(x / g)) < 1e-6), (s, c)
        hh = coin_hours(s, "2024-07-01", END)
        pick = np.sort(rng.choice(len(hh), 400, replace=False))
        a = mm.groupby(mm.index.floor("h")).agg(open=("open", "first"), high=("high", "max"),
                                                low=("low", "min"), close=("close", "last"))
        sub = a.loc[hh.index[pick]]
        diff = (np.abs(sub[PX].to_numpy() - hh[PX].to_numpy()[pick]) > 1e-9).any(axis=1)
        assert diff.sum() <= 2, (s, hh.index[pick][diff])
    say(f"  TICK matches the inference for {len(TICK)} perpetuals; minutes() of the six M1 coins: 1,206,720 bars "
        "each, every price on its grid (BTC 0.01: the archive's four off-tick prints are kept exactly); 400 random "
        "hours per coin aggregate to the hourly file")


def _check_tbill(say) -> None:
    from analysis_2026.regime_switch import rf_annual_pct
    t = pd.DatetimeIndex(["2020-03-02", "2024-01-02 15:00", "2025-06-02", "2026-10-16"], tz="UTC")
    d, s = tbill_daily(t), tbill_session(t)
    ref = rf_annual_pct(pd.DatetimeIndex(["2020-03-02", "2024-01-02", "2025-06-02", "2026-10-16"]))
    assert np.allclose(d, ref / 36500) and np.allclose(s, ref / 25200) and (d > 0).all()
    say(f"  tbill_daily: {', '.join(f'{x * 36500:.2f}%' for x in d)} a year (rf_annual_pct / 365 per day)")


def selftest() -> None:
    t0 = time.time()
    lines = []

    def say(s):
        print(s, flush=True); lines.append(s)

    assert len(COINS) == 40 and set(PRIMARY) <= set(COINS) and set(M1_COINS) <= set(COINS)
    assert set(COINS) <= set(MMR) and set(COINS) <= set(TICK) and all(0 < v <= 0.05 for v in MMR.values())
    assert MMR["BTC"] == MMR["ETH"] == 0.004                     # the snapshot's tier 1 (notional to 300,000 USDT)
    say("coin_hours on synthetic files (known answers)")
    _check_coin_hours_synthetic(say)
    say("coin_hours invariants (real files)")
    for sym in ("BTC", "SOL", "FTT", "ICP", "LUNA", "EOS", "MATIC", "XMR"):
        _check_coin_hours(sym, say)
    U = lambda t: pd.Timestamp(t, tz="UTC")
    f = coin_hours("FTT")
    at = lambda t, c: f.at[U(t), c]
    gap = f[(f.index > "2022-11-15 04:00") & (f.index < "2023-09-22 08:00")]
    assert (~gap.sig_live).all() and (gap.sig_close == at("2022-11-15 04:00", "sig_close")).all()
    assert at("2023-09-22 08:00", "seg") == 1 and at("2023-09-22 07:00", "seg") == 0
    late = f.index > U("2022-11-14 04:00")                       # FTTUSDT's last bar: nothing tradable after it
    assert f.perp_end.sum() == 1 and at("2022-11-14 04:00", "perp_end") and not f.tradable[late].any()
    assert (f.close[late] == at("2022-11-14 04:00", "close")).all() and f.sig_live[f.index >= U("2023-09-22 08:00")].all()
    lu = coin_hours("LUNA")
    e1, s1, p2 = U("2022-05-12 15:00"), U("2022-05-31 06:00"), U("2022-09-10")
    dead, stand = (lu.index > e1) & (lu.index < s1), (lu.index >= s1) & (lu.index < p2)
    assert lu.perp_end.sum() == 1 and lu.perp_end[e1] and lu.is_perp[e1]
    assert not (lu.tradable[dead] | lu.fund_synthetic[dead]).any() and (lu.funding[dead] == 0).all()
    assert (lu.trades[dead] == 0).all() and lu.sig_live[(lu.index > e1) & (lu.index <= U("2022-05-13"))].all()
    assert lu.spot_only[stand].all() and lu.live[stand].sum() > 0.99 * stand.sum() and lu.seg[s1] == 1
    hs = np.isin(lu.index[stand].hour, (0, 8, 16))
    assert np.array_equal(lu.funding[stand].to_numpy(), np.where(hs, FUND_SYN, 0.0))
    first2 = lu.index[lu.is_perp & (lu.index >= p2)][0]
    assert first2 >= p2 and first2 < p2 + DAY and not lu.spot_only[lu.index >= first2].any()
    i = coin_hours("ICP", "2022-06-11", "2022-09-26")             # date-only end: through 2022-09-26 23:00
    assert i.index[-1] == U("2022-09-26 23:00")
    assert i.is_perp.all() and (i.trades == 0).all() and i.sig_live.all()
    say("  FTT: perpetual ends 2022-11-14 04:00 (perp_end); no tradable hour after it although spot trades "
        "(7,467-hour spot gap, new signal segment at 2023-09-22 08:00); LUNA: LUNAUSDT ends 2022-05-12 15:00 "
        f"(perp_end), {int(dead.sum())} hours not tradable and without funding (old LUNA spot to 05-13 00:00, then "
        f"the gap), Terra 2.0 spot stands in {int(stand.sum()):,} hours with 0.01%/8 h until LUNA2USDT; ICP halt: "
        "perpetual rows with trades == 0 while the spot signal trades")
    say("bars")
    _check_bars(say)
    say("ny_clock")
    _check_ny_clock(say)
    say("T-bills")
    _check_tbill(say)
    say("ticks and minutes")
    _check_minutes_ticks(say)
    say("volume ranks")
    _check_ranks(say)
    say(f"selftest passed in {time.time() - t0:.0f}s")


# ================================================================ CLI
def _arg(name, default):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); sys.exit(0)
    cmd = sys.argv[1]
    w = min(int(_arg("--workers", MAX_WORKERS)), MAX_WORKERS)
    force = "--force" in sys.argv
    if cmd == "selftest":
        selftest()
    elif cmd == "fetch-all":
        fetch_d1_all(w, force)
    elif cmd == "entrants":
        print(json.dumps(fetch_entrants(w, force), indent=1, default=str))
    elif cmd == "entrant-spot":
        print(json.dumps(fetch_entrant_spot(None, w, force), indent=1, default=str))
    elif cmd == "ranks":
        pd.set_option("display.width", 250)
        for pool in ("40", "all"):
            print(f"pool {pool}"); print(volume_ranks(pool).to_string())
    else:
        raise SystemExit(f"unknown command {cmd}")
