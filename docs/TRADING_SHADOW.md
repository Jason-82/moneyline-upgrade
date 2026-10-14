# Daily Moneyline stock planner and shadow executor

This implementation computes the exact existing `analysis_2026.moneyline_ref.moneyline` daily indicator and constructs deterministic whole-share market orders in an offline simulation. It does not connect to Robinhood, read any real account, propose a trade, submit a trade, or cancel an order. There is no `live` or `submit` CLI command, and the adapter has no placement method.

The default frozen whitelist is empty and has `NOT_EVALUATED` status. A successful synthetic demonstration does not establish a profitable trading strategy. Selecting a real stock basket requires the separate research validation workflow and complete point-in-time data.

## Run the complete offline demonstration

From the repository root, with the repository requirements installed:

```bash
python -m trading.cli demo --output-dir .private_trading/shadow_demo
python -m unittest tests.test_stock_execution -v
```

The demo records three explicitly invented securities, invented split-only prices, an invented $30,000 budget, and the fake account identifier `SHADOW_DEMO_NO_REAL_ACCOUNT`. Session dates and UTC opens/closes come from the XNYS exchange calendar. It computes daily signals as of July 23, 2024, creates three intents before the following opening timestamp, and simulates fills at that exact next-session open. Console output contains only the mode, synthetic flag, order count and as-of date.

Private outputs are `config.json`, `manifest.json`, `inputs.json`, `signals.json`, `plan.json`, `shadow_result.json` and `journal.sqlite3`. They contain private financial context if real saved snapshots are subsequently used; the entire `.private_trading/` directory is gitignored. Files use owner-only permissions on platforms supporting POSIX permissions. SQLite uses WAL and full synchronization. No credentials, OAuth token store, or public account log is created.

## Signal and execution policy

- Daily split-adjusted OHLC only; dividends must not adjust the indicator history.
- Exact reference parameters: ATR Wilder RMA(10), factor 2, `hl2`, reset-on-flip.
- At least 100 bars, finite positive consistent OHLC, sorted unique session dates, no missing session since the first supplied bar.
- The saved calendar is verified against XNYS dates, opens and closes. Weekend guesses, omitted sessions and fabricated opening times fail.
- The latest daily bar must be the exact latest completed exchange session plus a 20-minute settled-close buffer. Its close must match an uninterpolated official close for that same date. A truncated old calendar cannot make old bars appear current.
- The capital budget and account identifier must be explicit. Buying power, portfolio value or model reasoning never supplies a budget. Buy sizing also respects both the saved authoritative and unleveraged buying power; margin leverage is not used.
- A frozen basket receives equal cash slots at initialization. Red slots retain their cash; cash is never redistributed among green stocks. Proceeds and profits stay with that stock's slot. Established runs require an explicit per-slot cash and owned-inventory ledger. Whole shares are bought with a 2% prior-close sizing buffer; this buffer is not a broker price guarantee.
- The configured cold start is `enter_current_green`: a new empty basket enters currently green stocks at the following open. `wait_for_next_green_flip` is supported as an explicitly different convention. No existing holdings are silently adopted into the strategy.
- Following initialization, an empty slot buys on a red-to-green flip. An owned position sells while red; this also lets a reconciled canceled partial sell dispose of the remaining whole shares on a subsequent red decision. Green positions are not topped up or rebalanced daily.
- Sells are limited to strategy-owned quantity and broker-provided `shares_available_for_sells`. Open sell quantities cap availability without double-subtracting broker holds; pending sell proposals are additionally reserved. Unknown local intent outcomes block a new order for that symbol. Pending buys block new buys. Fractional partial-fill inventory is accounted for, but this version sends only whole-share orders; fractional residuals remain pending a future explicit policy.
- A plan has one exact next-session opening timestamp. It must be recorded before that timestamp and expires at the opening instant. Offline fills must match that timestamp exactly. Late signals and late simulated fills are rejected.

The research's next-open price is an execution assumption. Robinhood's exposed equity-order schema supports `market`, `regular_hours`, quantity and `gfd`, but it does not expose a market-on-open order or an approval deadline enforcing the exact opening timestamp. A queued market order or an approval acted on after the open can fill at a different price. The shadow build therefore does not claim broker parity or enable live trading. Activation requires testing the achievable execution convention and updating its research validation.

## Saved JSON contracts

`config/trading_shadow.json` selects shadow mode, the frozen whitelist and the input file. The placeholder account is not a real Robinhood account. Change only an explicit shadow configuration when using saved inputs; changing `mode` to `LIVE` is rejected.

A manifest contains these fields:

```json
{
  "version": 1,
  "frozen_at": "2026-10-14T01:58:31Z",
  "cadence": "daily",
  "signal_params": {"period": 10, "factor": 2.0, "atr_type": "rma", "src": "hl2", "variant": "reset"},
  "symbols": [],
  "selection_rule": "No deployment-qualified selection rule",
  "research_verdict": {"status": "NOT_EVALUATED", "report_sha256": null, "limitations": ["Missing validation evidence"]},
  "manifest_sha256": "computed with trading.planner.freeze_manifest"
}
```

The manifest hash uses canonical JSON, sorted keys and compact separators, excluding `manifest_sha256`. It detects changes; a hash by itself is not evidence that a research verdict is valid or that trading is authorized. The latent live guard demands a nonempty whitelist, `PASS`, a research-report checksum and no unresolved limitations, then hard-blocks placement anyway because live activation is absent. A future activation must independently verify the actual frozen report and explicit user account/budget authorization rather than trusting a hand-edited `PASS` label.

An input file contains `calendar.sessions`, `market_data`, `snapshot` and, for shadow simulation, `fills`. The demo produces a complete inspectable example. The structure is:

```json
{
  "calendar": {"sessions": [{"date": "2024-07-23", "open": "2024-07-23T13:30:00Z", "close": "2024-07-23T20:00:00Z"}]},
  "market_data": {
    "interval": "day", "adjustment_type": "split",
    "bars": {"EXAMPLE": [{"date": "2024-07-23", "open": 100, "high": 102, "low": 99, "close": 101}]},
    "official_closes": {"EXAMPLE": {"date": "2024-07-23", "price": "101", "interpolated": false}}
  },
  "snapshot": {
    "account_number": "EXPLICIT_SHADOW_ACCOUNT", "asof": "2024-07-23", "captured_at": "2024-07-23T20:25:00Z",
    "currency": "USD", "buying_power": "10000", "unleveraged_buying_power": "10000", "cold_start": true,
    "positions": [], "orders": [], "approvals": [], "unresolved_symbols": []
  },
  "fills": {"timestamp": "2024-07-24T13:30:00Z", "open_prices": {"EXAMPLE": "101.50"}}
}
```

The abbreviated calendar/history above is illustrative and intentionally insufficient to run: real inputs require all calendar sessions through the next session and at least 100 complete bars. For an established strategy, `snapshot.cold_start` is false and `snapshot.slot_cash` and `snapshot.strategy_inventory` map every whitelist symbol to decimal strings. Saved equity positions include `symbol`, `quantity`, `shares_available_for_sells`, and `type`. Saved equity orders include at least `symbol`, `side`, `quantity`, `cumulative_quantity`, and `state`. Normalized approvals include `approval_id`, `symbol`, `side`, `quantity`, and `state`; a pending approval is never treated as a filled order.

The broker snapshot must be no older than the configured 300 seconds at planning time. This is an input freshness check, not a representation that a saved snapshot is a live broker response. CLI `--now` allows deterministic replay; normal commands default to real UTC wall-clock time. The demo alone deliberately uses its explicit historic synthetic timestamp.

Separate commands, using the demonstration files as an offline example:

```bash
python -m trading.cli signal --config .private_trading/shadow_demo/config.json --manifest .private_trading/shadow_demo/manifest.json --inputs .private_trading/shadow_demo/inputs.json --now 2024-07-23T20:25:00Z --output-dir .private_trading/replay
python -m trading.cli plan --config .private_trading/shadow_demo/config.json --manifest .private_trading/shadow_demo/manifest.json --inputs .private_trading/shadow_demo/inputs.json --now 2024-07-23T20:25:00Z --output-dir .private_trading/replay
python -m trading.cli shadow --config .private_trading/shadow_demo/config.json --manifest .private_trading/shadow_demo/manifest.json --inputs .private_trading/shadow_demo/inputs.json --now 2024-07-23T20:25:00Z --output-dir .private_trading/replay
```

## Journal, failures and reconciliation

One OS advisory lock covers each mutable CLI run. A transaction inserts every logical intent before a transport could be called. Its UUID `ref_id` is deterministic for the account, as-of date, frozen manifest, symbol, side and exact quantity. The same logical order keeps its UUID on all retries.

Immediately before a simulated submission, the journal commits `UNKNOWN`. A timeout or crash after this transition cannot create a second submission. Repeated shadow runs skip unknown, pending, partial and terminal intents. A different logical order for a symbol with an unresolved journal entry is blocked even if a saved snapshot omits it. There is no automatic retry when a broker read merely fails to find an order: missing orders can reflect pagination, pending approvals, delayed visibility or transport failure. A future connected runner must positively reconcile before resending the same ID; generating a new ID is never a recovery mechanism.

Reconciliation processes only journal-owned IDs or exact recorded client references. It verifies the account and exact symbol/side/quantity/type/hours/TIF, rejects collisions between broker IDs for one logical intent, and transactionally applies only incremental cumulative fills, notional and fees. Repeated observations do not double-count inventory or cash. Partial orders reserve their unfilled remainder; terminal cancellations can still receive a racing fill. An approved proposal is not a fill. The resulting order may carry the approval ID as `ref_id`, so the journal maps it through the recorded `approval_id`. Unrelated `agent_initiated` orders do not establish strategy ownership.

A normalized saved observation file is `{"orders": [...], "approvals": [...]}`. Orders include official `get_equity_orders` fields `id`, `symbol`, `side`, `quantity`, `cumulative_quantity`, `average_price`, `fees`, `state`, `ref_id`, `type`, `market_hours`, `time_in_force`, `trigger`, and optional per-fill `executions`. Then run:

```bash
python -m trading.cli reconcile --config YOUR_SHADOW_CONFIG.json --manifest YOUR_MANIFEST.json --inputs YOUR_INPUTS.json --observations YOUR_SAVED_OBSERVATIONS.json --output-dir .private_trading/YOUR_RUN
```

A missing average price on a nonzero fill, a decreasing cumulative quantity/fees/notional, a negative cash/inventory result, or an account/parameter mismatch fails and rolls back that transaction. The CLI reports a bounded policy error without echoing raw account or broker payloads. Preserve and inspect the private source observations when resolving discrepancies.

## Enforcement hook and STOP

`python -m trading.cli hook ... --request REQUEST.json` is a side-effect-free policy check. The request contains `tool_name`, `arguments`, `plan_sha256`, and `asof`. Connector prefixes are normalized to exact supported Robinhood operation names. Review and placement parameters must exactly match one hashed plan order; review omits the unsupported `ref_id` parameter. Extra dollar amounts, differing accounts, symbols, sides, quantities, execution hours or order types fail. The hook does not act as a credentialed connector or execute any tool.

Creating `.private_trading/YOUR_RUN/STOP` blocks new plans' simulated execution and all new order review/proposal/placement requests. The authorization checker retains permission to cancel a known journal-owned broker ID or decline a known journal-owned approval ID for the exact configured account, even after the plan expires. This is a permission result only: the current CLI has no cancellation transport. No unrelated or guessed ID is allowed. Removing STOP does not authorize live placement.

## Robinhood adapter status and future activation

`trading.robinhood_adapter` follows the official enabled Robinhood tool declarations inspected on October 14, 2026 UTC. It provides typed account, portfolio, quote, position, order and equity-order-request objects through an explicitly injected callable transport. No default callable is connected. Read pagination uses opaque cursors and detects repeated cursors; quotes are chunked at 20 to retain the official close response. Order reviews omit `ref_id`, which the review schema does not support. The adapter cannot place, approve, cancel or decline a trade.

The current official `get_trade_approvals` declaration exposes a generic `CallToolResult` without a documented payload schema. This adapter preserves that result rather than fabricating field names. A future real connector must inspect and validate the actual response shape before normalizing approvals into the saved-input contract. No real account or approval response was accessed during this implementation.

The official preview policy is represented by `approval_requirement`: nonempty `order_checks` requires presenting broker alerts and explicit confirmation; an empty-check preview with `customer_approval_required=true` uses the Robinhood app approval flow; false or absent approval-required calls for explicit confirmation after the preview. When a preview quote is presented, `market_data_disclosure` must be displayed exactly as provided. An unattended agent cannot infer that a configured strategy exempts it from this current tool approval policy.

Live deployment therefore still requires all of: a qualifying frozen research result on complete data; tested attainable fill semantics; explicit account and budget authorization; a verified agentic-allowed active account; fresh broker buying power/positions/orders/approvals; approval-payload parser verification; current pretrade preview/alert/disclosure policy; a connected enforcing transport; and deliberate activation of write capability. These are concrete remaining implementation dependencies. The current build safely exercises planning and recovery without pretending they are already complete.

## Read-only market-data acquisition and saved normalization

The injected adapter now also implements the official `get_equity_historicals` request contract. `historicals(symbols, start_time=..., end_time=...)` requires both explicit timezone-aware timestamps, sends `interval='day'`, `bounds='regular'`, `adjustment_type='split'`, and chunks symbol lists at ten. It never delegates the interval or end time to a default. It returns `HistoricalFetch`, retaining the full raw successful tool responses and exact request parameters; null bars and quality flags remain inspectable in this receipt. An upstream range-size error is not bypassed: explicitly narrow the date range and retain the separate receipts.

`normalise_historical_bars(receipt)` accepts only the actual documented `data.results[].bars` shape, exact requested symbols and echoed daily/regular settings. It rejects unresolved symbols, duplicate results, null entries, interpolated bars, unknown sessions, invalid OHLC, missing fields, and bars outside the requested timestamps. Derived prices preserve decimal strings exactly; there is no gap filling, rescaling or guessed bar. Actual daily labels in the inspected development response are midnight UTC; normalization takes that UTC calendar date and does not shift them into the preceding New York date.

`adapter.saved_signal_data(receipt, quotes, calendar, now)` builds the saved `market_data` contract and runs the complete `compute_signals` checks. The official closes must be for the same exact latest completed date and same symbol set. Historical `close_price` is a last trade, whereas the quote close is officially settled: a mismatch causes rejection rather than quietly replacing the historical value with the quote. The full raw receipt checksum is retained with the normalized input. No actual current official close was fabricated for the historical development sample.

The actual saved 2018–2022 public development historical response was checked offline through this new normalizer: nine symbols each supplied 1,259 valid bars; COIN was rejected because its response includes interpolated pre-IPO bars. This confirms shape parity for public market data, not a broker-account connection or complete point-in-time research dataset.

For data top-ups, use the strict saved historical importer documented in `screener.rh_ingest`. A top-up must overlap existing source prices at the same adjustment scale. A stock split or changed scale requires replacing the complete historical series with a fresh split-only export; appending a differently scaled recent slice can invalidate the indicator. This adapter deliberately provides raw fetch receipts and validation rather than silently merging or rescaling historical stores.

`trade_approval_setting(explicit_account)` implements the official read-only `get_trade_approval_setting` schema with a typed account, boolean approval requirement and optional timestamp. It verifies the echoed account and never changes the setting. A false setting does not promise that a particular order can bypass the preview's own approval policy. These methods all require an explicitly injected transport; the CLI still connects no transport and places no broker calls.

## Optional future external scheduling

The current commands can be invoked by an external scheduler after a trusted read-only acquisition process saves fresh inputs. For example, a future weekday task after the NYSE close can call `python -m trading.cli plan --config YOUR_SHADOW_CONFIG.json --inputs YOUR_FRESH_SAVED_INPUTS.json --output-dir .private_trading/YOUR_RUN`. Do not pass historic `--now` when scheduling real-time checks. The XNYS calendar, official-close checks and snapshot freshness—not a weekday cron expression—decide whether a plan is valid on a holiday, early close or delayed close settlement.

Record scheduler metadata alongside private run outputs: scheduler identity/version, UTC scheduled time and actual run time, command/config checksum, acquisition receipt checksum, as-of session, plan checksum and exit status. Use a single output directory per strategy so the OS lock coordinates concurrent invocations. Plan failure should alert the operator and preserve its inputs; it should never fall back to stale data or an alternate strategy. An opening-time task can only run the current offline shadow simulation with saved exact-open observations. Scheduling does not connect Robinhood, activate live writes or establish account/budget authorization. No scheduler or automation was activated during this work.
