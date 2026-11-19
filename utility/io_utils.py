import csv
import itertools
import json
import math
import re
import sys
from pathlib import Path

try:
    import inflection
except Exception:
    inflection = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FILTER_PATH = ROOT / 'Vanilla' / 'diffs' / 'term-key-filters.json'

CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+')
FORMAT_RE = re.compile(r'%(\d+\$)?[sdf]|%%|\{[^}]*\}|§.|\\n|\\t|\\r')
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
NAME_CHARS_RE = re.compile(r"[A-Za-z0-9'’\-\s]+$")
NAME_BAD_RE = re.compile(r"[.!?…:;,()\[\]{}\"“”«»/\\|<>+=*#@$^~`]")
WORD_BOUNDARY_RE = re.compile(r"[A-Za-z0-9]+(?:['’][A-Za-z0-9]+)*")

STOP = set("""a an the and or but if then than that this these those of to in on at for with from by as
is are was were be been being am do does did not no nor you your yours we our ours us it its he she they
them their his her my me i will would can could should shall may might must have has had here there when
where which who whom what how why all any some more most other such only own same so too very just also up
down out off over under again further once during before after above below between into through about
against while both each few because until unless upon onto within without across around""".split())
LEAD_OK = {'the'}
CONNECTORS = {'of', 'the'}
MAX_NAME_TOKENS = 7
MAX_GRAM = 5


def clean_en(s):
    s = FORMAT_RE.sub(' ', str(s or ''))
    s = s.replace('’', "'").replace('\u00a0', ' ')

    return ' '.join(s.split())


def clean_zh(s):
    s = FORMAT_RE.sub(' ', str(s or ''))

    return ' '.join(s.split())


def stripped(text):
    return re.sub(r'\s+', '', text)


def tokens_lc(s):
    return [t.lower() for t in TOKEN_RE.findall(s)]


def raw_tokens(s):
    return TOKEN_RE.findall(s)


def token_ok(w):
    if w.lower() in STOP:
        return True

    if any(c.isdigit() for c in w):
        return True

    if len(w) == 1 or w.isupper():
        return True

    return w[0].isupper()


def is_name_like(s):
    if not s or len(s) > 80:
        return False

    if NAME_BAD_RE.search(s) or not NAME_CHARS_RE.match(s):
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

    if len(rt) >= 5 and sum(1 for w in low if w in STOP) >= 2:
        return False

    return True


def norm_lemma(s):
    s = str(s or '').lower().replace('’', "'")
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


def entropy_bits(counter):
    total = sum(counter.values())

    if total <= 1:
        return 0.0

    return -sum((n / total) * math.log2(n / total) for n in counter.values() if n)


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def ensure_parent(path):
    p = Path(path)
    if p.parent and p.parent != Path(''):
        p.parent.mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    ensure_parent(path)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_text(path, text):
    ensure_parent(path)
    Path(path).write_text(text, encoding='utf-8')


def write_tsv(stream, header, rows):
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(header)

    for row in rows:
        writer.writerow(row)


def parse_lang(path):
    out = {}
    for line in Path(path).read_text(encoding='utf-8-sig').splitlines():
        s = line.strip()
        if not s or s.startswith('#') or '=' not in s:
            continue
        k, v = s.split('=', 1)
        out.setdefault(k.strip(), v)

    return out


def load_lang_file(path):
    p = Path(path)
    if p.suffix.lower() == '.json':
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict):
            raise SystemExit(f'JSON 语言文件必须是对象：{p}')
        return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}

    return parse_lang(p)


def find_lang_file(lang_dir, code):
    base = Path(lang_dir)
    for ext in ('.json', '.lang'):
        candidate = base / f'{code}{ext}'
        if candidate.is_file():
            return candidate

    return None


def _load_tsv_rows(path, en_col=None, zh_col=None):
    with open(path, encoding='utf-8-sig', newline='') as f:
        rd = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))

    if not rd:
        return []

    head = [c.strip().lower() for c in rd[0]]
    en_candidates = ([en_col.lower()] if en_col else []) + ['en_us', 'en', 'source']
    zh_candidates = ([zh_col.lower()] if zh_col else []) + ['zh_cn', 'zh', 'target']
    has_header = any(c in head for c in en_candidates + zh_candidates + ['key'])

    if has_header:
        ie = next((head.index(c) for c in en_candidates if c in head), None)
        iz = next((head.index(c) for c in zh_candidates if c in head), None)
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
        rows.append((key, r[ie].replace('\\n', '\n'), zh.replace('\\n', '\n')))

    return rows


def load_input_rows(path, en_col=None, zh_col=None):
    p = Path(path)

    if p.is_dir():
        en_file = find_lang_file(p, en_col or 'en_us')
        if not en_file:
            raise SystemExit(f'目录缺少语言文件 {en_col or "en_us"}.json/.lang：{p}')
        en_map = load_lang_file(en_file)
        zh_file = find_lang_file(p, zh_col or 'zh_cn')
        zh_map = load_lang_file(zh_file) if zh_file else {}

        return [(k, v, zh_map.get(k, '')) for k, v in en_map.items()]

    suffix = p.suffix.lower()

    if suffix == '.json':
        data = json.loads(p.read_text(encoding='utf-8-sig'))

        if isinstance(data, dict) and ('added' in data or 'changed' in data):
            rows = []
            for section in ('added', 'changed'):
                block = data.get(section)
                if isinstance(block, dict):
                    for key, val in block.items():
                        if isinstance(val, dict):
                            rows.append((key, val.get(en_col or 'en_us', val.get('en', '')),
                                         val.get(zh_col or 'zh_cn', val.get('zh', ''))))
            return rows

        if isinstance(data, dict):
            rows = []
            for key, val in data.items():
                if isinstance(val, dict):
                    rows.append((str(key), str(val.get(en_col or 'en_us', val.get('en', ''))),
                                 str(val.get(zh_col or 'zh_cn', val.get('zh', '')))))
                elif isinstance(val, str):
                    rows.append((str(key), val, ''))
            return rows

        if isinstance(data, list):
            rows = []
            for idx, item in enumerate(data, 1):
                if isinstance(item, dict):
                    rows.append((str(item.get('key', idx)),
                                 str(item.get(en_col or 'en', item.get('en_us', ''))),
                                 str(item.get(zh_col or 'zh', item.get('zh_cn', '')))))
            return rows

        return []

    if suffix == '.lang':
        return [(k, v, '') for k, v in parse_lang(p).items()]

    if suffix == '.txt':
        lines = p.read_text(encoding='utf-8-sig').splitlines()
        return [(str(i), line, '') for i, line in enumerate(lines, 1) if line]

    return _load_tsv_rows(p, en_col=en_col, zh_col=zh_col)


def load_key_filter(filter_file=None):
    path = Path(filter_file) if filter_file else DEFAULT_FILTER_PATH
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    wl = [re.compile(p) for p in data.get('whitelist_patterns', [])]
    bl = [re.compile(p) for p in data.get('blacklist_patterns', [])]

    return wl, bl


def is_product_key(key, wl, bl):
    if not key:
        return False

    if any(p.search(key) for p in bl):
        return False

    return any(p.search(key) for p in wl)


def filter_rows(rows, key_filter='auto', keys=None, exclude_keys=None, prefixes=None, filter_file=None):
    wl_re = re.compile(keys) if keys else None
    ex_re = re.compile(exclude_keys) if exclude_keys else None
    wl = bl = None

    if wl_re is None and not prefixes:
        if key_filter == 'on':
            wl, bl = load_key_filter(filter_file)
        elif key_filter == 'auto' and filter_file:
            wl, bl = load_key_filter(filter_file)

    out = []
    for key, en, zh in rows:
        if ex_re and ex_re.search(key):
            continue

        if prefixes and not any(key.startswith(pref) for pref in prefixes):
            continue

        if wl_re is not None and not wl_re.search(key):
            continue

        if wl is not None and not is_product_key(key, wl, bl):
            continue

        out.append((key, en, zh))

    return out


def load_focus_keys(path):
    p = Path(path)
    text = p.read_text(encoding='utf-8-sig')

    if p.suffix.lower() == '.json':
        data = json.loads(text)
        keys = set()

        if isinstance(data, dict) and ('added' in data or 'changed' in data or 'removed' in data):
            for section in ('added', 'changed', 'removed'):
                block = data.get(section)
                if isinstance(block, dict):
                    keys.update(block)
                elif isinstance(block, list):
                    keys.update(item if isinstance(item, str) else item.get('key', '') for item in block)
        elif isinstance(data, dict):
            keys.update(data.keys())
        elif isinstance(data, list):
            keys.update(item if isinstance(item, str) else str(item.get('key', '')) for item in data)

        return {k for k in keys if k}

    return {line.split('\t')[0].strip() for line in text.splitlines() if line.strip() and not line.startswith('#')}


def load_glossary_entries(paths):
    entries = []
    missing = 0

    for path in paths or []:
        p = Path(path)
        if not p.is_file():
            sys.stderr.write(f'known file not found: {p}\n')
            missing += 1
            continue

        with p.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))

        if not rows:
            continue

        head = [c.strip().lower() for c in rows[0]]
        if 'en' in head or 'zh' in head:
            ie = head.index('en') if 'en' in head else 0
            iz = head.index('zh') if 'zh' in head else 1
            ir = head.index('reason') if 'reason' in head else None
            data = rows[1:]
        else:
            ie, iz, ir = 0, 1, None
            data = rows

        for r in data:
            if len(r) <= max(ie, iz):
                continue
            en = clean_en(r[ie])
            zh_raw = clean_zh(r[iz])
            if not en or not zh_raw:
                continue
            variants = []
            for v in zh_raw.split('|'):
                v = v.strip()
                if v and v not in variants:
                    variants.append(v)
            if not variants:
                continue
            reason = r[ir].strip() if (ir is not None and ir < len(r)) else ''
            entries.append({'en': en, 'zh': variants, 'reason': reason, 'lemma': norm_lemma(en)})

    return entries, missing


def known_pairs(paths):
    entries, missing = load_glossary_entries(paths)
    pairs = {}

    for entry in entries:
        lemma = entry['lemma']
        if not lemma:
            continue
        bucket = pairs.setdefault(lemma, [])
        for v in entry['zh']:
            if v not in bucket:
                bucket.append(v)

    return pairs, missing


def compositions(en, pairs, cap=256, limit=400):
    tokens = norm_lemma(clean_en(en)).split()
    made = set()

    if not tokens:
        return made

    segments = []

    def walk(index, parts):
        if len(segments) >= limit:
            return
        if index == len(tokens):
            segments.append(tuple(parts))
            return
        for end in range(len(tokens), index, -1):
            key = ' '.join(tokens[index:end])
            if key in pairs:
                parts.append(key)
                walk(end, parts)
                parts.pop()

    walk(0, [])

    for parts in segments:
        total = 1
        for key in parts:
            total *= len(pairs[key])
        if total > cap:
            continue
        for combo in itertools.product(*(pairs[key] for key in parts)):
            made.add(stripped(''.join(combo)))

    return made


def is_known_term(en, known, zh_variants=None):
    lemma = norm_lemma(clean_en(en))
    if not lemma:
        return False

    if zh_variants is None:
        return lemma in known or bool(compositions(en, known))

    plain = [clean_zh(v) for v in zh_variants if clean_zh(v)]

    if lemma in known and all(v in known[lemma] for v in plain):
        return True

    stripped_variants = [stripped(v) for v in plain]
    made = compositions(en, known)

    return bool(made and stripped_variants and all(v in made for v in stripped_variants))


def build_term_matcher(entries):
    phrases = {}
    lemma_phrases = {}
    max_tokens = 1

    for entry in entries:
        toks = tuple(t.lower() for t in WORD_BOUNDARY_RE.findall(entry['en']))

        if toks:
            phrases.setdefault(toks, []).append(entry)
            max_tokens = max(max_tokens, len(toks))

    for entry in entries:
        toks = tuple(t.lower() for t in WORD_BOUNDARY_RE.findall(entry['en']))
        lemma_toks = tuple(norm_lemma(entry['en']).split())

        if lemma_toks and (lemma_toks == toks or lemma_toks not in phrases):
            lemma_phrases.setdefault(lemma_toks, []).append(entry)
            max_tokens = max(max_tokens, len(lemma_toks))

    return phrases, lemma_phrases, max_tokens


def match_known_in_row(en_text, zh_text, matcher):
    phrases, lemma_phrases, max_tokens = matcher
    toks = tuple(t.lower() for t in WORD_BOUNDARY_RE.findall(en_text or ''))

    if not toks or (not phrases and not lemma_phrases):
        return []

    consumed = [False] * len(toks)
    zh_lower = (zh_text or '').lower()
    hits = []

    for i in range(len(toks)):
        if consumed[i]:
            continue

        for w in range(min(max_tokens, len(toks) - i), 0, -1):
            if any(consumed[i:i + w]):
                continue

            window = toks[i:i + w]
            entries = phrases.get(window)

            if not entries and lemma_phrases:
                lemma_key = tuple(norm_lemma(' '.join(window)).split())
                entries = lemma_phrases.get(lemma_key)

            if not entries:
                continue

            for entry in entries:
                ok = any(z.lower() in zh_lower for z in entry['zh'])
                hits.append({'en': entry['en'], 'zh': entry['zh'], 'ok': ok, 'reason': entry['reason']})

            for k in range(i, i + w):
                consumed[k] = True

            break

    return hits
