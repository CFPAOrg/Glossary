# utility

术语候选提取、校对与维护生产工具套件，入口为 `utility/final.py`。全部能力只依赖 Python 标准库（仅英文长文本 `--termhood specificity` 策略按需使用 `wordfreq`）。

## 工作流入口

| 命令 | 使用场景 | 能力摘要 |
|---|---|---|
| `scope` | 定范围与洗输入 | 按前缀、正则、过滤文件或 `--diff OLD NEW` 切出目标语料；统一输出 TSV/JSON 与 `focus` 键清单 |
| `translate` | 无译文（待译发现） | `--corpus-type auto\|name\|prose`。短名走原子性组合过滤 + 共现家族聚类（`--family`）；长文本走 `wordfreq` 特异度 / MI + 边界熵，CJK 走凝固度 + 最长匹配。支持 `--known` 跳过已收词 |
| `review` | 有译文但不可信 | 查同词异译、名字骨架槽位分歧，以及对照 `--known` 术语表的漏译/错译违例 |
| `maintain` | 大体可信译文（建表/维护） | 短名走 `compose` 无损重建（零件 `u` / 模板 `t` / 变通例外 `x`）与 `*.terms.json` 审校导出；长文本走术语挖掘 + 双语对齐投票 |
| `clean` | 术语表清洗与审计 | 合并重词、去重校验，并可挂载 `--corpus` 排查 0 命中死词与误报 |

## 常用命令

```bash
# 1. 圈定范围（支持 TSV / 扁平 JSON / diff JSON / .lang / lang 目录）
python utility/final.py scope --input Vanilla/latest.tsv --key-filter on -o scoped.tsv
python utility/final.py scope --diff old.json new.json --prefix item. --focus-out focus.txt -o scoped.tsv

# 2. 翻译（无译文）：短名共现家族 / 长文本增量挖掘
python utility/final.py translate --input scoped.tsv --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --family
python utility/final.py translate --input story.tsv --corpus-type prose --lang en --ref zh --termhood specificity --known glossary.tsv

# 3. 校对（译文不可信）：查分歧与术语违例
python utility/final.py review --input scoped.tsv --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --format md

# 4. 维护（大体可信）：重建术语表 / CI 审校清单
python utility/final.py maintain --input Vanilla/latest.tsv --key-filter on --focus Vanilla/diffs/26.2-26.3.json --exclude-keys 'banner|tropical_fish|subtitles' --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --out-json Vanilla/diffs/26.2-26.3.terms.json
python utility/final.py compose judge --input Vanilla/latest.tsv --focus Vanilla/diffs/26.2-26.3.json --exclude-keys 'banner|tropical_fish|subtitles' --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv

# 5. 清洗与审计
python utility/final.py clean --input Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --corpus Vanilla/latest.tsv --key-filter on --audit-only

# 单元测试
cd utility && python -m unittest -v test_termgen
```

## 底层算法与文件

- `final.py`：统一入口，既暴露上述工作流，也保留 `compose`、`single`、`cjk`、`prose`（及 `mod` 兼容别名）直接调参。
- `io_utils.py`：统一输入解析（自动处理 UTF-8 BOM、扁平 JSON、Minecraft diff JSON、`.lang`、`.txt`、TSV）、key 过滤与术语匹配。
- `algos/compose.py`：中英平行短名无损组合抽取、模板归纳与 `judge` 审校导出。
- `algos/single.py`：英文单语原子提取与 LPA/连通分量家族聚类。
- `algos/cjk.py`：CJK 单语凝固度 + 最长匹配剪枝 + BPE。
- `algos/prose.py`：多语（`en`/`zh`/`ja`/`ko`）长文本 n-gram 挖掘、双向双语对齐、分歧与术语合规检测。
- `termgen_review.html`：浏览器端多表审校合并页。
- `test_termgen.py`：单元测试。
