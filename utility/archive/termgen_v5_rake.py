#!/usr/bin/env python3
"""termgen-v5-rake —— 同一候选池换 RAKE 排序：STOP 切短语，词分 = degree/frequency，短语分映射回 gram。

候选池固定为 v5 的支持度过滤结果（v5.pool_entries，1373 条），不增删，只重排：
degree = 该词与多少不同词共现，frequency = 出现次数；gram 分 = 短语分或词元分之和。
并排输出 v5 support 基线的 direct_recall / coverage / fp_rate，N ∈ {187, 681, 1373}。

用法：
    python utility/archive/termgen_v5_rake.py --input Vanilla/latest.tsv
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import termgen as tg
sys.path.insert(0, str(Path(__file__).resolve().parent))
import termgen_v5_single as v5

ROOT = Path(__file__).resolve().parent.parent.parent
NS = (187, 681, 1373)


def phrases_of(toks):
    out, current = [], []
    for tok in toks:
        if tok in tg.STOP:
            if current:
                out.append(tuple(current))
                current = []
        else:
            current.append(tok)
    if current:
        out.append(tuple(current))
    return out


def corpus_phrases(names):
    phrases = []
    for toks in names.values():
        phrases.extend(phrases_of(toks))
    return phrases


def word_scores(phrases):
    cooc = defaultdict(set)
    freq = Counter()
    for phrase in phrases:
        for word in phrase:
            freq[word] += 1
            cooc[word].update(w for w in phrase if w != word)
    return {w: len(cooc[w]) / freq[w] for w in freq}


def ranked(pool, names):
    phrases = corpus_phrases(names)
    words = word_scores(phrases)
    scores = {phrase: sum(words[w] for w in phrase) for phrase in phrases}
    out = []
    for entry in pool:
        gram = entry['gram']
        score = scores.get(gram)
        if score is None:
            score = sum(words.get(tok, 0.0) for tok in gram)
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
    parser = argparse.ArgumentParser(prog='termgen_v5_rake.py')
    parser.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
    parser.add_argument('--gold', action='append', default=[])
    args = parser.parse_args(argv)
    if not args.gold:
        args.gold = [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]

    result = v5.build(args.input, gates=False)
    pool = v5.pool_entries(result)
    names = result['names']
    gold = [tg.clean_en(en) for en, zh in tg.load_gold(args.gold)]
    mine = ranked(pool, names)
    base = baseline(pool)
    report = {
        'algorithm': 'rake degree=distinct-cooccur frequency=occurrences',
        'rows': [metric_row(mine, n, gold, names) for n in NS],
        'baseline': [metric_row(base, n, gold, names) for n in NS],
        'top20': [{'en': e['en'], 'score': e['score']} for e in mine[:20]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
