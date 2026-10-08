"""Write 50 synthetic expense claims with planted policy problems (seed 42, standard library only).

    python data/claims/make_claims.py            # writes data/claims/claims.jsonl

Gold labels come from the planting, not from a model. Before writing, an independent "oracle" re-checks
every claim from the hidden truth (receipt totals, receipt dates, items) and stops if a claim has a
problem that was not planted, or misses one that was.

Each planted problem is tagged with where a reviewer can see it:
- "fields": in the structured claim fields (dates, amounts, receipt flag, description, earlier claims);
- "receipt_text": only by reading the receipt text (for example a total that differs from the claim).
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "claims.jsonl"
rng = random.Random(42)

HOTEL_LIMIT, MEAL_LIMIT, RECEIPT_THRESHOLD, DEADLINE_DAYS, PREAPPROVAL_ABOVE = 600, 150, 50, 30, 2000
NOT_REIMBURSABLE = ("wine", "beer", "alcohol", "minibar", "spa", "souvenir", "traffic fine")

EMPLOYEES = [f"E-{n} ({role})" for n, role in zip(range(101, 116), [
    "field engineer", "sales consultant", "project manager", "analyst", "consultant", "field engineer",
    "sales consultant", "site supervisor", "consultant", "HR officer", "IT engineer", "consultant",
    "field engineer", "sales consultant", "auditor"], strict=True)]
DESTINATIONS = ["Abu Dhabi", "Al Ain", "Fujairah", "Ras Al Khaimah", "Sharjah", "Umm Al Quwain"]
HOTELS = {"Abu Dhabi": "Corniche Suites Abu Dhabi", "Al Ain": "Desert Rose Hotel Al Ain",
          "Fujairah": "Coral Bay Hotel Fujairah", "Ras Al Khaimah": "Mangrove View Hotel RAK",
          "Sharjah": "Lagoon Inn Sharjah", "Umm Al Quwain": "Creekside Lodge UAQ"}
RESTAURANTS = [("Spice Route Restaurant", "en"), ("Marina Grill", "en"), ("مطعم الفنار", "ar"),
               ("كافتيريا الواحة", "ar"), ("Harbour Kitchen", "en")]
PURPOSES = ["client site visit", "installation support", "sales meetings", "project kick-off",
            "quarterly audit visit", "training delivery"]


# ---------- receipts ----------

def receipt_text(vendor: str, lang: str, receipt_no: int, day: date, items: list[tuple[str, float]],
                 kind: str = "invoice") -> str:
    total = sum(amount for _, amount in items)
    if kind == "booking":  # looks like a receipt, but policy rule 1 says it is not one
        return (f"{vendor}\nBOOKING CONFIRMATION {receipt_no}\nArrival: {day:%d/%m/%Y}\n"
                f"Estimated amount payable at the hotel: AED {total:,.2f}\nThis is not a tax invoice.")
    if lang == "ar":
        lines = "\n".join(f"{name}  {amount:,.2f}" for name, amount in items)
        return f"{vendor}\nفاتورة ضريبية رقم {receipt_no}\nالتاريخ: {day:%Y/%m/%d}\n{lines}\nالمجموع: {total:,.2f} درهم (شامل الضريبة)"
    lines = "\n".join(f"{name}  {amount:,.2f}" for name, amount in items)
    return f"{vendor}\nTax invoice no. {receipt_no}\nDate: {day:%d/%m/%Y}\n{lines}\nTOTAL AED {total:,.2f} (VAT incl.)"


def make_line(line_id: str, day: date, category: str, vendor: str, description: str, items: list[tuple[str, float]],
              lang: str = "en", nights: int | None = None, receipt: bool = True) -> dict:
    """A clean line: the claimed amount equals the receipt total and the receipt date is the line date."""
    receipt_no = rng.randint(10000, 99999)
    total = round(float(sum(amount for _, amount in items)), 2)
    line = {"line_id": line_id, "date": day.isoformat(), "category": category, "vendor": vendor,
            "description": description, "amount_aed": total, "receipt_attached": receipt,
            "receipt_text": receipt_text(vendor, lang, receipt_no, day, items) if receipt else ""}
    if nights is not None:
        line["nights"] = nights
    # Hidden truth for the oracle (removed before writing the file).
    line["_truth"] = {"receipt_total": total, "receipt_date": day.isoformat(), "items": [n for n, _ in items],
                      "receipt_no": receipt_no, "nights": nights, "is_receipt": receipt}
    return line


def base_claim(number: int) -> dict:
    """A clean claim of 1-3 lines inside the policy limits."""
    destination = rng.choice(DESTINATIONS)
    start = date(2026, 6, 1) + timedelta(days=rng.randint(0, 90))
    nights = rng.choice([0, 1, 1, 2])
    end = start + timedelta(days=nights)
    lines = []
    if nights:
        per_night = rng.choice([380, 420, 450, 495, 540, 575])
        lines.append(make_line("L1", start, "hotel", HOTELS[destination], f"Hotel, {nights} night(s)",
                               [(f"Room ({nights} night(s))", per_night * nights)], nights=nights))
        lines[-1]["receipt_text"] = lines[-1]["receipt_text"].replace(f"Date: {start:%d/%m/%Y}", f"Date: {end:%d/%m/%Y}")
        lines[-1]["_truth"]["receipt_date"] = end.isoformat()  # hotels date the invoice at check-out
        lines[-1]["date"] = end.isoformat()
    restaurant, lang = rng.choice(RESTAURANTS)
    meal = rng.choice([42.0, 58.5, 64.0, 85.0, 96.0, 112.0])
    meal_name = "وجبة غداء" if lang == "ar" else "Lunch set"
    lines.append(make_line(f"L{len(lines) + 1}", start, "meal", restaurant, "Lunch during site visit",
                           [(meal_name, meal)], lang=lang))
    if rng.random() < 0.6:
        fare = rng.choice([28.0, 36.0, 44.0, 47.5])  # small taxi fares: no receipt needed (rule 1)
        lines.append(make_line(f"L{len(lines) + 1}", end, "taxi", "City Taxi", "Taxi to client office",
                               [("Taxi fare", fare)], receipt=rng.random() < 0.5))
    return {
        "claim_id": f"FB-C{number:03d}",
        "employee": rng.choice(EMPLOYEES),
        "trip": {"purpose": rng.choice(PURPOSES), "destination": destination,
                 "start": start.isoformat(), "end": end.isoformat()},
        "submitted_on": (end + timedelta(days=rng.randint(2, 20))).isoformat(),
        "pre_approval_ref": "",
        "justification": "",
        "lines": lines,
        "previous_claims": [],
        "gold_problems": [],
    }


def trip_dates(claim: dict) -> tuple[date, date]:
    return date.fromisoformat(claim["trip"]["start"]), date.fromisoformat(claim["trip"]["end"])


def plant(claim: dict, code: str, line_id: str, visible_in: str) -> None:
    claim["gold_problems"].append({"code": code, "line_id": line_id, "visible_in": visible_in})


def renumber(claim: dict) -> None:
    """Number lines L1, L2, ... again after removing one, and keep the gold labels pointing at them."""
    new_ids = {}
    for number, line in enumerate(claim["lines"], start=1):
        new_ids[line["line_id"]] = f"L{number}"
        line["line_id"] = f"L{number}"
    for problem in claim["gold_problems"]:
        problem["line_id"] = new_ids.get(problem["line_id"], problem["line_id"])


def remove_lines(claim: dict, keep) -> None:
    claim["lines"] = [line for line in claim["lines"] if keep(line)]
    renumber(claim)


def ensure_overnight(claim: dict, nights: int = 1) -> None:
    """Make the trip at least `nights` long (and move the submission date with it if needed)."""
    start, end = trip_dates(claim)
    if (end - start).days < nights:
        end = start + timedelta(days=nights)
        claim["trip"]["end"] = end.isoformat()
        claim["submitted_on"] = max(claim["submitted_on"], (end + timedelta(days=4)).isoformat())


def add_line(claim: dict, **kwargs) -> dict:
    line = make_line(f"L{len(claim['lines']) + 1}", **kwargs)
    claim["lines"].append(line)
    return line


# ---------- planted problems (one function per variant) ----------

def missing_receipt_fields(c):
    start, _ = trip_dates(c)
    line = add_line(c, day=start, category="fuel", vendor="Gulf Fuel Station 214", description="Fuel for pool car",
                    items=[("Petrol", 164.0)], receipt=False)
    plant(c, "missing_receipt", line["line_id"], "fields")


def missing_receipt_text(c):  # a booking confirmation is attached instead of an invoice
    remove_lines(c, lambda line: line["category"] != "hotel")
    ensure_overnight(c)
    start, end = trip_dates(c)
    line = add_line(c, day=end, category="hotel", vendor=HOTELS[c["trip"]["destination"]],
                    description="Hotel, 1 night(s)", items=[("Room (1 night(s))", 460.0)], nights=1)
    line["receipt_text"] = receipt_text(line["vendor"], "en", line["_truth"]["receipt_no"], start,
                                        [("Room", 460.0)], kind="booking")
    line["_truth"]["is_receipt"] = False
    plant(c, "missing_receipt", line["line_id"], "receipt_text")


def over_limit_hotel_fields(c):
    remove_lines(c, lambda line: line["category"] != "hotel")
    ensure_overnight(c)
    _, end = trip_dates(c)
    line = add_line(c, day=end, category="hotel", vendor=HOTELS[c["trip"]["destination"]], description="Hotel, 1 night(s)",
                    items=[("Room (1 night(s))", 720.0)], nights=1)
    plant(c, "over_limit", line["line_id"], "fields")


def over_limit_meals_fields(c):  # two meals on one day: each is fine, together they pass AED 150
    start, _ = trip_dates(c)
    remove_lines(c, lambda line: line["category"] != "meal")
    add_line(c, day=start, category="meal", vendor="Marina Grill", description="Lunch with site team",
             items=[("Lunch set", 95.0)])
    line = add_line(c, day=start, category="meal", vendor="Harbour Kitchen", description="Dinner",
                    items=[("Dinner", 115.0)])
    plant(c, "over_limit", line["line_id"], "fields")


def over_limit_text(c):  # the form says 2 nights, the invoice shows 1 night at AED 1,100
    remove_lines(c, lambda line: line["category"] != "hotel")
    start, _ = trip_dates(c)
    c["trip"]["end"] = (start + timedelta(days=2)).isoformat()
    c["submitted_on"] = (start + timedelta(days=9)).isoformat()
    line = add_line(c, day=start + timedelta(days=1), category="hotel", vendor=HOTELS[c["trip"]["destination"]],
                    description="Hotel, 2 night(s)", items=[("Room (1 night(s))", 1100.0)], nights=2)
    line["_truth"]["nights"] = 1
    plant(c, "over_limit", line["line_id"], "receipt_text")


def late_fields(c):
    _, end = trip_dates(c)
    c["submitted_on"] = (end + timedelta(days=rng.randint(37, 64))).isoformat()
    plant(c, "late_submission", "", "fields")


def outside_dates_fields(c):
    _, end = trip_dates(c)
    line = add_line(c, day=end + timedelta(days=4), category="taxi", vendor="City Taxi",
                    description="Taxi", items=[("Taxi fare", 86.0)])
    plant(c, "outside_trip_dates", line["line_id"], "fields")


def outside_dates_text(c):  # the form date is inside the trip, the receipt date is not
    start, _ = trip_dates(c)
    restaurant, lang = RESTAURANTS[1]
    line = add_line(c, day=start, category="meal", vendor=restaurant, description="Dinner",
                    items=[("Dinner", 74.0)], lang=lang)
    early = start - timedelta(days=6)
    line["receipt_text"] = line["receipt_text"].replace(f"{start:%d/%m/%Y}", f"{early:%d/%m/%Y}")
    line["_truth"]["receipt_date"] = early.isoformat()
    _drop_other_meals_on(c, start, keep=line["line_id"])
    plant(c, "outside_trip_dates", line["line_id"], "receipt_text")


def non_reimbursable_fields(c):
    _, end = trip_dates(c)
    item = rng.choice(["Hotel minibar", "Spa treatment"])
    line = add_line(c, day=end, category="other", vendor=HOTELS[c["trip"]["destination"]], description=item,
                    items=[(item, 120.0)])
    plant(c, "non_reimbursable", line["line_id"], "fields")


def non_reimbursable_text(c):  # "client dinner" on the form; the receipt lists wine
    start, _ = trip_dates(c)
    line = add_line(c, day=start, category="meal", vendor="Harbour Kitchen", description="Client dinner",
                    items=[("Grilled fish", 62.0), ("Red wine (glass)", 58.0)])
    _drop_other_meals_on(c, start, keep=line["line_id"])
    plant(c, "non_reimbursable", line["line_id"], "receipt_text")


def amount_mismatch_text(c):  # digits swapped when typing: 84.50 on the receipt, 845.00 claimed
    meal = next(line for line in c["lines"] if line["category"] == "meal")
    swapped = {42.0: 24.0, 58.5: 85.5, 64.0: 46.0, 85.0: 58.0, 96.0: 69.0, 112.0: 121.0}
    meal["amount_aed"] = swapped.get(meal["amount_aed"], meal["amount_aed"] + 40)
    plant(c, "amount_mismatch", meal["line_id"], "receipt_text")


def duplicate_fields(c):
    line = next(line for line in c["lines"] if line["receipt_attached"])
    c["previous_claims"].append({"claim_id": f"FB-P{rng.randint(100, 999)}", "date": line["date"],
                                 "vendor": line["vendor"], "amount_aed": line["amount_aed"],
                                 "receipt_no": str(line["_truth"]["receipt_no"])})
    plant(c, "duplicate", line["line_id"], "fields")


def duplicate_text(c):  # same receipt number, but the earlier claim spelled the vendor differently
    line = next(line for line in c["lines"] if line["receipt_attached"])
    short = line["vendor"].replace("Hotel", "Htl").replace("Restaurant", "Rest.").replace("Kitchen", "Kitch.")
    short = short if short != line["vendor"] else line["vendor"].upper() + " LLC"
    c["previous_claims"].append({"claim_id": f"FB-P{rng.randint(100, 999)}",
                                 "date": (date.fromisoformat(line["date"]) + timedelta(days=1)).isoformat(),
                                 "vendor": short, "amount_aed": line["amount_aed"],
                                 "receipt_no": str(line["_truth"]["receipt_no"])})
    plant(c, "duplicate", line["line_id"], "receipt_text")


def missing_preapproval_fields(c):
    start, _ = trip_dates(c)
    line = add_line(c, day=start, category="training", vendor="Emirates Skills Academy",
                    description="Safety training course fee", items=[("Course fee", 2400.0)])
    plant(c, "missing_preapproval", line["line_id"], "fields")


def _drop_other_meals_on(c, day, keep):
    """Keep the meals-per-day total under the limit when a planted meal line is added."""
    remove_lines(c, lambda line: not (line["category"] == "meal" and line["date"] == day.isoformat()
                                      and line["line_id"] != keep))


# ---------- clean "trap" claims: close to a limit but inside the policy ----------

def trap_hotel_at_limit(c):
    remove_lines(c, lambda line: line["category"] != "hotel")
    ensure_overnight(c)
    _, end = trip_dates(c)
    add_line(c, day=end, category="hotel", vendor=HOTELS[c["trip"]["destination"]], description="Hotel, 1 night(s)",
             items=[("Room (1 night(s))", 600.0)], nights=1)


def trap_meals_at_limit(c):
    start, _ = trip_dates(c)
    remove_lines(c, lambda line: line["category"] != "meal")
    add_line(c, day=start, category="meal", vendor="Spice Route Restaurant", description="Lunch",
             items=[("Lunch set", 70.0)])
    add_line(c, day=start, category="meal", vendor="مطعم الفنار", description="Dinner",
             items=[("عشاء", 80.0)], lang="ar")


def trap_deadline_day(c):
    _, end = trip_dates(c)
    c["submitted_on"] = (end + timedelta(days=30)).isoformat()


def trap_below_preapproval(c):
    start, _ = trip_dates(c)
    add_line(c, day=start, category="training", vendor="Emirates Skills Academy", description="Conference fee",
             items=[("Conference registration", 1950.0)])


def trap_with_preapproval(c):
    start, _ = trip_dates(c)
    add_line(c, day=start, category="training", vendor="Emirates Skills Academy", description="Safety training course fee",
             items=[("Course fee", 2400.0)])
    c["pre_approval_ref"] = f"PA-2026-{rng.randint(1000, 9999)}"


def trap_mocktails(c):
    start, _ = trip_dates(c)
    remove_lines(c, lambda line: line["category"] != "meal")
    add_line(c, day=start, category="meal", vendor="Harbour Kitchen", description="Client dinner",
             items=[("Grilled fish", 62.0), ("Mocktail (virgin mojito)", 28.0)])
    c["justification"] = "Dinner with the client's site manager; no alcohol was ordered."


def trap_same_vendor_other_visit(c):
    line = c["lines"][0]
    c["previous_claims"].append({"claim_id": f"FB-P{rng.randint(100, 999)}",
                                 "date": (date.fromisoformat(line["date"]) - timedelta(days=21)).isoformat(),
                                 "vendor": line["vendor"], "amount_aed": round(line["amount_aed"] + 35, 2),
                                 "receipt_no": str(rng.randint(10000, 99999))})


def trap_small_taxi_no_receipt(c):
    _, end = trip_dates(c)
    add_line(c, day=end, category="taxi", vendor="City Taxi", description="Taxi back to office",
             items=[("Taxi fare", 50.0)], receipt=False)


# 30 claims with problems: 40 planted (claim, problem) pairs, 5 per code, never the same code twice in a claim.
# 24 are visible in the structured fields, 16 only in the receipt text.
PROBLEM_PLAN = [
    [missing_receipt_fields], [missing_receipt_fields], [missing_receipt_fields, late_fields],
    [missing_receipt_text], [missing_receipt_text, missing_preapproval_fields],
    [over_limit_hotel_fields], [over_limit_hotel_fields, duplicate_fields], [over_limit_meals_fields],
    [over_limit_text], [over_limit_text, late_fields],
    [late_fields], [late_fields, non_reimbursable_fields], [late_fields],
    [outside_dates_fields], [outside_dates_fields], [outside_dates_fields, missing_preapproval_fields],
    [outside_dates_text], [outside_dates_text, amount_mismatch_text],
    [non_reimbursable_fields], [non_reimbursable_text], [non_reimbursable_text, missing_preapproval_fields],
    [non_reimbursable_text],
    [amount_mismatch_text], [amount_mismatch_text, duplicate_text], [amount_mismatch_text],
    [amount_mismatch_text, duplicate_fields], [duplicate_fields], [duplicate_text],
    [missing_preapproval_fields], [missing_preapproval_fields],
]
# 20 clean claims, 10 of them traps close to a limit
CLEAN_PLAN = [[trap_hotel_at_limit], [trap_meals_at_limit], [trap_deadline_day], [trap_below_preapproval],
              [trap_with_preapproval], [trap_mocktails], [trap_same_vendor_other_visit], [trap_small_taxi_no_receipt],
              [trap_hotel_at_limit, trap_deadline_day], [trap_mocktails]] + [[]] * 10


# ---------- oracle: recompute every problem from the hidden truth ----------

def oracle(claim: dict) -> set[str]:
    found = set()
    start, end = trip_dates(claim)
    if (date.fromisoformat(claim["submitted_on"]) - end).days > DEADLINE_DAYS:
        found.add("late_submission")
    meals_per_day: dict[str, float] = {}
    for line in claim["lines"]:
        truth = line["_truth"]
        if line["amount_aed"] > RECEIPT_THRESHOLD and not (line["receipt_attached"] and truth["is_receipt"]):
            found.add("missing_receipt")
        if line["category"] == "hotel" and truth["receipt_total"] / truth["nights"] > HOTEL_LIMIT:
            found.add("over_limit")
        if line["category"] == "meal":
            meals_per_day[truth["receipt_date"]] = meals_per_day.get(truth["receipt_date"], 0) + truth["receipt_total"]
        if not start <= date.fromisoformat(truth["receipt_date"]) <= end:
            found.add("outside_trip_dates")
        text = " ".join(truth["items"] + [line["description"]]).lower()
        if any(word in text for word in NOT_REIMBURSABLE):
            found.add("non_reimbursable")
        if line["receipt_attached"] and abs(line["amount_aed"] - truth["receipt_total"]) > 0.005:
            found.add("amount_mismatch")
        if any(p["receipt_no"] == str(truth["receipt_no"]) for p in claim["previous_claims"]):
            found.add("duplicate")
        if line["amount_aed"] > PREAPPROVAL_ABOVE and not claim["pre_approval_ref"]:
            found.add("missing_preapproval")
    if any(total > MEAL_LIMIT for total in meals_per_day.values()):
        found.add("over_limit")
    return found


def build() -> list[dict]:
    plans = [("problem", p) for p in PROBLEM_PLAN] + [("clean", p) for p in CLEAN_PLAN]
    rng.shuffle(plans)
    claims = []
    for number, (_, steps) in enumerate(plans, start=1):
        claim = base_claim(number)
        for step in steps:
            step(claim)
        planted = {p["code"] for p in claim["gold_problems"]}
        found = oracle(claim)
        if planted != found:
            raise SystemExit(f"{claim['claim_id']}: planted {sorted(planted)} but oracle found {sorted(found)}")
        for line in claim["lines"]:
            del line["_truth"]
        claims.append(claim)
    return claims


if __name__ == "__main__":
    claims = build()
    with OUT.open("w", encoding="utf-8") as handle:
        for claim in claims:
            handle.write(json.dumps(claim, ensure_ascii=False) + "\n")
    problems = [p for c in claims for p in c["gold_problems"]]
    print(f"Wrote {OUT.name}: {len(claims)} claims, {sum(1 for c in claims if c['gold_problems'])} with problems, "
          f"{len(problems)} planted problems ({sum(p['visible_in'] == 'fields' for p in problems)} in fields, "
          f"{sum(p['visible_in'] == 'receipt_text' for p in problems)} only in receipt text)")
