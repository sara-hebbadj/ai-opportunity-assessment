"""Use-case portfolio: score each AI use case 1-5 on five criteria, weight them, and rank.

Weights (stated up front, before any scoring): value 30%, feasibility 20%, data readiness 20%,
risk 15%, time to value 15%. For risk and time to value, 5 is the GOOD end (low risk, fast).

Three scorers can be compared:
- the analyst draft (data/portfolio/scores_analyst_draft.csv, written by hand with a reason per row);
- two independent LLM scorers that see one use case at a time, with the same rubric anchors.
Agreement between rankings is Spearman's rho (agreement.py).
"""

from __future__ import annotations

import csv
from pathlib import Path

from .agreement import spearman_rho
from .config import DATA_DIR
from .llm import parse_json

PORTFOLIO_DIR = DATA_DIR / "portfolio"
CRITERIA = ["value", "feasibility", "data_readiness", "risk", "time_to_value"]
WEIGHTS = {"value": 0.30, "feasibility": 0.20, "data_readiness": 0.20, "risk": 0.15, "time_to_value": 0.15}

ANCHORS = """Score each criterion from 1 to 5 (whole numbers):
- value: 1 = minor pain or few cases; 3 = clear benefit on a measured bottleneck or a common staff complaint;
  5 = removes a large measured loss (for example rework on more than 10% of cases) and a top staff complaint.
- feasibility: 1 = research problem or new platform; 3 = known technique with real integration work;
  5 = small build on existing data and tools.
- data_readiness: 1 = the data does not exist; 3 = it exists but needs extraction or cleaning;
  5 = clean and available now.
- risk (5 = LOW risk): 1 = automated decisions about people, likely high-risk under the EU AI Act or privacy law;
  3 = advisory output that uses personal data; 5 = no personal data and no decisions.
- time_to_value (5 = FAST): 1 = more than 12 months; 3 = 3 to 6 months; 5 = under 6 weeks."""

SYSTEM_PROMPT = f"""You are a management consultant scoring AI use cases for a client. Score independently and honestly.
{ANCHORS}
Answer only with JSON: {{"value": {{"score": 1-5, "reason": "..."}}, "feasibility": {{...}},
"data_readiness": {{...}}, "risk": {{...}}, "time_to_value": {{...}}}}"""

CONTEXT = ("Client: Falcon Bay Services LLC (fictional), a 600-person services firm in Dubai. Process: domestic "
           "travel-expense claims (submit, administration check, budget owner, supervisor, payment). "
           "Receipts are photos (Arabic and English) with no text extracted. Approval reminders exist in the "
           "system but are switched off. Staff want AI that warns, never blocks, and that flags claims, not people.")


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_use_cases(include_non_ai: bool = False) -> list[dict]:
    rows = read_csv(PORTFOLIO_DIR / "use_cases.csv")
    return rows if include_non_ai else [r for r in rows if r["use_case_id"].startswith("UC")]


def load_scores(path: Path) -> dict[str, dict]:
    """{use_case_id: {criterion: int, ...}} from a scores CSV."""
    return {r["use_case_id"]: {c: int(r[c]) for c in CRITERIA} for r in read_csv(path)}


def weighted_total(scores: dict) -> float:
    return round(sum(WEIGHTS[c] * scores[c] for c in CRITERIA), 4)


def ranking(scores_by_case: dict[str, dict]) -> list[tuple[str, float]]:
    """Use cases from best to worst. Ties are broken by value, then by ID, so the order is stable."""
    return sorted(((uc, weighted_total(s)) for uc, s in scores_by_case.items()),
                  key=lambda item: (-item[1], -scores_by_case[item[0]]["value"], item[0]))


def rank_numbers(scores_by_case: dict[str, dict]) -> dict[str, int]:
    return {uc: position for position, (uc, _) in enumerate(ranking(scores_by_case), start=1)}


def compare_rankings(scores_a: dict, scores_b: dict) -> dict:
    """Spearman's rho on the weighted totals of the use cases both scorers rated."""
    shared = sorted(set(scores_a) & set(scores_b))
    totals_a = [weighted_total(scores_a[uc]) for uc in shared]
    totals_b = [weighted_total(scores_b[uc]) for uc in shared]
    ranks_a, ranks_b = rank_numbers({u: scores_a[u] for u in shared}), rank_numbers({u: scores_b[u] for u in shared})
    top2_a = {uc for uc, r in ranks_a.items() if r <= 2}
    top2_b = {uc for uc, r in ranks_b.items() if r <= 2}
    return {
        "n": len(shared),
        "spearman_rho": spearman_rho(totals_a, totals_b),
        "same_top2": top2_a == top2_b,
        "top2_overlap": len(top2_a & top2_b),
        "biggest_rank_changes": sorted(((uc, ranks_a[uc], ranks_b[uc]) for uc in shared),
                                       key=lambda t: -abs(t[1] - t[2]))[:5],
    }


def build_messages(use_case: dict, evidence: str) -> list[dict]:
    user = (f"{CONTEXT}\n\nUse case {use_case['use_case_id']}: {use_case['name']}\n"
            f"What it does: {use_case['description']}\nAI technique: {use_case['ai_technique']}\n"
            f"Process step: {use_case['process_step']}\nEvidence: {evidence}")
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def llm_score(client, use_case: dict, evidence: str, role: str = "main", model: str | None = None) -> dict:
    """Return {criterion: score} plus 'reasons' and 'error'. Out-of-range or missing scores are an error."""
    try:
        result = client.complete(build_messages(use_case, evidence), role=role, purpose="rubric", json_mode=True,
                                 max_tokens=1500, model=model)
        answer = parse_json(result.text)
        scores = {c: int(answer[c]["score"]) for c in CRITERIA}
        if not all(1 <= s <= 5 for s in scores.values()):
            raise ValueError("score out of range")
        return {**scores, "reasons": {c: answer[c].get("reason", "") for c in CRITERIA}, "error": ""}
    except (ValueError, KeyError, TypeError) as error:
        return {"error": type(error).__name__}


def evidence_facts(summary: dict, theme_shares: dict, survey_means: dict) -> dict:
    """Formatted numbers for the evidence sentences in use_cases.csv ({rejected_share_pct}, {T3_share_pct}...)."""
    facts = {}
    for key, value in summary.items():
        if isinstance(value, bool):
            continue
        facts[key] = value
        if "share" in key:
            facts[f"{key}_pct"] = f"{value:.1%}"
        elif key.endswith("_days"):
            facts[f"{key}_fmt"] = f"{value:.1f}"
        elif isinstance(value, int):
            facts[f"{key}_fmt"] = f"{value:,}"
    for theme, share in theme_shares.items():
        facts[f"{theme}_share_pct"] = f"{share:.0%}"
    for question, mean in survey_means.items():
        facts[f"{question}_mean"] = f"{mean:.1f}"
    return facts


def render_evidence(use_case: dict, facts: dict) -> str:
    return use_case["evidence"].format(**facts)
