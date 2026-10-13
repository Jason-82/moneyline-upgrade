# Agentic trading plan — running the indicator strategy through Robinhood + Claude

Status: **design, not yet built.** Written 2026-10-13. Companion to `HANDOFF.md`.
Nothing here is financial advice; the account owner is fully responsible for every
trade an agent places (Robinhood's terms say so explicitly).

---

## 1. What Robinhood actually offers (researched Oct 2026)

Sources were mostly read via search snippets because robinhood.com is blocked from
the research environment; verify in the app before relying on any detail.

| topic | finding |
|---|---|
| Product | **Agentic Trading** (beta since 2026-05-27; options June; crypto rolled out 2026-08-17 to 08-31). US only. |
| Account | A separate **Agentic account**. The agent can *read* all your Robinhood accounts but can *trade* only in the Agentic account, and only with funds deposited there. Cash or "limited margin" (no borrowing, no leverage, no shorting). Taxable individual account, not an IRA. |
| Connect Claude | `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`, then `/mcp` to log in (OAuth). Claude Desktop: Settings → Connectors → Add custom connector. |
| Approvals | **Off by default for external agents like Claude** (on by default for Robinhood's built-in agents). Setting: Agent Settings → Safety Controls → Trade approvals. With approvals on, the agent's order becomes a proposal you tap to approve in the app. |
| Limits | No documented per-order, position or daily-loss caps. The **funded balance is the only hard limit**. Disconnecting the agent does not cancel open orders. |
| Market data (stocks) | `get_equity_historicals`: daily/weekly OHLCV, up to 10 symbols per call, split-adjusted by default (`adjustment_type`: none/split/all). `get_index_historicals` for SPX/NDX. Server-side `get_equity_technical_indicators` includes SuperTrend (default 10 / ×3, adjustable). |
| Market data (crypto) | **No historical candles.** Only live quotes (`get_crypto_quotes`). Crypto bars must come from outside Robinhood (e.g. Coinbase Exchange public candles, 00:00 UTC days). |
| Orders | Stocks: market, limit, stop-market, stop-limit; GFD/GTC; fractional/dollar orders only as market orders in regular hours; extended/overnight = limit only. No trailing-stop or bracket orders. Crypto: market, limit, stop-loss, stop-limit; dollar-market orders have collars (~+1% on buys, ~−5% on sells). `ref_id` UUID for idempotent retries. `review_equity_order` / `preview_crypto_order` simulate without placing. |
| Paper trading | **None.** Dry runs = the review/preview tools. |
| Auth | OAuth; access token ~4 days; refresh tokens appear single-use and rotating — two sessions using the connector at once can revoke the login. Headless `claude -p` cannot do the OAuth flow; log in interactively first. Claude Code cloud routines have open bug reports about attaching the Robinhood connector and hanging. |
| Crypto coverage | BTC, ETH, SOL, BNB, ZEC are all listed for US customers. Agent crypto trading is **not available in New York** (and BNB is not tradable in NY at all). |
| Crypto cost | **~0.95% per side on the default market-maker route** (≈1.9% round trip; a 1.87% BTC spread was observed on an agentic account in Sep 2026). Exchange routing: 0.95% taker / 0.50% maker below $10K trailing-30-day volume, falling to 0.25%/0.125% at $50K-$250K and 0.15%/0.075% at $250K-$500K. **Unknown which route agent orders use** — check with `preview_crypto_order`. |
| Stock cost | $0 commission; tiny sell-side SEC/FINRA fees; fills at or near NBBO. |
| Rules | Pattern-day-trader rule eliminated (effective 2026-06-04). T+1 settlement (cash accounts wait a day after stock sales). Wash-sale rule applies to stocks and ETFs across *all* your accounts (Robinhood does not cross-check); not to spot crypto under current law, but bill H.R. 10357 would apply it from 2026-09-14 if enacted as written. Gains will be short-term. |
| Policy | Robinhood's tool descriptions tell the agent to show a preview and get explicit confirmation before placing orders. Anthropic's usage policy update (effective 2026-11-12) treats personalized buy/sell recommendations as high-risk, needing a human in the loop. There are anecdotal (unverified) reports of Claude refusing to place Robinhood trades since late Aug 2026. **Design for approvals ON.** |
| Alternatives | **Robinhood Agents** (built-in, announced 2026-09-29): mobile-only, approvals on by default, pick an LLM. **Loops** (standing automations) "coming soon". Simpler, but cannot run our own validated code. |

Key sources: Robinhood support "Trading with your agent" / "Agentic trading overview";
Robinhood newsroom (2026-05-27, 2026-09-29 HOOD Summit); Robinhood crypto fee schedule
(June 2026); third-party capture of the official MCP tool schemas
(github.com/kevin1chun/robinhood-for-agents, 2026-10-12); Claude Code docs (MCP,
routines); anthropic.com/legal/aup.

---

## 2. Five facts that shape the design

1. **The indicator can be computed exactly from price bars.** Claude cannot look at a
   TradingView chart, and Robinhood cannot run a TradingView script. The repo's
   `analysis_2026/moneyline_ref.py` reproduces the indicator bar for bar (Wilder
   ATR(10) × 2.0 around (high+low)/2, reset-on-flip; 100% match on IWM, 213/213 flips).
   It needs **real highs and lows, unadjusted prices, and closed bars only** (fetch
   ≥250 daily bars so the line settles).
2. **Robinhood's crypto pricing destroys most of the crypto edge.** At ~0.95% per side
   (vs the 0.15% our backtests assumed), the daily signal falls behind buy-and-hold on
   BTC (+5.5 → −12.2 CAGR points) and BNB (+8.8 → −12.7). It survives on ETH (+13.5)
   and SOL (+18.4). See `analysis_2026/costs.py`.
3. **Spot crypto ETFs rescue it.** Trading the same daily crypto signal through
   commission-free spot ETFs one to two days later (the next US session) keeps the edge:
   ETH +22 to +43, SOL +38 to +40 CAGR points vs buy-and-hold; BTC roughly
   break-even on return but max drawdown −61% instead of −84%. (Proxy test using
   each coin's own history; real ETFs only exist since 2024-25.)
4. **The strategy only suits some assets.** From the research: crypto majors yes; equity
   indices no (daily destroys returns; weekly is optional crash insurance); TSLA no;
   HOOD/CRCL/COIN unvalidated. So every new ticker must pass a backtest gate first.
5. **Keep the math out of the LLM.** A deterministic Python script decides; Claude
   operates (fetches data, runs the script, shows the plan, places approved orders,
   reconciles). This makes every decision reproducible and testable.

---

## 3. Architecture

```
            ┌─────────────────────── monthly / quarterly ───────────────────────┐
            │  VALIDATION GATE  (offline backtest per candidate asset, realistic │
            │  costs for the actual vehicle)  ->  approved universe + class     │
            └──────────────────────────────────┬─────────────────────────────────┘
                                               │ approved_universe.json
   daily, after bar close                      ▼
 ┌──────────────┐   ┌───────────────────────────────────────────┐   ┌──────────────────┐
 │ DATA         │──▶│ SIGNAL ENGINE (deterministic Python)      │──▶│ ORDER PLAN +      │
 │ stocks/ETFs: │   │ moneyline_ref.py on last CLOSED bar       │   │ DAILY DIGEST     │
 │  RH MCP      │   │ -> state, flip?, line, distance-to-line   │   │ (json + markdown)│
 │  historicals │   │ sizing + caps -> target weights           │   └────────┬─────────┘
 │ crypto:      │   │ vs current positions -> orders            │            │
 │  Coinbase    │   │ sanity checks (stale data, bad bars)      │            ▼
 │  candles     │   └───────────────────────────────────────────┘   ┌──────────────────┐
 └──────────────┘                                                    │ EXECUTION        │
                                                                     │ Claude + RH MCP  │
   ┌───────────────────────────────────────────────────────────┐    │ preview/review → │
   │ RECONCILE + MONITOR: fills vs plan, positions vs targets,  │◀───│ place (approvals │
   │ auth/data failures -> alert; kill-switch file             │    │ ON → you tap OK) │
   └───────────────────────────────────────────────────────────┘    └──────────────────┘
```

### 3.1 Timing

| asset | signal computed | executed |
|---|---|---|
| Crypto via spot ETF | after the 00:00 UTC daily close (8 pm ET) | next US regular session (open or close); weekend signals wait for Monday |
| Crypto direct on Robinhood (only if cheap routing is confirmed) | after 00:00 UTC | immediately, limit order near mid (24/7) |
| Stocks / ETFs (daily class) | after 16:00 ET close (use `get_equity_quotes` for the settled close) | next regular session |
| Weekly class | after Friday close | Monday session |

Never act on a bar that is still forming — an intraday "flip" can reverse by the close.

### 3.2 Where it runs (pick one)

- **A. Local computer (recommended to start).** A cron job / Task Scheduler runs the
  Python signal job daily and writes the digest + order plan. You then open Claude Code
  and say "execute today's plan": Claude previews each order and places it; with
  approvals ON you tap approve on your phone. No unattended auth problems. Crypto
  candles come straight from Coinbase's public API (works locally; it is blocked only in
  this cloud sandbox).
- **B. Fully scheduled Claude run** (`claude -p` locally, or a Claude Code cloud
  routine). Possible, but fragile today: OAuth re-login every few days, rotating refresh
  tokens, open bugs with the Robinhood connector in cloud routines. Only after A has run
  cleanly for weeks, and with approvals still ON.
- **C. Robinhood's built-in Agents / Loops.** Simplest, but you cannot run this repo's
  validated code or backtests inside it. Worth revisiting when Loops ships.

---

## 4. Strategy rules by asset class (what the research supports)

| asset | rule | vehicle | why |
|---|---|---|---|
| ETH | daily signal, long while green | spot ETH ETF (e.g. ETHA, FETH), or direct crypto only if fees ≤ ~0.25%/side | edge survives every cost and fill test |
| SOL | daily signal | spot SOL ETF (e.g. BSOL/GSOL/FSOL/VSOL, launched late 2025 — verify), or direct | largest, most cost-robust edge; but −30% since 2024 |
| BTC | daily signal **for drawdown control** (return ≈ buy-and-hold), or simply hold | spot BTC ETF (e.g. IBIT, FBTC) | at Robinhood crypto prices the signal loses to holding |
| BNB | watch / hold | no confirmed US spot ETF; direct cost kills the edge | marginal even via ETF proxy |
| ZEC | exclude from signal | — | signal loses to holding |
| SPY / QQQ / IWM | buy-and-hold core; optional **weekly** signal as crash insurance | ETFs | daily signal gives up 60-75% of returns; weekly costs ~2 pts/yr for 16-30 pts less drawdown |
| TSLA | hold or skip; don't use the signal | — | signal halves CAGR |
| COIN, HOOD, CRCL | watch-only, or small "probation" size if you insist | — | too little history; results hinge on 1-2 trades and fill timing |
| Any new ticker | must pass the gate in section 5 | — | most stocks are expected to fail |

Things the research says **not** to add: daily-AND-weekly confirmation (gives up 30-98%
of returns), squeeze or retest filters (skip the biggest runs), trailing 1.5×ATR stops
(−37 CAGR points), leverage (not available anyway).

---

## 5. Per-asset validation gate

Run on **unadjusted daily OHLC** with the indicator computed by `moneyline_ref.py`, and
with **costs for the vehicle you will actually trade** (≈0.02%/side for ETFs and stocks;
0.50-0.95%/side for Robinhood crypto unless cheaper routing is confirmed).

An asset is tradable with the daily signal (**TRADE**) only if all of these hold:

1. **Enough history:** ≥ 7 years and ≥ 40 closed trades, ideally covering a full bear market.
2. **Beats holding after costs:** CAGR ≥ buy-and-hold, **or** CAGR within 2 points and
   max drawdown ≥ 15 points shallower (risk-reduction case, e.g. BTC).
3. **Profit factor ≥ 2.0** (crypto majors scored 3.4-16; daily equity indices 1.2-1.9).
4. **Not one lucky run:** still passes test 2 after removing the single best run.
5. **Fill-robust:** passes with both same-bar and next-bar fills.
6. **Era-stable:** not worse than buy-and-hold by more than 10 CAGR points in any
   ~3-year sub-period, and passes test 2 since 2022.
7. **Low whipsaw:** ≤ 30% of trades end within ±2%.

Other classes: **INSURANCE** (weekly signal saves ≥ 15 pts of drawdown for ≤ 3 pts/yr
CAGR), **HOLD** (no signal; buy-and-hold), **WATCH** (fails test 1), **EXCLUDE**.

Re-run the gate quarterly; demote anything that fails twice. Beware survivorship: we
only tested assets that are still around and popular. Judge a candidate list chosen
*before* looking at results, and treat a pass rate near 100% as a red flag.

---

## 6. Sizing and portfolio rules

- **Fund the agentic account only with money you are willing to let an agent trade.** It
  is the only hard limit Robinhood enforces.
- **Size by distance to the line.** The line is the exit, so the loss if it flips today
  is (price − line)/price. Choose a risk budget per position (e.g. 2-3% of the account):
  `position = account × risk% ÷ distance-to-line`, capped at the max position size.
  Typical crypto distance is 6-12%, so 2.5% risk → ~20-40% position, before the cap.
- **Caps:** max ~30% of the account in any one asset; crypto (BTC+ETH+SOL, ETF or direct)
  together ≤ ~60%, because they move together and behave like one bet.
- **Joining a run already in progress:** within ~3 weeks of the flip, entering earns about
  the same as entering on the flip day (geometric mean per trade: BTC 7.6% vs 8.3%, SOL
  7.0% vs 6.3%). Later than that the evidence is thin (ETH and SOL roughly halve) — use
  reduced size or wait for the next flip.
- **Cash while flat** should earn interest — check whether the agentic account's cash
  earns a sweep rate.

---

## 7. Safety rails (ours, because Robinhood provides almost none)

- **Trade approvals ON** — permanently is reasonable; at minimum for the first 2 months.
- Hard-coded **allowlist** of symbols and **max notional per order / per day** in the
  script; refuse anything else. Long-only; no options.
- **Kill switch:** the script checks for a `STOP` file (or env flag) and does nothing if
  present; plus Robinhood's own disconnect. Remember disconnecting does not cancel open
  orders.
- **Idempotency:** one `ref_id` per (date, symbol, side); check order status before any
  retry; never send an order twice.
- **Data sanity:** the last bar must be the expected closed date; reject zero or negative
  prices, missing highs/lows, or a close far from the live quote; skip trading on any
  failure and alert.
- **Reconcile every run:** positions vs expected; any mismatch → no new orders, alert.
- **One session at a time** with the Robinhood connector (rotating refresh tokens).
- **Log everything** (signals, plans, previews, orders, fills) in the repo or a private
  store. The public repo must never contain account numbers or balances.

---

## 8. Rollout

0. **Prerequisites:** US resident, not in New York for crypto; primary Robinhood account
   in good standing; open the Agentic account (cash, or limited margin to reuse
   unsettled stock proceeds); link the crypto account; turn **approvals ON**; connect
   Claude Code and run `tools/list` to confirm the real tool set.
1. **Cost discovery:** `preview_crypto_order` small BTC/ETH/SOL orders → read route and
   fee. Check spot-ETF tradability and spreads (`get_equity_tradability`, quotes).
   Decide: ETF route vs direct crypto.
2. **Replication check on live data:** pull 300 daily bars via `get_equity_historicals`
   (adjustment_type = none) for a few ETFs and compare `moneyline_ref.py` with the
   TradingView chart; for crypto, compare Coinbase-candle results with the chart for
   two weeks. Expect 100% agreement; investigate any mismatch.
3. **Validation gate** on the candidate list at realistic costs → verdict table.
4. **Shadow mode, 4-8 weeks:** daily digest plus would-be orders via review/preview only.
   Check each day against TradingView.
5. **Small live:** fund a small amount; approvals ON; TRADE-class assets only.
6. **Scale** after a clean run of several weeks with no data, auth or reconciliation
   incidents.

---

## 9. Daily digest (what you would receive)

```
MONEYLINE DIGEST — bars closed 2026-10-13 (crypto 00:00 UTC / stocks 16:00 ET)
ASSET  VEHICLE  STATE  DAYS  FLIP   LINE      DIST   ACTION     SIZE
ETH    ETHA     GREEN   41    -     2,310.4   -8.2%  HOLD       27% (cap 30%)
SOL    BSOL     GREEN    2   NEW    88.1      -9.6%  BUY        +24%
BTC    IBIT     RED      5    -     81,920    +3.1%  STAY FLAT  0%
SPY    SPY      (hold core; weekly GREEN since 2026-04-13)       —
Portfolio: target 51% invested / 49% cash; crypto cluster 51% (cap 60%)
Orders to approve: BUY BSOL $12,000 (limit at ask)
Warnings: none   |  Data: Coinbase candles OK, RH historicals OK, auth expires in 2d
```
(Illustrative numbers.)

---

## 10. Open items before building

- Confirm which crypto route agent orders use, and the real fee (step 1).
- Confirm `get_equity_historicals` returns ≥ 250 daily bars per symbol, unadjusted.
- Backtest the ETF route on the real ETF price histories (they are short: 2024+ for
  BTC/ETH, late 2025 for SOL) to complement the proxy test.
- Decide the user's risk budget, caps and how much to fund.
- Tax plan: short-term gains in a taxable account; track wash sales across all accounts
  for ETF/stock re-entries.
