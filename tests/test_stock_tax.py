"""Tax accounting cases that affect continuous portfolio research returns."""
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from research.tax import TaxLedger, TaxRates


def sales(ledger):
    return [t for t in ledger.transactions if t["type"] == "sell"]


def test_fifo_partial_sale_preserves_remaining_basis():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.buy("ABC", "2024-02-10", 10, 2000)
    assert ledger.sell("ABC", "2024-03-20", 15, 2250) == pytest.approx(250)
    assert ledger.position("ABC") == pytest.approx(5)
    assert ledger.lots["ABC"][0].total_cost == pytest.approx(1000)
    assert [f["basis"] for f in sales(ledger)[0]["realizations"]] == pytest.approx([1000, 1000])
    assert [f["shares"] for f in sales(ledger)[0]["realizations"]] == pytest.approx([10, 5])


def test_future_wash_partial_replacements_and_calendar_day_boundary():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.sell("ABC", "2024-06-01", 10, 800)
    first = ledger.buy("ABC", "2024-06-30", 4, 360)
    second = ledger.buy("ABC", "2024-07-01", 2, 180)  # Exactly +30, included.
    third = ledger.buy("ABC", "2024-07-02", 4, 400)  # +31, excluded.
    assert sales(ledger)[0]["recognized_gain"] == pytest.approx(-80)
    assert sales(ledger)[0]["wash_disallowed"] == pytest.approx(120)
    assert (first.total_cost, second.total_cost, third.total_cost) == pytest.approx((440, 220, 400))
    assert first.holding_credit_days == 152
    settlement = ledger.settle_year(2024, "2025-01-31")
    assert settlement.carry_short == pytest.approx(-80)


def test_prior_replacement_matches_only_unsold_shares_and_tacks_holding():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    replacement = ledger.buy("ABC", "2024-06-01", 4, 360)
    assert ledger.sell("ABC", "2024-06-20", 10, 800) == pytest.approx(-120)
    assert replacement.total_cost == pytest.approx(440)
    assert replacement.holding_credit_days == 171
    assert ledger.position("ABC") == 4
    ledger.sell("ABC", "2025-01-02", 4, 500)
    assert sales(ledger)[-1]["long_gain"] == pytest.approx(60)
    ledger.settle_year(2024, "2025-01-31")
    settlement = ledger.settle_year(2025, "2026-01-31")
    assert settlement.tax == 0  # Prior short loss offsets this long gain.
    assert settlement.carry_short == pytest.approx(-60)


def test_partial_wash_splits_new_lot_without_spreading_loss_to_extra_shares():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.sell("ABC", "2024-06-01", 5, 400)
    ledger.buy("ABC", "2024-06-15", 10, 900)
    lots = ledger.lots["ABC"]
    assert [l.shares for l in lots] == [5, 5, 5]
    assert [l.total_cost for l in lots] == pytest.approx([500, 550, 450])
    assert [l.holding_credit_days for l in lots] == [0, 152, 0]
    assert [l.replacement_available for l in lots] == [True, False, True]
    assert sales(ledger)[0]["recognized_gain"] == pytest.approx(0)
    assert ledger.position("ABC") == 15
    # Audit records are flat serializable data, with no object cycles.
    json.dumps(ledger.transactions, default=str)


def test_cross_year_wash_adjusts_old_year_before_settlement():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-11-01", 10, 1000)
    ledger.sell("ABC", "2024-12-20", 10, 800)
    with pytest.raises(ValueError, match="January 31"):
        ledger.settle_year(2024, "2025-01-01")
    replacement = ledger.buy("ABC", "2025-01-10", 10, 900)
    assert replacement.total_cost == pytest.approx(1100)
    old = ledger.settle_year(2024, "2025-01-31")
    assert old.raw_short_gain == pytest.approx(0)
    assert old.tax == pytest.approx(0)
    ledger.sell("ABC", "2025-02-20", 10, 1200)
    new = ledger.settle_year(2025, "2026-01-31")
    assert new.short_gain == pytest.approx(100)
    assert new.tax == pytest.approx(35)


def test_long_term_requires_more_than_calendar_anniversary_in_leap_year():
    ledger = TaxLedger()
    ledger.buy("ABC", "2020-01-01", 2, 200)
    ledger.sell("ABC", "2021-01-01", 1, 150)  # 366 days, still exactly one year.
    ledger.sell("ABC", "2021-01-02", 1, 150)
    assert sales(ledger)[0]["short_gain"] == pytest.approx(50)
    assert sales(ledger)[1]["long_gain"] == pytest.approx(50)
    settlement = ledger.settle_year(2021, "2022-01-31")
    assert settlement.tax == pytest.approx(27.5)


def test_carry_crosses_years_without_offsetting_interest_or_dividends():
    ledger = TaxLedger()
    ledger.buy("ABC", "2023-01-01", 10, 1000)
    ledger.sell("ABC", "2023-02-10", 10, 500)
    ledger.record_interest("2023-12-31", 100)
    ledger.record_dividend("2023-12-31", 100, qualified_fraction=0.5)
    first = ledger.settle_year(2023, "2024-01-31")
    assert first.tax == pytest.approx(62.5)
    assert ledger.carry == pytest.approx((-500, 0))
    ledger.buy("DEF", "2024-02-01", 10, 1000)
    ledger.sell("DEF", "2024-03-01", 10, 1200)
    second = ledger.settle_year(2024, "2025-01-31")
    assert second.raw_short_gain == pytest.approx(200)
    assert second.short_gain == 0
    assert ledger.carry == pytest.approx((-300, 0))
    ledger.buy("GHI", "2025-02-01", 10, 1000)
    ledger.sell("GHI", "2025-03-01", 10, 1500)
    third = ledger.settle_year(2025, "2026-01-31")
    assert third.short_gain == pytest.approx(200)
    assert third.tax == pytest.approx(70)
    assert ledger.carry == (0, 0)


def test_capital_categories_cross_net_before_applying_rates():
    ledger = TaxLedger()
    ledger.buy("LONG", "2022-01-01", 10, 1000)
    ledger.buy("SHORT", "2024-03-01", 10, 1000)
    ledger.sell("LONG", "2024-06-01", 10, 1400)
    ledger.sell("SHORT", "2024-07-01", 10, 850)
    result = ledger.settle_year(2024, "2025-01-31")
    assert result.raw_short_gain == pytest.approx(-150)
    assert result.raw_long_gain == pytest.approx(400)
    assert result.short_gain == 0
    assert result.long_gain == pytest.approx(250)
    assert result.tax == pytest.approx(50)


def test_each_replacement_share_is_matched_only_once():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.sell("ABC", "2024-06-01", 5, 400)
    ledger.buy("ABC", "2024-06-05", 5, 450)
    ledger.sell("ABC", "2024-06-10", 5, 400)
    # June 5 shares already replace June 1 loss, not also the June 10 loss.
    assert sales(ledger)[0]["wash_disallowed"] == pytest.approx(100)
    assert sales(ledger)[1]["wash_disallowed"] == pytest.approx(0)
    assert ledger.lots["ABC"][0].total_cost == pytest.approx(550)


def test_wash_chain_carries_basis_and_holding_days_once():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.sell("ABC", "2024-06-01", 10, 800)
    first = ledger.buy("ABC", "2024-06-05", 10, 900)
    ledger.sell("ABC", "2024-06-10", 10, 1000)
    second = ledger.buy("ABC", "2024-06-15", 10, 1000)
    assert first.holding_credit_days == 152
    assert second.holding_credit_days == 157
    assert second.total_cost == pytest.approx(1100)
    assert [s["recognized_gain"] for s in sales(ledger)] == pytest.approx([0, 0])
    ledger.sell("ABC", "2025-01-20", 10, 1200)
    assert sales(ledger)[-1]["long_gain"] == pytest.approx(100)


def test_same_security_id_only_and_no_cross_account_claim():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-01-01", 10, 1000)
    ledger.sell("ABC", "2024-06-01", 10, 800)
    ledger.buy("DIFFERENT", "2024-06-05", 10, 900)
    assert sales(ledger)[0]["recognized_gain"] == pytest.approx(-200)
    assert ledger.lots["DIFFERENT"][0].total_cost == 900


def test_year_order_duplicates_chronology_and_final_closure():
    ledger = TaxLedger()
    ledger.record_interest("2023-12-31", 1)
    ledger.record_interest("2024-12-31", 1)
    with pytest.raises(ValueError, match="earlier activity"):
        ledger.settle_year(2024, "2025-01-31")
    ledger.settle_year(2023, "2025-01-31")
    with pytest.raises(ValueError, match="already settled"):
        ledger.settle_year(2023, "2025-01-31")
    ledger.settle_year(2024, "2025-01-31")
    with pytest.raises(ValueError, match="chronological"):
        ledger.buy("ABC", "2025-01-30", 1, 100)
    ledger.record_interest("2025-06-01", 1)
    ledger.settle_year(2025, "2025-06-01", allow_final=True)
    with pytest.raises(ValueError, match="closed"):
        ledger.buy("ABC", "2025-06-02", 1, 100)


def test_invalid_inputs_are_rejected_without_inventing_tax_or_shares():
    with pytest.raises(ValueError):
        TaxRates(short_term=1.1)
    ledger = TaxLedger()
    for shares, cost in [(0, 100), (-1, 100), (1, -100), (1, float("nan"))]:
        with pytest.raises(ValueError):
            ledger.buy("ABC", "2024-01-01", shares, cost)
    ledger.buy("ABC", "2024-01-01", 1, 100)
    with pytest.raises(ValueError, match="exceeds"):
        ledger.sell("ABC", "2024-02-01", 2, 200)
    with pytest.raises(ValueError, match="qualified_fraction"):
        ledger.record_dividend("2024-02-01", 10, 1.5)
    assert ledger.position("ABC") == 1


def test_terminal_january_settles_two_years_at_same_asof_then_stays_closed():
    ledger = TaxLedger()
    ledger.buy("ABC", "2024-11-01", 10, 1000)
    ledger.sell("ABC", "2024-12-20", 10, 800)
    ledger.buy("ABC", "2025-01-05", 10, 900)
    ledger.sell("ABC", "2025-01-10", 10, 1200)
    previous = ledger.settle_year(2024, "2025-01-10", allow_final=True)
    current = ledger.settle_year(2025, "2025-01-10", allow_final=True)
    assert previous.raw_short_gain == pytest.approx(0)
    assert current.raw_short_gain == pytest.approx(100)
    assert previous.tax == pytest.approx(0)
    assert current.tax == pytest.approx(35)
    assert [s.year for s in ledger.settlements] == [2024, 2025]
    with pytest.raises(ValueError, match="closed"):
        ledger.buy("ABC", "2025-01-10", 1, 100)
    with pytest.raises(ValueError, match="closed"):
        ledger.record_interest("2025-01-11", 1)
    with pytest.raises(ValueError, match="closed"):
        ledger.record_dividend("2025-01-11", 1)
