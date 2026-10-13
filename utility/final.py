#!/usr/bin/env python3
# termgen 统一入口：第一个参数选算法，其余参数原样透传给该算法。
import importlib
import sys

ALGOS = {
    'compose': '中英平行名称压成条目（extract / bench / judge）',
    'single': '只有英文的单语候选（extract / bench）',
    'cjk': '中文/日文单语挖词（extract / bench）',
    'mod': '模组 lang 目录：prep / review / assemble / mine',
}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ALGOS:
        print('用法：python utility/final.py <算法> <子命令> [参数]', file=sys.stderr)
        for name, desc in ALGOS.items():
            print('  %-8s %s' % (name, desc), file=sys.stderr)
        return 2
    return importlib.import_module('algos.' + argv[0]).main(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
