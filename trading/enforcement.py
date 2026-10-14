from __future__ import annotations

import re
from pathlib import Path

from .common import TradingError, stamp
from .journal import Journal
from .planner import validate_manifest, validate_plan

OPERATIONS = {"get_accounts", "get_portfolio", "get_equity_positions", "get_equity_quotes", "get_equity_orders", "get_trade_approvals", "get_trade_approval_setting", "get_equity_historicals", "review_equity_order", "place_equity_order", "cancel_equity_order", "decline_trade_approval"}


def normalize_tool_name(value: str) -> str:
    """Recognize exact Robinhood operation suffixes across connector naming wrappers."""
    text = value.lower().replace(".", "_").replace("/", "_").replace(":", "_")
    for operation in OPERATIONS:
        if text == operation or text.endswith("robinhood_" + operation):
            return operation
    raise TradingError("Unsupported broker tool")


def check_payload_against_plan(plan: dict, request: dict, now: str) -> dict:
    validate_plan(plan)
    if request.get("plan_sha256") != plan["plan_sha256"] or request.get("asof") != plan["asof"]:
        raise TradingError("Enforcement request plan hash/as-of mismatch")
    if stamp(now) < stamp(plan["created_at"]) or stamp(now) >= stamp(plan["expires_at"]):
        raise TradingError("Plan is stale or expired at the exact next session open")
    args = request.get("arguments")
    if not isinstance(args, dict):
        raise TradingError("Tool arguments required")
    operation = normalize_tool_name(request["tool_name"])
    if operation == "review_equity_order":
        candidates = [{key: value for key, value in row.items() if key != "ref_id"} for row in plan["orders"]]
    elif operation == "place_equity_order":
        candidates = plan["orders"]
    else:
        raise TradingError("Payload-plan check only supports equity preview/place")
    if args not in candidates:
        raise TradingError("Account/symbol/side/quantity/order parameters differ from the hashed plan")
    return args


def authorize(request: dict, config: dict, plan: dict, manifest: dict, journal: Journal, now: str, stop_file: str | Path) -> dict:
    """Side-effect-free hook. Live placement is unavailable in this shadow-only build."""
    operation = normalize_tool_name(request["tool_name"])
    args = request.get("arguments", {})
    account = config.get("account_number")
    if operation in {"cancel_equity_order", "decline_trade_approval"}:
        key = "order_id" if operation == "cancel_equity_order" else "approval_id"
        if set(args) != {"account_number", key} or args.get("account_number") != account:
            raise TradingError("Cancellation/decline must target the configured account exactly")
        if not journal.owns(account, args[key], approval=key == "approval_id"):
            raise TradingError("Cancellation/decline ID is not known to this strategy journal")
        # STOP leaves a route for a future connected runner to reduce existing owned exposure.
        return {"allowed": True, "operation": operation, "scope": "known_owned_id_only", "transport_connected": False}
    if operation in {"review_equity_order", "place_equity_order"}:
        if Path(stop_file).exists():
            raise TradingError("STOP blocks all new order reviews/proposals/placements")
        check_payload_against_plan(plan, request, now)
        if manifest["manifest_sha256"] != plan["manifest_sha256"]:
            raise TradingError("Plan does not match frozen whitelist")
        validate_manifest(manifest, live=True)
        if config.get("mode") != "LIVE" or not account or config.get("budget_usd") is None:
            raise TradingError("Explicit LIVE account and strategy budget are not activated")
        # Deliberate hard block: installing a hook does not authorize financial transactions.
        raise TradingError("Live write transport and activation are not implemented; this build is shadow-only")
    if operation == "get_accounts":
        if args:
            raise TradingError("get_accounts takes no parameters")
    elif operation in {"get_equity_quotes", "get_equity_historicals"}:
        permitted = {"symbols"} if operation == "get_equity_quotes" else {"symbols", "start_time", "end_time", "interval", "bounds", "adjustment_type"}
        if set(args) != permitted or not set(args["symbols"]).issubset(set(manifest["symbols"])):
            raise TradingError("Market-data reads must remain in configured whitelist")
        if operation == "get_equity_historicals":
            if (args["interval"], args["bounds"], args["adjustment_type"]) != ("day", "regular", "split") or stamp(args["start_time"]) >= stamp(args["end_time"]):
                raise TradingError("Historical reads require explicit day/regular/split timestamp range")
    elif args.get("account_number") != account:
        raise TradingError("Broker reads must use the explicit configured account")
    return {"allowed": True, "operation": operation, "transport_connected": False}
