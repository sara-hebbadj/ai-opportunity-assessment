# LEARN: explain and change this project in an interview

## 10-minute walkthrough script (a "client presentation")

1. **The ask (1 min).** "A 600-person Dubai services firm asked where AI could help its finance back office.
   I ran a small engagement on one process, travel-expense claims: measure it, listen to staff, list and score
   the ideas, cost the best two, check the risks, and design a pilot that can be stopped. The client is
   fictional; the process data is a real public event log of 10,500 claims, used as a stand-in."
2. **The process (2 min).** Open `docs/board_deck.pdf`, slides 3–4, or the dashboard's *Process diagnostic* tab.
   "A claim takes 7.3 days at the median, 20.1 at p90. 12.4% are rejected at least once and those take 11.2 days.
   But 56% of all waiting is in the payment stage, after approval: that is a scheduling fix, not AI."
   Then `src/opportunity_assessment/diagnostic.py`: `prepare()` (wait = time since the previous event),
   `throughput_days()`, `rework()`. Show `tests/fixtures/README.md`: 20 numbers worked out by hand, 20/20 match.
3. **Voice of staff (1 min).** `data/staff/codebook.csv` (8 themes with include/exclude rules) and
   `themes.py`: one snippet per call, JSON answer, bad answers recorded as errors. "Three models agreed with the
   answer key at κ 0.93–0.97, but I wrote the answer key with the same agent, so it is an upper bound. My own
   blind coding is the real test."
4. **The portfolio (2 min).** `docs/use_case_portfolio.md` and the 2×2 chart. "18 AI ideas, each tied to a
   number. Weighted score: value 30%, feasibility and data 20% each, risk and speed 15% each. Then three models
   scored them blind: ρ 0.54–0.79. They agreed UC01 is strong, put my #2 in 8th–9th place, and liked a
   status chat I had ranked 10th because it needs no AI. I kept my scores and changed the recommendation."
5. **The business case (2 min).** Open `docs/roi_model.xlsx` or the *Business case* tab. "UC01 is AED 5k short
   of breaking even over 3 years in the base case. Break-even: prevent 42% of rejections. The tornado says clerk
   minutes saved per claim matters most, and that is an assumption, so the pilot measures it." Show `roi.py`:
   one formula string per result, used by Python and written into Excel.
6. **Prototype, risk, pilot (2 min).** *Pre-check* tab on claim FB-C001: rules find the duplicate; the model also
   reads the Arabic receipt and catches AED 121 claimed vs AED 112 on the receipt. "On 50 test claims, rules found
   24/40, each model 40/40 with no false flags. The set is too easy to rank the models, so the pilot's shadow week
   measures real precision." Close with `docs/pilot_plan.md`: kill criteria agreed up front.

## 10 interview questions with short answers

1. **Why these top 2 use cases?** They scored highest on my weighted rubric: the pre-check targets the biggest
   avoidable loop (12.4% rejected, 64% first rejected by the administration check), and the approver assistant
   targets supervisors, who are on 97% of claims. But only the first was robust: three model scorers put the
   second 8th–9th, so I recommend switching on the existing reminders (no AI) and testing the AI summary cheaply.
2. **Which assumption moves the ROI most?** For UC01, clerk minutes saved on every claim (0 to 3 minutes moves
   the 3-year net from −AED 55k to +AED 94k), then volume and run cost. The share of rejections prevented must
   reach about 42% to break even. For UC02, approver minutes saved per approval: break-even is about half a minute.
3. **What would make you stop the pilot in week 3?** Flag precision on clerk-reviewed real claims below 80%; the
   pre-check missing more of the clerks' problems than the rules alone; any personal-data incident or receipts
   leaving the approved hosting; or warnings costing staff more than 2 minutes per claim.
4. **How did you check that the LLM coded interviews the way a person would?** A fixed codebook with include and
   exclude rules, one snippet per call, and Cohen's κ against an answer key, per theme and overall. Today the
   answer key was written by the same agent that wrote the snippets, so κ 0.93–0.97 is an upper bound. My blind
   coding of the same 120 snippets (`evals/sara_coding_sheet.csv`) gives the real human–LLM κ; the target is ≥ 0.6.
5. **Why Cohen's κ and not just percent agreement?** Percent agreement ignores chance: with 8 themes, two coders
   agree sometimes by luck. κ = (observed − chance) / (1 − chance). I also report it per theme (one-vs-rest),
   because a good overall κ can hide one theme the model never gets right.
6. **How do you know the process numbers are right?** Plain pandas, no black-box library, and a 20-case log
   designed so every number can be worked out on paper: 20/20 checks match. The sum of all waits equals the sum
   of all throughput times, which is a second check.
7. **Why did a cheap model do as well as the expensive one in the prototype?** Because the test set is at the
   ceiling: all three found 40/40. The honest reading is that reading receipts finds what rules cannot (16 problems
   only visible in the receipt text), and that the cheapest model costs about US$0.02 per 100 claims, 34× less than
   the dearest. To rank models I need a harder set written before any run, and real claims from the pilot.
8. **What does the CC BY-NC licence allow you to do with the event log?** Share and adapt it with attribution,
   for non-commercial purposes only. So the repo downloads it with a script and commits only derived aggregate
   numbers, with attribution, for a non-commercial portfolio. A paid client project would need another source.
9. **What are the legal risks?** Under the EU AI Act (used here as a benchmark; it probably does not apply to a
   Dubai firm with no EU business), advisory use is minimal risk, but scoring employees for fraud would likely be
   high-risk (Annex III point 4). The UAE PDPL applies: keep a human decision (Art. 18), minimise data, and solve
   the cross-border transfer. General information, not legal advice.
10. **How would you run this with a real client in 4 weeks? Who first?** Week 1: an export of the claim system and
    interviews with the finance clerks first (they see every rejection), then budget owners and travellers.
    Week 2: diagnostic and themes. Week 3: long list, scoring workshop with the client, risk screen. Week 4:
    business case with their numbers, pilot design, board memo.

## 3 "change it live" exercises (tested on a copy of the repo on 8 October 2026)

1. **Re-weight the rubric.** In `src/opportunity_assessment/rubric.py`, set `WEIGHTS` to value 0.40, feasibility
   0.20, data readiness 0.15, risk 0.15, time to value 0.10. Run `pytest -q tests/test_rubric.py`: the two hand-worked
   examples fail because they assume the old weights. Update `test_weighted_total_hand_example` to 4.25
   (0.4×5 + 0.2×4 + 0.15×3 + 0.15×4 + 0.1×4) and, in `test_ranking_breaks_ties_by_value_then_id`, make a new tie:
   `a` = value 4, feasibility 3 and `b` = value 3, feasibility 5 (other criteria 3) both give 3.4. Run `python -m evals.run rebuild` and open
   `docs/use_case_portfolio.md`: UC01 4.25 and UC02 4.00 stay on top; UC07 (receipt OCR) moves from 7th to 5th.
   Explain why giving value more weight helps ideas with high value but slow delivery.
2. **Add a 5-year view to the business case.** In `src/opportunity_assessment/roi.py`, add
   `"five_year_net": "5 * net_annual - build_cost",` to `COMMON`. Run `python -m evals.run rebuild` and open the
   workbook: a new `five_year_net` row appears in both model sheets with a live formula. UC01 turns positive
   (about +AED 31k), UC02 reaches about AED 287k. Discuss why a 5-year horizon is risky for an AI tool (models,
   prices and the policy change).
3. **Tighten the hotel limit to AED 550 and see why policy and tests must change together.** In `precheck.py`,
   set `HOTEL_PER_NIGHT = 550`. Run `pytest -q tests/test_precheck.py`: three tests fail, because the rules now
   flag hotels at AED 575 and 600 that the answer key calls clean (7 false flags; precision 77%), and the
   "limits are inclusive" example breaks. The fix is to
   change the policy in three places: `travel_policy.md`, `HOTEL_LIMIT` in `data/claims/make_claims.py` (then
   re-run it), and `precheck.py`. Say in the README that the test set changed, because old results no longer apply.
