import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import io_utils as io

ENTROPY_GATE = 2.0
JOIN_GATE = 3.0


def load_rows(path, key_filter='on', keys=None, exclude_keys=None, filter_file=None, en_col=None):
    raw = io.load_input_rows(path, en_col=en_col)
    filtered = io.filter_rows(raw, key_filter=key_filter, keys=keys, exclude_keys=exclude_keys, filter_file=filter_file)
    rows = []

    for key, en, _ in filtered:
        cleaned = io.clean_en(en)
        if cleaned:
            rows.append((key, cleaned))

    return rows


def name_index(rows):
    names = {}
    for _, en in rows:
        toks = tuple(io.tokens_lc(en))
        if toks:
            names.setdefault(en, toks)

    return names


def gram_spans(toks):
    for start in range(len(toks)):
        for end in range(start + 1, min(len(toks), start + io.MAX_GRAM) + 1):
            gram = toks[start:end]
            if gram[0] in io.STOP or gram[-1] in io.STOP:
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
        raw = io.raw_tokens(en)
        for start, end, gram in gram_spans(toks):
            surfaces.setdefault(gram, ' '.join(raw[start:end]))

    return surfaces


def measures(supports, left, right, total_tokens):
    stats = {}
    for gram, names in supports.items():
        count = len(names)
        entropy = max(io.entropy_bits(left[gram]), io.entropy_bits(right[gram]))
        joins = None
        if len(gram) >= 2:
            joins = min(
                (count - len(supports.get(gram[:i], ())) * len(supports.get(gram[i:], ())) / total_tokens) / math.sqrt(count)
                for i in range(1, len(gram))
            )
        stats[gram] = (count, entropy, joins)

    return stats


def composable(toks, lexicon):
    def walk(pos):
        if pos == len(toks):
            return True
        for end in range(min(len(toks), pos + io.MAX_GRAM), pos, -1):
            if toks[pos:end] in lexicon and walk(end):
                return True
        if toks[pos] in io.CONNECTORS:
            return walk(pos + 1)
        return False

    return walk(0)


def build(path, min_support=2, entropy_gate=ENTROPY_GATE, join_gate=JOIN_GATE,
          gates=False, key_filter='on', keys=None, exclude_keys=None, filter_file=None,
          en_col=None, focus_keys=None, known=None):
    rows = load_rows(path, key_filter=key_filter, keys=keys, exclude_keys=exclude_keys,
                     filter_file=filter_file, en_col=en_col)
    names = name_index(rows)
    supports, left, right = collect(names)
    surfaces = surfaces_of(names)
    total_tokens = sum(len(toks) for toks in names.values()) or 1
    stats = measures(supports, left, right, total_tokens)
    whole = set(names.values())
    focus_set = set(focus_keys) if focus_keys is not None else None
    keys_of = defaultdict(list)

    for key, en in rows:
        toks = names.get(en)
        if toks:
            keys_of[toks].append(key)

    entries = []
    lexicon = {}
    dropped = {'support': 0, 'entropy': 0, 'join': 0, 'composable': 0, 'focus': 0, 'known': 0}

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

        surface = surfaces.get(gram, ' '.join(gram))
        src_keys = sorted(keys_of.get(gram, ()))
        if focus_set is not None:
            hit_keys = [k for k in src_keys if k in focus_set]
            if not hit_keys:
                dropped['focus'] += 1
                lexicon[gram] = {'en': surface, 'gram': gram}
                continue
            src_keys = hit_keys

        if known and io.is_known_term(surface, known):
            dropped['known'] += 1
            lexicon[gram] = {'en': surface, 'gram': gram}
            continue

        prod = len(left[gram]) + len(right[gram])
        entry = {
            'en': surface,
            'gram': gram,
            'support': count,
            'prod': prod,
            'entropy': round(entropy, 3),
            'join': round(joins, 3) if joins is not None else None,
            'score': round(count * (1.0 + 0.1 * min(prod, 10)), 3),
            'sources': src_keys[:5],
        }
        entries.append(entry)
        lexicon[gram] = entry

    entries.sort(key=lambda e: (-e['support'], -len(e['gram']), e['en']))

    return {
        'entries': entries,
        'lexicon': lexicon,
        'names': names,
        'supports': supports,
        'stats': stats,
        'dropped': dropped,
        'total_tokens': total_tokens,
    }


def pool_entries(result, min_support=2):
    whole = set(result['names'].values())
    out = []

    for gram, _ in result['supports'].items():
        count, entropy, joins = result['stats'][gram]
        if count < min_support and not (len(gram) == 1 and gram in whole):
            continue
        out.append({
            'en': ' '.join(gram),
            'gram': gram,
            'support': count,
            'entropy': round(entropy, 3),
            'join': round(joins, 3) if joins is not None else None,
        })

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
        rows.append({
            'size': len(members),
            'top': [{'en': ' '.join(g), 'support': nodes[g]['support']} for g in ranked[:5]],
            'members': [{'en': ' '.join(g), 'support': nodes[g]['support']} for g in ranked],
        })
    rows.sort(key=lambda r: (-r['size'], -r['top'][0]['support'], r['members'][0]['en']))

    return rows


def families(result, scope, min_support, min_cooc, min_dice, method, rounds):
    nodes = {e['gram']: e for e in (pool_entries(result, min_support) if scope == 'pool' else result['entries'])}
    adj, pairs, kept = build_adjacency(result['names'], nodes, min_cooc, min_dice)
    groups = label_propagation(adj, list(nodes), rounds) if method == 'lpa' else connected_components(adj, list(nodes))
    rows = family_rows(groups, nodes)
    summary = {
        'scope': scope,
        'method': method,
        'nodes': len(nodes),
        'pairs': pairs,
        'edges': kept,
        'linked': sum(1 for g in nodes if adj[g]),
        'groups': len(rows),
        'singletons': sum(1 for r in rows if r['size'] == 1),
        'min_cooc': min_cooc,
        'min_dice': min_dice,
    }

    return rows, summary


def print_families(rows, limit, show, stream):
    for rank, row in enumerate(rows[:limit], 1):
        top = ', '.join(f"{m['en']}({m['support']})" for m in row['top'])
        listed = ', '.join(m['en'] for m in row['members'][:show])
        tail = f" …（共 {row['size']} 个）" if row['size'] > show else ''
        print(f'#{rank}  {row["size"]} 个成员  support 最高: {top}', file=stream)
        print(f'    {listed}{tail}', file=stream)


def write_tsv(stream, entries):
    io.write_tsv(
        stream,
        ['en', 'tokens', 'support', 'prod', 'entropy', 'join', 'score', 'sources'],
        [[e['en'], ' '.join(e['gram']), e['support'], e.get('prod', ''), e['entropy'],
          e['join'] if e['join'] is not None else '', e.get('score', ''), ';'.join(e['sources'])] for e in entries],
    )


def extract(args):
    focus = io.load_focus_keys(args.focus) if getattr(args, 'focus', None) else None
    known, _ = io.known_pairs(getattr(args, 'known', None))
    result = build(
        args.input,
        min_support=args.min_support,
        entropy_gate=args.entropy_gate,
        join_gate=args.join_gate,
        gates=args.gates,
        key_filter=args.key_filter,
        keys=args.keys,
        exclude_keys=getattr(args, 'exclude_keys', None),
        filter_file=getattr(args, 'filter_file', None),
        en_col=getattr(args, 'en_col', None),
        focus_keys=focus,
        known=known or None,
    )
    entries = result['entries'][:args.limit] if args.limit else result['entries']
    summary = {'names': len(result['names']), 'pool': len(pool_entries(result, args.min_support)),
               'entries': len(entries), 'dropped': result['dropped']}
    rows = None

    if args.family:
        rows, fam = families(result, args.family_scope, args.min_support, args.min_cooc,
                             args.min_dice, args.method, args.rounds)
        summary['families'] = fam

    if args.out:
        io.ensure_parent(args.out)
        stream = open(args.out, 'w', encoding='utf-8', newline='')
    else:
        sys.stdout.reconfigure(newline='')
        stream = sys.stdout

    try:
        if rows is not None:
            if args.json:
                stream.write(json.dumps({'summary': summary, 'families': rows[:args.top]}, ensure_ascii=False, indent=2) + '\n')
            else:
                print_families(rows, args.top, args.show, stream)
        elif args.json:
            stream.write(json.dumps({'summary': summary, 'entries': entries}, ensure_ascii=False, indent=2) + '\n')
        else:
            write_tsv(stream, entries)
    finally:
        if args.out:
            stream.close()

    summary['out'] = str(args.out) if args.out else 'stdout'
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    return 0


def add_single_args(p):
    p.add_argument('--input', type=Path, default=io.ROOT / 'Vanilla/latest.tsv')
    p.add_argument('--en-col', help='英文列名或文件名')
    p.add_argument('--min-support', type=int, default=2)
    p.add_argument('--entropy-gate', type=float, default=ENTROPY_GATE)
    p.add_argument('--join-gate', type=float, default=JOIN_GATE)
    p.add_argument('--key-filter', choices=('on', 'off', 'auto'), default='on')
    p.add_argument('--keys', help='白名单 key 正则')
    p.add_argument('--exclude-keys', help='黑名单 key 正则')
    p.add_argument('--filter-file', type=Path, help='自定义 key 规则 JSON')
    p.add_argument('--focus', type=Path, help='diff JSON 或 key 清单')
    p.add_argument('--known', nargs='*', default=[], help='已有术语 TSV（跳过已收录或可推导词）')
    p.add_argument('--out', type=Path)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--gates', action='store_true', help='开启熵/搭配硬门')
    p.add_argument('--json', action='store_true')
    p.add_argument('--family', action='store_true')
    p.add_argument('--family-scope', choices=('pool', 'entries'), default='pool')
    p.add_argument('--min-cooc', type=int, default=2)
    p.add_argument('--min-dice', type=float, default=0.12)
    p.add_argument('--method', choices=('lpa', 'components'), default='lpa')
    p.add_argument('--rounds', type=int, default=30)
    p.add_argument('--top', type=int, default=15)
    p.add_argument('--show', type=int, default=30)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='final.py single')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('extract')
    add_single_args(p)
    args = parser.parse_args(argv)

    return extract(args)


if __name__ == '__main__':
    raise SystemExit(main())
