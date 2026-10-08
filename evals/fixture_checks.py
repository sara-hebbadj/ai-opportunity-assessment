"""The 20 hand-computed checks on tests/fixtures/mini_log.csv (worked out in tests/fixtures/README.md).

Shared by the tests (tests/test_diagnostic.py) and the evaluation report (python -m evals.run rebuild).
"""

from __future__ import annotations

from pathlib import Path

from opportunity_assessment import diagnostic as d
from opportunity_assessment.eventlog import load_log

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "mini_log.csv"

# (name, function that computes the number, hand-computed value)
HAND_CHECKS = [
    ("cases", lambda log: d.summary(log)["cases"], 20),
    ("throughput p50", lambda log: d.throughput_summary(log)["p50"], 8.0),
    ("throughput p90", lambda log: d.throughput_summary(log)["p90"], 13.0),
    ("throughput mean", lambda log: d.throughput_summary(log)["mean"], 8.35),
    ("p50 rejected cases", lambda log: d.throughput_summary(log)["p50_rejected"], 13.0),
    ("p50 not rejected", lambda log: d.throughput_summary(log)["p50_not_rejected"], 7.0),
    ("rejected share", lambda log: d.rework(log)["rejected_share"], 0.25),
    ("resubmitted share", lambda log: d.rework(log)["resubmitted_share"], 0.20),
    ("first rejecter admin", lambda log: d.rework(log)["first_rejecter"]["ADMINISTRATION"], 4),
    ("first rejecter supervisor", lambda log: d.rework(log)["first_rejecter"]["SUPERVISOR"], 1),
    ("variants", lambda log: d.summary(log)["variants"], 6),
    ("top variant share", lambda log: d.top_variants(log)["share"].iloc[0], 0.40),
    ("total waiting days", lambda log: d.waiting_by(log, "activity")["total_days"].sum(), 167.0),
    ("supervisor step total wait",
     lambda log: _step(log, "Declaration FINAL_APPROVED by SUPERVISOR", "total_days"), 36.0),
    ("supervisor step median wait",
     lambda log: _step(log, "Declaration FINAL_APPROVED by SUPERVISOR", "median_days"), 2.0),
    ("payment handled share", lambda log: _step(log, "Payment Handled", "share_of_waiting"), 57 / 167),
    ("payment stage share (role)", lambda log: d.summary(log)["payment_stage_share_of_waiting"], 76 / 167),
    ("cases via supervisor", lambda log: _role_share(log, "SUPERVISOR"), 0.95),
    ("cases via administration", lambda log: _role_share(log, "ADMINISTRATION"), 0.85),
    ("cases via budget owner", lambda log: _role_share(log, "BUDGET OWNER"), 0.20),
]


def _step(log, activity, column):
    return d.waiting_by(log, "activity").set_index("activity").loc[activity, column]


def _role_share(log, role):
    return d.role_share(log).set_index("role").loc[role, "share_of_cases"]



def run_checks(tolerance: float = 1e-9) -> list[dict]:
    """Compute every check on the fixture: [{"name", "expected", "got", "ok"}]."""
    log = load_log(FIXTURE)
    results = []
    for name, compute, expected in HAND_CHECKS:
        got = float(compute(log))
        results.append({"name": name, "expected": float(expected), "got": got, "ok": abs(got - expected) <= tolerance})
    return results
