"""termgen-v2 —— 术语候选抽取：枚举 → 平行对齐 → 排序 → 按预算截断。

候选只来自一件事：在名称串里反复出现的 n-gram。打分只用文献里的三条轴，
外加平行语料给的对齐证据：

  align      该 en 串在多少条译文里对应同一个 zh 片段（平行语料证据）
  weirdness  Ahmad 1994：域内相对频率 / 通用语料相对频率（wordfreq 提供分母）
  C-value    Frantzi & Ananiadou 2000：嵌套在更长候选里出现时扣掉嵌套频次
  PMI        相邻词是否咬合成一个单位
  freq       出现次数

没有 viterbi 切分、没有组合性删除、没有三级 tier、没有 why 调试串：
排完序按 --budget 截断，剩下的交给 LLM。

用法：
  python utility/termgen_v2.py extract --input Vanilla/latest.tsv --budget 800
  python utility/termgen_v2.py bench  --input Vanilla/latest.tsv --gold Vanilla/terms/terms-v1.tsv
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from termgen import (CJK_RE, LEAD_OK, STOP, clean_en, clean_zh, is_name_like,
                     is_product_key, load_gold, load_input_rows, load_key_filter,
                     norm_lemma, tokens_lc)

from wordfreq import zipf_frequency

MAXGRAM = 5
ZH_MAX = 8
ALIGN_CAP = 32
MIN_ALIGN = 0.5
DEFAULT_BUDGET = 800


# ---------------------------------------------------------------- 语料

def load_rows(input_path, background_path, exclude):
    wl, bl = load_key_filter()
    ex = re.compile(exclude) if exclude else None
    input_rows = [r for r in load_input_rows(input_path) if is_product_key(r[0], wl, bl)]
    bg_rows = load_input_rows(background_path) if background_path else []
    seen = set()
    rows = []
    for (key, en, zh) in input_rows + bg_rows:
        sig = (key, en, zh)
        if sig in seen:
            continue
        seen.add(sig)
        if key is not None and ex is not None and ex.search(key):
            continue
        en, zh = clean_en(en), clean_zh(zh)
        if not en:
            continue
        rows.append((key, en, zh))
    return input_rows, rows


class Corpus:
    """按 (en, zh) 去重的平行句对；en 串 → 它的所有译文 pid。"""

    def __init__(self, rows, input_rows):
        self.rows = rows
        self.pairs = []
        self.en_pids = defaultdict(list)
        self.zh_of = defaultdict(Counter)
        seen = set()
        for (_, en, zh) in rows:
            if not zh or (en, zh) in seen:
                continue
            seen.add((en, zh))
            pid = len(self.pairs)
            self.pairs.append((en, zh))
            self.en_pids[en].append(pid)
            self.zh_of[en][zh] += 1
        self.input_ens = {clean_en(e) for (_, e, _) in input_rows if clean_en(e)}


# ---------------------------------------------------------------- 枚举

def enumerate_grams(corpus):
    cnt = Counter()
    stand = Counter()
    names = defaultdict(set)
    gram_pids = defaultdict(set)
    tok_counts = Counter()
    bigram = Counter()
    left = defaultdict(Counter)
    right = defaultdict(Counter)
    for en, pids in corpus.en_pids.items():
        if not is_name_like(en):
            continue
        toks = tokens_lc(en)
        n = len(toks)
        for t in toks:
            tok_counts[(t,)] += 1
        for i in range(n - 1):
            bigram[(toks[i], toks[i + 1])] += 1
        for i in range(n):
            for j in range(i + 1, min(n, i + MAXGRAM) + 1):
                g = tuple(toks[i:j])
                if g[-1] in STOP:
                    continue
                if g[0] in STOP and g[0] not in LEAD_OK:
                    continue
                cnt[g] += 1
                names[g].add(en)
                if i == 0 and j == n:
                    stand[g] += 1
                if i > 0:
                    left[g][toks[i - 1]] += 1
                if j < n:
                    right[g][toks[j]] += 1
                gram_pids[g].update(pids)
    return {'cnt': cnt, 'stand': stand, 'names': names, 'pids': gram_pids,
            'tok': tok_counts, 'bigram': bigram, 'left': left, 'right': right,
            'total_tokens': max(1, sum(tok_counts.values()))}


# ---------------------------------------------------------------- 对齐

_SUBS = {}


def zh_subs(s):
    got = _SUBS.get(s)
    if got is None:
        out = []
        seen = set()
        for run in CJK_RE.findall(s):
            n = len(run)
            for i in range(n):
                for j in range(i + 1, min(n, i + ZH_MAX) + 1):
                    sub = run[i:j]
                    if sub not in seen:
                        seen.add(sub)
                        out.append(sub)
        got = tuple(out)
        _SUBS[s] = got
    return got


def build_subdf(corpus):
    df = Counter()
    for (_, zh) in corpus.pairs:
        for sub in set(zh_subs(zh)):
            df[sub] += 1
    return df


def align(corpus, subdf, pids):
    """在一组译文里找覆盖最好的 zh 片段。返回 (片段列表, cover, dice)。"""
    pids = sorted(pids)[:ALIGN_CAP]
    n = len(pids)
    if not n:
        return [], 0.0, 0.0
    hits = Counter()
    for pid in pids:
        for sub in set(zh_subs(corpus.pairs[pid][1])):
            hits[sub] += 1
    floor = max(2, math.ceil(MIN_ALIGN * n))
    scored = []
    for sub, c in hits.items():
        if c < floor or not CJK_RE.search(sub):
            continue
        scored.append((2.0 * c / (n + subdf.get(sub, c)), len(sub), sub, c))
    if not scored:
        return [], 0.0, 0.0
    scored.sort(key=lambda x: (-x[0], -x[1]))
    best = scored[0]
    picks = [best[2]]
    for d, ln, sub, c in scored[1:]:
        if len(picks) >= 2:
            break
        if sub in picks[0] or picks[0] in sub:
            continue
        picks.append(sub)
    return picks, best[3] / n, best[0]


# ---------------------------------------------------------------- 特征

def c_values(cnt):
    """Frantzi & Ananiadou 的 C-value：被更长候选包含时，扣掉那些长候选的平均频次。"""
    nested_n = Counter()
    nested_f = Counter()
    for g, f in cnt.items():
        n = len(g)
        for i in range(n):
            for j in range(i + 1, n + 1):
                if i == 0 and j == n:
                    continue
                h = g[i:j]
                if h in cnt:
                    nested_n[h] += 1
                    nested_f[h] += f
    out = {}
    for g, f in cnt.items():
        if nested_n[g]:
            out[g] = math.log2(len(g)) * max(0.0, f - nested_f[g] / nested_n[g])
        else:
            out[g] = math.log2(len(g)) * f
    return out


def local_mi(g, tok, bigram, total):
    """相邻二元组 PMI 的均值（与 termgen.py 同式，便于横向比）。"""
    if len(g) < 2:
        return 0.0
    vals = []
    for i in range(len(g) - 1):
        c1 = tok.get((g[i],), 0)
        c2 = tok.get((g[i + 1],), 0)
        c12 = bigram.get((g[i], g[i + 1]), 0)
        if c1 <= 0 or c2 <= 0 or c12 <= 0:
            continue
        vals.append(math.log2(c12 * total / (c1 * c2)))
    return sum(vals) / len(vals) if vals else 0.0


def weirdness(g, freq, total_names):
    """域内相对频率 / 通用语料相对频率。词之间按独立假设相乘。"""
    if not total_names:
        return 0.0
    gen = 1.0
    for w in g:
        gen *= 10.0 ** (zipf_frequency(w, 'en') - 9.0)
    if gen <= 0.0:
        return 0.0
    return math.log10((freq / total_names) / gen)


def build_records(corpus, stats, subdf):
    cnt = stats['cnt']
    tok = stats['tok']
    bigram = stats['bigram']
    total = stats['total_tokens']
    total_names = len({en for en in corpus.en_pids if is_name_like(en)})
    cv = c_values(cnt)
    whole = {tuple(tokens_lc(en)) for en in corpus.en_pids if is_name_like(en)}
    recs = []
    for g, f in cnt.items():
        if len(g) == 1 and len(g[0]) <= 1:
            continue
        if f < 2 and g not in whole:
            continue
        names = stats['names'][g]
        if corpus.input_ens and not (names & corpus.input_ens):
            continue
        pids = stats['pids'][g]
        zh, cover, dice = align(corpus, subdf, pids)
        heads = set(stats['left'][g]) | set(stats['right'][g])
        max_tok = max((tok.get((w,), 0) for w in g), default=0)
        recs.append({
            'g': g,
            'en': ' '.join(g),
            'zh': zh,
            'freq': f,
            'nzh': len({corpus.pairs[pid][1] for pid in pids}),
            'stand': stats['stand'].get(g, 0),
            'heads': len(heads),
            'cover': cover,
            'dice': dice,
            'cvalue': cv.get(g, 0.0),
            'weird': weirdness(g, f, total_names),
            'mi': local_mi(g, tok, bigram, total),
            'be': boundary_entropy(stats, g),
            'cmp': (f / max_tok) if max_tok else 0.0,
            'n': len(g),
        })
    return recs


def boundary_entropy(stats, g):
    """左右邻词分布的熵：越低说明这个词只在固定搭配里出现。"""
    hs = []
    for side in ('left', 'right'):
        d = stats[side].get(g)
        if not d:
            hs.append(0.0)
            continue
        n = sum(d.values())
        h = 0.0
        for c in d.values():
            p = c / n
            h -= p * math.log2(p)
        hs.append(h)
    return (hs[0] + hs[1]) / 2.0


# ---------------------------------------------------------------- 打分

# 候选按词数分三桶，桶序固定为 1 词 → 2 词 → 3+ 词，桶内按特征排序。
# 桶的切分和桶内特征都是 bench 实测出来的：三桶的 gold 占比是 0.504 / 0.204 / 0.027，
# 桶内最好的排序特征分别是 weird（域特异性）/ nzh+cmp+mi / cmp。
BUCKETS = ((1, 1, ('weird',)), (2, 2, ('nzh', 'cmp', 'mi')), (3, 99, ('cmp',)))


def _ranks(vals):
    """把一列特征压到 0..1 的名次，避免不同量纲的特征互相压制。"""
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    out = [0.0] * len(vals)
    for pos, i in enumerate(order):
        out[i] = pos / max(1, len(vals) - 1)
    return out


def rank(recs):
    """桶间按桶序、桶内按特征名次均值排序；score 是排序键的单调映射，范围 (1, 4]。"""
    n_b = len(BUCKETS)
    for i, (lo, hi, keys) in enumerate(BUCKETS):
        bucket = [r for r in recs if lo <= r['n'] <= hi]
        if not bucket:
            continue
        cols = [_ranks([r[k] for r in bucket]) for k in keys]
        for j, r in enumerate(bucket):
            r['key'] = sum(c[j] for c in cols) / len(cols)
        bucket.sort(key=lambda r: (-r['key'], r['en']))
        for j, r in enumerate(bucket):
            r['score'] = (n_b - i) + (1.0 - j / max(1, len(bucket) - 1))
    recs.sort(key=lambda r: -r['score'])
    return recs


# ---------------------------------------------------------------- 输出

def write_out(out_dir, recs, budget):
    os.makedirs(out_dir, exist_ok=True)
    kept = recs[:budget] if budget else recs
    with open(os.path.join(out_dir, 'candidates.tsv'), 'w', encoding='utf-8',
              newline='') as f:
        w = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\',
                       lineterminator='\n')
        w.writerow(['en', 'zh', 'score', 'freq', 'n', 'cover', 'dice',
                    'cvalue', 'weird', 'mi'])
        for r in kept:
            w.writerow([r['en'], '|'.join(r['zh']), '%.4f' % r['score'], r['freq'],
                        r['n'], '%.2f' % r['cover'], '%.2f' % r['dice'],
                        '%.2f' % r['cvalue'], '%.2f' % r['weird'], '%.2f' % r['mi']])
    path = os.path.join(out_dir, 'batch.jsonl')
    with open(path, 'w', encoding='utf-8', newline='') as f:
        for r in kept:
            f.write(json.dumps({'en': r['en'], 'zh_candidates': r['zh']},
                               ensure_ascii=False, separators=(',', ':')) + '\n')
    return kept, path


# ---------------------------------------------------------------- 命令

def build(args):
    input_rows, rows = load_rows(args.input, args.background, args.exclude_keys)
    corpus = Corpus(rows, input_rows)
    stats = enumerate_grams(corpus)
    subdf = build_subdf(corpus)
    recs = build_records(corpus, stats, subdf)
    rank(recs)
    return corpus, stats, recs


def extract(args):
    t0 = time.time()
    corpus, stats, recs = build(args)
    kept, path = write_out(args.out_dir, recs, args.budget)
    print('rows=%d pairs=%d grams=%d cands=%d kept=%d payload=%d %.1fs' % (
        len(corpus.rows), len(corpus.pairs), len(stats['cnt']), len(recs), len(kept),
        sum(len(l) for l in open(path, encoding='utf-8')), time.time() - t0))
    return 0


def gold_set(paths):
    return {norm_lemma(en) for (en, zh) in load_gold(paths)}


def hits_at(recs, gold, k):
    top = recs[:k] if k else recs
    return sum(1 for r in top if norm_lemma(r['en']) in gold), len(top)


def bench(args):
    t0 = time.time()
    corpus, stats, recs = build(args)
    gold = gold_set(args.gold)
    ceiling = sum(1 for r in recs if norm_lemma(r['en']) in gold)
    print('候选 %d，其中 gold %d；gold 全集 %d 条' % (len(recs), ceiling, len(gold)))
    print('%-6s %6s %6s %8s %8s' % ('K', '送出', '命中', '精度', '召回'))
    for k in [100, 200, 400, 800, 1600, 0]:
        if k and k > len(recs):
            continue
        h, n = hits_at(recs, gold, k)
        print('%-6s %6d %6d %8.3f %8.3f' % (k or 'all', n, h, h / n, h / len(gold)))
    print('\n分桶（桶序即输出顺序）：')
    for lo, hi, keys in BUCKETS:
        sub = [r for r in recs if lo <= r['n'] <= hi]
        h = sum(1 for r in sub if norm_lemma(r['en']) in gold)
        print('  %-5s %5d 个  gold %4d  桶内占比 %.3f  桶内排序 %s'
              % ('%d词' % lo if lo == hi else '%d+词' % lo, len(sub), h,
                 h / len(sub) if sub else 0.0, '+'.join(keys)))
    print('%.1fs' % (time.time() - t0))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='termgen_v2.py')
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('extract', 'bench'):
        p = sub.add_parser(name)
        p.add_argument('--input', required=True)
        p.add_argument('--background')
        p.add_argument('--exclude-keys')
        p.add_argument('--budget', type=int, default=DEFAULT_BUDGET)
        p.add_argument('--out-dir')
        p.add_argument('--gold', action='append', default=[])
        p.set_defaults(func=extract if name == 'extract' else bench)
    args = ap.parse_args(argv)
    if not args.out_dir:
        args.out_dir = os.path.join(os.path.dirname(os.path.abspath(args.input)),
                                    'termgen-v2-out')
    if args.func is bench and not args.gold:
        args.gold = ['Vanilla/terms/terms-v1.tsv']
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
