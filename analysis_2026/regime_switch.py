"""
Regime switching: buy & hold in "good" markets, the indicator in "bad" ones.

The user's two questions (2026-10-14):
  A. The daily indicator rarely beats buy & hold, yet it cuts drawdowns, so it must win in
     down markets and lose in up markets. Is the up-market loss "false breakouts" - selling
     on a red flip and having to buy back higher? If not, why does it fail overall?
  B. Then why not identify the regime, hold through good regimes and use the indicator only
     in bad ones? Test it on every asset.

Everything uses the exact indicator (moneyline_ref: Wilder ATR(10) x 2 around hl2,
reset-on-flip) or, for crypto, the TradingView export's own state. GREEN = long.

----------------------------------------------------------------------------- data
(all gitignored; rebuild steps in HANDOFF section 3 and in load_* below)
  SPX_LONG  S&P 500 1962-01 .. 2026-10. ^GSPC daily OHLC 1962-2018-12-21
            (github.com/vijinho/sp500, Yahoo; real highs/lows from 1962), then SPY's
            split-adjusted OHLC (Johnbrick123/sp500-data) rescaled at the splice. That one
            close series drives the indicator, the regimes and the price return; dividends
            are added as a daily factor from github.com/SteelCerberus/us-market-data
            (Adjusted Close / Close; that pair is SPY itself from 1993), then SPY adj_close /
            close. Risk-free rate: SteelCerberus 3-month T-bill to 2025-12-19, then the TBILL
            table. 38 ^GSPC bars in 1962-1983 have no real high/low (O=H=L=C); kept as is.
  ETFs      SPY QQQ IWM DIA EFA EEM TLT IEF TIP LQD HYG GLD SLV VNQ and TSLA COIN HOOD:
            Johnbrick123 parquet (Yahoo, split-adjusted OHLC for the indicator, adj_close
            for total return).
  crypto    BTC ETH SOL BNB ZEC: data/tv_full TradingView exports (exact state,
            close-only; the still-forming 2026-08-24 row is dropped). Breadth: 40 large
            Binance USDT pairs incl. dead LUNA and FTT (data/crypto_binance_regime, from the
            Binance S3 archive), MATIC spliced into POL; 41 series, because altcoins.load_crypto
            splits FTT at a 311-day archive gap and LUNA into old LUNA and Terra 2.0.
  stocks    S&P 500 point-in-time members 1995-2026 incl. ~400 dead companies
            (data/universe_pit_all, screener.data.from_sp500_pit, total-return OHLC).
  macro     UNRATE (1948+), from github.com/cyby2000/fred-relay (a daily FRED mirror;
            FRED itself is blocked here). Current vintage, not real-time: see caveats.

----------------------------------------------------------------------------- execution
  Signal at a bar's close. Long while `want`; cash earns the T-bill rate while flat.
  US stocks/ETFs/SPX_LONG: trade at the NEXT session's close (lag 1), 0.03%/side.
  TV crypto: same-bar close at 0.15%/side (the repo's headline convention); next bar and
    the spot-ETF route (costs.etf_want, 0.02%) as sensitivities.
  Binance basket: same-bar close, 0.30%/side.
  Pre-tax: total return. After tax (illustrative 35% short / 20% long, as gate.py): each
    round trip taxed at 35% if held <= 365 days else 20%, netted yearly with carry-forward
    (the netting of strictness._settle); dividends taxed yearly at 20%, T-bill interest yearly at 35%;
    the final position is liquidated and taxed. Buy & hold: same engine, one trade.

----------------------------------------------------------------------------- strategies
  BH      always long
  IND     long while the daily indicator is GREEN
  REG     long while the regime is good (the regime classifier as its own timer)
  SWITCH  long while the regime is good OR the indicator is GREEN  <- the user's idea:
          buy & hold in good regimes, the indicator in bad ones

Regime classifiers ("bad" = use the indicator), all ex ante, computed at the same close as
the indicator. Fixed conventional parameters, chosen before any run:
  ma200    close < 200-bar simple moving average                   [PRIMARY]
  cross    50-bar SMA < 200-bar SMA
  wk       the weekly indicator is RED (last closed week)
  mom12    trailing 12-month total return < 0 (252 / 365 bars)
  dd       close >= 20% below its running high (crypto: 50%)
  vol      21-bar realised vol > its trailing 1-year median
  hmm      2-state Gaussian HMM on daily log returns, refit monthly on an expanding
           window, FILTERED probability of the high-variance state > 0.5
  unrate   US unemployment rate > its 12-month average, each month's value used from the
           first day of the month after its release month (conservative 1-month extra lag);
           US assets primary, crypto exploratory. This is the user's idea with a non-price
           regime signal (cf. "Growth-Trend Timing", Philosophical Economics 2016); the
           original GTT rule (cash only if unrate bad AND close < 200-SMA) is reported too.
  market variants (exploratory): single US ETFs/stocks also use SPX_LONG's ma200 / dd /
           hmm / oracle; the stock basket SPX_LONG's ma200 / dd / hmm / vol / oracle;
           single coins BTC's (TradingView) ma200 / dd / hmm; the coin basket Binance BTC's
           ma200 / dd / hmm / vol.
  oracle   EX-POST bull/bear phases (peak-to-trough >= 20%, crypto 50%; a phase turns when
           price moves that far from the running extreme). Uses the future: a ceiling, not
           a strategy.

Common evaluation window per asset: starts once every ex-ante classifier is defined
(300 bars for daily stocks, 400 for crypto; all strategies share it). Sensitivity grid (EXPLORATORY, never used to
choose): ma 100/150/250, dd 10/15/30% (crypto 30/40/60%), mom 6/9 months.

----------------------------------------------------------------------------- Part A
Exact identity: ln(IND) - ln(BH) = -sum over flat days of x_t - trading costs, where
x_t = ln(1 + asset return) - ln(1 + T-bill). Two decompositions:
  drift/timing  -sum_flat x = -(flat share) * sum_all x   [drift: being out of a rising
                                                            asset, no timing at all]
                              - (sum_flat x - flat share * sum_all x)   [timing skill]
  red spells    each flat spell from the exit fill (close P_x) to the re-entry fill (P_e),
                with P_min the lowest close inside it and A = ATR(14)/close at the signal:
                  SAVE            P_e below P_x after cash interest (spell helped)
                  FALSE BREAKDOWN a losing spell whose lowest close stayed within 1 x A of
                                  P_x: no follow-through, the market just went up
                  LATE ROUND TRIP a losing spell where price did fall more than 1 x A after
                                  the exit but rebounded above P_x before the re-entry:
                                  a real pullback, too shallow to pay for the indicator's lag
                drop = ln(P_x / P_min), rebound = ln(P_e / P_min), exit lag =
                ln(peak since entry / P_x), all on total-return closes; also in ATR units.
                A window that starts flat opens a 'leading' spell at its first bar.
Spells are grouped by the ex-post phase at the exit (oracle) and by calendar-year buy &
hold return.

----------------------------------------------------------------------------- hypotheses
Pre-registered 2026-10-14, before any regime or Part A result was computed. Known
beforehand: results_full.csv / results_stocks.csv "Daily OR Weekly" rows (= SWITCH with
the wk classifier, TV data 2010-2026): on SPX/NDX/IWM it beat the daily signal but
trailed buy & hold; on crypto it was mixed. Nothing else about regimes had been seen.

  H-A1 (the user's mechanism) In ex-post bull phases, FALSE BREAKDOWN spells account for
       more than half of the gross loss from losing spells. Judged on SPX_LONG, the pooled
       S&P 500 stock universe and the pooled Binance universe: CONFIRMED if > 50% in all
       three, REJECTED if < 50% in all three, otherwise MIXED. Per-asset shares reported.
       (Sensitivity thresholds 0.5 and 2 x ATR.)
  H-A2 (reported, no pass/fail) Where IND trails BH, the drift/timing split says whether
       the indicator times badly (negative skill) or times well but is out of a rising
       asset too long; the phase split says how much of the year is bull vs bear.

  Named assets for counting: SPX_LONG, SPY, QQQ, IWM, TSLA, BTC, ETH, SOL, BNB, ZEC
  (COIN, HOOD: exploratory, under 5 years after warm-up).
  H-B1 SWITCH(ma200) beats IND on pre-tax CAGR on >= 7 of the 10 named assets AND in
       both equal-weight baskets (S&P 500 members 1997-2026, Binance coins 2019-2026).
  H-B2 (the decision) SWITCH(ma200) after tax passes the repo's T2 rule against BH
       (after-tax CAGR >= BH, or >= BH - 2 pts with max drawdown >= 15 pts shallower) on
       SPX_LONG over 1963-2026 AND separately over 1963-1993 and 1994-2026.
  H-B3 (does the indicator add anything inside bad regimes?) SWITCH(ma200) pre-tax CAGR
       >= REG(ma200), the plain 200-day rule, on SPX_LONG and on >= 6 of the 10 named
       assets.
  H-B4 (robustness) H-B2 also passes for at least 4 of the 6 other price-based ex-ante
       classifiers (cross, wk, mom12, dd, vol, hmm) on SPX_LONG.
  H-B5 (macro regime) SWITCH(unrate) after tax passes the T2 rule against BH on SPX_LONG
       over 1963-2026 and in both halves.
  The oracle, the market-regime variants, the ETFs other than SPY/QQQ/IWM, COIN/HOOD and
  the sensitivity grid are exploratory and never change a verdict.

Engine checks run before the pre-registration commit (the hypotheses above were written
first): IND and BH on the TV crypto exports reproduce run_full.py within 0.05 CAGR pts;
the computed indicator agrees with TradingView's SPX export on 100% of 2010-2018 days
(real ^GSPC bars) and 98.6% after the SPY splice, IWM 100%, QQQ vs the NDX chart ~98%;
after-tax buy & hold equals the closed form; the spell sum equals the flat-day identity to
1e-15; the HMM recovers synthetic regimes 96% of the time. Disclosure: the validation
printed Part A output for ETH (TV) - bull-phase FALSE BREAKDOWN share 91.5%, median round
trip 4.4 ATR - and a BH/IND-only Binance basket smoke test for 2019-2022. ETH is not one of
the H-A1 judgment sets and nothing was changed after seeing them.

AUDIT CORRECTIONS (after the first run, commit b04aad9; two independent audits - a
from-scratch recomputation and an adversarial code review). No verdict changed.
  1. SPX_LONG used SteelCerberus' Close/Adjusted Close for regimes and returns, which is
     SPY (price, fee, bad prints such as 2000-01-06/07) from 1993, while the indicator ran
     on ^GSPC. Now one series (index close x dividend factor) drives everything.
  2. Baskets skipped each year's first session (formed at the first close). Now formed at
     the prior session's close.
  3. The market-regime cache keyed only by name, so the coin basket's BTC-market regimes
     reused TradingView BTC instead of Binance BTC. Now keyed by name and source.
  4. The still-forming last TradingView row is dropped (HANDOFF section 3).
  5. A window starting flat lost its first spell (the "1e-15 identity" above held for ETH
     but not for 13 of 23 assets). Now a leading spell is opened.
  6. After tax: shares sold to pay tax now realise their gain (taxed the following year);
     the T-bill rate for 2025-12-22..31 carries the last daily value.
  Also: the pooled S&P stock set for H-A1 now keeps only spells that start during S&P 500
  membership (it had included non-member years and ETFs such as SPY), spells are tabulated
  by calendar-year buy & hold return as promised, and the two explanatory tables
  (spells by 200-day regime, GTT after publication) are produced by main().

    python -m analysis_2026.regime_switch
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analysis_2026.moneyline_ref import moneyline, to_weekly, atr as atr_fn  # noqa: E402
from analysis_2026.costs import etf_want  # noqa: E402
from screener.strictness import TBILL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "analysis_2026" / "results_regime"
ST, LT = 0.35, 0.20
NAMED = ["SPX_LONG", "SPY", "QQQ", "IWM", "TSLA", "BTC", "ETH", "SOL", "BNB", "ZEC"]
ETFS = ["SPY", "QQQ", "IWM", "DIA", "EFA", "EEM", "TLT", "IEF", "TIP", "LQD", "HYG", "GLD", "SLV", "VNQ"]
YAHOO_STOCKS = ["TSLA", "COIN", "HOOD"]
TV_CRYPTO = ["BTC", "ETH", "SOL", "BNB", "ZEC"]
CLASSIFIERS = ["ma200", "cross", "wk", "mom12", "dd", "vol", "hmm", "unrate"]
PRICE_CLASSIFIERS = ["ma200", "cross", "wk", "mom12", "dd", "vol", "hmm"]


# ============================================================================ data

_RF_CACHE = {}


def rf_annual_pct(index: pd.DatetimeIndex) -> np.ndarray:
    """3-month T-bill, % per year: SteelCerberus daily series, then the repo's TBILL table."""
    if "rf" not in _RF_CACHE:
        m = pd.read_csv(DATA / "macro" / "us_market_data.csv", usecols=["Date", "Risk Free Rate"],
                        parse_dates=["Date"]).set_index("Date")["Risk Free Rate"]
        _RF_CACHE["rf"] = m[~m.index.duplicated()].sort_index()
    s = _RF_CACHE["rf"]
    out = s.reindex(index, method="ffill").to_numpy(dtype=float, copy=True)
    late = index > s.index[-1]
    out[late] = [s.iloc[-1] if d.year == s.index[-1].year else TBILL.get(d.year, 3.7) for d in index[late]]
    return np.nan_to_num(out, nan=3.0)


def rf_per_bar(index: pd.DatetimeIndex) -> np.ndarray:
    """Interest earned over each bar (from the previous bar's close), calendar-day accrual."""
    days = np.r_[0.0, np.diff(index.values).astype("timedelta64[D]").astype(float)]
    return rf_annual_pct(index) / 100.0 * days / 365.0


def _weekly_state(daily_ohlc: pd.DataFrame) -> np.ndarray:
    """Weekly indicator state of the last CLOSED week, on daily bars."""
    w = moneyline(to_weekly(daily_ohlc)).green
    return w.shift(1).reindex(daily_ohlc.index, method="ffill").fillna(False).astype(bool).to_numpy()


def frame_from_ohlc(ohlc: pd.DataFrame, px: pd.Series, tr: pd.Series, ppy: int) -> pd.DataFrame:
    """Columns: open/high/low/close (indicator input), px (price index), tr (total-return
    index), r (total return per bar), r_div (dividend part), rf, green, wk_green, atr_pct."""
    f = ohlc[["open", "high", "low", "close"]].astype(float).copy()
    f["px"] = px.reindex(f.index).astype(float)
    f["tr"] = tr.reindex(f.index).astype(float)
    f = f.dropna()
    f["r"] = f.tr.pct_change().fillna(0.0)
    r_px = f.px.pct_change().fillna(0.0)
    f["r_div"] = f.r - r_px
    f["rf"] = rf_per_bar(f.index)
    m = moneyline(f)
    f["green"] = m.green.to_numpy()
    f["valid"] = ~np.isnan(m.line.to_numpy())
    f["wk_green"] = _weekly_state(f)
    a = atr_fn(f.high.to_numpy(), f.low.to_numpy(), f.close.to_numpy(), 14)
    f["atr_pct"] = a / f.close.to_numpy()
    f.attrs["ppy"] = ppy
    return f


def load_spx_long() -> pd.DataFrame:
    g = pd.read_csv(DATA / "macro" / "gspc_1950_2018.csv", parse_dates=["Date"]).set_index("Date")
    g.columns = [c.lower() for c in g.columns]
    g = g.loc["1962-01-02":, ["open", "high", "low", "close"]]
    m = pd.read_csv(DATA / "macro" / "us_market_data.csv", parse_dates=["Date"]).set_index("Date")
    m = m[~m.index.duplicated()]
    spy = _yahoo_raw("SPY")
    splice = g.index[-1]
    k = g.close.iloc[-1] / spy.close.loc[splice]
    post = spy.loc[spy.index > splice]
    ohlc = pd.concat([g, post[["open", "high", "low", "close"]] * k])
    # One price series drives the indicator, the regimes and the returns: the index close
    # (SPY's close x k after the splice). Dividends enter as a per-day factor taken from the
    # SteelCerberus pair (Adjusted Close / Close; that pair is SPY itself from 1993) and from
    # SPY's adj_close / close after the splice.
    dm = (m["Adjusted Close"] / m["Adjusted Close"].shift(1)) / (m["Close"] / m["Close"].shift(1))
    dp = (spy.adj_close / spy.adj_close.shift(1)) / (spy.close / spy.close.shift(1))
    div = pd.concat([dm.reindex(g.index), dp.reindex(post.index)]).fillna(1.0)
    px = ohlc.close
    tr = px * div.cumprod()
    f = frame_from_ohlc(ohlc, px, tr, 252)
    f.attrs.update(name="SPX_LONG", kind="us", cost=0.0003, lag=1, theta=0.20, source="index")
    return f


_PARQ = {}


def _yahoo_raw(sym: str) -> pd.DataFrame:
    if "p" not in _PARQ:
        want = ETFS + YAHOO_STOCKS
        p = pd.read_parquet(DATA / "raw_pit" / "prices.parquet", filters=[("ticker", "in", want)])
        _PARQ["p"] = {t: g.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
                      for t, g in p.groupby("ticker")}
    d = _PARQ["p"][sym]
    d = d[(d.close > 0) & d[["open", "high", "low"]].notna().all(axis=1)]
    d.index = pd.DatetimeIndex(d.index).normalize()
    return d


def load_yahoo(sym: str) -> pd.DataFrame:
    d = _yahoo_raw(sym)
    f = frame_from_ohlc(d, d.close, d.adj_close, 252)
    f.attrs.update(name=sym, kind="us", cost=0.0003, lag=1, theta=0.20, source="yahoo")
    return f


def load_tv_crypto(sym: str) -> pd.DataFrame:
    """TradingView export: exact state, close only. ATR column is RMA(14). The last row
    (2026-08-24) was still forming when exported (HANDOFF section 3) and is dropped."""
    from analysis_2026.run_full import load, weekly_on_daily
    d = load(sym, "1D").iloc[:-1]
    f = pd.DataFrame(index=d.index)
    f["close"] = d.close.astype(float)
    f["px"] = f.close; f["tr"] = f.close
    f["r"] = f.tr.pct_change().fillna(0.0); f["r_div"] = 0.0
    f["rf"] = rf_per_bar(f.index)
    f["green"] = d.green.to_numpy(bool); f["valid"] = True
    f["wk_green"] = weekly_on_daily(sym, d.index).to_numpy(bool)
    f["atr_pct"] = (d.atr / d.close).to_numpy(float)
    f.attrs.update(name=sym, kind="crypto", cost=0.0015, lag=0, theta=0.50, ppy=365, source="tradingview")
    return f


def load_binance(folder=DATA / "crypto_binance_regime") -> dict:
    from analysis_2026.altcoins import load_crypto
    data = load_crypto(folder)
    if "MATIC" in data and "POL" in data:           # MATIC migrated 1:1 to POL in Sept 2024
        m, p = data.pop("MATIC"), data.pop("POL")
        data["MATIC"] = pd.concat([m, p[p.index > m.index[-1]]])
    out = {}
    for s, d in data.items():
        f = frame_from_ohlc(d, d.close, d.close, 365)
        f.attrs.update(name=s, kind="crypto", cost=0.003, lag=0, theta=0.50, source="binance")
        out[s] = f
    return out


def load_pit_universe(folder=DATA / "universe_pit_all", exclude=("STI",)):
    from screener.data import from_csv_folder
    members = pd.read_csv(folder / "members.csv", parse_dates=["start", "end"])
    raw = from_csv_folder(folder)
    raw.pop("MEMBERS", None)
    return {s: d for s, d in raw.items() if s not in exclude}, members


# ============================================================================ regimes

def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=n).mean().to_numpy()


def unrate_bad(index: pd.DatetimeIndex) -> np.ndarray:
    """Unemployment above its 12-month average, month M used from the first day of M+2."""
    u = pd.read_csv(DATA / "macro" / "UNRATE.csv", parse_dates=["date"]).set_index("date").value.astype(float)
    bad = (u > u.rolling(12).mean()).astype(float)
    bad[u.rolling(12).mean().isna()] = np.nan
    bad.index = bad.index + pd.offsets.MonthBegin(2)
    return bad.reindex(index, method="ffill").to_numpy(dtype=float)


@njit(cache=True)
def _hmm_em(x, mu, sg, A, pi, iters):
    n = len(x)
    alpha = np.zeros((n, 2)); beta = np.zeros((n, 2)); c = np.zeros(n); b = np.zeros((n, 2))
    for _ in range(iters):
        for t in range(n):
            for k in range(2):
                z = (x[t] - mu[k]) / sg[k]
                b[t, k] = np.exp(-0.5 * z * z) / (sg[k] * 2.5066282746310002) + 1e-300
        for k in range(2):
            alpha[0, k] = pi[k] * b[0, k]
        c[0] = alpha[0, 0] + alpha[0, 1]; alpha[0] /= c[0]
        for t in range(1, n):
            for k in range(2):
                alpha[t, k] = (alpha[t - 1, 0] * A[0, k] + alpha[t - 1, 1] * A[1, k]) * b[t, k]
            c[t] = alpha[t, 0] + alpha[t, 1]; alpha[t] /= c[t]
        beta[n - 1, 0] = 1.0; beta[n - 1, 1] = 1.0
        for t in range(n - 2, -1, -1):
            for k in range(2):
                beta[t, k] = (A[k, 0] * b[t + 1, 0] * beta[t + 1, 0] + A[k, 1] * b[t + 1, 1] * beta[t + 1, 1]) / c[t + 1]
        gam = alpha * beta
        xi = np.zeros((2, 2))
        for t in range(n - 1):
            for i in range(2):
                for j in range(2):
                    xi[i, j] += alpha[t, i] * A[i, j] * b[t + 1, j] * beta[t + 1, j] / c[t + 1]
        pi = gam[0] / gam[0].sum()
        for i in range(2):
            s = xi[i, 0] + xi[i, 1]
            for j in range(2):
                A[i, j] = xi[i, j] / s
        for k in range(2):
            w = gam[:, k]; sw = w.sum()
            mu[k] = (w * x).sum() / sw
            sg[k] = max(np.sqrt((w * (x - mu[k]) ** 2).sum() / sw), 1e-5)
    return mu, sg, A, pi


@njit(cache=True)
def _hmm_filter(x, MU, SG, AA, start):
    """Filtered P(state 1) with time-varying parameters (row t = parameters valid at t)."""
    n = len(x); p = np.full(n, np.nan); a0, a1 = 0.5, 0.5
    for t in range(start, n):
        pr0 = a0 * AA[t, 0, 0] + a1 * AA[t, 1, 0]
        pr1 = a0 * AA[t, 0, 1] + a1 * AA[t, 1, 1]
        z0 = (x[t] - MU[t, 0]) / SG[t, 0]; z1 = (x[t] - MU[t, 1]) / SG[t, 1]
        l0 = pr0 * np.exp(-0.5 * z0 * z0) / SG[t, 0] + 1e-300
        l1 = pr1 * np.exp(-0.5 * z1 * z1) / SG[t, 1] + 1e-300
        a0, a1 = l0 / (l0 + l1), l1 / (l0 + l1)
        p[t] = a1
    return p


def hmm_bad(index: pd.DatetimeIndex, r: np.ndarray, min_obs: int) -> np.ndarray:
    """Refit at each month start on all returns BEFORE that month (expanding window); the
    filter at day t uses only returns up to t. State 1 = the higher-variance state."""
    x = np.log1p(np.asarray(r, dtype=float))
    x[0] = 0.0
    n = len(x)
    MU = np.zeros((n, 2)); SG = np.ones((n, 2)); AA = np.zeros((n, 2, 2))
    month_start = np.r_[True, index.month[1:] != index.month[:-1]]
    starts = [i for i in np.where(month_start)[0] if i >= min_obs]
    if not starts:
        return np.full(n, np.nan)
    s0 = np.std(x[1:starts[0]])
    mu = np.array([np.mean(x[1:starts[0]]), np.mean(x[1:starts[0]])])
    sg = np.array([0.7 * s0, 1.6 * s0]); A = np.array([[0.98, 0.02], [0.05, 0.95]]); pi = np.array([0.5, 0.5])
    first = True
    for k, i in enumerate(starts):
        mu, sg, A, pi = _hmm_em(x[1:i], mu.copy(), sg.copy(), A.copy(), pi.copy(), 60 if first else 8)
        first = False
        if sg[0] > sg[1]:                                   # keep state 1 = high variance
            mu, sg, A, pi = mu[::-1].copy(), sg[::-1].copy(), A[::-1, ::-1].copy(), pi[::-1].copy()
        j = starts[k + 1] if k + 1 < len(starts) else n
        MU[i:j] = mu; SG[i:j] = sg; AA[i:j] = A
    p = _hmm_filter(x, MU, SG, AA, starts[0])
    out = (p > 0.5).astype(float)
    out[np.isnan(p)] = np.nan
    return out


def oracle_bear(px: np.ndarray, theta: float) -> np.ndarray:
    """EX-POST phases: bear from a peak to the following trough, where a phase turns once
    price moves `theta` from the running extreme (uses the future)."""
    c = np.asarray(px, dtype=float); n = len(c)
    bear = np.zeros(n, dtype=bool)
    state, ext = "bull", 0
    turns = []                                   # (index, 'peak'|'trough')
    for i in range(1, n):
        if state == "bull":
            if c[i] > c[ext]:
                ext = i
            elif c[i] <= c[ext] * (1 - theta):
                turns.append((ext, "peak")); state, ext = "bear", i
        else:
            if c[i] < c[ext]:
                ext = i
            elif c[i] >= c[ext] * (1 + theta):
                turns.append((ext, "trough")); state, ext = "bull", i
    if state == "bear":
        turns.append((ext, "trough"))            # the open bear ends at its lowest point so far
    for (a, ka), (b, kb) in zip(turns, turns[1:]):
        if ka == "peak" and kb == "trough":
            bear[a + 1:b + 1] = True
    return bear


_MKT = {}


def regime_bad(f: pd.DataFrame, kind: str, market: pd.DataFrame | None = None) -> np.ndarray:
    """1.0 = bad regime (use the indicator), 0.0 = good (hold), NaN = undefined."""
    if kind.endswith("_mkt"):
        key = (market.attrs["name"], market.attrs.get("source"), kind)
        if key not in _MKT:
            _MKT[key] = pd.Series(regime_bad(market, kind[:-4]), index=market.index)
        return _MKT[key].reindex(f.index, method="ffill").to_numpy(dtype=float)
    ppy = f.attrs["ppy"]; px = f.px.to_numpy(float); tr = f.tr.to_numpy(float)
    theta = f.attrs["theta"]

    def fl(cond, defined):
        o = np.array(cond, dtype=float); o[~np.asarray(defined, dtype=bool)] = np.nan; return o
    if kind.startswith("ma"):
        m = sma(px, int(kind[2:])); return fl(px < m, ~np.isnan(m))
    if kind == "cross":
        a, b = sma(px, 50), sma(px, 200); return fl(a < b, ~np.isnan(b))
    if kind == "wk":
        return (~f.wk_green.to_numpy(bool)).astype(float)
    if kind.startswith("mom"):
        months = int(kind[3:]); L = int(round(ppy * months / 12))
        prev = np.r_[np.full(L, np.nan), tr[:-L]]; return fl(tr / prev - 1 < 0, ~np.isnan(prev))
    if kind.startswith("dd"):
        th = theta if kind == "dd" else int(kind[2:]) / 100
        return (px <= (1 - th) * np.maximum.accumulate(px)).astype(float)
    if kind == "vol":
        lr = pd.Series(np.log(tr)).diff()
        rv = lr.rolling(21, min_periods=21).std()
        med = rv.rolling(ppy, min_periods=ppy).median()
        return fl((rv > med).to_numpy(), med.notna().to_numpy())
    if kind == "hmm":
        return hmm_bad(f.index, f.r.to_numpy(float), ppy)
    if kind == "unrate":
        return unrate_bad(f.index)
    if kind == "oracle":
        return oracle_bear(px, theta).astype(float)
    if kind == "gtt":          # original Growth-Trend Timing regime: unrate bad AND below the 200-SMA
        u, m = unrate_bad(f.index), regime_bad(f, "ma200")
        o = ((u == 1) & (m == 1)).astype(float); o[np.isnan(u) | np.isnan(m)] = np.nan; return o
    raise ValueError(kind)


def eval_start(f: pd.DataFrame) -> int:
    """First bar where every ex-ante classifier is defined (and the indicator has warmed up)."""
    need = 400 if f.attrs["kind"] == "crypto" else 300
    valid = np.where(f.valid.to_numpy(bool))[0]
    return max(need, int(valid[0]) + 100 if len(valid) else need)


# ============================================================================ engines

def lagged(want: np.ndarray, lag: int) -> np.ndarray:
    w = np.asarray(want, dtype=bool)
    return w if lag == 0 else np.r_[np.zeros(lag, dtype=bool), w[:-lag]]


def position(f: pd.DataFrame, want: np.ndarray, route: str = "primary") -> np.ndarray:
    """Position held from each close to the next. route: 'primary' (asset's own lag),
    'next' (lag 1), 'same' (lag 0), 'etf' (crypto signal via a spot ETF, next NYSE session)."""
    if route == "etf":
        return etf_want(f.index, np.asarray(want, dtype=bool), 1)
    lag = {"primary": f.attrs["lag"], "next": 1, "same": 0}[route]
    return lagged(want, lag)


def pretax(f: pd.DataFrame, pos: np.ndarray, cost: float, i0: int, i1: int) -> np.ndarray:
    """Equity path over bars i0..i1 (1.0 before the first trade). Buys at close i0 if in
    position, liquidates at close i1."""
    p = np.asarray(pos[i0:i1 + 1], dtype=float)
    r = f.r.to_numpy(float)[i0:i1 + 1]; rf = f.rf.to_numpy(float)[i0:i1 + 1]
    g = np.ones(len(p))
    g[1:] = 1 + np.where(p[:-1] > 0, r[1:], rf[1:])
    trade = np.abs(np.diff(np.r_[0.0, p]))
    g *= (1 - cost * trade)
    eq = np.cumprod(g)
    eq[-1] *= (1 - cost * p[-1])
    return eq


@njit(cache=True)
def _aftertax(r_px, r_div, rf, pos, year, day, cost, st, lt):
    n = len(pos)
    cash = 1.0; val = 0.0; basis = 0.0; entry_day = 0
    gst = 0.0; glt = 0.0; div_inc = 0.0; int_inc = 0.0; c_st = 0.0; c_lt = 0.0
    pend_st = 0.0; pend_lt = 0.0
    if pos[0]:
        val = cash * (1 - cost); basis = cash; cash = 0.0; entry_day = day[0]
    for t in range(1, n):
        if pos[t - 1]:
            d = val * r_div[t]; div_inc += d; basis += d
            val *= (1 + r_px[t] + r_div[t])
        else:
            i = cash * rf[t]; int_inc += i; cash += i
        if pos[t] and not pos[t - 1]:
            val = cash * (1 - cost); basis = cash; cash = 0.0; entry_day = day[t]
        elif pos[t - 1] and not pos[t]:
            proceeds = val * (1 - cost); g = proceeds - basis
            if day[t] - entry_day > 365:
                glt += g
            else:
                gst += g
            cash = proceeds; val = 0.0; basis = 0.0
        last = t == n - 1
        if last or year[t + 1] != year[t]:
            if last and pos[t]:
                proceeds = val * (1 - cost); g = proceeds - basis
                if day[t] - entry_day > 365:
                    glt += g
                else:
                    gst += g
                cash += proceeds; val = 0.0; basis = 0.0
            nst = gst + c_st; nlt = glt + c_lt
            if nst < 0 < nlt:
                nlt += nst; nst = 0.0
            elif nlt < 0 < nst:
                nst += nlt; nlt = 0.0
            tax = st * max(nst, 0.0) + lt * max(nlt, 0.0) + lt * div_inc + st * int_inc
            c_st = min(nst, 0.0); c_lt = min(nlt, 0.0)
            pend_st = 0.0; pend_lt = 0.0
            if tax <= cash:
                cash -= tax
            else:
                rest = tax - cash; cash = 0.0
                if val > 0:
                    sold = min(rest, val)
                    g_sold = sold * (1 - basis / val)        # gain realised by selling to pay tax
                    if day[t] - entry_day > 365:
                        pend_lt = g_sold
                    else:
                        pend_st = g_sold
                    basis *= (val - sold) / val
                    val -= sold
            gst = pend_st; glt = pend_lt; div_inc = 0.0; int_inc = 0.0
    return cash + val


def aftertax(f: pd.DataFrame, pos: np.ndarray, cost: float, i0: int, i1: int) -> float:
    sl = slice(i0, i1 + 1)
    r = f.r.to_numpy(float)[sl]; rd = f.r_div.to_numpy(float)[sl]
    return float(_aftertax(r - rd, rd, f.rf.to_numpy(float)[sl], np.asarray(pos[sl], dtype=np.bool_),
                           f.index.year.to_numpy()[sl].astype(np.int64),
                           (f.index.to_numpy()[sl].astype("datetime64[D]").astype(np.int64)), cost, ST, LT))


def years_of(f, i0, i1):
    return (f.index[i1] - f.index[i0]).days / 365.25


def cagr(mult, yrs):
    return (mult ** (1 / yrs) - 1) * 100 if mult > 0 and yrs > 0 else -100.0


def maxdd(eq):
    eq = np.asarray(eq, dtype=float)
    return float((eq / np.maximum.accumulate(eq) - 1).min() * 100)


def stats(f, pos, i0, i1, cost, tax=True):
    eq = pretax(f, pos, cost, i0, i1); yrs = years_of(f, i0, i1)
    p = np.asarray(pos[i0:i1 + 1], dtype=bool)
    out = {"cagr": cagr(eq[-1], yrs), "maxdd": maxdd(eq), "exposure": p.mean() * 100,
           "trades_yr": int((p[1:] & ~p[:-1]).sum() + p[0]) / yrs}
    lr = np.diff(np.log(eq))
    out["sharpe"] = float(np.mean(lr) / np.std(lr) * np.sqrt(f.attrs["ppy"])) if np.std(lr) > 0 else np.nan
    if tax:
        out["cagr_tax"] = cagr(aftertax(f, pos, cost, i0, i1), yrs)
    return out


def t2(sig_c, sig_dd, bh_c, bh_dd):
    return bool(sig_c >= bh_c or (sig_c >= bh_c - 2 and sig_dd >= bh_dd + 15))


# ============================================================================ Part A

def spells(f: pd.DataFrame, pos: np.ndarray, i0: int, i1: int, bear: np.ndarray, lag: int) -> pd.DataFrame:
    """Every flat spell of the strategy inside [i0, i1]: exit fill at close x (pos[x]=0,
    pos[x-1]=1), re-entry fill at close e (pos[e]=1) or the window end. A window that starts
    flat opens a 'leading' spell at i0, so the spells cover every flat day."""
    p = np.asarray(pos, dtype=bool); tr = f.tr.to_numpy(float); rf = f.rf.to_numpy(float)
    atrp = f.atr_pct.to_numpy(float); idx = f.index
    ybh = year_buckets(f, i0, i1).to_dict()
    rows = []
    t = i0; entry = None
    while t <= i1:
        if not p[t] and (t == i0 or p[t - 1]):          # exit at close t (or the window starts flat)
            x = t; e = x + 1; leading = t == i0
            while e <= i1 and not p[e]:
                e += 1
            closed = e <= i1
            e_ = min(e, i1)
            seg = slice(x, e_ + 1)
            pmin = tr[seg].min()
            cash = np.log1p(rf[x + 1:e_ + 1]).sum()
            contrib = cash - np.log(tr[e_] / tr[x])
            peak = tr[entry:x + 1].max() if entry is not None else tr[x]
            a = atrp[max(x - lag, 0)]
            drop = np.log(tr[x] / pmin); reb = np.log(tr[e_] / pmin)
            if contrib > 0:
                cls = "SAVE"
            elif drop <= a:
                cls = "FALSE BREAKDOWN"
            else:
                cls = "LATE ROUND TRIP"
            rows.append({"exit": idx[x], "reentry": idx[e_] if closed else pd.NaT, "closed": closed,
                         "days": (idx[e_] - idx[x]).days, "contrib": contrib, "drop": drop, "rebound": reb,
                         "exit_lag": np.log(peak / tr[x]), "atr_pct": a, "class": cls,
                         "drop_atr": drop / a if a > 0 else np.nan, "rebound_atr": reb / a if a > 0 else np.nan,
                         "exit_lag_atr": np.log(peak / tr[x]) / a if a > 0 else np.nan,
                         "phase": "bear" if bear[x] else "bull", "leading": leading,
                         "year_bh_ret_%": ybh.get(idx[x].year, np.nan),
                         "fb_half": contrib <= 0 and drop <= 0.5 * a, "fb_two": contrib <= 0 and drop <= 2 * a})
            t = e
            continue
        if p[t] and (t == i0 or not p[t - 1]):
            entry = t
        t += 1
    return pd.DataFrame(rows)


YEAR_BUCKETS = [-np.inf, -60, -30, 0, 30, 100, np.inf]


def year_bucket_table(sp: pd.DataFrame, years: float) -> pd.DataFrame:
    """Spell P&L grouped by the calendar-year buy & hold return of the exit year."""
    b = pd.cut(sp["year_bh_ret_%"], YEAR_BUCKETS)
    g = sp.groupby(b, observed=False)
    loss = sp.contrib.where(sp.contrib <= 0, 0.0); fbl = sp.contrib.where(sp["class"] == "FALSE BREAKDOWN", 0.0)
    return pd.DataFrame({"spells": g.size(), "net_log_pts": g.contrib.sum() * 100,
                         "loss_log_pts": loss.groupby(b, observed=False).sum() * 100,
                         "fb_share_of_loss_%": fbl.groupby(b, observed=False).sum() / loss.groupby(b, observed=False).sum() * 100})


def year_buckets(f, i0, i1):
    s = f.tr.iloc[i0:i1 + 1]
    yr = s.groupby(s.index.year).agg(["first", "last"])
    # calendar-year buy & hold return, using the prior year's last close where available
    prev_last = f.tr.groupby(f.index.year).last().shift(1)
    ret = (yr["last"] / prev_last.reindex(yr.index).fillna(yr["first"]) - 1) * 100
    return ret


def part_a_asset(f: pd.DataFrame, route="primary") -> tuple[dict, pd.DataFrame]:
    i0, i1 = eval_start(f), len(f) - 1
    cost = f.attrs["cost"]; lag = f.attrs["lag"] if route == "primary" else (0 if route == "same" else 1)
    green = f.green.to_numpy(bool)
    pos = position(f, green, route); posb = np.ones(len(f), dtype=bool)
    eq_i = pretax(f, pos, cost, i0, i1); eq_b = pretax(f, posb, cost, i0, i1)
    yrs = years_of(f, i0, i1)
    bear = oracle_bear(f.px.to_numpy(float), f.attrs["theta"])
    r = f.r.to_numpy(float); rf = f.rf.to_numpy(float)
    x = np.log1p(r) - np.log1p(rf)
    held = pos[i0:i1].astype(bool)                       # position over bar t -> t+1
    xs = x[i0 + 1:i1 + 1]
    flat = ~held
    sh = flat.mean()
    drift = -sh * xs.sum() / yrs * 100
    timing = -(xs[flat].sum() - sh * xs.sum()) / yrs * 100
    total = (np.log(eq_i[-1]) - np.log(eq_b[-1])) / yrs * 100
    costs = total - drift - timing
    bear_w = bear[i0 + 1:i1 + 1]
    ph = {}
    for name, m in (("bull", ~bear_w), ("bear", bear_w)):
        yrs_p = m.sum() / len(m) * yrs
        ph[f"{name}_share_%"] = m.mean() * 100
        ph[f"{name}_rel_pts_per_phase_yr"] = (-xs[m & flat].sum()) / yrs_p * 100 if yrs_p > 0 else np.nan
        ph[f"{name}_rel_pts_of_total_per_yr"] = (-xs[m & flat].sum()) / yrs * 100
    sp = spells(f, pos, i0, i1, bear, lag)
    sp.insert(0, "asset", f.attrs["name"])
    res = {"asset": f.attrs["name"], "start": f.index[i0].date(), "end": f.index[i1].date(), "years": yrs,
           "ind_cagr": cagr(eq_i[-1], yrs), "bh_cagr": cagr(eq_b[-1], yrs),
           "ind_dd": maxdd(eq_i), "bh_dd": maxdd(eq_b), "exposure_%": (1 - sh) * 100,
           "excess_log_pts": total, "drift_pts": drift, "timing_pts": timing, "cost_pts": costs, **ph}
    res.update(spell_summary(sp))
    return res, sp


def spell_summary(sp: pd.DataFrame, prefix="") -> dict:
    out = {}
    if sp.empty:
        return out
    for ph in ("bull", "bear"):
        s = sp[sp.phase == ph]
        loss = s[s.contrib <= 0]
        gl = -loss.contrib.sum()
        out[f"{prefix}{ph}_spells"] = len(s)
        out[f"{prefix}{ph}_save_sum"] = s[s.contrib > 0].contrib.sum() * 100
        out[f"{prefix}{ph}_loss_sum"] = -gl * 100
        out[f"{prefix}{ph}_fb_share_%"] = (-loss[loss["class"] == "FALSE BREAKDOWN"].contrib.sum() / gl * 100) if gl > 0 else np.nan
        out[f"{prefix}{ph}_fb_share_half_%"] = (-loss[loss.fb_half].contrib.sum() / gl * 100) if gl > 0 else np.nan
        out[f"{prefix}{ph}_fb_share_two_%"] = (-loss[loss.fb_two].contrib.sum() / gl * 100) if gl > 0 else np.nan
        out[f"{prefix}{ph}_fb_count_%"] = (loss["class"] == "FALSE BREAKDOWN").mean() * 100 if len(loss) else np.nan
        out[f"{prefix}{ph}_median_roundtrip_atr"] = float(np.nanmedian(s.exit_lag_atr + s.rebound_atr)) if len(s) else np.nan
    return out


# ============================================================================ Part B

def strategies(f: pd.DataFrame, bad: np.ndarray) -> dict:
    g = f.green.to_numpy(bool)
    good = ~(np.nan_to_num(bad, nan=1.0) > 0.5)          # undefined -> treat as bad (indicator)
    return {"BH": np.ones(len(f), dtype=bool), "IND": g, "REG": good, "SWITCH": good | g}


def part_b_asset(f: pd.DataFrame, kinds, market=None, route="primary", windows=None, tax=True) -> pd.DataFrame:
    cost = f.attrs["cost"] if route != "etf" else 0.0002
    i0d, i1d = eval_start(f), len(f) - 1
    rows = []
    for kind in kinds:
        bad = regime_bad(f, kind, market)
        strat = strategies(f, bad)
        for wname, (a, b) in (windows or {"full": (None, None)}).items():
            i0 = i0d if a is None else max(i0d, int(np.searchsorted(f.index, pd.Timestamp(a))))
            i1 = i1d if b is None else int(np.searchsorted(f.index, pd.Timestamp(b), side="right")) - 1
            if i1 - i0 < 250:
                continue
            res = {}
            for s, w in strat.items():
                res[s] = stats(f, position(f, w, route), i0, i1, cost, tax)
            # exact attribution (log pts/yr): SWITCH vs IND gains the excess return on days the
            # indicator is flat in a good regime; SWITCH vs BH loses it on flat days in a bad one
            yrs = years_of(f, i0, i1)
            x = (np.log1p(f.r.to_numpy(float)) - np.log1p(f.rf.to_numpy(float)))[i0 + 1:i1 + 1]
            pi = position(f, strat["IND"], route)[i0:i1].astype(bool)
            ps = position(f, strat["SWITCH"], route)[i0:i1].astype(bool)
            badw = np.nan_to_num(bad, nan=1.0)[i0:i1] > 0.5
            row = {"asset": f.attrs["name"], "route": route, "classifier": kind, "window": wname,
                   "start": f.index[i0].date(), "end": f.index[i1].date(), "years": yrs,
                   "bad_share_%": float(badw.mean() * 100),
                   "switch_vs_ind_attrib": x[ps & ~pi].sum() / yrs * 100,
                   "switch_vs_bh_attrib": -x[~ps].sum() / yrs * 100}
            for s in strat:
                for k, v in res[s].items():
                    row[f"{s}_{k}"] = v
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- baskets

def basket(frames: dict, members_fn, years, kinds, market, cal: pd.DatetimeIndex, cost: float, lag: int,
           need: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Equal-weight basket formed at each year's first close from members_fn(year, first_day),
    each slot running a strategy on its own asset, liquidated at the year's last close. A
    slot whose asset stops trading sits in cash. Returns (yearly returns, per-slot rows)."""
    keys = [("BH", None), ("IND", None)] + [(s, k) for k in kinds for s in ("REG", "SWITCH")]
    rf_cal = rf_per_bar(cal)
    # per-asset daily growth on the calendar, per strategy
    acc = {k: {} for k in keys}
    slot_rows = []
    year_days = {}
    for y in years:                       # formed at the previous session's close (prior year end)
        d = np.where(cal.year == y)[0]
        if len(d):
            year_days[y] = np.r_[d[0] - 1, d] if d[0] > 0 else d
    mem = {y: set(members_fn(y, cal[year_days[y][0]])) for y in year_days}
    wanted = set().union(*mem.values())
    for sym in sorted(wanted):
        f = frames.get(sym)
        if f is None:
            continue
        bads = {k: regime_bad(f, k, market) for k in kinds}
        on_cal = cal[(cal >= f.index[0]) & (cal <= f.index[-1])]
        r = f.r.reindex(on_cal).fillna(0.0).to_numpy(float)
        g_ind = f.green.reindex(on_cal).ffill().fillna(False).to_numpy(bool)
        series = {}
        for (s, k) in keys:
            if s == "BH":
                w = np.ones(len(on_cal), dtype=bool)
            elif s == "IND":
                w = g_ind
            else:
                b = pd.Series(bads[k], index=f.index).reindex(on_cal).ffill().to_numpy(dtype=float)
                good = ~(np.nan_to_num(b, nan=1.0) > 0.5)
                w = good if s == "REG" else (good | g_ind)
            series[(s, k)] = lagged(w, lag)
        pos_in_cal = np.searchsorted(cal, on_cal)
        first_bar = f.index[0]
        for y in year_days:
            if sym not in mem.get(y, ()):
                continue
            days = year_days[y]
            d0 = cal[days[0]]
            hist = int((f.index < d0).sum())
            if hist < need or d0 < first_bar or d0 > f.index[-1]:
                continue
            # bars of this asset inside the year
            loc = np.where((on_cal >= d0) & (on_cal <= cal[days[-1]]))[0]
            if len(loc) == 0:
                continue
            for key in keys:
                p = series[key]
                gi = np.ones(len(days))
                # map asset bars to calendar positions within the year
                cpos = pos_in_cal[loc] - days[0]
                pl = p[loc]
                grow = np.ones(len(loc))
                grow[1:] = 1 + np.where(pl[:-1], r[loc][1:], rf_cal[days[0] + cpos[1:]])
                tr = np.abs(np.diff(np.r_[0.0, pl.astype(float)]))
                grow *= (1 - cost * tr)
                gi[cpos] = grow
                # days after the asset's last bar inside the year: cash (sold at the last close)
                end_c = cpos[-1]
                if end_c < len(days) - 1:
                    gi[end_c] *= (1 - cost * pl[-1])
                    gi[end_c + 1:] = 1 + rf_cal[days[end_c + 1:]]
                    final_cost = 0.0
                else:
                    final_cost = cost * pl[-1]
                path = np.cumprod(gi)
                path[-1] *= (1 - final_cost)
                a = acc[key].setdefault(y, [np.zeros(len(days)), 0])
                a[0] += path; a[1] += 1
                slot_rows.append((y, sym, key[0], key[1], path[-1] - 1))
    rows = []
    for key in keys:
        for y in years:
            if y in acc[key] and acc[key][y][1]:
                s, n = acc[key][y]
                rows.append({"strategy": key[0], "classifier": key[1] or "-", "year": y, "n": n,
                             "ret": s[-1] / n - 1, "path": s / n})
    return pd.DataFrame(rows), pd.DataFrame(slot_rows, columns=["year", "asset", "strategy", "classifier", "ret"])


def chain(yearly: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (s, k), g in yearly.groupby(["strategy", "classifier"], sort=False):
        g = g.sort_values("year")
        # each year's path starts at its formation close (the prior session): drop that point
        path = np.concatenate([p[1:] * np.prod(1 + g.ret.to_numpy()[:i]) for i, p in enumerate(g.path)])
        yrs = len(path) / (252 if len(path) / len(g) < 300 else 365)
        mult = float(np.prod(1 + g.ret))
        out.append({"strategy": s, "classifier": k, "years": len(g), "cagr": cagr(mult, yrs),
                    "maxdd": maxdd(np.r_[1.0, path]), "avg_n": g.n.mean(),
                    "years_beating_BH": None})
    res = pd.DataFrame(out)
    bh = yearly[yearly.strategy == "BH"].set_index("year").ret
    for i, r in res.iterrows():
        g = yearly[(yearly.strategy == r.strategy) & (yearly.classifier == r.classifier)].set_index("year").ret
        res.at[i, "years_beating_BH"] = f"{int((g > bh.reindex(g.index)).sum())}/{len(g)}"
    return res


def in_membership(sp: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """Keep spells whose exit falls inside one of the symbol's S&P 500 membership spells."""
    m = members.assign(symbol=members.symbol.str.upper(), end=members.end.fillna(pd.Timestamp("2100-01-01")))
    j = sp.reset_index().merge(m, left_on="asset", right_on="symbol", how="inner")
    ex = pd.to_datetime(j["exit"])
    keep = j.loc[(ex >= j.start) & (ex <= j.end), "index"].unique()
    return sp.loc[np.sort(keep)].reset_index(drop=True)


def spells_by_regime(frames: dict, spd: pd.DataFrame) -> pd.DataFrame:
    """IND red spells split by whether price was above or below its 200-day average at the
    exit (explanatory: the switch acts day by day, not spell by spell)."""
    rows = []
    for name in ["SPX_LONG", "SPY", "QQQ", "IWM", "TSLA", "BTC", "ETH", "SOL", "BNB", "ZEC"]:
        f = frames[name]
        bad = pd.Series(regime_bad(f, "ma200"), index=f.index)
        s = spd[spd.asset == name].copy()
        s["bad_at_exit"] = bad.reindex(pd.to_datetime(s.exit)).to_numpy() > 0.5
        yrs = years_of(f, eval_start(f), len(f) - 1)
        for reg, g in s.groupby("bad_at_exit"):
            rows.append({"asset": name, "regime_at_exit": "below 200d" if reg else "above 200d", "spells": len(g),
                         "net_pts_per_yr": g.contrib.sum() / yrs * 100,
                         "saves_pts_per_yr": g[g.contrib > 0].contrib.sum() / yrs * 100,
                         "losses_pts_per_yr": g[g.contrib <= 0].contrib.sum() / yrs * 100,
                         "biggest_save_%": (np.exp(g.contrib.max()) - 1) * 100, "share_saves_%": (g.contrib > 0).mean() * 100})
    return pd.DataFrame(rows)


# ============================================================================ main

def main():
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 60)
    OUT.mkdir(exist_ok=True)
    log = open(OUT / "summary.txt", "w")

    def say(*a):
        s = " ".join(str(x) for x in a); print(s); log.write(s + "\n"); log.flush()
    fmt = lambda x: f"{x:,.2f}"  # noqa: E731

    spx = load_spx_long()
    frames = {"SPX_LONG": spx}
    for s in ETFS + YAHOO_STOCKS:
        frames[s] = load_yahoo(s)
    for s in TV_CRYPTO:
        frames[s] = load_tv_crypto(s)
    btc_bin = load_binance()

    # ------------------------------------------------------------ Part A
    say("=" * 100); say("PART A - why the indicator trails buy & hold (IND, primary timing, full window)"); say("=" * 100)
    rows, allsp = [], []
    for name, f in frames.items():
        r_, sp = part_a_asset(f)
        rows.append(r_); allsp.append(sp)
    pa = pd.DataFrame(rows); spd = pd.concat(allsp, ignore_index=True)
    pa.to_csv(OUT / "partA_assets.csv", index=False); spd.to_csv(OUT / "partA_spells.csv", index=False)
    cols = ["asset", "start", "years", "ind_cagr", "bh_cagr", "ind_dd", "bh_dd", "exposure_%", "excess_log_pts",
            "drift_pts", "timing_pts", "cost_pts", "bull_share_%", "bull_rel_pts_of_total_per_yr",
            "bear_rel_pts_of_total_per_yr", "bull_rel_pts_per_phase_yr", "bear_rel_pts_per_phase_yr"]
    say(pa[cols].to_string(index=False, float_format=fmt))
    cols2 = ["asset", "bull_spells", "bull_save_sum", "bull_loss_sum", "bull_fb_share_%", "bull_fb_share_half_%",
             "bull_fb_share_two_%", "bull_fb_count_%", "bull_median_roundtrip_atr", "bear_spells", "bear_save_sum",
             "bear_loss_sum", "bear_fb_share_%", "bear_median_roundtrip_atr"]
    say("\nRed spells by ex-post phase (sums in log pts, whole window):")
    say(pa[cols2].to_string(index=False, float_format=fmt))

    # pooled universes for H-A1 (stocks / crypto): spells from every asset's full window
    stocks, members = load_pit_universe()
    sframes = {}
    for s, d in stocks.items():
        if len(d) < 300:
            continue
        f = frame_from_ohlc(d, d.close, d.close, 252)
        f.attrs.update(name=s, kind="us", cost=0.0003, lag=1, theta=0.20, source="pit")
        sframes[s] = f
    pooled = {}
    for label, src, tag in (("S&P 500 stocks", sframes, "stocks"), ("Binance coins", btc_bin, "crypto")):
        sps = []
        for s, f in src.items():
            if len(f) - eval_start(f) < 250:
                continue
            _, sp = part_a_asset(f)
            sps.append(sp)
        sp = pd.concat(sps, ignore_index=True)
        if tag == "stocks":               # S&P 500 members only, spells that start during membership
            sp = in_membership(sp, members)
        pooled[label] = sp
        sp.to_csv(OUT / f"partA_spells_{tag}.csv", index=False)
    say("\nH-A1 pooled: share of bull-phase gross loss from FALSE BREAKDOWN spells (1 x ATR; 0.5 / 2 x ATR)")
    hrows = []
    for label, sp in [("SPX_LONG", spd[spd.asset == "SPX_LONG"])] + list(pooled.items()):
        d = spell_summary(sp)
        hrows.append({"set": label, "spells": len(sp), "bull_fb_share_%": d.get("bull_fb_share_%"),
                      "half_atr_%": d.get("bull_fb_share_half_%"), "two_atr_%": d.get("bull_fb_share_two_%"),
                      "bull_loss_sum": d.get("bull_loss_sum"), "bull_save_sum": d.get("bull_save_sum"),
                      "bear_loss_sum": d.get("bear_loss_sum"), "bear_save_sum": d.get("bear_save_sum"),
                      "bull_median_roundtrip_atr": d.get("bull_median_roundtrip_atr")})
    ha = pd.DataFrame(hrows); ha.to_csv(OUT / "partA_H1.csv", index=False)
    say(ha.to_string(index=False, float_format=fmt))
    share = ha["bull_fb_share_%"].to_numpy()
    verdict = "CONFIRMED" if (share > 50).all() else ("REJECTED" if (share < 50).all() else "MIXED")
    say(f"H-A1: {verdict}")
    say("\nSpell P&L by the calendar-year buy & hold return of the exit year (log pts, whole window):")
    for label, sp in [("SPX_LONG", spd[spd.asset == "SPX_LONG"])] + list(pooled.items()):
        say(f"--- {label}"); t = year_bucket_table(sp, 1.0); t.to_csv(OUT / f"partA_yearbuckets_{label.split()[0]}.csv")
        say(t.to_string(float_format=fmt))
    say("\nIND red spells split by the 200-day regime at the exit (pts/yr):")
    sr = spells_by_regime(frames, spd)
    sr.to_csv(OUT / "partA_spells_by_ma200_regime.csv", index=False)
    say(sr.to_string(index=False, float_format=fmt))

    # ------------------------------------------------------------ Part B, single assets
    say("\n" + "=" * 100); say("PART B - regime switch on single assets"); say("=" * 100)
    kinds_us = CLASSIFIERS + ["gtt", "oracle"]
    kinds_cr = PRICE_CLASSIFIERS + ["unrate", "oracle"]
    btc_tv = frames["BTC"]
    pb = []
    for name, f in frames.items():
        kinds = kinds_us if f.attrs["kind"] == "us" else kinds_cr
        pb.append(part_b_asset(f, kinds))
        if f.attrs["kind"] == "crypto":
            pb.append(part_b_asset(f, ["ma200", "dd", "oracle"], route="next"))
            pb.append(part_b_asset(f, ["ma200", "dd", "oracle"], route="etf"))
            if name != "BTC":
                pb.append(part_b_asset(f, ["ma200_mkt", "dd_mkt", "hmm_mkt"], market=btc_tv))
        if f.attrs["kind"] == "us" and name != "SPX_LONG":
            pb.append(part_b_asset(f, ["ma200_mkt", "dd_mkt", "hmm_mkt", "oracle_mkt"], market=spx))
    pb = pd.concat(pb, ignore_index=True)
    pb.to_csv(OUT / "partB_assets.csv", index=False)
    gp = part_b_asset(spx, ["gtt", "ma200", "unrate"], windows={"2016-07+": ("2016-07-01", None)})
    gp.to_csv(OUT / "gtt_post_publication.csv", index=False)       # GTT was published in 2016
    show = ["asset", "route", "classifier", "start", "years", "bad_share_%", "BH_cagr", "IND_cagr", "REG_cagr",
            "SWITCH_cagr", "BH_cagr_tax", "IND_cagr_tax", "REG_cagr_tax", "SWITCH_cagr_tax", "BH_maxdd",
            "IND_maxdd", "REG_maxdd", "SWITCH_maxdd", "SWITCH_trades_yr", "switch_vs_ind_attrib", "switch_vs_bh_attrib"]
    say(pb[show].to_string(index=False, float_format=fmt))

    # halves / eras
    halves = {"SPX_LONG": {"1963-1993": ("1963-01-01", "1993-12-31"), "1994-2026": ("1994-01-01", None)}}
    for s in TV_CRYPTO:
        halves[s] = {"to 2020": (None, "2020-12-31"), "2021+": ("2021-01-01", None)}
    for s in ("SPY", "QQQ", "IWM"):
        halves[s] = {"to 2012": (None, "2012-12-31"), "2013+": ("2013-01-01", None)}
    ph = []
    for s, w in halves.items():
        f = frames[s]
        ph.append(part_b_asset(f, (kinds_us if f.attrs["kind"] == "us" else kinds_cr), windows=w))
    ph = pd.concat(ph, ignore_index=True); ph.to_csv(OUT / "partB_halves.csv", index=False)
    say("\nSub-periods:")
    say(ph[show[:3] + ["window"] + show[3:]].to_string(index=False, float_format=fmt))

    # ------------------------------------------------------------ baskets
    say("\n" + "=" * 100); say("BASKETS"); say("=" * 100)
    cal = spx.index[spx.index >= "1996-01-01"]
    mem = members.copy(); mem["end"] = mem["end"].fillna(pd.Timestamp("2100-01-01"))

    def sp_members(y, d0):
        m = mem[(mem.start <= d0) & (mem.end >= d0)]
        return m.symbol.str.upper().tolist()
    kinds_b = ["ma200", "cross", "wk", "mom12", "dd", "vol", "ma200_mkt", "dd_mkt", "hmm_mkt", "vol_mkt", "unrate", "oracle_mkt"]
    yearly_s, slots_s = basket(sframes, sp_members, list(range(1997, 2027)), kinds_b, spx, cal, 0.0003, 1, 300)
    cs = chain(yearly_s); cs.to_csv(OUT / "basket_stocks.csv", index=False)
    yearly_s.drop(columns="path").to_csv(OUT / "basket_stocks_yearly.csv", index=False)
    slots_s.to_csv(OUT / "basket_stocks_slots.csv", index=False)
    say("S&P 500 members, equal weight, formed at each year's start 1997-2026 (pre-tax):")
    say(cs.to_string(index=False, float_format=fmt))

    bin_frames = btc_bin
    calc = pd.date_range("2018-01-01", max(f.index[-1] for f in bin_frames.values()), freq="D")
    kinds_c = ["ma200", "cross", "wk", "mom12", "dd", "vol", "ma200_mkt", "dd_mkt", "hmm_mkt", "vol_mkt", "oracle"]

    def coin_members(y, d0):
        return [s for s, f in bin_frames.items() if f.index[0] <= d0 - pd.Timedelta(days=400) and f.index[-1] >= d0]
    yearly_c, slots_c = basket(bin_frames, coin_members, list(range(2019, 2027)), kinds_c, bin_frames["BTC"],
                               calc, 0.003, 0, 400)
    cc = chain(yearly_c); cc.to_csv(OUT / "basket_crypto.csv", index=False)
    yearly_c.drop(columns="path").to_csv(OUT / "basket_crypto_yearly.csv", index=False)
    slots_c.to_csv(OUT / "basket_crypto_slots.csv", index=False)
    say("\nBinance coins (40 large pairs, 41 series incl. dead LUNA, FTT), equal weight, formed at each year's start 2019-2026 (pre-tax):")
    say(cc.to_string(index=False, float_format=fmt))

    # ------------------------------------------------------------ verdicts
    say("\n" + "=" * 100); say("PRE-REGISTERED VERDICTS"); say("=" * 100)
    prim = pb[(pb.route == "primary") & (pb.window == "full")]
    m200 = prim[prim.classifier == "ma200"].set_index("asset")
    nb1 = int((m200.loc[NAMED, "SWITCH_cagr"] > m200.loc[NAMED, "IND_cagr"]).sum())
    bs = cs.set_index(["strategy", "classifier"]); bc = cc.set_index(["strategy", "classifier"])
    b1s = bs.loc[("SWITCH", "ma200"), "cagr"] > bs.loc[("IND", "-"), "cagr"]
    b1c = bc.loc[("SWITCH", "ma200"), "cagr"] > bc.loc[("IND", "-"), "cagr"]
    say(f"H-B1 SWITCH(ma200) > IND pre-tax: {nb1}/10 named; stock basket {b1s}; crypto basket {b1c} -> "
        f"{'PASS' if nb1 >= 7 and b1s and b1c else 'FAIL'}")

    def t2_row(r):
        return t2(r.SWITCH_cagr_tax, r.SWITCH_maxdd, r.BH_cagr_tax, r.BH_maxdd)
    spx_full = prim[(prim.asset == "SPX_LONG")].set_index("classifier")
    spx_h = ph[ph.asset == "SPX_LONG"]
    b2 = {}
    for k in CLASSIFIERS:
        ok_full = t2_row(spx_full.loc[k])
        ok_h = [t2_row(r) for _, r in spx_h[spx_h.classifier == k].iterrows()]
        b2[k] = ok_full and all(ok_h) and len(ok_h) == 2
        say(f"  SPX_LONG {k:7s}: after tax SWITCH {spx_full.loc[k].SWITCH_cagr_tax:.2f} vs BH {spx_full.loc[k].BH_cagr_tax:.2f}, "
            f"DD {spx_full.loc[k].SWITCH_maxdd:.1f} vs {spx_full.loc[k].BH_maxdd:.1f}; full {ok_full}, halves {ok_h}")
    say(f"H-B2 (ma200 on SPX_LONG, full + both halves): {'PASS' if b2['ma200'] else 'FAIL'}")
    nb3 = int((m200.loc[NAMED, "SWITCH_cagr"] >= m200.loc[NAMED, "REG_cagr"]).sum())
    b3 = m200.loc["SPX_LONG", "SWITCH_cagr"] >= m200.loc["SPX_LONG", "REG_cagr"] and nb3 >= 6
    say(f"H-B3 SWITCH(ma200) >= REG(ma200): SPX_LONG {m200.loc['SPX_LONG', 'SWITCH_cagr']:.2f} vs "
        f"{m200.loc['SPX_LONG', 'REG_cagr']:.2f}; named {nb3}/10 -> {'PASS' if b3 else 'FAIL'}")
    n4 = sum(b2[k] for k in ("cross", "wk", "mom12", "dd", "vol", "hmm"))
    say(f"H-B4 other classifiers passing H-B2 on SPX_LONG: {n4}/6 -> {'PASS' if n4 >= 4 else 'FAIL'}")
    say(f"H-B5 SWITCH(unrate) on SPX_LONG full + halves: {'PASS' if b2['unrate'] else 'FAIL'}")
    log.close()


def sensitivity():
    """EXPLORATORY parameter grid on the named assets (+ COIN, HOOD). Never used to choose."""
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    frames = {"SPX_LONG": load_spx_long()}
    for s in ("SPY", "QQQ", "IWM", "TSLA", "COIN", "HOOD"):
        frames[s] = load_yahoo(s)
    for s in TV_CRYPTO:
        frames[s] = load_tv_crypto(s)
    rows = []
    for name, f in frames.items():
        grid = ["ma100", "ma150", "ma200", "ma250", "mom6", "mom9", "mom12"]
        grid += ["dd10", "dd15", "dd20", "dd30"] if f.attrs["kind"] == "us" else ["dd30", "dd40", "dd50", "dd60"]
        rows.append(part_b_asset(f, grid))
    g = pd.concat(rows, ignore_index=True)
    g.to_csv(OUT / "sensitivity.csv", index=False)
    cols = ["asset", "classifier", "bad_share_%", "BH_cagr", "IND_cagr", "REG_cagr", "SWITCH_cagr", "BH_cagr_tax",
            "SWITCH_cagr_tax", "BH_maxdd", "SWITCH_maxdd"]
    print(g[cols].to_string(index=False, float_format=lambda x: f"{x:,.2f}"))


if __name__ == "__main__":
    if "--sensitivity" in sys.argv:
        sensitivity()
    else:
        main()
