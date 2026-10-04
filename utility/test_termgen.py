import argparse
import csv
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from termgen import build, chinese_match, compose, judge_cmd, measure, score_cases, write_candidates


class TermgenV3Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'input.tsv'

    def extract(self, entries, budget=0, exclude_keys=None):
        with self.path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerow(['key', 'en_us', 'zh_cn'])
            writer.writerows(entries)
        return build(self.path, budget, exclude_keys)

    def test_shared_parts_replace_names_but_nonliteral_name_survives(self):
        result = self.extract([
            ('color.minecraft.red', 'Red', '红色'),
            ('color.minecraft.blue', 'Blue', '蓝色'),
            ('block.minecraft.bed', 'Bed', '床'),
            ('block.minecraft.red_bed', 'Red Bed', '红色床'),
            ('block.minecraft.blue_bed', 'Blue Bed', '蓝色床'),
            ('item.minecraft.end', 'End', '末地'),
            ('item.minecraft.rod', 'Rod', '棒'),
            ('block.minecraft.end_rod', 'End Rod', '末地烛'),
        ])
        cards = {card['id']: card for card in result['review']}
        rows = {row['en']: row for row in result['audit']}
        self.assertEqual({cards[cid]['en'] for cid in rows['Red Bed']['terms']}, {'Red', 'Bed'})
        self.assertEqual(rows['End Rod']['status'], 'exception')
        self.assertEqual(cards[rows['End Rod']['terms'][0]]['zh_candidates'], ['末地烛'])
        self.assertNotIn('Red Bed', {card['en'] for card in result['review']})

    def test_rare_translation_variant_is_preserved(self):
        result = self.extract([
            ('block.minecraft.oak', 'Oak', '橡木'),
            ('block.minecraft.oak_alt', 'Oak', '橡树'),
            ('block.minecraft.planks', 'Planks', '木板'),
            ('block.minecraft.sapling', 'Sapling', '树苗'),
            ('block.minecraft.oak_planks', 'Oak Planks', '橡木木板'),
            ('block.minecraft.oak_sapling', 'Oak Sapling', '橡树树苗'),
        ])
        oak = next(card for card in result['review'] if card['en'] == 'Oak')
        self.assertEqual(set(oak['zh_candidates']), {'橡木', '橡树'})
        self.assertTrue(all(row['status'] == 'compositional' for row in result['audit']))

    def test_budget_reports_pending_dependencies_without_claiming_coverage(self):
        result = self.extract([
            ('item.minecraft.iron', 'Iron', '铁'),
            ('block.minecraft.block', 'Block', '块'),
            ('block.minecraft.iron_block', 'Block of Iron', '铁块'),
            ('item.minecraft.elytra', 'Elytra', '鞘翅'),
        ], budget=1)
        selected = {card['id'] for card in result['review']}
        self.assertEqual(len(selected), 1)
        self.assertEqual(result['stats']['backlog_cards'], 2)
        for row in result['audit']:
            self.assertEqual(set(row['pending']), set(row['terms']) - selected)
        block = next(row for row in result['audit'] if row['en'] == 'Block of Iron')
        self.assertTrue(block['pending'])
        self.assertEqual(result['stats']['ready_rows'] + result['stats']['pending_rows'], 4)

    def test_reordering_and_particles_do_not_allow_missing_or_repeated_parts(self):
        lex = {
            ('iron',): {'id': 'iron', 'zh_candidates': ['铁']},
            ('block',): {'id': 'block', 'zh_candidates': ['块']},
        }
        self.assertEqual(compose(('block', 'of', 'iron'), '铁块', lex), ['block', 'iron'])
        self.assertEqual(compose(('iron', 'block'), '铁的块', lex), ['iron', 'block'])
        self.assertIsNone(compose(('iron', 'iron'), '铁', lex))
        self.assertIsNone(compose(('iron', 'block'), '铁神秘块', lex))
        self.assertFalse(chinese_match('的铁块', list(lex.values())))

    def test_numbers_and_missing_translations_remain_explicit(self):
        result = self.extract([
            ('item.minecraft.potion_2', 'Potion 2', '药水'),
            ('item.minecraft.potion_3', 'Potion 3', '药水'),
            ('item.minecraft.unknown', 'Unknown', ''),
        ])
        self.assertEqual({card['en'] for card in result['review']}, {'Potion 2', 'Potion 3', 'Unknown'})
        self.assertTrue(all(row['status'] == 'exception' for row in result['audit']))
        self.assertEqual(next(card for card in result['review'] if card['en'] == 'Unknown')['zh_candidates'], [])

    def test_blacklist_precedes_whitelist_and_exclusion_removes_evidence(self):
        result = self.extract([
            ('item.minecraft.apple', 'Apple', '苹果'),
            ('block.minecraft.banner.red', 'Red Banner', '红色旗帜'),
            ('item.minecraft.apple.tooltip', 'Apple Tooltip', '苹果说明'),
            ('menu.apple', 'Menu Apple', '菜单苹果'),
            ('item.minecraft.pear', 'Pear', '梨'),
        ], exclude_keys='pear')
        self.assertEqual([row['key'] for row in result['audit']], ['item.minecraft.apple'])
        self.assertEqual([card['en'] for card in result['review']], ['Apple'])
        stream = StringIO()
        write_candidates(stream, result)
        self.assertIn('Apple', stream.getvalue())

    def test_metric_iterables_and_unlisted_candidates_are_not_false_positives(self):
        stats = measure(iter(['Oak', 'Oak Planks']), iter(['Oak', 'Mystery']),
                        iter(['Oak', 'Mystery']), iter(['Oak', 'Oak Planks']), 100, 40)
        self.assertEqual(stats['review_cards'], 2)
        self.assertEqual(stats['review_gold'], 1)
        self.assertEqual(stats['review_recall'], 0.5)
        self.assertEqual(stats['positive_match_rate'], 0.5)
        self.assertNotIn('precision', stats)
        self.assertEqual(stats['char_reduction'], 0.6)

    def test_case_references_cannot_supply_undelivered_cards(self):
        case = {'key': 'block.minecraft.red_bed', 'en': 'Red Bed', 'zh': '红色床',
                'expect': 'compositional', 'required_terms': ['Red', 'Bed']}
        report = score_cases([case], [{'en': 'Red', 'zh_candidates': ['红色']}],
                             [{'en': 'Red Bed', 'parts': ['Red', 'Bed'], 'zh': '红色床'}])
        self.assertEqual(report['covered'], 0)
        self.assertEqual(report['missed'][0]['missing_parts'], ['bed'])


    def test_nested_phrase_survives_alongside_short_terms(self):
        colors = {'Blue': '蓝色', 'Light Blue': '淡蓝色', 'Red': '红色', 'Green': '绿色',
                  'Yellow': '黄色', 'Black': '黑色', 'White': '白色', 'Orange': '橙色'}
        products = {'Wool': '羊毛', 'Concrete': '混凝土', 'Terracotta': '陶瓦', 'Dye': '染料',
                    'Bed': '床', 'Candle': '蜡烛', 'Carpet': '地毯', 'Glass': '玻璃',
                    'Banner': '旗帜', 'Bundle': '收纳袋', 'Harness': '挽具', 'Shield': '盾牌',
                    'Cushion': '坐垫', 'Shulker Box': '潜影盒', 'Stained Glass': '染色玻璃',
                    'Glazed Terracotta': '带釉陶瓦'}
        entries = []
        for color, color_zh in colors.items():
            entries.append(('color.minecraft.%s' % color.lower().replace(' ', '_'), color, color_zh))
        for product, product_zh in products.items():
            key = 'block.minecraft.%s' % product.lower().replace(' ', '_')
            entries.append((key, product, product_zh))
        for color, color_zh in colors.items():
            for product, product_zh in products.items():
                key = 'block.minecraft.%s_%s' % (color.lower().replace(' ', '_'),
                                                 product.lower().replace(' ', '_'))
                entries.append((key, '%s %s' % (color, product), color_zh + product_zh))
        result = self.extract(entries)
        cards = {card['en']: card for card in result['review']}
        self.assertIn('Light Blue', cards)
        self.assertIn('Blue', cards)
        self.assertEqual(cards['Light Blue']['zh_candidates'], ['淡蓝色'])
        self.assertEqual(cards['Light Blue']['reason'], 'nested_phrase')
        self.assertNotIn('Blue Wool', cards)
        rows = {row['en']: row for row in result['audit']}
        by_id = {card['id']: card for card in result['review']}
        self.assertEqual(rows['Light Blue Wool']['status'], 'compositional')
        self.assertEqual(sorted(by_id[cid]['en'] for cid in rows['Light Blue Wool']['terms']),
                         ['Light Blue', 'Wool'])


    def test_judge_skips_terms_derivable_from_known(self):
        colors = {'Blue': '蓝色', 'Light Blue': '淡蓝色', 'Red': '红色', 'Green': '绿色',
                  'Yellow': '黄色', 'Black': '黑色', 'White': '白色', 'Orange': '橙色'}
        products = {'Wool': '羊毛', 'Concrete': '混凝土', 'Terracotta': '陶瓦', 'Dye': '染料',
                    'Bed': '床', 'Candle': '蜡烛', 'Carpet': '地毯', 'Glass': '玻璃',
                    'Banner': '旗帜', 'Bundle': '收纳袋', 'Harness': '挽具', 'Shield': '盾牌',
                    'Cushion': '坐垫', 'Shulker Box': '潜影盒', 'Stained Glass': '染色玻璃',
                    'Glazed Terracotta': '带釉陶瓦'}
        entries = [('color.minecraft.%s' % color.lower().replace(' ', '_'), color, zh)
                   for color, zh in colors.items()]
        entries += [('block.minecraft.%s' % product.lower().replace(' ', '_'), product, zh)
                    for product, zh in products.items()]
        entries += [('block.minecraft.%s_%s' % (color.lower().replace(' ', '_'),
                                                product.lower().replace(' ', '_')),
                     '%s %s' % (color, product), color_zh + product_zh)
                    for color, color_zh in colors.items()
                    for product, product_zh in products.items()]
        self.extract(entries)
        known = Path(self.temp.name) / 'known.tsv'
        known.write_text('en\tzh\treason\tcomment\nLight\t淡\t\t\nBlue\t蓝色\t\t\n',
                         encoding='utf-8')
        out = Path(self.temp.name) / 'terms.json'
        args = argparse.Namespace(input=self.path, focus=None, budget=0, exclude_keys=None,
                                  known=[str(known)], out=out, batch_size=40)
        with mock.patch.dict(os.environ, {'LLM_API_KEY': ''}), \
                redirect_stdout(StringIO()) as printed:
            judge_cmd(args)
        stats = json.loads(printed.getvalue().strip().splitlines()[-1])
        self.assertEqual(stats['skipped_known'], 1)
        self.assertEqual(stats['skipped_derived'], 1)
        names = [entry['en'][0] for entry in json.loads(out.read_text(encoding='utf-8'))['added']]
        self.assertNotIn('Light Blue', names)
        self.assertIn('Cushion', names)

    def test_judge_sends_known_term_with_new_variant(self):
        self.extract([
            ('item.minecraft.foo', 'Foo', '福'),
            ('item.minecraft.bar', 'Bar', '巴'),
        ])
        known = Path(self.temp.name) / 'known.tsv'
        known.write_text('en\tzh\treason\tcomment\nFoo\t弗\t\t\nBar\t巴\t\t\n', encoding='utf-8')
        out = Path(self.temp.name) / 'terms.json'
        args = argparse.Namespace(input=self.path, focus=None, budget=0, exclude_keys=None,
                                  known=[str(known)], out=out, batch_size=40)
        with mock.patch.dict(os.environ, {'LLM_API_KEY': ''}), \
                redirect_stdout(StringIO()) as printed:
            judge_cmd(args)
        stats = json.loads(printed.getvalue().strip().splitlines()[-1])
        self.assertEqual(stats['skipped_known'], 1)
        names = [entry['en'][0] for entry in json.loads(out.read_text(encoding='utf-8'))['added']]
        self.assertIn('Foo', names)
        self.assertNotIn('Bar', names)


if __name__ == '__main__':
    unittest.main()
