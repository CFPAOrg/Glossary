import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from termgen import (CJK_RE, STOP, clean_en, clean_zh, is_name_like,
                     is_product_key, load_input_rows, load_key_filter, raw_tokens, tokens_lc)

ROOT = Path(__file__).resolve().parent.parent.parent
CONNECTORS = {'of', 'the'}
MAX_GRAM = 5
MIN_STRONG_FREQ = 3
ENTROPY_GATE = 2.0
JOIN_GATE = 3.0


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def zh_fragments(text):
    return {run[i:j] for run in CJK_RE.findall(text)
            for i in range(len(run))
            for j in range(i + 1, min(len(run), i + 8) + 1)}


def name_tokens(en):
    return tuple(tokens_lc(en)) if is_name_like(en) and not re.search(r'[0-9]', en) else ()


def translations(gram, support, pairs, fragments, subdf, whole):
    exact = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
    hits = Counter(sub for pid in support for sub in fragments[pid])
    eligible = {sub for sub, count in hits.items()
                if count >= 2 and count / subdf[sub] >= 0.5}
    variants = list(exact)
    covered = {pid for pid in support if any(z in pairs[pid][1] for z in variants)}
    confidence = 1.0 if exact else 0.0
    while len(variants) < max(4, len(exact)):
        uncovered = support - covered
        choices = []
        for sub in eligible:
            extra = {pid for pid in uncovered if sub in fragments[pid]}
            if len(extra) < 2:
                continue
            outside = subdf[sub] - hits[sub]
            dice = 2 * len(extra) / (len(uncovered) + len(extra) + outside)
            if dice >= 0.5:
                choices.append((dice, len(extra), len(sub), sub, extra))
        if not choices:
            break
        dice, count, length, sub, extra = max(choices)
        variants.append(sub)
        confidence = max(confidence, dice)
        covered.update(extra)
    return variants, confidence, len(covered) / len(support)


def chinese_match(zh, parts):
    target = re.sub(r'\s+', '', zh)
    variants = tuple(tuple(re.sub(r'\s+', '', z) for z in card['zh_candidates'] if z)
                     for card in parts)

    @lru_cache(maxsize=None)
    def visit(pos, remaining):
        if not remaining:
            return pos == len(target)
        if pos and pos < len(target) - 1 and target[pos] == '的':
            if visit(pos + 1, remaining):
                return True
        for i, options in enumerate(variants):
            if remaining & (1 << i):
                for variant in options:
                    if target.startswith(variant, pos) and visit(
                            pos + len(variant), remaining ^ (1 << i)):
                        return True
        return False

    return bool(parts) and visit(0, (1 << len(parts)) - 1)


def compose(toks, zh, lexicon, forbid=None):
    if not toks or not zh:
        return None
    attempts = 0

    def paths(pos, chosen):
        nonlocal attempts
        if attempts >= 256:
            return None
        if pos == len(toks):
            attempts += 1
            if chinese_match(zh, chosen):
                return [card['id'] for card in chosen]
            return None
        for end in range(min(len(toks), pos + MAX_GRAM), pos, -1):
            gram = toks[pos:end]
            if gram != forbid and gram in lexicon:
                found = paths(end, chosen + [lexicon[gram]])
                if found is not None:
                    return found
        if toks[pos] in CONNECTORS:
            return paths(pos + 1, chosen)
        return None

    return paths(0, [])


def refine_atoms(aligned, supports, pairs, fragments, whole):
    atoms = {gram[0]: {'zh_candidates': info[0]}
             for gram, info in aligned.items() if len(gram) == 1 and info[0]}
    refined = {}
    for word, card in atoms.items():
        gram = (word,)
        found = defaultdict(set)
        for pid in supports[gram]:
            en, zh = pairs[pid]
            toks = name_tokens(en)
            if toks.count(word) != 1 or len(toks) == 1:
                continue
            other = [t for t in toks if t != word and t not in CONNECTORS]
            if any(t not in atoms for t in other):
                continue
            parts = [atoms[t] for t in other]
            for sub in fragments[pid]:
                if chinese_match(zh, parts + [{'zh_candidates': [sub]}]):
                    found[sub].add(pid)
        choices = sorted(((len(pids), len(sub), sub, pids) for sub, pids in found.items()
                          if len({pairs[pid][0] for pid in pids}) >= 2), reverse=True)
        variants = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
        explained = set()
        for count, length, sub, pids in choices:
            if not (pids - explained):
                continue
            if sub not in variants:
                variants.append(sub)
            explained.update(pids)
            if len(variants) >= 4:
                break
        if len(explained) >= max(2, len(supports[gram]) / 2):
            refined[gram] = (variants, aligned[gram][1], len(explained) / len(supports[gram]))
        elif variants:
            merged = list(card['zh_candidates'])
            merged.extend(z for z in variants if z not in merged)
            refined[gram] = (merged, aligned[gram][1], aligned[gram][2])
    aligned.update(refined)


def entropy_bits(counter):
    total = sum(counter.values())
    if not total:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counter.values())


def outside_units(toks, bank):
    if not toks:
        return []
    for end in range(min(MAX_GRAM, len(toks)), 0, -1):
        gram = toks[:end]
        if gram in bank:
            rest = outside_units(toks[end:], bank)
            if rest is not None:
                return [bank[gram]] + rest
    if toks[0] in CONNECTORS:
        return outside_units(toks[1:], bank)
    return None


def verify_nested(grams, aligned, bank, supports, pairs, fragments, whole, names):
    for gram in grams:
        info = aligned.get(gram)
        if not info:
            continue
        found = defaultdict(set)
        head_of = {}
        for pid in supports[gram]:
            en, zh = pairs[pid]
            toks = names[en]
            positions = [i for i in range(len(toks) - len(gram) + 1)
                         if toks[i:i + len(gram)] == gram]
            if len(positions) != 1:
                continue
            start = positions[0]
            before = outside_units(toks[:start], bank)
            after = outside_units(toks[start + len(gram):], bank)
            if before is None or after is None or not before and not after:
                continue
            outside = toks[start + len(gram):] or toks[:start]
            head_of[pid] = outside[-1]
            for sub in fragments[pid]:
                if chinese_match(zh, before + after + [{'zh_candidates': [sub]}]):
                    found[sub].add(pid)
        eligible = sorted(((len(pids), len(sub), sub, pids)
                           for sub, pids in found.items()
                           if len({head_of[pid] for pid in pids}) >= 2), reverse=True)
        exact = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
        variants = list(exact)
        covered = set()
        for count, length, sub, pids in eligible:
            extra = pids - covered
            if len({head_of[pid] for pid in extra}) < 2:
                continue
            if sub not in variants:
                variants.append(sub)
            covered.update(pids)
            if len(variants) >= max(4, len(exact)):
                break
        if len(covered) >= max(2, len(supports[gram]) / 2):
            aligned[gram] = (variants, info[1], len(covered) / len(supports[gram]))


def trim_variants(cards, audit, by_id):
    observed = defaultdict(set)
    for row in audit:
        parts = [by_id[cid] for cid in row['terms']]
        for cid in set(row['terms']):
            card = by_id[cid]
            if card['kind'] == 'exception' or row['terms'].count(cid) > 1:
                observed[cid].update(card['zh_candidates'])
                continue
            for variant in card['zh_candidates']:
                narrowed = [dict(part, zh_candidates=[variant]) if part['id'] == cid
                            else part for part in parts]
                if chinese_match(row['zh'], narrowed):
                    observed[cid].add(variant)
    for card in cards:
        card['zh_candidates'] = [z for z in card['zh_candidates']
                                 if z in observed[card['id']]]


def compact_card(card):
    return {'id': card['id'], 'en': card['en'], 'zh': card['zh_candidates']}


def select_cards(cards, audit, budget):
    by_id = {card['id']: card for card in cards}
    bundles = defaultdict(int)
    for row in audit:
        bundles[frozenset(row['terms'])] += 1
    selected = set()
    order = []
    while len(selected) < len(cards):
        gains = defaultdict(int)
        for deps, count in bundles.items():
            missing = deps - selected
            if missing:
                gains[missing] += count
        if not gains:
            break
        remaining = budget - len(selected) if budget else len(cards)
        choices = [(gain / len(missing), gain, tuple(sorted(missing)), missing)
                   for missing, gain in gains.items() if len(missing) <= remaining]
        if not choices:
            break
        _, _, _, best = max(choices)
        for card_id in sorted(best, key=lambda cid: (-by_id[cid]['uses'], cid)):
            selected.add(card_id)
            order.append(by_id[card_id])
    return order


def build(input_path, budget=0, exclude_keys=None):
    raw_rows = load_input_rows(str(input_path))
    whitelist, blacklist = load_key_filter()
    excluded = re.compile(exclude_keys) if exclude_keys else None
    rows = [(key, en, zh) for key, en, zh in raw_rows
            if is_product_key(key, whitelist, blacklist)
            and not (excluded and excluded.search(key))]
    pairs = sorted({(en, zh) for _, en, zh in rows})
    pair_id = {pair: pid for pid, pair in enumerate(pairs)}
    pair_keys = defaultdict(list)
    for key, en, zh in rows:
        pair_keys[pair_id[(en, zh)]].append(key)
    supports = defaultdict(set)
    whole = defaultdict(set)
    surfaces = {}
    names = {}
    for pid, (en, zh) in enumerate(pairs):
        toks = name_tokens(en)
        if not toks or clean_en(en) != en or clean_zh(zh) != zh:
            continue
        whole[toks].add(pid)
        names.setdefault(en, toks)
        for start in range(len(toks)):
            for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                gram = toks[start:end]
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                supports[gram].add(pid)
                surfaces.setdefault(gram, ' '.join(raw_tokens(en)[start:end]))
    fragments = [zh_fragments(zh) for en, zh in pairs]
    subdf = Counter(sub for subs in fragments for sub in subs)
    aligned = {gram: translations(gram, support, pairs, fragments, subdf, whole)
               for gram, support in supports.items()
               if len({pairs[pid][0] for pid in support}) >= 2
               or (len(gram) == 1 and gram in whole)}
    refine_atoms(aligned, supports, pairs, fragments, whole)
    total_tokens = sum(len(toks) for toks in names.values())
    left_neighbors = defaultdict(Counter)
    right_neighbors = defaultdict(Counter)
    for toks in names.values():
        for start in range(len(toks)):
            for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                gram = toks[start:end]
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                left_neighbors[gram][toks[start - 1] if start else '<BOS>'] += 1
                right_neighbors[gram][toks[end] if end < len(toks) else '<EOS>'] += 1
    frequency = {gram: len({pairs[pid][0] for pid in support})
                 for gram, support in supports.items()}
    strong_atoms = {gram for gram, count in frequency.items()
                    if len(gram) == 1 and count >= MIN_STRONG_FREQ
                    and max(entropy_bits(left_neighbors[gram]),
                            entropy_bits(right_neighbors[gram])) >= ENTROPY_GATE}
    qualified = set()
    for gram, count in frequency.items():
        if len(gram) < 2 or count < MIN_STRONG_FREQ:
            continue
        if max(entropy_bits(left_neighbors[gram]),
               entropy_bits(right_neighbors[gram])) < ENTROPY_GATE:
            continue
        joins = [(count - frequency.get(gram[:i], 0) * frequency.get(gram[i:], 0)
                  / total_tokens) / math.sqrt(count) for i in range(1, len(gram))]
        if joins and min(joins) >= JOIN_GATE:
            qualified.add(gram)
    accepted = set(strong_atoms)
    discovered = set()
    while True:
        proposed = set()
        for toks in names.values():
            for start in range(len(toks)):
                for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                    if toks[start:end] not in accepted:
                        continue
                    for residual in (toks[:start], toks[end:]):
                        if residual in qualified and residual not in accepted:
                            proposed.add(residual)
        if not proposed:
            break
        accepted |= proposed
        discovered |= proposed
    bank = {}
    for gram in sorted(aligned, key=lambda g: (len(g), g)):
        variants = aligned[gram][0]
        if not variants:
            continue
        if len({pairs[pid][0] for pid in supports[gram]}) < 2 and not (
                len(gram) == 1 and gram in whole):
            continue
        if all(compose(gram, zh, bank) is not None for zh in variants):
            continue
        bank[gram] = {'id': gram, 'en': surfaces[gram], 'zh_candidates': variants}
    for gram in discovered:
        if gram in aligned:
            bank.setdefault(gram, {'id': gram, 'en': surfaces[gram],
                                   'zh_candidates': aligned[gram][0]})
    verify_nested(discovered, aligned, bank, supports, pairs, fragments, whole, names)
    lexicon = {}
    unit_cards = []
    for gram in sorted(supports, key=lambda g: (len(g), g)):
        support = supports[gram]
        distinct = {pairs[pid][0] for pid in support}
        if len(distinct) < 2 and not (len(gram) == 1 and gram in whole):
            continue
        variants, confidence, cover = aligned[gram]
        if not variants:
            continue
        if gram not in discovered and all(compose(gram, zh, lexicon) is not None
                                          for zh in variants):
            continue
        card = {'id': 'u%d' % (len(unit_cards) + 1), 'en': surfaces[gram],
                'zh_candidates': variants, 'kind': 'unit',
                'reason': ('nested_phrase' if gram in discovered else
                           'reusable_fragment' if len(distinct) >= 2 else 'standalone_name'),
                'score': round(confidence, 4), 'alignment_cover': round(cover, 4),
                'sources': sorted({key for pid in support for key in pair_keys[pid]}),
                'evidence': [{'variant': variant, 'key': pair_keys[pid][0],
                              'en': pairs[pid][0], 'zh': pairs[pid][1]}
                             for variant in variants
                             for pid in [p for p in sorted(support)
                                         if variant in pairs[p][1]][:2]],
                'uses': 0}
        unit_cards.append(card)
        lexicon[gram] = card
    proofs = {}
    exceptions = {}
    for pid, (en, zh) in enumerate(pairs):
        toks = name_tokens(en)
        proof = (compose(toks, zh, lexicon) if clean_en(en) == en
                 and clean_zh(zh) == zh else None)
        if proof is not None:
            proofs[pid] = proof
            continue
        if en not in exceptions:
            exceptions[en] = {'id': 'x%d' % (len(exceptions) + 1), 'en': en,
                              'zh_candidates': [], 'kind': 'exception',
                              'reason': 'missing_translation' if not zh else
                                        'unexplained_translation',
                              'score': 1.0, 'sources': [], 'evidence': [], 'uses': 0}
        card = exceptions[en]
        if zh and zh not in card['zh_candidates']:
            card['zh_candidates'].append(zh)
        card['sources'].extend(pair_keys[pid])
        if len(card['evidence']) < 3:
            card['evidence'].append({'key': pair_keys[pid][0], 'en': en, 'zh': zh})
        proofs[pid] = [card['id']]
    all_cards = {card['id']: card for card in unit_cards + list(exceptions.values())}
    audit = []
    for key, en, zh in rows:
        deps = proofs[pair_id[(en, zh)]]
        for card_id in set(deps):
            all_cards[card_id]['uses'] += 1
        audit.append({'key': key, 'en': en, 'zh': zh, 'terms': deps,
                      'status': 'exception' if deps[0].startswith('x') else 'compositional'})
    cards = [card for card in all_cards.values() if card['uses']]
    trim_variants(cards, audit, all_cards)
    review = select_cards(cards, audit, budget)
    selected = {card['id'] for card in review}
    for row in audit:
        row['pending'] = sorted(set(row['terms']) - selected)
    backlog = [card for card in cards if card['id'] not in selected]
    source_chars = sum(len(packed({'en': en, 'zh_candidates': [zh]})) + 1
                       for key, en, zh in rows)
    review_chars = sum(len(packed(compact_card(card))) + 1 for card in review)
    stats = {'input_rows': len(raw_rows), 'filtered_rows': len(rows),
             'unique_pairs': len(pairs), 'unit_cards': sum(c['kind'] == 'unit' for c in cards),
             'nested_cards': sum(c['reason'] == 'nested_phrase' for c in cards),
             'exception_cards': sum(c['kind'] == 'exception' for c in cards),
             'candidate_cards': len(cards), 'review_cards': len(review),
             'backlog_cards': len(backlog),
             'compositional_rows': sum(r['status'] == 'compositional' for r in audit),
             'exception_rows': sum(r['status'] == 'exception' for r in audit),
             'accounted_rows': len(audit),
             'ready_rows': sum(not r['pending'] for r in audit),
             'pending_rows': sum(bool(r['pending']) for r in audit),
             'input_chars': source_chars, 'review_chars': review_chars,
             'reading_reduction': 1 - review_chars / source_chars if source_chars else 0.0}
    return {'review': review, 'candidates': cards, 'backlog': backlog,
            'audit': audit, 'stats': stats}


def write_outputs(out_dir, result):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, values in [('batch.jsonl', map(compact_card, result['review'])),
                             ('backlog.jsonl', map(compact_card, result['backlog'])),
                             ('audit.jsonl', result['audit'])]:
        with (out_dir / filename).open('w', encoding='utf-8', newline='') as stream:
            for value in values:
                stream.write(packed(value) + '\n')
    with (out_dir / 'candidates.tsv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['id', 'en', 'zh', 'kind', 'uses', 'reason', 'score',
                         'sources', 'evidence'])
        for card in result['candidates']:
            writer.writerow([card['id'], card['en'], '|'.join(card['zh_candidates']),
                             card['kind'], card['uses'], card['reason'], card['score'],
                             ';'.join(card['sources']), packed(card['evidence'])])
    with (out_dir / 'summary.json').open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(result['stats'], ensure_ascii=False, indent=2) + '\n')


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError('must be zero or positive')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v3.py')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('extract')
    p.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    p.add_argument('--budget', type=nonnegative, default=0,
                   help='maximum review cards; 0 keeps the complete compressed inventory')
    p.add_argument('--exclude-keys')
    p.add_argument('--out-dir', type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = build(args.input, args.budget, args.exclude_keys)
    result['stats']['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    out_dir = args.out_dir or args.input.parent / 'termgen-v3-out'
    write_outputs(out_dir, result)
    print(packed({'out_dir': str(out_dir), **result['stats']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
