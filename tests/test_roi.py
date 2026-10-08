"""ROI model: formulas, break-even, sensitivity and the Excel formula text."""

from __future__ import annotations

import math

import pytest

from opportunity_assessment import roi

MEASURED = {"annual_claims": (1000, 500, 1500), "rejection_rate": (0.1, 0.07, 0.13),
            "approvals_per_claim": (1.0, 1.0, 1.0), "llm_cost_per_claim_usd": (0.0, 0.0, 0.0)}


def inputs(**changes):
    base = {key: a.value for key, a in roi.load_assumptions("UC01", MEASURED).items()}
    base.update(changes)
    return base


def test_uc01_hand_example():
    values = inputs(annual_claims=1000, rejection_rate=0.1, prevent_share=0.5, rework_staff_minutes=60,
                    staff_cost_per_hour=100, admin_minutes_saved_per_claim=1.0, employee_minutes_added_per_claim=1.0,
                    llm_cost_per_claim_usd=0.0, receipt_reading_cost_per_claim_usd=0.0, build_cost=3000,
                    run_cost_per_year=1000)
    r = roi.calculate("UC01", values)
    # 1000 claims x 10% x 50% = 50 rejections avoided x 1 hour x AED 100 = AED 5,000; checks net 0
    assert r["annual_benefit"] == pytest.approx(5000)
    assert r["net_annual"] == pytest.approx(4000)
    assert r["three_year_net"] == pytest.approx(9000)
    assert r["payback_months"] == pytest.approx(9.0)
    # break-even: (3000/3 + 1000) / (5000/1000 - 0) = 400 claims a year
    assert r["break_even_claims_per_year"] == pytest.approx(400)


def test_three_year_net_is_zero_at_break_even_volume():
    r = roi.calculate("UC01", inputs())
    if math.isinf(r["break_even_claims_per_year"]):
        pytest.skip("no break-even with these assumptions")
    at_break_even = roi.calculate("UC01", inputs(annual_claims=r["break_even_claims_per_year"]))
    assert at_break_even["three_year_net"] == pytest.approx(0, abs=1e-6)


def test_no_payback_when_net_is_negative():
    r = roi.calculate("UC01", inputs(prevent_share=0.0, admin_minutes_saved_per_claim=0.0))
    assert r["payback_months"] == math.inf


def test_break_even_value_of_one_input():
    assumptions = roi.load_assumptions("UC01", MEASURED)
    share = roi.break_even_value("UC01", assumptions, "prevent_share")
    values = {k: a.value for k, a in assumptions.items()} | {"prevent_share": share}
    assert roi.calculate("UC01", values)["three_year_net"] == pytest.approx(0, abs=1e-6)


def test_tornado_is_sorted_by_swing_and_skips_fixed_inputs():
    bars = roi.tornado("UC02", roi.load_assumptions("UC02", MEASURED))
    swings = [b["swing"] for b in bars]
    assert swings == sorted(swings, reverse=True)
    assert "usd_to_aed" not in {b["key"] for b in bars}


def test_excel_formula_uses_cell_addresses():
    cells = {"annual_claims": "B4", "rejection_rate": "B5", "net_annual": "B20"}
    assert roi.excel_formula("annual_claims * rejection_rate / 60", cells) == "=B4*B5/60"
    assert roi.excel_formula("3 * net_annual - annual_claims", cells) == "=3*B20-B4"


def test_every_formula_name_is_an_input_or_an_earlier_result():
    for use_case in roi.FORMULAS:
        known = set(roi.load_assumptions(use_case, MEASURED))
        for name, formula in roi.formulas_for(use_case).items():
            import re

            used = set(re.findall(r"[a-z_][a-z0-9_]*", formula))
            assert used <= known, (use_case, name, used - known)
            known.add(name)


def test_measured_rows_must_be_supplied():
    with pytest.raises(KeyError):
        roi.load_assumptions("UC01", {})
