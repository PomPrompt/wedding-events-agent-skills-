# JSON input and output reference — wedding-budget-scenario v1.0.0

This reference documents the **optional** local `scripts/budget_engine.py`. Using the text-only Skill does not require a JSON file or Python.

## Invocation and environment

Requires Python 3 with standard library only. No package install. From the installable skill folder:

```bash
python3 scripts/budget_engine.py path/to/my-budget.json
# or read JSON safely from stdin:
python3 scripts/budget_engine.py - < path/to/my-budget.json
```

Produces JSON on **stdout**; validation errors on **stderr** and return code 2. Does not write, fetch remote data or execute data fields as commands. Limit: 2 MB JSON, 500 items, 12 additional scenarios. Protect your input file with ordinary OS permissions; do not commit private budgets.

## Required top-level fields

| Field | Type | Meaning |
|---|---|---|
| `currency` | uppercase three-letter string | One reporting currency; no conversion |
| `budget` | decimal string or integer, >0 | Overall spending ceiling; no silent conversion |
| `items` | array (1–500) | Baseline priced and unpriced cost lines |

**For definite headroom**, also provide `contingency` as an object and complete cost information in each item; otherwise headroom is null.

Optional: `guest_count` (positive integer, narrative only); `rounding_places` (0..3 integer, uses `ROUND_HALF_UP` on line components; omission preserves exact Decimal); `scenarios` (0..12 entries).

## Item fields

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique lowercase row key `[a-z][a-z0-9_-]{0,39}` |
| `category`, `label` | Optional | Short human-readable descriptors; never code |
| `quantity` | Yes | Positive decimal, e.g. `"90"` |
| `unit_cost` | Yes for priced row | Nonnegative decimal string/integer, or `null` if genuinely unknown |
| `fee` | Needed for complete cost | Object with `type` and relevant amount/rate |
| `tax` | Needed for complete cost | Object with `type` and relevant amount/rate/basis |
| `paid` | Needed for complete cash reconciliation | Amount already paid; use `"0"` only when confirmed; null/omission is unknown |
| `cost_basis` | Yes | `quote`, `contract`, `estimate`, `actual`, `hypothetical` |

`fee` or `tax` value is `{ "type": "none" }`, `{ "type": "included" }`, `{ "type": "unknown" }`, `{ "type": "fixed", "amount": "150" }` or `{ "type": "rate", "rate": "0.08" }`. A **tax** rate additionally needs `"base": "base"` or `"base": "base_plus_fee"`. Fees use the line base as their percentage base. When included tax would be combined with an extra fee, the program refuses to assume how the two interact. For tax percentage, `0.08` means **8%**, not `8`. Rates are limited to 0..1 to catch percent input mistakes.

Amounts, including tax and fee, are *extra* unless `included` or `none`. In a tax-included row, `unit_cost` is the tax-included figure (not net of tax). Do not enter a paid deposit as an additional fee or expense row if it is already included in the contracted price. Any deposit beyond the quote must be reconciled outside the engine before submission.

`paid` is the cumulative cash paid against the **full line cost**, including earlier deposits. The engine does not track payment dates, credit-card fees, refundability, or partial refunds.

## Contingency

```json
"contingency": {"policy":"reserved_within_budget","amount":"1200"}
```

Or `policy: "additional_to_budget"`. Omitting contingency means *unspecified*, **not zero**. For a reserve within budget, spending cap = budget − reserve. For an additional fund, spending cap = budget and required overall target = budget + additional amount; this is not a statement that funds exist.

## Scenario updates

```json
"scenarios": [
  {"id":"fewer_guests", "label":"70 guests", "rationale":"Adjust variable catering and invitation quantities only.",
   "changes":{"catering":{"quantity":"70"},"invitations":{"quantity":"70"}}}
]
```

Allowed item changes: `quantity`, `unit_cost`, `fee`, `tax`, `paid`, `cost_basis`, or `omit: true` (alone, only if the original paid amount is known to be zero). Each scenario must have a nonempty `rationale`; changes to other fields or unknown row IDs are rejected. No new cost rows can be added through a scenario; add them to the baseline input or prepare a separate run. Changing package price is a *hypothesis* unless backed by a real quote. No automatic guest-count propagation.

## Interpretation of output fields

- `known_fully_priced_line_total`: sum of rows whose full cost can be determined; **not necessarily the whole wedding cost**.
- `known_paid_amounts_sum`: sum of explicitly entered payments, even if some lines have unknown final cost; not a proof of complete payments.
- `known_balances_sum`: sum of balances from rows with both full cost and paid specified; incomplete balances excluded.
- `spending_cap`: ceiling after policy for reserve within budget, or the budget itself for additional reserve; reserve omission does not mean zero.
- `budget_headroom`: **null** if priced items or contingency are incomplete. Otherwise spending cap minus total listed cost. **Does not cover omitted/unlisted expenses**.
- `headroom_after_known_priced_lines_only`: partial comparison number; never present it to users as definite available money when lines are incomplete.
- `incomplete_lines`: issues to resolve before finalizing.

## Example

See `documentation/fixtures/fictional-budget.json` in the full editorial package, which contains an explicitly fictional USD 24,000 budget, a baseline, 70-guest alternative, and simplified-decor alternative. It is not bundled with the small installable Skill to avoid implying vendor prices.

## Boundaries

No automatic market pricing, currency rates, tax jurisdiction analysis, advice about contract enforceability, checking duplicates by invoice semantics, vendor API integration or bank access. For real decisions confirm cancellation terms, included-package components, tips, taxes, amounts, dates and invoice rounding directly with relevant parties.
