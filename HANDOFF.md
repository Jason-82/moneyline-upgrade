# HANDOFF — trend-indicator research (read this first)

This file lets a new AI instance (or a person) continue the work without
re-deriving anything. It is the authoritative summary. The detailed, chronological
log with every table is `analysis_2026/FINDINGS.md` (read its final "audit
corrections" section — some earlier entries there are wrong). The design for
automated trading is `AGENTIC_TRADING_PLAN.md`.

**Repo:** https://github.com/Jason-82/moneyline-upgrade (**public** — never commit
account numbers, balances or positions).
**Working branch:** `claude/add-price-data-csvs-MTD46` (also the default branch).
**Last updated:** 2026-10-13.

---

## 0. The things you must know before anything else

1. **The indicator is an ATR trailing stop, and it is now replicated exactly.** The
   user's TradingView indicator ("Moneyline", from Ivan on Tech) is a
   reset-on-flip SuperTrend: Wilder ATR(**10**) × **2.0** around **hl2**.
   `analysis_2026/moneyline_ref.py` reproduces it bar for bar (100.000% state
   agreement and 213/213 flips on IWM, where real OHLC exists; consistent with all 23
   exported series). See section 2.
2. **README.md, `src/`, `run_backtest.py`, `scanner.py`, `reports/` and
   `analysis_2026/{run_all,common,strategies_ext,robustness}.py` model the WRONG
   indicator** (an Ichimoku HMA/EMA crossover). Do not cite their results.
3. **Crypto: the DAILY signal works; weekly does not.** Daily beat buy-and-hold on
   return and drawdown on 4 of 5 coins at low costs. **But at Robinhood's crypto
   pricing (~0.95% per side) it only survives on ETH and SOL**; trading via spot ETFs
   (near-zero cost, 1-2 day delay) keeps the edge for ETH/SOL and the drawdown benefit
   for BTC. Filters, confirmations and add-on ATR stops do not robustly help.
4. **Stocks: the signal mostly does not work.** Daily on indices destroys returns;
   weekly on indices is optional crash insurance. TSLA: no. HOOD, CRCL, COIN: too little
   history — results hinge on one or two trades and on fill timing.
5. **This cloud environment has no market-data access** (Yahoo, Alpha Vantage,
   Binance, Kraken, Coinbase, CoinGecko, robinhood.com all blocked → 403). Data came
   from the user's TradingView CSV exports, which hold **close only**.

---

## 1. Who the user is (no personal financial data here)

- Uses TradingView with Ivan on Tech's indicator; reads daily and weekly green/red
  flips. Trades crypto and US stocks on Robinhood. Interested in leverage,
  stop-losses, confirmation filters, a daily scanner, and (latest) **Robinhood Agentic
  Trading with Claude** (see `AGENTIC_TRADING_PLAN.md`).
- Holds concentrated single-stock positions; specifics are deliberately not in this
  public repo — ask the user if they matter.
- Asks sharp "does this add up?" questions. Answer with a reconciliation and a
  decisive table, state caveats once, give a concrete recommendation, and correct
  earlier mistakes plainly.

---

## 2. The indicator

**Export format** (TradingView "Export chart data"):
`time, close, Up Trend, Down Trend, Macro Score Heatmap, Rate Hike, Rate Cut, ATR`

- `Up Trend` populated ⇔ GREEN, `Down Trend` populated ⇔ RED (mutually exclusive);
  the value is the trailing line. GREEN ⇔ close > line on 100% of bars.
- The exported `ATR` column is Wilder RMA(**14**) — a separate plot, *not* the ATR the
  line uses. It lets you recover each day's true range exactly:
  `TR_t = 14·ATR_t − 13·ATR_{t−1}`, and bound the low:
  `low_t ≥ max(close_t, close_{t−1}) − TR_t`.
- `Macro Score Heatmap` is always 1; `Rate Hike`/`Rate Cut` are sparse flags. Unused.

**Exact construction** (`analysis_2026/moneyline_ref.py`, function `moneyline(df)`):

```
atr  = Wilder RMA(10) of true range          (seeded with SMA of first 10 TRs)
lo   = hl2 − 2.0·atr ;  hi = hl2 + 2.0·atr    (hl2 = (high+low)/2)
GREEN: line = max(line[1], lo); if close < line → RED,   line = hi (fresh band)
RED:   line = min(line[1], hi); if close > line → GREEN, line = lo (fresh band)
```

- Differs from TradingView's built-in `ta.supertrend` only on flip bars (restarts at
  the fresh band); `ta.supertrend(2, 10)` agrees on 99.97% of bars.
- Evidence: IWM daily 2011-2025, 3,790 bars: 100.000% state agreement, 213/213 flips
  same day, line error median 0.0004% (verified independently twice). IWM weekly:
  100%, 39/39 flips. Neighbours are clearly worse (ATR14×2 98.2%, ATR10×2.5 87.8%,
  ATR10×3 78.9%). On all 23 crypto/stock exports, inferred hl2 at every ratchet and
  flip bar is consistent with (10, 2.0) and inconsistent with alternatives.
- Requirements for matching the chart: **real highs/lows** (close-only input agrees on
  only 72% of bars), **unadjusted** as-traded prices (dividend-adjusted prices break a
  few flips), **closed bars only**, and ≥150-250 bars of history (the state locks on
  within ~10-45 bars, the line within ~60).
- Same parameters drive daily and weekly charts, stocks and crypto. Weekly bars are
  Monday-labelled (`to_weekly()`).

---

## 3. Data

| folder | contents | notes |
|---|---|---|
| `data/tv_full/` | BTC, ETH, SOL, BNB, ZEC `_1D`/`_1W` | **Primary crypto set.** Uploaded as COINBASE_BTCUSD/ETHUSD/SOLUSD, BINANCE_BNBUSD, BINANCE_ZECUSDT. Daily from BTC 2015-07, ETH 2016-05, BNB 2017-07, ZEC 2019-03, SOL 2021-06, to 2026-08-24. |
| `data/tv_stocks/` | SPX, NDX, IWM, COIN, TSLA, HOOD, CRCL `_1D`/`_1W` | Daily capped at ~2010 by TradingView (~4,054 bars); weekly SPX from 1967, NDX 1985, IWM 2000. |
| `data/tv_export/` | 300-bar crypto exports | Superseded (too short; misleading). |
| `data/crypto2026/` | CoinGecko closes | Wrong-model work only; ZEC's first weeks are garbage. |
| repo root `QQQ/SPY/IWM_historical_data.csv` | yfinance **OHLC**, dividend-adjusted | Only real highs/lows in the repo; used for wick calibration and indicator replication. |
| repo root `btc-usd.csv`, `eth-usd.csv`, `sol-usd-max.csv`, `avax-usd-max.csv`, `BATS_COIN, 1D.csv` | early uploads | Wrong-model work only. |

To get more data: ask the user to export from TradingView after scrolling the chart
back. A **candle-mode export** (open/high/low/close) would allow exact replication
checks on crypto and real intraday-stop tests.

---

## 4. Conventions in valid results

- Long while GREEN, flat while RED; no shorting; no leverage (except the illustrative
  model in `confirmation.py`).
- Fills at the close: **same-bar** primary, **next-bar** as sensitivity. Results can
  move a lot between the two — always check both.
- Costs per side: crypto 0.1% + 5 bp (≈0.15%) unless noted; stocks 1 bp + 2 bp.
  **Robinhood crypto is ~0.95%** — see 5.9.
- Weekly state on daily bars: `shift(1)` then forward-fill (a week counts once closed).
- If the series starts mid-green-run, engines buy on the first bar (not a flip). Because
  `stops.py` drops a few more warmup bars than `run_full.py`, its baselines differ by up
  to ~5 CAGR points (SOL 57.3 vs 62.7) — compare variants only within one engine.
- Stocks "adjusted" view adds dividends to holders and T-bill interest when flat.
- **pandas 3.0 trap:** `.shift()` on a bool Series yields object dtype and `~` becomes
  integer negation (`~False == -1`). Use numpy bool arrays for flip logic.

---

## 5. Current conclusions (real signal)

### 5.1 Crypto daily vs buy & hold — `run_full.py`, `supplementary.py`

| asset | signal | B&H | signal DD | B&H DD | Sharpe | trades | CAGR edge |
|---|---|---|---|---|---|---|---|
| BTC | 40,688% | 28,427% | -55.0% | -83.8% | 1.4 | 75 | +5.5 |
| ETH | 128,237% | 18,003% | -58.1% | -94.0% | 1.4 | 72 | +35.1 |
| SOL | 1,133% | 226% | -67.3% | -96.3% | 1.1 | 39 | +37.0 |
| BNB | 805,945% | 596,293% | -59.8% | -80.3% | 1.5 | 47 | +8.8 |
| ZEC | 1,139% | 1,379% | -87.8% | -94.3% | 0.8 | 54 | -3.4 |

- Same-bar fills at 0.15%/side. **With next-bar fills BTC's return edge disappears**
  (65.3% vs 66.4% CAGR) and ZEC's turns positive; drawdown advantages remain on all.
- BTC's edge is mainly **risk reduction** (1.43× terminal wealth; 29 pts less drawdown).
  ETH and SOL are the real return stories. Reconcile big % totals through CAGR.
- **Recent eras are weaker.** Since 2022: beats B&H on ETH (+26% vs −33%), SOL (+249% vs
  −46%), BNB (+38% vs +35%); roughly matches BTC (+60% vs +67%); trails ZEC. **Since
  2024 it trails B&H on 4 of 5** (only ETH wins). The edge comes from deep bear markets.
- Trades: ~7 per coin per year; win rate 39-53%. **Median losing trade −6% (BTC) to
  −12% (ZEC)**; median of all trades −4% to +1%; worst −20% (ETH) to −43% (ZEC). The
  trailing line is the stop — returns come from a few large winners.

### 5.2 Daily beats weekly (crypto)

Weekly loses to B&H on 4 of 5 coins (BTC 8,206% vs 33,628%; ETH 10,873% vs 20,892%; BNB
29,440% vs 89,665%; ZEC −3%); only SOL wins. Just 4-13 weekly trades per coin.

### 5.3 Confirmation filters — `confirmation.py`

- **Daily AND weekly green** gives up 86% (BTC), 83% (ETH), 98% (BNB), 45% (SOL), 30% (ZEC)
  of terminal wealth; drawdown improves except on BNB. Not worth it.
- Pooled over 287 entries: **breakout** and **weekly-green** confirmations raise hit rate
  (46.7% → 51.8-53.6%) and per-trade geometric gain (9.7% → 12.7-12.9%), but fewer trades
  means lower total return. **Squeeze** filters skip monster runs; **retest** is worst.
  A filter helps only if it does not filter out the few huge runs.
- Leverage (illustrative, close-based, frictionless): breakout confirmation cuts the worst
  in-trade drawdown (−25.8% vs −42.7%), raising survivable leverage from 2.34× to 3.88×;
  with fractional sizing the unfiltered signal still wins. Robinhood agentic accounts have
  no leverage anyway.

### 5.4 Joining a green run late (corrected)

Exit measured at the red-flip close (`supplementary.py`). Geometric mean per trade:

| | at flip | day 1-20 | day 21-50 | day 51+ (runs) |
|---|---|---|---|---|
| BTC | 8.3% | 7.6% | 7.4% | 12.0% (7) |
| ETH | 10.2% | 8.1% | 4.9% | −3.2% (7) |
| SOL | 6.3% | 7.0% | 4.2% | 7.1% (1) |
| BNB | 21.0% | 23.7% | 26.5% | 20.1% (7) |
| ZEC | 4.3% | 2.6% | 14.1% | 18.0% (4) |

Entering within ~3 weeks of a flip earns about the same as entering on the flip.
Later, the evidence is thin and mixed. **An earlier claim that late entry is *better*
was wrong** (it measured exits one bar early).

### 5.5 ATR stop-losses on top of the indicator — `stops.py`, `run_stops.py`

| variant | stop on daily close | resting order w=0.4 | w=0.6 | close, 2022+ |
|---|---|---|---|---|
| fixed 1.5×daily ATR, no re-entry (Ivan's rule) | +2.1 (3/5) | −2.7 (2/5) | −4.9 (1/5) | +4.1 (5/5) |
| fixed 1.5×daily + buy back above entry | +1.8 (4/5) | +1.8 (4/5) | −4.5 (1/5) | +2.7 (5/5) |
| trailing 1.5×daily ATR | **−37.5** | **−39.0** | **−53.8** | −3.3 |
| fixed 1.5×weekly ATR | 0.0 | 0.0 | −1.1 | 0.0 |
| trailing 1.5×weekly ATR | −20.7 | −12.8 | −28.2 | 0.0 |

(Median CAGR edge vs indicator-only; (n/5) = coins improved.) The indicator is already an
ATR stop (~2.4 daily ATR(14) below close at a flip), so a 1.5×ATR stop is a tighter copy.
1.5×weekly ATR ≈ 4-5×daily — wider than the line, so it almost never fires (not
"inconsistent", just pointless). Ivan's fixed stop wins small often but threw away BNB's
Nov-2020 run (+885% → −17%). **Recommendation given: indicator alone.** If a stop is
wanted: fixed 1.5×daily on the close with a buy-back rule (≈neutral), or a 2.5-3×daily
disaster stop. Never trailing 1.5×. Wick calibration from ETF OHLC: w ≈ 0.40.

### 5.6 Stocks and indices — `run_stocks.py` (SPX, NDX, IWM, COIN, TSLA, HOOD, CRCL)

| | daily signal | B&H | weekly signal (adj.) | B&H (adj.) |
|---|---|---|---|---|
| SPX | 3.3% | 12.8% | 8.3% (DD −38.9%) | 10.0% (DD −55.0%) |
| NDX | 8.7% | 18.7% | 13.1% (DD −52.2%) | 15.2% (DD −82.3%) |
| IWM | 3.4% | 10.0% | 5.3% (DD −36.2%) | 8.6% (DD −57.7%) |
| TSLA | 21.1% | 42.3% | 21.4% | 41.4% |

(Daily columns raw CAGR; weekly columns include dividends and cash yield.)

- Daily on indices: 40-46% of trades end within ±2%; profit factor 1.2-1.9 vs 3.4-16 on
  crypto. **Do not trade the daily signal on indices.**
- Weekly on indices = crash insurance: dot-com (NDX +28 pts) and GFC (SPX +29.5) helped;
  Covid too fast; cost 10-20 pts in the 2025-26 rally.
- **COIN** weekly: 15.1% vs −4.0% CAGR, but on **6 trades**, and next-bar fills cut it
  to 4.7%. Fragile. **HOOD**: daily 18.2% vs 16.7%, but 5.6% with next-bar fills; edge is
  2 trades. **CRCL**: 5 daily trades. All three: watch-only.
- Daily stock history starts ~2010 (no 2000-02 or 2008 on daily).

### 5.7 Which assets the signal suits

It needs sustained multi-month trends and deep (−70% to −95%) drawdowns to pay for its
whipsaws: crypto majors. It fails on assets that grind up and mean-revert quickly
(indices) or make their returns in short bursts (TSLA). Survivorship caveat: every asset
tested was chosen after the fact and is still around.

### 5.8 Position-sizing principle

When a personal stop and the indicator's line disagree, **don't move the stop — change the
size**, so the loss to the line is one you can sit through.

### 5.9 Robinhood costs change the crypto answer — `costs.py`

CAGR edge vs B&H by cost per side (full history; B&H pays the cost once):

| | 0.15% | 0.50% | 0.95% (RH default) | spot-ETF proxy, 1-day lag, 0.02% |
|---|---|---|---|---|
| BTC | +5.5 | −2.5 | **−12.2** | +1.8 (DD −61% vs −84%) |
| ETH | +35.1 | +25.4 | +13.5 | +42.9 |
| SOL | +37.0 | +28.6 | +18.4 | +40.3 |
| BNB | +8.8 | −0.8 | **−12.7** | +4.1 |
| ZEC | −3.4 | −10.4 | −18.9 | +3.6 (2-day lag −23.0) |

Robinhood crypto costs ~0.95%/side on the default route; exchange routing is
0.50-0.95% at small volume and only ~0.15% above $250K/month. Since 2022 at 0.95%, only
SOL (+28.7) clearly survives. Spot-ETF route (commission-free; signal from the 24/7
candle, executed next US session) is the practical fix; the proxy uses each coin's own
history because real ETFs only exist since 2024-25.

---

## 6. Superseded — do not cite

Everything on the Ichimoku/HMA/EMA model (baseline/filtered/hybrid, scaled entry,
"daily+weekly keeps 8%", trailing-stop+re-entry, "15% stop", `reports/*`,
`results_daily.csv`, `results_weekly.csv`, `coverage.csv`); the 300-bar weekly results;
the interim "green = close > kijun" proxy (81-91% agreement); "don't chase a daily flip
while weekly is red" (wrong model); "late entry is better" (exit bug); "median losing
trade −1% to −4.5%" (was the median of all trades); FINDINGS' dated "current state"
snapshots (stale and partly wrong).

---

## 7. Bugs found and fixed

- pandas 3.0 bool-shift negation (section 4) — silently broke two ad-hoc forward-return
  studies before being caught.
- Late-entry table exited at the last green close instead of the red-flip close.
- Losing-trade median computed over all trades.
- `stops.py`: wick proxy fired stops at prices that never traded (now clipped to the
  recovered-TR low floor); `run_attribution` paired runs across different windows;
  exposure omitted the open final position.
- Verification practice that caught real problems: independent reimplementation from a
  spec, adversarial code review with refute-or-reproduce, repo-vs-claims audit,
  concentration tests (drop the top 1-2 runs), next-bar fills, era splits.

---

## 8. Automated trading (summary — full design in `AGENTIC_TRADING_PLAN.md`)

- Robinhood Agentic Trading: separate agentic account, MCP server
  `https://agent.robinhood.com/mcp/trading`, approvals **off by default** for Claude
  (turn them on), no margin, no paper trading, no crypto price history in the MCP, ~0.95%
  crypto cost, OAuth re-login every few days.
- Design: deterministic Python computes signals with `moneyline_ref.py` on closed daily
  bars (stocks/ETFs from Robinhood's historicals; crypto from Coinbase candles), sizes by
  distance to the line, and writes an order plan + digest; Claude previews and places the
  orders through the MCP with approvals on; reconcile and alert.
- Every asset must pass a backtest gate (history, after-cost edge, profit factor ≥ 2,
  concentration, fill robustness, era stability, whipsaw) before it is traded.
- Current verdicts: ETH and SOL **trade** (daily, ideally via spot ETFs); BTC trade for
  drawdown control or hold; BNB watch; ZEC exclude; indices hold (optional weekly
  insurance); TSLA hold; COIN/HOOD/CRCL watch.

---

## 9. Open questions and next steps

1. Live checks with the Robinhood MCP: crypto order route and fee; whether
   `get_equity_historicals` returns ≥250 unadjusted daily bars; spot-ETF tradability.
2. Backtest the spot-ETF route on real ETF histories (short) to complement the proxy.
3. Candle-mode TradingView exports for crypto (exact replication check, intraday stops).
4. Walk-forward / out-of-sample testing and a survivorship-aware candidate universe.
5. Portfolio level: correlation-aware sizing across the crypto cluster.
6. README.md still documents the wrong indicator (banner added; full rewrite pending).
7. Some older interactive numbers (crash-window table, HOOD concentration, 20%-sizing
   leverage) have no committed script; recompute before relying on them.

## 10. Environment notes

- `python3` (3.11); install with `python3 -m pip install pandas numpy` (plain `pip`
  targets another interpreter). pandas is unpinned → mind the bool-shift trap.
- Market-data and robinhood.com hosts are blocked here (403) — don't retry; WebSearch
  works. Commit and push; containers are ephemeral.

## 11. File map (valid code)

| file | purpose |
|---|---|
| `AGENTIC_TRADING_PLAN.md` | Robinhood + Claude automated-trading design. |
| `analysis_2026/FINDINGS.md` | Chronological log of every result (see audit corrections at the end). |
| `analysis_2026/moneyline_ref.py` | **Exact indicator from OHLC** (`moneyline`, `supertrend`, `to_weekly`). |
| `analysis_2026/run_full.py` | Real-signal crypto backtests (daily/weekly); `load()`, `bt()`. |
| `analysis_2026/run_stocks.py` | Stocks/indices incl. TSLA/HOOD/CRCL; dividend/cash-yield view. |
| `analysis_2026/supplementary.py` | Losing trades, late entry (corrected), era split, daily-AND-weekly, fill convention. |
| `analysis_2026/costs.py` | Robinhood cost sensitivity. |
| `analysis_2026/confirmation.py` | Confirmation-filter decomposition and leverage model. |
| `analysis_2026/stops.py`, `run_stops.py` | ATR stop-loss study. |
| `analysis_2026/run_tv.py`, `tv.py` | Real signal vs old models on the 300-bar exports (agreement % only). |
| `analysis_2026/results_full.csv`, `results_stocks.csv`, `results_stops.csv`, `results_costs.csv` | Current result tables. |
