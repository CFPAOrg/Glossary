#!/usr/bin/env python3
"""Per-gold-term coverage analysis for termgen candidate files.

Classifies every gold term as exact match / compound component / missing
against a candidates.tsv, cross-checks corpus reachability and compdrop impact.

Usage:
  python utility/coverage_report.py --gold Vanilla/terms/terms-v1.tsv \
      --candidates Vanilla/termgen-out/candidates.tsv \
      [--input Vanilla/latest.tsv] [--out report.tsv]
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import termgen as tg


def ntoks(s):
    return tuple(tg.norm_lemma(s).split())


def rtoks(s):
    return tuple(t.lower() for t in tg.TOKEN_RE.findall(s))


def ngram_index(seqs, max_n=9):
    idx = defaultdict(list)
    for i, seq in enumerate(seqs):
        n = len(seq)
        for L in range(1, min(max_n, n) + 1):
            for a in range(n - L + 1):
                idx[seq[a:a + L]].append(i)
    return idx


def compdrop_parts(why):
    out = []
    for chunk in why.split(';'):
        if chunk.startswith('compdrop='):
            for part in chunk[len('compdrop='):].split('|'):
                out.append(tuple(part.split()))
    return out


def tier_of(rs):
    return sorted({r['tier'] for r in rs})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gold', nargs='+', required=True)
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--input')
    ap.add_argument('--out')
    ap.add_argument('--label', default='')
    args = ap.parse_args()
    label = args.label or os.path.basename(os.path.dirname(os.path.abspath(args.candidates)))

    gold = tg.load_gold(args.gold)
    recs = tg.read_candidates(args.candidates)
    tiers = Counter(r['tier'] for r in recs)
    cd_rows = [r for r in recs if 'compdrop=' in r['why']]
    cd_tiers = Counter(r['tier'] for r in cd_rows)

    cn = [tg.norm_lemma(r['en']) for r in recs]
    ctoks = [tuple(n.split()) for n in cn]
    rt = [rtoks(r['en']) for r in recs]
    by_norm = defaultdict(list)
    for i, n in enumerate(cn):
        by_norm[n].append(i)
    cng = ngram_index(ctoks)
    crng = ngram_index(rt)

    # gold normalized collisions
    gnorm = defaultdict(list)
    for en, zhv in gold:
        gnorm[ntoks(en)].append((en, zhv))
    coll = {k: v for k, v in gnorm.items() if len(v) > 1}

    # corpus status
    corpus = {}
    blob_reach = None
    if args.input:
        rows = tg.load_input_rows(args.input)
        ens = []
        for (key, en, zh) in rows:
            e = tg.clean_en(en)
            if e:
                ens.append(e)
        uniq = sorted(set(ens))
        full = set(ntoks(e) for e in uniq)
        ing = ngram_index([ntoks(e) for e in uniq])
        blob = ' ' + ' '.join(tg.norm_lemma(e) for e in ens) + ' '
        blob_reach = blob

    def corpus_status(en):
        if not args.input:
            return ''
        gt = ntoks(en)
        if gt in full:
            return 'standalone'
        for i in ing.get(gt, ()):
            return 'component'
        return 'absent'

    out_rows = []
    cat_all = Counter()
    cat_rev = Counter()
    comp_any_n = 0
    comp_rev_n = 0
    exact_zh_hit = 0
    exact_zh_tot = 0
    comp_examples = []
    missing_list = []
    cd_self = []
    cd_part = []

    for en, zhv in gold:
        gt = ntoks(en)
        rgt = rtoks(en)
        ex = by_norm.get(tg.norm_lemma(en), [])
        ex_rev = [i for i in ex if recs[i]['tier'] != 'drop']
        ex_surf = [i for i in ex if recs[i]['en'].lower() == en.lower()]
        cex = [i for i in cng.get(gt, ()) if len(ctoks[i]) > len(gt)]
        cex_rev = [i for i in cex if recs[i]['tier'] != 'drop']
        cex_raw = [i for i in crng.get(rgt, ()) if len(rt[i]) > len(rgt)]

        if ex:
            cat = 'exact'
        elif cex:
            cat = 'component'
        else:
            cat = 'missing'
        if ex_rev:
            catr = 'exact'
        elif cex_rev:
            catr = 'component'
        else:
            catr = 'missing'
        cat_all[cat] += 1
        cat_rev[catr] += 1
        if cex:
            comp_any_n += 1
        if cex_rev:
            comp_rev_n += 1

        # zh check on norm-exact hits (eval-style loose compare)
        if ex:
            exact_zh_tot += 1
            cz = []
            for i in ex:
                cz.extend(recs[i]['zh'])
            if any(c and g and (c == g or c in g or g in c) for c in cz for g in zhv):
                exact_zh_hit += 1

        # compdrop
        self_cd = [i for i in ex if 'compdrop=' in recs[i]['why']]
        if self_cd:
            cd_self.append((en, tier_of([recs[i] for i in self_cd]),
                            sorted({p for i in self_cd for p in compdrop_parts(recs[i]['why'])})))
        part_hit = False
        for r in recs:
            for p in compdrop_parts(r['why']):
                if p == gt:
                    part_hit = True
                    break
            if part_hit:
                break
        if part_hit:
            cd_part.append(en)

        if cat == 'component' and len(comp_examples) < 400:
            best = sorted(cex, key=lambda i: (recs[i]['tier'] == 'drop', len(ctoks[i]), recs[i]['en']))[:2]
            comp_examples.append((en, '; '.join('%s[%s]' % (recs[i]['en'], recs[i]['tier']) for i in best)))
        if cat == 'missing':
            missing_list.append((en, zhv, corpus_status(en)))

        zhok = ''
        if ex:
            zhok = 'Y' if any(c and g and (c == g or c in g or g in c)
                              for i in ex for c in recs[i]['zh'] for g in zhv) else 'N'
        out_rows.append({
            'gold_en': en, 'gold_zh': '|'.join(zhv), 'category': cat, 'category_review': catr,
            'exact_tiers': ','.join(tier_of([recs[i] for i in ex])) if ex else '',
            'exact_surfaces': '; '.join(sorted({recs[i]['en'] for i in ex})[:3]) if ex else '',
            'exact_same_surface': 'Y' if ex_surf else ('N' if ex else ''),
            'exact_zh_ok': zhok,
            'comp_norm_n': len(cex), 'comp_norm_tiers': ','.join(tier_of([recs[i] for i in cex])) if cex else '',
            'comp_raw_n': len(cex_raw),
            'comp_examples': '; '.join(recs[i]['en'] for i in
                                       sorted(cex, key=lambda i: (recs[i]['tier'] == 'drop', len(ctoks[i])))[:3]) if cex else '',
            'compdrop_self': 'Y' if self_cd else '',
            'compdrop_part': 'Y' if part_hit else '',
            'corpus': corpus_status(en),
        })

    # compdrop marked rows that are / are not gold
    gold_norm_set = set(gnorm)
    cd_gold = sum(1 for r in cd_rows
                  if tuple(tg.norm_lemma(r['en']).split()) in gold_norm_set)
    cd_non_gold = len(cd_rows) - cd_gold

    # ---- print report ----
    print('=' * 72)
    print('COVERAGE REPORT  %s' % label)
    print('candidates: %s' % args.candidates)
    print('=' * 72)
    print('candidates total=%d  review=%d drop=%d  |  compdrop-marked rows=%d (review=%d drop=%d)'
          % (len(recs), tiers.get('review', 0), tiers.get('drop', 0),
             len(cd_rows), cd_tiers.get('review', 0), cd_tiers.get('drop', 0)))
    print('compdrop-marked rows that are gold=%d, not gold=%d' % (cd_gold, cd_non_gold))
    print('gold raw=%d  unique norm=%d  norm-collision groups=%d'
          % (len(gold), len(gnorm), len(coll)))
    for k, v in coll.items():
        print('  collision: %s' % '  <->  '.join(en for en, _ in v))
    print()
    print('-- category (mutually exclusive), any tier / review+ tier --')
    print('%-12s %8s %8s' % ('category', 'any', 'review'))
    for c in ('exact', 'component', 'missing'):
        print('%-12s %8d %8d' % (c, cat_all[c], cat_rev[c]))
    print('exact matches: any tier=%d review=%d (exact only in drop tier=%d)'
          % (cat_all['exact'], cat_rev['exact'], cat_all['exact'] - cat_rev['exact']))
    print('component matches (independent of exact): any tier=%d review=%d'
          % (comp_any_n, comp_rev_n))
    print('norm-exact gold with zh ok: %d/%d' % (exact_zh_hit, exact_zh_tot))
    same_surface = sum(1 for r in out_rows if r['exact_same_surface'] == 'Y')
    print('norm-exact with identical surface: %d ; norm-only (stemming) matches: %d'
          % (same_surface, cat_all['exact'] - same_surface))
    if blob_reach is not None:
        reach = sum(1 for en, zhv in gold if (' ' + tg.norm_lemma(en) + ' ') in blob_reach)
        print('corpus reachable (eval-style blob): %d' % reach)
    if missing_list:
        cc = Counter(s for _, _, s in missing_list)
        print('missing terms corpus status: standalone=%d component=%d absent=%d'
              % (cc.get('standalone', 0), cc.get('component', 0), cc.get('absent', 0)))
    print()
    print('-- compdrop impact --')
    print('gold terms whose own candidate is compdrop-marked: %d' % len(cd_self))
    for en, ts, parts in cd_self[:40]:
        print('  %-32s tiers=%s parts=%s' % (en, ts, '|'.join(' '.join(p) for p in parts)))
    print('gold terms appearing as compdrop decomposition parts: %d' % len(cd_part))
    if cd_part:
        print('  e.g. %s' % ', '.join(cd_part[:30]))
    print()
    print('-- component-only examples (top 40) --')
    for en, exs in comp_examples[:40]:
        print('  %-32s <= %s' % (en, exs))
    print()
    print('-- missing terms (first 60) --')
    for en, zhv, cs in missing_list[:60]:
        print('  %-32s %-20s %s' % (en, '|'.join(zhv)[:20], cs))
    print('(total missing %d)' % len(missing_list))

    if args.out:
        cols = ['gold_en', 'gold_zh', 'category', 'category_review', 'exact_tiers',
                'exact_surfaces', 'exact_same_surface', 'exact_zh_ok', 'comp_norm_n',
                'comp_norm_tiers', 'comp_raw_n', 'comp_examples', 'compdrop_self',
                'compdrop_part', 'corpus']
        with open(args.out, 'w', encoding='utf-8', newline='') as f:
            import csv
            w = csv.DictWriter(f, fieldnames=cols, delimiter='\t', lineterminator='\n')
            w.writeheader()
            w.writerows(out_rows)
        print('per-term detail -> %s' % args.out)


if __name__ == '__main__':
    main()
