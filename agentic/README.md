# agentic/ — MoneyLine on the Robinhood Agentic account

Python decides and Claude only operates the Robinhood MCP tools. Python computes the signals, sizes the orders
and writes a plan. Claude copies the plan's tool calls verbatim, and the Claude Code hooks block any order that is
not in the plan. Design: [`AGENTIC_TRADING_PLAN.md`](../AGENTIC_TRADING_PLAN.md). Module contract:
[`SPEC.md`](SPEC.md).

**Not financial or tax advice.** You are responsible for every order the agent places. Keep **Trade approvals ON**
in the Robinhood app: every agent order is then a proposal that you approve or reject.

**The repo is public.** Your config, account numbers, tool captures, plans and journal live in `private/agentic/`,
which git ignores. Never commit anything from there, and never put account numbers in `config.example.json`.

## 1. Install

- Python 3.11+ with `pandas` and `numpy`. On a Python that refuses `pip install` (Homebrew, PEP 668), use a venv:
  `python3 -m venv .venv && .venv/bin/pip install pandas numpy`, and run that interpreter. `yfinance` is optional
  (the `yfinance` feed only).
- Claude Code, run from the repo root. The project `.claude/settings.json` already has everything; accept it when
  Claude Code asks, then check that `/hooks` lists the PreToolUse, PostToolUse and PostToolUseFailure hooks:
  - the guard hooks (`agentic/hooks/`) for every Robinhood MCP tool, and the PostToolUseFailure hook, so a place
    call that fails or times out is journaled (the order may exist) and counted against `max_day_usd`
  - deny rules for the option, alert, scan and watchlist write tools
  - deny rules so the agent cannot undo a STOP or replace a plan with placed orders, or edit the plan the hook
    trusts: `python3 -m agentic resume`, `run --replan`, `plan --replan`, and Edit/Write on `private/agentic/**`.
    `resume` also refuses to run without a terminal, so only you can clear a flag.
- Connect Robinhood: `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`,
  then `/mcp` to log in. The hooks guard any `mcp__*robinhood*` name; the deny list covers the server names
  `robinhood-trading`, `Robinhood`, `robinhood-for-agents` and the claude.ai connector's `claude_ai_Robinhood`.
  Use one of those.
- In the Robinhood app: open the Agentic account, fund it with only what this sleeve may use, link crypto if
  needed, and turn on Agent Settings → Safety Controls → **Trade approvals**.

## 2. Init and config

```bash
python3 -m agentic init        # creates private/agentic/ and copies config.example.json to config.json
```

Edit `private/agentic/config.json`:

- `account.account_number` and `account.rhs_account_number` come from `get_accounts`: use the entry with
  `agentic_allowed: true`. Stock tools take `account_number`; crypto tools take the numeric `rhs_account_number`.
  `python3 -m agentic fetch-list` tells Claude to call `get_accounts` while these are still `FILL-IN`.
- `live: false` is shadow mode: plans are written and previewed, and the hook blocks every `place_*` call.
  `live`, `approvals_required`, `enabled` and `fractional` must be JSON `true`/`false`; a quoted `"false"` is a
  config error.
- `capital.max_usd` caps what the sleeve deploys: it uses min(account total value, max_usd). Start small.
- `limits`: `max_order_usd` and `max_day_usd` are enforced by the planner and again by the hook. Others:
  `max_asset_frac` (0.30), `max_crypto_frac` (0.60, all crypto-signal assets together, unless
  `allocation.class_max_frac` sets it; above 1 means no cap), `min_order_usd`, `rebalance_band_frac`, the price
  collars and `min_bars`.
- `allocation` (section 9): `method` `slots` (the example: each position is `slot_frac` 0.20 of capital, new
  entries by `priority` `crypto_first`, `class_max_frac` crypto 0.60) or `fixed` (per-asset `alloc_frac`; the
  default when the block is missing). `slot_frac` must be at most `max_asset_frac`.
- `entry` (section 9): `policy` `join_recent` (default), `join` or `fresh_only`; `max_join_bars` (20),
  `max_join_rise_frac` (null or e.g. 0.10), `start_date` (null or `YYYY-MM-DD`). An asset may override any key
  with its own `"entry": {...}`. **Upgrading:** a config without an `entry` block now gets `join_recent`, so an
  asset that has been green for more than 20 bars and that the sleeve does not hold is no longer bought (add
  `"entry": {"policy": "join"}` for the old behaviour). Signals files from before this change have no flip ages:
  nothing is bought until `signals` runs again.
- `assets`: one entry per thing you trade.

  | field | meaning |
  |---|---|
  | `class` | `crypto` or `equity`: which bar the signal waits for (00:00 UTC close or the 16:00 ET close) |
  | `signal.source` | `computed` (old MoneyLine from OHLC) or `tv_export` (new TradingView MoneyLine, section 7) |
  | `signal.feed`, `signal.symbol` | `coinbase` + `ETH-USD` for crypto; `robinhood` + `SPY` for stocks (bars captured through Claude); also `yfinance` or `csv` (+ `signal.path`) |
  | `vehicle.type`, `vehicle.symbol` | `equity` (a stock or spot ETF, e.g. `ETHA`) or `crypto` (the coin, e.g. `SOL`); `fractional: true` allows fractional market orders in regular hours |
  | `alloc_frac` | share of capital at full target with `allocation.method: fixed` (at most `max_asset_frac`); ignored with slots |
  | `mode` | `immediate`, `split` or `confirm5` (section 8) |
  | `enabled` | only enabled assets trade; `signals --all` also shows disabled ones |

  Example stock asset:

  ```json
  {"name": "QQQ", "class": "equity", "enabled": true, "alloc_frac": 0.20, "mode": "split",
   "signal": {"source": "computed", "feed": "robinhood", "symbol": "QQQ"},
   "vehicle": {"type": "equity", "symbol": "QQQ", "fractional": true}}
  ```

- **Keeping both modes ready:** only one enabled asset may trade a given vehicle. To watch the other mode daily,
  add a disabled twin, such as `ETH-SPLIT` with `mode: split`. `python3 -m agentic signals --all` shows both
  targets. Switching is a one-word config change.
- `wash_sale_block_symbols`: tickers the planner must never buy (section 10).
- **The sleeve owns only its own shares.** The first reconcile adopts the account's positions as the baseline, but
  shares already held then belong to you, not the sleeve: the plan never sells them, even on a red signal or under
  FLATTEN. From then on the sleeve owns what its own orders filled. To hand existing holdings to the sleeve,
  declare them before the first reconcile: `"sleeve_initial_qty": {"ETHA": 9}` (vehicle symbol or crypto code).
  Best: fund the Agentic account with cash for this sleeve only.

## 3. Daily runbook

### Phase 1: crypto signals from cron (no Robinhood access)

The Coinbase daily bar closes at 00:00 UTC. At 00:10 UTC:

```cron
CRON_TZ=UTC
10 0 * * * cd /path/to/moneyline-upgrade && /path/to/python3 -m agentic signals --class crypto >> private/agentic/cron.log 2>&1 || echo "moneyline signals failed: see private/agentic/cron.log"
```

- **Linux and macOS:** use `crontab -e`, with the absolute path of the interpreter that has pandas (`which
  python3` in the shell where `python3 -c "import pandas"` works, e.g. `/opt/homebrew/bin/python3` or the venv's
  `.venv/bin/python`). On macOS, `/usr/bin/python3` is Apple's 3.9 and cannot run this. If your cron ignores
  `CRON_TZ`, use local time; any time from 20:05 to 23:59 US Eastern is after the 00:00 UTC close in both summer
  and winter. On a Mac, the machine must be awake, and cron needs Full Disk Access (System Settings → Privacy &
  Security) when the repo is under `~/Documents` or `~/Desktop`.
- **Windows Task Scheduler:** create a daily task at a local time after 00:00 UTC (for US Eastern, 20:05-23:59).
  - Program: `py`
  - Arguments: `-m agentic signals --class crypto`
  - Start in: the repo folder
  - Or from a command prompt:
    `schtasks /Create /SC DAILY /ST 20:15 /TN moneyline-signals /TR "cmd /c cd /d C:\path\to\moneyline-upgrade && py -m agentic signals --class crypto >> private\agentic\cron.log 2>&1"`

The job writes `signals/signals_<UTC date>.json` and `digests/digest_<date>_crypto.txt`, and prints the digest. It
exits 1 if any enabled asset has a signal error. Everything it prints goes to `cron.log`, so the `|| echo ...`
part is what reaches cron mail (if your system delivers it; on a Mac it lands in the local `/var/mail`). Swap in
`osascript -e 'display notification "moneyline signals failed"'` for a Mac notification. Stock signals on the
`robinhood` feed need fresh Claude captures, so they are computed in phase 2.

### Phase 2: `/moneyline` in Claude Code

| what you trade | run `/moneyline` | plan valid until |
|---|---|---|
| stocks/ETFs, and crypto signals traded through an ETF | a trading day after 9:45 ET | 15:45 ET that session |
| direct crypto (`vehicle.type: crypto`) | any time after 00:00 UTC | 6 hours |

`/moneyline` (`.claude/commands/moneyline.md`) makes Claude:

1. run `python3 -m agentic fetch-list` and make exactly those read calls (the PostToolUse hook saves each result
   to `private/agentic/inbox/`)
2. run `python3 -m agentic run`: signals, reconcile, plan
3. preview each order, then place it with the plan's params verbatim (shadow mode: previews only)
4. read the orders back and report every state

Then **approve or reject each proposal in the Robinhood app**, after checking it against the digest.

Rules of thumb:

- Do not re-run `plan` or `run` while orders await approval or fills. A new plan would cancel the old plan's open
  orders, or duplicate proposals the broker does not list yet. So `plan` refuses while the current plan is valid
  and has placed orders. `--attempt N+1` (a re-quote) is allowed, and `--replan` overrides (you only, never
  Claude). `python3 -m agentic calls` shows the current plan's calls again.
- If an approved limit order hasn't filled after 15 minutes (stocks/ETFs) or 30 minutes (crypto): run
  `/moneyline --attempt 2` (`--attempt 3` at most). Each attempt widens the collar and makes new `ref_id`s. The
  attempt-N plan first lists a cancel for the old order and holds the new one back; after the cancel, re-fetch
  orders, then positions, then quotes, and run `python3 -m agentic plan --attempt N` again (the same N; plain
  `plan` also keeps N while the current plan is holding orders back). That second plan has the wider-collar order.
  An exit that still won't fill is yours to handle in the app.
- The planner checks the captured positions against the baseline plus this system's fills. If they disagree (for
  example, positions were captured before an order filled), that asset is skipped with an error, buys and sells
  alike: re-fetch orders, then positions. `fetch-list` lists orders before positions for this reason.
- `python3 -m agentic status` shows flags, the last signals and plan, today's placed notional and the journal tail,
  with no account numbers.

## 4. Shadow mode first (`live: false`, 4-8 weeks)

Run `/moneyline` daily with `live: false`. Claude previews and never places. Confirm each item below and keep
notes:

- [ ] The hooks are active: `/hooks` lists them, and each Robinhood call adds a file to `private/agentic/inbox/`.
- [ ] **Line check, every day:** the digest's LINE (the old MoneyLine on the closed bar) matches TradingView's
      daily chart within 0.05%, along with the colour and flip date. Use COINBASE:ETHUSD etc. for crypto, never
      the ETF's own chart. A mismatch means: no buys for that asset until it is explained.
- [ ] **Replication:** stock bars from `get_equity_historicals` (`adjustment_type: split`) match TradingView's
      closes. Check what time `begins_at` carries on daily bars; the code uses its UTC date. For crypto, Coinbase
      closes match `data/tv_full/*_1D.csv` and every flip lands on the same day.
- [ ] **Costs:** `preview_crypto_order` shows the route and fee for direct crypto (about 0.95% per side on the
      default route). Check spot-ETF spreads. Choose the ETF or direct vehicle.
- [ ] **The approval response shape.** A place call is blocked in shadow mode, so record it on the first live
      order: what `place_equity_order` / `place_crypto_order` returns with approvals ON (`data.order` omitted or
      null), which status the proposal shows, whether unapproved proposals expire, and whether orders placed
      after the close are queued. With approvals required, the PostToolUse hook writes STOP when a place result
      carries any order (a proposal never does), when it has order fields but no `data.order`, and when a later
      order listing shows an order with this system's own `ref_id` (approved orders carry the approval's id) or
      `placed_agent: agentic`. Adjust it if the real shape differs.
- [ ] `reconcile` stays clean day after day: no BLOCK_BUYS you can't explain.

## 5. Going live

1. Set `live: true`, keep approvals ON, and keep `capital.max_usd` small. ETH via a spot ETF is the asset that
   passed every gate test. SOL is on probation at ≤10%.
2. The first live day: place one order, then check what the app shows and what the PostToolUse hook recorded
   (`status`, `journal.jsonl`).
3. Keep the daily line check running. Scale only after several clean weeks with no data, login or reconcile
   incidents.

## 6. Kill switch and flags

| command | effect |
|---|---|
| `python3 -m agentic stop "reason"` | STOP: the hook blocks every place call. The next plan lists a cancel for each open order this system placed; run `/moneyline` to make those cancels, or cancel in the app. |
| `python3 -m agentic flatten` | FLATTEN: every target becomes 0; sells of the sleeve's own shares only. The next `run` replaces the current plan (even with placed orders) and cancels its open buys; reject buy proposals still waiting in the app. |
| `python3 -m agentic resume` | removes flags after you type `resume` (`--flag NAME` for one). It refuses without a terminal, so Claude cannot run it. |
| `python3 -m agentic reconcile --accept` | after checking a BLOCK_BUYS mismatch in the app, adopt the positions as the new baseline |

- Disconnecting the agent does **not** cancel open orders, and crypto limit orders last 90 days. Cancel them first.
- The PostToolUse hook writes STOP by itself if an agent order goes live without your approval. Check the app and
  your approval setting before `resume`.

## 7. Which signal: `computed` or `tv_export`

| | `computed` (old MoneyLine) | `tv_export` (new Oct 2026 MoneyLine) |
|---|---|---|
| what | Wilder ATR(10) × 2 around hl2, reset on flip (`analysis_2026/moneyline_ref.py`) | the indicator you now see on TradingView |
| replication | exact: 100% of IWM bars and 213/213 flips | none: we read its Direction, ConfirmCount and MoneyLine Level columns |
| flips | about 7 per year per coin | not measured here |
| automation | full: public bars, cron | needs a fresh CSV export after every close |
| evidence | every backtest in this repo | only the exports |

For `tv_export`:

- Add the indicator to the chart, then use Export chart data. Save the file under `private/tv_exports/` and point
  `signal.path` at a glob, such as `private/tv_exports/COINBASE_ETHUSD_1D*.csv`. The newest file wins.
- The signal job drops the forming last row. It errors if the expected closed bar is missing, or if the file was
  saved before that bar closed.
- `signal.tv_confirm` chooses how the 5-close tranche reads the export:
  - `count` (default): acts on the close where ConfirmCount reaches 5, matching "5 daily confirmations" and the
    computed N=5.
  - `direction`: green while Direction = −1. In the 19 exports checked, Direction flipped one bar after
    ConfirmCount reached 5 in all 349 flips, and ConfirmCount resets to 0 on the flip bar, so this waits a bar
    (24 h for crypto, a session for stocks) with no new information. It acts on the 6th close.
  - `backtest --asset NAME` tests the variant the asset is configured with and prints it.

## 8. Modes and what the evidence says

| mode | tranches |
|---|---|
| `immediate` | 100% on the first close beyond the line |
| `split` | 50% on the first close, 50% after 5 consecutive closes beyond the line (exits the same way) |
| `confirm5` | 100% after 5 consecutive closes |

- **Crypto through a spot ETF (~0.02%): keep the immediate flip.** The 21-coin basket was worse at every delay
  (HANDOFF 5.15), and crypto breakouts tend to run right after the flip. Single coins vary:
  [`results_agentic_modes`](../analysis_2026/results_agentic_modes/summary.txt) has ETH better at confirm5 and SOL
  and BTC better at immediate at 0.15%. HANDOFF 5.1: the edge is mostly bear-market avoidance.
- **Direct crypto (~0.95% per side): turnover matters.** Cost is charged on each change of position size, so
  split's half-size tranches cost no more than immediate's full flips. In the modes table at 0.95%, split beats
  immediate after tax on all three coins (ETH 26.9 vs 18.6, SOL 113.5 vs 105.5, BTC 13.8 vs 11.5) and confirm5
  does on ETH and BTC, so consider split for direct-crypto vehicles. BTC trails buy & hold after tax in every
  mode.
- **Stocks: the 5-close delay helps, but holding wins after tax.** On the S&P 500 point-in-time basket the delay
  raised Sharpe from 0.53 to 0.70 and cut drawdown from −34% to −22%. But no timing rule beat holding after tax
  (HANDOFF 5.15, 5.19, plan section 4b). On SPY, QQQ and IWM every mode trails buy & hold after tax by 3-6.5
  points a year. The gain is drawdown.
- **split is a blend.** Its return usually lands between the other two, and it had the shallowest drawdown in 8 of
  9 rows of the modes table. It places about 1.5× the orders of immediate, but each is half-size, so its turnover
  (and cost) is no higher.
- Check one asset yourself: `python3 -m agentic backtest --asset ETH [--modes immediate,split] [--cost 0.0015]
  [--start 2022-01-01]`. The default cost is 0.95% per side for a direct-crypto vehicle and 0.02% otherwise. A
  `tv_export` asset is backtested on its own export.
- Full-history backtests (and `analysis_2026/results_agentic_modes/run_modes.py`) read `data/crypto_4h`,
  `data/etf` and `data/universe_pit_all`, which are gitignored downloads, not part of the public repo. Without
  them, pass `--csv FILE` (any daily OHLC CSV, e.g. a TradingView export). Otherwise `backtest` falls back to the
  asset's live feed and warns: Coinbase gives about 2 years, the Robinhood inbox about 700 days.

## 9. Entry policy and slots

**Joining a green run late (`entry`).** When the strategy starts, or a slot frees up, some assets are already green.
HANDOFF 5.4 measured the remaining return of entries made later in a run (geometric mean per entry day, exit at the
red flip):

| | at flip | day 1-20 | day 21-50 |
|---|---|---|---|
| BTC | 8.3% | 7.6% | 7.4% |
| ETH | 10.2% | 8.1% | 4.9% |
| SOL | 6.3% | 7.0% | 4.2% |

Entering within about 20 bars of the flip earned about the same as entering on it. Later entries were worse on ETH
and SOL and noisy elsewhere (BNB and ZEC did better late; day 51+ rests on 1-7 runs per coin).

| policy | a green tranche may be bought |
|---|---|
| `join` | at any time (the old behaviour) |
| `join_recent` (default) | within `max_join_bars` (20) bars of its own green flip, counted in the asset's own bars (crypto days, stock sessions); with `max_join_rise_frac` (e.g. 0.10) only while the close is at most that far above the flip close |
| `fresh_only` | as `join_recent`, and only flips on or after the strategy start: `start_date`, else the date of the first live plan (`private/agentic/strategy_start.json`). In shadow mode before that it is today, so nothing already green qualifies |

- **Per tranche.** In split mode the first half may be too old while the 5-close half flipped yesterday: the plan
  buys only the fresh half. A green state with no flip in the available history counts as too old. A half the
  sleeve already holds stays held and a fresh half is added on top (also when the first half re-flips green during
  an old 5-close run). The journal tells which half is held: a buy placed after a tranche's flip holds that tranche,
  so the day after a fresh-half buy the old half is not bought instead.
- **Buys only.** A position the sleeve holds is never sold because its run is old: buys raise it only to the
  eligible share of the target, sells cut it only to the full target, and anything between is held. A red flip is
  a full exit whatever the policy; STOP, FLATTEN and BLOCK_BUYS work as before.
- The digest and the plan say why, e.g. `green 35 bars, too late to join (max 20): waiting for the next flip`.

**Allocation (`allocation`).**

| method | sizing |
|---|---|
| `fixed` (when the block is missing) | each asset's `alloc_frac` of capital (enabled ones sum to at most 1); a class over its cap is scaled down proportionally (a green run the entry policy will not buy counts only as far as it is held, so it never trims the others) |
| `slots` (the example config) | every position is `slot_frac` × capital, whatever the asset. Holdings keep their whole slot, earliest into their run first (a split position can add its second half later), and are never trimmed to make room. The rest of capital goes to new entries in `priority` order: a full slot, or a partial one if at least half a slot is left; otherwise the entry waits ("no free slot"). A new entry buys only its eligible share of the slot now |

- `priority`: `crypto_first` (default: crypto-class assets, then stocks; within a class the newest green flip
  first, ties in config order), `equity_first`, `newest_flip`, `config_order`.
- `class_max_frac`: each class's cap as a share of capital (default crypto = `limits.max_crypto_frac`, equity 1.0;
  1.0 = no cap). With slots it limits the room handed out; a holding above it is not sold.
- With slots, a position counts at its value until it is sold: an exit or a trim frees its room only once the
  positions show it (the next plan), so buys never take the sleeve's positions above capital or a class above its
  cap, even when a sell is held back or does not fill. A holding that got a partial slot is the last one in, so it
  tops up only when capital frees up. Buying power and the order and day caps apply as before.
- A position worth less than `min_order_usd` (dust left by an exit) is not a holding. BLOCK_BUYS and FLATTEN hand
  out no new slots (`SLOTS ... new - (BLOCK_BUYS)`). The digest's ALLOC column shows `slot_frac` with slots.
- Every slot is the same size: to keep a probation asset smaller (SOL at 10%, section 5), use `fixed`.

Trade-offs:

- **Slots avoid trimming and turnover.** With fixed shares and a class cap, one more green coin scales every crypto
  holding down: sells, realized short-term gains, then buys. With slots the newcomer waits instead. The price: an
  asset that flips while the slots are full may miss its run, since by the time a slot frees up it is usually too
  late to join, and an exiting asset's slot passes on only in the plan after its exit fills. The rebalance band still
  trims a position that grows past 1.25 × its slot (section 11).
- **`crypto_first`** is defensible because the MoneyLine's evidence of adding value is on crypto, not stocks: it
  beats holding in about 97% of asset-years that fall more than 60%, which crypto has and stocks rarely do, and no
  timing rule beat holding stocks after tax (HANDOFF 5.11, 5.15). It is not a claim that anyone can time a bull run.
- **The crypto cap is a correlation guardrail.** Coins flip red together, and exits fill past the line in crashes
  (ETF route: median 1-3%, worst 21-40%, HANDOFF 5.8), so full crypto slots lose together.

## 10. Taxes and wash sales

- The Agentic account is taxable. The strategy realizes short-term gains several times a year per asset, while
  holding defers them. The backtests tax strategies at 35% a year and buy & hold at 20% once. Put your own rates
  in `tax`.
- **Wash sales apply to stocks and ETFs across all your accounts, and Robinhood does not check them.** If your
  Schwab robo-advisor runs tax-loss harvesting, its sales and buys of the same or substantially identical ETFs
  can collide with this sleeve. For example, the robo harvests a loss in an S&P 500 fund while this sleeve buys
  SPY within 30 days. Prefer vehicles the robo does not hold, and list the conflicts in `wash_sale_block_symbols`.
  The planner also warns when the journal shows a loss sale of the same symbol in the last 30 days, but it only
  sees this account.
- Spot crypto is not covered by the wash-sale rule under current law (H.R. 10357 would change that). Spot crypto
  **ETFs are** securities, so it applies to them.

## 11. Limitations

- Half-day sessions are treated as full sessions.
- Robinhood daily bars: the date is taken from `begins_at` in UTC, and `close_price` is the last trade. Both need
  confirming in shadow mode.
- A crypto signal traded through an ETF waits for the next NYSE session; weekend flips trade on Monday. Fractional
  orders are market orders in regular hours only.
- An asset with a data error is skipped entirely, exits included, with an alert in the digest and plan.
- The line is a trigger, not a stop: exits fill past it, and a gap can cost several times the distance.
- The 25% rebalance band trims winners, which realizes gains (with slots too: a position past 1.25 × its slot).
- `join_recent` can miss a run that a full slot book or a data error kept out for its first 20 bars.
- The daily cap assumes Claude makes place calls one at a time.
- The hook matches calls against `private/agentic/plan_current.json`, but caps each call on its own quantity ×
  limit price (or × the newest captured quote for a market order), allows only the order shapes the planner makes,
  and checks the plan's ref_ids, lifetime and live flag. An edited plan can still change which planned order is
  placed within those limits: deny Edit and Write on `private/agentic/**` (section 1). Approvals ON remain the real
  backstop.
- Old open equity orders: `fetch-list` lists equity orders from the last baseline (at least 7 days back). This
  system's equity orders are day orders, so that covers them, but a gtc stock order you placed in this account
  before that window is not seen. Open crypto orders are listed whatever their age.
- Each place call must go through Claude Code with the hooks: an order placed in the app or by another tool is not
  the sleeve's, and reconcile flags it.
- The Robinhood login lasts about 4 days, and refresh tokens rotate: use one Claude session at a time.
- Always run as `python3 -m agentic` from the repo root (`agentic/calendar.py` would hide the standard
  `calendar` module if `agentic/` itself were on `sys.path`).

## 12. Files

| path | contents |
|---|---|
| `agentic/*.py` | config, indicator, backtest, calendar, data, snapshot, entry, planner, ledger, signals, cli |
| `agentic/hooks/` | PreToolUse guard and PostToolUse capture/journal hooks (standard library only) |
| `private/agentic/config.json` | your config (account numbers): private |
| `private/agentic/inbox/` | raw Robinhood tool results saved by the PostToolUse hook |
| `private/agentic/signals/`, `digests/`, `plans/`, `plan_current.json` | daily outputs |
| `private/agentic/journal.jsonl`, `ledger.json`, `positions_reconciled.json`, `hook.log` | audit trail |
| `private/agentic/STOP`, `FLATTEN`, `BLOCK_BUYS` | flags |
| `private/agentic/strategy_start.json` | the first live plan's date (entry policy `fresh_only`) |

Set `AGENTIC_STATE_DIR` to keep state elsewhere (tests use a temporary directory).
