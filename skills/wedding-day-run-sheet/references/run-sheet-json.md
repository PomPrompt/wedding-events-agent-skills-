# Offline audit input format (schema 1.0)

The optional `scripts/audit_run_sheet.py` checks **only declared data**. Treat it as a secondary diagnostic, not a replacement for the agent's operational review or human approvals. Python 3.9+ with local IANA zoneinfo data required. Invoke from the installed skill folder or with the absolute script path. Stdout is JSON. Exit code: `0` valid input, no ERROR (warnings may exist); `1` audit found ERROR; `2` malformed/unusable input.

## Input object

- `timezone`: required IANA identifier, e.g. `America/New_York`; never use a guessed zone.
- `items`: 1–500 objects. Required `id` unique lowercase ASCII slug. Optional `kind` (`task`, `milestone`, `ceremony`, `reception`, `setup`, `teardown`, `travel`, `buffer`, `transition`), `status` (`confirmed` or `provisional`), `start` and `end` offset-aware ISO-8601 timestamps, `owner_role`, `resources` list, `location`, `depends_on` list. For `travel` items, set `travel_duration_source` to `verified`, `estimated`, or `unknown`.
- `buffers`: optional objects with unique-in-list `id`, `from_id`, `to_id`, `minutes` (integer 0–10080 or null). A buffer of zero is a deliberate supplied requirement, not a default. Report `BUFFER_UNKNOWN` for null.
- `transitions`: optional objects with `id`, `from_id`, `to_id`, `minutes` (integer or null), `verified` (boolean). Setting `verified=true` must reflect actual source confirmation, not a guess.
- `handoffs`: optional objects with `owner_role`, `confirmed`. Blank/unconfirmed handoffs are warnings.

Times are localized to the declared zone but **must include the correct offset** (e.g. a New York summer time uses `-04:00`). A local timestamp with an inconsistent offset or nonexistent DST time is rejected; ambiguous times must be offset-qualified. Different dates are permitted for overnight tasks. Items may omit times when not yet scheduled; these produce warnings. An instantaneous milestone may use identical start/end; other kinds need a positive interval. Resource labels express mutual exclusion, so use the same label for tasks that cannot overlap. Spaces must be specific: different rooms need different `location` strings.

Sample synthetic JSON (the ceremony setup ends exactly when guest admission begins):

```json
{
  "timezone": "America/New_York",
  "items": [
    {"id":"setup","kind":"setup","status":"confirmed","start":"2027-06-12T15:00:00-04:00","end":"2027-06-12T16:30:00-04:00","owner_role":"Venue operations","location":"garden lawn","resources":["garden_lawn"]},
    {"id":"guest_seating","kind":"task","status":"provisional","start":"2027-06-12T16:40:00-04:00","end":"2027-06-12T17:00:00-04:00","owner_role":"Guest services","location":"garden lawn","resources":["garden_lawn"],"depends_on":["setup"]},
    {"id":"ceremony","kind":"ceremony","status":"confirmed","start":"2027-06-12T17:00:00-04:00","end":"2027-06-12T17:30:00-04:00","owner_role":"Ceremony coordinator","location":"garden lawn","resources":["garden_lawn"],"depends_on":["guest_seating"]}
  ],
  "buffers": [{"id":"setup_to_guests","from_id":"setup","to_id":"guest_seating","minutes":10}],
  "transitions": [],
  "handoffs": [{"owner_role":"Ceremony coordinator","confirmed":false}]
}
```

For a transition with **unknown duration**, use `"minutes": null, "verified": false`. Never enter a fabricated transit time to clear a check.

## What it does not infer

The audit script does not discover every physically shared resource, calculate routes, verify vendor arrival or forecasts, track guest needs, automatically assign personnel, send messages, solve optimal schedules, or validate venue safety. It reports overlaps only where resources and/or same-space setup/event combinations are declared. Human review must confirm completeness of those declarations.

## Privacy and security

Use placeholder IDs and owner **roles**, not people’s names, phone numbers, contact lists or private addresses. Do not upload event JSON to external websites to run the checker. The script accepts a single local path, has a 1 MiB file limit, and makes no external requests or file writes. Host shell execution is still subject to host permissions; do not execute scripts copied from untrusted vendors.
