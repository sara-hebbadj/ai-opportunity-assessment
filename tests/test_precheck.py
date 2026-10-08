"""The pre-check prototype: the claims set, the rules baseline, the model check and the scoring."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from opportunity_assessment import precheck

CLAIMS_DIR = Path(__file__).resolve().parents[1] / "data" / "claims"


@pytest.fixture(scope="module")
def claims():
    return precheck.load_claims()


def test_claim_set_shape(claims):
    problems = [p for c in claims for p in c["gold_problems"]]
    assert len(claims) == 50
    assert sum(1 for c in claims if c["gold_problems"]) == 30
    assert len(problems) == 40
    assert sum(p["visible_in"] == "fields" for p in problems) == 24
    assert {p["code"] for p in problems} == set(precheck.CODES)


def test_generator_is_reproducible(claims):
    """Re-running data/claims/make_claims.py (seed 42) gives exactly the committed file."""
    spec = importlib.util.spec_from_file_location("make_claims", CLAIMS_DIR / "make_claims.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build() == claims


def test_rules_find_every_field_problem_and_nothing_else(claims):
    for claim in claims:
        found = precheck.rules_check(claim)
        in_fields = {p["code"] for p in claim["gold_problems"] if p["visible_in"] == "fields"}
        assert in_fields <= found, claim["claim_id"]
        assert found <= precheck.gold_codes(claim), claim["claim_id"]


def test_rules_never_read_the_receipt_text(claims):
    for claim in claims:
        blanked = copy.deepcopy(claim)
        for line in blanked["lines"]:
            line["receipt_text"] = "unreadable"
        assert precheck.rules_check(blanked) == precheck.rules_check(claim)


def test_limits_are_inclusive():
    claim = {"trip": {"start": "2026-07-01", "end": "2026-07-02"}, "submitted_on": "2026-08-01",  # day 30
             "pre_approval_ref": "", "previous_claims": [], "lines": [
                 {"line_id": "L1", "date": "2026-07-02", "category": "hotel", "vendor": "H", "description": "Hotel",
                  "amount_aed": 600.0, "nights": 1, "receipt_attached": True, "receipt_text": ""},
                 {"line_id": "L2", "date": "2026-07-01", "category": "taxi", "vendor": "T", "description": "Taxi",
                  "amount_aed": 50.0, "receipt_attached": False, "receipt_text": ""},
                 {"line_id": "L3", "date": "2026-07-01", "category": "meal", "vendor": "M", "description": "Barbecue",
                  "amount_aed": 150.0, "receipt_attached": True, "receipt_text": ""}]}
    assert precheck.rules_check(claim) == set()


def test_model_never_sees_gold_labels(claims):
    text = " ".join(m["content"] for m in precheck.build_messages(claims[0], "policy"))
    assert "gold_problems" not in text and "visible_in" not in text


def test_llm_check_keeps_known_codes_only(scripted, claims):
    answer = {"problems": [{"code": "amount_mismatch", "line_id": "L1", "evidence": "x"},
                           {"code": "made_up", "line_id": "", "evidence": "y"}]}
    result = precheck.llm_check(scripted(json.dumps(answer)), claims[0], "policy")
    assert result["codes"] == {"amount_mismatch"}
    assert "made_up" in result["error"]


def test_llm_check_records_unparseable_answers(scripted, claims):
    assert precheck.llm_check(scripted("sorry"), claims[0], "policy")["error"] == "ValueError"


def test_score_hand_example():
    claims = [
        {"claim_id": "A", "gold_problems": [{"code": "late_submission", "visible_in": "fields"},
                                            {"code": "amount_mismatch", "visible_in": "receipt_text"}]},
        {"claim_id": "B", "gold_problems": []},
    ]
    scored = precheck.score({"A": {"late_submission"}, "B": {"duplicate"}}, claims)
    # 1 correct flag, 1 false flag, 1 missed -> precision 1/2, recall 1/2
    assert scored["precision"] == pytest.approx(0.5)
    assert scored["recall"] == pytest.approx(0.5)
    assert scored["recall_fields"] == 1.0 and scored["recall_receipt_text"] == 0.0
    assert scored["claim_level_precision"] == pytest.approx(0.5)


def test_rules_baseline_numbers(claims):
    scored = precheck.score({c["claim_id"]: precheck.rules_check(c) for c in claims}, claims)
    assert (scored["true_pos"], scored["false_pos"], scored["false_neg"]) == (24, 0, 16)
