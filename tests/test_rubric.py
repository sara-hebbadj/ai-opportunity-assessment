"""Use-case scoring: weights, ranking, evidence sentences and model answers."""

from __future__ import annotations

import json

import pytest

from opportunity_assessment import rubric
from opportunity_assessment.config import DATA_DIR


def test_weights_add_up_to_one():
    assert sum(rubric.WEIGHTS.values()) == pytest.approx(1.0)


def test_weighted_total_hand_example():
    scores = {"value": 5, "feasibility": 4, "data_readiness": 3, "risk": 4, "time_to_value": 4}
    # 0.3*5 + 0.2*4 + 0.2*3 + 0.15*4 + 0.15*4 = 1.5 + 0.8 + 0.6 + 0.6 + 0.6 = 4.1
    assert rubric.weighted_total(scores) == pytest.approx(4.1)


def test_ranking_breaks_ties_by_value_then_id():
    # Both total 3.3: A = 1.2 + 0.6 + 0.6 + 0.45 + 0.45; B = 0.9 + 0.6 + 0.6 + 0.75 + 0.45
    a = {"value": 4, "feasibility": 3, "data_readiness": 3, "risk": 3, "time_to_value": 3}
    b = {"value": 3, "feasibility": 3, "data_readiness": 3, "risk": 5, "time_to_value": 3}
    assert rubric.weighted_total(a) == pytest.approx(rubric.weighted_total(b))
    order = [uc for uc, _ in rubric.ranking({"UC05": b, "UC04": b, "UC09": a})]
    assert order == ["UC09", "UC04", "UC05"]


def test_long_list_has_18_ai_use_cases_and_2_non_ai():
    everything = rubric.load_use_cases(include_non_ai=True)
    assert len(rubric.load_use_cases()) == 18
    assert len(everything) == 20


def test_analyst_draft_scores_every_ai_use_case_in_range():
    scores = rubric.load_scores(DATA_DIR / "portfolio" / "scores_analyst_draft.csv")
    assert set(scores) == {uc["use_case_id"] for uc in rubric.load_use_cases()}
    assert all(1 <= s <= 5 for row in scores.values() for s in row.values())


def test_every_evidence_placeholder_resolves():
    summary = {"rejected_share": 0.1, "rejected_cases": 10, "first_rejected_by_admin_share": 0.6,
               "throughput_p50_rejected_days": 11.0, "throughput_p50_not_rejected_days": 7.0,
               "supervisor_wait_p50_days": 0.9, "supervisor_wait_p90_days": 5.9, "cases_via_supervisor_share": 0.97,
               "supervisor_share_of_waiting": 0.17, "variants": 99, "payment_stage_share_of_waiting": 0.56,
               "top_variant_share": 0.44, "employee_fix_wait_p50_days": 1.0, "employee_fix_wait_p90_days": 5.7,
               "resubmitted_share": 0.1, "cases_via_budget_owner_share": 0.27, "saved_never_submitted_cases": 134,
               "payment_handled_wait_p50_days": 3.2}
    shares = {f"T{i}": 0.125 for i in range(1, 9)}
    survey = {"q1_policy_clear": 2.6, "q3_status_visible": 1.9}
    facts = rubric.evidence_facts(summary, shares, survey)
    for use_case in rubric.load_use_cases(include_non_ai=True):
        assert "{" not in rubric.render_evidence(use_case, facts)


def test_llm_score_parses_and_validates(scripted):
    good = json.dumps({c: {"score": 4, "reason": "ok"} for c in rubric.CRITERIA})
    bad = json.dumps({c: {"score": 7, "reason": "too high"} for c in rubric.CRITERIA})
    llm = scripted(good, bad)
    use_case = rubric.load_use_cases()[0]
    assert rubric.llm_score(llm, use_case, "evidence")["value"] == 4
    assert rubric.llm_score(llm, use_case, "evidence")["error"] == "ValueError"


def test_compare_rankings_reports_rho_and_top2():
    a = {f"UC0{i}": {c: i for c in rubric.CRITERIA} for i in range(1, 5)}
    b = {f"UC0{i}": {c: 5 - i for c in rubric.CRITERIA} for i in range(1, 5)}
    same = rubric.compare_rankings(a, a)
    opposite = rubric.compare_rankings(a, b)
    assert same["spearman_rho"] == pytest.approx(1.0) and same["same_top2"]
    assert opposite["spearman_rho"] == pytest.approx(-1.0) and opposite["top2_overlap"] == 0
