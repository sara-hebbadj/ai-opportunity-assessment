"""Rebuild every report number, chart and the ROI workbook from the raw log and the saved model outputs.

`python -m evals.run rebuild` calls `rebuild()`. It makes NO model calls: it only reads
- data/raw/domestic_declarations.csv (the event log; if missing, the saved diagnostic summary is reused),
- the saved model outputs in evals/results/ (theme codes, rubric scores, pre-check runs),
and writes evals/results/summary.json, charts in docs/charts/, docs/roi_model.xlsx and
docs/use_case_portfolio.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no window
import matplotlib.pyplot as plt  # noqa: E402

from . import diagnostic, precheck, roi, rubric, themes  # noqa: E402
from .config import CHARTS_DIR, CLIENT_NAME, DATA_DIR, DOCS_DIR, RESULTS_DIR, RUN_DATE  # noqa: E402
from .eventlog import LOG_CSV, load_log  # noqa: E402

# Chart colours: validated categorical slots 1-2 (blue, orange) + recessive greys (dataviz reference palette)
BLUE, ORANGE, GREY = "#2a78d6", "#eb6834", "#b9b8b3"
TEXT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e1", "#fcfcfb"
SURVEY_QUESTIONS = ["q1_policy_clear", "q2_easy_to_submit", "q3_status_visible", "q4_approvals_fast",
                    "q5_would_use_precheck"]
# Which saved pre-check run sets the model cost per claim in the ROI model (see README "Results").
ROI_COST_RUN = "cheap"
# Where charts and generated documents go. A dry run redirects them to evals/dry_run/ so fake outputs
# can never overwrite the real charts in docs/.
TARGET = {"charts": CHARTS_DIR, "docs": DOCS_DIR}


# ---------- small helpers ----------

def read_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False, default=_jsonable) + "\n", encoding="utf-8")


def _jsonable(value):
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return str(value)


def clean(value):
    """Replace inf/nan with None everywhere so the JSON stays valid."""
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [clean(v) for v in value]
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return None
    return value


def saved_runs(out_dir: Path, prefix: str, extension: str) -> dict[str, Path]:
    """{label: path} for saved full runs, e.g. theme_codes_main.csv -> 'main'. Smoke runs (_firstN) are skipped."""
    runs = {}
    for path in sorted(out_dir.glob(f"{prefix}_*{extension}")):
        label = path.name[len(prefix) + 1: -len(extension)]
        if "_first" in label or label.endswith("_summary"):
            continue
        runs[label] = path
    return runs


def style(ax, title: str, subtitle: str = "") -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=12, color=TEXT, fontweight="bold", pad=18 if subtitle else 8)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=MUTED)


def save(fig, name: str) -> str:
    TARGET["charts"].mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    path = TARGET["charts"] / name
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return str(path.relative_to(DOCS_DIR.parent))


# ---------- 1. process diagnostic ----------

def run_diagnostic(out_dir: Path) -> dict:
    """Process numbers from the raw log. Without the raw file, reuse the saved summary (and say so)."""
    summary_path = RESULTS_DIR / "diagnostic_summary.json"
    if not LOG_CSV.exists():
        if summary_path.exists():
            print(f"{LOG_CSV} not found: reusing the saved {summary_path.name}")
            return read_json(summary_path)
        raise FileNotFoundError(f"{LOG_CSV} not found. Run: python -m opportunity_assessment.eventlog")
    log = load_log()
    summary = diagnostic.summary(log)
    steps = diagnostic.waiting_by(log, "activity")
    roles = diagnostic.waiting_by(log, "role")
    variants = diagnostic.top_variants(log, n=10)
    shares = diagnostic.role_share(log)
    for name, table in (("waiting_by_step", steps), ("waiting_by_role", roles), ("top_variants", variants),
                        ("role_share", shares)):
        table.round(4).to_csv(out_dir / f"diagnostic_{name}.csv", index=False)
    summary["source"] = "BPI Challenge 2020, Domestic Declarations (4TU.ResearchData, CC BY-NC 4.0)"
    summary["run_date"] = RUN_DATE
    write_json(out_dir / "diagnostic_summary.json", summary)
    summary["charts"] = [chart_waiting_by_role(roles), chart_throughput(summary)]
    return summary


def chart_waiting_by_role(roles) -> str:
    names = {"UNDEFINED": "Payment stage (system)", "SUPERVISOR": "Supervisor", "ADMINISTRATION": "Administration",
             "EMPLOYEE": "Employee (fixing rejections)", "BUDGET OWNER": "Budget owner",
             "PRE_APPROVER": "Pre-approver", "MISSING": "Unknown role"}
    table = roles.sort_values("share_of_waiting")
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    labels = [names.get(r, r) for r in table["role"]]
    ax.barh(labels, table["share_of_waiting"] * 100, color=BLUE, height=0.55)
    for y, value in enumerate(table["share_of_waiting"] * 100):
        ax.text(value + 0.8, y, f"{value:.1f}%", va="center", fontsize=9, color=TEXT)
    ax.set_xlabel("Share of all waiting time (%)", color=MUTED, fontsize=9)
    ax.set_xlim(0, max(table["share_of_waiting"] * 100) * 1.18)
    style(ax, "Where claims wait", "Sum of waits before each step, by who does the step (10,500 cases)")
    return save(fig, "waiting_by_role.png")


def chart_throughput(summary: dict) -> str:
    groups = ["No rejection", "At least one rejection"]
    p50 = [summary["throughput_p50_not_rejected_days"], summary["throughput_p50_rejected_days"]]
    p90 = [summary["throughput_p90_not_rejected_days"], summary["throughput_p90_rejected_days"]]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    y = range(len(groups))
    ax.barh([i + 0.17 for i in y], p50, height=0.3, color=BLUE, label="Median (p50)")
    ax.barh([i - 0.17 for i in y], p90, height=0.3, color=ORANGE, label="90th percentile (p90)")
    for i in y:
        ax.text(p50[i] + 0.5, i + 0.17, f"{p50[i]:.1f} d", va="center", fontsize=9, color=TEXT)
        ax.text(p90[i] + 0.5, i - 0.17, f"{p90[i]:.1f} d", va="center", fontsize=9, color=TEXT)
    ax.set_yticks(list(y), groups)
    ax.set_xlabel("Days from first to last event", color=MUTED, fontsize=9)
    ax.set_xlim(0, max(p90) * 1.2)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    style(ax, "Rejections make claims slower",
          f"Throughput time per case; {summary['rejected_cases']:,} of {summary['cases']:,} cases had a rejection")
    return save(fig, "throughput_rejected.png")


# ---------- 2. voice of staff ----------

def survey_means() -> dict:
    rows = themes.read_csv(DATA_DIR / "staff" / "survey.csv")
    return {q: sum(int(r[q]) for r in rows) / len(rows) for q in SURVEY_QUESTIONS} | {"n": len(rows)}


def load_codes(path: Path) -> dict[str, str]:
    return {r["snippet_id"]: r["theme"] for r in themes.read_csv(path) if r["theme"]}


def theme_section(out_dir: Path) -> dict:
    author = themes.load_author_labels()
    author_codes = {s: r["author_theme"] for s, r in author.items()}
    clear_ids = {s for s, r in author.items() if r["clarity"] == "clear"}
    coders = {label: load_codes(path) for label, path in saved_runs(out_dir, "theme_codes", ".csv").items()}
    runs = saved_runs(out_dir, "theme_codes", ".csv")
    models = {label: themes.read_csv(path)[0]["model"] for label, path in runs.items()}
    section = {"coders": {}, "pairs": {}, "sara": None, "models": models}
    for label, codes in coders.items():
        rows = themes.read_csv(out_dir / f"theme_codes_{label}.csv")
        section["coders"][label] = {
            "model": models[label],
            "coded": len(codes), "errors": sum(1 for r in rows if r["error"]),
            "cost_usd": sum(float(r["cost_usd"] or 0) for r in rows),
            "vs_author_all": themes.compare_coders(codes, author_codes),
            "vs_author_clear": themes.compare_coders({s: c for s, c in codes.items() if s in clear_ids}, author_codes),
            "vs_author_mixed": themes.compare_coders({s: c for s, c in codes.items() if s not in clear_ids},
                                                     author_codes),
        }
    labels = sorted(coders)
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            section["pairs"][f"{a}_vs_{b}"] = themes.compare_coders(coders[a], coders[b])
    sara = themes.load_sara_codes()
    if sara:
        section["sara"] = {label: themes.compare_coders(codes, sara) for label, codes in coders.items()}
    preferred = next((label for label in ("main", "cheap") if label in coders), labels[0] if labels else None)
    counts = themes.theme_counts([{"theme": t} for t in (coders[preferred] if preferred else author_codes).values()])
    total = sum(counts.values()) or 1
    section["counts_from"] = preferred or "author labels"
    section["counts"] = counts
    section["shares"] = {t: c / total for t, c in counts.items()}
    section["chart"] = chart_themes(section["shares"], section["counts_from"], models.get(preferred, ""))
    return section


def chart_themes(shares: dict, source: str, model: str) -> str:
    names = {t["theme_id"]: t["name"] for t in themes.load_codebook()}
    order = sorted(shares, key=lambda t: shares[t])
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    ax.barh([f"{t} {names[t]}" for t in order], [shares[t] * 100 for t in order], color=BLUE, height=0.55)
    for y, t in enumerate(order):
        ax.text(shares[t] * 100 + 0.3, y, f"{shares[t]:.0%}", va="center", fontsize=9, color=TEXT)
    ax.set_xlabel("Share of 120 snippets (%)", color=MUTED, fontsize=9)
    ax.set_xlim(0, max(shares.values()) * 118)
    who = f"coded by {model}" if model else f"coded by {source}"
    style(ax, "Staff pain points (synthetic interviews + survey)", f"One main theme per snippet, {who}")
    return save(fig, "staff_themes.png")


# ---------- 3. use-case portfolio ----------

def evidence_facts_from_saved(out_dir: Path = RESULTS_DIR) -> dict:
    summary = read_json(RESULTS_DIR / "diagnostic_summary.json")
    shares = theme_section_shares(out_dir)
    return rubric.evidence_facts(summary, shares, {q: m for q, m in survey_means().items() if q != "n"})


def theme_section_shares(out_dir: Path) -> dict:
    runs = saved_runs(out_dir, "theme_codes", ".csv")
    label = next((label for label in ("main", "cheap") if label in runs), None)
    codes = load_codes(runs[label]) if label else {s: r["author_theme"] for s, r in themes.load_author_labels().items()}
    counts = themes.theme_counts([{"theme": t} for t in codes.values()])
    total = sum(counts.values()) or 1
    return {t: c / total for t, c in counts.items()}


def rubric_section(out_dir: Path, facts: dict) -> dict:
    analyst = rubric.load_scores(DATA_DIR / "portfolio" / "scores_analyst_draft.csv")
    scorers = {"analyst_draft": analyst}
    models = {"analyst_draft": "hand-written draft (coding agent; Sara to review)"}
    for label, path in saved_runs(out_dir, "rubric_scores", ".csv").items():
        rows = [r for r in themes.read_csv(path) if not r["error"]]
        scorers[label] = {r["use_case_id"]: {c: int(r[c]) for c in rubric.CRITERIA} for r in rows}
        models[label] = themes.read_csv(path)[0]["model"]
    use_cases = rubric.load_use_cases(include_non_ai=True)
    ranks = {label: rubric.rank_numbers(s) for label, s in scorers.items()}
    table = []
    for uc in use_cases:
        row = {"use_case_id": uc["use_case_id"], "name": uc["name"], "ai_technique": uc["ai_technique"],
               "evidence": rubric.render_evidence(uc, facts)}
        for label, s in scorers.items():
            if uc["use_case_id"] in s:
                row[f"{label}_total"] = rubric.weighted_total(s[uc["use_case_id"]])
                row[f"{label}_rank"] = ranks[label][uc["use_case_id"]]
        if uc["use_case_id"] in analyst:
            row.update({c: analyst[uc["use_case_id"]][c] for c in rubric.CRITERIA})
        table.append(row)
    labels = list(scorers)
    comparisons = {}
    for i, a in enumerate(labels):
        for b in labels[i + 1:]:
            comparisons[f"{a}_vs_{b}"] = rubric.compare_rankings(scorers[a], scorers[b])
    top2 = [uc for uc, _ in rubric.ranking(analyst)[:2]]
    return {"table": table, "comparisons": comparisons, "models": models, "top2": top2,
            "weights": rubric.WEIGHTS, "chart": chart_value_feasibility(analyst, top2)}


def chart_value_feasibility(scores: dict, top2: list[str]) -> str:
    fig, ax = plt.subplots(figsize=(6.5, 5.2))
    cells: dict[tuple, list[str]] = {}
    for uc, s in sorted(scores.items()):
        cells.setdefault((s["feasibility"], s["value"]), []).append(uc)
    for (feasibility, value), group in cells.items():
        for k, uc in enumerate(group):
            # Use cases with the same scores are stacked a little apart so every ID stays readable.
            y = value + (k - (len(group) - 1) / 2) * 0.19
            is_top = uc in top2
            ax.scatter(feasibility, y, s=70 if is_top else 45, color=BLUE if is_top else GREY, edgecolor=SURFACE,
                       linewidth=1.5, zorder=3)
            ax.annotate(uc, (feasibility, y), textcoords="offset points", xytext=(7, -3), fontsize=8,
                        color=TEXT if is_top else MUTED, fontweight="bold" if is_top else "normal")
    ax.axhline(3, color=GRID, linewidth=1)
    ax.axvline(3, color=GRID, linewidth=1)
    for (x, y, label) in ((4.95, 5.35, "Do first"), (1.05, 5.35, "Big bets"), (4.95, 0.65, "Quick tidy-ups"),
                          (1.05, 0.65, "Drop for now")):
        ax.text(x, y, label, fontsize=8, color=MUTED, ha="right" if x > 3 else "left", va="center")
    ax.set_xlim(0.8, 5.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_xlabel("Feasibility (1-5)", color=MUTED, fontsize=9)
    ax.set_ylabel("Value (1-5)", color=MUTED, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    style(ax, "Value vs feasibility: 18 AI use cases", "Analyst draft scores; blue = top 2 by weighted score")
    return save(fig, "value_vs_feasibility.png")


# ---------- 4. pre-check prototype ----------

def precheck_section(out_dir: Path) -> dict:
    claims = precheck.load_claims()
    rules = {c["claim_id"]: precheck.rules_check(c) for c in claims}
    rows = [{"system": "rules", "model": "none", **_flat_score(precheck.score(rules, claims)),
             "cost_per_100_claims_usd": 0.0, "avg_latency_ms": None, "errors": 0}]
    for label, path in saved_runs(out_dir, "precheck", ".jsonl").items():
        if label == "rules":
            continue
        runs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(runs) < len(claims):
            continue
        predicted = {r["claim_id"]: set(r["codes"]) for r in runs}
        cost = sum(r["cost_usd"] for r in runs) / len(runs)
        latency = sum(r["latency_ms"] for r in runs) / len(runs)
        errors = sum(1 for r in runs if r["error"])
        base = {"model": runs[0]["model"], "cost_per_100_claims_usd": cost * 100, "avg_latency_ms": latency,
                "errors": errors}
        rows.append({"system": f"llm_{label}", **_flat_score(precheck.score(predicted, claims)), **base})
        hybrid = {cid: predicted.get(cid, set()) | rules[cid] for cid in rules}
        rows.append({"system": f"hybrid_{label}", **_flat_score(precheck.score(hybrid, claims)), **base})
    section = {"rows": rows, "claims": len(claims),
               "planted": sum(len(precheck.gold_codes(c)) for c in claims)}
    section["chart"] = chart_precheck(rows)
    return section


def _same_score(a: dict, b: dict | None) -> bool:
    return b is not None and (a["true_pos"], a["false_pos"]) == (b["true_pos"], b["false_pos"])


def _flat_score(scored: dict) -> dict:
    return {k: v for k, v in scored.items() if k != "per_code"} | {"per_code": scored["per_code"]}


def system_name(row: dict) -> str:
    """'rules' -> 'Rules only'; 'llm_cheap' -> 'LLM only: gpt-6-luna'; 'hybrid_cheap' -> 'Rules + gpt-6-luna'."""
    model = row["model"].split("/")[-1]
    if row["system"] == "rules":
        return "Rules only"
    return f"LLM only: {model}" if row["system"].startswith("llm_") else f"Rules + {model}"


def chart_precheck(rows: list[dict]) -> str:
    # "Rules + model" rows are drawn only when they differ from the model alone (otherwise they repeat a bar).
    plain = {r["system"][4:]: r for r in rows if r["system"].startswith("llm_")}
    rows = [r for r in rows if not (r["system"].startswith("hybrid_") and _same_score(r, plain.get(r["system"][7:])))]
    fig, ax = plt.subplots(figsize=(7.5, 0.55 * len(rows) + 1.6))
    names = [system_name(r) for r in rows][::-1]
    precision = [r["precision"] * 100 for r in rows][::-1]
    recall = [r["recall"] * 100 for r in rows][::-1]
    y = range(len(rows))
    ax.barh([i + 0.17 for i in y], precision, height=0.3, color=BLUE, label="Precision")
    ax.barh([i - 0.17 for i in y], recall, height=0.3, color=ORANGE, label="Recall")
    for i in y:
        ax.text(precision[i] + 1, i + 0.17, f"{precision[i]:.0f}%", va="center", fontsize=8, color=TEXT)
        ax.text(recall[i] + 1, i - 0.17, f"{recall[i]:.0f}%", va="center", fontsize=8, color=TEXT)
    ax.set_yticks(list(y), names)
    ax.set_xlim(0, 115)
    ax.set_xlabel("% of (claim, problem) pairs", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.12 - 0.6 / len(rows)), ncols=2)
    style(ax, "Pre-check on 50 synthetic claims (40 planted problems)", "Precision = correct flags / all flags; "
          "recall = planted problems found / 40")
    return save(fig, "precheck_comparison.png")


# ---------- 5. ROI model ----------

def measured_inputs(summary: dict, pre: dict) -> dict:
    llm_rows = [r for r in pre["rows"] if r["system"].startswith("llm_")]
    costs = {r["system"][4:]: r["cost_per_100_claims_usd"] / 100 for r in llm_rows}
    base_cost = costs.get(ROI_COST_RUN, min(costs.values()) if costs else 0.0)
    return {
        "annual_claims": (summary["annual_cases"], round(summary["annual_cases"] * 0.5),
                          round(summary["annual_cases"] * 1.5)),
        "rejection_rate": (summary["annual_rejected_share"], summary["annual_rejected_share"] * 0.7,
                           summary["annual_rejected_share"] * 1.3),
        "approvals_per_claim": (summary["approver_steps_per_case"],) * 3,
        "llm_cost_per_claim_usd": (base_cost, min(costs.values(), default=base_cost),
                                   max(costs.values(), default=base_cost)),
    }


def roi_section(summary: dict, pre: dict, top2: list[str]) -> dict:
    measured = measured_inputs(summary, pre)
    section = {"use_cases": {}, "measured": {k: v[0] for k, v in measured.items()},
               "ai_cost_measured": any(r["system"].startswith("llm_") for r in pre["rows"])}
    for uc in top2:
        if uc not in roi.FORMULAS:
            section["use_cases"][uc] = {"error": "no ROI formulas for this use case"}
            continue
        assumptions = roi.load_assumptions(uc, measured)
        results = roi.calculate(uc, roi.base_inputs(assumptions))
        bars = roi.tornado(uc, assumptions)
        entry = {"results": results, "tornado": bars, "assumptions": {k: vars(a) for k, a in assumptions.items()}}
        if uc == "UC01":
            entry["break_even_prevent_share"] = roi.break_even_value(uc, assumptions, "prevent_share")
        if uc == "UC02":
            entry["break_even_approver_minutes"] = roi.break_even_value(uc, assumptions, "approver_minutes_saved")
        entry["chart"] = chart_tornado(uc, bars)
        section["use_cases"][uc] = entry
    section["workbook"] = write_workbook(section, top2)
    return section


LABELS = {"annual_claims": "Claims per year", "rejection_rate": "Rejection rate", "prevent_share":
          "Rejections prevented", "rework_staff_minutes": "Rework minutes per rejection",
          "admin_minutes_saved_per_claim": "Clerk minutes saved per claim", "employee_minutes_added_per_claim":
          "Employee minutes added per claim", "receipt_reading_cost_per_claim_usd": "Receipt-reading cost",
          "build_cost": "Build cost", "run_cost_per_year": "Run cost per year", "staff_cost_per_hour":
          "Staff cost per hour", "approver_cost_per_hour": "Approver cost per hour", "llm_cost_per_claim_usd":
          "Model cost per claim", "approver_minutes_saved": "Approver minutes saved per approval"}
UC_TITLES = {"UC01": "Receipt and policy pre-check", "UC02": "Approver assistant"}


def chart_tornado(uc: str, bars: list[dict]) -> str:
    bars = [b for b in bars if b["swing"] > 0][:8][::-1]
    base = bars[0]["base"] if bars else 0
    fig, ax = plt.subplots(figsize=(7.5, 0.45 * len(bars) + 1.6))
    for i, bar in enumerate(bars):
        low, high = bar["result_at_low"] / 1000, bar["result_at_high"] / 1000
        ax.barh(i, low - base / 1000, left=base / 1000, height=0.5, color=BLUE,
                label="Assumption at its low value" if i == 0 else None)
        ax.barh(i, high - base / 1000, left=base / 1000, height=0.5, color=ORANGE,
                label="Assumption at its high value" if i == 0 else None)
    ax.axvline(base / 1000, color=TEXT, linewidth=1)
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_yticks(range(len(bars)), [LABELS.get(b["key"], b["key"]) for b in bars])
    ax.set_xlabel("3-year net benefit (thousand AED)", color=MUTED, fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    base_text = f"{'−' if base < 0 else ''}AED {abs(base) / 1000:,.0f}k"
    style(ax, f"{uc} {UC_TITLES.get(uc, '')}: what moves the 3-year net",
          f"Base case {base_text} (black line); one assumption changed at a time")
    return save(fig, f"tornado_{uc}.png")


def write_workbook(section: dict, top2: list[str]) -> str:
    """docs/roi_model.xlsx: one live-formula sheet per use case + a sensitivity sheet with the tornado charts."""
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image
    from openpyxl.styles import Font, PatternFill

    workbook = Workbook()
    readme = workbook.active
    readme.title = "Read me"
    notes = [
        f"ROI model for the top 2 AI use cases: {CLIENT_NAME}.",
        "Built by python -m evals.run rebuild. Change any yellow input cell: the results recalculate.",
        "Sources: 'measured: event log' = BPI Challenge 2020 Domestic Declarations (CC BY-NC 4.0, 2018 cases);",
        "'measured: prototype' = OpenRouter cost per claim from the pre-check run; 'assumption' = labelled guess",
        "with a low and a high value, to be replaced with the client's own numbers.",
        "Money in AED. 3-year net = 3 x (annual benefit - AI cost - run cost) - build cost. No discounting.",
        "Faster reimbursement for employees is a real benefit but is NOT counted in AED here.",
    ]
    for row, text in enumerate(notes, start=1):
        readme.cell(row=row, column=1, value=text)
    readme.column_dimensions["A"].width = 110
    yellow = PatternFill("solid", fgColor="FFF4C2")
    bold = Font(bold=True)
    for uc in top2:
        entry = section["use_cases"].get(uc)
        if not entry or "error" in entry:
            continue
        sheet = workbook.create_sheet(f"{uc} model")
        sheet["A1"] = f"{uc} {UC_TITLES.get(uc, '')}"
        sheet["A1"].font = Font(bold=True, size=13)
        headers = ["Input", "Value", "Low", "High", "Unit", "Source", "Description"]
        for col, text in enumerate(headers, start=1):
            sheet.cell(row=3, column=col, value=text).font = bold
        cells = {}
        row = 4
        for key, a in entry["assumptions"].items():
            values = [key, a["value"], a["low"], a["high"], a["unit"], a["source"], a["description"]]
            for col, value in enumerate(values, start=1):
                sheet.cell(row=row, column=col, value=value)
            sheet.cell(row=row, column=2).fill = yellow
            cells[key] = f"B{row}"
            row += 1
        row += 1
        sheet.cell(row=row, column=1, value="Result").font = bold
        sheet.cell(row=row, column=2, value="Value (formula)").font = bold
        sheet.cell(row=row, column=3, value="Formula in words").font = bold
        row += 1
        for name, formula in roi.formulas_for(uc).items():
            sheet.cell(row=row, column=1, value=name)
            sheet.cell(row=row, column=2, value=roi.excel_formula(formula, cells))
            sheet.cell(row=row, column=3, value=formula)
            cells[name] = f"B{row}"
            row += 1
        net, build = cells["net_annual"], cells["build_cost"]
        sheet.cell(row=row, column=1, value="payback_months")
        sheet.cell(row=row, column=2, value=f'=IF({net}>0,{build}/({net}/12),"no payback")')
        sheet.cell(row=row, column=3, value="build_cost / (net_annual / 12), only if net_annual > 0")
        for column, width in zip("ABCDEFG", (34, 16, 60, 12, 16, 22, 70), strict=True):
            sheet.column_dimensions[column].width = width
    sensitivity = workbook.create_sheet("Sensitivity")
    sensitivity["A1"] = "One assumption at a time at its low / high value -> 3-year net (AED). Values from Python."
    row = 3
    for uc in top2:
        entry = section["use_cases"].get(uc)
        if not entry or "error" in entry:
            continue
        sensitivity.cell(row=row, column=1, value=f"{uc} {UC_TITLES.get(uc, '')}").font = bold
        row += 1
        for col, text in enumerate(["Input", "Low", "High", "3-year net at low", "3-year net at high", "Swing"], 1):
            sensitivity.cell(row=row, column=col, value=text).font = bold
        row += 1
        for bar in entry["tornado"]:
            for col, value in enumerate([bar["key"], bar["low_input"], bar["high_input"], round(bar["result_at_low"]),
                                         round(bar["result_at_high"]), round(bar["swing"])], start=1):
                sensitivity.cell(row=row, column=col, value=value)
            row += 1
        image = Image(DOCS_DIR.parent / entry["chart"])
        image.width, image.height = image.width * 0.5, image.height * 0.5
        sensitivity.add_image(image, f"H{row - len(entry['tornado']) - 2}")
        row += 12
    sensitivity.column_dimensions["A"].width = 36
    path = TARGET["docs"] / "roi_model.xlsx"
    workbook.save(path)
    return str(path.relative_to(DOCS_DIR.parent))


# ---------- 6. portfolio document ----------

def write_portfolio(rub: dict) -> str:
    lines = [
        "# Use-case portfolio (long list, scores and ranking)",
        "",
        f"*Generated by `python -m evals.run rebuild` on {RUN_DATE}. Client: {CLIENT_NAME}. Evidence numbers come "
        "from the event log (BPI Challenge 2020, CC BY-NC 4.0) and the synthetic staff interviews and survey.*",
        "",
        "Weights: " + ", ".join(f"{k.replace('_', ' ')} {v:.0%}" for k, v in rubric.WEIGHTS.items())
        + ". Scores are 1-5; for risk and time to value, 5 is the good end (low risk, fast).",
        "",
        "Analyst scores are a **draft written by the coding agent for Sara to review**; the LLM columns are "
        "independent model scores (one use case per call, same anchors).",
        "",
    ]
    scorer_labels = [label for label in rub["models"] if label != "analyst_draft"]
    header = "| Rank | ID | Use case | V | F | D | R | T | Weighted | " + " | ".join(
        f"{label} rank" for label in scorer_labels) + " | Evidence |"
    lines += [header, "|" + "---|" * (10 + len(scorer_labels))]
    ai_rows = sorted([r for r in rub["table"] if "analyst_draft_rank" in r], key=lambda r: r["analyst_draft_rank"])
    for r in ai_rows:
        others = " | ".join(str(r.get(f"{label}_rank", "–")) for label in scorer_labels)
        lines.append(f"| {r['analyst_draft_rank']} | {r['use_case_id']} | **{r['name']}** ({r['ai_technique']}) | "
                     f"{r['value']} | {r['feasibility']} | {r['data_readiness']} | {r['risk']} | "
                     f"{r['time_to_value']} | "
                     f"{r['analyst_draft_total']:.2f} | {others} | {r['evidence']} |")
    lines += ["", "## Not AI, but do them anyway", "", "| ID | Change | Evidence |", "|---|---|---|"]
    for r in rub["table"]:
        if r["use_case_id"].startswith("N"):
            lines.append(f"| {r['use_case_id']} | **{r['name']}** | {r['evidence']} |")
    path = TARGET["docs"] / "use_case_portfolio.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path.relative_to(DOCS_DIR.parent))


# ---------- everything ----------

def rebuild(diagnostic_only: bool = False, out_dir: Path = RESULTS_DIR, fixture_results: list | None = None) -> dict:
    real = out_dir == RESULTS_DIR
    TARGET["charts"] = CHARTS_DIR if real else out_dir / "charts"
    TARGET["docs"] = DOCS_DIR if real else out_dir
    summary = run_diagnostic(out_dir)
    print(f"Diagnostic: {summary['cases']:,} cases, p50 {summary['throughput_p50_days']:.2f} d, "
          f"p90 {summary['throughput_p90_days']:.2f} d, rejected {summary['rejected_share']:.1%}")
    if diagnostic_only:
        return summary
    staff = theme_section(out_dir)
    facts = rubric.evidence_facts(summary, staff["shares"], {q: m for q, m in survey_means().items() if q != "n"})
    rub = rubric_section(out_dir, facts)
    pre = precheck_section(out_dir)
    money = roi_section(summary, pre, rub["top2"])
    report = clean({
        "run_date": RUN_DATE, "client": CLIENT_NAME,
        "fixture_checks": {"passed": sum(r["ok"] for r in fixture_results or []), "total": len(fixture_results or [])},
        "diagnostic": summary, "survey_means": survey_means(), "themes": staff, "rubric": rub,
        "precheck": pre, "roi": money, "portfolio_doc": write_portfolio(rub),
    })
    write_json(out_dir / "summary.json", report)
    print(f"Wrote {out_dir / 'summary.json'}, charts in {TARGET['charts']}, {money['workbook']}")
    return report


def load_summary(path: Path = RESULTS_DIR / "summary.json") -> dict:
    return read_json(path) if Path(path).exists() else {}
