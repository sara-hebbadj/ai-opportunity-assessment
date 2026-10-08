# Notes for coding agents working on this repo

Project P11 of Sara Hebbadj's portfolio: a consulting-style AI opportunity assessment for the fictional
"Falcon Bay Services LLC". Sara must be able to explain every line, so keep functions short and names plain.

## Layout

- `src/opportunity_assessment/eventlog.py`: downloads the BPI 2020 log (CC BY-NC 4.0) and flattens the XES to CSV.
  The raw file goes to `data/raw/` and is **never committed**.
- `diagnostic.py`: process numbers in plain pandas. Any change must keep `tests/fixtures/README.md` true
  (20 hand-computed checks in `evals/fixture_checks.py`).
- `themes.py`, `rubric.py`, `precheck.py`: the three LLM tasks. Each builds its own prompt, parses JSON with
  `llm.parse_json`, and records bad answers as an `error` instead of raising.
- `roi.py`: every result is one formula string in `FORMULAS`/`COMMON`; Python evaluates it and the Excel
  export writes the same text. Add a result there, not in two places.
- `report.py`: `rebuild()` makes every number, chart, `docs/roi_model.xlsx` and `docs/use_case_portfolio.md`
  from the raw log + saved outputs. It makes no model calls.
- `llm.py`: the only place that calls a model. `FakeLLM` is for tests, dry runs and the offline demo.
- `evals/run.py`: the command line. `evals/results/` = real runs; `evals/dry_run/` = fake model, never results.
- `app/app.py`: Gradio dashboard; reads `evals/results/summary.json`.
- `data/claims/make_claims.py`: regenerates the 50 claims (seed 42); an oracle re-checks the planted labels.

## Rules

- Tests never touch the network (a fixture blocks sockets) and never need keys or the raw event log.
- Answer keys stay away from models: `evals/author_labels.csv` (theme labels) and `gold_problems` in the claims.
  Tests check both prompts.
- Do not edit `data/claims/claims.jsonl` by hand: change `make_claims.py` and re-run it. Changing the test set
  invalidates earlier results: say so in the README and RESULTS.md.
- Do not tune prompts on the evaluation items and then report the same items as results.
- Never copy a dry-run number into the README. Every reported number needs n, model ID, date and command.
- Keys come from `Portfolio Projects/.env` or environment variables. Never print or commit them.
- Ask Sara before creating a GitHub repo, pushing, or deploying a Space.

## Checks before you finish

```bash
pytest -q
ruff check .
python -m evals.run precheck --system llm --model cheap --limit 5 --dry-run   # pipeline still runs
python -m evals.run rebuild        # needs data/raw/ (or reuses the saved diagnostic summary)
```
