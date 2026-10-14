from __future__ import annotations

from pathlib import Path
import uuid

from .common import TradingError, number, stamp
from .journal import Journal
from .planner import validate_plan


def execute_shadow(plan: dict, fills: dict, journal: Journal, now: str, stop_file: str | Path) -> dict:
    """Offline simulation only: journal intents before fake transport/fills, never calls a broker."""
    validate_plan(plan)
    if Path(stop_file).exists():
        raise TradingError("STOP blocks new shadow order activity")
    if stamp(fills["timestamp"]) != stamp(plan["scheduled_open"]):
        raise TradingError("Shadow fills must be from the exact next-session open")
    journal.prepare(plan, now)
    observations = []
    for order in plan["orders"]:
        if Path(stop_file).exists():
            raise TradingError("STOP appeared during execution; remaining intents were not attempted")
        existing = journal.get(order["ref_id"])
        if existing["state"] != "INTENT":
            continue  # Existing unknown/partial/pending/terminal intent is never blindly re-submitted.
        payload = journal.begin_attempt(order["ref_id"])
        price = number(fills["open_prices"][payload["symbol"]])
        if price <= 0:
            raise TradingError("Positive synthetic/open fill price required")
        broker_id = str(uuid.uuid5(uuid.UUID(payload["ref_id"]), "shadow-order"))
        journal.acknowledge(payload["ref_id"], broker_id=broker_id)
        slot = journal.ledger(payload["account_number"])
        affordable = payload["side"] != "buy" or price * number(payload["quantity"]) <= number(slot["slot_cash"][payload["symbol"]])
        observed = {**payload, "id": broker_id, "state": "filled" if affordable else "rejected",
                    "cumulative_quantity": payload["quantity"] if affordable else "0",
                    "average_price": str(price) if affordable else None, "fees": "0", "trigger": "immediate",
                    "executions": [{"id": str(uuid.uuid5(uuid.UUID(broker_id), "fill")), "price": str(price),
                                    "quantity": payload["quantity"], "fees": "0", "timestamp": fills["timestamp"]}] if affordable else []}
        journal.reconcile(plan["account_number"], [observed])
        observations.append(observed)
    return {"version": 1, "mode": "SHADOW", "plan_sha256": plan["plan_sha256"], "simulated_fill_time": fills["timestamp"],
            "observations": observations, **journal.ledger(plan["account_number"])}
