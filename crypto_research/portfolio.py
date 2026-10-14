"""Cash-only crypto research with completed UTC-day signals/next-day opens.

Each selected coin owns one of ``slot_capacity`` equal capital sleeves. Red
signals leave that sleeve in cash; unused sleeves stay in the reserve. Unchanged
binary or fixed-fraction signals never trigger daily price-drift rebalancing.
Only an explicit changed selection redistributes capital across sleeves. The
Donchian volatility adaptation changes its target only after a relative target
change reaches the configured threshold; regime changes always bypass it.

Actual daily opens and closes are required for every selected coin, including
when it is in cash. Missing histories and disappearing listings cannot be
removed after observing their outcomes or filled at stale prices. The declared
end-close liquidation is a research convention. Fees include that liquidation.

Optional tax estimates reuse the stock research's single-account FIFO ledger,
including its conservative stock-like wash-sale assumptions and 35%/20% default
rates. They are an illustrative sensitivity, not US crypto tax liability: USDT
is treated as a constant quote unit, outside accounts and cash-asset gains are
not represented. Its opt-in canonical FIFO quantity accounting avoids independent
aggregate/lot rounding drift; this changes numeric bookkeeping, not tax policy.
No order or brokerage functionality is present here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from research.tax import TaxLedger, TaxRates


class CryptoPortfolioDataError(ValueError):
    """An actual candle, prior signal or executable settlement is unavailable."""


@dataclass(frozen=True)
class Rebalance:
    date: Any
    picks: tuple[str, ...]


@dataclass(frozen=True)
class CryptoPortfolioConfig:
    initial_capital: float = 100_000.0
    cost_bps: float = 10.0
    slot_capacity: int = 20
    rebalance_threshold: float = 0.20
    tax_enabled: bool = False
    tax_rates: TaxRates = field(default_factory=TaxRates)
    liquidate_at_end: bool = True


@dataclass
class CryptoPortfolioResult:
    path: pd.Series
    metrics: dict[str, float]
    ledger: pd.DataFrame
    tax_records: pd.DataFrame
    trade_summary: dict[str, Any]
    flags: tuple[str, ...]
    deployment_blocked: bool = True
    carry: tuple[float, float] = (0.0, 0.0)
    positions: dict[str, float] = field(default_factory=dict)

    @property
    def mult(self) -> float:
        return self.metrics["total_return"] + 1.0


@dataclass
class _Slot:
    cash: float = 0.0
    quantity: float = 0.0
    last_target: float | None = None
    last_regime: float | None = None


def _index(values: Any, name: str) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(values)
    if idx.tz is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    if idx.hasnans or idx.has_duplicates or not idx.is_monotonic_increasing:
        raise CryptoPortfolioDataError(f"{name}: dates must be finite, unique and increasing")
    if not idx.equals(idx.normalize()):
        raise CryptoPortfolioDataError(f"{name}: daily dates must be midnight UTC")
    return idx


def _date(value: Any) -> pd.Timestamp:
    value = pd.Timestamp(value)
    if value.tzinfo is not None:
        value = value.tz_convert("UTC").tz_localize(None)
    if pd.isna(value) or value != value.normalize():
        raise CryptoPortfolioDataError("daily dates must be finite midnight UTC")
    return value


def portfolio_metrics(path: pd.Series, initial_capital: float) -> dict[str, float]:
    """Daily returns include day one's entry cost and end-day liquidation/tax."""
    values = np.r_[initial_capital, path.to_numpy(float)]
    drawdown = values / np.maximum.accumulate(values) - 1.0
    returns = values[1:] / values[:-1] - 1.0
    years = len(path) / 365.25  # Every selected UTC bar represents a full day.
    multiple = float(values[-1] / initial_capital)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    return {
        "total_return": multiple - 1.0,
        "cagr": multiple ** (1.0 / years) - 1.0 if multiple > 0 else -1.0,
        "max_drawdown": float(drawdown.min()),
        "final_value": float(values[-1]),
        "years": years,
        "sharpe365": float(np.mean(returns) / std * np.sqrt(365)) if std > 0 else float("nan"),
        "annualized_volatility365": std * np.sqrt(365),
    }


def _trade_summary(lots: list[dict[str, Any]]) -> dict[str, Any]:
    """Completed entry FIFO lots, with fees, excluding unfinished lots.

    Partial exits are accumulated into their entry lot. This is not a count of
    independent indicator episodes: volatility additions create extra lots.
    """
    complete = [lot for lot in lots if lot["remaining"] <= 1e-9]
    gains = np.array([lot["proceeds"] - lot["cost"] for lot in complete], float)
    returns = np.array([(lot["proceeds"] / lot["cost"] - 1.0)
                        if lot["cost"] > 0 else 0 for lot in complete], float)
    wins, losses = gains > 1e-9, gains < -1e-9
    gross_win, gross_loss = float(gains[wins].sum()), float(-gains[losses].sum())
    per_coin: dict[str, dict[str, float]] = {}
    for lot in complete:
        entry = per_coin.setdefault(lot["security_id"], {"closed_lots": 0, "realized_gain": 0.0,
                                                        "entry_cost": 0.0})
        entry["closed_lots"] += 1
        entry["realized_gain"] += lot["proceeds"] - lot["cost"]
        entry["entry_cost"] += lot["cost"]
    return {
        "definition": "completed_entry_FIFO_lots_including_fees_not_independent_signal_episodes",
        "closed_lots": len(complete),
        "winning_lots": int(wins.sum()),
        "losing_lots": int(losses.sum()),
        "win_rate": float(wins.mean()) if len(complete) else float("nan"),
        "mean_winning_return": float(returns[wins].mean()) if wins.any() else float("nan"),
        "mean_losing_return": float(returns[losses].mean()) if losses.any() else float("nan"),
        "profit_factor": gross_win / gross_loss if gross_loss else float("nan"),
        "top_winner_profit_share": float(gains[wins].max() / gross_win) if gross_win else float("nan"),
        "gross_winning_gain": gross_win,
        "gross_losing_loss": gross_loss,
        "per_coin": per_coin,
    }


def simulate_portfolio(
    prices: Mapping[str, pd.DataFrame], calendar: pd.DatetimeIndex,
    schedule: Sequence[Rebalance | Mapping[str, Any]], start: Any, end: Any,
    *, signals: Mapping[str, pd.DataFrame] | None = None,
    config: CryptoPortfolioConfig | None = None, always_in: bool = False,
) -> CryptoPortfolioResult:
    cfg = config or CryptoPortfolioConfig()
    if not np.isfinite(cfg.initial_capital) or cfg.initial_capital <= 0:
        raise ValueError("initial_capital must be positive and finite")
    if not np.isfinite(cfg.cost_bps) or not 0 <= cfg.cost_bps < 10_000:
        raise ValueError("cost_bps must be finite and in [0,10000)")
    if not isinstance(cfg.slot_capacity, int) or isinstance(cfg.slot_capacity, bool) or cfg.slot_capacity < 1:
        raise ValueError("slot_capacity must be a positive integer")
    if not np.isfinite(cfg.rebalance_threshold) or not 0 <= cfg.rebalance_threshold <= 1:
        raise ValueError("rebalance_threshold must be in [0,1]")
    if cfg.tax_enabled and not cfg.liquidate_at_end:
        raise ValueError("illustrative tax comparison requires declared final liquidation")
    cal = _index(calendar, "calendar")
    if cal.empty or not cal.equals(pd.date_range(cal[0], cal[-1], freq="D")):
        raise CryptoPortfolioDataError("calendar must contain every UTC day without gaps")
    start, end = _date(start), _date(end)
    days = cal[(cal >= start) & (cal <= end)]
    expected = pd.date_range(start, end, freq="D")
    if start > end or not days.equals(expected):
        raise CryptoPortfolioDataError("calendar must cover the complete requested UTC-day horizon")

    parsed = []
    for event in schedule:
        date, picks = ((event.date, event.picks) if isinstance(event, Rebalance)
                       else (event.get("date", event.get("start")), event["picks"]))
        names = tuple(str(sid) for sid in picks)
        if len(names) > cfg.slot_capacity or len(names) != len(set(names)):
            raise ValueError("selection must contain distinct names within slot_capacity")
        parsed.append((_date(date), names))
    parsed.sort(key=lambda event: event[0])
    if len({date for date, _ in parsed}) != len(parsed):
        raise ValueError("selection schedule contains duplicate dates")
    before = [event for event in parsed if event[0] <= start]
    parsed = ([before[-1]] if before else []) + [event for event in parsed if start < event[0] <= end]
    events = {max(date, start): names for date, names in parsed}
    events.setdefault(start, ())
    required = {sid for names in events.values() for sid in names}
    opens, closes, highs, lows = {}, {}, {}, {}
    targets, regimes = {}, {}
    # Reindex to horizon + previous completed day. No future price is validated
    # or used to prune selection; only selected execution/valuation days matter.
    needed = pd.date_range(start - pd.Timedelta(days=1), end, freq="D")
    for sid in required:
        if sid not in prices:
            raise CryptoPortfolioDataError(f"{sid}: selected price history unavailable")
        frame = prices[sid].rename(columns=str.lower).copy()
        frame.index = _index(frame.index, f"{sid} prices")
        if not {"open", "high", "low", "close"}.issubset(frame.columns):
            raise CryptoPortfolioDataError(f"{sid}: actual OHLC required")
        needed_frame = frame.reindex(needed)
        opens[sid] = needed_frame.open.to_numpy(float)
        highs[sid] = needed_frame.high.to_numpy(float)
        lows[sid] = needed_frame.low.to_numpy(float)
        closes[sid] = needed_frame.close.to_numpy(float)
        if not always_in:
            supplied = None if signals is None else signals.get(sid)
            if supplied is None or not {"target", "regime"}.issubset(supplied.columns):
                raise CryptoPortfolioDataError(f"{sid}: prior-day target and regime required")
            supplied = supplied.copy()
            supplied.index = _index(supplied.index, f"{sid} signals")
            aligned = supplied.reindex(needed)
            targets[sid] = aligned.target.to_numpy(float)
            regimes[sid] = aligned.regime.to_numpy(float)
    slots: dict[str, _Slot] = {}
    current: tuple[str, ...] = ()
    reserve = float(cfg.initial_capital)
    cost = cfg.cost_bps / 10_000.0
    ledger: list[dict[str, Any]] = []
    book = TaxLedger(cfg.tax_rates, canonical_quantities=True) if cfg.tax_enabled else None
    analytics_lots: list[dict[str, Any]] = []
    fifo: dict[str, list[dict[str, Any]]] = {}
    settled: set[int] = set()
    path: list[float] = []
    exposures: list[float] = []
    traded_notional = 0.0
    order_count = 0

    def actual_bar(sid: str, loc: int, day: pd.Timestamp) -> tuple[float, float]:
        bar = np.array([opens[sid][loc], highs[sid][loc], lows[sid][loc], closes[sid][loc]])
        if not np.isfinite(bar).all() or (bar <= 0).any():
            raise CryptoPortfolioDataError(f"{sid} {day.date()}: actual selected OHLC unavailable")
        op, hi, lo, cl = bar
        if hi < max(op, lo, cl) or lo > min(op, hi, cl):
            raise CryptoPortfolioDataError(f"{sid} {day.date()}: inconsistent selected OHLC")
        return float(op), float(cl)

    def trade(sid: str, day: pd.Timestamp, quantity: float, price: float, reason: str) -> None:
        nonlocal traded_notional, order_count
        slot = slots[sid]
        if abs(quantity) < 1e-12:
            return
        notional = abs(quantity) * price
        fee = notional * cost
        if quantity > 0:
            spent = notional + fee
            if spent > slot.cash + 1e-7:
                raise RuntimeError("buy exceeds its cash sleeve")
            slot.cash = max(0.0, slot.cash - spent)
            slot.quantity += quantity
            if book is not None:
                book.buy(sid, day, quantity, spent)
                # The FIFO lot inventory is authoritative in the optional
                # tax account. Repeated independent aggregate +/- updates can
                # drift by ULPs from lots for billions of low-price coin units.
                slot.quantity = book.position(sid)
            lot = {"security_id": sid, "date": day, "quantity": quantity,
                   "remaining": quantity, "cost": spent, "proceeds": 0.0}
            analytics_lots.append(lot)
            fifo.setdefault(sid, []).append(lot)
            cash_flow, event = -spent, "buy"
        else:
            sold = -quantity
            if sold > slot.quantity + 1e-7:
                raise RuntimeError("sale exceeds owned coin quantity")
            proceeds = notional - fee
            slot.quantity = max(0.0, slot.quantity - sold)
            slot.cash += proceeds
            if book is not None:
                book.sell(sid, day, sold, proceeds, reason=reason)
                slot.quantity = book.position(sid)
            left = sold
            for lot in list(fifo.get(sid, [])):
                piece = min(left, lot["remaining"])
                lot["proceeds"] += proceeds * piece / sold
                lot["remaining"] = max(0.0, lot["remaining"] - piece)
                left -= piece
                if lot["remaining"] <= 1e-9:
                    fifo[sid].remove(lot)
                if left <= 1e-12:
                    break
            cash_flow, event = proceeds, "sell"
        traded_notional += notional
        order_count += 1
        ledger.append({"date": day, "security_id": sid, "event": event,
                       "shares": abs(quantity), "price": price, "notional": notional,
                       "fee": fee, "cash_flow": cash_flow, "reason": reason})

    def pay_tax(day: pd.Timestamp, liability: float, year: int, opening: Mapping[str, float]) -> None:
        nonlocal reserve
        if liability <= 1e-12:
            return
        cash = reserve + sum(slot.cash for slot in slots.values())
        for sid, slot in sorted(slots.items()):
            if cash + 1e-9 >= liability:
                break
            if slot.quantity <= 1e-12:
                continue
            price = opening[sid]
            quantity = min(slot.quantity, (liability - cash) / (price * (1.0 - cost)))
            trade(sid, day, -quantity, price, "illustrative_tax_funding")
            cash += quantity * price * (1.0 - cost)
        if cash + 1e-7 < liability:
            raise CryptoPortfolioDataError("illustrative tax exceeds available portfolio cash and positions")
        left = liability
        taken = min(reserve, left)
        reserve -= taken
        left -= taken
        total_slot_cash = sum(slot.cash for slot in slots.values())
        if left > 1e-10:
            for slot in slots.values():
                slot.cash = max(0.0, slot.cash - left * slot.cash / total_slot_cash)
        ledger.append({"date": day, "event": "tax_payment", "cash_flow": -liability,
                       "tax_year": year, "reason": "illustrative_continuous_annual_settlement"})

    for loc, day in enumerate(days, start=1):
        names = events.get(day, current)
        selected = set(current) | set(names)
        bars = {sid: actual_bar(sid, loc, day) for sid in selected}
        opening = {sid: bar[0] for sid, bar in bars.items()}
        wants = {}
        for sid in names:
            target, regime = (1.0, 1.0) if always_in else (targets[sid][loc - 1], regimes[sid][loc - 1])
            if not np.isfinite([target, regime]).all() or not 0 <= target <= 1 or not 0 <= regime <= 1:
                raise CryptoPortfolioDataError(f"{sid} {day.date()}: prior completed UTC-day target/regime unavailable or leveraged")
            wants[sid] = (float(target), float(regime))
        changed = day in events and set(names) != set(current)
        if changed:
            for sid in set(slots) - set(names):
                slot = slots[sid]
                if slot.quantity > 1e-12:
                    trade(sid, day, -slot.quantity, opening[sid], "selection_removal")
                reserve += slots.pop(sid).cash
            for sid in names:
                slots.setdefault(sid, _Slot())
            total = reserve + sum(slot.cash + slot.quantity * opening[sid] for sid, slot in slots.items())
            allocation = total / cfg.slot_capacity
            # Retained coins keep FIFO lots. Sell surplus only when necessary,
            # moving actual cash before filling deficits; fees cannot be borrowed.
            for sid, slot in slots.items():
                value = slot.quantity * opening[sid]
                if value > allocation + 1e-9:
                    trade(sid, day, -(value - allocation) / opening[sid], opening[sid], "selection_resize")
                excess = max(0.0, slot.cash + slot.quantity * opening[sid] - allocation)
                moved = min(excess, slot.cash)
                slot.cash -= moved
                reserve += moved
            for sid, slot in slots.items():
                deficit = max(0.0, allocation - slot.cash - slot.quantity * opening[sid])
                moved = min(reserve, deficit)
                slot.cash += moved
                reserve -= moved
            current = tuple(names)
        if book is not None:
            for year in range(days[0].year, day.year):
                if year not in settled and day >= pd.Timestamp(year + 1, 1, 31):
                    settlement = book.settle_year(year, day)
                    settled.add(year)
                    pay_tax(day, settlement.tax, year, opening)
        for sid, slot in slots.items():
            target, regime = wants[sid]
            regime_changed = slot.last_regime is None or not np.isclose(regime, slot.last_regime, rtol=0, atol=1e-12)
            target_changed = slot.last_target is None or not np.isclose(target, slot.last_target, rtol=0, atol=1e-12)
            relative_change = (abs(target - slot.last_target) / abs(slot.last_target)
                               if slot.last_target not in (None, 0.0) else float("inf"))
            adjust = changed or regime_changed or (target_changed and relative_change + 1e-12 >= cfg.rebalance_threshold)
            if not adjust:
                continue
            price = opening[sid]
            value = slot.quantity * price
            equity = slot.cash + value
            # Solve for target fraction AFTER this trade's cost. At 100% this
            # spends exactly available cash; at 0% it liquidates exactly shares.
            if target * equity > value + 1e-9:
                notional = (target * equity - value) / (1.0 + target * cost)
                trade(sid, day, notional / price, price, "prior_close_target_increase")
            elif target * equity < value - 1e-9:
                # Full exits use the exact owned quantity. Multiplying very
                # large low-price coin quantities by price and dividing back
                # can overshoot ownership by one float64 ULP. For fractional
                # exits, rearrange the same post-cost target equation into
                # quantities: q*(1-t)/(1-t*c) - t*cash/(price*(1-t*c)). The
                # first multiplier is at most one and the subtracted cash
                # term is nonnegative, so a valid target cannot oversell.
                denominator = 1.0 - target * cost
                quantity = (slot.quantity if target == 0.0 else
                            slot.quantity * ((1.0 - target) / denominator)
                            - (target / denominator) * (slot.cash / price))
                trade(sid, day, -quantity, price, "prior_close_target_decrease")
            slot.last_target, slot.last_regime = target, regime
        value = reserve + sum(slot.cash + slot.quantity * bars[sid][1] for sid, slot in slots.items())
        invested = sum(slot.quantity * bars[sid][1] for sid, slot in slots.items())
        if not np.isfinite(value) or value <= 0:
            raise CryptoPortfolioDataError("portfolio value must remain finite and positive")
        if reserve < -1e-7 or any(slot.cash < -1e-7 for slot in slots.values()):
            raise RuntimeError("cash-only portfolio acquired a negative cash balance")
        path.append(value)
        exposures.append(invested / value)
    if cfg.liquidate_at_end:
        day = days[-1]
        loc = len(days)
        for sid, slot in slots.items():
            if slot.quantity > 1e-12:
                _, close = actual_bar(sid, loc, day)
                trade(sid, day, -slot.quantity, close, "declared_final_close_liquidation")
        if book is not None:
            for year in range(days[0].year, day.year + 1):
                if year not in settled:
                    settlement = book.settle_year(year, day, allow_final=True)
                    settled.add(year)
                    pay_tax(day, settlement.tax, year, {})
        path[-1] = reserve + sum(slot.cash for slot in slots.values())
    series = pd.Series(path, index=days, name="equity")
    metrics = portfolio_metrics(series, cfg.initial_capital)
    metrics.update(exposure=float(np.mean(exposures)), trades=float(order_count),
                   trades_per_year=order_count / metrics["years"], traded_notional=traded_notional,
                   turnover=traded_notional / float(series.mean()),
                   annual_turnover=traded_notional / float(series.mean()) / metrics["years"],
                   total_fees=float(sum(row.get("fee", 0.0) for row in ledger)),
                   total_tax=float(sum(row.get("cash_flow", 0.0) * -1.0 for row in ledger if row["event"] == "tax_payment")))
    flags = {"historical_research_not_prospective", "cash_only_zero_cash_yield",
             "missing_terminal_proceeds_not_assumed", "usdt_quote_unit_not_verified_usd_tax_basis"}
    if cfg.liquidate_at_end:
        flags.add("declared_end_close_liquidation_including_cost")
    else:
        flags.add("open_positions_not_terminally_liquidated")
    if book is not None:
        flags.add("illustrative_stock_like_fifo_tax_with_same_account_wash_sales_not_crypto_liability")
        flags.add("canonical_fifo_quantity_accounting")
    ledger_frame = pd.DataFrame(ledger) if ledger else pd.DataFrame(columns=[
        "date", "security_id", "event", "shares", "price", "notional", "fee", "cash_flow", "reason"])
    return CryptoPortfolioResult(
        path=series, metrics=metrics, ledger=ledger_frame,
        tax_records=pd.DataFrame([vars(s) for s in book.settlements]) if book is not None else pd.DataFrame(),
        trade_summary=_trade_summary(analytics_lots), flags=tuple(sorted(flags)),
        carry=tuple(book.carry) if book is not None else (0.0, 0.0),
        positions={sid: slot.quantity for sid, slot in slots.items()},
    )
