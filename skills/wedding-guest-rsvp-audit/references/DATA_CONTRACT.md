# CSV data contract (v1.0.0)

**One row = one invitation unit** (single person or household) for **one event**. A unit may represent several invitees, so status counts are **unit counts** while seat and attendee counts are **people counts**. A household with two distinct invitations can legitimately have two records. Do not silently convert per-person exports to this format.

## Input fields

| Column | Required | Allowed values and meaning |
|---|---|---|
| `record_id` | Yes | Unique stable pseudonymous **invitation-unit** ID. Never a phone/email. |
| `invitation_status` | Yes | `invited`, `draft`, `cancelled`, `not_invited`, `unknown`. Only `invited` enters invitation totals. |
| `rsvp_status` | Yes | `accepted`, `declined`, `pending`, `unknown` (blank treated as `unknown`). The status applies to the **unit**. Mixed household replies require splitting into agreed units or explicit prior reconciliation. |
| `invited_seats` | Yes for active invitations | Integer 1–10000. Includes all allowed plus-one slots, **not added again**. |
| `confirmed_attendees` | Yes for accepted units | Integer at least 1 on `accepted`; otherwise blank or 0. This is a *total number of people*, including confirmed plus-ones. |
| `event_id` | Optional | When present, must be populated consistently and match on every row. Mixed event IDs block counts. |
| `household_id` | Optional | Pseudonymous household reference. Same household ID **does not prove duplicate**. |
| `guest_label` | Optional | User-supplied label; can contain names and is sensitive. The helper only uses normalized equality to flag possible duplicates; never prints it. Prefer omitting for minimal data. |
| `plus_one_slots` | Optional | Allowed plus-one places **inside** `invited_seats`; blank means unknown entitlement. |
| `plus_one_confirmed` | Optional | Confirmed plus-ones **inside** `confirmed_attendees`. Blank means unknown, 0 means known zero. Must be at most `plus_one_slots` when supplied. |
| `meal_count` | Optional | Recorded number of meal selections for the unit. Blank means unknown. Must not exceed `confirmed_attendees`. With `--meals-required`, missing/different count raises a warning for accepted units. |

- Integer fields allow digits only (`0`, `1`, ...), no negative, fraction, plus sign or thousands separator. Per-row integer maximum: 10000. CSV UTF-8 with optional BOM. Field/header casing is exact. All unknown extra columns are ignored, not copied. File limits: **5 MiB, 10,000 data rows**. Standard CSV quoting applies.
- **Duplicate `record_id`:** exclude all duplicates, not first-wins; show source rows.
- **Likely duplicate:** matching normalized `guest_label` across different IDs is a warning only; **do not merge** or exclude based solely on label.
- **Invited seats:** a capacity allocation, not a definitive count of named people. There is no inferred "pending people" calculation.
- **Status:** `COMPLETE` means the mechanics found no flagged issues; it does **not** mean every invitee has replied. `REVIEW_REQUIRED` means one or more warnings/errors or unresolved plus-one confirmations. `BLOCKED` means no totals can be computed.
- **Excluded source rows:** errors or exact duplicated IDs. `excluded_nonactive_units` are valid draft/cancelled/not-invited/unknown invitations not included in active totals.
- **Privacy:** JSON output contains only aggregate counts, issue codes and input data-record positions (header = position 1, not necessarily physical file lines if cells contain embedded newlines). These positions can still be reidentified by the person holding the input file, so protect reports too. No guest labels, IDs, contact details, dietary notes or CSV content are printed.
- **Limits:** No phone/email matching, approximate name matching, multi-event reconciliation, automatic guest-to-seat allocation, RSVP sending, live platform sync, legal-basis determination, secure erasure certification or verification of spreadsheet CSV export safety.

## Fictional minimal input

```csv
record_id,invitation_status,rsvp_status,invited_seats,confirmed_attendees,plus_one_slots,plus_one_confirmed,meal_count
UNIT-001,invited,accepted,2,2,1,1,2
UNIT-002,invited,pending,3,0,1,,
UNIT-003,invited,declined,1,0,0,0,0
```

Expected (illustrative, not a live test): 6 invited seats, 2 confirmed people, 1 accepted unit, 1 pending unit, 1 declined unit, 1 known confirmed plus-one. Unit 002's unknown plus-one confirmation is not counted as zero.
