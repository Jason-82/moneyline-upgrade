# agentic/ — build spec

Implements `AGENTIC_TRADING_PLAN.md`. Deterministic Python decides and Claude only operates the Robinhood MCP tools.
Read the plan's sections 2, 3, 6 and 7 before changing anything here.

**The repo is public.** Code, tests and docs are committed. Everything under `private/agentic/` is state and must
never be committed: config with account numbers, raw tool captures, signals, plans, journal, digests. Tests must use
`AGENTIC_STATE_DIR=<tmp>`.

**Dependencies:** pandas and numpy only, plus `urllib` for HTTP. `yfinance` is an optional import. Hooks use the
standard library only.

## 0. Vocabulary

- **asset:** one entry in `config["assets"]` (see `agentic/config.py` and `config.example.json`).
  - **signal:** where the green/red state comes from.
  - **vehicle:** what is actually traded.
  - Example: signal = Coinbase ETH-USD, vehicle = the ETHA ETF.
- **signal source:**
  - `computed`: the old MoneyLine, replicated exactly from OHLC (`analysis_2026/moneyline_ref.py`: Wilder
    ATR10 × 2.0 around hl2, reset-on-flip).
  - `tv_export`: the new October 2026 TradingView MoneyLine, read from the user's CSV export.
- **mode:** a list of tranches `{weight, n_entry, n_exit}` whose weights sum to 1.
  - Tranche k is long while its own N-confirmed state is green.
  - **target_frac** = Σ weight_k · green_k ∈ [0, 1].
  - Built-ins:
    - `immediate` = [(1.0, 1, 1)]
    - `split` = [(0.5, 1, 1), (0.5, 5, 5)]
    - `confirm5` = [(1.0, 5, 5)]
- **N-confirmed state:** flip only after N consecutive closes beyond the still-trailing line; a close back inside
  resets the count. This is `analysis_2026/flip_delay.moneyline_delay` generalized to a separate N for entries
  (red→green) and exits (green→red). N=1 must equal `moneyline_ref.moneyline(df).green` exactly.
- **Closed bar:**
  - Crypto: the daily bar labelled D, from D 00:00 UTC to D+1 00:00 UTC. It is closed once now ≥ D+1 00:00 UTC.
    Coinbase and TradingView both label by the open.
  - Stocks: the session D is closed after 16:20 ET on an NYSE trading day (`screener/data.py`
    `last_closed_session`, extended with the holiday calendar in `agentic/calendar.py`).
  - Never compute on a forming bar.

## 1. Modules and owners

| file | owner | purpose |
|---|---|---|
| `config.py` | done | load/validate config, state paths, `tranches_for` |
| `entry.py` | done | entry policy (join / join_recent / fresh_only), shared by `signals.py` and `planner.py` |
| `universe.py` | done | crypto universe: every Robinhood coin, filtered, mapped to a spot ETF or direct (section 13) |
| `indicator.py` | A | N-confirmed MoneyLine with separate entry/exit N, tranche targets, tv_export reader |
| `backtest.py` | A | modes vs buy & hold on any OHLC (fractional weights) |
| `calendar.py` | B | NYSE trading days and holidays, closed-bar dates, execution session, `valid_until` |
| `data.py` | B | bar feeds (coinbase, robinhood inbox, yfinance, csv), normalisation, data checks |
| `snapshot.py` | C | parse raw MCP captures in the inbox into an account snapshot, with validation |
| `planner.py` | C | signals + snapshot + config → plan (orders, cancels, ref_ids, collars, caps) |
| `ledger.py` | C | journal (jsonl), daily notional ledger, reconcile |
| `hooks/pre_tool_use.py` | D | guard every Robinhood MCP call (fail closed) |
| `hooks/post_tool_use.py` | D | save raw tool results to the inbox; journal place/cancel; approval check |
| `.claude/settings.json` | D | register hooks; deny unused write tools |
| `signals.py` | E | phase 1: feeds → checks → indicator → `signals_<date>.json` + digest |
| `cli.py`, `__main__.py` | E | `.venv/Scripts/python.exe -m agentic <cmd>` (section 12) |
| `README.md`, `.claude/commands/moneyline.md` | E | runbook and daily slash command |

Tests go in `tests/test_agentic_<module>.py` and run with `.venv/Scripts/python.exe -m pytest tests/test_agentic_*.py
-q` in Git Bash (`.venv/bin/python` on macOS/Linux). They must not touch the network; mock urllib.

## 2. indicator.py (A)

```python
def moneyline_confirmed(df, n_entry=1, n_exit=1, period=10, factor=2.0) -> pd.DataFrame
```

- `df`: DatetimeIndex with open/high/low/close in any case.
- Returns columns:
  - `green` (bool)
  - `line` (float; the trailing line on that bar, NaN during warm-up)
  - `pending` (int; consecutive closes beyond the line not yet confirmed, 0..N-1)
  - `flip` (+1 / -1 / 0; a confirmed flip on this bar)
  - `atr` (float)
- Logic is `flip_delay.moneyline_delay` with threshold `n_entry` while red and `n_exit` while green. Its first-bar
  seeding is: `is_green = close >= hl2`, then `stop` from the matching band.
- The line keeps trailing during pending bars. After a flip the line restarts at the flip bar's fresh band (reset
  variant).
- **Tests:**
  - n=1 equals `moneyline_ref.moneyline(df)` green and line exactly, including on an IWM-like random walk.
  - n_entry = n_exit = N equals `flip_delay.moneyline_delay(df, N)`.
  - Asymmetric N is honoured.

```python
def tranche_targets(df, tranches) -> pd.DataFrame
```

- Returns one column per tranche (`g0`, `g1`, …, bool) plus `target_frac` (float).
- Also returns `pending0`, … and `line0`, … for the digest.

**tv_export (new indicator):**

```python
def read_tv_export(path_glob) -> pd.DataFrame
```

- Picks the newest file matching the glob by mtime and parses the TradingView CSV.
- `time` can be unix seconds or ISO. Map it to a date: for crypto the UTC date of the open; for stocks the exchange
  date.
- Keeps `close`, plus `open`/`high`/`low` if present, and the columns `Direction`, `ConfirmCount`,
  `MoneyLine Level`.
  - Column names may carry suffixes such as `Direction.1`. Match case-insensitively on the prefix.
  - Direction −1 = bull.

```python
def tv_export_targets(df, mode_name) -> pd.DataFrame
```

- `immediate_green` = (D == −1 & cnt == 0) | (D == 1 & cnt ≥ 1). On the user's exports this was 100% equal to
  close > the previous bar's level.
- `confirm_green` = (D == −1).
- `target_frac`:
  - immediate → immediate_green
  - confirm5 → confirm_green
  - split → 0.5·immediate + 0.5·confirm
- Also returns `level`, `pending` = cnt, `direction`, and `confirm_green_early` (the confirmed state from the close
  on which ConfirmCount reaches 5). `signals.py` and the tv backtest trade `confirm_green_early` by default
  (`signal.tv_confirm: count`; Direction flips one bar later in every export checked); `direction` uses
  `confirm_green`.
- The last row of an export is the live, forming bar. The caller (`signals.py`) drops rows after the expected closed
  bar date.

## 3. backtest.py (A)

```python
def weights_returns(df, w, cost, cash_rate_annual=None) -> tuple[pd.Series, int]
```

- `w[t]` is decided at close t and held from the next open. On a change day i, the old weight earns the move from
  the prior close to the open, then the new weight earns the move from the open to the close.
- Costs: `cost × |Δw|` at the open. The cash share earns T-bills (`screener.strictness.TBILL` by year, calendar-day
  compounding, as `flip_delay.strat_returns`).
- Must equal `flip_delay.strat_returns(df, green, cost)[0]` when w ∈ {0, 1} (test).
- Returns the daily returns and the number of weight changes.

```python
def compare_modes(df, cfg_modes, cost, ppy, start=None, st_rate=0.35, lt_rate=0.20) -> pd.DataFrame
```

- One row per mode plus BUY & HOLD.
- Columns: CAGR_%, CAGR_tax_% (strategies: 35% on each year's growth with loss carry, as `flip_delay.stats`; B&H:
  20% once at the end), Sharpe, maxDD_%, trades_per_yr, exposure_%.
- The warm-up of 120 bars is excluded.

```python
def load_history(asset, cfg) -> pd.DataFrame
```

- For the CLI. Tries, in order:
  1. a local CSV path given on the command line
  2. repo data: `flip_delay.load_crypto_daily(sym)` for crypto, `flip_delay.load_etf(sym)` for the 13 ETFs,
     `data/universe_pit_all/<SYM>.csv` via `screener.data.from_csv_folder` for stocks
  3. the asset's live feed (`data.py`)

## 4. calendar.py (B)

Standard library plus pandas.

- `nyse_holidays(year) -> set[date]`:
  - New Year (observed, but not when Jan 1 is a Saturday)
  - MLK (3rd Monday of January)
  - Presidents (3rd Monday of February)
  - Good Friday (Easter − 2, anonymous Gregorian algorithm)
  - Memorial (last Monday of May)
  - Juneteenth (observed, from 2022)
  - Independence Day (observed)
  - Labor (1st Monday of September)
  - Thanksgiving (4th Thursday of November)
  - Christmas (observed)
- Observed rule: Saturday → Friday, Sunday → Monday.
- `is_trading_day(d)`.
- `last_closed_equity_session(now_utc) -> date`: the latest trading day whose 16:20 ET has passed.
- `last_closed_crypto_bar(now_utc) -> date`: the UTC date of the latest fully closed daily bar, i.e. today_utc − 1.
- `execution_session(now_utc) -> date`:
  - today if today is a trading day and now < 15:45 ET
  - else the next trading day
- `valid_until(vehicle_type, now_utc, limits) -> datetime (UTC)`:
  - equity: 15:45 ET on the execution session
  - crypto: now + `limits.plan_valid_min_crypto`
- `market_open(now_utc) -> bool`: 9:30–16:00 ET on a trading day. Half days count as normal; documented as a
  limitation.
- `ET`: `zoneinfo("America/New_York")` when a tz database exists, else the built-in `USEastern` tzinfo (2007+ US
  DST rule, PEP 495 folds as zoneinfo); `ET_SOURCE` is `"zoneinfo"` or `"fallback"`. Windows has no system tz
  database, and the hooks may run on a Python without `tzdata`. `ledger.ET` is this object.

## 5. data.py (B)

Every feed returns a DataFrame with a date index (naive, normalised) and float columns open/high/low/close (volume
optional), ascending, one row per bar, closed bars only.

- `fetch_coinbase_daily(product, start, end=None, opener=urllib.request.urlopen)`:
  - Endpoint: `GET https://api.exchange.coinbase.com/products/{product}/candles?granularity=86400&start=…&end=…`.
    It returns at most 300 rows of `[time, low, high, open, close, volume]`, newest first; paginate backwards.
  - Send a User-Agent header. Retry 3 times with backoff on HTTP 429/5xx.
  - Drop the forming bar (date ≥ today UTC).
- `load_robinhood_bars(inbox_dir, symbols) -> dict[sym, df]`:
  - Reads the captures saved by the PostToolUse hook (format in section 8) whose `tool` ends with
    `get_equity_historicals`.
  - Parses with `screener.data.from_robinhood_json` logic, applied to the capture's `response` object rather than a
    file. Merges multiple captures, the newest bar wins.
  - Requires interval 'day'.
  - Drops interpolated bars and bars after `last_closed_equity_session`.
- `fetch_yfinance(symbol, start)`: optional import; `auto_adjust=False`, split-adjusted OHLC, never 'Adj Close'.
- `load_csv(path)`: via `screener.data.normalise`.
- `get_bars(asset, cfg, now_utc, inbox_dir, offline=False) -> df`: dispatches on `asset["signal"]["feed"]`. It fetches at least
  `limits.min_bars + 150` bars (about 2 years of crypto; for stocks request ≥ 700 calendar days), or the asset's own
  `min_bars + 150` if larger (universe coins).
- **Coinbase cache** (`coinbase_daily_cached(product, start, now_utc, opener=None, *, base, pace, sleep, issues,
  retries, timeout, offline)`, used by `get_bars` and the universe):
  - Stored in `<state>/cache/coinbase/<PRODUCT>.csv` (date, OHLC, volume) plus `meta.json` (per product
    `history_from`, the earliest start ever requested, `full_fetch`, the UTC date of the last full fetch, and `gaps`,
    the days missing from Coinbase's own history at that fetch).
  - Only bars after the last cached closed bar are fetched, none when it is the last closed bar. Older history is
    fetched only for a start earlier than `history_from`.
  - A missing, unreadable or corrupt cache (NaN or ≤ 0 prices, duplicate or unsorted dates) is fetched again in
    full; so is one with missing days that are not in `gaps`, at most once per UTC day (Coinbase skips days
    without trades, so a permanent hole is neither fetched again nor warned about).
  - `offline`: no request; the cached bars as they are, DataError without a readable cache (after the universe
    scan found Coinbase unreachable). `retries` / `timeout` per request (default 3 / 30 s).
  - A bar is cached only once it closed at least 5 minutes before the fetch.
  - Requests are paced by `Pacer` (`PACER`, at most 5 per second), on top of the retry and backoff above.
- `coinbase_products(now_utc, opener=None, *, base, pace, sleep, retries, timeout)`: `GET https://api.exchange.coinbase.com/products`,
  cached for the UTC day in `cache/coinbase/products.json`, returning `{products: {ID: {base, quote, online}},
  fetched_at, error}`. A failed fetch falls back to an older cache; `products` is None without one.
- `median_dollar_volume(df, n=30)`: the median close × volume of the last `n` bars.

```python
def check_bars(df, expected_last: date, min_bars: int) -> dict(errors=[...], warnings=[...])
```

- **Errors:**
  - last bar ≠ `expected_last`
  - fewer than `min_bars` bars
  - NaN or ≤ 0 prices
  - high < max(open, close) or low > min(open, close) beyond 1e-9 relative
  - a one-day close ratio within 3% of 1/2, 1/3, 1/4, 1/5, 1/10, 2, 3, 4, 5 or 10 (a missed split), in the last 300
    bars
  - duplicate dates
- **Warnings:**
  - the last bar's true range > 4 × the prior ATR10 (a big wick: check TradingView before approving)
  - gaps longer than 5 calendar days (stocks) or 1 day (crypto) in the last 300 bars

## 6. snapshot.py (C)

Input: the inbox captures (section 8). Use the newest capture per tool, and for quotes the newest per symbol.
Field names follow the official schemas, from a capture of Robinhood's `tools/list` (2026-10-12):

- `get_portfolio` → `data.total_value`, `data.cash`, `data.buying_power.buying_power`, `data.crypto_buying_power…`
- `get_equity_positions` → `data.positions[]`: symbol, quantity, `shares_available_for_sells`
- `get_crypto_positions` → `data.results[]`: `currency.code`, quantity, `quantity_transferable`
- `get_equity_quotes` → per symbol: `bid_price`, `ask_price`, `last_trade_price`, timestamps.
  - Accept `data.results[]` or `data.quotes[]`. Be tolerant and test both.
- `get_crypto_quotes` → bid/ask/mark per pair symbol, e.g. 'ETH-USD'
- `get_equity_orders` / `get_crypto_orders` → open orders: id, `ref_id`, symbol or `currency_code`, side, state,
  `state_group`, quantity, `cumulative_quantity`, price
- `get_currency_pairs` → per pair: `min_order_size`, `asset_increment`, `quote_increment` (optional; defaults are
  6-decimal quantities and 2-decimal prices)

MCP wrappers to accept: a response may be the structured object, or `{"content":[{"type":"text","text":"<json>"}]}`,
or `{"structuredContent": {...}}`. Unwrap all three.

```python
def build_snapshot(inbox_dir, cfg, now_utc) -> dict
```

Returns:

```
{as_of, total_value, cash, buying_power, crypto_buying_power,
 equity_positions{SYM: {qty, sellable}}, crypto_positions{CODE: {qty, sellable}},
 quotes{SYM or PAIR: {bid, ask, last, ts}},
 open_orders[{id, ref_id, symbol, side, state, qty, filled, price, kind: 'equity'|'crypto'}],
 pairs{PAIR: {min_order_size, asset_increment, quote_increment}},
 errors[], warnings[]}
```

- **Errors:**
  - a required capture is missing: portfolio, equity positions, open equity orders; plus crypto positions and open
    crypto orders if any crypto vehicle is enabled or the crypto universe may trade coins directly
    (`config.direct_crypto_possible`), or, as the CLI passes `crypto=cli.crypto_needed(cfg)`, while the reconciled
    positions or this system's orders since then hold a coin (`ledger.holds_crypto`; fetch-list uses the same test)
  - a capture is older than `snapshot_max_age_min`
  - a quote needed for a planned order is older than `quote_max_age_min` or has bid/ask ≤ 0
  - a capture belongs to a different account number than the config. Captures store `tool_input`; check
    `account_number` / `rhs_account_number`.
- **Warning:** Σ positions × mid + cash differs from total_value by more than 2% + $1.

## 7. planner.py (C)

```python
def make_plan(signals, snapshot, cfg, now_utc, attempt=1, flags) -> dict
```

`flags` are read from the state dir: STOP, FLATTEN, BLOCK_BUYS.

**Entry policy** (`entry.py`; config `entry`, per-asset override `asset.entry`):
- `full_tf` = Σ w_k · green_k (the signal's `target_frac`); `entry_tf` = Σ w_k · green_k · eligible_k, capped at
  `full_tf`. Recomputed here from the tranche fields (section 12) with the planner's strategy start.
- eligible_k: `join` always; `join_recent` if `bars_since_green_flip` ≤ `max_join_bars` and, with
  `max_join_rise_frac`, close ≤ `flip_close` × (1 + rise); `fresh_only` also needs `last_green_flip_date` ≥ the
  strategy start (`entry.start_date`, else `strategy_start.json`, else the signals date). No flip in the history, or
  a signals file without the fields → not eligible.
- `strategy_start.json` is written by `write_plan` for the first plan with `live: true` (its signals date); the plan
  records the start it used in `strategy_start` (`entry.start_date`, else the recorded date, else the signals date)
  and per-asset `fresh_only` starts that differ in `strategy_start_assets`.
- A held position (worth ≥ `min_order_usd`) covers, first, the eligible tranches this system bought after their flip
  (a journaled buy placed after the flip bar closed), then the green tranches that may not be bought; `entry_tf`
  adds what it covers of the latter. So an old half the sleeve holds stays held while a fresh half is added, and the
  day after a fresh-half buy the old half is not bought instead.
- Buys raise a position only up to `entry_tf`; sells cut it only down to `full_tf`; between the two it is held. A
  green tranche that may not be bought adds its reason to the order reason (partial buy) or to `skipped`.

**Sizing:**
- `capital = min(snapshot.total_value, cfg.capital.max_usd)`
- Class caps: `allocation.class_max_frac` {crypto, equity} × capital; default crypto = `max_crypto_frac`, equity 1.0.
- `allocation.method` `fixed` (default when the block is absent): `slot_usd = capital × alloc_frac`; a class whose
  Σ slot_usd × min(full_tf, max(entry_tf, current/slot_usd)) (what the plan will hold; a holding without a quote
  counts at full_tf) exceeds its cap is scaled down proportionally (both targets).
- `allocation.method` `slots`: `slot_usd = slot_frac × capital` for every asset. A position worth less than
  `min_order_usd` is dust, not a holding (it may compete as a new entry).
  1. Every holding counts at its current value until the positions show it sold (an exit or a trim frees room only
     in a later plan, so a sell that is not placed or not filled never makes room); an enabled asset skipped this run
     whose sleeve holds shares reserves max(slot, sleeve qty × mid) and counts at its value in step 4 (a slot
     without a quote).
  2. Green holdings, earliest into their run first (the first journaled buy after the run's first green flip
     closed; none = first; ties in config order), keep up to a whole slot (`cap_usd`): the last one in gets the room
     left, so a partial slot grows only when capital frees up. Holdings are never trimmed to make room.
  3. New entries (not held, entry_tf > 0) in `priority` order (`crypto_first`: crypto class first, then equity;
     within a class the newest eligible green flip first, ties in config order, in which universe coins follow
     the explicit assets, the higher `dollar_volume_usd` of the signal first, then by name; `equity_first`,
     `newest_flip` (the same ties), `config_order`) take min(room, class room): a full slot, or a partial one if ≥ half a slot,
     else they wait (`skipped`: "no free slot"). `wash_sale_block_symbols` and hold-only universe coins take no
     slot; BLOCK_BUYS and FLATTEN hand out none.
  4. Buys (holdings first, then new entries, in priority order) are capped so the sleeve's positions, counted at
     their current value, plus this plan's buys stay within capital and each class cap ("no free capital" below
     `min_order_usd`).
  - `plan["allocation"]` = {method, priority, slot_frac, slot_usd, held[], new[{asset, usd, partial}],
    waiting[{asset, reason}], blocked (flag, if any)}; `format_plan` prints it as a `SLOTS` line.
- `full_usd = slot_usd × full_tf × scale`, `entry_usd = min(slot_usd × entry_tf × scale, cap_usd)`.
- `current_usd` = the sleeve's qty × mid. Mid = (bid+ask)/2, else last. The sleeve's qty is
  min(position, `ledger.sleeve_status` sleeve qty): config `sleeve_initial_qty` at the first baseline plus this
  system's own fills. Shares outside the sleeve are never sold (warning). No reconciled baseline → no orders; a
  vehicle whose captured position disagrees with baseline + own fills → that asset is skipped with an error.
- band = max(min_order_usd, rebalance_band_frac × slot_usd). Sell to `full_usd` if current > full_usd + band; buy to
  `entry_usd` if current < entry_usd − band; a full exit (full_tf == 0, position non-zero) always sells everything
  sellable, whatever the entry policy. A position worth
  less than `min_order_usd` with target 0 is "dust": sell it only if the vehicle allows that size; otherwise skip
  with a warning.

**Orders:**
- **Equity, whole shares:** `qty = floor(|Δusd| / price)`.
  - Use a limit at ask × (1 + collar) for buys and bid × (1 − collar) for sells. Round to $0.01; prices under $1
    round to $0.0001.
  - `time_in_force` 'gfd', `market_hours` 'regular_hours'.
  - `collar = equity_collar_frac × collar_ladder[attempt−1]`, capped at `max_collar_frac`.
- **Equity, fractional:**
  - Used when the vehicle has `fractional: true` and whole-share rounding would miss the target by more than 10% of
    |Δusd|, or qty would be 0.
  - Type 'market' with quantity to 6 decimals, regular hours only.
  - Fractional market orders may be planned only while `calendar.market_open(now)`. Otherwise add to `skipped` with
    "fractional orders need regular hours: re-run the plan during the session".
- **Crypto direct:** limit with quantity rounded down to `asset_increment` and price to `quote_increment`.
  `time_in_force` 'gtc' (Robinhood allows only gtc for crypto limits, valid 90 days), so the plan's `valid_until`
  matters: the next plan cancels it.
- **Full exits:** sell the snapshot's sellable quantity (`shares_available_for_sells` / `quantity_transferable`),
  capped at the sleeve's qty, never more.
- **Market orders** (fractional) only while `market_open(now)` and `execution_session(now)` is today (before 15:45 ET).
- **Crypto pair metadata** (`asset_increment`, `quote_increment`) is required; without it the asset is skipped with
  an error. A price that rounds to 0 at its tick skips the asset, never the whole plan.
- **Quotes it needs:** a missing, stale or unusable quote for an asset the plan would trade skips that asset; its
  `skipped` reason names the call to repeat, and `plan["refetch"]` holds the exact calls (`get_equity_quotes`
  `{symbols}`, `get_crypto_quotes` `{symbols, rhs_account_number}`, 20 symbols each). It is also an error, except
  for a universe coin's new entry. With slots, a universe candidate without a quote still competes for a slot; one
  that gets a slot holds it while its quote is fetched, and one that does not needs no quote and is not reported.
  `cli.format_calls` prints the calls first as `RE-FETCH QUOTES`; `plan` without `--attempt` keeps the attempt
  while the current plan lists them.
- **Hold-only universe coins** (`asset.universe.hold_only`): no buys; sells and exits as usual.
- **notional_usd** is q × price rounded up to the cent; max_order_usd, max_day_usd and buying power hold on those
  rounded values.
- **Buys:**
  - capped by available buying power (crypto: `crypto_buying_power`)
  - capped per order at `max_order_usd`; split into several orders only if needed, keys `…|0`, `…|1`
  - the day total must stay under `max_day_usd`, using the ledger's placed notional today
- **Flags:**
  - STOP: no orders at all (the plan has `orders=[]` and lists why).
  - FLATTEN: every target → 0, sells only.
  - BLOCK_BUYS: sells only.
  - An asset whose signal has errors is skipped entirely, with an alert.
  - `wash_sale_block_symbols`: no buys of those symbols.
- **Wash-sale warning:** the journal shows a loss sale of the same equity symbol in the last 30 days (sell
  average_price < the position's average_buy_price, recorded at the time) → warning. Crypto is exempt.
- **ref_id:** `str(uuid.uuid5(NAMESPACE_URL, f"moneyline|{plan_id}|{key}|{attempt}"))`.
  - `plan_id` = `f"{signals_date}-{sha1(json.dumps(orders_core, sort_keys=True))[:8]}"`, so identical inputs give
    an identical plan.
  - `key` = `f"{asset}|{vehicle_symbol}|{side}|{i}"`.
- **Cancels:** every open order of this system (`ledger.is_own_order`, or agent-initiated on a managed vehicle)
  that is not in this plan, i.e. stale plan orders, goes into `plan["cancels"]` as cancel tool params; STOP cancels
  the same set. The user's own orders are never cancelled: on a managed vehicle they hold that asset back ("cancel
  it in the app"), elsewhere they are ignored. A plan never places a new order for a symbol that still has an open
  order: it cancels first and says "re-run plan after the cancel settles (`plan --attempt N`)".

**Plan JSON** (written to `plans/plan_<plan_id>.json` and copied to `plan_current.json`):

```json
{"plan_id": "...", "created_at": "...Z", "valid_until": "...Z", "live": false, "attempt": 1,
 "account_number": "...", "rhs_account_number": "...", "capital_usd": 0.0,
 "signals_file": "signals/signals_2026-10-17.json",
 "orders": [{"key": "ETH|ETHA|buy|0", "asset": "ETH", "tool": "place_equity_order", "preview_tool": "review_equity_order",
             "params": {"account_number": "...", "symbol": "ETHA", "side": "buy", "type": "limit", "quantity": "12",
                        "limit_price": "25.43", "time_in_force": "gfd", "market_hours": "regular_hours", "ref_id": "..."},
             "notional_usd": 305.16, "reason": "target 0.50 -> 1.00 (tranche 2: 5/5 closes above the line)"}],
 "cancels": [{"tool": "cancel_equity_order", "params": {"account_number": "...", "order_id": "..."}, "reason": "..."}],
 "skipped": [{"asset": "...", "reason": "..."}], "warnings": [], "errors": [], "refetch": []}
```

- All params are strings, exactly as they will be sent. Claude copies them verbatim; the hook compares them
  exactly.
- `preview_tool` params = `params` minus `ref_id`.

## 8. Inbox capture format (written by hooks/post_tool_use.py, D; read by data.py/snapshot.py)

- File: `inbox/<YYYYMMDDTHHMMSS.ffffffZ>_<short_tool>.json`, where `short_tool` is the part after the last `__`,
  e.g. `get_equity_positions`.
- Content:

```json
{"captured_at": "...Z", "tool": "<full tool name>", "tool_input": {...}, "response": <tool_response exactly as received>}
```

- Never edit or reformat `response` beyond JSON serialisation.
- Captured tools: every `get_*` tool, `search`, `review_equity_order`, `preview_crypto_order`, and every
  place/cancel result.
- Files are private; the hook never prints their content.

## 9. hooks/pre_tool_use.py (D)

- Reads the hook JSON on stdin: `tool_name`, `tool_input`, `cwd`.
- The tool is a Robinhood tool if `tool_name` matches `^mcp__.*robinhood.*__` (case-insensitive). Anything else →
  exit 0 immediately.
- **Classification by short name:**
  - **read:** `get_*`, `search`, `preview_scan`, `run_scan`, `get_*_onboarding_info` → allow.
  - **simulate:** `review_equity_order`, `preview_crypto_order` → allow if `tool_input` targets the configured
    account; log.
  - **trade:** `place_equity_order`, `place_crypto_order` → allow only if ALL of these hold (otherwise exit 2 with a
    one-line reason on stderr):
    1. no STOP file
    2. config `live` is true
    3. `plan_current.json` exists, `now < valid_until`, and the plan's account numbers match the config
    4. an order in the plan has `tool` == short name and `params` == `tool_input` exactly, comparing JSON values
       as strings with surrounding whitespace stripped, and no extra keys in `tool_input`
    5. FLATTEN or BLOCK_BUYS present → side must be 'sell'
    6. the order's `notional_usd` ≤ `max_order_usd`
    7. the ledger's placed notional today (ET date) + this notional ≤ `max_day_usd`
    8. the same `ref_id` was not already placed successfully today (a retry of a transport failure is allowed if
       the journal shows no order id for that ref_id)
    9. added after review: the plan has `live: true`, `created_at` not in the future, a lifetime ≤ 24 h and a
       planner-shaped `plan_id`; the call's `ref_id` equals `ref_id(plan_id, key, attempt)`; the order has a
       planner shape (equity: gfd regular_hours limit, or market without limit_price; crypto: gtc limit; never
       dollar_amount / tax_lots / stop_price); a market order only in regular hours before 15:45 ET; caps 6-7 use
       max(plan notional, quantity × limit_price or × the newest captured quote); config `live` must be `true`
  - **cancel:** `cancel_equity_order`, `cancel_crypto_order` → allow if `order_id` is in `plan.cancels`, or the
    journal shows an order this system placed. Cancels are allowed even under STOP (the kill switch must be able to
    pull orders).
  - **everything else** (options, alerts, scans, watchlists, `exercise_option`, unknown tools) → block.
- Any exception while handling a trade/cancel/unknown tool → exit 2, fail closed. On a read tool → exit 0 and log the
  exception.
- Every decision is appended to `hook.log` as JSON: ts, tool, decision, reason, ref_id. No account numbers or
  balances in the reason text.

## 10. hooks/post_tool_use.py (D)

- Robinhood tools only. Saves the capture (section 8) for read, simulate and trade tools.
- For place/cancel it appends to `journal.jsonl`:
  `{ts, event, tool, plan_id, key, ref_id, params (minus account numbers), order_id, state, placed_agent, agent_initiated, error}`.
- For a successful place it adds `notional_usd` from the matching plan order to `ledger.json[ET date]`.
- **Approval check:** if config `account.approvals_required`, a successful place response with any non-null
  `data.order` (whatever `placed_agent` says: an approval happens later, in the app) means the agent's order went
  live without the user's approval. Write STOP with that reason and print a loud warning on stderr (the warning is
  printed even if STOP cannot be written).
  - `data.order` null or omitted, with no order fields in `data`, is recorded as
    `"state": "proposal_pending_approval?"`; order fields without `data.order` → STOP ("unrecognised"). The exact
    approval response shape must be confirmed on the first live order (README).
  - `get_equity_orders` / `get_crypto_orders` results are checked too: an order carrying a ref_id of a journaled
    proposal or of the current plan (approved orders carry the approval's id), or a recent one with
    `placed_agent` / `initiator_type` agentic, → STOP once per order (journal event `approval_bypass`).
- A Robinhood tool outside the allowlist that ran → STOP.
- `PostToolUseFailure` events (the same script is registered for them): a failed place is journaled as
  `failed_or_unknown` (the order may exist) and its plan notional is counted in the ledger.
- Files are written ASCII-escaped, so odd characters in a response never drop a capture or journal line.
- Never block (always exit 0); log errors to `hook.log`.

## 11. .claude/settings.json (D)

`.claude/settings.json` is authoritative; its PreToolUse entry is:

```json
{"matcher": "mcp__.*[Rr][Oo][Bb][Ii][Nn][Hh][Oo][Oo][Dd].*",
 "hooks": [{"type": "command", "timeout": 30,
            "command": "\"${AGENTIC_PYTHON:-python3}\" -I \"${CLAUDE_PROJECT_DIR}/agentic/hooks/pre_tool_use.py\" || exit 2"}]}
```

- No `shell` key: on Windows Claude Code runs shell-form hook commands in Git Bash (in PowerShell only when Git
  Bash is missing, where this command cannot work: `doctor` FAILs), and in `sh` elsewhere.
- `AGENTIC_PYTHON` is the interpreter, set per PC in `.claude/settings.local.json` `env` (gitignored; Windows: the
  full path of the repo's `.venv/Scripts/python.exe`, forward slashes). Settings `env` values are copied literally,
  with no `~` or `$VAR` expansion, and hooks and Bash tool commands inherit them. Unset, the command runs `python3`
  (macOS/Linux; on Windows that is usually the Microsoft Store stub). `CLAUDE_PROJECT_DIR` is exported to hooks; both
  are quoted, so paths with spaces work.
- `-I` (isolated mode) ignores `PYTHON*` variables and user site-packages and keeps the script's directory and the
  working directory off `sys.path`; the hooks insert the repo root themselves. `|| exit 2` blocks the call if the
  interpreter itself fails, e.g. a wrong `AGENTIC_PYTHON` (fail closed; exit 2 blocks on Windows too).
- PostToolUse and PostToolUseFailure run
  `"${AGENTIC_PYTHON:-python3}" -I "${CLAUDE_PROJECT_DIR}/agentic/hooks/post_tool_use.py"` with the same matcher
  (never blocking).
- `permissions.deny` lists the option, alert, scan, watchlist and exercise tools for the server names
  robinhood-trading, Robinhood, robinhood-for-agents and claude_ai_Robinhood, plus `Bash(*agentic resume*)`,
  `Bash(*agentic*--replan*)` (any interpreter path in front), `Bash(*agentic*init*--update*)`,
  `Edit(private/agentic/**)`
  (Claude Code applies Edit rules to every file-editing tool; a Write(path) rule is ignored with a warning). Deny rules match command text and are not a security boundary: `resume` refusing to
  run without a terminal is the real guard. On Windows with Git Bash, Bash deny rules also turn off the PowerShell
  tool.
- `doctor.HOOK_COMMANDS` holds the same three command strings; tests check them, and this section, against
  `.claude/settings.json`.

## 12. signals.py, cli.py (E)

```python
def compute_signals(cfg, now_utc, inbox_dir) -> dict
```

For each enabled asset (and disabled ones with `--all`):
1. get bars, or the tv_export frame
2. find the expected closed bar date for its class:
   - crypto: `last_closed_crypto_bar`
   - equity-signal assets: `last_closed_equity_session`
3. cut bars after it
4. run `check_bars`
5. compute tranche targets
6. record the latest values

Signals JSON per asset:

```
{name, class, mode, source, signal_symbol, vehicle_type, vehicle_symbol, alloc_frac, slot_frac (slots: the size the
 plan uses, shown as the digest's ALLOC; else null), bar_date, expected_bar_date, close,
 tranches:[{weight,n_entry,n_exit,green,pending,line,last_flip_date,
            last_green_flip_date,bars_since_green_flip,flip_close}], target_frac, prev_target_frac (previous bar),
 changed (bool), line_n1, dist_to_line_pct, atr10, entry_policy, entry_frac, entry_notes[], errors[], warnings[],
 dollar_volume_usd (Coinbase feeds: median close x volume of the last 30 bars), held (the sleeve holds the vehicle),
 universe (generated coins: {outcome, reason, dollar_volume_usd, rank, held, hold_only}; else null)}
```

- With the crypto universe on (and the crypto class requested), the file also has `universe: {assets, report}`:
  the generated assets (section 13) after the explicit ones, and the report. Watch-only coins are included, with
  `enabled: false`.
- **The digest:**
  - a `SCAN` line: assets scanned, green, partial, eligible to buy today (enabled, no errors, `entry_frac` > 0),
    held, changed today, with errors
  - `universe.summary_lines`
  - a table of the explicit assets and of every universe coin that is held (`*`), changed today, eligible or in
    error
  - an `OTHERS` line with the rest by state
  - `format_digest(sig, full=True)` (`signals --all`) prints every asset and every coin's outcome.

- Per tranche: the last confirmed red → green flip (`flip == +1`; tv_export: a False → True step of the immediate or
  confirm series), the bars since it in the asset's own series, and the close on it; all null without a flip in the
  history. `entry_frac` is `entry.entry_frac` with the asset's effective entry config and start
  (`entry.start_date`, else `strategy_start.json`, else the run date); `entry_notes` say why a green tranche may
  not be bought. The digest prints them (`entry join_recent: green 35 bars, too late to join (max 20): ...`).
- The file also carries `strategy_start` (the recorded start, or null).

- Written to `signals/signals_<run date UTC>.json` with `generated_at`.
- Writes a digest (text table like plan section 9) to `digests/` and prints it.

CLI commands run from the repo root in Git Bash: `.venv/Scripts/python.exe -m agentic <cmd>` for the user
(`.venv/bin/python` on macOS/Linux), and `"${AGENTIC_PYTHON:-python3}" -m agentic <cmd>` in the slash command. The CLI's
own hints name the interpreter running it (`config.cli_command()`):

| command | does |
|---|---|
| `init` | create the state dirs; copy the example config if missing (never overwrite) |
| `init --update` | add every top-level block of `config.example.json` the private config lacks (e.g. `universe`, `allocation`, `entry`), changing no existing value or asset; validates the result and prints what it adds; needs a terminal and a typed `update` (like `resume`), then writes `config.json.bak-<UTC time>` and the config. `.claude/settings.json` denies it like `resume` (`Bash(*agentic*init*--update*)`) |
| `signals [--all]` | compute signals (`--all`: disabled assets too, and the full digest) |
| `fetch-list` | print exactly which MCP read calls Claude must make now: accounts → portfolio → orders (equity since the baseline; crypto since the baseline and `state_group: open`) → positions (equity, crypto) → historicals for robinhood-feed symbols (interval day, adjustment_type split, start = 700 days ago) → quotes for every vehicle symbol. Orders come before positions so a fill in between shows up as a mismatch, never as a missed fill. With the crypto universe on (section 13): `get_currency_pairs {limit: 700}` (follow `next`), then `get_equity_tradability` (10 symbols per call) for the mapped ETFs of the scanned coins, and quotes (20 symbols per call) for every held vehicle plus every universe coin that is green and entry-eligible on crypto signals computed from the Coinbase cache: the ETF for a mapped coin, else the pair. Without any `get_currency_pairs` capture it prints stage 1 only (the pair list and every mapped ETF's tradability) and "Then run fetch-list again". The crypto reads are listed whenever `cli.crypto_needed` holds: a crypto vehicle, the universe trading coins directly or holding one for exits, or a coin in the reconciled positions or this system's orders since then (so reconcile never compares against a missing capture); `rhs_account_number` must then be filled in (checked with the same universe needs) |
| `plan [--attempt N]` | build the snapshot, make the plan, print a human summary plus the exact tool calls in order (cancels first, then sells, then buys; each with its preview call) |
| `run` | `signals` then `plan` |
| `reconcile` | compare captured positions with expected positions (last reconciled + journal fills); write BLOCK_BUYS on unexplained changes; update `positions_reconciled.json` when clean |
| `status` | flags, last signals and plan, today's ledger, journal tail (no account numbers) |
| `stop`, `flatten`, `resume` | create or remove the flag files; resume needs a terminal and a typed confirmation (no `--yes`) |
| `doctor` | install check (`doctor.py`): Python, pandas/numpy, tz source, AGENTIC_PYTHON (settings env or environment; when it is not the interpreter running doctor, it must also run Python 3.11+ and import pandas and numpy, since the slash command runs the CLI with it), a UTF-8 BOM in a settings file (FAIL), state dir, config and filled account numbers (never printed), git ignores, the hook registration in `.claude/settings.json`, Git Bash on Windows, and the real PreToolUse hook run in a throwaway state dir (unplanned place → exit 2, read → exit 0), directly and through the settings command; and the crypto universe (on/off, source, a fixed allocation, a trimmed `exclude`, the newest `get_currency_pairs` capture's age, enabled explicit assets trading a coin directly while `etf_map` has its ETF, disabled explicit assets that keep a coin out, the Coinbase cache: WARN lines only); PASS/WARN/FAIL lines, exit 1 on any FAIL |
| `backtest --asset NAME [--modes a,b] [--csv path] [--start YYYY-MM-DD] [--cost x]` | compare modes; print the table |

- `README.md`: setup, daily runbook (phase 1 cron; phase 2 "/moneyline" in Claude Code), shadow mode, rollout steps
  from plan section 8, the choice between `computed` (old MoneyLine) and `tv_export` (new), and limitations.
- `.claude/commands/moneyline.md`: the daily operator procedure for Claude:
  1. fetch-list calls
  2. `"${AGENTIC_PYTHON:-python3}" -m agentic run` (every CLI command; it stops if `AGENTIC_PYTHON` is unset on
     Windows)
  3. preview each order
  4. place each order verbatim
  5. read back status
  6. report

  The command never invents or edits order parameters, and stops on any hook block. It makes stage-1 fetch-list calls
  and then fetch-list again when asked, and makes `RE-FETCH QUOTES` calls once, before any place call, then plans
  again with the same attempt.

## 13. universe.py

```python
def build_universe(cfg, now_utc, inbox_dir, fetch=None, *, products=None, held=None, base=None)
    -> tuple[list[dict], dict]
```

- **Config** `universe.crypto` (validated in `config.py`; `enabled` is false when the block is absent):
  - `source`: `robinhood` or `list`
  - `symbols`, `exclude`: coin codes (the default `exclude` is the stablecoins and wrapped tokens in
    `config.DEFAULT_EXCLUDE`)
  - `mode`, `entry` (override keys of the `entry` block)
  - `min_history_bars` (null = `limits.min_bars`; ≥ 30), `min_dollar_volume_usd` (5,000,000), `max_assets` (30)
  - `etf_map` {coin: ticker} (default BTC IBIT, ETH ETHA, SOL BSOL, XRP XRPC, LTC LTCC, NEAR NRR; null drops a
    coin; one ticker per coin)
  - `prefer_etf`, `direct_crypto` (true)
- **Candidates:**
  - `source: robinhood`: the USD pairs of the newest complete `get_currency_pairs` fetch with any USD pair (first
    page and its cursor pages; any age, warning past 7 days; a newer fetch with no USD pairs, results null or [], is
    skipped with a warning), plus `symbols`. Without a usable capture: `symbols` only, with a warning.
  - `source: list`: `symbols` only.
  - Plus the coins the sleeve may hold: `sleeve_vehicles(base)`, the reconciled sleeve plus buys journaled since the
    baseline, including a held mapped ETF's coin.
  - **Universe off** (`enabled: false`): only the coins of the last scan (`last_scan_coins`: the universe assets of
    the newest signals file that has a universe section) that the sleeve still holds and no explicit asset covers,
    each hold only ("universe.crypto is off"), until they exit; none for a config that never ran the universe.
- **Outcomes in order** (each coin gets one, with a reason and a category):
  - `explicit`: an explicit asset has the coin's name (enabled or not), or an enabled one trades the coin, its
    mapped ETF, or on its Coinbase `<CODE>-USD` signal
  - excluded: `exclude` (stablecoin/wrapped or by config); a Robinhood pair that is not `tradable` (robinhood
    source only); no online Coinbase `<CODE>-USD` (products list or a candle 404); a Coinbase data error; a last
    bar older than the last closed bar; fewer than `min_history_bars` bars; pegged (the last 90 closes all within
    3% of their median: stablecoin/wrapped, so an unlisted stablecoin is caught); median dollar volume of the last
    30 bars below `min_dollar_volume_usd`; beyond `max_assets` by that volume
  - **Circuit breaker:** scan requests use 1 retry and a 10 s timeout; after 2 network errors in a row
    (`coinbase_down` in the report) no further Coinbase request is made this run: the remaining coins are scanned
    from current cached bars only ("Coinbase unreachable: not scanned" otherwise), and `compute_signals` /
    `fetch_needs` compute every signal from the cache (`offline`)
  - a coin that passes gets its vehicle:
    - a coin the sleeve holds directly stays direct (hold only if its ETF is preferred or `direct_crypto` is false)
    - a held mapped ETF stays the vehicle (hold only unless `prefer_etf` and the newest tradability capture
      confirms it)
    - a mapped coin with `prefer_etf` trades the ETF when the newest `get_equity_tradability` capture of the
      configured account (at most 7 days old) says `tradeable: true`, `state: active`, tradable for some account
      type and not halted in regular hours; `fractional` from `fractional_tradability`. Otherwise it is `watch`,
      never direct.
    - other coins are `direct` with `direct_crypto`, else `watch`
    - a symbols-only coin without a tradable Robinhood pair is `watch`
  - a held coin that fails a filter is kept with `hold_only` set (no buys)
- **Assets:** each generated asset is `{name: CODE, class: crypto, enabled: outcome in (etf, direct), alloc_frac: 0,
  mode, signal: {computed, coinbase, CODE-USD}, vehicle, min_bars: min_history_bars, universe: {outcome, reason,
  dollar_volume_usd, rank, held, hold_only}, entry?}`, ordered by dollar volume, then code.
- **Report:** `{enabled, source, generated_at, pairs{file, captured_at, age_days, pages, complete}, products,
  tradability, coinbase_down, warnings[], coins[{coin, outcome, reason, category, vehicle, dollar_volume_usd, bars,
  rank, held, hold_only}], counts}`.
- **Allocation `fixed`:** generated assets have `alloc_frac` 0: never bought, and the planner sells a held one only
  on a full exit (red or FLATTEN), never as a trim toward its zero target.
- `with_universe(cfg, signals) -> (cfg, warnings)`:
  - adds the signals file's generated assets for `plan`, the snapshot and reconcile, each re-checked: a coin code no
    explicit asset covers, the signal Coinbase `<CODE>-USD`, and the vehicle the coin itself (with `direct_crypto`)
    or its `etf_map` ticker (with `prefer_etf`); either one for a watch-only or hold-only asset, which is never
    bought
  - takes mode, entry and `min_bars` from the config; anything else is ignored with a warning
  - with the universe off, keeps only hold-only assets (one warning counts the rest)
- `fetch_needs(cfg, now_utc, inbox_dir)`: what fetch-list adds (section 12): `{stage1, tradability, equity_quotes,
  crypto_quotes, candidates, crypto_vehicles, report}`; `crypto_vehicles`: an enabled generated asset trades a coin,
  so crypto positions and orders are fetched (`cli.crypto_needed`).
- **Tests:** `tests/test_agentic_universe.py`, with no network.
