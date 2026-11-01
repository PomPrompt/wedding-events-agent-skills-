#!/usr/bin/env python3
"""Offline audit of user-approved run-sheet JSON. Stdlib only; no network or writes.

Exit 0: parsed, possibly with warnings. Exit 1: schedule conflicts/errors.
Exit 2: invalid input or unsupported schema. All outputs are JSON, item IDs only.
This is a diagnostic, not approval or proof that an event can run safely.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ID_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
KINDS = {"task", "milestone", "ceremony", "reception", "setup", "teardown", "travel", "buffer", "transition"}
STATUSES = {"confirmed", "provisional"}
MAX_BYTES = 1024 * 1024
MAX_ITEMS = 500

class InputError(Exception):
    pass

def unique_pairs(pairs):
    obj = {}
    for key, val in pairs:
        if key in obj:
            raise InputError("Duplicate JSON key found; reconcile the input")
        obj[key] = val
    return obj

def identifier(v, where):
    if not isinstance(v, str) or not ID_RE.fullmatch(v):
        raise InputError(f"Invalid ID at {where}; use lowercase letters, digits, _ or -")
    return v

def nonnegative_int(v, where, allow_zero=True):
    if type(v) is not int or v < (0 if allow_zero else 1) or v > 10080:
        raise InputError(f"Invalid integer minutes at {where}")
    return v

def parse_local(value, tz, where):
    if value is None:
        return None
    if not isinstance(value, str):
        raise InputError(f"Timestamp at {where} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise InputError(f"Invalid ISO-8601 timestamp at {where}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputError(f"Timezone offset required at {where}")
    local = parsed.astimezone(tz)
    if local.replace(tzinfo=None) != parsed.replace(tzinfo=None) or local.utcoffset() != parsed.utcoffset():
        raise InputError(f"Timestamp offset / local time does not match IANA timezone at {where}")
    return parsed.astimezone(timezone.utc)

def audit(data):
    if not isinstance(data, dict):
        raise InputError("JSON root must be an object")
    tz_name = data.get("timezone")
    if not isinstance(tz_name, str) or not tz_name or tz_name.upper() in {"UTC+1", "LOCAL"}:
        raise InputError("timezone must be an IANA timezone, e.g. Europe/London")
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as exc:
        raise InputError("Unrecognized IANA timezone or timezone database unavailable") from exc
    items = data.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise InputError("items must be an array with 1 to 500 entries")
    issues = []
    def issue(level, code, ids, detail):
        issues.append({"severity": level, "code": code, "item_ids": ids, "detail": detail})
    entries = {}
    for ix, item in enumerate(items):
        where = f"items[{ix}]"
        if not isinstance(item, dict):
            raise InputError(f"{where} must be an object")
        eid = identifier(item.get("id"), where + ".id")
        if eid in entries:
            raise InputError("Duplicate item ID: " + eid)
        status = item.get("status", "provisional")
        kind = item.get("kind", "task")
        if not isinstance(status, str) or status not in STATUSES or not isinstance(kind, str) or kind not in KINDS:
            raise InputError(f"Invalid kind/status at {where}")
        start = parse_local(item.get("start"), tz, where + ".start")
        end = parse_local(item.get("end"), tz, where + ".end")
        if start is not None and end is not None:
            if end < start or (end == start and kind != "milestone"):
                issue("ERROR", "INVALID_INTERVAL", [eid], "End must follow start, except a zero-length milestone")
        else:
            issue("WARNING", "UNSCHEDULED_ITEM", [eid], "Start and/or end time missing; cannot verify interval")
        owner = item.get("owner_role")
        if not isinstance(owner, str) or not owner.strip():
            issue("WARNING", "OWNER_UNASSIGNED", [eid], "Assign a responsible role before approval")
        resources = item.get("resources", [])
        if not isinstance(resources, list) or any(not isinstance(r, str) or not r.strip() or len(r) > 80 for r in resources):
            raise InputError(f"resources at {where} must be an array of short strings")
        if len(set(resources)) != len(resources):
            raise InputError(f"Duplicate resource at {where}")
        deps = item.get("depends_on", [])
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise InputError(f"depends_on at {where} must be an array of IDs")
        if len(set(deps)) != len(deps):
            raise InputError(f"Duplicate dependency at {where}")
        location = item.get("location", "")
        if not isinstance(location, str):
            raise InputError(f"location at {where} must be a string")
        if kind == "travel":
            travel_evidence = item.get("travel_duration_source", "unknown")
            if travel_evidence not in {"verified", "estimated", "unknown"}:
                raise InputError(f"Invalid travel_duration_source at {where}")
            if travel_evidence != "verified":
                issue("WARNING", "TRAVEL_NOT_VERIFIED", [eid], "Do not treat estimated or unknown travel time as assured")
        entries[eid] = {"id": eid, "kind": kind, "status": status, "start": start, "end": end,
                        "location": location.strip(), "resources": set(resources), "depends_on": deps}
    for item in entries.values():
        for predecessor_id in item["depends_on"]:
            if predecessor_id not in entries:
                issue("ERROR", "MISSING_DEPENDENCY", [item["id"], predecessor_id], "Referenced predecessor does not exist")
                continue
            pred = entries[predecessor_id]
            if pred["end"] is None or item["start"] is None:
                issue("WARNING", "DEPENDENCY_TIME_UNKNOWN", [predecessor_id, item["id"]], "Cannot verify predecessor handoff")
            elif pred["end"] > item["start"]:
                issue("ERROR", "DEPENDENCY_OVERLAP", [predecessor_id, item["id"]], "Predecessor finishes after successor starts")
    # A dependency cycle is impossible even when unscheduled.
    visited, active = set(), set()
    def visit(key):
        if key in active:
            issue("ERROR", "DEPENDENCY_CYCLE", [key], "Dependency graph contains a cycle")
            return
        if key in visited:
            return
        active.add(key)
        for dep in entries[key]["depends_on"]:
            if dep in entries:
                visit(dep)
        active.remove(key)
        visited.add(key)
    for key in entries:
        visit(key)
    values = list(entries.values())
    for i, a in enumerate(values):
        if not a["start"] or not a["end"] or a["start"] == a["end"]:
            continue
        for b in values[i + 1:]:
            if not b["start"] or not b["end"] or b["start"] == b["end"]:
                continue
            if a["start"] < b["end"] and b["start"] < a["end"]:
                shared = a["resources"] & b["resources"]
                if shared:
                    issue("ERROR", "RESOURCE_OVERLAP", [a["id"], b["id"]], "Same declared resource is assigned concurrently")
                if a["location"] and a["location"] == b["location"] and (
                    (a["kind"] in {"setup", "teardown"} and b["kind"] in {"ceremony", "reception"})
                    or (b["kind"] in {"setup", "teardown"} and a["kind"] in {"ceremony", "reception"})
                ):
                    issue("ERROR", "SPACE_NOT_READY", [a["id"], b["id"]], "Setup/teardown overlaps an event in the same precisely defined space")
    for field, code in (("buffers", "INSUFFICIENT_BUFFER"), ("transitions", "IMPOSSIBLE_TRANSITION")):
        checks = data.get(field, [])
        if not isinstance(checks, list):
            raise InputError(field + " must be a list")
        seen_check_ids = set()
        for idx, x in enumerate(checks):
            if not isinstance(x, dict):
                raise InputError(f"{field}[{idx}] must be an object")
            check_id = identifier(x.get("id"), f"{field}[{idx}].id")
            if check_id in seen_check_ids:
                raise InputError(f"Duplicate {field} ID: {check_id}")
            seen_check_ids.add(check_id)
            frm, to = x.get("from_id"), x.get("to_id")
            identifier(frm, f"{field}[{idx}].from_id")
            identifier(to, f"{field}[{idx}].to_id")
            if frm not in entries or to not in entries:
                issue("ERROR", "MISSING_REFERENCE", [str(frm), str(to)], "Check references unknown items")
                continue
            minutes = x.get("minutes")
            if minutes is not None:
                nonnegative_int(minutes, field + ".minutes")
            if field == "transitions" and (minutes is None or x.get("verified") is not True):
                issue("WARNING", "TRANSITION_UNVERIFIED", [frm, to], "Travel duration or verification missing; do not mark transition feasible")
            if field == "buffers" and minutes is None:
                issue("WARNING", "BUFFER_UNKNOWN", [frm, to], "Required buffer minutes must be confirmed")
            start = entries[frm]["end"]
            end = entries[to]["start"]
            if not start or not end:
                issue("WARNING", "GAP_NOT_COMPUTABLE", [frm, to], "Cannot compute gap without both timestamps")
            elif minutes is not None and (end - start).total_seconds() < minutes * 60:
                issue("ERROR", code, [frm, to], "Gap shorter than specified minutes")
    handoffs = data.get("handoffs", [])
    if not isinstance(handoffs, list):
        raise InputError("handoffs must be a list")
    for idx, handoff in enumerate(handoffs):
        if not isinstance(handoff, dict):
            raise InputError(f"handoffs[{idx}] must be an object")
        if not handoff.get("owner_role"):
            issue("WARNING", "HANDOFF_UNASSIGNED", [], "A handoff lacks a receiving responsible role")
        if handoff.get("confirmed") is not True:
            issue("WARNING", "HANDOFF_UNCONFIRMED", [], "A handoff needs human confirmation")
    issues.sort(key=lambda q: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[q["severity"]], q["code"], q["item_ids"]))
    counts = {s: sum(q["severity"] == s for q in issues) for s in ("ERROR", "WARNING", "INFO")}
    return {"schema_version": "1.0", "timezone": tz_name, "checked_items": len(entries),
            "diagnostic_status": "conflicts_found" if counts["ERROR"] else "needs_review" if counts["WARNING"] else "no_issues_detected",
            "issue_counts": counts, "issues": issues,
            "disclaimer": "Diagnostic checks only; human approval and vendor/location confirmation required."}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Local UTF-8 JSON file; never uploads anything")
    ns = parser.parse_args(argv)
    try:
        raw = ns.input.read_bytes()
        if len(raw) > MAX_BYTES:
            raise InputError("Input file over 1 MiB limit")
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs)
        result = audit(data)
    except (OSError, UnicodeError, json.JSONDecodeError, InputError) as exc:
        print(json.dumps({"diagnostic_status": "invalid_input", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["issue_counts"]["ERROR"] else 0

if __name__ == "__main__":
    sys.exit(main())
