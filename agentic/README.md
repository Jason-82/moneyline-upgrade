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

These steps are for **Windows with Git Bash**: run every command in Git Bash, from the repo folder. macOS and Linux:
see the last bullet.

- **Python 3.11+** from [python.org](https://www.python.org/downloads/windows/). In the installer, tick **Add
  python.exe to PATH**. It also installs the `py` launcher. Do not use `python3` on Windows: that name is often the
  Microsoft Store stub.
- **Git for Windows** ([git-scm.com](https://git-scm.com/download/win)), which includes Git Bash. It is required:
  Claude Code runs its Bash tool and these hooks in Git Bash. Without it, Claude Code runs hooks in PowerShell,
  where the hook command cannot run, so the guard does not work.
- **The repo and its venv:**

  ```bash
  git clone https://github.com/Jason-82/moneyline-upgrade.git && cd moneyline-upgrade    # or `git pull` in your clone
  py -3 -m venv .venv && .venv/Scripts/python.exe -m pip install pandas numpy tzdata
  ```

  Windows has no time-zone database, so `tzdata` provides one. The code also has a built-in US Eastern fallback,
  but install `tzdata` anyway. `yfinance` is optional (the `yfinance` feed only). Every command in this README runs
  the venv's interpreter: `.venv/Scripts/python.exe -m agentic ...`. After `source .venv/Scripts/activate`, plain
  `python -m agentic ...` works too.
- **Tell the hooks which Python to use.** The hook commands in `.claude/settings.json` run
  `"${AGENTIC_PYTHON:-python3}"`, so set `AGENTIC_PYTHON` in `.claude/settings.local.json`. That file is for this PC
  only, and the repo's `.gitignore` keeps it out of git. Use your own path, with forward slashes:

  ```json
  {"env": {"AGENTIC_PYTHON": "C:/Users/<you>/moneyline-upgrade/.venv/Scripts/python.exe"}}
  ```

  Claude Code copies `env` values literally: `~`, `$HOME` and `%USERPROFILE%` are not expanded. If the file does
  not exist yet, this writes it with the right path (`pwd -W` prints the repo folder as `C:/...`). If it already
  exists (Claude Code keeps your "don't ask again" approvals there), the command refuses with `cannot overwrite
  existing file` and changes nothing: add the `"env"` key to that file by hand instead.

  ```bash
  ( set -C; printf '{"env": {"AGENTIC_PYTHON": "%s/.venv/Scripts/python.exe"}}\n' "$(pwd -W)" > .claude/settings.local.json )
  ```

- **Claude Code**, started from the repo folder. The project `.claude/settings.json` has the rest; accept it when
  Claude Code asks. **Restart Claude Code** after creating `settings.local.json`, then check that `/hooks` lists the
  PreToolUse, PostToolUse and PostToolUseFailure hooks:
  - the guard hooks (`agentic/hooks/`) for every Robinhood MCP tool, and the PostToolUseFailure hook, so a place
    call that fails or times out is journaled (the order may exist) and counted against `max_day_usd`
  - deny rules for the option, alert, scan and watchlist write tools
  - deny rules so the agent cannot undo a STOP or replace a plan with placed orders, or edit the plan the hook
    trusts: any command containing `agentic resume` or `agentic ... --replan`, and Edit/Write on
    `private/agentic/**`. `resume` also refuses to run without a terminal, so only you can clear a flag. These
    Bash deny rules also turn off Claude Code's PowerShell tool on Windows. That is fine: everything here runs in
    Git Bash.
- **Check the install:** `.venv/Scripts/python.exe -m agentic doctor`. It prints one PASS, WARN or FAIL line for
  each check:
  - Python, pandas, numpy and the time-zone source
  - `AGENTIC_PYTHON`, read from `settings.local.json`, so your Git Bash does not need it set, and that it can
    import pandas and numpy (`/moneyline` runs every command with it)
  - the state dir, and the config and account numbers (never shown)
  - that git ignores the private files, the hook registration and Git Bash
  - a live test of the PreToolUse hook: an unplanned order must be blocked and a read allowed

  It exits 1 on any FAIL. The state dir, config and account lines fail until section 2 is done. Fix every FAIL
  before you run `/moneyline`.
- Connect Robinhood: `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`,
  then `/mcp` to log in. The hooks guard any `mcp__*robinhood*` name; the deny list covers the server names
  `robinhood-trading`, `Robinhood`, `robinhood-for-agents` and the claude.ai connector's `claude_ai_Robinhood`.
  Use one of those.
- In the Robinhood app: open the Agentic account, fund it with only what this sleeve may use, link crypto if
  needed, and turn on Agent Settings → Safety Controls → **Trade approvals**.
- **macOS/Linux:** `python3 -m venv .venv && .venv/bin/python -m pip install pandas numpy tzdata`, then use
  `.venv/bin/python` wherever this README says `.venv/Scripts/python.exe`. `AGENTIC_PYTHON` is optional there:
  without it the hooks run `python3`, and they need only the standard library. `/moneyline` runs the CLI with that
  `python3` too, so it needs pandas and numpy, or set `AGENTIC_PYTHON` to the full path of `.venv/bin/python`
  (`doctor` checks).

## 2. Init and config

```bash
.venv/Scripts/python.exe -m agentic init      # creates private/agentic/ and copies config.example.json to config.json
```

Edit `private/agentic/config.json`, then run `.venv/Scripts/python.exe -m agentic doctor` again: once the account
numbers are in, every line should PASS.

- `account.account_number` and `account.rhs_account_number` come from `get_accounts`: use the entry with
  `agentic_allowed: true`. Stock tools take `account_number`; crypto tools take the numeric `rhs_account_number`.
  The `fetch-list` command tells Claude to call `get_accounts` while these are still `FILL-IN`.
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
  `max_join_rise_frac` (0.50; null = no cap; section 9), `start_date` (null or `YYYY-MM-DD`). An asset may override any key
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
  add a disabled twin, such as `ETH-SPLIT` with `mode: split`. `.venv/Scripts/python.exe -m agentic signals --all`
  shows both targets. Switching is a one-word config change.
- `wash_sale_block_symbols`: tickers the planner must never buy (section 10).
- **The sleeve owns only its own shares.** The first reconcile adopts the account's positions as the baseline, but
  shares already held then belong to you, not the sleeve: the plan never sells them, even on a red signal or under
  FLATTEN. From then on the sleeve owns what its own orders filled. To hand existing holdings to the sleeve,
  declare them before the first reconcile: `"sleeve_initial_qty": {"ETHA": 9}` (vehicle symbol or crypto code).
  Best: fund the Agentic account with cash for this sleeve only.

## 3. Daily runbook

### Phase 1: crypto signals on a schedule (no Robinhood access)

The Coinbase daily bar closes at 00:00 UTC. A scheduled job computes the crypto signals soon after, so the digest is
ready before you run `/moneyline`. It is optional: `run` in phase 2 computes the signals anyway.

**Windows: Task Scheduler, set up from Git Bash.** In the repo folder:

```bash
bash agentic/windows/crypto_signals.sh                     # run the job once by hand; output goes to cron.log
bash agentic/windows/schedule_crypto_signals.sh install    # a daily task at 20:15 local time
bash agentic/windows/schedule_crypto_signals.sh status     # the task, its last result and the end of cron.log
bash agentic/windows/schedule_crypto_signals.sh remove     # delete the task
```

- `install` registers a task named `moneyline-crypto-signals`. It runs Git Bash's `bash.exe` on
  `agentic/windows/crypto_signals.sh`, which goes to the repo folder, runs `.venv/Scripts/python.exe -m agentic
  signals --class crypto` and appends everything to `private/agentic/cron.log`. Running `install` again replaces
  the task, and `--dry-run` prints the `schtasks` command instead of running it.
- **20:15 assumes the PC is on US Eastern time.** That is 00:15 UTC in summer (EDT) and 01:15 UTC in winter (EST),
  after the close in both. On another time zone, choose a local time that is at least 00:10 UTC all year and pass
  it as `install --time HH:MM`: for example `--time 19:15` on US Central, `--time 17:15` on US Pacific or
  `--time 01:15` in the UK.
- Git Bash turns `schtasks` flags such as `/Create` into paths, so the script runs it with `MSYS_NO_PATHCONV=1`. Do
  the same if you call `schtasks` yourself.
- The task runs only while you are logged on and the PC is awake, and a console window flashes while it runs. A
  missed run is not repeated.

**macOS/Linux:** use cron instead (`crontab -e`). If your cron ignores `CRON_TZ`, use a local time from 20:05 to
23:59 US Eastern. On a Mac the machine must be awake, and cron needs Full Disk Access when the repo is under
`~/Documents` or `~/Desktop`.

```cron
CRON_TZ=UTC
10 0 * * * cd /path/to/moneyline-upgrade && .venv/bin/python -m agentic signals --class crypto >> private/agentic/cron.log 2>&1 || echo "moneyline signals failed: see private/agentic/cron.log"
```

The job writes `signals/signals_<UTC date>.json` and `digests/digest_<date>_crypto.txt` under `private/agentic/`,
and prints the digest into `cron.log`. It exits 1 if any enabled asset has a signal error. Task Scheduler then shows
Last Run Result 0x1 (see `status`), and the cron line's `|| echo` reaches cron mail. Stock signals on the
`robinhood` feed need fresh Claude captures, so they are computed in phase 2.

### Phase 2: `/moneyline` in Claude Code

| what you trade | run `/moneyline` | plan valid until |
|---|---|---|
| stocks/ETFs, and crypto signals traded through an ETF | a trading day after 9:45 ET | 15:45 ET that session |
| direct crypto (`vehicle.type: crypto`) | any time after 00:00 UTC | 6 hours |

`/moneyline` (`.claude/commands/moneyline.md`) makes Claude do the following. Claude runs each command as
`"${AGENTIC_PYTHON:-python3}" -m agentic ...`, and stops if `AGENTIC_PYTHON` is not set on Windows (section 1).

1. run `fetch-list` and make exactly those read calls (the PostToolUse hook saves each result to
   `private/agentic/inbox/`)
2. run `run`: signals, reconcile, plan
3. preview each order, then place it with the plan's params verbatim (shadow mode: previews only)
4. read the orders back and report every state

Then **approve or reject each proposal in the Robinhood app**, after checking it against the digest.

Rules of thumb:

- Do not re-run `plan` or `run` while orders await approval or fills. A new plan would cancel the old plan's open
  orders, or duplicate proposals the broker does not list yet. So `plan` refuses while the current plan is valid
  and has placed orders. `--attempt N+1` (a re-quote) is allowed, and `--replan` overrides (you only, never
  Claude). `.venv/Scripts/python.exe -m agentic calls` shows the current plan's calls again.
- If an approved limit order hasn't filled after 15 minutes (stocks/ETFs) or 30 minutes (crypto): run
  `/moneyline --attempt 2` (`--attempt 3` at most). Each attempt widens the collar and makes new `ref_id`s. The
  attempt-N plan first lists a cancel for the old order and holds the new one back; after the cancel, re-fetch
  orders, then positions, then quotes, and run `plan --attempt N` again (the same N; plain `plan` also keeps N
  while the current plan is holding orders back). That second plan has the wider-collar order.
  An exit that still won't fill is yours to handle in the app.
- The planner checks the captured positions against the baseline plus this system's fills. If they disagree (for
  example, positions were captured before an order filled), that asset is skipped with an error, buys and sells
  alike: re-fetch orders, then positions. `fetch-list` lists orders before positions for this reason.
- `.venv/Scripts/python.exe -m agentic status` shows flags, the last signals and plan, today's placed notional and
  the journal tail, with no account numbers.

## 4. Shadow mode first (`live: false`, 4-8 weeks)

Run `/moneyline` daily with `live: false`. Claude previews and never places. Confirm each item below and keep
notes:

- [ ] The hooks are active: `/hooks` lists them, and each Robinhood call adds a file to `private/agentic/inbox/`.
- [ ] **Line check, every day:** the digest's LINE (the old MoneyLine on the closed bar) matches TradingView's
      daily chart within 0.05%, along with the colour and flip date. Use COINBASE:ETHUSD etc. for crypto, never
      the ETF's own chart. A mismatch means: no buys for that asset until it is explained.
      - Your TradingView MoneyLine is now the October 2026 version, which is a different indicator. For this check,
        add TradingView's built-in **Supertrend** with ATR Period 10 and Factor 2 on the default chart data.
      - Its colour matches the old MoneyLine on about 99.97% of bars.
      - Its line can differ for a while after a flip: on about 10% of flips it restarts from a different band. So
        compare the line between flips, and the colour and flip date always.
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
| `.venv/Scripts/python.exe -m agentic stop "reason"` | STOP: the hook blocks every place call. The next plan lists a cancel for each open order this system placed; run `/moneyline` to make those cancels, or cancel in the app. |
| `.venv/Scripts/python.exe -m agentic flatten` | FLATTEN: every target becomes 0; sells of the sleeve's own shares only. The next `run` replaces the current plan (even with placed orders) and cancels its open buys; reject buy proposals still waiting in the app. |
| `.venv/Scripts/python.exe -m agentic resume` | removes flags after you type `resume` (`--flag NAME` for one). It refuses without a terminal, so Claude cannot run it. |
| `.venv/Scripts/python.exe -m agentic reconcile --accept` | after checking a BLOCK_BUYS mismatch in the app, adopt the positions as the new baseline |

- **`resume` in Git Bash's own window:** that window (mintty) does not give Windows programs a terminal, so
  `resume` refuses there. Prefix the command with `winpty`, which comes with Git for Windows:
  `winpty .venv/Scripts/python.exe -m agentic resume`. A Git Bash tab in Windows Terminal works without it.
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

- **Crypto: split is the default (since 2026-10-19).** Results from
  [`split_crypto.txt`](../analysis_2026/results_agentic_modes/split_crypto.txt), tested beyond the three-coin modes
  table:
  - **21 coins one by one:** split beat immediate after tax on 14 of 21 coins (16 of 21 at 0.95% per side), with a
    shallower drawdown on 17 of 21.
  - **The survivorship-free top-20 basket including dead coins:** immediate was 2-4 points a year ahead at low
    cost (Sharpe 1.14 vs 1.08, not significant), split's drawdown was slightly shallower (−49% vs −51%), and at
    0.95% the two tie.
  - **Never the worst:** split is never the worst mode, and it beats confirm5 in every version. A full 5-close
    delay is what hurt crypto in HANDOFF 5.15.
  - **To switch back:** set an asset's `mode` to `immediate` for the faster version (slightly higher return in the
    strictest test, deeper drawdowns).
  - HANDOFF 5.1: the edge over holding is mostly bear-market avoidance.
- **Direct crypto (~0.95% per side): turnover matters.** Cost is charged on each change of position size, so
  split's half-size tranches cost no more than immediate's full flips. Split ties or beats immediate at this
  cost in every test above. BTC trails buy & hold after tax in every mode.
- **Stocks: the 5-close delay helps, but holding wins after tax.** On the S&P 500 point-in-time basket the delay
  raised Sharpe from 0.53 to 0.70 and cut drawdown from −34% to −22%. But no timing rule beat holding after tax
  (HANDOFF 5.15, 5.19, plan section 4b). On SPY, QQQ and IWM every mode trails buy & hold after tax by 3-6.5
  points a year. The gain is drawdown.
- **split is a blend.** Its return usually lands between or above the other two, and it had the shallowest drawdown
  in 8 of 9 rows of the modes table. It places about 1.5× the orders of immediate, but each is half-size, so its turnover
  (and cost) is no higher.
- Check one asset yourself: `.venv/Scripts/python.exe -m agentic backtest --asset ETH [--modes immediate,split]
  [--cost 0.0015] [--start 2022-01-01]`. The default cost is 0.95% per side for a direct-crypto vehicle and 0.02% otherwise. A
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

**How far the price has already risen.** [`results_late_entry`](../analysis_2026/results_late_entry/summary.txt)
pools every entry day 1-20 bars after a green flip (old MoneyLine, N=1; decide at the close, buy at the next open,
sell at the open after the red-flip close): 21 coins at 0.10% per side (1,055 runs, 2018-2026), 293 random S&P 500
point-in-time stocks at 0.03% (44,776 runs) and 13 ETFs at 0.02% (2,287 runs). Geometric mean per trade after
cost, with a 95% interval clustered by run:

| rise since the flip close | crypto | S&P stocks | ETFs |
|---|---|---|---|
| entry on the flip | 3.6% [1.7, 5.5] | 0.40% [0.31, 0.50] | 0.43% [0.22, 0.63] |
| ≤ 0 | 2.0% [0.0, 4.0] | 0.44% [0.31, 0.57] | 0.48% [0.17, 0.80] |
| 0-5% | 2.2% [0.4, 4.0] | 0.38% [0.30, 0.47] | 0.38% [0.21, 0.55] |
| 5-10% | 3.0% [0.5, 5.4] | 0.25% [0.11, 0.40] | 1.1% [0.4, 1.8] |
| 10-20% | 4.3% [1.5, 7.3] | 0.30% [0.00, 0.60] | 1.2% [−0.9, 3.4] |
| 20-35% | 6.8% [2.0, 11.8] | 1.0% [0.2, 1.8] | −2.5% (11 runs) |
| 35-50% | 8.7% [1.3, 16.7] | 2.9% [0.7, 5.2] | 1 run |
| > 50% | 12.1% [−2.2, 28.5] (96 runs) | −3.3% [−6.0, −0.5] (220 runs) | none |

- **Up to +50%, a bigger rise did not mean less was left, nor reliably more.** On crypto, entries 10-50% above the
  flip close had higher pooled means than entries on the flip, but every difference from the flip has an interval
  that includes zero, and a few runs drive the means: without each bucket's 10 best runs, 10-20%, 20-35% and 35-50%
  earn 1.1%, 0.7% and −0.6%, against 1.6% on the flip without its 10 best. Before 2021 the 10-20% bucket was below
  the flip, and only 11 of 21 coins had the higher mean. So crypto shows no penalty for rises up to +50%, but no
  reliable premium either. Stocks were about flat up to +20% and better from +20% to +50%.
- **Entries 21+ bars after the flip were weaker on stocks and ETFs.** Stocks earned 0.01% per trade against 0.40%
  on the flip (−0.39 log points [−0.54, −0.24]), ETFs 0.14% against 0.43%. Pooled crypto was not weaker: 3.9%
  against 3.6% (2.7% at bars 21-50, 11.5% at 51+ on 63 runs). It was weaker per coin (14 of 21 coins below their
  own flip entries) and without the 3 best runs (−0.4%, against 2.8% on the flip without its 3 best). So
  `max_join_bars` 20 rests on HANDOFF 5.4 and the stock and ETF results, not on pooled crypto.
- **Above +50% the evidence turns.** Stocks lost 3.3% per trade, the only bucket entirely below zero, and lost in
  both halves of the sample. Crypto's 12.1% rests on a few huge runs: its interval includes zero; the median run
  lost 10.9% (about 4% in the other buckets, since trend trades usually lose small and win big); the mean falls to
  6.9% without the single best run and to 1.6% without the best three (20-35% and 35-50% keep 3.9% and 4.7%); and
  in runs since March 2023 it was 4.5% [−8.6, 19.5].
- **Default `max_join_rise_frac`: 0.50**, on top of `max_join_bars` 20. Within the 20-bar window it blocks 3.2% of
  crypto entry days (96 of 1,055 runs ever got there) and 0.16% of stock entry days. The trade-off: in this sample
  the crypto entries it blocks earned more on average than the ones it allows (12.1% against 3.1% per trade). The
  cap gives up a mean that rests on a handful of runs to skip entries whose typical outcome was a loss and that
  lost on stocks. It is a judgment on 96 crypto runs, not a fitted optimum.
- **The case for the cap comes from the N=1 table above, but the cap applies to every tranche**, including the
  5-close tranche of `split` and `confirm5`, which compares the close with its own N=5 flip close. At N=5 the
  evidence points the other way: entries more than 50% up earned +2.5% per trade on stocks [−6.1, 11.9] (104 runs,
  against 1.3% on the flip) and +27% on crypto [−2.6, 66] (46 runs, against 5.3%). Both intervals include zero.
  The N=1 stock loss is not robust either: split at 2021 it is −2.8% [−5.6, 0.2] before and −5.3% [−12.4, 2.3]
  after, and without the 3 worst runs it is −2.4% [−5.0, 0.3]. Whether the cap should apply only to N=1 tranches is
  an open decision. Until it is made, the cap applies to all tranches.
- **A tighter cap is not supported.** 0.20 would block 13.6% of crypto entry days, which earned 8.4% per trade
  [2.3, 14.9], and 0.10 would block 26% at 6.5% [2.4, 10.7]: the strongest runs.
- `null` turns the cap off, and an asset may set its own in its `entry`. **Upgrading:** a config copied from the
  earlier example has `"max_join_rise_frac": null`, which keeps the cap off. Set 0.50 to use the default; a config
  without the key gets 0.50.
- These are per-trade returns of overlapping entries (a run counts once per entry day), not a portfolio backtest.
  Re-run: `.venv/Scripts/python.exe analysis_2026/results_late_entry/late_rise.py` (needs the gitignored data
  downloads, section 8). The N=5, per-coin, split-at-2021, pooled 21+ bar, drop-worst and flip-without-best-runs
  figures come from an independent re-check on the same data (2026-10-18); its tables are not in
  `results_late_entry` yet.

| policy | a green tranche may be bought |
|---|---|
| `join` | at any time (the old behaviour) |
| `join_recent` (default) | within `max_join_bars` (20) bars of its own green flip, counted in the asset's own bars (crypto days, stock sessions), and only while the close is at most `max_join_rise_frac` (0.50, i.e. +50%; `null` = no cap) above the flip close |
| `fresh_only` | as `join_recent`, and only flips on or after the strategy start: `start_date`, else the date of the first live plan (`private/agentic/strategy_start.json`). In shadow mode before that it is today, so nothing already green qualifies |

- **Per tranche.** In split mode the first half may be too old while the 5-close half flipped yesterday: the plan
  buys only the fresh half. A green state with no flip in the available history counts as too old. A half the
  sleeve already holds stays held and a fresh half is added on top (also when the first half re-flips green during
  an old 5-close run). The journal tells which half is held: a buy placed after a tranche's flip holds that tranche,
  so the day after a fresh-half buy the old half is not bought instead.
- **Buys only.** A position the sleeve holds is never sold because its run is old or has risen past the cap: buys
  raise it only to the eligible share of the target, sells cut it only to the full target, and anything between is
  held. A red flip is a full exit whatever the policy; STOP, FLATTEN and BLOCK_BUYS work as before.
- The digest and the plan say why, e.g. `green 35 bars, too late to join (max 20): waiting for the next flip` or
  `up 60.0% since the green flip 2026-10-13 (max 50%): waiting for the next flip`.

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
- Always run as `.venv/Scripts/python.exe -m agentic` from the repo root (`agentic/calendar.py` would hide the
  standard `calendar` module if `agentic/` itself were on `sys.path`). The CLI's own hints name the interpreter that
  is running it, e.g. `.venv/Scripts/python.exe -m agentic plan`.
- Windows support (Git Bash hooks, `doctor`, Task Scheduler scripts, the time-zone fallback) is tested on Linux, with
  Windows simulated where it matters. Run `doctor` after every install or Python update, and check the first
  scheduled run in `cron.log`.
- Without a time-zone database (no `tzdata`), US Eastern time comes from the built-in 2007+ rule. It matches the
  database from 2007 on, but not earlier dates.

## 12. Files

| path | contents |
|---|---|
| `agentic/*.py` | config, indicator, backtest, calendar, data, snapshot, entry, planner, ledger, signals, cli, doctor |
| `agentic/hooks/` | PreToolUse guard and PostToolUse capture/journal hooks (standard library only) |
| `agentic/windows/` | Git Bash scripts: `crypto_signals.sh` (the phase 1 job) and `schedule_crypto_signals.sh` (Task Scheduler) |
| `.claude/settings.json` | hooks and deny rules (committed) |
| `.claude/settings.local.json` | `AGENTIC_PYTHON` for this PC: gitignored |
| `private/agentic/config.json` | your config (account numbers): private |
| `private/agentic/inbox/` | raw Robinhood tool results saved by the PostToolUse hook |
| `private/agentic/signals/`, `digests/`, `plans/`, `plan_current.json` | daily outputs |
| `private/agentic/journal.jsonl`, `ledger.json`, `positions_reconciled.json`, `hook.log` | audit trail |
| `private/agentic/cron.log` | output of the scheduled phase 1 job |
| `private/agentic/STOP`, `FLATTEN`, `BLOCK_BUYS` | flags |
| `private/agentic/strategy_start.json` | the first live plan's date (entry policy `fresh_only`) |

Set `AGENTIC_STATE_DIR` to keep state elsewhere (tests use a temporary directory).
