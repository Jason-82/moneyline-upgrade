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
(Places where the pre-registration could not be followed exactly; see also C2.)
  D1  Robinhood currency pairs (A-RH) are read from data/scalping/rh/currency_pairs.json when it exists.
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
             "n_orders", "n_cancels", "n_orders_filled", "flags", "n_tmax", "n_postonly_cancel", "eod_inv_usd",
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
    t = pacsv.read_csv(io.BytesIO(b))
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
    res.append(ok(int(j1["flags"]) & FLAG_STOPPED and close(j1["exit_usd"], 4 * 99.9 * (1 - 0.6 / 100.2)),
                  "stopped trading: last seller print x (1 - implied spread)"))
    # --- K: Q1-LO never sells coins it does not hold; Q1 does (pre-held coins)
    tk = [(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 100.6, 5, 1), (20, 99.5, 1, -1), (21, 100.7, 1, 1)]
    k1, k2 = _run(tk, strat=Q1LO), _run(tk, strat=Q1)
    res.append(ok(k1["sold_usd"] == 0 and close(k2["sold_usd"], 5 * 100.5), "Q1-LO long-only; Q1 may sell down pre-held coins"))
    # --- L: 25% participation; Q3 one tick behind; latency 1 s
    l1 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 4, -1), (20, 99.5, 1, -1)], part=0.25)
    res.append(ok(close(l1["bought_usd"], 1 * 100.0), "25% participation takes a quarter of the through volume"))
    l2 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (3, 99.9, 4, -1), (4, 99.85, 4, -1), (20, 99.5, 1, -1)], strat=Q3)
    res.append(ok(close(l2["bought_usd"], 4 * 99.9) and l2["n_maker"] == 1,
                  f"Q3 bids one tick behind (99.9): filled only by the 99.85 print ({l2['bought_usd']:.2f})"))
    l3 = _run([(1, 100.0, 1, -1), (2, 100.5, 1, 1), (2.9, 99.9, 4, -1), (20, 99.5, 1, -1)], delta=1.0)
    res.append(ok(l3["bought_usd"] == 0, "latency 1 s: an order decided at t=2 is not live at 2.9"))
    print(f"{sum(res)}/{len(res)} engine tests passed")
    return all(res)
