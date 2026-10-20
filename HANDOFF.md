# HANDOFF — trend-indicator research (read this first)

This file lets a new AI instance, or a person, continue the work without re-deriving
anything. It is the authoritative summary.

- Detailed chronological log with every table: `analysis_2026/FINDINGS.md`. Read its
  final "audit corrections" sections; several earlier entries there are wrong.
- Automated-trading design: `AGENTIC_TRADING_PLAN.md`.

**Repo:** https://github.com/Jason-82/moneyline-upgrade. It is **public**: never
commit account numbers, balances, positions, order logs or digests.
**Working branch:** `claude/add-price-data-csvs-MTD46` (also the default branch).
**Last updated:** 2026-10-19. Most recent additions:

- `agentic/`: MoneyLine execution on the Robinhood Agentic account (section 8, `agentic/README.md`)
- the Larsson Line (EMA 32/58) long-history study (section 5.19), and a note on the new
  October 2026 MoneyLine read from exports (section 2)
- the 2x S&P + gold study (the other instance's 50% SSO / 50% GLD) and leverage + trend (section 5.18)
- the ten theory-driven strategies (section 5.16)
- a pointer to the other instance's regime-switch study (section 5.17)

Earlier (2026-10-14/15): sections 5.10-5.15, each adversarially audited. The rest was
reviewed by 41 agents on 2026-10-13.

---

## 0. Know these first

1. **The indicator is an ATR trailing stop, replicated exactly.** The user's TradingView
   indicator ("Moneyline", from Ivan on Tech) is a reset-on-flip SuperTrend: Wilder
   ATR(**10**) × **2.0** around **hl2**.
   - `analysis_2026/moneyline_ref.py` reproduces it bar for bar.
   - Evidence (`analysis_2026/replicate.py`): 100.000% state agreement and 213/213
     flips on IWM daily, after rescaling the dividend-adjusted yfinance OHLC to
     TradingView's closes. It is also consistent with 23 of 24 exports (CRCL weekly is
     too short to test).
2. **The obsolete code models the wrong indicator** (an Ichimoku HMA/EMA crossover):
   README's indicator section, `src/`, `run_backtest.py`, `scanner.py`, `reports/`,
   and `analysis_2026/{run_all,common,strategies_ext,robustness}.py`. Do not cite them.
3. **Crypto: the daily signal beats buy-and-hold before costs, but costs and taxes
   decide.**
   - At Robinhood's ~0.95%/side crypto pricing only ETH and SOL survive.
   - Via spot ETFs (near-zero cost, executed in the next NYSE session), ETH and SOL keep
     large edges. BTC slightly trails holding (−3.1 CAGR points) and is clearly behind
     after short-term tax.
   - Gate verdicts (`gate.py`): **ETH = TRADE (via ETF), SOL = PROBATION** (too little
     history), BTC/BNB/ZEC = no signal (hold or skip).
4. **Stocks: the daily signal never passes, singly or as a basket.**
   - **Single stocks:** 0 of 7 tested pass the gate.
   - **Baskets** (section 5.10): picked by past indicator fit at any strictness, walk-forward
     on S&P 500 history 2005–2026. None beat SPY after tax out of sample. Fit carries forward
     only ~7%, and "decent fit" baskets lose clearly.
   - **Scanner:** `screener/scan.py` matches TradingView on every IWM date 2012-2025. It is
     information only.
   - **Indices:** the weekly signal on SPY/QQQ qualifies only as optional crash insurance;
     on IWM it does not.
   - **TSLA:** no.
   - **COIN, HOOD and CRCL:** too little history, and their results hinge on one or two
     trades and on fill timing.
5. **Market data in this cloud environment:**
   - **Blocked (403):** Yahoo, Alpha Vantage, Binance, Kraken, Coinbase, CoinGecko and
     robinhood.com.
   - **Reachable for stocks** (section 3): qlib's US dataset (GitHub release; 2000 to
     2024-04), a daily-updated split-adjusted parquet (2024-08 to today), point-in-time
     S&P 500 membership, and the Robinhood connector's historicals. Large results are saved
     to a file, and history starts 1999-09.
   - **Crypto and the TradingView-based backtests** still rely on the user's close-only
     exports. Those backtests read the exported Up/Down Trend state, not
     `moneyline_ref.py`.
   - **Latest crypto/TV state:** the 2026-08-24 bar, which was still forming when exported
     (see section 3).

---

## 1. Who the user is (no personal financial data here)

- **Windows PC with Git Bash** as the shell: never PowerShell or cmd, never a Mac. Give Git Bash commands
  (see `CLAUDE.md`).
- Uses TradingView with Ivan on Tech's indicator and reads daily and weekly green/red
  flips. Trades crypto and US stocks on Robinhood.
- Has explored leverage, stop-losses, confirmation filters, a daily scanner, and
  **Robinhood Agentic Trading with Claude** (`AGENTIC_TRADING_PLAN.md`).
- Holds concentrated single-stock positions. The specifics are deliberately left out of
  this public repo; ask the user if they matter.
- Asks sharp "does this add up?" questions. Answer with a reconciliation and the
  decisive table, state caveats once, give a concrete recommendation, and correct
  earlier mistakes plainly.

---

## 2. The indicator

**Export format** (TradingView "Export chart data"):
`time, close, Up Trend, Down Trend, Macro Score Heatmap, Rate Hike, Rate Cut, ATR`

- `Up Trend` populated ⇔ GREEN, `Down Trend` populated ⇔ RED. The two are mutually
  exclusive, and the value is the trailing line. GREEN ⇔ close > line.
- The exported `ATR` column is Wilder RMA(**14**). It is a separate plot, not the ATR
  the line uses, but it lets you recover each day's true range exactly:
  `TR_t = 14·ATR_t − 13·ATR_{t−1}`. That bounds the low:
  `low_t ≥ max(close_t, close_{t−1}) − TR_t`.
- `Macro Score Heatmap` is always 1, and `Rate Hike`/`Rate Cut` are sparse flags. Both
  unused.

**Exact construction** (`moneyline_ref.moneyline(df)`):

```
atr  = Wilder RMA(10) of true range          (seeded with SMA of first 10 TRs)
lo   = hl2 − 2.0·atr ;  hi = hl2 + 2.0·atr    (hl2 = (high+low)/2)
GREEN: line = max(line[1], lo); if close < line → RED,   line = hi (fresh band)
RED:   line = min(line[1], hi); if close > line → GREEN, line = lo (fresh band)
```

- It differs from TradingView's built-in `ta.supertrend(2, 10)` only on flip bars, where
  it restarts at the fresh band. The built-in agrees on 99.97% of bars.
- **IWM results** (`replicate.py`):

  | test | state agreement | flips | line error |
  |---|---|---|---|
  | daily, 3,790 bars | 100.000% | 213/213 same day | median 0.0004% |
  | weekly 2010+ | 100% | 38/38 | — |

- **Neighbours are clearly worse:** ATR14×2 98.2%, ATR10×2.5 87.8%, ATR10×3 78.9%,
  close-only input 72.2%.
- **hl2-consistency test** on every export: (10, 2.0) passes 100% of the ratchet and
  flip bars, while the alternatives pass only 4-95%.
- **What you need to match the chart:**
  - real highs and lows
  - **split-adjusted but not dividend-adjusted** prices, which is TradingView's default.
    Raw as-traded prices put a fake crash at every split; dividend-adjusted prices
    break a few flips.
  - closed bars only
  - at least 150-250 bars of history
- The same parameters drive daily and weekly charts, for stocks and crypto alike.
  Weekly bars are Monday-labelled (`to_weekly()`).

**The October 2026 update ("Bullmania™ MoneyLine") is a different indicator.**
`moneyline_ref` and every backtest in this repo use the version above. The new one was
examined on seven fresh daily exports (stocks and crypto; the files are private, not
committed). What is known:

- **Export columns:** it adds `Weekly Dir`, `Daily Dir`, `Confluence`, `ConfirmCount`,
  `Direction` and `MoneyLine Level` (−1 = bull).
- **Confirmation:** `Direction` always equals `Daily Dir`. Every flip (205 of 205) came
  after exactly 5 consecutive closes beyond the level (input "Confirmation Candles = 5").
  The weekly direction is shown, but it does not gate flips.
- **The ATR columns are not MoneyLine plots.**
  - `LA1`, `LA2`, `ATR` and `ATR.1` belong to the **Larsson Line**, a separate paid
    indicator that was on the same charts. Larsson-only exports carry exactly these
    columns.
  - So the MoneyLine's own ATR length is unknown.
  - The Larsson Line's two lines are exactly EMA(32) and EMA(58) of the close (median
    error 0 on three coins). Its red/green colouring is presumably their crossover,
    which is unconfirmed.
  - Only `Direction`, `Daily Dir`, `ConfirmCount` and `MoneyLine Level` were used to
    evaluate the MoneyLine.
- **The level is much wider than ATR10×2, and adaptive.**
  - Measured against Wilder ATR(14) as a yardstick, at a flip it starts about 4-5.5 ATR
    from hl2. Within a trend it ratchets in to about 1-2.5 ATR.
  - The implied multiple falls when short-term ATR is high relative to long-term ATR.
  - It sometimes lands exactly on an earlier high or low.
- **The exact formula is not reproduced.** Dozens of candidates were tested (hl2, close,
  body, extremes; daily and weekly ATRs; lags), and none explains more than about 80%
  of the level.
- **It flips about 1.5-2 times a year,** against about 7 for the old version.
- **Consequence:** old-version results (sections 5.1-5.18) do not carry over to the new
  indicator. Test it from exports (`Direction` column), as the original TradingView
  backtests did, until it is replicated.

---

## 3. Data

| folder | contents | notes |
|---|---|---|
| `data/tv_full/` | BTC, ETH, SOL, BNB, ZEC `_1D`/`_1W` | **Primary crypto set.** Uploaded as COINBASE_BTCUSD/ETHUSD/SOLUSD, BINANCE_BNBUSD, BINANCE_ZECUSDT. Daily from BTC 2015-07, ETH 2016-05, BNB 2017-07, ZEC 2019-03, SOL 2021-06, to 2026-08-24. |
| `data/tv_stocks/` | SPX, NDX, IWM, COIN, TSLA, HOOD, CRCL `_1D`/`_1W` | Daily capped at ~2010 by TradingView (no 2000-02 or 2008 on daily). Weekly: SPX from 1967, NDX 1985, IWM 2000. |
| `data/tv_export/` | 300-bar crypto exports | Superseded. |
| `data/crypto2026/` | CoinGecko closes | Wrong-model work only. |
| repo root `QQQ/SPY/IWM_historical_data.csv` | yfinance **OHLC**, dividend-adjusted | The only real highs and lows in the repo. |
| repo root `btc-usd.csv`, `eth-usd.csv`, `sol-usd-max.csv`, `avax-usd-max.csv`, `BATS_COIN, 1D.csv` | early uploads | Wrong-model work only. |
| `data/universe_qlib/` (gitignored, rebuild) | qlib US daily for every S&P 500 member since 1999 that qlib has (852 tickers), 2000 to 2024-04-25 | Download `https://github.com/SunsetWolf/qlib_dataset/releases/download/v0/qlib_data_us_1d_v3.zip` (615 MB), then `screener.data.from_qlib(root, symbols, out_folder)`. Total return until 2021-09-16, price-only after (`--prices qlib`). Survivorship-biased: 60-66% of 2005/2008 members usable. |
| `data/universe_recent/` (gitignored, rebuild) | ~2,300 US stocks and ETFs, split-adjusted OHLC, 2024-08 to the latest close | `https://github.com/q100423gg-coder/us-stock-data/releases/download/data/prices.parquet` (refreshed daily), then `screener.data.from_long_parquet`. Needs pyarrow. Third-party and unofficial. |
| `data/universe/members.csv` (gitignored, rebuild) | point-in-time S&P 500 membership spells | `screener.data.sp500_members(out)`, from fja05680/sp500 via raw.githubusercontent.com |
| `data/universe_pit_all/`, `data/universe_pit_ohlc/` (gitignored, rebuild) | **Best stock research set:** point-in-time S&P 500 members 1995 to 2026-10 including ~400 dead or acquired companies, plus SPY and `members.csv` | Download `https://github.com/Johnbrick123/sp500-data/releases/download/data/prices.parquet` (175 MB) and `.../membership_intervals.parquet`, then `screener.data.from_sp500_pit(prices, members, out, max_close_only=1.0 or 0.05)`. OHLC is scaled to total return (`--prices total`). CRSP close-only failures get approximated bars. STI is a recycled ticker (use `--exclude STI`). Third-party; the tag is overwritten nightly. |

**Getting the current state.** `moneyline_ref.py` cannot run on the `data/tv_*`
exports, because they have no highs or lows. Faking high = low = close matches only
60-72% of bars. Instead:

- Read the state straight from the export: `Up Trend` populated means GREEN, and its
  value is the line.
- The **last row of every export was still forming** when exported (2026-08-24; HOOD
  and CRCL daily 2026-08-27). Drop it unless the export was taken after that bar closed.
- Never report an export's last row as today's state.
- For a current state, ask the user for a fresh **candle-mode** export (OHLC, so
  `moneyline_ref.py` can also be checked), or run the signal job locally on Coinbase
  candles (plan section 3.2 A).

---

## 4. Conventions in the backtests

- Long while GREEN, flat while RED; no shorting. No leverage, except the illustrative
  model in `confirmation.py`.
- **Fills at the close.** Tables report same-bar fills with next-bar as a sensitivity
  check, and results can move a lot between the two.
  - Same-bar fills **cannot be executed** for stocks, ETFs or the spot-ETF route,
    because the plan trades those in the next session.
  - For those vehicles, judge by the next-session numbers (`gate.py` does).
- **Costs per side:**

  | where | cost |
  |---|---|
  | crypto (unless noted) | 0.1% + 5 bp |
  | stocks | 1 bp + 2 bp |
  | Robinhood crypto | ~0.95% |
  | ETF route | 0.02% |

- The weekly state is applied to daily bars with `shift(1)` then forward-fill, so a week
  counts only once it has closed.
- If a series starts mid-green-run, the engines buy on the first bar. `stops.py` drops a
  few more warm-up bars than `run_full.py`, so its baselines differ by up to ~5 CAGR
  points. Compare variants only within one engine.
- The stocks "adjusted" view adds dividends to holders and T-bill interest while flat.
- **pandas 3.0 traps:**
  - `.shift()` on a bool Series yields object dtype, and `~` then means integer
    negation (`~False == -1`).
  - `.to_numpy()` can return read-only views; use `copy=True` before writing to it.

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

These use same-bar fills at 0.15%/side.

- **With next-bar fills**, BTC's return edge disappears (65.3% vs 66.4% CAGR) and ZEC's
  turns positive. The drawdown advantage remains on all five.
- **BTC's edge is mainly risk reduction:** 1.43× terminal wealth, but 29 points less
  drawdown. ETH and SOL are the real return stories. Reconcile big percentage totals
  through CAGR before comparing.
- **The edge is mostly bear-market avoidance.** ETH's sits in the 2017-19 block and
  SOL's in 2022. Since 2022 at 0.15% the signal beats B&H on ETH (+26% vs −33%), SOL
  (+249% vs −46%) and BNB (+38% vs +35%), roughly matches BTC (+60% vs +67%), and trails
  ZEC.
- **Since 2024 (~20 trades per coin) the answer depends on execution.** The same-bar
  0.15% version trails B&H on 4 of 5. The weekend-aware ETF proxy beats B&H on BTC, ETH
  and SOL and trails BNB and ZEC. This window cannot separate weakness from noise.
- **Trades:** about 7 per coin per year, win rate 39-53%.
  - Median **losing** trade: −6% (BTC) to −12% (ZEC).
  - Median of all trades: −4% to +1%.
  - Worst trade: −20% (ETH) to −43% (ZEC).
  - Returns come from a few large winners.

### 5.2 Daily beats weekly (crypto)

Weekly loses to B&H on 4 of 5 coins (BTC 8,206% vs 33,628%; ETH 10,873% vs 20,892%;
BNB 29,440% vs 89,665%; ZEC −3%). Only SOL wins, on just 4-13 weekly trades per coin.

### 5.3 Confirmation filters — `confirmation.py`, `supplementary.py`

- **Daily AND weekly green** gives up a large share of terminal wealth: 86% (BTC),
  83% (ETH), 98% (BNB), 45% (SOL), 30% (ZEC). Drawdown improves except on BNB.
- Pooled over 287 entries, **breakout** and **weekly-green** confirmations raise the hit
  rate (46.7% → 51.8-53.6%) and the per-trade geometric gain (9.7% → 12.7-12.9%). But
  they take fewer trades, so total return falls.
- **Squeeze** filters skip the monster runs, and **retest** is the worst filter tested.
- Leverage (illustrative): breakout confirmation cuts the worst in-trade drawdown and
  raises survivable leverage from 2.34× to 3.88×. Agentic accounts have no leverage, so
  this is moot there.
- `confirmation.py` has no `__main__`; drive it from a script to reproduce.

### 5.4 Joining a green run late — `supplementary.py late_entry_geo()`

Exits are measured at the red-flip close. Each cell is the geometric mean of the
remaining return, pooled over every (run, entry-day) pair in the bucket. Entries
overlap, so the effective sample is about the run count; only "at flip" is one trade
per run.

| | at flip | day 1-20 | day 21-50 | day 51+ (runs) |
|---|---|---|---|---|
| BTC | 8.3% | 7.6% | 7.4% | 12.0% (7) |
| ETH | 10.2% | 8.1% | 4.9% | −3.2% (7) |
| SOL | 6.3% | 7.0% | 4.2% | 7.1% (1) |
| BNB | 21.0% | 23.7% | 26.5% | 20.1% (7) |
| ZEC | 4.3% | 2.6% | 14.1% | 18.0% (4) |

- Medians (`late_entry()`) are negative in most buckets, just as the median at-flip
  trade is, because the gains come from a few large runs.
- Entering within ~3 weeks of the flip earns about the same as entering on the flip.
- Broader check by rise since the flip (21 coins, 13 ETFs, 293 stocks; FINDINGS 2026-10-19): no penalty for
  bigger rises on crypto within 20 bars, no reliable premium; stocks more than 50% up did worse (fragile).
- **The earlier claim that late entry is *better* was wrong:** it measured exits one
  bar early.

### 5.5 ATR stop-losses on top of the indicator — `stops.py`, `run_stops.py`

Median CAGR edge vs indicator-only; (n/5) = coins improved.

| variant | stop on daily close | resting order w=0.4 | w=0.6 | close, 2022+ |
|---|---|---|---|---|
| fixed 1.5×daily ATR, no re-entry (Ivan's rule) | +2.1 (3/5) | −2.7 (2/5) | −4.9 (1/5) | +4.1 (5/5) |
| fixed 1.5×daily + buy back above entry | +1.8 (4/5) | +1.8 (4/5) | −4.5 (1/5) | +2.7 (5/5) |
| trailing 1.5×daily ATR | **−37.5** | **−39.0** | **−53.8** | −3.3 |
| fixed 1.5×weekly ATR | 0.0 | 0.0 | −1.1 | 0.0 |
| trailing 1.5×weekly ATR | −20.7 | −12.8 | −28.2 | 0.0 |

- The line already sits ~2.4 daily ATR(14) below the close at a flip, so a 1.5×ATR stop
  is just a tighter copy of it.
- 1.5×weekly ATR is about 4-5×daily: wider than the line, so it almost never fires.
- Ivan's fixed stop discarded BNB's Nov-2020 run (+885% → −17%).
- **Recommendation: use the indicator alone.** The wick parameter w was calibrated on
  ETF OHLC (≈0.40, no committed script).

### 5.6 Stocks and indices — `run_stocks.py`, `gate.py`

| | daily signal (raw) | B&H (raw) | weekly signal (adj.) | B&H (adj.) |
|---|---|---|---|---|
| SPX | 3.3% | 12.8% | 8.3% (DD −38.9%) | 10.0% (DD −55.0%) |
| NDX | 8.7% | 18.7% | 13.1% (DD −52.2%) | 15.2% (DD −82.3%) |
| IWM | 3.4% | 10.0% | 5.3% (DD −36.2%) | 8.6% (DD −57.7%) |
| TSLA | 21.1% | 42.3% | 21.4% | 41.4% |

- **Daily on indices:** 32-45% of trades end within ±2%, and profit factor is 1.3-2.0
  (vs 3.4-16 on crypto). Never trade it.
- **Weekly INSURANCE** (`gate.py`), with dividends and cash yield counted, at same-week
  and next-week fills:

  | | CAGR given up / yr | drawdown saved | qualifies? |
  |---|---|---|---|
  | SPX | 1.7-1.9 pts | 16-21 pts | yes |
  | NDX | 2.1-2.9 pts | 30-36 pts | yes |
  | IWM | 3.3-4.1 pts | 16-21 pts | no |

  It helped in dot-com and the GFC, was too slow for Covid, and cost 10-20 points in the
  2025-26 rally.
- **COIN weekly:** 15.1% vs −4.0% CAGR, but on 6 trades, and next-bar fills cut it to
  4.7%.
- **HOOD daily:** 18.2% vs 16.7%, but 5.6% with next-bar fills.
- **CRCL:** 5 daily trades.
- All of COIN, HOOD and CRCL fail the history test.

### 5.7 Which assets the signal suits

The signal needs sustained multi-month trends and deep drawdowns (−70% to −95%) to pay
for its whipsaws, which means crypto majors. It fails on assets that grind up and
mean-revert quickly (indices) or make their returns in short bursts (TSLA).

Survivorship caveat: every asset tested was chosen after the fact and is still around.

### 5.8 Sizing — `portfolio.py`

ETF route, pre-tax, total crypto capped at 60% (CAGR / max drawdown):

| basket | buy & hold | signal, full | fixed 25% | 2.5% ÷ (1.5×distance) |
|---|---|---|---|---|
| ETH+SOL 2021+ | 17.7 / −91 | 49.4 / −60 | 31.6 / −37 | 15.6 / −19 |
| BTC+ETH 2016+ | 64.8 / −91 | 89.3 / −60 | 48.8 / −36 | 30.8 / −22 |

- Sizing changes how much risk you take, not how good the trade is.
- Prefer a fixed fraction: distance-based sizing is no better.
- Price sits a median **10-16% above the line at a flip** (6.6-10.5% later in a run).
- **Exits fill past the line** (`supplementary.py entry_distance_and_overshoot()`):

  | exit timing | median | worst |
  |---|---|---|
  | same-bar | 1.5-2.3% | 10-33% |
  | ETF route (next session) | 1.0-2.9% | 21-40% |

- When a personal stop and the line disagree, **don't move the stop, change the size**.

### 5.10 Stock baskets: how strict a fit? — `screener/strictness.py`, `screener/selection.py`

Full tables and the pre-registration are in `screener/README.md`.

- **Universe and method:** S&P 500 members at each re-pick date. Each is scored on 5 years
  of past indicator "skill" (drift-neutral timing value), then baskets from top 5 to all
  stocks are traded for the next 3 years: next-open fills, 0.03%, cash at T-bill (or SPY)
  while red, tax at 35%/20%.
- **Development 2005–2022:** SPY held 7.45%/yr after tax. Skill top 5 made 7.63 and skill
  > 10 made 7.41, each beating SPY in only 3 of 6 windows. Top 20 made 4.6, all stocks 3.2,
  "decent fit" (skill > 0 / > 5) 3.7, strict-gate style 1.6, random 2.2-3.6.
- **Pre-registered rule:** no level qualifies.
- **H2 (SPY when red, skill > 10):** passed development (+1.8) and holdout 2023-01 to
  2024-04 (+0.5), then failed forward 2025-01 to 2026-10 (−4.6).
- **Selection is real but small and fragile:**
  - p ≈ 0.001-0.002 vs all stocks, but 0.005-0.009 against a volatility-matched null.
  - About one big winner per window carries the top-5 lead.
  - Only 7% of past skill persists.
  - The pre-registered top-20 selection study gave test skill +1.75 vs −1.91 for all.
  - High-volatility and deep-drawdown selectors with no backtest did as well.
- **Biases:** survivorship flatters the baskets vs SPY by an estimated 0.3-1 pt/yr, so the
  ties are upper bounds. Taxes take most of the edge (top 5: 11.5% pre-tax vs 8.5%).
- **Robustness on point-in-time data with dead companies** (Johnbrick123/sp500-data,
  89-98% coverage):
  - 2001-2021: no park = cash level beats SPY (best 6.89 vs 7.16).
  - Park = spy is ahead in development (+0.8 to +2.3) but **loses at every level in the
    full 2023-2025 holdout**; H2 made 12.1 vs 18.8.
  - 2026 to date is uninformative: random baskets also beat SPY by ~18 pts.
- **The average S&P 500 stock** loses about 2.2%/yr of timing skill to the indicator.

### 5.11 Why crypto and not stocks; small coins — `analysis_2026/altcoins.py`

- **Data:** 581 Binance USDT coins 2019-2026, delisted ones included, ranked into volume
  tiers each year. Results in `analysis_2026/results_altcoins/`.
- **Mechanism:** the signal beats holding in ~97% of asset-years that fall more than 60%,
  but only in 22-41% of rising crypto years and 6-23% of rising stock-years.
  - **Crypto:** 37% of coin-years fell more than 60%.
  - **S&P stocks:** 1.8% did, and 89% of stock-years sit between −30% and +100%, where the
    signal lags.
  - So it is crash insurance plus partial trend capture, and taxes and whipsaw dominate
    when crashes are rare.
- **Small coins:** the signal beats holding the same coins in every tier (72/72 variants),
  but the edge comes from the 2022 and 2025 crash years. There is no consistent size
  gradient. Small coins lost money even with the signal over 2022-25 (−7.6%/yr after tax).
  The positive 2019-25 small-coin figure rests on one coin (DENT 2021) and January starts.
- **Absolute returns:** BTC held vs a signal basket of altcoins depends on the window.
  - BTC wins after tax for 2022-25 (14.3 vs 5.5 / 11.0 for the top-10 / 11-30 baskets).
  - January-start windows ending 2022-24 had the large-coin signal baskets 20-60 pts/yr
    ahead of BTC.

### 5.12 Professional-style trend sleeve — `analysis_2026/trend_portfolio.py`

- **Setup:** 12-month time-series momentum on 12 diversified ETFs (2005-2026), sized by
  volatility. Compared as a 20% sleeve next to 80% SPY.
- **Long/short (needs futures or margin):** beat an equal T-bill allocation by about
  +0.5 pt/yr (+0.4 to +0.9), with Sharpe +0.03 to +0.05.
  - +15.8% in 2008 and +11.7% in 2022.
  - About 3%/yr since 2015.
  - Against an equal bond allocation it's a coin flip.
- **Long-only:** a similar return gain, little risk benefit.
- **The user's indicator, diversified and volatility-sized:** adds nothing.
- **No 80/20 mix beats 100% SPY's return.**
- **Best risk-adjusted mix:** 60/20/20 SPY/IEF/trend, Sharpe 0.67, max DD −29% (exploratory).
- **Implementation:** a managed-futures ETF (DBMF, KMLM), ideally in a tax-advantaged
  account. Not the Robinhood agentic account.

### 5.13 Style and sector mean reversion — `analysis_2026/style_rotation.py`

- **Tested:** contrarian rotation toward 3-5-year laggards, rebalanced each December
  against equal weight. On Ken French style boxes and industries 1926-2026 (the 25 size x
  BM portfolios with BE/ME, 10 and 49 industries) and on ETFs 2006-2026.
- **No reliable edge.** Pre-registered R1, R3 and E3 fail, and R2 is not significant.
  - Small value vs large growth timed by relative return lost in every period.
  - Timed by the valuation spread: about 0 overall.
- **Mechanism:** mild long-term reversal exists, but the losers are often chronically weak
  boxes (small growth), and what industry reversal exists is just value and size exposure.
- **Momentum (12-1):** strong on 49 industries over 1932-2026, but not confirmed in the
  unseen 1932-48 / 2017-26 slices.
- **Practical:** a static value/small tilt (if any) beats any timing rule. It lagged for
  ~20 years (2006-2026).

### 5.14 Leverage, tight stops, key-level breakouts — `analysis_2026/leverage_breakout.py`

- **Leverage on the indicator destroys wealth.** At 3x, 85% of the 20 coins' sub-accounts
  blow up; at 5x, 100%. BTC: 12.4x at 1x spot vs 1.9x at 3x vs liquidated at 5x.
  - Kelly-optimal leverage is ≤ 1.85 on every coin.
  - Funding on perpetuals costs ~8-12 pts/yr even at 1x.
- **Tight stops lower expectancy:** 2.7% vs 10.3% per trade, 89% stopped out.
- **4-hour bars are worse than daily.**
- **Turtle/Donchian breakouts are about the same trend exposure as the indicator, not
  better** (paired t 0.07). Their expectancy is positive but carried by the top 5% of
  trades from 2020-21.
- **The user's literal idea (BTC, tight stop, 5x):** 430x in-sample from 1-3 trades, but 5x
  lost money on 16-19 of 20 coins. Lottery, not edge.
- **ETF breakouts lag buy & hold.**

### 5.15 Flip-confirmation delay (Ivan's hourglass N/5) — `analysis_2026/flip_delay.py`

- **Rule:** flip only after N consecutive closes beyond the line. N=1 is the original.
- **Stocks: helps robustly.** S&P 500 point-in-time basket at N=5: Sharpe 0.53 → 0.70,
  CAGR 5.0 → 6.6%, max DD −34 → −22% (bootstrap p ≤ 0.009; every definition, both halves).
- **ETFs: helps in direction** (10/13), but statistically fragile.
- **Crypto: no help.** The top-20 basket is worse at every N; keep the immediate flip, or a
  short exit-only delay at most.
- **Mechanism:** immediate flips are false about twice as often in stocks/ETFs (10-13%
  reversed within 4 bars) as in crypto (5-6%), and crypto breakouts tend to run right
  after the flip.
- **Versus buy & hold:** even delayed, the indicator matches B&H's risk-adjusted return on
  stocks/ETFs at half the drawdown, but with lower CAGR (S&P basket 6.6% vs 10.9%).

### 5.16 Ten theory-driven strategies (S1-S10) — `analysis_2026/theory_strategies.py`

Pre-registered in `analysis_2026/THEORY_PREREG.md`. Each has a published mechanism and suits
an individual. The test is the Sharpe gain vs a benchmark (block bootstrap, Holm across
ten) that must also be positive in a later or post-publication sub-period. A three-lens
audit plus a confirm stage reproduced everything.

- **9 of 10 fail:**
  - vol-managed equity, 10-month SMA, dual momentum, low-vol stocks
  - 12-1 momentum, turn of the month, Halloween
  - crypto trend × vol target, crypto 4-week momentum
- **Risk reducers (S1, S2, S4)** cut max drawdown (e.g. −48% vs −84% for the 10-month
  SMA) but do not raise the Sharpe reliably, and cost CAGR, especially after tax.
- **Turn of the month** is the decay case: highly significant 1927-88, zero since 2009.
  Halloween is similar.
- **S9, BTC/ETH cash-and-carry** (long spot, short perpetual), passes the pre-registered
  rule: 6.5%/yr over T-bills at 1% vol since 2019-10.
  - 96% of that came in 2020-21. Since 2023: +0.8%/yr, not significant. Since 2025:
    −1.4%/yr, significantly negative.
  - Significance holds up to about 100 Newey-West lags and under the pre-registered
    bootstrap, but not at longer bandwidths.
  - It needs daily margin top-ups and carries exchange-failure risk.
  - **Do not trade it at current funding.**
- **Takeaway:** no candidate beats its benchmark reliably now. That matches every earlier
  study: published edges decay, and risk reduction costs return.

### 5.17 Regime switching (other instance) — branch `claude/youthful-goldberg-31vs8h`

Another Claude instance ran this study and audited it with a 6-lens verification. It is
**not merged** into this branch. Its full section (numbered 5.15 there, so renumber on
merge), FINDINGS entry, `analysis_2026/regime_switch.py` and `results_regime/` live on
that branch.

- **Why the indicator trails buy & hold on stocks (H-A1 confirmed):** about 81% of
  bull-phase losses are false breakdowns. The indicator re-enters 2.2-2.6 ATR above the
  low, while price falls only a median 0.9-1.7 ATR after an exit. Bull phases are 84% of
  S&P time.
- **Switching** (hold while the regime is good, indicator while bad) **fails H-B1 to H-B5,**
  some narrowly.
  - S&P 1963-2026: 7.9% after tax vs buy & hold 9.8%.
  - It beats the indicator on every ETF and index, but never on the coins.
  - No ex-ante regime beats S&P buy & hold after tax. Hindsight regimes would add about
    4 pts/yr, so the failure is in identifying the regime.
- **Use:** index money, hold. For drawdown control, a plain 200-day / 50-200 rule or the
  switch is cheaper insurance than the weekly signal, at about 1-3 pts/yr after tax.
  Crypto: no regime filter on top of the indicator.

### 5.18 2x S&P + gold (50% SSO / 50% GLD) and leverage + trend — `analysis_2026/sso_gold.py`

Pre-registered in `analysis_2026/SSO_GOLD_PREREG.md`. Audited by six lenses plus confirm checks;
FINDINGS has the full entry.

- **The other instance's C4** (`codex/theory-lab`) beat SPY 2007-2025, 14.3% vs 10.6%. It is
  0.99 × S&P + 0.51 × gold with alpha −0.7 to −0.8%/yr (R² 0.995): a bet that gold beats
  T-bills, not an edge.
  - Synthetic C4, edge vs S&P (gold = LBMA fix from 1968, 2x fund = S&P × 2 minus financing
    and fee):
    - 1972-2006, out of sample: +0.4%/yr, p 0.42. FAIL.
    - 1972-2026: +1.35%/yr, p 0.24. FAIL.
    - From 1975: −1.85 to 2006, 0.0 to 2026.
    - By decade: +13.6, −6.7, −4.7, +3.8, +0.8, +5.0 %/yr, following gold.
  - Break-even: gold must beat T-bills by about 0.8-1.5%/yr. Real gold is at a record level.
  - Bonds in place of gold: about 0. WisdomTree's GDE (90/90) live record is the same gold
    bet, and its gold-futures gains are taxed as ordinary income every year.
- **P3, 2x S&P while above the 200-day average, else T-bills (Gayed-Bilello): PASS.**
  - +3.9%/yr over 1929-2026, Holm 0.014.
  - Pre-1928 Dow: +3.5%/yr. Real SSO 2006-2026: 13.7% vs 11.3%.
  - But most of the evidence comes from 1929-1971, when it could not be traded at these
    costs. In tradable eras (1975+, 1982+, 2006+, 2016+) it is +1.8 to +3.1%/yr with p
    0.03-0.13, which does not survive correction.
  - Its Sharpe ratio has not improved since 1975.
  - It is sensitive to execution timing and to the average length.
  - About 6 switches a year; trailed the S&P by more than 10 points in 18 of 97 years
    (2022: −30% vs −18%).
  - **Tax:** after-tax edge 1972-2026 is +0.56 federal, +0.29 with NIIT, about 0 with state
    tax, below 0 if the S&P would be held for heirs.
- **Moneyline-timed leverage (P5) and C4 with trend filters (P4) fail.** P4 is a risk
  reducer: drawdown −30% vs −55%.
- **Use:** don't hold C4 expecting to beat the S&P. If P3 is used at all, use it in a
  tax-advantaged account, at a modest allocation, with acceptance of whipsaws.

### 5.19 The Larsson Line (EMA 32/58) on long histories — `analysis_2026/larsson.py`

Pre-registered in `analysis_2026/LARSSON_PREREG.md`. Audited by three lenses plus confirm
checks; FINDINGS has the full entry. The user's Larsson Line plots EMA(32) and EMA(58).
The colour rule is unconfirmed:
- LARSSON: green while EMA32 > EMA58
- LARSSON-PRICE (sensitivity): green once the close is above both lines, red once it is
  below both, unchanged in between

- **All five primary tests FAIL** (Sharpe gain, Holm across five):

  | test | dSharpe | p |
  |---|---|---|
  | P1 S&P 1929-2026 vs buy & hold | +0.058 | 0.24 |
  | P2 S&P point-in-time basket | +0.009 | 0.40 |
  | P3 crypto top-20 basket | +0.154 | 0.18 |
  | P4 vs old ML N=5 on stocks | +0.009 | 0.45 |
  | P5 vs old ML N=1 on crypto | −0.360 | 0.95 |

  The crypto tests can only detect gains of about 0.6 Sharpe: 80% power at the 0.01 level
  a Holm pass needs; about 0.5 at 0.05.
- **Stocks: an ordinary slow trend filter.**
  - S&P 1929-2026:
    - drawdown −35% vs −84% (−41% to −46% if the fill moves a day either way; −53% two
      days late)
    - Sharpe_xs 0.48 vs 0.42
    - CAGR 8.7% vs 9.9%
    - after tax (realised, audit engine) 6.6% vs 9.0%
  - Since 1972 it adds nothing (Sharpe_xs 0.41 vs 0.44).
  - 32/58 sits at the 31st percentile of 4,567 EMA pairs.
- **Crypto: beaten by the old MoneyLine N=1.** Held baskets give −0.46 with the CI
  excluding 0.
  - The gain vs buy & hold halves with held baskets: +0.07.
  - Per-coin medians flip with the start date.
- **The colour rule changes a verdict only on crypto.** On stocks it moves results both
  ways, but every test still fails.
  - LARSSON-PRICE would pass P3 at study costs (+0.41, Holm 0.005).
  - It fails with held baskets alone (Holm about 0.08) and is borderline with retail costs
    (about 0.05; 4 of 10 seeds fail).
  - It fails with both (about 0.19) and at 0.95%. The test is also post hoc.
  - It is still below the old MoneyLine N=1 in every basket version (about even per coin).
    The edge is speed, like EMA15/30.
- **The 200-day average:**
  - best Sharpe_xs and pre-tax CAGR on the 1929-2026 index (p 0.049 unadjusted)
  - not the best drawdown there (−51%, one 1932-33 whipsaw)
  - not best after tax, or in 4 of 5 eras
  - worst of the five main rules on crypto (EMA50/200 is as bad)
- **Tax conventions.**
  - The pre-registered after-tax figures tax buy & hold's dividends only once, at the end
    (never yearly), and they tax the strategies' unrealised gains yearly.
  - The index tables now carry a realisation-based column as well.
- **Use:** no reason to prefer it over the old MoneyLine on crypto or over holding stocks
  after tax. On the pre-1928 Dow, LARSSON-PRICE roughly tied buy & hold after tax: 6.8 vs
  6.7 realised. Confirm the colour rule with the user before reading the crypto result.

### 5.20 Split mode's second-half wait — `analysis_2026/split_delay.py`

Pre-registered (`analysis_2026/SPLIT_DELAY_PREREG.md`) and audited; FINDINGS 2026-10-19 has the tables.

- **The second half's wait: no change.**
  - 36 variants of the second tranche's (n_entry, n_exit) were tested on three samples: the S&P point-in-time
    basket, the high-volatility fifth of it, and the crypto top-20 incl. dead coins.
  - The in-sample pick lost to split(5,5) out of sample in all three. Reality-check p 0.80 / 0.85 / 0.34.
  - The stock surface is flat. Selling after 8 closes is about 0.01-0.02 Sharpe better in and out of sample (not
    significant) and has about 2 points deeper drawdowns.
- **Stocks: confirm5 beats every split.** 100% at N=5 vs split(5,5):
  - S&P basket: Sharpe 0.515 vs 0.444, out of sample 0.536 vs 0.491; drawdown −22% vs −28%.
  - High-volatility stocks: 0.426 vs 0.328.
  - Consistent with 5.15. These are reference rows, not pre-registered candidates.
- **Crypto:** immediate 1.071, split 0.976, confirm5 0.812. Keep split or immediate.

### 5.9 Costs, vehicle and tax — `costs.py`, `gate.py`

CAGR edge vs B&H, full history; B&H pays the cost once.

| | 0.15% | 0.95% (RH direct) | spot-ETF proxy, next / 2nd NYSE session, 0.02% | after tax (ETF, 35%/20%) |
|---|---|---|---|---|
| BTC | +5.5 | **−12.2** | −3.1 / −0.2 (DD −69% vs −84%) | **−14.3** |
| ETH | +35.1 | +13.5 | +38.7 / +25.8 | +21.5 |
| SOL | +37.0 | +18.4 | +42.4 / +35.7 | +26.6 |
| BNB | +8.8 | **−12.7** | −0.4 / −2.7 | −25.2 |
| ZEC | −3.4 | −18.9 | +2.3 / −28.3 | −8.0 |

- At 0.95% since 2022, only SOL clearly survives: ETH is +1.4, and −2.7 since 2024.
- An earlier ETF proxy that also traded on weekends (BTC +1.8, ETH +42.9) is superseded.
- The ETF proxy uses each coin's own history, since real ETFs exist only from 2024-25.

---

## 6. Superseded — do not cite

- Everything on the Ichimoku/HMA/EMA model.
- The 300-bar weekly results.
- The "green = close > kijun" proxy.
- "Don't chase a daily flip while weekly is red."
- "Late entry is better."
- "Median losing trade −1% to −4.5%."
- The calendar-lag spot-ETF numbers.
- "BTC: trade the signal for drawdown control."
- "Indices get weekly insurance" (IWM fails).
- "6-12% typical distance → 20-40% positions."
- FINDINGS' dated "current state" snapshots.
- Larsson pre-audit (2cf7aa7) readings:
  - crypto basket buy & hold at 15.25% (daily-rebalanced; held: 20.6%)
  - "LARSSON 18.4 vs buy & hold 10.8 after tax per coin" (depends on the start date)
  - "buy & hold best after tax on 12/13 ETFs" (about 9-10/13 with coupons taxed yearly)
  - LARSSON index drawdown "−35%" without the fill-day range

---

## 7. Bugs found and fixed

- **pandas 3.0 bool-shift negation.** It silently broke two ad-hoc studies before it was
  caught.
- **Late-entry table** exited at the last green close; it now exits at the red-flip
  close.
- **Losing-trade median** had been computed over all trades.
- **Spot-ETF proxy** traded on weekends.
- **"Unadjusted prices" instruction** would have broken stock splits; corrected to
  split-adjusted.
- **`stops.py`:**
  - the wick proxy fired stops at prices that never traded
  - `run_attribution` misaligned windows
  - exposure ignored the open final position
- **What caught them:**
  - independent reimplementation
  - adversarial review with refute-or-reproduce
  - a repo-vs-claims audit
  - a newcomer test
  - concentration, timing and era tests

---

## 8. Automated trading (summary of `AGENTIC_TRADING_PLAN.md`)

- **Robinhood Agentic Trading:** a separate taxable account, reached through the MCP
  server `https://agent.robinhood.com/mcp/trading`.
  - Approvals are **off by default** for Claude; turn them on.
  - No margin and no paper trading.
  - The MCP has no crypto price history.
  - Crypto costs ~0.95%.
  - OAuth re-login every few days.
- **Phase 1 (cron, no Robinhood access):** Python computes signals with
  `moneyline_ref.py` on closed bars from public data (Coinbase candles for crypto;
  split-adjusted daily OHLC for stocks/ETFs) and writes `signals.json` and a digest to a
  private store.
- **Phase 2 (interactive Claude Code):**
  1. Claude saves raw Robinhood MCP JSON (positions, equity, quotes, open orders).
  2. Python validates it and writes `plan.json`.
  3. Claude previews and places only those orders. A PreToolUse hook blocks anything
     that doesn't match exactly, and a STOP file cancels the agent's open orders.
  4. With approvals on, the user approves in the app.
- **Built (2026-10-18): `agentic/`**, runbook `agentic/README.md`, contract `agentic/SPEC.md`.
  - **Daily use:** `/moneyline` in Claude Code (`.claude/commands/moneyline.md`).
  - **Hooks** in `.claude/settings.json` guard every Robinhood MCP tool. The PreToolUse hook fails closed and
    allows a place call only if it exactly matches a plan order within the caps. The PostToolUse hook captures
    results, keeps the journal and the ledger, and writes STOP if an order skips approval.
  - **STOP is sticky (2026-10-20):** `stop` and the PostToolUse hook also record STOP in the append-only `hook.log`,
    so deleting the STOP file no longer re-enables trading; only `resume` in the user's terminal clears it, and each
    clear is logged (README section 6). Deleting, emptying, trimming or rotating `hook.log`, or a sync tool restoring
    an older copy, does lift it (a missing hook.log means the file check alone): never touch hook.log while STOP may
    be set. FLATTEN and BLOCK_BUYS stay file-based.
  - **Signal:** the old MoneyLine computed from OHLC (exact replica), by the user's choice, so no daily exports
    are needed. `tv_export` remains available for the new indicator.
  - **Modes** (per asset): `immediate`, `split` (half at N=1, half at N=5) and `confirm5`. Default **split** for crypto and
    stocks (FINDINGS 2026-10-19: never the worst, shallower drawdowns; immediate is 2-4 pts/yr ahead in the dead-coin
    basket at low cost, within noise).
  - **Allocation:** `slots` (example 10 × 10%, `crypto_first`, crypto cap 0.60; `favorites` breaks same-day ties
    after class and flip date, never eligibility or caps, and the universes scan favorites past their liquidity and
    `max_assets` cuts, every other filter still applying; to the scans a name that is both a coin and a stock universe
    ticker means the stock, and `TICKER-STOCK` favors a stock under either name) or `fixed`.
  - **Entry policy:** `join_recent` (default; join only within 20 bars of the green flip and at most 50% above the
    flip close; risk controls, FINDINGS 2026-10-19), `join`, or `fresh_only`.
  - **Windows + Git Bash** setup with `AGENTIC_PYTHON` in `.claude/settings.local.json`, a time-zone fallback,
    `python -m agentic doctor` (checks the install and live-tests the guard hook) and a Task Scheduler script
    (`agentic/windows/`).
  - **The sleeve sells only shares it bought itself.**
  - **Crypto universe (2026-10-19, `agentic/universe.py`, README section 10):** scans every coin Robinhood offers
    (`get_currency_pairs`), minus stablecoins and wrapped tokens. It keeps coins with a Coinbase pair, ≥ 300 bars and
    a median volume ≥ $5M/day, the 30 most liquid (the evidence is on large coins: 5.11).
    - Each coin trades its spot ETF where one is mapped and confirmed tradable on the account: IBIT, ETHA, BSOL,
      XRPC, LTCC, NRR. Otherwise it trades directly at about 0.95% per side.
    - **Direct coins are a judgment, not evidence:** at 0.95% per side the edge over holding is −12.2 (BTC),
      −12.7 (BNB) and −18.9 (ZEC), and since 2022 only SOL clearly survives (5.9). After tax, BTC beat the
      baskets over 2022-25 (5.11). `direct_crypto: false` trades only coins with a confirmed spot ETF.
    - Held coins are never dropped. `init --update` adds the block (and missing nested settings) to an older config.
  - **Stock universe (2026-10-19, `agentic/stocks.py`, README section 13):** the user's own ticker list
    (`universe.equity`, off in the example; tickers only in the private config). Tradability per ticker
    (`get_equity_tradability`; fractional or whole shares), ≥ 150 bars (younger: watch-only), median volume ≥ $1M/day,
    the 60 most liquid; held tickers never dropped. Not evidence-based: no stock timing rule beat holding after tax
    (5.10, 5.15).
    - Bars: `yfinance` (default; Python downloads in one batch, cached; buys need the last close to match Robinhood's
      `previous_close` within 0.5%, exits never blocked) or `robinhood` (cached; fetch-list asks only for missing
      bars: incremental calls ≤ 200 bars, backfill windows ≤ 120 sessions, one symbol per call). A first live run
      showed one 2-year SPY result (~85k chars) exceeds Claude Code's 50,000-character limit for MCP text results
      (saved to a file; `MAX_MCP_OUTPUT_TOKENS` does not change it); the PostToolUse hook records such a notice as
      `capture_error: response_too_large`, and the next fetch-list asks for that data in smaller calls.
    - The scheduled job runs `signals --skip-feed robinhood`; `install` picks 00:15 UTC under the PC's DST offset.
    - The digest's ACTION column is now SIGNAL (`1.00->0.50`, `new 0.50`, `-`): the target, not an order.
  - **Status:** shadow mode (`live: false`) by default. First `/moneyline` runs against the real Robinhood MCP have
    happened on the user's PC (that is where the too-large SPY result came from); the connector still fails to
    connect in cloud sessions. Mode backtests are in `analysis_2026/results_agentic_modes/`.
- **Gate verdicts:**
  - ETH: TRADE via spot ETF.
  - SOL: PROBATION (≤10%).
  - BTC, BNB, ZEC: hold or skip.
  - SPY/QQQ: hold, with optional weekly insurance.
  - IWM and TSLA: hold.
  - COIN, HOOD, CRCL: watch.
  - Stock baskets picked by past fit: don't run (section 5.10). Scanner for information
    only.

---

## 9. Next steps (single to-do list; plan section 8 is the deployment order)

**Doable now in a sandbox:**

0. Stock universe: **done** (section 5.10). The verdict is no stock basket. Only two things
   could change it:
   - a survivorship-free dataset with delisted names (Norgate, Sharadar or CRSP, all
     paid), which would most likely make the baskets look *worse*
   - a tax-advantaged account, though out-of-sample results were mixed even before tax
   Optional: a nightly cloud scan of ~2,300 stocks from the daily parquet, as
   information.

1. Phase-1 signal job, planner, hooks and journal: **done** (`agentic/`, section 8). Next for the user:
   run the README's shadow mode on their machine for 4-8 weeks, record the exact approval response shape
   on the first live order, and compare the line value with TradingView daily.
2. Add a `__main__` to `confirmation.py`, and commit scripts for the remaining
   interactive numbers: the crash-window table, HOOD concentration, 20%-sizing
   leverage, wick calibration.
3. Walk-forward / out-of-sample testing, and a survivorship-aware candidate universe for
   the gate.

**Needs the user or live access:**

4. Fresh **candle-mode** TradingView exports, so `moneyline_ref.py` can be checked on
   crypto.
4b. The Larsson Line's colour rule: EMA32 vs EMA58 crossover, or price vs both lines?
   On the user's exports to 2026-10-15 the two rules disagree on ETH and SOL (crossover
   green, price rule red). It decides how to read the crypto result
   (section 5.19).
5. The user's tax rates and risk budget; open the Agentic account; turn approvals on.
6. Live MCP checks:
   - the crypto order route and fee
   - `get_equity_historicals` with `adjustment_type='split'` returns ≥250 bars
   - spot-ETF tradability and spreads
   - proposal statuses and expiry
7. Locally: Coinbase-candle backfill vs `data/tv_full` (plan section 8 step 2), then
   shadow mode.

## 10. Environment notes

- Use `python3` (3.11) and install with `python3 -m pip install pandas numpy` (plain
  `pip` targets another interpreter). pandas is unpinned.
- Market-data hosts and robinhood.com are blocked here (403); don't retry. WebSearch
  works.
- Other agents work in parallel on separate branches:
  - `claude/youthful-goldberg-31vs8h`: the regime-switch study. It is audited as of
    44952ae, not merged, and summarised in section 5.17.
  - `codex/*`: crypto regime, crypto trend comparison, stock shadow trading, and `codex/theory-lab`
    (five strategies C1-C5, `THEORY_LAB_RESULTS.md`; its C4 is examined in section 5.18).

  Fetch and rebase before pushing.
- The user runs a Schwab robo-advisor, which already does tax-loss harvesting. Wash-sale
  rules span all of the user's accounts, IRAs included, so any agentic-account plan must
  avoid buying, within 30 days, securities that are substantially identical to ones the
  robo just sold at a loss.
- `git clone` of public GitHub repos works, and so do GitHub release downloads
  (github.com/…/releases/download/… redirects to release-assets.githubusercontent.com).
  raw.githubusercontent.com, PyPI, S3 and GCS work too.
- Most api.github.com paths and GitHub search are blocked.
- Binance's public data archive is reachable through its S3 bucket
  (`s3-ap-northeast-1.amazonaws.com/data.binance.vision`), though not via
  data.binance.vision itself. It has daily klines for all spot pairs, delisted ones
  included.
- The Robinhood connector's large results land in
  `~/.claude/projects/<session>/tool-results/*.txt`; parse them with `screener/rh_ingest.py`.
- Commit code and backtest results only; logs and digests go to a private store.
  Containers are ephemeral.

## 11. File map (valid code)

| file | purpose |
|---|---|
| `AGENTIC_TRADING_PLAN.md` | Robinhood + Claude automated-trading design. |
| `screener/` | `scan.py` daily screener, `selection.py` walk-forward selection study (+ `--calibrate`), `strictness.py` basket strictness study vs SPY after tax, `data.py` loaders (CSV, Robinhood JSON, yfinance, qlib, long parquet, S&P membership, `quality_filter`), `rh_ingest.py`. See `screener/README.md` for the holdout, pre-registrations, survivorship and results. |
| `analysis_2026/altcoins.py`, `analysis_2026/results_altcoins/` | Crypto size-tier study on the Binance archive incl. delisted coins (Q1/Q2 pre-registered), payoff profile crypto vs S&P stocks (section 5.11). Data: `data/crypto_binance/` (gitignored); rebuild from `https://s3-ap-northeast-1.amazonaws.com/data.binance.vision` (`data/spot/monthly/klines/<SYM>/1d/`). |
| `analysis_2026/trend_portfolio.py`, `analysis_2026/results_trend/` | Trend sleeve study (H1-H3 pre-registered): TSMOM long/short, long-only, and the moneyline signal diversified across ETFs, as a 20% sleeve vs SPY (section 5.12). Data `data/etf/` (gitignored): universe A from the Johnbrick123 parquet (SPY IWM EFA EEM TLT IEF SHY TIP LQD HYG GLD SLV VNQ, scaled to total return); universe B extras and WTMF/DBMF/KMLM from qlib (`Q_*.csv`). |
| `analysis_2026/style_rotation.py`, `analysis_2026/results_style/` | Style/sector mean-reversion study (R1-R3, E1-E3 pre-registered; section 5.13). Data in `data/ff/` (gitignored): linearmodels FF bundle (PyPI), French CSV mirrors on GitHub (anshhkrishna/factor-zoo-postpublication 25 portfolios 202606, Achintya1311 10 industries, ZachTheAnalyst 49 industries), Johnbrick123 / o-bensalah / qlib ETFs. `french_sections()` parses raw French CSVs. |
| `analysis_2026/leverage_breakout.py`, `analysis_2026/results_leverage/` | Leverage / tight-stop / Donchian / key-level study (H1-H4 pre-registered; section 5.14). Data `data/crypto_4h/`, `data/crypto_funding/` (gitignored; Binance S3 archive spot 4h klines and USDT-M fundingRate). |
| `analysis_2026/flip_delay.py`, `analysis_2026/results_delay/` | Flip-confirmation delay study (D1-D3 pre-registered; section 5.15); `--supplement` runs the follow-ups. |
| `analysis_2026/sso_gold.py`, `analysis_2026/results_sso_gold/`, `analysis_2026/SSO_GOLD_PREREG.md` | 2x S&P + gold and leverage + trend study (section 5.18). Synthetic leveraged funds calibrated to actual SSO, lot-level tax engine (FIFO, collectibles, NIIT/state scenarios, step-up), stationary bootstrap, reality check. `python3 -m analysis_2026.sso_gold` (about 1.5 min). Data in `data/sso_gold/` (gitignored; sources in the module docstring: SteelCerberus, LBMA via forex-centuries, Johnbrick123, qlib, Testfolio_checker/ravelab SSO, Treasury composites). |
| `analysis_2026/split_delay.py`, `analysis_2026/results_split_delay/`, `analysis_2026/SPLIT_DELAY_PREREG.md` | Split-mode second-tranche delay sweep (section 5.20). Takes about 6 min on 4 workers. Daily basket returns (`basket_returns_P*.csv.gz`) are regenerated, not committed. |
| `agentic/`, `.claude/settings.json`, `.claude/commands/moneyline.md`, `analysis_2026/results_agentic_modes/` | Execution of the MoneyLine on the Robinhood Agentic account (section 8): signals, data feeds, planner, Claude Code safety hooks, `/moneyline` command; `python3 -m agentic --help`; tests `python3 -m pytest tests/test_agentic_*.py -q`. State in `private/agentic/` (gitignored). |
| `analysis_2026/larsson.py`, `analysis_2026/results_larsson/`, `analysis_2026/LARSSON_PREREG.md` | Larsson Line (EMA32/58) long-history study (section 5.19): S&P 500 1929-2026 and the pre-1928 Dow, 13 ETFs, 21 coins, point-in-time S&P and crypto top-20 baskets (daily-rebalanced and held), old MoneyLine and SMA200 comparators, realisation-based tax via `sso_gold.simulate`. `python3 -m analysis_2026.larsson` (about 30 min). Uses `data/sso_gold/`, `data/etf/`, `data/crypto_4h/`, `data/crypto_binance/` and `data/universe_pit_all/` (all gitignored). |
| `analysis_2026/theory_strategies.py`, `analysis_2026/results_theory/`, `analysis_2026/THEORY_PREREG.md` | Ten theory-driven strategies S1-S10 (section 5.16), run with `python3 analysis_2026/theory_strategies.py` (about 2 min). Needs `data/ff/ff3_daily.csv`: Ken French daily FF3 + Mom 1926-2026, built from the GitHub mirror ZachTheAnalyst/trend-following-crash-insurance. It also uses `data/etf/`, `data/universe_pit_all/`, `data/crypto_binance/` and `data/crypto_funding/` (all gitignored). |
| `analysis_2026/results_strictness/` | Strictness-study outputs, audited v3: per-window rows (incl. picks) and chained tables for development, holdout A and forward B; calibration rows. |
| `analysis_2026/FINDINGS.md` | Chronological log (see the audit-correction sections at the end). |
| `analysis_2026/moneyline_ref.py` | **Exact indicator from OHLC** (`moneyline`, `supertrend`, `to_weekly`). Not used by the backtests; needs high/low. |
| `analysis_2026/replicate.py` | IWM replication and hl2-consistency evidence. |
| `analysis_2026/gate.py` | Per-asset, per-vehicle validation gate (after tax; vs own buy & hold and vs SPY), index INSURANCE test, `placebo()` false-pass estimate, `asof` for walk-forward use. |
| `analysis_2026/costs.py` | Robinhood cost sensitivity; weekend-aware spot-ETF proxy (`etf_want`, `etf_proxy`). |
| `analysis_2026/portfolio.py` | Portfolio sizing comparison. |
| `analysis_2026/supplementary.py` | Losing trades, late entry (medians and pooled geometric means), entry distance and exit overshoot, era split, daily-AND-weekly, fill convention. |
| `analysis_2026/run_full.py` | Real-signal crypto backtests (daily/weekly); `load()`, `bt()`. |
| `analysis_2026/run_stocks.py` | Stocks/indices incl. TSLA/HOOD/CRCL; dividend/cash-yield view. |
| `analysis_2026/confirmation.py` | Confirmation-filter decomposition and leverage model. |
| `analysis_2026/stops.py`, `run_stops.py` | ATR stop-loss study. |
| `analysis_2026/run_tv.py`, `tv.py` | Real signal vs old models on the 300-bar exports (agreement % only). |
| `analysis_2026/results_*.csv` | Current tables: full, stocks, stops, costs, etf_proxy, gate, insurance, portfolio. |
