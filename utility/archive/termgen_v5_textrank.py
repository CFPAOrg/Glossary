#!/usr/bin/env python3
"""termgen-v5-textrank —— 同一候选池换 TextRank 排序：gram 作节点，同名称共现连边，PageRank 定序。

候选池固定为 v5 的支持度过滤结果（v5.pool_entries，1373 条），不增删，只重排。
节点分 = PageRank(共现图, damping=0.85, 20 轮, 纯字典实现)；最终分 = node_weight × 归一化节点分
+ (1 - node_weight) × 归一化 log1p(support)，默认 node_weight=0.25（实测纯节点分不如 support 基线）。
并排输出 v5 support 基线的 direct_recall / coverage / fp_rate，N ∈ {187, 681, 1373}。

用法：
    python utility/archive/termgen_v5_textrank.py --input Vanilla/latest.tsv
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen as tg
sys.path.insert(0, str(Path(__file__).resolve().parent))
import termgen_v5_single as v5

ROOT = Path(__file__).resolve().parent.parent.parent
NS = (187, 681, 1373)
DAMPING = 0.85
ITERATIONS = 20


# 每个名称里出现的池内 gram 及跨度，按 (start, end) 升序
def name_occurrences(names, pool):
    out = []
    for toks in names.values():
        occ = [(start, end, toks[start:end])
               for start in range(len(toks))
               for end in range(start + 1, min(len(toks), start + v5.MAX_GRAM) + 1)
               if toks[start:end] in pool]
        if occ:
            out.append(occ)
    return out


# 无向共现图：边权 = 同时出现的名称数；window 给定时要求跨度间隙 ≤ window-1
def cooccurrence(occs, window=None):
    edges = defaultdict(float)
    for occ in occs:
        for i, (_, e1, g1) in enumerate(occ):
            for s2, _, g2 in occ[i + 1:]:
                if g1 == g2 or (window and s2 - e1 > window - 1):
                    continue
                edges[(g1, g2) if g1 < g2 else (g2, g1)] += 1.0
    return edges


def pagerank(nodes, edges, damping=DAMPING, iterations=ITERATIONS):
    size = len(nodes)
    out_weight = defaultdict(float)
    for (a, b), weight in edges.items():
        out_weight[a] += weight
        out_weight[b] += weight
    incoming = {g: [] for g in nodes}
    for (a, b), weight in edges.items():
        incoming[a].append((b, weight / out_weight[b]))
        incoming[b].append((a, weight / out_weight[a]))
    score = {g: 1.0 / size for g in nodes}
    for _ in range(iterations):
        dangling = sum(s for g, s in score.items() if out_weight[g] == 0.0) / size
        score = {g: (1.0 - damping) / size + damping * (dangling + sum(score[n] * w for n, w in incoming[g]))
                 for g in nodes}
    return score


def normalize(scores):
    low, high = min(scores.values()), max(scores.values())
    if high == low:
        return {g: 0.0 for g in scores}
    return {g: (v - low) / (high - low) for g, v in scores.items()}


def ranked(pool, names, window=None, node_weight=0.25):
    pool_set = {e['gram'] for e in pool}
    edges = cooccurrence(name_occurrences(names, pool_set), window)
    node = normalize(pagerank(pool_set, edges))
    support = normalize({e['gram']: math.log1p(e['support']) for e in pool})
    out = []
    for entry in pool:
        gram = entry['gram']
        score = node_weight * node[gram] + (1.0 - node_weight) * support[gram]
        out.append(dict(entry, score=round(score, 6)))
    out.sort(key=lambda e: (-e['score'], -e['support'], e['en']))
    return out


def baseline(pool):
    return sorted((dict(e) for e in pool), key=lambda e: (-e['support'], -len(e['gram']), e['en']))


def metric_row(entries, n, gold, names):
    m = v5.metrics(entries[:n], gold, names)
    return {'n': n, 'entries': m['entries'], 'direct_recall': m['direct_recall'],
            'coverage': m['coverage'], 'fp_rate': m['fp_rate']}


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v5_textrank.py')
    parser.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    parser.add_argument('--gold', action='append', default=[])
    parser.add_argument('--window', type=int, default=0, help='0 = 整名共现；3 = 窗口 3')
    parser.add_argument('--node-weight', type=float, default=0.25,
                        help='节点分权重；1.0 = 纯 TextRank，0.0 = 纯 support')
    args = parser.parse_args(argv)
    if not args.gold:
        args.gold = [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]

    result = v5.build(args.input, gates=False)
    pool = v5.pool_entries(result)
    names = result['names']
    gold = [tg.clean_en(en) for en, zh in tg.load_gold(args.gold)]
    mine = ranked(pool, names, args.window or None, args.node_weight)
    base = baseline(pool)
    report = {
        'algorithm': 'textrank cooccur=%s node_weight=%s blend=node+log1p(support) damping=%s iters=%s' % (
            'window%d' % args.window if args.window else 'whole-name',
            args.node_weight, DAMPING, ITERATIONS),
        'rows': [metric_row(mine, n, gold, names) for n in NS],
        'baseline': [metric_row(base, n, gold, names) for n in NS],
        'top20': [{'en': e['en'], 'score': e['score']} for e in mine[:20]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
