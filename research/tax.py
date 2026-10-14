"""Continuous illustrative FIFO tax accounting for stock research.

This is a research approximation, not a calculation of an investor's liability.
Wash sales cover identical ``security_id`` values in this one controlled account,
including purchases in the preceding/following 30 calendar days. They do not
cover outside accounts, spouses, options, or other substantially identical
securities. Ordinary capital-loss deductions are conservatively set to zero.

Loss-sale records stay mutable until the following year's wash window closes.
Settlements must run in year order and cannot reset a capital-loss carryforward.
``allow_final=True`` explicitly assumes no subsequent replacement purchases and
permanently closes the ledger to trades/income; successive tax years may be
settled at that same terminal as-of. Use it only for a terminal liquidation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

import pandas as pd

_EPS = 1e-10


def _date(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if pd.isna(result):
        raise ValueError("date must be nonmissing")
    if result.tzinfo is not None:
        result = result.tz_localize(None)
    return result.normalize()


def _amount(value: float, name: str, *, positive: bool = False) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0 or (positive and value <= 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


@dataclass(frozen=True)
class TaxRates:
    short_term: float = 0.35
    long_term: float = 0.20
    ordinary: float = 0.35
    qualified_dividend: float = 0.20

    def __post_init__(self):
        for name in self.__dataclass_fields__:
            value = getattr(self, name)
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} rate must be between zero and one")


@dataclass
class TaxLot:
    lot_id: int
    security_id: str
    acquired: pd.Timestamp
    shares: float
    total_cost: float
    holding_credit_days: int = 0
    replacement_available: bool = True

    @property
    def basis(self) -> float:
        return self.total_cost

    @property
    def basis_per_share(self) -> float:
        return self.total_cost / self.shares if self.shares > _EPS else 0.0

    @property
    def holding_start(self) -> pd.Timestamp:
        return self.acquired - pd.Timedelta(days=self.holding_credit_days)

    def is_long_term(self, sold: pd.Timestamp) -> bool:
        # IRS long-term treatment requires MORE than one year, not >=365 days.
        return sold > self.holding_start + pd.DateOffset(years=1)


@dataclass(frozen=True)
class TaxSettlement:
    year: int
    tax: float
    short_gain: float
    long_gain: float
    interest: float
    qualified_dividends: float
    nonqualified_dividends: float
    carry_short: float
    carry_long: float
    asof: pd.Timestamp
    raw_short_gain: float = 0.0
    raw_long_gain: float = 0.0


@dataclass
class _Realization:
    date: pd.Timestamp
    security_id: str
    shares: float
    original_gain: float
    recognized_gain: float
    long_term: bool
    holding_days: int
    transaction: dict
    fragment: dict = field(default_factory=dict)


@dataclass
class _PendingLoss:
    realization: _Realization
    remaining_shares: float
    loss_per_share: float


class TaxLedger:
    """FIFO lots, same-account wash adjustments, and continuous annual taxes.

    ``carry`` is a tuple of signed, nonpositive (short, long) loss carryforwards.
    Settlement gain fields are taxable gains after carry and category netting;
    ``raw_*_gain`` fields preserve the year's recognized realization sums.
    Costs and proceeds include any trading costs supplied by the caller. The
    caller pays ``settlement.tax`` from portfolio cash; this ledger never invents
    a tax payment or a position sale. Calls must arrive chronologically.
    """

    def __init__(self, rates: TaxRates = TaxRates(), *, canonical_quantities: bool = False):
        """Optionally make FIFO lots the authoritative fractional quantity.

        ``canonical_quantities`` is for the crypto research integration, where
        low prices can produce billions of units and repeated partial trades.
        It sums lots accurately, requires caller quantities never exceed that
        exact represented position, and consumes all lots on an exact full
        liquidation. Stock callers retain the existing default behavior.
        """
        if not isinstance(canonical_quantities, bool):
            raise ValueError("canonical_quantities must be boolean")
        self.rates = rates
        self.canonical_quantities = canonical_quantities
        self.lots: dict[str, list[TaxLot]] = {}
        self.transactions: list[dict] = []
        self.settlements: list[TaxSettlement] = []
        self.carry: tuple[float, float] = (0.0, 0.0)
        self._realizations: list[_Realization] = []
        self._pending: list[_PendingLoss] = []
        self._next_lot = 1
        self._last_date: pd.Timestamp | None = None
        self._finalized = False

    def _advance(self, date: Any) -> pd.Timestamp:
        date = _date(date)
        if self._finalized:
            raise ValueError("ledger is closed after a final settlement")
        if self._last_date is not None and date < self._last_date:
            raise ValueError("tax ledger events must be chronological")
        self._last_date = date
        self._pending = [p for p in self._pending
                         if p.remaining_shares > _EPS
                         and date <= p.realization.date + pd.Timedelta(days=30)]
        return date

    def _lot(self, security_id, date, shares, cost, credit=0, available=True):
        lot = TaxLot(self._next_lot, str(security_id), date, shares, cost, credit, available)
        self._next_lot += 1
        return lot

    def position(self, security_id: str) -> float:
        quantities = [lot.shares for lot in self.lots.get(str(security_id), [])]
        return math.fsum(quantities) if self.canonical_quantities else sum(quantities)

    @staticmethod
    def _refresh(record: dict):
        fragments = record["realizations"]
        record["gain"] = sum(f["recognized_gain"] for f in fragments)
        record["recognized_gain"] = record["gain"]
        record["short_gain"] = sum(f["recognized_gain"] for f in fragments if not f["long_term"])
        record["long_gain"] = sum(f["recognized_gain"] for f in fragments if f["long_term"])
        record["wash_disallowed"] = record["gain"] - record["original_gain"]

    def _assign_replacement(self, lot: TaxLot, shares: float, pending: _PendingLoss,
                            date: pd.Timestamp) -> TaxLot | None:
        """Assign shares to one loss, splitting a partially matched FIFO lot."""
        shares = min(shares, lot.shares, pending.remaining_shares)
        original_shares, original_cost = lot.shares, lot.total_cost
        remainder = None
        if shares < original_shares - _EPS:
            remainder = self._lot(lot.security_id, lot.acquired, original_shares - shares,
                                  original_cost * (1 - shares / original_shares),
                                  lot.holding_credit_days, lot.replacement_available)
            entries = self.lots[lot.security_id]
            entries.insert(entries.index(lot) + 1, remainder)
        lot.shares = shares
        deferred = shares * pending.loss_per_share
        lot.total_cost = original_cost * shares / original_shares + deferred
        lot.holding_credit_days += pending.realization.holding_days
        lot.replacement_available = False
        pending.remaining_shares = max(0.0, pending.remaining_shares - shares)
        realization = pending.realization
        realization.recognized_gain += deferred
        # The externally visible sale fragment must change too, including when
        # replacement happens next year and revises the preceding year's loss.
        realization.fragment["recognized_gain"] = realization.recognized_gain
        realization.fragment["wash_disallowed"] += deferred
        self._refresh(realization.transaction)
        self.transactions.append({
            "type": "wash_adjustment", "date": date,
            "security_id": lot.security_id, "sale_date": realization.date,
            "replacement_date": lot.acquired, "lot_id": lot.lot_id,
            "shares": shares, "deferred_loss": deferred,
            "holding_credit_days": realization.holding_days,
        })
        return remainder

    def buy(self, security_id: str, date: Any, shares: float, total_cost: float) -> TaxLot:
        """Buy shares and return the first FIFO lot (wash matching can split it)."""
        shares = _amount(shares, "shares", positive=True)
        total_cost = _amount(total_cost, "total_cost")
        date = self._advance(date)
        security_id = str(security_id)
        lot = self._lot(security_id, date, shares, total_cost)
        self.lots.setdefault(security_id, []).append(lot)
        self.transactions.append({"type": "buy", "date": date,
                                  "security_id": security_id, "shares": shares,
                                  "total_cost": total_cost, "lot_id": lot.lot_id})
        remaining = lot
        for pending in list(self._pending):
            if remaining is None:
                break
            if (pending.realization.security_id == security_id
                    and pending.remaining_shares > _EPS
                    and pending.realization.date <= date
                    <= pending.realization.date + pd.Timedelta(days=30)):
                remaining = self._assign_replacement(
                    remaining, min(remaining.shares, pending.remaining_shares), pending, date)
        self._pending = [p for p in self._pending if p.remaining_shares > _EPS]
        return lot

    def sell(self, security_id: str, date: Any, shares: float,
             total_proceeds: float, reason: str = "signal") -> float:
        """Sell FIFO shares; return recognized gain known at this sale time.

        A later replacement purchase can increase the sale record's recognized
        gain by deferring a loss; callers should use settlement totals for taxes.
        """
        shares = _amount(shares, "shares", positive=True)
        total_proceeds = _amount(total_proceeds, "total_proceeds")
        security_id = str(security_id)
        position = self.position(security_id)
        if shares > position + (0.0 if self.canonical_quantities else _EPS):
            raise ValueError(f"sale exceeds position in {security_id}")
        full_liquidation = self.canonical_quantities and shares == position
        date = self._advance(date)
        record = {"type": "sell", "date": date, "security_id": security_id,
                  "shares": shares, "total_proceeds": total_proceeds,
                  "reason": reason, "original_gain": 0.0, "realizations": []}
        self.transactions.append(record)
        remaining = shares
        losses = []
        entries = self.lots.get(security_id, [])
        available = list(entries)
        assigned_proceeds = 0.0
        for i, lot in enumerate(available):
            if remaining <= _EPS and not full_liquidation:
                break
            quantity = lot.shares if full_liquidation else min(lot.shares, remaining)
            basis = lot.total_cost if full_liquidation else lot.total_cost * quantity / lot.shares
            # An exact full sale closes every lot even if subtracting many
            # quantities leaves a floating residue. Assign its last proceeds
            # fragment by remainder so actual sale cash is conserved exactly.
            proceeds = (total_proceeds - assigned_proceeds
                        if full_liquidation and i == len(available) - 1
                        else total_proceeds * quantity / shares)
            assigned_proceeds += proceeds
            gain = proceeds - basis
            holding_days = int((date - lot.acquired).days) + lot.holding_credit_days
            realization = _Realization(date, security_id, quantity, gain, gain,
                                       lot.is_long_term(date), holding_days, record)
            self._realizations.append(realization)
            realization.fragment = {
                "lot_id": lot.lot_id, "shares": quantity, "basis": basis,
                "original_gain": gain, "recognized_gain": gain,
                "long_term": realization.long_term, "wash_disallowed": 0.0,
            }
            record["realizations"].append(realization.fragment)
            record["original_gain"] += gain
            lot.shares -= quantity
            lot.total_cost -= basis
            remaining -= quantity
            if lot.shares <= _EPS:
                entries.remove(lot)
            if gain < -_EPS:
                losses.append(_PendingLoss(realization, quantity, -gain / quantity))
        # Remove ALL sold shares first: shares just disposed of cannot also be
        # replacement shares held after this sale.
        for pending in losses:
            for lot in list(entries):
                if pending.remaining_shares <= _EPS:
                    break
                if (lot.replacement_available
                        and date - pd.Timedelta(days=30) <= lot.acquired <= date):
                    self._assign_replacement(
                        lot, min(lot.shares, pending.remaining_shares), pending, date)
            if pending.remaining_shares > _EPS:
                self._pending.append(pending)
        self._refresh(record)
        return record["recognized_gain"]

    def record_interest(self, date: Any, amount: float):
        amount = _amount(amount, "interest")
        date = self._advance(date)
        self.transactions.append({"type": "interest", "date": date, "amount": amount})

    def record_dividend(self, date: Any, amount: float, qualified_fraction: float = 0):
        amount = _amount(amount, "dividend")
        fraction = _amount(qualified_fraction, "qualified_fraction")
        if fraction > 1:
            raise ValueError("qualified_fraction must be between zero and one")
        date = self._advance(date)
        self.transactions.append({"type": "dividend", "date": date, "amount": amount,
                                  "qualified_fraction": fraction})

    def settle_year(self, year: int, asof: Any, allow_final: bool = False) -> TaxSettlement:
        """Settle one year after its wash window; never offset ordinary income.

        ``allow_final`` permits a terminal, earlier settlement, but closes the
        ledger so later purchases cannot invalidate its wash-sale assumption.
        Additional final years may be settled at the identical terminal as-of.
        """
        if int(year) != year:
            raise ValueError("year must be an integer")
        year = int(year)
        asof = _date(asof)
        if any(s.year == year for s in self.settlements):
            raise ValueError(f"tax year {year} is already settled")
        if self.settlements and year < self.settlements[-1].year:
            raise ValueError("tax years must be settled in chronological order")
        settled_years = {s.year for s in self.settlements}
        if any(t["date"].year < year and t["date"].year not in settled_years
               for t in self.transactions if t["type"] in {"sell", "interest", "dividend"}):
            raise ValueError("settle earlier activity years before carrying losses forward")
        if asof.year < year:
            raise ValueError("cannot settle a future tax year")
        if not allow_final and asof < pd.Timestamp(year=year + 1, month=1, day=31):
            raise ValueError("annual settlement requires January 31 after the wash-sale window")
        if self._finalized:
            if not allow_final or asof != self._last_date:
                raise ValueError("ledger is closed after a final settlement")
        else:
            asof = self._advance(asof)
        raw_short = sum(r.recognized_gain for r in self._realizations
                        if r.date.year == year and not r.long_term)
        raw_long = sum(r.recognized_gain for r in self._realizations
                       if r.date.year == year and r.long_term)
        short, long = raw_short + self.carry[0], raw_long + self.carry[1]
        if short * long < 0:
            offset = min(abs(short), abs(long))
            short += offset if short < 0 else -offset
            long += offset if long < 0 else -offset
        carry_short, carry_long = min(short, 0.0), min(long, 0.0)
        taxable_short, taxable_long = max(short, 0.0), max(long, 0.0)
        interest = sum(t["amount"] for t in self.transactions
                       if t["type"] == "interest" and t["date"].year == year)
        dividends = [t for t in self.transactions
                     if t["type"] == "dividend" and t["date"].year == year]
        qualified = sum(t["amount"] * t["qualified_fraction"] for t in dividends)
        nonqualified = sum(t["amount"] * (1 - t["qualified_fraction"]) for t in dividends)
        tax = (taxable_short * self.rates.short_term + taxable_long * self.rates.long_term
               + (interest + nonqualified) * self.rates.ordinary
               + qualified * self.rates.qualified_dividend)
        result = TaxSettlement(year, tax, taxable_short, taxable_long, interest,
                               qualified, nonqualified, carry_short, carry_long,
                               asof, raw_short, raw_long)
        self.carry = (carry_short, carry_long)
        self.settlements.append(result)
        self.transactions.append({"type": "tax_settlement", "date": asof,
                                  "year": year, "tax": tax,
                                  "carry_short": carry_short, "carry_long": carry_long})
        self._finalized = allow_final
        return result
