#!/usr/bin/env python3
"""Deterministic, local-only, decimal wedding budget scenarios (stdlib only).

Input: JSON file path or '-' for stdin. Output: JSON on stdout. No network, writes,
or external integrations. Untrusted JSON is data, not commands.
"""
import argparse
import copy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext
import json
from pathlib import Path
import re
import sys

getcontext().prec = 64  # bounded inputs can multiply long decimal values

MAX_ITEMS = 500
MAX_SCENARIOS = 12
MAX_RAW_BYTES = 2_000_000
MAX_DIGITS = 18
MAX_RATE = Decimal('1')  # Enter percentage rates as fractions 0..1 (e.g. 0.08).

class BudgetError(ValueError):
    pass


def dec(value, field, *, allow_zero=True):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise BudgetError(f'{field}: use a decimal string or integer (no float or boolean)')
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BudgetError(f'{field}: invalid decimal') from None
    if not v.is_finite() or v < 0 or (v == 0 and not allow_zero):
        raise BudgetError(f'{field}: expected finite nonnegative value' + (' > 0' if not allow_zero else ''))
    if len(v.as_tuple().digits) > MAX_DIGITS or abs(v.as_tuple().exponent) > 8:
        raise BudgetError(f'{field}: excessive precision or magnitude')
    return v


def shown(value):
    if value is None:
        return None
    s = format(value, 'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s


def choose_precision(data):
    places = data.get('rounding_places')
    if places is None:
        return None
    if isinstance(places, bool) or not isinstance(places, int) or places not in (0, 1, 2, 3):
        raise BudgetError('rounding_places must be 0..3 or omitted')
    return Decimal(1).scaleb(-places)


def round_money(v, quantum):
    return v.quantize(quantum, rounding=ROUND_HALF_UP) if quantum is not None else v


def cost_component(info, field, base, quantum, *, kind='fee', fee_added=Decimal('0')):
    if not isinstance(info, dict):
        return None, f'{field} not specified'
    kind_value = info.get('type')
    if kind_value == 'unknown':
        return None, f'{field} unknown'
    if kind_value in ('none', 'included'):
        return Decimal('0'), None
    if kind_value == 'fixed':
        return round_money(dec(info.get('amount'), f'{field}.amount'), quantum), None
    if kind_value == 'rate':
        rate = dec(info.get('rate'), f'{field}.rate')
        if rate > MAX_RATE:
            raise BudgetError(f'{field}.rate: rate is unreasonably large; clarify fraction vs percent')
        if kind == 'tax':
            basis = info.get('base')
            if basis not in ('base', 'base_plus_fee'):
                raise BudgetError('tax.base must explicitly be base or base_plus_fee')
            if basis == 'base_plus_fee' and fee_added is None:
                return None, 'tax amount depends on unknown service fee'
            taxable = base + (fee_added if basis == 'base_plus_fee' else Decimal('0'))
        else:
            taxable = base
        return round_money(taxable * rate, quantum), None
    raise BudgetError(f'{field}.type: expected none, included, fixed, rate, or unknown')


def row_total(row, quantum):
    rid = row['id']
    q = dec(row.get('quantity'), f'{rid}.quantity', allow_zero=False)
    price = row.get('unit_cost')
    base = round_money(q * dec(price, f'{rid}.unit_cost'), quantum) if price is not None else None
    unknowns = []
    fee = tax = gross = None
    if base is None:
        unknowns.append('unit cost unknown')
    else:
        fee, problem = cost_component(row.get('fee'), f'{rid}.fee', base, quantum)
        if problem:
            unknowns.append(problem)
        tax_info = row.get('tax')
        if isinstance(tax_info, dict) and tax_info.get('type') == 'included' and isinstance(row.get('fee'), dict) and row['fee'].get('type') not in ('none','included'):
            raise BudgetError(f'{rid}: included tax with separately added or unknown fee is ambiguous; clarify tax treatment')
        tax, problem = cost_component(tax_info, f'{rid}.tax', base, quantum, kind='tax', fee_added=fee)
        if problem:
            unknowns.append(problem)
        if fee is not None and tax is not None:
            gross = base + fee + tax
    paid_raw = row.get('paid')
    paid = None if paid_raw is None else dec(paid_raw, f'{rid}.paid')
    if paid is None:
        unknowns.append('paid/deposit amount unknown')
    if paid is not None and gross is not None and paid > gross:
        raise BudgetError(f'{rid}.paid exceeds the full line cost; reconcile before reporting')
    balance = gross - paid if gross is not None and paid is not None else None
    if row.get('cost_basis') not in ('quote','contract','estimate','actual','hypothetical'):
        raise BudgetError(f'{rid}.cost_basis must be quote, contract, estimate, actual, or hypothetical')
    # All components in unit_cost are quoted as total contract cost before any paid amount.
    return {
        'id':rid, 'category':row.get('category','Uncategorized'), 'label':row.get('label',rid),
        'cost_basis':row['cost_basis'], 'quantity':shown(q), 'unit_cost':shown(dec(price, f'{rid}.unit_cost')) if price is not None else None,
        'base_cost':shown(base), 'added_fee':shown(fee), 'added_tax':shown(tax), 'full_cost':shown(gross),
        'paid_to_date':shown(paid), 'balance_due':shown(balance), 'unknowns':unknowns
    }, gross, paid, balance


def read_contingency(value, budget):
    if value is None:
        return 'unspecified', None
    if not isinstance(value, dict):
        raise BudgetError('contingency must be object or omitted')
    policy = value.get('policy')
    if policy not in ('reserved_within_budget', 'additional_to_budget'):
        raise BudgetError('contingency.policy must be reserved_within_budget or additional_to_budget')
    amount = dec(value.get('amount'), 'contingency.amount')
    if policy == 'reserved_within_budget' and amount > budget:
        raise BudgetError('contingency reserve cannot exceed total budget')
    return policy, amount


def validate_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ITEMS:
        raise BudgetError('items must be a list containing 1..500 rows')
    seen = set()
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            raise BudgetError(f'items[{i}] must be object')
        rid = r.get('id')
        if not isinstance(rid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', rid):
            raise BudgetError(f'items[{i}].id invalid')
        if rid in seen:
            raise BudgetError(f'duplicate item id: {rid}')
        seen.add(rid)
        if 'currency' in r and r['currency'] is not None:
            raise BudgetError(f'{rid}.currency: mixed currencies are unsupported; convert with an approved rate before analysis')
        for field in ('category','label'):
            if field in r and (not isinstance(r[field], str) or len(r[field]) > 120):
                raise BudgetError(f'{rid}.{field} must be short text')
    return seen


def prepare_variation(rows, scenario):
    if not isinstance(scenario, dict):
        raise BudgetError('each scenario must be an object')
    sid = scenario.get('id')
    if not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', sid):
        raise BudgetError('scenario.id invalid')
    changes = scenario.get('changes', {})
    if not isinstance(changes, dict):
        raise BudgetError(f'{sid}.changes must be an object')
    allowed = {'quantity', 'unit_cost', 'fee', 'tax', 'paid', 'omit', 'cost_basis'}
    known = {r['id'] for r in rows}
    out = copy.deepcopy(rows)
    for rid, patch in changes.items():
        if rid not in known:
            raise BudgetError(f'{sid}: scenario changes unknown line {rid}')
        if not isinstance(patch, dict) or any(k not in allowed for k in patch):
            raise BudgetError(f'{sid}: illegal change fields for {rid}')
        if patch.get('omit') is True:
            original = next(r for r in rows if r['id'] == rid)
            if original.get('paid') is None or dec(original['paid'], f'{rid}.paid') != 0:
                raise BudgetError(f'{sid}: cannot omit {rid} with unknown or positive payments; establish refunds/sunk costs first')
            if len(patch) != 1:
                raise BudgetError(f'{sid}: omit cannot be combined with other changes')
            out = [r for r in out if r['id'] != rid]
        elif 'omit' in patch:
            raise BudgetError(f'{sid}: omit must be true if provided')
        else:
            for r in out:
                if r['id'] == rid:
                    r.update(copy.deepcopy(patch))
                    break
    if not isinstance(scenario.get('rationale'), str) or not scenario['rationale'].strip():
        raise BudgetError(f'{sid}: scenario.rationale must explain changes')
    return sid, out


def calculate(data):
    if not isinstance(data, dict):
        raise BudgetError('top-level JSON must be an object')
    currency = data.get('currency')
    if not isinstance(currency, str) or not re.fullmatch(r'[A-Z]{3}',currency):
        raise BudgetError('currency must be a three-letter uppercase currency code')
    budget = dec(data.get('budget'), 'budget', allow_zero=False)
    quantum = choose_precision(data)
    if 'guest_count' in data:
        guest_count = data['guest_count']
        if isinstance(guest_count,bool) or not isinstance(guest_count,int) or guest_count <= 0:
            raise BudgetError('guest_count must be a positive integer')
    policy, reserve = read_contingency(data.get('contingency'), budget)
    rows = data.get('items')
    validate_rows(rows)
    scenarios = data.get('scenarios', [])
    if not isinstance(scenarios, list) or len(scenarios) > MAX_SCENARIOS:
        raise BudgetError('scenarios must be an array of at most 12 comparisons')
    ids = {'baseline'}
    variants = [('baseline', 'Original submitted line items', 'No scenario changes', copy.deepcopy(rows))]
    for s in scenarios:
        sid, modified = prepare_variation(rows,s)
        if sid in ids:
            raise BudgetError(f'duplicate scenario id: {sid}')
        ids.add(sid)
        variants.append((sid, s.get('label',sid), s['rationale'], modified))
    outputs = []
    for sid, label, reason, current in variants:
        if not isinstance(label,str) or len(label) > 120:
            raise BudgetError(f'{sid}: label invalid')
        outrows=[]; known_total=Decimal('0'); known_paid=Decimal('0'); known_due=Decimal('0')
        full_costs=True; all_paid=True; issues=[]
        for row in current:
            line, gross, paid, due = row_total(row,quantum)
            outrows.append(line)
            if gross is None:
                full_costs=False
            else:
                known_total += gross
            if paid is None:
                all_paid=False
            else:
                known_paid += paid
            if due is not None:
                known_due += due
            if line['unknowns']:
                issues.append({'item':row['id'],'issues':line['unknowns']})
        spend_cap = budget - reserve if policy == 'reserved_within_budget' else budget
        remaining_after_known = spend_cap - known_total
        totals_complete = full_costs and reserve is not None
        outputs.append({
            'id':sid, 'label':label, 'rationale':reason, 'lines':outrows,
            'priced_items_complete':full_costs, 'paid_amounts_complete':all_paid,
            'known_fully_priced_line_total':shown(known_total),
            'known_paid_amounts_sum':shown(known_paid),
            'known_balances_sum':shown(known_due),
            'spending_cap':shown(spend_cap),
            'budget_headroom':shown(remaining_after_known) if totals_complete else None,
            'headroom_after_known_priced_lines_only':shown(remaining_after_known),
            'known_priced_lines_exceed_spending_cap':remaining_after_known < 0,
            'incomplete_lines':issues,
        })
    return {
        'currency':currency, 'budget':shown(budget), 'guest_count':data.get('guest_count'),
        'rounding_places':data.get('rounding_places'), 'contingency_policy':policy,
        'contingency_amount':shown(reserve),
        'additional_funding_if_contingency_is_extra':shown(budget + reserve) if policy == 'additional_to_budget' else None,
        'comparison':outputs,
        'global_warnings':[
            'Vendor quotes, tax treatment, inclusions, and market rates were not externally verified.',
            'Paid/deposits reduce balance due only; never add paid amounts to cost again.',
            'Unpriced lines or unknown fees/taxes make computed budget headroom incomplete.',
            'No FX conversion, price estimates, authorization, or purchase occurs.',
            'Scenario changes are hypotheses unless separately confirmed by the user or vendors.',
            'No rounding applied unless rounding_places was explicitly supplied; verify invoice rounding rules.' if quantum is None else 'ROUND_HALF_UP is applied to displayed line components at supplied precision; vendor invoice rules may differ.'
        ]
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='JSON input path or - for stdin')
    args=parser.parse_args(argv)
    try:
        if args.input == '-':
            raw = sys.stdin.buffer.read(MAX_RAW_BYTES + 1)
        else:
            path=Path(args.input)
            if path.stat().st_size > MAX_RAW_BYTES:
                raise BudgetError('input file too large')
            raw=path.read_bytes()
        if len(raw) > MAX_RAW_BYTES:
            raise BudgetError('input exceeds 2 MB limit')
        def reject_json_float(_):
            raise BudgetError('JSON decimal numbers must be quoted strings to preserve exact money precision')
        payload=json.loads(raw.decode('utf-8'),parse_float=reject_json_float)
        result=calculate(payload)
        print(json.dumps(result,indent=2,ensure_ascii=False))
    except (BudgetError, ValueError, UnicodeError, OSError, json.JSONDecodeError) as exc:
        print('INPUT ERROR: ' + str(exc), file=sys.stderr)
        return 2
    return 0

if __name__=='__main__':
    sys.exit(main())
