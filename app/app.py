"""Gradio dashboard for the AI opportunity assessment.

Run:  python app/app.py     then open http://127.0.0.1:7860

- Every number comes from evals/results/summary.json (built by `python -m evals.run rebuild`).
- The "Pre-check" tab runs the rules baseline live. With OPENROUTER_API_KEY and MODEL_CHEAP set it also
  calls the model live; without them it is in demo mode and shows the recorded model answer from the
  evaluation run instead (clearly labelled).
All company data is fictional (Falcon Bay Services LLC); the event log is public research data (CC BY-NC 4.0).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # run without installing the package

import gradio as gr  # noqa: E402

from opportunity_assessment import precheck, roi, rubric  # noqa: E402
from opportunity_assessment.config import CHARTS_DIR, RESULTS_DIR, env, model_id  # noqa: E402
from opportunity_assessment.llm import make_client  # noqa: E402
from opportunity_assessment.report import load_summary, measured_inputs  # noqa: E402

SUMMARY = load_summary()
LIVE = bool(env("OPENROUTER_API_KEY") and env("MODEL_CHEAP"))
CLAIMS = {c["claim_id"]: c for c in precheck.load_claims()}
POLICY = precheck.POLICY_PATH.read_text(encoding="utf-8")
RECORDED_RUN = RESULTS_DIR / "precheck_cheap.jsonl"

BANNER = (
    "**AI opportunity assessment for Falcon Bay Services LLC (fictional), a 600-person Dubai services firm.** "
    "The process data is a real public event log (BPI Challenge 2020, travel-expense claims at a Dutch "
    "university, CC BY-NC 4.0), used as a stand-in for the client's process. Staff interviews, survey and "
    "claims are synthetic.\n\n"
    + (f"Live AI: the Pre-check tab calls `{env('MODEL_CHEAP')}` through OpenRouter." if LIVE else
       "**Demo mode — live AI is off; add OPENROUTER_API_KEY in Space settings to enable** (plus a `MODEL_CHEAP` "
       "variable). The Pre-check tab shows the model's recorded answer from the evaluation run of 8 October 2026; "
       "the rules check runs live.")
)


def pct(value) -> str:
    return "–" if value is None else f"{value:.1%}"


def chart(name: str) -> str | None:
    path = CHARTS_DIR / name
    return str(path) if path.exists() else None


# ---------- overview ----------

def overview_markdown() -> str:
    if not SUMMARY:
        return "No results yet. Run `python -m evals.run rebuild` first."
    d, pre = SUMMARY["diagnostic"], SUMMARY["precheck"]
    best = max((r for r in pre["rows"] if r["system"].startswith("hybrid_")), key=lambda r: r["recall"], default=None)
    rules = pre["rows"][0]
    lines = [
        "### Headline numbers",
        f"- **{d['cases']:,} claims** in the log; median throughput **{d['throughput_p50_days']:.1f} days**, "
        f"p90 **{d['throughput_p90_days']:.1f} days**.",
        f"- **{pct(d['rejected_share'])}** of claims are rejected at least once; those take "
        f"**{d['throughput_p50_rejected_days']:.1f} days** at the median instead of "
        f"{d['throughput_p50_not_rejected_days']:.1f}.",
        f"- The payment stage holds **{pct(d['payment_stage_share_of_waiting'])}** of all waiting time "
        "(a process fix, not an AI one).",
        f"- Pre-check prototype on 50 synthetic claims: rules only find {rules['true_pos']}/{rules['pairs_gold']} "
        "planted problems"
        + (f"; rules + `{best['model']}` find {best['true_pos']}/{best['pairs_gold']} "
           f"with precision {pct(best['precision'])}." if best else "."),
        f"- Top 2 use cases (analyst draft ranking): **{', '.join(SUMMARY['rubric']['top2'])}**. Three LLM scorers "
        "agreed on the first more than on the second (see the README, \"What failed\").",
    ]
    return "\n".join(lines)


# ---------- portfolio: re-rank with your own weights ----------

def rerank(value, feasibility, data_readiness, risk, time_to_value):
    weights = {"value": value, "feasibility": feasibility, "data_readiness": data_readiness, "risk": risk,
               "time_to_value": time_to_value}
    total = sum(weights.values()) or 1
    weights = {k: v / total for k, v in weights.items()}
    rows = []
    for row in SUMMARY.get("rubric", {}).get("table", []):
        if "value" not in row:
            continue
        score = sum(weights[c] * row[c] for c in rubric.CRITERIA)
        rows.append([row["use_case_id"], row["name"], *[row[c] for c in rubric.CRITERIA], round(score, 2),
                     row.get("analyst_draft_rank")])
    rows.sort(key=lambda r: -r[7])
    note = "Weights after scaling to 100%: " + ", ".join(f"{k.replace('_', ' ')} {v:.0%}" for k, v in weights.items())
    return rows, note


# ---------- business case: change the assumptions ----------

def roi_inputs(use_case: str) -> dict:
    measured = measured_inputs(SUMMARY["diagnostic"], SUMMARY["precheck"])
    return roi.base_inputs(roi.load_assumptions(use_case, measured))


def business_case(use_case, claims_per_year, key_share, minutes, build_cost, run_cost):
    inputs = roi_inputs(use_case)
    inputs.update({"annual_claims": claims_per_year, "build_cost": build_cost, "run_cost_per_year": run_cost})
    if use_case == "UC01":
        inputs.update({"prevent_share": key_share, "rework_staff_minutes": minutes})
    else:
        inputs.update({"approver_minutes_saved": minutes})
    r = roi.calculate(use_case, inputs)
    payback = "no payback" if r["payback_months"] == float("inf") else f"{r['payback_months']:.1f} months"
    even = ("never (each claim costs more than it saves)" if r["break_even_claims_per_year"] == float("inf")
            else f"{r['break_even_claims_per_year']:,.0f} claims/year")
    return (f"| Result | Value |\n|---|---|\n| Annual benefit | AED {r['annual_benefit']:,.0f} |\n"
            f"| Annual AI model cost | AED {r['annual_ai_cost']:,.0f} |\n"
            f"| Net per year | AED {r['net_annual']:,.0f} |\n"
            f"| **3-year net** (after build cost) | **AED {r['three_year_net']:,.0f}** |\n| Payback | {payback} |\n"
            f"| Break-even volume | {even} |"), chart(f"tornado_{use_case}.png")


def roi_defaults(use_case: str):
    a = roi_inputs(use_case)
    key_share = a.get("prevent_share", 0.0)
    minutes = a["rework_staff_minutes"] if use_case == "UC01" else a["approver_minutes_saved"]
    return (gr.update(value=a["annual_claims"]), gr.update(value=key_share, interactive=use_case == "UC01"),
            gr.update(value=minutes, label="Rework minutes per rejection" if use_case == "UC01"
                      else "Approver minutes saved per approval"),
            gr.update(value=a["build_cost"]), gr.update(value=a["run_cost_per_year"]))


# ---------- pre-check demo ----------

def recorded_answers() -> dict:
    if not RECORDED_RUN.exists():
        return {}
    rows = [json.loads(line) for line in RECORDED_RUN.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["claim_id"]: r for r in rows}


RECORDED = recorded_answers()


def claim_markdown(claim: dict) -> str:
    t = claim["trip"]
    lines = [f"**{claim['claim_id']}** · {claim['employee']} · {t['purpose']} in {t['destination']} "
             f"({t['start']} to {t['end']}) · submitted {claim['submitted_on']} · pre-approval: "
             f"{claim['pre_approval_ref'] or 'none'}"]
    for line in claim["lines"]:
        lines.append(f"\n**{line['line_id']}** {line['date']} · {line['category']} · {line['vendor']} · "
                     f"{line['description']} · **AED {line['amount_aed']:,.2f}** · receipt: "
                     f"{'yes' if line['receipt_attached'] else 'no'}")
        if line["receipt_text"]:
            lines.append("```\n" + line["receipt_text"] + "\n```")
    if claim["previous_claims"]:
        lines.append("\nEarlier claims by this employee: " + "; ".join(
            f"{p['claim_id']} {p['date']} {p['vendor']} AED {p['amount_aed']:,.2f} (receipt {p['receipt_no']})"
            for p in claim["previous_claims"]))
    if claim["justification"]:
        lines.append(f"\nJustification: {claim['justification']}")
    return "\n".join(lines)


def run_check(claim_id: str):
    claim = CLAIMS[claim_id]
    rules = sorted(precheck.rules_check(claim))
    if LIVE:
        checked = precheck.llm_check(make_client(offline=False), claim, POLICY, role="cheap")
        model_text = f"**Live model ({model_id('cheap')}):** " + _codes(checked["codes"], checked["problems"])
    elif claim_id in RECORDED:
        r = RECORDED[claim_id]
        model_text = (f"**Recorded model answer** ({r['model']}, evaluation run 8 Oct 2026, not live): "
                      + _codes(r["codes"], r.get("problems", [])))
    else:
        model_text = "Model answer: not available in demo mode (no recorded run found)."
    gold = sorted(precheck.gold_codes(claim))
    return (claim_markdown(claim), f"**Rules only (live, no AI):** {', '.join(rules) or 'no problems found'}",
            model_text, f"**Planted problems (answer key):** {', '.join(gold) or 'none: this claim is clean'}")


def _codes(codes, problems) -> str:
    if not codes:
        return "no problems found"
    details = [f"`{p.get('code')}` {p.get('line_id', '')}: {p.get('evidence', '')}" for p in problems
               if isinstance(p, dict)]
    return ", ".join(sorted(codes)) + ("\n\n" + "\n\n".join(details) if details else "")


# ---------- layout ----------

def build() -> gr.Blocks:
    with gr.Blocks(title="AI opportunity assessment") as demo:
        gr.Markdown("# AI opportunity assessment: travel-expense claims")
        gr.Markdown(BANNER)
        with gr.Tab("Overview"):
            gr.Markdown(overview_markdown())
            gr.Image(chart("value_vs_feasibility.png"), show_label=False, height=420)
        with gr.Tab("Process diagnostic"):
            gr.Image(chart("waiting_by_role.png"), show_label=False)
            gr.Image(chart("throughput_rejected.png"), show_label=False)
        with gr.Tab("Voice of staff"):
            gr.Image(chart("staff_themes.png"), show_label=False)
            gr.Markdown(staff_markdown())
        with gr.Tab("Use-case portfolio"):
            gr.Markdown("Change the weights and the ranking updates. Scores are the analyst draft (1-5).")
            sliders = [gr.Slider(0, 50, value=round(w * 100), step=5, label=c.replace("_", " "))
                       for c, w in rubric.WEIGHTS.items()]
            note = gr.Markdown()
            table = gr.Dataframe(headers=["ID", "Use case", "Value", "Feasibility", "Data", "Risk (5=low)",
                                          "Speed", "Weighted", "Draft rank"], interactive=False, wrap=True)
            for slider in sliders:
                slider.change(rerank, sliders, [table, note])
            demo.load(rerank, sliders, [table, note])
        with gr.Tab("Business case"):
            use_case = gr.Radio(["UC01", "UC02"], value="UC01",
                                label="Use case (UC01 pre-check, UC02 approver assistant)")
            with gr.Row():
                claims_per_year = gr.Number(label="Claims per year")
                key_share = gr.Slider(0, 1, step=0.05, label="Share of rejections prevented (UC01)")
                minutes = gr.Slider(0, 90, step=0.5, label="Rework minutes per rejection")
            with gr.Row():
                build_cost = gr.Number(label="Build cost (AED)")
                run_cost = gr.Number(label="Run cost per year (AED)")
            result = gr.Markdown()
            tornado_img = gr.Image(show_label=False)
            inputs = [use_case, claims_per_year, key_share, minutes, build_cost, run_cost]
            use_case.change(roi_defaults, use_case, inputs[1:]).then(business_case, inputs, [result, tornado_img])
            for control in inputs[1:]:
                control.change(business_case, inputs, [result, tornado_img])
            demo.load(roi_defaults, use_case, inputs[1:]).then(business_case, inputs, [result, tornado_img])
        with gr.Tab("Pre-check"):
            gr.Markdown("Pick one of the 50 synthetic claims. The rules check reads only the form fields; the "
                        "model also reads the receipts. The pre-check only **warns**: it never rejects a claim.")
            claim_id = gr.Dropdown(sorted(CLAIMS), value="FB-C001", label="Claim")
            button = gr.Button("Check this claim", variant="primary")
            rules_out, model_out, gold_out = gr.Markdown(), gr.Markdown(), gr.Markdown()
            claim_out = gr.Markdown()
            button.click(run_check, claim_id, [claim_out, rules_out, model_out, gold_out])
    return demo


def staff_markdown() -> str:
    staff = SUMMARY.get("themes", {})
    lines = ["| Coder (model) | Agreement with the author's intended theme | Cohen's kappa |", "|---|---|---|"]
    for label, coder in staff.get("coders", {}).items():
        vs = coder["vs_author_all"]
        lines.append(f"| {label} ({coder['model']}) | {pct(vs['agreement'])} of {vs['n']} | {vs['kappa']:.2f} |")
    lines.append("\nSara's own blind coding of the 120 snippets is pending (`evals/sara_coding_sheet.csv`). "
                 "The author labels were written by the same coding agent that wrote the snippets.")
    return "\n".join(lines)


if __name__ == "__main__":
    build().launch()
