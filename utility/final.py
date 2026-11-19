#!/usr/bin/env python3
import argparse
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import io_utils as io
from algos import cjk, compose, prose, scope, single

ALGO_ALIASES = ('compose', 'single', 'cjk', 'prose', 'mod')


def _auto_corpus_type(input_path, en_col=None, zh_col=None):
    rows = io.load_input_rows(input_path, en_col=en_col, zh_col=zh_col)
    lens = sorted(len(en or zh) for _, en, zh in rows if (en or zh).strip())
    if not lens:
        return 'name'

    return 'prose' if lens[len(lens) // 2] >= prose.PROSE_MED_LEN else 'name'


def _cmd_translate(args):
    corpus_type = args.corpus_type
    if corpus_type == 'auto':
        corpus_type = _auto_corpus_type(args.input, en_col=args.en_col, zh_col=args.zh_col)

    if corpus_type == 'name':
        if args.lang == 'en':
            return single.extract(args)
        if args.lang in ('zh', 'ja'):
            args.column = args.zh_col or ('ja_jp' if args.lang == 'ja' else 'zh_cn')
            return cjk.extract(args)

    return prose.run_mine(args)


def _cmd_review(args):
    return prose.run_review(args)


def _cmd_maintain(args):
    corpus_type = args.corpus_type
    if corpus_type == 'auto':
        corpus_type = _auto_corpus_type(args.input, en_col=args.en_col, zh_col=args.zh_col)

    if corpus_type == 'name':
        if args.out_json or (args.focus and str(args.focus).endswith('.json') and not args.out):
            if not args.out and args.out_json:
                args.out = args.out_json
            return compose.judge_cmd(args)
        return compose.run_extract(args)

    return prose.run_maintain_prose(args)


def _build_workflow_parser():
    ap = argparse.ArgumentParser(
        prog='final.py',
        description='术语生产工具套件：scope / translate / review / maintain / clean，兼容 compose / single / cjk / prose',
    )
    sub = ap.add_subparsers(dest='command', required=True)

    p_scope = sub.add_parser('scope', help='圈定语料范围、清洗格式、从 diff 切片')
    scope.add_scope_args(p_scope)
    p_scope.set_defaults(func=lambda a: p_scope.error('必须提供 --input、--diff OLD NEW 或 --style') if not a.input and not a.diff and not a.style else scope.run_scope(a))

    p_tr = sub.add_parser('translate', help='无译文场景：提取待译术语候选与共现家族')
    p_tr.add_argument('--input', type=Path, required=True, help='输入语料：TSV / JSON / .lang / .txt / lang目录')
    p_tr.add_argument('--corpus-type', choices=('auto', 'name', 'prose'), default='auto')
    p_tr.add_argument('--lang', choices=prose.MINE_LANGS, default='en')
    p_tr.add_argument('--ref', choices=prose.MINE_LANGS)
    p_tr.add_argument('--en-col')
    p_tr.add_argument('--zh-col')
    p_tr.add_argument('--key-filter', choices=('auto', 'on', 'off'), default='auto')
    p_tr.add_argument('--keys')
    p_tr.add_argument('--exclude-keys')
    p_tr.add_argument('--filter-file', type=Path)
    p_tr.add_argument('--focus', type=Path)
    p_tr.add_argument('--known', nargs='*', default=[])
    p_tr.add_argument('--min-support', type=int, default=2)
    p_tr.add_argument('--min-impact', type=int, default=2)
    p_tr.add_argument('--entropy-gate', type=float, default=single.ENTROPY_GATE)
    p_tr.add_argument('--join-gate', type=float, default=single.JOIN_GATE)
    p_tr.add_argument('--gates', action='store_true')
    p_tr.add_argument('--family', action='store_true')
    p_tr.add_argument('--family-scope', choices=('pool', 'entries'), default='pool')
    p_tr.add_argument('--min-cooc', type=int, default=2)
    p_tr.add_argument('--min-dice', type=float, default=0.12)
    p_tr.add_argument('--method', choices=('lpa', 'components'), default='lpa')
    p_tr.add_argument('--rounds', type=int, default=30)
    p_tr.add_argument('--top', type=int, default=50)
    p_tr.add_argument('--show', type=int, default=30)
    p_tr.add_argument('--cohesion-gate', type=float, default=cjk.COHESION_GATE)
    p_tr.add_argument('--freedom-gate', type=float, default=cjk.FREEDOM_GATE)
    p_tr.add_argument('--max-len', type=int, default=cjk.MAX_CHAR)
    p_tr.add_argument('--max-name', type=int, default=16)
    p_tr.add_argument('--stopwords', type=Path)
    p_tr.add_argument('--pool', action='store_true')
    p_tr.add_argument('--show-seg', type=int, default=0)
    p_tr.add_argument('--bpe-merges', type=int, default=400)
    p_tr.add_argument('--max-n', type=int, default=None)
    p_tr.add_argument('--min-n', type=int, default=None)
    p_tr.add_argument('--ko-unit', choices=('eojeol', 'syllable'), default='eojeol')
    p_tr.add_argument('--pct-coh', type=float, default=prose.MINE_PCT_COH)
    p_tr.add_argument('--pct-ent', type=float, default=prose.MINE_PCT_ENT)
    p_tr.add_argument('--no-entropy', action='store_true')
    p_tr.add_argument('--termhood', choices=prose.TERMHOODS, default='auto')
    p_tr.add_argument('--limit', type=int, default=0)
    p_tr.add_argument('--format', choices=('tsv', 'json', 'md'), default='tsv')
    p_tr.add_argument('--json', action='store_true')
    p_tr.add_argument('-o', '--out', type=Path)
    p_tr.set_defaults(func=_cmd_translate, out_file=None)

    p_rev = sub.add_parser('review', help='译文不可信场景：排查同词异译、骨架分歧与已知术语违例')
    prose.add_review_args(p_rev)
    p_rev.set_defaults(func=_cmd_review)

    p_mt = sub.add_parser('maintain', help='大体可信译文场景：重建术语表并收容变通例外')
    p_mt.add_argument('--input', type=Path, default=io.ROOT / 'Vanilla/latest.tsv')
    p_mt.add_argument('--corpus-type', choices=('auto', 'name', 'prose'), default='auto')
    p_mt.add_argument('--en-col')
    p_mt.add_argument('--zh-col')
    p_mt.add_argument('--key-filter', choices=('auto', 'on', 'off'), default='auto')
    p_mt.add_argument('--keys')
    p_mt.add_argument('--exclude-keys')
    p_mt.add_argument('--filter-file', type=Path)
    p_mt.add_argument('--focus', type=Path)
    p_mt.add_argument('--known', nargs='*', default=[])
    p_mt.add_argument('--budget', type=compose.nonnegative, default=0)
    p_mt.add_argument('--batch-size', type=int, default=40)
    p_mt.add_argument('--out-json', type=Path, help='输出 *.terms.json 审校清单')
    p_mt.add_argument('--max-n', type=int, default=None)
    p_mt.add_argument('--min-n', type=int, default=None)
    p_mt.add_argument('--min-impact', type=int, default=2)
    p_mt.add_argument('--pct-coh', type=float, default=prose.MINE_PCT_COH)
    p_mt.add_argument('--pct-ent', type=float, default=prose.MINE_PCT_ENT)
    p_mt.add_argument('--no-entropy', action='store_true')
    p_mt.add_argument('--termhood', choices=prose.TERMHOODS, default='auto')
    p_mt.add_argument('--include-known', action='store_true')
    p_mt.add_argument('--format', choices=('tsv', 'json'), default='tsv')
    p_mt.add_argument('--json', action='store_true')
    p_mt.add_argument('-o', '--out', type=Path)
    p_mt.set_defaults(func=_cmd_maintain)

    p_cl = sub.add_parser('clean', help='清洗去重术语表，并可用语料核验死词与误报')
    p_cl.add_argument('--input', type=Path, nargs='+', required=True, help='待清洗的一个或多个术语 TSV')
    p_cl.add_argument('--corpus', type=Path, help='对照语料（用于统计 0 命中死词与误报）')
    p_cl.add_argument('--en-col')
    p_cl.add_argument('--zh-col')
    p_cl.add_argument('--key-filter', choices=('auto', 'on', 'off'), default='auto')
    p_cl.add_argument('--pattern')
    p_cl.add_argument('--exclude')
    p_cl.add_argument('--filter-file', type=Path)
    p_cl.add_argument('--audit-only', action='store_true')
    p_cl.add_argument('-o', '--out', type=Path)
    p_cl.set_defaults(func=scope.run_clean)

    return ap


def _run_mod_compat(rest):
    if rest and rest[0] == 'review':
        ap = argparse.ArgumentParser(prog='final.py mod review')
        ap.add_argument('input', type=Path)
        ap.add_argument('-o', '--out', type=Path)
        ap.add_argument('--top', type=int, default=25)
        ap.add_argument('--min-impact', type=int, default=2)
        args = ap.parse_args(rest[1:])
        if args.out and not str(args.out).endswith('.md'):
            args.out = Path(str(args.out) + '-divergence.md')
        args.format = 'md'
        return prose.run_review(args)

    if rest and rest[0] == 'mine':
        ap = argparse.ArgumentParser(prog='final.py mod mine')
        ap.add_argument('input', type=Path)
        ap.add_argument('lang', choices=prose.MINE_LANGS)
        ap.add_argument('--ref', choices=prose.MINE_LANGS)
        ap.add_argument('-o', '--out')
        ap.add_argument('--max-n', type=int, default=None)
        ap.add_argument('--min-n', type=int, default=None)
        ap.add_argument('--ko-unit', choices=('eojeol', 'syllable'), default='eojeol')
        ap.add_argument('--min-impact', type=int, default=2)
        ap.add_argument('--pct-coh', type=float, default=prose.MINE_PCT_COH)
        ap.add_argument('--pct-ent', type=float, default=prose.MINE_PCT_ENT)
        ap.add_argument('--no-entropy', action='store_true')
        ap.add_argument('--termhood', choices=prose.TERMHOODS, default='auto')
        ap.add_argument('--top', type=int, default=300)
        args = ap.parse_args(rest[1:])
        args.format = 'both' if args.out else 'tsv'
        return prose.run_mine(args)

    return prose.main(rest)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ALGO_ALIASES:
        cmd, rest = argv[0], argv[1:]
        if cmd == 'mod':
            return _run_mod_compat(rest)
        return importlib.import_module('algos.' + cmd).main(rest)

    parser = _build_workflow_parser()
    args = parser.parse_args(argv)
    if args.command == 'translate':
        args.out_file = args.out
        if args.json:
            args.format = 'json'
        if not hasattr(args, 'method'):
            args.method = 'lpa'
    elif args.command == 'maintain' and args.json:
        args.format = 'json'

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
