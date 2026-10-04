#!/usr/bin/env python3
import argparse
import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from termgen import (STOP, clean_en, is_product_key, load_input_rows,
                     load_key_filter, norm_lemma, raw_tokens, tokens_lc)
from termgen_v3 import (ENTROPY_GATE, JOIN_GATE, entropy_bits, name_tokens, packed,
                        translations, zh_fragments)

ROOT = Path(__file__).resolve().parent.parent.parent
MAX_ROUNDS = 5
MAX_ITER = 8
MAX_MATCH = 8
SLOT_RE = re.compile(r'\{\d\}')
SLOT_SPLIT = re.compile(r'\{\d\}')


def positions(text, sub):
    out = []
    start = 0
    while True:
        found = text.find(sub, start)
        if found < 0:
            return out
        out.append(found)
        start = found + 1


def match_en(pattern, toks, limit=MAX_MATCH):
    results = []

    def walk(pi, ti, spans):
        if len(results) >= limit:
            return
        if pi == len(pattern):
            if ti == len(toks):
                results.append(tuple(spans))
            return
        token = pattern[pi]
        if SLOT_RE.fullmatch(token):
            for end in range(ti + 1, len(toks) + 1):
                spans.append((ti, end))
                walk(pi + 1, end, spans)
                spans.pop()
                if len(results) >= limit:
                    return
        elif ti < len(toks) and toks[ti] == token:
            walk(pi + 1, ti + 1, spans)

    walk(0, 0, [])
    return results


def match_zh(parts, target, limit=MAX_MATCH):
    size = len(parts)
    slots = [bool(SLOT_RE.fullmatch(piece)) for piece in parts]
    memo = {}

    def feasible(pi, ti):
        key = (pi, ti)
        if key in memo:
            return memo[key]
        if pi == size:
            result = ti == len(target)
        elif slots[pi]:
            result = any(feasible(pi + 1, end) for end in range(ti + 1, len(target) + 1))
        else:
            result = target.startswith(parts[pi], ti) and feasible(pi + 1, ti + len(parts[pi]))
        memo[key] = result
        return result

    results = []

    def walk(pi, ti, fills):
        if len(results) >= limit:
            return
        if pi == size:
            if ti == len(target):
                results.append(dict(fills))
            return
        if slots[pi]:
            for end in range(ti + 1, len(target) + 1):
                if feasible(pi + 1, end):
                    fills.append((parts[pi], target[ti:end]))
                    walk(pi + 1, end, fills)
                    fills.pop()
                    if len(results) >= limit:
                        return
        elif target.startswith(parts[pi], ti):
            walk(pi + 1, ti + len(parts[pi]), fills)

    walk(0, 0, [])
    return results


def fill(pattern, parts):
    return re.sub(r'\{(\d+)\}', lambda match: parts[int(match.group(1))], pattern)


def most_common(counter):
    return min(counter.items(), key=lambda item: (-item[1], item[0]))[0]


def scan_names(pairs, name_like, toks, target):
    supports = defaultdict(set)
    whole = defaultdict(set)
    surfaces = defaultdict(Counter)
    span_pids = defaultdict(set)
    token_df = Counter()
    fragments = [zh_fragments(text) for text in target]
    raws = [raw_tokens(en) for en, zh in pairs]
    for pid in range(len(pairs)):
        if not name_like[pid]:
            continue
        tokens = toks[pid]
        raw = raws[pid]
        whole[tokens].add(pid)
        for token in set(tokens):
            token_df[token] += 1
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                gram = tokens[start:end]
                span_pids[gram].add(pid)
                surfaces[gram][' '.join(raw[start:end])] += 1
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                supports[gram].add(pid)
    return {'supports': supports, 'whole': whole, 'surfaces': surfaces,
            'span_pids': span_pids, 'token_df': token_df, 'fragments': fragments, 'raws': raws}


def collocation_grams(pairs, name_like, toks, target, scan, lexicon):
    names = {}
    for pid in range(len(pairs)):
        if name_like[pid]:
            names.setdefault(pairs[pid][0], toks[pid])
    left = defaultdict(Counter)
    right = defaultdict(Counter)
    for tokens in names.values():
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                gram = tokens[start:end]
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                left[gram][tokens[start - 1] if start else '<BOS>'] += 1
                right[gram][tokens[end] if end < len(tokens) else '<EOS>'] += 1
    holders = defaultdict(set)
    for pid in range(len(pairs)):
        if not name_like[pid]:
            continue
        tokens = toks[pid]
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                holders[tokens[start:end]].add(pairs[pid][0])
    total_tokens = sum(len(tokens) for tokens in names.values())
    found = set()
    for gram, group in holders.items():
        if len(gram) < 2 or len(group) < 2:
            continue
        variants = sorted(variant for variant in lexicon.get(gram, ()) if variant)
        occurrences = [pid for pid in scan['span_pids'].get(gram, ()) if name_like[pid]]
        if not variants or not occurrences:
            continue
        dominant = max(sum(1 for pid in occurrences if variant in target[pid])
                       for variant in variants)
        if dominant * 2 < len(occurrences):
            continue
        count = len(group)
        entropy = max(entropy_bits(left[gram]), entropy_bits(right[gram]))
        joins = []
        dices = []
        for split in range(1, len(gram)):
            first = holders.get(gram[:split], ())
            second = holders.get(gram[split:], ())
            joins.append((count - len(first) * len(second) / total_tokens) / math.sqrt(count))
            dices.append(2 * count / (len(first) + len(second)) if first or second else 0.0)
        if (entropy >= ENTROPY_GATE and min(joins) >= JOIN_GATE) or max(dices) >= 0.5:
            found.add(gram)
    return found


def seed_lexicon(pairs, name_like, toks, target, scan):
    stripped = [(en, target[pid]) for pid, (en, zh) in enumerate(pairs)]
    subdf = Counter(fragment for pieces in scan['fragments'] for fragment in pieces)
    aligned = {gram: translations(gram, support, stripped, scan['fragments'], subdf, scan['whole'])
               for gram, support in scan['supports'].items()
               if len({stripped[pid][0] for pid in support}) >= 2
               or (len(gram) == 1 and gram in scan['whole'])}
    lexicon = defaultdict(set)
    for pid in range(len(pairs)):
        if name_like[pid]:
            lexicon[toks[pid]].add(target[pid])
    for gram, (variants, _, _) in aligned.items():
        for variant in variants:
            variant = re.sub(r'\s+', '', variant)
            if variant:
                lexicon[gram].add(variant)
    return lexicon


def extract_templates(pairs, name_like, toks, target, raws, lexicon):
    instances = defaultdict(lambda: {'fillers': set(), 'pids': set(), 'surfaces': Counter()})
    for pid in range(len(pairs)):
        if not name_like[pid]:
            continue
        tokens = toks[pid]
        text = target[pid]
        raw = raws[pid]
        size = len(tokens)
        options = []
        for start in range(size):
            for end in range(start + 1, size + 1):
                for zh in sorted(lexicon.get(tokens[start:end], ())):
                    if not zh or zh == text:
                        continue
                    spots = positions(text, zh)
                    if len(spots) == 1:
                        options.append((start, end, zh, spots[0]))
        for start, end, zh, spot in options:
            en_pattern = tuple(tokens[:start]) + ('{0}',) + tuple(tokens[end:])
            if en_pattern == ('{0}',):
                continue
            zh_pattern = text[:spot] + '{0}' + text[spot + len(zh):]
            instance = instances[(en_pattern, zh_pattern)]
            instance['fillers'].add((zh,))
            instance['pids'].add(pid)
            instance['surfaces'][' '.join(raw[:start] + ['{0}'] + raw[end:])] += 1
        for first in range(len(options)):
            for second in range(first + 1, len(options)):
                i1, j1, zh1, p1 = options[first]
                i2, j2, zh2, p2 = options[second]
                if not (j1 <= i2 or j2 <= i1) or not (p1 + len(zh1) <= p2 or p2 + len(zh2) <= p1):
                    continue
                if i2 < i1:
                    i1, j1, zh1, p1, i2, j2, zh2, p2 = i2, j2, zh2, p2, i1, j1, zh1, p1
                en_pattern = (tuple(tokens[:i1]) + ('{0}',) + tuple(tokens[j1:i2])
                              + ('{1}',) + tuple(tokens[j2:]))
                if p1 < p2:
                    zh_pattern = (text[:p1] + '{0}' + text[p1 + len(zh1):p2]
                                  + '{1}' + text[p2 + len(zh2):])
                else:
                    zh_pattern = (text[:p2] + '{1}' + text[p2 + len(zh2):p1]
                                  + '{0}' + text[p1 + len(zh1):])
                if not any(not SLOT_RE.fullmatch(token) for token in en_pattern) and not any(
                        SLOT_SPLIT.split(zh_pattern)):
                    continue
                instance = instances[(en_pattern, zh_pattern)]
                instance['fillers'].add((zh1, zh2))
                instance['pids'].add(pid)
                instance['surfaces'][' '.join(raw[:i1] + ['{0}'] + raw[j1:i2]
                                              + ['{1}'] + raw[j2:])] += 1
    return instances


def build_index(confirmed, token_df):
    index = defaultdict(list)
    for key in confirmed:
        literals = [token for token in key[0] if not SLOT_RE.fullmatch(token)]
        token = min(literals, key=lambda word: (token_df.get(word, 0), word)) if literals else ''
        index[token].append(key)
    return index


def infer_lexicon(confirmed, index, pairs, name_like, toks, target, lexicon):
    added = False
    for pid in range(len(pairs)):
        if not name_like[pid]:
            continue
        tokens = toks[pid]
        text = target[pid]
        candidates = set()
        for token in sorted(set(tokens)):
            candidates.update(index.get(token, ()))
        candidates.update(index.get('', ()))
        for key in sorted(candidates):
            matches = match_en(key[0], tokens, limit=2)
            if len(matches) != 1:
                continue
            fills = match_zh(re.split(r'(\{\d\})', key[1]), text, limit=2)
            if len(fills) != 1:
                continue
            spans = matches[0]
            filled = fills[0]
            if len(spans) == 2:
                first = filled.get('{0}')
                second = filled.get('{1}')
                if first is None or second is None:
                    continue
                if (first not in lexicon.get(tokens[spans[0][0]:spans[0][1]], ())
                        and second not in lexicon.get(tokens[spans[1][0]:spans[1][1]], ())):
                    continue
            for (start, end), label in zip(spans, ('{0}', '{1}')):
                zh = filled[label]
                if zh and zh not in lexicon[tokens[start:end]]:
                    lexicon[tokens[start:end]].add(zh)
                    added = True
    return added


def grow_lexicon(pairs, name_like, toks, target, raws, lexicon, token_df):
    for _ in range(MAX_ROUNDS):
        instances = extract_templates(pairs, name_like, toks, target, raws, lexicon)
        confirmed = {key: info for key, info in instances.items()
                     if len(info['fillers']) >= 2 and len(info['pids']) >= 2}
        if not infer_lexicon(confirmed, build_index(confirmed, token_df),
                             pairs, name_like, toks, target, lexicon):
            return confirmed, instances
    instances = extract_templates(pairs, name_like, toks, target, raws, lexicon)
    confirmed = {key: info for key, info in instances.items()
                 if len(info['fillers']) >= 2 and len(info['pids']) >= 2}
    return confirmed, instances


def prepare(pairs, name_like, toks, target, lexicon, confirmed, token_df, collocations):
    part_index = defaultdict(list)
    for key in confirmed:
        for piece in set(SLOT_SPLIT.split(key[1])):
            if piece:
                part_index[piece].append(key)
    template_index = build_index(confirmed, token_df)
    cache = {}

    def span_matches(span):
        found = cache.get(span)
        if found is None:
            candidates = set()
            for token in sorted(set(span)):
                candidates.update(template_index.get(token, ()))
            candidates.update(template_index.get('', ()))
            found = []
            for key in sorted(candidates):
                for spans in match_en(key[0], span):
                    found.append((key, spans))
            cache[span] = found
        return found

    prepared = {}
    for pid in range(len(pairs)):
        if not name_like[pid]:
            continue
        tokens = toks[pid]
        text = target[pid]
        applicable = set()
        for piece, keys in part_index.items():
            if piece in text:
                applicable.update(keys)
        leaves = {}
        sites = defaultdict(list)
        breaks = defaultdict(float)
        collocs = []
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                gram = tokens[start:end]
                variants = sorted(variant for variant in lexicon.get(gram, ()) if variant in text)
                if variants:
                    leaves[(start, end)] = (gram, variants)
                for key, spans in span_matches(gram):
                    if key in applicable:
                        sites[(start, end)].append((key, spans))
                if gram in collocations and variants:
                    penalty = len(packed({'id': 'u0', 'en': ' '.join(gram),
                                          'zh': [min(variants, key=len)]})) + 1
                    collocs.append((start, end, penalty))
                    for middle in range(start + 1, end):
                        breaks[middle] = max(breaks[middle], penalty)
        prepared[pid] = {'n': len(tokens), 'leaves': leaves, 'sites': sites,
                         'breaks': breaks, 'collocs': collocs,
                         'root': (tokens, ('@', pairs[pid][0]))}
    return prepared


def pattern_plans(confirmed):
    plans = {}
    for key in confirmed:
        pieces = re.split(r'(\{\d\})', key[1])
        literals = [piece for piece in pieces if not SLOT_RE.fullmatch(piece)]
        slots = [int(piece[1]) for piece in pieces if SLOT_RE.fullmatch(piece)]
        plans[key] = (literals, slots)
    return plans


def seed_costs(lexicon, confirmed, span_pids, surfaces, template_surfaces, target, at_pids):
    entries = [('t', key, len(confirmed[key]['pids']), template_surfaces[key]) for key in confirmed]
    entries += [('u', gram, len(span_pids.get(gram, ())), most_common(surfaces[gram]))
                for gram in lexicon]
    entries += [('x', key, len(pids), key[1]) for key, pids in at_pids.items()]
    entries.sort(key=lambda item: (item[0], -item[2], item[3]))
    counter = Counter()
    meta = {}
    for kind, key, uses, en in entries:
        counter[kind] += 1
        meta[key] = {'id': kind + str(counter[kind]), 'en': en}
    uses = {'card': {}, 'variant': {}, 'template': {}}
    for gram, variants in lexicon.items():
        pids = span_pids.get(gram, ())
        uses['card'][gram] = len(pids)
        for variant in variants:
            uses['variant'][(gram, variant)] = sum(1 for pid in pids if variant in target[pid])
    for key, pids in at_pids.items():
        uses['card'][key] = len(pids)
        for pid in pids:
            uses['variant'][(key, target[pid])] = uses['variant'].get((key, target[pid]), 0) + 1
    for key in confirmed:
        uses['template'][key] = len(confirmed[key]['pids'])
    return meta, uses


def leaf_cost_table(variants_map, meta, uses, forbidden):
    table = {}
    for key, variants in variants_map.items():
        entry = meta[key]
        base = len(packed({'id': entry['id'], 'en': entry['en'], 'zh': []})) + 1
        share = max(1, uses['card'].get(key, 0))
        for variant in variants:
            if (key, variant) in forbidden:
                continue
            table[(key, variant)] = (base / share + (len(variant) + 3) / max(
                1, uses['variant'].get((key, variant), 0)))
    return table


def template_cost_table(confirmed, meta, uses, forbidden):
    table = {}
    for key in confirmed:
        if key in forbidden:
            continue
        entry = meta[key]
        table[key] = (len(packed({'id': entry['id'], 'en': entry['en'], 'zh': [key[1]]})) + 1) / max(
            1, uses['template'].get(key, 0))
    return table


def cut_drift(zh, left, right, anchors, anchor_key, lexicon):
    left_z = anchors.get(anchor_key.get(left['c'], ''))
    right_z = anchors.get(anchor_key.get(right['c'], ''))
    left_v = left['v']
    right_v = right['v']
    left_known = set(left_z or ()) | set(lexicon.get(left['c'], ()))
    right_known = set(right_z or ()) | set(lexicon.get(right['c'], ()))
    if left_z and left_v not in left_z:
        for w in left_known:
            if len(w) > len(left_v) and zh.startswith(w):
                return True
    if right_z and right_v not in right_z:
        for w in right_known:
            if len(w) > len(right_v) and zh.endswith(w):
                return True
        if right_v and any(w and right_v[0] == w[-1] for w in left_known):
            return True
    return False


def derive_pair(prepared, text, leaf_costs, template_costs, plans, anchors, anchor_key, lexicon):
    size = prepared['n']
    leaves = prepared['leaves']
    sites = prepared['sites']
    breaks = prepared['breaks']
    collocs = prepared['collocs']
    root_gram, root_key = prepared['root']
    chart = [[None] * (size + 1) for _ in range(size + 1)]
    for length in range(1, size + 1):
        for start in range(size - length + 1):
            end = start + length
            entries = {}
            leaf = leaves.get((start, end))
            if leaf:
                gram, variants = leaf
                for variant in variants:
                    cost = leaf_costs.get((gram, variant))
                    if cost is None:
                        continue
                    current = entries.get(variant)
                    if current is None or cost < current[0]:
                        entries[variant] = (cost, {'c': gram, 'v': variant})
            if start == 0 and end == size and (root_gram, text) not in leaf_costs:
                cost = leaf_costs[(root_key, text)]
                current = entries.get(text)
                if current is None or cost < current[0]:
                    entries[text] = (cost, {'c': root_key, 'v': text})
            for key, spans in sites.get((start, end), ()):
                children = [chart[start + a][start + b] for a, b in spans]
                if any(not child for child in children):
                    continue
                base = template_costs.get(key)
                if base is None:
                    continue
                penalty = 0.0
                for a, b, value in collocs:
                    if start <= a and b <= end and not any(
                            start + s <= a and b <= start + e for s, e in spans):
                        penalty = max(penalty, value)
                literals, slots = plans[key]
                if len(children) == 1:
                    for zh, (cost, node) in children[0].items():
                        filled = literals[0] + zh + literals[1]
                        if filled not in text:
                            continue
                        total = base + cost + penalty
                        current = entries.get(filled)
                        if current is None or total < current[0]:
                            entries[filled] = (total, {'c': key, 's': [node]})
                else:
                    for zh0, (cost0, node0) in children[0].items():
                        for zh1, (cost1, node1) in children[1].items():
                            parts = (zh0, zh1)
                            filled = (literals[0] + parts[slots[0]] + literals[1]
                                      + parts[slots[1]] + literals[2])
                            if filled not in text:
                                continue
                            total = base + cost0 + cost1 + penalty
                            current = entries.get(filled)
                            if current is None or total < current[0]:
                                entries[filled] = (total, {'c': key, 's': [node0, node1]})
            for middle in range(start + 1, end):
                left = chart[start][middle]
                right = chart[middle][end]
                if not left or not right:
                    continue
                for zh_left, (cost_left, node_left) in left.items():
                    for zh_right, (cost_right, node_right) in right.items():
                        filled = zh_left + zh_right
                        if filled not in text:
                            continue
                        if 'v' in node_left and 'v' in node_right and cut_drift(
                                filled, node_left, node_right, anchors, anchor_key, lexicon):
                            continue
                        total = cost_left + cost_right + breaks.get(middle, 0.0)
                        current = entries.get(filled)
                        if current is None or total < current[0]:
                            entries[filled] = (total, {'cat': [node_left, node_right]})
            chart[start][end] = entries
    return chart[0][size].get(text)


def node_uses(node):
    leaves = set()
    templates = set()
    stack = [(node, True)]
    while stack:
        current, is_root = stack.pop()
        if 'v' in current:
            leaves.add((current['c'], current['v'], is_root))
        elif 's' in current:
            templates.add(current['c'])
            stack.extend((child, False) for child in current['s'])
        else:
            stack.extend((child, False) for child in current['cat'])
    return leaves, templates


def recount(derivations):
    card_pids = defaultdict(set)
    variant_pids = defaultdict(set)
    template_pids = defaultdict(set)
    for pid, (_, node) in derivations.items():
        leaves, templates = node_uses(node)
        for key, variant, _ in leaves:
            card_pids[key].add(pid)
            variant_pids[(key, variant)].add(pid)
        for key in templates:
            template_pids[key].add(pid)
    return {'card': {key: len(pids) for key, pids in card_pids.items()},
            'variant': {key: len(pids) for key, pids in variant_pids.items()},
            'template': {key: len(pids) for key, pids in template_pids.items()}}


def relabel(node, by_key):
    if 'v' in node:
        return {'c': by_key[node['c']]['id'], 'v': node['v']}
    if 's' in node:
        return {'c': by_key[node['c']]['id'],
                's': [relabel(child, by_key) for child in node['s']]}
    return {'cat': [relabel(node['cat'][0], by_key), relabel(node['cat'][1], by_key)]}


def collect_terms(node, out):
    if 'c' in node:
        out.append(node['c'])
    if 's' in node:
        for child in node['s']:
            collect_terms(child, out)
    elif 'cat' in node:
        for child in node['cat']:
            collect_terms(child, out)
    return out


def forbidden_from(cards, anchors, anchor_key):
    leaves = set()
    templates = set()
    for card in cards:
        key = card['key']
        if card['kind'] == 'unit':
            for index, variant in enumerate(card['zh']):
                if index > 0 and card['variants'][variant] == 1:
                    leaves.add((key, variant))
        elif card['kind'] == 'template' and card['uses'] <= 1:
            templates.add(key)
        anchored = anchors.get(anchor_key.get(key, ''))
        if not anchored:
            continue
        for variant in card['zh']:
            if variant in anchored or card['variants'][variant] >= 3:
                continue
            if any(variant != z and (variant in z or z in variant) for z in anchored):
                leaves.add((key, variant))
    return leaves, templates


def assemble(rows, pairs, pair_id, pair_keys, derivations, surfaces, template_surfaces):
    leaf_pids = defaultdict(set)
    variant_pids = defaultdict(set)
    part_keys = set()
    template_pids = defaultdict(set)
    for pid, (_, node) in derivations.items():
        leaves, templates = node_uses(node)
        for key, variant, is_root in leaves:
            leaf_pids[key].add(pid)
            variant_pids[(key, variant)].add(pid)
            if not is_root:
                part_keys.add(key)
        for key in templates:
            template_pids[key].add(pid)
    variants_by_key = defaultdict(Counter)
    for (key, variant), pids in variant_pids.items():
        variants_by_key[key][variant] = len(pids)
    cards = []
    for key, pids in leaf_pids.items():
        if key[0] == '@':
            kind = 'exception'
            en = key[1]
        else:
            kind = 'unit' if key in part_keys else 'exception'
            en = most_common(surfaces[key])
        cards.append({'key': key, 'kind': kind, 'en': en, 'pids': pids,
                      'variants': variants_by_key[key]})
    for key, pids in template_pids.items():
        cards.append({'key': key, 'kind': 'template', 'en': template_surfaces[key],
                      'pids': pids, 'variants': Counter({key[1]: len(pids)})})
    rank = {'unit': 0, 'template': 1, 'exception': 2}
    prefix = {'unit': 'u', 'template': 't', 'exception': 'x'}
    cards.sort(key=lambda card: (rank[card['kind']], -len(card['pids']), card['en']))
    counter = Counter()
    for card in cards:
        counter[card['kind']] += 1
        card['id'] = prefix[card['kind']] + str(counter[card['kind']])
        card['zh'] = [variant for variant, count in sorted(card['variants'].items(),
                                                           key=lambda item: (-item[1], item[0]))]
        card['uses'] = len(card['pids'])
    batch = [{'id': card['id'], 'en': card['en'], 'zh': card['zh']} for card in cards]
    by_key = {card['key']: card for card in cards}
    audit = []
    for key, en, zh in rows:
        tree = relabel(derivations[pair_id[(en, zh)]][1], by_key)
        audit.append({'key': key, 'en': en, 'zh': zh,
                      'terms': list(dict.fromkeys(collect_terms(tree, []))),
                      'status': 'exception' if 'v' in tree else 'compositional',
                      'tree': tree})
    review_chars = sum(len(packed(card)) + 1 for card in batch)
    return {'cards': cards, 'batch': batch, 'audit': audit, 'review_chars': review_chars}


def reconstruct(node, by_id):
    if 'cat' in node:
        left = reconstruct(node['cat'][0], by_id)
        right = reconstruct(node['cat'][1], by_id)
        if left is None or right is None:
            return None
        return left[0] + ' ' + right[0], left[1] + right[1]
    card = by_id.get(node['c'])
    if card is None:
        return None
    if 'v' in node:
        if node['v'] not in card['zh']:
            return None
        return card['en'], node['v']
    children = [reconstruct(child, by_id) for child in node['s']]
    if any(child is None for child in children):
        return None
    return (fill(card['en'], [child[0] for child in children]),
            fill(card['zh'][0], [child[1] for child in children]))


def verify_rows(audit, batch):
    by_id = {card['id']: card for card in batch}
    failed = []
    for row in audit:
        rebuilt = reconstruct(row['tree'], by_id)
        if rebuilt is None or tokens_lc(rebuilt[0]) != tokens_lc(row['en']) or rebuilt[1] != re.sub(
                r'\s+', '', row['zh']):
            failed.append(row['key'])
    return len(audit) - len(failed), failed


def build(input_path, exclude_keys=None):
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
    target = [re.sub(r'\s+', '', zh) for en, zh in pairs]
    toks = [name_tokens(en) for en, zh in pairs]
    name_like = [bool(tokens) and clean_en(pairs[pid][0]) == pairs[pid][0]
                 for pid, tokens in enumerate(toks)]
    scan = scan_names(pairs, name_like, toks, target)
    lexicon = seed_lexicon(pairs, name_like, toks, target, scan)
    confirmed, instances = grow_lexicon(pairs, name_like, toks, target, scan['raws'],
                                        lexicon, scan['token_df'])
    template_surfaces = {key: most_common(info['surfaces']) for key, info in instances.items()}
    collocations = collocation_grams(pairs, name_like, toks, target, scan, lexicon)
    prepared = prepare(pairs, name_like, toks, target, lexicon, confirmed, scan['token_df'],
                       collocations)
    plans = pattern_plans(confirmed)
    anchors = defaultdict(set)
    for key, en, zh in rows:
        anchors[norm_lemma(en)].add(re.sub(r'\s+', '', zh))
    at_pids = defaultdict(set)
    for pid in range(len(pairs)):
        if name_like[pid]:
            at_pids[('@', pairs[pid][0])].add(pid)
    variants_map = {gram: sorted(variants) for gram, variants in lexicon.items()}
    for key, pids in at_pids.items():
        variants_map[key] = sorted({target[pid] for pid in pids})
    anchor_key = {gram: norm_lemma(most_common(scan['surfaces'][gram]))
                  for gram in lexicon}
    meta, uses = seed_costs(lexicon, confirmed, scan['span_pids'], scan['surfaces'],
                            template_surfaces, target, at_pids)
    best = None
    cheapest = None
    previous = None
    forbidden_leaf = set()
    forbidden_tpl = set()
    for _ in range(MAX_ITER):
        leaf_costs = leaf_cost_table(variants_map, meta, uses, forbidden_leaf)
        template_costs = template_cost_table(confirmed, meta, uses, forbidden_tpl)
        derivations = {}
        for pid in range(len(pairs)):
            if not name_like[pid]:
                derivations[pid] = (0.0, {'c': ('@', pairs[pid][0]), 'v': target[pid]})
                continue
            found = derive_pair(prepared[pid], target[pid], leaf_costs, template_costs, plans,
                                anchors, anchor_key, lexicon)
            derivations[pid] = found if found is not None else (0.0, {'c': toks[pid],
                                                                     'v': target[pid]})
        candidate = assemble(rows, pairs, pair_id, pair_keys, derivations, scan['surfaces'],
                             template_surfaces)
        candidate['forbidden'] = forbidden_from(candidate['cards'], anchors, anchor_key)
        if cheapest is None or candidate['review_chars'] < cheapest['review_chars']:
            cheapest = candidate
        if not candidate['forbidden'][0] and not candidate['forbidden'][1] and (
                best is None or candidate['review_chars'] < best['review_chars']):
            best = candidate
        uses = recount(derivations)
        meta.update({card['key']: {'id': card['id'], 'en': card['en']}
                     for card in candidate['cards']})
        forbidden_leaf |= candidate['forbidden'][0]
        forbidden_tpl |= candidate['forbidden'][1]
        signature = tuple(packed(node) for _, (_, node) in sorted(derivations.items()))
        if signature == previous:
            break
        previous = signature
    best = best or cheapest
    reconstructed, failed = verify_rows(best['audit'], best['batch'])
    source_chars = sum(len(packed({'en': en, 'zh_candidates': [zh]})) + 1 for _, en, zh in rows)
    stats = {'input_rows': len(raw_rows), 'filtered_rows': len(rows),
             'unique_pairs': len(pairs),
             'unit_cards': sum(card['kind'] == 'unit' for card in best['cards']),
             'template_cards': sum(card['kind'] == 'template' for card in best['cards']),
             'exception_cards': sum(card['kind'] == 'exception' for card in best['cards']),
             'review_cards': len(best['cards']),
             'compositional_rows': sum(row['status'] == 'compositional' for row in best['audit']),
             'exception_rows': sum(row['status'] == 'exception' for row in best['audit']),
             'input_chars': source_chars, 'review_chars': best['review_chars'],
             'reading_reduction': 1 - best['review_chars'] / source_chars if source_chars else 0.0,
             'reconstructed_rows': reconstructed, 'failed_keys': failed}
    return {'cards': best['cards'], 'batch': best['batch'], 'audit': best['audit'],
            'pairs': pairs, 'pair_keys': pair_keys, 'stats': stats}


def write_outputs(out_dir, result):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, values in [('batch.jsonl', result['batch']),
                             ('audit.jsonl', result['audit'])]:
        with (out_dir / filename).open('w', encoding='utf-8', newline='') as stream:
            for value in values:
                stream.write(packed(value) + '\n')
    with (out_dir / 'candidates.tsv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
        writer.writerow(['id', 'en', 'zh', 'kind', 'uses', 'reason', 'sources', 'evidence'])
        for card in result['cards']:
            reason = {'unit': 'reusable_fragment', 'template': 'slot_template'}.get(
                card['kind'], 'non_name_like' if card['key'][0] == '@' else 'whole_name')
            sources = sorted({key for pid in card['pids'] for key in result['pair_keys'][pid]})
            evidence = [{'key': result['pair_keys'][pid][0], 'en': result['pairs'][pid][0],
                         'zh': result['pairs'][pid][1]} for pid in sorted(card['pids'])[:2]]
            writer.writerow([card['id'], card['en'], '|'.join(card['zh']), card['kind'],
                             card['uses'], reason, ';'.join(sources), packed(evidence)])
    with (out_dir / 'summary.json').open('w', encoding='utf-8') as stream:
        stream.write(json.dumps(result['stats'], ensure_ascii=False, indent=2) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v4.py')
    sub = parser.add_subparsers(dest='command', required=True)
    extract = sub.add_parser('extract')
    extract.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    extract.add_argument('--exclude-keys')
    extract.add_argument('--out-dir', type=Path)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = build(args.input, args.exclude_keys)
    result['stats']['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    out_dir = args.out_dir or ROOT / 'Vanilla/termgen-v4-out'
    write_outputs(out_dir, result)
    print(packed({'out_dir': str(out_dir), **result['stats']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
