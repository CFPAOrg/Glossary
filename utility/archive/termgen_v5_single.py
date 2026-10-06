#!/usr/bin/env python3
"""termgen-v5-single —— 单语术语候选：统计定候选，组合纪律定原子性。

没有中文时现行 termgen 一条都发不出来：条目要由中文变体证明、由中文切分核验。
本工具把同一套纪律换成单语版：

    支持度过滤 → 长度升序，能被更短条目拼出来的就不单列

产出是「有原子性、没有译文证明」的英文候选，供人工或 LLM 定译名。
bench 给出 池子 / 原子化 / 加门控 三档的 规模-召回-假阳性，用来量这一步单语化掉多少。
--family 把候选按共现图分家族（木种/颜色/矿物这种），便于成组翻译。

门控默认关：熵/搭配当硬门会砍掉 support 很高的词——Egg 的邻居熵只有 0.59，
因为它几乎总跟着 Spawn。它们是排序特征，不是过滤器。

key 过滤默认走原版白名单；模组 key（block.<modid>.*）用 --key-filter off，或 --keys 给正则。

用法：
    python utility/archive/termgen_v5_single.py extract --input Vanilla/latest.tsv --out en-terms.tsv
    python utility/archive/termgen_v5_single.py extract --input mod-en.tsv --key-filter off --family
    python utility/archive/termgen_v5_single.py bench --input Vanilla/latest.tsv --gold Vanilla/terms/terms-v1.tsv
"""
import argparse
import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen as tg

MAX_GRAM = tg.MAX_GRAM
CONNECTORS = tg.CONNECTORS
ROOT = Path(__file__).resolve().parent.parent.parent


def load_rows(path, key_filter='on', keys=None):
    wl, bl = tg.load_key_filter()
    pattern = re.compile(keys) if keys else None
    rows = []
    for key, en, zh in tg.load_input_rows(str(path)):
        en = tg.clean_en(en)
        if not en:
            continue
        if key_filter == 'off':
            rows.append((key, en))
        elif pattern is not None:
            if pattern.search(key):
                rows.append((key, en))
        elif tg.is_product_key(key, wl, bl):
            rows.append((key, en))
    return rows


def name_index(rows):
    names = {}
    for key, en in rows:
        toks = tg.name_tokens(en)
        if toks:
            names.setdefault(en, toks)
    return names


def gram_spans(toks):
    for start in range(len(toks)):
        for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
            gram = toks[start:end]
            if gram[0] in tg.STOP or gram[-1] in tg.STOP:
                continue
            yield start, end, gram


def collect(names):
    supports = defaultdict(set)
    left = defaultdict(Counter)
    right = defaultdict(Counter)
    for en, toks in names.items():
        for start, end, gram in gram_spans(toks):
            supports[gram].add(en)
            left[gram][toks[start - 1] if start else '<BOS>'] += 1
            right[gram][toks[end] if end < len(toks) else '<EOS>'] += 1
    return supports, left, right


def surfaces_of(names):
    surfaces = {}
    for en, toks in names.items():
        raw = tg.raw_tokens(en)
        for start, end, gram in gram_spans(toks):
            surfaces.setdefault(gram, ' '.join(raw[start:end]))
    return surfaces


def measures(supports, left, right, total_tokens):
    stats = {}
    for gram, names in supports.items():
        count = len(names)
        entropy = max(tg.entropy_bits(left[gram]), tg.entropy_bits(right[gram]))
        joins = None
        if len(gram) >= 2:
            joins = min((count - len(supports.get(gram[:i], ())) * len(supports.get(gram[i:], ()))
                         / total_tokens) / math.sqrt(count) for i in range(1, len(gram)))
        stats[gram] = (count, entropy, joins)
    return stats


# 单语的「已经拼得出」：词元串能否被已有条目完整覆盖，of/the 可跳过
def composable(toks, lexicon):
    def walk(pos):
        if pos == len(toks):
            return True
        for end in range(min(len(toks), pos + MAX_GRAM), pos, -1):
            if toks[pos:end] in lexicon and walk(end):
                return True
        if toks[pos] in CONNECTORS:
            return walk(pos + 1)
        return False
    return walk(0)


def build(path, min_support=2, entropy_gate=tg.ENTROPY_GATE, join_gate=tg.JOIN_GATE,
          gates=False, key_filter='on', keys=None):
    rows = load_rows(path, key_filter, keys)
    names = name_index(rows)
    supports, left, right = collect(names)
    surfaces = surfaces_of(names)
    total_tokens = sum(len(toks) for toks in names.values())
    stats = measures(supports, left, right, total_tokens)
    whole = set(names.values())
    keys_of = defaultdict(list)
    for key, en in rows:
        toks = names.get(en)
        if toks:
            keys_of[toks].append(key)

    entries = []
    lexicon = {}
    dropped = {'support': 0, 'entropy': 0, 'join': 0, 'composable': 0}
    for gram in sorted(supports, key=lambda g: (len(g), g)):
        count, entropy, joins = stats[gram]
        if count < min_support and not (len(gram) == 1 and gram in whole):
            dropped['support'] += 1
            continue
        if gates:
            if entropy < entropy_gate:
                dropped['entropy'] += 1
                continue
            if joins is not None and joins < join_gate:
                dropped['join'] += 1
                continue
        if composable(gram, lexicon):
            dropped['composable'] += 1
            continue
        prod = len(left[gram]) + len(right[gram])
        entry = {'en': surfaces.get(gram, ' '.join(gram)), 'gram': gram,
                 'support': count, 'prod': prod, 'entropy': round(entropy, 3),
                 'join': round(joins, 3) if joins is not None else None,
                 'score': round(count * (1.0 + 0.1 * min(prod, 10)), 3),
                 'sources': sorted(keys_of.get(gram, ()))[:5]}
        entries.append(entry)
        lexicon[gram] = entry
    entries.sort(key=lambda e: (-e['support'], -len(e['gram']), e['en']))
    return {'entries': entries, 'lexicon': lexicon, 'names': names, 'supports': supports,
            'stats': stats, 'dropped': dropped, 'total_tokens': total_tokens}


def pool_entries(result, min_support=2):
    whole = set(result['names'].values())
    out = []
    for gram, names in result['supports'].items():
        count, entropy, joins = result['stats'][gram]
        if count < min_support and not (len(gram) == 1 and gram in whole):
            continue
        out.append({'en': ' '.join(gram), 'gram': gram, 'support': count,
                    'entropy': round(entropy, 3),
                    'join': round(joins, 3) if joins is not None else None})
    return out


def build_adjacency(names, nodes, min_cooc, min_dice):
    cooc = Counter()
    for toks in names.values():
        grams = sorted({gram for _, _, gram in gram_spans(toks) if gram in nodes})
        for i in range(len(grams)):
            for j in range(i + 1, len(grams)):
                cooc[(grams[i], grams[j])] += 1
    adj = defaultdict(list)
    kept = 0
    for (a, b), weight in cooc.items():
        if weight < min_cooc:
            continue
        dice = 2.0 * weight / (nodes[a]['support'] + nodes[b]['support'])
        if dice < min_dice:
            continue
        adj[a].append((b, dice))
        adj[b].append((a, dice))
        kept += 1
    return adj, len(cooc), kept


def label_propagation(adj, nodes, rounds):
    labels = {gram: gram for gram in nodes}
    for _ in range(rounds):
        changed = 0
        for gram in sorted(nodes):
            votes = Counter()
            for neighbor, weight in adj[gram]:
                votes[labels[neighbor]] += weight
            if not votes:
                continue
            best_weight = max(votes.values())
            best = min(label for label, weight in votes.items() if weight == best_weight)
            if best != labels[gram]:
                labels[gram] = best
                changed += 1
        if not changed:
            break
    groups = defaultdict(list)
    for gram, label in labels.items():
        groups[label].append(gram)
    return list(groups.values())


def connected_components(adj, nodes):
    seen = set()
    groups = []
    for start in sorted(nodes):
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            gram = stack.pop()
            group.append(gram)
            for neighbor, _ in adj[gram]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        groups.append(group)
    return groups


def family_rows(groups, nodes):
    rows = []
    for members in groups:
        ranked = sorted(members, key=lambda g: (-nodes[g]['support'], g))
        rows.append({'size': len(members),
                     'top': [{'en': ' '.join(g), 'support': nodes[g]['support']}
                             for g in ranked[:5]],
                     'members': [{'en': ' '.join(g), 'support': nodes[g]['support']}
                                 for g in ranked]})
    rows.sort(key=lambda r: (-r['size'], -r['top'][0]['support'], r['members'][0]['en']))
    return rows


def families(result, scope, min_support, min_cooc, min_dice, method, rounds):
    nodes = {e['gram']: e for e in (pool_entries(result, min_support) if scope == 'pool'
                                    else result['entries'])}
    adj, pairs, kept = build_adjacency(result['names'], nodes, min_cooc, min_dice)
    groups = (label_propagation(adj, list(nodes), rounds) if method == 'lpa'
              else connected_components(adj, list(nodes)))
    rows = family_rows(groups, nodes)
    summary = {'scope': scope, 'method': method, 'nodes': len(nodes), 'pairs': pairs,
               'edges': kept, 'linked': sum(1 for g in nodes if adj[g]),
               'groups': len(rows), 'singletons': sum(1 for r in rows if r['size'] == 1),
               'min_cooc': min_cooc, 'min_dice': min_dice}
    return rows, summary


def print_families(rows, limit, show, stream):
    for rank, row in enumerate(rows[:limit], 1):
        top = ', '.join('%s(%d)' % (m['en'], m['support']) for m in row['top'])
        listed = ', '.join(m['en'] for m in row['members'][:show])
        tail = ' …（共 %d 个）' % row['size'] if row['size'] > show else ''
        print('#%d  %d 个成员  support 最高: %s' % (rank, row['size'], top), file=stream)
        print('    %s%s' % (listed, tail), file=stream)


def tokens_of(en):
    return tuple(tg.tokens_lc(en))


def reachable_gold(gold, names):
    seqs = list(names.values())
    out = []
    for en in gold:
        toks = tokens_of(en)
        if not toks:
            continue
        for seq in seqs:
            if len(toks) <= len(seq) and any(
                    seq[i:i + len(toks)] == toks for i in range(len(seq) - len(toks) + 1)):
                out.append(en)
                break
    return out


def metrics(entries, gold, names):
    lexicon = {e['gram']: e for e in entries}
    reach = reachable_gold(gold, names)
    gold_set = {tokens_of(en) for en in gold}
    hits = [e for e in entries if e['gram'] in gold_set]
    direct = [en for en in reach if tokens_of(en) in lexicon]
    covered = [en for en in reach if tokens_of(en) in lexicon or composable(tokens_of(en), lexicon)]
    return {'entries': len(entries), 'gold': len(gold), 'reachable': len(reach),
            'direct': len(direct), 'direct_recall': round(len(direct) / len(reach), 4) if reach else None,
            'covered': len(covered), 'coverage': round(len(covered) / len(reach), 4) if reach else None,
            'gold_hits': len(hits), 'fp': len(entries) - len(hits),
            'fp_rate': round((len(entries) - len(hits)) / len(entries), 4) if entries else None}


def write_tsv(stream, entries):
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['en', 'tokens', 'support', 'prod', 'entropy', 'join', 'score', 'sources'])
    for e in entries:
        writer.writerow([e['en'], ' '.join(e['gram']), e['support'], e.get('prod', ''),
                         e['entropy'], e['join'] if e['join'] is not None else '',
                         e.get('score', ''), ';'.join(e['sources'])])


def extract(args):
    result = build(args.input, args.min_support, args.entropy_gate, args.join_gate,
                   gates=args.gates, key_filter=args.key_filter, keys=args.keys)
    entries = result['entries'][:args.limit] if args.limit else result['entries']
    summary = {'names': len(result['names']), 'pool': len(pool_entries(result, args.min_support)),
               'entries': len(entries), 'dropped': result['dropped']}
    rows = None
    if args.family:
        rows, fam = families(result, args.family_scope, args.min_support, args.min_cooc,
                             args.min_dice, args.method, args.rounds)
        summary['families'] = fam
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        stream = open(args.out, 'w', encoding='utf-8', newline='')
    else:
        sys.stdout.reconfigure(newline='')
        stream = sys.stdout
    try:
        if rows is not None:
            if args.json:
                stream.write(json.dumps({'summary': summary, 'families': rows[:args.top]},
                                        ensure_ascii=False, indent=2) + '\n')
            else:
                print_families(rows, args.top, args.show, stream)
        elif args.json:
            stream.write(json.dumps({'summary': summary, 'entries': entries},
                                    ensure_ascii=False, indent=2) + '\n')
        else:
            write_tsv(stream, entries)
    finally:
        if args.out:
            stream.close()
    summary['out'] = str(args.out) if args.out else 'stdout'
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0


def bench(args):
    result = build(args.input, args.min_support, args.entropy_gate, args.join_gate, gates=True,
                   key_filter=args.key_filter, keys=args.keys)
    atomic = build(args.input, args.min_support, args.entropy_gate, args.join_gate, gates=False,
                   key_filter=args.key_filter, keys=args.keys)
    gold = [tg.clean_en(en) for en, zh in tg.load_gold(args.gold)]
    names = result['names']
    report = {
        'names': len(names),
        'gold': len(gold),
        'variants': {
            'pool': metrics(pool_entries(result, args.min_support), gold, names),
            'atomic': metrics(atomic['entries'], gold, names),
            'gated': metrics(result['entries'], gold, names),
        },
        'dropped': result['dropped'],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v5_single.py')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('extract', 'bench'):
        p = sub.add_parser(command)
        p.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
        p.add_argument('--min-support', type=int, default=2)
        p.add_argument('--entropy-gate', type=float, default=tg.ENTROPY_GATE)
        p.add_argument('--join-gate', type=float, default=tg.JOIN_GATE)
        p.add_argument('--key-filter', choices=('on', 'off'), default='on',
                       help='on 走原版 key 白名单；模组 key 用 off')
        p.add_argument('--keys', help='正则；给了就代替原版白名单')
        if command == 'extract':
            p.add_argument('--out', type=Path)
            p.add_argument('--limit', type=int, default=0)
            p.add_argument('--gates', action='store_true', help='开熵/搭配硬门（默认关）')
            p.add_argument('--json', action='store_true')
            p.add_argument('--family', action='store_true')
            p.add_argument('--family-scope', choices=('pool', 'entries'), default='pool')
            p.add_argument('--min-cooc', type=int, default=2)
            p.add_argument('--min-dice', type=float, default=0.12)
            p.add_argument('--method', choices=('lpa', 'components'), default='lpa')
            p.add_argument('--rounds', type=int, default=30)
            p.add_argument('--top', type=int, default=15)
            p.add_argument('--show', type=int, default=30)
        else:
            p.add_argument('--gold', action='append', default=[])
    args = parser.parse_args(argv)
    if not getattr(args, 'gold', None):
        args.gold = [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]
    return extract(args) if args.command == 'extract' else bench(args)


if __name__ == '__main__':
    raise SystemExit(main())
