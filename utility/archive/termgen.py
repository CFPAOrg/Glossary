#!/usr/bin/env python3
import argparse
import csv
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict

try:
    import inflection
except Exception:
    inflection = None
try:
    from wordfreq import zipf_frequency
except Exception:
    def zipf_frequency(word, lang='en'):
        return 5.0

CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+')
ASCII_RUN_RE = re.compile(r'[A-Za-z]+')
FORMAT_RE = re.compile(r'%(\d+\$)?[sdf]|%%|\{[^}]*\}|§.|\\n|\\t|\\r')
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
NAME_CHARS_RE = re.compile(r"[A-Za-z0-9'’\-\s]+$")
NAME_BAD_RE = re.compile(r"[.!?…:;,()\[\]{}\"“”«»/\\|<>+=*#@$^~`]")
STOP = set("""a an the and or but if then than that this these those of to in on at for with from by as
is are was were be been being am do does did not no nor you your yours we our ours us it its he she they
them their his her my me i will would can could should shall may might must have has had here there when
where which who whom what how why all any some more most other such only own same so too very just also up
down out off over under again further once during before after above below between into through about
against while both each few because until unless upon onto within without across around""".split())
LEAD_OK = {'the'}
MAXN = 5
MAX_NAME_TOKENS = 7

KEEP_SCORE = 0.85
ZIPF_GATE = 5.0
ZIPF_SCOPE = 'label'
REVIEW_SCORE = 0.30
COHESION_CMP = 0.05
COHESION_MI = 6.0
KEY_FILTER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'Vanilla', 'diffs', 'term-key-filters.json')


def clean_en(s):
    s = FORMAT_RE.sub(' ', s)
    s = s.replace('’', "'").replace('\u00a0', ' ')
    return ' '.join(s.split())


def clean_zh(s):
    s = FORMAT_RE.sub(' ', s)
    return ' '.join(s.split())


def tokens_lc(s):
    return [t.lower() for t in TOKEN_RE.findall(s)]


def raw_tokens(s):
    return TOKEN_RE.findall(s)


def token_ok(w):
    if w.lower() in STOP:
        return True
    if any(c.isdigit() for c in w):
        return True
    if len(w) == 1:
        return True
    if w.isupper():
        return True
    return w[0].isupper()


def is_name_like(s):
    if not s or len(s) > 80:
        return False
    if NAME_BAD_RE.search(s):
        return False
    if not NAME_CHARS_RE.match(s):
        return False
    rt = raw_tokens(s)
    if not rt or len(rt) > MAX_NAME_TOKENS:
        return False
    low = [t.lower() for t in rt]
    if low[0] in STOP and low[0] not in LEAD_OK:
        return False
    if not any(w[0].isupper() or w.isupper() for w in rt):
        return False
    for w in rt:
        if not token_ok(w):
            return False
    nstop = sum(1 for w in low if w in STOP)
    if len(rt) >= 5 and nstop >= 2:
        return False
    return True


def norm_lemma(s):
    s = s.lower().replace('’', "'")
    s = re.sub(r"[^a-z0-9' ]+", ' ', s)
    s = re.sub(r"'s\b", '', s)
    out = []
    for w in s.split():
        if inflection is not None and len(w) > 3 and w.isalpha():
            try:
                w = inflection.singularize(w)
            except Exception:
                pass
        out.append(w)
    return ' '.join(out)


def load_key_filter():
    with open(KEY_FILTER_PATH, encoding='utf-8') as f:
        data = json.load(f)
    wl = [re.compile(p) for p in data.get('whitelist_patterns', [])]
    bl = [re.compile(p) for p in data.get('blacklist_patterns', [])]
    return wl, bl


def is_product_key(key, wl, bl):
    if not key:
        return False
    if any(p.search(key) for p in bl):
        return False
    return any(p.search(key) for p in wl)


def load_known(paths):
    known = {}
    for path in paths or []:
        with open(path, encoding='utf-8', newline='') as f:
            for r in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                if len(r) < 2:
                    continue
                en = clean_en(r[0])
                if not en or en.lower() == 'en':
                    continue
                key = tuple(tokens_lc(en))
                if not key:
                    continue
                variants = [clean_zh(v) for v in r[1].split('|') if clean_zh(v)]
                if variants:
                    known.setdefault(key, [])
                    for v in variants:
                        if v not in known[key]:
                            known[key].append(v)
    return known


class Corpus:
    def __init__(self):
        self.rows = []
        self.docs = {}
        self.input_ens = set()
        self.input_pairs = set()
        self.pair_list = []
        self.char_post = defaultdict(set)
        self.zh_subs_cache = {}
        self.sub_pids_cache = {}

    def add_rows(self, rows):
        for (key, en, zh) in rows:
            en = clean_en(en)
            zh = clean_zh(zh)
            if not en and not zh:
                continue
            self.rows.append((key, en, zh))
            doc = self.docs.get(en)
            if doc is None:
                doc = {'en': en, 'zh': Counter(), 'keys': [], 'zh_pids': {}}
                self.docs[en] = doc
            if zh:
                doc['zh'][zh] += 1
            if key is not None:
                doc['keys'].append(key)
        return self

    def mark_input(self, rows):
        for (key, en, zh) in rows:
            self.input_ens.add(clean_en(en))
            self.input_pairs.add((clean_en(en), clean_zh(zh)))
        return self

    def finalize(self):
        for en, doc in self.docs.items():
            for zh in doc['zh']:
                pid = len(self.pair_list)
                self.pair_list.append((en, zh))
                doc['zh_pids'][zh] = pid
                for ch in set(zh):
                    self.char_post[ch].add(pid)
        return self

    def zh_subs(self, zh):
        got = self.zh_subs_cache.get(zh)
        if got is None:
            subs = []
            seen = set()
            for run in CJK_RE.findall(zh):
                n = len(run)
                for i in range(n):
                    for j in range(i + 1, min(n, i + 8) + 1):
                        s = run[i:j]
                        if s not in seen:
                            seen.add(s)
                            subs.append(s)
            for run in ASCII_RUN_RE.findall(zh):
                if len(run) >= 2 and run not in seen:
                    seen.add(run)
                    subs.append(run)
            got = tuple(subs)
            self.zh_subs_cache[zh] = got
        return got

    def sub_df(self):
        if not self.sub_pids_cache:
            df = Counter()
            for (en, zh) in self.pair_list:
                for s in self.zh_subs(zh):
                    df[s] += 1
            self.sub_pids_cache = df
        return self.sub_pids_cache


PARTICLES = set('的了着之地得是在和与及或为被把让使对从向于而且并也都就才还又很更最不没有无')
SLACK = PARTICLES | {'色'}


def trim_particles(corpus, s, rows):
    while len(s) > 1 and s[0] in PARTICLES and all(s[1:] in corpus.pair_list[q][1] for q in rows):
        s = s[1:]
    while len(s) > 1 and s[-1] in PARTICLES and all(s[:-1] in corpus.pair_list[q][1] for q in rows):
        s = s[:-1]
    return s


def align_rows(corpus, pids, min_share=0.5):
    pids = sorted(set(pids))[:32]
    n = len(pids)
    if n == 0:
        return []
    sub_df = corpus.sub_df()
    hits = defaultdict(set)
    for pid in pids:
        for s in corpus.zh_subs(corpus.pair_list[pid][1]):
            hits[s].add(pid)
    floor = max(2, int(math.ceil(min_share * n)))
    scored = []
    for s, h in hits.items():
        c = len(h)
        if c < floor and c < n:
            continue
        df = sub_df.get(s, c)
        if df <= 0:
            continue
        scored.append((2.0 * c / (n + df) * (1.0 if CJK_RE.search(s) else 0.55), len(s), s))
    if not scored:
        for s, h in hits.items():
            c = len(h)
            df = sub_df.get(s, c)
            if df > 0:
                scored.append((2.0 * c / (n + df) * (1.0 if CJK_RE.search(s) else 0.55),
                               len(s), s))
    if scored:
        cjk = [x for x in scored if CJK_RE.search(x[2])]
        if cjk and max(x[0] for x in cjk) >= 0.75 * max(x[0] for x in scored):
            scored = cjk
        top_cov = max(x[0] for x in scored)
        scored.sort(key=lambda x: (-(x[0] >= 0.75 * top_cov), -x[1], -x[0]))
        del scored[60:]
    out = []
    rest = set(pids)
    used = set()
    for _ in range(2):
        best = None
        for dice, ln, s in scored:
            if s in used:
                continue
            h = hits[s]
            inter = len(h & rest)
            if inter == 0:
                continue
            if len(rest) > 1 and inter < int(math.ceil(0.5 * len(rest))):
                continue
            best = (s, h, inter)
            break
        if best is None:
            break
        s, h, inter = best
        s = trim_particles(corpus, s, h)
        used.add(s)
        rest -= h
        out.append({'zh': s, 'cover': inter / n, 'dice': 2.0 * inter / (n + sub_df.get(s, inter))})
        if len(rest) < 2:
            break
    return out


def viterbi(toks, lex, tok_counts, total, forbid=None):
    n = len(toks)
    best = [None] * (n + 1)
    best[0] = (0.0, [])
    for i in range(1, n + 1):
        cur = None
        for ln in range(1, min(MAXN, i) + 1):
            g = tuple(toks[i - ln:i])
            if forbid is not None and g == forbid:
                continue
            c = lex.get(g)
            if c is None:
                continue
            prev = best[i - ln]
            if prev is None:
                continue
            cost = prev[0] + math.log(total / c)
            if cur is None or cost < cur[0]:
                cur = (cost, prev[1] + [(i - ln, i, g)])
        g = (toks[i - 1],)
        c = tok_counts.get(g, 0)
        if c > 0:
            prev = best[i - 1]
            cost = prev[0] + math.log(total / c)
            if cur is None or cost < cur[0]:
                cur = (cost, prev[1] + [(i - 1, i, g)])
        if cur is None:
            cur = (best[i - 1][0], best[i - 1][1] + [(i - 1, i, (toks[i - 1],))])
        best[i] = cur
    return best[n][1]


def build_stats(name_docs, known):
    cnt = Counter()
    stand = Counter()
    gram_names = defaultdict(set)
    left = defaultdict(Counter)
    right = defaultdict(Counter)
    tok_counts = Counter()
    bigram_counts = Counter()
    trigram_counts = Counter()
    total_tokens = 0
    for en in name_docs:
        toks = tokens_lc(en)
        total_tokens += len(toks)
        for t in toks:
            tok_counts[(t,)] += 1
        n = len(toks)
        for k in range(n - 1):
            bigram_counts[(toks[k], toks[k + 1])] += 1
        for k in range(n - 2):
            trigram_counts[(toks[k], toks[k + 1], toks[k + 2])] += 1
        for i in range(n):
            for j in range(i + 1, min(n, i + MAXN) + 1):
                g = tuple(toks[i:j])
                if g[-1] in STOP:
                    continue
                if g[0] in STOP and g[0] not in LEAD_OK:
                    continue
                cnt[g] += 1
                gram_names[g].add(en)
                if i == 0 and j == n:
                    stand[g] += 1
                if i > 0:
                    left[g][toks[i - 1]] += 1
                if j < n:
                    right[g][toks[j]] += 1
    lex = {}
    frag = {}
    for g, c in cnt.items():
        if len(g) == 1 and len(g[0]) <= 1:
            continue
        if c < 2:
            continue
        if stand[g] == 0:
            dom = False
            for side in (left, right):
                d = side.get(g)
                if d and max(d.values()) >= 0.75 * c:
                    dom = True
                    break
            if dom:
                frag[g] = True
        lex[g] = c
    for g in known:
        if 1 <= len(g) <= MAXN and g[0] not in STOP:
            lex[g] = max(lex.get(g, 0), 3)
    return {'cnt': cnt, 'stand': stand, 'left': left, 'right': right,
            'tok_counts': tok_counts, 'total': max(1, total_tokens), 'lex': lex,
            'gram_names': gram_names, 'frag': frag,
            'bigram': bigram_counts, 'trigram': trigram_counts}


def local_mi(g, stats):
    if len(g) < 2:
        return 0.0
    total = stats['total']
    tok = stats['tok_counts']
    big = stats['bigram']
    vals = []
    for i in range(len(g) - 1):
        c1 = tok.get((g[i],), 0)
        c2 = tok.get((g[i + 1],), 0)
        c12 = big.get((g[i], g[i + 1]), 0)
        if c1 <= 0 or c2 <= 0 or c12 <= 0:
            continue
        vals.append(math.log2(c12 * total / (c1 * c2)))
    if not vals:
        return 0.0
    return sum(vals) / len(vals)


def boundary_entropy(g, stats):
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


def compactness_score(g, stats):
    if len(g) < 2:
        return 1.0
    c = stats['cnt'].get(g, 0)
    if c <= 0:
        return 0.0
    m = max((stats['tok_counts'].get((w,), 0) for w in g), default=0)
    if m <= 0:
        return 0.0
    return min(1.0, c / m)


def coverage_of(toks, segs, variants, zh):
    covered = set()
    toks_cov = set()
    pos = 0
    found = 0
    units = 0
    for (a, b, g) in segs:
        vs = variants.get(g)
        if not vs:
            continue
        units += 1
        for v in sorted(vs, key=len, reverse=True):
            idx = zh.find(v, pos)
            if idx >= 0:
                for k in range(idx, idx + len(v)):
                    covered.add(k)
                for k in range(a, b):
                    toks_cov.add(k)
                pos = idx + len(v)
                found += 1
                break
    return covered, toks_cov, found, units


def composition_of(toks, segs, variants, zh, self_g):
    if not zh:
        return (False, 1.0)
    parts = [(a, b, g) for (a, b, g) in segs if g != self_g]
    if not parts:
        return (False, 1.0)
    covered, toks_cov, found, units = coverage_of(toks, parts, variants, zh)
    if units == 0:
        return (False, 1.0)
    ratio = len(covered) / max(1, len(zh))
    return (found == units and ratio >= 0.7, ratio)


def make_record(surface, g, pids, ens, stats, corpus, wl, cov, dice, comp, variants_zh,
                kind, prose_df=0, prose_pids=()):
    is_comp, cratio = comp
    occ = []
    seen = set()
    for pid in list(pids) + list(prose_pids):
        pair = corpus.pair_list[pid]
        if pair not in seen:
            seen.add(pair)
            occ.append(pair)
    prod_flags = []
    wl_flags = []
    named_flags = []
    for en in ens:
        doc = corpus.docs.get(en)
        if not doc:
            continue
        named_flags.append(is_name_like(en))
        for key in doc['keys']:
            wl_flags.append(is_product_key(key, wl, []))
    src_wl = (sum(1 for f in wl_flags if f) / len(wl_flags)) if wl_flags else 0.0
    wl_any = any(wl_flags)
    src_named = (sum(1 for f in named_flags if f) / len(named_flags)) if named_flags else 0.0
    src_prod = src_wl if wl else src_named
    heads = set()
    m = len(g)
    for en in sorted(ens)[:60]:
        t = tokens_lc(en)
        for i in range(len(t) - m + 1):
            if tuple(t[i:i + m]) == g:
                if i + m < len(t):
                    heads.add(t[i + m])
                if i > 0:
                    heads.add(t[i - 1])
    fam = 0
    for w in g:
        gg = (w,)
        if gg in stats['lex']:
            fam = max(fam, len(stats['gram_names'].get(gg, ())) - stats['stand'].get(gg, 0))
    zipf_vals = [zipf_frequency(w, 'en') for w in g if len(w) > 1]
    rec = {
        'en': surface, 'g': g, 'zh': list(variants_zh), 'kind': kind,
        'freq': max(stats['cnt'].get(g, 0), len(ens)),
        'prod': len(heads), 'cov': cov, 'dice': dice, 'src_prod': src_prod, 'src_wl': src_wl,
        'wl_any': wl_any,
        'zipf': max(zipf_vals) if zipf_vals else 4.0, 'stand': stats['stand'].get(g, 0),
        'compositional': is_comp, 'cratio': cratio,
        'nstop': sum(1 for w in g if w in STOP), 'fam': fam,
        'frag': bool(stats.get('frag', {}).get(g)),
        'local_mi': local_mi(g, stats),
        'boundary_entropy': boundary_entropy(g, stats),
        'compactness': compactness_score(g, stats),
        'occ': occ, 'occ_ens': set(ens) | {e for (e, z) in occ}, 'text_df': prose_df,
        'tier': 'drop', 'score': 0.0, 'src': [], 'ev': [],
    }
    return rec


def merge_record(records, rec):
    old = records.get(rec['g'])
    if old is None:
        records[rec['g']] = rec
        return
    for f in ('freq', 'prod', 'cov', 'dice', 'src_prod', 'src_wl', 'stand', 'text_df', 'fam'):
        old[f] = max(old[f], rec[f])
    old['compositional'] = old['compositional'] and rec['compositional']
    for v in rec['zh']:
        if v not in old['zh']:
            old['zh'].append(v)
    seen = set(old['occ'])
    for pair in rec['occ']:
        if pair not in seen:
            old['occ'].append(pair)
            seen.add(pair)
    old['occ_ens'] |= rec['occ_ens']
    old['wl_any'] = old['wl_any'] or rec.get('wl_any', False)
    if rec['kind'] == 'unit' and old['kind'] != 'unit':
        old['kind'] = 'unit'


def title_spans(en):
    rt = raw_tokens(en)
    spans = []
    i = 0
    n = len(rt)
    while i < n:
        if rt[i][0].isupper() or rt[i].isupper():
            j = i + 1
            while j < n and (rt[j][0].isupper() or rt[j].isupper() or rt[j].lower() in STOP):
                j += 1
            k = j
            while k > i + 1 and rt[k - 1].lower() in STOP:
                k -= 1
            spans.append([w.lower() for w in rt[i:k]])
            i = j
        else:
            i += 1
    return spans


def build_prose_index(prose_docs, corpus):
    prose_df = Counter()
    prose_pids = defaultdict(set)
    prose_surface = {}
    for en, doc in prose_docs.items():
        pids = {doc['zh_pids'][z] for z in doc['zh']}
        if not pids:
            continue
        raw = raw_tokens(en)
        grams = {}
        for words in title_spans(en):
            g = tuple(words)
            if len(g) >= 2 or len(g[0]) >= 4:
                grams[g] = ' '.join(words)
        toks = tokens_lc(en)
        for i in range(len(toks)):
            for j in range(i + 1, min(len(toks), i + 2) + 1):
                g = tuple(toks[i:j])
                if g[-1] in STOP or g[0] in STOP:
                    continue
                if len(g) == 1 and len(g[0]) < 4:
                    continue
                grams.setdefault(g, ' '.join(raw[i:j]))
        for g, surf in grams.items():
            prose_df[g] += 1
            prose_pids[g] |= pids
            prose_surface.setdefault(g, surf)
    return prose_df, prose_pids, prose_surface


def extract(args):
    global ZIPF_GATE, ZIPF_SCOPE
    ZIPF_GATE = args.zipf_gate
    ZIPF_SCOPE = args.zipf_gate_scope
    t0 = time.time()
    wl, bl = load_key_filter()
    ex = re.compile(args.exclude_keys) if args.exclude_keys else None
    known = load_known(args.known)

    input_rows = [r for r in load_input_rows(args.input) if is_product_key(r[0], wl, bl)]
    bg_rows = load_input_rows(args.background) if args.background else []
    seen_rows = set()
    filtered = []
    for (key, en, zh) in input_rows + bg_rows:
        sig = (key, en, zh)
        if sig in seen_rows:
            continue
        seen_rows.add(sig)
        if key is not None and ex is not None and ex.search(key):
            continue
        filtered.append((key, en, zh))

    corpus = Corpus()
    corpus.add_rows(filtered).mark_input(input_rows).finalize()

    name_docs = {}
    prose_docs = {}
    for en, doc in corpus.docs.items():
        if is_name_like(en):
            name_docs[en] = doc
        else:
            prose_docs[en] = doc

    doc_by_tokens = {}
    case_map = {}
    for en, doc in name_docs.items():
        doc_by_tokens.setdefault(tuple(tokens_lc(en)), doc)
        for w in raw_tokens(en):
            case_map.setdefault(w.lower(), w)
    for en, doc in corpus.docs.items():
        doc_by_tokens.setdefault(tuple(tokens_lc(en)), doc)
    surf_by_tokens = defaultdict(list)
    for en in corpus.docs:
        surf_by_tokens[tuple(tokens_lc(en))].append(en)

    stats = build_stats(name_docs, known)
    lex = dict(stats['lex'])
    total = stats['total']
    tok_counts = stats['tok_counts']
    gram_names = stats['gram_names']
    prose_df, prose_pids, prose_surface = build_prose_index(prose_docs, corpus)

    def pids_for(names, cap=48):
        out = set()
        for en in sorted(names):
            doc = corpus.docs.get(en)
            if not doc:
                continue
            for z in doc['zh']:
                out.add(doc['zh_pids'][z])
            if len(out) >= cap:
                break
        return sorted(out)

    def align_unit(g):
        pids = pids_for(gram_names.get(g, ()))
        if not pids:
            return [], []
        res = align_rows(corpus, pids)
        vs = [v['zh'] for v in res]
        kv = known.get(g)
        if kv:
            vs = list(dict.fromkeys(list(kv) + vs))
        return res, vs

    variants = {}
    align_info = {}
    for g in list(lex):
        res, vs = align_unit(g)
        if vs:
            align_info[g] = res
            variants[g] = vs

    pruned = set()
    for g in list(lex):
        if len(g) < 2 or g in known or g in pruned:
            continue
        segs = viterbi(list(g), lex, tok_counts, total, forbid=g)
        if not segs or not all(gg in lex and gg in variants for (_, _, gg) in segs):
            continue
        comp, ratio = composition_of(list(g), segs, variants, primary_zh(g, doc_by_tokens), g)
        if comp and (len(gram_names.get(g, ())) - stats['stand'].get(g, 0)) < 2:
            pruned.add(g)
    for g in pruned:
        lex.pop(g, None)

    segs_by_name = {}
    unit_pids = defaultdict(set)
    unit_names = defaultdict(set)
    for en, doc in name_docs.items():
        toks = tokens_lc(en)
        if not toks:
            continue
        segs = viterbi(toks, lex, tok_counts, total)
        segs_by_name[en] = segs
        pids = [doc['zh_pids'][z] for z in doc['zh']]
        for (_, _, g) in segs:
            if g in lex:
                unit_names[g].add(en)
                for pid in pids:
                    unit_pids[g].add(pid)
        if len(toks) > 1 and all(g in lex for (_, _, g) in segs):
            unit_names[tuple(toks)].add(en)
            for pid in pids:
                unit_pids[tuple(toks)].add(pid)

    records = {}
    unit_keys = list(lex.keys()) + [g for g in variants if g not in lex]
    for g in unit_keys:
        vs = variants.get(g, [])
        if len(g) == 1 and len(g[0]) <= 1:
            continue
        names = gram_names.get(g, set())
        pids = pids_for(names, cap=64)
        info = align_info.get(g) or []
        cov = min(1.0, sum(v['cover'] for v in info[:2]))
        dice = info[0]['dice'] if info else 0.0
        surface = display_surface(g, doc_by_tokens, case_map, surf_by_tokens)
        zh = primary_zh(g, doc_by_tokens)
        comp = composition_of(list(g), viterbi(list(g), lex, tok_counts, total, forbid=g),
                              variants, zh, g)
        rec = make_record(surface, g, pids, unit_names.get(g) or names, stats, corpus, wl,
                          cov, dice, comp, vs, 'unit', prose_df.get(g, 0),
                          prose_pids.get(g, ()))
        merge_record(records, rec)

    for en, doc in name_docs.items():
        toks = tokens_lc(en)
        if not toks:
            continue
        g = tuple(toks)
        if len(g) == 1 and len(g[0]) <= 1:
            continue
        zh = doc['zh'].most_common(1)[0][0] if doc['zh'] else ''
        if args.mode == 'aligned' and not zh:
            continue
        old = records.get(g)
        if old is not None and old['freq'] >= 2:
            continue
        pids = {doc['zh_pids'][z] for z in doc['zh']}
        segs = segs_by_name.get(en) or viterbi(toks, lex, stats['tok_counts'], total)
        info = align_rows(corpus, pids) if pids else []
        cov = sum(v['cover'] for v in info[:2]) if info else 0.0
        dice = info[0]['dice'] if info else 0.0
        comp = composition_of(toks, segs, variants, zh, g)
        rec = make_record(en, g, pids, {en}, stats, corpus, wl, cov, dice, comp,
                          [v['zh'] for v in info], 'name', prose_df.get(g, 0), prose_pids.get(g, ()))
        merge_record(records, rec)
        for cand in residual_candidates(en, toks, segs, variants, corpus, doc, wl, case_map):
            merge_record(records, cand)

    for g, pids in prose_pids.items():
        if g in lex or g in records:
            continue
        df = prose_df[g]
        if df < 2 and (len(g) == 1 or len(g[0]) < 6):
            continue
        info = align_rows(corpus, pids)
        cov = sum(v['cover'] for v in info[:2]) if info else 0.0
        dice = info[0]['dice'] if info else 0.0
        rec = make_record(prose_surface.get(g, ' '.join(g)), g, pids, set(), stats, corpus, wl,
                          cov, dice, (False, 1.0), [v['zh'] for v in info], 'text', df)
        merge_record(records, rec)

    out_recs = []
    for g, rec in records.items():
        if corpus.input_ens and not (rec['occ_ens'] & corpus.input_ens):
            continue
        if g in known:
            continue
        finalize_record(rec, corpus, args.mode)
        out_recs.append(rec)
    if args.compdrop == 'on':
        apply_compdrop(out_recs, records, known, align_info, gram_names, lex, stats, variants,
                       doc_by_tokens, whole_guard=args.compdrop_whole_guard == 'on')
    out_recs.sort(key=lambda r: ({'keep': 0, 'review': 1, 'drop': 2}[r['tier']], -r['score'], r['en']))
    if args.review_cap:
        seen = 0
        for r in out_recs:
            if r['tier'] != 'review':
                continue
            seen += 1
            if seen > args.review_cap:
                r['tier'] = 'drop'

    out_dir = args.out_dir or os.path.join(os.path.dirname(os.path.abspath(args.input)), 'termgen-out')
    os.makedirs(out_dir, exist_ok=True)
    write_candidates(os.path.join(out_dir, 'candidates.tsv'), out_recs)
    write_batches(os.path.join(out_dir, 'llm-batches.jsonl'), out_recs, args.mode, args.batch_size)
    n_keep = sum(1 for r in out_recs if r['tier'] == 'keep')
    n_rev = sum(1 for r in out_recs if r['tier'] == 'review')
    print('rows=%d names=%d prose=%d lex=%d cands=%d keep=%d review=%d drop=%d %.1fs' % (
        len(corpus.rows), len(name_docs), len(prose_docs), len(lex), len(out_recs),
        n_keep, n_rev, len(out_recs) - n_keep - n_rev, time.time() - t0))
    return 0


def primary_zh(g, doc_by_tokens):
    doc = doc_by_tokens.get(g)
    if doc and doc['zh']:
        return doc['zh'].most_common(1)[0][0]
    return ''


def display_surface(g, doc_by_tokens, case_map=None, surf_by_tokens=None):
    for s in (surf_by_tokens or {}).get(g, ()):
        if not s.islower() and s == ' '.join(raw_tokens(s)):
            return s
    doc = doc_by_tokens.get(g)
    if doc and not doc['en'].islower():
        return doc['en']
    if case_map:
        return ' '.join(case_map.get(w, w) for w in g)
    return doc['en'] if doc else ' '.join(g)


def residual_candidates(en, toks, segs, variants, corpus, doc, wl, case_map):
    if not doc['zh']:
        return []
    zh = doc['zh'].most_common(1)[0][0]
    covered, toks_cov, found, units = coverage_of(toks, segs, variants, zh)
    if not segs:
        return []
    bad = [k for k, (a, b, g) in enumerate(segs) if not all(i in toks_cov for i in range(a, b))]
    if not bad:
        return []
    a = segs[min(bad)][0]
    b = segs[max(bad)][1]
    span_toks = toks[a:b]
    if not span_toks or all(t in STOP for t in span_toks):
        return []
    residual = ''.join(ch for i, ch in enumerate(zh) if i not in covered)
    if not residual:
        return []
    pids = {doc['zh_pids'][z] for z in doc['zh']}
    flags = [is_product_key(k, wl, []) for k in doc['keys']]
    src_prod = (sum(1 for f in flags if f) / len(flags)) if flags else 0.0

    return [{
        'en': ' '.join(case_map.get(w, w) for w in span_toks), 'g': tuple(span_toks),
        'zh': [residual], 'kind': 'residual',
        'freq': 1, 'prod': 0, 'cov': 1.0, 'dice': 1.0, 'src_prod': src_prod, 'src_wl': 0.0,
        'wl_any': any(flags),
        'zipf': max([zipf_frequency(w, 'en') for w in span_toks] or [4.0]),
        'stand': 0, 'compositional': False, 'cratio': 1.0, 'fam': 0,
        'nstop': sum(1 for w in span_toks if w in STOP),
        'occ': [(en, zh)], 'occ_ens': {en}, 'text_df': 0, 'tier': 'drop', 'score': 0.0,
        'src': [], 'ev': [], 'frag': False,
        'local_mi': 0.0, 'boundary_entropy': 0.0, 'compactness': 0.0,
    }]


def compute_score(rec, mode):
    freq_t = min(1.0, math.log1p(rec['freq']) / math.log(21))
    prod_t = min(1.0, math.log1p(rec['prod']) / math.log(9))
    fam_t = min(1.0, math.log1p(rec.get('fam', 0)) / math.log(16))
    align = (0.65 * rec['cov'] + 0.35 * rec['dice']) if mode == 'aligned' else 0.5
    stand = 1.0 if rec['stand'] else 0.0
    prod = 1.0 if rec['src_prod'] >= 0.5 else (0.5 if rec['src_prod'] >= 0.25 else 0.0)
    len1 = 1.0 if len(rec['g']) == 1 else 0.0
    multi = 0.0 if len(rec['g']) == 1 else 1.0
    mi_t = max(0.0, min(10.0, rec.get('local_mi', 0.0))) / 10.0
    be_t = max(0.0, min(5.0, rec.get('boundary_entropy', 0.0))) / 5.0
    cmp_t = max(0.0, min(1.0, rec.get('compactness', 0.0)))
    if mode == 'aligned':
        s = (0.14 * align + 0.30 * prod + 0.20 * freq_t + 0.12 * prod_t + 0.12 * stand
             - 0.05 * fam_t + 0.10 * len1 + 0.13)
    else:
        s = (0.26 * prod + 0.22 * freq_t + 0.20 * prod_t + 0.20 * stand + 0.06 * fam_t
             + 0.08 * len1 + 0.04)
    if multi:
        s = 0.769 * s + 0.15 * mi_t + 0.10 * be_t + 0.05 * cmp_t
    if rec['kind'] == 'text':
        s -= 0.08
        if rec['freq'] >= 4 and rec['cov'] >= 0.85 and rec['dice'] >= 0.45 and len(rec['g']) >= 2:
            s += 0.30
    if len(rec['g']) == 1 and rec.get('src_wl', 0) < 0.5 and rec['zipf'] > 4.0:
        s -= 0.20
    if rec.get('frag'):
        s -= 0.04
    if rec['nstop'] > 1:
        s -= 0.05 * (rec['nstop'] - 1)
    if len(rec['g']) >= 4:
        s -= 0.05 * (len(rec['g']) - 3)
    if rec['kind'] == 'residual':
        s += 0.03
    if rec['stand'] and rec['kind'] == 'name' and rec['src_prod'] >= 0.5:
        s += 0.10
    return max(0.0, min(1.0, s))


def gate_drop(rec):
    if not ZIPF_GATE or rec.get('wl_any') or rec['zipf'] < ZIPF_GATE:
        return False
    # 豁免高产出度的unit与整串name，只对纯通用词门控
    if rec['kind'] == 'unit' and rec.get('prod', 0) >= 1:
        return False
    if rec['kind'] == 'name':
        return False
    if len(rec['g']) >= 2 and (rec.get('compactness', 0.0) >= COHESION_CMP
                               or rec.get('local_mi', 0.0) >= COHESION_MI):
        return False
    if ZIPF_SCOPE == 'named' and rec['kind'] == 'text':
        return False
    if ZIPF_SCOPE == 'label' and (rec['kind'] == 'text' or not rec['stand']):
        return False
    return True


def strip_slack(s):
    return ''.join(ch for ch in s if ch not in SLACK)


def comp_equal(zh, parts_variants):
    target = strip_slack(zh)
    if not target:
        return False
    combos = ['']
    for vs in parts_variants:
        nxt = []
        for pre in combos:
            for v in vs:
                nxt.append(pre + v)
        combos = nxt[:64]
    return any(strip_slack(c) == target for c in combos)


def part_is_atom(g, known, lex, stats, variants, doc_by_tokens, records=None):
    if len(g) == 1:
        return True
    segs = viterbi(list(g), lex, stats['tok_counts'], stats['total'], forbid=g)
    if not segs or len(segs) < 2:
        return False
    pvs = []
    for (_, _, sub) in segs:
        if len(sub) > 1:
            return False
        vs = variants.get(sub) or known.get(sub) or []
        if not vs:
            return False
        pvs.append(vs)
    extra = list(records.get(g, {}).get('zh', [])) if records else []
    zhs = [z for z in ([primary_zh(g, doc_by_tokens)] + list(variants.get(g) or known.get(g) or [])
                       + extra) if z]
    return any(comp_equal(z, pvs) for z in zhs)


def apply_compdrop(out_recs, records, known, align_info, gram_names, lex, stats, variants,
                   doc_by_tokens, whole_guard=True):
    strong = set(known.keys())
    for g, rec in records.items():
        if rec['tier'] == 'keep':
            strong.add(g)
    for g, info in align_info.items():
        if len(gram_names.get(g, ())) >= 4 and info and info[0]['dice'] >= 0.7:
            strong.add(g)
    dropped = []
    for rec in out_recs:
        g = rec['g']
        if len(g) < 2 or rec['tier'] == 'drop':
            continue
        if g in known or rec['tier'] == 'keep':
            continue
        if whole_guard and rec['stand'] >= 1:
            continue
        segs = viterbi(list(g), lex, stats['tok_counts'], stats['total'], forbid=g)
        if not segs or len(segs) < 2:
            continue
        parts = [gg for (_, _, gg) in segs]
        pvs = []
        for gg in parts:
            vs = variants.get(gg) or known.get(gg) or []
            if gg not in strong or not vs or not part_is_atom(gg, known, lex, stats, variants,
                                                             doc_by_tokens, records):
                pvs = None
                break
            pvs.append(vs)
        if not pvs:
            continue
        zh_variants = [z for z in list(rec['zh']) + [primary_zh(g, doc_by_tokens)] if z]
        if any(comp_equal(z, pvs) for z in zh_variants):
            rec['tier'] = 'drop'
            rec['why'] += ';compdrop=' + '|'.join(' '.join(gg) for gg in parts)
            dropped.append(rec['en'])
    return dropped


def finalize_record(rec, corpus, mode):
    if mode == 'en':
        rec['zh'] = []
    if rec['kind'] == 'residual':
        rec['freq'] = max(rec['freq'], len(rec['occ_ens']))
    if rec['kind'] == 'text':
        rec['freq'] = max(rec['freq'], rec['text_df'])
    rec['score'] = compute_score(rec, mode)
    # 取消 keep 特殊地位，所有符合条件的候选统一进 review 交给 LLM
    if rec['score'] >= REVIEW_SCORE and (rec['freq'] >= 2 or rec['stand'] >= 1
                                         or rec['kind'] in ('name', 'residual', 'text')):
        rec['tier'] = 'review'
    else:
        rec['tier'] = 'drop'
    if gate_drop(rec):
        rec['tier'] = 'drop'
    rec['src'] = pick_sources(rec, corpus)
    rec['ev'] = pick_evidence(rec, corpus)
    if mode == 'en':
        rec['ev'] = [(e, '') for (e, z) in rec['ev']]
    rec['why'] = why_str(rec, mode)


def why_str(rec, mode):
    parts = ['k=%s' % rec['kind'][0], 'x%d' % rec['freq']]
    if rec['prod']:
        parts.append('p%d' % rec['prod'])
    if rec['stand']:
        parts.append('whole')
    if mode == 'aligned':
        parts.append('cov%.2f' % rec['cov'])
        parts.append('dic%.2f' % rec['dice'])
    if rec['src_prod'] >= 0.5:
        parts.append('product')
    if not rec.get('wl_any'):
        parts.append('nwl')
    elif rec['kind'] == 'text':
        parts.append('text')
    if rec['compositional']:
        parts.append('comp%.2f' % rec['cratio'])
    if len(rec['g']) >= 2:
        parts.append('mi%.1f' % rec.get('local_mi', 0.0))
        parts.append('be%.1f' % rec.get('boundary_entropy', 0.0))
        parts.append('cmp%.2f' % rec.get('compactness', 0.0))
    if rec['text_df']:
        parts.append('prose%d' % rec['text_df'])
    if rec.get('fam', 0) >= 6:
        parts.append('fam%d' % rec['fam'])
    return ';'.join(parts)


def pick_sources(rec, corpus, limit=5):
    keys = []
    for (en, zh) in rec['occ']:
        doc = corpus.docs.get(en)
        if not doc:
            continue
        for k in doc['keys']:
            if k not in keys:
                keys.append(k)
        if len(keys) >= limit * 4:
            break
    keys.sort(key=lambda k: (len(k), k))
    return keys[:limit]


def pick_evidence(rec, corpus, limit=3):
    pairs = [p for p in rec['occ'] if len(p[0]) <= 70]
    pairs.sort(key=lambda p: (len(p[0]), p[0]))
    out = []
    for p in pairs:
        if p not in out:
            out.append(p)
        if len(out) >= limit:
            break
    return out


def flat(s):
    return re.sub(r'[\t\r\n]+', ' ', s or '')


def write_candidates(path, recs):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\',
                       lineterminator='\n')
        w.writerow(['en', 'zh', 'tier', 'score', 'why', 'sources', 'evidence'])
        for r in recs:
            zh = '|'.join(r['zh'][:3])
            ev = ' ‖ '.join('%s => %s' % (e, z) for (e, z) in r['ev'])
            w.writerow([flat(r['en']), flat(zh), r['tier'], '%.3f' % r['score'],
                        flat(r['why']), flat(';'.join(r['src'])), flat(ev)])


def write_batches(path, recs, mode, batch_size):
    if mode == 'en':
        items = [r for r in recs if r['tier'] != 'drop']
    else:
        items = [r for r in recs if r['tier'] == 'review']
    groups = defaultdict(list)
    for r in items:
        head = (r['g'][-1] if r['kind'] == 'unit' else r['g'][0]) if r['g'] else ''
        groups[head[:1]].append(r)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        for head in sorted(groups):
            bucket = groups[head]
            for i in range(0, len(bucket), batch_size):
                chunk = bucket[i:i + batch_size]
                obj = {'mode': mode, 'items': [
                    {'en': r['en'], 'zh_candidates': r['zh'][:2],
                     'evidence': [[e[:40], z[:24]] for (e, z) in r['ev'][:1]]} for r in chunk]}
                f.write(json.dumps(obj, ensure_ascii=False, separators=(',', ':')) + '\n')


def load_input_rows(path):
    if path.endswith('.json'):
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        rows = []
        for section in ('added', 'changed'):
            for key, val in data.get(section, {}).items():
                rows.append((key, val.get('en_us', ''), val.get('zh_cn', '')))
        return rows
    if path.endswith('.txt'):
        with open(path, encoding='utf-8') as f:
            return [(str(i), line, '') for i, line in enumerate(f, 1)]
    with open(path, encoding='utf-8', newline='') as f:
        rd = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))
    if not rd:
        return []
    head = [c.strip().lower() for c in rd[0]]
    if 'en_us' in head or 'en' in head or 'key' in head:
        ie = head.index('en_us') if 'en_us' in head else (head.index('en') if 'en' in head else None)
        iz = head.index('zh_cn') if 'zh_cn' in head else (head.index('zh') if 'zh' in head else None)
        ik = head.index('key') if 'key' in head else None
        data = rd[1:]
        start = 2
    else:
        ie, iz, ik = 0, (1 if len(rd[0]) > 1 else None), None
        data = rd
        start = 1
    rows = []
    for i, r in enumerate(data, start):
        if ie is None or ie >= len(r):
            continue
        key = r[ik] if (ik is not None and ik < len(r)) else str(i)
        zh = r[iz] if (iz is not None and iz < len(r)) else ''
        rows.append((key, r[ie], zh))
    return rows


def read_candidates(path):
    recs = []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\'):
            ev = []
            for part in (r.get('evidence') or '').split(' ‖ '):
                if ' => ' in part:
                    a, b = part.split(' => ', 1)
                    ev.append((a, b))
            recs.append({
                'en': r['en'], 'zh': [z for z in (r.get('zh') or '').split('|') if z],
                'tier': r['tier'], 'score': float(r.get('score') or 0), 'why': r.get('why', ''),
                'src': r.get('sources', ''), 'ev': ev,
            })
    return recs


def judge(args):
    recs = read_candidates(args.candidates)
    keep = [r for r in recs if r['tier'] == 'keep']
    review = [r for r in recs if r['tier'] == 'review']
    api_key = os.environ.get('LLM_API_KEY')
    base = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1').rstrip('/')
    model = os.environ.get('LLM_MODEL', 'gpt-4o-mini')
    accepted = []
    if not api_key:
        for r in keep:
            accepted.append({'en': r['en'], 'zh': r['zh'][0] if r['zh'] else '', 'reason': r['why'],
                             'comment': '来源：%s；auto' % r['src']})
        print('LLM_API_KEY not set; keep-tier only (%d items)' % len(accepted))
    else:
        todo = keep + review
        for i in range(0, len(todo), args.batch_size):
            chunk = todo[i:i + args.batch_size]
            items = [{'id': str(i + j), 'en': r['en'], 'zh_candidates': r['zh'][:3],
                      'prior': r['tier'], 'why': r['why'],
                      'evidence': [[e, z] for (e, z) in r['ev']]} for j, r in enumerate(chunk)]
            payload = {
                'model': model, 'temperature': 0,
                'messages': [
                    {'role': 'system', 'content': 'You curate a Minecraft glossary of reusable '
                     'translation units. For each item decide keep=true if it is a reusable term or a '
                     'non-compositional name that should enter the glossary, keep=false for generic UI '
                     'words, sentence fragments, advancement titles or broken surfaces. Items with '
                     'prior="keep" are statistically high-confidence: keep them unless clearly wrong. '
                     'Give the Simplified Chinese translation in "zh" '
                     '(keep the provided candidate if correct). Reply with a JSON array only: '
                     '[{"id": str, "keep": bool, "zh": str, "reason": str}].'},
                    {'role': 'user', 'content': json.dumps({'items': items}, ensure_ascii=False)},
                ]}
            req = urllib.request.Request(base + '/chat/completions',
                                         data=json.dumps(payload).encode('utf-8'),
                                         headers={'Content-Type': 'application/json',
                                                  'Authorization': 'Bearer ' + api_key})
            try:
                with urllib.request.urlopen(req, timeout=120) as resp:
                    body = json.loads(resp.read().decode('utf-8'))
                content = body['choices'][0]['message']['content']
                content = re.sub(r'^```(?:json)?|```$', '', content.strip(), flags=re.M).strip()
                verdicts = json.loads(content)
            except Exception as exc:
                sys.stderr.write('batch %d failed: %s\n' % (i // args.batch_size + 1, exc))
                for r in chunk:
                    if r['tier'] == 'keep':
                        accepted.append({'en': r['en'], 'zh': r['zh'][0] if r['zh'] else '',
                                         'reason': r['why'], 'comment': '来源：%s；auto' % r['src']})
                continue
            by_id = {str(i + j): r for j, r in enumerate(chunk)}
            for v in (verdicts if isinstance(verdicts, list) else []):
                r = by_id.get(str(v.get('id')))
                if not r or not v.get('keep'):
                    continue
                zh = clean_zh(str(v.get('zh') or '')) or (r['zh'][0] if r['zh'] else '')
                accepted.append({'en': r['en'], 'zh': zh, 'reason': str(v.get('reason') or r['why']),
                                 'comment': '来源：%s；llm;%s' % (r['src'], r['tier'])})
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.candidates)), 'terms.tsv')
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_NONE, escapechar='\\',
                       lineterminator='\n')
        w.writerow(['en', 'zh', 'reason', 'comment'])
        for r in accepted:
            w.writerow([r['en'], r['zh'], r['reason'], r['comment']])
    print('terms=%d -> %s' % (len(accepted), out))
    return 0


def load_gold(paths):
    out = []
    for path in paths:
        with open(path, encoding='utf-8', newline='') as f:
            for r in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                if len(r) < 2 or not r[0].strip() or r[0].strip().lower() == 'en':
                    continue
                out.append((clean_en(r[0]), [clean_zh(v) for v in r[1].split('|') if clean_zh(v)]))
    return out


def eval_cmd(args):
    recs = read_candidates(args.candidates)
    gold = load_gold(args.gold)
    input_rows = load_input_rows(args.input) if args.input else []
    text_ens = [clean_en(en) for (key, en, zh) in input_rows]
    if not text_ens:
        for r in recs:
            text_ens.extend(e for (e, z) in r['ev'])
    blob = ' ' + ' '.join(norm_lemma(e) for e in text_ens) + ' '
    reach = [(en, zhv) for en, zhv in gold if (' ' + norm_lemma(en) + ' ') in blob]
    gold_norm = {}
    for en, zhv in gold:
        gold_norm.setdefault(norm_lemma(en), (en, zhv))
    reach_norm = {norm_lemma(en) for en, _ in reach}
    keep = [r for r in recs if r['tier'] == 'keep']
    rev = [r for r in recs if r['tier'] == 'review']
    kn = {norm_lemma(r['en']) for r in keep}
    rn = {norm_lemma(r['en']) for r in rev}
    knr = kn | rn
    hit_keep = kn & set(gold_norm)
    hit_knr = knr & set(gold_norm)
    zh_hit = 0
    zh_tot = 0
    cand_zh = {}
    for r in keep + rev:
        cand_zh.setdefault(norm_lemma(r['en']), r['zh'])
    for n in sorted(hit_knr):
        gen, gzh = gold_norm[n]
        czh = cand_zh.get(n) or []
        zh_tot += 1
        for c in czh:
            if any(c and g and (c == g or c in g or g in c) for g in gzh):
                zh_hit += 1
                break
    batch_path = os.path.join(os.path.dirname(os.path.abspath(args.candidates)), 'llm-batches.jsonl')
    payload_chars = 0
    if os.path.exists(batch_path):
        with open(batch_path, encoding='utf-8') as f:
            payload_chars = sum(len(line) for line in f)
    input_chars = sum(len(en) + len(zh) for (key, en, zh) in input_rows)
    print('gold=%d reachable=%d' % (len(gold), len(reach)))
    print('recall@keep        = %.3f (vs gold) %.3f (vs reachable)' % (
        len(hit_keep) / max(1, len(gold_norm)), len(hit_keep & reach_norm) / max(1, len(reach_norm))))
    print('recall@keep+review = %.3f (vs gold) %.3f (vs reachable)' % (
        len(hit_knr) / max(1, len(gold_norm)), len(hit_knr & reach_norm) / max(1, len(reach_norm))))
    print('FDR@keep           = %.3f' % (1.0 - len(hit_keep) / max(1, len(keep))))
    print('FDR@keep+review    = %.3f' % (1.0 - len(hit_knr) / max(1, len(knr))))
    print('zh hit rate        = %.3f (%d/%d matched)' % (zh_hit / max(1, zh_tot), zh_hit, zh_tot))
    print('tiers: keep=%d review=%d drop=%d' % (len(keep), len(rev),
                                                len(recs) - len(keep) - len(rev)))
    print('payload chars=%d vs input en+zh chars=%d' % (payload_chars, input_chars))
    best_score = {}
    for r in recs:
        n = norm_lemma(r['en'])
        if r['score'] > best_score.get(n, 0.0):
            best_score[n] = r['score']
    fn = []
    for n, (en, zhv) in gold_norm.items():
        if n not in knr:
            fn.append((best_score.get(n, 0.0), en))
    fn.sort(key=lambda x: -x[0])
    fp = sorted(((r['score'], r['en'], r['tier']) for r in keep + rev
                 if norm_lemma(r['en']) not in gold_norm), key=lambda x: -x[0])
    try:
        print('-- top false negatives --')
        for s, en in fn[:30]:
            print('%.3f\t%s' % (s, en))
        print('-- top false positives --')
        for s, en, tier in fp[:30]:
            print('%.3f\t%s\t%s' % (s, en, tier))
    except (BrokenPipeError, OSError):
        pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog='termgen.py')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('extract', help='extract glossary candidates')
    p.add_argument('--input', required=True)
    p.add_argument('--background')
    p.add_argument('--known', nargs='*', default=[])
    p.add_argument('--exclude-keys')
    p.add_argument('--mode', choices=['aligned', 'en'], required=True)
    p.add_argument('--out-dir')
    p.add_argument('--batch-size', type=int, default=40)
    p.add_argument('--review-cap', type=int, default=0)
    p.add_argument('--zipf-gate', type=float, default=ZIPF_GATE)
    p.add_argument('--zipf-gate-scope', choices=['all', 'named', 'label'], default=ZIPF_SCOPE)
    p.add_argument('--compdrop', choices=['on', 'off'], default='on')
    p.add_argument('--compdrop-whole-guard', choices=['on', 'off'], default='off')
    p.set_defaults(func=extract)

    p = sub.add_parser('judge', help='LLM-judge review-tier candidates')
    p.add_argument('--candidates', required=True)
    p.add_argument('--batch-size', type=int, default=40)
    p.add_argument('--out')
    p.set_defaults(func=judge)

    p = sub.add_parser('eval', help='evaluate candidates against gold')
    p.add_argument('--candidates', required=True)
    p.add_argument('--gold', nargs='+', required=True)
    p.add_argument('--input')
    p.set_defaults(func=eval_cmd)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
