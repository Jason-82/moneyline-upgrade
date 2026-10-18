"""
Part A of the scalping study: passive quoting on illiquid Binance spot pairs
(analysis_2026/SCALPING_PREREG.md, "Part A"). The pre-registration is the specification.

    python3 -m analysis_2026.scalp_crypto --universe            # exclusions.csv, eligibility.csv, draws.csv, arh_pairs.csv
    python3 -m analysis_2026.scalp_crypto --tests               # unit tests of the event engine (hand-built tapes)
    python3 -m analysis_2026.scalp_crypto --controls            # Control (i) synthetic GM market; (ii)+(iii) USD-M true book
    python3 -m analysis_2026.scalp_crypto --smoke               # 2 drawn pairs x 3 days: plumbing and speed (prints no P&L)
    python3 -m analysis_2026.scalp_crypto --run [--workers 4]   # every drawn pair-month, then the A-RH stratum if
                                                                #   data/scalping/rh/currency_pairs.json exists
    python3 -m analysis_2026.scalp_crypto --run --stratum arh   # only the A-RH stratum
    python3 -m analysis_2026.scalp_crypto --analyze             # primary_cells.csv and every reporting table

Outputs: analysis_2026/results_scalping/A/ (small tables), data/scalping/A/ (per pair-day parquet, gitignored).
Holm across the study's 36 tests and the final verdicts are applied by the combine script, not here.
No account data is read or written: only Binance's public archive and the klines parquet.

---------------------------------------------------------------------------------------------- data
klines   data/scalping/binance/klines_1d.parquet (fetch_scalping_data klines): universe, bands, vol split.
trades   data/spot/daily/trades/{SYM}/{SYM}-trades-{day}.zip from the Binance S3 bucket, streamed through
         fetch_scalping_data.s3_get_zip_csv (checksum-verified, held in memory, never written to disk).
futures  data/futures/um/daily/{bookTicker,trades}/... for Control (ii)/(iii), streamed the same way.
pilot    data/scalping/binance_pilot/spot_trades (already seen) supplies only the order-size distribution
         of the synthetic market in Control (i).

---------------------------------------------------------------------------------------------- engine
One event-driven simulator (numba) over taker orders, used for Part A and every control:
  taker order    consecutive prints with the same timestamp and aggressor side
  implied quote  bid = last price of the latest seller-initiated order, ask = same for buyer-initiated;
                 valid when ask > bid and both sides printed within 300 s; carried across midnight
  tick           gcd of distinct-price gaps over days d-7..d-1, extended in-day by any off-grid print
  latency        a decision at t sees prints up to t; places/reprices/cancels take effect at t + D; the old
                 order stays live and fillable until then; fills are known at once and their reactions
                 (Q5 offer, cap-side resize, T_max timer) take effect at fill + D
  fills          F1 strictly through (size = through volume), F2 at-or-through, crossed quotes at the print
                 price with the taker fee, post-only step-inside orders cancelled when reached, one fill per
                 aggressor order; in book mode (controls) a FIFO queue behind the displayed size
  taker exits    R = min(implied bid at t, first seller print at/after t + D) (buys: max with the ask),
                 price R(1 -/+ w), w = walk table of the previous 7 days, w >= tick/R, taker fee
  day end        all quotes cancelled effective 00:00; flatten decided at 00:00 and priced off the next day's
                 file; no next-day print => stopped-trading valuation (last print x (1 -/+ implied spread))
Fees do not change behaviour, so each configuration is simulated once and every fee scenario is applied
linearly: net = gross - f_m x maker $ - f_t x taker $.

---------------------------------------------------------------------------------------------- Implementation choices
Where the pre-registration is silent or ambiguous the reading less likely to produce a false PASS was taken
(or, where neither is more conservative, the most literal one). Each choice is listed here.
Universe and draw
  U1  "90 days of klines before the month" = at least 90 daily kline rows dated before the month start;
      "non-zero kline on the last day" = a kline row for the day before the month with quote volume > 0.
  U2  Trailing 30-day median quote volume: the 30 calendar days before the month, a missing kline counted as
      $0 (as for the US windows). Bands are half-open: A [50k,200k), B [200k,1M), C [1M,5M), D [5M,50M).
  U3  Exclusions are fixed from the 605-symbol kline list before any simulation (exclusions.csv):
      stablecoin/fiat bases (incl. U, KGST, the euro tokens and the depegged USTC, by name), gold-backed
      PAXG/XAUT (pegged real-world assets, "and the like"), wrapped/staked WBTC/WBETH/BNSOL, and tokenized
      equities = every base ending in "B" whose first kline is on or after 2026-06-01 (all 90+ such pairs
      are US stock/ETF tickers + B; none of them meets the 90-day rule in any month anyway).
  U4  The draw expression is evaluated literally once per band: default_rng(20261018 + m).choice(sorted
      candidates, size=min(k, n), replace=False), bands in the order A, B, C, D. If fewer than k undrawn
      pairs remain, the same generator then draws the remaining slots from all eligible non-pilot pairs of
      the band not already picked that month. "Already drawn" is per band, as written.
  U5  A-RH: base codes parsed from the saved get_currency_pairs JSON (asset_currency.code or the base of
      "XXX-USD"), matched exactly to Binance bases; BTCUSDT and ETHUSDT forced in; exclusion list applied;
      pilot pairs are kept (the stratum is defined as every listed pair); month eligibility as U1; "every
      7th day" = day index 0, 7, 14, ... from 2025-10-01 (53 days, always Wednesdays). Bands outside A-D are
      labelled "<A" and ">D".
Engine
  E1  Order size is fixed in coins per pair-day: q = size / (previous day's last price), so round trips net
      to exactly zero inventory; the cap is 3q coins. The increasing side quotes min(q, 3q - |inv|) and is
      skipped below Binance's $5 minimum notional.
  E2  A partly filled order is not topped up while its price is unchanged (it keeps its place); it is
      resized down only if the cap requires it. Q5's offer always covers the whole position. Long-only
      sell orders (Q5, Q1-LO) are capped at the coins held when they go live (the exchange's balance check).
  E3  T_max: the timer starts when inventory turns non-zero, at fill + D ("timers go live at fill + D");
      a sign flip without passing through zero does not reset it; the flatten is decided at expiry and
      executed at + D for the inventory then held.
  E4  Crossed fills: size = min(remaining, participation x volume of the order's prints at/through our
      price), price = the worst of those prints for us. If one aggressor order could both cross one of our
      quotes and fill the other, only the crossing (it comes first in the sweep) is counted.
  E5  Taker-exit reference R uses the latest same-side print price whether or not the quote is valid (it
      only enters a min/max, so including it is conservative); "first seller-initiated print" = the first
      print of the first seller-initiated order at/after t + D, searched into the next day's file.
      Exit notional N = |inventory| x R. The sqrt fallback is applied literally (it can scale down when the
      10 largest orders' median notional exceeds N). If no seller order exists in the 7 days, w = tick/R.
  E6  Day end: quotes are cancelled by a decision at 00:00 - D (effective 00:00); the flatten is decided at
      00:00 with R = min(implied bid at 00:00, first seller print at/after 00:00 + D in the next day's file).
      A T_max exit pending at midnight is executed instead (no double exit).
  E7  Stopped trading: if no qualifying print exists after the exit time (rest of the day and the whole next
      day), inventory is valued at the last same-side print x (1 -/+ the last implied relative spread) with
      the taker fee; such pair-days are flagged and listed. A missing day file = a zero pair-day (kept).
  E8  Q5 offer = max(implied ask at fill time (latest buyer print, valid or not), fill price + 1 tick);
      the bid's unfilled remainder is cancelled at fill + D and any fill before then is added to the offer.
      Q5 keeps its offer when the quote turns invalid; Q1/Q2/Q3 cancel both sides.
  E9  Q2 freshness ("both sides printed within the last 10 s") and quote validity expire on timers, so the
      orders are repriced or cancelled at expiry + D even without a new print.
  E10 Participation 25% multiplies the qualifying volume of every fill rule.
  E11 "$ filled" (edge denominator, fill rate, share of pair volume) = notional of fills of our resting
      orders (maker + crossed); taker exits are not fills. Fill rate = orders with any fill / orders placed.
  E12 Markouts: passive (maker) fills only, signed P&L to the valid implied mid at fill + 60 s / + 300 s
      (fills whose mid is invalid then are excluded and the covered notional is stored).
  E13 Taker-exit P&L = (exit price - implied mid at the decision) x quantity, signed, plus its taker fee.
Inference and reporting
  I1  Control (ii) bias per strategy = the larger of (a) pooled sum(net)/sum(filled) trades-only minus
      true-book and (b) the mean over symbol-days of the same difference; if it exceeds +0.5 bp the WHOLE
      bias (not only the part above 0.5 bp) is subtracted per $ filled for PASS condition 5. Q3 and Q1-LO
      use Q1's bias. The corrected statistic and edge are written next to the uncorrected ones so the combine
      script can apply "a cell whose verdict changes under the correction is INCONCLUSIVE".
  I2  Drop-worst-day groups pair-days by UTC calendar day across all pairs of the cell.
  I3  Splits use the 30 days before the month: median pre-trade implied spread in ticks (tick = gcd over the
      30 days), spread (bp) / SD of 60-s implied-mid log changes (bp); terciles within band across that
      band's pair-months; volatility = SD of daily kline log returns over the same 30 days; listing age from
      the first monthly kline in the archive, bucketed <1 y, 1-3 y, >=3 y.
  I4  Day-block bootstrap: 4,999 resamples of UTC days (seed 20261018), p as in the general rules.
      Month-level t: the 12 monthly means of net $ per pair-day, Student t with 11 df.
  I5  Capital = 4 x order size per pair; annualized return = 365 x mean net $ per pair-day / capital;
      Sharpe = mean/SD of net $ per pair-day x sqrt(365) (one pair as one account); also the band-portfolio
      version (daily mean over pairs). SPY: adjusted close from data/universe_recent_raw, 20% LT tax.
Controls
  C1  Control (i) market: makers quote B* and B* + S around an exogenous random walk (one-tick moves every
      30 s on average); on a move the side that would be crossed is pulled at once and the other side follows
      after 2 s, so a no-information market never sweeps a stale order; every aggressor order sweeps the
      best queue (exponential, mean $1,000) and then $2,000 per deeper level, after which the book refills;
      informed orders (share alpha) trade in the direction of the mid change over the next 60 s. Sizes are
      resampled from the pilot band-A (or band-C) pairs' taker orders. Markouts are to the book mid.
  C2  Control (ii)/(iii) use the same day's prices for the tick (book and trades) and the same day's taker
      orders for the walk in BOTH legs (no 7 prior futures days are downloaded); the session runs 00:00-23:50
      UTC and the flatten at 23:50 is priced off that day's later prints; the trades-only leg starts with
      no carried quote. Book mode treats the bookTicker as the truth: quote valid when two-sided; Q2's 10-s
      print-freshness rule is kept (it is part of the strategy); joining = queue ahead equal to the displayed
      size at activation, depleted only by prints at our price (no cancels ahead); any trade-through fills
      at least its through volume; a book that crosses our resting order fills it as maker; an order that
      would cross on activation takes the displayed size as taker (post-only: rejected).

---------------------------------------------------------------------------------------------- Deviations
(Places where the pre-registration could not be followed exactly.)
  D1  Control (ii)/(iii): tick and walk come from the control day itself, not days d-7..d-1, and the session ends
      at 23:50 with an in-file flatten instead of a next-day file (C2). Both legs use identical inputs, so the
      trades-only minus true-book difference, which is all the control feeds into Part A, is not affected by it.
  D2  A-RH needs data/scalping/rh/currency_pairs.json (a read-only get_currency_pairs response saved by an agent
      session); until it exists the stratum is skipped and reported as missing.
Notes (the draw as specified, not deviations)
  N1  Band A ($50-200k) has only 1, 2 and 0 eligible pairs in 2025-10, -11 and -12, so min(k, n) yields 3 band-A
      pair-months in the first quarter (33 in the first half vs 60 in the second); bands B-D are full.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import math
import os
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pacsv
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026 import scalp_stats as SS  # noqa: E402
from analysis_2026.fetch_scalping_data import s3_get_zip_csv, s3_ls  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "analysis_2026" / "results_scalping" / "A"
DATA = ROOT / "data" / "scalping" / "A"
KLINES = ROOT / "data" / "scalping" / "binance" / "klines_1d.parquet"
RH_PAIRS = ROOT / "data" / "scalping" / "rh" / "currency_pairs.json"
PILOT_TRADES = ROOT / "data" / "scalping" / "binance_pilot" / "spot_trades"
SPY_PRICES = ROOT / "data" / "universe_recent_raw" / "prices.parquet"

SEED = 20261018
P0 = date(2025, 10, 1)
MONTHS = [pd.Timestamp(2025, 10, 1) + pd.DateOffset(months=m) for m in range(12)]
BANDS = {"A": (50e3, 200e3), "B": (200e3, 1e6), "C": (1e6, 5e6), "D": (5e6, 50e6)}
K_DRAW = {"A": 10, "B": 10, "C": 5, "D": 5}
PILOT = [s + "USDT" for s in "GNO XVS REQ KNC KSM SUSHI COMP TRB RUNE GALA ETC ATOM LTC LINK BTC HOODB".split()]
UM_SYMS = [s + "USDT" for s in "DGB XVS KNC KSM COMP RUNE ETC ATOM LINK LTC BTC BTCDOM DEFI ORBS STPT HFT OXT".split()]
UM_RANGE = (date(2023, 5, 16), date(2024, 3, 30))
UM_EXCLUDED = date(2024, 3, 29)

STABLE_FIAT = ("USDC FDUSD TUSD USDP DAI BUSD PYUSD USDS USDE USD1 RLUSD XUSD BFUSD U KGST USTC "
               "EUR EURI AEUR TRY BRL GBP AUD JPY RUB UAH ZAR NGN IDRT BIDR PLN ARS MXN COP CZK").split()
PEGGED_RWA = "PAXG XAUT".split()
WRAPPED = "WBTC WBETH BETH BNSOL STETH WSTETH CBETH RETH".split()
EQUITY_FIRST = pd.Timestamp(2026, 6, 1)

SCALE = 1e-8               # prices are int64 in units of 1e-8
STALE, FRESH, TMAX = 300.0, 10.0, 3600.0
MIN_NOTIONAL = 5.0
DAY = 86400.0
E_THRESH = 1.0             # bp net per $ filled
FEES = [(0, 2), (1, 3), (2, 5), (7.5, 7.5), (12.5, 25), (50, 90), (50, 95)]
FEE_NAMES = ["0/2 Binance.US (primary)", "1/3 Robinhood $10-25M", "2/5 Binance USD-M VIP0",
             "7.5/7.5 Binance.com VIP0+BNB", "12.5/25 Robinhood $50-250k", "50/90 Coinbase entry",
             "50/95 Robinhood entry"]
REBATES = [-0.5, -1.0, -2.0, -5.0]

# strategy and fill codes (numba sees module ints as constants)
Q1, Q2, Q3, Q5, Q1LO = 1, 2, 3, 5, 6
STRAT_NAME = {Q1: "Q1", Q2: "Q2", Q3: "Q3", Q5: "Q5", Q1LO: "Q1LO"}
F1, F2, FIFO, FRONT = 0, 1, 2, 3
FILL_NAME = {F1: "F1", F2: "F2", FIFO: "FIFO", FRONT: "FRONT"}

RES_NAMES = ["gross_usd", "maker_usd", "taker_usd", "crossed_usd", "exit_usd", "n_maker", "n_crossed", "n_exits",
             "filled_usd", "max_inv_usd", "mk60_usd", "mk60_cov_usd", "mk300_usd", "mk300_cov_usd", "exit_cost_usd",
             "n_orders", "n_cancels", "n_orders_filled", "flag_bits", "n_tmax", "n_postonly_cancel", "eod_inv_usd",
             "bought_usd", "sold_usd", "mk0_usd", "mk0_cov_usd"]
(R_GROSS, R_MAKER, R_TAKER, R_CROSSED, R_EXIT, R_NMF, R_NCF, R_NEX, R_FILLED, R_MAXINV, R_MK60, R_MK60C, R_MK300,
 R_MK300C, R_EXCOST, R_NORD, R_NCAN, R_NOF, R_FLAGS, R_NTMAX, R_NPOC, R_EODINV, R_BOUGHT, R_SOLD, R_MK0,
 R_MK0C) = range(26)
NRES = 26
FLAG_STOPPED, FLAG_OVERFLOW, FLAG_RESIDUAL, FLAG_MKFULL, FLAG_NODATA, FLAG_NONEXT = 1, 2, 4, 8, 16, 32


def cfg_name(strat, size, fill, delta, part):
    return f"{STRAT_NAME[strat]}_{int(size // 1000)}k_{FILL_NAME[fill]}_{int(round(delta * 1000))}ms_{int(round(part * 100))}"


# primary + every sensitivity the PASS rule and the reporting need
MAIN_CONFIGS = ([(s, 1000, F1, 0.25, 1.0) for s in (Q1, Q2, Q5)] +          # primary
                [(s, 1000, F1, 1.0, 1.0) for s in (Q1, Q2, Q5)] +           # PASS condition 3
                [(s, 1000, F2, 0.25, 1.0) for s in (Q1, Q2, Q5, Q3)] +      # kill rule / illusion baseline
                [(s, z, F1, 0.25, 1.0) for z in (10000, 25000) for s in (Q1, Q2, Q5)] +   # capacity
                [(s, 1000, F1, 0.25, 0.25) for s in (Q1, Q2, Q5)] +         # 25% participation
                [(Q3, 1000, F1, 0.25, 1.0)])                                # Q3 exploratory
ARH_CONFIGS = [(s, 1000, f, d, 1.0) for s in (Q1, Q2, Q5, Q1LO) for f, d in ((F1, 0.25), (F1, 1.0), (F2, 0.25))]
PRIMARY = {s: cfg_name(s, 1000, F1, 0.25, 1.0) for s in (Q1, Q2, Q5, Q3, Q1LO)}
DELTA1 = {s: cfg_name(s, 1000, F1, 1.0, 1.0) for s in (Q1, Q2, Q5, Q1LO)}
F2CFG = {s: cfg_name(s, 1000, F2, 0.25, 1.0) for s in (Q1, Q2, Q5, Q3, Q1LO)}


# ============================================================================================ universe
def load_klines() -> pd.DataFrame:
    k = pd.read_parquet(KLINES)
    k["day"] = pd.to_datetime(k["day"]).dt.normalize()
    return k


def exclusions(k: pd.DataFrame) -> pd.DataFrame:
    """Fixed from the symbol list (and first-kline dates) before any simulation."""
    first = k.groupby("sym").day.min()
    rows = []
    for s in sorted(first.index):
        base = s[:-4]
        if base in STABLE_FIAT:
            rows.append((s, base, "stablecoin/fiat base"))
        elif base in PEGGED_RWA:
            rows.append((s, base, "gold-backed token (pegged real-world asset)"))
        elif base in WRAPPED:
            rows.append((s, base, "wrapped/staked token"))
        elif base.endswith("B") and first[s] >= EQUITY_FIRST:
            rows.append((s, base, "tokenized equity (stock/ETF ticker + B, listed 2026-06 or later)"))
    return pd.DataFrame(rows, columns=["sym", "base", "reason"])


def band_of(v: float) -> str:
    for b, (lo, hi) in BANDS.items():
        if lo <= v < hi:
            return b
    return "<A" if v < BANDS["A"][0] else ">D"


def eligibility(k: pd.DataFrame, excl: pd.DataFrame) -> pd.DataFrame:
    ex = set(excl.sym)
    rows = []
    for m, ms in enumerate(MONTHS):
        prev = ms - pd.Timedelta(days=1)
        h = k[k.day < ms]
        n = h.groupby("sym").size()
        last = h[h.day == prev].set_index("sym").quote_volume
        w = h[h.day >= ms - pd.Timedelta(days=30)].pivot_table(index="day", columns="sym", values="quote_volume")
        w = w.reindex(pd.date_range(ms - pd.Timedelta(days=30), prev, freq="D")).fillna(0.0)
        for s in n.index:
            med = float(w[s].median()) if s in w else 0.0
            ok90 = int(n[s]) >= 90
            oklast = bool(s in last.index and last[s] > 0)
            rows.append(dict(m=m, month=ms.strftime("%Y-%m"), sym=s, n_klines=int(n[s]), last_day_qv=float(last.get(s, 0.0)),
                             med30_qv=med, band=band_of(med), excluded=s in ex, pilot=s in PILOT,
                             eligible=ok90 and oklast and s not in ex))
    return pd.DataFrame(rows)


def draw(elig: pd.DataFrame) -> pd.DataFrame:
    drawn = {b: set() for b in BANDS}
    rows = []
    for m in range(12):
        e = elig[(elig.m == m) & elig.eligible]
        for b in BANDS:
            k_ = K_DRAW[b]
            pool = sorted(s for s in e[e.band == b].sym if s not in PILOT)
            cands = [s for s in pool if s not in drawn[b]]
            rng = np.random.default_rng(SEED + m)
            pick = [str(x) for x in rng.choice(cands, size=min(k_, len(cands)), replace=False)] if cands else []
            fb = []
            if len(pick) < k_:
                rest = [s for s in pool if s not in pick]
                fb = [str(x) for x in rng.choice(rest, size=min(k_ - len(pick), len(rest)), replace=False)] if rest else []
            for i, s in enumerate(pick + fb):
                rows.append(dict(m=m, month=MONTHS[m].strftime("%Y-%m"), band=b, sym=s, slot=i, fallback=i >= len(pick),
                                 n_candidates=len(cands), n_band_eligible=len(pool)))
            drawn[b] |= set(pick) | set(fb)
    return pd.DataFrame(rows)


def rh_bases(path: Path = RH_PAIRS) -> list[str]:
    """Base asset codes from a saved Robinhood get_currency_pairs response (any wrapper)."""
    text = path.read_text()
    i = min([j for j in (text.find("{"), text.find("[")) if j >= 0], default=0)
    stack, codes = [json.loads(text[i:])], set()
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            ac = o.get("asset_currency")
            if isinstance(ac, dict) and isinstance(ac.get("code"), str):
                codes.add(ac["code"].upper())
            sym = o.get("symbol")
            if isinstance(sym, str) and "-" in sym and sym.upper().endswith(("-USD", "-USDT", "-USDC")):
                codes.add(sym.split("-")[0].upper())
            for v in o.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
                elif isinstance(v, str) and v.lstrip()[:1] in "{[":
                    try:
                        stack.append(json.loads(v))
                    except ValueError:
                        pass
        elif isinstance(o, list):
            stack.extend(o)
    return sorted(c for c in codes if c not in ("USD",))


def arh_pairs(k: pd.DataFrame, excl: pd.DataFrame) -> pd.DataFrame | None:
    if not RH_PAIRS.exists():
        return None
    syms = set(k.sym)
    bases = rh_bases()
    want = sorted({b + "USDT" for b in bases if b + "USDT" in syms} | {"BTCUSDT", "ETHUSDT"})
    ex = set(excl.sym)
    return pd.DataFrame(dict(sym=want, excluded=[s in ex for s in want], rh_listed=[s[:-4] in bases for s in want]))


def universe(write=True):
    k = load_klines()
    excl = exclusions(k)
    elig = eligibility(k, excl)
    dr = draw(elig)
    arh = arh_pairs(k, excl)
    if write:
        RES.mkdir(parents=True, exist_ok=True)
        excl.to_csv(RES / "exclusions.csv", index=False)
        elig.to_csv(RES / "eligibility.csv", index=False)
        dr.to_csv(RES / "draws.csv", index=False)
        if arh is not None:
            arh.to_csv(RES / "arh_pairs.csv", index=False)
    return k, excl, elig, dr, arh


# ============================================================================================ data
SPOT_COLS = ["id", "price", "qty", "quote", "time", "ibm", "best"]


def parse_trades(b: bytes, futures: bool = False) -> dict | None:
    """Binance trades CSV -> arrays sorted by (time, id). Spot: no header, us from 2025; futures: header, ms."""
    if b is None or len(b) == 0:
        return None
    header = not b[:1].isdigit()
    ro = pacsv.ReadOptions(autogenerate_column_names=False, column_names=None if header else SPOT_COLS[:len(b.split(b"\n", 1)[0].split(b","))],
                           skip_rows=0)
    t = pacsv.read_csv(io.BytesIO(b), read_options=ro)
    cols = t.column_names
    if header:
        ren = {"quote_qty": "quote", "quoteQty": "quote", "is_buyer_maker": "ibm", "isBuyerMaker": "ibm"}
        cols = [ren.get(c, c) for c in cols]
        t = t.rename_columns(cols)
    if t.num_rows == 0:
        return None
    tm = t.column("time").to_numpy().astype(np.int64)
    ibm = t.column("ibm").to_numpy(zero_copy_only=False)
    if ibm.dtype != np.bool_:
        ibm = np.char.lower(ibm.astype(str)) == "true"
    unit = 1 if tm[0] > 10 ** 14 else 1000                      # -> microseconds
    d = dict(t_us=tm * unit, id=t.column("id").to_numpy().astype(np.int64),
             px=np.rint(t.column("price").to_numpy().astype(np.float64) / SCALE).astype(np.int64),
             qty=t.column("qty").to_numpy().astype(np.float64), quote=t.column("quote").to_numpy().astype(np.float64),
             ibm=ibm.astype(np.bool_))
    o = np.lexsort((d["id"], d["t_us"]))
    if not (np.all(np.diff(o) == 1)):
        d = {k_: v[o] for k_, v in d.items()}
    return d


def parse_book(b: bytes) -> dict | None:
    if b is None:
        return None
    cols = ["update_id", "best_bid_price", "best_bid_qty", "best_ask_price", "best_ask_qty", "transaction_time"]
    t = pacsv.read_csv(io.BytesIO(b), convert_options=pacsv.ConvertOptions(
        include_columns=cols, column_types={c: (pa.int64() if c in ("update_id", "transaction_time") else pa.float64()) for c in cols}))
    if t.num_rows == 0:
        return None
    tt = t.column("transaction_time").to_numpy().astype(np.int64)
    uid = t.column("update_id").to_numpy().astype(np.int64)
    o = np.lexsort((uid, tt))
    f = lambda c: t.column(c).to_numpy().astype(np.float64)[o]  # noqa: E731
    return dict(t_us=tt[o] * 1000, bid=np.rint(f("best_bid_price") / SCALE).astype(np.int64), bq=f("best_bid_qty"),
                ask=np.rint(f("best_ask_price") / SCALE).astype(np.int64), aq=f("best_ask_qty"))


def spot_key(sym, d):
    return f"data/spot/daily/trades/{sym}/{sym}-trades-{d:%Y-%m-%d}.zip"


def fetch_spot(sym, d):
    for k in range(3):
        try:
            return s3_get_zip_csv(spot_key(sym, d))
        except (IOError, zipfile.BadZipFile):
            if k == 2:
                raise
    return None


# ============================================================================================ numba kernels
@njit(cache=True)
def _gcd(a, b):
    a = abs(a)
    b = abs(b)
    while b:
        a, b = b, a % b
    return a


@njit(cache=True)
def price_grid(px):
    """(reference price, gcd of gaps from it) of a price array; gcd 0 if fewer than two distinct prices."""
    if px.shape[0] == 0:
        return -1, 0
    ref = px[0]
    g = 0
    for p in px:
        d = abs(p - ref)
        if d > 0 and (g == 0 or d % g != 0):
            g = _gcd(g, d)
    return ref, g


@njit(cache=True)
def build_events(t_us, ibm, px, quote):
    """Taker orders = runs of prints with the same timestamp and aggressor side."""
    n = t_us.shape[0]
    ne = 0
    for j in range(n):
        if j == 0 or t_us[j] != t_us[j - 1] or ibm[j] != ibm[j - 1]:
            ne += 1
    ev_tu = np.empty(ne, np.int64)
    side = np.empty(ne, np.int8)
    st = np.empty(ne, np.int64)
    en = np.empty(ne, np.int64)
    pf = np.empty(ne, np.int64)
    pl = np.empty(ne, np.int64)
    nt = np.zeros(ne)
    wk = np.zeros(ne)
    k = -1
    for j in range(n):
        if j == 0 or t_us[j] != t_us[j - 1] or ibm[j] != ibm[j - 1]:
            if k >= 0:
                en[k] = j
            k += 1
            st[k] = j
            ev_tu[k] = t_us[j]
            side[k] = -1 if ibm[j] else 1
        nt[k] += quote[j]
    if k >= 0:
        en[k] = n
    for k in range(ne):
        pf[k] = px[st[k]]
        pl[k] = px[en[k] - 1]
        if side[k] < 0:
            wk[k] = (pf[k] - pl[k]) / pf[k]
        else:
            wk[k] = (pl[k] - pf[k]) / pf[k]
    return ev_tu, side, st, en, pf, pl, nt, wk


@njit(cache=True)
def next_side(side):
    """nxt_s[j] = first index >= j of a seller-initiated order (n if none); nxt_b likewise for buyers."""
    n = side.shape[0]
    ns = np.empty(n + 1, np.int64)
    nb = np.empty(n + 1, np.int64)
    ns[n] = n
    nb[n] = n
    for j in range(n - 1, -1, -1):
        ns[j] = j if side[j] < 0 else ns[j + 1]
        nb[j] = j if side[j] > 0 else nb[j + 1]
    return ns, nb


@njit(cache=True)
def _fen_find(fen, n, r, top):
    pos = 0
    b = top
    while b > 0:
        if pos + b <= n and fen[pos + b] < r:
            pos += b
            r -= fen[pos]
        b >>= 1
    return pos


@njit(cache=True)
def walk_table(notional, walk):
    """Sorted notionals (ascending), medk[k] = median walk of the k largest orders, median notional of the top 10."""
    n = notional.shape[0]
    asc = np.sort(notional)
    medk = np.zeros(n + 1)
    if n == 0:
        return asc, medk, 0.0
    order = np.argsort(-notional, kind="mergesort")
    w = walk[order]
    ro = np.argsort(w, kind="mergesort")
    sw = w[ro]
    rank = np.empty(n, np.int64)
    for i in range(n):
        rank[ro[i]] = i
    fen = np.zeros(n + 1, np.int64)
    top = 1
    while top * 2 <= n:
        top *= 2
    for k in range(1, n + 1):
        i = rank[k - 1] + 1
        while i <= n:
            fen[i] += 1
            i += i & (-i)
        if k % 2 == 1:
            medk[k] = sw[_fen_find(fen, n, (k + 1) // 2, top)]
        else:
            medk[k] = 0.5 * (sw[_fen_find(fen, n, k // 2, top)] + sw[_fen_find(fen, n, k // 2 + 1, top)])
    m = min(n, 10)
    mn10 = np.median(notional[order[:m]])
    return asc, medk, mn10


@njit(cache=True)
def walk_lookup(N, asc, medk, mn10):
    """Median walk of orders with notional >= N; if fewer than 10, the 10 largest's median walk x sqrt(N / their
    median notional)."""
    n = asc.shape[0]
    if n == 0:
        return 0.0
    k = n - np.searchsorted(asc, N)
    if k >= 10:
        return medk[k]
    m = min(n, 10)
    if mn10 <= 0:
        return medk[m]
    return medk[m] * math.sqrt(N / mn10)


@njit(cache=True)
def day_stats(ev_t, side, pl, ib, tb, ia, ta, t_end):
    """Pre-trade valid implied spreads/mids of the day's taker orders, the implied mid on the 60-s grid, and the
    quote state at the end of the day (times relative to the day start)."""
    n = ev_t.shape[0]
    spr = np.empty(n, np.int64)
    mid = np.empty(n)
    c = 0
    grid = np.full(1440, np.nan)
    gi = 0
    for k in range(n):
        T = ev_t[k]
        if T >= t_end:
            break
        while gi < 1440 and 60.0 * (gi + 1) < T:
            tg = 60.0 * (gi + 1)
            if ia > ib and ib > 0 and tg - tb <= STALE and tg - ta <= STALE:
                grid[gi] = 0.5 * (ia + ib)
            gi += 1
        if ia > ib and ib > 0 and T - tb <= STALE and T - ta <= STALE:
            spr[c] = ia - ib
            mid[c] = 0.5 * (ia + ib)
            c += 1
        if side[k] < 0:
            ib = pl[k]
            tb = T
        else:
            ia = pl[k]
            ta = T
    while gi < 1440:
        tg = 60.0 * (gi + 1)
        if ia > ib and ib > 0 and tg - tb <= STALE and tg - ta <= STALE:
            grid[gi] = 0.5 * (ia + ib)
        gi += 1
    return spr[:c], mid[:c], grid, ib, tb, ia, ta


@njit(cache=True)
def _cur_mid(mk_src, due, ib, tb, ia, ta, bb, ba):
    if mk_src == 0:
        if ia > ib and ib > 0 and due - tb <= STALE and due - ta <= STALE:
            return 0.5 * (ia + ib)
        return -1.0
    if bb > 0 and ba > bb:
        return 0.5 * (bb + ba)
    return -1.0


@njit(cache=True)
def _push(pq_t, pq_op, pq_px, pq_q, pq_po, ph, pc, s, t, op, px, qty, po, res):
    cap_ = pq_t.shape[1]
    if pc[s] >= cap_:
        j = (ph[s] + pc[s] - 1) % cap_
        res[R_FLAGS] = float(int(res[R_FLAGS]) | FLAG_OVERFLOW)
    else:
        j = (ph[s] + pc[s]) % cap_
        pc[s] += 1
    pq_t[s, j] = t
    pq_op[s, j] = op
    pq_px[s, j] = px
    pq_q[s, j] = qty
    pq_po[s, j] = po


@njit(cache=True)
def _fill(SF, SI, res, s, price, qty, maker, T, delta, eps, strat, q5ref, tick):
    """Book one fill of our resting order on side s (0 bid: we buy, 1 ask: we sell) at price ($)."""
    usd = qty * price
    if s == 0:
        SF[0] += qty
        SF[1] -= usd
        res[R_BOUGHT] += usd
        if strat == Q5 and SI[0] < 0:            # Q5 offer: max(implied ask at fill time, fill + 1 tick)
            tk = tick if tick > 0 else 1
            fp = int(round(price / SCALE))
            SI[0] = max(q5ref, fp + tk)
    else:
        SF[0] -= qty
        SF[1] += usd
        res[R_SOLD] += usd
    res[R_FILLED] += usd
    if maker:
        res[R_MAKER] += usd
        res[R_NMF] += 1
    else:
        res[R_TAKER] += usd
        res[R_CROSSED] += usd
        res[R_NCF] += 1
    _inv_change(SF, SI, res, T, delta, eps, price)


@njit(cache=True)
def _inv_change(SF, SI, res, T, delta, eps, price):
    if abs(SF[0]) <= eps:
        SF[0] = 0.0
        SF[2] = -1.0
        SF[3] = 1e30
        SI[0] = -1
    elif SF[2] < 0:
        SF[2] = T + delta
        SF[3] = T + delta + TMAX
    v = abs(SF[0]) * price
    if v > res[R_MAXINV]:
        res[R_MAXINV] = v


@njit(cache=True)
def engine(ev_t, ev_side, ev_st, ev_en, ev_pf, ev_pl, pr_px, pr_q,
           bk_t, bk_b, bk_bq, bk_a, bk_aq, nxt_s, nxt_b,
           ib, tb, ia, ta, tick, ref,
           ws_asc, ws_medk, ws_mn10, wb_asc, wb_medk, wb_mn10,
           strat, q, delta, fill, part, mode, mk_src, t_close, t_hard, min_not):
    """Simulate one strategy on one pair-day. mode 0: implied quotes from prints (F1/F2); mode 1: true book
    (FIFO/FRONT). Times in seconds from the day start; prices int (1e-8). Returns the result vector."""
    INF = 1e30
    res = np.zeros(NRES)
    n_ev = ev_t.shape[0]
    n_bk = bk_t.shape[0]
    cap = 3.0 * q
    eps = 1e-9 * q
    long_only = strat == Q5 or strat == Q1LO
    bb = -1
    ba = -1
    bq = 0.0
    aq = 0.0
    last_spr = 0.0
    if ia > ib and ib > 0:
        last_spr = (ia - ib) / (0.5 * (ia + ib))
    SF = np.zeros(4)                 # inv, cash, nonzero-since, T_max timer
    SF[2] = -1.0
    SF[3] = INF
    SI = np.full(1, -1, np.int64)    # Q5 offer price
    lon = np.zeros(2, np.bool_)
    lpx = np.zeros(2, np.int64)
    lrem = np.zeros(2)
    lpo = np.zeros(2, np.bool_)
    lqa = np.zeros(2)
    lfl = np.zeros(2, np.bool_)
    CAP = 4096
    pq_t = np.zeros((2, CAP))
    pq_op = np.zeros((2, CAP), np.int8)
    pq_px = np.zeros((2, CAP), np.int64)
    pq_q = np.zeros((2, CAP))
    pq_po = np.zeros((2, CAP), np.bool_)
    ph = np.zeros(2, np.int64)
    pc = np.zeros(2, np.int64)
    M = n_ev + 1024
    fr_t = np.empty(M)
    fr_s = np.empty(M)
    fr_p = np.empty(M)
    fr_q = np.empty(M)
    nfr = 0
    h60 = 0
    h300 = 0
    tm_open = 0.0
    tm_qexp = INF
    tm_fresh = INF
    tm_eod = t_close - delta
    tm_mid = t_close
    ex_t = INF
    ex_rb = -1
    ex_ra = -1
    ex_mid = -1.0
    flattening = False
    eod = False
    iev = 0
    ibk = 0
    while True:
        t_ev = ev_t[iev] if iev < n_ev else INF
        t_bk = bk_t[ibk] if ibk < n_bk else INF
        t_mk = t_ev if t_ev <= t_bk else t_bk
        t_act = INF
        s_act = -1
        for s in range(2):
            if pc[s] > 0 and pq_t[s, ph[s]] < t_act:
                t_act = pq_t[s, ph[s]]
                s_act = s
        t_tm = min(tm_open, tm_qexp, tm_fresh, SF[3], tm_eod, tm_mid)
        T = min(min(t_act, ex_t), min(t_tm, t_mk))
        if T >= t_hard or T >= INF:
            break
        need = False
        if t_act <= T:
            # ---------------------------------------------------------------- an order action takes effect
            s = s_act
            j = ph[s]
            op = pq_op[s, j]
            px = pq_px[s, j]
            qq = pq_q[s, j]
            po = pq_po[s, j]
            ph[s] = (j + 1) % CAP
            pc[s] -= 1
            if op == 0:
                lon[s] = False
            else:
                if long_only and s == 1:
                    qq = min(qq, max(SF[0], 0.0))
                lon[s] = qq > eps
                lpx[s] = px
                lrem[s] = qq
                lpo[s] = po
                lfl[s] = False
                lqa[s] = 0.0
                if lon[s] and mode == 1:
                    if s == 0:
                        cross = ba > 0 and ba <= px
                        oq = aq
                        opx = ba
                        same = bb
                        sq = bq
                    else:
                        cross = bb > 0 and bb >= px
                        oq = bq
                        opx = bb
                        same = ba
                        sq = aq
                    if cross:
                        if po:
                            lon[s] = False
                            res[R_NPOC] += 1
                        else:
                            f = min(lrem[s], part * oq)
                            if f > 0:
                                _fill(SF, SI, res, s, opx * SCALE, f, False, T, delta, eps, strat, ia if mode == 0 else ba, tick)
                                lrem[s] -= f
                                lfl[s] = True
                                res[R_NOF] += 1
                                if lrem[s] <= eps:
                                    lon[s] = False
                        need = True
                    elif fill == FRONT or same <= 0:
                        lqa[s] = 0.0
                    elif px == same:
                        lqa[s] = sq
                    elif (s == 0 and px > same) or (s == 1 and px < same):
                        lqa[s] = 0.0
                    else:
                        lqa[s] = INF
        elif ex_t <= T:
            # ---------------------------------------------------------------- taker exit executes
            qty = SF[0]
            if abs(qty) > eps:
                j0 = np.searchsorted(ev_t, T)
                if qty > 0:
                    k = nxt_s[j0] if j0 < n_ev else n_ev
                    if k < n_ev:
                        R = ev_pf[k]
                        if ex_rb > 0 and ex_rb < R:
                            R = ex_rb
                        Rf = R * SCALE
                        w = walk_lookup(qty * Rf, ws_asc, ws_medk, ws_mn10)
                        if tick > 0:
                            w = max(w, tick / R)
                        price = Rf * (1.0 - w)
                    else:
                        lp = ib if ib > 0 else ia
                        price = lp * SCALE * (1.0 - last_spr)
                        res[R_FLAGS] = float(int(res[R_FLAGS]) | FLAG_STOPPED)
                    SF[1] += qty * price
                else:
                    k = nxt_b[j0] if j0 < n_ev else n_ev
                    if k < n_ev:
                        R = ev_pf[k]
                        if ex_ra > 0 and ex_ra > R:
                            R = ex_ra
                        Rf = R * SCALE
                        w = walk_lookup(-qty * Rf, wb_asc, wb_medk, wb_mn10)
                        if tick > 0:
                            w = max(w, tick / R)
                        price = Rf * (1.0 + w)
                    else:
                        lp = ia if ia > 0 else ib
                        price = lp * SCALE * (1.0 + last_spr)
                        res[R_FLAGS] = float(int(res[R_FLAGS]) | FLAG_STOPPED)
                    SF[1] += qty * price
                usd = abs(qty) * price
                res[R_TAKER] += usd
                res[R_EXIT] += usd
                res[R_NEX] += 1
                if ex_mid > 0:
                    res[R_EXCOST] += (price - ex_mid * SCALE) * qty
                SF[0] = 0.0
                _inv_change(SF, SI, res, T, delta, eps, price)
            ex_t = INF
            flattening = False
            need = True
        elif t_tm <= T:
            # ---------------------------------------------------------------- timers
            if tm_open <= T:
                tm_open = INF
                need = True
            elif tm_eod <= T:
                tm_eod = INF
                eod = True
                need = True
            elif tm_mid <= T:
                tm_mid = INF
                m_ = _cur_mid(1 if mode == 1 else 0, T, ib, tb, ia, ta, bb, ba)
                res[R_EODINV] = abs(SF[0]) * (m_ * SCALE if m_ > 0 else max(ib, ia) * SCALE)
                if abs(SF[0]) > eps and ex_t >= INF:
                    ex_t = T + delta
                    ex_rb = ib if mode == 0 else bb
                    ex_ra = ia if mode == 0 else ba
                    ex_mid = 0.5 * (ex_rb + ex_ra) if (ex_rb > 0 and ex_ra > ex_rb) else -1.0
                    flattening = True
            elif SF[3] <= T:
                SF[3] = INF
                if (not eod) and ex_t >= INF and abs(SF[0]) > eps:
                    flattening = True
                    ex_t = T + delta
                    ex_rb = ib if mode == 0 else bb
                    ex_ra = ia if mode == 0 else ba
                    ex_mid = 0.5 * (ex_rb + ex_ra) if (ex_rb > 0 and ex_ra > ex_rb) else -1.0
                    res[R_NTMAX] += 1
                    need = True
            elif tm_qexp <= T:
                tm_qexp = INF
                need = True
            else:
                tm_fresh = INF
                need = True
        else:
            # ---------------------------------------------------------------- market data
            while h60 < nfr and fr_t[h60] + 60.0 < T:
                m_ = _cur_mid(mk_src, fr_t[h60] + 60.0, ib, tb, ia, ta, bb, ba)
                if m_ > 0:
                    res[R_MK60] += fr_s[h60] * (m_ * SCALE - fr_p[h60]) * fr_q[h60]
                    res[R_MK60C] += fr_p[h60] * fr_q[h60]
                h60 += 1
            while h300 < nfr and fr_t[h300] + 300.0 < T:
                m_ = _cur_mid(mk_src, fr_t[h300] + 300.0, ib, tb, ia, ta, bb, ba)
                if m_ > 0:
                    res[R_MK300] += fr_s[h300] * (m_ * SCALE - fr_p[h300]) * fr_q[h300]
                    res[R_MK300C] += fr_p[h300] * fr_q[h300]
                h300 += 1
            if t_ev <= t_bk:
                k = iev
                iev += 1
                sd = ev_side[k]
                st0 = ev_st[k]
                en0 = ev_en[k]
                if T < t_close:
                    m0 = _cur_mid(mk_src, T, ib, tb, ia, ta, bb, ba)
                    used = False
                    o = 0 if sd > 0 else 1           # the side a crossing print reaches
                    if mode == 0 and lon[o]:
                        P = lpx[o]
                        vr = 0.0
                        worst = -1
                        for j in range(st0, en0):
                            p = pr_px[j]
                            if (o == 0 and p <= P) or (o == 1 and p >= P):
                                vr += pr_q[j]
                                if worst < 0 or (o == 0 and p > worst) or (o == 1 and p < worst):
                                    worst = p
                        if vr > 0:
                            if lpo[o]:
                                lon[o] = False
                                res[R_NPOC] += 1
                            else:
                                f = min(lrem[o], part * vr)
                                _fill(SF, SI, res, o, worst * SCALE, f, False, T, delta, eps, strat, ia if mode == 0 else ba, tick)
                                lrem[o] -= f
                                if not lfl[o]:
                                    lfl[o] = True
                                    res[R_NOF] += 1
                                if lrem[o] <= eps:
                                    lon[o] = False
                                used = True
                    sm = 0 if sd < 0 else 1              # the side this aggressor can fill passively
                    if (not used) and lon[sm]:
                        P = lpx[sm]
                        f = 0.0
                        if mode == 0:
                            vol = 0.0
                            for j in range(st0, en0):
                                p = pr_px[j]
                                if fill == F1:
                                    c_ = p < P if sm == 0 else p > P
                                else:
                                    c_ = p <= P if sm == 0 else p >= P
                                if c_:
                                    vol += pr_q[j]
                            f = min(lrem[sm], part * vol)
                        else:
                            va = 0.0
                            vt = 0.0
                            for j in range(st0, en0):
                                p = pr_px[j]
                                if p == P:
                                    va += pr_q[j]
                                elif (sm == 0 and p < P) or (sm == 1 and p > P):
                                    vt += pr_q[j]
                            if vt > 0:
                                avail = max(vt, va + vt - lqa[sm])
                                lqa[sm] = 0.0
                            else:
                                avail = max(0.0, va - lqa[sm])
                                lqa[sm] = max(0.0, lqa[sm] - va)
                            f = min(lrem[sm], part * avail)
                        if f > 0:
                            _fill(SF, SI, res, sm, P * SCALE, f, True, T, delta, eps, strat, ia if mode == 0 else ba, tick)
                            lrem[sm] -= f
                            if not lfl[sm]:
                                lfl[sm] = True
                                res[R_NOF] += 1
                            if lrem[sm] <= eps:
                                lon[sm] = False
                            sg = 1.0 if sm == 0 else -1.0
                            if nfr < M:
                                fr_t[nfr] = T
                                fr_s[nfr] = sg
                                fr_p[nfr] = P * SCALE
                                fr_q[nfr] = f
                                nfr += 1
                            else:
                                res[R_FLAGS] = float(int(res[R_FLAGS]) | FLAG_MKFULL)
                            if m0 > 0:
                                res[R_MK0] += sg * (m0 - P) * SCALE * f
                                res[R_MK0C] += P * SCALE * f
                # quote state and tick grid
                for j in range(st0, en0):
                    p = pr_px[j]
                    if ref < 0:
                        ref = p
                    else:
                        d = abs(p - ref)
                        if d > 0 and (tick == 0 or d % tick != 0):
                            tick = _gcd(tick, d)
                if sd < 0:
                    ib = ev_pl[k]
                    tb = T
                else:
                    ia = ev_pl[k]
                    ta = T
                if ia > ib and ib > 0:
                    last_spr = (ia - ib) / (0.5 * (ia + ib))
                if mode == 0:
                    if ia > ib and ib > 0 and T - tb <= STALE and T - ta <= STALE:
                        tm_qexp = min(tb, ta) + STALE + 1e-6
                    else:
                        tm_qexp = INF
                if strat == Q2:
                    if T - tb <= FRESH and T - ta <= FRESH:
                        tm_fresh = min(tb, ta) + FRESH + 1e-6
                    else:
                        tm_fresh = INF
                need = True
            else:
                k = ibk
                ibk += 1
                nb_ = bk_b[k]
                na_ = bk_a[k]
                if T < t_close and mode == 1:
                    for s in range(2):
                        if not lon[s]:
                            continue
                        P = lpx[s]
                        if s == 0:
                            cr = na_ > 0 and na_ <= P and not (ba > 0 and ba <= P)
                            vol = bk_aq[k]
                        else:
                            cr = nb_ > 0 and nb_ >= P and not (bb > 0 and bb >= P)
                            vol = bk_bq[k]
                        if cr:
                            avail = max(0.0, vol - lqa[s])
                            lqa[s] = max(0.0, lqa[s] - vol)
                            f = min(lrem[s], part * avail)
                            if f > 0:
                                _fill(SF, SI, res, s, P * SCALE, f, True, T, delta, eps, strat, na_, tick)
                                lrem[s] -= f
                                if not lfl[s]:
                                    lfl[s] = True
                                    res[R_NOF] += 1
                                if lrem[s] <= eps:
                                    lon[s] = False
                                sg = 1.0 if s == 0 else -1.0
                                if nfr < M:
                                    fr_t[nfr] = T
                                    fr_s[nfr] = sg
                                    fr_p[nfr] = P * SCALE
                                    fr_q[nfr] = f
                                    nfr += 1
                bb = nb_
                ba = na_
                bq = bk_bq[k]
                aq = bk_aq[k]
                need = mode == 1
        # -------------------------------------------------------------------- decision
        if need and T < t_close:
            if mode == 0:
                qb = ib
                qa = ia
                valid = qa > qb and qb > 0 and T - tb <= STALE and T - ta <= STALE
            else:
                qb = bb
                qa = ba
                valid = qa > qb and qb > 0
            fresh = T - tb <= FRESH and T - ta <= FRESH
            blk = eod or flattening or ex_t < INF
            inv = SF[0]
            d_on = np.zeros(2, np.bool_)
            d_px = np.zeros(2, np.int64)
            d_q = np.zeros(2)
            d_po = np.zeros(2, np.bool_)
            exact1 = False
            if not blk:
                if strat == Q5:
                    if inv > eps:
                        if SI[0] > 0:
                            d_on[1] = True
                            d_px[1] = SI[0]
                            d_q[1] = inv
                            exact1 = True
                    elif valid:
                        d_on[0] = True
                        d_px[0] = qb
                        d_q[0] = q
                elif valid:
                    pb = qb
                    pa = qa
                    po = False
                    ok = True
                    if strat == Q2 and tick > 0 and qa - qb >= 3 * tick and fresh:
                        pb = qb + tick
                        pa = qa - tick
                        po = True
                    elif strat == Q3:
                        if tick > 0:
                            pb = qb - tick
                            pa = qa + tick
                        else:
                            ok = False
                    if ok:
                        qbid = min(q, cap - inv)
                        qask = min(q, inv) if strat == Q1LO else min(q, cap + inv)
                        if pb > 0 and qbid * pb * SCALE >= min_not:
                            d_on[0] = True
                            d_px[0] = pb
                            d_q[0] = qbid
                            d_po[0] = po
                        if qask * pa * SCALE >= min_not:
                            d_on[1] = True
                            d_px[1] = pa
                            d_q[1] = qask
                            d_po[1] = po
            for s in range(2):
                if pc[s] > 0:
                    j = (ph[s] + pc[s] - 1) % CAP
                    ion = pq_op[s, j] == 1
                    ipx = pq_px[s, j]
                    iq = pq_q[s, j]
                    ipo = pq_po[s, j]
                else:
                    ion = lon[s]
                    ipx = lpx[s]
                    iq = lrem[s]
                    ipo = lpo[s]
                if not d_on[s]:
                    if ion:
                        _push(pq_t, pq_op, pq_px, pq_q, pq_po, ph, pc, s, T + delta, 0, 0, 0.0, False, res)
                        res[R_NCAN] += 1
                else:
                    keep = ion and ipx == d_px[s] and ipo == d_po[s]
                    if keep:
                        if s == 1 and exact1:
                            keep = abs(d_q[s] - iq) <= 1e-9 * q
                        else:
                            keep = d_q[s] >= iq - 1e-9 * q
                    if not keep:
                        _push(pq_t, pq_op, pq_px, pq_q, pq_po, ph, pc, s, T + delta, 1, d_px[s], d_q[s], d_po[s], res)
                        res[R_NORD] += 1
                        if ion:
                            res[R_NCAN] += 1
    # resolve markouts still open with the final state
    while h60 < nfr:
        m_ = _cur_mid(mk_src, fr_t[h60] + 60.0, ib, tb, ia, ta, bb, ba)
        if m_ > 0:
            res[R_MK60] += fr_s[h60] * (m_ * SCALE - fr_p[h60]) * fr_q[h60]
            res[R_MK60C] += fr_p[h60] * fr_q[h60]
        h60 += 1
    while h300 < nfr:
        m_ = _cur_mid(mk_src, fr_t[h300] + 300.0, ib, tb, ia, ta, bb, ba)
        if m_ > 0:
            res[R_MK300] += fr_s[h300] * (m_ * SCALE - fr_p[h300]) * fr_q[h300]
            res[R_MK300C] += fr_p[h300] * fr_q[h300]
        h300 += 1
    if abs(SF[0]) > eps:                         # should not happen: value at the last price, flagged
        lp = ib if SF[0] > 0 else ia
        SF[1] += SF[0] * max(lp, 0) * SCALE
        res[R_FLAGS] = float(int(res[R_FLAGS]) | FLAG_RESIDUAL)
    res[R_GROSS] = SF[1]
    return res


# ============================================================================================ per-day pipeline
EPOCH = date(1970, 1, 1)
E_I64 = np.empty(0, np.int64)
E_F64 = np.empty(0, np.float64)


def day_start_s(d: date) -> float:
    return float((d - EPOCH).days * 86400)


def load_day(sym: str, d: date, raw: bytes | None = None, futures: bool = False) -> dict | None:
    """One trades file -> taker-order arrays (times in seconds from the day's 00:00 UTC)."""
    b = raw if raw is not None else fetch_spot(sym, d)
    t = parse_trades(b, futures)
    if t is None:
        return None
    ev_tu, side, st, en, pf, pl, nt, wk = build_events(t["t_us"], t["ibm"], t["px"], t["quote"])
    t0 = int(day_start_s(d)) * 10 ** 6
    ref, g = price_grid(t["px"])
    return dict(day=d, ev_t=(ev_tu - t0) / 1e6, side=side, st=st, en=en, pf=pf, pl=pl, nt=nt, wk=wk,
                px=t["px"], q=t["qty"], qv=float(t["quote"].sum()), n=len(t["px"]), ref=int(ref), g=int(g),
                last=int(t["px"][-1]), first=int(t["px"][0]))


def grid_of(days: list[dict]) -> tuple[int, int]:
    """(tick, ref) from per-day (ref, gcd) pairs: gcd of all distinct-price gaps over the days."""
    ds = [x for x in days if x is not None and x["ref"] >= 0]
    if not ds:
        return 0, -1
    ref = ds[0]["ref"]
    g = 0
    for x in ds:
        g = math.gcd(g, int(x["g"]))
        g = math.gcd(g, abs(int(x["ref"]) - ref))
    return g, ref


def walk_tables(days: list[dict]):
    sn = np.concatenate([x["sn"] for x in days]) if days else E_F64
    sw = np.concatenate([x["sw"] for x in days]) if days else E_F64
    bn = np.concatenate([x["bn"] for x in days]) if days else E_F64
    bw = np.concatenate([x["bw"] for x in days]) if days else E_F64
    return walk_table(sn, sw), walk_table(bn, bw)


def summary(x: dict) -> dict:
    """What the 7-day window keeps of a day: price grid and the taker orders' notional/walk by side."""
    s = x["side"] < 0
    return dict(day=x["day"], ref=x["ref"], g=x["g"], sn=x["nt"][s].astype(np.float64), sw=x["wk"][s],
                bn=x["nt"][~s].astype(np.float64), bw=x["wk"][~s])


def concat_next(cur: dict, nxt: dict | None):
    if nxt is None:
        return cur["ev_t"], cur["side"], cur["st"], cur["en"], cur["pf"], cur["pl"], cur["px"], cur["q"]
    npr = len(cur["px"])
    return (np.r_[cur["ev_t"], nxt["ev_t"] + DAY], np.r_[cur["side"], nxt["side"]], np.r_[cur["st"], nxt["st"] + npr],
            np.r_[cur["en"], nxt["en"] + npr], np.r_[cur["pf"], nxt["pf"]], np.r_[cur["pl"], nxt["pl"]],
            np.r_[cur["px"], nxt["px"]], np.r_[cur["q"], nxt["q"]])


def run_day(cur: dict, nxt: dict | None, window: list[dict], carry: tuple, last_px: int, configs) -> list[np.ndarray]:
    """All configurations on one pair-day. carry = (ib, tb_epoch, ia, ta_epoch)."""
    t0 = day_start_s(cur["day"])
    ib, tb, ia, ta = carry
    tick, ref = grid_of(window)
    (wsa, wsm, ws10), (wba, wbm, wb10) = walk_tables(window)
    ev_t, side, st, en, pf, pl, px, q = concat_next(cur, nxt)
    ns, nb = next_side(side)
    p_ref = (last_px if last_px > 0 else cur["first"]) * SCALE
    out = []
    for strat, size, fill, delta, part in configs:
        out.append(engine(ev_t, side, st, en, pf, pl, px, q, E_F64, E_I64, E_F64, E_I64, E_F64, ns, nb,
                          int(ib), float(tb - t0), int(ia), float(ta - t0), int(tick), int(ref),
                          wsa, wsm, ws10, wba, wbm, wb10, strat, size / p_ref, delta, fill, part, 0, 0,
                          DAY, DAY + 301.0, MIN_NOTIONAL))
    return out


def month_split_stats(prior: list[dict], k: pd.DataFrame, sym: str, ms: pd.Timestamp) -> dict:
    """Split variables measured over the 30 days before the month (I3)."""
    tick, _ = grid_of([p for p in prior if p is not None])
    spr = np.concatenate([p["spr"] for p in prior if p is not None] or [E_I64])
    mid = np.concatenate([p["mid"] for p in prior if p is not None] or [E_F64])
    lr = []
    for p in prior:
        if p is None:
            continue
        g = p["grid"]
        ok = np.isfinite(g[1:]) & np.isfinite(g[:-1])
        lr.append(np.log(g[1:][ok] / g[:-1][ok]))
    lr = np.concatenate(lr) if lr else E_F64
    kk = k[(k.sym == sym) & (k.day < ms) & (k.day >= ms - pd.Timedelta(days=30))].sort_values("day")
    dv = np.diff(np.log(kk.close.to_numpy())) if len(kk) > 2 else E_F64
    spr_bp = float(np.median(spr / mid * 1e4)) if len(spr) else np.nan
    sig60 = float(np.std(lr) * 1e4) if len(lr) > 10 else np.nan
    return dict(pre_days=sum(p is not None for p in prior), pre_tick=int(tick),
                pre_spread_ticks=float(np.median(spr / tick)) if (len(spr) and tick > 0) else np.nan,
                pre_spread_bp=spr_bp, pre_sigma60_bp=sig60,
                pre_spread_to_vol=spr_bp / sig60 if sig60 and np.isfinite(sig60) and sig60 > 0 else np.nan,
                pre_vol_daily=float(np.std(dv, ddof=1)) if len(dv) > 2 else np.nan)


class Prefetch:
    """Download the day files of one job in order with a few threads ahead of the consumer."""

    def __init__(self, sym, days, threads=6, ahead=10):
        self.sym, self.days, self.ahead = sym, days, ahead
        self.ex = cf.ThreadPoolExecutor(threads)
        self.fut = {}
        self.i = 0

    def _fill(self):
        while len(self.fut) < self.ahead and self.i < len(self.days):
            d = self.days[self.i]
            self.fut[d] = self.ex.submit(fetch_spot, self.sym, d)
            self.i += 1

    def get(self, d):
        self._fill()
        if d not in self.fut:
            self.fut[d] = self.ex.submit(fetch_spot, self.sym, d)
        b = self.fut.pop(d).result()
        self._fill()
        return b

    def close(self):
        self.ex.shutdown(wait=False, cancel_futures=True)


def _iso(d: date):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def run_segment(stratum: str, sym: str, months: list[tuple[int, str]], configs, k: pd.DataFrame,
                sim_rule=None, out_dir: Path = DATA, limit_days=None, log=print) -> dict:
    """Simulate one symbol over a run of consecutive months (each month written as its own parquet)."""
    ms0 = MONTHS[months[0][0]].date()
    me = (MONTHS[months[-1][0]] + pd.DateOffset(months=1)).date() - timedelta(days=1)
    first = ms0 - timedelta(days=30)
    days = [first + timedelta(days=i) for i in range((me - first).days + 2)]
    band_of_month = {MONTHS[m].strftime("%Y-%m"): b for m, b in months}
    sim_days = set()
    for m, _ in months:
        a = MONTHS[m].date()
        n = (MONTHS[m] + pd.DateOffset(months=1)).date() - a
        for i in range(n.days):
            d = a + timedelta(days=i)
            if sim_rule is None or sim_rule(d):
                sim_days.add(d)
    if limit_days is not None:
        sim_days = set(sorted(sim_days)[:limit_days])
        days = [d for d in days if d <= max(sim_days) + timedelta(days=1)]
    names = [cfg_name(*c) for c in configs]
    pf = Prefetch(sym, days)
    timing = dict(download=0.0, parse=0.0, sim=0.0, events=0, sim_days=0)
    window, prior = [], {}
    carry = (-1, -1e18, -1, -1e18)
    last_px = 0
    rows, mstats = {}, {}
    cur = None
    try:
        for i, d in enumerate(days):
            mo = d.strftime("%Y-%m")
            if d.day == 1 and mo in band_of_month and mo not in mstats:      # split variables: the 30 days before
                ms = pd.Timestamp(d)
                mstats[mo] = month_split_stats([prior.get(d - timedelta(days=j)) for j in range(30, 0, -1)], k, sym, ms)
            t_ = time.time()
            if cur is None or cur["day_"] != d:
                b = pf.get(d)
                timing["download"] += time.time() - t_
                t_ = time.time()
                cur = load_day(sym, d, raw=b) if b is not None else None
                cur = {"day_": d, "x": cur}
                timing["parse"] += time.time() - t_
            x = cur["x"]
            nxt_x = None
            if d in sim_days:
                t_ = time.time()
                b2 = pf.get(d + timedelta(days=1)) if i + 1 < len(days) else fetch_spot(sym, d + timedelta(days=1))
                timing["download"] += time.time() - t_
                t_ = time.time()
                nxt_x = load_day(sym, d + timedelta(days=1), raw=b2) if b2 is not None else None
                timing["parse"] += time.time() - t_
            # simulation of day d (needs the carry state before d)
            if d in sim_days:
                t_ = time.time()
                mo = d.strftime("%Y-%m")
                base = dict(stratum=stratum, sym=sym, band=band_of_month[mo], month=mo, day=pd.Timestamp(d),
                            week=_iso(d), dow=d.weekday(), has_data=x is not None, has_next=nxt_x is not None,
                            day_qv=x["qv"] if x else 0.0, n_events=len(x["ev_t"]) if x else 0)
                win = [w for w in window if d - timedelta(days=7) <= w["day"] <= d - timedelta(days=1)]
                if x is not None:
                    outs = run_day(x, nxt_x, win, carry, last_px, configs)
                    timing["events"] += len(x["ev_t"]) * len(configs)
                else:
                    outs = [np.zeros(NRES) for _ in configs]
                    for o in outs:
                        o[R_FLAGS] = FLAG_NODATA
                for nm, o in zip(names, outs):
                    if x is not None and nxt_x is None:
                        o[R_FLAGS] = float(int(o[R_FLAGS]) | FLAG_NONEXT)
                    r = dict(base, config=nm)
                    r.update(zip(RES_NAMES, o.tolist()))
                    r["n_fills"] = r["n_maker"] + r["n_crossed"]
                    rows.setdefault(mo, []).append(r)
                timing["sim"] += time.time() - t_
                timing["sim_days"] += 1
            # day statistics, carry and window update
            if x is not None:
                t0 = day_start_s(d)
                spr, mid, grid, ib, tb, ia, ta = day_stats(x["ev_t"], x["side"], x["pl"], int(carry[0]), carry[1] - t0,
                                                           int(carry[2]), carry[3] - t0, DAY)
                carry = (int(ib), tb + t0, int(ia), ta + t0)
                last_px = x["last"]
                prior[d] = dict(spr=spr, mid=mid, grid=grid, ref=x["ref"], g=x["g"])
                window.append(summary(x))
            else:
                prior[d] = None
            window = [w for w in window if w["day"] > d - timedelta(days=7)]
            if d in sim_days:
                cur = {"day_": d + timedelta(days=1), "x": nxt_x}
            # month finished -> write
            if mo in rows and ((d + timedelta(days=1)).strftime("%Y-%m") != mo or (limit_days and d == max(sim_days))):
                df = pd.DataFrame(rows.pop(mo))
                for c_, v in mstats.get(mo, {}).items():
                    df[c_] = v
                p = out_dir / stratum / sym
                p.mkdir(parents=True, exist_ok=True)
                df.to_parquet(p / f"{mo}.parquet", index=False)
            for dd in [dd for dd in prior if dd < d - timedelta(days=40)]:
                del prior[dd]
    finally:
        pf.close()
    return timing


# ============================================================================================ unit tests
def _tape(rows):
    """rows: (t seconds, price $, qty, side +1 buyer / -1 seller); same (t, side) consecutive rows = one order."""
    t = np.array([r[0] for r in rows]); px = np.array([int(round(r[1] / SCALE)) for r in rows], np.int64)
    qy = np.array([float(r[2]) for r in rows]); ibm = np.array([r[3] < 0 for r in rows])
    ev_tu, side, st, en, pf, pl, nt, wk = build_events(np.rint(t * 1e6).astype(np.int64), ibm, px, qy * px * SCALE)
    return dict(ev_t=ev_tu / 1e6, side=side, st=st, en=en, pf=pf, pl=pl, px=px, q=qy, nt=nt, wk=wk)


def _run(rows, strat=Q1, fill=F1, q=10.0, delta=0.25, part=1.0, tick=int(0.1 / SCALE), ref=int(100 / SCALE),
         t_close=10.0, t_hard=400.0, book=None, mode=0, mk_src=0, init=(-1, -1e9, -1, -1e9), walk=None):
    x = _tape(rows)
    ns, nb = next_side(x["side"])
    if book is None:
        bk = (E_F64, E_I64, E_F64, E_I64, E_F64)
    else:
        bk = (np.array([b[0] for b in book]), np.array([int(round(b[1] / SCALE)) for b in book], np.int64),
              np.array([float(b[2]) for b in book]), np.array([int(round(b[3] / SCALE)) for b in book], np.int64),
              np.array([float(b[4]) for b in book]))
    w = walk if walk is not None else ((E_F64, np.zeros(1), 0.0), (E_F64, np.zeros(1), 0.0))
    r = engine(x["ev_t"], x["side"], x["st"], x["en"], x["pf"], x["pl"], x["px"], x["q"], *bk, ns, nb,
               int(round(init[0] / SCALE)) if init[0] > 0 else -1, init[1], int(round(init[2] / SCALE)) if init[2] > 0 else -1,
               init[3], tick, ref, *w[0], *w[1], strat, q, delta, fill, part, mode, mk_src, t_close, t_hard, 1.0)
    return dict(zip(RES_NAMES, r))


def tests():
    ok = lambda c, msg: print(("ok   " if c else "FAIL ") + msg) or c  # noqa: E731
    close = lambda a, b, tol=1e-6: abs(a - b) <= tol * max(1.0, abs(b))  # noqa: E731
    res = []
    # --- walk table vs brute force
    rng = np.random.default_rng(1)
    nt = rng.lognormal(3, 1.5, 500); wk = np.abs(rng.normal(0, 1e-3, 500)) * (rng.random(500) < 0.3)
    asc, medk, mn10 = walk_table(nt, wk)
    good = True
    for N in (1.0, 20.0, 200.0, 2000.0, 1e5):
        sel = wk[nt >= N]
        if len(sel) >= 10:
            want = np.median(sel)
        else:
            top = np.argsort(-nt)[:10]
            want = np.median(wk[top]) * math.sqrt(N / np.median(nt[top]))
        good &= close(walk_lookup(N, asc, medk, mn10), want)
    res.append(ok(good, "walk table = brute-force median over orders >= N, sqrt fallback"))
    # --- price grid and events
    x = _tape([(1, 100.0, 1, -1), (1, 99.9, 2, -1), (1, 100.2, 1, 1), (2, 100.5, 1, 1)])
    res.append(ok(len(x["ev_t"]) == 3 and list(x["side"]) == [-1, 1, 1] and close(x["wk"][0], 0.1 / 100),
                  "taker orders: same timestamp + side grouped; walk first-to-last"))
    res.append(ok(price_grid(np.array([100, 130, 160, 115], np.int64))[1] == 15, "price grid gcd"))
    # --- A: latency, F1 vs F2, exit at the close with R = min(implied bid, first seller print after)
    tapeA = [(1, 100.0, 1, -1), (2, 100.5, 1, 1), (2.1, 99.9, 3, -1), (2.3, 99.8, 4, -1), (2.5, 99.9, 2, -1),
             (20, 99.5, 1, -1)]
    a1 = _run(tapeA, fill=F1)
    res.append(ok(close(a1["maker_usd"], 400.0) and a1["n_maker"] == 1,
                  f"F1: order not live before t+D, old order fillable until replaced, through volume only "
                  f"(maker {a1['maker_usd']:.2f})"))
    res.append(ok(close(a1["exit_usd"], 4 * 99.4) and close(a1["gross_usd"], -400 + 4 * 99.4) and
                  close(a1["exit_cost_usd"], (99.4 - 100.2) * 4),
                  f"midnight flatten: R = min(99.9, 99.5), w = tick/R -> 99.4 (gross {a1['gross_usd']:.3f})"))
    a2 = _run(tapeA, fill=F2)
    res.append(ok(close(a2["maker_usd"], 400 + 2 * 99.9), f"F2 adds the at-price print (maker {a2['maker_usd']:.2f})"))
    # --- B: crossed bid (buyer prints at/below our bid) pays taker and fills at the print price
    b1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 2, 1), (20, 99.5, 1, -1), (21, 100.6, 1, 1)])
    res.append(ok(close(b1["crossed_usd"], 2 * 99.9) and b1["n_crossed"] == 1 and b1["maker_usd"] == 0,
                  f"crossed bid fills at the print price as taker ({b1['crossed_usd']:.2f})"))
    # --- C: Q2 steps inside (spread 5 ticks, both sides fresh), post-only cancel, F1 at the improved price
    c1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 100.1, 1, 1), (3.5, 100.5, 1, 1), (4, 100.0, 3, -1),
               (20, 99.5, 1, -1), (21, 100.6, 1, 1)], strat=Q2)
    res.append(ok(c1["n_postonly_cancel"] == 1, "Q2 post-only bid cancelled unfilled when a buyer print reaches it"))
    # (the 100.1 buyer print collapses the spread to 1 tick, so Q2 joins; the 100.5 buyer print then fills that
    #  join ask at 100.1; the spread is 5 ticks again and the re-posted inside bid fills 3 at 100.1 by F1)
    res.append(ok(close(c1["maker_usd"], 4 * 100.1) and close(c1["bought_usd"], 3 * 100.1),
                  f"Q2 re-posted inside bid fills by F1 at 100.1 ({c1['bought_usd']:.2f})"))
    c2 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (14, 100.0, 3, -1), (20, 99.5, 1, -1), (21, 100.6, 1, 1)],
              strat=Q2, t_close=18)
    res.append(ok(c2["maker_usd"] == 0, "Q2 freshness expires after 10 s -> back to joining (seller at 100.0 no F1 fill)"))
    # --- D: T_max flatten after 60 min of non-zero inventory, executed at + D
    keep = [(t, 100.0 + (0.5 if s > 0 else 0), 0.001, s) for t in range(100, 3900, 100) for s in (-1, 1)]
    d1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (5, 99.9, 4, -1)] + keep + [(5000, 99.5, 1, -1)],
              t_close=4000, t_hard=6000)
    res.append(ok(d1["n_tmax"] == 1 and d1["n_exits"] == 1, f"T_max exit after 3600 s (exits {d1['n_exits']})"))
    # --- E: Q5 buys at the bid, offers at max(implied ask, fill + tick), sells by F1, re-bids
    e1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 4, -1), (4, 100.6, 10, 1), (20, 99.5, 1, -1)], strat=Q5)
    res.append(ok(close(e1["gross_usd"], 4 * 0.5) and e1["n_maker"] == 2 and e1["n_exits"] == 0,
                  f"Q5 round trip 100.0 -> 100.5 by F1 ({e1['gross_usd']:.3f})"))
    # --- F: one fill per aggressor order: a sell sweep crossing our ask then through our bid fills once
    f1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 100.6, 1, -1), (3, 99.9, 5, -1), (20, 99.5, 1, -1),
               (21, 100.6, 1, 1)])
    res.append(ok(f1["n_crossed"] == 1 and f1["n_maker"] == 0, "one fill per aggressor order (crossing counted)"))
    # --- G: inventory cap 3q
    g1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1)] + [(3 + i, 99.9 - 0.1 * i, 50, -1) for i in range(8)] +
              [(20, 99.0, 1, -1)], t_close=15)
    want = 10 * (100.0 + 99.9 + 99.8)
    res.append(ok(close(g1["bought_usd"], want) and g1["n_maker"] == 3,
                  f"inventory cap 3q on the increasing side (bought {g1['bought_usd']:.1f})"))
    # --- H: FIFO queue in book mode: join behind the displayed 5, prints at our price deplete it
    book = [(0.5, 100.0, 5, 100.5, 5)]
    h1 = _run([(1, 100.0, 3, -1), (2, 100.0, 4, -1), (3, 100.0, 4, -1), (20, 99.5, 1, -1)], book=book, mode=1,
              fill=FIFO, mk_src=1)
    res.append(ok(close(h1["bought_usd"], 6 * 100.0), f"FIFO: 3+4 at our price fill 2, then 4 ({h1['bought_usd']:.1f})"))
    h2 = _run([(1, 100.0, 3, -1), (20, 99.5, 1, -1)], book=book, mode=1, fill=FRONT, mk_src=1)
    res.append(ok(close(h2["bought_usd"], 3 * 100.0), "front of queue: first print at our price fills"))
    # --- I: implied quote carried across midnight; stale > 300 s => no quote
    i1 = _run([(1, 100.0, 5, -1), (20, 99.5, 1, -1)], init=(100.1, -5.0, 100.5, -2.0))
    i2 = _run([(1, 100.0, 5, -1), (20, 99.5, 1, -1)], init=(100.1, -500.0, 100.5, -400.0))
    res.append(ok(i1["n_orders"] >= 2 and i2["n_orders"] == 0, "quote state carried from the previous day; stale => no quote"))
    # --- J: stopped trading valuation when no print follows the exit
    j1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 4, -1)])
    res.append(ok(int(j1["flag_bits"]) & FLAG_STOPPED and close(j1["exit_usd"], 4 * 99.9 * (1 - 0.6 / 100.2)),
                  "stopped trading: last seller print x (1 - implied spread)"))
    # --- K: Q1-LO never sells coins it does not hold; Q1 does (pre-held coins)
    tk = [(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 100.6, 5, 1), (20, 99.5, 1, -1), (21, 100.7, 1, 1)]
    k1, k2 = _run(tk, strat=Q1LO), _run(tk, strat=Q1)
    res.append(ok(k1["sold_usd"] == 0 and close(k2["sold_usd"], 5 * 100.5), "Q1-LO long-only; Q1 may sell down pre-held coins"))
    # --- L: 25% participation; Q3 one tick behind; latency 1 s
    l1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 4, -1), (20, 99.5, 1, -1)], part=0.25)
    res.append(ok(close(l1["bought_usd"], 1 * 100.0), "25% participation takes a quarter of the through volume"))
    l2 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.95, 4, -1), (4, 99.85, 4, -1), (20, 99.5, 1, -1)], strat=Q3)
    res.append(ok(close(l2["bought_usd"], 4 * 99.9) and l2["n_maker"] == 1,
                  f"Q3 bids one tick behind (99.9): not filled at 99.95, filled by 99.85 ({l2['bought_usd']:.2f})"))
    l3 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (2.9, 99.9, 4, -1), (20, 99.5, 1, -1)], delta=1.0)
    res.append(ok(l3["bought_usd"] == 0, "latency 1 s: an order decided at t=2 is not live at 2.9"))
    print(f"{sum(res)}/{len(res)} engine tests passed")
    return all(res)


# ============================================================================================ jobs
SCRATCH = Path("/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad")
_K = None


def _segments(months: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    out = []
    for m, b in sorted(months):
        if out and out[-1][-1][0] == m - 1:
            out[-1].append((m, b))
        else:
            out.append([(m, b)])
    return out


def arh_rule(d: date) -> bool:
    return (d - P0).days % 7 == 0


def jobs(stratum: str) -> list[tuple]:
    k, excl, elig, dr, arh = universe(write=True)
    if stratum == "main":
        js = [("main", s, seg) for s, g in dr.groupby("sym") for seg in _segments(list(zip(g.m, g.band)))]
    else:
        if arh is None:
            return []
        e = elig[elig.eligible & elig.sym.isin(arh.sym[~arh.excluded])]
        js = [("arh", s, seg) for s, g in e.groupby("sym") for seg in _segments(list(zip(g.m, g.band)))]
    return sorted(js, key=lambda j: (-len(j[2]), j[1]))


def _done(stratum, sym, m, names) -> bool:
    p = DATA / stratum / sym / f"{MONTHS[m]:%Y-%m}.parquet"
    if not p.exists():
        return False
    try:
        c = pd.read_parquet(p, columns=["config"]).config
    except Exception:
        return False
    return set(names) <= set(c)


def run_job(job) -> dict:
    global _K
    stratum, sym, months = job
    configs = MAIN_CONFIGS if stratum == "main" else ARH_CONFIGS
    names = [cfg_name(*c) for c in configs]
    todo = [(m, b) for m, b in months if not _done(stratum, sym, m, names)]
    if _K is None:
        _K = load_klines()
    t0 = time.time()
    tim = dict(download=0.0, parse=0.0, sim=0.0, events=0, sim_days=0)
    for seg in _segments(todo):
        t = run_segment(stratum, sym, seg, configs, _K, sim_rule=arh_rule if stratum == "arh" else None)
        for c_ in tim:
            tim[c_] += t[c_]
    tim.update(job=f"{stratum} {sym} {len(months)}m ({len(todo)} to do)", wall=time.time() - t0)
    return tim


def run_all(stratum: str = "main", workers: int = 4):
    js = jobs(stratum)
    if not js:
        print(f"{stratum}: nothing to run" + (" (data/scalping/rh/currency_pairs.json not found)" if stratum == "arh" else ""))
        return
    DATA.mkdir(parents=True, exist_ok=True)
    log = open(DATA / f"run_{stratum}.log", "a")
    print(f"{stratum}: {len(js)} jobs, {sum(len(j[2]) for j in js)} pair-months, {workers} workers", flush=True)
    t0 = time.time()
    with cf.ProcessPoolExecutor(workers) as ex:
        futs = {ex.submit(run_job, j): j for j in js}
        for i, f in enumerate(cf.as_completed(futs), 1):
            try:
                r = f.result()
                msg = (f"[{i}/{len(js)}] {r['job']}: wall {r['wall']:.0f}s download {r['download']:.0f}s parse "
                       f"{r['parse']:.0f}s sim {r['sim']:.0f}s events x configs {r['events']:,}")
            except Exception as e:  # keep going; a rerun retries the missing pair-months
                msg = f"[{i}/{len(js)}] FAILED {futs[f]}: {e!r}"
            print(msg, f"(elapsed {time.time() - t0:.0f}s)", flush=True)
            log.write(msg + "\n"); log.flush()


def smoke():
    """2 drawn pairs x 3 days with the full warm-up (30 prior days for the split stats, 7 for the tick/walk)."""
    k, excl, elig, dr, arh = universe(write=True)
    picks = [dr[(dr.m == 0) & (dr.band == "B")].iloc[0], dr[(dr.m == 0) & (dr.band == "D")].iloc[0]]
    out = SCRATCH / "smoke_A"
    for r in picks:
        t0 = time.time()
        t = run_segment("smoke", r.sym, [(int(r.m), r.band)], MAIN_CONFIGS, k, out_dir=out, limit_days=3)
        df = pd.read_parquet(out / "smoke" / r.sym / f"{MONTHS[int(r.m)]:%Y-%m}.parquet")
        days = 30 + 3 + 1
        print(f"{r.sym} (band {r.band}): {days} files, wall {time.time() - t0:.1f}s; download {t['download']:.1f}s, "
              f"parse {t['parse']:.1f}s, sim {t['sim']:.1f}s for {t['sim_days']} days x {len(MAIN_CONFIGS)} configs "
              f"({t['events'] / max(t['sim'], 1e-9) / 1e6:.2f}M order-events/s); rows {len(df)}, "
              f"events/day {df.n_events.mean():,.0f}; flags {sorted(set(df.flag_bits.astype(int)))}")
        print("   columns:", ", ".join(df.columns[:12]), "...")


# ============================================================================================ Control (i): synthetic GM market
@njit(cache=True)
def synth_market(seed, S, alpha, lam_a, lam_v, sizes, qmean, ddeep, tau, p0t, tk, H, t_end):
    """One synthetic day (C1). Prices in ticks internally, int 1e-8 units on output. Returns trades
    (t_us, px, qty, ibm) and book updates (t, bid, bid qty, ask, ask qty)."""
    np.random.seed(seed)
    INF = 1e30
    nvm = int((t_end + H + 100) * lam_v * 3 + 100)
    vt = np.empty(nvm)
    vc = np.empty(nvm, np.int64)
    t = 0.0
    nv = 0
    c = 0
    while nv < nvm:
        t += np.random.exponential(1.0 / lam_v)
        if t > t_end + H + 10:
            break
        c += 1 if np.random.random() < 0.5 else -1
        vt[nv] = t
        vc[nv] = c
        nv += 1
    vt = vt[:nv]
    vc = vc[:nv]
    nam = int(t_end * lam_a * 2 + 100)
    nlev = 64
    tr_t = np.empty(nam * 4)
    tr_p = np.empty(nam * 4, np.int64)
    tr_q = np.empty(nam * 4)
    tr_s = np.empty(nam * 4, np.bool_)
    ntr = 0
    nbm = nam + 4 * nv + 16
    bk_t = np.empty(nbm)
    bk_b = np.empty(nbm, np.int64)
    bk_bq = np.empty(nbm)
    bk_a = np.empty(nbm, np.int64)
    bk_aq = np.empty(nbm)
    nbk = 0
    Bs = p0t
    b = Bs
    a = Bs + S
    px0 = p0t * tk * SCALE
    qb = np.random.exponential(qmean) / px0
    qa = np.random.exponential(qmean) / px0
    tpb = INF
    tpa = INF
    iv = 0
    ta_next = np.random.exponential(1.0 / lam_a)
    bk_t[0] = 0.0; bk_b[0] = b * tk; bk_bq[0] = qb; bk_a[0] = a * tk; bk_aq[0] = qa
    nbk = 1
    while True:
        t_v = vt[iv] if iv < nv else INF
        T = min(min(t_v, ta_next), min(tpb, tpa))
        if T >= t_end:
            break
        if t_v == T:
            Bs = p0t + vc[iv]
            iv += 1
            if b > Bs:
                b = Bs
                qb = np.random.exponential(qmean) / (b * tk * SCALE)
            if a < Bs + S:
                a = Bs + S
                qa = np.random.exponential(qmean) / (a * tk * SCALE)
            tpb = T + tau if b < Bs else INF
            tpa = T + tau if a > Bs + S else INF
        elif tpb == T:
            tpb = INF
            if b < Bs:
                b = Bs
                qb = np.random.exponential(qmean) / (b * tk * SCALE)
        elif tpa == T:
            tpa = INF
            if a > Bs + S:
                a = Bs + S
                qa = np.random.exponential(qmean) / (a * tk * SCALE)
        else:
            ta_next = T + np.random.exponential(1.0 / lam_a)
            if np.random.random() < alpha:
                j = np.searchsorted(vt, T + H, side="right") - 1
                fut = p0t + (vc[j] if j >= 0 else 0)
                sd = 1 if fut > Bs else (-1 if fut < Bs else (1 if np.random.random() < 0.5 else -1))
            else:
                sd = 1 if np.random.random() < 0.5 else -1
            N = sizes[np.random.randint(0, sizes.shape[0])]
            rem = N / px0
            if sd < 0:
                lev = b
                avail = qb
                for _ in range(nlev):
                    take = min(rem, avail)
                    if ntr < tr_t.shape[0]:
                        tr_t[ntr] = T; tr_p[ntr] = lev * tk; tr_q[ntr] = take; tr_s[ntr] = True
                        ntr += 1
                    rem -= take
                    if lev == b:
                        qb -= take
                    if rem <= 1e-12:
                        break
                    lev -= 1
                    avail = ddeep / (lev * tk * SCALE)
                if qb <= 1e-12:
                    qb = np.random.exponential(qmean) / (b * tk * SCALE)
            else:
                lev = a
                avail = qa
                for _ in range(nlev):
                    take = min(rem, avail)
                    if ntr < tr_t.shape[0]:
                        tr_t[ntr] = T; tr_p[ntr] = lev * tk; tr_q[ntr] = take; tr_s[ntr] = False
                        ntr += 1
                    rem -= take
                    if lev == a:
                        qa -= take
                    if rem <= 1e-12:
                        break
                    lev += 1
                    avail = ddeep / (lev * tk * SCALE)
                if qa <= 1e-12:
                    qa = np.random.exponential(qmean) / (a * tk * SCALE)
        if nbk < nbm:
            bk_t[nbk] = T; bk_b[nbk] = b * tk; bk_bq[nbk] = qb; bk_a[nbk] = a * tk; bk_aq[nbk] = qa
            nbk += 1
    return (np.rint(tr_t[:ntr] * 1e6).astype(np.int64), tr_p[:ntr], tr_q[:ntr], tr_s[:ntr],
            bk_t[:nbk], bk_b[:nbk], bk_bq[:nbk], bk_a[:nbk], bk_aq[:nbk])


def pilot_sizes(syms) -> np.ndarray:
    """Taker-order notionals of pilot pairs (already seen; used only as a size distribution)."""
    out = []
    for s in syms:
        for f in sorted(PILOT_TRADES.glob(f"{s}-trades-*.zip")):
            z = zipfile.ZipFile(f)
            t = parse_trades(z.read(z.namelist()[0]))
            out.append(build_events(t["t_us"], t["ibm"], t["px"], t["quote"])[6])
    return np.concatenate(out)


def run_book_day(tr, bk, strats_fills, tick, ref, t_close, configs_size=1000.0, delta=0.25, p_ref=None, mk_book=False):
    """Run strategies on one day with both a trade tape and a true book. strats_fills: list of (strat, fill, mode).
    mk_book: mark the trades-only legs' markouts to the book mid too (synthetic control)."""
    ev_tu, side, st, en, pf, pl, nt, wk = build_events(tr["t_us"], tr["ibm"], tr["px"], tr["quote"])
    t0 = (tr["t_us"][0] // (86400 * 10 ** 6)) * 86400 * 10 ** 6 if tr.get("day0") is None else tr["day0"]
    ev_t = (ev_tu - t0) / 1e6
    ns, nb = next_side(side)
    s_ = side < 0
    ws = walk_table(nt[s_].astype(np.float64), wk[s_])
    wb = walk_table(nt[~s_].astype(np.float64), wk[~s_])
    bt = (bk["t_us"] - t0) / 1e6
    pr = p_ref if p_ref is not None else tr["px"][0] * SCALE
    out = []
    for strat, fill, mode in strats_fills:
        mk = 1 if (mode == 1 or mk_book) else 0
        b_ = (bt, bk["bid"], bk["bq"], bk["ask"], bk["aq"]) if (mode == 1 or mk) else (E_F64, E_I64, E_F64, E_I64, E_F64)
        r = engine(ev_t, side, st, en, pf, pl, tr["px"], tr["qty"], *b_, ns, nb,
                   -1, -1e9, -1, -1e9, int(tick), int(ref), *ws, *wb, strat, configs_size / pr, delta, fill, 1.0,
                   mode, mk, t_close, DAY + 1.0, MIN_NOTIONAL)
        out.append(r)
    return out


def control_i(days_a=20, days_c=10):
    """Control (i): Q1/Q2/Q5 under F1, F2 and the true queue on synthetic no-information (alpha 0) and informed
    (alpha 0.3) markets with spreads of 1, 3 and 10 ticks."""
    sizes = {"A-like (150 orders/h)": (pilot_sizes([s + "USDT" for s in ("GNO", "XVS", "REQ", "KNC")]), 150 / 3600, days_a),
             "C-like (1000 orders/h)": (pilot_sizes([s + "USDT" for s in ("TRB", "RUNE", "GALA", "ETC")]), 1000 / 3600, days_c)}
    tk = int(0.0005 / SCALE)                 # $0.0005 tick on a $1 price: 5 bp
    p0t = int(1.0 / SCALE) // tk
    runs = [(s, f, m) for s in (Q1, Q2, Q5) for f, m in ((F1, 0), (F2, 0), (FIFO, 1))]
    rows = []
    for sp_name, (sz, lam_a, nd) in sizes.items():
        for S in (1, 3, 10):
            for alpha in (0.0, 0.3):
                for dd in range(nd):
                    seed = SEED + 1000 * S + int(alpha * 10) * 100 + dd + (0 if lam_a < 0.1 else 50000)
                    tt, tp, tq, ts, bt, bb, bq, ba, aq = synth_market(seed, S, alpha, lam_a, 1 / 30, sz, 1000.0, 2000.0,
                                                                      2.0, p0t, tk, 60.0, DAY)
                    tr = dict(t_us=tt, px=tp, qty=tq, ibm=ts, quote=tq * tp * SCALE, day0=0)
                    bk = dict(t_us=np.rint(bt * 1e6).astype(np.int64), bid=bb, bq=bq, ask=ba, aq=aq)
                    out = run_book_day(tr, bk, runs, tk, p0t * tk, DAY - 600, p_ref=1.0, mk_book=True)
                    for (s, f, m), r in zip(runs, out):
                        rows.append(dict(market=sp_name, S=S, alpha=alpha, day=dd, strat=STRAT_NAME[s], fill=FILL_NAME[f],
                                         half_spread_bp=S * 5 / 2, **dict(zip(RES_NAMES, r))))
    df = pd.DataFrame(rows)
    g = df.groupby(["market", "S", "alpha", "strat", "fill"])
    bp = lambda a, b: 1e4 * a.sum() / b.sum() if b.sum() > 0 else np.nan  # noqa: E731
    summ = g.apply(lambda x: pd.Series(dict(
        half_spread_bp=x.half_spread_bp.iloc[0], fills_per_day=(x.n_maker + x.n_crossed).mean(),
        filled_usd_day=x.filled_usd.mean(), mk0_bp=bp(x.mk0_usd, x.mk0_cov_usd), mk60_bp=bp(x.mk60_usd, x.mk60_cov_usd),
        mk60_se_bp=np.std(1e4 * x.mk60_usd / x.mk60_cov_usd.where(x.mk60_cov_usd > 0), ddof=1) / math.sqrt(len(x)),
        mk300_bp=bp(x.mk300_usd, x.mk300_cov_usd), gross_bp=bp(x.gross_usd, x.filled_usd),
        net02_bp=bp(x.gross_usd - 2e-4 * x.taker_usd, x.filled_usd), gross_usd_day=x.gross_usd.mean(),
        exit_share_of_taker=x.exit_usd.sum() / max(x.taker_usd.sum(), 1e-9))), include_groups=False).reset_index()
    q = summ[(summ.strat == "Q1") & (summ.fill == "FIFO") & (summ.alpha == 0)].copy()
    q["dev_bp"] = q.mk60_bp - q.half_spread_bp
    q["pass"] = (q.dev_bp.abs() <= np.maximum(3 * q.mk60_se_bp, 0.2 * q.half_spread_bp))
    RES.mkdir(parents=True, exist_ok=True)
    df.to_csv(RES / "control_i_days.csv", index=False)
    summ.to_csv(RES / "control_i.csv", index=False)
    q.to_csv(RES / "control_i_check.csv", index=False)
    return summ, q


# ============================================================================================ Control (ii)/(iii): USD-M true book
def um_days() -> list[date]:
    n = (UM_RANGE[1] - UM_RANGE[0]).days + 1
    cand = [UM_RANGE[0] + timedelta(days=i) for i in range(n) if UM_RANGE[0] + timedelta(days=i) != UM_EXCLUDED]
    pick = np.random.default_rng(SEED).choice(np.array(cand, dtype=object), size=20, replace=False)
    return sorted(pick.tolist())


def _um_fetch(sym, d):
    kb = f"data/futures/um/daily/bookTicker/{sym}/{sym}-bookTicker-{d:%Y-%m-%d}.zip"
    kt = f"data/futures/um/daily/trades/{sym}/{sym}-trades-{d:%Y-%m-%d}.zip"
    with cf.ThreadPoolExecutor(2) as ex:
        fb, ft = ex.submit(s3_get_zip_csv, kb), ex.submit(s3_get_zip_csv, kt)
        return fb.result(), ft.result()


CTRL_RUNS = [(Q1, F1, 0), (Q1, FIFO, 1), (Q1, FRONT, 1), (Q2, F1, 0), (Q2, FIFO, 1), (Q5, F1, 0), (Q5, FIFO, 1)]


def _um_one(job):
    sym, d = job
    out = DATA / "control_ii" / f"{d:%Y-%m-%d}_{sym}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    bb, bt = _um_fetch(sym, d)
    base = dict(day=pd.Timestamp(d), sym=sym)
    if bb is None or bt is None:
        df = pd.DataFrame([dict(base, missing=("bookTicker " if bb is None else "") + ("trades" if bt is None else ""))])
    else:
        tr = parse_trades(bt, futures=True)
        bk = parse_book(bb)
        del bb, bt
        tr["day0"] = int(day_start_s(d)) * 10 ** 6
        keep = bk["ask"] > bk["bid"]
        bk = {k_: v[keep] for k_, v in bk.items()}
        _, g1 = price_grid(tr["px"])
        ref = int(tr["px"][0])
        g = math.gcd(int(g1), int(price_grid(np.r_[bk["bid"][::20], bk["ask"][::20], ref])[1]))
        out_r = run_book_day(tr, bk, CTRL_RUNS, g, ref, DAY - 600)
        rows = [dict(base, missing="", strat=STRAT_NAME[s], leg=("trades-only " + FILL_NAME[f]) if m == 0 else ("true book " + FILL_NAME[f]),
                     n_trades=len(tr["px"]), n_book=len(bk["bid"]), day_usd=float(tr["quote"].sum()), tick=g,
                     **dict(zip(RES_NAMES, r))) for (s, f, m), r in zip(CTRL_RUNS, out_r)]
        df = pd.DataFrame(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


def control_ii(workers=3):
    days = um_days()
    heavy = {"BTCUSDT"}                        # 90-270 MB bookTicker zips: one at a time (memory)
    t0 = time.time()
    dfs = []
    for js, w in (([(s, d) for d in days for s in UM_SYMS if s not in heavy], workers),
                  ([(s, d) for d in days for s in UM_SYMS if s in heavy], 1)):
        with cf.ProcessPoolExecutor(w) as ex:
            for i, df in enumerate(ex.map(_um_one, js), 1):
                dfs.append(df)
                if i % 16 == 0 or i == len(js):
                    print(f"  control (ii): {i}/{len(js)} symbol-days ({'BTC' if w == 1 else 'others'}), "
                          f"{time.time() - t0:.0f}s", flush=True)
    df = pd.concat(dfs, ignore_index=True)
    miss = df[df.missing.fillna("") != ""][["day", "sym", "missing"]]
    df = df[df.missing.fillna("") == ""].copy()
    df["net02"] = df.gross_usd - 2e-4 * df.taker_usd
    rows, bias = [], {}
    for s in ("Q1", "Q2", "Q5"):
        a = df[(df.strat == s) & (df.leg == "trades-only F1")].set_index(["day", "sym"])
        b = df[(df.strat == s) & (df.leg == "true book FIFO")].set_index(["day", "sym"])
        j = a.join(b, lsuffix="_to", rsuffix="_tr", how="inner")
        pooled = 1e4 * (j.net02_to.sum() / j.filled_usd_to.sum() - j.net02_tr.sum() / j.filled_usd_tr.sum())
        jj = j[(j.filled_usd_to > 0) & (j.filled_usd_tr > 0)]
        per = 1e4 * (jj.net02_to / jj.filled_usd_to - jj.net02_tr / jj.filled_usd_tr)
        mean_d = float(per.mean())
        se_d = float(per.std(ddof=1) / math.sqrt(len(per))) if len(per) > 1 else np.nan
        bias[s] = max(pooled, mean_d)
        rows.append(dict(strat=s, symbol_days=len(j), symbol_days_both_filled=len(jj),
                         to_net_bp=1e4 * j.net02_to.sum() / j.filled_usd_to.sum(), true_net_bp=1e4 * j.net02_tr.sum() / j.filled_usd_tr.sum(),
                         to_gross_bp=1e4 * j.gross_usd_to.sum() / j.filled_usd_to.sum(), true_gross_bp=1e4 * j.gross_usd_tr.sum() / j.filled_usd_tr.sum(),
                         pooled_diff_bp=pooled, mean_symday_diff_bp=mean_d, se_mean_diff_bp=se_d, bias_bp=bias[s],
                         correction_applied=bias[s] > 0.5,
                         to_filled_usd_day=j.filled_usd_to.mean(), true_filled_usd_day=j.filled_usd_tr.mean(),
                         to_fills_day=(j.n_maker_to + j.n_crossed_to).mean(), true_fills_day=(j.n_maker_tr + j.n_crossed_tr).mean(),
                         to_net_usd_day=j.net02_to.mean(), true_net_usd_day=j.net02_tr.mean(),
                         to_mk60_bp=1e4 * j.mk60_usd_to.sum() / j.mk60_cov_usd_to.sum(), true_mk60_bp=1e4 * j.mk60_usd_tr.sum() / j.mk60_cov_usd_tr.sum()))
    summ = pd.DataFrame(rows)
    # (iii) front of the queue at every new level vs the back of the displayed queue
    f = df[(df.strat == "Q1") & (df.leg == "true book FRONT")].set_index(["day", "sym"])
    b = df[(df.strat == "Q1") & (df.leg == "true book FIFO")].set_index(["day", "sym"])
    j = f.join(b, lsuffix="_front", rsuffix="_fifo", how="inner")
    iii = pd.DataFrame([dict(symbol_days=len(j), front_net_bp=1e4 * j.net02_front.sum() / j.filled_usd_front.sum(),
                             fifo_net_bp=1e4 * j.net02_fifo.sum() / j.filled_usd_fifo.sum(),
                             front_net_usd_day=j.net02_front.mean(), fifo_net_usd_day=j.net02_fifo.mean(),
                             speed_value_usd_day=(j.net02_front - j.net02_fifo).mean(),
                             speed_value_se=(j.net02_front - j.net02_fifo).std(ddof=1) / math.sqrt(len(j)),
                             front_filled_usd_day=j.filled_usd_front.mean(), fifo_filled_usd_day=j.filled_usd_fifo.mean())])
    by_sym = df.groupby(["sym", "strat", "leg"]).apply(lambda x: pd.Series(dict(
        days=len(x), net_bp=1e4 * x.net02.sum() / max(x.filled_usd.sum(), 1e-9), filled_usd_day=x.filled_usd.mean(),
        net_usd_day=x.net02.mean())), include_groups=False).reset_index()
    RES.mkdir(parents=True, exist_ok=True)
    summ.to_csv(RES / "control_ii.csv", index=False)
    iii.to_csv(RES / "control_iii.csv", index=False)
    by_sym.to_csv(RES / "control_ii_by_symbol.csv", index=False)
    miss.to_csv(RES / "control_ii_missing.csv", index=False)
    pd.DataFrame([dict(day=d) for d in days]).to_csv(RES / "control_ii_days.csv", index=False)
    bias.update(Q3=bias["Q1"], Q1LO=bias["Q1"])
    (RES / "control_ii_bias.json").write_text(json.dumps(bias, indent=1))
    return summ, iii, miss


# ============================================================================================ analysis
def load_rows(stratum: str, data_dir: Path = DATA) -> pd.DataFrame:
    fs = sorted((data_dir / stratum).glob("*/*.parquet"))
    if not fs:
        return pd.DataFrame()
    df = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    df["day"] = pd.to_datetime(df["day"])
    df["half"] = np.where(df.month <= "2026-03", 1, 2)
    df["n_fills"] = df.n_maker + df.n_crossed
    return df


def net(u: pd.DataFrame, fm=0.0, ft=2.0) -> np.ndarray:
    return (u.gross_usd - fm * 1e-4 * u.maker_usd - ft * 1e-4 * u.taker_usd).to_numpy()


def spy_after_tax(start="2025-10-01", end="2026-09-30") -> float:
    try:
        p = pd.read_parquet(SPY_PRICES)
        s = p[(p.ticker == "SPY") & (p.date >= start) & (p.date <= end)].sort_values("date")
        r = s.adj.iloc[-1] / s.adj.iloc[0] - 1
        return float(r * (1 - 0.20) if r > 0 else r)
    except Exception:
        return np.nan


def listing_dates(syms, path: Path) -> pd.Series:
    have = pd.read_csv(path).set_index("sym").first_month if path.exists() else pd.Series(dtype=str)
    todo = [s for s in syms if s not in have.index]

    def one(s):
        try:
            _, ks = s3_ls(f"data/spot/monthly/klines/{s}/1d/")
            ms = sorted(k.split("-1d-")[-1][:7] for k, _ in ks if k.endswith(".zip"))
            return s, ms[0] if ms else ""
        except Exception:
            return s, ""
    if todo:
        with cf.ThreadPoolExecutor(16) as ex:
            new = dict(ex.map(one, todo))
        have = pd.concat([have, pd.Series(new)])
        have.rename("first_month").rename_axis("sym").reset_index().to_csv(path, index=False)
    return have


def cell_stats(u: pd.DataFrame, size: float, fm=0.0, ft=2.0, spy=np.nan, boot=True) -> dict:
    """Every per-cell number of the pre-registration (Part A 'Reported for every cell' + general rules)."""
    x = net(u, fm, ft)
    n = len(u)
    if n < 3:
        return dict(n_units=n)
    m, se, t, p, dfree = SS.cluster2_t(x, u.sym.to_numpy(), u.week.to_numpy())
    fil = u.filled_usd.to_numpy()
    R, Rse, Rdf = SS.ratio_cluster2(x, fil, u.sym.to_numpy(), u.week.to_numpy())
    Sf = fil.sum()
    gross_bp = 1e4 * u.gross_usd.sum() / Sf if Sf > 0 else np.nan
    act = u.n_fills.to_numpy() > 0
    daysum = pd.Series(x).groupby(u.day.to_numpy()).sum()
    mon = pd.Series(x).groupby(u.month.to_numpy()).mean()
    mt = mon.mean() / (mon.std(ddof=1) / math.sqrt(len(mon))) if len(mon) > 2 and mon.std(ddof=1) > 0 else np.nan
    mp = float(1 - SS.stats.t.cdf(mt, len(mon) - 1)) if np.isfinite(mt) else np.nan
    bp_ = np.nan
    if boot:
        rng = np.random.default_rng(SEED)
        dsum = pd.Series(x).groupby(u.day.to_numpy()).agg(["sum", "size"])
        ss, cc = dsum["sum"].to_numpy(), dsum["size"].to_numpy()
        idx = rng.integers(0, len(ss), size=(4999, len(ss)))
        bm = ss[idx].sum(1) / cc[idx].sum(1)
        bp_ = SS.boot_p(m, bm)
    cap = 4 * size
    sd = float(np.std(x, ddof=1))
    ann = 365 * m / cap
    port = pd.Series(x).groupby(u.day.to_numpy()).mean()
    exit_pnl = (u.exit_cost_usd - ft * 1e-4 * u.exit_usd).sum()
    out = dict(
        n_units=n, n_pairs=u.sym.nunique(), n_days=u.day.nunique(), mean_usd=m, se=se, t=t, p_one_sided=p, df=dfree,
        mde_usd=SS.mde(se, dfree), share_active=float(act.mean()), mean_active_usd=float(x[act].mean()) if act.any() else np.nan,
        edge_bp=1e4 * R, edge_se_bp=1e4 * Rse, edge_df=Rdf,
        edge_ub_bp=SS.upper_bound(1e4 * R, 1e4 * Rse, Rdf), edge_ub95_bp=SS.upper_bound(1e4 * R, 1e4 * Rse, Rdf, level=0.95),
        edge_lo95_bp=1e4 * R - SS.stats.t.ppf(0.975, Rdf) * 1e4 * Rse, edge_hi95_bp=1e4 * R + SS.stats.t.ppf(0.975, Rdf) * 1e4 * Rse,
        gross_bp=gross_bp, fee_bp=gross_bp - 1e4 * R if np.isfinite(R) else np.nan, net_bp=1e4 * R,
        filled_usd_day=fil.mean(), maker_usd_day=u.maker_usd.mean(), taker_usd_day=u.taker_usd.mean(),
        crossed_usd_day=u.crossed_usd.mean(), exit_usd_day=u.exit_usd.mean(),
        maker_share_filled=u.maker_usd.sum() / Sf if Sf > 0 else np.nan,
        q01=np.quantile(x, .01), q05=np.quantile(x, .05), q25=np.quantile(x, .25), q50=np.quantile(x, .5),
        q75=np.quantile(x, .75), q95=np.quantile(x, .95), q99=np.quantile(x, .99), worst_pairday=x.min(),
        worst_day=str(daysum.idxmin().date()), worst_day_usd=float(daysum.min()),
        fill_rate=u.n_orders_filled.sum() / max(u.n_orders.sum(), 1), share_pair_volume=Sf / max(u.day_qv.sum(), 1e-9),
        fills_per_day=u.n_fills.mean(), max_inv_usd=u.max_inv_usd.max(), mean_max_inv_usd=u.max_inv_usd.mean(),
        mk60_bp=1e4 * u.mk60_usd.sum() / max(u.mk60_cov_usd.sum(), 1e-9), mk300_bp=1e4 * u.mk300_usd.sum() / max(u.mk300_cov_usd.sum(), 1e-9),
        exit_pnl_usd_day=exit_pnl / n, exit_pnl_share_of_net=exit_pnl / x.sum() if x.sum() != 0 else np.nan,
        passive_pnl_usd_day=(x.sum() - exit_pnl) / n,
        month_t=mt, month_p=mp, boot_p=bp_, capital_usd=cap, ann_return=ann, sharpe_pair=m / sd * math.sqrt(365) if sd > 0 else np.nan,
        sharpe_portfolio=port.mean() / port.std(ddof=1) * math.sqrt(365) if port.std(ddof=1) > 0 else np.nan,
        ann_return_after_tax=ann * (1 - 0.35) if ann > 0 else ann, spy_after_tax=spy,
        route="bot on a crypto-venue API (not Robinhood)", orders_per_day=u.n_orders.mean(), cancels_per_day=u.n_cancels.mean(),
        stopped_pairdays=int(((u.flag_bits.astype(int) & FLAG_STOPPED) > 0).sum()),
        nodata_pairdays=int((~u.has_data).sum()))
    for r_ in (0.10, 0.25, 0.50):
        mu = r_ * cap / 365
        out[f"months_t2_at_{int(r_ * 100)}pct"] = (2 * sd / mu) ** 2 / 30.44
    return out


def _bias() -> dict:
    p = RES / "control_ii_bias.json"
    return json.loads(p.read_text()) if p.exists() else {}


def primary_cells(df: pd.DataFrame, bias: dict) -> pd.DataFrame:
    rows = []
    for s in (Q1, Q2, Q5):
        for b in BANDS:
            u = df[(df.config == PRIMARY[s]) & (df.band == b)]
            u1 = df[(df.config == DELTA1[s]) & (df.band == b)]
            tid = f"A-{STRAT_NAME[s]}-{b}"
            r = dict(test_id=tid, part="A", statistic_name="mean net $ per pair-day (fee 0/2, $1k, F1, 250 ms)",
                     edge_name="net bp per $ filled", threshold_E=E_THRESH, friend_relevant=s == Q5, n_units=len(u))
            if len(u) < 3:
                rows.append(r)
                continue
            x = net(u)
            m, se, t, p, dfree = SS.cluster2_t(x, u.sym.to_numpy(), u.week.to_numpy())
            R, Rse, Rdf = SS.ratio_cluster2(x, u.filled_usd.to_numpy(), u.sym.to_numpy(), u.week.to_numpy())
            h1, h2 = x[u.half.to_numpy() == 1], x[u.half.to_numpy() == 2]
            md, dd = SS.drop_worst(x, u.day.dt.strftime("%Y-%m-%d").to_numpy())
            bb_ = float(bias.get(STRAT_NAME[s], np.nan))
            corr = bb_ if (np.isfinite(bb_) and bb_ > 0.5) else 0.0
            xc = x - corr * 1e-4 * u.filled_usd.to_numpy()
            mc, sec, tc, pc_, dfc = SS.cluster2_t(xc, u.sym.to_numpy(), u.week.to_numpy())
            Rc, Rsec, Rdfc = SS.ratio_cluster2(xc, u.filled_usd.to_numpy(), u.sym.to_numpy(), u.week.to_numpy())
            x1 = net(u1) if len(u1) else np.array([np.nan])
            r.update(estimate=m, se=se, df=dfree, t=t, p_one_sided=p, edge_estimate=1e4 * R, edge_se=1e4 * Rse, edge_df=Rdf,
                     cond_halves=bool(len(h1) and len(h2) and h1.mean() > 0 and h2.mean() > 0),
                     cond_delta1s=bool(np.nanmean(x1) > 0), cond_dropworst=bool(md > 0),
                     cond_biascorr=bool(mc > 0) if np.isfinite(bb_) else False,
                     share_active=float((u.n_fills > 0).mean()),
                     mde=SS.mde(se, dfree), edge_ub=SS.upper_bound(1e4 * R, 1e4 * Rse, Rdf),
                     edge_ub95=SS.upper_bound(1e4 * R, 1e4 * Rse, Rdf, level=0.95),
                     mean_half1=h1.mean() if len(h1) else np.nan, mean_half2=h2.mean() if len(h2) else np.nan,
                     n_half1=len(h1), n_half2=len(h2), mean_delta1s=float(np.nanmean(x1)), n_delta1s=len(u1),
                     mean_dropworst=md, dropped_day=dd, bias_bp=bb_, bias_bp_applied=corr,
                     bias_available=bool(np.isfinite(bb_)), corr_estimate=mc, corr_se=sec, corr_t=tc, corr_p_one_sided=pc_,
                     corr_df=dfc, corr_edge_estimate=1e4 * Rc, corr_edge_se=1e4 * Rsec, corr_edge_df=Rdfc,
                     corr_edge_ub=SS.upper_bound(1e4 * Rc, 1e4 * Rsec, Rdfc))
            rows.append(r)
    cols = ["test_id", "part", "statistic_name", "estimate", "se", "df", "t", "p_one_sided", "edge_name", "edge_estimate",
            "edge_se", "edge_df", "threshold_E", "cond_halves", "cond_delta1s", "cond_dropworst", "cond_biascorr",
            "n_units", "share_active"]
    out = pd.DataFrame(rows)
    return out[[c for c in cols if c in out] + [c for c in out if c not in cols]]


def _splits(df: pd.DataFrame, ages: pd.Series) -> pd.DataFrame:
    """Split labels per pair-day, all measured before the month (I3)."""
    pm = df.groupby(["sym", "month", "band"]).agg(st=("pre_spread_ticks", "first"), sv=("pre_spread_to_vol", "first"),
                                                  vol=("pre_vol_daily", "first")).reset_index()

    def terc(v):
        r = v.rank(method="first")
        return pd.cut(r, 3, labels=["T1 low", "T2", "T3 high"]) if v.notna().sum() >= 3 else pd.Series(np.nan, index=v.index)
    pm["spread_vol_tercile"] = pm.groupby("band").sv.transform(lambda v: terc(v.dropna()).reindex(v.index).astype(object))
    pm["vol_tercile"] = pm.groupby("band").vol.transform(lambda v: terc(v.dropna()).reindex(v.index).astype(object))
    pm["tick_class"] = np.where(pm.st <= 1.5, "tick-constrained (<=1.5 ticks)", np.where(pm.st >= 3, "wide (>=3 ticks)",
                                                                                         np.where(pm.st.notna(), "1.5-3 ticks", None)))
    fm = pd.to_datetime(pm.sym.map(ages).fillna("") + "-01", errors="coerce")
    age = (pd.to_datetime(pm.month + "-01") - fm).dt.days / 365.25
    pm["listing_age"] = np.where(age < 1, "<1 y", np.where(age < 3, "1-3 y", np.where(age >= 3, ">=3 y", None)))
    return df.merge(pm.drop(columns=["st", "sv", "vol"]), on=["sym", "month", "band"], how="left")


def analyze(data_dir: Path = DATA, res_dir: Path | None = None, boot=True):
    global RES
    if res_dir is not None:
        RES = res_dir
    RES.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 500)
    log = open(RES / "summary.txt", "w")

    def say(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    df = load_rows("main", data_dir)
    if df.empty:
        say("no Part A pair-day results under", data_dir / "main"); return
    bias = _bias()
    spy = spy_after_tax()
    ages = listing_dates(sorted(df.sym.unique()), RES / "listing_dates.csv") if res_dir is None else pd.Series(dtype=str)
    df = _splits(df, ages)
    size_of = {cfg_name(*c): c[1] for c in MAIN_CONFIGS + ARH_CONFIGS}
    say("Part A: passive quoting on illiquid Binance spot pairs (SCALPING_PREREG.md). Units = pair-days.")
    say(f"pair-days per config: {df.groupby('config').size().min():,} - {df.groupby('config').size().max():,}; "
        f"pairs {df.sym.nunique()}; control (ii) bias (bp per $ filled): {bias}")
    # ---------------------------------------------------------------- primary cells
    pc = primary_cells(df, bias)
    pc.to_csv(RES / "primary_cells.csv", index=False)
    prov = pc[["test_id", "p_one_sided"]].copy()
    prov["p_holm_within_A_provisional"] = SS.holm(prov.p_one_sided.to_numpy())
    prov.to_csv(RES / "primary_cells_provisional_holm_within_A.csv", index=False)
    say("\nPRIMARY CELLS (Holm across all 36 tests is applied by the combine script):")
    say(pc[[c for c in pc.columns[:19] if c not in ("part", "statistic_name", "edge_name")]].to_string(index=False))
    # ---------------------------------------------------------------- per-cell report, fee ladder, sensitivities
    rep, ladder, sens, cap_rows = [], [], [], []
    for s in (Q1, Q2, Q5):
        for b in BANDS:
            u = df[(df.config == PRIMARY[s]) & (df.band == b)]
            if len(u) < 3:
                continue
            rep.append(dict(cell=f"A-{STRAT_NAME[s]}-{b}", **cell_stats(u, 1000, spy=spy, boot=boot)))
            Sm, St, Sg, Sf = u.maker_usd.sum(), u.taker_usd.sum(), u.gross_usd.sum(), u.filled_usd.sum()
            for (fm, ft), nm in list(zip(FEES, FEE_NAMES)) + [((r_, 2.0), f"{r_}/2 maker rebate") for r_ in REBATES]:
                x = net(u, fm, ft)
                ladder.append(dict(cell=f"A-{STRAT_NAME[s]}-{b}", fee=nm, maker_bp=fm, taker_bp=ft, net_usd_pairday=x.mean(),
                                   net_bp_per_filled=1e4 * x.sum() / Sf if Sf > 0 else np.nan,
                                   breakeven_maker_bp_at_taker2=1e4 * (Sg - 2e-4 * St) / Sm if Sm > 0 else np.nan))
    pd.DataFrame(rep).to_csv(RES / "cell_report.csv", index=False)
    pd.DataFrame(ladder).to_csv(RES / "fee_ladder.csv", index=False)
    for c in sorted(df.config.unique()):
        for b in BANDS:
            u = df[(df.config == c) & (df.band == b)]
            if len(u) < 3:
                continue
            st = cell_stats(u, size_of.get(c, 1000), spy=spy, boot=False)
            sens.append(dict(config=c, band=b, **{k_: st[k_] for k_ in ("n_units", "mean_usd", "se", "t", "p_one_sided",
                                                                        "edge_bp", "edge_se_bp", "gross_bp", "net_bp",
                                                                        "filled_usd_day", "share_active", "fill_rate",
                                                                        "share_pair_volume", "mk60_bp", "mk300_bp")}))
            if c.split("_")[2] == "F1" and c.endswith("250ms_100"):
                cap_rows.append(dict(config=c, strat=c.split("_")[0], size=size_of.get(c), band=b,
                                     filled_usd_day=st["filled_usd_day"], net_usd_day=st["mean_usd"],
                                     gross_usd_day=u.gross_usd.mean(), share_pair_volume=st["share_pair_volume"],
                                     max_inv_usd=st["max_inv_usd"]))
    sens = pd.DataFrame(sens); sens.to_csv(RES / "sensitivities.csv", index=False)
    capd = pd.DataFrame(cap_rows); capd.to_csv(RES / "capacity.csv", index=False)
    say("\nCELL REPORT (primary settings):")
    say(pd.DataFrame(rep)[["cell", "n_units", "mean_usd", "edge_bp", "gross_bp", "fee_bp", "filled_usd_day", "share_active",
                           "fill_rate", "mk60_bp", "mk300_bp", "exit_pnl_usd_day", "month_t", "boot_p", "ann_return"]].to_string(index=False))
    say("\nCAPACITY (F1, 250 ms, 100%):"); say(capd.to_string(index=False))
    # ---------------------------------------------------------------- kill rule (F2 at fee 0/2)
    kr = sens[sens.config.isin([F2CFG[s] for s in (Q1, Q2, Q5, Q3)])][["config", "band", "mean_usd", "edge_bp"]]
    kill = bool(len(kr) and (kr.mean_usd <= 0).all())
    kr = kr.assign(le_zero=kr.mean_usd <= 0); kr.to_csv(RES / "kill_rule.csv", index=False)
    say(f"\nKILL RULE (every strategy and band <= 0 under F2 at fee 0/2): {kill}"); say(kr.to_string(index=False))
    # ---------------------------------------------------------------- splits and the exploratory conditional cell
    sp = []
    for s in (Q1, Q2, Q5):
        for b in BANDS:
            u0 = df[(df.config == PRIMARY[s]) & (df.band == b)]
            for var in ("tick_class", "spread_vol_tercile", "vol_tercile", "listing_age", "weekend"):
                lab = (u0.dow >= 5).map({True: "weekend", False: "weekday"}) if var == "weekend" else u0[var]
                for g, u in u0.groupby(lab.to_numpy(), dropna=True):
                    if len(u) < 3:
                        continue
                    st = cell_stats(u, 1000, boot=False)
                    sp.append(dict(cell=f"A-{STRAT_NAME[s]}-{b}", split=var, group=g, **{k_: st[k_] for k_ in (
                        "n_units", "mean_usd", "se", "p_one_sided", "edge_bp", "edge_se_bp", "filled_usd_day", "share_active")}))
    pd.DataFrame(sp).to_csv(RES / "splits.csv", index=False)
    cc = []
    for b in list(BANDS) + ["all"]:
        u = df[(df.config == PRIMARY[Q2]) & (df.spread_vol_tercile == "T3 high") & ((df.band == b) if b != "all" else True)]
        if len(u) >= 3:
            cc.append(dict(cell=f"A-Q2 top spread/vol tercile, band {b}", **cell_stats(u, 1000, spy=spy, boot=boot)))
    pd.DataFrame(cc).to_csv(RES / "conditional_cell.csv", index=False)
    st_ = df[df.config.isin(PRIMARY.values()) & ((df.flag_bits.astype(int) & FLAG_STOPPED) > 0)]
    st_[["config", "sym", "band", "day", "gross_usd", "exit_usd"]].to_csv(RES / "stopped_pairdays.csv", index=False)
    df[df.config == PRIMARY[Q1]].groupby(["month", "band"]).agg(pair_days=("sym", "size"), pairs=("sym", "nunique"),
                                                                 nodata=("has_data", lambda v: int((~v).sum()))
                                                                 ).reset_index().to_csv(RES / "units.csv", index=False)
    # ---------------------------------------------------------------- A-RH stratum (exploratory, outside Holm)
    ar = load_rows("arh", data_dir)
    if not ar.empty:
        rows = []
        for s in (Q1, Q2, Q5, Q1LO):
            for b in sorted(ar.band.unique()) + ["all"]:
                u = ar[(ar.config == PRIMARY[s]) & ((ar.band == b) if b != "all" else True)]
                if len(u) < 3:
                    continue
                st = cell_stats(u, 1000, spy=spy, boot=boot)
                x = net(u)
                u1 = ar[(ar.config == DELTA1[s]) & ((ar.band == b) if b != "all" else True)]
                md, _ = SS.drop_worst(x, u.day.dt.strftime("%Y-%m-%d").to_numpy())
                bb_ = float(bias.get(STRAT_NAME[s], np.nan)); corr = bb_ if (np.isfinite(bb_) and bb_ > 0.5) else 0.0
                h = u.half.to_numpy()
                rows.append(dict(cell=f"A-RH-{STRAT_NAME[s]}-{b}", **st,
                                 cond_halves=bool((h == 1).any() and (h == 2).any() and x[h == 1].mean() > 0 and x[h == 2].mean() > 0),
                                 cond_delta1s=bool(len(u1) and net(u1).mean() > 0), cond_dropworst=md > 0,
                                 cond_biascorr=bool((x - corr * 1e-4 * u.filled_usd.to_numpy()).mean() > 0),
                                 f2_mean_usd=net(ar[(ar.config == F2CFG[s]) & ((ar.band == b) if b != "all" else True)]).mean()))
        pd.DataFrame(rows).to_csv(RES / "arh_cells.csv", index=False)
        say("\nA-RH STRATUM (exploratory, every 7th day):")
        say(pd.DataFrame(rows)[["cell", "n_units", "mean_usd", "se", "p_one_sided", "edge_bp", "share_active"]].to_string(index=False))
    else:
        say("\nA-RH stratum: no results (needs data/scalping/rh/currency_pairs.json, then --run --stratum arh)")
    ci = RES / "control_i_check.csv"
    if ci.exists():
        say("\nCONTROL (i) no-information level (Q1, true queue, alpha 0): 60-s markout vs half-spread (bp)")
        say(pd.read_csv(ci)[["market", "S", "half_spread_bp", "mk60_bp", "mk60_se_bp", "pass"]].to_string(index=False))
        c1 = pd.read_csv(RES / "control_i.csv")
        say("Engine no-information level (alpha 0): net bp per $ filled at fee 0/2 by fill model")
        say(c1[c1.alpha == 0].pivot_table(index=["market", "S", "strat"], columns="fill", values="net02_bp").round(2).to_string())
    log.close()
    return pc


# ============================================================================================ CLI
def main():
    ap = argparse.ArgumentParser(description="Part A: passive quoting on illiquid Binance spot pairs")
    ap.add_argument("--universe", action="store_true", help="exclusions, eligibility, draws (no trades read)")
    ap.add_argument("--tests", action="store_true", help="engine unit tests on hand-built tapes")
    ap.add_argument("--controls", action="store_true", help="Control (i) synthetic market, (ii)+(iii) USD-M true book")
    ap.add_argument("--smoke", action="store_true", help="2 drawn pairs x 3 days, timing only")
    ap.add_argument("--run", action="store_true", help="simulate every drawn pair-month (incremental)")
    ap.add_argument("--stratum", choices=["main", "arh", "both"], default="both")
    ap.add_argument("--analyze", action="store_true", help="primary_cells.csv and the reporting tables")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 300)
    if not any((a.universe, a.tests, a.controls, a.smoke, a.run, a.analyze)):
        print(__doc__.split("------")[0]); return
    if a.universe:
        k, excl, elig, dr, arh = universe(write=True)
        print(f"exclusions {len(excl)} ({excl.reason.value_counts().to_dict()}); draws {len(dr)} pair-months, "
              f"{dr.sym.nunique()} pairs, fallback slots {int(dr.fallback.sum())}; A-RH pairs "
              f"{'n/a (no currency_pairs.json)' if arh is None else int((~arh.excluded).sum())}")
        print(dr.groupby(["month", "band"]).size().unstack().fillna(0).astype(int).to_string())
    if a.tests:
        if not tests():
            sys.exit(1)
    if a.controls:
        summ, q = control_i()
        print("Control (i): Q1 under the true queue at alpha = 0 (60-s markout vs half-spread, bp)")
        print(q[["market", "S", "half_spread_bp", "mk0_bp", "mk60_bp", "mk60_se_bp", "dev_bp", "pass"]].round(3).to_string(index=False))
        print(summ[["market", "S", "alpha", "strat", "fill", "fills_per_day", "mk60_bp", "gross_bp", "net02_bp"]].round(2).to_string(index=False))
        s2, iii, miss = control_ii(workers=min(a.workers, 3))
        print("Control (ii): trades-only F1 vs true-book FIFO, net bp per $ filled at fee 0/2")
        print(s2.round(3).to_string(index=False))
        print("Control (iii): front of the queue vs back of the displayed queue (Q1)")
        print(iii.round(3).to_string(index=False))
        print(f"missing symbol-days: {len(miss)}")
    if a.smoke:
        smoke()
    if a.run:
        if a.stratum in ("main", "both"):
            run_all("main", a.workers)
        if a.stratum in ("arh", "both"):
            run_all("arh", a.workers)
    if a.analyze:
        analyze()


if __name__ == "__main__":
    main()
