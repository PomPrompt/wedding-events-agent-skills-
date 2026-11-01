#!/usr/bin/env python3
"""Private, deterministic, bounded table-assignment solver; Python 3 stdlib only.
No network, no event file writes, no external imports. See references/INPUT_SCHEMA.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}\Z")
MAX_GUESTS, MAX_TABLES = 250, 50


class DataError(Exception):
    pass


def ensure(test, detail):
    if not test:
        raise DataError(detail)


def check_keys(obj, allowed, context):
    ensure(isinstance(obj, dict), f"{context} must be an object")
    ensure(not set(obj).difference(allowed), f"{context} contains unsupported field(s)")


def require_id(s, context):
    ensure(isinstance(s, str) and ID.fullmatch(s), f"{context} requires a non-sensitive ASCII ID (1–32 characters)")
    return s


def validate(data):
    check_keys(data, {"guests", "tables", "keep_together", "keep_apart", "locked_tables", "soft_preferences"}, "Root")
    guests = data.get("guests")
    tables = data.get("tables")
    ensure(isinstance(guests, list) and 1 <= len(guests) <= MAX_GUESTS, "guests must be a nonempty list of at most 250 records")
    ensure(isinstance(tables, list) and 1 <= len(tables) <= MAX_TABLES, "tables must be a nonempty list of at most 50 records")
    lookup = {}
    for item in guests:
        check_keys(item, {"id", "rsvp", "allowed_tables"}, "Guest")
        g = require_id(item.get("id"), "Guest")
        ensure(g not in lookup, "Duplicate guest ID: " + g)
        status = item.get("rsvp")
        ensure(status in ("confirmed", "pending", "declined") and isinstance(status, str), "Unknown RSVP status for " + g)
        lookup[g] = item
    tablecaps = {}
    for item in tables:
        check_keys(item, {"id", "capacity"}, "Table")
        t = require_id(item.get("id"), "Table")
        cap = item.get("capacity")
        ensure(type(cap) is int and 1 <= cap <= 100, "Table capacity must be an integer from 1 to 100 for " + t)
        ensure(t not in tablecaps, "Duplicate table ID: " + t)
        tablecaps[t] = cap
    active = {g for g, r in lookup.items() if r["rsvp"] == "confirmed"}
    ensure(active, "At least one guest must be confirmed; no assignment was generated")
    allowed = {}
    for g in sorted(active):
        v = lookup[g].get("allowed_tables", sorted(tablecaps))
        ensure(isinstance(v, list) and len(v) > 0 and all(isinstance(x, str) for x in v), "allowed_tables must be a nonempty array of table IDs for " + g)
        ensure(len(v) == len(set(v)) and set(v) <= set(tablecaps), "allowed_tables contains a duplicate or unknown table ID for " + g)
        allowed[g] = set(v)

    def check_pairs(key, minimum, exact):
        v = data.get(key, [])
        ensure(isinstance(v, list), key + " must be an array")
        result = []
        for x in v:
            ensure(isinstance(x, list) and len(x) >= minimum and (exact is None or len(x) == exact), key + " has an invalid group")
            ensure(all(isinstance(g, str) and g in active for g in x), key + " refers to missing or non-confirmed guests")
            ensure(len(set(x)) == len(x), key + " has a repeated ID in a group")
            result.append(x)
        return result

    together = check_pairs("keep_together", 2, None)
    apart = check_pairs("keep_apart", 2, 2)
    locked = data.get("locked_tables", {})
    ensure(isinstance(locked, dict), "locked_tables must be an object")
    for g, t in locked.items():
        ensure(g in active and isinstance(t, str) and t in tablecaps, "locked_tables refers to missing, nonconfirmed or invalid ID")
    prefs = data.get("soft_preferences", [])
    ensure(isinstance(prefs, list), "soft_preferences must be an array")
    for p in prefs:
        check_keys(p, {"type", "a", "b"}, "Soft preference")
        ensure(p.get("type") in ("together", "apart") and isinstance(p.get("a"), str) and isinstance(p.get("b"), str) and p["a"] in active and p["b"] in active and p["a"] != p["b"], "Invalid soft preference: distinct confirmed guests and together/apart required")
    return lookup, active, tablecaps, allowed, together, apart, locked, prefs


def solve(data, max_nodes=50000):
    ensure(type(max_nodes) is int and 1 <= max_nodes <= 1000000, "max_nodes must be an integer from 1 to 1000000")
    lookup, active, caps, allowed, together, apart, locked, prefs = validate(data)
    summary = {
        "confirmed": len(active),
        "pending": sum(g["rsvp"] == "pending" for g in lookup.values()),
        "declined": sum(g["rsvp"] == "declined" for g in lookup.values()),
        "total_table_capacity": sum(caps.values()),
        "table_count": len(caps),
    }
    base = {"status": None, "summary": summary, "assignments": None, "issues": [],
            "soft_preferences_review": [], "search": {"nodes": 0, "max_nodes": max_nodes, "exhaustive": True}}
    if len(active) > sum(caps.values()):
        base.update(status="INFEASIBLE", issues=["Confirmed guests exceed aggregate table capacity: " + str(len(active)) + " > " + str(sum(caps.values()))])
        return base
    parent = {g: g for g in active}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for group in together:
        for g in group[1:]:
            parent[find(g)] = find(group[0])
    groups = {}
    for g in sorted(active):
        groups.setdefault(find(g), []).append(g)
    components = sorted((tuple(sorted(v)) for v in groups.values()), key=lambda x: x[0])
    cmap = {g: i for i, comp in enumerate(components) for g in comp}
    conflicts = []
    allowed_comp = {}
    for i, comp in enumerate(components):
        elig = set(caps)
        for g in comp:
            elig &= allowed[g]
            if g in locked:
                elig &= {locked[g]}
        possible = sorted(t for t in elig if caps[t] >= len(comp))
        if not possible:
            conflicts.append("Together-component " + ",".join(comp) + " has no eligible table with sufficient capacity / compatible locks")
        allowed_comp[i] = possible
    adjacent = {i: set() for i in range(len(components))}
    for a, b in apart:
        ca, cb = cmap[a], cmap[b]
        if ca == cb:
            conflicts.append("Hard-rule contradiction: keep-apart " + a + "/" + b + " lies inside a transitive keep-together component")
        else:
            adjacent[ca].add(cb)
            adjacent[cb].add(ca)
    if conflicts:
        base.update(status="INFEASIBLE", issues=conflicts)
        return base

    order = sorted(range(len(components)), key=lambda i: (-len(adjacent[i]), len(allowed_comp[i]), -len(components[i]), components[i]))
    remaining = dict(caps)
    assigned = {}
    nodes = 0
    cutoff = False

    def search(depth):
        nonlocal nodes, cutoff
        if depth == len(order):
            return True
        i = order[depth]
        for t in allowed_comp[i]:
            if remaining[t] < len(components[i]) or any(assigned.get(n) == t for n in adjacent[i]):
                continue
            if nodes >= max_nodes:
                cutoff = True
                return False
            nodes += 1
            assigned[i] = t
            remaining[t] -= len(components[i])
            if search(depth + 1):
                return True
            remaining[t] += len(components[i])
            del assigned[i]
            if cutoff:
                return False
        return False

    found = search(0)
    base["search"] = {"nodes": nodes, "max_nodes": max_nodes, "exhaustive": (not cutoff and not found)}
    if not found:
        base["status"] = "UNVERIFIED" if cutoff else "INFEASIBLE"
        base["issues"] = ["Search budget exhausted; no infeasibility conclusion is justified"] if cutoff else ["Exhaustive search found no table assignment satisfying all hard constraints"]
        return base
    assignments = {t: [] for t in sorted(caps)}
    for i, comp in enumerate(components):
        assignments[assigned[i]].extend(comp)
    assignments = {t: {"guests": sorted(v), "occupied": len(v), "capacity": caps[t]}
                   for t, v in assignments.items()}
    gast = {g: t for t, v in assignments.items() for g in v["guests"]}
    # Defence-in-depth: assert invariants before outputting a result.
    assert set(gast) == active and len(gast) == len(active)
    assert all(x["occupied"] <= x["capacity"] for x in assignments.values())
    assert all(len({gast[g] for g in group}) == 1 for group in together)
    assert all(gast[a] != gast[b] for a, b in apart)
    assert all(gast[g] == t for g, t in locked.items())
    assert all(gast[g] in allowed[g] for g in active)
    soft = []
    for p in prefs:
        met = (gast[p["a"]] == gast[p["b"]]) == (p["type"] == "together")
        soft.append({"type": p["type"], "a": p["a"], "b": p["b"], "met": met})
    base.update(status="FEASIBLE", assignments=assignments, soft_preferences_review=soft,
                hard_constraint_check="PASS", preferences_optimized=False,
                issues=["Physical floor plan, accessibility and venue approvals are not checked"])
    return base


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline bounded wedding seating solver; JSON input -> JSON output")
    parser.add_argument("input", type=Path, help="Private local JSON input path")
    parser.add_argument("--max-nodes", type=int, default=50000)
    args = parser.parse_args(argv)
    try:
        ensure(args.input.is_file(), "Input file does not exist")
        ensure(args.input.stat().st_size <= 524288, "Input file exceeds 512 KiB limit")
        raw = args.input.read_text(encoding="utf-8")
        data = json.loads(raw)
        result = solve(data, args.max_nodes)
    except (DataError, json.JSONDecodeError, UnicodeError, OSError) as exc:
        result = {"status": "INVALID_INPUT", "summary": None, "assignments": None,
                  "issues": [str(exc) if isinstance(exc, DataError) else "Input file is unreadable or is not valid UTF-8 JSON"],
                  "search": {"nodes": 0, "exhaustive": False}}
    print(json.dumps(result, indent=2, ensure_ascii=True, sort_keys=True))
    return 0 if result["status"] == "FEASIBLE" else (3 if result["status"] == "UNVERIFIED" else 2)


if __name__ == "__main__":
    sys.exit(main())
