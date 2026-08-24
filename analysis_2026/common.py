"""
Shared loader + strategy library for the 2026 crypto re-run.

Data format: event_date, close_price_usd, market_cap_usd, volume_usd
(price-only — OHLC is synthesized from daily closes)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from indicators import compute_moneyline, compute_contraction, compute_donchian  # noqa: E402
from backtester import run_backtest  # noqa: E402

ASSETS = ["BTC", "ETH", "SOL", "BNB", "ZEC"]
DATA_DIR = REPO / "data" / "crypto2026"

ML_PARAMS = dict(
    conv_period=9,
    base_period=26,
    fast_hma_period=5,
    slow_ema_period=13,
    exit_percent=2.0,
)

COSTS = dict(fee_percent=0.1, slippage_bps=5.0, initial_capital=10000.0)


# ---------------------------------------------------------------- loading

def load_asset(symbol: str) -> pd.DataFrame:
    """Load a price-only CSV and synthesize OHLC bars from daily closes."""
    df = pd.read_csv(DATA_DIR / f"{symbol}.csv")
    df["date"] = pd.to_datetime(df["event_date"], format="mixed", utc=True).dt.tz_localize(None)
    df["close"] = pd.to_numeric(df["close_price_usd"], errors="coerce")
    df = df.dropna(subset=["close"]).sort_values("date").set_index("date")
    df = df[~df.index.duplicated(keep="last")]

    # Synthesize OHLC: open = prior close, high/low = max/min of the two.
    # With no intraday data this is the honest reconstruction — it understates
    # true bar range, which makes the Ichimoku lines slightly smoother than
    # TradingView's.
    out = pd.DataFrame(index=df.index)
    out["close"] = df["close"]
    out["open"] = df["close"].shift(1).fillna(df["close"])
    out["high"] = out[["open", "close"]].max(axis=1)
    out["low"] = out[["open", "close"]].min(axis=1)
    out["volume"] = pd.to_numeric(df.get("volume_usd"), errors="coerce")
    return out


def to_weekly(daily: pd.DataFrame) -> pd.DataFrame:
    """Resample daily bars to Monday-Sunday weekly bars (TradingView convention)."""
    wk = daily.resample("W-SUN").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["close"])
    return wk


# ---------------------------------------------------------------- signals

def add_indicators(df: pd.DataFrame, contraction_window: int = 252) -> pd.DataFrame:
    """Attach Moneyline, contraction, and breakout columns."""
    res = compute_moneyline(df, **ML_PARAMS)
    con = compute_contraction(df, bb_period=20, bb_std=2.0,
                              quantile_window=contraction_window, quantile_threshold=0.20)
    res["bbw"] = con["bbw"]
    res["contracted"] = con["contracted"].fillna(False)
    res["contracted_recent"] = (
        res["contracted"].astype(int).rolling(20, min_periods=1).max().astype(bool)
    )
    don = compute_donchian(df, period=20)
    res["breakout_long"] = don["breakout_long"].fillna(False)
    return res


def align_weekly_state(daily_idx: pd.DatetimeIndex, weekly: pd.DataFrame) -> pd.Series:
    """
    Map the weekly trend state onto daily bars WITHOUT lookahead.

    A weekly bar closing Sunday is only knowable from Monday onward, so the
    weekly state is shifted one full bar before being forward-filled.
    """
    wk_state = weekly["trend_green"].shift(1)
    return wk_state.reindex(daily_idx, method="ffill").fillna(False).astype(bool)


# ---------------------------------------------------------------- metrics

def buy_hold_return(df: pd.DataFrame) -> float:
    return (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100


def max_drawdown(equity: pd.Series) -> float:
    eq = equity.dropna()
    if eq.empty:
        return 0.0
    return float(((eq / eq.cummax()) - 1).min() * 100)


def metrics(result, df: pd.DataFrame, periods_per_year: int) -> dict:
    trades = result.trades_df()
    eq = result.equity_curve.dropna()
    total_ret = (eq.iloc[-1] / COSTS["initial_capital"] - 1) * 100 if len(eq) else 0.0

    n = len(trades)
    wins = trades[trades["net_pnl_pct"] > 0] if n else trades
    losses = trades[trades["net_pnl_pct"] <= 0] if n else trades

    gross_win = wins["net_pnl_pct"].sum() if len(wins) else 0.0
    gross_loss = abs(losses["net_pnl_pct"].sum()) if len(losses) else 0.0

    rets = eq.pct_change().dropna()
    sharpe = (rets.mean() / rets.std() * np.sqrt(periods_per_year)) if rets.std() > 0 else 0.0

    years = (df.index[-1] - df.index[0]).days / 365.25
    cagr = ((eq.iloc[-1] / COSTS["initial_capital"]) ** (1 / years) - 1) * 100 if years > 0 and len(eq) else 0.0

    # "Chop" = trades that closed within +/-2% — whipsaws, not real trends
    chop = (trades["net_pnl_pct"].abs() < 2.0).sum() / n * 100 if n else 0.0

    return {
        "return_pct": total_ret,
        "cagr_pct": cagr,
        "max_dd_pct": max_drawdown(eq),
        "sharpe": sharpe,
        "trades": n,
        "win_rate": len(wins) / n * 100 if n else 0.0,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf"),
        "avg_win": wins["net_pnl_pct"].mean() if len(wins) else 0.0,
        "avg_loss": losses["net_pnl_pct"].mean() if len(losses) else 0.0,
        "chop_pct": chop,
        "exposure_pct": (result.position_series.fillna(0) > 0).mean() * 100,
    }


def bt(df, entry, exit_sig, periods_per_year):
    res = run_backtest(df, entry, exit_sig, **COSTS)
    return res, metrics(res, df, periods_per_year)
