"""Schema-aligned read adapter, injected transport only; no placement method.

Source: enabled official Robinhood tool declarations inspected 2026-10-14 UTC.
No credentials, account discovery, broker calls or plugin installation occur on import.
Trade approval response fields are not published by the current tool declaration:
get_trade_approvals therefore preserves its response rather than inventing a parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .common import TradingError, digest, iso, number, quantity, stamp, symbol

Transport = Callable[[str, dict[str, Any]], Mapping[str, Any]]
PREFIX = "mcp__codex_apps__robinhood_"


@dataclass(frozen=True)
class Account:
    account_number: str
    agentic_allowed: bool
    state: str
    type: str
    brokerage_account_type: str
    deactivated: bool
    permanently_deactivated: bool

    @classmethod
    def parse(cls, record):
        return cls(**{key: record[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Portfolio:
    buying_power: str
    unleveraged_buying_power: str
    currency: str
    cash: str

    @classmethod
    def parse(cls, record):
        power = record.get("buying_power")
        if not power:
            raise TradingError("Authoritative buying power missing")
        if power["display_currency"] != "USD" or record["currency"] != "USD":
            raise TradingError("Only USD stock portfolios supported")
        for field in (power["buying_power"], power["unleveraged_buying_power"], record["cash"]):
            number(field, nonnegative=False)
        return cls(power["buying_power"], power["unleveraged_buying_power"], record["currency"], record["cash"])


@dataclass(frozen=True)
class Position:
    symbol: str
    quantity: str
    shares_available_for_sells: str
    shares_held_for_sells: str
    type: str

    @classmethod
    def parse(cls, record):
        symbol(record["symbol"])
        number(record["quantity"], nonnegative=False)
        number(record["shares_available_for_sells"])
        number(record["shares_held_for_sells"])
        return cls(**{key: record[key] for key in cls.__dataclass_fields__})


@dataclass(frozen=True)
class TradeApprovalSetting:
    account_number: str
    human_must_approve_trades: bool
    updated_at: str | None

    @classmethod
    def parse(cls, record, requested_account):
        if record.get("account_number") != requested_account or type(record.get("human_must_approve_trades")) is not bool:
            raise TradingError("Approval setting account/boolean does not match documented response")
        updated = record.get("updated_at") or None
        if updated is not None:
            stamp(updated)
        return cls(requested_account, record["human_must_approve_trades"], updated)


@dataclass(frozen=True)
class HistoricalFetch:
    """Full raw responses plus exact requests; never silently remove invalid/null bars."""
    symbols: list[str]
    start_time: str
    end_time: str
    requests: list[dict]
    raw_responses: list[Mapping[str, Any]]

    def saved(self) -> dict:
        return {"version": 1, "symbols": self.symbols, "start_time": self.start_time, "end_time": self.end_time,
                "requests": self.requests, "raw_responses": self.raw_responses}


@dataclass(frozen=True)
class EquityOrderRequest:
    account_number: str
    symbol: str
    side: str
    quantity: str
    type: str = "market"
    market_hours: str = "regular_hours"
    time_in_force: str = "gfd"
    ref_id: str | None = None

    def parameters(self, *, review: bool = False) -> dict:
        symbol(self.symbol)
        quantity(self.quantity)
        if not self.account_number or self.side not in {"buy", "sell"}:
            raise TradingError("Account and valid order side required")
        if (self.type, self.market_hours, self.time_in_force) != ("market", "regular_hours", "gfd"):
            raise TradingError("Only frozen regular-hours market GFD policy supported")
        result = {name: value for name, value in self.__dict__.items() if value is not None}
        if review:
            result.pop("ref_id", None)  # Current review tool does not accept ref_id.
        return result


@dataclass(frozen=True)
class EquityOrder:
    id: str
    symbol: str
    side: str
    state: str
    quantity: str | None
    cumulative_quantity: str
    average_price: str | None
    fees: str
    ref_id: str | None
    type: str
    trigger: str
    market_hours: str
    time_in_force: str
    executions: list[dict]

    @classmethod
    def parse(cls, record):
        symbol(record["symbol"])
        number(record["cumulative_quantity"])
        return cls(**{name: record.get(name, [] if name == "executions" else None)
                      for name in cls.__dataclass_fields__})


@dataclass(frozen=True)
class Quote:
    symbol: str
    quote: dict
    official_close: dict | None

    @classmethod
    def parse(cls, record):
        quote = record.get("quote")
        if not quote or not quote.get("has_traded") or quote.get("state") != "active":
            raise TradingError("Quote missing, untraded or inactive")
        return cls(symbol(quote["symbol"]), quote, record.get("close"))


def response_data(response: Mapping[str, Any]) -> dict:
    if response.get("isError"):
        raise TradingError("Broker tool returned an error; response is retained privately by caller")
    candidate = response.get("structuredContent", response)
    if not isinstance(candidate, Mapping) or not isinstance(candidate.get("data"), Mapping):
        raise TradingError("Broker tool response lacks documented structured data")
    return dict(candidate["data"])


class RobinhoodReadAdapter:
    """Transport must be explicitly supplied; safe default has no connector transport."""
    def __init__(self, transport: Transport | None = None):
        self.transport = transport

    def _call(self, operation: str, parameters: dict) -> dict:
        if self.transport is None:
            raise TradingError("No Robinhood transport configured; this build is shadow-only")
        if operation not in {"get_accounts", "get_portfolio", "get_equity_positions", "get_equity_quotes", "get_equity_orders", "get_trade_approvals", "get_trade_approval_setting", "get_equity_historicals", "review_equity_order"}:
            raise TradingError("Adapter exposes only documented reads/review, never placement")
        return response_data(self.transport(PREFIX + operation, parameters))

    def accounts(self) -> list[Account]:
        return [Account.parse(r) for r in self._call("get_accounts", {})["accounts"] or [] if r]

    def portfolio(self, account: str) -> Portfolio:
        return Portfolio.parse(self._call("get_portfolio", {"account_number": account}))

    def _pages(self, operation: str, account: str, field: str, filters: dict | None = None) -> list[dict]:
        if not account:
            raise TradingError("Explicit account required")
        rows, cursor, seen = [], None, set()
        while True:
            args = {"account_number": account, **(filters or {})}
            if cursor:
                args["cursor"] = cursor
            data = self._call(operation, args)
            rows.extend(r for r in data.get(field) or [] if r)
            cursor = data.get("next")
            if not cursor:
                return rows
            if cursor in seen:
                raise TradingError("Broker repeated pagination cursor")
            seen.add(cursor)

    def positions(self, account: str) -> list[Position]:
        return [Position.parse(r) for r in self._pages("get_equity_positions", account, "positions")]

    def orders(self, account: str, **filters) -> list[EquityOrder]:
        allowed = {"agent_initiated", "created_at_gte", "order_id", "placed_agent", "state", "symbol"}
        if set(filters) - allowed:
            raise TradingError("Unsupported equity-order read filter")
        return [EquityOrder.parse(r) for r in self._pages("get_equity_orders", account, "orders", filters)]

    def quotes(self, symbols: list[str]) -> list[Quote]:
        # >20 silently loses closes in the official schema; chunk to retain close confirmations.
        results = []
        for start in range(0, len(symbols), 20):
            requested = [symbol(name) for name in symbols[start:start + 20]]
            data = self._call("get_equity_quotes", {"symbols": requested})
            if data.get("closes_error"):
                raise TradingError("Official settled close lookup unavailable")
            batch = [Quote.parse(r) for r in data.get("results") or [] if r]
            if {r.symbol for r in batch} != set(requested) or any(not r.official_close for r in batch):
                raise TradingError("Quote batch or official closes incomplete")
            results.extend(batch)
        return results

    def trade_approvals(self, account: str, *, approval_ids: list[str] | None = None, cursor: str | None = None) -> dict:
        args = {"account_number": account}
        if approval_ids is not None:
            if len(approval_ids) > 100:
                raise TradingError("At most 100 approval IDs per official tool call")
            args["approval_ids"] = approval_ids
        else:
            args["asset_class"] = "ASSET_CLASS_EQUITY"
            if cursor:
                args["cursor"] = cursor
        return self._call("get_trade_approvals", args)

    def historicals(self, symbols: list[str], *, start_time: str, end_time: str) -> HistoricalFetch:
        """Explicit daily/regular/split queries, <=10 symbols; retain each full raw response.

        No auto interval, default end time, timestamp guessing or price adjustment occurs.
        Oversized upstream ranges raise normally; caller must explicitly narrow the range.
        Normalization is a separate atomic validation stage so the original response is
        available even when an interpolated, null or invalid bar makes it unusable.
        """
        if not isinstance(start_time, str) or not isinstance(end_time, str):
            raise TradingError("Historical start/end must be explicit RFC3339 timestamps")
        start, end = iso(start_time), iso(end_time)
        if stamp(start) >= stamp(end):
            raise TradingError("Historical start must precede explicit end")
        names = [symbol(name) for name in symbols]
        if len(names) != len(set(names)):
            raise TradingError("Historical symbols must be unique")
        requests, responses = [], []
        for index in range(0, len(names), 10):
            parameters = {"symbols": names[index:index + 10], "start_time": start, "end_time": end,
                          "interval": "day", "bounds": "regular", "adjustment_type": "split"}
            if self.transport is None:
                raise TradingError("No Robinhood transport configured; this build is shadow-only")
            response = self.transport(PREFIX + "get_equity_historicals", parameters)
            response_data(response)  # Reject tool errors/missing structured data; keep successful payload verbatim.
            requests.append(parameters)
            responses.append(response)
        return HistoricalFetch(names, start, end, requests, responses)

    def trade_approval_setting(self, account: str) -> TradeApprovalSetting:
        if not account:
            raise TradingError("Explicit account required for approval setting")
        data = self._call("get_trade_approval_setting", {"account_number": account})
        return TradeApprovalSetting.parse(data["setting"], account)

    def saved_signal_data(self, history: HistoricalFetch, quotes: list[Quote], calendar, now: str, *, minimum_bars: int = 100) -> dict:
        """Normalize raw historicals and exact official closes, then run all signal guards.

        A last-trade historical close that differs from the official close is rejected;
        it is never repaired or replaced to manufacture agreement.
        """
        from .signals import compute_signals
        bars = normalise_historical_bars(history)
        if len(quotes) != len({quote.symbol for quote in quotes}) or {quote.symbol for quote in quotes} != set(history.symbols):
            raise TradingError("Official quote universe must match historical universe exactly")
        closes = {quote.symbol: quote.official_close for quote in quotes}
        market = {"interval": "day", "adjustment_type": "split", "bars": bars, "official_closes": closes,
                  "source": "Robinhood get_equity_historicals plus get_equity_quotes",
                  "raw_fetch_sha256": digest(history.saved())}
        compute_signals(market, calendar, now, history.symbols, minimum_bars)
        return market

    def review(self, request: EquityOrderRequest) -> dict:
        return self._call("review_equity_order", request.parameters(review=True))


def normalise_historical_bars(history: HistoricalFetch) -> dict[str, list[dict]]:
    """Strict, lossless-price normalization of documented actual `data.results[].bars`.

    UTC daily labels supply the session date (the actual tool labels daily bars at
    00:00Z); converting midnight labels to New York would incorrectly shift a day.
    Raw tool payloads remain in HistoricalFetch; this derived view does not fill gaps.
    """
    if len(history.requests) != len(history.raw_responses):
        raise TradingError("Historical request/response receipt count differs")
    outputs = {}
    for request, raw in zip(history.requests, history.raw_responses):
        if (request.get("interval"), request.get("bounds"), request.get("adjustment_type")) != ("day", "regular", "split"):
            raise TradingError("Historical receipt must pin day/regular/split")
        if request.get("start_time") != history.start_time or request.get("end_time") != history.end_time:
            raise TradingError("Historical receipt timestamp mismatch")
        data = response_data(raw)
        if data.get("not_found"):
            raise TradingError("Historical response includes unresolved securities")
        results = data.get("results")
        if not isinstance(results, list) or any(not isinstance(record, Mapping) for record in results):
            raise TradingError("Historical results contain null/malformed entries")
        names = [record.get("symbol") for record in results]
        if len(names) != len(set(names)) or set(names) != set(request["symbols"]):
            raise TradingError("Historical result symbols do not match the exact requested batch")
        for record in results:
            name = symbol(record["symbol"])
            if name in outputs or record.get("interval") != "day" or record.get("bounds") != "regular":
                raise TradingError("Historical symbols duplicate or interval/bounds differ")
            if record.get("adjustment_type", "split") != "split":
                raise TradingError("Historical response adjustment differs from split-only request")
            raw_bars = record.get("bars")
            if not isinstance(raw_bars, list) or not raw_bars:
                raise TradingError("Historical response has no complete bars")
            rows = []
            for bar in raw_bars:
                if not isinstance(bar, Mapping):
                    raise TradingError("Historical response contains a null/malformed bar")
                if bar.get("interpolated", False) is not False:
                    raise TradingError("Interpolated/unknown-quality bars are unusable for signals")
                if bar.get("session") != "reg":
                    raise TradingError("Historical bar must explicitly identify the regular session")
                begins = stamp(bar["begins_at"])
                if begins < stamp(history.start_time) or begins >= stamp(history.end_time):
                    raise TradingError("Historical bar lies outside the explicit requested interval")
                prices = {name: number(bar[name + "_price"]) for name in ("open", "high", "low", "close")}
                if any(value <= 0 for value in prices.values()) or prices["low"] > min(prices.values()) or prices["high"] < max(prices.values()):
                    raise TradingError("Historical bar has invalid OHLC range or nonpositive price")
                number(bar["volume"])
                rows.append({"date": begins.date().isoformat(), **{field: str(value) for field, value in prices.items()}})
            dates = [row["date"] for row in rows]
            if dates != sorted(set(dates)):
                raise TradingError("Historical bars must be unique and ascending")
            outputs[name] = rows
    if set(outputs) != set(history.symbols):
        raise TradingError("Historical receipt universe differs from requested universe")
    return outputs


def approval_requirement(preview: dict) -> str:
    """Actual current official review policy; no approval or placement is performed."""
    if not isinstance(preview.get("order_checks"), dict):
        raise TradingError("Missing current broker order checks")
    if preview["order_checks"]:
        return "EXPLICIT_CONFIRMATION_AFTER_BROKER_ALERTS_AND_DISCLOSURE"
    if preview.get("customer_approval_required") is True:
        return "CUSTOMER_APPROVAL_IN_ROBINHOOD_APP"
    return "EXPLICIT_CONFIRMATION_AFTER_PREVIEW_AND_DISCLOSURE"
