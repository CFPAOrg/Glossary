#!/usr/bin/env python3
# 术语候选生成：把 en→zh 平行名称压成可复用条目（零件/模板/例外），人只审条目。
# 流水线：key 过滤 → 挖片段 → 统计门控 → 组合证明 → 模板 → 选条目 → 逐行核验。
# 用法：extract 打 TSV / judge 出审校 JSON / bench 打分；设计见 Docs/TERMGEN.md。
import argparse
import csv
import itertools
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

try:
    import inflection
except Exception:
    inflection = None


CJK_RE = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+')
FORMAT_RE = re.compile(r'%(\d+\$)?[sdf]|%%|\{[^}]*\}|§.|\\n|\\t|\\r')  # 剥掉 %s、{}、§x 这类格式符
TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
NAME_CHARS_RE = re.compile(r"[A-Za-z0-9'’\-\s]+$")
NAME_BAD_RE = re.compile(r"[.!?…:;,()\[\]{}\"“”«»/\\|<>+=*#@$^~`]")
STOP = set("""a an the and or but if then than that this these those of to in on at for with from by as
is are was were be been being am do does did not no nor you your yours we our ours us it its he she they
them their his her my me i will would can could should shall may might must have has had here there when
where which who whom what how why all any some more most other such only own same so too very just also up
down out off over under again further once during before after above below between into through about
against while both each few because until unless upon onto within without across around""".split())  # 停用词
LEAD_OK = {'the'}  # 允许出现在开头的停用词
MAX_NAME_TOKENS = 7  # 名字最多 7 个词

KEY_FILTER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'Vanilla', 'diffs', 'term-key-filters.json')  # key 白/黑名单


# 去格式符、规范撇号、压空白
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


# 合法词：停用词/数字/单字母/全大写/首字母大写
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


# 名字门槛：≤7 词、无标点、有首字母大写、停用词受限
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


# 规范化：小写、去标点、去 's、单数化
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


# 黑名单命中即否，白名单命中才算
def is_product_key(key, wl, bl):
    if not key:
        return False
    if any(p.search(key) for p in bl):
        return False
    return any(p.search(key) for p in wl)


# 输入三种形态：diff JSON / 纯文本 / TSV
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


def load_focus_keys(path):
    path = str(path)
    with open(path, encoding='utf-8', newline='') as f:
        text = f.read()
    if path.endswith('.json'):
        data = json.loads(text)
        keys = set()
        for section in ('added', 'changed', 'removed'):
            block = data.get(section)
            if isinstance(block, dict):
                keys.update(block)
            elif isinstance(block, list):
                keys.update(item if isinstance(item, str) else item.get('key', '')
                            for item in block)
        return {key for key in keys if key}
    return {line.split('\t')[0].strip() for line in text.splitlines() if line.strip()}


def load_gold(paths):
    out = []
    for path in paths:
        with open(path, encoding='utf-8', newline='') as f:
            for r in csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE):
                if len(r) < 2 or not r[0].strip() or r[0].strip().lower() == 'en':
                    continue
                out.append((clean_en(r[0]), [clean_zh(v) for v in r[1].split('|') if clean_zh(v)]))
    return out


ROOT = Path(__file__).resolve().parent.parent
CONNECTORS = {'of', 'the'}  # 拼接时可跳过的连接词
MAX_GRAM = 5  # 英文片段最长 5 词
MIN_STRONG_FREQ = 3  # 至少出现在 3 个不同名字里
ENTROPY_GATE = 2.0  # 邻居熵门槛（bit）：邻居够杂才算独立单位
JOIN_GATE = 3.0  # 搭配强度门槛：共现远超偶然才算固定搭配
MIN_ROWS = 2  # 模板/原子至少覆盖 2 行
MIN_PAIRS = 2  # 且至少 2 对不同对照
MAX_INDUCTION_ROUNDS = 2
MAX_PRUNE_ROUNDS = 4


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


# 中文候选：CJK 段里 1~8 字的全部子串
def zh_fragments(text):
    return {run[i:j] for run in CJK_RE.findall(text)
            for i in range(len(run))
            for j in range(i + 1, min(len(run), i + 8) + 1)}


# 名字→小写词元；不像名字或含数字返回空
def name_tokens(en):
    return tuple(tokens_lc(en)) if is_name_like(en) and not re.search(r'[0-9]', en) else ()


# 给英文片段找中文候选：整名精确对照 + Dice 贪心覆盖
def translations(gram, support, pairs, fragments, subdf, whole):
    exact = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
    hits = Counter(sub for pid in support for sub in fragments[pid])
    eligible = {sub for sub, count in hits.items()
                if count >= 2 and count / subdf[sub] >= 0.5}
    variants = list(exact)
    covered = {pid for pid in support if any(z in pairs[pid][1] for z in variants)}
    confidence = 1.0 if exact else 0.0
    while len(variants) < max(4, len(exact)):
        uncovered = support - covered
        choices = []
        for sub in eligible:
            extra = {pid for pid in uncovered if sub in fragments[pid]}
            if len(extra) < 2:
                continue
            outside = subdf[sub] - hits[sub]
            dice = 2 * len(extra) / (len(uncovered) + len(extra) + outside)  # 扎堆在未覆盖行、外面少见
            if dice >= 0.5:
                choices.append((dice, len(extra), len(sub), sub, extra))
        if not choices:
            break
        dice, count, length, sub, extra = max(choices)
        variants.append(sub)
        confidence = max(confidence, dice)
        covered.update(extra)
    return variants, confidence, len(covered) / len(support)


# 条目中文按序拼接 == 目标译文，每个条目只用一次
def chinese_match(zh, parts):
    target = re.sub(r'\s+', '', zh)
    variants = tuple(tuple(re.sub(r'\s+', '', z) for z in entry['zh_candidates'] if z)
                     for entry in parts)

    @lru_cache(maxsize=None)
    def visit(pos, remaining):
        if not remaining:
            return pos == len(target)
        if pos and pos < len(target) - 1 and target[pos] == '的':  # 片段之间允许多一个「的」
            if visit(pos + 1, remaining):
                return True
        for i, options in enumerate(variants):
            if remaining & (1 << i):
                for variant in options:
                    if target.startswith(variant, pos) and visit(
                            pos + len(variant), remaining ^ (1 << i)):
                        return True
        return False

    return bool(parts) and visit(0, (1 << len(parts)) - 1)


# 贪心最长匹配切词；尝试封顶 256；of/the 跳过
def compose(toks, zh, lexicon, forbid=None):
    if not toks or not zh:
        return None
    attempts = 0

    def paths(pos, chosen):
        nonlocal attempts
        if attempts >= 256:
            return None
        if pos == len(toks):
            attempts += 1
            if chinese_match(zh, chosen):
                return [entry['id'] for entry in chosen]
            return None
        for end in range(min(len(toks), pos + MAX_GRAM), pos, -1):
            gram = toks[pos:end]
            if gram != forbid and gram in lexicon:
                found = paths(end, chosen + [lexicon[gram]])
                if found is not None:
                    return found
        if toks[pos] in CONNECTORS:
            return paths(pos + 1, chosen)
        return None

    return paths(0, [])


# 反推单词译文：其余词已知时从整名切出，需 ≥2 个名字佐证
def refine_atoms(aligned, supports, pairs, fragments, whole):
    atoms = {gram[0]: {'zh_candidates': info[0]}
             for gram, info in aligned.items() if len(gram) == 1 and info[0]}
    refined = {}
    for word, entry in atoms.items():
        gram = (word,)
        found = defaultdict(set)
        for pid in supports[gram]:
            en, zh = pairs[pid]
            toks = name_tokens(en)
            if toks.count(word) != 1 or len(toks) == 1:
                continue
            other = [t for t in toks if t != word and t not in CONNECTORS]
            if any(t not in atoms for t in other):
                continue
            parts = [atoms[t] for t in other]
            for sub in fragments[pid]:
                if chinese_match(zh, parts + [{'zh_candidates': [sub]}]):
                    found[sub].add(pid)
        choices = sorted(((len(pids), len(sub), sub, pids) for sub, pids in found.items()
                          if len({pairs[pid][0] for pid in pids}) >= 2), reverse=True)
        variants = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
        explained = set()
        for count, length, sub, pids in choices:
            if not (pids - explained):
                continue
            if sub not in variants:
                variants.append(sub)
            explained.update(pids)
            if len(variants) >= 4:
                break
        if len(explained) >= max(2, len(supports[gram]) / 2):
            refined[gram] = (variants, aligned[gram][1], len(explained) / len(supports[gram]))
        elif variants:
            merged = list(entry['zh_candidates'])
            merged.extend(z for z in variants if z not in merged)
            refined[gram] = (merged, aligned[gram][1], aligned[gram][2])
    aligned.update(refined)


# 分布熵（bit）：邻居花样多少
def entropy_bits(counter):
    total = sum(counter.values())
    if not total:
        return 0.0
    return -sum((count / total) * math.log2(count / total) for count in counter.values())


# 把词元串递归切成 bank 里的已知单元
def outside_units(toks, bank):
    if not toks:
        return []
    for end in range(min(MAX_GRAM, len(toks)), 0, -1):
        gram = toks[:end]
        if gram in bank:
            rest = outside_units(toks[end:], bank)
            if rest is not None:
                return [bank[gram]] + rest
    if toks[0] in CONNECTORS:
        return outside_units(toks[1:], bank)
    return None


# 交叉核对：片段唯一出现、前后可解释、中文可拼、≥2 个不同邻居做证
def verify_nested(grams, aligned, bank, supports, pairs, fragments, whole, names):
    for gram in grams:
        info = aligned.get(gram)
        if not info:
            continue
        found = defaultdict(set)
        head_of = {}
        for pid in supports[gram]:
            en, zh = pairs[pid]
            toks = names[en]
            positions = [i for i in range(len(toks) - len(gram) + 1)
                         if toks[i:i + len(gram)] == gram]
            if len(positions) != 1:
                continue
            start = positions[0]
            before = outside_units(toks[:start], bank)
            after = outside_units(toks[start + len(gram):], bank)
            if before is None or after is None or not before and not after:
                continue
            outside = toks[start + len(gram):] or toks[:start]
            head_of[pid] = outside[-1]
            for sub in fragments[pid]:
                if chinese_match(zh, before + after + [{'zh_candidates': [sub]}]):
                    found[sub].add(pid)
        eligible = sorted(((len(pids), len(sub), sub, pids)
                           for sub, pids in found.items()
                           if len({head_of[pid] for pid in pids}) >= 2), reverse=True)
        exact = sorted({pairs[pid][1] for pid in whole.get(gram, ()) if pairs[pid][1]})
        variants = list(exact)
        covered = set()
        for count, length, sub, pids in eligible:
            extra = pids - covered
            if len({head_of[pid] for pid in extra}) < 2:
                continue
            if sub not in variants:
                variants.append(sub)
            covered.update(pids)
            if len(variants) >= max(4, len(exact)):
                break
        if len(covered) >= max(2, len(supports[gram]) / 2):
            aligned[gram] = (variants, info[1], len(covered) / len(supports[gram]))


# 只保留核验真正用到的中文变体
def trim_variants(entries, audit, by_id):
    observed = defaultdict(set)
    for row in audit:
        parts = [by_id[cid] for cid in row['terms']]
        for cid in set(row['terms']):
            entry = by_id[cid]
            if entry['kind'] == 'exception' or row['terms'].count(cid) > 1:
                observed[cid].update(entry['zh_candidates'])
                continue
            for variant in entry['zh_candidates']:
                narrowed = [dict(part, zh_candidates=[variant]) if part['id'] == cid
                            else part for part in parts]
                if chinese_match(row['zh'], narrowed):
                    observed[cid].add(variant)
    for entry in entries:
        entry['zh_candidates'] = [z for z in entry['zh_candidates']
                                 if z in observed[entry['id']]]


def compact_entry(entry):
    return {'id': entry['id'], 'en': entry['en'], 'zh': entry['zh_candidates']}


# 预算内最大覆盖贪心：挑覆盖行数最多的条目组合
def select_entries(entries, audit, budget):
    by_id = {entry['id']: entry for entry in entries}
    bundles = defaultdict(int)
    for row in audit:
        bundles[frozenset(row['terms'])] += 1
    selected = set()
    order = []
    while len(selected) < len(entries):
        gains = defaultdict(int)
        for deps, count in bundles.items():
            missing = deps - selected
            if missing:
                gains[missing] += count
        if not gains:
            break
        remaining = budget - len(selected) if budget else len(entries)
        choices = [(gain / len(missing), gain, tuple(sorted(missing)), missing)
                   for missing, gain in gains.items() if len(missing) <= remaining]
        if not choices:
            break
        _, _, _, best = max(choices)
        for entry_id in sorted(best, key=lambda cid: (-by_id[cid]['uses'], cid)):
            selected.add(entry_id)
            order.append(by_id[entry_id])
    return order


def stripped(text):
    return re.sub(r'\s+', '', text)


# 只有 unit 条目进可组合词典
def build_lexicon(entries, atoms):
    lexicon = {}
    for entry in list(entries.values()) + atoms:
        if entry['kind'] != 'unit':
            continue
        tokens = name_tokens(entry['en'])
        if tokens:
            lexicon[tokens] = entry
    return lexicon


def load_standalone(rows):
    standalone = defaultdict(set)
    for _, en, zh in rows:
        standalone[norm_lemma(en)].add(zh)
    return standalone


def unit_variants(entries):
    variants = set()
    for entry in entries.values():
        if entry['kind'] == 'unit':
            variants.update(entry['zh_candidates'])
    return variants


# 译文能否被变体集合切分覆盖（DP）
def accounted(variants, zh):
    target = stripped(zh)
    reachable = [False] * (len(target) + 1)
    reachable[0] = True
    for end in range(1, len(target) + 1):
        for start in range(end):
            if reachable[start] and target[start:end] in variants:
                reachable[end] = True
                break
    return reachable[-1]


def row_tokens(en):
    return name_tokens(en) or tuple(tokens_lc(en))


# 找英文词元里能对上目标中文的条目跨度
def span_variants(lexicon, target, tokens):
    spans = []
    for start in range(len(tokens)):
        for end in range(start + 1, len(tokens) + 1):
            entry = lexicon.get(tokens[start:end])
            if entry is None:
                continue
            found = [z for z in entry['zh_candidates']
                     if z and z != target and target.count(z) == 1]
            if found:
                spans.append((start, end, max(found, key=lambda z: (len(z), z))))
    return spans


def has_literal(pattern):
    return any(not token.startswith('{') and token not in CONNECTORS for token in pattern)


def add_template(templates, pattern, zh_pattern, row, fillers):
    record = templates.setdefault((pattern, zh_pattern),
                                  {'keys': set(), 'fillers': set(), 'pairs': set()})
    record['keys'].add(row['key'])
    record['fillers'].add(fillers)
    record['pairs'].add((row['en'], row['zh']))


# 从例外行切句子骨架（单槽 + 双槽）
def extract_templates(audit, lexicon):
    templates = {}
    for row in audit:
        tokens = row_tokens(row['en'])
        target = stripped(row['zh'])
        if not tokens or not target:
            continue
        spans = span_variants(lexicon, target, tokens)
        for start, end, variant in spans:
            pattern = tokens[:start] + ('{0}',) + tokens[end:]
            if not has_literal(pattern):
                continue
            cut = target.index(variant)
            add_template(templates, pattern, target[:cut] + '{0}' + target[cut + len(variant):],
                         row, tokens[start:end])
        for first in range(len(spans)):
            for second in range(first + 1, len(spans)):
                i1, j1, v1 = spans[first]
                i2, j2, v2 = spans[second]
                if j1 > i2:
                    continue
                p1, p2 = target.index(v1), target.index(v2)
                if not (p1 + len(v1) <= p2 or p2 + len(v2) <= p1):
                    continue
                pattern = tokens[:i1] + ('{0}',) + tokens[j1:i2] + ('{1}',) + tokens[j2:]
                if not has_literal(pattern):
                    continue
                events = sorted([(p1, len(v1), '{0}'), (p2, len(v2), '{1}')])
                pieces, position = [], 0
                for pos, size, slot in events:
                    pieces.append(target[position:pos])
                    pieces.append(slot)
                    position = pos + size
                pieces.append(target[position:])
                add_template(templates, pattern, ''.join(pieces), row,
                             (tokens[i1:j1], tokens[i2:j2]))
    return templates


def split_pattern(pattern):
    parts, current = [], ''
    for char in pattern:
        if char == '{':
            if current:
                parts.append(('lit', current))
            current = '{'
        elif char == '}':
            parts.append(('slot', current + '}'))
            current = ''
        else:
            current += char
    if current:
        parts.append(('lit', current))
    return parts


# 骨架匹配：字面对齐、槽位吃一段，返回第一组切分
def match_zh(pattern, target):
    parts = split_pattern(pattern)
    found = []

    def visit(index, position, slots):
        if found:
            return
        if index == len(parts):
            if position == len(target):
                found.append(list(slots))
            return
        kind, value = parts[index]
        if kind == 'lit':
            if target.startswith(value, position):
                visit(index + 1, position + len(value), slots)
            return
        for end in range(position + 1, len(target) + 1):
            slots.append(target[position:end])
            visit(index + 1, end, slots)
            slots.pop()
            if found:
                return

    visit(0, 0, [])
    return found[0] if found else None


def match_en(pattern, tokens):
    found = []

    def visit(index, position, spans):
        if found:
            return
        if index == len(pattern):
            if position == len(tokens):
                found.append(list(spans))
            return
        token = pattern[index]
        if token.startswith('{'):
            for end in range(position + 1, len(tokens) + 1):
                spans.append((position, end))
                visit(index + 1, end, spans)
                spans.pop()
                if found:
                    return
            return
        if position < len(tokens) and tokens[position] == token:
            visit(index + 1, position + 1, spans)

    visit(0, 0, [])
    return found[0] if found else None


# 模板门槛：≥2 个不同填充词、≥2 对对照
def confirmed(templates):
    return {key for key, record in templates.items()
            if len(record['fillers']) >= MIN_ROWS and len(record['pairs']) >= MIN_PAIRS}


# 例外行 × 已确认模板做匹配
def prepare(audit, order, variants):
    matched = []
    for row in audit:
        if row['status'] != 'exception' or accounted(variants, row['zh']):
            continue
        tokens = row_tokens(row['en'])
        target = stripped(row['zh'])
        if not tokens or not target:
            continue
        matches = []
        for key in order:
            pattern, zh_pattern = key
            spans = match_en(pattern, tokens)
            if spans is None:
                continue
            slots = match_zh(zh_pattern, target)
            if slots is None:
                continue
            matches.append((key, spans, slots))
        if matches:
            matched.append({'row': row, 'tokens': tokens, 'raw': raw_tokens(row['en']),
                            'target': target, 'matches': matches})
    return matched


# 槽位填充词必须已知（独立条目或独立对照）且可组合
def filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
    entry = lexicon.get(filler)
    if not (entry and entry['id'] in atom_ids):
        known = standalone.get(norm_lemma(surface))
        if not known or slot_zh not in known:
            return False
    return compose(filler, slot_zh, lexicon) is not None


# 逐行用模板解释，成功则记下模板与槽位条目
def attempt(matched, lexicon, standalone, atom_ids, allowed):
    results = {}
    for item in matched:
        for key, spans, slots in item['matches']:
            if allowed is not None and key not in allowed:
                continue
            terms, ok = [], True
            for (start, end), slot_zh in zip(spans, slots):
                filler = item['tokens'][start:end]
                surface = ' '.join(item['raw'][start:end])
                if not filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
                    ok = False
                    break
                terms.append(compose(filler, slot_zh, lexicon))
            if ok:
                results[item['row']['key']] = {'template': key, 'slots': terms}
                break
    return results


# 收集不认识槽位的填充词，供 induce 补条目
def collect_failures(matched, results, lexicon, standalone, atom_ids):
    failed = defaultdict(set)
    for item in matched:
        if item['row']['key'] in results:
            continue
        for key, spans, slots in item['matches']:
            for (start, end), slot_zh in zip(spans, slots):
                filler = item['tokens'][start:end]
                surface = ' '.join(item['raw'][start:end])
                if not filler_ready(filler, surface, slot_zh, lexicon, standalone, atom_ids):
                    failed[(norm_lemma(surface), slot_zh)].add(item['row']['key'])
    return failed


def next_unit_id(entries, atoms):
    numbers = [int(entry_id[1:]) for entry_id in entries
               if entry_id.startswith('u') and entry_id[1:].isdigit()]
    return max(numbers or [0]) + 1 + len(atoms)


def atom_surface(matched, keys, en_norm):
    for item in matched:
        if item['row']['key'] not in keys:
            continue
        for start in range(len(item['tokens'])):
            for end in range(start + 1, len(item['tokens']) + 1):
                surface = ' '.join(item['raw'][start:end])
                if norm_lemma(surface) == en_norm:
                    return surface
    return None


# 反复失败的填充词升格为独立条目（≥2 行）
def induce(matched, entries, lexicon, standalone, atoms, atom_ids):
    for _ in range(MAX_INDUCTION_ROUNDS):
        results = attempt(matched, lexicon, standalone, atom_ids, None)
        failed = collect_failures(matched, results, lexicon, standalone, atom_ids)
        added = 0
        for (en_norm, slot_zh), keys in sorted(failed.items()):
            if len(keys) < MIN_ROWS:
                continue
            tokens = tuple(en_norm.split())
            if tokens in lexicon:
                continue
            surface = atom_surface(matched, keys, en_norm)
            if not surface or name_tokens(surface) != tokens:
                continue
            entry = {'id': 'u%d' % next_unit_id(entries, atoms), 'en': surface,
                    'zh_candidates': [slot_zh], 'kind': 'unit',
                    'reason': 'induced_atom', 'uses': 0}
            lexicon[tokens] = entry
            atoms.append(entry)
            atom_ids.add(entry['id'])
            added += 1
        if not added:
            break
    return atoms


# 迭代裁剪：模板用不够 2 次、原子覆盖不够 2 行/2 对就删
def prune(matched, entries, atoms, pair_of, standalone):
    atom_ids = {atom['id'] for atom in atoms}
    allowed = None
    for _ in range(MAX_PRUNE_ROUNDS):
        lexicon = build_lexicon(entries, atoms)
        results = attempt(matched, lexicon, standalone, atom_ids, allowed)
        uses = Counter(record['template'] for record in results.values())
        kept = {key for key in {match[0] for item in matched for match in item['matches']}
                if uses[key] >= MIN_ROWS}
        covered = defaultdict(set)
        for row_key, record in results.items():
            for entries_in_slot in record['slots']:
                for entry_id in entries_in_slot:
                    if entry_id in atom_ids:
                        covered[entry_id].add(row_key)
        dropped = {entry_id for entry_id in atom_ids
                   if len(covered[entry_id]) < MIN_ROWS
                   or len({pair_of[key] for key in covered[entry_id]}) < MIN_PAIRS}
        if kept == allowed and not dropped:
            break
        allowed = kept
        if dropped:
            atom_ids -= dropped
            atoms[:] = [atom for atom in atoms if atom['id'] not in dropped]
    lexicon = build_lexicon(entries, atoms)
    results = attempt(matched, lexicon, standalone, atom_ids, allowed)
    return atoms, allowed, results


# 模板行核验：重匹配英文、重切中文、槽位逐条核对
def verify_template(row, terms, by_id):
    template = by_id[terms[0]]
    pattern = tuple(template['en'].split(' '))
    tokens = row_tokens(row['en'])
    spans = match_en(pattern, tokens)
    if spans is None:
        return False
    filler_entries = [by_id[entry_id] for entry_id in terms[1:]]
    rebuilt, slot_entries, index = [], [], 0
    for token in pattern:
        if not token.startswith('{'):
            rebuilt.append(token)
            continue
        start, end = spans[int(token[1])]
        chunk, collected = [], []
        while len(collected) < end - start:
            if index >= len(filler_entries):
                return False
            entry_tokens = list(name_tokens(filler_entries[index]['en']))
            if not entry_tokens:
                return False
            collected.extend(entry_tokens)
            chunk.append(filler_entries[index])
            index += 1
        if collected != list(tokens[start:end]):
            return False
        rebuilt.extend(entry['en'] for entry in chunk)
        slot_entries.append(chunk)
    if index != len(filler_entries):
        return False
    if stripped(' '.join(rebuilt)).lower() != stripped(row['en']).lower():
        return False
    target = stripped(row['zh'])
    slots = match_zh(template['zh_candidates'][0], target)
    if slots is None or len(slots) != len(slot_entries):
        return False
    rebuilt = template['zh_candidates'][0]
    for number, (slot_zh, entries_in_slot) in enumerate(zip(slots, slot_entries)):
        if not chinese_match(slot_zh, entries_in_slot):
            return False
        rebuilt = rebuilt.replace('{%d}' % number, slot_zh, 1)
    return stripped(rebuilt) == target


def sort_key(entry):
    return (-entry['uses'], entry['id'])


# 主流水线：对齐 → 出条目 → 模板 → 选条目 → 核验
def build(input_path, budget=0, exclude_keys=None, focus_keys=None):
    # 1. 过滤 key，按 focus 定输出范围
    raw_rows = load_input_rows(str(input_path))
    whitelist, blacklist = load_key_filter()
    excluded = re.compile(exclude_keys) if exclude_keys else None
    rows = [(key, en, zh) for key, en, zh in raw_rows
            if is_product_key(key, whitelist, blacklist)
            and not (excluded and excluded.search(key))]
    scope = set(focus_keys) if focus_keys is not None else None
    scope_rows = [row for row in rows if row[0] in scope] if scope is not None else rows
    # 2. 唯一对照表：英文片段支撑 + 中文候选片段
    pairs = sorted({(en, zh) for _, en, zh in rows})
    pair_id = {pair: pid for pid, pair in enumerate(pairs)}
    pair_keys = defaultdict(list)
    for key, en, zh in rows:
        pair_keys[pair_id[(en, zh)]].append(key)
    supports = defaultdict(set)
    whole = defaultdict(set)
    surfaces = {}
    names = {}
    for pid, (en, zh) in enumerate(pairs):
        toks = name_tokens(en)
        if not toks or clean_en(en) != en or clean_zh(zh) != zh:
            continue
        whole[toks].add(pid)
        names.setdefault(en, toks)
        for start in range(len(toks)):
            for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                gram = toks[start:end]
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                supports[gram].add(pid)
                surfaces.setdefault(gram, ' '.join(raw_tokens(en)[start:end]))
    fragments = [zh_fragments(zh) for en, zh in pairs]
    subdf = Counter(sub for subs in fragments for sub in subs)
    aligned = {gram: translations(gram, support, pairs, fragments, subdf, whole)
               for gram, support in supports.items()
               if len({pairs[pid][0] for pid in support}) >= 2
               or (len(gram) == 1 and gram in whole)}
    # 3. 单词对齐：用已知邻居从整名反推
    refine_atoms(aligned, supports, pairs, fragments, whole)
    # 4. 邻居熵 + 搭配强度门控，锚点递归发现残余片段
    total_tokens = sum(len(toks) for toks in names.values())
    left_neighbors = defaultdict(Counter)
    right_neighbors = defaultdict(Counter)
    for toks in names.values():
        for start in range(len(toks)):
            for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                gram = toks[start:end]
                if gram[0] in STOP or gram[-1] in STOP:
                    continue
                left_neighbors[gram][toks[start - 1] if start else '<BOS>'] += 1
                right_neighbors[gram][toks[end] if end < len(toks) else '<EOS>'] += 1
    frequency = {gram: len({pairs[pid][0] for pid in support})
                 for gram, support in supports.items()}
    strong_atoms = {gram for gram, count in frequency.items()
                    if len(gram) == 1 and count >= MIN_STRONG_FREQ
                    and max(entropy_bits(left_neighbors[gram]),
                            entropy_bits(right_neighbors[gram])) >= ENTROPY_GATE}
    qualified = set()
    for gram, count in frequency.items():
        if len(gram) < 2 or count < MIN_STRONG_FREQ:
            continue
        if max(entropy_bits(left_neighbors[gram]),
               entropy_bits(right_neighbors[gram])) < ENTROPY_GATE:
            continue
        joins = [(count - frequency.get(gram[:i], 0) * frequency.get(gram[i:], 0)
                  / total_tokens) / math.sqrt(count) for i in range(1, len(gram))]
        if joins and min(joins) >= JOIN_GATE:
            qualified.add(gram)
    accepted = set(strong_atoms)
    discovered = set()
    while True:
        proposed = set()
        for toks in names.values():
            for start in range(len(toks)):
                for end in range(start + 1, min(len(toks), start + MAX_GRAM) + 1):
                    if toks[start:end] not in accepted:
                        continue
                    for residual in (toks[:start], toks[end:]):
                        if residual in qualified and residual not in accepted:
                            proposed.add(residual)
        if not proposed:
            break
        accepted |= proposed
        discovered |= proposed
    # 5. 临时词库：给嵌套核对当上下文
    bank = {}
    for gram in sorted(aligned, key=lambda g: (len(g), g)):
        variants = aligned[gram][0]
        if not variants:
            continue
        if len({pairs[pid][0] for pid in supports[gram]}) < 2 and not (
                len(gram) == 1 and gram in whole):
            continue
        if all(compose(gram, zh, bank) is not None for zh in variants):
            continue
        bank[gram] = {'id': gram, 'en': surfaces[gram], 'zh_candidates': variants}
    for gram in discovered:
        if gram in aligned:
            bank.setdefault(gram, {'id': gram, 'en': surfaces[gram],
                                   'zh_candidates': aligned[gram][0]})
    # 6. 交叉核对发现的片段
    verify_nested(discovered, aligned, bank, supports, pairs, fragments, whole, names)
    # 7. 出零件条目：长度升序，已能拼出的不收
    lexicon = {}
    unit_entries = []
    for gram in sorted(supports, key=lambda g: (len(g), g)):
        support = supports[gram]
        distinct = {pairs[pid][0] for pid in support}
        if len(distinct) < 2 and not (len(gram) == 1 and gram in whole):
            continue
        variants, confidence, cover = aligned[gram]
        if not variants:
            continue
        if gram not in discovered and all(compose(gram, zh, lexicon) is not None
                                          for zh in variants):
            continue
        entry = {'id': 'u%d' % (len(unit_entries) + 1), 'en': surfaces[gram],
                'zh_candidates': variants, 'kind': 'unit',
                'reason': ('nested_phrase' if gram in discovered else
                           'reusable_fragment' if len(distinct) >= 2 else 'standalone_name'),
                'score': round(confidence, 4), 'alignment_cover': round(cover, 4),
                'sources': sorted({key for pid in support for key in pair_keys[pid]}),
                'evidence': [{'variant': variant, 'key': pair_keys[pid][0],
                              'en': pairs[pid][0], 'zh': pairs[pid][1]}
                             for variant in variants
                             for pid in [p for p in sorted(support)
                                         if variant in pairs[p][1]][:2]],
                'uses': 0}
        unit_entries.append(entry)
        lexicon[gram] = entry
    # 8. 逐行组合证明：拼得出算零件行，拼不出收例外条目
    proofs = {}
    exceptions = {}
    for pid, (en, zh) in enumerate(pairs):
        toks = name_tokens(en)
        proof = (compose(toks, zh, lexicon) if clean_en(en) == en
                 and clean_zh(zh) == zh else None)
        if proof is not None:
            proofs[pid] = proof
            continue
        if en not in exceptions:
            exceptions[en] = {'id': 'x%d' % (len(exceptions) + 1), 'en': en,
                              'zh_candidates': [], 'kind': 'exception',
                              'reason': 'missing_translation' if not zh else
                                        'unexplained_translation',
                              'score': 1.0, 'sources': [], 'evidence': [], 'uses': 0}
        entry = exceptions[en]
        if zh and zh not in entry['zh_candidates']:
            entry['zh_candidates'].append(zh)
        entry['sources'].extend(pair_keys[pid])
        if len(entry['evidence']) < 3:
            entry['evidence'].append({'key': pair_keys[pid][0], 'en': en, 'zh': zh})
        proofs[pid] = [entry['id']]
    # 9. 行级台账：记录每行用到的条目（例外行也算）
    all_entries = {entry['id']: entry for entry in unit_entries + list(exceptions.values())}
    audit = []
    for key, en, zh in scope_rows:
        deps = proofs[pair_id[(en, zh)]]
        for entry_id in set(deps):
            all_entries[entry_id]['uses'] += 1
        audit.append({'key': key, 'en': en, 'zh': zh, 'terms': deps,
                      'status': 'exception' if deps[0].startswith('x') else 'compositional'})
    entries = [entry for entry in all_entries.values() if entry['uses']]
    trim_variants(entries, audit, all_entries)
    entries_by_id = {entry['id']: entry for entry in entries}
    standalone = load_standalone(rows)
    # 10. 模板挖掘：例外行切骨架、补原子、迭代裁剪
    templates = extract_templates(audit, build_lexicon(entries_by_id, []))
    order = sorted(confirmed(templates),
                   key=lambda key: (-len(templates[key]['keys']), len(' '.join(key[0])),
                                    key[0], key[1]))
    matched = prepare(audit, order, unit_variants(entries_by_id))
    pair_of = {item['row']['key']: (item['row']['en'], item['row']['zh'])
               for item in matched}
    atoms = induce(matched, entries_by_id, build_lexicon(entries_by_id, []), standalone, [], set())
    atoms, allowed, results = prune(matched, entries_by_id, atoms, pair_of, standalone)
    template_uses = Counter(record['template'] for record in results.values())
    ranked = sorted((key for key in allowed if template_uses[key] >= MIN_ROWS),
                    key=lambda key: (-template_uses[key], key[0], key[1]))
    # 11. 模板条目定稿，预算内选条目，汇总统计
    template_entries = [{'id': 't%d' % number, 'en': ' '.join(key[0]),
                         'zh_candidates': [key[1]], 'kind': 'template',
                         'reason': 'sentence_template', 'uses': template_uses[key],
                         'sources': sorted(row_key for row_key, record in results.items()
                                           if record['template'] == key),
                         'evidence': [{'key': row_key, 'en': pair_of[row_key][0],
                                       'zh': pair_of[row_key][1]}
                                      for row_key in sorted(
                                          row_key for row_key, record in results.items()
                                          if record['template'] == key)[:2]]}
                        for number, key in enumerate(ranked, 1)]
    template_ids = {key: entry['id'] for key, entry in zip(ranked, template_entries)}
    emitted = []
    for row in audit:
        row = dict(row, pending=[])
        record = results.get(row['key'])
        if record is not None:
            terms = [template_ids[record['template']]]
            for entries_in_slot in record['slots']:
                terms.extend(entries_in_slot)
            row['terms'] = list(dict.fromkeys(terms))
            row['status'] = 'compositional'
        emitted.append(row)
    referenced = Counter(entry_id for row in emitted for entry_id in set(row['terms']))
    for entry in entries_by_id.values():
        entry['uses'] = referenced.get(entry['id'], 0)
    for atom in atoms:
        atom['uses'] = referenced.get(atom['id'], 0)
        atom['sources'] = sorted(row_key for row_key, record in results.items()
                                 if atom['id'] in {entry_id for slot in record['slots']
                                                   for entry_id in slot})
        atom['evidence'] = [{'key': row_key, 'en': pair_of[row_key][0],
                             'zh': pair_of[row_key][1]} for row_key in atom['sources'][:2]]
    batch = [entry for entry in entries_by_id.values()
             if entry['kind'] == 'unit' or referenced.get(entry['id'], 0)]
    batch.extend(template_entries)
    batch.extend(atoms)
    batch = (sorted((entry for entry in batch if entry['kind'] == 'unit'), key=sort_key)
             + sorted((entry for entry in batch if entry['kind'] == 'template'), key=sort_key)
             + sorted((entry for entry in batch if entry['kind'] == 'exception'), key=sort_key))
    totals = Counter(entry_id for key, en, zh in rows
                     for entry_id in set(proofs[pair_id[(en, zh)]]))
    for entry in batch:
        entry['total_uses'] = totals.get(entry['id'], 0)
    review = select_entries(batch, emitted, budget)
    selected = {entry['id'] for entry in review}
    for row in emitted:
        row['pending'] = sorted(set(row['terms']) - selected)
    backlog = [entry for entry in batch if entry['id'] not in selected]
    report = verify_rows(emitted, review)
    source_chars = sum(len(packed({'en': en, 'zh_candidates': [zh]})) + 1
                       for key, en, zh in scope_rows)
    review_chars = sum(len(packed(compact_entry(entry))) + 1 for entry in review)
    stats = {'input_rows': len(raw_rows), 'filtered_rows': len(scope_rows),
             'context_rows': len(rows),
             'unique_pairs': len(pairs),
             'unit_entries': sum(entry['kind'] == 'unit' for entry in batch),
             'nested_entries': sum(entry['reason'] == 'nested_phrase' for entry in batch),
             'exception_entries': sum(entry['kind'] == 'exception' for entry in batch),
             'template_entries': sum(entry['kind'] == 'template' for entry in batch),
             'candidate_entries': len(batch), 'review_entries': len(review),
             'backlog_entries': len(backlog),
             'compositional_rows': sum(row['status'] == 'compositional' for row in emitted),
             'exception_rows': sum(row['status'] == 'exception' for row in emitted),
             'template_rows': sum(any(cid.startswith('t') for cid in row['terms'])
                                  for row in emitted),
             'accounted_rows': len(emitted),
             'ready_rows': sum(not row['pending'] for row in emitted),
             'pending_rows': sum(bool(row['pending']) for row in emitted),
             'input_chars': source_chars, 'review_chars': review_chars,
             'reading_reduction': 1 - review_chars / source_chars if source_chars else 0.0,
             'rescued_rows': len(results),
             'removed_exception_entries': sum(1 for entry in entries_by_id.values()
                                            if entry['kind'] == 'exception'
                                            and not referenced.get(entry['id'], 0)),
             'added_atoms': len(atoms),
             'reconstructed_rows': report['reconstructed'],
             'failed_keys': report['failed_keys']}
    return {'review': review, 'candidates': batch, 'backlog': backlog,
            'audit': emitted, 'stats': stats}


def write_candidates(stream, result):
    writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
    writer.writerow(['id', 'en', 'zh', 'kind', 'uses', 'reason', 'score',
                     'sources', 'evidence'])
    for entry in result['candidates']:
        writer.writerow([entry['id'], entry['en'], '|'.join(entry['zh_candidates']),
                         entry['kind'], entry['uses'], entry['reason'], entry.get('score', ''),
                         ';'.join(entry['sources']), packed(entry['evidence'])])


# 无损核验：例外/模板/零件三种行各按各的查法重放
def verify_rows(rows, entries):
    by_id = {entry['id']: entry for entry in entries}
    failed = []
    checked = pending = 0
    for row in rows:
        if row.get('pending'):
            pending += 1
            continue
        checked += 1
        if any(cid not in by_id for cid in row['terms']):
            failed.append(row['key'])
            continue
        parts = [by_id[cid] for cid in row['terms']]
        if row['status'] == 'exception':
            valid = (len(parts) == 1 and parts[0]['en'] == row['en']
                     and (row['zh'] in parts[0]['zh_candidates']
                          or not row['zh'] and not parts[0]['zh_candidates']))
        elif row['terms'][0].startswith('t'):
            valid = verify_template(row, row['terms'], by_id)
        else:
            expected = tuple(t for t in name_tokens(row['en']) if t not in CONNECTORS)
            actual = tuple(t for entry in parts for t in name_tokens(entry['en'])
                           if t not in CONNECTORS)
            valid = bool(expected) and actual == expected and chinese_match(row['zh'], parts)
        if not valid:
            failed.append(row['key'])
    return {'checked': checked, 'reconstructed': checked - len(failed),
            'pending': pending, 'failed_keys': failed}


JUDGE_SYSTEM = ('You curate a Minecraft glossary of reusable translation units. For each entry you get '
                'an English term and proposed Simplified Chinese variants. Return the final zh variant '
                'list: keep the correct proposals or replace them, preferring the established Minecraft '
                'translation. Reply with one JSON object keyed by entry id only: '
                '{"<id>": {"zh": ["..."], "reason": "one line"}}.')


def known_pairs(paths):
    pairs = {}
    missing = 0
    for path in paths or []:
        if not os.path.exists(path):
            sys.stderr.write('known file not found: %s\n' % path)
            missing += 1
            continue
        with open(path, encoding='utf-8', newline='') as stream:
            for row in csv.reader(stream, delimiter='\t', quoting=csv.QUOTE_NONE):
                if len(row) < 2:
                    continue
                en = clean_en(row[0])
                if not en or en.lower() == 'en':
                    continue
                lemma = norm_lemma(en)
                if not lemma:
                    continue
                bucket = pairs.setdefault(lemma, [])
                for value in (clean_zh(v) for v in row[1].split('|')):
                    if value and value not in bucket:
                        bucket.append(value)
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


def strip_fences(text):
    text = (text or '').strip()
    text = re.sub(r'^```[A-Za-z]*\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def parse_verdicts(content):
    text = strip_fences(content)
    data = None
    try:
        data = json.loads(text)
    except Exception:
        match = re.search(r'\{.*\}', text, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if isinstance(data, list):
        if len(data) == 1:
            data = data[0]
        elif data and all(isinstance(item, dict) and 'id' in item for item in data):
            data = {str(item['id']): item for item in data}
        else:
            merged = {}
            for item in data:
                if isinstance(item, dict):
                    merged.update(item)
            data = merged
    return data if isinstance(data, dict) else {}


def verdict_variants(entry):
    values = entry
    if isinstance(entry, dict):
        values = entry.get('zh')
        if values is None:
            values = entry.get('variants')
    if isinstance(values, str):
        values = values.split('|')
    if not isinstance(values, (list, tuple)):
        return []
    out = []
    for value in values:
        value = clean_zh(str(value or ''))
        if value and value not in out:
            out.append(value)
    return out


def verdict_reason(entry, fallback):
    if isinstance(entry, dict):
        reason = entry.get('reason') or entry.get('why')
        if reason:
            return ' '.join(str(reason).split())
    return fallback


def entry_row(entry):
    return {'id': entry['id'], 'en': entry['en'], 'zh': '|'.join(entry['zh_candidates']),
            'kind': entry['kind'], 'uses': entry['uses'], 'reason': entry['reason'],
            'score': entry.get('score', ''), 'sources': ';'.join(entry['sources']),
            'total_uses': entry.get('total_uses', entry['uses']),
            'evidence': entry['evidence']}


def variants_of(row):
    return [value for value in (clean_zh(v) for v in (row.get('zh') or '').split('|')) if value]


def label_domains(row):
    domains = {key.split('.')[0] for key in (row.get('sources') or '').split(';') if key}
    extra = sorted(domains - {'block', 'item', 'entity'})
    return extra if domains and not (domains & {'block', 'item', 'entity'}) else []


def diff_context(path):
    if not path or not str(path).endswith('.json'):
        return {}, {}, [], {}
    with open(str(path), encoding='utf-8') as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        return {}, {}, [], {}
    meta = {'from': data.get('from') or '', 'to': data.get('to') or '',
            'source_diff': Path(path).as_posix()}
    origins = {}
    order = {}
    for section in ('added', 'changed'):
        block = data.get(section)
        if isinstance(block, dict):
            for key, value in block.items():
                order.setdefault(key, len(order))
                if section == 'changed' and isinstance(value, dict) and value.get('origin_zh'):
                    origins[key] = [v for v in str(value['origin_zh']).split('|') if v]
    removed = []
    block = data.get('removed')
    if isinstance(block, dict):
        for key, value in block.items():
            if not isinstance(value, dict):
                continue
            en = value.get('en_us') or ''
            zh = [v for v in str(value.get('zh_cn') or '').split('|') if v]
            if en and is_product_key(key, *load_key_filter()):
                removed.append({'en': [en], 'zh': zh})
    return meta, origins, removed, order


def review_entry(row, variants, reason, origins):
    entry = {'en': [row['en']], 'zh': list(variants)}
    if int(row.get('total_uses') or 0) == 1:
        entry['single_use'] = True
    labels = label_domains(row)
    if labels:
        entry['labels'] = labels
    revised = sorted({origin for key in (row.get('sources') or '').split(';')
                      for origin in origins.get(key, [])})
    if revised:
        entry['origin_zh'] = revised
    if reason:
        entry['reason'] = reason
    return entry


def format_document(value, indent=0):
    pad = ' ' * indent
    if isinstance(value, dict):
        if not value:
            return '{}'
        items = list(value.items())
        lines = ['{']
        for index, (key, item) in enumerate(items):
            lines.append('%s%s: %s%s' % (' ' * (indent + 2),
                                         json.dumps(key, ensure_ascii=False),
                                         format_document(item, indent + 2),
                                         ',' if index < len(items) - 1 else ''))
        lines.append(pad + '}')
        return '\n'.join(lines)
    if isinstance(value, list):
        if not value:
            return '[]'
        if all(isinstance(item, str) for item in value):
            return '[' + ', '.join(json.dumps(item, ensure_ascii=False) for item in value) + ']'
        lines = ['[']
        for index, item in enumerate(value):
            lines.append('%s%s%s' % (' ' * (indent + 2), format_document(item, indent + 2),
                                     ',' if index < len(value) - 1 else ''))
        lines.append(pad + ']')
        return '\n'.join(lines)
    return json.dumps(value, ensure_ascii=False)


def llm_verdicts(chunk, base, model, api_key):
    entries = []
    for entry in chunk:
        item = {'id': entry['id'], 'en': entry['en'],
                'zh_candidates': [v for v in (entry.get('zh') or '').split('|') if v],
                'kind': entry.get('kind') or '', 'uses': entry.get('uses') or ''}
        evidence = entry.get('evidence')
        if isinstance(evidence, str):
            try:
                evidence = json.loads(evidence or '[]')
            except Exception:
                evidence = []
        if evidence:
            item['evidence'] = evidence
        entries.append(item)
    payload = {'model': model, 'temperature': 0,
               'messages': [{'role': 'system', 'content': JUDGE_SYSTEM},
                            {'role': 'user', 'content': packed({'entries': entries})}]}
    request = urllib.request.Request(base + '/chat/completions',
                                     data=json.dumps(payload).encode('utf-8'),
                                     headers={'Content-Type': 'application/json',
                                              'Authorization': 'Bearer ' + api_key})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode('utf-8'))
        return parse_verdicts(body['choices'][0]['message']['content']) or None
    except Exception as exc:
        sys.stderr.write('batch failed: %s\n' % exc)
        return None


# 生成审校 JSON：跳过模板/已收/可推导；LLM 复核暂停时原样通过
def judge_cmd(args):
    focus = load_focus_keys(args.focus) if args.focus else None
    result = build(args.input, args.budget, args.exclude_keys, focus)
    rows = [entry_row(entry) for entry in result['review']]
    meta, origins, removed, order = diff_context(args.focus or args.input)
    known, missing = known_pairs(args.known)
    queue = []
    skipped_template = skipped_known = skipped_derived = 0
    for row in rows:
        if row['kind'] == 'template':
            skipped_template += 1
            continue
        plain = variants_of(row)
        variants = [stripped(value) for value in plain]
        lemma = norm_lemma(clean_en(row['en']))
        if lemma in known and all(value in known[lemma] for value in plain):
            skipped_known += 1
            continue
        made = compositions(row['en'], known)
        if made and variants and all(value in made for value in variants):
            skipped_derived += 1
            continue
        queue.append(row)
    if order:
        queue.sort(key=lambda row: min([order.get(key, len(order))
                                        for key in row['sources'].split(';') if key]
                                       or [len(order)]))
    entries = []
    judged = auto = failed = 0

    def accept(row, variants, reason):
        entries.append(review_entry(row, variants, reason, origins))

    # LLM 复核暂停：条目全部按原样通过。恢复时取消注释、删掉下面的直通。
    # api_key = os.environ.get('LLM_API_KEY')
    # base = (os.environ.get('LLM_BASE_URL') or 'https://api.openai.com/v1').rstrip('/')
    # model = os.environ.get('LLM_MODEL') or 'gpt-4o-mini'
    # if api_key:
    #     size = max(1, args.batch_size)
    #     for start in range(0, len(queue), size):
    #         chunk = queue[start:start + size]
    #         verdicts = llm_verdicts(chunk, base, model, api_key)
    #         if verdicts is None:
    #             failed += 1
    #             for row in chunk:
    #                 accept(row, variants_of(row), '')
    #                 auto += 1
    #             continue
    #         for row in chunk:
    #             verdict = verdicts.get(row['id'])
    #             variants = verdict_variants(verdict)
    #             if variants:
    #                 accept(row, variants, verdict_reason(verdict, ''))
    #                 judged += 1
    #             else:
    #                 accept(row, variants_of(row), '')
    #                 auto += 1
    # else:
    for row in queue:
        accept(row, variants_of(row), '')
        auto += 1
    document = {}
    if meta.get('from') or meta.get('to'):
        document.update({'from': meta['from'], 'to': meta['to'],
                         'source_diff': meta['source_diff']})
    document['added_count'] = len(entries)
    document['added'] = entries
    document['updated_count'] = 0
    document['updated'] = []
    document['removed_count'] = len(removed)
    document['removed'] = removed
    source = args.focus or (args.input if str(args.input).endswith('.json') else None)
    out = args.out or (Path(source).with_suffix('.terms.json') if source
                       else Path('terms.json'))
    if out.parent != Path(''):
        out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as stream:
        stream.write(format_document(document) + '\n')
    print(packed({'out': str(out), 'entries': len(rows), 'added': len(entries),
                  'judged': judged, 'auto': auto, 'skipped_known': skipped_known,
                  'skipped_derived': skipped_derived, 'skipped_template': skipped_template,
                  'batches_failed': failed, 'known_files_missing': missing, **result['stats']}))
    return 0


CASES_PATH = Path(__file__).with_name('termgen_cases.json')


CASE_FIELDS = ('key', 'en', 'zh', 'expect', 'required_terms', 'reason')
EXPECT = ('unit', 'compositional', 'exception')


def _en_of(item):
    return item.get('en', '') if isinstance(item, dict) else item


def _zh_of(item):
    if not isinstance(item, dict):
        return []
    val = item.get('zh_candidates')
    if val is None:
        val = item.get('zh')
    if val is None:
        return []
    if isinstance(val, str):
        val = val.split('|')
    out = []
    for v in val:
        v = clean_zh(str(v)).strip()
        if v:
            out.append(v)
    return out


def _variants(s):
    out = []
    for v in str(s or '').split('|'):
        v = clean_zh(v).strip()
        if v:
            out.append(v)
    return out


def _norm_set(terms):
    out = set()
    for t in terms or ():
        n = norm_lemma(_en_of(t) or '')
        if n:
            out.add(n)
    return out


def _ratio(num, den):
    return (num / den) if den else None


def _zh_ok(want, got_lists):
    if not want:
        return None
    saw_empty = False
    for got in got_lists:
        if not got:
            saw_empty = True
            continue
        for w in want:
            if w in got:
                return True
    return None if saw_empty else False


def load_cases(path=None):
    with open(path or CASES_PATH, encoding='utf-8') as f:
        data = json.load(f)
    cases = data.get('cases') if isinstance(data, dict) else data
    out = []
    for c in cases or ():
        missing = [k for k in CASE_FIELDS if k not in c]
        if missing:
            raise ValueError('case %r missing %s' % (c.get('key'), ','.join(missing)))
        if c['expect'] not in EXPECT:
            raise ValueError('case %r has bad expect %r' % (c['key'], c['expect']))
        out.append(c)
    return out


# 对 gold 算召回、命中率、字符减少
def measure(gold_terms, candidate_terms, review_terms, reachable_terms, input_chars, review_chars,
            baseline_terms=None, baseline_chars=None):
    gold_terms = list(gold_terms)
    candidate_terms = list(candidate_terms)
    review_terms = list(review_terms)
    reachable_terms = list(reachable_terms)
    gold = _norm_set(gold_terms)
    cand = _norm_set(candidate_terms)
    rev = _norm_set(review_terms)
    reach = _norm_set(reachable_terms)
    cand_entries = [t for t in (candidate_terms or ()) if _en_of(t)]
    rev_entries = [t for t in (review_terms or ()) if _en_of(t)]
    out = {
        'gold': len(gold),
        'reachable_gold': len(reach),
        'candidate_gold': len(cand & gold),
        'review_gold': len(rev & gold),
        'candidate_count': len(cand),
        'review_count': len(rev),
        'candidate_entries': len(cand_entries),
        'review_entries': len(rev_entries),
        'candidate_reachable_hits': len(cand & reach),
        'review_reachable_hits': len(rev & reach),
        'candidate_recall': _ratio(len(cand & reach), len(reach)),
        'review_recall': _ratio(len(rev & reach), len(reach)),
        'positive_match_rate': _ratio(len(rev & gold), len(rev)),
        'input_chars': input_chars,
        'review_chars': review_chars,
        'char_reduction': (1.0 - review_chars / input_chars) if (input_chars and review_chars is not None) else None,
        'baseline': None,
    }
    if baseline_terms is not None or baseline_chars is not None:
        base = _norm_set(baseline_terms or ())
        base_gold = len(base & gold)
        base_hits = len(base & reach)
        b = {
            'count': len(base),
            'gold': base_gold,
            'reachable_hits': base_hits,
            'recall': _ratio(base_hits, len(reach)),
            'positive_match_rate': _ratio(base_gold, len(base)),
            'chars': baseline_chars,
            'char_reduction': (1.0 - baseline_chars / input_chars) if (input_chars and baseline_chars is not None) else None,
        }
        if baseline_chars:
            b['char_saving'] = baseline_chars - (review_chars or 0)
            b['char_ratio'] = _ratio(review_chars, baseline_chars)
        if b['recall'] is not None and out['review_recall'] is not None:
            b['recall_delta'] = out['review_recall'] - b['recall']
        out['baseline'] = b
    return out


def _iter_comps(compositions):
    if compositions is None:
        return []
    if isinstance(compositions, dict):
        seq = []
        for en, val in compositions.items():
            if isinstance(val, dict):
                seq.append({'en': en, 'parts': val.get('parts') or val.get('refs') or (),
                            'zh': val.get('zh_candidates', val.get('zh'))})
            else:
                seq.append({'en': en, 'parts': val})
        return seq
    return list(compositions)


# 评估用例打分：unit / compositional / exception
def score_cases(cases, entries, compositions=None, strict_kind=False):
    entry_rows = []
    for c in entries or ():
        entry_rows.append((norm_lemma(_en_of(c) or ''), _zh_of(c),
                          c.get('kind') if isinstance(c, dict) else None))
    comp_rows = []
    for c in _iter_comps(compositions):
        comp_rows.append((norm_lemma(c.get('en') or ''), _norm_set(c.get('parts') or ()), _zh_of(c)))
    available = {n for n, _, _ in entry_rows}

    out = {'total': len(cases), 'covered': 0, 'coverage': None, 'zh_unchecked': 0,
           'kind_mismatch': 0, 'parts_ready': 0, 'delivered_kinds': {}, 'by_expect': {},
           'missed': []}
    for expect in EXPECT:
        out['by_expect'][expect] = {'total': 0, 'covered': 0}
    for _, _, kind in entry_rows:
        if kind:
            out['delivered_kinds'][kind] = out['delivered_kinds'].get(kind, 0) + 1

    for case in cases:
        en = norm_lemma(case.get('en') or '')
        expect = case.get('expect')
        want = _variants(case.get('zh'))
        rec = {'key': case.get('key'), 'en': case.get('en'), 'expect': expect}
        why = []
        if expect == 'compositional':
            req = _norm_set(case.get('required_terms') or ())
            comps = [r for r in comp_rows if r[0] == en]
            missing = sorted(t for t in req if t not in available)
            refs_ok = any(req <= parts for _, parts, _ in comps) if comps else False
            zh_ok = _zh_ok(want, [zh for _, _, zh in comps]) if comps else None
            if not comps:
                why.append('no_composition')
            elif not refs_ok:
                why.append('composition_does_not_reference_required')
            if missing:
                why.append('missing_parts')
            if zh_ok is False:
                why.append('zh_mismatch')
            covered = bool(comps) and refs_ok and not missing and zh_ok is not False
            if not missing:
                out['parts_ready'] += 1
            rec['composition_found'] = bool(comps)
            rec['missing_parts'] = missing
        else:
            matches = [r for r in entry_rows if r[0] == en]
            if strict_kind:
                matches = [r for r in matches if r[2] == expect]
            zh_ok = _zh_ok(want, [zh for _, zh, _ in matches]) if matches else None
            if not matches:
                why.append('no_entry')
            elif zh_ok is False:
                why.append('zh_mismatch')
            covered = bool(matches) and zh_ok is not False
            kinds = sorted({k for _, _, k in matches if k})
            if kinds:
                rec['entry_kind'] = kinds
                if expect not in kinds and not strict_kind:
                    out['kind_mismatch'] += 1
        if covered and zh_ok is None:
            out['zh_unchecked'] += 1
        bucket = out['by_expect'].setdefault(expect, {'total': 0, 'covered': 0})
        bucket['total'] += 1
        if covered:
            out['covered'] += 1
            bucket['covered'] += 1
        else:
            rec['why'] = why or ['uncovered']
            out['missed'].append(rec)
    out['coverage'] = _ratio(out['covered'], out['total'])
    return out


def run_cases(result, path):
    selected = {entry['id']: entry for entry in result['review']}
    compositions = [{'en': row['en'], 'zh': row['zh'],
                     'parts': [selected[cid]['en'] for cid in row['terms']]}
                    for row in result['audit']
                    if row['status'] == 'compositional' and not row['pending']]
    cases = load_cases(path)
    report = score_cases(cases, result['review'], compositions)
    by_key = {row['key']: row for row in result['audit']}
    sample = [{**by_key[case['key']], 'en': case['en'], 'zh': case['zh']}
              for case in cases if case['key'] in by_key]
    report['reconstruction'] = verify_rows(sample, result['review'])
    report['absent_keys'] = [case['key'] for case in cases if case['key'] not in by_key]
    return report


def benchmark(args, result):
    gold = [en for en, zh in load_gold(args.gold)]
    reachable = set()
    names = [tuple(norm_lemma(row['en']).split()) for row in result['audit']]
    for en in gold:
        gram = tuple(norm_lemma(en).split())
        if any(any(toks[i:i + len(gram)] == gram for i in range(len(toks) - len(gram) + 1))
               for toks in names):
            reachable.add(en)
    metrics = measure(gold, [entry['en'] for entry in result['candidates']],
                      [entry['en'] for entry in result['review']], reachable,
                      result['stats']['input_chars'], result['stats']['review_chars'])
    print(json.dumps({'stats': result['stats'], 'metrics': metrics,
                      'reconstruction': verify_rows(result['audit'], result['review']),
                      'cases': run_cases(result, args.cases)}, ensure_ascii=False, indent=2))


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError('must be zero or positive')
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(prog='termgen.py')
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('extract', 'bench', 'judge'):
        p = sub.add_parser(command)
        p.add_argument('--input', type=Path, default=ROOT / 'Vanilla/latest.tsv')
        p.add_argument('--budget', type=nonnegative, default=0,
                       help='maximum review entries; 0 keeps the complete compressed inventory')
        p.add_argument('--exclude-keys')
        if command != 'bench':
            p.add_argument('--focus', type=Path,
                           help='diff json or key list; keep the full corpus for alignment '
                                'but emit only entries and rows for those keys')
        if command == 'bench':
            p.add_argument('--gold', action='append', default=[])
            p.add_argument('--cases', type=Path, default=Path(__file__).with_name('termgen_cases.json'))
        elif command == 'judge':
            p.add_argument('--known', nargs='*', default=[],
                           help='terms files whose en or composed zh is already curated')
            p.add_argument('--out', type=Path, help='review json path')
            p.add_argument('--batch-size', type=int, default=40)
    args = parser.parse_args(argv)
    if args.command == 'judge':
        return judge_cmd(args)
    started = time.perf_counter()
    focus_keys = load_focus_keys(args.focus) if getattr(args, 'focus', None) else None
    result = build(args.input, args.budget, args.exclude_keys, focus_keys)
    result['stats']['elapsed_seconds'] = round(time.perf_counter() - started, 3)
    if args.command == 'extract':
        sys.stdout.reconfigure(newline='')  # 重定向到文件时保持 LF
        write_candidates(sys.stdout, result)
        print(packed(result['stats']), file=sys.stderr)
    else:
        args.gold = args.gold or [str(ROOT / 'Vanilla/terms/terms-v1.tsv')]
        benchmark(args, result)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
