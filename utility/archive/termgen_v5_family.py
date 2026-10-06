#!/usr/bin/env python3
"""termgen-v5-family —— 把固定候选池按共现图分成可读家族（木种/颜色/矿物这种）。

节点 = 池子里的 gram；两个 gram 出现在同一个名字里就连边，边权 = Dice(共现)，
即 2*共现数/(两 gram 的 support 之和)。滤掉共现 < min_cooc 与 Dice < min_dice 的边，
再跑带权标签传播（纯标准库；固定节点顺序、平票取最小标签，结果确定）。
输出按规模排序的前 15 个家族：成员数、成员列表、support 最高的几个。

用法：
    python utility/archive/termgen_v5_family.py --input Vanilla/latest.tsv
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# utility/ 必须最后插入：archive/ 里躺着同名的旧 termgen.py，别让它盖住
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen_v5_single as v5

ROOT = Path(__file__).resolve().parent.parent.parent


def build_adjacency(names, pool_grams, min_cooc, min_dice):
    cooc = Counter()
    for toks in names.values():
        grams = sorted({gram for _, _, gram in v5.gram_spans(toks) if gram in pool_grams})
        for i in range(len(grams)):
            for j in range(i + 1, len(grams)):
                cooc[(grams[i], grams[j])] += 1
    adj = defaultdict(list)
    kept = 0
    for (a, b), weight in cooc.items():
        if weight < min_cooc:
            continue
        dice = 2.0 * weight / (pool_grams[a]['support'] + pool_grams[b]['support'])
        if dice < min_dice:
            continue
        adj[a].append((b, dice))
        adj[b].append((a, dice))
        kept += 1
    return adj, len(cooc), kept


def label_propagation(adj, nodes, rounds):
    labels = {gram: gram for gram in nodes}
    order = sorted(nodes)
    for _ in range(rounds):
        changed = 0
        for gram in order:
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
        stack = [start]
        seen.add(start)
        group = []
        while stack:
            gram = stack.pop()
            group.append(gram)
            for neighbor, _ in adj[gram]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        groups.append(group)
    return groups


def family_rows(groups, pool_grams):
    rows = []
    for members in groups:
        ranked = sorted(members, key=lambda g: (-pool_grams[g]['support'], g))
        rows.append({
            'size': len(members),
            'top': [{'en': ' '.join(g), 'support': pool_grams[g]['support']}
                    for g in ranked[:5]],
            'members': [{'en': ' '.join(g), 'support': pool_grams[g]['support']}
                        for g in ranked],
        })
    rows.sort(key=lambda r: (-r['size'], -r['top'][0]['support'], r['members'][0]['en']))
    return rows


def print_families(rows, limit, show, stream):
    for rank, row in enumerate(rows[:limit], 1):
        top = ', '.join(f"{m['en']}({m['support']})" for m in row['top'])
        listed = ', '.join(m['en'] for m in row['members'][:show])
        tail = f' …（共 {row["size"]} 个）' if row['size'] > show else ''
        print(f'#{rank}  {row["size"]} 个成员  support 最高: {top}', file=stream)
        print(f'    {listed}{tail}', file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v5_family.py')
    parser.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    parser.add_argument('--min-cooc', type=int, default=2)
    parser.add_argument('--min-dice', type=float, default=0.12)
    parser.add_argument('--method', choices=('lpa', 'components'), default='lpa')
    parser.add_argument('--rounds', type=int, default=30)
    parser.add_argument('--top', type=int, default=15)
    parser.add_argument('--show', type=int, default=30)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)

    result = v5.build(args.input, gates=False)
    pool = v5.pool_entries(result)
    pool_grams = {e['gram']: e for e in pool}
    names = result['names']

    adj, pairs, kept = build_adjacency(names, pool_grams, args.min_cooc, args.min_dice)
    groups = (label_propagation(adj, list(pool_grams), args.rounds) if args.method == 'lpa'
              else connected_components(adj, list(pool_grams)))
    rows = family_rows(groups, pool_grams)
    linked = sum(1 for gram in pool_grams if adj[gram])
    summary = {'input': str(args.input), 'nodes': len(pool_grams), 'pairs': pairs,
               'edges': kept, 'linked_nodes': linked, 'groups': len(groups),
               'singletons': sum(1 for row in rows if row['size'] == 1),
               'method': args.method, 'min_cooc': args.min_cooc, 'min_dice': args.min_dice}

    if args.json:
        print(json.dumps({**summary, 'families': rows[:args.top]},
                         ensure_ascii=False, indent=2))
        return 0
    print(f"池子 {summary['nodes']} 个 gram，共现对 {pairs}，过阈值边 {kept}，"
          f"有边的 gram {linked}，组 {summary['groups']}（其中单点组 {summary['singletons']}）",
          file=sys.stderr)
    print_families(rows, args.top, args.show, sys.stdout)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
