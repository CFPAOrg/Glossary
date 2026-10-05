import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from termgen import (build, clean_zh, compact_entry, is_product_key, load_gold,
                     load_input_rows, load_key_filter, norm_lemma, tokens_lc, verify_rows)

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / 'Vanilla/latest.tsv'
GOLD = ROOT / 'Vanilla/terms/terms-v1.tsv'
CASES = Path(__file__).with_name('termgen_cases.json')
SLOT_RE = re.compile(r'\{(\d+)\}')
WS_RE = re.compile(r'\s+')
KINDS = {'u': 'unit', 't': 'template', 'x': 'exception'}
EXPECT = ('unit', 'compositional', 'exception')


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def ratio(num, den):
    return num / den if den else None


def load_jsonl(path):
    with open(path, encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def line_chars(path):
    # +1 计行尾换行，与 v3/v4 写盘时的 review_chars 口径一致
    with open(path, encoding='utf-8', newline='') as stream:
        return sum(len(line.rstrip('\n')) + 1 for line in stream)


def entry_kind(entry_id):
    return KINDS.get(str(entry_id)[:1], 'other')


def zh_variants(values):
    out = []
    for value in values or ():
        text = WS_RE.sub('', clean_zh(str(value)))
        if text:
            out.append(text)
    return out


def case_variants(value):
    return zh_variants(str(value or '').split('|'))


def load_filtered_rows():
    raw = load_input_rows(str(INPUT))
    whitelist, blacklist = load_key_filter()
    return [(key, en, zh) for key, en, zh in raw
            if is_product_key(key, whitelist, blacklist)]


def reachable_gold(gold, rows):
    names = [tuple(norm_lemma(en).split()) for _, en, _ in rows]
    out = []
    for en, variants in gold:
        gram = tuple(norm_lemma(en).split())
        if gram and any(any(toks[i:i + len(gram)] == gram
                            for i in range(len(toks) - len(gram) + 1))
                        for toks in names):
            out.append((en, variants))
    return out


def gold_report(entries, gold, rows):
    reach = reachable_gold(gold, rows)
    index = defaultdict(list)
    for entry in entries:
        if entry_kind(entry['id']) == 'template':
            continue
        key = norm_lemma(entry['en'])
        if key:
            index[key].append(entry)
    matched = 0
    pairs = []
    for en, variants in reach:
        hits = index.get(norm_lemma(en))
        if hits:
            matched += 1
            pairs.extend((en, variants, entry) for entry in hits)
    any_ok = all_ok = 0
    examples = []
    for en, gvars, entry in pairs:
        want = set(gvars)
        variants = zh_variants(entry.get('zh'))
        any_hit = any(v in want for v in variants)
        all_hit = bool(variants) and all(v in want for v in variants)
        any_ok += any_hit
        all_ok += all_hit
        if not all_hit and len(examples) < 30:
            examples.append({'en': en, 'id': entry['id'], 'entry_zh': variants,
                             'gold_zh': gvars})
    return {'gold_terms': len(gold), 'reachable': len(reach), 'matched': matched,
            'recall': ratio(matched, len(reach)), 'matched_entries': len(pairs),
            'any_ok': any_ok, 'all_ok': all_ok,
            'any_ok_rate': ratio(any_ok, len(pairs)),
            'all_ok_rate': ratio(all_ok, len(pairs)), 'not_all_ok': examples}


def ranked_gold(entries, gold, rows):
    reach = reachable_gold(gold, rows)
    index = defaultdict(list)
    for en, variants in entries:
        key = norm_lemma(en or '')
        if key:
            index[key].append(variants)
    matched = checked = any_ok = 0
    for en, gvars in reach:
        hits = index.get(norm_lemma(en))
        if not hits:
            continue
        matched += 1
        want = set(gvars)
        for variants in hits:
            variants = zh_variants(variants)
            if not variants:
                continue
            checked += 1
            if any(v in want for v in variants):
                any_ok += 1
    return {'reachable': len(reach), 'matched': matched,
            'recall': ratio(matched, len(reach)), 'zh_checked': checked,
            'any_ok': any_ok, 'any_ok_rate': ratio(any_ok, checked)}


def case_report(cases, audit, entries):
    by_key = {row['key']: row for row in audit}
    by_id = {entry['id']: entry for entry in entries}
    index = defaultdict(list)
    for entry in entries:
        key = norm_lemma(entry['en'])
        if key:
            index[key].append(entry)
    by_expect = {expect: {'total': 0, 'covered': 0} for expect in EXPECT}
    missed = []
    for case in cases:
        expect = case['expect']
        bucket = by_expect.setdefault(expect, {'total': 0, 'covered': 0})
        bucket['total'] += 1
        row = by_key.get(case['key'])
        why = []
        if expect == 'unit':
            want = set(case_variants(case.get('zh')))
            hits = index.get(norm_lemma(case.get('en') or ''), [])
            if not hits:
                why.append('no_entry')
            elif not any(want & set(zh_variants(entry.get('zh'))) for entry in hits):
                why.append('zh_mismatch')
        elif expect == 'compositional':
            if row is None:
                why.append('no_row')
            else:
                if row.get('status') != 'compositional':
                    why.append('status_' + str(row.get('status')))
                required = [norm_lemma(term) for term in case.get('required_terms') or []]
                present = {norm_lemma(by_id[cid]['en']) for cid in row.get('terms') or []
                           if cid in by_id}
                if [term for term in required if term and term not in present]:
                    why.append('missing_terms')
        else:
            if row is None:
                why.append('no_row')
            elif not any(entry_kind(cid) in ('exception', 'template')
                         for cid in row.get('terms') or []):
                why.append('no_exception_or_template')
        if why:
            missed.append({'key': case['key'], 'en': case['en'], 'expect': expect,
                           'why': why})
        else:
            bucket['covered'] += 1
    return {'total': len(cases),
            'covered': sum(bucket['covered'] for bucket in by_expect.values()),
            'by_expect': by_expect, 'missed': missed}


def noise_report(entries):
    units = [entry for entry in entries if entry_kind(entry['id']) == 'unit']
    variants = sum(len(entry.get('zh') or []) for entry in units)
    return {'unit_entries': len(units), 'variants_total': variants,
            'per_entry_avg': ratio(variants, len(units))}


def fill_slots(pattern, values):
    def replace(match):
        index = int(match.group(1))
        if index >= len(values):
            raise ValueError('slot {%d} missing' % index)
        return values[index]
    return SLOT_RE.sub(replace, pattern)


def expand_tree(node, by_id):
    if 'cat' in node:
        left_en, left_zh = expand_tree(node['cat'][0], by_id)
        right_en, right_zh = expand_tree(node['cat'][1], by_id)
        return left_en + ' ' + right_en, left_zh + right_zh
    entry = by_id.get(node.get('c'))
    if entry is None:
        raise ValueError('unknown entry %s' % node.get('c'))
    if 's' in node:
        parts = [expand_tree(child, by_id) for child in node['s']]
        if not entry.get('zh'):
            raise ValueError('template %s has no zh' % entry['id'])
        return (fill_slots(entry['en'], [part[0] for part in parts]),
                fill_slots(entry['zh'][0], [part[1] for part in parts]))
    variant = node.get('v')
    if variant not in (entry.get('zh') or []):
        raise ValueError('variant %r missing from %s' % (variant, entry['id']))
    return entry['en'], variant


def verify_v4(audit, entries):
    by_id = {entry['id']: entry for entry in entries}
    failures = []
    for row in audit:
        try:
            en, zh = expand_tree(row.get('tree'), by_id)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            failures.append({'key': row.get('key'), 'why': str(exc)})
            continue
        if (tokens_lc(en) != tokens_lc(row.get('en') or '')
                or zh != WS_RE.sub('', row.get('zh') or '')):
            failures.append({'key': row.get('key'), 'why': 'mismatch'})
    return {'checked': len(audit), 'reconstructed': len(audit) - len(failures),
            'failed_keys': [failure['key'] for failure in failures],
            'failures': failures[:10]}


def check_lossless(version, audit, entries):
    if version == 'termgen':
        converted = [{'id': entry['id'], 'en': entry['en'],
                      'zh_candidates': entry.get('zh') or []} for entry in entries]
        return verify_rows(audit, converted)
    return verify_v4(audit, entries)


def lossless_report(version, dir_label, entries, audit, review_chars, rows, gold, cases):
    input_chars = sum(len(packed({'en': en, 'zh_candidates': [zh]})) + 1
                      for _, en, zh in rows)
    kinds = Counter(entry_kind(entry['id']) for entry in entries)
    exception_rows = sum(1 for row in audit if row.get('status') == 'exception')
    return {'dir': dir_label,
            'lossless': check_lossless(version, audit, entries),
            'review_chars': review_chars, 'input_chars': input_chars,
            'reduction': 1 - review_chars / input_chars if input_chars else None,
            'entries': {'total': len(entries), 'by_kind': dict(kinds),
                      'exception_rows': exception_rows,
                      'exception_share': ratio(exception_rows, len(audit))},
            'gold': gold_report(entries, gold, rows),
            'noise': noise_report(entries),
            'cases': case_report(cases, audit, entries)}


def termgen_aligned(gold, rows):
    temp = tempfile.mkdtemp(prefix='termgen-scorecard-')
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'utility/archive/termgen.py'), 'extract',
             '--input', str(INPUT), '--mode', 'aligned', '--out-dir', temp],
            cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode:
            return {'lossless': None,
                    'error': (proc.stderr or proc.stdout or '').strip()[-500:]}
        items = []
        for batch in load_jsonl(Path(temp) / 'llm-batches.jsonl'):
            items.extend(batch.get('items') or [])
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    entries = [(item.get('en'), item.get('zh_candidates') or []) for item in items]
    return {'lossless': None, 'candidates': len(items),
            'chars': sum(len(packed({'en': item.get('en'),
                                     'zh_candidates': item.get('zh_candidates') or []})) + 1
                         for item in items),
            'gold': ranked_gold(entries, gold, rows)}


def termgen_v4(gold, rows, cases):
    temp = tempfile.mkdtemp(prefix='termgen-v4-')
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'utility/archive/termgen_v4.py'), 'extract',
             '--input', str(INPUT), '--out-dir', temp],
            cwd=str(ROOT), capture_output=True, text=True)
        if proc.returncode:
            return {'lossless': None,
                    'error': (proc.stderr or proc.stdout or '').strip()[-500:]}
        out_dir = Path(temp)
        return lossless_report('v4', 'temp', load_jsonl(out_dir / 'batch.jsonl'),
                               load_jsonl(out_dir / 'audit.jsonl'),
                               line_chars(out_dir / 'batch.jsonl'), rows, gold, cases)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def ranked_report(gold, rows):
    from argparse import Namespace
    sys.path.append(str(Path(__file__).resolve().parent / 'archive'))
    import termgen_v2
    _, _, recs = termgen_v2.build(Namespace(input=str(INPUT), background=None,
                                            exclude_keys=None))
    report = {'v2': {'lossless': None, 'candidates': len(recs),
                     'chars': sum(len(packed({'en': rec['en'],
                                              'zh_candidates': rec['zh']})) + 1
                                  for rec in recs),
                     'gold': ranked_gold([(rec['en'], rec['zh']) for rec in recs],
                                         gold, rows)}}
    report['v1'] = termgen_aligned(gold, rows)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_scorecard.py')
    parser.add_argument('--with-ranked', action='store_true')
    args = parser.parse_args(argv)
    rows = load_filtered_rows()
    gold = [(en, zh_variants(variants)) for en, variants in load_gold([str(GOLD)])]
    cases = json.loads(CASES.read_text(encoding='utf-8'))
    cases = cases.get('cases') if isinstance(cases, dict) else cases
    result = build(INPUT)
    report = {'termgen': lossless_report(
        'termgen', 'in-process', [compact_entry(entry) for entry in result['review']],
        result['audit'], result['stats']['review_chars'], rows, gold, cases)}
    report['v4'] = termgen_v4(gold, rows, cases)
    if args.with_ranked:
        report.update(ranked_report(gold, rows))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
