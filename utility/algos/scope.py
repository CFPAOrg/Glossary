import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import io_utils as io


def _write_rows_tsv(path, rows):
    if path:
        io.ensure_parent(path)
        stream = open(path, 'w', encoding='utf-8', newline='')
    else:
        sys.stdout.reconfigure(newline='')
        stream = sys.stdout

    try:
        io.write_tsv(stream, ['key', 'en_us', 'zh_cn'], [
            [k, en.replace('\n', '\\n'), zh.replace('\n', '\\n')] for k, en, zh in rows
        ])
    finally:
        if path:
            stream.close()


def _write_rows_json(path, rows):
    payload = {k: {'en_us': en, 'zh_cn': zh} if zh else en for k, en, zh in rows}
    text = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'

    if path:
        io.write_text(path, text)
    else:
        sys.stdout.write(text)


def _diff_rows(old_path, new_path, en_col=None, zh_col=None):
    old_map = {k: (en, zh) for k, en, zh in io.load_input_rows(old_path, en_col=en_col, zh_col=zh_col)}
    new_rows = io.load_input_rows(new_path, en_col=en_col, zh_col=zh_col)

    added, changed, removed = {}, {}, {}
    new_keys = set()

    for k, en, zh in new_rows:
        new_keys.add(k)
        if k not in old_map:
            added[k] = {'en_us': en, 'zh_cn': zh}
        else:
            oen, ozh = old_map[k]
            if oen != en or ozh != zh:
                rec = {'en_us': en, 'zh_cn': zh}
                if oen != en:
                    rec['origin_en'] = oen
                if ozh != zh:
                    rec['origin_zh'] = ozh
                changed[k] = rec

    for k, (oen, ozh) in old_map.items():
        if k not in new_keys:
            removed[k] = {'en_us': oen, 'zh_cn': ozh}

    return {'added': added, 'changed': changed, 'removed': removed}, new_rows


def run_scope(args):
    if args.diff:
        diff_obj, raw_rows = _diff_rows(args.diff[0], args.diff[1], en_col=args.en_col, zh_col=args.zh_col)
        focus_keys = set(diff_obj['added']) | set(diff_obj['changed'])
        if args.diff_only:
            raw_rows = [(k, v['en_us'], v['zh_cn']) for sec in ('added', 'changed') for k, v in diff_obj[sec].items()]
    else:
        raw_rows = io.load_input_rows(args.input, en_col=args.en_col, zh_col=args.zh_col)
        focus_keys = io.load_focus_keys(args.focus) if args.focus else None

    if args.non_empty_zh:
        raw_rows = [(k, en, zh) for k, en, zh in raw_rows if zh.strip()]

    rows = io.filter_rows(
        raw_rows,
        key_filter=args.key_filter,
        keys=args.pattern,
        exclude_keys=args.exclude,
        prefixes=args.prefix,
        filter_file=args.filter_file,
    )

    if focus_keys is not None and not args.diff:
        rows = [r for r in rows if r[0] in focus_keys]
    elif focus_keys is not None and args.diff:
        focus_keys = {k for k, _, _ in rows if k in focus_keys}

    if args.focus_out and focus_keys is not None:
        io.write_text(args.focus_out, '\n'.join(sorted(focus_keys)) + ('\n' if focus_keys else ''))

    if args.format == 'json':
        _write_rows_json(args.out, rows)
    else:
        _write_rows_tsv(args.out, rows)

    summary = {'input_rows': len(raw_rows), 'kept_rows': len(rows), 'out': str(args.out) if args.out else 'stdout'}
    if focus_keys is not None:
        summary['focus_keys'] = len(focus_keys)
    print(json.dumps(summary, ensure_ascii=False), file=sys.stderr)

    return 0


def run_clean(args):
    entries, missing = io.load_glossary_entries([str(p) for p in args.input])
    by_lemma = {}
    duplicates = []

    for entry in entries:
        key = entry['lemma'] or entry['en'].lower()
        if key not in by_lemma:
            by_lemma[key] = {'en': entry['en'], 'zh': list(entry['zh']), 'reason': entry['reason']}
            continue
        duplicates.append(entry['en'])
        existing = by_lemma[key]
        for z in entry['zh']:
            if z not in existing['zh']:
                existing['zh'].append(z)
        if not existing['reason'] and entry['reason']:
            existing['reason'] = entry['reason']

    cleaned = sorted(by_lemma.values(), key=lambda e: e['en'].lower())
    report = {'raw_entries': len(entries), 'cleaned_entries': len(cleaned), 'merged_duplicates': len(duplicates), 'missing_files': missing}

    if args.corpus:
        raw_rows = io.load_input_rows(args.corpus, en_col=args.en_col, zh_col=args.zh_col)
        rows = io.filter_rows(raw_rows, key_filter=args.key_filter, keys=args.pattern, exclude_keys=args.exclude, filter_file=args.filter_file)
        matcher = io.build_term_matcher(cleaned)
        stats = defaultdict(lambda: {'ok': 0, 'fail': 0, 'samples': []})

        for key, en, zh in rows:
            if not zh.strip():
                continue
            for hit in io.match_known_in_row(en, zh, matcher):
                st = stats[hit['en']]
                if hit['ok']:
                    st['ok'] += 1
                else:
                    st['fail'] += 1
                    if len(st['samples']) < 3:
                        st['samples'].append({'key': key, 'en': en, 'zh': zh})

        dead_terms = [e['en'] for e in cleaned if e['en'] not in stats]
        failing_terms = [
            {'en': e['en'], 'zh': '|'.join(e['zh']), 'ok': stats[e['en']]['ok'], 'fail': stats[e['en']]['fail'], 'samples': stats[e['en']]['samples']}
            for e in cleaned if stats[e['en']]['fail'] > 0
        ]
        failing_terms.sort(key=lambda x: (-x['fail'], x['en']))
        report['corpus_rows'] = len(rows)
        report['dead_terms_count'] = len(dead_terms)
        report['failing_terms_count'] = len(failing_terms)
        report['dead_terms'] = dead_terms[:50]
        report['failing_terms'] = failing_terms[:50]

    if args.out:
        io.ensure_parent(args.out)
        with open(args.out, 'w', encoding='utf-8', newline='') as f:
            io.write_tsv(f, ['en', 'zh', 'reason', 'comment'], [[e['en'], '|'.join(e['zh']), e['reason'], ''] for e in cleaned])
        report['out'] = str(args.out)
    elif not args.audit_only:
        sys.stdout.reconfigure(newline='')
        io.write_tsv(sys.stdout, ['en', 'zh', 'reason', 'comment'], [[e['en'], '|'.join(e['zh']), e['reason'], ''] for e in cleaned])
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        return 0

    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0


def add_scope_args(ap, require_input=True):
    if require_input:
        ap.add_argument('--input', type=Path, help='输入语料：TSV / JSON(扁平或diff) / .lang / .txt / lang目录')
    ap.add_argument('--diff', nargs=2, metavar=('OLD', 'NEW'), help='直接比对两份语言文件并圈定差异')
    ap.add_argument('--diff-only', action='store_true', help='仅输出 diff 里的 added/changed 行（不保留上下文）')
    ap.add_argument('--focus', type=Path, help='diff JSON 或 key 清单文件')
    ap.add_argument('--focus-out', type=Path, help='把生效的 focus key 写成清单文件')
    ap.add_argument('--prefix', action='append', default=[], help='保留的 key 前缀（可重复）')
    ap.add_argument('--pattern', help='保留的 key 正则（白名单）')
    ap.add_argument('--exclude', help='排除的 key 正则（黑名单）')
    ap.add_argument('--key-filter', choices=('auto', 'on', 'off'), default='auto',
                    help='key 规则文件过滤：auto 仅在存在且未指定 prefix/pattern 时启用')
    ap.add_argument('--filter-file', type=Path, help='自定义 key 白/黑名单 JSON')
    ap.add_argument('--en-col', help='英文列名或文件名（默认自动探测）')
    ap.add_argument('--zh-col', help='中文列名或文件名（默认自动探测）')
    ap.add_argument('--non-empty-zh', action='store_true', help='丢弃译文为空的行')
    ap.add_argument('--format', choices=('tsv', 'json'), default='tsv')
    ap.add_argument('-o', '--out', type=Path, help='输出路径（默认 stdout）')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='final.py scope')
    add_scope_args(parser)
    args = parser.parse_args(argv)

    if not args.input and not args.diff:
        parser.error('必须提供 --input 或 --diff OLD NEW')

    return run_scope(args)


if __name__ == '__main__':
    raise SystemExit(main())
