from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from .common import TradingError, canonical_json, number, private_dir, stamp
from .planner import OPEN_STATES, validate_plan

FINAL_STATES = {"filled", "cancelled", "rejected", "failed", "voided", "partially_filled_rest_cancelled", "locate_failed", "declined", "expired"}


@contextmanager
def run_lock(folder: str | Path):
    """Process-wide advisory lock released by the OS on crashes; never delete a live lock."""
    location = private_dir(folder) / "run.lock"
    fd = os.open(location, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise TradingError("Another trading run holds the lock") from exc
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise TradingError("Another trading run holds the lock") from exc
        yield
    finally:
        os.close(fd)


class Journal:
    def __init__(self, path: str | Path):
        location = Path(path)
        private_dir(location.parent)
        self.db = sqlite3.connect(location, timeout=0, isolation_level=None)
        os.chmod(location, 0o600)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
          CREATE TABLE IF NOT EXISTS intents (
            ref_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, payload TEXT NOT NULL,
            state TEXT NOT NULL, broker_id TEXT, approval_id TEXT,
            filled TEXT NOT NULL DEFAULT '0', notional TEXT NOT NULL DEFAULT '0', fees TEXT NOT NULL DEFAULT '0');
          CREATE TABLE IF NOT EXISTS slots (
            account TEXT NOT NULL, symbol TEXT NOT NULL, cash TEXT NOT NULL, quantity TEXT NOT NULL,
            PRIMARY KEY(account,symbol));
          CREATE TABLE IF NOT EXISTS receipts (
            execution_id TEXT PRIMARY KEY, ref_id TEXT NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def prepare(self, plan: dict, now: str) -> None:
        validate_plan(plan)
        if stamp(now) >= stamp(plan["expires_at"]) or stamp(now) < stamp(plan["created_at"]):
            raise TradingError("Only a current pre-open plan may create intents")
        with self.transaction():
            already_seen = bool(plan["orders"]) and all(self.get(order["ref_id"]) and self.get(order["ref_id"])["plan_hash"] == plan["plan_sha256"] for order in plan["orders"])
            for ticker in plan["symbols"]:
                cash, held = str(plan["slot_cash"][ticker]), str(plan["strategy_inventory"][ticker])
                existing = self.db.execute("SELECT cash,quantity FROM slots WHERE account=? AND symbol=?", (plan["account_number"], ticker)).fetchone()
                if existing and not already_seen and (number(existing["cash"]) != number(cash) or number(existing["quantity"]) != number(held)):
                    raise TradingError("Plan ledger differs from journal; reconcile and rebuild plan")
                self.db.execute("INSERT OR IGNORE INTO slots VALUES(?,?,?,?)", (plan["account_number"], ticker, cash, held))
            for order in plan["orders"]:
                existing = self.get(order["ref_id"])
                if existing and existing["payload"] != canonical_json(order):
                    raise TradingError("Logical ref_id cannot be reused with different parameters")
                import json
                unresolved = self.db.execute("SELECT * FROM intents WHERE state NOT IN ('filled','cancelled','rejected','failed','voided','partially_filled_rest_cancelled','locate_failed','declined','expired')").fetchall()
                for row in unresolved:
                    old = json.loads(row["payload"])
                    if row["ref_id"] != order["ref_id"] and old["account_number"] == order["account_number"] and old["symbol"] == order["symbol"]:
                        raise TradingError("A prior unresolved order blocks a new logical order")
                self.db.execute("INSERT OR IGNORE INTO intents(ref_id,plan_hash,payload,state) VALUES(?,?,?,?)",
                                (order["ref_id"], plan["plan_sha256"], canonical_json(order), "INTENT"))

    def get(self, ref_id: str):
        return self.db.execute("SELECT * FROM intents WHERE ref_id=?", (ref_id,)).fetchone()

    def begin_attempt(self, ref_id: str) -> dict:
        """Commit UNKNOWN before transport: timeout/crash must reconcile, never blindly retry."""
        import json
        with self.transaction():
            row = self.get(ref_id)
            if not row or row["state"] != "INTENT":
                raise TradingError("Existing outcome requires reconciliation; no automatic resubmission")
            self.db.execute("UPDATE intents SET state='UNKNOWN' WHERE ref_id=?", (ref_id,))
            return json.loads(row["payload"])

    def acknowledge(self, ref_id: str, *, broker_id: str | None = None, approval_id: str | None = None) -> None:
        if bool(broker_id) == bool(approval_id):
            raise TradingError("Acknowledgment needs exactly one broker or approval ID")
        with self.transaction():
            row = self.get(ref_id)
            if not row or row["state"] != "UNKNOWN":
                raise TradingError("Only a recorded unknown attempt may be acknowledged")
            self.db.execute("UPDATE intents SET broker_id=?,approval_id=?,state=? WHERE ref_id=?",
                            (broker_id, approval_id, "pending" if approval_id else "queued", ref_id))

    def reconcile(self, account: str, orders: list[dict], approvals: list[dict] = ()) -> int:
        """Apply monotonic cumulative fills exactly once, including fills racing cancellation."""
        import json
        count = 0
        with self.transaction():
            for observed in orders:
                ref = observed.get("ref_id")
                row = self.db.execute("SELECT * FROM intents WHERE ref_id=? OR broker_id=? OR approval_id=?",
                                      (ref, observed.get("id"), ref)).fetchone()
                if not row:
                    continue  # A broker's agent_initiated flag does not establish this strategy's ownership.
                payload = json.loads(row["payload"])
                if row["broker_id"] and row["broker_id"] != observed.get("id"):
                    raise TradingError("Broker returned another order ID for the same logical intent")
                if payload["account_number"] != account or observed.get("account_number", account) != account:
                    raise TradingError("Reconciliation account mismatch")
                if (observed.get("symbol") != payload["symbol"] or observed.get("side") != payload["side"]
                        or number(observed.get("quantity")) != number(payload["quantity"])
                        or observed.get("type") != payload["type"] or observed.get("market_hours") != payload["market_hours"]
                        or observed.get("time_in_force") != payload["time_in_force"] or observed.get("trigger", "immediate") != "immediate"):
                    raise TradingError("Broker observation differs from recorded intent")
                state = observed.get("state")
                if state not in OPEN_STATES | FINAL_STATES:
                    raise TradingError("Unknown broker lifecycle state")
                filled, previous = number(observed.get("cumulative_quantity", "0")), number(row["filled"])
                if filled < previous or filled > number(payload["quantity"]):
                    raise TradingError("Nonmonotonic or excessive cumulative fill")
                fees = number(observed.get("fees", "0"))
                if fees < number(row["fees"]):
                    raise TradingError("Nonmonotonic cumulative fees")
                price = number(observed.get("average_price") or "0")
                if filled and price <= 0:
                    raise TradingError("Filled order requires a positive average execution price")
                total_notional = filled * price
                delta, cash_delta = filled - previous, total_notional - number(row["notional"])
                if total_notional < number(row["notional"]):
                    raise TradingError("Nonmonotonic cumulative notional")
                if state == "filled" and filled != number(payload["quantity"]):
                    raise TradingError("Filled state must have complete cumulative quantity")
                if row["state"] in FINAL_STATES and state in OPEN_STATES:
                    raise TradingError("Terminal order cannot return to open state")
                slot = self.db.execute("SELECT * FROM slots WHERE account=? AND symbol=?", (account, payload["symbol"])).fetchone()
                if not slot:
                    raise TradingError("Order lacks initialized capital slot")
                sign = 1 if payload["side"] == "buy" else -1
                held = number(slot["quantity"]) + sign * delta
                cash = number(slot["cash"]) - sign * cash_delta - (fees - number(row["fees"]))
                if held < 0 or cash < 0:
                    raise TradingError("Fill violates slot cash/inventory; stop and investigate")
                self.db.execute("UPDATE slots SET cash=?,quantity=? WHERE account=? AND symbol=?", (str(cash), str(held), account, payload["symbol"]))
                self.db.execute("UPDATE intents SET state=?,broker_id=?,filled=?,notional=?,fees=? WHERE ref_id=?",
                                (state, observed["id"], str(filled), str(total_notional), str(fees), row["ref_id"]))
                for receipt in observed.get("executions") or []:
                    existing = self.db.execute("SELECT ref_id FROM receipts WHERE execution_id=?", (receipt["id"],)).fetchone()
                    if existing and existing["ref_id"] != row["ref_id"]:
                        raise TradingError("Execution ID reused by another logical order")
                    self.db.execute("INSERT OR IGNORE INTO receipts VALUES(?,?)", (receipt["id"], row["ref_id"]))
                count += 1
            for approval in approvals:
                row = self.db.execute("SELECT * FROM intents WHERE approval_id=?", (approval.get("approval_id"),)).fetchone()
                if not row:
                    continue
                payload = json.loads(row["payload"])
                if payload["account_number"] != account or approval.get("account_number", account) != account:
                    raise TradingError("Approval account mismatch")
                state = approval.get("state")
                if state not in {"pending", "approved", "auto-approved", "declined", "expired"}:
                    raise TradingError("Unknown trade approval state")
                if row["broker_id"] or row["state"] in FINAL_STATES:
                    continue  # Broker order/fill state is authoritative once the approval becomes an order.
                # Approved is not a fill: order reads must locate the resulting order (its ref_id may be approval_id).
                self.db.execute("UPDATE intents SET state=? WHERE ref_id=?", (state, row["ref_id"]))
                count += 1
        return count

    def owns(self, account: str, identifier: str, approval: bool = False) -> bool:
        import json
        field = "approval_id" if approval else "broker_id"
        rows = self.db.execute(f"SELECT payload FROM intents WHERE {field}=?", (identifier,)).fetchall()
        return any(json.loads(row["payload"])["account_number"] == account for row in rows)

    def ledger(self, account: str) -> dict:
        rows = self.db.execute("SELECT * FROM slots WHERE account=? ORDER BY symbol", (account,)).fetchall()
        return {"slot_cash": {r["symbol"]: r["cash"] for r in rows}, "strategy_inventory": {r["symbol"]: r["quantity"] for r in rows}}
