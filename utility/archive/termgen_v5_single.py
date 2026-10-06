#!/usr/bin/env python3
"""termgen-v5-single —— 单语术语候选：统计定候选，组合纪律定原子性。

没有中文时现行 termgen 一条都发不出来：条目要由中文变体证明、由中文切分核验。
本工具把同一套纪律换成单语版：

    支持度过滤 → 熵/搭配门控 → 长度升序，能被更短条目拼出来的就不单列

产出是「有原子性、没有译文证明」的英文候选，供人工或 LLM 定译名。
bench 给出 池子 / 原子化 / 加门控 三档的 规模-召回-假阳性，用来量这一步单语化掉多少。

用法：
    python utility/archive/termgen_v5_single.py extract --input Vanilla/latest.tsv --out en-terms.tsv
    python utility/archive/termgen_v5_single.py bench --input Vanilla/latest.tsv --gold Vanilla/terms/terms-v1.tsv
"""
import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen as tg

MAX_GRAM = tg.MAX_GRAM
CONNECTORS = tg.CONNECTORS
ROOT = Path(__file__).resolve().parent.parent.parent


def load_rows(path):
    wl, bl = tg.load_key_filter()
    rows = []
    for key, en, zh in tg.load_input_rows(str(path)):
        en = tg.clean_en(en)
        if en and tg.is_product_key(key, wl, bl):
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
          gates=True):
    rows = load_rows(path)
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
                   gates=not args.no_gates)
    entries = result['entries'][:args.limit] if args.limit else result['entries']
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, 'w', encoding='utf-8', newline='') as stream:
            write_tsv(stream, entries)
    else:
        sys.stdout.reconfigure(newline='')
        write_tsv(sys.stdout, entries)
    print(json.dumps({'names': len(result['names']),
                      'pool': len(pool_entries(result, args.min_support)),
                      'entries': len(entries), 'dropped': result['dropped'],
                      'out': str(args.out) if args.out else 'stdout'}, ensure_ascii=False),
          file=sys.stderr)
    return 0


def bench(args):
    result = build(args.input, args.min_support, args.entropy_gate, args.join_gate, gates=True)
    atomic = build(args.input, args.min_support, args.entropy_gate, args.join_gate, gates=False)
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
        if command == 'extract':
            p.add_argument('--out', type=Path)
            p.add_argument('--limit', type=int, default=0)
            p.add_argument('--no-gates', action='store_true')
        else:
            p.add_argument('--gold', action='append', default=[])
    args = parser.parse_args(argv)
    if not getattr(args, 'gold', None):
        args.gold = [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]
    return extract(args) if args.command == 'extract' else bench(args)


if __name__ == '__main__':
    raise SystemExit(main())
