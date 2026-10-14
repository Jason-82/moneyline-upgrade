from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from analysis_2026.moneyline_ref import MONEYLINE_PARAMS
from .calendar import SavedCalendar
from .common import iso, private_json, stamp
from .planner import freeze_manifest


def create_demo(folder: str | Path) -> dict:
    """Explicit synthetic stocks and money; the exchange dates are real, prices are invented."""
    calendar = SavedCalendar.from_exchange("2024-01-02", "2024-10-01")
    history = calendar.sessions[:140]
    asof = history[-1]
    now = iso(stamp(asof.close) + timedelta(minutes=25))
    following = calendar.next_session(asof.date)
    names = ["DEMOA", "DEMOB", "DEMOC"]
    bars, official, prices = {}, {}, {}
    for index, ticker in enumerate(names):
        rows = []
        for i, day in enumerate(history):
            price = round((30 + 30 * index) * (1 + 0.002 * i), 4)
            rows.append({"date": day.date, "open": price, "high": round(price * 1.01, 4),
                         "low": round(price * 0.99, 4), "close": price})
        bars[ticker] = rows
        official[ticker] = {"date": asof.date, "price": str(rows[-1]["close"]), "interpolated": False, "source": "SYNTHETIC"}
        prices[ticker] = str(round(rows[-1]["close"] * 1.005, 4))
    config = {"mode": "SHADOW", "account_number": "SHADOW_DEMO_NO_REAL_ACCOUNT", "budget_usd": "30000",
              "cold_start": "enter_current_green", "slot_policy": "fixed_equal_slots_no_redistribution",
              "max_snapshot_age_seconds": 300, "buy_price_buffer_fraction": "0.02", "minimum_signal_bars": 100}
    manifest = freeze_manifest({"version": 1, "frozen_at": now, "cadence": "daily", "signal_params": MONEYLINE_PARAMS,
                                "symbols": names, "selection_rule": "synthetic demonstration only",
                                "research_verdict": {"status": "NOT_EVALUATED", "report_sha256": None,
                                                     "limitations": ["Invented example securities/prices; no performance validation"]}})
    inputs = {"now": now, "synthetic": True, "calendar": {"sessions": [r.__dict__ for r in calendar.sessions]},
              "market_data": {"interval": "day", "adjustment_type": "split", "bars": bars, "official_closes": official},
              "snapshot": {"account_number": config["account_number"], "asof": asof.date, "captured_at": now,
                           "currency": "USD", "buying_power": "30000", "unleveraged_buying_power": "30000", "cold_start": True,
                           "positions": [], "orders": [], "approvals": []},
              "fills": {"timestamp": following.open, "open_prices": prices}}
    out = Path(folder)
    private_json(out / "config.json", config)
    private_json(out / "manifest.json", manifest)
    private_json(out / "inputs.json", inputs)
    return {"config": config, "manifest": manifest, "inputs": inputs}
