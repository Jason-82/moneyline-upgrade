# Agentic trading plan — running the indicator strategy through Robinhood + Claude

Status: **design, not yet built.** Written 2026-10-13, revised the same day after an
adversarial review (35 of 37 high/medium findings confirmed and applied). Companion
to `HANDOFF.md`. Not financial advice; the account owner is fully responsible for
every trade an agent places.

Every number below comes from a committed script: `analysis_2026/costs.py`,
`gate.py`, `portfolio.py`, `supplementary.py`, `replicate.py`.

---

## 1. What Robinhood offers (researched Oct 2026)

Mostly read through search snippets, because robinhood.com is blocked from the
research environment. Verify in the app before relying on any detail.

| topic | finding |
|---|---|
| Product | **Agentic Trading**: beta since 2026-05-27, options added in June, crypto rolled out 2026-08-17 to 08-31. US only. |
| Account | A separate **Agentic account**. The agent can *read* all your Robinhood accounts but *trades* only the Agentic account, using only funds deposited there. Cash or "limited margin" (no borrowing, no leverage, no shorting). Taxable individual account, not an IRA. |
| Connect Claude | `claude mcp add robinhood-trading --transport http https://agent.robinhood.com/mcp/trading`, then `/mcp` to log in (OAuth). |
| Approvals | **Off by default for external agents like Claude.** Turn on under Agent Settings → Safety Controls → Trade approvals. With approvals on, the agent's order becomes a proposal that you approve in the app. |
| Limits | No documented per-order, position or loss caps. **The funded balance is the only hard limit.** Disconnecting the agent does not cancel open orders, and crypto limit orders last 90 days. |
| Stock data | `get_equity_historicals`: daily/weekly OHLCV, 10 symbols per call, `adjustment_type` = `split` (default) / `none` / `all`. Server-side SuperTrend indicator available (default 10 / ×3, adjustable). |
| Crypto data | **No historical candles.** Live quotes only, so crypto bars must come from outside Robinhood (e.g. Coinbase Exchange public candles, 00:00 UTC). |
| Orders | Stocks: market, limit, stop-market, stop-limit, GFD/GTC. Fractional and dollar orders are market-only, regular hours. Extended hours: limit only. No trailing-stop or bracket orders. Crypto: market, limit, stop-loss, stop-limit; dollar-market orders have collars (~+1% buy / ~−5% sell). `ref_id` UUID for idempotency. `review_equity_order` / `preview_crypto_order` simulate an order without placing it. |
| Paper trading | **None.** Dry runs use the review/preview tools. |
| Auth | OAuth. Access token ~4 days. Refresh tokens appear single-use and rotating, so two sessions using the connector at once can revoke the login. Headless `claude -p` cannot run the OAuth flow. Open bug reports cover the Robinhood connector in Claude Code cloud routines. |
| Crypto coverage | BTC, ETH, SOL, BNB, ZEC are listed for US customers. Agent crypto trading is **not available in New York**. |
| Crypto cost | **~0.95% per side on the default route** (~1.9% round trip; a 1.87% BTC spread was observed on an agentic account). Exchange routing: 0.95% taker / 0.50% maker under $10K trailing-30-day volume, about 0.15% taker only above $250K. **Which route agent orders use is unknown**; check with `preview_crypto_order`. |
| Stock cost | $0 commission; small sell-side SEC/FINRA fees. |
| Rules | The pattern-day-trader rule is gone (2026-06-04). T+1 settlement. Wash sales apply to stocks/ETFs across *all* your accounts, and Robinhood does not cross-check them; spot crypto is not covered under current law (H.R. 10357 would change that). Gains will be short-term. |
| Policy | Robinhood's tool descriptions require a preview and explicit user confirmation before an order is placed. Anthropic's usage policy (effective 2026-11-12) treats personalized buy/sell recommendations as high-risk, needing a human in the loop. There are unverified reports of Claude refusing Robinhood trades since late August. **Design for approvals ON.** |
| Alternatives | **Robinhood Agents** (built-in, announced 2026-09-29): mobile-only, approvals on by default. **Loops** "coming soon". Simpler, but they cannot run this repo's validated code. |

Key sources: Robinhood support articles ("Trading with your agent", "Agentic trading
overview"); Robinhood newsroom (2026-05-27, 2026-09-29); Robinhood crypto fee schedule
(June 2026); third-party capture of the official MCP tool schemas
(github.com/kevin1chun/robinhood-for-agents, 2026-10-12); Claude Code docs (MCP,
routines); anthropic.com/legal/aup.

---

## 2. Facts that shape the design

1. **The indicator can be computed exactly from price bars** (`moneyline_ref.py`:
   Wilder ATR(10) × 2.0 around (high+low)/2, reset-on-flip). On IWM it matched
   100% of bars and 213/213 flips (`replicate.py`), and it is consistent with all 23
   testable exports. Requirements:
   - real highs and lows
   - **split-adjusted but not dividend-adjusted** prices, i.e. TradingView's default
     (Robinhood `adjustment_type='split'`). Never `'none'`: every split becomes a fake
     crash and a false red flip.
   - **closed bars only**
   - ≥250 daily bars of history
2. **Robinhood's crypto pricing destroys most of the direct-crypto edge.** At ~0.95%
   per side the daily signal trails buy-and-hold on BTC (−12.2 CAGR points) and BNB
   (−12.7). ETH (+13.5) and SOL (+18.4) survive on full history, but since 2022 ETH is
   only +1.4, and since 2024 it is −2.7.
3. **Spot crypto ETFs rescue ETH and SOL, not BTC.** The proxy uses the daily crypto
   signal, executed only in NYSE sessions (weekend and holiday signals wait), at
   0.02% per side. CAGR edge vs buy-and-hold, next session / one session later:
   - **ETH +38.7 / +25.8**
   - **SOL +42.4 / +35.7**
   - **BTC −3.1 / −0.2** (max drawdown −69% vs −84%)
   - BNB −0.4 / −2.7

   Proxy caveats:
   - It uses each coin's own history, because real ETFs only exist since 2024-25.
   - It fills at the crypto close, ~4 h after the US close.
   - It ignores ETF fees (~0.1-0.25%/yr), premium/discount, and spreads on small SOL ETFs.
   - An earlier version also traded on weekends and overstated BTC (+1.8); superseded.
4. **Taxes matter, because the account is taxable.** The signal realizes short-term
   gains about 7 times a year per coin; buy-and-hold defers them. With illustrative
   35% short-term / 20% long-term rates (`gate.py`), after-tax edges via ETF are:
   - ETH +21.5
   - SOL +26.6
   - BTC −14.3
5. **The edge vs holding is mostly bear-market avoidance.** ETH's edge sits in the
   2017-19 block (+0.60/yr in log wealth, vs +0.05 in 2020-22 and −0.07 in 2023-25).
   SOL's comes from 2022. Across five correlated coins that is roughly two
   independent crashes (2018, 2022). Expect the signal to lag in bull markets.
6. **Keep the math out of the LLM.** Deterministic Python decides; Claude operates.
   - Price bars come from public feeds that Python reads directly.
   - Robinhood account data (positions, equity, quotes) reaches Python only as raw,
     unedited MCP tool output saved to disk, which Python validates.
   - Only Python produces orders. Claude never retypes numbers or sizes positions.

---

## 3. Architecture

```
  quarterly:  GATE (gate.py on fresh data, vehicle costs + timing, after tax)
              -> approved_universe.json  {asset: class, vehicle, size}

  PHASE 1 — cron, no Robinhood access, after each bar closes
  ┌────────────────────────┐   ┌──────────────────────────────────────────────┐
  │ PUBLIC DATA            │──▶│ SIGNAL JOB (Python)                          │
  │ crypto: Coinbase daily │   │ moneyline_ref on last CLOSED bar per asset   │
  │  candles (00:00 UTC)   │   │ state, flip, line, distance, target weight   │
  │ stocks/ETFs: public    │   │ data checks (dates, OHLC sanity, big wicks)  │
  │  split-adj. daily OHLC │   │ -> signals.json + digest (private store)     │
  └────────────────────────┘   └──────────────────────────┬───────────────────┘
                                                           │
  PHASE 2 — interactive Claude Code session (holds the only Robinhood login)
  ┌────────────────────────────────────────────────────────▼───────────────────┐
  │ 1. Claude saves raw MCP JSON: positions, equity, quotes, open orders       │
  │ 2. Python validates it (schema, positions×quotes+cash≈equity, quotes near  │
  │    last close, RH bars ≈ public bars) and writes plan.json:                │
  │    plan_id, as_of_bar, valid_until, orders[symbol, side, whole shares,     │
  │    limit, TIF, ref_id = uuid5(plan_id|symbol|side|attempt)]                │
  │ 3. Claude previews and places ONLY plan.json orders. A PreToolUse hook     │
  │    blocks any place/cancel call that doesn't match exactly (see section 7) │
  │ 4. Approvals ON: you approve in the app, checking against the digest       │
  │ 5. Python reconciles fills and journals them (private store)               │
  └────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Timing and plan validity

| vehicle | signal computed | executed | plan expires (`valid_until`) |
|---|---|---|---|
| Crypto via spot ETF | after the 00:00 UTC close (8 pm ET) | next NYSE regular session; weekend/holiday signals wait | 15:45 ET that session |
| Crypto direct (only if cheap routing is confirmed) | after 00:00 UTC | right away, limit near mid, with the section 7 reprice ladder | 6 h |
| Stocks/ETFs (daily class) | after 16:00 ET | next regular session | 15:45 ET that session |
| Weekly class (index insurance) | after Friday close | Monday session | Monday 15:45 ET |

- Never act on a bar that is still forming.
- At `valid_until`, cancel everything unfilled or unapproved from that plan, and let the
  next run recompute. Never re-submit an old plan.
- Lag costs money. Executing every trade one session late cuts ETH's ETF-route edge from
  +38.7 to +25.8.
- Evening option, after verifying in shadow mode: place whole-share GFD limit orders for
  the next session right after the 00:00 UTC run, and approve them while you're awake.

### 3.2 Where it runs

- **A. Local computer (recommended).** Phase 1 runs from cron / Task Scheduler.
  Coinbase's public API works locally; it is blocked only in this cloud sandbox. For
  phase 2 you open Claude Code and say "execute today's plan". Only the interactive
  session holds the Robinhood login, so nothing expires unattended.
- **B. Fully scheduled Claude run** (`claude -p`, or a cloud routine). This is fragile
  today: re-login every few days, rotating refresh tokens, and connector bugs. Consider
  it only after A has run cleanly for weeks, still with approvals on.
- **C. Robinhood's built-in Agents / Loops.** Simplest, but cannot run this repo's
  validated code.

---

## 4. Verdicts by asset (from `gate.py`, illustrative tax rates)

| asset | gate result | what to do | vehicle |
|---|---|---|---|
| **ETH** | **TRADE** via spot ETF (passes all 7 tests). Direct crypto fails era stability (2023-25 block −0.27/yr) and is +1.9 after tax. | daily signal | spot ETH ETF (e.g. ETHA, FETH) |
| **SOL** | **PROBATION**: fails only the history test (5.2 yrs, 39 trades). After-tax ETF edge +26.6. Edge comes from 2022; −30% since 2024. | daily signal at small fixed size (≤10%); re-gate mid-2028 | spot SOL ETF (BSOL/GSOL/FSOL/VSOL reported since late 2025; verify) |
| BTC | NO-SIGNAL: −14.3 after tax via ETF, −22.2 direct | **hold** (signal only in a tax-advantaged account, by explicit choice) | spot BTC ETF or coin |
| BNB | NO-SIGNAL | hold or skip | no confirmed US spot ETF |
| ZEC | NO-SIGNAL | hold or skip | — |
| SPY / QQQ | daily NO-SIGNAL; weekly **INSURANCE** qualifies (SPX gives up 1.7-1.9 pts/yr for 16-21 pts less drawdown; NDX 2.1-2.9 for 30-36). HANDOFF 5.17 (exploratory, daily bars, after tax): a plain 200-day rule cut at least as much drawdown for less in every SPY/QQQ/S&P window except QQQ 2000-2012; the regime switch (hold above the 200-day, daily signal below) costs less still but cuts less drawdown on QQQ | hold; optional crash insurance (weekly signal, or the cheaper plain 200-day rule or regime switch) | ETF |
| IWM | daily NO-SIGNAL; weekly fails INSURANCE (gives up 3.3-4.1 pts/yr); HANDOFF 5.17 (exploratory): only the 200-day regime switch was near-free insurance 2001-2026 | hold | ETF |
| TSLA | NO-SIGNAL (signal halves CAGR) | hold or skip | — |
| COIN, HOOD, CRCL | NO-SIGNAL; also fail the history test | watch only | — |
| new tickers | run `gate.py` first | — | — |

Caveats on these verdicts:

- The gate thresholds were written after seeing these results.
- The five coins are correlated survivors.
- A pass on ~two bear markets of evidence is not proof.

Do **not** add these (all tested):

- daily-AND-weekly confirmation (gives up 30-98% of terminal wealth)
- squeeze or retest filters
- trailing 1.5×ATR stops (−37 CAGR points)
- leverage (not available anyway)
- a regime switch on crypto (hold in good regimes, the indicator in bad ones): on ETH it is
  far below the indicator alone on every route (HANDOFF section 5.17). On indices it is
  drawdown insurance, not an edge. It does not robustly beat holding after tax: never on the
  S&P 1963-2026, and the SPY and QQQ wins are post hoc and window-dependent (QQQ's window
  starts at the dot-com top).
- buying touches of moving averages ("bounces at key levels", e.g. the 200-day SMA): no edge
  on S&P 500 members 1996-2026 or 40 coins, on any of 34 daily/weekly/monthly averages, and
  the average is no better than a line 1-2 ATR away (HANDOFF section 5.19).
- scalping or bid-ask capture (resting at the bid, selling at the ask) in low-volume stocks or
  illiquid crypto: in crypto it loses to adverse selection in every tested band, even with zero
  maker fees; in stocks the intraday test on 5-minute bars was inconclusive (bars without quotes
  cannot test it), and daily liquidity provision in thin stocks cannot pay its spreads (HANDOFF
  section 5.21). The agent is also too slow for it, gets no rebates and cannot short.

---

## 4b. Opening up the stock universe (`screener/`)

**Result (2026-10-14): don't run a stock basket on this indicator in the taxable account.**

- **The test:** `screener/strictness.py` traded baskets from strict to loose, picked by
  past indicator fit, walk-forward on S&P 500 history 2005–2026 (point-in-time membership,
  next-open execution, costs, tax).
- **Development:** no level beat SPY after tax consistently. The best levels tied it and
  beat it in only half the 3-year windows.
- **Out of sample:** the one variant that looked better (hold SPY while a stock is red)
  failed in 2025–26. On point-in-time data that includes dead companies, every basket level
  lost to SPY in the full 2023–2025 holdout.
- **Fit carries forward only weakly:** about 7%.
- **"Decent fit" baskets lost clearly**, and the per-stock gate's strict filter did worse
  than random picks.
- **Scan broadly, for information only.** `screener/scan.py` matches TradingView on every
  IWM date. A free daily-updated source of split-adjusted OHLC for about 2,300 US stocks
  (`data.from_long_parquet`, see `screener/README.md`) makes a nightly cloud scan possible
  with no Yahoo access and no local machine.
- **If the user still wants a stock sleeve:** treat it as an experiment with small money
  and a forward log. Use SPY as the default holding and swap a slot into a top-10
  past-skill stock while it is green. On the qlib data it was slightly ahead of SPY in all
  three periods (+1.4, −0.1 and +1.0 pts/yr). On the less biased point-in-time data it
  **lost by 5.9 pts/yr over 2023–2025**. It depends on single big winners and ran deeper
  drawdowns (about −60% in 2008 vs −55%). Not validated, and the better data argues against
  it.

## 5. Validation gate (`analysis_2026/gate.py` is authoritative)

Run per asset **per vehicle**, using that vehicle's cost and timing. The coin's own
history stands in for an ETF.

| vehicle | cost/side | primary timing | alternate timing |
|---|---|---|---|
| crypto direct | 0.95% | same-bar close | next bar |
| spot ETF | 0.02% | next NYSE session | session after |
| stock daily | 0.03% | next session | same-bar |

1. **History:** ≥ 7 years and ≥ 40 closed trades.
2. **Edge after costs and taxes**, primary timing: after-tax CAGR ≥ buy-and-hold's
   after-tax CAGR (taxed once at the long-term rate), **or** within 2 points with max
   drawdown ≥ 15 points shallower.
3. **Profit factor ≥ 2.0** (sum of winning trade % / |sum of losing %|).
4. **Not one lucky trade:** remove the best closed trade's dates from both series;
   rule 2 (pre-tax) must still pass.
5. **Timing-robust:** rule 2 (after tax) also passes at the alternate timing.
6. **Era-stable:** non-overlapping 3-calendar-year blocks. Annualized ln(signal ÷ B&H)
   must be ≥ −0.15 in every block, with a median above 0, and rule 2 (pre-tax) must
   pass since 2022.
7. **Low whipsaw:** ≤ 30% of trades end within ±2%.
8. **T2b, beats holding SPY:** after-tax CAGR ≥ holding the S&P 500 (dividends counted,
   taxed once at the long-term rate) over the same dates, or within 2 points with max
   drawdown ≥ 15 points shallower; and above the after-tax T-bill yield. Rule 2 alone
   flatters assets that fell; COIN passes rule 2 while losing money.

Noise also passes. On no-edge stocks about 2% get TRADE at 7-8 years of history, versus
~0.2-0.7% at 19-20 years. When gating many names, compare the real pass count with
`placebo()`'s expected false passes.

Results:

- **TRADE**: all seven pass.
- **PROBATION**: fails only test 1; small fixed size at most.
- **NO-SIGNAL**: hold or skip.
- **INSURANCE** (weekly index signal, dividends and cash yield counted): gives up
  ≤ 3 CAGR points a year and saves ≥ 15 points of drawdown, at both same-week and
  next-week fills.

Tax rates are inputs: replace the illustrative 35% / 20% with your federal + state
rates. Re-run quarterly and after every new data export. Judge a candidate list chosen
*before* looking at results, and treat a high pass rate as a red flag.

---

## 6. Sizing (from `portfolio.py`, ETF route, pre-tax)

| basket | buy & hold | signal, full allocation | fixed 25% per asset | 2.5% risk ÷ (1.5 × distance), cap 30% |
|---|---|---|---|---|
| ETH+SOL (2021-06+) | 17.7% / −91% | 49.4% / −60% | 31.6% / −37% | 15.6% / −19% |
| BTC+ETH (2016-06+) | 64.8% / −91% | 89.3% / −60% | 48.8% / −36% | 30.8% / −22% |

(CAGR / max drawdown. Total crypto exposure is capped at 60% in all signal schemes.)

- **Sizing sets how much risk you take; it adds no edge.** Return per unit of drawdown
  is about the same for every scheme. Distance-based sizing is no better than a fixed
  fraction, so **prefer a fixed fraction**. It is simpler, and it doesn't grow late
  entries.
- **Caps:** ≤30% per asset; total crypto ≤60%, because the coins flip red together.
- **The line is a trigger, not a stop price.** At a flip, price sits a median 10-16%
  above the line (BTC 10.0, ETH 13.5, SOL 15.9), versus 6.6-10.5% later in a run.
  Exits fill past the line:

  | | median | 10th percentile | worst |
  |---|---|---|---|
  | same-bar | 1.5-2.3% | 5.5-7.1% | 10-33% |
  | ETF route (next session) | 1.0-2.9% | 8-12% | 21-40% |

  Plan for a crash costing several times the "distance" across the whole crypto cluster.
- **Joining a run already in progress:** entering within ~3 weeks of the flip earns
  about the same as entering on the flip. Pooled geometric mean, at flip vs day 1-20:

  | | at flip | day 1-20 |
  |---|---|---|
  | BTC | 8.3% | 7.6% |
  | SOL | 6.3% | 7.0% |
  | BNB | 21.0% | 23.7% |

  After ~3 weeks ETH roughly halves and SOL falls by a third, on thin samples. Use at
  most the flip-day size.
- Check whether cash in the agentic account earns interest.

---

## 7. Safety rails (Robinhood provides almost none)

- **Approvals ON**, and prove it. After each place call, read the order status; it must
  show "awaiting your approval" (record the exact status name in shadow mode). If an
  order is accepted or filled without approval, write `STOP` and alert.
- **Rails enforced where orders are placed.** Python enforces the allowlist and the
  per-order and per-day notional caps when it writes `plan.json`. A Claude Code
  `PreToolUse` hook on `mcp__robinhood-trading__(place|cancel)_.*` re-reads `plan.json`
  and blocks the call (exit 2) unless all of these hold:
  - no `STOP` file exists
  - the plan date is today and the time is before `valid_until`
  - symbol, side, type, time-in-force and `ref_id` exactly match a plan entry
  - quantity is no more than the plan's
  - the limit price is within the plan's collar
  - today's placed notional (from a local ledger) stays under the daily cap

  Deny every other write-capable Robinhood tool in `permissions.deny` (options, alerts,
  scans, watchlists). Give the executor session no web or news tools. Execute only from
  Claude Code; Claude Desktop has no hooks.
- **Kill switch.** A `STOP` file blocks all place calls; the executor then lists the
  agent's open orders and cancels each one (there is no bulk cancel). A `FLATTEN` file
  allows sells only.
- **Idempotency and journal.** Python generates every `ref_id`. A private journal
  records (plan_id, ref_id, status, filled quantity). At the start of each run:
  1. list open orders and pending proposals, and cancel any that aren't in today's plan
  2. resume, never re-send, anything already placed
  3. size against positions plus open orders
- **Reconcile in shares.** Expected = last reconciled positions + journaled fills.
  - Partial fills and expired orders are normal states, not mismatches.
  - An unexplained change (manual trade, unknown order, corporate action) blocks new
    *buys* and alerts.
  - **Exits toward target are always allowed.**
- **Unfilled limits:** time out (15 min for stocks/ETFs, 30 min for crypto), re-quote up
  to twice, then cross the spread within a set collar. An exit still unfilled goes to
  you as an urgent alert; it is never silently skipped.
- **Data sanity:**
  - the last bar is the expected closed date
  - no zero or negative prices; high ≥ max(open, close) ≥ min(open, close) ≥ low
  - quotes are near the last close (in ATR units)
  - one-day close ratios near 1/2, 1/3, 1/10 (missed splits) are flagged
  - a bar whose true range exceeds ~4× the prior ATR10 is flagged, and you check it on
    TradingView before approving. A single bad wick can move a flip.

  Any data failure means no new buys and an alert.
- **Script vs chart.** The script on closed bars is the authority. If a daily check
  finds a different state, flip date or line (beyond 0.05%) from TradingView's closed
  bar, block entries for that asset, still allow exits, and alert.
- **One session at a time** with the Robinhood connector (rotating refresh tokens).
- **Logs go to a private store only** (outside this public repo, or a gitignored
  `private/`). Orders, fills and digests reveal positions and account size. Only code
  and backtests are committed.

---

## 8. Rollout

**Interim (no local job, nothing unvalidated):**

- **IBIT:** hold and ignore flips.
- **BSOL:** if you follow the SOL signal (PROBATION, ≤10%), read it on TradingView
  **COINBASE:SOLUSD**, after the 00:00 UTC close, and act in the next NYSE session.
  Never read it off BSOL's own chart.
- **Ivan's screener:** discovery only, with a dated log of what it flags.

0. **Prerequisites:**
   - US resident; not New York, for crypto
   - open the Agentic account (cash, or limited margin to reuse unsettled stock
     proceeds)
   - link the crypto account
   - turn **approvals ON**
   - connect Claude Code and run `tools/list` to confirm the real tool set
1. **Cost discovery:**
   - `preview_crypto_order` small BTC/ETH/SOL orders and read the route and fee
   - check spot-ETF tradability and spreads
   - decide ETF route vs direct crypto
2. **Replication check:**
   - **Stocks/ETFs:** 300 daily bars (`adjustment_type='split'`) for a few ETFs.
     Compare state, flip dates **and line value** with the TradingView chart.
   - **Crypto, locally:** fetch Coinbase daily candles covering
     `data/tv_full/{BTC,ETH,SOL}_1D.csv` (TradingView's COINBASE pairs). Check the
     closes match every day, then require every flip on the same day and the line
     within 0.05% after a 250-bar warm-up.
   - A two-week colour-only comparison proves little. Do not trade crypto until this
     check passes.
3. **Gate:** run `gate.py` with your tax rates on fresh exports.
4. **Shadow mode, 4-8 weeks:** daily digest plus would-be orders via review/preview
   only. Compare the closed bar's line value (not just its colour) with TradingView
   every day. Confirm:
   - which status a proposal shows
   - whether unapproved proposals expire
   - whether orders placed after the close are queued
5. **Small live:** approvals ON; ETH (TRADE) at normal size; SOL (PROBATION) at
   ≤10%. Keep the daily line check running.
6. **Scale** after several clean weeks with no data, auth or reconciliation incidents.

---

## 9. Daily digest — EXAMPLE, NOT AN ORDER

```
MONEYLINE DIGEST
crypto bar 2026-10-12 (closed 00:00 UTC 10-13) / stocks bar 2026-10-12 (closed 16:00 ET)
ASSET  VEHICLE  STATE  DAYS  FLIP  LINE         DIST    TARGET   ACTION
ETH    ETHA     GREEN   41    -    2310.4123    -8.2%   25%      HOLD
SOL    BSOL     GREEN    2   NEW   88.1077      -14.1%  10%      BUY (probation size)
BTC    IBIT     (hold core — signal not used)
SPY    SPY      (hold core; weekly GREEN since 2026-04-13)
Orders for phase 2: BUY <N> sh BSOL LIMIT <ask+collar> GFD, valid until 15:45 ET
                    (whole shares computed at execution from the live ask)
Warnings: none | Data: Coinbase candles OK, stock OHLC OK
```
(Illustrative numbers. TradingView labels a crypto daily candle by its 00:00 UTC open.)

---

## 10. Open items before building

- Crypto order route and fee (step 1); spot-ETF spreads, especially the small SOL ETFs.
- A public source of split-adjusted daily OHLC for stocks/ETFs, checked against
  Robinhood historicals.
- Whether Claude Code can save an MCP tool result to disk without the model retyping it.
  If not, keep payloads small and rely on Python validation.
- Your tax rates (federal + state); wash-sale tracking across all accounts for ETF
  re-entries.
- Backtest on real ETF price histories (short: BTC/ETH 2024+, SOL late 2025+).
- Your risk budget, caps and funding amount.
