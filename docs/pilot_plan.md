# Pilot plan: UC01 receipt and policy pre-check

*Falcon Bay Services LLC is fictional. Numbers come from `evals/results/summary.json` (8 October 2026);
the ROI inputs marked "assumption" are guesses to be replaced with the client's own numbers.*

## 1. What we are testing

**The idea.** Before an employee submits a travel-expense claim, a pre-check reads the claim and its
receipts, compares them with the travel policy, and **warns** the employee about likely problems (missing
receipt, over a limit, outside the trip dates, alcohol on the bill, amount that does not match the receipt,
a receipt claimed before, a missing pre-approval, a late claim). It never rejects or blocks a claim, and its
warnings go only to the employee.

**Design.** Plain rules check the form fields (limits, dates, deadlines, duplicates); a language model reads
the receipt text. In the prototype, rules alone found 24 of 40 planted problems; rules plus a model found 40 of
40 with no false flags, on 50 synthetic claims, for each of the three models tried (see the README).

**The question the pilot must answer.** Does the pre-check cut rejections enough to pay for itself? With
the base-case assumptions the 3-year net is about −AED 5k: break-even needs the pre-check to prevent about
**42% of rejections** (the base case assumes 40%) or to save clerks time on every claim. The tornado chart
shows that "clerk minutes saved per claim" moves the result most, so the pilot measures that too.

## 2. People

| Role | Who | Does what |
|---|---|---|
| Business owner | Finance operations lead | Owns the pilot, decides go / no-go, can stop it at any time |
| AI analyst | Sara Hebbadj | Builds the evaluation, runs the weekly review, writes the read-out |
| Finance clerks (2) | Travel administration | Label every flag in shadow week; record check time per claim |
| IT | Finance systems analyst | Integration, hosting in an approved region, access and logging |
| Reviewer | Internal audit | Reviews the flag log and the kill-criteria decisions |
| Pilot group | Two departments, about 60 frequent travellers | Use the pre-check; answer a 3-question survey in weeks 3 and 6 |
| Comparison group | Two similar departments | Work as today (no pre-check) |

## 3. Timeline (6 weeks)

| Week | Activity | Output |
|---|---|---|
| 0 | Baseline rejection rate and clerk check time for both groups (last 6 months from the claim system); data-processing terms and the hosting decision (UAE region or approved transfer); 30-minute briefing for clerks and pilot users; re-run the 50-claim regression set | Baseline sheet; signed-off data terms |
| 1 | **Shadow mode:** the pre-check runs on every pilot claim but nobody sees the warnings; clerks label each flag as right or wrong and note problems it missed | Real-claim precision and miss rate |
| 2–5 | **Live, warnings only**, for the pilot group | Weekly flag review (sample of 30 flags) |
| 3 | **Checkpoint** against the kill criteria below | Continue / fix / stop |
| 6 | Read-out: rejection rate change (pilot vs comparison), clerk minutes, cost, staff survey, updated ROI | Go / no-go for a wider roll-out |

## 4. Success metrics

| Metric | How measured | Target |
|---|---|---|
| Share of rejections prevented | Rejection rate, pilot vs comparison group, before vs during (difference in differences) | ≥ 42% (break-even); report the confidence interval, the sample is small |
| Flag precision on real claims | Clerk labels in shadow week and weekly samples | ≥ 85% |
| Problems missed | Problems clerks find that the pre-check did not flag, vs the rules alone | Fewer misses than the rules alone |
| Clerk minutes per claim | Timed sample, pilot vs comparison | Measure (base case assumes 1 minute saved) |
| Employee minutes added | Short survey + click timing | ≤ 1 minute per claim |
| Model cost per 100 claims | OpenRouter `usage.cost` in traces | Stays near the prototype's cost; alert above US$1 |
| Blocked submissions | System log | 0 (it only warns) |

## 5. Evaluation design

- **Shadow week first**, so real-claim precision is known before any employee sees a warning.
- **Comparison group** and a before/after baseline, because rejection rates move with the season and with
  travel volume.
- **Sample size.** About 160 claims a week across the firm (8,260 a year) means the pilot group submits
  roughly 30 a week, about 150 in 5 live weeks. At a 13% rejection rate that is about 20 expected rejections,
  too few to prove a 42% drop on its own. So the read-out combines the rejection rate with the per-flag
  evidence (did the employee fix the flagged problem before submitting?), and states its uncertainty.
- **Regression set.** The 50 synthetic claims are re-run before any prompt or policy change; a change
  that loses a planted problem or adds a false flag is not shipped.
- **No tuning on the read-out data.** Prompt changes during the pilot are logged, and claims seen while
  tuning are not counted in the final numbers.

## 6. Kill criteria (agreed before the pilot starts)

Stop the pilot, or go back to shadow mode, if **any** of these happens:

1. Flag precision on clerk-reviewed real claims is below **70% in shadow week** (do not go live) or below
   **80% at the week-3 checkpoint**.
2. The pre-check misses more of the clerks' problems than the rules alone would have.
3. Receipts or claim data are sent outside the approved hosting, or any personal-data incident happens.
4. Employees spend more than **2 extra minutes** per claim on warnings (survey or timing), or more than 1 in
   10 pilot users report a wrong warning that cost them time.
5. At week 6, the reduction in rejections is clearly below the **42%** break-even and the clerk time saved
   does not make up the difference. Then do not scale: keep the free rules-only checks, and move the
   budget to UC02 (approver assistant).

## 7. What happens after a "go"

Roll out by department, keep the weekly flag review for three months, add receipt photos (OCR or a vision
model: the prototype only read receipt text, and the receipt-reading cost is still an assumption), and run a
risk screen again before adding any new purpose (see `risk_screen.md`).
