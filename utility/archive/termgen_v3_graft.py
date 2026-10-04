import argparse
import csv
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from termgen import is_product_key, load_input_rows, load_key_filter, norm_lemma, tokens_lc
from termgen_v3 import chinese_match, compose, name_tokens, raw_tokens

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_V3_DIR = ROOT / 'Vanilla/termgen-v3-out'
DEFAULT_OUT_DIR = ROOT / 'Vanilla/termgen-v3-graft-out'
INPUT_PATH = ROOT / 'Vanilla/latest.tsv'
CONNECTORS = {'of', 'the'}
MIN_ROWS = 2
MIN_PAIRS = 2
MAX_INDUCTION_ROUNDS = 2
MAX_PRUNE_ROUNDS = 4


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def stripped(text):
    return re.sub(r'\s+', '', text)


def load_cards(path):
    cards = {}
    with open(path, encoding='utf-8', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            cards[row['id']] = {'id': row['id'], 'en': row['en'],
                                'zh_candidates': row['zh'].split('|') if row['zh'] else [],
                                'kind': row['kind'], 'uses': int(row['uses'])}
    return cards


def load_audit(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def build_lexicon(cards, atoms):
    lexicon = {}
    for card in list(cards.values()) + atoms:
        if card['kind'] != 'unit':
            continue
        tokens = name_tokens(card['en'])
        if tokens:
            lexicon[tokens] = card
    return lexicon


def load_standalone(rows):
    standalone = defaultdict(set)
    for _, en, zh in rows:
        standalone[norm_lemma(en)].add(zh)
    return standalone


def unit_variants(cards):
    variants = set()
    for card in cards.values():
        if card['kind'] == 'unit':
            variants.update(card['zh_candidates'])
    return variants


def accounted(variants, zh):
    target = stripped(zh)
    reachable = [False] * (len(target) + 1)
    reachable[0] = True
    for end in range(1, len(target) + 1):
        for start in range(end):
            if reachable[start] and target[start:end] in variants:
                reachable[end] = True
                break
    return reachable[-1]


def row_tokens(en):
    return name_tokens(en) or tuple(tokens_lc(en))


def span_variants(lexicon, target, tokens):
    spans = []
    for start in range(len(tokens)):
        for end in range(start + 1, len(tokens) + 1):
            card = lexicon.get(tokens[start:end])
            if card is None:
                continue
            found = [z for z in card['zh_candidates']
                     if z and z != target and target.count(z) == 1]
            if found:
                spans.append((start, end, max(found, key=lambda z: (len(z), z))))
    return spans


def has_literal(pattern):
    return any(not token.startswith('{') and token not in CONNECTORS for token in pattern)


def add_template(templates, pattern, zh_pattern, row, fillers):
    record = templates.setdefault((pattern, zh_pattern),
                                  {'keys': set(), 'fillers': set(), 'pairs': set()})
    record['keys'].add(row['key'])
    record['fillers'].add(fillers)
    record['pairs'].add((row['en'], row['zh']))


def extract_templates(audit, lexicon):
    templates = {}
    for row in audit:
        tokens = row_tokens(row['en'])
        target = stripped(row['zh'])
        if not tokens or not target:
            continue
        spans = span_variants(lexicon, target, tokens)
        for start, end, variant in spans:
            pattern = tokens[:start] + ('{0}',) + tokens[end:]
            if not has_literal(pattern):
                continue
            cut = target.index(variant)
            add_template(templates, pattern, target[:cut] + '{0}' + target[cut + len(variant):],
                         row, tokens[start:end])
        for first in range(len(spans)):
            for second in range(first + 1, len(spans)):
                i1, j1, v1 = spans[first]
                i2, j2, v2 = spans[second]
                if j1 > i2:
                    continue
                p1, p2 = target.index(v1), target.index(v2)
                if not (p1 + len(v1) <= p2 or p2 + len(v2) <= p1):
                    continue
                pattern = tokens[:i1] + ('{0}',) + tokens[j1:i2] + ('{1}',) + tokens[j2:]
                if not has_literal(pattern):
                    continue
                events = sorted([(p1, len(v1), '{0}'), (p2, len(v2), '{1}')])
                pieces, position = [], 0
                for pos, size, slot in events:
                    pieces.append(target[position:pos])
                    pieces.append(slot)
                    position = pos + size
                pieces.append(target[position:])
                add_template(templates, pattern, ''.join(pieces), row,
                             (tokens[i1:j1], tokens[i2:j2]))
    return templates


def split_pattern(pattern):
    parts, current = [], ''
    for char in pattern:
        if char == '{':
            if current:
                parts.append(('lit', current))
            current = '{'
        elif char == '}':
            parts.append(('slot', current + '}'))
            current = ''
        else:
            current += char
    if current:
        parts.append(('lit', current))
    return parts


def match_zh(pattern, target):
    parts = split_pattern(pattern)
    found = []

    def visit(index, position, slots):
        if found:
            return
        if index == len(parts):
            if position == len(target):
                found.append(list(slots))
            return
        kind, value = parts[index]
        if kind == 'lit':
            if target.startswith(value, position):
                visit(index + 1, position + len(value), slots)
            return
        for end in range(position + 1, len(target) + 1):
            slots.append(target[position:end])
            visit(index + 1, end, slots)
            slots.pop()
            if found:
                return

    visit(0, 0, [])
    return found[0] if found else None


def match_en(pattern, tokens):
    found = []

    def visit(index, position, spans):
        if found:
            return
        if index == len(pattern):
            if position == len(tokens):
                found.append(list(spans))
            return
        token = pattern[index]
        if token.startswith('{'):
            for end in range(position + 1, len(tokens) + 1):
                spans.append((position, end))
                visit(index + 1, end, spans)
                spans.pop()
                if found:
                    return
            return
        if position < len(tokens) and tokens[position] == token:
            visit(index + 1, position + 1, spans)

    visit(0, 0, [])
    return found[0] if found else None


def confirmed(templates):
    return {key for key, record in templates.items()
            if len(record['fillers']) >= MIN_ROWS and len(record['pairs']) >= MIN_PAIRS}


def prepare(audit, order, variants):
    entries = []
    for row in audit:
        if row['status'] != 'exception' or accounted(variants, row['zh']):
            continue
        tokens = row_tokens(row['en'])
        target = stripped(row['zh'])
        if not tokens or not target:
            continue
        matches = []
        for key in order:
            pattern, zh_pattern = key
            spans = match_en(pattern, tokens)
            if spans is None:
                continue
            slots = match_zh(zh_pattern, target)
            if slots is None:
                continue
            matches.append((key, spans, slots))
        if matches:
            entries.append({'row': row, 'tokens': tokens, 'raw': raw_tokens(row['en']),
                            'target': target, 'matches': matches})
    return entries


def filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
    card = lexicon.get(filler)
    if not (card and card['id'] in atom_ids):
        known = standalone.get(norm_lemma(surface))
        if not known or slot_zh not in known:
            return False
    return compose(filler, slot_zh, lexicon) is not None


def attempt(entries, lexicon, standalone, atom_ids, allowed):
    results = {}
    for entry in entries:
        for key, spans, slots in entry['matches']:
            if allowed is not None and key not in allowed:
                continue
            terms, ok = [], True
            for (start, end), slot_zh in zip(spans, slots):
                filler = entry['tokens'][start:end]
                surface = ' '.join(entry['raw'][start:end])
                if not filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
                    ok = False
                    break
                terms.append(compose(filler, slot_zh, lexicon))
            if ok:
                results[entry['row']['key']] = {'template': key, 'slots': terms}
                break
    return results


def collect_failures(entries, results, lexicon, standalone, atom_ids):
    failed = defaultdict(set)
    for entry in entries:
        if entry['row']['key'] in results:
            continue
        for key, spans, slots in entry['matches']:
            for (start, end), slot_zh in zip(spans, slots):
                filler = entry['tokens'][start:end]
                surface = ' '.join(entry['raw'][start:end])
                if not filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
                    failed[(norm_lemma(surface), slot_zh)].add(entry['row']['key'])
    return failed


def next_unit_id(cards, atoms):
    numbers = [int(card_id[1:]) for card_id in cards
               if card_id.startswith('u') and card_id[1:].isdigit()]
    return max(numbers or [0]) + 1 + len(atoms)


def atom_surface(entries, keys, en_norm):
    for entry in entries:
        if entry['row']['key'] not in keys:
            continue
        for start in range(len(entry['tokens'])):
            for end in range(start + 1, len(entry['tokens']) + 1):
                surface = ' '.join(entry['raw'][start:end])
                if norm_lemma(surface) == en_norm:
                    return surface
    return None


def induce(entries, cards, lexicon, standalone, atoms, atom_ids):
    for _ in range(MAX_INDUCTION_ROUNDS):
        results = attempt(entries, lexicon, standalone, atom_ids, None)
        failed = collect_failures(entries, results, lexicon, standalone, atom_ids)
        added = 0
        for (en_norm, slot_zh), keys in sorted(failed.items()):
            if len(keys) < MIN_ROWS:
                continue
            tokens = tuple(en_norm.split())
            if tokens in lexicon:
                continue
            surface = atom_surface(entries, keys, en_norm)
            if not surface or name_tokens(surface) != tokens:
                continue
            card = {'id': 'u%d' % next_unit_id(cards, atoms), 'en': surface,
                    'zh_candidates': [slot_zh], 'kind': 'unit',
                    'reason': 'induced_atom', 'uses': 0}
            lexicon[tokens] = card
            atoms.append(card)
            atom_ids.add(card['id'])
            added += 1
        if not added:
            break
    return atoms


def prune(entries, cards, atoms, pair_of, standalone):
    atom_ids = {atom['id'] for atom in atoms}
    allowed = None
    for _ in range(MAX_PRUNE_ROUNDS):
        lexicon = build_lexicon(cards, atoms)
        results = attempt(entries, lexicon, standalone, atom_ids, allowed)
        uses = Counter(record['template'] for record in results.values())
        kept = {key for key in {match[0] for entry in entries for match in entry['matches']}
                if uses[key] >= MIN_ROWS}
        covered = defaultdict(set)
        for row_key, record in results.items():
            for cards_in_slot in record['slots']:
                for card_id in cards_in_slot:
                    if card_id in atom_ids:
                        covered[card_id].add(row_key)
        dropped = {card_id for card_id in atom_ids
                   if len(covered[card_id]) < MIN_ROWS
                   or len({pair_of[key] for key in covered[card_id]}) < MIN_PAIRS}
        if kept == allowed and not dropped:
            break
        allowed = kept
        if dropped:
            atom_ids -= dropped
            atoms[:] = [atom for atom in atoms if atom['id'] not in dropped]
    lexicon = build_lexicon(cards, atoms)
    results = attempt(entries, lexicon, standalone, atom_ids, allowed)
    return atoms, allowed, results


def verify(audit, by_id):
    failed = []
    for row in audit:
        terms = row['terms']
        if any(card_id not in by_id for card_id in terms):
            failed.append(row['key'])
            continue
        if row['status'] == 'exception':
            card = by_id[terms[0]]
            ok = (len(terms) == 1 and card['en'] == row['en']
                  and (row['zh'] in card['zh_candidates']
                       or not row['zh'] and not card['zh_candidates']))
        elif terms[0].startswith('t'):
            ok = verify_template(row, terms, by_id)
        else:
            parts = [by_id[card_id] for card_id in terms]
            expected = tuple(token for token in name_tokens(row['en'])
                             if token not in CONNECTORS)
            actual = tuple(token for card in parts for token in name_tokens(card['en'])
                           if token not in CONNECTORS)
            ok = bool(expected) and actual == expected and chinese_match(row['zh'], parts)
        if not ok:
            failed.append(row['key'])
    return {'checked': len(audit), 'reconstructed': len(audit) - len(failed),
            'failed_keys': failed}


def verify_template(row, terms, by_id):
    template = by_id[terms[0]]
    pattern = tuple(template['en'].split(' '))
    tokens = row_tokens(row['en'])
    spans = match_en(pattern, tokens)
    if spans is None:
        return False
    filler_cards = [by_id[card_id] for card_id in terms[1:]]
    rebuilt, slot_cards, index = [], [], 0
    for token in pattern:
        if not token.startswith('{'):
            rebuilt.append(token)
            continue
        start, end = spans[int(token[1])]
        chunk, collected = [], []
        while len(collected) < end - start:
            if index >= len(filler_cards):
                return False
            card_tokens = list(name_tokens(filler_cards[index]['en']))
            if not card_tokens:
                return False
            collected.extend(card_tokens)
            chunk.append(filler_cards[index])
            index += 1
        if collected != list(tokens[start:end]):
            return False
        rebuilt.extend(card['en'] for card in chunk)
        slot_cards.append(chunk)
    if index != len(filler_cards):
        return False
    if stripped(' '.join(rebuilt)).lower() != stripped(row['en']).lower():
        return False
    target = stripped(row['zh'])
    slots = match_zh(template['zh_candidates'][0], target)
    if slots is None or len(slots) != len(slot_cards):
        return False
    rebuilt = template['zh_candidates'][0]
    for number, (slot_zh, cards_in_slot) in enumerate(zip(slots, slot_cards)):
        if not chinese_match(slot_zh, cards_in_slot):
            return False
        rebuilt = rebuilt.replace('{%d}' % number, slot_zh, 1)
    return stripped(rebuilt) == target


def write_outputs(out_dir, batch, audit, stats):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / 'batch.jsonl').open('w', encoding='utf-8', newline='') as stream:
        for card in batch:
            stream.write(packed({'id': card['id'], 'en': card['en'],
                                 'zh': card['zh_candidates']}) + '\n')
    with (out_dir / 'audit.jsonl').open('w', encoding='utf-8', newline='') as stream:
        for row in audit:
            stream.write(packed(row) + '\n')
    with (out_dir / 'summary.json').open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(stats, ensure_ascii=False, indent=2) + '\n')


def sort_key(card):
    return (-card['uses'], card['id'])


def graft(v3_dir, out_dir):
    cards = load_cards(v3_dir / 'candidates.tsv')
    stats = json.loads((v3_dir / 'summary.json').read_text(encoding='utf-8'))
    audit = load_audit(v3_dir / 'audit.jsonl')
    rows = [(key, en, zh) for key, en, zh in load_input_rows(str(INPUT_PATH))
            if is_product_key(key, *load_key_filter())]
    standalone = load_standalone(rows)
    templates = extract_templates(audit, build_lexicon(cards, []))
    order = sorted(confirmed(templates),
                   key=lambda key: (-len(templates[key]['keys']), len(' '.join(key[0])),
                                    key[0], key[1]))
    entries = prepare(audit, order, unit_variants(cards))
    pair_of = {entry['row']['key']: (entry['row']['en'], entry['row']['zh'])
               for entry in entries}
    atoms = induce(entries, cards, build_lexicon(cards, []), standalone, [], set())
    atoms, allowed, results = prune(entries, cards, atoms, pair_of, standalone)
    uses = Counter(record['template'] for record in results.values())
    ranked = sorted((key for key in allowed if uses[key] >= MIN_ROWS),
                    key=lambda key: (-uses[key], key[0], key[1]))
    template_cards = [{'id': 't%d' % number, 'en': ' '.join(key[0]),
                       'zh_candidates': [key[1]], 'kind': 'template',
                       'reason': 'sentence_template', 'uses': uses[key],
                       'sources': sorted(row_key for row_key, record in results.items()
                                         if record['template'] == key),
                       'evidence': [{'key': row_key, 'en': pair_of[row_key][0],
                                     'zh': pair_of[row_key][1]}
                                    for row_key in sorted(
                                        row_key for row_key, record in results.items()
                                        if record['template'] == key)[:2]]}
                      for number, key in enumerate(ranked, 1)]
    template_ids = {key: card['id'] for key, card in zip(ranked, template_cards)}
    emitted = []
    for row in audit:
        row = dict(row, pending=[])
        record = results.get(row['key'])
        if record is not None:
            terms = [template_ids[record['template']]]
            for cards_in_slot in record['slots']:
                terms.extend(cards_in_slot)
            row['terms'] = list(dict.fromkeys(terms))
            row['status'] = 'compositional'
        emitted.append(row)
    referenced = Counter(card_id for row in emitted for card_id in set(row['terms']))
    for card in cards.values():
        card['uses'] = referenced.get(card['id'], 0)
    for atom in atoms:
        atom['uses'] = referenced.get(atom['id'], 0)
        atom['sources'] = sorted(row_key for row_key, record in results.items()
                                 if atom['id'] in {card_id for slot in record['slots']
                                                   for card_id in slot})
        atom['evidence'] = [{'key': row_key, 'en': pair_of[row_key][0],
                             'zh': pair_of[row_key][1]} for row_key in atom['sources'][:2]]
    batch = [card for card in cards.values()
             if card['kind'] == 'unit' or referenced.get(card['id'], 0)]
    batch.extend(template_cards)
    batch.extend(atoms)
    units = sorted((card for card in batch if card['kind'] == 'unit'), key=sort_key)
    templates_out = sorted((card for card in batch if card['kind'] == 'template'), key=sort_key)
    exceptions = sorted((card for card in batch if card['kind'] == 'exception'), key=sort_key)
    batch = units + templates_out + exceptions
    by_id = {card['id']: card for card in batch}
    report = verify(emitted, by_id)
    removed = sum(1 for card in cards.values()
                  if card['kind'] == 'exception' and referenced.get(card['id'], 0) == 0)
    review_chars = sum(len(packed({'id': card['id'], 'en': card['en'],
                                   'zh': card['zh_candidates']})) + 1 for card in batch)
    stats['review_chars'] = review_chars
    stats['review_cards'] = len(batch)
    stats['exception_rows'] = sum(row['status'] == 'exception' for row in emitted)
    stats['compositional_rows'] = sum(row['status'] == 'compositional' for row in emitted)
    stats['rescued_rows'] = len(results)
    stats['removed_exception_cards'] = removed
    stats['added_template_cards'] = len(templates_out)
    stats['added_atoms'] = len(atoms)
    stats['reconstructed_rows'] = report['reconstructed']
    stats['failed_keys'] = report['failed_keys']
    write_outputs(out_dir, batch, emitted, stats)
    return {'out_dir': str(out_dir), 'rescued_rows': len(results),
            'templates': [{'id': card['id'], 'en': card['en'], 'zh': card['zh_candidates'],
                           'uses': card['uses']} for card in templates_out],
            'review_chars': review_chars, 'review_cards': len(batch),
            'exception_rows': stats['exception_rows'],
            'compositional_rows': stats['compositional_rows'],
            'removed_exception_cards': removed,
            'added_template_cards': len(templates_out), 'added_atoms': len(atoms),
            'checked': report['checked'], 'reconstructed_rows': report['reconstructed'],
            'failed_keys': report['failed_keys']}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v3_graft.py')
    parser.add_argument('--v3-dir', type=Path, default=DEFAULT_V3_DIR)
    parser.add_argument('--out-dir', type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    summary = graft(args.v3_dir, args.out_dir)
    summary['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    print(packed(summary))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
