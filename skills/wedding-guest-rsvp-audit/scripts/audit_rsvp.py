#!/usr/bin/env python3
"""Read-only, local, event-scoped CSV RSVP audit. Standard library only.

Every CSV row is an invitation UNIT (person or household), not necessarily one person.
Output is JSON aggregate counts and row numbers only; no guest labels or IDs.
The tool never changes the source or contacts anyone. This is not an identity resolver.
"""
import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
MAX_CELL_BYTES = 20000
REQUIRED = {"record_id", "invitation_status", "rsvp_status", "invited_seats", "confirmed_attendees"}
ALLOWED = REQUIRED | {"event_id", "household_id", "guest_label", "plus_one_slots", "plus_one_confirmed", "meal_count"}
INV_STATES = {"invited", "draft", "cancelled", "not_invited", "unknown"}
RSVP_STATES = {"accepted", "declined", "pending", "unknown"}


def normalized_label(s):
    return " ".join(unicodedata.normalize("NFKC", s).casefold().split())


def integer(s, *, required=False):
    if s == "":
        if required:
            raise ValueError("missing integer")
        return None
    if not re.fullmatch(r"[0-9]+", s):
        raise ValueError("not a nonnegative integer")
    n = int(s)
    if n > 10000:
        raise ValueError("integer exceeds documented per-row limit")
    return n


def issue(issues, code, severity, rows, message):
    issues.append({"code": code, "severity": severity, "rows": sorted(set(rows)), "message": message})


def blocked(message):
    return {"status": "BLOCKED", "counts": None,
            "issues": [{"code": "INPUT_BLOCKED", "severity": "ERROR", "rows": [], "message": message}],
            "notes": ["No event-level counts were calculated."]}


def audit(path, meals_required=False):
    try:
        if not path.is_file():
            return blocked("Input is not an existing regular file.")
        if path.stat().st_size > MAX_BYTES:
            return blocked("Input exceeds the 5 MiB size limit.")
        csv.field_size_limit(MAX_CELL_BYTES)
        with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as f:
            reader = csv.DictReader(f, restkey="__EXTRA_FIELDS__", restval="")
            if not reader.fieldnames:
                return blocked("CSV header is missing.")
            header = reader.fieldnames
            if any(h is None or h == "" for h in header) or len(set(header)) != len(header):
                return blocked("CSV header contains blank or repeated field names.")
            if missing := sorted(REQUIRED - set(header)):
                return blocked("Required CSV columns missing: " + ", ".join(missing))
            # Ignore unknown columns to avoid processing unnecessary personal fields.
            units = []
            for number, row in enumerate(reader, start=2):
                if number > MAX_ROWS + 1:
                    return blocked("Input exceeds the 10,000-row limit.")
                if "__EXTRA_FIELDS__" in row:
                    return blocked("A CSV row has more fields than the header.")
                if any(len((v or "").encode("utf-8")) > MAX_CELL_BYTES for v in row.values()):
                    return blocked("A CSV field exceeds the size limit.")
                units.append((number, {k: (row.get(k) or "").strip() for k in ALLOWED}))
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        # Error class only: don't reveal paths, guest content, or OS error strings.
        return blocked("Unable to safely read a valid UTF-8 CSV (" + type(exc).__name__ + ").")
    if not units:
        return blocked("CSV has no data rows.")
    event_values = {r["event_id"] for _, r in units if r.get("event_id")}
    if len(event_values) > 1 or (event_values and any(not r.get("event_id") for _, r in units)):
        return blocked("Event IDs are mixed or missing on some rows; filter to one event before auditing.")

    issues, bad_rows = [], set()
    seen_ids = defaultdict(list)
    seen_labels = defaultdict(list)
    for line, r in units:
        if not r["record_id"]:
            issue(issues, "MISSING_RECORD_ID", "ERROR", [line], "Missing stable invitation-unit ID; row excluded.")
            bad_rows.add(line)
        else:
            seen_ids[r["record_id"]].append(line)
        if r.get("guest_label"):
            seen_labels[normalized_label(r["guest_label"])].append((line, r["record_id"]))
    for _id, lines in seen_ids.items():
        if len(lines) > 1:
            issue(issues, "DUPLICATE_RECORD_ID", "ERROR", lines,
                  "Identical record ID on multiple rows; all occurrences excluded until resolved.")
            bad_rows.update(lines)
    for _label, occurrences in seen_labels.items():
        if len(set(id_ for _, id_ in occurrences if id_)) > 1:
            issue(issues, "POSSIBLE_DUPLICATE_LABEL", "WARNING", [line for line, _ in occurrences],
                  "Matching normalized guest labels with distinct IDs; verify manually, do not merge automatically.")

    parsed = []
    for line, r in units:
        inv = r["invitation_status"].lower()
        rsp = r["rsvp_status"].lower() or "unknown"
        if inv not in INV_STATES or rsp not in RSVP_STATES:
            issue(issues, "INVALID_STATE", "ERROR", [line], "Unknown invitation or RSVP status; row excluded.")
            bad_rows.add(line)
            continue
        try:
            seats = integer(r["invited_seats"], required=(inv == "invited"))
            attendees = integer(r["confirmed_attendees"], required=(rsp == "accepted"))
            slots = integer(r["plus_one_slots"])
            plus = integer(r["plus_one_confirmed"])
            meals = integer(r["meal_count"])
        except ValueError:
            issue(issues, "INVALID_NUMBER", "ERROR", [line], "Missing or invalid nonnegative count; row excluded.")
            bad_rows.add(line)
            continue
        attendees = 0 if attendees is None else attendees
        if inv == "invited" and (seats is None or seats == 0):
            issue(issues, "NO_INVITED_SEATS", "ERROR", [line], "Active invitation must have at least one invited seat.")
            bad_rows.add(line)
        if inv != "invited" and rsp == "accepted":
            issue(issues, "ACCEPTED_NOT_INVITED", "ERROR", [line],
                  "Accepted RSVP is not attached to an active invitation; row excluded from event totals.")
            bad_rows.add(line)
        if (rsp == "accepted" and attendees < 1) or (rsp != "accepted" and attendees > 0):
            issue(issues, "RSVP_COUNT_CONFLICT", "ERROR", [line],
                  "Confirmed count contradicts RSVP status; row excluded.")
            bad_rows.add(line)
        if seats is not None and attendees > seats:
            issue(issues, "OVER_INVITATION_CAPACITY", "ERROR", [line],
                  "Confirmed attendees exceed invited seats; row excluded.")
            bad_rows.add(line)
        if slots is not None and seats is not None and slots > seats:
            issue(issues, "INVALID_PLUS_ONE_SLOTS", "ERROR", [line],
                  "Plus-one slots exceed invited seats; row excluded.")
            bad_rows.add(line)
        if plus is not None and (plus > attendees or (slots is not None and plus > slots)):
            issue(issues, "PLUS_ONE_CONFLICT", "ERROR", [line],
                  "Confirmed plus-ones exceed confirmed attendees or allowed slots; row excluded.")
            bad_rows.add(line)
        if plus is not None and slots is None:
            issue(issues, "UNKNOWN_PLUS_ONE_POLICY", "WARNING", [line],
                  "Plus-one confirmations supplied without an explicit allowance; verify policy.")
        if meals is not None and meals > attendees:
            issue(issues, "MEALS_EXCEED_CONFIRMED", "ERROR", [line],
                  "Meal count exceeds confirmed attendees; row excluded.")
            bad_rows.add(line)
        if inv == "invited" and rsp == "accepted" and meals_required and meals != attendees:
            issue(issues, "MEALS_INCOMPLETE", "WARNING", [line],
                  "Meals-required policy: meal count missing or different from confirmed attendees.")
        parsed.append((line, inv, rsp, seats, attendees, slots, plus, meals))

    counts = {"source_rows": len(units), "usable_invitation_units": 0,
              "excluded_rows": len(bad_rows), "excluded_nonactive_units": 0,
              "known_invited_seats": 0, "confirmed_attendees": 0,
              "accepted_units": 0, "declined_units": 0, "pending_units": 0, "unknown_rsvp_units": 0,
              "known_confirmed_plus_ones": 0, "plus_one_confirmation_unknown_units": 0,
              "accepted_units_with_meal_count_unknown": 0, "known_meal_count": 0,
              "unconfirmed_seats_within_accepted_units": 0}
    for line, inv, rsp, seats, attendees, slots, plus, meals in parsed:
        if line in bad_rows:
            continue
        if inv != "invited":
            counts["excluded_nonactive_units"] += 1
            continue
        counts["usable_invitation_units"] += 1
        counts["known_invited_seats"] += seats
        counts[{"accepted": "accepted_units", "declined": "declined_units",
                "pending": "pending_units", "unknown": "unknown_rsvp_units"}[rsp]] += 1
        if rsp == "accepted":
            counts["confirmed_attendees"] += attendees
            counts["unconfirmed_seats_within_accepted_units"] += seats - attendees
            if plus is not None:
                counts["known_confirmed_plus_ones"] += plus
            elif slots is None or slots > 0:
                counts["plus_one_confirmation_unknown_units"] += 1
            if meals is None:
                counts["accepted_units_with_meal_count_unknown"] += 1
            else:
                counts["known_meal_count"] += meals
    counts["excluded_rows"] = len(bad_rows)
    counts["unclassified_source_rows"] = counts["source_rows"] - counts["usable_invitation_units"] - counts["excluded_nonactive_units"] - counts["excluded_rows"]
    # Rows excluded for bad identity and other categories are not silently counted.
    issues.sort(key=lambda x: (x["rows"][0] if x["rows"] else -1, x["code"]))
    return {"status": "REVIEW_REQUIRED" if issues or bad_rows or counts["plus_one_confirmation_unknown_units"] else "COMPLETE",
            "counts": counts, "issues": issues,
            "notes": ["One source row represents one invitation unit, potentially multiple people.",
                      "All counts exclude rows with validation errors or duplicate IDs; when excluded_rows > 0, totals are partial.",
                      "Invited seats already include permitted plus-one slots; do not add slots again.",
                      "Pending/unknown units do not imply any known number of attendees.",
                      "Known meal counts are only recorded values, not a prediction of catering orders.",
                      "Matching labels are candidate duplicates only; no automatic merges.",
                      "No personal labels, IDs, emails, phone numbers, or meal details are emitted."]}


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline invitation-unit RSVP audit; emits redacted JSON to stdout.")
    p.add_argument("--input", required=True, help="Authorized UTF-8 CSV file (one event).")
    p.add_argument("--meals-required", action="store_true", help="Require one meal count per confirmed attendee.")
    args = p.parse_args(argv)
    result = audit(Path(args.input), args.meals_required)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
