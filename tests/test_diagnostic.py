"""The process numbers must match the hand calculations in tests/fixtures/README.md.

Each entry of HAND_CHECKS (evals/fixture_checks.py) is one hand-computed number. The evaluation reports
how many of them pass.
"""

from __future__ import annotations

import pandas as pd
import pytest

from evals.fixture_checks import FIXTURE, HAND_CHECKS, run_checks
from opportunity_assessment import diagnostic as d
from opportunity_assessment.eventlog import load_log


@pytest.fixture(scope="module")
def log():
    return load_log(FIXTURE)


@pytest.mark.parametrize("name, compute, expected", HAND_CHECKS, ids=[c[0] for c in HAND_CHECKS])
def test_hand_computed_number(log, name, compute, expected):
    assert compute(log) == pytest.approx(expected), name


def test_waiting_adds_up_to_throughput(log):
    """Sum of all waits = sum of all throughput times (each case's waits tile its duration)."""
    assert d.waiting_by(log, "role")["total_days"].sum() == pytest.approx(d.throughput_days(log).sum())


def test_ties_keep_file_order():
    """Two events with the same timestamp keep the order they had in the file (stable sort)."""
    log = pd.DataFrame({
        "case_id": ["x", "x", "x"],
        "activity": ["Declaration SUBMITTED by EMPLOYEE", "Declaration APPROVED by ADMINISTRATION", "Payment Handled"],
        "timestamp": pd.to_datetime(["2018-01-01 09:00", "2018-01-01 09:00", "2018-01-02 09:00"], utc=True),
        "role": ["EMPLOYEE", "ADMINISTRATION", "UNDEFINED"],
    })
    assert list(d.prepare(log)["activity"])[:2] == ["Declaration SUBMITTED by EMPLOYEE",
                                                    "Declaration APPROVED by ADMINISTRATION"]


def test_volume_year(log):
    assert d.cases_started_in(log, 2018) == 20
    assert d.cases_started_in(log, 2017) == 0


def test_run_checks_reports_all_passing():
    results = run_checks()
    assert len(results) == len(HAND_CHECKS) == 20
    assert all(r["ok"] for r in results)
