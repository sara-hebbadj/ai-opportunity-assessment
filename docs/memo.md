# Memo: where AI can speed up travel-expense claims

| | |
|---|---|
| **To** | Chief Financial Officer and Chief Operating Officer, Falcon Bay Services LLC (fictional) |
| **From** | Sara Hebbadj, AI solutions analyst (portfolio case study; drafted with a coding agent) |
| **Date** | 8 October 2026 |
| **Decision asked** | Approve a 6-week pilot of a claim pre-check, a UAE-hosted model option, and a daily payment run |

*The process data is a real public event log used as a stand-in for Falcon Bay (BPI Challenge 2020: 10,500
travel-expense claims at a Dutch university, 2017–18, CC BY-NC 4.0). Interviews, survey and test claims are
synthetic. Every number below is in `evals/results/summary.json`; money figures marked "assumption" are
guesses to be replaced with Falcon Bay's own data.*

## 1. Recommendation

1. **Pilot a receipt and policy pre-check (UC01) for 6 weeks in two departments.** It reads a claim and its
   receipts before submission and **warns** the employee; it never rejects. It targets the biggest avoidable
   loop: 12.4% of claims are rejected at least once, and those take 11.2 days at the median instead of 7.3.
2. **Fix two things that need no AI:** pay approved claims daily (the payment stage holds 56% of all waiting
   time), and switch on the approval reminders the system already has.
3. **Test the AI approver summary (UC02) cheaply, not as a project.** Its business case rests on one
   assumption (minutes saved per approval) and its ranking was not robust.

## 2. What we found

- **A claim takes 7.3 days at the median and 20.1 days at p90.** 99 different process paths; 44% of
  claims follow the main one.
- **Rejections are the main avoidable delay.** 1,301 claims (12.4%) were rejected at least once; the
  administration check rejected first in 64% of them; 9.7% of claims were resubmitted.
- **Most waiting is after approval.** The payment stage (request to payment: 3.2 days median) holds 56%
  of all waiting time; supervisors hold 17%. Payment timing is a scheduling decision, not an AI problem.
- **Staff ask for help, with conditions.** In the (synthetic) interviews, staff want a tool that "warns,
  never blocks" and that "flags the claim, not the person"; IT wants AI inside a UAE cloud tenancy.
  An LLM coded the 120 interview and survey snippets into 8 themes with κ 0.93–0.97 against the intended
  themes (three models). That is an upper bound: the same agent wrote the snippets and the answer key, and
  the themes were spread evenly by design, so the shares do not rank the pains. Sara's own blind coding is
  the real test and is pending.

## 3. Options and how they were ranked

We listed **18 AI use cases and 2 non-AI changes**, each tied to a measured number or a staff theme, and
scored the AI ones 1–5 on value (30%), feasibility (20%), data readiness (20%), risk (15%, 5 = low) and time
to value (15%). The draft ranking put the pre-check (UC01, 4.10) first and the approver assistant (UC02,
4.00) second; a fraud-risk score per employee (UC18) came last.

**Robustness check.** Three language models scored every use case blind, one at a time. Rank agreement with
the draft was moderate (Spearman ρ 0.54, 0.64 and 0.79). UC01 stayed in the top 3 for two of the three
models. UC02 fell to 8th–9th for all three: approvers already wait under a day at the median, and plain
reminders capture much of the benefit. All three put a "where is my claim?" chat (UC06) first or second;
the draft put it 10th because the status already exists in the database and can be shown without AI. The
lesson: the rubric needs an explicit "is AI needed?" criterion, which the next version will add.

## 4. Business case (top 2 by the draft ranking)

| | UC01 pre-check | UC02 approver assistant |
|---|---|---|
| Annual benefit | AED 42,564 | AED 80,452 |
| Net per year (after model and run costs) | AED 18,256 | AED 65,446 |
| 3-year net (after build cost) | **−AED 5,232** | **AED 156,339** |
| Payback | 39 months | 7 months |
| Break-even | 8,601 claims a year (Falcon Bay: 8,260), or 42% of rejections prevented (assumed 40%) | 0.53 approver minutes saved per approval (assumed 1.5) |

Measured inputs: 8,260 claims a year and a 13.0% rejection rate (2018), 1.30 approvals per claim, and a model
cost of US$0.016 per 100 claims for the pre-check (`openai/gpt-6-luna`). Minutes, hourly costs, build and run
costs are labelled assumptions with low and high values in `docs/roi_model.xlsx`; Excel and Python give the
same results. For UC01, **clerk minutes saved on every claim** moves the 3-year net most (−AED 55k to
+AED 94k across its range), then volume and run cost. Faster reimbursement for staff is real but not counted.

## 5. Prototype evidence

On 50 synthetic claims with 40 planted problems, plain rules on the form fields found 24/40 with no false
flags; they cannot read receipts. Each of three models (`openai/gpt-6-luna`, `google/gemini-3.8-flash`,
`anthropic/claude-sonnet-5.5`) found **40/40 with 0 false flags**, including the 16 problems visible only in
the receipt text (some receipts in Arabic). Cost per 100 claims: US$0.016, US$0.15 and US$0.53. The set is too
easy to separate the models (all at the ceiling), and real receipts are photos, not clean text. So the
prototype shows that the approach works and what it costs, not how accurate it will be on real claims: the
pilot's shadow week measures that.

## 6. Risks

Advisory use keeps the pre-check and the approver summary out of high-risk territory under the EU AI Act
benchmark (Annex III point 4, workers' management). A per-employee fraud score would likely be high-risk and is
not recommended. The UAE PDPL applies to employees' data: keep a human decision (Art. 18), send the model the
claim but not the person's name or bank details, and settle the cross-border transfer before go-live. Details:
`docs/risk_screen.md` (general information, not legal advice).

## 7. The pilot and when to stop it

Owner: finance operations lead. Week 0 baseline and data terms; week 1 shadow mode (clerks label every flag);
weeks 2–5 live warnings for about 60 travellers; week 3 checkpoint; week 6 go / no-go. **Stop if** flag
precision on real claims is below 80%, if it misses more than the rules alone, if any personal-data incident
occurs, if warnings cost staff more than 2 minutes per claim, or if by week 6 rejections are not trending
towards the 42% break-even. Full plan: `docs/pilot_plan.md`.

## 8. What this analysis cannot tell you

The log is a Dutch university's process, not Falcon Bay's; the staff data and test claims are synthetic and were
written by the same agent that built the checks; each model ran once; the Arabic texts are not yet reviewed by a
native speaker; and the money figures depend on labelled assumptions. The pilot replaces the most important
assumptions with Falcon Bay's own numbers.
