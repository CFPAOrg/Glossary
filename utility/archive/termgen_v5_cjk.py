#!/usr/bin/env python3
"""termgen-v5-cjk —— 从 CJK 名字表挖术语（单语，不看英文列）。

中文没有空格，词要"发现"出来，所以英文版 v5 的机制在这里主次互换：
    英文：词由空格给定 → 组合纪律当主力，熵/搭配只做排序特征
    CJK：词要自己发现 → 凝固度当门，最长匹配剪碎片

三步：
    1. 虚词和标点当分隔符，切出可组词的汉字串
    2. 候选 = 2~5 字子串，支持度 = 出现在多少个不同名字里
       凝固度 cohesion = min over 切分点 log2[ p(w) / (p(左)p(右)) ]（bit）
       内部结合够紧才是一个整体；不够紧的丢掉
    3. 最长匹配切一遍：每个位置取最长的已收单元，从没被切中过的丢掉
       碎片（混凝/凝土/色羊毛）永远轮不到它，因为它们前面总有更长的真词

第 3 步是主力。没有它，过门的 3889 条候选里 46.7% 是共享边界的碎片；
剪完剩 1078 条，碎片降到 1.1%，对 terms-v1 的 783 条中文术语：
精确召回 0.43、宽松召回 0.53，平均每名 1.69 个单元。

**自由度（左右邻熵）在本工具里默认不当门**，只当输出列。原因：名字表里
后缀词（木板）右邻永远是 EOS，熵为 0，一开门就误杀；实测门开到 1.0，
词表从 1078 塌到 83 条、精确召回 0.43 → 0.04。这条配方（凝固度+自由度）是为
散文语料设计的，名字表上只有凝固度站得住。

常量表来源：
    虚词表按本仓库语料实测裁剪——只收 的/之/与 这类在语料里从不做实义的字。
    地(恶地/末地)、着(着火)、和(饱和)、把(火把)、向(向日葵) 实测都是实义字，故意不收。
    要用大表（stopwords-iso/stopwords-zh、stopwords-iso/stopwords-ja）走 --stopwords 传文件。

用法：
    python utility/archive/termgen_v5_cjk.py extract --input Vanilla/latest.tsv --column zh_cn
    python utility/archive/termgen_v5_cjk.py extract --input Vanilla/latest.tsv --column ja_jp --out ja.tsv
    python utility/archive/termgen_v5_cjk.py extract --input Vanilla/latest.tsv --show-seg 20
    python utility/archive/termgen_v5_cjk.py bench --input Vanilla/latest.tsv --method bpe
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

ROOT = Path(__file__).resolve().parent.parent.parent

# 汉字（含扩展A/兼容）+ 日文平假名/片假名 + 々
CJK_CHAR_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\u3005]')
# 格式符、全角标点、空白：一律当分隔符
SEP_RE = re.compile(r'[%{}§\\\s\u3000-\u303f\uff00-\uffef\u2000-\u206f\u2010-\u2027]+')
SENT_RE = re.compile(r'[。！？；：，、“”‘’…—（）【】《》]')

# 虚词：出现即断开，不跨它组词。只收语料里从不做实义的字
STOP_CJK = set('的之与及或而则就都还很等们被为以') | set('のをがはへもやにでとからまで')
MAX_CHAR = 5  # 候选最长 5 字
COHESION_GATE = 1.0  # 凝固度门槛（bit）
FREEDOM_GATE = 0.0  # 默认关，见文件头说明


def load_stopwords(path):
    if not path:
        return set()
    with open(path, encoding='utf-8') as f:
        return {line.strip() for line in f if line.strip() and not line.startswith('#')}


def load_rows(path, column='zh_cn', key_filter='on', keys=None, max_name=16):
    """读 TSV 指定列；key 过滤沿用英文侧那套（key 与语言无关）"""
    wl, bl = tg.load_key_filter()
    pattern = re.compile(keys) if keys else None
    with open(path, encoding='utf-8', newline='') as f:
        rd = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))
    head = [c.strip().lower() for c in rd[0]]
    if column not in head:
        raise SystemExit('列 %s 不在表头 %s 里' % (column, head))
    ik, iz = (head.index('key') if 'key' in head else None), head.index(column)
    rows = []
    for i, r in enumerate(rd[1:], 2):
        if iz >= len(r):
            continue
        key = r[ik] if (ik is not None and ik < len(r)) else str(i)
        if pattern is not None:
            if not pattern.search(key):
                continue
        elif key_filter == 'on' and not tg.is_product_key(key, wl, bl):
            continue
        text = tg.clean_zh(r[iz])
        if not text or len(text) > 80 or SENT_RE.search(text):
            continue
        if not 0 < len(CJK_CHAR_RE.findall(text)) <= max_name:
            continue
        rows.append((key, text))
    return rows


def char_runs(text, stop):
    """切成可组词的字符段：虚词和标点当分隔符"""
    runs, cur = [], []
    for ch in text:
        if CJK_CHAR_RE.match(ch) and ch not in stop:
            cur.append(ch)
        elif cur:
            runs.append(tuple(cur))
            cur = []
    if cur:
        runs.append(tuple(cur))
    return runs


def corpus(rows, stop):
    out = []
    for key, text in rows:
        for run in char_runs(text, stop):
            if len(run) >= 2:
                out.append((key, run))
    return out


def candidates(streams, max_len):
    """支持度 = 出现在多少个不同名字里；顺带记左右邻居（自由度输出用）"""
    supports = defaultdict(set)
    left = defaultdict(Counter)
    right = defaultdict(Counter)
    for key, run in streams:
        for start in range(len(run)):
            for end in range(start + 1, min(len(run), start + max_len) + 1):
                gram = run[start:end]
                supports[gram].add(key)
                left[gram][run[start - 1] if start else '<BOS>'] += 1
                right[gram][run[end] if end < len(run) else '<EOS>'] += 1
    return supports, left, right


def cohesion(gram, supports, total):
    """凝固度：所有切分点里最松的那一处（bit）"""
    if len(gram) < 2:
        return None
    whole = len(supports[gram]) / total
    worst = math.inf
    for i in range(1, len(gram)):
        a, b = len(supports.get(gram[:i], ())) / total, len(supports.get(gram[i:], ())) / total
        if a <= 0 or b <= 0:
            return -math.inf
        worst = min(worst, math.log2(whole / (a * b)))
    return worst


def scores(supports, left, right, total):
    out = {}
    for gram in supports:
        out[gram] = (len(supports[gram]), cohesion(gram, supports, total),
                     min(tg.entropy_bits(left[gram]), tg.entropy_bits(right[gram])))
    return out


def gated(supports, stats, min_support, coh_gate, free_gate):
    """过门的候选：长度≥2 要凝固度够；单字只看支持度"""
    out = {}
    for gram, (count, coh, free) in stats.items():
        if count < min_support:
            continue
        if len(gram) >= 2 and (coh is None or coh < coh_gate):
            continue
        if len(gram) >= 2 and free < free_gate:
            continue
        out[gram] = (count, coh, free)
    return out


def longest_match(run, lexicon, max_len=MAX_CHAR):
    """从左到右取最长命中；一个字都没命中的位置退化成单字"""
    i, parts = 0, []
    while i < len(run):
        hit = None
        for size in range(min(max_len, len(run) - i), 1, -1):
            if run[i:i + size] in lexicon:
                hit = run[i:i + size]
                break
        parts.append(hit if hit else run[i:i + 1])
        i += len(hit) if hit else 1
    return parts


def winning_units(streams, lexicon, rounds=4):
    """只留最长匹配里真正赢过的多字单元；迭代到不动点"""
    for _ in range(rounds):
        used = set()
        for _, run in streams:
            used.update(parts for parts in longest_match(run, lexicon) if len(parts) >= 2)
        if used == lexicon:
            break
        lexicon = used
    return lexicon


def build(path, column='zh_cn', min_support=2, coh_gate=COHESION_GATE, free_gate=FREEDOM_GATE,
          max_len=MAX_CHAR, key_filter='on', keys=None, stopwords=None, max_name=16):
    rows = load_rows(path, column, key_filter, keys, max_name)
    stop = STOP_CJK | load_stopwords(stopwords)
    streams = corpus(rows, stop)
    supports, left, right = candidates(streams, max_len)
    total = len({key for key, _ in streams})
    stats = scores(supports, left, right, total)
    kept = gated(supports, stats, min_support, coh_gate, free_gate)
    return {'rows': rows, 'streams': streams, 'supports': supports, 'stats': stats,
            'kept': kept, 'total': total, 'stop': stop}


def entries_of(result, atomic=True):
    """atomic=True 出剪枝后的词表；False 出过门的全部候选（对照用）"""
    src = winning_units(result['streams'], set(result['kept'])) if atomic else result['kept']
    out = []
    for gram in src:
        count, coh, free = result['stats'][gram]
        out.append({'unit': ''.join(gram), 'gram': gram, 'support': count,
                    'cohesion': round(coh, 2) if coh is not None else None,
                    'freedom': round(free, 2), 'uses': None})
    out.sort(key=lambda e: (-e['support'], -len(e['gram']), e['unit']))
    return out


def bpe_units(streams, merges=400, min_support=2):
    """BPE 对照：反复合并最高频相邻对。纯频率、没有"内部结合"的概念"""
    seqs = [list(run) for _, run in streams]
    vocab = {}
    for _ in range(merges):
        pairs = Counter()
        for seq in seqs:
            for i in range(len(seq) - 1):
                pairs[(seq[i], seq[i + 1])] += 1
        if not pairs:
            break
        (a, b), count = max(pairs.items(), key=lambda kv: (kv[1], kv[0]))
        if count < min_support:
            break
        merged = a + b
        vocab[merged] = count
        for idx, seq in enumerate(seqs):
            out, i = [], 0
            while i < len(seq):
                if i < len(seq) - 1 and seq[i] == a and seq[i + 1] == b:
                    out.append(merged)
                    i += 2
                else:
                    out.append(seq[i])
                    i += 1
            seqs[idx] = out
    out = [{'unit': u, 'gram': tuple(u), 'support': n, 'cohesion': None, 'freedom': None,
            'uses': None} for u, n in vocab.items()]
    out.sort(key=lambda e: (-e['support'], -len(e['gram']), e['unit']))
    return out


def gold_terms(paths):
    out = set()
    for en, variants in tg.load_gold(paths):
        out.update(variants)
    return out


def metrics(entries, streams, gold, supports):
    units = {''.join(e['unit']) for e in entries}
    grams = {e['gram'] for e in entries}
    exact = units & gold
    loose = {t for t in gold if any(t in u for u in units)}
    frag = {u for u in units if len(u) > 1 and any(
        u != v and u in v and len(supports.get(tuple(v), ())) == len(supports.get(tuple(u), ()))
        for v in units)}
    segs = sum(len(longest_match(run, grams)) for _, run in streams)
    return {'units': len(units),
            'avg_len': round(sum(len(u) for u in units) / len(units), 2) if units else None,
            'seg_per_name': round(segs / len(streams), 2) if streams else None,
            'gold': len(gold),
            'exact_hit': len(exact),
            'exact_recall': round(len(exact) / len(gold), 4) if gold else None,
            'loose_recall': round(len(loose) / len(gold), 4) if gold else None,
            'fragment_rate': round(len(frag) / len(units), 4) if units else None}


def write_tsv(stream, entries):
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['unit', 'chars', 'support', 'cohesion', 'freedom'])
    for e in entries:
        writer.writerow([e['unit'], len(e['gram']), e['support'],
                         '' if e['cohesion'] is None else e['cohesion'], e['freedom']])


def show_segments(stream, result, entries, limit):
    grams = {e['gram'] for e in entries}
    for _, run in result['streams'][:limit]:
        parts = longest_match(run, grams)
        print('%s\t%s' % (''.join(run), ' | '.join(''.join(p) for p in parts)), file=stream)


def extract(args):
    result = build(args.input, args.column, args.min_support, args.cohesion_gate,
                   args.freedom_gate, args.max_len, args.key_filter, args.keys, args.stopwords,
                   args.max_name)
    entries = entries_of(result, atomic=not args.pool)
    if args.limit:
        entries = entries[:args.limit]
    present = {ch for _, run in result['streams'] for ch in run}
    summary = {'names': len(result['streams']), 'candidates': len(result['stats']),
               'kept': len(result['kept']), 'units': len(entries), 'column': args.column,
               'stop_hit': ''.join(sorted(result['stop'] & present))}
    stream = open(args.out, 'w', encoding='utf-8', newline='') if args.out else sys.stdout
    if not args.out:
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        if args.json:
            stream.write(json.dumps({'summary': summary, 'units': entries},
                                    ensure_ascii=False, indent=2) + '\n')
        else:
            write_tsv(stream, entries)
            if args.show_seg:
                print('\n# 切分示例', file=stream)
                show_segments(stream, result, entries_of(result, atomic=not args.pool), args.show_seg)
    finally:
        if args.out:
            stream.close()
    summary['out'] = str(args.out) if args.out else 'stdout'
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0


def bench(args):
    result = build(args.input, args.column, args.min_support, args.cohesion_gate,
                   args.freedom_gate, args.max_len, args.key_filter, args.keys, args.stopwords,
                   args.max_name)
    gold = gold_terms(args.gold)
    report = {'names': len(result['streams']),
              'chars': sum(len(run) for _, run in result['streams']),
              'candidates': len(result['stats']), 'gold': len(gold)}
    if args.method == 'bpe':
        report['bpe'] = {str(n): metrics(bpe_units(result['streams'], n, args.min_support),
                                         result['streams'], gold, result['supports'])
                         for n in (200, 400, 1005)}
    else:
        grid = {}
        for coh in (0.0, 0.5, 1.0, 2.0, 3.0):
            for free in (0.0, 0.5, 1.0):
                kept = gated(result['supports'], result['stats'], args.min_support, coh, free)
                if not kept:
                    continue
                entries = entries_of({**result, 'kept': kept}, atomic=True)
                grid['coh=%.1f free=%.1f' % (coh, free)] = metrics(entries, result['streams'],
                                                                   gold, result['supports'])
        report['grid'] = grid
        report['pool'] = metrics(entries_of(result, atomic=False), result['streams'], gold,
                                 result['supports'])
        report['atomic'] = metrics(entries_of(result, atomic=True), result['streams'], gold,
                                   result['supports'])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen_v5_cjk.py')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('extract', 'bench'):
        p = sub.add_parser(command)
        p.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
        p.add_argument('--column', default='zh_cn', help='zh_cn / zh_tw / zh_hk / ja_jp')
        p.add_argument('--min-support', type=int, default=2)
        p.add_argument('--cohesion-gate', type=float, default=COHESION_GATE)
        p.add_argument('--freedom-gate', type=float, default=FREEDOM_GATE,
                       help='默认关：名字表里后缀词右邻恒为 EOS，开门会误杀')
        p.add_argument('--max-len', type=int, default=MAX_CHAR, help='候选最长字数')
        p.add_argument('--max-name', type=int, default=16, help='名字最长汉字数')
        p.add_argument('--key-filter', choices=('on', 'off'), default='on')
        p.add_argument('--keys')
        p.add_argument('--stopwords', type=Path,
                       help='额外虚词表，一行一个（如 stopwords-iso/stopwords-zh.txt）')
        if command == 'extract':
            p.add_argument('--out', type=Path)
            p.add_argument('--limit', type=int, default=0)
            p.add_argument('--pool', action='store_true', help='出过门的全部候选，不做最长匹配剪枝')
            p.add_argument('--show-seg', type=int, default=0, help='打印 N 条切分示例')
            p.add_argument('--json', action='store_true')
        else:
            p.add_argument('--method', choices=('pmi', 'bpe'), default='pmi')
            p.add_argument('--gold', action='append', default=[])
    args = parser.parse_args(argv)
    if not getattr(args, 'gold', None):
        args.gold = [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]
    return extract(args) if args.command == 'extract' else bench(args)


if __name__ == '__main__':
    raise SystemExit(main())
