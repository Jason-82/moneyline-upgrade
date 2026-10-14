from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .calendar import SavedCalendar
from .common import TradingError, private_json, read_json
from .enforcement import authorize
from .fixtures import create_demo
from .journal import Journal, run_lock
from .planner import make_plan, validate_manifest
from .shadow import execute_shadow
from .signals import compute_signals


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Moneyline deterministic SHADOW-only stock planner")
    parser.add_argument("command", choices=["signal", "plan", "shadow", "reconcile", "hook", "demo"])
    parser.add_argument("--config", default="config/trading_shadow.json")
    parser.add_argument("--manifest")
    parser.add_argument("--inputs")
    parser.add_argument("--plan")
    parser.add_argument("--observations")
    parser.add_argument("--request")
    parser.add_argument("--now", help="Timezone-aware UTC timestamp; defaults to wall-clock now except explicit synthetic demo")
    parser.add_argument("--output-dir", default=".private_trading")
    args = parser.parse_args(argv)
    folder = Path(args.output_dir)
    journal = None
    try:
        if args.command == "demo":
            with run_lock(folder):
                bundle = create_demo(folder)
                config, manifest, inputs = bundle["config"], bundle["manifest"], bundle["inputs"]
                now = inputs["now"]
                calendar = SavedCalendar(inputs["calendar"]["sessions"])
                signals = compute_signals(inputs["market_data"], calendar, now, manifest["symbols"])
                plan = make_plan(config, manifest, signals, inputs["snapshot"], calendar, now)
                private_json(folder / "signals.json", signals)
                private_json(folder / "plan.json", plan)
                journal = Journal(folder / "journal.sqlite3")
                result = execute_shadow(plan, inputs["fills"], journal, now, folder / "STOP")
                private_json(folder / "shadow_result.json", result)
            print(json.dumps({"mode": "SHADOW", "synthetic": True, "order_count": len(plan["orders"]), "asof": plan["asof"]}))
            return 0
        config = read_json(args.config)
        manifest = read_json(args.manifest or config["manifest_file"])
        inputs = read_json(args.inputs or config["inputs_file"])
        now = args.now or datetime.now(timezone.utc).isoformat()
        calendar = SavedCalendar(inputs["calendar"]["sessions"])
        with run_lock(folder):
            if args.command in {"signal", "plan"}:
                names = validate_manifest(manifest)
                signals = compute_signals(inputs["market_data"], calendar, now, names, config.get("minimum_signal_bars", 100))
                private_json(folder / "signals.json", signals)
                if args.command == "plan":
                    plan = make_plan(config, manifest, signals, inputs["snapshot"], calendar, now)
                    private_json(folder / "plan.json", plan)
                print(json.dumps({"mode": "SHADOW", "asof": signals["asof"], "symbol_count": len(names)}))
            else:
                journal = Journal(folder / "journal.sqlite3")
                if args.command == "reconcile":
                    observations = read_json(args.observations)
                    count = journal.reconcile(config["account_number"], observations.get("orders", []), observations.get("approvals", []))
                    private_json(folder / "ledger.json", journal.ledger(config["account_number"]))
                    print(json.dumps({"mode": "SHADOW", "reconciled_count": count}))
                else:
                    plan = read_json(args.plan or folder / "plan.json")
                    if args.command == "shadow":
                        result = execute_shadow(plan, inputs["fills"], journal, now, folder / "STOP")
                        private_json(folder / "shadow_result.json", result)
                        print(json.dumps({"mode": "SHADOW", "simulated_count": len(result["observations"])}))
                    else:
                        request = read_json(args.request) if args.request else json.load(sys.stdin)
                        print(json.dumps(authorize(request, config, plan, manifest, journal, now, folder / "STOP")))
        return 0
    except (TradingError, FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        # Never echo raw JSON, tool payloads, account numbers, secrets or broker errors into console logs.
        message = str(exc) if isinstance(exc, TradingError) else "Missing or malformed saved input; consult documented JSON contracts"
        print(json.dumps({"allowed": False, "error": message}), file=sys.stderr)
        return 2
    finally:
        if journal:
            journal.close()


if __name__ == "__main__":
    raise SystemExit(main())
