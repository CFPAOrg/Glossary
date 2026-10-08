#!/usr/bin/env python3
"""termgen v6：近无参数术语抽取。三种模式 mono-en / mono-zh / bi。

没有魔数。每个判据要么是结构下限（2），要么直接来自语料自身的分布：

  候选门槛  支撑 ≥2 行（结构下限）
            + 左邻或右邻的**不同语境 ≥2 种**（边界熵 ≥1 bit，同样是下限：
              只有一个语境 = 永远被同一个词夹住 = 不是独立单元）
  排序      先比新覆盖行数，同分再比边界熵（bit）——熵高的更自由
  目标函数  最小条目集合覆盖：挑能新覆盖最多行的单元，条目数就是人工审阅量
  停机      最优单元新覆盖 <2 行就停（1 个单元换 1 个例外是平局，不值）
  自检      行留出重建率：八成行上诱导，两成行能不能被切出来（不需要 gold）

声明式的东西只有两样：key 类型策略（glob），和中文单元最短 2 字（语言事实）。

用法：
  python termgen_v6_noparam.py --mode mono-en --input Vanilla/latest.tsv --out en.json
  python termgen_v6_noparam.py --mode mono-zh --input Vanilla/latest.tsv --out zh.json
  python termgen_v6_noparam.py --mode bi      --input Vanilla/latest.tsv --out bi.json
"""
import argparse
import csv
import heapq
import json
import math
import random
import re
from collections import Counter, defaultdict

FORMAT_RE = re.compile(r'%(\d+\$)?[sdf]|%%|\{[^}]*\}|§.|\\n|\\t|\\r')
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+')
WS_RE = re.compile(r'\s+')
BOS, EOS = '<BOS>', '<EOS>'

DEFAULT_KEEP = ['block.*', 'item.*', 'entity.*', 'biome.*', 'effect.*', 'enchantment.*',
                'trim_pattern.*', 'trim_material.*', 'color.*', 'instrument.*',
                'flat_world_preset.*', 'generator.*', 'attribute.*', 'stat.*',
                'stat_type.*', 'itemGroup.*', 'fluid.*', 'potion.*']
DEFAULT_DROP = ['*.desc', '*.description', '*.tooltip', '*.narration', '*banner*',
                '*tropical_fish*', '*subtitles*']
ZH_MIN = 2  # 中文单元最短 2 字：单字多为粘着语素
ZH_MAX = 8  # 中文子串窗口上限


def clean(s):
    return WS_RE.sub(' ', FORMAT_RE.sub(' ', s or '').replace('’', "'").replace('\u00a0', ' ')).strip()


def glob_ok(key, patterns):
    low = str(key or '').lower()
    for p in patterns:
        rx = re.escape(p).replace(r'\*', '.*')
        if re.fullmatch(rx, low) or re.search(rx, low):
            return True
    return False


def type_ok(key, keep, drop):
    if not key:
        return False
    return False if glob_ok(key, drop) else glob_ok(key, keep)


def load_rows(path, keep, drop):
    """读 TSV / diff JSON / 纯文本；格式符只清掉，整行照进。"""
    if str(path).endswith('.json'):
        data = json.load(open(path, encoding='utf-8'))
        raw = [(k, v.get('en_us', ''), v.get('zh_cn', ''))
               for sec in ('added', 'changed') for k, v in data.get(sec, {}).items()]
    elif str(path).endswith('.txt'):
        raw = [(str(i), line, '') for i, line in enumerate(open(path, encoding='utf-8'), 1)]
    else:
        with open(path, encoding='utf-8', newline='') as fh:
            table = list(csv.reader(fh, delimiter='\t', quoting=csv.QUOTE_NONE))
        head = [c.strip().lower() for c in table[0]] if table else []
        named = 'en' in head or 'en_us' in head or 'key' in head
        ie = (head.index('en_us') if 'en_us' in head else head.index('en')) if named else 0
        iz = (head.index('zh_cn') if 'zh_cn' in head else head.index('zh')) if named and (
            'zh_cn' in head or 'zh' in head) else (1 if len(table[0]) > 1 else None)
        ik = head.index('key') if named and 'key' in head else None
        raw = []
        for i, r in enumerate(table[1:] if named else table, 1):
            if ie >= len(r):
                continue
            raw.append((r[ik] if ik is not None and ik < len(r) else str(i), r[ie],
                        r[iz] if iz is not None and iz < len(r) else ''))
    return [{'key': k, 'type': str(k).split('.')[0].lower(), 'en': clean(en), 'zh': clean(zh)}
            for k, en, zh in raw if type_ok(k, keep, drop)]


def name_tokens(en):
    return tuple(t.lower() for t in TOKEN_RE.findall(en))


def rare_rows(seqs, span=1):
    """含「只出现过一次的片段」的行——这种行推不出来，才值得单列一条。

    span=1 按词（英文），span=2 按双字（中文）。判据是结构下限（1 次），不是阈值。
    """
    freq = Counter()
    for s in seqs:
        for j in range(len(s) - span + 1):
            freq[s[j:j + span]] += 1
    return {i for i, s in enumerate(seqs)
            if any(freq[s[j:j + span]] == 1 for j in range(len(s) - span + 1))}


def quantile(values, q, fallback):
    if not values:
        return fallback
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def zh_seq(zh):
    return tuple(''.join(CJK_RE.findall(zh)))


def segmentable(seq, lexicon, max_gram):
    n = len(seq)
    reach = bytearray(n + 1)
    reach[0] = 1
    for i in range(1, n + 1):
        for j in range(max(0, i - max_gram), i):
            if reach[j] and seq[j:i] in lexicon:
                reach[i] = 1
                break
    return bool(reach[n])


def grams(seq, max_gram, min_gram=1):
    for a in range(len(seq)):
        for b in range(a + min_gram, min(len(seq), a + max_gram) + 1):
            yield seq[a:b]


def boundaries(seqs, max_gram, min_gram=1):
    """每个候选的左右邻接语境（去重集合）与边界熵（bit）。"""
    left, right = defaultdict(Counter), defaultdict(Counter)
    for s in seqs:
        for a in range(len(s)):
            for b in range(a + min_gram, min(len(s), a + max_gram) + 1):
                c = s[a:b]
                left[c][s[a - 1] if a else BOS] += 1
                right[c][s[b] if b < len(s) else EOS] += 1
    return left, right


def entropy(counter):
    total = sum(counter.values())
    if total <= 1:
        return 0.0
    return -sum((v / total) * math.log2(v / total) for v in counter.values())


def free_ok(c, left, right):
    """边界自由：左右两侧至少有一侧存在 2 种以上不同语境（= 边界熵 ≥1 bit）。"""
    return len(left[c]) >= 2 or len(right[c]) >= 2


def freedom(c, left, right):
    return max(entropy(left[c]), entropy(right[c]))


def induce(seqs, max_gram, min_gram=1, allowed=None):
    """贪心：每轮挑「新解释的字符数 / 自身长度」最大的自由单元，记录覆盖率轨迹。

    停机不写常数：跑到没有净收益为止，再按「单元数 + 例外行数」最小截断——那才是人工审阅量。
    用惰性堆代替每轮全扫（覆盖率单调下降，堆顶重算后变差就压回去）。
    allowed 非空时只在该集合里挑（双语模式用来强制"先对齐再出条目"）。
    """
    covered = bytearray(len(seqs))
    rows_of = defaultdict(set)
    for i, s in enumerate(seqs):
        for c in grams(s, max_gram, min_gram):
            rows_of[c].add(i)
    left, right = boundaries(seqs, max_gram, min_gram)

    def key_of(c):
        fresh = [r for r in rows_of[c] if not covered[r]]
        eff = sum(len(seqs[r]) for r in fresh) / len(c) if fresh else 0.0
        return fresh, eff, freedom(c, left, right)

    heap = []
    for c, rows in rows_of.items():
        if allowed is not None and c not in allowed:
            continue
        if len(rows) < 2 or not free_ok(c, left, right):
            continue
        fresh, eff, free = key_of(c)
        if fresh:
            heap.append((-eff, -free, c))
    heapq.heapify(heap)

    lexicon, order, trace, dead = set(), [], [(0, 0)], set()
    while heap:
        neg_eff, neg_free, c = heapq.heappop(heap)
        if c in lexicon or c in dead:
            continue
        fresh, eff, free = key_of(c)
        if not fresh:
            continue
        if (-eff, -free) > (neg_eff, neg_free):
            heapq.heappush(heap, (-eff, -free, c))
            continue
        if eff <= 1.0:
            break
        gained = [r for r in fresh if segmentable(seqs[r], lexicon | {c}, max_gram)]
        if not gained:
            dead.add(c)
            continue
        lexicon.add(c)
        order.append(c)
        for r in gained:
            covered[r] = 1
        trace.append((len(order), sum(covered)))
    return order, trace


def align_gate(en_seqs, zh_seqs, en_max):
    """先对齐：只有同一行里互相作证（共现 ≥2 行）的英文片段与中文片段才算候选。

    这是双语模式的核心——单元必须由对照关系担保，而不是先压缩再事后配对。
    """
    en_grams = [set(grams(s, en_max)) for s in en_seqs]
    zh_grams = [set(grams(s, ZH_MAX, ZH_MIN)) for s in zh_seqs]
    votes = defaultdict(int)
    for i in range(len(en_seqs)):
        for g in en_grams[i]:
            for z in zh_grams[i]:
                votes[(g, z)] += 1
    ok_en, ok_zh = set(), set()
    for (g, z), count in votes.items():
        if count >= 2:
            ok_en.add(g)
            ok_zh.add(z)
    return ok_en, ok_zh


def pair_units(en_lex, zh_lex, en_seqs, zh_seqs, en_max):
    """英文单元 → 中文单元：同行共现投票，整名行用整条译文加权。"""
    unit_rows = defaultdict(set)
    for i, s in enumerate(en_seqs):
        for c in grams(s, en_max):
            if c in en_lex:
                unit_rows[c].add(i)
    pairs = {}
    for unit, idxs in unit_rows.items():
        votes = Counter()
        for i in idxs:
            zh = zh_seqs[i]
            if tuple(en_seqs[i]) == unit:
                votes[zh] += 3
                continue
            for z in grams(zh, ZH_MAX, ZH_MIN):
                if z in zh_lex:
                    votes[z] += 1
        if votes:
            top, count = votes.most_common(1)[0]
            if count >= 2:
                pairs[unit] = top
    return pairs


def holdout_rate(seqs, max_gram, min_gram=1, seed=0, share=0.2):
    idx = list(range(len(seqs)))
    random.Random(seed).shuffle(idx)
    cut = int(len(idx) * (1 - share))
    order, _ = induce([seqs[i] for i in idx[:cut]], max_gram, min_gram)
    lexicon = set(order)
    hit = sum(1 for i in idx[cut:] if segmentable(seqs[i], lexicon, max_gram))
    return hit / len(idx[cut:]) if len(idx) > cut else 0.0


def prepare(rows, mode):
    """按模式取序列，丢掉该模式无法处理的空行。"""
    keep = []
    for r in rows:
        en, zh = name_tokens(r['en']), zh_seq(r['zh'])
        if mode == 'mono-en' and en:
            keep.append((r, en, zh))
        elif mode == 'mono-zh' and len(zh) >= ZH_MIN:
            keep.append((r, en, zh))
        elif mode == 'bi' and en and len(zh) >= ZH_MIN:
            keep.append((r, en, zh))
    return [k[0] for k in keep], [k[1] for k in keep], [k[2] for k in keep]


def run(mode, rows, seed=0):
    rows, en_seqs, zh_seqs = prepare(rows, mode)
    stats = {'mode': mode, 'rows': len(rows)}
    if mode == 'mono-en':
        top = quantile([len(s) for s in en_seqs], 0.99, 7)
        order, trace = induce(en_seqs, top)
        lex = set(order)
        keep = rare_rows(en_seqs, 1)
        stats.update({'units': len(lex), 'greedy_units': len(order), 'listed': len(keep),
                      'lossless': sum(1 for s in en_seqs if segmentable(s, lex, top)) / len(en_seqs),
                      'holdout': holdout_rate(en_seqs, top, seed=seed)})
        units = sorted(' '.join(c) for c in lex)
        listed = sorted(rows[i]['en'] for i in keep)
        return {'en_candidates': units + listed, 'stats': stats}
    if mode == 'mono-zh':
        order, trace = induce(zh_seqs, ZH_MAX, ZH_MIN)
        lex = set(order)
        keep = rare_rows(zh_seqs, 2)
        stats.update({'units': len(lex), 'greedy_units': len(order), 'listed': len(keep),
                      'lossless': sum(1 for s in zh_seqs if segmentable(s, lex, ZH_MAX)) / len(zh_seqs),
                      'holdout': holdout_rate(zh_seqs, ZH_MAX, ZH_MIN, seed=seed)})
        units = sorted(''.join(c) for c in lex)
        listed = sorted(''.join(zh_seqs[i]) for i in keep)
        return {'zh_candidates': units + listed, 'stats': stats}
    en_max = quantile([len(s) for s in en_seqs], 0.99, 7)
    ok_en, ok_zh = align_gate(en_seqs, zh_seqs, en_max)
    en_order, _ = induce(en_seqs, en_max, allowed=ok_en)
    zh_order, _ = induce(zh_seqs, ZH_MAX, ZH_MIN, allowed=ok_zh)
    en_lex, zh_lex = set(en_order), set(zh_order)
    keep_en, keep_zh = rare_rows(en_seqs, 1), rare_rows(zh_seqs, 2)
    keep = keep_en | keep_zh
    pairs = pair_units(en_lex, zh_lex, en_seqs, zh_seqs, en_max)
    stats.update({'pairs': len(pairs), 'units_en': len(en_lex), 'units_zh': len(zh_lex),
                  'grounded_en': len(ok_en), 'grounded_zh': len(ok_zh), 'listed': len(keep),
                  'lossless_en': sum(1 for s in en_seqs if segmentable(s, en_lex, en_max)) / len(en_seqs),
                  'lossless_zh': sum(1 for s in zh_seqs if segmentable(s, zh_lex, ZH_MAX)) / len(zh_seqs),
                  'holdout_en': holdout_rate(en_seqs, en_max, seed=seed),
                  'holdout_zh': holdout_rate(zh_seqs, ZH_MAX, ZH_MIN, seed=seed)})
    en_list = sorted({' '.join(c) for c in en_lex} | {rows[i]['en'] for i in keep_en})
    zh_list = sorted({''.join(c) for c in zh_lex} | {''.join(zh_seqs[i]) for i in keep_zh})
    all_pairs = sorted([[' '.join(e), ''.join(z)] for e, z in pairs.items()]
                       + [[' '.join(en_seqs[i]), ''.join(zh_seqs[i])] for i in keep_en])
    return {'en_candidates': en_list, 'zh_candidates': zh_list, 'pairs': all_pairs,
            'stats': stats}


def main(argv=None):
    ap = argparse.ArgumentParser(prog='termgen_v6_noparam.py')
    ap.add_argument('--mode', choices=('mono-en', 'mono-zh', 'bi'), required=True)
    ap.add_argument('--input', default='Vanilla/latest.tsv')
    ap.add_argument('--types', help='key 类型策略 JSON（keep/drop 两个 glob 数组）')
    ap.add_argument('--out', required=True)
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args(argv)
    keep, drop = DEFAULT_KEEP, DEFAULT_DROP
    if args.types:
        cfg = json.load(open(args.types, encoding='utf-8'))
        keep, drop = cfg.get('keep', keep), cfg.get('drop', drop)
    result = run(args.mode, load_rows(args.input, keep, drop), args.seed)
    json.dump(result, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(json.dumps(result['stats'], ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
