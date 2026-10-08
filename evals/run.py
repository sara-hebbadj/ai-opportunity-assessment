"""Run the evaluation, step by step or all at once.

  python -m evals.run diagnostic                          # process numbers from the raw event log (no LLM)
  python -m evals.run themes --model cheap --limit 10     # LLM codes staff snippets (smoke test)
  python -m evals.run themes --model main                 # all 120 snippets
  python -m evals.run rubric --model main                 # an LLM scores the 18 AI use cases, one at a time
  python -m evals.run precheck --system rules             # rules baseline on the 50 claims (no LLM)
  python -m evals.run precheck --system llm --model cheap # LLM pre-check on the 50 claims
  python -m evals.run rebuild                             # every report number, chart and the ROI workbook
                                                          # from the raw log + saved outputs (no LLM calls)
  python -m evals.run themes --model cheap --dry-run      # FAKE model: proves the pipeline, NOT results

--model takes a role (cheap, main, judge: the IDs come from MODEL_CHEAP / MODEL_MAIN / MODEL_JUDGE) or a
full OpenRouter model ID (for example anthropic/claude-haiku-5.5).
Real runs write to evals/results/, dry runs to evals/dry_run/. Every model call goes to traces.jsonl there.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from opportunity_assessment import precheck, rubric, themes
from opportunity_assessment.config import EVALS_DIR, RESULTS_DIR, max_cost_per_run, model_id
from opportunity_assessment.llm import BudgetExceeded, FakeLLM, OpenRouterClient, Tracer

DRY_DIR = EVALS_DIR / "dry_run"
ROLES = ("cheap", "main", "judge")


def resolve_model(model: str) -> tuple[str, str, str]:
    """Return (role, model ID, file label). A full ID is used as-is with role 'cheap' for the env lookup."""
    if model in ROLES:
        return model, model_id(model), model
    return "cheap", model, model.split("/")[-1]


def make_client(dry_run: bool, out_dir: Path):
    tracer = Tracer(path=out_dir / "traces.jsonl")
    return FakeLLM(tracer) if dry_run else OpenRouterClient(tracer, budget_usd=max_cost_per_run())


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_items(items: list, work, client, label: str) -> tuple[list, bool]:
    """Call work(item) for each item, recording cost and latency per item. Stops cleanly at the budget."""
    results, stopped = [], False
    for number, item in enumerate(items, start=1):
        before, start = client.tracer.total_cost, time.perf_counter()
        try:
            row = work(item)
        except BudgetExceeded as error:
            print(f"STOPPED: {error}")
            stopped = True
            break
        except Exception as error:  # a failed API call is recorded with the item, the run goes on
            row = {"error": f"{type(error).__name__}: {str(error)[:120]}"}
        row["cost_usd"] = round(client.tracer.total_cost - before, 8)
        row["latency_ms"] = int((time.perf_counter() - start) * 1000)
        results.append(row)
        if number % 10 == 0:
            print(f"  {label}: {number}/{len(items)} done, US${client.tracer.total_cost:.4f} so far")
    return results, stopped


def cmd_themes(args, out_dir: Path) -> None:
    role, model, label = resolve_model(args.model)
    client = make_client(args.dry_run, out_dir)
    client.tracer.context = {"run": f"themes_{label}"}
    codebook, snippets = themes.load_codebook(), themes.load_snippets()[: args.limit]

    def work(snippet):
        client.tracer.context["item_id"] = snippet["snippet_id"]
        return themes.code_snippet(client, snippet, codebook, role=role, model=model or None)

    rows, stopped = run_items(snippets, work, client, "themes")
    for row, snippet in zip(rows, snippets, strict=False):
        row.setdefault("snippet_id", snippet["snippet_id"])
        row.setdefault("theme", "")
        row["model"] = "fake-offline" if args.dry_run else model
    columns = ["snippet_id", "theme", "reason", "error", "model", "cost_usd", "latency_ms"]
    write_csv(out_dir / f"theme_codes_{label}{suffix(args)}.csv", [{c: r.get(c, "") for c in columns} for r in rows])
    report_cost(client, rows, stopped)


def cmd_rubric(args, out_dir: Path) -> None:
    from opportunity_assessment import report  # evidence sentences need the diagnostic + theme numbers

    role, model, label = resolve_model(args.model)
    client = make_client(args.dry_run, out_dir)
    client.tracer.context = {"run": f"rubric_{label}"}
    facts = report.evidence_facts_from_saved()
    use_cases = rubric.load_use_cases()[: args.limit]

    def work(use_case):
        client.tracer.context["item_id"] = use_case["use_case_id"]
        scored = rubric.llm_score(client, use_case, rubric.render_evidence(use_case, facts), role=role,
                                  model=model or None)
        return {"use_case_id": use_case["use_case_id"], **scored}

    rows, stopped = run_items(use_cases, work, client, "rubric")
    flat = []
    for row in rows:
        flat.append({"use_case_id": row.get("use_case_id", ""),
                     **{c: row.get(c, "") for c in rubric.CRITERIA},
                     "reasons": json.dumps(row.get("reasons", {}), ensure_ascii=False),
                     "error": row.get("error", ""), "model": "fake-offline" if args.dry_run else model,
                     "cost_usd": row["cost_usd"], "latency_ms": row["latency_ms"]})
    write_csv(out_dir / f"rubric_scores_{label}{suffix(args)}.csv", flat)
    report_cost(client, rows, stopped)


def cmd_precheck(args, out_dir: Path) -> None:
    claims = precheck.load_claims()[: args.limit]
    if args.system == "rules":
        start = time.perf_counter()
        rows = [{"claim_id": c["claim_id"], "codes": sorted(precheck.rules_check(c)), "error": "", "cost_usd": 0.0}
                for c in claims]
        latency = (time.perf_counter() - start) * 1000 / len(claims)
        for row in rows:
            row["latency_ms"] = round(latency, 3)
        label, model = "rules", "none"
    else:
        role, model, label = resolve_model(args.model)
        client = make_client(args.dry_run, out_dir)
        client.tracer.context = {"run": f"precheck_{label}"}
        policy_text = precheck.POLICY_PATH.read_text(encoding="utf-8")

        def work(claim):
            client.tracer.context["item_id"] = claim["claim_id"]
            checked = precheck.llm_check(client, claim, policy_text, role=role, model=model or None)
            return {"claim_id": claim["claim_id"], "codes": sorted(checked["codes"]),
                    "problems": checked["problems"], "error": checked["error"]}

        rows, stopped = run_items(claims, work, client, "precheck")
        for row, claim in zip(rows, claims, strict=False):
            row.setdefault("claim_id", claim["claim_id"])
            row.setdefault("codes", [])
        report_cost(client, rows, stopped)
        model = "fake-offline" if args.dry_run else model
    for row in rows:
        row["gold"] = sorted(precheck.gold_codes(next(c for c in claims if c["claim_id"] == row["claim_id"])))
        row["model"] = model
    path = out_dir / f"precheck_{label}{suffix(args)}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    scored = precheck.score({r["claim_id"]: set(r["codes"]) for r in rows}, claims[: len(rows)])
    print(f"{label}: precision {scored['precision']:.3f}, recall {scored['recall']:.3f} "
          f"({scored['true_pos']}/{scored['pairs_gold']} planted problems found, {scored['false_pos']} false flags)")


def suffix(args) -> str:
    return f"_first{args.limit}" if args.limit else ""


def report_cost(client, rows: list[dict], stopped: bool) -> None:
    errors = sum(1 for r in rows if r.get("error"))
    print(f"{len(rows)} items, {errors} with errors, {client.tracer.calls} model calls, "
          f"US${client.tracer.total_cost:.4f} this run{' (stopped at budget)' if stopped else ''}")
    print(f"Project total in {client.tracer.path.name}: US${traces_total(client.tracer.path):.4f}")


def traces_total(path: Path) -> float:
    if not path.exists():
        return 0.0
    return sum(json.loads(line).get("cost_usd", 0) for line in path.read_text(encoding="utf-8").splitlines() if line)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["diagnostic", "themes", "rubric", "precheck", "rebuild"])
    parser.add_argument("--model", default="cheap", help="cheap, main, judge or a full OpenRouter model ID")
    parser.add_argument("--system", choices=["rules", "llm"], default="llm", help="precheck only")
    parser.add_argument("--limit", type=int, default=None, help="only the first N items (smoke test)")
    parser.add_argument("--dry-run", action="store_true", help="use the fake model; outputs go to evals/dry_run/")
    args = parser.parse_args()
    out_dir = DRY_DIR if args.dry_run else RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.step in ("diagnostic", "rebuild"):
        from opportunity_assessment import report

        from .fixture_checks import run_checks

        checks = run_checks()
        print(f"Hand-computed fixture: {sum(c['ok'] for c in checks)}/{len(checks)} checks match")
        report.rebuild(diagnostic_only=args.step == "diagnostic", out_dir=out_dir, fixture_results=checks)
    elif args.step == "themes":
        cmd_themes(args, out_dir)
    elif args.step == "rubric":
        cmd_rubric(args, out_dir)
    else:
        cmd_precheck(args, out_dir)


if __name__ == "__main__":
    main()
