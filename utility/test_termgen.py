import argparse
import csv
import io as pyio
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import final
import io_utils
from algos import cjk, compose, single


class ComposeCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'input.tsv'

    def extract(self, input_rows, budget=0, exclude_keys=None):
        with self.path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream, delimiter='\t', lineterminator='\n')
            writer.writerow(['key', 'en_us', 'zh_cn'])
            writer.writerows(input_rows)
        return compose.build(self.path, budget, exclude_keys)

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
        entries = {entry['id']: entry for entry in result['review']}
        rows = {row['en']: row for row in result['audit']}
        self.assertEqual({entries[cid]['en'] for cid in rows['Red Bed']['terms']}, {'Red', 'Bed'})
        self.assertEqual(rows['End Rod']['status'], 'exception')
        self.assertEqual(entries[rows['End Rod']['terms'][0]]['zh_candidates'], ['末地烛'])
        self.assertNotIn('Red Bed', {entry['en'] for entry in result['review']})

    def test_rare_translation_variant_is_preserved(self):
        result = self.extract([
            ('block.minecraft.oak', 'Oak', '橡木'),
            ('block.minecraft.oak_alt', 'Oak', '橡树'),
            ('block.minecraft.planks', 'Planks', '木板'),
            ('block.minecraft.sapling', 'Sapling', '树苗'),
            ('block.minecraft.oak_planks', 'Oak Planks', '橡木木板'),
            ('block.minecraft.oak_sapling', 'Oak Sapling', '橡树树苗'),
        ])
        oak = next(entry for entry in result['review'] if entry['en'] == 'Oak')
        self.assertEqual(set(oak['zh_candidates']), {'橡木', '橡树'})
        self.assertTrue(all(row['status'] == 'compositional' for row in result['audit']))

    def test_budget_reports_pending_dependencies_without_claiming_coverage(self):
        result = self.extract([
            ('item.minecraft.iron', 'Iron', '铁'),
            ('block.minecraft.block', 'Block', '块'),
            ('block.minecraft.iron_block', 'Block of Iron', '铁块'),
            ('item.minecraft.elytra', 'Elytra', '鞘翅'),
        ], budget=1)
        selected = {entry['id'] for entry in result['review']}
        self.assertEqual(len(selected), 1)
        self.assertEqual(result['stats']['backlog_entries'], 2)
        for row in result['audit']:
            self.assertEqual(set(row['pending']), set(row['terms']) - selected)

    def test_reordering_and_particles_do_not_allow_missing_or_repeated_parts(self):
        lex = {
            ('iron',): {'id': 'iron', 'zh_candidates': ['铁']},
            ('block',): {'id': 'block', 'zh_candidates': ['块']},
        }
        self.assertEqual(compose.compose(('block', 'of', 'iron'), '铁块', lex), ['block', 'iron'])
        self.assertEqual(compose.compose(('iron', 'block'), '铁的块', lex), ['iron', 'block'])
        self.assertIsNone(compose.compose(('iron', 'iron'), '铁', lex))
        self.assertIsNone(compose.compose(('iron', 'block'), '铁神秘块', lex))
        self.assertFalse(compose.chinese_match('的铁块', list(lex.values())))

    def test_judge_skips_known_and_derivable_but_keeps_new_variant(self):
        colors = {'Blue': '蓝色', 'Light Blue': '淡蓝色', 'Red': '红色', 'Green': '绿色',
                  'Yellow': '黄色', 'Black': '黑色', 'White': '白色', 'Orange': '橙色'}
        products = {'Wool': '羊毛', 'Concrete': '混凝土', 'Terracotta': '陶瓦', 'Dye': '染料',
                    'Bed': '床', 'Candle': '蜡烛', 'Carpet': '地毯', 'Glass': '玻璃',
                    'Banner': '旗帜', 'Bundle': '收纳袋', 'Harness': '挽具', 'Shield': '盾牌',
                    'Cushion': '坐垫', 'Shulker Box': '潜影盒', 'Stained Glass': '染色玻璃',
                    'Glazed Terracotta': '带釉陶瓦'}
        input_rows = [('color.minecraft.%s' % color.lower().replace(' ', '_'), color, zh)
                      for color, zh in colors.items()]
        input_rows += [('block.minecraft.%s' % product.lower().replace(' ', '_'), product, zh)
                       for product, zh in products.items()]
        input_rows += [('block.minecraft.%s_%s' % (color.lower().replace(' ', '_'),
                                                   product.lower().replace(' ', '_')),
                        f'{color} {product}', color_zh + product_zh)
                       for color, color_zh in colors.items()
                       for product, product_zh in products.items()]
        self.extract(input_rows)
        known = Path(self.temp.name) / 'known.tsv'
        known.write_text('en\tzh\treason\tcomment\nLight\t淡\t\t\nBlue\t蓝色\t\t\n', encoding='utf-8')
        out = Path(self.temp.name) / 'terms.json'
        args = argparse.Namespace(input=self.path, focus=None, budget=0, exclude_keys=None,
                                  known=[str(known)], out=out, batch_size=40)
        with mock.patch.dict(os.environ, {'LLM_API_KEY': ''}), redirect_stdout(pyio.StringIO()) as printed:
            compose.judge_cmd(args)
        stats = json.loads(printed.getvalue().strip().splitlines()[-1])
        self.assertEqual(stats['skipped_known'], 1)
        self.assertEqual(stats['skipped_derived'], 1)
        names = [entry['en'][0] for entry in json.loads(out.read_text(encoding='utf-8'))['added']]
        self.assertNotIn('Light Blue', names)
        self.assertIn('Cushion', names)

    def test_omitted_char_compound_stays_separate_without_polluting_atom(self):
        result = self.extract([
            ('color.minecraft.blue', 'Blue', '蓝色'),
            ('color.minecraft.red', 'Red', '红色'),
            ('block.minecraft.bed', 'Bed', '床'),
            ('block.minecraft.wool', 'Wool', '羊毛'),
            ('block.minecraft.blue_bed', 'Blue Bed', '蓝色床'),
            ('block.minecraft.red_bed', 'Red Bed', '红色床'),
            ('block.minecraft.blue_wool', 'Blue Wool', '蓝色羊毛'),
            ('block.minecraft.red_wool', 'Red Wool', '红色羊毛'),
            ('block.minecraft.ice', 'Ice', '冰'),
            ('block.minecraft.packed_ice', 'Packed Ice', '浮冰'),
            ('block.minecraft.sand', 'Sand', '沙子'),
            ('block.minecraft.red_sand', 'Red Sand', '红沙'),
            ('block.minecraft.blue_ice', 'Blue Ice', '蓝冰'),
        ])
        entries = {entry['en']: entry for entry in result['review']}
        self.assertEqual(entries['Blue']['zh_candidates'], ['蓝色'])
        self.assertEqual(entries['Red']['zh_candidates'], ['红色'])
        self.assertIn('Blue Ice', entries)
        self.assertEqual(entries['Blue Ice']['zh_candidates'], ['蓝冰'])
        self.assertIn('Red Sand', entries)
        self.assertEqual(entries['Red Sand']['zh_candidates'], ['红沙'])

    def test_neighbor_boundary_theft_is_prevented(self):
        result = self.extract([
            ('color.minecraft.brown', 'Brown', '棕色'),
            ('color.minecraft.red', 'Red', '红色'),
            ('block.minecraft.brown_bed', 'Brown Bed', '棕色床'),
            ('block.minecraft.red_bed', 'Red Bed', '红色床'),
            ('block.minecraft.brown_mushroom', 'Brown Mushroom', '棕色蘑菇'),
            ('block.minecraft.red_mushroom', 'Red Mushroom', '红色蘑菇'),
            ('block.minecraft.bed', 'Bed', '床'),
            ('block.minecraft.brown_mushroom_block', 'Brown Mushroom Block', '棕色蘑菇方块'),
            ('block.minecraft.red_mushroom_block', 'Red Mushroom Block', '红色蘑菇方块'),
            ('block.minecraft.acacia', 'Acacia', '金合欢木'),
            ('block.minecraft.birch', 'Birch', '白桦木'),
            ('item.minecraft.iron', 'Iron', '铁'),
            ('item.minecraft.boat', 'Boat', '船'),
            ('item.minecraft.acacia_boat', 'Acacia Boat', '金合欢木船'),
            ('item.minecraft.birch_boat', 'Birch Boat', '白桦木船'),
            ('block.minecraft.iron_block', 'Iron Block', '铁块'),
            ('block.minecraft.block', 'Block', '块'),
            ('block.minecraft.acacia_door', 'Acacia Door', '金合欢木门'),
            ('block.minecraft.birch_door', 'Birch Door', '白桦木门'),
            ('block.minecraft.iron_door', 'Iron Door', '铁门'),
        ])
        entries = {entry['en']: entry for entry in result['review']}
        self.assertEqual(entries['Mushroom Block']['zh_candidates'], ['蘑菇方块'])
        self.assertIn('门', entries['Door']['zh_candidates'])
        self.assertNotIn('木门', entries['Door']['zh_candidates'])


class ProductionSuiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_bom_tsv_and_flat_json_loading(self):
        bom_tsv = self.root / 'bom.tsv'
        bom_tsv.write_bytes('\ufeffkey\ten_us\tzh_cn\nitem.mod.a\tSteel Ingot\t钢锭\n'.encode('utf-8'))
        rows = io_utils.load_input_rows(bom_tsv)
        self.assertEqual(rows, [('item.mod.a', 'Steel Ingot', '钢锭')])

        flat_json = self.root / 'en_us.json'
        flat_json.write_text(json.dumps({'item.mod.a': 'Steel Ingot', 'gui.ok': 'OK'}), encoding='utf-8')
        jrows = io_utils.load_input_rows(flat_json)
        self.assertEqual(len(jrows), 2)
        self.assertEqual(jrows[0], ('item.mod.a', 'Steel Ingot', ''))

    def test_key_filter_lazy_loading(self):
        tsv = self.root / 'mod.tsv'
        tsv.write_text('key\ten_us\tzh_cn\nblock.mod.iron\tIron Block\t铁块\nui.done\tDone\t完成\n', encoding='utf-8')
        with mock.patch('io_utils.load_key_filter', side_effect=AssertionError('不该读默认过滤文件')):
            self.assertEqual(len(single.load_rows(tsv, key_filter='off')), 2)
            self.assertEqual(len(single.load_rows(tsv, key_filter='on', keys='^block\\.')), 1)
            self.assertEqual(len(cjk.load_rows(tsv, column='zh_cn', key_filter='off')), 2)

    def test_scope_diff_and_prefix_slicing(self):
        old_json = self.root / 'old.json'
        new_json = self.root / 'new.json'
        old_json.write_text(json.dumps({'item.a': 'Iron', 'gui.b': 'Cancel'}), encoding='utf-8')
        new_json.write_text(json.dumps({'item.a': 'Iron', 'item.c': 'Copper', 'gui.b': 'OK'}), encoding='utf-8')
        scoped = self.root / 'scoped.tsv'
        focus = self.root / 'focus.txt'
        with redirect_stderr(pyio.StringIO()):
            rc = final.main([
                'scope', '--diff', str(old_json), str(new_json),
                '--prefix', 'item.', '--focus-out', str(focus), '-o', str(scoped),
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(focus.read_text(encoding='utf-8').strip(), 'item.c')
        self.assertIn('Copper', scoped.read_text(encoding='utf-8'))
        self.assertNotIn('gui.b', scoped.read_text(encoding='utf-8'))

    def test_translate_name_prose_and_known_filter(self):
        prose_tsv = self.root / 'story.tsv'
        lines = [
            'key\ten_us\tzh_cn',
            'story.1\tReach the Astral Spire before dusk and greet the Crimson Altar guards near the old gate.\t在黄昏前抵达星界尖塔并问候旧门旁的绯红祭坛守卫。',
            'story.2\tSeek another Astral Spire inside the valley or inspect an old Crimson Altar stone.\t在山谷中寻找另一座星界尖塔或检查古老的绯红祭坛石碑。',
            'story.3\tClimb every Astral Spire beyond the river while guarding this Crimson Altar relic.\t攀登河对岸的每座星界尖塔同时守护这件绯红祭坛遗物。',
            'story.4\tOpen that Astral Spire gate under moonlight beside my Crimson Altar shrine.\t在月光下打开那扇星界尖塔大门，就在我的绯红祭坛神龛旁。',
            'story.5\tTravelers rest near the old gate before dawn.\t旅人在黎明前于旧门附近歇息。',
            'story.6\tMerchants trade old spices across the harbor.\t商人在港口交易陈年香料。',
            'story.7\tLanterns glow along the cobblestone road.\t灯笼沿着圆石路闪烁微光。',
            'story.8\tRain falls quietly over the northern hills.\t雨水静静落在北方山丘上。',
            'story.9\tWatchmen lock the iron gate at midnight.\t守夜人在午夜锁上铁门。',
            'story.10\tWind blows across the silent courtyard.\t风吹过寂静的庭院。',
        ]
        prose_tsv.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        known = self.root / 'known.tsv'
        known.write_text('en\tzh\nAstral Spire\t星界尖塔\n', encoding='utf-8')
        out_json = self.root / 'prose_out.json'
        with redirect_stderr(pyio.StringIO()):
            rc = final.main([
                'translate', '--input', str(prose_tsv), '--corpus-type', 'prose',
                '--lang', 'en', '--ref', 'zh', '--termhood', 'self',
                '--pct-coh', '15', '--known', str(known), '--json', '-o', str(out_json),
            ])
        self.assertEqual(rc, 0)
        data = json.loads(out_json.read_text(encoding='utf-8'))
        terms = {t['term'].lower(): t for t in data['terms']}
        self.assertNotIn('astral spire', terms)
        self.assertGreaterEqual(data['summary']['skipped_known'], 1)
        self.assertTrue(any('crimson altar' in k or 'astral keeper' in k for k in terms))

    def test_review_divergence_and_known_violations(self):
        rev_tsv = self.root / 'rev.tsv'
        rev_tsv.write_text(
            'key\ten_us\tzh_cn\n'
            'item.1\tIron Ingot\t铁锭\n'
            'item.2\tIron Ingot\t钢铁锭\n'
            'item.3\tGold Ingot\t金锭\n'
            'item.4\tCopper Ingot\t铜条\n',
            encoding='utf-8',
        )
        known = self.root / 'known.tsv'
        known.write_text('en\tzh\nCopper Ingot\t铜锭\n', encoding='utf-8')
        out = self.root / 'review.json'
        with redirect_stderr(pyio.StringIO()):
            rc = final.main(['review', '--input', str(rev_tsv), '--known', str(known), '--format', 'json', '-o', str(out)])
        self.assertEqual(rc, 0)
        rep = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(rep['summary']['same_source_divergence'], 1)
        self.assertEqual(rep['summary']['known_violations'], 1)
        self.assertEqual(rep['known_violations'][0]['term'], 'Copper Ingot')

    def test_maintain_prose_and_clean_audit(self):
        corp = self.root / 'corp.tsv'
        rows = ['key\ten_us\tzh_cn']
        for i in range(1, 5):
            rows.append(f'd.{i}\tThe Astral Beacon glows softly in the dark cavern.\t星界信标在幽暗洞穴中微弱发光。')
        rows.append('d.5\tThe Astral Beacon guides lost travelers home.\t星界灯塔指引迷途旅人归乡。')
        corp.write_text('\n'.join(rows) + '\n', encoding='utf-8')
        known = self.root / 'known.tsv'
        known.write_text('en\tzh\nAstral Beacon\t星界信标\nDead Entry\t死词\n', encoding='utf-8')
        mt_out = self.root / 'maintain.json'
        with redirect_stderr(pyio.StringIO()):
            rc = final.main([
                'maintain', '--input', str(corp), '--corpus-type', 'prose',
                '--termhood', 'self', '--known', str(known), '--json', '-o', str(mt_out),
            ])
        self.assertEqual(rc, 0)
        mt = json.loads(mt_out.read_text(encoding='utf-8'))
        self.assertEqual(mt['summary']['pairs'], 5)

        clean_out = self.root / 'clean_audit.json'
        with redirect_stdout(pyio.StringIO()) as out_buf:
            rc = final.main([
                'clean', '--input', str(known), '--corpus', str(corp), '--audit-only',
            ])
        self.assertEqual(rc, 0)
        audit = json.loads(out_buf.getvalue())
        self.assertEqual(audit['dead_terms_count'], 1)
        self.assertEqual(audit['failing_terms_count'], 1)


if __name__ == '__main__':
    unittest.main()
