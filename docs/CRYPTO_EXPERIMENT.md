# Fixed crypto trend comparison

This experiment tests whether the unchanged Moneyline rule adds value in crypto,
and whether a small set of entry, exit and sizing changes improves it. Everything
is research-only. No broker account, trade, proposed order or live configuration
is involved. The original stock indicator and shadow defaults are unchanged.

## Candidates declared before the run

| Candidate | Entry | Exit / exposure | Question |
| --- | --- | --- | --- |
| `moneyline` | Exact existing daily green state | Exact daily red state; own slot holds cash | Baseline |
| `confirm2` | Two consecutive completed green closes | Original red exit | Do fewer false starts pay for the later entry? |
| `breakout20` | Original green plus a close strictly above the previous 20 closes | Original red exit | Does stronger price confirmation preserve enough winners? |
| `wider_exit3` | Original green entry | Current-day ratcheted `hl2 − 3 × ATR(10)` stop | Does holding through more noise improve net returns enough to justify greater giveback? |
| `donchianensemble_fixed` | Equal average of nine close-channel signals | Ratcheted channel-midpoint exits; fractional exposure | Does diversification across trend horizons help without changing risk sizing? |
| `donchianensemble_vol25` | Same nine-horizon signal | 90-day volatility sizing, 25% target, exposure capped at 100% | Does risk sizing improve the comparison after its extra turnover? |

The two entry filters retain a position until the original red exit; they do not
continually require a new breakout. The wider-exit candidate waits for a fresh
original green flip after its own exit. Its stop ratchets before comparing the
current close, preserving Moneyline's timing convention. Signal state carries
causally through the pre-test warmup; it is not reset to fit a test boundary.

No volume/RSI/ADX stack, parameter sweep, best-coin hindsight filter or combination
of whichever modifications happen to win is part of this declared comparison.

## Paper source and explicit departures

The accessible author-hosted [Catching Crypto Trends PDF](https://concretumgroup.com/wp-content/uploads/2026/02/Catching-Crypto-Trends.pdf)
is dated April 9, 2025. It uses close-based Donchian channels, nine horizons
5/10/20/30/60/90/150/250/360, ratcheted midpoint stops and 90-day volatility
sizing. This implementation follows its formal entry-priority and `<=` exit
conditions, including current-close channel maxima and the previously active
Donchian stop. It freezes sample standard deviation of simple returns times
`sqrt(365)` and a relative 20% volatility-only rebalance threshold where the
paper does not fully specify the numerical convention.

The volatility threshold compares the desired target with the last executed
target. Daily price drift alone does not rebalance a position. This explicit
convention is another reason these results are not an exact paper replication.

This is an **adaptation**, not an exact reproduction of the paper's performance.
We cap exposure at 100% rather than the paper's 200%, execute at the following
UTC candle open rather than infer trades from close-to-close returns, and use
fixed causal three-year venue baskets rather than monthly market-wide rotation.
Signal changes bypass the volatility rebalance threshold. The fixed-size ensemble
is included to separate the indicator effect from the position-sizing effect.

## Universe and windows

The acquisition starts from the historical Binance spot archive catalog, not a
list of currently tradable coins. Formation snapshots are 2019-12-31 and
2022-12-31. Each ranks the preceding 30 completed UTC days by median quote
volume, requiring a year of observed venue history and median daily quote volume
of at least 2 million USDT. Stablecoins, wrapped and leveraged tokens are excluded
by declared classification rules. Top 20 and subsequent 20 liquidity ranks are
separate hypotheses; missing slots remain in cash.

The second group is **lower liquidity, not a verified small-cap group**. Historical
market capitalization is not available in this venue dataset. Venue volume does
not measure all-exchange liquidity or current Robinhood order-book depth.

The declared historical windows are 2020–2022 and 2023–2025. The latter is a
later historical check, **not a globally untouched independent holdout**: the
published paper and existing project research already cover overlapping dates.
The rules are frozen before this implementation's outcome calculation, and no
2026 market outcomes are acquired for selecting a winner in this study.

Unknown gaps, migrations, missing executable prices and delisting outcomes do
not erase selected assets. They make affected comparisons unidentified. A
historical archive catalog does not certify complete token identities or
complete failure coverage; these limitations continue to block deployment.

## Fair comparisons and diagnostics

Every candidate uses the same initial capital, selected assets, full horizon,
cash assumption and execution lag. The primary capital model uses 20 separate
slots. A red slot's cash is not transferred to another green asset. Binary
positions are not topped up every day. Fractional ensemble exposure changes
require actual trades, with costs on the amount traded.

Controls are buying and holding the same selected basket, Bitcoin, and SPY's
total-return price index over the matching horizon. SPY remains in cash until
its first actual exchange session; weekend prices represent held-position marks,
not fictional equity trades. SPY's assumed entry/exit cost is 3 basis points.
Crypto all-in cost scenarios are 0/10/50/95 basis points per side. These are
declared sensitivities, not a promise about a particular account's future fees,
spreads or market impact. Limit orders are not assumed to eliminate costs.

The crypto quote unit is USDT while SPY is USD. Treating these as equal is an
explicit peg assumption, not verified USD performance. Spot price histories
exclude staking income, token rewards and unreconciled migrations. A supplied
illustrative tax scenario uses the existing single-account FIFO stock-like
35%/20% model, including its wash-sale deferral convention, and is not an
assertion that every crypto transaction has those tax rules or dollar basis.
After-tax outputs must retain that label; missing data never becomes a tax result.

The report retains all candidate failures and compares CAGR, drawdown, exposure,
turnover and trade outcomes. A change should earn its complexity across periods
and cost assumptions, rather than merely produce the best single backtest.
BTC/ETH/SOL single-asset diagnostics help inspect entry/exit effects; an asset
without sufficient pre-test history is reported unavailable for that full window,
rather than given a conveniently shortened test.

## Reproduction

Install the repository requirements. Acquisition commands, frozen run commands
and final source/output hashes are recorded in the accompanying results document.
The runner refuses changed settings, implementation, source bundle or benchmark
after freezing. Raw downloads, source receipts and full local ledgers remain in
gitignored `private/` paths. A compact aggregate results receipt can be published.

No candidate is promoted to a live whitelist by this experiment. A future
prospective evaluation, actual venue execution checks and deliberate account/
budget authorization are still needed before funded trading.
