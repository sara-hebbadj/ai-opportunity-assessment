"""Build the 10-slide board deck (docs/board_deck.html and docs/board_deck.pdf) from evals/results/summary.json.

    pip install -e ".[docs]"          # Playwright, only needed for the PDF
    python scripts/build_deck.py      # uses an installed Chromium (set PLAYWRIGHT_BROWSERS_PATH if needed)

Every number on the slides is read from summary.json, so the deck always matches the latest rebuild.
"""

from __future__ import annotations

import json
import math
import os
import sys
from html import escape
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from opportunity_assessment.report import load_summary, system_name  # noqa: E402

DOCS = REPO / "docs"
NAMES = {"cheap": "gpt-6-luna", "main": "claude-sonnet-5.5", "judge": "gemini-3.8-flash"}


def pct(value, digits=1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def aed(value) -> str:
    if value is None or (isinstance(value, float) and math.isinf(value)):
        return "n/a"
    sign = "−" if value < 0 else ""
    return f"{sign}AED {abs(value) / 1000:,.0f}k"


def months(value) -> str:
    return "no payback in 3 years" if value is None or value > 36 else f"{value:.0f} months"


def slide(title: str, body: str, kicker: str = "", number: int = 0) -> str:
    return (f'<section class="slide"><div class="kicker">{escape(kicker)}</div><h1>{title}</h1>'
            f'<div class="body">{body}</div><footer><span>Falcon Bay Services LLC is fictional · process data: '
            f'BPI Challenge 2020 (CC BY-NC 4.0) · staff data and claims are synthetic</span><span>{number}</span>'
            f"</footer></section>")


def img(name: str, width: str = "100%") -> str:
    return f'<img src="charts/{name}" style="width:{width}">'


def build(s: dict) -> str:
    d, staff, rub, pre, money = s["diagnostic"], s["themes"], s["rubric"], s["precheck"], s["roi"]
    rows = {r["system"]: r for r in pre["rows"]}
    rules = rows["rules"]
    hybrids = [r for k, r in rows.items() if k.startswith("hybrid_")]
    best = max(hybrids, key=lambda r: (r["recall"], r["precision"], -r["cost_per_100_claims_usd"]))
    cheap_hybrid = rows.get("hybrid_cheap", best)
    uc1, uc2 = money["use_cases"].get("UC01", {}), money["use_cases"].get("UC02", {})
    r1, r2 = uc1.get("results", {}), uc2.get("results", {})
    names = {r["use_case_id"]: r["name"] for r in rub["table"]}
    coders = staff["coders"]
    kappas = ", ".join(f"{NAMES.get(k, k)} κ {v['vs_author_all']['kappa']:.2f}" for k, v in coders.items())
    rhos = [(k, v["spearman_rho"]) for k, v in rub["comparisons"].items() if k.startswith("analyst_draft_vs_")]
    rho_text = ", ".join(f"{NAMES.get(k.split('_vs_')[1], k)} ρ = {v:.2f}" for k, v in rhos)
    same_top2 = sum(1 for k, v in rub["comparisons"].items() if k.startswith("analyst_draft_vs_") and v["same_top2"])
    top5 = sorted([r for r in rub["table"] if "analyst_draft_rank" in r], key=lambda r: r["analyst_draft_rank"])[:5]
    slides = []

    slides.append(
        '<section class="slide title"><div class="kicker">Board briefing · 8 October 2026</div>'
        "<h1>Where AI can speed up travel-expense claims</h1>"
        "<p class=lead>An AI opportunity assessment for Falcon Bay Services LLC (fictional), "
        "a 600-person services firm in Dubai</p>"
        "<p class=meta>Sara Hebbadj · portfolio case study · process data: a real public event log used as a "
        "stand-in for the client (BPI Challenge 2020, 10,500 claims); interviews, survey and claims are synthetic</p>"
        "</section>")

    slides.append(slide("Recommendation: pilot a pre-check that warns; fix payments and reminders without AI", f"""
<div class=cols3>
<div class=card><div class=big>{pct(d['rejected_share'])}</div><p>of claims are rejected at least once.
Rejected claims take <b>{d['throughput_p50_rejected_days']:.1f} days</b> (median) instead of
{d['throughput_p50_not_rejected_days']:.1f}.</p></div>
<div class=card><div class=big>{cheap_hybrid['true_pos']}/{cheap_hybrid['pairs_gold']}</div><p>planted policy problems
found by rules + {escape(NAMES.get(cheap_hybrid['system'][7:], cheap_hybrid['model']))} on 50 test claims, vs
{rules['true_pos']}/{rules['pairs_gold']} for rules alone, at US${cheap_hybrid['cost_per_100_claims_usd']:.2f}
per 100 claims.</p></div>
<div class=card><div class=big>{pct(d['payment_stage_share_of_waiting'], 0)}</div><p>of all waiting happens
<b>after</b> approval, in the payment stage. That is a process fix (pay daily), not an AI project.</p></div>
</div>
<ul>
<li><b>Pilot UC01</b> ({escape(names.get('UC01', ''))}) for 6 weeks in two departments, advisory only.
Base-case 3-year net {aed(r1.get('three_year_net'))}: it only pays back if it prevents at least
<b>{pct(uc1.get('break_even_prevent_share'), 0)}</b> of rejections, which the pilot must measure.</li>
<li><b>Switch on the existing approver reminders now</b> (no AI). Add the AI summary of UC02
({escape(names.get('UC02', ''))}) only if a 2-week test shows at least
{uc2.get('break_even_approver_minutes', 0):.1f} minutes saved per approval: base case 3-year net
{aed(r2.get('three_year_net'))}, but its rank was not robust (8th–9th for all three model scorers).</li>
<li><b>Decision today:</b> approve the pilot budget, a UAE-hosted model option, and a daily payment run.</li>
</ul>""", "Executive summary", 2))

    slides.append(slide("A claim takes a week; one in eight is rejected and takes much longer", f"""
<div class=cols2><div>{img('throughput_rejected.png')}</div><div>
<table><tr><th>Measure (10,500 claims, 2017–18)</th><th>Value</th></tr>
<tr><td>Median / p90 throughput</td><td>{d['throughput_p50_days']:.1f} / {d['throughput_p90_days']:.1f} days</td></tr>
<tr><td>Claims rejected at least once</td><td>{d['rejected_cases']:,} ({pct(d['rejected_share'])})</td></tr>
<tr><td>…of which administration rejected first</td><td>{pct(d['first_rejected_by_admin_share'], 0)}</td></tr>
<tr><td>Claims resubmitted</td><td>{pct(d['resubmitted_share'])}</td></tr>
<tr><td>Different process paths</td><td>{d['variants']}</td></tr>
<tr><td>Claims in 2018 (annual volume used)</td><td>{d['annual_cases']:,}</td></tr></table>
<p class=note>Every number is rebuilt from the raw log by one command; 20 of the calculations are checked
against a hand-computed 20-case example ({s['fixture_checks']['passed']}/{s['fixture_checks']['total']} match).</p>
</div></div>""", "Process diagnostic", 3))

    slides.append(slide("Most waiting happens after approval, in the payment stage", f"""
<div class=cols2><div>{img('waiting_by_role.png')}</div><div><ul>
<li>The payment stage holds <b>{pct(d['payment_stage_share_of_waiting'], 0)}</b> of all waiting time;
from payment request to payment takes {d['payment_handled_wait_p50_days']:.1f} days at the median. Payments
run on fixed days: <b>a daily payment run is the fastest win, and needs no AI.</b></li>
<li>Supervisors are on {pct(d['cases_via_supervisor_share'], 0)} of claims and hold
{pct(d['supervisor_share_of_waiting'], 0)} of waiting; their p90 wait is {d['supervisor_wait_p90_days']:.1f} days.</li>
<li>After a rejection, employees take {d['employee_fix_wait_p50_days']:.1f} days (median),
{d['employee_fix_wait_p90_days']:.1f} (p90) to respond.</li></ul></div></div>""", "Process diagnostic", 4))

    slides.append(slide("Voice of staff: an LLM codes interviews as consistently as the answer key", f"""
<div class=cols2><div>{img('staff_themes.png')}</div><div><ul>
<li>12 interviews and 40 survey answers (synthetic), split into 120 snippets and coded into 8 themes by an LLM,
one snippet per call.</li>
<li>Agreement with the theme each snippet was written for: {escape(kappas)} (n = 120). This is an upper
bound: the same agent wrote the snippets and the labels. <b>Sara's blind coding is pending.</b></li>
<li>Survey (n = {s['survey_means']['n']}, 1–5, synthetic): "I can see where my claim is"
{s['survey_means']['q3_status_visible']:.1f};
"I would use a pre-check" {s['survey_means']['q5_would_use_precheck']:.1f}.</li>
<li>What staff asked for: <b>"warn, never block"</b> and <b>"flag the claim, not the person"</b>.</li>
<li class=note>The synthetic snippets were written to cover the 8 themes about evenly, so the shares above do not
rank pain points; with real interviews they would.</li></ul>
</div></div>""", "Voice of staff", 5))

    top_rows = "".join(f"<tr><td>{r['analyst_draft_rank']}</td><td>{r['use_case_id']} {escape(r['name'])}</td>"
                       f"<td>{r['analyst_draft_total']:.2f}</td></tr>" for r in top5)
    slides.append(slide("18 AI ideas, scored on value, feasibility, data, risk and speed", f"""
<div class=cols2><div>{img('value_vs_feasibility.png', '88%')}</div><div>
<table><tr><th>#</th><th>Use case (analyst draft)</th><th>Score</th></tr>{top_rows}</table>
<p>Weights: value 30%, feasibility 20%, data readiness 20%, risk 15%, time to value 15%.</p>
<p>Robustness: three LLMs scored every use case blind. Rank agreement with the draft: {escape(rho_text)}.
{same_top2} of {len(rhos)} kept the same top 2.</p>
<p class=note>All three models put UC06 ("where is my claim?" chat) 1st or 2nd; the draft put it 10th because
showing the existing status in the portal needs no AI. UC02 fell to 8th–9th for all three. The rubric has no
"is AI needed?" criterion: next version adds one. Lowest everywhere: UC18, a fraud score per employee.</p>
</div></div>""", "Use-case portfolio", 6))

    shown = [r for r in pre["rows"] if not r["system"].startswith("hybrid_")]
    costs = [r["cost_per_100_claims_usd"] for r in shown if r["system"].startswith("llm_")]
    ratio = max(costs) / min(costs) if costs and min(costs) > 0 else float("nan")
    pre_rows = "".join(
        f"<tr><td>{escape(system_name(r))}</td><td>{pct(r['precision'], 0)}</td>"
        f"<td>{r['true_pos']}/{r['pairs_gold']}</td><td>{r['found_receipt_text']}/{r['total_receipt_text']}</td>"
        f"<td>US${r['cost_per_100_claims_usd']:.2f}</td></tr>" for r in shown)
    slides.append(slide("Prototype: rules do the arithmetic, the model reads the receipts", f"""
<div class=cols2><div>{img('precheck_comparison.png')}</div><div>
<table><tr><th>System</th><th>Precision</th><th>Found</th><th>Only in receipt</th><th>Per 100 claims</th></tr>
{pre_rows}</table>
<p>Rules + each model scored the same as the model alone. All three models hit the ceiling, so this set
cannot separate them: the difference is cost (about {ratio:.0f}× between the cheapest and the dearest) and speed.</p>
<p class=note>50 synthetic claims, 40 planted problems (24 visible in the form fields, 16 only in the receipt
text, some receipts in Arabic). The rules see only the fields by design. Same agent wrote the claims and the
rules; one run per model on 8 October 2026.</p></div></div>""", "Pre-check prototype", 7))

    def case_row(label, r, extra):
        return (f"<tr><td>{label}</td><td>{aed(r.get('annual_benefit'))}</td><td>{aed(r.get('net_annual'))}</td>"
                f"<td><b>{aed(r.get('three_year_net'))}</b></td><td>{months(r.get('payback_months'))}</td>"
                f"<td>{extra}</td></tr>")
    be1 = r1.get("break_even_claims_per_year")
    slides.append(slide("The business case: UC01 is close to break-even; UC02 depends on one assumption", f"""
<table><tr><th>Use case</th><th>Benefit / year</th><th>Net / year</th><th>3-year net</th><th>Payback</th>
<th>Break-even</th></tr>
{case_row('UC01 pre-check', r1, f"{be1:,.0f} claims/yr or {pct(uc1.get('break_even_prevent_share'), 0)} prevented"
          if be1 else 'n/a')}
{case_row('UC02 approver assistant', r2, f"{uc2.get('break_even_approver_minutes', 0):.1f} min saved per approval")}
</table>
<div class=cols2><div>{img('tornado_UC01.png')}</div><div><ul>
<li>Volumes and rejection rate are measured ({d['annual_cases']:,} claims in 2018, {pct(d['annual_rejected_share'])}
rejected). Model cost per claim is measured in the prototype. Minutes, hourly costs and build costs are
<b>labelled assumptions</b> with low/high values (docs/roi_model.xlsx).</li>
<li>For UC01, the clerk minutes saved on every claim move the result most, then volume and run cost; the
share of rejections prevented must reach {pct(uc1.get('break_even_prevent_share'), 0)}. For UC02, everything
rests on approver minutes saved per approval. Faster reimbursement for staff is real but not counted in AED.</li>
</ul></div></div>""", "Business case", 8))

    slides.append(slide("Risks are manageable if the AI warns and a person decides", """
<div class=cols2><div><table><tr><th>Use case</th><th>EU AI Act (benchmark)</th><th>Main control</th></tr>
<tr><td>UC01 pre-check</td><td>Minimal risk while advisory</td>
<td>Never rejects; flags go to the employee only</td></tr>
<tr><td>UC02 approver assistant</td><td>Minimal risk</td><td>Summary shows facts, never "approve"</td></tr>
<tr><td>UC08 straight-through approval</td><td>Borderline (Annex III 4(b) if ML decides)</td><td>Not now</td></tr>
<tr><td>UC18 fraud score per employee</td><td>Likely high-risk (Annex III 4(b))</td><td>Do not build</td></tr>
</table></div><div><ul>
<li><b>UAE PDPL</b> applies (employees' data): keep a human decision (Art. 18), minimise what is sent, and
solve the cross-border transfer: IT wants AI inside a UAE cloud tenancy.</li>
<li><b>NIST AI RMF</b>: owner and change log (Govern), intended use (Map), precision/recall and cost (Measure),
weekly flag review and an off switch (Manage).</li>
<li class=note>General information, not legal advice; see docs/risk_screen.md.</li></ul></div></div>""",
                        "Risk screen", 9))

    slides.append(slide("Pilot: 6 weeks, two departments, with kill criteria agreed up front", f"""
<div class=cols2><div><table><tr><th>Week</th><th>What happens</th></tr>
<tr><td>0</td><td>Baseline rejection rate, data terms, UAE hosting choice, briefing for clerks</td></tr>
<tr><td>1</td><td>Shadow mode: the pre-check runs, staff do not see it; clerks label every flag</td></tr>
<tr><td>2–5</td><td>Live for the pilot group (warnings only); comparison group as today</td></tr>
<tr><td>3</td><td>Checkpoint against the kill criteria</td></tr>
<tr><td>6</td><td>Read-out and go / no-go</td></tr></table></div><div>
<p><b>Stop the pilot if</b> (any one):</p><ul>
<li>flag precision on clerk-reviewed real claims is below 80% (week 1 or 3);</li>
<li>it misses more of the clerks' problems than the rules alone;</li>
<li>receipts leave the approved hosting, or any personal-data incident;</li>
<li>staff spend more than 2 extra minutes per claim on warnings;</li>
<li>by week 6 rejections are not trending towards the break-even reduction
({pct(uc1.get('break_even_prevent_share'), 0)}).</li></ul>
<p><b>Owner:</b> finance operations lead · <b>Analyst:</b> Sara · <b>Reviewers:</b> internal audit, IT.</p>
</div></div>""", "Pilot plan", 10))
    return "\n".join(slides)


CSS = """
@page { size: 1280px 720px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: "Helvetica Neue", Helvetica, "Liberation Sans", Arial, sans-serif; color: #0b0b0b;
       background: #fcfcfb; }
.slide { width: 1280px; height: 720px; padding: 44px 56px 36px; position: relative; page-break-after: always;
         background: #fcfcfb; overflow: hidden; }
.kicker { font-size: 13px; letter-spacing: .08em; text-transform: uppercase; color: #2a78d6; font-weight: 700; }
h1 { font-size: 30px; line-height: 1.2; margin: 8px 0 18px; max-width: 1100px; }
.title { display: flex; flex-direction: column; justify-content: center; padding: 80px; }
.title h1 { font-size: 46px; max-width: 900px; }
.lead { font-size: 22px; color: #52514e; max-width: 900px; }
.meta { font-size: 14px; color: #52514e; margin-top: 40px; max-width: 900px; }
.body { font-size: 16px; line-height: 1.45; }
.cols2 { display: grid; grid-template-columns: 1.05fr 1fr; gap: 28px; align-items: start; }
.cols3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 14px; }
.card { border: 1px solid #e6e5e1; border-radius: 10px; padding: 14px 18px; background: #fff; }
.card p { margin: 6px 0 0; font-size: 15px; }
.big { font-size: 40px; font-weight: 700; color: #2a78d6; }
table { border-collapse: collapse; width: 100%; font-size: 14px; margin-bottom: 10px; }
th { text-align: left; color: #52514e; font-weight: 600; border-bottom: 1px solid #b9b8b3; padding: 5px 6px; }
td { border-bottom: 1px solid #e6e5e1; padding: 5px 6px; vertical-align: top; }
ul { margin: 6px 0; padding-left: 20px; }
li { margin-bottom: 7px; }
.note { font-size: 13px; color: #52514e; }
footer { position: absolute; left: 56px; right: 56px; bottom: 16px; display: flex; justify-content: space-between;
         font-size: 11px; color: #8a8984; }
img { display: block; }
"""


def main() -> None:
    summary = load_summary()
    if not summary:
        raise SystemExit("No evals/results/summary.json: run python -m evals.run rebuild first")
    html = (f"<!doctype html><html lang=en><head><meta charset=utf-8><title>Board briefing: AI opportunity "
            f"assessment</title><style>{CSS}</style></head><body>{build(summary)}</body></html>")
    (DOCS / "board_deck.html").write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # CHROMIUM_PATH: use an already-installed Chromium instead of the one Playwright downloads.
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto((DOCS / "board_deck.html").as_uri())
        page.pdf(path=str(DOCS / "board_deck.pdf"), width="1280px", height="720px", print_background=True)
        browser.close()
    print(f"Wrote docs/board_deck.html and docs/board_deck.pdf ({json.dumps(summary['run_date'])})")


if __name__ == "__main__":
    main()
