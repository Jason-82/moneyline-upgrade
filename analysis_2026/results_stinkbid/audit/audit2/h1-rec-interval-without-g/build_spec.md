# Stink-bid study: module contracts for the build agents

The frozen design is `analysis_2026/STINKBID_PREREG.md` (commit 72ac2a4). It is the source of truth. Where it is
silent, `analysis_2026/research_notes/Stink bids/design_draft.md` (commit ae5425c) applies (level formulas §6.2,
capacity window §8.3, data series §4.1). The three critiques in the same folder explain the reasons. This file only
fixes how the code is split so modules written in parallel fit together. If this file and the pre-registration
disagree, the pre-registration wins; say so in your report.

## Ground rules for every agent

- **Frozen design.** Implement the pre-registration; never change a rule, threshold, window or universe. Where it is
  silent, take the most literal reading, write it in your module docstring under "Coding choices the
  pre-registration leaves open", and list it in your report.
- **No result peeking.** On real data you may compute counts, coverage, fill frequencies, timings and fill-audit
  status. Never compute, print, compare or tune on post-fill prices, returns, P&L, a_f, Δ, knife rates or any other
  outcome on real data. Correctness is shown on synthetic data with known answers (and oracles computed by separate
  code).
- **File ownership.** Write only your own module(s), scratch files under
  `/tmp/claude-0/-home-user-moneyline-upgrade/5e565363-4044-518a-a642-8a4d3835a58f/scratchpad/sb_<agent>/`, and data
  under `data/stinkbid/` (gitignored). Do not edit other modules, the pre-registration, HANDOFF.md or FINDINGS.md. Do
  not commit or push. Never call any Robinhood tool.
- **Public repo.** Never write anything personal (accounts, balances, positions, orders).
- **Style.** Match the repo (see `analysis_2026/bb_engine.py`, `bb_stats.py`, `fetch_bb_data.py`): a module docstring
  citing the pre-registration sections; plain functions; numpy/pandas; numba (installed) for minute loops. Python 3.13,
  numpy 2.5, pandas 3. Machine: 4 CPUs, 15 GB RAM, ~28 GB free disk.
- **Self-test.** `python3 -m analysis_2026.<module> selftest` runs synthetic known-answer checks and asserts, in under
  15 minutes.
- **Times** are UTC (`datetime64[ns, UTC]`, bars labelled by their open time). New York conversions use
  `zoneinfo.ZoneInfo("America/New_York")`.
- **Existing data and code to reuse.** `data/stinkbid/` was built by `analysis_2026/fetch_stinkbid_data.py` (read its
  docstring and `research_notes/Stink bids/data_inventory.md`): 1d spot for all USDT pairs (`d1_spot_all.parquet`),
  1h spot for 486 candidates (`h1_spot/`), USD-M 1d (`d1_um/`), event aggTrades, universes, coverage tables. The
  Binance archive is reachable only through the path-style S3 URL in `analysis_2026/fetch_scalping_data.py` (`S3`,
  `s3_ls`, `s3_get_zip_csv`); `analysis_2026/fetch_bb_data.py` has checksum-verified kline building. The read-only
  Robinhood catalog of 2026-11-18 is saved at `data/stinkbid/ref/currency_pairs.json`. Reuse `bb_stats.holm`,
  `scalp_stats.holm`, `regime_switch.rf_annual_pct`, `moneyline_ref` (the replicated pre-October-2026 MoneyLine) where
  they fit.

## Modules and contracts

### `stinkbid_data.py` (agent: data)
- **Universes** (prereg §5): `universes() -> DataFrame[month, coin, U_B, U_Q1, U_Q1_12, U_Q1_xm, U_C, U_A, rank,
  rank_med12, listing_age_months]`, point in time. Listing age across quote assets (USDT, BTC, BNB, ETH, BUSD);
  successors inherit age and ranks; ticker reuse restarts; stablecoin exclusions incl. PAX/USDP and the 0.5% backstop.
- **Bars:** `m1(coin, start=None, end=None)`, `h1(coin)`, `d1(coin)` -> spot klines with columns open, high, low,
  close, volume, quote_volume, trades, taker_buy_quote and `seg` (segment id, prereg §4.1). Prices float64. 1m bars
  cached as per-coin parquet under `data/stinkbid/m1_spot/` (fetch for U-Q1 ∪ U-Q1-12 ∪ U-A ∪ U-C; stream the rest of
  U-B on demand: `m1_stream(coin)` returns the frame without keeping the file).
- **Futures:** `index1m(coin, day)`, `perp1m(coin, day)` (cached, with the index klines' update-count field named
  `updates`), `metrics(coin)` (5-minute open interest), `mark1h(coin)`; `index_fetch_days(...)` implementing prereg
  §4 / V4's fetch rule. Missing archive files are recorded, not filled.
- **Capacity:** `agg_capacity(coin, day, windows)` -> seller-initiated (is_buyer_maker = True) notional printed below
  each level within each window, streamed from aggTrades (download, reduce, discard), cached as small parquet.
- **Integrity:** `segments(coin)` (boundaries: missing day or >25% jump across a no-trading gap), redenomination joins
  and swaps with ratios (the prereg lists; unconfirmed ratios -> delisting), `delist_value(coin)` (VWAP of the last
  full trading day; last trade as a sensitivity).
- **Other:** `usdt_usd_hourly()` (USDC/BUSD/TUSD vs USDT proxy), `rh_pairs()` (ticks, quantity increments, min/max
  sizes from the saved catalog), `tbill_daily(index)`.
- **CLI:** `python3 -m analysis_2026.stinkbid_data {universes|m1|index1m|perp1m|agg|metrics|ages|d1-2017|all} ...`
  with resumable caches and checksum verification.

### `stinkbid_levels.py` (agent: levels)
- `inputs_at(coin, t0, data=None) -> dict(P0, sigma30, atr_pct, tick, seg_ok, ...)`: spot inputs through d0 (the last
  completed UTC day before t0), futures inputs through d0 − 1 (prereg §6.1). Tick from decimal strings of the last 7
  days of 1m prices.
- `level(method, inputs, **params) -> (L, delta)` for M1, M2, M2a, M3 (pooled expanding quantile calibration; needs
  daily bars back to 2017-08), M4, M4f, M4s, M5f, M5a, M5b, M6, M7, M8 exactly per prereg §6.2 / draft §6.2; returns
  None when a chart method abstains (δ outside [4, 14]).
- `placebos(L, atr_pct)` (±0.5, ±1.0 ATR%), `rh_round(coin, L)` (floor to Robinhood's tick; δ recomputed).
- Injection: every function accepts injected frames so controls can feed synthetic or perturbed data.

### `stinkbid_engine.py` (agent: engine)
- `run_program(program, universe, coins=None, data=None, cfg=None) -> dict` with:
  - `bids`: one row per bid (coin, program, method, rung/param, t0, P0, L, delta, sigma30, live_from, life_end);
  - `fills`: one row per fill (bid id, fill minute, gap_through flag, F2/F1/F3/F3d/F4/F5 flags per s, capacity
    C(L) and filled share at Q = 1k/10k/100k and theta = 1/0.25, s24/s6/s1 speeds, market-wide flag, episode id,
    month-block id, MoneyLine state at d0 and at the fill day's close);
  - `outcomes`: per fill and per exit/route/cost scenario: r_f, the twin mean (B-TWIN, 100 twins; B-POST), Δ, a_f
    (B-ALERT, rule M and fixed delays), B-ML, recovery-curve flags (D12), knife and lowest-price fields (T1, D-H5);
  - `audit`: fill-audit violations (K5 rules: gap-through fills at the limit allowed and listed).
- Programs: P1, P1-30, P1-90, P1-1, P1-lazy, P1-G, the M1/M2a/M3/M8 rows, and the H4 chart programs (M4 N=90 0.5 ATR,
  M5b, M6, M7 and every other M4/M5 variant) each with their four placebos (stacked, with coin-week ids).
- Fill rules F1-F5 and capacity exactly per prereg §7; exits X-FLIP (manual clock M), X-FLIP-bot, the flip grid,
  X-HOLD-h, X-OWN, X-ML per §8; costs per §9; benchmarks per §10.1.
- `accounts(...)` for D7 (flip account, one position per rung, carry) and D7-OWN, with B-MIX, B-TBILL, B-DCA,
  B-ALERT-DCA, B-ML-DCA, B-HOLD.
- Injection of synthetic 1m data (frames shaped like `stinkbid_data.m1`, plus index frames) so the controls can run
  the engine on synthetic paths. Numba for minute loops.
- A `counts_only=True` mode that produces bids and fills but computes no outcome (for the "fill counts before returns"
  stage).

### `stinkbid_stats.py` (agent: stats)
- CR1 with G/(G−1); `gstar(cluster_sizes)`; the wild cluster restricted bootstrap-t (Webb six-point, B = 9,999);
  `p_decide = max(p_WCR, p_Gstar)`; NO EDGE bound = max(wild bootstrap-t bound, θ̂ + t_{1−0.05/3, G*−1}·SE) at
  1 − 0.05/3 (prereg §10.2).
- H4: the stacked regression with coin-week fixed effects and a depth term per method; Romano-Wolf max-t with wild
  (Webb) multipliers on month-block score sums; the Bonferroni t(G*−1) companion (prereg §10.3).
- Holm on the three decisive p-values; BH for descriptive tables; verdict mapping with E and HARMS; MDE =
  (t_{1−α_b, G*−1} + t_{0.80, G*−1})·SE.
- Descriptive machinery: two-way (coin × quarter) clustering with min(G)−1 df; Ibragimov-Müller; month-block and
  episode construction from fill timestamps (episodes = fill days at most 3 days apart; month-blocks merge months
  linked by an episode); Kaplan-Meier waiting times with restricted mean (365 days); overdispersion φ; stationary
  block bootstrap for accounts (6- and 12-month mean blocks); episode-cluster bootstrap for D5.
- `inference_calibration(sim_fn, n_reps, scenarios)` used by the controls (K3): false-PASS rates at 1.67/2.5/5%, NO
  EDGE miss rates, and the simulation-calibrated p rule.

### `stinkbid_controls.py` (agent: controls)
- The synthetic market (1m; ≥ 40 coins; 6.9 years; Student-t(4) market and idiosyncratic shocks; volatility regimes;
  K1b jumps tuned to P1's real fill counts within ±25%; K1c regime drift; K1d delistings; K2 transient jumps) and an
  oracle written as separate code (not importing the engine's fill/exit functions).
- K1-K8 exactly per prereg §10.5, writing `analysis_2026/results_stinkbid/controls/{summary.json, summary.txt, ...}`
  with `all_passed`, the K3 calibration (and any simulation-calibrated p mapping and bound quantiles), the K3 power
  re-run (MDEs by test), and D11's null distribution.

### `stinkbid_run.py` and `stinkbid_desc.py` (agent: runner)
- CLI stages in prereg §14 order with gating (each refuses until the previous stage is complete; primary refuses
  unless controls `all_passed`): `data | controls | fcount | primary | report | desc | explore | sheet | status`.
- `fcount` writes every program's fill counts before any outcome exists.
- `primary`: H1, H2R, H4 per prereg §10.3 (all gates), using `stinkbid_stats`.
- `report`: Holm, verdicts, and the answer per prereg §11 (recommendation table, fixed sentences with their numbers,
  descriptive sentences), written to `results_stinkbid/verdicts.txt`, `verdicts.csv`, `answer.json`.
- `desc` / `explore`: every descriptive estimand, table, sensitivity row and exploratory split in prereg §10.4, with
  the reporting rules of §12.

### `stinkbid_sheet.py` (agent: sheet)
- The level sheet exactly per prereg §13, reading verdicts and descriptive outputs from `results_stinkbid/` to decide
  what is shown, Robinhood ticks from the saved catalog, and fresh reference prices from `--price`. Git Bash-friendly
  CLI. Never places orders.

## Performance targets (4 CPUs)

- 1m fetch for the primary set: < 30 min; U-B streaming: < 45 min; aggTrades capacity: < 40 min.
- P1 on U-Q1 with outcomes and 100 twins per fill: < 30 min.
- K3: ≥ 2,000 null replications per scenario × 3 scenarios: < 2 h in total (hourly synthetic paths are allowed for K3).
