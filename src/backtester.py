"""
Backtest Engine (Agent 4)
=========================
Handles trade execution, fees, and position lifecycle.
Long-only, one position at a time.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Trade:
    """Represents a completed trade."""
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    entry_bar_idx: int
    exit_bar_idx: int
    gross_pnl_pct: float = 0.0
    net_pnl_pct: float = 0.0
    pnl_cash: float = 0.0
    duration_days: int = 0
    mfe: float = 0.0  # Maximum Favorable Excursion (highest return during trade)
    mae: float = 0.0  # Maximum Adverse Excursion (worst drawdown during trade)
    fees_paid: float = 0.0

    def to_dict(self) -> dict:
        return {
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'exit_time': self.exit_time,
            'exit_price': self.exit_price,
            'duration_days': self.duration_days,
            'gross_pnl_pct': round(self.gross_pnl_pct, 4),
            'net_pnl_pct': round(self.net_pnl_pct, 4),
            'pnl_cash': round(self.pnl_cash, 2),
            'mfe': round(self.mfe, 4),
            'mae': round(self.mae, 4),
            'fees_paid': round(self.fees_paid, 4)
        }


@dataclass
class BacktestResult:
    """Container for backtest results."""
    trades: List[Trade]
    equity_curve: pd.Series
    position_series: pd.Series  # 1 = in position, 0 = flat
    signals_df: pd.DataFrame    # DataFrame with entry/exit signals
    initial_capital: float
    final_equity: float
    config: dict = field(default_factory=dict)

    def trades_df(self) -> pd.DataFrame:
        """Convert trades to DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([t.to_dict() for t in self.trades])


def run_backtest(
    df: pd.DataFrame,
    entry_signal: pd.Series,
    exit_signal: pd.Series,
    initial_capital: float = 10000.0,
    fee_percent: float = 0.1,
    slippage_bps: float = 5.0,
    fill_on_next_open: bool = True
) -> BacktestResult:
    """
    Run a long-only backtest.

    CRITICAL FILL LOGIC:
    - Signal detected on bar close
    - Fill executed at NEXT bar open (if fill_on_next_open=True)
    - This prevents lookahead bias

    Parameters
    ----------
    df : pd.DataFrame
        OHLC data with 'open', 'high', 'low', 'close' columns
    entry_signal : pd.Series
        Boolean series, True on bars where entry is signaled
    exit_signal : pd.Series
        Boolean series, True on bars where exit is signaled
    initial_capital : float
        Starting capital
    fee_percent : float
        Fee per trade side (e.g., 0.1 = 0.1%)
    slippage_bps : float
        Slippage in basis points
    fill_on_next_open : bool
        If True, fill at next bar's open. If False, fill at signal bar's close.

    Returns
    -------
    BacktestResult
        Contains trades list, equity curve, and position series
    """
    # Validate inputs
    if len(df) == 0:
        raise ValueError("Empty DataFrame provided")

    required_cols = ['open', 'high', 'low', 'close']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # Ensure signals align with DataFrame
    entry_signal = entry_signal.reindex(df.index).fillna(False).astype(bool)
    exit_signal = exit_signal.reindex(df.index).fillna(False).astype(bool)

    # Initialize state
    trades = []
    equity = initial_capital
    equity_curve = pd.Series(index=df.index, dtype=float)
    position_series = pd.Series(index=df.index, dtype=int)

    in_position = False
    entry_price = 0.0
    entry_time = None
    entry_bar_idx = 0
    shares = 0.0
    pending_entry = False
    pending_exit = False

    # Track MFE/MAE
    trade_high = 0.0
    trade_low = float('inf')

    # Fee/slippage multipliers
    fee_mult = 1 - fee_percent / 100
    slip_mult_buy = 1 + slippage_bps / 10000  # Pay more when buying
    slip_mult_sell = 1 - slippage_bps / 10000  # Get less when selling

    # Iterate through bars
    for i, (timestamp, row) in enumerate(df.iterrows()):
        # Process pending entry from previous bar's signal
        if pending_entry and not in_position:
            if fill_on_next_open:
                fill_price = row['open'] * slip_mult_buy
            else:
                # This branch shouldn't be used for next-open fills
                fill_price = df.iloc[i-1]['close'] * slip_mult_buy

            # Apply entry fee
            entry_cost = equity * fee_mult
            shares = entry_cost / fill_price
            entry_price = fill_price
            entry_time = timestamp
            entry_bar_idx = i
            trade_high = row['high']
            trade_low = row['low']
            in_position = True
            pending_entry = False

        # Process pending exit from previous bar's signal
        if pending_exit and in_position:
            if fill_on_next_open:
                fill_price = row['open'] * slip_mult_sell
            else:
                fill_price = df.iloc[i-1]['close'] * slip_mult_sell

            # Calculate proceeds with exit fee
            gross_proceeds = shares * fill_price
            net_proceeds = gross_proceeds * fee_mult
            fees_paid = (equity - equity * fee_mult) + (gross_proceeds - net_proceeds)

            # Calculate PnL
            gross_pnl_pct = (fill_price / entry_price - 1) * 100
            net_pnl_pct = (net_proceeds / equity - 1) * 100

            # Calculate MFE/MAE
            mfe = (trade_high / entry_price - 1) * 100
            mae = (trade_low / entry_price - 1) * 100

            # Duration
            duration = (timestamp - entry_time).days

            # Create trade record
            trade = Trade(
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=timestamp,
                exit_price=fill_price,
                entry_bar_idx=entry_bar_idx,
                exit_bar_idx=i,
                gross_pnl_pct=gross_pnl_pct,
                net_pnl_pct=net_pnl_pct,
                pnl_cash=net_proceeds - equity,
                duration_days=duration,
                mfe=mfe,
                mae=mae,
                fees_paid=fees_paid
            )
            trades.append(trade)

            # Update equity
            equity = net_proceeds
            shares = 0
            in_position = False
            pending_exit = False
            trade_high = 0
            trade_low = float('inf')

        # Update MFE/MAE if in position
        if in_position:
            trade_high = max(trade_high, row['high'])
            trade_low = min(trade_low, row['low'])

        # Calculate current equity (mark to market)
        if in_position:
            current_equity = shares * row['close']
        else:
            current_equity = equity

        equity_curve.iloc[i] = current_equity
        position_series.iloc[i] = 1 if in_position else 0

        # Check for new signals (will be filled next bar)
        if entry_signal.iloc[i] and not in_position:
            pending_entry = True

        if exit_signal.iloc[i] and in_position:
            pending_exit = True

    # Close any open position at end
    if in_position:
        final_row = df.iloc[-1]
        fill_price = final_row['close'] * slip_mult_sell
        gross_proceeds = shares * fill_price
        net_proceeds = gross_proceeds * fee_mult

        gross_pnl_pct = (fill_price / entry_price - 1) * 100
        net_pnl_pct = (net_proceeds / equity - 1) * 100
        duration = (df.index[-1] - entry_time).days

        trade = Trade(
            entry_time=entry_time,
            entry_price=entry_price,
            exit_time=df.index[-1],
            exit_price=fill_price,
            entry_bar_idx=entry_bar_idx,
            exit_bar_idx=len(df) - 1,
            gross_pnl_pct=gross_pnl_pct,
            net_pnl_pct=net_pnl_pct,
            pnl_cash=net_proceeds - equity,
            duration_days=duration,
            mfe=(trade_high / entry_price - 1) * 100,
            mae=(trade_low / entry_price - 1) * 100,
            fees_paid=0  # Approximate
        )
        trades.append(trade)
        equity_curve.iloc[-1] = net_proceeds

    # Create signals DataFrame
    signals_df = pd.DataFrame({
        'entry_signal': entry_signal,
        'exit_signal': exit_signal,
        'position': position_series
    }, index=df.index)

    return BacktestResult(
        trades=trades,
        equity_curve=equity_curve,
        position_series=position_series,
        signals_df=signals_df,
        initial_capital=initial_capital,
        final_equity=equity_curve.iloc[-1] if len(equity_curve) > 0 else initial_capital,
        config={
            'fee_percent': fee_percent,
            'slippage_bps': slippage_bps,
            'fill_on_next_open': fill_on_next_open
        }
    )


def run_dual_series_backtest(
    df_usd: pd.DataFrame,
    df_btc: Optional[pd.DataFrame],
    entry_usd: pd.Series,
    exit_usd: pd.Series,
    entry_btc: Optional[pd.Series] = None,
    exit_btc: Optional[pd.Series] = None,
    require_btc_entry: bool = True,
    require_btc_exit: bool = True,
    initial_capital: float = 10000.0,
    fee_percent: float = 0.1,
    slippage_bps: float = 5.0
) -> BacktestResult:
    """
    Run backtest with optional dual-series confirmation.

    Entry logic: entry_usd AND entry_btc (if btc enabled)
    Exit logic: exit_usd OR exit_btc (if btc enabled)

    Parameters
    ----------
    df_usd : pd.DataFrame
        Primary OHLC series (coinUSD)
    df_btc : pd.DataFrame, optional
        Secondary OHLC series (coinBTC)
    entry_usd : pd.Series
        Entry signals on USD series
    exit_usd : pd.Series
        Exit signals on USD series
    entry_btc : pd.Series, optional
        Entry signals on BTC series
    exit_btc : pd.Series, optional
        Exit signals on BTC series
    require_btc_entry : bool
        If True, require BTC entry signal for entry
    require_btc_exit : bool
        If True, exit on BTC exit signal (OR logic)

    Returns
    -------
    BacktestResult
    """
    # Single series mode
    if df_btc is None or entry_btc is None:
        return run_backtest(
            df_usd, entry_usd, exit_usd,
            initial_capital=initial_capital,
            fee_percent=fee_percent,
            slippage_bps=slippage_bps
        )

    # Combine signals for dual-series mode
    combined_entry = entry_usd.copy()
    combined_exit = exit_usd.copy()

    if require_btc_entry:
        # Entry requires both USD and BTC signals
        # But they don't need to be on the exact same bar
        # We use a rolling window approach: BTC signal within last N bars
        btc_entry_window = entry_btc.rolling(window=5, min_periods=1).max().astype(bool)
        combined_entry = entry_usd & btc_entry_window

    if require_btc_exit:
        # Exit on either USD or BTC signal
        combined_exit = exit_usd | exit_btc

    return run_backtest(
        df_usd, combined_entry, combined_exit,
        initial_capital=initial_capital,
        fee_percent=fee_percent,
        slippage_bps=slippage_bps
    )
