"""
Data layer of the stink-bid study: universes, bars, futures series, capacity and integrity rules, exactly as frozen in
analysis_2026/STINKBID_PREREG.md (§4 data, §4.1 integrity rules, §5 universes, §7 capacity, §9 carry), with the draft's
data series (research_notes/Stink bids/design_draft.md §4.1-4.2), level inputs (§6.1-6.2: daily bars back to 2017-08
for M3, 1h bars for M6, open interest / mark prices for M7) and capacity window (§8.3). Module contract:
research_notes/Stink bids/build_spec.md. Reuses analysis_2026/fetch_stinkbid_data.py (listing, exclusion lists, the
2019-10.. daily and 2020-01.. hourly files), the S3 helpers of fetch_scalping_data.py and the checksum-verified kline
builder of fetch_bb_data.py; none of them is edited. Counts, coverage and timings only: nothing here computes a
post-fill price, return or outcome.

    python3 -m analysis_2026.stinkbid_data ages          # first monthly 1d file per base x quote (USDT BTC BNB ETH BUSD)
    python3 -m analysis_2026.stinkbid_data d1-2017       # daily klines from listing for pairs listed before 2019-10
    python3 -m analysis_2026.stinkbid_data universes     # monthly ranks (exclusions + backstop), U-B, U-Q1, ... U-C
    python3 -m analysis_2026.stinkbid_data segments      # ref/segments.csv only (part of universes)
    python3 -m analysis_2026.stinkbid_data h1pre         # hourly 2019-10..12 in front of h1_spot (M6's 90-day look-back)
    python3 -m analysis_2026.stinkbid_data m1            # 1m spot klines for U-Q1 u U-Q1-12 u U-A u U-C (+ successors)
    python3 -m analysis_2026.stinkbid_data metrics       # USD-M 5-minute metrics (open interest) for U-Q1 coins (M7)
    python3 -m analysis_2026.stinkbid_data mark          # USD-M 1h mark-price klines for U-Q1 coins (M7)
    python3 -m analysis_2026.stinkbid_data perp1h        # USD-M 1h last-price klines for U-Q1 coins (M7's hourly VWAP)
    python3 -m analysis_2026.stinkbid_data usd           # USDT/USD hourly proxy (BUSD, USDC, TUSD against USDT)
    python3 -m analysis_2026.stinkbid_data tbill         # FRED DTB3 (continues rf_annual_pct's source) and DGS3MO
    python3 -m analysis_2026.stinkbid_data index1d       # USD-M 1d index klines of the 1m coins (V4's fetch rule)
    python3 -m analysis_2026.stinkbid_data index1m|perp1m --coins NEAR,SOL --months 2025-10,2021-05   (prefetch)
    python3 -m analysis_2026.stinkbid_data agg --windows FILE.parquet   # capacity windows (coin, wid, L, start, end)
    python3 -m analysis_2026.stinkbid_data report        # counts and coverage (no outcome)
    python3 -m analysis_2026.stinkbid_data all           # ages d1-2017 universes h1pre usd tbill m1 metrics mark
                                                         # perp1h index1d report
    python3 -m analysis_2026.stinkbid_data selftest      # synthetic known answers + real-data invariants
  options: --workers N (download threads)  --procs N (m1 processes, default 4)  --force (rebuild existing files)
           --coins A,B (restrict a bulk step; m1's default set is U-Q1 u U-Q1-12 u U-A u U-C, the U-A / U-C lists
           and their successors)

Public functions (UTC timestamps, datetime64[ns, UTC], bars labelled by their open time):
  universes(first, last) -> month, coin, sym, U_B, U_Q1, U_Q1_12, U_Q1_xm, U_C, U_A, rank, rank_med12,
                            listing_age_months, adv90, days_traded90, sd90, lineage      (one row per ranked coin-month)
  ranks(first, last)     -> every coin-month passing the U-B volume eligibility, with the backstop flag and rank
  backstop(first, last)  -> the stablecoin backstop (sd90 < 0.5%) for every non-excluded coin-month (M3's pool)
  d1(coin), h1(coin), m1(coin, start, end), m1_stream(coin) -> open_time, open, high, low, close, volume,
                            quote_volume, trades, taker_buy_quote, seg
  d1_panel()             -> every USDT pair's daily bars from listing (2017-08 for BTC), with coin, seg, excluded
  segments(coin)         -> one row per segment: first/last day, end kind, continues (a position continues), units,
                            successor, ratio checks, delisting values (VWAP of the last full trading day; last trade),
                            last_trade_time (the minute of the last trade for every segment ending before END)
  delist_value(coin, t)  -> the §4.1 value of a position open when trading stops (VWAP x (1 - 0.30) and sensitivities)
  swaps(), redenominations(), successor(coin), predecessors(coin), lineage(coin), coin_sym(coin), um_contract(coin),
  first_listing(), u_c_coins(), excluded_bases()
  index1m(coin, day), perp1m(coin, day), index1d(coin), fut_prefetch(kind, coin_days), index_fetch_days(bids)
  metrics(coin), mark1h(coin), perp1h(coin)
  agg_capacity(coin, day, windows), agg_prefetch(windows)
  usdt_usd_hourly(), rh_pairs(), tbill_daily(index), tbill_series()

Writes (all under the gitignored data/stinkbid/):
  ref/ages_quotes.csv, ref/listing_gaps.csv    one S3 listing per base x quote; month gaps in the union of quotes
  d1_full/{SYM}.parquet, d1_full_all.parquet   daily klines from listing for the 80 pairs listed before 2019-10; the
                                               panel stacks them with d1_spot/ (the other pairs, identical rules)
  ref/ranks.parquet, ref/universes.parquet/.csv, ref/segments.csv
  ref/last_minute.json                         minute of the last trade on segment-end days of hourly-only coins
  h1_spot_pre/{SYM}.parquet                    hourly 2019-10..12 (joined in front of h1_spot/ by h1())
  m1_spot/{SYM}.parquet                        1m spot klines 2019-12..END: prices float64, volumes float32, trades int32
  fut1m/{index|perp}/{COIN}/{YYYY-MM}.parquet  1m USD-M index / last-price klines per coin-month, + .json day status
  fut1d/index/{COIN}.parquet                   1d index klines (V4's fetch rule)
  metrics/{COIN}.parquet, mark1h/{COIN}.parquet, perp1h/{COIN}.parquet   M7 inputs
  agg_cap/{COIN}/{DAY}.parquet                 reduced aggTrades capacity rows per requested window and minute
  usd/h1_{SYM}.parquet, usd/usdt_usd_hourly.parquet
  macro/us_market_data.csv                     the 3-month T-bill source of regime_switch.rf_annual_pct (if data/macro
                                               is absent)
  macro/fred_DTB3.csv, macro/fred_DGS3MO.csv   FRED: DTB3 continues that source after 2025-12-19; DGS3MO only checks
                                               the prereg's stated 4.21% (stats/tbill.json: coverage, overlap check)
  stats/*.json, reports/data_report.txt

Rules implemented (prereg section in brackets):
- Universes (§5). U-B: top 100 of month M by the median daily USDT volume over the traded days of the 90 days before
  M (>= 30 traded days, traded on the last day before M; fetch_stinkbid_data.universe_monthly's rule), dead and
  delisted coins included, after the exclusions: the inventory lists (stablecoins/fiat, gold, wrapped, leveraged,
  tokenized equities), PAX and USDP, and the backstop (90-day SD of daily log returns < 0.5% at the start of M).
  U-Q1: U-B with listing age >= 24 months (first monthly 1d kline of the base against any of USDT, BTC, BNB, ETH,
  BUSD) and median monthly rank <= 50 over M-11..M (unranked months count as 999, draft §5.1). U-Q1-12: age >= 12.
  U-Q1-xm: U-Q1 without DOGE SHIB PEPE FLOKI BONK WIF PEOPLE. U-A: the 24 user-style coins plus MKR. U-C: the
  Robinhood-tradable bases of the saved 2026-11-18 catalog. U-A and U-C are subsets of U-B, as in the draft's fill
  calendar (§7.4), and are hindsight sets.
- Successors (§4.1, V12) inherit the predecessor's listing age and monthly ranks: the rank history of a successor
  uses its own rank where it is ranked, else its predecessor's. A ticker reuse (LUNA from 2022-05-31 = "LUNA2",
  Terra 2.0) restarts both.
- Segments (§4.1, V2). A new segment starts after a missing UTC day (no daily kline, or one with zero trades) or at
  a day whose open is more than 25% from the prior day's close. Segments are found on the daily klines and mapped to
  1h and 1m bars by UTC day. Bars before a boundary never depend on data after it: a segment's id is fixed when it
  starts.
- Redenominations (§4.1, V9). A boundary across which next open / last close lies within +-5% of 10^n (n != 0) is
  joined at 10^n when Binance's announcement confirms it (REDENOM, with the announcement URLs); a boundary inside the
  band without a confirmation, or a confirmed one outside the band, is a delisting.
- Swaps (§4.1): EOS->A, MATIC->POL, FTM->S, RNDR->RENDER, MKR->SKY, AGIX/OCEAN->FET, BTT->BTTC, LIT->HEI continue at
  the announced ratio (SWAPS). Every one was confirmed (announcement URLs below); the data ratio is reported beside it.
  Prereg Addendum 1 (A1.1, before any outcome) reads the rule as general and adds the confirmed rebrands found by
  screening every U-B coin whose history ends: BCHABC->BCH, ERD->EGLD, LEND->AAVE, STORM->STMX, STRAT->STRAX,
  NPXS->PUNDIX, MFT->HIFI, MC->BEAMX, TOMO->VIC, GAL->G, KLAY->KAIA, DAR->D, BNX->FORM, FXS->FRAX, OM->MANTRA,
  TON->GRAM.
- Delisting value (§4.1, V9): VWAP (quote volume / volume) of the last full trading day (a UTC day with trading,
  i.e. a bar with trades > 0, in its first and last hour) x (1 - 0.30); the last trade x 0.70, 0% and 100% haircuts
  are sensitivities. A relisting after a gap (FTT) starts a new segment and the gap is a delisting.
- Capacity (§7, draft §8.3): seller-initiated (is_buyer_maker = True) aggTrades notional printed strictly below L,
  per minute, inside each requested window; the engine decides the windows and accumulates causally. "Below L" is
  tick-robust: price < L x (1 - 1e-12), so a print at L's own tick never counts (coding choice 13).
- Futures (§4, §7, V4): index klines' count field is named `updates`. 1m index / last-price bars come from the
  monthly zip of the month, and from the daily zip for days the monthly zip lacks (and for END's month); a day in
  neither is recorded as missing and never filled. Every zip is checked against its .CHECKSUM.

Coding choices the pre-registration leaves open (most literal reading; listed in the build report):
 1. U-A and U-C are subsets of U-B (the draft's calendar rows are all U-B rows; checked). U-C = the 92 tradable
    catalog pairs that have a Binance USDT spot pair of the same asset, minus the excluded USDC and PAXG and the reused
    ticker LIT (Binance's LIT was Litentry, Robinhood's is Lighter): POL is "untradable" in the catalog and is not in
    U-C. Membership is by the coin's own ticker (MKR is not in U-C; it is in U-A by name).
 2. U-B membership in month M uses the coin's own rank in M; inheritance fills only the rank HISTORY used by the
    12-month median (a successor whose own 90-day window is too short is not in U-B that month).
 3. The rank history needs months back to M-11 = 2019-02 for 2020-01, so ranks are computed from 2017-09 on the full
    daily history (d1-2017). Months with no eligible pair before 2017-10 are empty.
 4. A boundary with a >25% open jump but no missing day (trading continued; only SCR 2024-10-22, before SCR could be
    in U-B) cancels bids and restarts sigma windows; an open position continues (join at 1), because trading never
    stopped and no §4.1 valuation rule applies to it.
 5. Rebrands and swaps: the frozen list plus the confirmed ones of prereg Addendum 1 (A1.1; SWAPS) continue; any
    other rename gets no inheritance (its old ticker's end is a delisting and the new ticker's age starts at its own
    first listing). LUNA->LUNC (2022-09) is not a swap: Binance halted LUNA classic on 2022-05-13 and relisted it as
    LUNC months later, a relisting after a gap (§4.1, as FTT). QUICK's 1:1000 redenomination (2023-07-21) is joined by the general rule (inside the band,
    confirmed); QUICK was never in U-B. VIDT's confirmed 1:10 swap (2022-11-09) is 7.0% outside the band, so the
    literal rule makes it a delisting; VIDT's only U-B month (2023-02) is after it, so no bid or position is affected.
 6. Stablecoin backstop: SD (ddof 1) of daily log close-to-close returns over consecutive traded days inside one
    segment whose day lies in the 90 days before M; needs >= 2 returns; applied before ranking (the excluded coin
    does not take a rank).
 7. 1m bars start 2019-12 (the tick of the first placement reads the 7 days before 2020-01-06). Futures 1m bars are
    cached per coin-month: the monthly zip first, the daily zip for days it lacks; the daily index archive alone
    misses many days before 2021 that the monthly zips hold.
 8. "Last full trading day" = the latest UTC day of the segment with a traded bar (trades > 0; zero-trade placeholder
    bars are not trading) in hour 00 and in hour 23 (1m bars where cached, else hourly bars, which give the same hours;
    the second-to-last day where neither exists). A segment's last_trade_time is the open of its last 1m bar with
    trades > 0, the minute of the last trade, for every segment that ends before END: from the cached 1m bars, else
    from that day's 1m archive zip (ref/last_minute.json; all 126 such ends resolved, each inside the last traded hour
    of the hourly bars). Censored segments (data_end) of hourly-only coins keep the hour bar's open
    (last_trade_res = '1h'); trading does not stop there.
 9. Listing age is measured in whole calendar months from the first listing month (age at M = months between the
    two month starts). Binance's SKY/BTC, SKY/BNB and SKY/ETH pairs of 2018-05..2021-11 were Skycoin, a different
    asset: SKY's own listing starts 2025-09 (REUSE_LISTING) and it inherits MKR's 2020-07.
10. Perpetual mapping: the exact {COIN}USDT contract, else the 1000x / 1000000x contract rescaled to one coin
    (fetch_stinkbid_data.um_contracts); spot coins whose own name starts with digits (1000SATS) use the same-named
    contract 1:1; LUNA (classic) uses LUNAUSDT and LUNA2 (Terra 2.0) LUNA2USDT. Each cached futures day records
    whether its last close is within a factor of 2 of the spot close (a mapping check; no data are changed).
11. The 12-month median rank uses a full window (12 months of rank history, which exists from 2018-08 on).
12. 1m bars are kept exactly as published. Zero-trade minutes are placeholder bars whose OHLC is the prior close
    (8.8% of cached minutes, mostly 2019-2020 illiquid hours); they never fill or trigger an exit (§4.1), and they
    are the only reason a day's 1m aggregate can differ from its 1d kline: with them dropped, every cached day
    agrees with the 1d kline to 1e-9 (the builder repaired 52 days from daily zips; stats/m1.json lists the rest).
13. Capacity's "printed below L" (§7; draft §8.3: price < L, by price priority) is read on decimal prices: a print at
    L's own tick is not below L. A level floored to its tick in floating point (np.floor(x / tau) * tau) is often one
    ULP above its decimal value, so the test is price < L x (1 - 1e-12): far above that float error (2.2e-16
    relative) and far below the smallest relative Binance spot tick (about 1e-7, BTC). Cached capacity rows carry the
    rule version in their key (v2); rows reduced under the raw-float rule are never reused.
14. Cash (§4: "regime_switch.rf_annual_pct(). The 3-month T-bill was 4.21% on 2026-11-02."). The function's daily
    source, SteelCerberus's 'Risk Free Rate', ends 2025-12-19; after that it returns its annual table, a flat 3.70%
    for all of 2026. That source is FRED DTB3 (3-month bill, secondary market, discount basis): identical on 99.9% of
    the 1,552 overlapping days since 2019-10, never more than 0.01 apart. tbill_daily therefore continues it with
    DTB3 itself, handed to rf_annual_pct through its cache, so every value through 2025-12-19 is the function's own
    and 2026 follows the market (3.52-4.16%). The prereg's 4.21% is FRED DGS3MO (constant maturity, investment
    basis), a different quote of the same bill; DTB3 reads 4.03% that day (a disagreement reported, not resolved by
    switching series, which would change every value the named function gives). E = 3.75% is fixed in the prereg
    and does not use this series.
"""
from __future__ import annotations

import concurrent.futures as cf
import contextlib
import functools
import io
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pandas as pd

from analysis_2026 import fetch_bb_data as bb
from analysis_2026 import fetch_stinkbid_data as fsd
from analysis_2026.fetch_scalping_data import get, s3_ls

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "stinkbid"
END = fsd.END                                   # 2026-11-17, the last complete UTC day in the archive
UNIV_FIRST, UNIV_LAST = "2020-01", "2026-11"     # placement months (Mondays 2020-01-06 .. 2026-11-09)
RANK_FIRST = "2017-09"
M1_FROM = "2019-12"
H1_PRE = ("2019-10", "2020-01-01")               # hourly warm-up: monthly zips 2019-10..12
FUT_FROM, FUT_FROM_BTC = "2021-11", "2020-09"     # M7 inputs (prereg §4: from 2021-12; BTC from 2020-09)
QUOTES = ("USDT", "BTC", "BNB", "ETH", "BUSD")
TOP_N, Q1_RANK, Q1_AGE, Q1_12_AGE, UNRANKED = 100, 50, 24, 12, 999.0
MIN_DAYS, WINDOW = 30, 90
SD_MIN, SD_DAYS = 0.005, 90
JUMP, BAND, HAIRCUT = 0.25, 0.05, 0.30
MEMES = ("DOGE", "SHIB", "PEPE", "FLOKI", "BONK", "WIF", "PEOPLE")
U_A_COINS = tuple(fsd.USER_STYLE) + ("MKR",)
STABLE_EXTRA = ("PAX", "USDP")
WORKERS = 32
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_quote"]
NS = "datetime64[ns, UTC]"
BA = "https://www.binance.com/en/support/announcement/"

# ---------------------------------------------------------------- registry (§4.1), every ratio confirmed 2026-11-18
# Redenominations: coin -> (first day of the new segment, price ratio new/old = 10^n, Binance announcement).
REDENOM = {
    "COCOS": ("2021-01-23", 1e3, BA + "binance-will-support-the-cocos-bcx-cocos-1-000-1-redenomination-plan-"
                                       "f555f8013eff42bc9c91eaa48b9da24b"),
    "BTCST": ("2021-03-19", 1e-1, BA + "binance-will-support-the-btc-standard-hashrate-token-btcst-1-10-"
                                        "redenomination-plan-2c08ba9e1a1b409fb6a4a2cb2f5ed58b"),
    "DREP": ("2021-04-02", 1e2, BA + "binance-will-support-the-drep-drep-100-1-redenomination-plan-"
                                      "51eb4f0351194fab957bb23cc6ee52dd"),
    "SUN": ("2021-06-18", 1e-3, "https://www.binance.com/en/amp/support/announcement/f923f2e4056843a9a9b87beb2aaa2f31"),
    "VIDT": ("2022-11-09", 1e-1, BA + "binance-will-support-the-vidt-datalink-vidt-token-swap-redenomination-"
                                       "rebranding-plan-to-vidt-dao-vidt-ef40b40af1944bc9b399ad9c52861a04"),
    "BNX": ("2023-02-22", 1e-2, BA + "binance-will-support-the-binaryx-bnx-token-swap-and-redenomination-plan-"
                                      "4d23ada51a2e4fa182835c77d51ba1a9"),
    "QUICK": ("2023-07-21", 1e-3, BA + "binance-will-support-the-quickswap-quick-token-swap-and-redenomination-plan-"
                                        "50b38ae7b25a45a7854c94ab67a1e7d0"),
    "STRAX": ("2024-03-28", 1e-1, BA + "binance-will-support-the-stratis-strax-token-swap-and-redenomination-plan-"
                                        "2e6eb8e644664a6ca7b6659a226c41b0"),
}
# Swaps: predecessor -> (successor, successor units per predecessor unit, Binance announcement).
SWAPS = {
    "BTT": ("BTTC", 1000.0, BA + "binance-will-support-the-bittorrent-btt-token-migration-redenomination-and-"
                                  "renaming-plan-2722e6da4f5141dd9b2fb07b5b1f3f75"),
    "AGIX": ("FET", 0.433350, BA + "binance-will-support-the-fetch-ai-fet-ocean-protocol-ocean-and-singularitynet-"
                                    "agix-token-merge-e485541c370240adba3929fded74f269"),
    "OCEAN": ("FET", 0.433226, BA + "binance-will-support-the-fetch-ai-fet-ocean-protocol-ocean-and-singularitynet-"
                                     "agix-token-merge-e485541c370240adba3929fded74f269"),
    "RNDR": ("RENDER", 1.0, BA + "binance-will-support-the-render-rndr-token-swap-and-rebranding-to-render-render-"
                                  "d1f2ae8d99b24439a7a900caa9bb6b3b"),
    "MATIC": ("POL", 1.0, BA + "binance-will-support-the-polygon-matic-token-swap-to-polygon-pol-"
                                "6a6de383727f4659a3050f7982e1620f"),
    "FTM": ("S", 1.0, "https://www.binance.com/en/square/post/17987822177746 (repost of Binance's 'Will Support the "
                      "Fantom (FTM) Token Swap and Rebranding to Sonic (S)')"),
    "LIT": ("HEI", 1.0, "https://www.binance.com/el/support/announcement/detail/2a9feaa556f74dcdaa2192366f0e247c"),
    "EOS": ("A", 1.0, BA + "1e89a9ca957c4b0ca7502e60b993e201"),
    "MKR": ("SKY", 24000.0, "https://support.binance.us/en/articles/12270478 (Binance.US; Binance.com removed the MKR "
                            "pairs 2025-09-15 and opened SKY 2025-09-17; data ratio 23,997)"),
    # Prereg Addendum 1 (A1.1), ruled before any outcome: §4.1's rebrand/swap rule is general; the frozen list named
    # the cases the inventory had found. Screening every U-B coin whose history ends in a delisting found these; each
    # ratio is confirmed by Binance's announcement (or a report quoting it) and by the data ratio (successor's first
    # open / predecessor's last close, within 2% of the announced ratio; scratch screen of 2026-11-19).
    "BCHABC": ("BCH", 1.0, "https://www.binance.com/en/support/articles/360037219511 (ticker BCHABC -> BCH, "
                           "2019-11-28, 1:1)"),
    "ERD": ("EGLD", 0.001, "https://www.binance.com/en/support/articles/24feffc4fccf446f9c97fe527cf379be (1,000 ERD = "
                           "1 EGLD, 2020-09-03)"),
    "LEND": ("AAVE", 0.01, BA + "aave-lend-token-swap-to-aave-will-be-supported-on-binance-with-various-service-"
                                 "updates-settlements-17595222999545348c8acdd5dc41c00a (100 LEND = 1 AAVE, 2020-10-15)"),
    "STORM": ("STMX", 1.0, BA + "360043990532 (1 STORM = 1 STMX, STMX trading 2020-06-11; data ratio 1.02)"),
    "STRAT": ("STRAX", 1.0, BA + "stratis-strat-token-swap-to-strax-will-be-supported-on-binance-"
                                 "1937b7781c5043efa66c07141be3bdc2 (1:1, 2020-11)"),
    "NPXS": ("PUNDIX", 0.001, "reports quoting Binance's notice (1,000 NPXS = 1 PUNDIX, PUNDIX trading 2021-04-09); "
                              "the ratio is Pundi X's own; data ratio 0.001"),
    "MFT": ("HIFI", 0.01, BA + "binance-will-support-the-mainframe-mft-token-swap-redenomination-rebranding-plan-to-"
                               "hifi-finance-hifi-8d28d328f7b94cf89850fe7e796881d7 (100 MFT = 1 HIFI, 2023-01)"),
    "MC": ("BEAMX", 100.0, "https://www.binance.com/sl/square/post/2023-11-14-binance-completes-merit-circle-mc-token-"
                           "swap-and-rebranding-to-beam-beamx-1758106 (1 MC = 100 BEAMX, 2023-11-14)"),
    "TOMO": ("VIC", 1.0, BA + "0491a610ab2d4ab3af6d15dce961c5ae (ticker TOMO -> VIC, 1:1, 2023-11; data ratio 1.017)"),
    "GAL": ("G", 60.0, "https://blockchain.news/news/binance-support-galxe-token-swap-rebranding-gravity (report "
                       "quoting Binance: 1 GAL = 60 G, G trading 2024-07-19; Binance.US also 1:60)"),
    "KLAY": ("KAIA", 1.0, "https://www.binance.com/en/support/articles/f75f933759ee49d0af1dfbce7e32144c (1 KLAY = 1 "
                          "KAIA, KAIA trading 2024-10-31)"),
    "DAR": ("D", 1.0, "https://support.binance.us/en/articles/10658932 (Binance.US, 1:1) and reports of Binance's "
                      "completion, D trading 2025-01-09; data ratio 1.000"),
    "BNX": ("FORM", 1.0, BA + "2f963977c7274e0583f16f2e26987b61 (1 BNX = 1 FORM, FORM trading 2025-03-19)"),
    "FXS": ("FRAX", 1.0, "reports of Binance's notice (FXS -> FRAX 1:1, FRAX trading 2026-01-15); data ratio 1.000"),
    "OM": ("MANTRA", 4.0, "https://www.binance.com/de/square/post/291310083489746 (Binance notice of 2026-02-13 as "
                          "quoted: 1 OM = 4 MANTRA, MANTRA trading 2026-03-04); data ratio 3.999"),
    "TON": ("GRAM", 1.0, "reports of Binance's notice (TON -> GRAM 1:1, TON pairs removed 2026-06-30, GRAM trading "
                         "2026-07-02 08:00 UTC); data ratio 1.000"),
}
# Ticker reuse: symbol -> [(coin, first day)]: the same Binance pair holds different assets.
REUSE = {"LUNAUSDT": [("LUNA", None), ("LUNA2", "2022-05-31")]}
# Ticker reuse seen only in the other quote assets: base -> first month of the current asset. Binance's SKY/BTC,
# SKY/BNB and SKY/ETH pairs of 2018-05..2021-11 were Skycoin; SKY from 2025-09 is the Sky protocol token (ex-MKR).
# (ref/listing_gaps.csv: the only base with a multi-year gap across quotes that is not a stablecoin.)
REUSE_LISTING = {"SKY": "2025-09"}
UM_OVERRIDE = {"LUNA": ("LUNAUSDT", 1.0), "LUNA2": ("LUNA2USDT", 1.0)}   # classic perp / Terra 2.0 perp
RH_CATALOG = (OUT / "ref" / "currency_pairs.json", ROOT / "analysis_2026" / "stinkbid_ref" /
              "robinhood_pairs_2026-11-18.json")
RH_REUSED = {"LIT": "Binance LITUSDT was Litentry (swapped to HEI 2025-02); Robinhood's LIT is Lighter"}


# ================================================================ small helpers
def _mi(m: str) -> int:
    return int(m[:4]) * 12 + int(m[5:7]) - 1


def _ms(i: int) -> str:
    return f"{i // 12:04d}-{i % 12 + 1:02d}"


def _months(first: str, last: str) -> list[str]:
    return [_ms(i) for i in range(_mi(first), _mi(last) + 1)]


def _ns(s: pd.Series) -> pd.Series:
    return s.astype(NS) if str(s.dtype) != NS else s


def _tmp(path: Path) -> Path:
    return path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")


def _save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    tmp.write_text(json.dumps(obj, indent=1, default=str))
    os.replace(tmp, path)


def _load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        return {} if default is None else default


def _write_parquet(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _tmp(path)
    df.to_parquet(tmp, index=False, compression="zstd")
    os.replace(tmp, path)


def _get_zip(key: str, need_sum: bool = False):
    """(CSV bytes or None, sha256 compared?) for one archive zip; retries; raises on a checksum mismatch that persists."""
    err = None
    for _ in range(3):
        try:
            return bb._get_zip_csv(key, need_sum)
        except Exception as e:                                   # network error or checksum mismatch: retry
            err = e
    raise IOError(f"{key}: {err!r}")


def _pairs() -> pd.DataFrame:
    return fsd._pairs()


def excluded_bases() -> dict[str, str]:
    """Base -> exclusion reason: the inventory's lists (fetch_stinkbid_data.listing) plus PAX/USDP (§4.1)."""
    p = _pairs()
    out = {b: e for b, e in zip(p.base, p.excluded) if e}
    for b in STABLE_EXTRA:
        out.setdefault(b, "stablecoin (PAX/USDP, prereg §4.1)")
    return out


# ================================================================ coins, symbols, lineage
def coin_sym(coin: str) -> tuple[str, str | None, str | None]:
    """(Binance USDT spot symbol, first day or None, last day or None) of a coin; reused tickers are split."""
    for sym, parts in REUSE.items():
        for i, (c, start) in enumerate(parts):
            if c == coin:
                nxt = parts[i + 1][1] if i + 1 < len(parts) else None
                last = str((pd.Timestamp(nxt) - pd.Timedelta("1D")).date()) if nxt else None
                return sym, start, last
    return coin + "USDT", None, None


def sym_coins(sym: str) -> list[str]:
    return [c for c, _ in REUSE[sym]] if sym in REUSE else [sym[:-4]]


def predecessors(coin: str) -> list[str]:
    """Direct and indirect predecessors under the frozen swap list."""
    out, todo = [], [coin]
    while todo:
        c = todo.pop()
        for p, (s, _, _) in SWAPS.items():
            if s == c and p not in out:
                out.append(p); todo.append(p)
    return out


def successor(coin: str):
    """(successor, units per unit) of a listed swap, else None."""
    return SWAPS[coin][:2] if coin in SWAPS else None


def lineage(coin: str) -> str:
    """The coin at the end of its swap chain (MATIC -> POL); the coin itself otherwise."""
    seen = {coin}
    while coin in SWAPS:
        coin = SWAPS[coin][0]
        if coin in seen:
            break
        seen.add(coin)
    return coin


def swaps() -> pd.DataFrame:
    return pd.DataFrame([dict(predecessor=p, successor=s, units=u, source=src) for p, (s, u, src) in SWAPS.items()])


def redenominations() -> pd.DataFrame:
    return pd.DataFrame([dict(coin=c, first_day=d, price_ratio=r, units=1 / r, source=src)
                         for c, (d, r, src) in REDENOM.items()])


# ================================================================ 1. listing ages across quote assets (§5)
def ages(force=False, workers=WORKERS) -> pd.DataFrame:
    """One S3 listing per (base, quote) for every base with a USDT pair: first and last monthly 1d file and the months
    present. Writes ref/ages_quotes.csv and ref/listing_gaps.csv (months missing from the union of quotes)."""
    f = OUT / "ref" / "ages_quotes.csv"
    if f.exists() and not force:
        return pd.read_csv(f, keep_default_na=False)
    t0 = time.time()
    pref, _ = s3_ls("data/spot/monthly/klines/")
    syms = {p.rstrip("/").split("/")[-1] for p in pref}
    bases = sorted(set(_pairs().base))
    jobs = [(b, q, b + q) for b in bases for q in QUOTES if b != q and b + q in syms]

    def one(j):
        b, q, s = j
        _, k = s3_ls(f"data/spot/monthly/klines/{s}/1d/")
        m = sorted(x[-11:-4] for x, _ in k if x.endswith(".zip"))
        return dict(base=b, quote=q, sym=s, first_month=m[0] if m else "", last_month=m[-1] if m else "",
                    n_months=len(m), months=" ".join(m))
    with cf.ThreadPoolExecutor(workers) as ex:
        a = pd.DataFrame(list(ex.map(one, jobs)))
    a.to_csv(f, index=False)
    gaps = []
    for b, g in a.groupby("base"):
        ms = sorted({m for x in g.months for m in x.split()})
        if not ms:
            continue
        have = {_mi(m) for m in ms}
        miss = [i for i in range(_mi(ms[0]), _mi(ms[-1]) + 1) if i not in have]
        if miss:
            runs, start = [], miss[0]
            for x, y in zip(miss, miss[1:] + [None]):
                if y != x + 1:
                    runs.append((start, x)); start = y
            for s0, s1 in runs:
                gaps.append(dict(base=b, gap_first=_ms(s0), gap_last=_ms(s1), months=s1 - s0 + 1,
                                 quotes=" ".join(sorted(g.quote)), first_any=ms[0], last_any=ms[-1]))
    pd.DataFrame(gaps, columns=["base", "gap_first", "gap_last", "months", "quotes", "first_any", "last_any"]).to_csv(
        OUT / "ref" / "listing_gaps.csv", index=False)
    print(f"ages: {len(bases)} bases, {len(jobs)} base x quote listings in {time.time() - t0:.0f}s; "
          f"bases with a month gap across quotes: {len({g['base'] for g in gaps})}", flush=True)
    return a


@functools.lru_cache(maxsize=1)
def first_listing() -> dict[str, str]:
    """coin -> first listing month across USDT, BTC, BNB, ETH, BUSD (the earliest monthly 1d file; the coin's own
    first daily bar where no monthly file exists yet). Reused tickers restart at the reuse month; listed successors
    inherit the earliest month of their predecessors (§4.1, V12)."""
    q = ages()
    q = q[q.first_month != ""]
    first = q.groupby("base").first_month.min().to_dict()
    for b, m0 in REUSE_LISTING.items():                         # an older, different asset under the same ticker
        ms = sorted(m for x in q.months[q.base == b] for m in x.split() if m >= m0)
        if ms:
            first[b] = ms[0]
        else:
            first.pop(b, None)
    pan = d1_panel()
    own = pan.groupby("coin").day.min().dt.strftime("%Y-%m").to_dict()
    for c, m in own.items():
        if c not in first or m < first[c]:
            first[c] = min(first.get(c, m), m)
    return _inherit_listing(first)


def _inherit_listing(first: dict) -> dict:
    """Ticker reuse restarts the listing month (REUSE); listed successors take the earliest month of their
    predecessors (SWAPS, recursively)."""
    first = dict(first)
    for sym, parts in REUSE.items():
        for c, start in parts[1:]:
            first[c] = start[:7]                                # the new asset's age restarts at the reuse month
    out = dict(first)
    for c in list(out):
        for p in predecessors(c):
            if p in first and first[p] < out[c]:
                out[c] = first[p]
    return out


# ================================================================ 2. daily klines from listing (2017-08 for BTC)
def d1_full(force=False, workers=WORKERS):
    """Daily klines from the first monthly file for every USDT pair listed before 2019-10 (the d1_spot/ files start
    at 2019-10); stacked with d1_spot/ into d1_full_all.parquet. Same builder and checks as fetch_stinkbid_data.d1."""
    p = _pairs()
    syms = list(p.sym[(p.first_month != "") & (p.first_month < fsd.WARMUP)])
    dd = OUT / "d1_full"
    t0 = time.time()
    with cf.ThreadPoolExecutor(max(1, workers // 8)) as ex:
        res = list(ex.map(lambda s: fsd._series("spot", s, "1d", END, None, dd / f"{s}.parquet", force, 8), syms))
    stats = _load_json(OUT / "stats" / "d1_full.json")
    stats.update({s: st for s, st in res if st is not None})
    _save_json(OUT / "stats" / "d1_full.json", stats)
    parts = []
    full = {f.stem for f in dd.glob("*.parquet")}
    for f in sorted((OUT / "d1_spot").glob("*.parquet")):
        if f.stem not in full:
            k = pd.read_parquet(f); k.insert(0, "sym", f.stem); parts.append(k)
    for f in sorted(dd.glob("*.parquet")):
        k = pd.read_parquet(f); k.insert(0, "sym", f.stem); parts.append(k)
    a = pd.concat(parts, ignore_index=True)
    a["day"] = a.open_time.dt.tz_convert(None).dt.normalize()
    a = a.sort_values(["sym", "day"]).reset_index(drop=True)
    _write_parquet(a, OUT / "d1_full_all.parquet")
    new = [st for _, st in res if st is not None]
    print(f"d1-2017: {len(syms)} pairs listed before {fsd.WARMUP}; downloaded {len(new)} in {time.time() - t0:.0f}s, "
          f"zips {sum(s['zips'] for s in new)}, verified {sum(s['verified'] for s in new)}, failed "
          f"{sum(len(s['failed']) for s in new)}; panel {len(a):,} rows, {a.sym.nunique()} pairs, "
          f"{a.day.min().date()}..{a.day.max().date()}", flush=True)
    d1_panel.cache_clear()
    return a


@functools.lru_cache(maxsize=1)
def d1_panel() -> pd.DataFrame:
    """Every USDT pair's daily klines from listing (d1_full_all.parquet; d1_spot_all.parquet before d1-2017 ran), with
    `coin` (reused tickers split), `excluded` (list reason or ''), `seg` (segment id within the coin) and `day`
    (tz-naive UTC date). Sorted by coin and day."""
    f = OUT / "d1_full_all.parquet"
    a = pd.read_parquet(f if f.exists() else OUT / "d1_spot_all.parquet")
    a["open_time"] = _ns(a.open_time)
    a["day"] = a.open_time.dt.tz_convert(None).dt.normalize().astype("datetime64[ns]")
    a["coin"] = a.sym.str[:-4]
    for sym, parts in REUSE.items():
        m = a.sym == sym
        for c, start in parts:
            if start:
                a.loc[m & (a.day >= pd.Timestamp(start)), "coin"] = c
            else:
                a.loc[m, "coin"] = c
    exc = excluded_bases()
    a["excluded"] = a.sym.str[:-4].map(exc).fillna("")
    a = a.sort_values(["coin", "day"]).reset_index(drop=True)
    a["seg"] = _seg_ids(a)
    return a


def _seg_ids(a: pd.DataFrame) -> np.ndarray:
    """Segment id within each coin (§4.1): a new segment after a missing UTC day or at a >25% open jump. Zero-trade
    daily bars count as missing days (they carry no trading). Rows must be sorted by coin and day."""
    live = a.trades.to_numpy() > 0
    b = a[live]
    coin = b.coin.to_numpy()
    day = b.day.to_numpy().astype("datetime64[D]").astype(np.int64)
    op, cl = b.open.to_numpy(float), b.close.to_numpy(float)
    new = np.r_[True, coin[1:] != coin[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        brk = np.r_[False, (day[1:] - day[:-1] > 1) | (np.abs(op[1:] / cl[:-1] - 1) > JUMP)] & ~new
    cs = np.cumsum(brk)
    start = np.maximum.accumulate(np.where(new, np.arange(len(b)), 0))
    seg = np.full(len(a), -1, np.int32)
    seg[np.nonzero(live)[0]] = (cs - cs[start]).astype(np.int32)
    return seg


def d1(coin: str) -> pd.DataFrame:
    """Daily spot klines of a coin (from listing; 2017-08 for BTC) with `seg`."""
    a = d1_panel()
    k = a[(a.coin == coin) & (a.seg >= 0)]
    return k[KCOLS + ["seg"]].reset_index(drop=True)


# ================================================================ 3. segments, joins, delisting values (§4.1)
def _hour_bounds(coin: str) -> pd.DataFrame | None:
    """Per UTC day with trading: the first and last hour with a traded bar and the open of the last traded bar (t_last,
    tz-naive UTC, at the resolution t_res of the source), from the cached 1m bars, else the hourly files. Only bars
    with trades > 0 count: zero-trade placeholder bars (OHLC = prior close) are not trading (§4.1)."""
    sym, lo, hi = coin_sym(coin)
    f1 = OUT / "m1_spot" / f"{sym}.parquet"
    fh = OUT / "h1_spot" / f"{sym}.parquet"
    src = f1 if f1.exists() else fh if fh.exists() else None
    if src is None:
        return None
    k = pd.read_parquet(src, columns=["open_time", "trades"])
    pre = OUT / "h1_spot_pre" / f"{sym}.parquet"
    if src == fh and pre.exists():
        k = pd.concat([pd.read_parquet(pre, columns=["open_time", "trades"]), k], ignore_index=True)
    return _bounds_from(k, lo, hi, "1m" if src == f1 else "1h")


def _bounds_from(k: pd.DataFrame, lo=None, hi=None, source: str = "1m") -> pd.DataFrame:
    """_hour_bounds' table from bars with open_time and trades (days restricted to [lo, hi] when given)."""
    k = k[k.trades.to_numpy() > 0]
    t = _ns(k.open_time).reset_index(drop=True)
    day = t.dt.tz_convert(None).dt.normalize()
    keep = np.ones(len(t), bool)
    if lo:
        keep &= (day >= pd.Timestamp(lo)).to_numpy()
    if hi:
        keep &= (day <= pd.Timestamp(hi)).to_numpy()
    t, day = t[keep], day[keep]
    g = pd.DataFrame({"day": day.to_numpy(), "h": t.dt.hour.to_numpy(),
                      "t": t.dt.tz_convert(None).to_numpy()}).groupby("day")
    out = g.agg(h_first=("h", "min"), h_last=("h", "max"), t_last=("t", "max"))
    out["source"] = source
    out["t_res"] = source
    return out


_LM_LOCK = threading.Lock()


def _last_traded_minute(sym: str, day) -> pd.Timestamp | None:
    """The open (UTC) of the last 1m bar with trades > 0 on one UTC day, from the archive's daily 1m zip, else the
    monthly one (checksums required). None when neither zip has a traded minute that day, or the archive cannot be
    reached (then nothing is cached and a later call retries). Cached in ref/last_minute.json by 'SYM|YYYY-MM-DD'."""
    d = pd.Timestamp(day)
    d = (d.tz_convert(None) if d.tzinfo else d).normalize()
    ds = f"{d:%Y-%m-%d}"
    f, ck = OUT / "ref" / "last_minute.json", f"{sym}|{ds}"
    with _LM_LOCK:
        hit = _load_json(f).get(ck)
    if hit is not None:
        return pd.Timestamp(hit["t"]) if hit["t"] else None
    rec, err = None, None
    for z in (f"data/spot/daily/klines/{sym}/1m/{sym}-1m-{ds}.zip",
              f"data/spot/monthly/klines/{sym}/1m/{sym}-1m-{ds[:7]}.zip"):
        try:
            b, ok = _get_zip(z, True)
        except IOError as e:                                       # unreachable or checksum failure: try the next
            err = repr(e)
            continue
        if b is None:
            continue
        k = bb._parse_klines(b)
        t = pd.to_datetime(bb._to_utc_ms(k.open_time), unit="ms", utc=True)
        live = (k.trades.to_numpy() > 0) & (t.dt.tz_convert(None).dt.normalize() == d).to_numpy()
        rec = {"t": str(t[live].max()) if live.any() else None, "zip": z, "verified": bool(ok)}
        if live.any():
            break
    if err is not None and (rec is None or rec["t"] is None):         # unresolved after an error: retry later
        return None
    rec = rec or {"t": None, "zip": None, "verified": False}
    with _LM_LOCK:
        c = _load_json(f)
        c[ck] = rec
        _save_json(f, c)
    return pd.Timestamp(rec["t"]) if rec["t"] else None


def _refine_last(coin: str, k: pd.DataFrame, hb: pd.DataFrame | None, fetch=None, end: str = END):
    """Minute resolution for the last day of every segment that ends before `end` when hb comes from hourly bars:
    t_last = the open of that day's last 1m bar with trades > 0 (fetch(day), default _last_traded_minute), kept only
    when it lies inside the last traded hour of the hourly bars. Days it cannot resolve keep the hour (t_res '1h')."""
    if hb is None or k.empty or not (hb.t_res == "1h").any():
        return hb
    fetch = fetch or functools.partial(_last_traded_minute, coin_sym(coin)[0])
    day = k.open_time.dt.tz_convert(None).dt.normalize()
    last = day.groupby(k.seg.to_numpy()).max()
    hb = hb.copy()
    for d in sorted(set(last[last < pd.Timestamp(end)])):
        if d not in hb.index or hb.at[d, "t_res"] != "1h":
            continue
        t = fetch(d)
        if t is None:
            continue
        t = (t.tz_convert(None) if t.tzinfo else t)
        h0 = pd.Timestamp(hb.at[d, "t_last"])
        if h0 <= t < h0 + pd.Timedelta("1h"):
            hb.at[d, "t_last"] = t
            hb.at[d, "t_res"] = "1m"
    return hb


@functools.lru_cache(maxsize=4096)
def segments(coin: str) -> pd.DataFrame:
    """One row per segment of a coin's spot series (§4.1); see _segments_from for the columns."""
    succ = d1(SWAPS[coin][0]) if coin in SWAPS else None
    k = d1(coin)
    return _segments_from(k, coin, _refine_last(coin, k, _hour_bounds(coin)), succ)


def _segments_from(k: pd.DataFrame, coin: str, hb: pd.DataFrame | None = None,
                   succ: pd.DataFrame | None = None, end: str = END) -> pd.DataFrame:
    """One row per segment of a coin's spot series (§4.1): seg, first_day, last_day, days, first_open, last_close,
    end (last day + 1 day, UTC: no bar of this segment opens at or after it), kind, continues (a position open at the
    end continues: joined redenomination, swap, jump, or data end), units (new units per old unit when it continues), successor, next_first_day, next_open, data_ratio (next
    open / last close; for swaps the predecessor's last close / the successor's price at the same time), band_dev,
    source (announcement), and the delisting values used when continues is False: last_full_day (the last day with
    trading, i.e. a bar with trades > 0, in hours 00 and 23), vwap_last_full_day (quote volume / volume of that day),
    last_trade (close of the last daily bar: the last trade's price), last_trade_time (open of the last bar with
    trades > 0) and last_trade_res: '1m' = that bar is a minute, the minute of the last trade (every segment ending
    before END: cached 1m bars, else the last day's 1m archive zip); '1h' = an hour bar (only data_end segments of
    coins without cached 1m bars, or a day the archive could not resolve).
    kind: data_end (trades through END: censored, not a delisting) | delisting | gap (trading resumed after missing
    days: relisting, a delisting at the gap) | redenomination (joined) | redenomination_unconfirmed (inside the band,
    no announcement: delisting) | redenomination_outside_band (announced, ratio outside +-5%: delisting) | swap
    (continues in the successor) | jump (>25% open jump without a missing day: bids cancelled, positions continue)."""
    if k.empty:
        return pd.DataFrame()
    end_day = pd.Timestamp(end)
    day = k.open_time.dt.tz_convert(None).dt.normalize()
    rows = []
    for s, g in k.groupby("seg", sort=True):
        gd = day[g.index]
        r = dict(coin=coin, seg=int(s), first_day=gd.iloc[0], last_day=gd.iloc[-1], days=len(g),
                 first_open=float(g.open.iloc[0]), last_close=float(g.close.iloc[-1]),
                 end=(gd.iloc[-1] + pd.Timedelta("1D")).tz_localize("UTC"), kind="", continues=False, units=np.nan,
                 successor="", next_first_day=pd.NaT, next_open=np.nan, data_ratio=np.nan, band_dev=np.nan,
                 source="")
        nxt = k[k.seg == s + 1]
        if len(nxt):
            nd = day[nxt.index[0]]
            ratio = float(nxt.open.iloc[0]) / r["last_close"]
            n = int(np.round(np.log10(ratio))) if ratio > 0 else 0
            dev = ratio / 10.0 ** n - 1
            r.update(next_first_day=nd, next_open=float(nxt.open.iloc[0]), data_ratio=ratio, band_dev=dev)
            gap = (nd - r["last_day"]).days > 1
            rd = REDENOM.get(coin)
            if rd and abs((nd - pd.Timestamp(rd[0])).days) <= 3:
                inside = abs(ratio / rd[1] - 1) <= BAND
                r.update(kind="redenomination" if inside else "redenomination_outside_band", continues=inside,
                         units=1 / rd[1] if inside else np.nan, band_dev=ratio / rd[1] - 1, source=rd[2])
            elif n != 0 and abs(dev) <= BAND:
                r.update(kind="redenomination_unconfirmed")
            elif not gap:
                r.update(kind="jump", continues=True, units=1.0)
            else:
                r.update(kind="gap")
        elif r["last_day"] >= end_day:
            r.update(kind="data_end", continues=True, units=1.0)
        elif coin in SWAPS:
            succ_coin, units, src = SWAPS[coin]
            r.update(kind="swap", continues=True, units=units, successor=succ_coin, source=src)
            sk = succ if succ is not None else pd.DataFrame()
            if len(sk):
                sd = sk.open_time.dt.tz_convert(None).dt.normalize()
                after, same = sk[sd > r["last_day"]], sk[sd == r["last_day"]]
                ref = (float(same.close.iloc[0]) if len(same) else
                       float(after.open.iloc[0]) if len(after) else np.nan)
                r.update(next_first_day=sd[after.index[0]] if len(after) else pd.NaT,
                         next_open=float(after.open.iloc[0]) if len(after) else np.nan,
                         data_ratio=r["last_close"] / ref if ref == ref else np.nan,
                         band_dev=(r["last_close"] / ref) / units - 1 if ref == ref else np.nan)
        else:
            r.update(kind="delisting")
        # delisting values (used when the position does not continue): VWAP of the last full trading day (trading,
        # i.e. a bar with trades > 0, in its first and last hour) and the last trade
        full_day, src = None, "fallback: second-to-last day"
        if hb is not None:
            h = hb[(hb.index >= r["first_day"]) & (hb.index <= r["last_day"])]
            fd = h[(h.h_first == 0) & (h.h_last == 23)]
            if len(fd):
                full_day, src = fd.index[-1], h.source.iloc[0]
            if len(h):
                r["last_trade_time"] = pd.Timestamp(h.t_last.iloc[-1]).tz_localize("UTC")
                r["last_trade_res"] = h.t_res.iloc[-1] if "t_res" in h else h.source.iloc[-1]
        if full_day is None:
            full_day = gd.iloc[-2] if len(gd) >= 2 else gd.iloc[-1]
        row = g[(gd == full_day).to_numpy()]
        vol = float(row.volume.iloc[0]) if len(row) else np.nan
        r.update(last_full_day=full_day, full_day_source=src,
                 vwap_last_full_day=float(row.quote_volume.iloc[0]) / vol if len(row) and vol > 0 else np.nan,
                 last_trade=r["last_close"])
        rows.append(r)
    out = pd.DataFrame(rows)
    out["end"] = pd.to_datetime(out["end"], utc=True).astype(NS)
    if "last_trade_time" in out:
        out["last_trade_time"] = pd.to_datetime(out["last_trade_time"], utc=True).astype(NS)
    return out


def delist_value(coin: str, t=None, haircut: float = HAIRCUT) -> dict:
    """§4.1 value of one unit of a position open when its segment ends and does not continue (delisting,
    gap/relisting, unconfirmed or out-of-band redenomination): VWAP of the last full trading day x (1 - haircut) is the primary; the last trade x
    (1 - haircut) and the 0% / 100% haircuts are sensitivities. t selects the segment (any time inside it; default:
    the last segment)."""
    return _delist_row(segments(coin), coin, t, haircut)


def _delist_row(s: pd.DataFrame, coin: str, t=None, haircut: float = HAIRCUT) -> dict:
    if t is None:
        r = s.iloc[-1]
    else:
        t = pd.Timestamp(t)
        d = (t.tz_convert(None) if t.tzinfo else t).normalize()
        hit = s[(s.first_day <= d) & (s.last_day >= d)]
        if hit.empty:
            raise ValueError(f"{coin}: {t} is not inside a segment")
        r = hit.iloc[0]
    v, lt = float(r.vwap_last_full_day), float(r.last_trade)
    return dict(coin=coin, seg=int(r.seg), kind=r.kind, continues=bool(r["continues"]), end=r.end,
                last_full_day=r.last_full_day, vwap=v, last_trade=lt, value=v * (1 - haircut),
                value_last_trade=lt * (1 - haircut), value_haircut0=v, value_haircut100=0.0)


# ================================================================ 4. monthly ranks, stablecoin backstop, universes (§5)
@functools.lru_cache(maxsize=4)
def ranks(first: str = RANK_FIRST, last: str = UNIV_LAST) -> pd.DataFrame:
    """Every coin-month passing the U-B volume eligibility (>= 30 traded days of the 90 before M and traded on the
    last day before M), with adv90 (median USDT volume over the traded days), sd90 (stablecoin backstop), backstop
    (True = excluded), and rank among the coins that are neither list-excluded nor backstop-excluded."""
    return _ranks(d1_panel(), first, last)


def _ranks(a: pd.DataFrame, first: str, last: str) -> pd.DataFrame:
    a = a[(a.excluded == "") & (a.seg >= 0)]
    if a.empty:
        return pd.DataFrame(columns=["month", "coin", "sym", "adv90", "days_traded90", "sd90", "backstop", "rank"])
    coins = sorted(a.coin.unique())
    days = pd.date_range(a.day.min(), max(a.day.max(), pd.Timestamp(_months(last, last)[0] + "-01")), freq="D")
    ix = {c: i for i, c in enumerate(coins)}
    di = ((a.day - days[0]).dt.days).to_numpy()
    ci = a.coin.map(ix).to_numpy()
    shape = (len(days), len(coins))
    qv = np.full(shape, np.nan); qv[di, ci] = a.quote_volume.to_numpy(float)
    tr = np.zeros(shape, bool); tr[di, ci] = a.trades.to_numpy() > 0
    cl = np.full(shape, np.nan); cl[di, ci] = a.close.to_numpy(float)
    sg = np.full(shape, -1, np.int64); sg[di, ci] = a.seg.to_numpy()
    ret = np.full(shape, np.nan)
    ok = tr[1:] & tr[:-1] & (sg[1:] == sg[:-1]) & (sg[1:] >= 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = np.where(ok, np.log(cl[1:] / cl[:-1]), np.nan)
    qv = np.where(tr, qv, np.nan)
    sym = a.drop_duplicates("coin").set_index("coin").sym
    rows = []
    for m in _months(first, last):
        t1 = (pd.Timestamp(m + "-01") - pd.Timedelta("1D") - days[0]).days
        if t1 < 0:
            continue
        lo = max(0, t1 - WINDOW + 1)
        n = tr[lo:t1 + 1].sum(0)
        okm = (n >= MIN_DAYS) & tr[t1]
        if not okm.any():
            continue
        idx = np.nonzero(okm)[0]
        with np.errstate(all="ignore"):
            adv = np.nanmedian(qv[lo:t1 + 1, idx], axis=0)
            r = ret[lo:t1 + 1, idx]
            nr = np.isfinite(r).sum(0)
            sd = np.where(nr >= 2, np.nanstd(r, axis=0, ddof=1), np.nan)
        back = sd < SD_MIN                                     # NaN compares False: not excluded
        df = pd.DataFrame({"month": m, "coin": [coins[i] for i in idx], "adv90": adv, "days_traded90": n[idx],
                           "sd90": sd, "backstop": back})
        el = df[~df.backstop].sort_values(["adv90", "coin"], ascending=[False, True])
        df["rank"] = np.nan
        df.loc[el.index, "rank"] = np.arange(1, len(el) + 1, dtype=float)
        rows.append(df)
    out = pd.concat(rows, ignore_index=True)
    out["sym"] = out.coin.map(sym)
    return out[["month", "coin", "sym", "adv90", "days_traded90", "sd90", "backstop", "rank"]]


def backstop(first: str = RANK_FIRST, last: str = UNIV_LAST) -> pd.DataFrame:
    """The §4.1 stablecoin backstop for every non-list-excluded coin with >= 2 returns in the 90 days before M:
    month, coin, sd90, n_returns, excluded (sd90 < 0.5%). With d1_panel().excluded it gives U-B's exclusions for any
    pair (M3's pooled calibration)."""
    a = d1_panel()
    a = a[(a.excluded == "") & (a.seg >= 0)]
    coins = sorted(a.coin.unique())
    days = pd.date_range(a.day.min(), a.day.max(), freq="D")
    ix = {c: i for i, c in enumerate(coins)}
    di, ci = (a.day - days[0]).dt.days.to_numpy(), a.coin.map(ix).to_numpy()
    shape = (len(days), len(coins))
    cl = np.full(shape, np.nan); cl[di, ci] = a.close.to_numpy(float)
    tr = np.zeros(shape, bool); tr[di, ci] = a.trades.to_numpy() > 0
    sg = np.full(shape, -1, np.int64); sg[di, ci] = a.seg.to_numpy()
    ret = np.full(shape, np.nan)
    ok = tr[1:] & tr[:-1] & (sg[1:] == sg[:-1]) & (sg[1:] >= 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = np.where(ok, np.log(cl[1:] / cl[:-1]), np.nan)
    rows = []
    for m in _months(first, last):
        t1 = (pd.Timestamp(m + "-01") - pd.Timedelta("1D") - days[0]).days
        if t1 < 1:
            continue
        r = ret[max(0, t1 - WINDOW + 1):t1 + 1]
        nr = np.isfinite(r).sum(0)
        idx = np.nonzero(nr >= 2)[0]
        with np.errstate(all="ignore"):
            sd = np.nanstd(r[:, idx], axis=0, ddof=1)
        rows.append(pd.DataFrame({"month": m, "coin": [coins[i] for i in idx], "sd90": sd, "n_returns": nr[idx],
                                  "excluded": sd < SD_MIN}))
    return pd.concat(rows, ignore_index=True)


def u_c_coins() -> list[str]:
    """U-C: tradable catalog bases (2026-11-18) with a Binance USDT spot pair of the same asset, not excluded."""
    rh = rh_pairs()
    p = _pairs().set_index("base")
    exc = excluded_bases()
    out = []
    for b in rh.coin[rh.tradable]:
        if b in p.index and b not in exc and b not in RH_REUSED:
            out.append(b)
    return sorted(out)


def universes(first: str = UNIV_FIRST, last: str = UNIV_LAST) -> pd.DataFrame:
    """Point-in-time universes (§5): one row per coin ranked in month M (U-B eligibility after exclusions)."""
    f = OUT / "ref" / "universes.parquet"
    if f.exists() and first == UNIV_FIRST and last == UNIV_LAST:
        u = pd.read_parquet(f)
        return u
    return _universes(ranks(), first, last, first_listing(), u_c_coins())


def _universes(rk: pd.DataFrame, first: str, last: str, listing: dict, ucoins) -> pd.DataFrame:
    r = rk[rk["rank"].notna()]
    allm = _months(min(r.month.min(), first), last)
    piv = r.pivot(index="month", columns="coin", values="rank").reindex(allm)
    hist = piv.copy()
    for c in hist.columns:
        preds = [p for p in predecessors(c) if p in piv.columns]
        if preds:
            inh = piv[preds].min(axis=1)
            hist[c] = hist[c].where(hist[c].notna(), inh)
    med12 = hist.fillna(UNRANKED).rolling(12, min_periods=12).median()
    out = r[(r.month >= first) & (r.month <= last)].copy()
    out["rank_med12"] = [med12.at[m, c] for m, c in zip(out.month, out.coin)]
    out["listing_age_months"] = [(_mi(m) - _mi(listing[c])) if c in listing else -1 for m, c in zip(out.month, out.coin)]
    out["U_B"] = out["rank"] <= TOP_N
    out["U_Q1"] = out.U_B & (out.listing_age_months >= Q1_AGE) & (out.rank_med12 <= Q1_RANK)
    out["U_Q1_12"] = out.U_B & (out.listing_age_months >= Q1_12_AGE) & (out.rank_med12 <= Q1_RANK)
    out["U_Q1_xm"] = out.U_Q1 & ~out.coin.isin(MEMES)
    out["U_A"] = out.U_B & out.coin.isin(U_A_COINS)
    out["U_C"] = out.U_B & out.coin.isin(list(ucoins))
    out["lineage"] = out.coin.map(lineage)
    cols = ["month", "coin", "sym", "U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_C", "U_A", "rank", "rank_med12",
            "listing_age_months", "adv90", "days_traded90", "sd90", "lineage"]
    return out[cols].sort_values(["month", "rank"]).reset_index(drop=True)


def build_universes():
    t0 = time.time()
    rk = ranks()
    _write_parquet(rk, OUT / "ref" / "ranks.parquet")
    u = _universes(rk, UNIV_FIRST, UNIV_LAST, first_listing(), u_c_coins())
    _write_parquet(u, OUT / "ref" / "universes.parquet")
    u.to_csv(OUT / "ref" / "universes.csv", index=False)
    build_segments(u)
    n = u.groupby("month")[["U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_A", "U_C"]].sum()
    print(f"universes: {u.month.nunique()} months {u.month.min()}..{u.month.max()} in {time.time() - t0:.0f}s; "
          f"coins ever: " + ", ".join(f"{c} {u.coin[u[c]].nunique()}" for c in
                                      ("U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_A", "U_C")), flush=True)
    print("  per month (min / median / max): " + "; ".join(
        f"{c} {int(n[c].min())}/{int(n[c].median())}/{int(n[c].max())}" for c in n.columns), flush=True)
    bs = rk[rk.backstop]
    print(f"  stablecoin backstop exclusions: {bs.coin.nunique()} coins, {len(bs)} coin-months: "
          f"{' '.join(sorted(bs.coin.unique()))}", flush=True)
    return u


def build_segments(u: pd.DataFrame | None = None, workers: int = 8) -> pd.DataFrame:
    """ref/segments.csv: every segment of the U-B and cached-1m coins. For segment ends before END of coins with only
    hourly bars, the last day's 1m archive zip gives the minute of the last trade (cached in ref/last_minute.json)."""
    t0 = time.time()
    u = universes() if u is None else u
    coins = sorted(set(u.coin[u.U_B]) | set(_m1_coins(u)))
    d1_panel()
    with cf.ThreadPoolExecutor(workers) as ex:
        seg = pd.concat(list(ex.map(segments, coins)), ignore_index=True)
    seg.to_csv(OUT / "ref" / "segments.csv", index=False)
    b = seg[seg.kind != "data_end"]
    print(f"segments: {len(coins)} coins, {len(seg)} segments in {time.time() - t0:.0f}s; {len(b)} end before {END} "
          f"({b.kind.value_counts().to_dict()}); last_trade_time resolution there "
          f"{b.last_trade_res.value_counts(dropna=False).to_dict()}; last full day from "
          f"{b.full_day_source.value_counts(dropna=False).to_dict()}", flush=True)
    return seg


# ================================================================ 5. spot bars with segment ids
def _with_seg(k: pd.DataFrame, coin: str) -> pd.DataFrame:
    """Restrict bars to the coin's days and attach the daily segment id by UTC day (-1: a day without a daily bar)."""
    sym, lo, hi = coin_sym(coin)
    k = k.copy()
    k["open_time"] = _ns(k.open_time)
    day = k.open_time.dt.tz_convert(None).dt.normalize()
    keep = np.ones(len(k), bool)
    if lo:
        keep &= (day >= pd.Timestamp(lo)).to_numpy()
    if hi:
        keep &= (day <= pd.Timestamp(hi)).to_numpy()
    k, day = k[keep], day[keep]
    dk = d1(coin)
    dd = dk.open_time.dt.tz_convert(None).dt.normalize()
    m = pd.Series(dk.seg.to_numpy(), index=dd.to_numpy())
    k["seg"] = day.map(m).fillna(-1).astype(np.int32).to_numpy()
    return k.reset_index(drop=True)


def h1(coin: str) -> pd.DataFrame:
    """Hourly spot klines (2019-10 warm-up + h1_spot 2020-01..END) with `seg`."""
    sym = coin_sym(coin)[0]
    parts = [pd.read_parquet(f) for f in (OUT / "h1_spot_pre" / f"{sym}.parquet", OUT / "h1_spot" / f"{sym}.parquet")
             if f.exists()]
    if not parts:
        raise FileNotFoundError(f"no hourly file for {coin} ({sym})")
    k = pd.concat(parts, ignore_index=True)
    k["open_time"] = _ns(k.open_time)
    k = k.sort_values("open_time", kind="stable").drop_duplicates("open_time", keep="last")
    return _with_seg(k, coin)


def _m1_build(sym: str, inner: int = 16):
    """1m spot klines 2019-12..END from the archive (checksums, holes from daily zips, every day checked against the
    1d kline); prices float64, volumes float32, trades int32. Returns (frame or None, stats)."""
    t0 = time.time()
    dk = d1_panel()
    ref = dk[dk.sym == sym].set_index("open_time")[["open", "high", "low", "close"]]
    k, st = bb.klines("spot", sym, "1m", END, start_month=M1_FROM, workers=inner, ref=ref if len(ref) else None)
    if k is None:
        st["seconds"] = time.time() - t0
        return None, st
    for c in ("volume", "quote_volume", "taker_buy_quote"):
        k[c] = k[c].astype("float32")
    k["trades"] = k.trades.astype("int32")
    k["open_time"] = _ns(k.open_time)
    st["seconds"] = time.time() - t0
    return k[KCOLS].reset_index(drop=True), st


def m1_fetch(sym: str, force: bool = False, inner: int = 16):
    f = OUT / "m1_spot" / f"{sym}.parquet"
    if f.exists() and not force:
        return sym, None
    k, st = _m1_build(sym, inner)
    if k is not None:
        _write_parquet(k, f)
        st["bytes"] = f.stat().st_size
    return sym, st


def m1(coin: str, start=None, end=None, fetch: bool = True) -> pd.DataFrame:
    """1-minute spot klines of a coin with `seg`, from the per-symbol cache (built on first use when fetch=True)."""
    sym = coin_sym(coin)[0]
    f = OUT / "m1_spot" / f"{sym}.parquet"
    if not f.exists():
        if not fetch:
            raise FileNotFoundError(f)
        _, st = m1_fetch(sym)
        if st is not None:
            s = _load_json(OUT / "stats" / "m1.json"); s[sym] = st; _save_json(OUT / "stats" / "m1.json", s)
    filt = []
    if start is not None:
        filt.append(("open_time", ">=", pd.Timestamp(start, tz="UTC") if pd.Timestamp(start).tzinfo is None
                     else pd.Timestamp(start)))
    if end is not None:
        filt.append(("open_time", "<", pd.Timestamp(end, tz="UTC") if pd.Timestamp(end).tzinfo is None
                     else pd.Timestamp(end)))
    k = pd.read_parquet(f, filters=filt or None)
    return _with_seg(k, coin)


def m1_stream(coin: str, inner: int = 16) -> pd.DataFrame:
    """The same frame as m1(), built from the archive without keeping a file (U-B streaming); cached files are read."""
    sym = coin_sym(coin)[0]
    if (OUT / "m1_spot" / f"{sym}.parquet").exists():
        return m1(coin)
    k, st = _m1_build(sym, inner)
    if k is None:
        raise FileNotFoundError(f"no 1m klines for {coin}: {st.get('failed')}")
    k = _with_seg(k, coin)
    k.attrs["stats"] = st
    return k


def _m1_coins(u: pd.DataFrame | None = None) -> list[str]:
    """Coins whose 1m bars are cached: ever in U-Q1, U-Q1-12, U-A or U-C, every U-A / U-C list coin with a Binance
    spot pair (the sheet), and the successors of all of them (positions continue through swaps)."""
    u = universes() if u is None else u
    c = set(u.coin[u.U_Q1 | u.U_Q1_12 | u.U_A | u.U_C])
    p = set(_pairs().base)
    c |= {x for x in U_A_COINS if x in p} | set(u_c_coins())
    todo = list(c)
    while todo:
        x = todo.pop()
        if x in SWAPS and SWAPS[x][0] not in c:
            c.add(SWAPS[x][0]); todo.append(SWAPS[x][0])
    return sorted(c)


def m1_bulk(coins=None, force=False, procs=4, inner=16):
    """Build the cached 1m files (largest first) in `procs` processes; stats/m1.json gets per-symbol counts."""
    coins = coins or _m1_coins()
    syms = sorted({coin_sym(c)[0] for c in coins})
    todo = [s for s in syms if force or not (OUT / "m1_spot" / f"{s}.parquet").exists()]
    size = pd.read_parquet(OUT / "coverage" / "daily_sizes.parquet") if (OUT / "coverage" /
                                                                       "daily_sizes.parquet").exists() else None
    if size is not None:
        b = size[size.kind == "1m"].groupby("sym").bytes.sum()
        todo.sort(key=lambda s: -b.get(s, 0))
    t0 = time.time()
    print(f"m1: {len(syms)} symbols for {len(coins)} coins; to build {len(todo)}", flush=True)
    stats = _load_json(OUT / "stats" / "m1.json")
    done = 0
    with cf.ProcessPoolExecutor(procs) as ex:
        futs = {ex.submit(m1_fetch, s, force, inner): s for s in todo}
        for fu in cf.as_completed(futs):
            s = futs[fu]
            try:
                _, st = fu.result()
            except Exception as e:                               # recorded, the bulk run goes on
                st = {"error": repr(e)}
            if st is not None:
                stats[s] = st
                _save_json(OUT / "stats" / "m1.json", stats)
            done += 1
            print(f"  m1 {done}/{len(todo)} {s}: rows {st.get('rows', 0):,} zips {st.get('zips', 0)} verified "
                  f"{st.get('verified', 0)} failed {len(st.get('failed', []))} holes+{st.get('hole_bars_filled', 0)} "
                  f"repaired {len(st.get('ref_days_repaired', []))} unresolved {len(st.get('ref_days_unresolved', []))} "
                  f"{st.get('bytes', 0) / 2 ** 20:.0f} MB {st.get('seconds', 0):.0f}s "
                  f"[{time.time() - t0:.0f}s]{' ERROR ' + st['error'] if 'error' in st else ''}", flush=True)
    tot = sum((OUT / "m1_spot" / f"{s}.parquet").stat().st_size for s in syms
              if (OUT / "m1_spot" / f"{s}.parquet").exists())
    print(f"m1: done in {time.time() - t0:.0f}s; cache {tot / 2 ** 30:.2f} GB for {len(syms)} symbols", flush=True)


def h1_pre(force=False, workers=WORKERS):
    """Hourly klines 2019-10..2019-12 for the hourly candidates listed before 2020 (M6 needs 90 days of 1h bars)."""
    d = OUT / "h1_spot_pre"
    a = d1_panel()
    first = a.groupby("sym").day.min()
    syms = [f.stem for f in sorted((OUT / "h1_spot").glob("*.parquet")) if first.get(f.stem, pd.Timestamp(END)) <
            pd.Timestamp("2020-01-01")]
    t0 = time.time()

    def one(s):
        f = d / f"{s}.parquet"
        if f.exists() and not force:
            return s, None
        ref = a[a.sym == s].set_index("open_time")[["open", "high", "low", "close"]]
        k, st = bb.klines("spot", s, "1h", H1_PRE[1], start_month=H1_PRE[0], workers=8, ref=ref)
        if k is not None:
            k = k[k.open_time < pd.Timestamp(H1_PRE[1], tz="UTC")]
            _write_parquet(k, f)
        return s, st
    with cf.ThreadPoolExecutor(max(1, workers // 8)) as ex:
        res = list(ex.map(one, syms))
    stats = _load_json(OUT / "stats" / "h1_pre.json")
    stats.update({s: st for s, st in res if st is not None})
    _save_json(OUT / "stats" / "h1_pre.json", stats)
    new = [st for _, st in res if st is not None]
    print(f"h1pre: {len(syms)} symbols, built {len(new)} in {time.time() - t0:.0f}s; zips "
          f"{sum(s['zips'] for s in new)}, verified {sum(s['verified'] for s in new)}, failed "
          f"{sum(len(s['failed']) for s in new)}", flush=True)


# ================================================================ 6. USD-M futures (§4, §7 F3/F5, V4; M7)
@functools.lru_cache(maxsize=1)
def _um_map() -> dict:
    m = fsd.um_contracts()
    names = set(pd.read_csv(OUT / "ref" / "um_contracts.csv").contract)
    for n in names:                                   # a spot coin named like the contract (1000SATS, 1000CAT): 1:1
        if n.endswith("USDT") and "_" not in n and n[:1].isdigit():
            m[n[:-4]] = (n, 1.0)
    m.update(UM_OVERRIDE)
    return m


def um_contract(coin: str):
    """(USDT-margined perpetual, units of the coin per contract price unit) or None."""
    return _um_map().get(coin)


_LS_LOCK = threading.Lock()
_LS: dict[str, set] = {}


def _daily_keys(prefix: str) -> set:
    """Daily zip keys under a prefix, listed once per process."""
    with _LS_LOCK:
        if prefix in _LS:
            return _LS[prefix]
    keys = {k for k, _ in s3_ls(prefix, delimiter="")[1] if k.endswith(".zip")}
    with _LS_LOCK:
        _LS[prefix] = keys
    return keys


_FUT = {"index": ("indexPriceKlines", ["open_time", "open", "high", "low", "close", "updates"]),
        "perp": ("klines", KCOLS)}


def _fut_parse(b: bytes, kind: str, mult: float) -> pd.DataFrame:
    k = bb._parse_klines(b)
    k["open_time"] = pd.to_datetime(bb._to_utc_ms(k.open_time), unit="ms", utc=True).astype(NS)
    for c in ("open", "high", "low", "close"):
        k[c] = k[c].astype("float64") / mult
    if kind == "index":
        k = k.rename(columns={"trades": "updates"})
        k["updates"] = k.updates.astype("int32")
        return k[_FUT["index"][1]]
    k["volume"] = (k.volume.astype("float64") * mult).astype("float32")
    for c in ("quote_volume", "taker_buy_quote"):
        k[c] = k[c].astype("float32")
    k["trades"] = k.trades.astype("int32")
    return k[KCOLS]


def _fut_path(kind: str, coin: str, month: str) -> Path:
    return OUT / "fut1m" / kind / coin / f"{month}.parquet"


def _fut_month(kind: str, coin: str, month: str, force: bool = False) -> dict:
    """Build one coin-month of 1m index (kind='index') or last-price (kind='perp') klines: the monthly zip, then the
    daily zip of every day the monthly zip lacks. Writes the parquet and a JSON day status; returns the status."""
    f = _fut_path(kind, coin, month)
    sf = f.with_suffix(".json")
    if f.exists() and sf.exists() and not force:
        return _load_json(sf)
    um = um_contract(coin)
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range(month + "-01", periods=31, freq="D")
            if d.strftime("%Y-%m") == month and d <= pd.Timestamp(END)]
    st = {"coin": coin, "month": month, "kind": kind, "contract": um[0] if um else None, "monthly": None,
          "days": {}, "verified": 0, "zips": 0}
    parts = []
    if um is not None:
        con, mult = um
        folder = _FUT[kind][0]
        if month < END[:7]:
            b, ok = _get_zip(f"data/futures/um/monthly/{folder}/{con}/1m/{con}-1m-{month}.zip")
            if b is not None:
                parts.append(_fut_parse(b, kind, mult)); st["monthly"] = "ok"; st["zips"] += 1; st["verified"] += ok
        have = set(parts[0].open_time.dt.strftime("%Y-%m-%d")) if parts else set()
        need = [d for d in days if d not in have]
        if need:
            dk = _daily_keys(f"data/futures/um/daily/{folder}/{con}/1m/")
            for d in need:
                key = f"data/futures/um/daily/{folder}/{con}/1m/{con}-1m-{d}.zip"
                if key not in dk:
                    continue
                b, ok = _get_zip(key, True)
                if b is not None:
                    x = _fut_parse(b, kind, mult)
                    x = x[x.open_time.dt.strftime("%Y-%m-%d") == d]
                    parts.append(x); st["zips"] += 1; st["verified"] += ok
                    st["days"][d] = "daily"
        for d in days:
            if d not in st["days"]:
                st["days"][d] = "monthly" if d in have else "missing"
    k = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=_FUT[kind][1])
    if len(k):
        k = k.sort_values("open_time", kind="stable").drop_duplicates("open_time", keep="last")
    k = k.reset_index(drop=True)
    st["rows"] = len(k)
    # sanity check of the contract mapping (no data is changed): the day's last futures close against the spot close
    st["basis_outside_half_to_double"] = []
    if len(k):
        try:
            sk = d1(coin)
        except Exception:
            sk = pd.DataFrame()
        if len(sk):
            sc = pd.Series(sk.close.to_numpy(), index=sk.open_time.dt.strftime("%Y-%m-%d"))
            fc = k.groupby(k.open_time.dt.strftime("%Y-%m-%d")).close.last()
            r = (fc / sc.reindex(fc.index)).dropna()
            st["basis_outside_half_to_double"] = sorted(r.index[(r < 0.5) | (r > 2.0)])
            st["basis_median_abs"] = float((r - 1).abs().median()) if len(r) else None
    _write_parquet(k, f)
    _save_json(sf, st)
    return st


@functools.lru_cache(maxsize=256)
def _fut_load(kind: str, coin: str, month: str) -> pd.DataFrame:
    f = _fut_path(kind, coin, month)
    if not f.exists():
        _fut_month(kind, coin, month)
    k = pd.read_parquet(f)
    if len(k):
        k["open_time"] = _ns(k.open_time)
    return k


def _fut_day(kind: str, coin: str, day) -> pd.DataFrame:
    d = pd.Timestamp(day)
    d = (d.tz_convert(None) if d.tzinfo else d).normalize()
    k = _fut_load(kind, coin, d.strftime("%Y-%m"))
    if k.empty:
        return k
    t = k.open_time.dt.tz_convert(None)
    return k[(t >= d) & (t < d + pd.Timedelta("1D"))].reset_index(drop=True)


def index1m(coin: str, day) -> pd.DataFrame:
    """USD-M index-price 1m klines of a coin's perpetual on one UTC day: open_time, open, high, low, close, updates
    (index updates in the minute; < 30 or a missing minute is an index outage, prereg §7). Empty = missing."""
    return _fut_day("index", coin, day)


def perp1m(coin: str, day) -> pd.DataFrame:
    """USD-M last-price 1m klines (F5) of a coin's perpetual on one UTC day; empty = missing."""
    return _fut_day("perp", coin, day)


def fut_status(kind: str, coin: str) -> pd.DataFrame:
    """Day status of every cached coin-month: day, source (monthly | daily | missing)."""
    rows = []
    for sf in sorted((OUT / "fut1m" / kind / coin).glob("*.json")):
        st = _load_json(sf)
        rows += [dict(coin=coin, day=d, source=s) for d, s in st.get("days", {}).items()]
    return pd.DataFrame(rows, columns=["coin", "day", "source"])


def fut_prefetch(kind: str, coin_days, workers: int = WORKERS, force: bool = False) -> pd.DataFrame:
    """Bulk helper: build every coin-month that contains a requested (coin, day) (or (coin, 'YYYY-MM')); returns the
    per coin-month status counts. Missing days are recorded, never filled."""
    cm = sorted({(c, str(d)[:7]) for c, d in coin_days})
    t0 = time.time()

    def one(x):
        try:
            st = _fut_month(kind, x[0], x[1], force)
            v = list(st["days"].values())
            return dict(coin=x[0], month=x[1], rows=st["rows"], zips=st["zips"], verified=st["verified"],
                        monthly=v.count("monthly"), daily=v.count("daily"), missing=v.count("missing"), error="")
        except Exception as e:
            return dict(coin=x[0], month=x[1], rows=0, zips=0, verified=0, monthly=0, daily=0, missing=0,
                        error=repr(e))
    with cf.ThreadPoolExecutor(workers) as ex:
        res = pd.DataFrame(list(ex.map(one, cm)))
    _fut_load.cache_clear()
    if len(res):
        print(f"{kind}1m: {len(cm)} coin-months in {time.time() - t0:.0f}s; days monthly {res.monthly.sum()}, daily "
              f"{res.daily.sum()}, missing {res.missing.sum()}; zips {res.zips.sum()} verified {res.verified.sum()}; "
              f"errors {(res.error != '').sum()}", flush=True)
    return res


def _um_keys(kind: str, con: str, interval: str, first_month: str | None = None):
    """[(key, has_checksum)]: monthly zips before END's month (from first_month), then daily zips up to END for the
    months after the last monthly file (at most two), as fetch_bb_data._keys does for klines."""
    _, mk = s3_ls(f"data/futures/um/monthly/{kind}/{con}/{interval}/")
    names = {k for k, _ in mk}
    em = END[:7]
    out = [(k, k + ".CHECKSUM" in names) for k in sorted(names) if k.endswith(".zip") and k[-11:-4] < em
           and (first_month is None or k[-11:-4] >= first_month)]
    last = max([k[-11:-4] for k, _ in out], default=None)
    months, m = [], (_ms(_mi(last) + 1) if last else em)
    while m <= em:
        months.append(m); m = _ms(_mi(m) + 1)
    for mo in (months if len(months) <= 2 else []):
        _, dk = s3_ls(f"data/futures/um/daily/{kind}/{con}/{interval}/{con}-{interval}-{mo}")
        dn = {k for k, _ in dk}
        out += [(k, k + ".CHECKSUM" in dn) for k in sorted(dn) if k.endswith(".zip") and k[-14:-4] <= END]
    return out


def index1d(coin: str, force: bool = False) -> pd.DataFrame:
    """USD-M 1d index klines of a coin's perpetual (for V4's fetch rule): open_time, open, high, low, close, updates."""
    f = OUT / "fut1d" / "index" / f"{coin}.parquet"
    if f.exists() and not force:
        k = pd.read_parquet(f)
        k["open_time"] = _ns(k.open_time)
        return k
    um = um_contract(coin)
    if um is None:
        return pd.DataFrame(columns=_FUT["index"][1])
    con, mult = um
    jobs = _um_keys("indexPriceKlines", con, "1d")
    blobs, st = bb._download(jobs, 8)
    k = (pd.concat([_fut_parse(b, "index", mult) for _, b in blobs], ignore_index=True) if blobs
         else pd.DataFrame(columns=_FUT["index"][1]))
    if len(k):
        k = k.sort_values("open_time", kind="stable").drop_duplicates("open_time", keep="last").reset_index(drop=True)
    _write_parquet(k, f)
    with _LS_LOCK:
        s = _load_json(OUT / "stats" / "index1d.json"); s[coin] = st; _save_json(OUT / "stats" / "index1d.json", s)
    return k


def index1d_bulk(coins=None, workers=WORKERS, force=False):
    """1d index klines (V4's fetch rule) for the cached-1m coin set (default) in parallel."""
    coins = coins or _m1_coins()
    t0 = time.time()

    def one(c):
        try:
            return c, len(index1d(c, force)), ""
        except Exception as e:
            return c, 0, repr(e)
    with cf.ThreadPoolExecutor(max(1, workers // 8)) as ex:
        res = list(ex.map(one, coins))
    print(f"index1d: {len(coins)} coins in {time.time() - t0:.0f}s; with rows {sum(n > 0 for _, n, _ in res)}; "
          f"no contract or no data: {' '.join(c for c, n, e in res if n == 0 and not e)}; errors "
          f"{[(c, e) for c, _, e in res if e]}", flush=True)
    return res


def index_fetch_days(bids: pd.DataFrame, s_values=(0.01, 0.02, 0.03, 0.05), near: float = 0.05) -> pd.DataFrame:
    """V4's fetch rule (prereg §4): the UTC days of each bid's life on which the 1d index low or the 1d spot low comes
    within 5% of L/(1 + s) or L, i.e. low <= (1 + near) x max(L, L/(1 + s)). bids: coin, L, live_from, live_to
    (timestamps). Returns the distinct (coin, day) pairs."""
    out = []
    for coin, g in bids.groupby("coin"):
        lows = {}
        sk = d1(coin)
        if len(sk):
            lows["spot"] = pd.Series(sk.low.to_numpy(), index=sk.open_time.dt.tz_convert(None).dt.normalize())
        ik = index1d(coin)
        if len(ik):
            lows["index"] = pd.Series(ik.low.to_numpy(), index=_ns(ik.open_time).dt.tz_convert(None).dt.normalize())
        if not lows:
            continue
        low = pd.concat(lows.values(), axis=1).min(axis=1).sort_index()
        days = low.index.to_numpy()
        lv = low.to_numpy()
        for r in g.itertuples():
            thr = (1 + near) * max([r.L] + [r.L / (1 + s) for s in s_values])
            a = pd.Timestamp(r.live_from); b = pd.Timestamp(r.live_to)
            a = (a.tz_convert(None) if a.tzinfo else a).normalize()
            b = (b.tz_convert(None) if b.tzinfo else b).normalize()
            i0, i1 = np.searchsorted(days, np.datetime64(a)), np.searchsorted(days, np.datetime64(b), side="right")
            hit = np.nonzero(lv[i0:i1] <= thr)[0]
            out += [(coin, pd.Timestamp(days[i0 + j])) for j in hit]
    return pd.DataFrame(sorted(set(out)), columns=["coin", "day"])


def _q1_coin_days(u: pd.DataFrame | None = None, first_btc: str = FUT_FROM_BTC, first: str = FUT_FROM):
    """Per U-Q1 coin: the days [M start - 31 days, M end] of every U-Q1 month M from 2021-12 (BTC from 2020-10)."""
    u = universes() if u is None else u
    q = u[u.U_Q1]
    out = {}
    for c, g in q.groupby("coin"):
        f0 = first_btc if c == "BTC" else first
        days = set()
        for m in g.month:
            if _mi(m) <= _mi(f0):
                continue
            a = pd.Timestamp(m + "-01") - pd.Timedelta("31D")
            b = min(pd.Timestamp(m + "-01") + pd.offsets.MonthEnd(0), pd.Timestamp(END))
            days |= set(pd.date_range(max(a, pd.Timestamp(f0 + "-01")), b, freq="D"))
        if days:
            out[c] = sorted(days)
    return out


def metrics_fetch(coin: str, days, workers: int = WORKERS, force: bool = False) -> dict:
    """USD-M futures metrics (5-minute open interest etc.) for the given days: daily zips only (the archive has no
    monthly metrics); appended to metrics/{COIN}.parquet; missing days recorded in stats."""
    um = um_contract(coin)
    if um is None:
        return {"coin": coin, "error": "no USD-M contract"}
    con, mult = um
    f = OUT / "metrics" / f"{coin}.parquet"
    sf = OUT / "metrics" / f"{coin}.json"
    st = _load_json(sf) or {"coin": coin, "contract": con, "days": {}}
    want = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in days]
    want = [d for d in want if force or d not in st["days"]]
    if not want:
        return st
    dk = _daily_keys(f"data/futures/um/daily/metrics/{con}/")

    def one(d):
        key = f"data/futures/um/daily/metrics/{con}/{con}-metrics-{d}.zip"
        if key not in dk:
            return d, None, False
        b, ok = _get_zip(key, True)
        return d, b, ok
    with cf.ThreadPoolExecutor(min(workers, max(1, len(want)))) as ex:
        res = list(ex.map(one, want))
    parts = []
    for d, b, ok in res:
        if b is None:
            st["days"][d] = "missing"; continue
        x = pd.read_csv(io.BytesIO(b))
        if not str(x.columns[0]).startswith("create"):
            x = pd.read_csv(io.BytesIO(b), header=None, names=["create_time", "symbol", "sum_open_interest",
                                                                 "sum_open_interest_value",
                                                                 "count_toptrader_long_short_ratio",
                                                                 "sum_toptrader_long_short_ratio",
                                                                 "count_long_short_ratio",
                                                                 "sum_taker_long_short_vol_ratio"])
        t = pd.to_datetime(x.create_time, utc=True, format="mixed")
        y = pd.DataFrame({"create_time": t.astype(NS),
                          "oi": x.sum_open_interest.astype(float) * mult,
                          "oi_usd": x.sum_open_interest_value.astype(float),
                          "toptrader_ls_count": pd.to_numeric(x.count_toptrader_long_short_ratio, errors="coerce"),
                          "toptrader_ls_sum": pd.to_numeric(x.sum_toptrader_long_short_ratio, errors="coerce"),
                          "ls_count": pd.to_numeric(x.count_long_short_ratio, errors="coerce"),
                          "taker_ls_vol": pd.to_numeric(x.sum_taker_long_short_vol_ratio, errors="coerce")})
        parts.append(y)
        st["days"][d] = "ok" + ("" if ok else " (no checksum)")
    if parts:
        new = pd.concat(parts, ignore_index=True)
        if f.exists():
            old = pd.read_parquet(f)
            old["create_time"] = _ns(old.create_time)
            new = pd.concat([old, new], ignore_index=True)
        new = new.sort_values("create_time", kind="stable").drop_duplicates("create_time", keep="last")
        _write_parquet(new.reset_index(drop=True), f)
    st["rows"] = int(len(pd.read_parquet(f, columns=["create_time"]))) if f.exists() else 0
    _save_json(sf, st)
    return st


def metrics(coin: str) -> pd.DataFrame:
    """5-minute USD-M metrics of a coin's perpetual: create_time (UTC), oi (coins), oi_usd, long/short ratios."""
    k = pd.read_parquet(OUT / "metrics" / f"{coin}.parquet")
    k["create_time"] = _ns(k.create_time)
    return k


def _um_hourly(coin: str, what: str, first_month: str, force: bool = False):
    """1h USD-M mark-price (what='mark') or last-price (what='perp') klines from first_month..END."""
    d = OUT / ("mark1h" if what == "mark" else "perp1h")
    f = d / f"{coin}.parquet"
    if f.exists() and not force:
        return None
    um = um_contract(coin)
    if um is None:
        return {"error": "no USD-M contract"}
    con, mult = um
    if what == "mark":
        jobs = bb._keys("um", "markPriceKlines", con, "1h", END, first_month)
        blobs, st = bb._download(jobs, 8)
        if not blobs:
            return st
        k = bb._frame(blobs).sort_values("open_time", kind="stable").drop_duplicates("open_time", keep="last")
        k = k[["open_time", "open", "high", "low", "close"]].reset_index(drop=True)
        k[["open", "high", "low", "close"]] = k[["open", "high", "low", "close"]].astype(float) / mult
    else:
        k, st = bb.klines("um", con, "1h", END, start_month=first_month, workers=8, mult=mult)
        if k is None:
            return st
    k["open_time"] = _ns(k.open_time)
    _write_parquet(k, f)
    st.update(contract=con, mult=mult, rows=len(k), first=str(k.open_time.iloc[0]), last=str(k.open_time.iloc[-1]))
    return st


def mark1h(coin: str) -> pd.DataFrame:
    k = pd.read_parquet(OUT / "mark1h" / f"{coin}.parquet")
    k["open_time"] = _ns(k.open_time)
    return k


def perp1h(coin: str) -> pd.DataFrame:
    k = pd.read_parquet(OUT / "perp1h" / f"{coin}.parquet")
    k["open_time"] = _ns(k.open_time)
    return k


def m7_bulk(what: str, coins=None, workers=WORKERS, force=False):
    """M7 inputs for U-Q1 coins: what in metrics | mark | perp1h."""
    cd = _q1_coin_days()
    if coins:
        cd = {c: v for c, v in cd.items() if c in coins}
    t0 = time.time()
    stats = _load_json(OUT / "stats" / f"{what}.json")
    if what == "metrics":
        n_ok = n_miss = 0

        def one_m(item):
            c, days = item
            try:
                return c, metrics_fetch(c, days, workers, force)
            except Exception as e:
                return c, {"error": repr(e), "days": {}}
        with cf.ThreadPoolExecutor(4) as ex:
            for i, (c, st) in enumerate(ex.map(one_m, sorted(cd.items()))):
                v = list(st.get("days", {}).values())
                stats[c] = {"contract": st.get("contract"), "days": len(v), "ok": sum(x.startswith("ok") for x in v),
                            "missing": v.count("missing"), "rows": st.get("rows", 0), "error": st.get("error", "")}
                n_ok += stats[c]["ok"]; n_miss += stats[c]["missing"]
                if (i + 1) % 10 == 0:
                    print(f"  metrics {i + 1}/{len(cd)} coins [{time.time() - t0:.0f}s]", flush=True)
        _save_json(OUT / "stats" / "metrics.json", stats)
        print(f"metrics: {len(cd)} coins in {time.time() - t0:.0f}s; days ok {n_ok}, missing {n_miss}", flush=True)
        return stats

    def one(c):
        return c, _um_hourly(c, "mark" if what == "mark" else "perp", FUT_FROM_BTC if c == "BTC" else FUT_FROM, force)
    with cf.ThreadPoolExecutor(max(1, workers // 8)) as ex:
        res = list(ex.map(one, sorted(cd)))
    stats.update({c: st for c, st in res if st is not None})
    _save_json(OUT / "stats" / f"{what}.json", stats)
    new = [st for _, st in res if st is not None]
    print(f"{what}: {len(cd)} coins, built {len(new)} in {time.time() - t0:.0f}s; zips "
          f"{sum(s.get('zips', 0) for s in new)}, verified {sum(s.get('verified', 0) for s in new)}, failed "
          f"{sum(len(s.get('failed', [])) for s in new)}", flush=True)
    return stats


# ================================================================ 7. aggTrades capacity (§7 Capacity; draft §8.3; K6)
def _agg_read(b: bytes) -> dict:
    """aggTrades CSV bytes -> numpy arrays (price, qty, time in microseconds UTC, is_buyer_maker)."""
    import pyarrow.csv as pc
    head = not b[:1].isdigit()
    names = ["agg_id", "price", "qty", "first_id", "last_id", "time", "is_buyer_maker", "is_best_match"]
    opts = pc.ReadOptions(column_names=names, skip_rows=1 if head else 0, block_size=1 << 26)
    conv = pc.ConvertOptions(include_columns=["price", "qty", "time", "is_buyer_maker"],
                             column_types={"price": "float64", "qty": "float64", "time": "int64",
                                           "is_buyer_maker": "string"})
    t = pc.read_csv(io.BytesIO(b), read_options=opts, convert_options=conv)
    import pyarrow.compute as pcm
    tm = t.column("time").to_numpy()
    tm = np.where(tm > 10 ** 14, tm, tm * 1000)                   # spot: microseconds since 2025, ms before
    bm = pcm.equal(pcm.utf8_lower(t.column("is_buyer_maker")), "true").to_numpy(zero_copy_only=False)
    out = {"price": t.column("price").to_numpy(), "qty": t.column("qty").to_numpy(), "time": tm,
           "bm": np.asarray(bm, bool)}
    if len(tm) > 1 and (np.diff(tm) < 0).any():
        o = np.argsort(tm, kind="stable")
        out = {k: v[o] for k, v in out.items()}
    return out


# "Strictly below L" as decimal prices (§7, draft §8.3 price priority: a print at L's own tick is not below L). A
# level floored to its tick in floating point is often one ULP (2.2e-16 relative) above its decimal value, so a raw
# `p < L` would count every print at L. The relative tolerance 1e-12 is far above that float error and far below any
# Binance spot tick (the smallest relative tick is about 1e-7: BTC at $100k with a $0.01 tick).
CAP_REL = 1e-12
_CAP_V = "v2"        # cache-key version: rows reduced under the raw-float rule (v1, unversioned keys) are not reused


def _agg_reduce(x: dict, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tm = x["time"]
    for w in windows.itertuples():
        a = np.searchsorted(tm, w.t0, side="left")
        b = np.searchsorted(tm, w.t1, side="left")
        if b <= a:
            continue
        p, q, bm = x["price"][a:b], x["qty"][a:b], x["bm"][a:b]
        m = bm & (p < w.L * (1.0 - CAP_REL))
        if not m.any():
            continue
        minute = (tm[a:b][m] // 60_000_000) * 60_000_000
        df = pd.DataFrame({"minute": minute, "usd": p[m] * q[m], "qty": q[m]})
        g = df.groupby("minute").agg(sell_below_usd=("usd", "sum"), sell_below_qty=("qty", "sum"),
                                     n_trades=("usd", "size")).reset_index()
        g.insert(0, "key", w.key)
        rows.append(g)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["key", "minute", "sell_below_usd", "sell_below_qty", "n_trades"])


def _wkey(L, t0, t1) -> str:
    return f"{_CAP_V}|{float(L)!r}|{int(t0)}|{int(t1)}"


def agg_capacity(coin: str, day, windows, cache: bool = True) -> pd.DataFrame:
    """Seller-initiated (is_buyer_maker = True) Binance spot aggTrades notional printed strictly below each level L,
    per minute, inside each window [start, end) clipped to the UTC day (prereg §7; draft §8.3). windows: rows with
    L, start, end (and optional wid). Returns wid, L, start, end, minute (UTC), sell_below_usd, sell_below_qty,
    n_trades: one row per window-minute with such trades (no row = no capacity in that minute). attrs['missing'] is
    True when the day's zip is absent from the archive (recorded in the cache, never filled). Results are cached per
    coin-day by (L, start, end); the day's zip is downloaded, reduced and discarded only for windows not yet cached.
    "Strictly below L" is meant as decimal prices: a print at L's own tick is not below L, whatever float noise L
    carries. The test is price < L x (1 - CAP_REL), CAP_REL = 1e-12, far below any Binance tick and far above the float
    error of a tick-floored level (one ULP, often above its decimal value)."""
    d = pd.Timestamp(day)
    d = (d.tz_convert(None) if d.tzinfo else d).normalize()
    w = pd.DataFrame(windows).copy()
    if "wid" not in w:
        w["wid"] = np.arange(len(w))
    d0 = pd.Timestamp(d, tz="UTC")
    d1_ = d0 + pd.Timedelta("1D")
    us = pd.Timedelta("1us")
    w["t0"] = (pd.to_datetime(w["start"], utc=True).clip(lower=d0, upper=d1_) - pd.Timestamp(0, tz="UTC")) // us
    w["t1"] = (pd.to_datetime(w["end"], utc=True).clip(lower=d0, upper=d1_) - pd.Timestamp(0, tz="UTC")) // us
    w["key"] = [_wkey(L, a, b) for L, a, b in zip(w.L, w.t0, w.t1)]
    cols = ["key", "minute", "sell_below_usd", "sell_below_qty", "n_trades"]
    f = OUT / "agg_cap" / coin / f"{d:%Y-%m-%d}.parquet"
    kf = f.with_suffix(".json")
    meta = _load_json(kf) if cache else {}
    done = {k for k in meta.get("keys", []) if k.startswith(_CAP_V + "|")}   # older-rule keys are recomputed
    todo = w[~w.key.isin(done) & (w.t1 > w.t0)].drop_duplicates("key")
    missing = bool(meta.get("missing", False))
    fresh = pd.DataFrame(columns=cols)
    if len(todo) and not missing:
        sym = coin_sym(coin)[0]
        key = f"data/spot/daily/aggTrades/{sym}/{sym}-aggTrades-{d:%Y-%m-%d}.zip"
        b, ok = _get_zip(key, False)
        if b is None:
            missing = True
            meta.update(missing=True, key=key)
        else:
            x = _agg_read(b)
            del b
            fresh = _agg_reduce(x, todo)
            meta.update(missing=False, key=key, sha256_verified=bool(ok), trades=int(len(x["price"])),
                        keys=sorted(done | set(todo.key)), rule=f"{_CAP_V}: is_buyer_maker and price < L*(1-{CAP_REL})")
        if cache:
            if len(fresh):
                old = pd.read_parquet(f) if f.exists() else None
                old = old[old.key.isin(done)] if old is not None else None          # drop rows of older rules
                _write_parquet(pd.concat([old, fresh], ignore_index=True) if old is not None and len(old) else fresh,
                               f)
            _save_json(kf, meta)
    res = pd.read_parquet(f) if cache and f.exists() else fresh
    res = res[res.key.isin(set(w.key))]
    out = w[["wid", "L", "start", "end", "key"]].merge(res, on="key", how="inner").drop(columns="key")
    out["minute"] = pd.to_datetime(out.minute.astype("int64"), unit="us", utc=True).astype(NS)
    out = out.sort_values(["wid", "minute"]).reset_index(drop=True)
    out.attrs["missing"] = missing
    return out


def agg_prefetch(windows: pd.DataFrame, workers: int = 4) -> pd.DataFrame:
    """Bulk helper: windows with coin, L, start, end (wid optional; a window may span UTC days). Streams each
    coin-day's aggTrades zip once (download, reduce, discard) and caches the reduced rows. Returns per coin-day
    status (windows, rows, missing, seconds)."""
    w = windows.copy()
    w["start"] = pd.to_datetime(w.start, utc=True); w["end"] = pd.to_datetime(w.end, utc=True)
    rows = []
    for r in w.itertuples(index=False):
        for d in pd.date_range(r.start.floor("D"), (r.end - pd.Timedelta("1ns")).floor("D"), freq="D"):
            rows.append((r.coin, d.tz_convert(None), r.L, r.start, r.end))
    jobs = pd.DataFrame(rows, columns=["coin", "day", "L", "start", "end"])
    t0 = time.time()

    def one(key):
        (c, d), g = key
        t = time.time()
        try:
            out = agg_capacity(c, d, g[["L", "start", "end"]])
            return dict(coin=c, day=d, windows=len(g), rows=len(out), missing=out.attrs.get("missing", False),
                        seconds=time.time() - t, error="")
        except Exception as e:
            return dict(coin=c, day=d, windows=len(g), rows=0, missing=False, seconds=time.time() - t, error=repr(e))
    with cf.ThreadPoolExecutor(workers) as ex:
        res = pd.DataFrame(list(ex.map(one, list(jobs.groupby(["coin", "day"])))))
    if len(res):
        print(f"agg: {len(res)} coin-days, {len(w)} windows in {time.time() - t0:.0f}s; missing days "
              f"{int(res.missing.sum())}, errors {(res.error != '').sum()}", flush=True)
    return res


# ================================================================ 8. USDT/USD proxy, Robinhood pairs, T-bill
USD_STABLES = ("BUSDUSDT", "USDCUSDT", "TUSDUSDT")


def usd_fetch(force=False):
    d = OUT / "usd"
    stats = {}
    for s in USD_STABLES:
        f = d / f"h1_{s}.parquet"
        if f.exists() and not force:
            continue
        k, st = bb.klines("spot", s, "1h", END, start_month=M1_FROM, workers=16)
        if k is not None:
            _write_parquet(k, f)
        stats[s] = st
    if stats:
        old = _load_json(OUT / "stats" / "usd.json"); old.update(stats); _save_json(OUT / "stats" / "usd.json", old)
    u = usdt_usd_hourly(rebuild=True)
    print(f"usd: hourly proxy {len(u):,} hours {u.index.min()}..{u.index.max()}; hours with >= 1 liquid stable "
          f"{(u.n_liquid > 0).mean():.1%}; median |usd_per_usdt - 1| {np.nanmedian(np.abs(u.usd_per_usdt - 1)):.5f}",
          flush=True)
    return u


def usdt_usd_hourly(min_quote_volume: float = 2e5, rebuild: bool = False) -> pd.DataFrame:
    """Hourly USD value of one USDT (§4: USDC/BUSD/TUSD vs USDT): 1 / median close of the stablecoins that traded at
    least $200k in the hour; the most traded one when none did; NaN when none traded. A USD price = USDT price x
    usd_per_usdt. Index: `open_time`, the hour's open, datetime64[ns, UTC], the same whether the frame is rebuilt or
    read from its cache (look up a fill minute with .reindex(t.floor('h')))."""
    f = OUT / "usd" / "usdt_usd_hourly.parquet"
    if f.exists() and not rebuild:
        u = pd.read_parquet(f)
        u.index = pd.DatetimeIndex(_ns(u.pop("open_time")), name="open_time")
        return u
    px, qv = {}, {}
    for s in USD_STABLES:
        k = pd.read_parquet(OUT / "usd" / f"h1_{s}.parquet")
        k["open_time"] = _ns(k.open_time)
        k = k.set_index("open_time")
        live = k.trades > 0
        px[s[:-4]] = k.close.where(live); qv[s[:-4]] = k.quote_volume.where(live)
    px, qv = pd.DataFrame(px), pd.DataFrame(qv)
    idx = pd.date_range(px.index.min(), pd.Timestamp(END, tz="UTC") + pd.Timedelta("23h"), freq="h", name="open_time")
    px, qv = px.reindex(idx), qv.reindex(idx)
    liq = qv >= min_quote_volume
    med = px.where(liq).median(axis=1)
    aq = qv.fillna(-1).to_numpy()
    j = aq.argmax(axis=1)
    top = pd.Series(np.asarray(qv.columns)[j], index=idx)
    fb = pd.Series(np.where(aq.max(axis=1) >= 0, px.to_numpy()[np.arange(len(idx)), j], np.nan), index=idx)
    p = med.where(liq.any(axis=1), fb)
    out = pd.concat([px.add_suffix("_close"), qv.add_suffix("_qv")], axis=1)
    out["n_liquid"] = liq.sum(axis=1)
    out["usd_per_usdt"] = 1.0 / p
    out["source"] = np.where(liq.any(axis=1), "median", np.where(p.notna(), "most traded: " + top, "none"))
    out.index = pd.DatetimeIndex(_ns(pd.Series(out.index)), name="open_time")
    _write_parquet(out.reset_index(), f)
    return out


def rh_pairs() -> pd.DataFrame:
    """Robinhood's read-only catalog of 2026-11-18: coin, symbol, tradability, tradable, price_tick, qty_increment,
    min_order_size, max_order_size (floats; the decimal strings are kept in *_str), market_orders_only, halted,
    halted_regions."""
    path = next((p for p in RH_CATALOG if p.exists()), None)
    if path is None:
        raise FileNotFoundError("the saved Robinhood catalog is missing (data/stinkbid/ref/currency_pairs.json)")
    d = json.loads(path.read_text())
    rows = []
    for x in d["results"]:
        rows.append(dict(coin=x["asset_currency"], symbol=x["symbol"], tradability=x["tradability"],
                         tradable=x["tradability"] == "tradable",
                         price_tick=float(x["min_order_price_increment"]),
                         qty_increment=float(x["min_order_quantity_increment"]),
                         min_order_size=float(x["min_order_size"]), max_order_size=float(x["max_order_size"]),
                         price_tick_str=x["min_order_price_increment"],
                         qty_increment_str=x["min_order_quantity_increment"],
                         min_order_size_str=x["min_order_size"], max_order_size_str=x["max_order_size"],
                         market_orders_only=bool(x["market_orders_only"]), halted=bool(x["halted"]),
                         halted_regions=" ".join(x.get("halted_regions") or [])))
    out = pd.DataFrame(rows).sort_values("coin").reset_index(drop=True)
    out.attrs["source"] = f"{d.get('source', '')} ({path.relative_to(ROOT)})"
    return out


FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
TBILL_EXT = "DTB3"        # FRED 3-month T-bill, secondary market, discount basis = SteelCerberus's 'Risk Free Rate'
TBILL_PREREG = "DGS3MO"   # FRED 3-month constant-maturity yield: the source of the prereg's '4.21% on 2026-11-02'


def _fred(series: str, force: bool = False) -> pd.Series:
    """A FRED daily series (% a year) from its public CSV, kept as data/stinkbid/macro/fred_{series}.csv."""
    f = OUT / "macro" / f"fred_{series}.csv"
    if force or not f.exists():
        b = get(FRED + series, 120)
        if b is None or b.split(b"\n", 1)[0].strip().split(b",")[-1] != series.encode():
            raise IOError(f"FRED {series}: unreachable or not a FRED CSV")
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = _tmp(f)
        tmp.write_bytes(b)
        os.replace(tmp, f)
    x = pd.read_csv(f)
    s = pd.Series(pd.to_numeric(x[series], errors="coerce").to_numpy(), index=pd.to_datetime(x.iloc[:, 0]), name=series)
    return s.dropna().sort_index()


def _rf_base() -> pd.Series:
    """The daily series regime_switch.rf_annual_pct reads (SteelCerberus us_market_data.csv, 'Risk Free Rate'), read
    the way it reads it; kept under data/stinkbid/macro/ when data/macro/ is absent."""
    from analysis_2026 import regime_switch as rs
    f = rs.DATA / "macro" / "us_market_data.csv"
    if not f.exists():
        f = OUT / "macro" / "us_market_data.csv"
        if not f.exists():
            from analysis_2026.fetch_regime_data import MACRO
            b = get(MACRO["us_market_data.csv"], 120)
            if b is None:
                raise IOError("T-bill source unreachable")
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(b)
    m = pd.read_csv(f, usecols=["Date", "Risk Free Rate"], parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
    return m[~m.index.duplicated()].sort_index()


@functools.lru_cache(maxsize=1)
def tbill_series() -> pd.Series:
    """The daily 3-month T-bill (% a year) behind tbill_daily: rf_annual_pct's own source through its last day
    (2025-12-19), then FRED DTB3, the same series (identical on the overlap; selftest), so 2026 is not the TBILL table's
    flat 3.70%."""
    base = _rf_base()
    ext = _fred(TBILL_EXT)
    return pd.concat([base, ext[ext.index > base.index[-1]]]).rename("Risk Free Rate")


def tbill_daily(index) -> pd.Series:
    """3-month T-bill, % a year, on `index`: regime_switch.rf_annual_pct (prereg §4 Cash) run on tbill_series(), which
    is handed to it through its cache. Through 2025-12-19 the numbers are the function's own; later days are FRED DTB3
    (forward-filled over non-business days by the function), not its annual table."""
    from analysis_2026 import regime_switch as rs
    idx = pd.DatetimeIndex(index)
    idx_n = idx.tz_convert(None) if idx.tz is not None else idx
    rs._RF_CACHE["rf"] = tbill_series()
    return pd.Series(rs.rf_annual_pct(pd.DatetimeIndex(idx_n.normalize())), index=index, name="tbill_pct")


def tbill_fetch(force: bool = False) -> dict:
    """Fetch (or refresh with force) the FRED series under data/stinkbid/macro/ and record their coverage."""
    tbill_series.cache_clear()
    st = {}
    for s in (TBILL_EXT, TBILL_PREREG):
        x = _fred(s, force)
        st[s] = dict(rows=len(x), first=str(x.index[0].date()), last=str(x.index[-1].date()),
                     fetched=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()) if force else None)
    base, ext = _rf_base(), _fred(TBILL_EXT)
    j = pd.concat([base, ext], axis=1, keys=["base", "ext"], sort=True).dropna().loc["2019-10-01":]
    st["overlap"] = dict(days=len(j), identical=float(((j.base - j.ext).abs() < 0.005).mean()),
                         max_abs_diff=float((j.base - j.ext).abs().max()), base_last=str(base.index[-1].date()))
    old = _load_json(OUT / "stats" / "tbill.json")
    for s in (TBILL_EXT, TBILL_PREREG):
        if st[s]["fetched"] is None:
            st[s]["fetched"] = old.get(s, {}).get("fetched")
    _save_json(OUT / "stats" / "tbill.json", st)
    tb = tbill_daily(pd.DatetimeIndex(["2025-12-19", "2026-01-05", "2026-11-02", "2026-11-17"]))
    print(f"tbill: {TBILL_EXT} {st[TBILL_EXT]['first']}..{st[TBILL_EXT]['last']}; overlap with rf_annual_pct's source "
          f"since 2019-10: {st['overlap']['days']} days, identical {st['overlap']['identical']:.3f}, max |diff| "
          f"{st['overlap']['max_abs_diff']:.3f}; " + ", ".join(f"{d.date()} {v:.2f}%" for d, v in tb.items()),
          flush=True)
    return st


# ================================================================ 9. report (counts and coverage; no outcome)
def m1_coverage(syms=None) -> pd.DataFrame:
    """Per cached 1m symbol: bars, first/last bar, minutes missing between them, zero-trade minutes, days with more
    than 60 minutes missing (first and last day excluded), minutes on days without a daily kline, and which OHLC fields
    differ from the 1d kline on the builder's unresolved days. attrs['months'][(sym, 'YYYY-MM')] = share of the
    month's minutes present; attrs['by_year'] = unresolved days by year."""
    st = _load_json(OUT / "stats" / "m1.json")
    files = sorted((OUT / "m1_spot").glob("*.parquet"))
    if syms:
        files = [f for f in files if f.stem in set(syms)]
    a = d1_panel()
    dday = {s: set((g.day.to_numpy().astype("datetime64[D]").astype(np.int64)).tolist()) for s, g in a.groupby("sym")}
    rows, months, by_year = [], {}, {}
    for f in files:
        k = pd.read_parquet(f, columns=["open_time", "trades"])
        ti = _ns(k.open_time).dt.tz_convert(None).to_numpy().astype("datetime64[m]").astype(np.int64)
        n = len(ti)
        r = dict(sym=f.stem, bars=n)
        if n == 0:
            rows.append(r); continue
        day = ti // 1440
        ud, cnt = np.unique(day, return_counts=True)
        inner = cnt[1:-1] if len(cnt) > 2 else cnt[:0]
        known = dday.get(f.stem, set())
        r.update(first=pd.Timestamp(int(ti[0]) * 60_000_000_000, tz="UTC"),
                 last=pd.Timestamp(int(ti[-1]) * 60_000_000_000, tz="UTC"),
                 missing=int(ti[-1] - ti[0] + 1 - n), zero_trade=int((k.trades.to_numpy() == 0).sum()),
                 days_gt60_missing=int((inner < 1380).sum()),
                 seg_minus1=int(cnt[~np.isin(ud, list(known))].sum()))
        mo = ti.astype("datetime64[m]").astype("datetime64[M]")
        um, mc = np.unique(mo, return_counts=True)
        for m, c in zip(um, mc):
            ms = str(m)[:7]
            months[(f.stem, ms)] = c / (pd.Period(ms).days_in_month * 1440)
        un = st.get(f.stem, {}).get("ref_days_unresolved", [])
        r["unresolved_days"] = len(un)
        diff = {"open": 0, "high": 0, "low": 0, "close": 0, "traded_only": 0}
        if un:
            ux = np.array([np.datetime64(x, "D").astype(np.int64) for x in un])
            sel = np.isin(day, ux)
            x = pd.read_parquet(f, columns=["open", "high", "low", "close"])[sel]
            x["day"] = day[sel]
            x["traded"] = k.trades.to_numpy()[sel] > 0
            agg = dict(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"))
            g = x.groupby("day").agg(**agg)
            gt = x[x.traded].groupby("day").agg(**agg)                # zero-trade placeholder minutes dropped
            ref = a[a.sym == f.stem].copy()
            ref["di"] = ref.day.to_numpy().astype("datetime64[D]").astype(np.int64)
            ref = ref.set_index("di")
            for xd, xs in zip(ux, un):
                by_year[xs[:4]] = by_year.get(xs[:4], 0) + 1
                if xd in g.index and xd in ref.index:
                    for c in ("open", "high", "low", "close"):
                        diff[c] += int(abs(g.at[xd, c] / ref.at[xd, c] - 1) > 1e-9)
                    diff["traded_only"] += int(xd not in gt.index or any(
                        abs(gt.at[xd, c] / ref.at[xd, c] - 1) > 1e-9 for c in ("open", "high", "low", "close")))
        r.update({f"diff_{c}": v for c, v in diff.items()})
        rows.append(r)
    out = pd.DataFrame(rows)
    out.attrs["months"] = months
    out.attrs["by_year"] = dict(sorted(by_year.items()))
    return out


def report(write: bool = True) -> str:
    lines = []

    def say(s=""):
        print(s, flush=True); lines.append(str(s))
    u = universes()
    say(f"universes {u.month.min()}..{u.month.max()} ({u.month.nunique()} months)")
    n = u.groupby("month")[["U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_A", "U_C"]].sum()
    for c in n.columns:
        say(f"  {c:8s} coins ever {u.coin[u[c]].nunique():4d}; per month min {int(n[c].min())} median "
            f"{n[c].median():.0f} max {int(n[c].max())}; coin-months {int(n[c].sum())}")
    for m in ("2020-01", "2021-05", "2022-05", "2022-11", "2025-10", "2026-11"):
        if m in n.index:
            say(f"  {m}: " + ", ".join(f"{c} {int(n.at[m, c])}" for c in n.columns) + "; U-Q1: " +
                " ".join(sorted(u.coin[(u.month == m) & u.U_Q1])))
    for c in ("LUNA", "FTT", "LUNA2", "LUNC", "POL", "S", "RENDER", "SKY", "HEI", "A", "BTTC"):
        x = u[(u.coin == c)]
        if len(x):
            say(f"  {c:6s} U-B months {int(x.U_B.sum())} ({x.month[x.U_B].min()}..{x.month[x.U_B].max()}), U-Q1 "
                f"{int(x.U_Q1.sum())}, U-Q1-12 {int(x.U_Q1_12.sum())}; best rank {x['rank'].min():.0f}; "
                f"age at first U-B month {x.listing_age_months[x.U_B].min() if x.U_B.any() else ''}")
    rk = ranks()
    bs = rk[rk.backstop]
    say(f"stablecoin backstop: {bs.coin.nunique()} coins excluded in {len(bs)} coin-months "
        f"({' '.join(sorted(bs.coin.unique()))})")
    seg = pd.read_csv(OUT / "ref" / "segments.csv") if (OUT / "ref" / "segments.csv").exists() else None
    if seg is not None:
        b = seg[seg.kind != "data_end"]
        say(f"segment ends (U-B and 1m coins): {b.kind.value_counts().to_dict()}")
        for r in b[b.kind.isin(["redenomination", "redenomination_outside_band", "redenomination_unconfirmed",
                                "swap", "gap", "jump"])].itertuples():
            say(f"  {r.coin:7s} {r.kind:28s} last {str(r.last_day)[:10]} next {str(r.next_first_day)[:10]} data ratio "
                f"{r.data_ratio:.6g} units {r.units} {r.successor}")
    st = _load_json(OUT / "stats" / "m1.json")
    if st:
        ok = {s: x for s, x in st.items() if "error" not in x}
        say(f"m1: {len(ok)} symbols, rows {sum(x.get('rows', 0) for x in ok.values()):,}, zips "
            f"{sum(x.get('zips', 0) for x in ok.values()):,}, verified {sum(x.get('verified', 0) for x in ok.values()):,},"
            f" failed {sum(len(x.get('failed', [])) for x in ok.values())}, holes filled "
            f"{sum(x.get('hole_bars_filled', 0) for x in ok.values()):,}, days checked vs 1d "
            f"{sum(x.get('ref_days_checked', 0) for x in ok.values()):,}, repaired "
            f"{sum(len(x.get('ref_days_repaired', [])) for x in ok.values())}, unresolved "
            f"{sum(len(x.get('ref_days_unresolved', [])) for x in ok.values())}; cache "
            f"{sum(x.get('bytes', 0) for x in ok.values()) / 2 ** 30:.2f} GB; build time "
            f"{sum(x.get('seconds', 0) for x in ok.values()) / 60:.1f} process-minutes; errors "
            f"{len(st) - len(ok)}")
    cov = m1_coverage()
    if len(cov):
        say(f"m1 coverage: {len(cov)} symbols, {cov.bars.sum():,} bars; minutes missing between first and last bar "
            f"{cov.missing.sum():,} ({cov.missing.sum() / (cov.bars.sum() + cov.missing.sum()):.4%}); zero-trade minutes "
            f"{cov.zero_trade.sum():,}; days with > 60 minutes missing {cov.days_gt60_missing.sum():,}; minutes on days "
            f"without a daily kline {cov.seg_minus1.sum():,}")
        say(f"  1m days whose aggregate differs from the 1d kline: {int(cov.unresolved_days.sum())} days (by year "
            f"{cov.attrs.get('by_year', {})}); fields differing: open {int(cov.diff_open.sum())}, high "
            f"{int(cov.diff_high.sum())}, low {int(cov.diff_low.sum())}, close {int(cov.diff_close.sum())}; still "
            f"differing once zero-trade placeholder minutes (OHLC = prior close; never fill, §4.1) are dropped: "
            f"{int(cov.diff_traded_only.sum())}")
        months = cov.attrs.get("months", {})
        for c in ("U_Q1", "U_Q1_12", "U_A", "U_C"):
            x = u[u[c]]
            have = [months.get((coin_sym(cc)[0], m), 0.0) for cc, m in zip(x.coin, x.month)]
            have = np.asarray(have)
            say(f"  {c}: coin-months {len(x)}, with >= 95% of the month's minutes in the 1m cache "
                f"{(have >= 0.95).mean():.2%}, with none {(have == 0).mean():.2%}")
    for name in ("metrics", "mark", "perp1h", "index1d", "d1_full", "h1_pre", "usd"):
        s = _load_json(OUT / "stats" / f"{name}.json")
        if s:
            v = list(s.values())
            say(f"{name}: {len(v)} series; " + ", ".join(
                f"{k} {sum(x.get(k, 0) for x in v if isinstance(x.get(k, 0), (int, float))):,}"
                for k in ("zips", "verified", "days", "ok", "missing", "rows") if any(k in x for x in v)) +
                f"; failed {sum(len(x.get('failed', [])) for x in v)}")
    txt = "\n".join(lines) + "\n"
    if write:
        (OUT / "reports").mkdir(parents=True, exist_ok=True)
        (OUT / "reports" / "data_report.txt").write_text(txt)
    return txt


# ================================================================ CLI
def _arg(name, default):
    a = sys.argv
    return a[a.index(name) + 1] if name in a else default


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__); return
    cmd = sys.argv[1]
    force = "--force" in sys.argv
    workers = int(_arg("--workers", WORKERS))
    procs = int(_arg("--procs", 4))
    coins = [c for c in _arg("--coins", "").split(",") if c]
    t0 = time.time()
    steps = {
        "ages": lambda: ages(True, workers),
        "d1-2017": lambda: d1_full(force, workers),
        "universes": build_universes,
        "segments": build_segments,
        "h1pre": lambda: h1_pre(force, workers),
        "usd": lambda: usd_fetch(force),
        "tbill": lambda: tbill_fetch(force),
        "m1": lambda: m1_bulk(coins or None, force, procs),
        "metrics": lambda: m7_bulk("metrics", coins or None, workers, force),
        "mark": lambda: m7_bulk("mark", coins or None, workers, force),
        "perp1h": lambda: m7_bulk("perp1h", coins or None, workers, force),
        "index1d": lambda: index1d_bulk(coins or None, workers, force),
        "report": report,
    }
    if cmd == "all":
        for s in ("ages", "d1-2017", "universes", "h1pre", "usd", "tbill", "m1", "metrics", "mark", "perp1h",
                  "index1d", "report"):
            t = time.time(); steps[s](); print(f"[{s}: {time.time() - t:.0f}s]", flush=True)
    elif cmd in steps:
        steps[cmd]()
    elif cmd in ("index1m", "perp1m"):
        months = [m for m in _arg("--months", "").split(",") if m]
        fut_prefetch(cmd[:-2] if cmd == "index1m" else "perp", [(c, m) for c in coins for m in months], workers, force)
    elif cmd == "agg":
        f = _arg("--windows", None)
        w = pd.read_parquet(f) if f.endswith(".parquet") else pd.read_csv(f)
        agg_prefetch(w, int(_arg("--procs", 4)))
    elif cmd == "selftest":
        selftest()
    else:
        print(__doc__); sys.exit(1)
    print(f"[{cmd}: {time.time() - t0:.0f}s]", flush=True)


# ================================================================ selftest
@contextlib.contextmanager
def _patched(**kw):
    """Replace module globals (OUT, _get_zip, ...) for the duration of a selftest block."""
    g = globals()
    old = {k: g[k] for k in kw}
    g.update(kw)
    try:
        yield
    finally:
        g.update(old)


@contextlib.contextmanager
def _scratch_out():
    """A temporary OUT for selftests that write files (inside data/stinkbid/ when it exists; removed afterwards)."""
    with tempfile.TemporaryDirectory(prefix=".selftest_", dir=OUT if OUT.exists() else None) as d:
        with _patched(OUT=Path(d)):
            yield Path(d)


def _synth(coin, start, n, price=10.0, qv=1e6, sd=0.03, seed=0, drop=(), jumps=None, zero=(), sym=None):
    """Synthetic daily klines: open = prior close (x jumps[day] on given days), close = open x exp(N(0, sd))."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(start, periods=n, freq="D")
    rows, c = [], price
    for d in days:
        o = c * (jumps or {}).get(str(d.date()), 1.0)
        c = o * float(np.exp(rng.normal(0, sd)))
        hi, lo = max(o, c) * 1.01, min(o, c) * 0.99
        v = qv * float(np.exp(rng.normal(0, 0.2)))
        rows.append(dict(sym=sym or coin + "USDT", coin=coin, day=d, open_time=d.tz_localize("UTC"), open=o, high=hi,
                         low=lo, close=c, volume=v / ((o + c) / 2), quote_volume=v,
                         trades=0 if str(d.date()) in zero else 1000, taker_buy_quote=v / 2, excluded=""))
    k = pd.DataFrame(rows)
    k = k[~k.day.astype(str).str[:10].isin(drop)]
    return k.reset_index(drop=True)


def _panel_seg(a: pd.DataFrame) -> pd.DataFrame:
    a = a.sort_values(["coin", "day"]).reset_index(drop=True)
    a["open_time"] = _ns(a.open_time)
    a["seg"] = _seg_ids(a)
    return a


def _oracle_seg(k: pd.DataFrame) -> list:
    """Segment ids written out directly from the rule (separate code from _seg_ids)."""
    out, s, prev = [], 0, None
    for r in k.itertuples():
        if r.trades == 0:
            out.append(-1); continue
        if prev is not None and ((r.day - prev.day).days > 1 or abs(r.open / prev.close - 1) > 0.25):
            s += 1
        out.append(s); prev = r
    return out


def _t_segments():
    a = pd.concat([_synth("XA", "2020-01-01", 91, seed=1),
                   _synth("XB", "2020-01-01", 91, seed=2, drop=("2020-02-10",)),
                   _synth("XC", "2020-01-01", 91, seed=3, jumps={"2020-02-15": 1.30, "2020-03-01": 1.20}),
                   _synth("XD", "2020-01-01", 91, seed=4, zero=("2020-03-05",)),
                   _synth("XE", "2020-01-01", 91, seed=5, jumps={"2020-02-01": 0.70})], ignore_index=True)
    a = _panel_seg(a)
    for c, g in a.groupby("coin"):
        assert list(g.seg) == _oracle_seg(g), c
    seg = {c: g.set_index(g.day.dt.strftime("%Y-%m-%d")).seg for c, g in a.groupby("coin")}
    assert set(seg["XA"]) == {0}
    assert seg["XB"]["2020-02-09"] == 0 and seg["XB"]["2020-02-11"] == 1 and "2020-02-10" not in seg["XB"]
    assert seg["XC"]["2020-02-14"] == 0 and seg["XC"]["2020-02-15"] == 1 and seg["XC"]["2020-03-01"] == 1
    assert seg["XD"]["2020-03-05"] == -1 and seg["XD"]["2020-03-04"] == 0 and seg["XD"]["2020-03-06"] == 1
    assert seg["XE"]["2020-02-01"] == 1                          # a 30% fall at the open is a boundary too
    return "segments: missing day, >25% open jump (up and down), zero-trade day, 20% jump kept; matches oracle"


def _t_joins():
    out = []
    # confirmed redenomination inside the band: COCOS x1000 across 2021-01-19..22
    def two(coin, ratio, gap=True, d0="2021-01-01", n0=18, d1="2021-01-23", n1=20, seed=0):
        a = _synth(coin, d0, n0, price=0.0007, seed=seed)
        p1 = float(a.close.iloc[-1]) * ratio
        b = _synth(coin, d1 if gap else str((pd.Timestamp(d0) + pd.Timedelta(days=n0)).date()), n1, price=p1,
                   seed=seed + 1)
        b.loc[0, "open"] = p1
        k = _panel_seg(pd.concat([a, b], ignore_index=True))
        return k[KCOLS + ["seg"]]
    t = _segments_from(two("COCOS", 1000.0), "COCOS")
    assert t.kind.iloc[0] == "redenomination" and bool(t["continues"].iloc[0]) and abs(t.units.iloc[0] - 1e-3) < 1e-15
    assert abs(t.band_dev.iloc[0]) < 1e-9 and t.kind.iloc[1] == "delisting"
    t = _segments_from(two("COCOS", 1100.0), "COCOS")
    assert t.kind.iloc[0] == "redenomination_outside_band" and not bool(t["continues"].iloc[0])
    t = _segments_from(two("COCOS", 1040.0), "COCOS")
    assert t.kind.iloc[0] == "redenomination" and bool(t["continues"].iloc[0])          # 4% off: inside the band
    t = _segments_from(two("ZZZQ", 0.01), "ZZZQ")
    assert t.kind.iloc[0] == "redenomination_unconfirmed" and not bool(t["continues"].iloc[0])
    t = _segments_from(two("ZZZQ", 0.7), "ZZZQ")
    assert t.kind.iloc[0] == "gap" and not bool(t["continues"].iloc[0])
    t = _segments_from(two("ZZZQ", 1.4, gap=False), "ZZZQ")
    assert t.kind.iloc[0] == "jump" and bool(t["continues"].iloc[0]) and t.units.iloc[0] == 1.0
    out.append("redenomination joined at 10^n inside +-5% only when announced; outside band / unannounced / plain "
               "gap -> delisting; jump without gap continues")
    # swap: MATIC ends 2024-09-10, POL opens 2024-09-13 at MATIC's last close (1:1)
    m = _panel_seg(_synth("MATIC", "2024-08-01", 41, price=0.4, seed=7))[KCOLS + ["seg"]]
    pol = _panel_seg(_synth("POL", "2024-09-13", 30, price=float(m.close.iloc[-1]), seed=8))[KCOLS + ["seg"]]
    pol.loc[0, "open"] = float(m.close.iloc[-1])
    t = _segments_from(m, "MATIC", None, pol)
    assert t.kind.iloc[-1] == "swap" and t.successor.iloc[-1] == "POL" and bool(t["continues"].iloc[-1])
    assert t.units.iloc[-1] == 1.0 and abs(t.data_ratio.iloc[-1] - 1) < 1e-12
    assert t.next_first_day.iloc[-1] == pd.Timestamp("2024-09-13")
    mk = _panel_seg(_synth("MKR", "2025-08-01", 46, price=1800.0, seed=9))[KCOLS + ["seg"]]
    sky = _panel_seg(_synth("SKY", "2025-09-17", 20, price=float(mk.close.iloc[-1]) / 24000, seed=10))[KCOLS + ["seg"]]
    sky.loc[0, "open"] = float(mk.close.iloc[-1]) / 24000
    t = _segments_from(mk, "MKR", None, sky)
    assert t.kind.iloc[-1] == "swap" and t.units.iloc[-1] == 24000.0 and abs(t.band_dev.iloc[-1]) < 1e-9
    k = _panel_seg(_synth("ZZZQ", "2026-10-01", 48, seed=11))[KCOLS + ["seg"]]
    t = _segments_from(k, "ZZZQ")
    assert t.kind.iloc[-1] == "data_end" and bool(t["continues"].iloc[-1])            # trades through END: censored
    out.append("swaps continue at the announced units (MATIC->POL 1, MKR->SKY 24,000) with the data ratio beside it; "
               "a series through END is censored, not delisted")
    return "; ".join(out)


def _t_delist():
    k = _panel_seg(_synth("DLX", "2024-01-01", 20, seed=12))
    k.loc[18, ["quote_volume", "volume"]] = [1000.0, 10.0]                  # 2024-01-19: VWAP 100
    k.loc[19, ["quote_volume", "volume"]] = [10.0, 1.0]                     # 2024-01-20: partial last day
    days = pd.DatetimeIndex(k.day)
    hb = pd.DataFrame({"h_first": 0, "h_last": 23, "t_last": days + pd.Timedelta("23h59min"), "source": "1h"},
                      index=days)
    hb.loc[days[-1], ["h_last", "t_last"]] = [5, days[-1] + pd.Timedelta("5h30min")]
    t = _segments_from(k[KCOLS + ["seg"]], "DLX", hb)
    assert t.kind.iloc[-1] == "delisting" and t.last_full_day.iloc[-1] == pd.Timestamp("2024-01-19")
    v = _delist_row(t, "DLX")
    assert abs(v["vwap"] - 100.0) < 1e-12 and abs(v["value"] - 70.0) < 1e-12
    assert abs(v["value_last_trade"] - 0.7 * float(k.close.iloc[-1])) < 1e-12 and v["value_haircut100"] == 0.0
    assert abs(v["value_haircut0"] - 100.0) < 1e-12
    assert t.last_trade_time.iloc[-1] == pd.Timestamp("2024-01-20 05:30", tz="UTC")
    hb2 = hb.copy(); hb2.loc[days[-2], "h_first"] = 3                       # 2024-01-19 began late: not full
    t2 = _segments_from(k[KCOLS + ["seg"]], "DLX", hb2)
    assert t2.last_full_day.iloc[-1] == pd.Timestamp("2024-01-18")
    t3 = _segments_from(k[KCOLS + ["seg"]], "DLX", None)                    # no intraday bars: second-to-last day
    assert t3.last_full_day.iloc[-1] == pd.Timestamp("2024-01-19")
    return ("delisting value = VWAP (quote volume / volume) of the last day with trading in hours 00 and 23, x 0.70; "
            "last trade x 0.70, 0% and 100% haircuts as sensitivities")


def _kline_csv(t: pd.DatetimeIndex, trades) -> bytes:
    """A spot kline CSV as the archive prints it (12 columns, no header, ms before 2025, us from 2025)."""
    us = t[0] >= pd.Timestamp("2025-01-01", tz="UTC")
    ot = (t.as_unit("us").asi8 if us else t.as_unit("ms").asi8)
    return "".join(f"{o},1.0,1.0,1.0,1.0,{n},{o + (59_999_999 if us else 59_999)},{n},{n},{n / 2},{n / 2},0\n"
                   for o, n in zip(ot, trades)).encode()


def _t_hour_bounds():
    """_hour_bounds on bars with zero-trade placeholders; the minute of the last trade (refinement and archive read)."""
    days = pd.date_range("2024-01-01", "2024-01-20", freq="D", tz="UTC")
    k = pd.DataFrame({"open_time": days, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 24.0,
                      "quote_volume": 2400.0, "trades": 240, "taker_buy_quote": 12.0, "seg": 0})
    k.loc[17, ["quote_volume", "volume"]] = [900.0, 10.0]                   # 2024-01-18: VWAP 90 (last full day)
    k.loc[18, ["quote_volume", "volume"]] = [1100.0, 10.0]                  # 2024-01-19: VWAP 110 (trading to 05:59)
    # bars: 2024-01-19 trades to 05:59, then zero-trade placeholders (OHLC = prior close) to 23:59; 2024-01-20 trades to
    # 02:41 (the last trade), placeholders to 02:59, then nothing (delisted)
    mins = pd.date_range(days[0], days[-1] + pd.Timedelta("2h59min"), freq="min")
    tr = np.full(len(mins), 7)
    tr[(mins >= days[-2] + pd.Timedelta("6h")) & (mins < days[-1])] = 0
    tr[mins > days[-1] + pd.Timedelta("2h41min")] = 0
    m1b = pd.DataFrame({"open_time": mins, "trades": tr})
    h1b = m1b.groupby(m1b.open_time.dt.floor("h")).trades.sum().reset_index()
    out = []
    for name, bars, sub in (("1h", h1b, "h1_spot"), ("1m", m1b, "m1_spot")):
        with _scratch_out() as o:
            (o / sub).mkdir(parents=True)
            bars.to_parquet(o / sub / "DLYUSDT.parquet")
            hb = _hour_bounds("DLY")
        assert hb.at[pd.Timestamp("2024-01-19"), "h_last"] == 5 and (hb.t_res == name).all()   # placeholders ignored
        t = _segments_from(k, "DLY", hb)
        assert t.kind.iloc[-1] == "delisting" and t.last_full_day.iloc[-1] == pd.Timestamp("2024-01-18")
        assert abs(t.vwap_last_full_day.iloc[-1] - 90.0) < 1e-12 and t.last_trade_res.iloc[-1] == name
        want = "2024-01-20 02:00" if name == "1h" else "2024-01-20 02:41"
        assert t.last_trade_time.iloc[-1] == pd.Timestamp(want, tz="UTC"), t.last_trade_time.iloc[-1]
        out.append(hb)
    hb1 = out[0]
    # refinement of the hourly table: the minute is kept only inside the last traded hour; None keeps the hour; a
    # segment ending at the data end (censored) is not looked up
    calls = []
    for got, want, res in (("2024-01-20 02:41", "2024-01-20 02:41", "1m"),
                           ("2024-01-20 03:10", "2024-01-20 02:00", "1h"), (None, "2024-01-20 02:00", "1h")):
        fetch = (lambda d, g=got: calls.append(d) or (pd.Timestamp(g, tz="UTC") if g else None))
        t = _segments_from(k, "DLY", _refine_last("DLY", k, hb1, fetch=fetch, end="2026-11-17"))
        assert t.last_trade_time.iloc[-1] == pd.Timestamp(want, tz="UTC") and t.last_trade_res.iloc[-1] == res
    assert calls == [pd.Timestamp("2024-01-20")] * 3
    assert _refine_last("DLY", k, hb1, fetch=calls.append, end="2024-01-20") is not None and len(calls) == 3
    # the archive read: daily zip absent, monthly zip (other days included) gives 02:41; cached; network errors are not
    zips = []

    def fake_zip(key, need_sum=False):
        zips.append(key)
        if "/daily/" in key:
            return None, False
        sel = (mins >= days[-2]) & (mins < days[-1] + pd.Timedelta("3h"))
        return _kline_csv(mins[sel], tr[sel]), True

    def down(key, need_sum=False):
        raise IOError("unreachable")
    with _scratch_out() as o, _patched(_get_zip=fake_zip):
        a = _last_traded_minute("DLYUSDT", "2024-01-20")
        b = _last_traded_minute("DLYUSDT", pd.Timestamp("2024-01-20 05:00", tz="UTC"))
        rec = _load_json(o / "ref" / "last_minute.json")
        with _patched(_get_zip=down):
            c = _last_traded_minute("DLYUSDT", "2024-01-19")
        rec2 = _load_json(o / "ref" / "last_minute.json")
    assert a == b == pd.Timestamp("2024-01-20 02:41", tz="UTC") and len(zips) == 2 and c is None
    assert rec["DLYUSDT|2024-01-20"]["zip"].endswith("2024-01.zip") and set(rec2) == {"DLYUSDT|2024-01-20"}
    # spot files from 2025 carry microseconds
    t25 = pd.date_range("2025-03-01", periods=120, freq="min", tz="UTC")
    with _scratch_out(), _patched(_get_zip=lambda key, need_sum=False: (_kline_csv(t25, [3] * 100 + [0] * 20), True)):
        assert _last_traded_minute("XUSDT", "2025-03-01") == t25[99]
    return ("last full trading day and last trade from bars with trades > 0 (zero-trade placeholders ignored, hourly "
            "and 1m files); the minute of the last trade from the archive's 1m zip (daily, else monthly; ms and us "
            "files), kept only inside the last traded hour, cached, not cached on network errors")


def _t_inherit():
    lst = _inherit_listing({"MATIC": "2019-04", "POL": "2024-09", "LUNA": "2020-08", "LUNA2": "2020-08",
                            "MKR": "2020-07", "SKY": "2025-09", "BTT": "2019-01", "BTTC": "2022-01",
                            "AGIX": "2021-06", "OCEAN": "2020-08", "FET": "2019-02"})
    assert lst["POL"] == "2019-04" and lst["SKY"] == "2020-07" and lst["BTTC"] == "2019-01"
    assert lst["FET"] == "2019-02" and lst["LUNA2"] == "2022-05" and lst["LUNA"] == "2020-08"
    months = _months("2021-01", "2025-06")
    rows = []
    for m in months:
        if m <= "2024-09":
            rows.append(dict(month=m, coin="MATIC", rank=10.0))
        if m >= "2024-11":
            rows += [dict(month=m, coin="POL", rank=30.0), dict(month=m, coin="XPOL", rank=30.0)]
        if m <= "2022-05":
            rows.append(dict(month=m, coin="LUNA", rank=3.0))
        if m >= "2022-07":
            rows.append(dict(month=m, coin="LUNA2", rank=5.0))
    rk = pd.DataFrame(rows)
    rk["sym"] = rk.coin + "USDT"
    for c in ("adv90", "days_traded90", "sd90"):
        rk[c] = 1.0
    rk["backstop"] = False
    lst["XPOL"] = "2024-09"
    u = _universes(rk, "2023-01", "2025-06", lst, ["POL"]).set_index(["month", "coin"])
    r = u.loc[("2024-11", "POL")]
    assert r.U_B and r.listing_age_months == _mi("2024-11") - _mi("2019-04") and r.rank_med12 == 10.0 and r.U_Q1
    assert r.U_C and not r.U_A
    x = u.loc[("2024-11", "XPOL")]
    assert x.U_B and x.rank_med12 == UNRANKED and not x.U_Q1 and not x.U_Q1_12 and x.listing_age_months == 2
    # the successor's own rank takes over: by 2025-06 the 12-month window holds MATIC 2024-07..09 (10), 2024-10
    # unranked (999) and POL 2024-11..2025-06 (30)
    assert u.loc[("2025-06", "POL")].rank_med12 == 30.0
    u2 = _universes(rk, "2022-06", "2023-12", lst, []).set_index(["month", "coin"])
    for m in ("2022-07", "2022-08", "2023-05"):
        y = u2.loc[(m, "LUNA2")]
        assert not y.U_Q1 and y.listing_age_months == _mi(m) - _mi("2022-05")
    assert u2.loc[("2022-08", "LUNA2")].rank_med12 == UNRANKED            # LUNA's ranks are not inherited
    y = u2.loc[("2023-06", "LUNA2")]
    assert y.rank_med12 == 5.0 and y.listing_age_months == 13 and y.U_Q1_12 and not y.U_Q1
    return ("successors inherit the listing month (MATIC->POL, MKR->SKY, BTT->BTTC; FET keeps its own older one) and "
            "the rank history (POL in U-Q1 in its first ranked month; the same coin without a predecessor is not); "
            "ticker reuse (LUNA2) restarts both")


def _t_backstop():
    n = 200
    parts = [_synth("STB", "2019-01-01", n, price=1.0, qv=5e9, sd=0.001, seed=20),
             _synth("DEP", "2019-01-01", n, price=1.0, qv=4e9, sd=0.001, seed=21, jumps={"2019-05-20": 0.93}),
             _synth("USDC", "2019-01-01", n, price=1.0, qv=9e9, sd=0.001, seed=22)]
    parts += [_synth(f"C{i}", "2019-01-01", n, qv=1e9 / (i + 1), sd=0.03, seed=30 + i) for i in range(5)]
    a = pd.concat(parts, ignore_index=True)
    a.loc[a.coin == "USDC", "excluded"] = "stablecoin/fiat"
    a = _panel_seg(a)
    rk = _ranks(a, "2019-03", "2019-07")
    st = rk[rk.coin == "STB"]
    assert st.backstop.all() and st["rank"].isna().all() and (st.sd90 < SD_MIN).all()
    assert "USDC" not in set(rk.coin)
    for m in ("2019-04", "2019-05"):                                    # before the depeg: excluded
        assert bool(rk[(rk.month == m) & (rk.coin == "DEP")].backstop.iloc[0])
    # the -7% open move on 2019-05-20 (inside one segment) lifts the 90-day SD above 0.5% from 2019-06 on
    d6 = rk[(rk.month == "2019-06") & (rk.coin == "DEP")].iloc[0]
    assert not d6.backstop and d6.sd90 > SD_MIN and d6["rank"] == 1.0
    r4 = rk[rk.month == "2019-04"].set_index("coin")["rank"]
    assert r4["C0"] == 1 and r4["C4"] == 5
    # independent SD for STB in 2019-04: returns of days 2019-01-01..2019-03-31 window (90 days to 03-31)
    g = a[(a.coin == "STB")].set_index("day").close
    w = g[(g.index >= pd.Timestamp("2019-03-31") - pd.Timedelta("89D")) & (g.index <= "2019-03-31")]
    full = g[(g.index >= pd.Timestamp("2019-03-31") - pd.Timedelta("90D")) & (g.index <= "2019-03-31")]
    r = np.log(full / full.shift()).dropna()
    r = r[r.index >= w.index[0]]
    assert abs(st[st.month == "2019-04"].sd90.iloc[0] - r.std(ddof=1)) < 1e-12
    return ("stablecoin backstop: 90-day SD < 0.5% excluded before ranking (listed stablecoins never ranked); a "
            "depeg inside the window lifts the SD and re-admits the coin; SD matches an independent computation")


def _t_point_in_time():
    rng = np.random.default_rng(5)
    parts = []
    for i in range(40):
        start = pd.Timestamp("2017-09-01") + pd.Timedelta(days=int(rng.integers(0, 700)))
        n = int(rng.integers(150, 1500))
        parts.append(_synth(f"P{i:02d}", str(start.date()), n, qv=float(10 ** rng.uniform(5, 9)), seed=100 + i,
                            drop=tuple(str((start + pd.Timedelta(days=int(d))).date())
                                       for d in rng.integers(5, n, 2))))
    a = _panel_seg(pd.concat(parts, ignore_index=True))
    lst = a.groupby("coin").day.min().dt.strftime("%Y-%m").to_dict()
    base = _universes(_ranks(a, "2017-09", "2021-12"), "2019-01", "2021-12", lst, ["P01", "P02"])
    cols = ["U_B", "U_Q1", "U_Q1_12", "U_Q1_xm", "U_C", "U_A", "rank", "rank_med12", "listing_age_months"]
    checked = 0
    for cut in ("2019-06", "2020-03", "2020-11", "2021-07"):
        t = pd.Timestamp(cut + "-01")
        b = a.copy()
        late = b.day >= t
        b.loc[late, "quote_volume"] *= rng.uniform(0.01, 100, late.sum())
        b.loc[late, ["open", "high", "low", "close"]] *= rng.uniform(0.5, 1.5, (late.sum(), 1))
        b = b[~(late & (rng.uniform(size=len(b)) < 0.2))]                 # delete 20% of the later bars
        b = b[~((b.coin == "P03") & (b.day >= t))]                        # a coin stops trading at the cut
        new = _synth("PNEW", cut + "-01", 200, qv=1e12, seed=999)
        b = _panel_seg(pd.concat([b, new], ignore_index=True))
        l2 = dict(lst, PNEW=cut)
        u = _universes(_ranks(b, "2017-09", "2021-12"), "2019-01", "2021-12", l2, ["P01", "P02"])
        x = base[base.month <= cut].set_index(["month", "coin"])[cols]
        y = u[u.month <= cut].set_index(["month", "coin"])[cols]
        assert x.index.equals(y.index) and x.equals(y), cut
        assert not base[base.month > cut].set_index(["month", "coin"])[cols].equals(
            u[u.month > cut].set_index(["month", "coin"])[cols])            # the perturbation does bite later
        checked += len(x)
    return (f"universes point in time: every membership, rank, 12-month median and age for months <= the cut is "
            f"unchanged when later bars are rescaled, deleted, a coin stops and a giant coin lists at the cut "
            f"({checked:,} coin-month rows over 4 cuts)")


def _t_agg():
    us = 1_000_000
    t0 = int(pd.Timestamp("2025-03-01", tz="UTC").value // 1000)
    tr = [(10.0, 1.0, t0 + 5 * us, True), (9.5, 2.0, t0 + 30 * us, True), (9.0, 1.0, t0 + 59 * us, False),
          (9.9, 1.0, t0 + 61 * us, True), (10.5, 3.0, t0 + 62 * us, True), (9.0, 4.0, t0 + 150 * us, True),
          (8.0, 1.0, t0 + 200 * us, True)]
    x = {"price": np.array([p for p, _, _, _ in tr]), "qty": np.array([q for _, q, _, _ in tr]),
         "time": np.array([t for _, _, t, _ in tr]), "bm": np.array([b for _, _, _, b in tr])}
    w = pd.DataFrame({"key": ["a", "b"], "L": [10.0, 9.6], "t0": [t0, t0 + 60 * us], "t1": [t0 + 180 * us, t0 + 180 * us]})
    r = _agg_reduce(x, w).set_index(["key", "minute"])
    m0, m1_, m2 = t0, t0 + 60 * us, t0 + 120 * us
    # oracle by hand: window a (L = 10, [0, 180s)): minute 0: 9.5 x 2 (10.0 not < L; 9.0 is buyer-initiated);
    # minute 1: 9.9; minute 2: 9.0 x 4 (8.0 at 200s is outside); window b (L = 9.6, [60s, 180s)): minute 2: 9.0 x 4
    assert abs(r.loc[("a", m0)].sell_below_usd - 19.0) < 1e-12 and r.loc[("a", m0)].n_trades == 1
    assert abs(r.loc[("a", m1_)].sell_below_usd - 9.9) < 1e-12
    assert abs(r.loc[("a", m2)].sell_below_usd - 36.0) < 1e-12 and r.loc[("a", m2)].sell_below_qty == 4.0
    assert ("b", m1_) not in r.index and abs(r.loc[("b", m2)].sell_below_usd - 36.0) < 1e-12
    for head, scale in ((True, 1), (False, 1000)):                         # header / no header; us / ms timestamps
        csv = ("agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker,"
               "is_best_match\n" if head else "")
        for i, (pp, q, t, b) in enumerate(tr):
            tt = t if scale == 1 else t // 1000
            csv += f"{i},{pp},{q},{i},{i},{tt},{'true' if head else 'True'},{'true' if head else 'True'}\n".replace(
                "true" if head else "True", ("true" if head else "True") if b else ("false" if head else "False"), 1)
        y = _agg_read(csv.encode())
        assert np.array_equal(y["time"], x["time"]) and np.array_equal(y["bm"], x["bm"])
        assert np.allclose(y["price"], x["price"]) and np.allclose(y["qty"], x["qty"])
    # "strictly below L" on decimal prices (coding choice 13): L = floor(x / tau) * tau sits one ULP above '3880.20',
    # so three sells printed at the level must not count; the one a tick below does
    L = np.floor(3880.209761368103 / 0.01) * 0.01
    assert L > 3880.2
    xa = {"price": np.array([3880.2, 3880.2, 3880.2, 3880.19]), "qty": np.array([100.0, 100.0, 100.0, 1.0]),
          "time": t0 + np.arange(1, 5) * us, "bm": np.ones(4, bool)}
    ra = _agg_reduce(xa, pd.DataFrame({"key": ["at"], "L": [L], "t0": [t0], "t1": [t0 + 60 * us]}))
    assert len(ra) == 1 and ra.n_trades.iloc[0] == 1 and abs(ra.sell_below_usd.iloc[0] - 3880.19) < 1e-9
    # random levels floored to random ticks, prints at the level's decimal price, one tick below and one tick above:
    # only the print a tick below counts (oracle: the decimal strings). Relative ticks 1e-8..1e-2 (Binance spot's
    # smallest is about 1e-7: BTC with a $0.01 tick)
    rng = np.random.default_rng(13)
    pr, ts, rows = [], [], []
    for i in range(3000):
        dec = int(rng.integers(0, 9))
        tau = 10.0 ** -dec
        lv = np.floor(float(10 ** rng.uniform(-5, 5)) / tau) * tau
        if not 1e-8 <= tau / max(lv, tau) <= 1e-2:
            continue
        s0 = f"{lv:.{dec}f}"
        pr += [float(s0), float(f"{float(s0) - tau:.{dec}f}"), float(f"{float(s0) + tau:.{dec}f}")]
        b0 = t0 + i * 60 * us
        ts += [b0 + us, b0 + 2 * us, b0 + 3 * us]
        rows.append(dict(key=f"r{i}", L=lv, t0=b0, t1=b0 + 60 * us, want=pr[-2], above=lv > float(s0)))
    w = pd.DataFrame(rows)
    xr = {"price": np.array(pr), "qty": np.ones(len(pr)), "time": np.array(ts), "bm": np.ones(len(pr), bool)}
    rr = _agg_reduce(xr, w).set_index("key")
    assert len(rr) == len(w) and (rr.n_trades == 1).all()
    assert np.array_equal(rr.loc[w.key, "sell_below_usd"].to_numpy(), w.want.to_numpy())
    # the cache: rows reduced under the raw-float rule (v1, unversioned keys) are recomputed, never reused, and dropped
    csv = "".join(f"{i},{p},{q},{i},{i},{t},True,True\n" for i, (p, q, t) in
                  enumerate(((3880.2, 100.0, t0 + us), (3880.2, 100.0, t0 + 2 * us), (3880.19, 1.0, t0 + 3 * us))))
    calls = []

    def fake_zip(key, need_sum=False):
        calls.append(key)
        return csv.encode(), True
    s0, e0 = pd.Timestamp(t0 * 1000, tz="UTC"), pd.Timestamp((t0 + 60 * us) * 1000, tz="UTC")
    win = pd.DataFrame({"L": [L], "start": [s0], "end": [e0]})
    with _scratch_out() as o, _patched(_get_zip=fake_zip):
        f = o / "agg_cap" / "XCAP" / "2025-03-01.parquet"
        k1 = f"{float(L)!r}|{t0}|{t0 + 60 * us}"                         # v1 key holding the raw-float answer
        _write_parquet(pd.DataFrame({"key": [k1], "minute": [t0], "sell_below_usd": [3 * 100 * 3880.2 + 3880.19],
                                     "sell_below_qty": [301.0], "n_trades": [4]}), f)
        _save_json(f.with_suffix(".json"), {"missing": False, "keys": [k1]})
        c1 = agg_capacity("XCAP", "2025-03-01", win)
        c2 = agg_capacity("XCAP", "2025-03-01", win)                      # served from the v2 cache: no download
        left = pd.read_parquet(f)
    assert len(calls) == 1 and len(c1) == len(c2) == 1 and abs(c1.sell_below_usd.iloc[0] - 3880.19) < 1e-9
    assert c2.sell_below_usd.iloc[0] == c1.sell_below_usd.iloc[0] and set(left.key) == {_wkey(L, t0, t0 + 60 * us)}
    return ("capacity: seller-initiated notional strictly below L per minute inside [start, end) matches a hand "
            "oracle; the reader handles header / no header and ms / us timestamps; prints at L's own tick never count "
            f"(L one ULP above '3880.20'; {len(w):,} random tick-floored levels, {int(w.above.sum())} of them above "
            "their decimal value, match the decimal-string oracle); cached rows of the raw-float rule are recomputed")


def _t_usd():
    """usdt_usd_hourly: the same frame (open_time, datetime64[ns, UTC]) rebuilt and read from its cache."""
    t = pd.date_range(pd.Timestamp(END, tz="UTC") - pd.Timedelta("1D"), periods=48, freq="h")
    with _scratch_out() as o:
        (o / "usd").mkdir(parents=True)
        for s, px, qv in (("BUSDUSDT", 1.0, 1e6), ("USDCUSDT", 0.998, 1e6), ("TUSDUSDT", 1.004, 1e3)):
            q = np.full(48, qv)
            q[5] = 5e3 if s == "TUSDUSDT" else 1e3                       # hour 5: none liquid, TUSD the most traded
            pd.DataFrame({"open_time": t.astype("datetime64[ms, UTC]"), "open": px, "high": px, "low": px,
                          "close": px, "volume": q, "quote_volume": q, "trades": 10,
                          "taker_buy_quote": q / 2}).to_parquet(o / "usd" / f"h1_{s}.parquet")
        built = usdt_usd_hourly(rebuild=True)
        cached = usdt_usd_hourly()
    for u in (built, cached):
        assert str(u.index.dtype) == NS and u.index.name == "open_time", u.index.dtype
    pd.testing.assert_frame_equal(built, cached)
    v = cached.usd_per_usdt.reindex(t[[3, 5, 30]])                       # UTC-aware hours, as fills are stamped
    assert np.isfinite(v).all() and abs(v.iloc[0] - 1 / 0.999) < 1e-12 and abs(v.iloc[1] - 1 / 1.004) < 1e-12
    assert cached.source.iloc[5] == "most traded: TUSD" and cached.n_liquid.iloc[3] == 2
    assert cached.loc[t[30], "usd_per_usdt"] == v.iloc[2]
    return ("USDT/USD proxy: rebuilt and cached frames identical, index open_time datetime64[ns, UTC]; median of the "
            "liquid stablecoins, the most traded one when none is liquid; reindex on UTC fill hours is finite")


def _oracle_last_full_day(coin: str, first_day, last_day):
    """The last day in [first_day, last_day] with a traded bar (trades > 0) in hour 00 and one in hour 23, read
    straight from the bar files (separate code from _hour_bounds / _segments_from); None without intraday bars."""
    sym = coin_sym(coin)[0]
    f1 = OUT / "m1_spot" / f"{sym}.parquet"
    src = [f1] if f1.exists() else [p for p in (OUT / "h1_spot_pre" / f"{sym}.parquet",
                                               OUT / "h1_spot" / f"{sym}.parquet") if p.exists()]
    if not src:
        return None
    x = pd.concat([pd.read_parquet(p, columns=["open_time", "trades"]) for p in src], ignore_index=True)
    ts = pd.to_datetime(x.open_time[x.trades > 0], utc=True).dt.tz_convert(None)
    d, h = ts.dt.normalize(), ts.dt.hour
    full = sorted(z for z in set(d[h == 0]) & set(d[h == 23]) if first_day <= z <= last_day)
    return full[-1] if full else None


def _t_real(lines):
    """Real-data invariants (counts only; no price after any fill is read)."""
    a = d1_panel()
    dup = a.duplicated(["sym", "day"]).sum()
    srt = all(g.day.is_monotonic_increasing for _, g in a.groupby("coin"))
    ohlc = int(((a.low > a[["open", "close"]].min(axis=1)) | (a.high < a[["open", "close"]].max(axis=1))).sum())
    lines.append(f"daily panel: {len(a):,} rows, {a.sym.nunique()} pairs, {a.day.min().date()}..{a.day.max().date()}; "
                 f"duplicates {dup}; sorted {srt}; OHLC violations {ohlc}; segment boundaries "
                 f"{int((a.groupby('coin').seg.max().clip(lower=0)).sum())}")
    assert dup == 0 and srt
    for name in ("d1_full", "m1", "h1_pre", "usd", "mark", "perp1h", "index1d"):
        st = _load_json(OUT / "stats" / f"{name}.json")
        if not st:
            continue
        v = [x for x in st.values() if isinstance(x, dict) and "zips" in x]
        z, ver, ws = sum(x["zips"] for x in v), sum(x["verified"] for x in v), sum(x.get("with_checksum", 0) for x in v)
        fl = sum(len(x.get("failed", [])) for x in v)
        lines.append(f"stats/{name}: {len(v)} series, zips {z:,}, listed with .CHECKSUM {ws:,}, sha256 verified "
                     f"{ver:,}, failed {fl}")
        assert ver == ws and fl == 0, name
    mj = sorted((OUT / "metrics").glob("*.json"))
    if mj:
        dv = [v for f in mj for v in _load_json(f).get("days", {}).values()]
        lines.append(f"metrics: {len(mj)} coins, days fetched with a verified .CHECKSUM {dv.count('ok'):,}, without "
                     f"{sum(v == 'ok (no checksum)' for v in dv)}, missing from the archive {dv.count('missing'):,}")
        assert not any(v == "ok (no checksum)" for v in dv)
    files = sorted((OUT / "m1_spot").glob("*.parquet"))
    bad = []
    rows = 0
    for f in files:
        t = pd.read_parquet(f, columns=["open_time"]).open_time
        rows += len(t)
        if not t.is_monotonic_increasing or t.duplicated().any() or (t.dt.second != 0).any():
            bad.append(f.stem)
    lines.append(f"m1 cache: {len(files)} files, {rows:,} bars, unsorted/duplicated/off-grid: {bad or 'none'}")
    assert not bad
    cov = m1_coverage([s for s in ("BTCUSDT", "DOGEUSDT", "NEARUSDT", "HBARUSDT", "ONEUSDT")
                       if (OUT / "m1_spot" / f"{s}.parquet").exists()])
    lines.append(f"m1 vs 1d kline on the builder's unresolved days ({', '.join(cov.sym)}): "
                 f"{int(cov.unresolved_days.sum())} days differ with placeholder minutes, "
                 f"{int(cov.diff_traded_only.sum())} once zero-trade minutes are dropped; minutes on days without a "
                 f"daily kline {int(cov.seg_minus1.sum())}")
    assert int(cov.diff_traded_only.sum()) == 0 and int(cov.seg_minus1.sum()) == 0
    u = universes()
    assert not u.duplicated(["month", "coin"]).any()
    for c in ("U_Q1", "U_Q1_12", "U_A", "U_C"):
        assert not (u[c] & ~u.U_B).any(), c
    assert not (u.U_Q1 & ~u.U_Q1_12).any() and not (u.U_Q1_xm & ~u.U_Q1).any()
    for m, g in u.groupby("month"):
        rr = np.sort(g["rank"].to_numpy())
        assert np.array_equal(rr, np.arange(1, len(rr) + 1)), m
    nb = u.groupby("month").U_B.sum()
    lines.append(f"universes: {u.month.nunique()} months; U-B size min {nb.min()} max {nb.max()}; ranks 1..n each "
                 f"month; U-Q1 within U-Q1-12 within U-B; U-A and U-C within U-B")
    # point in time on real data: recompute three months from the panel cut at the month start
    full = universes()
    for m in ("2021-05", "2022-11", "2025-10"):
        cut = a[a.day < pd.Timestamp(m + "-01")]
        rk = _ranks(cut, RANK_FIRST, m)
        um = _universes(rk, m, m, first_listing(), u_c_coins())
        x = full[full.month == m].set_index("coin")[["U_B", "U_Q1", "U_Q1_12", "U_C", "U_A", "rank", "rank_med12"]]
        y = um.set_index("coin")[x.columns]
        assert x.sort_index().equals(y.sort_index()), m
    lines.append("universes on real data: 2021-05, 2022-11 and 2025-10 recomputed from bars before the month: identical")
    # futures: daily and monthly index zips agree where both exist (one sample coin-month)
    um = um_contract("NEAR")
    if um is not None:
        con, mult = um
        b1, _ = _get_zip(f"data/futures/um/monthly/indexPriceKlines/{con}/1m/{con}-1m-2021-05.zip")
        b2, _ = _get_zip(f"data/futures/um/daily/indexPriceKlines/{con}/1m/{con}-1m-2021-05-19.zip", True)
        if b1 is not None and b2 is not None:
            x = _fut_parse(b1, "index", mult)
            x = x[x.open_time.dt.strftime("%Y-%m-%d") == "2021-05-19"].reset_index(drop=True)
            y = _fut_parse(b2, "index", mult).reset_index(drop=True)
            same = len(x) == len(y) and np.allclose(x[["open", "high", "low", "close"]].to_numpy(),
                                                     y[["open", "high", "low", "close"]].to_numpy(), rtol=0, atol=0)
            lines.append(f"index 1m NEAR 2021-05-19: monthly zip {len(x)} rows, daily zip {len(y)} rows, identical "
                         f"prices {same}, updates equal {bool(len(x) == len(y) and (x.updates == y.updates).all())}")
    # capacity pipeline against the inventory's independently parsed aggTrades (fetch_stinkbid_data._agg_frame), with
    # a second level AT a printed sell price and a third one ULP above it (must count none of the prints at it)
    ev = OUT / "events" / "2021-05-19_NEARUSDT_spot.parquet"
    if ev.exists():
        e = pd.read_parquet(ev)
        e["time"] = _ns(e.time)
        L = float(e.price.quantile(0.2))
        st0 = pd.Timestamp("2021-05-19 12:00", tz="UTC"); en0 = pd.Timestamp("2021-05-19 14:00", tz="UTC")
        sw = (e.time >= st0) & (e.time < en0) & e.is_buyer_maker
        vc = e.price[sw].value_counts()
        ps = float(vc[vc.index < e.price[sw].median()].idxmax())         # the most printed sell price below the median
        got = agg_capacity("NEAR", "2021-05-19", pd.DataFrame({"L": [L, ps, float(np.nextafter(ps, np.inf))],
                                                                 "start": st0, "end": en0}), cache=False)
        g0, tot = got[got.wid == 0], got.groupby("wid").sell_below_usd.sum()
        m = sw & (e.price < L * (1 - CAP_REL))
        ref = (e.price * e.qty)[m].groupby(e.time[m].dt.floor("min")).sum()
        ok = len(g0) == len(ref) and np.allclose(g0.sell_below_usd.to_numpy(), ref.to_numpy(), rtol=1e-12)
        n_at = int((sw & (e.price == ps)).sum())
        ok_ulp = bool(tot[1] == tot[2] and np.isclose(tot[1], float((e.price * e.qty)[sw & (e.price < ps)].sum()),
                                                       rtol=1e-12) and n_at > 0)
        lines.append(f"capacity NEAR 2021-05-19 12-14h below the 20th-percentile price: {len(g0)} minutes, total "
                     f"${g0.sell_below_usd.sum():,.0f}; matches the inventory's parse: {ok}; a level one ULP above a "
                     f"printed sell price ({n_at} sells at it) counts none of them: {ok_ulp}")
        assert ok and ok_ulp
    rh = rh_pairs()
    hype = rh.set_index("coin").loc["HYPE"]
    assert len(rh) == 93 and rh.tradable.sum() == 92 and hype.price_tick == 0.001 and hype.max_order_size == 7000
    lines.append(f"Robinhood catalog: {len(rh)} pairs, {rh.tradable.sum()} tradable; U-C coins {len(u_c_coins())}")
    # T-bill: rf_annual_pct's source is FRED DTB3; its continuation leaves every earlier value the function's own
    from analysis_2026 import regime_switch as rs
    base, ext, dgs = _rf_base(), _fred(TBILL_EXT), _fred(TBILL_PREREG)
    j = pd.concat([base, ext], axis=1, keys=["base", "ext"], sort=True).dropna().loc["2019-10-01":]
    dd = (j.base - j.ext).abs()
    assert len(j) > 1500 and (dd < 0.005).mean() > 0.99 and dd.max() <= 0.0101
    days = pd.date_range("2019-10-01", base.index[-1], freq="D")
    rs._RF_CACHE["rf"] = base
    own = rs.rf_annual_pct(days)
    assert np.array_equal(own, tbill_daily(days).to_numpy())
    t26 = tbill_daily(pd.date_range("2026-01-01", END, freq="D"))
    x = pd.Timestamp("2026-11-02")
    tb = tbill_daily(pd.DatetimeIndex(["2020-03-02", "2023-06-01", "2026-11-02"]))
    assert np.isfinite(tb).all() and ((tb >= 0) & (tb <= 10)).all() and tb.iloc[-1] == ext[x] and dgs[x] == 4.21
    assert t26.nunique() > 20 and base.index[-1] < pd.Timestamp("2026-01-01")
    lines.append(f"T-bill: rf_annual_pct's source = FRED {TBILL_EXT} on {(dd < 0.005).mean():.1%} of {len(j):,} days "
                 f"since 2019-10 (max |diff| {dd.max():.2f}); through {base.index[-1].date()} tbill_daily = the "
                 f"function's own values; 2026: {t26.nunique()} distinct daily values {t26.min():.2f}.."
                 f"{t26.max():.2f}% (was a flat 3.70%); " + ", ".join(f"{d.date()} {v:.2f}%" for d, v in tb.items()) +
                 f" (prereg §4 states 4.21% that day: FRED {TBILL_PREREG} = {dgs[x]:.2f}%, a different quote basis)")
    f = OUT / "usd" / "usdt_usd_hourly.parquet"
    if f.exists():
        uu = usdt_usd_hourly()
        frac = float(((uu.usd_per_usdt > 0.97) & (uu.usd_per_usdt < 1.03)).mean())
        hrs = pd.DatetimeIndex(["2021-05-19 13:00", "2022-05-12 03:00", "2025-10-10 21:00"], tz="UTC")
        fin = bool(np.isfinite(uu.usd_per_usdt.reindex(hrs)).all())
        lines.append(f"USDT/USD proxy: {len(uu):,} hours, share within 3% of 1: {frac:.4f}; unique sorted "
                     f"{uu.index.is_monotonic_increasing and not uu.index.duplicated().any()}; cached index "
                     f"{uu.index.dtype}; finite on UTC-aware lookups: {fin}")
        assert frac > 0.99 and str(uu.index.dtype) == NS and fin
    # segment ends: last full day (trading in hours 00 and 23) against separate code; minute of the last trade
    sg = pd.read_csv(OUT / "ref" / "segments.csv", parse_dates=["first_day", "last_day", "last_full_day"])
    b = sg[sg.kind != "data_end"]
    cs = sorted(set(b.coin))
    with cf.ThreadPoolExecutor(8) as ex:
        now = pd.concat(list(ex.map(segments, cs)), ignore_index=True)
    now = now[now.kind != "data_end"].set_index(["coin", "seg"]).sort_index()
    bb_ = b.set_index(["coin", "seg"]).sort_index()
    assert now.index.equals(bb_.index)
    # daily-only segments (no cached 1m or 1h bars: successors outside U-B such as VIC, Addendum 1 A1.1) have no
    # last-trade minute and take the documented fallback (the second-to-last day); every other end is checked fully
    daily = now.last_trade_res.isna()
    assert (now.loc[daily, "full_day_source"] == "fallback: second-to-last day").all()
    assert bb_.loc[daily, "last_trade_time"].isna().all() and now.loc[daily, "last_trade_time"].isna().all()
    nd, bd = now[~daily], bb_[~daily]
    assert (pd.to_datetime(bd.last_trade_time, utc=True) == nd.last_trade_time).all()     # the CSV is current
    assert (bd.last_full_day == nd.last_full_day).all() and (bd.last_trade_res == nd.last_trade_res).all()
    assert (bb_.loc[daily, "last_full_day"] == now.loc[daily, "last_full_day"]).all()
    orc = [_oracle_last_full_day(c, r.first_day, r.last_day) for (c, _), r in nd.iterrows()]
    lt = nd.last_trade_time.dt.tz_convert(None)
    assert all(o == d for o, d in zip(orc, nd.last_full_day)) and (nd.last_trade_res == "1m").all()
    assert (lt.dt.normalize() == nd.last_day).all()
    lines.append(f"segment ends before {END}: {len(now)}; with intraday bars {len(nd)}: last full day equals separate "
                 f"code on all, last trade time at minute resolution on all (minute :59 for "
                 f"{int((lt.dt.minute == 59).sum())}); daily-only (second-to-last-day fallback): "
                 f"{', '.join(c for c, _ in now.index[daily]) or 'none'}; ref/segments.csv current")


def selftest():
    t0 = time.time()
    lines = []
    for name, fn in (("segments", _t_segments), ("joins", _t_joins), ("delist", _t_delist),
                     ("hour_bounds", _t_hour_bounds), ("inherit", _t_inherit), ("backstop", _t_backstop),
                     ("point_in_time", _t_point_in_time), ("capacity", _t_agg), ("usd", _t_usd)):
        t = time.time()
        msg = fn()
        lines.append(f"PASS {name} ({time.time() - t:.1f}s): {msg}")
        print(lines[-1], flush=True)
    t = time.time()
    real = []
    _t_real(real)
    for x in real:
        print("  " + x, flush=True)
    lines.append(f"PASS real-data invariants ({time.time() - t:.1f}s)")
    print(lines[-1], flush=True)
    print(f"selftest: all passed in {time.time() - t0:.0f}s", flush=True)
    return lines


if __name__ == "__main__":
    main()
