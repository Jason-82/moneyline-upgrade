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
| `cli.py`, `__main__.py` | E | `python3 -m agentic <cmd>` |
| `README.md`, `.claude/commands/moneyline.md` | E | runbook and daily slash command |

Tests go in `tests/test_agentic_<module>.py` and run with `python3 -m pytest tests/test_agentic_*.py -q`. They must not
touch the network; mock urllib.

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
- Also returns `level`, `pending` = cnt, `direction`.
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
- Use `zoneinfo("America/New_York")`.

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
- `get_bars(asset, cfg, now_utc, inbox_dir) -> df`: dispatches on `asset["signal"]["feed"]`. It fetches at least
  `limits.min_bars + 150` bars (about 2 years of crypto; for stocks request ≥ 700 calendar days).

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
    crypto orders if any crypto vehicle is enabled
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

**Sizing:**
- `capital = min(snapshot.total_value, cfg.capital.max_usd)`
- per enabled asset: `target_usd = capital × alloc_frac × target_frac`
- Crypto-class assets are capped together at `max_crypto_frac × capital`. Scale them down proportionally.
- `current_usd` = vehicle position qty × mid. Mid = (bid+ask)/2, else last.
- Trade only if `|target_usd − current_usd| > max(min_order_usd, rebalance_band_frac × capital × alloc_frac)`, or
  if target_frac == 0 and the position is non-zero (a full exit always sells everything sellable). A position worth
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
  never more.
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
- **Cancels:** every open order in the snapshot that belongs to this account and is not in this plan, i.e. stale
  plan orders, goes into `plan["cancels"]` as cancel tool params. A plan never places a new order for a symbol that
  still has an open order: it cancels first and says "re-run plan after the cancel settles".

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
 "skipped": [{"asset": "...", "reason": "..."}], "warnings": [], "errors": []}
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
- **Approval check:** if config `account.approvals_required`, a successful place response with `data.order` not null
  and `data.order.placed_agent == "agentic"` means the agent's order went live without the user's approval. Write
  STOP with that reason and print a loud warning on stderr.
  - `data.order == null` is recorded as `"state": "proposal_pending_approval?"`. The exact approval response shape
    must be confirmed in shadow mode (README).
- Never block (always exit 0); log errors to `hook.log`.

## 11. .claude/settings.json (D)

```json
{"hooks": {
   "PreToolUse":  [{"matcher": "mcp__.*([Rr]obinhood).*", "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/agentic/hooks/pre_tool_use.py\""}]}],
   "PostToolUse": [{"matcher": "mcp__.*([Rr]obinhood).*", "hooks": [{"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/agentic/hooks/post_tool_use.py\""}]}]},
 "permissions": {"deny": [ ...the option, alert, scan, watchlist and exercise tools for server names robinhood-trading, Robinhood, robinhood-for-agents... ]}}
```

Check the matcher syntax against Claude Code's hooks documentation.

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
{name, class, mode, source, signal_symbol, vehicle_type, vehicle_symbol, bar_date, expected_bar_date, close,
 tranches:[{weight,n_entry,n_exit,green,pending,line,last_flip_date}], target_frac, prev_target_frac (previous bar),
 changed (bool), line_n1, dist_to_line_pct, atr10, errors[], warnings[]}
```

- Written to `signals/signals_<run date UTC>.json` with `generated_at`.
- Writes a digest (text table like plan section 9) to `digests/` and prints it.

`python3 -m agentic <cmd>`:

| command | does |
|---|---|
| `init` | create the state dirs; copy the example config if missing (never overwrite) |
| `signals [--all]` | compute signals |
| `fetch-list` | print exactly which MCP read calls Claude must make now: accounts → portfolio → positions (equity, crypto) → open orders → historicals for robinhood-feed symbols (interval day, adjustment_type split, start = 700 days ago) → quotes for every vehicle symbol |
| `plan [--attempt N]` | build the snapshot, make the plan, print a human summary plus the exact tool calls in order (cancels first, then sells, then buys; each with its preview call) |
| `run` | `signals` then `plan` |
| `reconcile` | compare captured positions with expected positions (last reconciled + journal fills); write BLOCK_BUYS on unexplained changes; update `positions_reconciled.json` when clean |
| `status` | flags, last signals and plan, today's ledger, journal tail (no account numbers) |
| `stop`, `flatten`, `resume` | create or remove the flag files; resume asks for confirmation |
| `backtest --asset NAME [--modes a,b] [--csv path] [--start YYYY-MM-DD] [--cost x]` | compare modes; print the table |

- `README.md`: setup, daily runbook (phase 1 cron; phase 2 "/moneyline" in Claude Code), shadow mode, rollout steps
  from plan section 8, the choice between `computed` (old MoneyLine) and `tv_export` (new), and limitations.
- `.claude/commands/moneyline.md`: the daily operator procedure for Claude:
  1. fetch-list calls
  2. `python3 -m agentic run`
  3. preview each order
  4. place each order verbatim
  5. read back status
  6. report

  The command never invents or edits order parameters, and stops on any hook block.
