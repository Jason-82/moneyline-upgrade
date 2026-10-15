# Crypto regime study — declared before its first run, 2026-10-14

Base: `4cb2b28`, the latest default branch when this study began. Read HANDOFF and
the corrected FINDINGS entries first. The new size-tier results already describe
crash avoidance, not superior upside capture. The leverage/breakout study has code
but no committed results at this base. Earlier Codex PR #2 used different dates,
venues and accounting, so its numbers are not interchangeable with these.

## Question and fixed candidates

Does a regime detectable using only completed historical bars improve the original
daily Moneyline strategy relative to **both** holding the same coin and always
using Moneyline? Regime detection itself must also have a control.

Primary classifier: BTC closing price versus its 200-calendar-day simple moving
average, and that average's change over the preceding 20 days. Bull = price above
a rising average; bear = price below a falling average; transition = other valid
days. Undefined history is unavailable, never retroactively filled.

Primary hybrid: **hold continuously in bull; daily Moneyline green/flat in bear
and transition**. This tests whether avoiding bull-market whipsaws is useful.
Comparators: buy-and-hold; always Moneyline; bull-only Moneyline/cash; bull-only
holding/cash (isolates the classifier); Moneyline outside bull/cash; and the
opposite hybrid (Moneyline in bull, hold otherwise). All are long-only, unlevered.

Declared alternatives, reported together without selecting a winner: own-coin
200-day average/slope; BTC 150/250-day averages with the same 20-day slope; BTC
200-day level alone; BTC running-high drawdown hysteresis (bear at -20%, recover
to bull at -10%; running high starts at observed history's beginning).

Descriptive conditions: the primary classifier; price path efficiency over 60
days (<0.25 = choppy); and high volatility (60-day annualized daily-return SD above
its strictly prior expanding 75th percentile, minimum 365 past observations).
These are prior-state labels, not forecasts or externally observed true regimes.

## Data, execution and attribution

1. Five full TradingView daily exports in the repo: preserve their actual exported
   Moneyline states, discard each last potentially forming row. Close-only data
   cannot support open fills or intraday stops. Primary execution is the **next
   day's close**, with one extra day's delay as sensitivity. No same-bar fills.
2. Independently inspect the earlier SHA-receipted Binance OHLC bundle if available:
   actual next UTC-day **open** fills, exact `moneyline_ref`, each asset's complete
   observed history. Report missing windows explicitly rather than manufacture
   delisting/migration prices. This bundle is a historically selected subset, not
   the full 578-coin archive or a new point-in-time basket.
3. Reproduce the published full-universe payoff table from `coin_years_retail.csv`.
   Annual return buckets are **hindsight attribution only**, never a trading rule.
   Independently aggregate those rows by BTC's calendar-year sign for market-wide
   hindsight context; that too is unavailable at the start of a year.
4. Zero cash return primary (no future annual T-bill averages); fixed 4% annual
   cash return sensitivity. Costs per side: 0.15%, 0.30%, 0.95%, treated as scenarios,
   not verified current broker fees. Buy-and-hold pays both entry and final exit.
5. Each path retains positions and cash through regime changes and calendar years.
   Pay every actual position change; switching from hold to Moneyline while green
   creates no sale. Fully liquidate at the end for fair comparison. Attribute
   additive daily **log relative wealth** to labels known before that return period;
   never concatenate separate regime-day returns into a pretend CAGR/drawdown.
6. Periods: full available history with at least 250-day own/BTC warm-up; development
   through 2022; later 2023-2025; 2026 through the last completed exported date.
   Later slices are already exposed historical checks, **not untouched holdouts**.
   Also report complete calendar years and rolling non-overlapping 365-day blocks.
7. Illustrative tax sensitivity: one-position full-sale realized gains, 35% short
   term / 20% after more than 365 days, losses carried forward with no tax credit,
   tax paid immediately at sale, no wash-sale modeling. No actual tax-law/account
   claim. This is separate from pretax inference.

## Evidence and rejection discipline

Do not infer a usable classifier from hindsight crash buckets. Do not optimize
thresholds after results. A primary hybrid is promising only if it beats both
controls on growth without worse drawdown in the later BTC and ETH slices, the
direction survives cost/delay checks and 150/250-day neighbors, and gains are not
just one crash. Report all failures. SOL/BNB/ZEC are cross-asset diagnostics, not
five independent crypto cycles. Use time-block uncertainty on equal-weight daily
log active returns (preserving shared cross-asset dates), not iid coin-day tests.
No changes to signal production, existing gates, defaults or live trading.

This study cannot establish a live regime today: committed TradingView exports
end in August 2026. Prospective shadow tracking would still be needed.
