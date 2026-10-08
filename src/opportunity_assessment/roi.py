"""Business case for the top 2 use cases: annual benefit, cost, 3-year net, payback, break-even, tornado.

Every result is ONE formula written as text in FORMULAS. Python evaluates that text, and the Excel export
writes the same text with the names replaced by cell addresses, so the spreadsheet and the Python numbers
cannot drift apart. (The formulas are our own fixed strings, never user input.)

Inputs come from three places, and each assumption row says which:
- measured from the event log (claims per year, rejection rate, approvals per claim);
- measured from the prototype run (model cost per claim);
- labelled assumptions with a low and a high value (minutes, hourly costs, build and run costs).
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path

from .config import DATA_DIR

ASSUMPTIONS_PATH = DATA_DIR / "portfolio" / "roi_assumptions.csv"
YEARS = 3

# Results in calculation order. Later formulas may use earlier results.
FORMULAS = {
    "UC01": {
        "benefit_rework": "annual_claims * rejection_rate * prevent_share * rework_staff_minutes"
                          " / 60 * staff_cost_per_hour",
        "benefit_checks": "annual_claims * (admin_minutes_saved_per_claim - employee_minutes_added_per_claim)"
                          " / 60 * staff_cost_per_hour",
        "annual_benefit": "benefit_rework + benefit_checks",
        "ai_cost_per_claim_aed": "(llm_cost_per_claim_usd + receipt_reading_cost_per_claim_usd) * usd_to_aed",
    },
    "UC02": {
        "annual_benefit": "annual_claims * approvals_per_claim * approver_minutes_saved / 60 * approver_cost_per_hour",
        "ai_cost_per_claim_aed": "llm_cost_per_claim_usd * approvals_per_claim * usd_to_aed",
    },
}
COMMON = {
    "annual_ai_cost": "annual_claims * ai_cost_per_claim_aed",
    "net_annual": "annual_benefit - annual_ai_cost - run_cost_per_year",
    "three_year_net": f"{YEARS} * net_annual - build_cost",
    "benefit_per_claim": "annual_benefit / annual_claims",
    "break_even_claims_per_year": f"(build_cost / {YEARS} + run_cost_per_year)"
                                  " / (benefit_per_claim - ai_cost_per_claim_aed)",
}


@dataclass
class Assumption:
    key: str
    description: str
    value: float
    low: float
    high: float
    unit: str
    source: str


def formulas_for(use_case_id: str) -> dict[str, str]:
    return {**FORMULAS[use_case_id], **COMMON}


def load_assumptions(use_case_id: str, measured: dict, path: Path = ASSUMPTIONS_PATH) -> dict[str, Assumption]:
    """Rows for ALL + this use case. Empty values are filled from `measured` ({key: (value, low, high)})."""
    rows = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["use_case_id"] not in ("ALL", use_case_id):
                continue
            if row["value"] == "":
                if row["key"] not in measured:
                    raise KeyError(f"no measured value for {row['key']}")
                value, low, high = measured[row["key"]]
            else:
                value, low, high = float(row["value"]), float(row["low"]), float(row["high"])
            rows[row["key"]] = Assumption(row["key"], row["description"], value, low, high, row["unit"], row["source"])
    return rows


def evaluate(formula: str, values: dict) -> float:
    try:
        return float(eval(formula, {"__builtins__": {}}, values))  # noqa: S307 (fixed formulas from this file)
    except ZeroDivisionError:
        return math.inf


def calculate(use_case_id: str, inputs: dict[str, float]) -> dict[str, float]:
    """Evaluate every result formula in order. Returns inputs + results."""
    values = dict(inputs)
    for name, formula in formulas_for(use_case_id).items():
        values[name] = evaluate(formula, values)
    net = values["net_annual"]
    values["payback_months"] = values["build_cost"] / (net / 12) if net > 0 else math.inf
    # A negative break-even means each claim costs more than it saves: no volume breaks even.
    if values["break_even_claims_per_year"] < 0:
        values["break_even_claims_per_year"] = math.inf
    return values


def base_inputs(assumptions: dict[str, Assumption]) -> dict[str, float]:
    return {key: a.value for key, a in assumptions.items()}


def tornado(use_case_id: str, assumptions: dict[str, Assumption], output: str = "three_year_net") -> list[dict]:
    """Change one assumption at a time to its low and high value; biggest swing first."""
    base = calculate(use_case_id, base_inputs(assumptions))[output]
    bars = []
    for key, a in assumptions.items():
        if a.low == a.high:
            continue
        results = {}
        for end in ("low", "high"):
            inputs = base_inputs(assumptions)
            inputs[key] = getattr(a, end)
            results[end] = calculate(use_case_id, inputs)[output]
        bars.append({"key": key, "low_input": a.low, "high_input": a.high, "base": base,
                     "result_at_low": results["low"], "result_at_high": results["high"],
                     "swing": abs(results["high"] - results["low"])})
    return sorted(bars, key=lambda bar: -bar["swing"])


def break_even_value(use_case_id: str, assumptions: dict[str, Assumption], key: str) -> float:
    """The value of one input at which the 3-year net is exactly zero (all results are linear in it)."""
    inputs = base_inputs(assumptions)
    inputs[key] = 0.0
    at_zero = calculate(use_case_id, inputs)["three_year_net"]
    inputs[key] = 1.0
    at_one = calculate(use_case_id, inputs)["three_year_net"]
    slope = at_one - at_zero
    return -at_zero / slope if slope else math.inf


def excel_formula(formula: str, cells: dict[str, str]) -> str:
    """Turn 'annual_claims * rejection_rate' into '=B5*B6' using the cell address of each name."""
    def replace(match: re.Match) -> str:
        name = match.group(0)
        return cells.get(name, name)

    return "=" + re.sub(r"[a-z_][a-z0-9_]*", replace, formula).replace(" ", "")
