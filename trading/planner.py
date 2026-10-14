from __future__ import annotations

from decimal import ROUND_FLOOR
import uuid

from analysis_2026.moneyline_ref import MONEYLINE_PARAMS
from .calendar import SavedCalendar
from .common import TradingError, digest, iso, number, quantity, stamp, symbol

OPEN_STATES = {"new", "queued", "confirmed", "unconfirmed", "partially_filled", "pending_cancelled", "locating"}
PENDING_APPROVAL_STATES = {"pending", "approved", "auto-approved"}
NAMESPACE = uuid.UUID("fc4b2341-fc25-4d9f-b61f-2f0795e8bf1c")


def freeze_manifest(value: dict) -> dict:
    result = dict(value)
    result.pop("manifest_sha256", None)
    result["manifest_sha256"] = digest(result)
    return result


def validate_manifest(value: dict, *, live: bool = False) -> list[str]:
    body = dict(value)
    supplied = body.pop("manifest_sha256", None)
    if supplied != digest(body):
        raise TradingError("Whitelist manifest hash mismatch")
    if value.get("version") != 1 or value.get("cadence") != "daily" or value.get("signal_params") != MONEYLINE_PARAMS:
        raise TradingError("Unsupported frozen signal or whitelist version")
    iso(value["frozen_at"])
    names = value.get("symbols")
    if not isinstance(names, list) or len(names) != len(set(names)):
        raise TradingError("Whitelist symbols must be a unique list")
    for name in names:
        symbol(name)
    verdict = value.get("research_verdict", {})
    if verdict.get("status") not in {"PASS", "RESEARCH_ONLY", "FAIL", "NOT_EVALUATED"}:
        raise TradingError("Missing explicit research verdict")
    if live and (not names or verdict.get("status") != "PASS" or not verdict.get("report_sha256")
                 or verdict.get("limitations")):
        raise TradingError("LIVE requires a nonempty frozen whitelist and passing validation with no unresolved limitations")
    return names


def validate_plan(plan: dict) -> None:
    body = dict(plan)
    supplied = body.pop("plan_sha256", None)
    if supplied != digest(body):
        raise TradingError("Plan hash mismatch")
    if plan.get("mode") != "SHADOW" or plan.get("version") != 1:
        raise TradingError("Only shadow plans are supported by this implementation")
    if stamp(plan["expires_at"]) != stamp(plan["scheduled_open"]):
        raise TradingError("Plan must expire at the exact next session open")
    seen = set()
    for order in plan["orders"]:
        if set(order) != {"account_number", "symbol", "side", "quantity", "type", "market_hours", "time_in_force", "ref_id"}:
            raise TradingError("Unsupported order parameters")
        if order["account_number"] != plan["account_number"] or order["symbol"] not in plan["symbols"]:
            raise TradingError("Plan account/symbol mismatch")
        if order["side"] not in {"buy", "sell"} or order["type"] != "market" or order["market_hours"] != "regular_hours" or order["time_in_force"] != "gfd":
            raise TradingError("Order differs from frozen execution policy")
        quantity(order["quantity"])
        uuid.UUID(order["ref_id"])
        if order["ref_id"] in seen:
            raise TradingError("Duplicate logical order")
        seen.add(order["ref_id"])


def make_plan(config: dict, manifest: dict, signals: dict, snapshot: dict, calendar: SavedCalendar, now: str) -> dict:
    if config.get("mode") != "SHADOW":
        raise TradingError("LIVE activation is not implemented; no live submit command exists")
    names = validate_manifest(manifest)
    if config.get("cold_start") not in {"enter_current_green", "wait_for_next_green_flip"}:
        raise TradingError("Choose an explicit frozen cold-start convention")
    if config.get("slot_policy") != "fixed_equal_slots_no_redistribution":
        raise TradingError("Unsupported capital-slot policy")
    if signals.get("params") != MONEYLINE_PARAMS or signals.get("timeframe") != "daily":
        raise TradingError("Signals must use the exact frozen Moneyline reference")
    asof = calendar.latest_completed(now).date
    if signals.get("asof") != asof or snapshot.get("asof") != asof:
        raise TradingError("Signal and account snapshot must match the latest completed date")
    if set(signals.get("signals", {})) != set(names):
        raise TradingError("Signal universe must match the frozen whitelist exactly")
    account = config.get("account_number")
    if not isinstance(account, str) or not account or snapshot.get("account_number") != account:
        raise TradingError("An explicit configured account must match the saved snapshot")
    age = (stamp(now) - stamp(snapshot["captured_at"])).total_seconds()
    if age < 0 or age > int(config.get("max_snapshot_age_seconds", 300)):
        raise TradingError("Saved account snapshot is stale or from the future")
    if names and config.get("budget_usd") is None:
        raise TradingError("A stock budget must be explicitly configured; portfolio value is not a budget")
    budget = number(config.get("budget_usd") or "0")
    if names and budget <= 0:
        raise TradingError("Nonempty strategy requires a positive explicitly configured budget")
    if snapshot.get("currency") != "USD":
        raise TradingError("USD stock account snapshot required")
    spendable = min(number(snapshot["buying_power"]), number(snapshot["unleveraged_buying_power"]))
    initial = bool(snapshot.get("cold_start", False))
    slots = snapshot.get("slot_cash", {})
    inventory = snapshot.get("strategy_inventory", {})
    if not initial and (set(slots) != set(names) or set(inventory) != set(names)):
        raise TradingError("Established strategy requires explicit per-slot cash and owned inventory")
    positions = {}
    for row in snapshot.get("positions", []):
        ticker = symbol(row["symbol"])
        if ticker in positions or row.get("type", "long") not in {"long", "empty"}:
            raise TradingError("Duplicate or unsupported short/boxed position")
        positions[ticker] = row
    if initial:
        if any(number(positions.get(name, {}).get("quantity", "0")) != 0 for name in names):
            raise TradingError("Cold start requires no existing whitelist holdings; establish explicit strategy ownership first")
        slots = {name: str(budget / len(names)) for name in names} if names else {}
        inventory = {name: "0" for name in names}
    if initial and sum(number(v) for v in slots.values()) > budget:
        raise TradingError("Slot cash exceeds the explicit total strategy budget")
    buffer = number(config.get("buy_price_buffer_fraction", "0.02"))
    if buffer > number("0.20"):
        raise TradingError("Unexpected sizing buffer")
    next_session = calendar.next_session(asof)
    if stamp(now) >= stamp(next_session.open):
        raise TradingError("Next-open plan is already expired; do not trade a stale decision")
    for row in snapshot.get("orders", []):
        if row.get("account_number", account) != account or row.get("state") not in OPEN_STATES | {"filled", "cancelled", "rejected", "failed", "voided", "partially_filled_rest_cancelled", "locate_failed"}:
            raise TradingError("Saved order account or lifecycle state is unsupported")
    for row in snapshot.get("approvals", []):
        if row.get("account_number", account) != account or row.get("state") not in PENDING_APPROVAL_STATES | {"declined", "expired"}:
            raise TradingError("Saved approval account or lifecycle state is unsupported")
    notes, orders = [], []
    for ticker in names:
        state = signals["signals"][ticker]
        held = number(inventory.get(ticker, "0"))
        broker = positions.get(ticker, {"quantity": "0", "shares_available_for_sells": "0"})
        total = number(broker["quantity"])
        if held > total:
            raise TradingError("Owned inventory cannot exceed broker holdings")
        if ticker in snapshot.get("unresolved_symbols", []):
            notes.append({"symbol": ticker, "reason": "unresolved_intent_requires_reconciliation"})
            continue
        pending = [r for r in snapshot.get("approvals", []) if r.get("symbol") == ticker and r.get("state") in PENDING_APPROVAL_STATES]
        if any(r.get("side") == "buy" for r in snapshot.get("orders", []) if r.get("symbol") == ticker and r.get("state") in OPEN_STATES):
            notes.append({"symbol": ticker, "reason": "open_buy_requires_reconciliation"})
            continue
        buy = bool(state["green"]) and held == 0 and (state["flip"] == 1 or (initial and config["cold_start"] == "enter_current_green"))
        sell = not state["green"] and held > 0
        if not buy and not sell:
            continue
        if buy:
            if pending or any(r.get("symbol") == ticker and r.get("state") in OPEN_STATES for r in snapshot.get("orders", [])):
                notes.append({"symbol": ticker, "reason": "pending_activity_requires_reconciliation"})
                continue
            cash = number(slots[ticker])
            close = number(state["close"])
            if close <= 0:
                raise TradingError("Sizing price must be positive")
            count = int((min(cash, spendable) / (close * (1 + buffer))).to_integral_value(rounding=ROUND_FLOOR))
            spendable -= count * close * (1 + buffer)
            side = "buy"
        else:
            outstanding = sum(max(number(r["quantity"]) - number(r.get("cumulative_quantity", "0")), 0)
                              for r in snapshot.get("orders", []) if r.get("symbol") == ticker and r.get("side") == "sell" and r.get("state") in OPEN_STATES)
            proposals = sum(number(r["quantity"]) for r in pending if r.get("side") == "sell")
            # Broker sellable already subtracts broker holds: cap against total minus observed orders, rather than subtract twice.
            available = max(min(number(broker["shares_available_for_sells"]), total - outstanding) - proposals, 0)
            count = int(min(held, available).to_integral_value(rounding=ROUND_FLOOR))
            side = "sell"
        if count <= 0:
            notes.append({"symbol": ticker, "reason": "insufficient_unreserved_cash_or_whole_shares"})
            continue
        logical = {"account": account, "manifest": manifest["manifest_sha256"], "asof": asof,
                   "symbol": ticker, "side": side, "quantity": str(count)}
        ref = str(uuid.uuid5(NAMESPACE, digest(logical)))
        orders.append({"account_number": account, "symbol": ticker, "side": side, "quantity": str(count),
                       "type": "market", "market_hours": "regular_hours", "time_in_force": "gfd", "ref_id": ref})
    plan = {"version": 1, "mode": "SHADOW", "account_number": account, "asof": asof, "created_at": iso(now),
            "scheduled_open": next_session.open, "expires_at": next_session.open,
            "execution_policy": "record_before_next_open_simulate_at_exact_next_open_no_late_execution",
            "symbols": names, "budget_usd": str(budget), "slot_cash": slots, "strategy_inventory": inventory,
            "cold_start": config["cold_start"], "manifest_sha256": manifest["manifest_sha256"],
            "signals_sha256": digest(signals), "snapshot_sha256": digest(snapshot),
            "reference_sha256": signals["reference_sha256"], "orders": orders, "notes": notes}
    plan["plan_sha256"] = digest(plan)
    validate_plan(plan)
    return plan
