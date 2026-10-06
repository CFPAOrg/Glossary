#!/usr/bin/env python3
"""termgen-v5-ntc —— 在固定候选池上重排：unithood × termhood 合成一个分数。

termhood = support（域内相对频率）；unithood = 邻居熵与搭配强度 join（v5 的 stats）。
两者各自 min-max / rank 归一化后按乘法或加权和合成，对整个池子排序，
与 v5 的 support 基线并排报 direct_recall / coverage / fp_rate。
单词的 unithood 记 1.0：单个词元本身就是单位，unithood 对它是空问题。

用法：
    python utility/archive/termgen_v5_ntc.py --input Vanilla/latest.tsv
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# utility/ 必须最后插入：archive/ 里躺着同名的旧 termgen.py，别让它盖住
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen as tg
import termgen_v5_single as v5

ROOT = Path(__file__).resolve().parent.parent.parent
NS = (187, 681, 1373)
PRIMARY = 'ntc_sum_minmax_50_50'
CONTROL = 'ctrl_uni_first'


def minmax(values):
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    return [(v - lo) / span for v in values]


def rank_pct(values, mask=None):
    idx = [i for i in range(len(values)) if mask is None or mask[i]]
    order = sorted(idx, key=lambda i: values[i])
    out = [0.0] * len(values)
    scale = max(1, len(order) - 1)
    for pos, i in enumerate(order):
        out[i] = pos / scale
    return out


def unithood(pool, entropy_norm, join_norm):
    out = []
    for i, e in enumerate(pool):
        if e['join'] is None:
            out.append(1.0)
        else:
            out.append(0.5 * (entropy_norm[i] + join_norm[i]))
    return out


def variants(pool):
    support = [e['support'] for e in pool]
    entropy = [e['entropy'] for e in pool]
    join = [e['join'] if e['join'] is not None else 0.0 for e in pool]
    multi = [e['join'] is not None for e in pool]
    sup_mm, sup_rk = minmax(support), rank_pct(support)
    ent_mm, ent_rk = minmax(entropy), rank_pct(entropy)
    join_mm, join_rk = minmax(join), rank_pct(join, multi)
    uh_mm = unithood(pool, ent_mm, join_mm)
    uh_rk = unithood(pool, ent_rk, join_rk)
    n = len(pool)
    return [
        ('ntc_mul_minmax', [sup_mm[i] * uh_mm[i] for i in range(n)]),
        ('ntc_mul_rank', [sup_rk[i] * uh_rk[i] for i in range(n)]),
        ('ntc_sum_minmax_50_50', [0.5 * sup_mm[i] + 0.5 * uh_mm[i] for i in range(n)]),
        ('ntc_sum_rank_50_50', [0.5 * sup_rk[i] + 0.5 * uh_rk[i] for i in range(n)]),
        (CONTROL, None),
    ]


def ranked(pool, scores, uni_first=False):
    if uni_first:
        return sorted(pool, key=lambda e: (len(e['gram']) > 1, -e['support'],
                                           -len(e['gram']), e['en']))
    order = sorted(range(len(pool)), key=lambda i: (-scores[i], -len(pool[i]['gram']),
                                                    pool[i]['en']))
    return [pool[i] for i in order]


def scored_top(pool, scores, limit):
    order = sorted(range(len(pool)), key=lambda i: (-scores[i], -len(pool[i]['gram']),
                                                    pool[i]['en']))
    return [{'en': pool[i]['en'], 'score': round(scores[i], 6),
             'support': pool[i]['support'], 'entropy': pool[i]['entropy'],
             'join': pool[i]['join']} for i in order[:limit]]


def evaluate(pool, names, gold):
    rows = []
    for name, scores in variants(pool):
        top = ranked(pool, scores, uni_first=(name == CONTROL))
        for N in NS:
            rows.append({'variant': name, 'n': N, **v5.metrics(top[:N], gold, names)})
    base = sorted(pool, key=lambda e: (-e['support'], -len(e['gram']), e['en']))
    baseline = [{'variant': 'baseline_support', 'n': N, **v5.metrics(base[:N], gold, names)}
                for N in NS]
    return rows, baseline


def print_table(rows, baseline, names, stream):
    lookup = {(r['variant'], r['n']): r for r in rows + baseline}
    print(f"{'N':>5}  {'variant':<24}  {'direct_recall':>13}  {'coverage':>8}  "
          f"{'fp_rate':>7}  {'gold_hits/fp':>12}", file=stream)
    for N in NS:
        for variant in ['baseline_support'] + names:
            r = lookup[(variant, N)]
            print(f"{N:>5}  {variant:<24}  {r['direct_recall']:>13}  {r['coverage']:>8}  "
                  f"{r['fp_rate']:>7}  {str(r['gold_hits']) + '/' + str(r['fp']):>12}",
                  file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v5_ntc.py')
    parser.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    parser.add_argument('--gold', type=Path, default=ROOT / 'Vanilla/terms/terms-v1.tsv')
    parser.add_argument('--top', type=int, default=20)
    args = parser.parse_args(argv)

    result = v5.build(args.input, gates=False)
    pool = v5.pool_entries(result)
    names = result['names']
    gold = [tg.clean_en(en) for en, zh in tg.load_gold([args.gold])]

    variants_cache = variants(pool)
    rows, baseline = evaluate(pool, names, gold)
    primary_scores = dict(variants_cache)[PRIMARY]
    report = {
        'algorithm': PRIMARY,
        'input': str(args.input),
        'pool': len(pool),
        'gold': len(gold),
        'rows': rows,
        'baseline': baseline,
        'top20': scored_top(pool, primary_scores, args.top),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print_table(rows, baseline, [name for name, _ in variants_cache], sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
