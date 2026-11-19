import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import io_utils as io

CJK_CHAR_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u309f\u30a0-\u30ff\u3005]')
SENT_RE = re.compile(r'[。！？；：，、“”‘’…—（）【】《》]')
STOP_CJK = set('的之与及或而则就都还很等们被为以') | set('のをがはへもやにでとからまで')
MAX_CHAR = 5
COHESION_GATE = 1.0
FREEDOM_GATE = 0.0


def load_stopwords(path):
    if not path:
        return set()

    with open(path, encoding='utf-8-sig') as f:
        return {line.strip() for line in f if line.strip() and not line.startswith('#')}


def load_rows(path, column='zh_cn', key_filter='on', keys=None, exclude_keys=None,
              filter_file=None, max_name=16):
    raw = io.load_input_rows(path, zh_col=column, en_col=column)
    filtered = io.filter_rows(raw, key_filter=key_filter, keys=keys, exclude_keys=exclude_keys, filter_file=filter_file)
    rows = []

    for key, en, zh in filtered:
        raw_val = zh or en
        text = io.clean_zh(raw_val)
        if not text or len(text) > 80 or SENT_RE.search(text):
            continue
        if not 0 < len(CJK_CHAR_RE.findall(text)) <= max_name:
            continue
        rows.append((key, text))

    return rows


def char_runs(text, stop):
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
    if len(gram) < 2:
        return None

    whole = len(supports[gram]) / total
    worst = math.inf

    for i in range(1, len(gram)):
        a = len(supports.get(gram[:i], ())) / total
        b = len(supports.get(gram[i:], ())) / total
        if a <= 0 or b <= 0:
            return -math.inf
        worst = min(worst, math.log2(whole / (a * b)))

    return worst


def scores(supports, left, right, total):
    return {
        gram: (len(supports[gram]), cohesion(gram, supports, total),
               min(io.entropy_bits(left[gram]), io.entropy_bits(right[gram])))
        for gram in supports
    }


def gated(supports, stats, min_support, coh_gate, free_gate):
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


def winning_units(streams, lexicon, rounds=4, max_len=MAX_CHAR):
    for _ in range(rounds):
        used = set()
        for _, run in streams:
            used.update(parts for parts in longest_match(run, lexicon, max_len=max_len) if len(parts) >= 2)
        if used == lexicon:
            break
        lexicon = used

    return lexicon


def bpe_units(streams, merges=400, min_support=2):
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

    out = [{'unit': u, 'gram': tuple(u), 'support': n, 'cohesion': None, 'freedom': None}
           for u, n in vocab.items()]
    out.sort(key=lambda e: (-e['support'], -len(e['gram']), e['unit']))

    return out


def build(path, column='zh_cn', min_support=2, coh_gate=COHESION_GATE, free_gate=FREEDOM_GATE,
          max_len=MAX_CHAR, key_filter='on', keys=None, exclude_keys=None, filter_file=None,
          stopwords=None, max_name=16):
    rows = load_rows(path, column=column, key_filter=key_filter, keys=keys,
                     exclude_keys=exclude_keys, filter_file=filter_file, max_name=max_name)
    stop = STOP_CJK | load_stopwords(stopwords)
    streams = corpus(rows, stop)
    supports, left, right = candidates(streams, max_len)
    total = len({key for key, _ in streams}) or 1
    stats = scores(supports, left, right, total)
    kept = gated(supports, stats, min_support, coh_gate, free_gate)

    return {'rows': rows, 'streams': streams, 'supports': supports, 'stats': stats,
            'kept': kept, 'total': total, 'stop': stop, 'max_len': max_len}


def entries_of(result, atomic=True, method='pmi', bpe_merges=400, min_support=2, known_zh=None):
    if method == 'bpe':
        entries = bpe_units(result['streams'], merges=bpe_merges, min_support=min_support)
    else:
        src = winning_units(result['streams'], set(result['kept']), max_len=result.get('max_len', MAX_CHAR)) if atomic else result['kept']
        entries = []
        for gram in src:
            count, coh, free = result['stats'][gram]
            entries.append({
                'unit': ''.join(gram),
                'gram': gram,
                'support': count,
                'cohesion': round(coh, 2) if coh is not None else None,
                'freedom': round(free, 2),
            })
        entries.sort(key=lambda e: (-e['support'], -len(e['gram']), e['unit']))

    if known_zh:
        entries = [e for e in entries if e['unit'] not in known_zh]

    return entries


def write_tsv(stream, entries):
    io.write_tsv(
        stream,
        ['unit', 'chars', 'support', 'cohesion', 'freedom'],
        [[e['unit'], len(e['gram']), e['support'], '' if e['cohesion'] is None else e['cohesion'],
          '' if e['freedom'] is None else e['freedom']] for e in entries],
    )


def show_segments(stream, result, entries, limit):
    grams = {e['gram'] for e in entries}
    for _, run in result['streams'][:limit]:
        parts = longest_match(run, grams, max_len=result.get('max_len', MAX_CHAR))
        print(f'{"".join(run)}\t{" | ".join("".join(p) for p in parts)}', file=stream)


def extract(args):
    result = build(
        args.input,
        column=args.column,
        min_support=args.min_support,
        coh_gate=args.cohesion_gate,
        free_gate=args.freedom_gate,
        max_len=args.max_len,
        key_filter=args.key_filter,
        keys=args.keys,
        exclude_keys=getattr(args, 'exclude_keys', None),
        filter_file=getattr(args, 'filter_file', None),
        stopwords=args.stopwords,
        max_name=args.max_name,
    )
    known_entries, _ = io.load_glossary_entries(getattr(args, 'known', None))
    known_zh = {z for e in known_entries for z in e['zh']} if known_entries else None
    entries = entries_of(result, atomic=not args.pool, method=args.method,
                         bpe_merges=args.bpe_merges, min_support=args.min_support, known_zh=known_zh)
    if args.limit:
        entries = entries[:args.limit]

    present = {ch for _, run in result['streams'] for ch in run}
    summary = {'names': len(result['streams']), 'candidates': len(result['stats']),
               'kept': len(result['kept']), 'units': len(entries), 'column': args.column,
               'stop_hit': ''.join(sorted(result['stop'] & present))}

    if args.out:
        io.ensure_parent(args.out)
        stream = open(args.out, 'w', encoding='utf-8', newline='')
    else:
        sys.stdout.reconfigure(encoding='utf-8', newline='')
        stream = sys.stdout

    try:
        if args.json:
            stream.write(json.dumps({'summary': summary, 'units': entries}, ensure_ascii=False, indent=2) + '\n')
        else:
            write_tsv(stream, entries)
            if args.show_seg:
                print('\n# 切分示例', file=stream)
                show_segments(stream, result, entries, args.show_seg)
    finally:
        if args.out:
            stream.close()

    summary['out'] = str(args.out) if args.out else 'stdout'
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    return 0


def add_cjk_args(p):
    p.add_argument('--input', type=Path, default=io.ROOT / 'Vanilla/latest.tsv')
    p.add_argument('--column', default='zh_cn', help='zh_cn / zh_tw / zh_hk / ja_jp')
    p.add_argument('--min-support', type=int, default=2)
    p.add_argument('--cohesion-gate', type=float, default=COHESION_GATE)
    p.add_argument('--freedom-gate', type=float, default=FREEDOM_GATE)
    p.add_argument('--max-len', type=int, default=MAX_CHAR)
    p.add_argument('--max-name', type=int, default=16)
    p.add_argument('--key-filter', choices=('on', 'off', 'auto'), default='on')
    p.add_argument('--keys')
    p.add_argument('--exclude-keys')
    p.add_argument('--filter-file', type=Path)
    p.add_argument('--stopwords', type=Path)
    p.add_argument('--known', nargs='*', default=[])
    p.add_argument('--method', choices=('pmi', 'bpe'), default='pmi')
    p.add_argument('--bpe-merges', type=int, default=400)
    p.add_argument('--out', type=Path)
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--pool', action='store_true')
    p.add_argument('--show-seg', type=int, default=0)
    p.add_argument('--json', action='store_true')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='final.py cjk')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('extract')
    add_cjk_args(p)
    args = parser.parse_args(argv)

    return extract(args)


if __name__ == '__main__':
    raise SystemExit(main())
