# Data and licences

Nothing in this repo is real company or personal data. **Falcon Bay Services LLC is a fictional company.**
The one real dataset is public research data about a Dutch university's travel-expense process, used as a
stand-in for the fictional client's process.

## 1. The event log (real, public, NOT committed)

| | |
|---|---|
| Dataset | BPI Challenge 2020: Domestic Declarations |
| Publisher | 4TU.ResearchData, Eindhoven University of Technology (author: Boudewijn van Dongen) |
| DOI / page | [10.4121/uuid:3f422315-ed9d-4882-891f-e180b5b4feb5](https://data.4tu.nl/datasets/6a0a26d2-82d0-4018-b1cd-89afb0e8627f) |
| Licence | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): share and adapt with attribution, **non-commercial use only** |
| Size | 10,500 cases (claims), 56,437 events, 2017–2018 (2017: two departments; 2018: the whole university) |
| What it contains | One row per process step: claim ID, activity (e.g. "Declaration APPROVED by ADMINISTRATION"), timestamp, role, the claim amount. Staff are anonymised ("STAFF MEMBER"). |

**How to get it:** `python -m opportunity_assessment.eventlog` downloads `DomesticDeclarations.xes.gz`
from 4TU, checks its MD5 against the published one (`6a78c39491498363ce4788e0e8ca75ef`) and writes
`data/raw/domestic_declarations.csv`. `data/raw/` is in `.gitignore`: the log is not redistributed here.
If 4TU is down, download the file by hand from the page above and run
`python -m opportunity_assessment.eventlog --xes <file>` (it reads `.xes`, `.xes.gz` or `.zip`).

What *is* committed: aggregate numbers derived from the log (`evals/results/diagnostic_*.csv/json`),
with attribution, for a non-commercial portfolio. Re-check the licence before any commercial use.

> Build note (8 October 2026): 4TU's file storage answered "temporarily unavailable for maintenance" (HTTP 503)
> during the build, so the coding agent converted a copy of the same file from a public GitHub mirror
> (`DomesticDeclarations.xes.zip`). It has exactly the published 10,500 cases and 56,437 events, but its MD5
> could not be compared with the official `.gz`. Re-run the official download once 4TU is back and check
> that the numbers in `evals/results/diagnostic_summary.json` do not change.

## 2. Staff interviews and survey (synthetic)

Written by the coding agent for this project, as if from a discovery phase at the fictional client. No
real people. Roles only, no names.

| File | Rows | Columns |
|---|---|---|
| `staff/codebook.csv` | 8 themes | theme_id (T1–T8), name, definition, include, exclude |
| `staff/interviews.csv` | 80 snippets from 12 interviews | snippet_id (S001–S080), interview_id (I01–I12), role, question, text |
| `staff/survey.csv` | 40 respondents | respondent_id, role_group, five 1–5 ratings, snippet_id (S081–S120), free_text |

The 12 interviews: 3 finance (2 clerks, 1 team lead), 2 budget owners, 2 supervisors, 3 travellers,
1 IT analyst, 1 internal auditor. The survey ratings were drawn with a seeded random generator (seed 7)
around means chosen by the author to echo the interviews, so they are **illustrative, not evidence**.

The author's intended theme for each snippet (and whether it is "clear" or "mixed") is in
`evals/author_labels.csv`, kept outside `data/` because it is an answer key that the model never sees.

## 3. Expense claims for the pre-check prototype (synthetic)

| File | What it is |
|---|---|
| `claims/travel_policy.md` | The fictional client's domestic travel-expense policy (9 rules, AED) |
| `claims/make_claims.py` | Generator (seed 42, standard library only). Plants known problems and re-checks every claim with an independent "oracle" before writing |
| `claims/claims.jsonl` | 50 claims: 30 with problems (40 planted (claim, problem) pairs, 5 per problem code), 20 clean (10 of them "traps" close to a limit) |

Each claim has trip details, 1–4 expense lines with receipt text (English or Arabic), the employee's earlier
claims (for the duplicate rule) and `gold_problems` (the answer key). Of the 40 planted problems, 24 can be
seen in the structured fields and 16 only by reading the receipt text. Vendors, employees ("E-104
(field engineer)") and places are invented or generic.

## 4. Use-case portfolio inputs (written for this project)

| File | What it is |
|---|---|
| `portfolio/use_cases.csv` | 18 AI use cases + 2 non-AI changes, each with an evidence sentence whose `{placeholders}` are filled with measured numbers |
| `portfolio/scores_analyst_draft.csv` | Draft 1–5 scores with a reason per use case, **written by the coding agent for Sara to review** |
| `portfolio/roi_assumptions.csv` | Every ROI input with a low/high value and its source (measured or labelled assumption) |
