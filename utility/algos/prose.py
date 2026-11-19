import argparse
import collections
import json
import math
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

try:
    from wordfreq import zipf_frequency
except ImportError:
    zipf_frequency = None

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import io_utils as io

CJK = re.compile(r'[\u4e00-\u9fff]')
LAT = re.compile(r'[A-Za-z]')
WORD = re.compile(r'[a-z0-9]+')
FMT = re.compile(r'%(\d+\$)?[sdf]|§.|\\n')

NAME_PUNCT = '.!?;:,'
NAME_WORDS = (1, 6)
PHRASE_N = (2, 3)
WRAP = 100

STOPWORDS = {
    'the', 'a', 'an', 'of', 'to', 'in', 'on', 'at', 'by', 'for', 'from', 'with', 'without',
    'and', 'or', 'nor', 'but', 'as', 'into', 'onto', 'over', 'under', 'out', 'up', 'down',
    'off', 'about', 'above', 'below', 'between', 'through', 'than', 'then', 'so', 'if',
    'when', 'while', 'during', 'after', 'before', 'until', 'because', 'via', 'per',
    'it', 'its', 'this', 'that', 'these', 'those', 'your', 'you', 'we', 'our', 'us',
    'their', 'they', 'them', 'he', 'she', 'his', 'her', 'i', 'me', 'my', 'all', 'any',
    'some', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'only', 'own', 'same',
    'such', 'here', 'there', 'what', 'which', 'who', 'whom', 'whose', 'how', 'why', 'where',
    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am', 'do', 'does', 'did', 'done',
    'have', 'has', 'had', 'can', 'could', 'will', 'would', 'shall', 'should', 'may',
    'might', 'must', 'not', 'no', 's', 't',
    'unlock', 'unlocks', 'unlocked', 'acquire', 'acquires', 'obtain', 'obtains',
    'get', 'gets', 'use', 'used', 'uses', 'using',
}

MINE_N_MAX = 5
MINE_SPLIT = re.compile(r"[^A-Za-z0-9'’\-\s_]+")
MINE_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'’\-]*")
MINE_EX_LEN = 60
MINE_EX_SRC = 200
MINE_PCT_COH = 30
MINE_PCT_ENT = 40
TERMHOODS = ('auto', 'self', 'specificity')
PROSE_MED_LEN = 60
COMMON_ZIPF = 4.5
INVENTED_ZIPF = 1.5
CAP_RATIO = 0.10
NOUN_DET_RATIO = 0.10
MINE_MI_ABS = 3.0
MINE_ENT_ABS = 1.5

DET_WORDS = {'the', 'a', 'an', 'your', 'her', 'his', 'their', 'its', 'this', 'that',
             'these', 'those', 'my', 'our', 'some', 'each', 'every', 'another', 'any'}
PRONOUNS = {'i', 'me', 'my', 'mine', 'you', 'your', 'yours', 'he', 'him', 'his', 'she',
            'her', 'hers', 'it', 'its', 'we', 'us', 'our', 'ours', 'they', 'them',
            'their', 'theirs', 'myself', 'yourself', 'himself', 'herself', 'itself',
            'ourselves', 'themselves', 'who', 'whom', 'whose'}

MINE_LATIN = r"[A-Za-z][A-Za-z0-9'’\-]*"
MINE_NUMBER = r"\d+"
MINE_SCRIPT = {
    'zh': r"\u4e00-\u9fff\u3400-\u4dbf",
    'ja': r"\u4e00-\u9fff\u3400-\u4dbf\u3040-\u309f\u30a0-\u30ff",
    'ko': r"\uac00-\ud7af\u1100-\u11ff",
}
MINE_JA_SEP = r"|[\u30fb\u30a0]"
MINE_JA_UNIT = r"[\u4e00-\u9fff\u3400-\u4dbf]|[\u30a0-\u30ff]+|[\u3040-\u309f]|[A-Za-z0-9]+"
MINE_JA_EDGE = re.compile(r"[\u3040-\u309f]")

STOP_CJK = set('的了在是和平与为以及或也都就而其之等被把对从向由让使能会要可不没很更最'
               '个些这那有我你他它们上下中里外前后时地得着过来去到于并但且则若如即才再又还'
               '只各每某该此本一二三四五六七八九十')
STOP_KO = set('이 가 은 는 을 를 의 에 와 과 도 만 까지 부터 로 으로 그리고 하지만 그러나 또한 '
              '및 등 것 수 있다 없다 하다 되다 이 그 저 어떤 이렇게 그렇게 저렇게'.split())

CJK_NAME_PUNCT = '.!?;:，。！？；：、…～'
CJK_NAME_UNITS = (1, 12)


def _mine_units(chars, run=False, extra=''):
    body = f"[{chars}]{'+' if run else ''}"

    return (re.compile(f"{body}|{MINE_LATIN}|{MINE_NUMBER}"),
            re.compile(f"[^%sA-Za-z0-9'’\\-\\s_]+%s" % (chars, extra)))


def _mine_lang_table():
    table = {'en': {'file': 'en_us', 'max_n': MINE_N_MAX, 'min_n': 1, 'split': MINE_SPLIT,
                    'unit': MINE_WORD, 'stop': STOPWORDS, 'edge': None, 'cjk': False,
                    'join': ' ', 'label': 'en'}}
    for lang, code, stop, max_n, join in (('zh', 'zh_cn', STOP_CJK, 8, ''),
                                          ('ja', 'ja_jp', STOP_CJK, 8, ''),
                                          ('ko', 'ko_kr', STOP_KO, 5, ' ')):
        unit, split = _mine_units(MINE_SCRIPT[lang], extra=MINE_JA_SEP if lang == 'ja' else '')
        table[lang] = {'file': code, 'max_n': max_n, 'min_n': 2, 'unit': unit,
                       'split': split, 'stop': stop, 'edge': None, 'cjk': True,
                       'join': join, 'label': lang}
    table['ja']['unit'] = re.compile(MINE_JA_UNIT)
    table['ja']['edge'] = MINE_JA_EDGE
    table['ko']['unit'] = MINE_KO_EOJEOL
    table['ko-syllable'] = dict(table['ko'], unit=MINE_KO_SYLLABLE, max_n=8, label='ko 音节')

    return table


MINE_LANGS = ('en', 'zh', 'ja', 'ko')
MINE_KO_SYLLABLE = _mine_units(MINE_SCRIPT['ko'])[0]
MINE_KO_EOJEOL = _mine_units(MINE_SCRIPT['ko'], run=True)[0]
MINE_LANG = _mine_lang_table()


def mine_lang_key(lang, ko_unit='eojeol'):
    return 'ko-syllable' if lang == 'ko' and ko_unit == 'syllable' else lang


def norm_en(s):
    return WORD.findall(FMT.sub(' ', s.lower()))


def name_like(s):
    if not isinstance(s, str) or any(c in NAME_PUNCT for c in s):
        return False
    raw = s.split()
    if not NAME_WORDS[0] <= len(raw) <= NAME_WORDS[1]:
        return False

    return sum(1 for w in raw if w[:1].isupper()) * 2 > len(raw)


def name_like_cjk(s, lang):
    if not isinstance(s, str) or any(c in CJK_NAME_PUNCT for c in s):
        return False
    n = len(MINE_LANG[lang]['unit'].findall(s))

    return CJK_NAME_UNITS[0] <= n <= CJK_NAME_UNITS[1]


def norm_zh(s):
    return ' '.join(FMT.sub(' ', s).split()).strip()


def lcp(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1

    return a[:i]


def lcs(a, b):
    n = min(len(a), len(b))
    i = 0
    while i < n and a[len(a) - 1 - i] == b[len(b) - 1 - i]:
        i += 1

    return a[len(a) - i:]


def disp_width(s):
    return sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in s)


def wpad(s, width):
    return s + ' ' * max(0, width - disp_width(s))


def mine_clauses(text, lang='en'):
    spec = MINE_LANG[lang]
    out = []

    for cl in spec['split'].split(FMT.sub(' ', text).replace('_', ' ')):
        cl = cl.strip()
        ws = spec['unit'].findall(cl)
        if ws:
            out.append((cl, ws))

    return out


def mine_candidate(gram, lang='en'):
    spec = MINE_LANG[lang]
    stop = spec['stop']
    edge = spec['edge']

    return not (gram[0] in stop or gram[-1] in stop
                or all(w in stop for w in gram)
                or (edge is not None and (edge.match(gram[0]) or edge.match(gram[-1]))))


def shannon(counter):
    tot = sum(counter.values())
    if tot <= 1:
        return 0.0

    return max(0.0, -sum((n / tot) * math.log2(n / tot) for n in counter.values() if n))


def percentile(vals, pct):
    if not vals:
        return 0.0
    v = sorted(vals)

    return v[min(len(v) - 1, int(len(v) * pct / 100.0))]


def mine_entries(data, max_n=MINE_N_MAX, lang='en'):
    out = []
    for key, val in data.items():
        if not isinstance(val, str):
            continue
        cl = mine_clauses(val, lang)
        if cl:
            out.append((key, name_like(val) if lang == 'en' else name_like_cjk(val, lang), cl))

    return out


def mine_freqs(parsed, max_n):
    docs = collections.Counter()
    namec = collections.Counter()

    for _, is_name, clauses in parsed:
        seen = set()
        for _, ws in clauses:
            low = [w.lower() for w in ws]
            for n in range(1, min(max_n, len(low)) + 1):
                for i in range(len(low) - n + 1):
                    seen.add(tuple(low[i:i + n]))
        for g in seen:
            docs[g] += 1
            if is_name:
                namec[g] += 1

    return docs, namec


def mine_context(parsed, keep, max_n, lang='en'):
    left = collections.defaultdict(collections.Counter)
    right = collections.defaultdict(collections.Counter)
    whole = collections.Counter()
    init_name = collections.Counter()
    surf = collections.defaultdict(collections.Counter)
    occ = collections.Counter()
    ex_long, ex_name = {}, {}
    join = MINE_LANG[lang]['join']

    for _, is_name, clauses in parsed:
        for cl, ws in clauses:
            low = [w.lower() for w in ws]
            for n in range(1, min(max_n, len(low)) + 1):
                for i in range(len(low) - n + 1):
                    g = tuple(low[i:i + n])
                    if g not in keep:
                        continue
                    occ[g] += 1
                    if i:
                        left[g][low[i - 1]] += 1
                    else:
                        whole[g] += i + n == len(low)
                        init_name[g] += is_name
                    if i + n < len(low):
                        right[g][low[i + n]] += 1
                    surf[g][join.join(ws[i:i + n])] += 1
                    ex = ex_name if is_name else ex_long
                    cur = ex.get(g)
                    if cur is None or (len(cur) < len(cl) <= MINE_EX_SRC):
                        ex[g] = cl

    return left, right, whole, init_name, surf, occ, ex_long, ex_name


def mine_hmin(left, right, whole, init_name):
    free = math.inf if (whole or init_name) else 0.0
    hl = shannon(left) if sum(left.values()) >= 2 else free
    hr = shannon(right) if sum(right.values()) >= 2 else math.inf

    return min(hl, hr)


def mine_mi(gram, docs, n_docs):
    if len(gram) < 2:
        return math.inf

    return min(math.log2(docs[gram] * n_docs / (docs[gram[:s]] * docs[gram[s:]])) for s in range(1, len(gram)))


def mine_surface(counter, fallback=''):
    return (counter or collections.Counter()).most_common(1)[0][0] if counter else fallback


def mine_scores(parsed, max_n, min_impact, lang='en'):
    docs, namec = mine_freqs(parsed, max_n)
    ok = {g for g, c in docs.items() if c >= min_impact}
    keep = {g for g in ok if mine_candidate(g, lang)}
    left, right, whole, init_name, surf, occ, ex_long, ex_name = mine_context(parsed, keep, max_n, lang)
    rows = []

    for g in keep:
        f = docs[g]
        rows.append({
            'gram': g, 'n': len(g), 'freq': f, 'long': f - namec[g], 'name': namec[g],
            'mi': mine_mi(g, docs, len(parsed)),
            'hmin': mine_hmin(left[g], right[g], whole[g], init_name[g]),
            'example': (ex_long.get(g) or ex_name.get(g) or '')[:MINE_EX_LEN],
            'surface': mine_surface(surf.get(g), MINE_LANG[lang]['join'].join(g)),
        })

    return rows, {'left': left, 'right': right, 'occ': occ, 'stopped': len(ok) - len(keep)}


def drop_substrings(rows):
    sup = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in rows:
        g = r['gram']
        for m in range(1, len(g)):
            for i in range(len(g) - m + 1):
                sup[r['freq']][g[i:i + m]].add(g)

    return [r for r in rows if not sup[r['freq']].get(r['gram'])]


def mine_window(rows, ent_thr, left, right, occ):
    cand = {r['gram']: r for r in rows}
    ends = {g: occ[g] - sum((right.get(g) or {}).values()) for g in occ}

    def whole(g):
        return cand[g]['hmin'] > ent_thr and ends[g] > 0

    merged, suspect, promote = {}, [], {}
    for r in rows:
        g = r['gram']
        if len(g) < 2 or r['hmin'] <= ent_thr:
            continue
        ext = {x: n for x, n in left[g].items() if (x,) + g in cand}
        conf = {x: n for x, n in ext.items() if (x,) + g[:1] in cand and cand[(x,) + g[:1]]['hmin'] > ent_thr}
        free = occ[g] - sum(ext.values())
        if len(conf) >= 2 and free == 0:
            merged[g] = conf
            promote.update({(x,) + g: cand[(x,) + g] for x in conf if whole((x,) + g)})
        elif len(ext) >= 2:
            suspect.append(g)

    return merged, suspect, {g: r for g, r in promote.items() if g not in merged}


class SpecLexicon:
    def __init__(self, parsed):
        self.tot = collections.Counter()
        self.med = collections.Counter()
        self.det = collections.Counter()

        for _, _, clauses in parsed:
            for _, ws in clauses:
                low = [w.lower() for w in ws]
                for i, w in enumerate(low):
                    self.tot[w] += 1
                    if i and ws[i][:1].isupper():
                        self.med[w] += 1
                    if i and low[i - 1] in DET_WORDS:
                        self.det[w] += 1

        total = sum(self.tot.values()) or 1
        self.delta = {w: math.log2(c / total) - (zipf_frequency(w, 'en') - 9) * math.log2(10)
                      for w, c in self.tot.items()}

    def cap_ratio(self, w):
        return self.med[w] / self.tot[w] if self.tot[w] else 0.0

    def det_ratio(self, w):
        return self.det[w] / self.tot[w] if self.tot[w] else 0.0

    def termish(self, w):
        if len(w) < 3 or self.tot[w] < 3:
            return False
        z = zipf_frequency(w, 'en')
        if z <= INVENTED_ZIPF:
            return not w.endswith('ly') and max(self.cap_ratio(w), self.det_ratio(w)) >= CAP_RATIO

        return self.cap_ratio(w) >= 0.5 and z <= COMMON_ZIPF


def mine_terms_specificity(rows, lexicon, min_n):
    bad_mi = {r['gram'] for r in rows if r['n'] >= 2 and r['mi'] < MINE_MI_ABS}
    bad_ent = {r['gram'] for r in rows if r['hmin'] < MINE_ENT_ABS}
    kept = []

    for r in rows:
        g = r['gram']
        if not any(lexicon.termish(w) for w in g):
            continue
        if len(g) > 1 and any(w in PRONOUNS for w in g):
            continue
        if len(g) > 1 and lexicon.det_ratio(g[-1]) < NOUN_DET_RATIO:
            continue
        if g in bad_mi or g in bad_ent:
            continue
        kept.append(r)

    pre_sub = len(kept)
    kept = [r for r in kept if len(r['surface']) >= min_n]
    kept.sort(key=lambda r: (-r['freq'], -r['n'], -r['mi'], r['gram']))
    stats = {
        'cand': len(rows), 'kept': len(kept), 'pre_sub': pre_sub,
        'mi_thr': MINE_MI_ABS, 'ent_thr': MINE_ENT_ABS,
        'unconstrained': sum(1 for r in rows if r['hmin'] == math.inf),
        'bad_mi': len(bad_mi), 'bad_ent': len(bad_ent), 'both': len(bad_mi & bad_ent),
        'stopped': 0, 'merged': {}, 'suspect': [], 'promote': [],
        'min_n': min_n, 'thin': 0, 'termhood': 'specificity',
    }

    return kept, stats


def mine_terms(parsed, max_n=MINE_N_MAX, min_impact=2, pct_coh=MINE_PCT_COH,
               pct_ent=MINE_PCT_ENT, use_entropy=True, lang='en', min_n=1,
               termhood='self', lexicon=None):
    rows, ctx = mine_scores(parsed, max_n, min_impact, lang)

    if termhood == 'specificity':
        return mine_terms_specificity(rows, lexicon, min_n)

    mi_thr = percentile([r['mi'] for r in rows if r['n'] >= 2], pct_coh)
    finite = [r['hmin'] for r in rows if r['hmin'] != math.inf]
    ent_thr = percentile(finite, pct_ent) if use_entropy else 0.0
    bad_mi = {r['gram'] for r in rows if r['n'] >= 2 and r['mi'] <= mi_thr}
    bad_ent = {r['gram'] for r in rows if use_entropy and r['hmin'] <= ent_thr}
    merged, suspect, promote = ({}, [], {})

    if MINE_LANG[lang]['cjk']:
        merged, suspect, promote = mine_window(rows, ent_thr, ctx['left'], ctx['right'], ctx['occ'])

    kept = [r for r in rows if r['gram'] not in merged and r['gram'] not in bad_mi and r['gram'] not in bad_ent]
    pre_sub = len(kept)
    kept = drop_substrings(kept)
    have = {r['gram'] for r in kept}
    kept += [r for g, r in promote.items() if g not in have]
    thin = len(kept)
    kept = [r for r in kept if len(r['surface']) >= min_n]
    kept.sort(key=lambda r: (-r['freq'], -r['n'], -r['mi'], r['gram']))
    stats = {
        'cand': len(rows), 'kept': len(kept), 'pre_sub': pre_sub,
        'mi_thr': mi_thr, 'ent_thr': ent_thr,
        'unconstrained': len(rows) - len(finite),
        'bad_mi': len(bad_mi), 'bad_ent': len(bad_ent),
        'both': len(bad_mi & bad_ent), 'stopped': ctx['stopped'],
        'merged': merged, 'suspect': suspect, 'min_n': min_n,
        'thin': thin - len(kept), 'promote': [g for g in promote if g not in have],
        'termhood': 'self',
    }

    return kept, stats


def mine_coverage(parsed, rows, max_n):
    terms = {r['gram'] for r in rows}
    multi = {g for g in terms if len(g) > 1}
    n_all = n_multi = l_all = l_multi = nm_all = nm_multi = 0

    for _, is_name, clauses in parsed:
        hit = hitm = False
        for _, ws in clauses:
            low = [w.lower() for w in ws]
            for n in range(1, min(max_n, len(low)) + 1):
                for i in range(len(low) - n + 1):
                    g = tuple(low[i:i + n])
                    if g in terms:
                        hit = True
                        hitm = hitm or g in multi
        if is_name:
            nm_all += hit
            nm_multi += hitm
        else:
            l_all += hit
            l_multi += hitm
        n_all += hit
        n_multi += hitm

    return {'all': n_all, 'multi': n_multi, 'long': l_all, 'long_multi': l_multi,
            'name': nm_all, 'name_multi': nm_multi}


def median_value_len(data):
    lens = sorted(len(v) for v in data.values() if isinstance(v, str) and v)

    return lens[len(lens) // 2] if lens else 0


def resolve_termhood(termhood, data, lang):
    if termhood == 'auto':
        termhood = 'specificity' if median_value_len(data) >= PROSE_MED_LEN else 'self'

    if termhood == 'specificity':
        if lang != 'en':
            raise SystemExit('术语度 specificity 只支持 en（wordfreq 只有英语频率）')
        if zipf_frequency is None:
            raise SystemExit('术语度 specificity 需要 wordfreq：pip install wordfreq')

    return termhood


def _ref_map_from_input(path_or_dir, ref_lang, en_col=None, zh_col=None,
                        key_filter='off', keys=None, exclude_keys=None, filter_file=None):
    p = Path(path_or_dir)
    if p.is_dir():
        ref_path = io.find_lang_file(p, MINE_LANG[ref_lang]['file'])
        if not ref_path:
            raise SystemExit(f"缺少 {MINE_LANG[ref_lang]['file']}.json / .lang：{p}")
        return io.load_lang_file(ref_path)

    raw = io.load_input_rows(p, en_col=en_col, zh_col=zh_col)
    filtered = io.filter_rows(raw, key_filter=key_filter, keys=keys, exclude_keys=exclude_keys, filter_file=filter_file)
    if MINE_LANG[ref_lang]['cjk']:
        return {k: zh for k, _, zh in filtered if zh}

    return {k: en for k, en, _ in filtered if en}


def _primary_map_from_input(path_or_dir, lang, en_col=None, zh_col=None,
                            key_filter='off', keys=None, exclude_keys=None, filter_file=None):
    p = Path(path_or_dir)
    spec = MINE_LANG[lang]
    if p.is_dir():
        src_path = io.find_lang_file(p, spec['file'])
        if not src_path:
            raise SystemExit(f"缺少 {spec['file']}.json / .lang：{p}")
        return io.load_lang_file(src_path)

    raw = io.load_input_rows(p, en_col=en_col, zh_col=zh_col)
    filtered = io.filter_rows(raw, key_filter=key_filter, keys=keys, exclude_keys=exclude_keys, filter_file=filter_file)
    if spec['cjk']:
        return {k: (zh or en) for k, en, zh in filtered if (zh or en)}

    return {k: en for k, en, _ in filtered if en}


def _align_en_to_zh(term_en, pairs, ref_subdf):
    toks = tuple(io.tokens_lc(term_en))
    if not toks:
        return [], 0

    pat = re.compile(r'\b' + r'\s+'.join(re.escape(t) for t in toks) + r'\b', re.I)
    matched = [zh for en, zh in pairs if pat.search(en)]
    total = len(matched)
    if not total:
        return [], 0

    sub_counts = collections.Counter()
    for zh in matched:
        subs = set()
        for run in io.CJK_RE.findall(zh):
            for i in range(len(run)):
                for j in range(i + 2, min(len(run), i + 7) + 1):
                    subs.add(run[i:j])
        for s in subs:
            sub_counts[s] += 1

    scored = []
    for s, c in sub_counts.items():
        if total >= 2 and c < 2:
            continue
        dice = 2.0 * c / (total + ref_subdf.get(s, c))
        scored.append((dice, c, len(s), s))
    scored.sort(reverse=True)

    chosen = []
    for dice, c, _, s in scored:
        if any(s in kept for kept, _, _ in chosen):
            continue
        chosen.append((s, c, round(dice, 3)))
        if len(chosen) >= 3:
            break

    return chosen, total


def _build_zh_subdf(pairs):
    subdf = collections.Counter()
    for _, zh in pairs:
        subs = set()
        for run in io.CJK_RE.findall(zh):
            for i in range(len(run)):
                for j in range(i + 2, min(len(run), i + 7) + 1):
                    subs.add(run[i:j])
        for s in subs:
            subdf[s] += 1

    return subdf


def _anchor_cjk_to_en(gram, pairs):
    term = ''.join(gram)
    cnt, total = collections.Counter(), 0

    for val, other in pairs:
        if term in val:
            total += 1
            cnt.update(w for w in norm_en(other) if w not in STOPWORDS and not w.isdigit())

    if not cnt:
        return '', 0, 0, []

    top = cnt.most_common(3)

    return top[0][0], top[0][1], total, top[1:]


def fmt_h(v):
    return f'{v:.2f}' if v != math.inf else '∞'


def run_mine(args):
    t0 = time.time()
    lang_key = mine_lang_key(args.lang, args.ko_unit)
    spec = MINE_LANG[lang_key]
    data = _primary_map_from_input(
        args.input, lang_key,
        en_col=getattr(args, 'en_col', None),
        zh_col=getattr(args, 'zh_col', None),
        key_filter=getattr(args, 'key_filter', 'off'),
        keys=getattr(args, 'keys', None),
        exclude_keys=getattr(args, 'exclude_keys', None),
        filter_file=getattr(args, 'filter_file', None),
    )

    max_n = spec['max_n'] if args.max_n is None else args.max_n
    min_n = spec['min_n'] if args.min_n is None else args.min_n
    parsed = mine_entries(data, max_n, lang_key)
    termhood = resolve_termhood(args.termhood, data, lang_key)
    lexicon = SpecLexicon(parsed) if termhood == 'specificity' else None
    rows, stats = mine_terms(parsed, max_n, args.min_impact, args.pct_coh,
                             args.pct_ent, not args.no_entropy, lang_key, min_n,
                             termhood, lexicon)

    known, _ = io.known_pairs(getattr(args, 'known', None))
    skipped_known = 0
    if known:
        kept_rows = []
        for r in rows:
            if io.is_known_term(r['surface'], known):
                skipped_known += 1
                continue
            kept_rows.append(r)
        rows = kept_rows

    if getattr(args, 'focus', None):
        focus = io.load_focus_keys(args.focus)
        focus_parsed = [item for item in parsed if item[0] in focus]
        focus_grams = set()
        for _, _, clauses in focus_parsed:
            for _, ws in clauses:
                low = [w.lower() for w in ws]
                for n in range(1, min(max_n, len(low)) + 1):
                    for i in range(len(low) - n + 1):
                        focus_grams.add(tuple(low[i:i + n]))
        rows = [r for r in rows if r['gram'] in focus_grams]

    pairs = []
    ref_subdf = None
    if args.ref:
        ref_data = _ref_map_from_input(
            args.input, args.ref,
            en_col=getattr(args, 'en_col', None),
            zh_col=getattr(args, 'zh_col', None),
            key_filter=getattr(args, 'key_filter', 'off'),
            keys=getattr(args, 'keys', None),
            exclude_keys=getattr(args, 'exclude_keys', None),
            filter_file=getattr(args, 'filter_file', None),
        )
        pairs = [(v, ref_data[k]) for k, v in data.items() if isinstance(v, str) and isinstance(ref_data.get(k), str)]
        if not spec['cjk']:
            ref_subdf = _build_zh_subdf(pairs)

    cov = mine_coverage(parsed, rows, max_n)
    sec = f'{time.time() - t0:.1f}s'
    chars = sum(len(spec['join'].join(c for c, _ in cl)) for _, k, cl in parsed if not k)
    limit_rows = rows[:args.limit] if getattr(args, 'limit', 0) else rows

    out_records = []
    for r in limit_rows:
        rec = {
            'term': r['surface'], 'n': r['n'], 'impact': r['freq'],
            'long': r['long'], 'name': r['name'],
            'mi': None if r['mi'] == math.inf else round(r['mi'], 3),
            'hmin': None if r['hmin'] == math.inf else round(r['hmin'], 3),
            'example': ' '.join(r['example'].split()),
        }
        if args.ref and spec['cjk']:
            ref_word, votes, tot, _ = _anchor_cjk_to_en(r['gram'], pairs)
            rec['ref'] = ref_word
            rec['ref_votes'] = votes
            rec['ref_total'] = tot
        elif args.ref:
            cands, tot = _align_en_to_zh(r['surface'], pairs, ref_subdf)
            rec['ref'] = '|'.join(c[0] for c in cands)
            rec['ref_votes'] = cands[0][1] if cands else 0
            rec['ref_total'] = tot
        out_records.append(rec)

    summary = {
        'lang': args.lang, 'ref': args.ref, 'termhood': termhood,
        'entries': len(parsed), 'terms': len(limit_rows),
        'skipped_known': skipped_known, 'cov': cov, 'sec': round(time.time() - t0, 3),
    }

    fmt = getattr(args, 'format', 'tsv')
    out_prefix = getattr(args, 'out', None)
    if out_prefix and fmt == 'both':
        tsv_path = str(out_prefix) + '-mine.tsv'
        md_path = str(out_prefix) + '-mine.md'
        _write_mine_tsv(tsv_path, out_records, bool(args.ref))
        _write_mine_md(md_path, args.input, parsed, out_records, stats, cov, args.top, sec, chars, lang_key, bool(args.ref))
        summary['tsv'] = tsv_path
        summary['md'] = md_path
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    out_file = getattr(args, 'out_file', None)
    if fmt == 'json':
        text = json.dumps({'summary': summary, 'terms': out_records}, ensure_ascii=False, indent=2) + '\n'
        if out_file:
            io.write_text(out_file, text)
        else:
            sys.stdout.write(text)
    elif fmt == 'md':
        lines = _mine_md_lines(args.input, parsed, out_records, stats, cov, args.top, sec, chars, lang_key, bool(args.ref))
        text = '\n'.join(lines) + '\n'
        if out_file:
            io.write_text(out_file, text)
        else:
            sys.stdout.write(text)
    else:
        head = ['term', 'n', 'impact', 'long', 'name', 'mi', 'hmin'] + (['ref', 'ref_votes', 'ref_total'] if args.ref else []) + ['example']
        table = [
            [r['term'], r['n'], r['impact'], r['long'], r['name'],
             '∞' if r['mi'] is None else f"{r['mi']:.2f}",
             '∞' if r['hmin'] is None else f"{r['hmin']:.2f}"]
            + ([r.get('ref', ''), r.get('ref_votes', 0), r.get('ref_total', 0)] if args.ref else [])
            + [r['example']]
            for r in out_records
        ]
        if out_file:
            io.ensure_parent(out_file)
            with open(out_file, 'w', encoding='utf-8', newline='') as f:
                io.write_tsv(f, head, table)
        else:
            sys.stdout.reconfigure(newline='')
            io.write_tsv(sys.stdout, head, table)

    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    return 0


def _write_mine_tsv(path, records, has_ref):
    head = ['term', 'n', 'impact', 'long', 'name', 'mi', 'hmin'] + (['ref', 'ref_votes', 'ref_total'] if has_ref else []) + ['example']
    rows = [
        [r['term'], r['n'], r['impact'], r['long'], r['name'],
         '∞' if r['mi'] is None else f"{r['mi']:.2f}",
         '∞' if r['hmin'] is None else f"{r['hmin']:.2f}"]
        + ([r.get('ref', ''), r.get('ref_votes', 0), r.get('ref_total', 0)] if has_ref else [])
        + [r['example']]
        for r in records
    ]
    io.ensure_parent(path)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        io.write_tsv(f, head, rows)


def _mine_md_lines(src, parsed, records, stats, cov, top, sec, chars, lang, has_ref):
    n_name = sum(1 for _, k, _ in parsed if k)
    lines = [
        f'# 全文本术语挖掘（语言 {MINE_LANG[lang]["label"]}）',
        '',
        f'- 来源：`{src}`',
        f'- 条目 {len(parsed)} 条：名字型 {n_name} / 长文本 {len(parsed) - n_name}（长文本 {chars} 字）',
        f'- 策略：{stats.get("termhood", "self")}，候选 {stats["cand"]} → 产出 {len(records)} 个（用时 {sec}）',
        f'- 覆盖：{cov["all"]}/{len(parsed)} 条（{100.0 * cov["all"] / max(1, len(parsed)):.1f}%）',
        '',
    ]
    head = '| 术语 | 影响条目 | 长文本 | 名字 | 最小互信息 | 最小边界熵 |' + (' 对照候选 |' if has_ref else '') + ' 例句 |'
    rule = '|---|---:|---:|---:|---:|---:|' + ('---|' if has_ref else '') + '---|'
    lines += [head, rule]
    shown = records[:top] if top else records

    for r in shown:
        mi_s = '∞' if r['mi'] is None else f"{r['mi']:.2f}"
        h_s = '∞' if r['hmin'] is None else f"{r['hmin']:.2f}"
        ref_cell = f" {r.get('ref') or '—'} ({r.get('ref_votes', 0)}/{r.get('ref_total', 0)}) |" if has_ref else ''
        ex_cell = (r['example'] or '—').replace('|', '/')
        lines.append(f"| {r['term']} | {r['impact']} | {r['long']} | {r['name']} | {mi_s} | {h_s} |{ref_cell} {ex_cell} |")

    return lines


def _write_mine_md(path, src, parsed, records, stats, cov, top, sec, chars, lang, has_ref):
    io.write_text(path, '\n'.join(_mine_md_lines(src, parsed, records, stats, cov, top, sec, chars, lang, has_ref)) + '\n')


def harvest(group, votes, stats, seen):
    toks = set(g[0] for g in group)
    if len(group) < 2 or len(toks) < 2:
        stats['small'] += 1
        return

    pre = suf = None
    for g in group:
        z = g[1]
        pre = z if pre is None else lcp(pre, z)
        suf = z if suf is None else lcs(suf, z)
        if not pre and not suf:
            break

    if not pre and not suf:
        stats['noctx'] += 1
        return

    pairs = []
    for t, z, m in group:
        if len(z) < len(pre) + len(suf):
            continue
        mid = z[len(pre):len(z) - len(suf)]
        if mid and CJK.search(mid) and len(mid) <= 12 and not LAT.search(mid):
            pairs.append((t, mid, m))

    if len(set(p[1] for p in pairs)) > len(toks):
        stats['ambig'] += 1
        return

    t2m = {}
    for t, m, _ in pairs:
        if t2m.get(t, m) != m:
            stats['notfun'] += 1
            return
        t2m[t] = m

    if len(t2m) < 2:
        stats['small2'] += 1
        return

    stats['ok'] += 1
    for t, m, mm in pairs:
        k = (mm, t, m)
        if k in seen:
            continue
        seen.add(k)
        votes[t][m] += 1


def mine_pairs(rows, stats=None):
    groups = collections.defaultdict(list)
    for modid, toks, z in rows:
        if len(toks) < 2 or len(toks) > 9:
            continue
        for i in range(len(toks)):
            sk = (tuple(toks[:i]), tuple(toks[i + 1:]))
            groups[sk].append((toks[i], z, modid))

    votes = collections.defaultdict(collections.Counter)
    st = stats if stats is not None else collections.Counter()
    seen = set()

    for g in groups.values():
        if len(g) >= 2:
            harvest(g, votes, st, seen)

    return votes, st


def run_review(args):
    raw_rows = io.load_input_rows(args.input, en_col=getattr(args, 'en_col', None), zh_col=getattr(args, 'zh_col', None))
    rows = io.filter_rows(
        raw_rows,
        key_filter=getattr(args, 'key_filter', 'off'),
        keys=getattr(args, 'keys', None),
        exclude_keys=getattr(args, 'exclude_keys', None),
        filter_file=getattr(args, 'filter_file', None),
    )
    focus = io.load_focus_keys(args.focus) if getattr(args, 'focus', None) else None

    by_en = collections.defaultdict(collections.Counter)
    ex = collections.defaultdict(list)
    bilingual = []

    for key, e, z in rows:
        z_clean = norm_zh(z)
        if not e.strip() or not z_clean:
            continue
        bilingual.append((key, e, z_clean))
        by_en[e][z_clean] += 1
        if len(ex[(e, z_clean)]) < 2:
            ex[(e, z_clean)].append(key)

    same_src_div = []
    for e, c in by_en.items():
        if len(c) < 2 or sum(c.values()) < args.min_impact:
            continue
        if focus is not None and not any(k in focus for v in c for k in ex[(e, v)]):
            continue
        same_src_div.append({
            'en': e,
            'total': sum(c.values()),
            'variants': [{'zh': v, 'count': n, 'keys': ex[(e, v)]} for v, n in c.most_common(5)],
        })
    same_src_div.sort(key=lambda x: (-x['total'], x['en']))

    frame_rows = [('corpus', norm_en(e), z) for _, e, z in bilingual if CJK.search(z)]
    votes, _ = mine_pairs(frame_rows)
    slot_div = []
    for t, c in votes.items():
        if len(c) < 2 or sum(c.values()) < args.min_impact:
            continue
        examples = []
        for v, _ in c.most_common(3):
            for key, e, z in bilingual:
                if (focus is None or key in focus) and t in norm_en(e) and v in z:
                    examples.append({'key': key, 'en': e, 'zh': z, 'variant': v})
                    break
        if focus is not None and not examples:
            continue
        slot_div.append({
            'token': t,
            'variants': [{'zh': v, 'count': n} for v, n in c.most_common(5)],
            'examples': examples,
        })
    slot_div.sort(key=lambda x: (-sum(v['count'] for v in x['variants']), x['token']))

    known_violations = []
    known_entries, _ = io.load_glossary_entries(getattr(args, 'known', None))
    if known_entries:
        matcher = io.build_term_matcher(known_entries)
        for key, e, z in bilingual:
            if focus is not None and key not in focus:
                continue
            for hit in io.match_known_in_row(e, z, matcher):
                if not hit['ok']:
                    known_violations.append({
                        'key': key, 'en': e, 'zh': z,
                        'term': hit['en'], 'expected': '|'.join(hit['zh']), 'reason': hit['reason'],
                    })

    summary = {
        'rows': len(rows), 'bilingual': len(bilingual),
        'same_source_divergence': len(same_src_div),
        'slot_divergence': len(slot_div),
        'known_violations': len(known_violations),
    }

    fmt = getattr(args, 'format', 'md')
    out_path = getattr(args, 'out', None)
    if fmt == 'json':
        payload = json.dumps({
            'summary': summary,
            'same_source_divergence': same_src_div[:args.top] if args.top else same_src_div,
            'slot_divergence': slot_div[:args.top] if args.top else slot_div,
            'known_violations': known_violations[:args.top] if args.top else known_violations,
        }, ensure_ascii=False, indent=2) + '\n'
        if out_path:
            io.write_text(out_path, payload)
        else:
            sys.stdout.write(payload)
    elif fmt == 'tsv':
        table = []
        for item in same_src_div[:args.top] if args.top else same_src_div:
            var_s = ' / '.join(f"{v['zh']}({v['count']})" for v in item['variants'])
            table.append(['same_source', item['en'], var_s, item['variants'][0]['keys'][0], ''])
        for item in slot_div[:args.top] if args.top else slot_div:
            var_s = ' / '.join(f"{v['zh']}({v['count']})" for v in item['variants'])
            ex_k = item['examples'][0]['key'] if item['examples'] else ''
            table.append(['slot_frame', item['token'], var_s, ex_k, ''])
        for item in known_violations[:args.top] if args.top else known_violations:
            table.append(['known_violation', item['term'], item['expected'], item['key'], item['zh']])
        if out_path:
            io.ensure_parent(out_path)
            with open(out_path, 'w', encoding='utf-8', newline='') as f:
                io.write_tsv(f, ['kind', 'term_or_en', 'variants_or_expected', 'key', 'zh'], table)
        else:
            sys.stdout.reconfigure(newline='')
            io.write_tsv(sys.stdout, ['kind', 'term_or_en', 'variants_or_expected', 'key', 'zh'], table)
    else:
        lines = [
            f'# 译文分歧与术语校对报告：{args.input}',
            f'- 条目 {len(rows)} 条，有效双语 {len(bilingual)} 条',
            '',
            f'## 同一英文，多种译法：{len(same_src_div)} 组',
        ]
        for item in (same_src_div[:args.top] if args.top else same_src_div):
            var_s = ' / '.join(f"{v['zh']}({v['count']})" for v in item['variants'][:3])
            lines.append(f"- `{item['en']}`（{item['total']} 条）：{var_s}")
            for v in item['variants'][:2]:
                lines.append(f"  - `{v['keys'][0]}` = {v['zh']}")

        lines += ['', f'## 同一名字骨架，变动词多种译法：{len(slot_div)} 个']
        for item in (slot_div[:args.top] if args.top else slot_div):
            var_s = ' / '.join(f"{v['zh']}({v['count']})" for v in item['variants'][:3])
            lines.append(f"- `{item['token']}`：{var_s}")
            for e in item['examples'][:2]:
                lines.append(f"  - `{e['key']}` = {e['zh']}")

        if known_entries:
            lines += ['', f'## 已知术语违例/未命中：{len(known_violations)} 条']
            for item in (known_violations[:args.top] if args.top else known_violations):
                reason_s = f"（{item['reason']}）" if item['reason'] else ''
                lines.append(f"- `{item['key']}`：`{item['term']}` 期望 `{item['expected']}`{reason_s} | 实际：`{item['zh']}`")

        text = '\n'.join(lines) + '\n'
        if out_path:
            io.write_text(out_path, text)
        else:
            sys.stdout.write(text)

    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    return 0


def run_maintain_prose(args):
    raw_rows = io.load_input_rows(args.input, en_col=getattr(args, 'en_col', None), zh_col=getattr(args, 'zh_col', None))
    rows = io.filter_rows(
        raw_rows,
        key_filter=getattr(args, 'key_filter', 'off'),
        keys=getattr(args, 'keys', None),
        exclude_keys=getattr(args, 'exclude_keys', None),
        filter_file=getattr(args, 'filter_file', None),
    )
    focus = io.load_focus_keys(args.focus) if getattr(args, 'focus', None) else None
    en_map = {k: en for k, en, _ in rows if en.strip()}
    zh_map = {k: zh for k, _, zh in rows if zh.strip()}
    pairs = [(en_map[k], zh_map[k]) for k in en_map if k in zh_map]
    ref_subdf = _build_zh_subdf(pairs)

    parsed = mine_entries(en_map, args.max_n or MINE_N_MAX, 'en')
    termhood = resolve_termhood(args.termhood, en_map, 'en')
    lexicon = SpecLexicon(parsed) if termhood == 'specificity' else None
    mined, stats = mine_terms(
        parsed, args.max_n or MINE_N_MAX, args.min_impact,
        args.pct_coh, args.pct_ent, not args.no_entropy, 'en',
        args.min_n or 1, termhood, lexicon,
    )

    known, _ = io.known_pairs(getattr(args, 'known', None))
    out_rows = []
    for r in mined:
        if focus is not None:
            toks = r['gram']
            pat = re.compile(r'\b' + r'\s+'.join(re.escape(t) for t in toks) + r'\b', re.I)
            if not any(k in focus and pat.search(en_map[k]) for k in en_map):
                continue
        cands, total = _align_en_to_zh(r['surface'], pairs, ref_subdf)
        cand_zh = [c[0] for c in cands]
        lemma = io.norm_lemma(r['surface'])
        if lemma in known:
            extra = [z for z in cand_zh if z not in known[lemma]]
            status = 'variant_or_exception' if extra else 'known_consistent'
            if status == 'known_consistent' and not getattr(args, 'include_known', False):
                continue
        else:
            status = 'new_candidate'
        out_rows.append({
            'en': r['surface'],
            'zh': '|'.join(cand_zh),
            'status': status,
            'impact': r['freq'],
            'aligned_rows': total,
            'known_zh': '|'.join(known.get(lemma, [])),
            'example': ' '.join(r['example'].split()),
        })

    out_file = getattr(args, 'out', None)
    fmt = getattr(args, 'format', 'tsv')
    summary = {'rows': len(rows), 'pairs': len(pairs), 'termhood': termhood, 'emitted': len(out_rows)}
    if fmt == 'json':
        text = json.dumps({'summary': summary, 'terms': out_rows}, ensure_ascii=False, indent=2) + '\n'
        if out_file:
            io.write_text(out_file, text)
        else:
            sys.stdout.write(text)
    else:
        table = [[r['en'], r['zh'], r['status'], r['impact'], r['aligned_rows'], r['known_zh'], r['example']] for r in out_rows]
        head = ['en', 'zh', 'status', 'impact', 'aligned_rows', 'known_zh', 'example']
        if out_file:
            io.ensure_parent(out_file)
            with open(out_file, 'w', encoding='utf-8', newline='') as f:
                io.write_tsv(f, head, table)
        else:
            sys.stdout.reconfigure(newline='')
            io.write_tsv(sys.stdout, head, table)
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)
    return 0

def add_mine_args(m):
    m.add_argument('--input', '--lang-dir', dest='input', type=Path, required=True, help='lang 目录或 TSV/JSON 文件')
    m.add_argument('--lang', choices=MINE_LANGS, default='en')
    m.add_argument('--ref', choices=MINE_LANGS, help='对照语言（双语对齐候选译法）')
    m.add_argument('--en-col')
    m.add_argument('--zh-col')
    m.add_argument('--key-filter', choices=('on', 'off', 'auto'), default='off')
    m.add_argument('--keys')
    m.add_argument('--exclude-keys')
    m.add_argument('--filter-file', type=Path)
    m.add_argument('--focus', type=Path)
    m.add_argument('--known', nargs='*', default=[])
    m.add_argument('--max-n', type=int, default=None)
    m.add_argument('--min-n', type=int, default=None)
    m.add_argument('--ko-unit', choices=('eojeol', 'syllable'), default='eojeol')
    m.add_argument('--min-impact', type=int, default=2)
    m.add_argument('--pct-coh', type=float, default=MINE_PCT_COH)
    m.add_argument('--pct-ent', type=float, default=MINE_PCT_ENT)
    m.add_argument('--no-entropy', action='store_true')
    m.add_argument('--termhood', choices=TERMHOODS, default='auto')
    m.add_argument('--limit', type=int, default=0)
    m.add_argument('--top', type=int, default=300)
    m.add_argument('--format', choices=('tsv', 'json', 'md', 'both'), default='tsv')
    m.add_argument('-o', '--out-file', dest='out_file', type=Path, help='单文件输出路径')
    m.add_argument('--out-prefix', dest='out', help='both 模式输出前缀')


def add_review_args(r):
    r.add_argument('--input', '--lang-dir', dest='input', type=Path, required=True, help='lang 目录或双语 TSV/JSON 文件')
    r.add_argument('--en-col')
    r.add_argument('--zh-col')
    r.add_argument('--key-filter', choices=('on', 'off', 'auto'), default='off')
    r.add_argument('--keys')
    r.add_argument('--exclude-keys')
    r.add_argument('--filter-file', type=Path)
    r.add_argument('--focus', type=Path)
    r.add_argument('--known', nargs='*', default=[])
    r.add_argument('--top', type=int, default=50)
    r.add_argument('--min-impact', type=int, default=2)
    r.add_argument('--format', choices=('md', 'tsv', 'json'), default='md')
    r.add_argument('-o', '--out', type=Path)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='final.py prose')
    sub = ap.add_subparsers(dest='cmd', required=True)
    m = sub.add_parser('mine')
    add_mine_args(m)
    m.set_defaults(func=run_mine)
    r = sub.add_parser('review')
    add_review_args(r)
    r.set_defaults(func=run_review)
    args = ap.parse_args(argv)

    return args.func(args)
