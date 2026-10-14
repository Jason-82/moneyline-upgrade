"""Continuous, close-signal/next-open stock portfolio research.

This module deliberately does not implement stock selection or broker orders. A
selection schedule is supplied before simulation. Equal capital slots hold their
stock while green and their own cash while red. Capital is redistributed only at
an explicitly supplied *changed* selection, never at quarter/year boundaries.
Retained securities keep FIFO lots when a selection changes.

Bars must be split-only OHLC. Dividends and terminal cash proceeds must use the
same normalized share units as those bars. Ex-date dividend entitlements accrue
to shares held before that day's open; this research interface assumes cash is
available on the ex-date, and does not claim to model payment-date liquidity.
Dividends reinvest at the next actual open while the slot remains green (the
explicit ``cash`` policy leaves them in that slot instead). This is a declared
research convention, not a claim about a broker's actual DRIP price or timing.
No missing open is manufactured. Strict mode rejects missing bars and unresolved
terminal histories. Diagnostic mode marks an unavailable position at its last
observed close but never trades it at that mark; these results block deployment.

Tax is an illustrative, single-controlled-account FIFO model, not a tax return.
Annual liability is paid after the forward wash-sale window closes. A cash
shortfall causes explicit next-open sales, with normal lot/gain accounting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from analysis_2026.moneyline_ref import moneyline
from research.tax import TaxLedger, TaxRates
from screener.data import valid_ohlc_mask


class PortfolioDataError(ValueError):
    """A price needed for actual execution or valuation is unavailable."""


@dataclass(frozen=True)
class Rebalance:
    date: Any
    picks: tuple[str, ...]


@dataclass
class PortfolioConfig:
    initial_capital: float = 100_000.0
    cost_bps: float = 3.0
    strict: bool = True
    price_mode: str = "split_only"
    tax_enabled: bool = False
    tax_rates: TaxRates = field(default_factory=TaxRates)
    cash_daily_returns: pd.Series | None = None
    liquidate_at_end: bool = True
    qualified_dividend_fraction: float = 0.0
    dividend_reinvestment: str = "next_open"


@dataclass
class PortfolioResult:
    path: pd.Series
    mult: float
    metrics: dict[str, float]
    ledger: pd.DataFrame
    tax_records: pd.DataFrame
    flags: tuple[str, ...]
    deployment_blocked: bool
    carry: tuple[float, float]
    window_metrics: pd.DataFrame
    positions: dict[str, float]
    blocking_flags: tuple[str, ...] = ()


@dataclass
class _Slot:
    cash: float = 0.0
    shares: float = 0.0


def _date(value: Any) -> pd.Timestamp:
    out = pd.Timestamp(value)
    if out.tzinfo is not None:
        out = out.tz_localize(None)
    return out.normalize()


def _index(index: Any) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    return idx.normalize()


def portfolio_metrics(path: pd.Series, initial_capital: float,
                      start: Any, end: Any) -> dict[str, float]:
    """Fraction-valued returns; drawdown includes initial capital before day one."""
    values = np.r_[initial_capital, path.to_numpy(float)]
    dd = values / np.maximum.accumulate(values) - 1
    years = max((_date(end) - _date(start)).days / 365.25, 1 / 365.25)
    mult = float(values[-1] / initial_capital)
    return {"total_return": mult - 1,
            "cagr": mult ** (1 / years) - 1 if mult > 0 else -1.0,
            "max_drawdown": float(dd.min()), "final_value": float(values[-1]),
            "years": years}


class PortfolioEngine:
    def __init__(self, prices: Mapping[str, pd.DataFrame], calendar: pd.DatetimeIndex,
                 *, signals: Mapping[str, pd.Series] | None = None,
                 dividends: Mapping[str, pd.Series] | None = None,
                 terminal_events: Sequence[Any] = (), metadata: Mapping[str, Any] | None = None,
                 config: PortfolioConfig | None = None):
        self.config = config or PortfolioConfig()
        self.cal = _index(calendar)
        if self.cal.empty or self.cal.has_duplicates or not self.cal.is_monotonic_increasing:
            raise PortfolioDataError("calendar must contain unique ascending exchange sessions")
        if self.config.initial_capital <= 0 or not 0 <= self.config.cost_bps < 10_000:
            raise ValueError("invalid initial capital or transaction cost")
        if not 0 <= self.config.qualified_dividend_fraction <= 1:
            raise ValueError("qualified_dividend_fraction must be in [0,1]")
        if self.config.dividend_reinvestment not in ("next_open", "cash"):
            raise ValueError("dividend_reinvestment must be next_open or cash")
        self.cost = self.config.cost_bps / 10_000
        mode = {"split": "split_only", "total": "total_return"}.get(
            self.config.price_mode, self.config.price_mode)
        self.flags: set[str] = set()
        self.blocking_flags: set[str] = set()
        if mode != "split_only":
            if self.config.strict:
                raise PortfolioDataError("strict research requires split-only OHLC")
            if self.config.tax_enabled:
                raise PortfolioDataError("separate dividend tax cannot be inferred from total-adjusted OHLC")
            self.flags.add("diagnostic_total_return_ohlc_indicator_differs_from_live")
            self.blocking_flags.add("diagnostic_total_return_ohlc_indicator_differs_from_live")
        meta = dict(metadata or {})
        if not meta.get("validated", False):
            self.flags.add("dataset_not_validated")
            self.blocking_flags.add("dataset_not_validated")
        for name in ("universe_complete", "dividends_complete", "terminal_complete", "point_in_time_ids"):
            if meta.get(name) is not True:
                self.flags.add(f"incomplete_{name}")
                self.blocking_flags.add(f"incomplete_{name}")
        sources = ("price_source", "dividend_source", "corporate_action_source", "calendar_source")
        for name in sources:
            if not str(meta.get(name, "")).strip():
                self.flags.add(f"missing_{name}")
                self.blocking_flags.add(f"missing_{name}")
        if meta.get("price_basis") not in (mode, None):
            raise PortfolioDataError("configuration price_mode disagrees with dataset price_basis")
        for gap in meta.get("data_quality_gaps", []):
            self.flags.add(f"data_quality_gap:{gap}")
            self.blocking_flags.add(f"data_quality_gap:{gap}")
        if self.config.strict and (meta.get("price_basis") != "split_only" or self.blocking_flags):
            raise PortfolioDataError("strict research requires a validated complete split-only dataset manifest: "
                                     + ", ".join(sorted(self.blocking_flags)))
        if self.config.tax_enabled:
            self.flags.add("illustrative_tax_single_controlled_account_only")
            self.flags.add("qualified_dividend_classification_is_configured_not_inferred")
        # The public Qlib archive stores OHLC in float32. A nominal high/open
        # equality can differ by one or two source ULPs after rescaling. Only
        # this explicitly declared exploratory source may tolerate that range
        # error; original execution prices remain untouched and deployment stays
        # blocked. Validated split-only inputs retain exact range checks.
        range_ulps = 0
        if (not self.config.strict and mode == "total_return"
                and meta.get("mode") in ("exploratory", "legacy_qlib")
                and meta.get("source_precision") == "float32"
                and "qlib" in str(meta.get("price_source", "")).lower()):
            range_ulps = meta.get("ohlc_float32_ulps", 0)
            if not isinstance(range_ulps, int) or isinstance(range_ulps, bool) or not 0 <= range_ulps <= 2:
                raise PortfolioDataError("declared exploratory float32 range tolerance must be an integer from 0 to 2")
            if range_ulps:
                self.flags.add("exploratory_qlib_float32_range_tolerance")
                self.blocking_flags.add("exploratory_qlib_float32_range_tolerance")
        self.frames: dict[str, pd.DataFrame] = {}
        self.signals: dict[str, pd.Series] = {}
        self._positions = {date: i for i, date in enumerate(self.cal)}
        self._opens: dict[str, np.ndarray] = {}
        self._closes: dict[str, np.ndarray] = {}
        for sid, raw in prices.items():
            df = raw.rename(columns=str.lower).copy()
            df.index = _index(df.index)
            if df.index.has_duplicates or not df.index.is_monotonic_increasing:
                raise PortfolioDataError(f"{sid}: bars must have unique ascending dates")
            if any(col not in df for col in ("open", "high", "low", "close")):
                raise PortfolioDataError(f"{sid}: actual OHLC required")
            vals = df[["open", "high", "low", "close"]].to_numpy(float)
            if not np.isfinite(vals).all() or (vals <= 0).any():
                raise PortfolioDataError(f"{sid}: invalid OHLC values")
            if not valid_ohlc_mask(df, float32_ulps=range_ulps).all():
                raise PortfolioDataError(f"{sid}: inconsistent OHLC range")
            self.frames[str(sid)] = df
            self._opens[str(sid)] = df.open.reindex(self.cal).to_numpy(float)
            self._closes[str(sid)] = df.close.reindex(self.cal).to_numpy(float)
            supplied = None if signals is None else signals.get(sid)
            if supplied is None:
                self.signals[str(sid)] = moneyline(df).green
            else:
                ser = supplied.copy()
                ser.index = _index(ser.index)
                if ser.index.has_duplicates or not ser.isin([True, False, 0, 1]).all():
                    raise PortfolioDataError(f"{sid}: signal must contain unique boolean closed-bar states")
                self.signals[str(sid)] = ser.astype(bool)
        self.dividends: dict[str, pd.Series] = {}
        for sid, source in (dividends or {}).items():
            ser = source.copy()
            ser.index = _index(ser.index)
            if ser.index.has_duplicates or not np.isfinite(ser.to_numpy(float)).all() or (ser < 0).any():
                raise PortfolioDataError(f"{sid}: invalid dividend events")
            self.dividends[str(sid)] = ser
        if self.dividends:
            if mode != "split_only":
                raise PortfolioDataError("cannot add separate dividends to total-return OHLC")
            self.flags.add("dividend_cash_available_on_ex_date_assumption")
        self.terminal: dict[str, dict[pd.Timestamp, float]] = {}
        for event in terminal_events:
            def get(name: str):
                return event[name] if isinstance(event, Mapping) else getattr(event, name)
            sid, date, payout = str(get("security_id")), _date(get("date")), float(get("cash_per_share"))
            if not np.isfinite(payout) or payout < 0:
                raise PortfolioDataError(f"{sid}: terminal payout must be known and nonnegative")
            if sid in self.terminal:
                raise PortfolioDataError(f"{sid}: duplicate terminal events")
            available = self.cal[self.cal >= date]
            # Cash payouts on a non-session become available on the next session.
            execution_date = available[0] if len(available) else date
            self.terminal[sid] = {execution_date: payout}
        self.cash_returns = self.config.cash_daily_returns
        if self.cash_returns is not None:
            self.cash_returns = self.cash_returns.copy()
            self.cash_returns.index = _index(self.cash_returns.index)
            if (self.cash_returns.index.has_duplicates or
                    not np.isfinite(self.cash_returns.to_numpy(float)).all() or
                    (self.cash_returns <= -1).any()):
                raise PortfolioDataError("cash daily returns must be finite, > -1, and unique")
            if self.config.tax_enabled and (self.cash_returns < 0).any():
                raise PortfolioDataError("tax-enabled cash returns must be nonnegative; "
                                         "the illustrative ledger does not model negative cash income")
        self._base_flags = set(self.flags)
        self._base_blocking_flags = set(self.blocking_flags)

    def _bar(self, sid: str, day: pd.Timestamp, column: str) -> float | None:
        values = (self._opens if column == "open" else self._closes).get(sid)
        i = self._positions.get(day)
        if values is not None and i is not None and np.isfinite(values[i]):
            return float(values[i])
        return None

    def _unavailable(self, sid: str, day: pd.Timestamp, purpose: str) -> None:
        df = self.frames.get(sid)
        reason = "unknown_terminal" if df is not None and len(df) and day > df.index[-1] else "missing_bar"
        message = f"{sid} {day.date()}: {reason}; no {purpose} price exists"
        if self.config.strict:
            raise PortfolioDataError(message)
        self.flags.add(reason)
        self.flags.add("unavailable_positions_marked_stale_never_executed")
        self.blocking_flags.add(reason)

    def run(self, schedule: Sequence[Rebalance | Mapping[str, Any]], start: Any, end: Any,
            *, always_in: bool = False) -> PortfolioResult:
        self.flags = set(self._base_flags)
        self.blocking_flags = set(self._base_blocking_flags)
        days = self.cal[(self.cal >= _date(start)) & (self.cal <= _date(end))]
        if days.empty:
            raise PortfolioDataError("simulation horizon has no exchange sessions")
        events: dict[pd.Timestamp, tuple[str, ...]] = {}
        parsed_schedule = []
        for event in schedule:
            if isinstance(event, Rebalance):
                date, picks = event.date, event.picks
            else:
                date, picks = event.get("date", event.get("start")), event["picks"]
            if date is None:
                raise ValueError("selection schedule requires date or start")
            parsed_schedule.append((_date(date), picks))
        # Use the latest schedule known before this horizon rather than creating
        # several rebalances artificially on its first session.
        parsed_schedule.sort(key=lambda item: item[0])
        before = [item for item in parsed_schedule if item[0] <= days[0]]
        parsed_schedule = ([before[-1]] if before else []) + [
            item for item in parsed_schedule if item[0] > days[0]]
        for date, picks in parsed_schedule:
            candidates = self.cal[self.cal >= _date(date)]
            if candidates.empty or candidates[0] > days[-1]:
                continue
            execution_date = max(candidates[0], days[0])
            if execution_date in events:
                raise ValueError("multiple selection schedules on the same execution session")
            names = tuple(str(x) for x in picks)
            if len(names) != len(set(names)):
                raise ValueError("selection contains duplicate securities")
            events[execution_date] = names
        if days[0] not in events:
            events[days[0]] = ()
        slots: dict[str, _Slot] = {}
        reserve = float(self.config.initial_capital)
        book = TaxLedger(rates=self.config.tax_rates)
        raw_ledger: list[dict[str, Any]] = []
        path: list[float] = []
        exposure_sum = 0.0
        trades = 0
        ended: set[str] = {sid for sid, event in self.terminal.items()
                          if next(iter(event)) < days[0]}
        last_marks: dict[str, float] = {}
        settled: set[int] = set()
        current_picks: tuple[str, ...] = ()
        dividend_pending: dict[str, float] = {}

        def trade(sid: str, day: pd.Timestamp, quantity: float, price: float, reason: str) -> float:
            nonlocal trades
            slot = slots[sid]
            if quantity > 1e-12:
                spent = quantity * price * (1 + self.cost)
                if spent > slot.cash + 1e-7:
                    raise RuntimeError("buy exceeds slot cash")
                slot.cash -= spent
                slot.shares += quantity
                if self.config.tax_enabled:
                    book.buy(sid, day, quantity, spent)
                amount = -spent
                side = "buy"
            elif quantity < -1e-12:
                sold = -quantity
                if sold > slot.shares + 1e-7:
                    raise RuntimeError("sell exceeds shares")
                proceeds = sold * price * (1 - self.cost)
                slot.shares = max(0.0, slot.shares - sold)
                slot.cash += proceeds
                if self.config.tax_enabled:
                    book.sell(sid, day, sold, proceeds, reason=reason)
                amount = proceeds
                side = "sell"
            else:
                return 0.0
            trades += 1
            raw_ledger.append({"date": day, "security_id": sid, "event": side,
                               "shares": abs(quantity), "price": price, "cash_flow": amount,
                               "reason": reason})
            return amount

        def mark(sid: str, day: pd.Timestamp, column: str) -> float:
            value = self._bar(sid, day, column)
            if value is not None:
                last_marks[sid] = value
                return value
            self._unavailable(sid, day, f"{column} valuation")
            if sid not in last_marks:
                raise PortfolioDataError(f"{sid}: even diagnostic valuation lacks a prior observed mark")
            return last_marks[sid]

        def pay_tax(day: pd.Timestamp, tax: float, tax_year: int) -> None:
            nonlocal reserve
            if tax <= 1e-12:
                return
            cash = reserve + sum(s.cash for s in slots.values())
            if cash + 1e-9 < tax:
                for sid, slot in sorted(slots.items()):
                    if slot.shares <= 1e-12:
                        continue
                    price = self._bar(sid, day, "open")
                    if price is None:
                        self._unavailable(sid, day, "tax-funding execution")
                        continue
                    q = min(slot.shares, (tax - cash) / (price * (1 - self.cost)))
                    cash += trade(sid, day, -q, price, "tax_funding")
                    if cash + 1e-9 >= tax:
                        break
            if cash + 1e-7 < tax:
                raise PortfolioDataError("tax liability cannot be funded from available cash or executable shares")
            left = tax
            use = min(reserve, left)
            reserve -= use
            left -= use
            total_slot_cash = sum(s.cash for s in slots.values())
            if left > 0:
                for slot in slots.values():
                    use = left * slot.cash / total_slot_cash
                    slot.cash -= use
            raw_ledger.append({"date": day, "event": "tax_payment", "cash_flow": -tax,
                               "tax_year": tax_year, "reason": "continuous_annual_settlement"})

        for day in days:
            loc = int(self.cal.get_loc(day))
            previous = self.cal[loc - 1] if loc else None
            dividend_due, dividend_pending = dividend_pending, {}
            # Dividend ownership is determined before today's open or selection.
            for sid, slot in slots.items():
                dividend = self.dividends.get(sid)
                if slot.shares > 0 and dividend is not None and day in dividend.index:
                    income = slot.shares * float(dividend.at[day])
                    slot.cash += income
                    dividend_pending[sid] = dividend_pending.get(sid, 0.0) + income
                    if self.config.tax_enabled:
                        book.record_dividend(day, income, self.config.qualified_dividend_fraction)
                    raw_ledger.append({"date": day, "security_id": sid, "event": "dividend",
                                       "cash_flow": income, "reason": "prior_close_entitlement"})
            # Known terminal payouts never use a stale price and may legally be zero.
            for sid, terminal in self.terminal.items():
                if day in terminal:
                    ended.add(sid)
                    if sid in slots and slots[sid].shares > 1e-12:
                        slot = slots[sid]
                        proceeds = slot.shares * terminal[day]
                        if self.config.tax_enabled:
                            book.sell(sid, day, slot.shares, proceeds, reason="terminal_payout")
                        raw_ledger.append({"date": day, "security_id": sid, "event": "terminal_payout",
                                           "shares": slot.shares, "price": terminal[day], "cash_flow": proceeds})
                        slot.cash += proceeds
                        slot.shares = 0.0
            wants: dict[str, bool] = {}
            names_today = events.get(day, current_picks)
            for sid in set(current_picks) | set(names_today):
                if sid in ended:
                    wants[sid] = False
                    continue
                # Missing selected bars are not an excuse to remove the security ex post.
                if self._bar(sid, day, "open") is None:
                    self._unavailable(sid, day, "execution")
                    wants[sid] = slots.get(sid, _Slot()).shares > 0
                    continue
                if always_in:
                    wants[sid] = True
                else:
                    signal = self.signals.get(sid)
                    if previous is None or signal is None or previous not in signal.index:
                        if self.config.strict:
                            raise PortfolioDataError(f"{sid} {day.date()}: prior completed-session signal unavailable")
                        self.flags.add("prior_session_signal_missing_no_trade")
                        self.blocking_flags.add("prior_session_signal_missing_no_trade")
                        wants[sid] = slots.get(sid, _Slot()).shares > 0
                    else:
                        wants[sid] = bool(signal.at[previous])
            # Signal exits and removals execute only at this session's actual open.
            for sid, slot in list(slots.items()):
                if slot.shares > 1e-12 and (sid not in names_today or not wants.get(sid, False)):
                    price = self._bar(sid, day, "open")
                    if price is not None:
                        trade(sid, day, -slot.shares, price,
                              "selection_removal" if sid not in names_today else "red_previous_close")
            # Reallocate only a changed selection; unchanged selected names keep their lots.
            if day in events and set(names_today) != set(current_picks):
                removed = set(slots) - set(names_today)
                for sid in removed:
                    if slots[sid].shares > 1e-12:
                        raise PortfolioDataError(f"{sid}: cannot remove a position without an executable open")
                    reserve += slots.pop(sid).cash
                for sid in names_today:
                    slots.setdefault(sid, _Slot())
                total = reserve + sum(slot.cash + slot.shares * mark(sid, day, "open")
                                      for sid, slot in slots.items() if slot.shares > 0)
                total += sum(slot.cash for slot in slots.values() if slot.shares == 0)
                target = total / len(names_today) if names_today else 0.0
                # Sell surplus shares; transfer surplus cash to the allocation reserve.
                for sid, slot in slots.items():
                    price = self._bar(sid, day, "open")
                    stock_value = slot.shares * (price or 0)
                    if stock_value > target + 1e-9:
                        if price is None:
                            raise PortfolioDataError(f"{sid}: changed selection needs unavailable rebalance price")
                        trade(sid, day, -(stock_value - target) / price, price, "selection_resize")
                    excess = max(0.0, slot.cash + slot.shares * (price or 0) - target)
                    move = min(excess, slot.cash)
                    slot.cash -= move
                    reserve += move
                for sid, slot in slots.items():
                    price = self._bar(sid, day, "open")
                    deficit = max(0.0, target - slot.cash - slot.shares * (price or 0))
                    move = min(reserve, deficit)
                    slot.cash += move
                    reserve -= move
                current_picks = tuple(names_today)
            # Annual settlement is delayed until all +/-30-day December matches are known.
            if self.config.tax_enabled:
                for year in range(days[0].year, day.year):
                    if year not in settled and day >= pd.Timestamp(year + 1, 1, 31):
                        settlement = book.settle_year(year, day)
                        settled.add(year)
                        pay_tax(day, settlement.tax, year)
            for sid, slot in slots.items():
                price = self._bar(sid, day, "open")
                if wants.get(sid, False) and slot.shares <= 1e-12 and slot.cash > 1e-12 and price is not None:
                    trade(sid, day, slot.cash / (price * (1 + self.cost)), price, "green_previous_close")
                elif (self.config.dividend_reinvestment == "next_open" and wants.get(sid, False)
                      and slot.shares > 1e-12 and dividend_due.get(sid, 0) > 0 and price is not None):
                    budget = min(slot.cash, dividend_due[sid])
                    trade(sid, day, budget / (price * (1 + self.cost)), price, "dividend_reinvestment")
            cash_rate = 0.0
            if self.cash_returns is not None:
                if day not in self.cash_returns.index:
                    if self.config.strict:
                        raise PortfolioDataError(f"{day.date()}: cash return missing")
                    self.flags.add("cash_return_missing_assumed_zero")
                    self.blocking_flags.add("cash_return_missing_assumed_zero")
                else:
                    cash_rate = float(self.cash_returns.at[day])
            income = (reserve + sum(s.cash for s in slots.values())) * cash_rate
            reserve *= 1 + cash_rate
            for slot in slots.values():
                slot.cash *= 1 + cash_rate
            if income:
                if self.config.tax_enabled:
                    book.record_interest(day, income)
                raw_ledger.append({"date": day, "event": "interest", "cash_flow": income})
            value = reserve + sum(slot.cash + slot.shares * mark(sid, day, "close")
                                  for sid, slot in slots.items() if slot.shares > 0)
            value += sum(slot.cash for slot in slots.values() if slot.shares == 0)
            invested = sum(slot.shares * last_marks[sid] for sid, slot in slots.items() if slot.shares > 0)
            exposure_sum += invested / value if value else 0.0
            path.append(value)

        if self.config.liquidate_at_end:
            day = days[-1]
            for sid, slot in slots.items():
                if slot.shares > 1e-12:
                    price = self._bar(sid, day, "close")
                    if price is None:
                        self._unavailable(sid, day, "terminal close liquidation")
                        self.flags.add("terminal_liquidation_unavailable")
                        self.blocking_flags.add("terminal_liquidation_unavailable")
                    else:
                        trade(sid, day, -slot.shares, price, "declared_final_close_liquidation")
            if self.config.tax_enabled:
                # Closed controlled account has no subsequent replacements. This cannot
                # exclude wash sales in other accounts, which is explicitly a limitation.
                for year in range(days[0].year, days[-1].year + 1):
                    if year not in settled:
                        settlement = book.settle_year(year, day, allow_final=True)
                        settled.add(year)
                        pay_tax(day, settlement.tax, year)
            final = reserve + sum(s.cash for s in slots.values())
            final += sum(s.shares * last_marks[sid] for sid, s in slots.items() if s.shares > 0)
            path[-1] = final
        elif self.config.tax_enabled:
            self.flags.add("unsettled_current_year_tax_and_unrealized_terminal_gains")
            self.blocking_flags.add("unsettled_current_year_tax_and_unrealized_terminal_gains")
        series = pd.Series(path, index=days, name="equity")
        metrics = portfolio_metrics(series, self.config.initial_capital, days[0], days[-1])
        metrics.update(exposure=exposure_sum / len(days), trades=float(trades))
        windows = []
        ordered = sorted(events)
        for i, day in enumerate(ordered):
            finish = ordered[i + 1] if i + 1 < len(ordered) else None
            subset = series[(series.index >= day) & ((series.index < finish) if finish is not None else True)]
            if subset.empty:
                continue
            prior = series[series.index < day]
            before = float(prior.iloc[-1]) if len(prior) else self.config.initial_capital
            windows.append({"start": subset.index[0], "end": subset.index[-1], "n": len(events[day]),
                            "start_value": before, "end_value": float(subset.iloc[-1]),
                            "multiple": float(subset.iloc[-1]) / before})
        tax_records = pd.DataFrame([vars(s) for s in book.settlements]) if self.config.tax_enabled else pd.DataFrame()
        tax_transactions = book.transactions if self.config.tax_enabled else []
        ledger = pd.DataFrame(raw_ledger)
        if tax_transactions:
            # Preserve detailed tax records separately from portfolio cash flows.
            tax_detail = pd.DataFrame(tax_transactions)
            tax_detail["ledger_type"] = "tax_detail"
            ledger = pd.concat([ledger, tax_detail], ignore_index=True, sort=False)
        flags = tuple(sorted(self.flags))
        return PortfolioResult(series, float(series.iloc[-1] / self.config.initial_capital), metrics,
                               ledger, tax_records, flags, bool(self.blocking_flags),
                               tuple(book.carry) if self.config.tax_enabled else (0.0, 0.0),
                               pd.DataFrame(windows), {s: x.shares for s, x in slots.items()},
                               tuple(sorted(self.blocking_flags)))


def simulate_portfolio(prices: Mapping[str, pd.DataFrame], calendar: pd.DatetimeIndex,
                       schedule: Sequence[Rebalance | Mapping[str, Any]], start: Any, end: Any,
                       *, signals: Mapping[str, pd.Series] | None = None,
                       dividends: Mapping[str, pd.Series] | None = None,
                       terminal_events: Sequence[Any] = (), metadata: Mapping[str, Any] | None = None,
                       config: PortfolioConfig | None = None, always_in: bool = False) -> PortfolioResult:
    names = set()
    for event in schedule:
        names.update(event.picks if isinstance(event, Rebalance) else event["picks"])
    # An unused security's later malformed history cannot retrospectively remove
    # a selected stock or abort an unrelated portfolio. Selected names are never
    # dropped on the basis of their subsequent outcomes.
    required_prices = {sid: frame.loc[_index(frame.index) <= _date(end)]
                       for sid, frame in prices.items() if sid in names}
    required_dividends = {sid: event.loc[_index(event.index) <= _date(end)]
                          for sid, event in (dividends or {}).items() if sid in names}
    required_signals = None if signals is None else {
        sid: event.loc[_index(event.index) <= _date(end)] for sid, event in signals.items() if sid in names}
    return PortfolioEngine(required_prices, calendar, signals=required_signals, dividends=required_dividends,
                           terminal_events=terminal_events, metadata=metadata,
                           config=config).run(schedule, start, end, always_in=always_in)
