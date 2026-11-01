# Input contract — seat_solver.py v1.0.0

This JSON input is **private event data**. Use synthetic IDs wherever possible. The script never requires names, contact details, dietary details or medical information.

```json
{
  "guests": [
    {"id":"G1","rsvp":"confirmed","allowed_tables":["T1","T2"]},
    {"id":"G2","rsvp":"confirmed"},
    {"id":"G3","rsvp":"pending"}
  ],
  "tables": [{"id":"T1","capacity":2},{"id":"T2","capacity":2}],
  "keep_together": [["G1","G2"]],
  "keep_apart": [],
  "locked_tables": {},
  "soft_preferences": [{"type":"apart","a":"G1","b":"G2"}]
}
```

- Keys outside the documented schema are rejected: `guests`, `tables`, `keep_together`, `keep_apart`, `locked_tables`, `soft_preferences`.
- Every guest requires `id` and `rsvp`. Only `confirmed`, `pending`, `declined` accepted. `allowed_tables` is optional; if present, it must contain one or more valid table IDs and applies **only if the guest is confirmed**. Optional absent means any table. An explicit empty eligibility list is invalid.
- Every table requires `id` and integer `capacity` (1–100, not booleans or decimals). Table IDs and guest IDs are unique 1–32-character ASCII `[A-Za-z0-9][A-Za-z0-9_-]*`; never encode a person's name or private data in an ID.
- `keep_together` is a list of arrays, each with at least two **distinct confirmed IDs**. These groups are transitive (overlap merges them). `keep_apart` is a list of two-distinct-confirmed-ID arrays.
- `locked_tables` maps confirmed guest IDs to valid table IDs. `soft_preferences` is a list of `{type:"together"|"apart",a:"G1",b:"G2"}` (confirmed distinct IDs).
- All optional top-level keys default to empty collections if absent. No invented RSVP states or capacity defaults. Limit: at most 250 guest records, at most 50 tables; input file <= 512 KiB; max search nodes 1–1,000,000.
- Result `status`: `FEASIBLE`, `INFEASIBLE` (proven arithmetic or exhaustive finite search), `UNVERIFIED` (node budget), `INVALID_INPUT` (schema or reference error). `FEASIBLE` result is a *valid table assignment*, not the optimum for preferences or a legally approved layout.
- The program reads only the supplied local UTF-8 JSON file and prints JSON to standard output; it does not make network requests or write event files. Use `--max-nodes 50000` unless a reviewer explicitly permits a higher limit.
- For script exit codes: 0 = FEASIBLE, 2 = INFEASIBLE/INVALID_INPUT, 3 = UNVERIFIED. Treat every output as local draft data, never automatically publish/share.
