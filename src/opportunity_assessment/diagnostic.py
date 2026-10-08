"""Process diagnostic: plain pandas, so every number can be explained and checked by hand.

Definitions (all times in days, computed on UTC timestamps):
- throughput time of a case = last event time - first event time;
- waiting time of an event  = its time - the previous event's time in the same case
  (it is "the wait before this step"; the first event of a case has no wait);
- a variant = the ordered list of activities of a case;
- a rejected case has at least one activity containing "REJECTED";
- a resubmitted case has more than one "Declaration SUBMITTED by EMPLOYEE" event.

Quantiles use pandas' default (linear interpolation), e.g. p90 of 20 values = value at position 0.9 x 19.
"""

from __future__ import annotations

import pandas as pd

SUBMIT = "Declaration SUBMITTED by EMPLOYEE"
APPROVER_ROLES = ["SUPERVISOR", "BUDGET OWNER", "PRE_APPROVER"]
DAY_SECONDS = 86_400


def prepare(log: pd.DataFrame) -> pd.DataFrame:
    """Sort events inside each case and add the wait before each event.

    The sort is stable, so events with the same timestamp keep their order from the file.
    """
    log = log.sort_values(["case_id", "timestamp"], kind="stable").reset_index(drop=True)
    log["wait_days"] = log.groupby("case_id")["timestamp"].diff().dt.total_seconds() / DAY_SECONDS
    return log


def throughput_days(log: pd.DataFrame) -> pd.Series:
    """One value per case: last event time - first event time."""
    by_case = log.groupby("case_id")["timestamp"]
    return (by_case.max() - by_case.min()).dt.total_seconds() / DAY_SECONDS


def is_rejected(log: pd.DataFrame) -> pd.Series:
    """True for cases with at least one REJECTED step."""
    return log.groupby("case_id")["activity"].agg(lambda acts: acts.str.contains("REJECTED").any())


def throughput_summary(log: pd.DataFrame) -> dict:
    days = throughput_days(log)
    rejected = is_rejected(log)
    return {
        "cases": int(days.size),
        "p50": float(days.quantile(0.5)),
        "p90": float(days.quantile(0.9)),
        "mean": float(days.mean()),
        "p50_rejected": float(days[rejected].quantile(0.5)),
        "p90_rejected": float(days[rejected].quantile(0.9)),
        "p50_not_rejected": float(days[~rejected].quantile(0.5)),
        "p90_not_rejected": float(days[~rejected].quantile(0.9)),
    }


def waiting_by(log: pd.DataFrame, column: str) -> pd.DataFrame:
    """Waiting time before each step, grouped by 'activity' or by 'role' (who does the step)."""
    waits = prepare(log).dropna(subset=["wait_days"])
    table = waits.groupby(column)["wait_days"].agg(
        events="count",
        median_days="median",
        p90_days=lambda s: s.quantile(0.9),
        total_days="sum",
    )
    table["share_of_waiting"] = table["total_days"] / table["total_days"].sum()
    return table.sort_values("total_days", ascending=False).reset_index()


def top_variants(log: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """The n most common activity sequences, with how many cases follow each one."""
    variants = prepare(log).groupby("case_id")["activity"].agg(" > ".join)
    counts = variants.value_counts()
    table = counts.head(n).rename_axis("variant").reset_index(name="cases")
    table["share"] = table["cases"] / variants.size
    return table


def rework(log: pd.DataFrame) -> dict:
    """Rejection and resubmission loops."""
    log = prepare(log)
    cases = log["case_id"].nunique()
    rejected = is_rejected(log)
    submissions = log[log["activity"] == SUBMIT].groupby("case_id").size()
    # Who rejected first (ignoring the employee's own "REJECTED by EMPLOYEE", which confirms a rejection)
    rejections = log[log["activity"].str.contains("REJECTED") & (log["role"] != "EMPLOYEE")]
    first_rejecter = rejections.groupby("case_id")["role"].first().value_counts()
    return {
        "rejected_cases": int(rejected.sum()),
        "rejected_share": float(rejected.sum() / cases),
        "resubmitted_cases": int((submissions > 1).sum()),
        "resubmitted_share": float((submissions > 1).sum() / cases),
        "first_rejecter": {role: int(count) for role, count in first_rejecter.items()},
    }


def role_share(log: pd.DataFrame) -> pd.DataFrame:
    """Share of cases that wait for each role at least once.

    The first event of a case is skipped: nobody waits for the step that opens the case.
    """
    log = prepare(log)
    cases = log["case_id"].nunique()
    waited = log.dropna(subset=["wait_days"]).groupby("role")["case_id"].nunique()
    table = waited.rename("cases").reset_index()
    table["share_of_cases"] = table["cases"] / cases
    return table.sort_values("cases", ascending=False).reset_index(drop=True)


def cases_started_in(log: pd.DataFrame, year: int) -> int:
    """Number of cases whose first event is in `year` (used as the annual volume)."""
    first = log.groupby("case_id")["timestamp"].min()
    return int((first.dt.year == year).sum())


def rejected_share_in(log: pd.DataFrame, year: int) -> float:
    first = log.groupby("case_id")["timestamp"].min()
    in_year = first[first.dt.year == year].index
    return float(is_rejected(log).loc[in_year].mean())


def approver_steps_per_case(log: pd.DataFrame) -> float:
    """Approvals by a supervisor, budget owner or pre-approver, per case (what an approver assistant touches)."""
    approvals = log["activity"].str.contains("APPROVED") & log["role"].isin(APPROVER_ROLES)
    return float(approvals.sum() / log["case_id"].nunique())


def summary(log: pd.DataFrame, volume_year: int = 2018) -> dict:
    """All headline numbers in one flat dictionary (used by the README, use-case evidence and the deck)."""
    through = throughput_summary(log)
    rw = rework(log)
    steps = waiting_by(log, "activity").set_index("activity")
    roles = waiting_by(log, "role").set_index("role")
    share = role_share(log).set_index("role")["share_of_cases"]
    variants = top_variants(log, n=1)
    first_rejecter = rw["first_rejecter"]

    def step(activity: str, column: str) -> float:
        return float(steps.loc[activity, column]) if activity in steps.index else 0.0

    def role(name: str, column: str) -> float:
        return float(roles.loc[name, column]) if name in roles.index else 0.0

    return {
        "cases": through["cases"],
        "events": int(len(log)),
        "variants": int(prepare(log).groupby("case_id")["activity"].agg(" > ".join).nunique()),
        "top_variant_share": float(variants["share"].iloc[0]),
        "throughput_p50_days": through["p50"],
        "throughput_p90_days": through["p90"],
        "throughput_mean_days": through["mean"],
        "throughput_p50_rejected_days": through["p50_rejected"],
        "throughput_p90_rejected_days": through["p90_rejected"],
        "throughput_p50_not_rejected_days": through["p50_not_rejected"],
        "throughput_p90_not_rejected_days": through["p90_not_rejected"],
        "rejected_cases": rw["rejected_cases"],
        "rejected_share": rw["rejected_share"],
        "resubmitted_cases": rw["resubmitted_cases"],
        "resubmitted_share": rw["resubmitted_share"],
        "first_rejected_by_admin_cases": first_rejecter.get("ADMINISTRATION", 0),
        "first_rejected_by_admin_share": first_rejecter.get("ADMINISTRATION", 0) / max(rw["rejected_cases"], 1),
        "supervisor_wait_p50_days": step("Declaration FINAL_APPROVED by SUPERVISOR", "median_days"),
        "supervisor_wait_p90_days": step("Declaration FINAL_APPROVED by SUPERVISOR", "p90_days"),
        "supervisor_share_of_waiting": role("SUPERVISOR", "share_of_waiting"),
        "admin_share_of_waiting": role("ADMINISTRATION", "share_of_waiting"),
        "employee_share_of_waiting": role("EMPLOYEE", "share_of_waiting"),
        "payment_stage_share_of_waiting": role("UNDEFINED", "share_of_waiting"),
        "payment_handled_wait_p50_days": step("Payment Handled", "median_days"),
        "employee_fix_wait_p50_days": step("Declaration REJECTED by EMPLOYEE", "median_days"),
        "employee_fix_wait_p90_days": step("Declaration REJECTED by EMPLOYEE", "p90_days"),
        "cases_via_budget_owner_share": float(share.get("BUDGET OWNER", 0.0)),
        "cases_via_admin_share": float(share.get("ADMINISTRATION", 0.0)),
        "cases_via_supervisor_share": float(share.get("SUPERVISOR", 0.0)),
        "saved_never_submitted_cases": int(
            (prepare(log).groupby("case_id")["activity"].agg(" > ".join) == "Declaration SAVED by EMPLOYEE").sum()
        ),
        "approver_steps_per_case": approver_steps_per_case(log),
        "volume_year": volume_year,
        "annual_cases": cases_started_in(log, volume_year),
        "annual_rejected_share": rejected_share_in(log, volume_year),
    }
