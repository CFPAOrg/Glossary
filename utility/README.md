# utility

术语候选提取、校对与维护工具套件，入口为 `utility/final.py`。核心功能只依赖 Python 标准库；英文长文本启用 `--termhood specificity` 时按需使用 `wordfreq`，环境安装 `inflection` 时辅助英文词形单数化。

## 工作流入口

| 命令 | 使用场景 | 能力摘要 |
|---|---|---|
| `scope` | 定范围与洗输入 | 按前缀、正则、`Vanilla/diffs/term-key-filters.json` 或 `--diff OLD NEW` 切分语料，支持 `--style` 按 key 筛选 `STYLE.md` |
| `translate` | 无译文（待译发现） | `--corpus-type auto\|name\|prose`。短名走原子提取与共现家族聚类或 CJK 凝固度切分，长文本走 n-gram 挖掘与双语对齐 |
| `review` | 译文不可信 | 排查同词异译、名称骨架槽位分歧，以及对照 `--known` 术语表的漏译与错译违例 |
| `maintain` | 译文大体可信 | 短名走 `compose` 无损重建或导出 `*.terms.json` 审校清单；长文本走术语挖掘与双向对齐投票 |
| `clean` | 术语表清洗与审计 | 合并多张术语 TSV、按词形去重，并可用 `--corpus` 排查 0 命中死词与失败样例 |

如需直接调整底层参数，也可以通过 `python utility/final.py <compose|single|cjk|prose|mod>` 调用对应算法模块。

## 常用命令

```bash
# 1. 圈定范围（支持 TSV / 扁平 JSON / diff JSON / .lang / .txt / lang 目录）
python utility/final.py scope --input Vanilla/latest.tsv --key-filter on -o scoped.tsv
python utility/final.py scope --diff old.json new.json --prefix item. --focus-out focus.txt -o scoped.tsv
python utility/final.py scope --style --key biome.minecraft.plains

# 2. 翻译（无译文）：短名共现家族 / 长文本增量挖掘
python utility/final.py translate --input scoped.tsv --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --family
python utility/final.py translate --input story.tsv --corpus-type prose --lang en --ref zh --termhood specificity --known glossary.tsv

# 3. 校对（译文不可信）：查分歧与术语违例
python utility/final.py review --input scoped.tsv --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --format md

# 4. 维护（大体可信）：生成审校清单 / 全量提取
python utility/final.py maintain --input Vanilla/latest.tsv --key-filter on --focus Vanilla/diffs/26.2-26.3.json --exclude-keys 'banner|tropical_fish|subtitles' --known Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --out-json Vanilla/diffs/26.2-26.3.terms.json
python utility/final.py compose extract

# 5. 清洗与审计
python utility/final.py clean --input Vanilla/terms/terms-v1.tsv Vanilla/terms/terms-biome.tsv Vanilla/terms/terms-enchantment.tsv Vanilla/terms/terms-effect.tsv Vanilla/terms/terms-color.tsv Vanilla/terms/terms-mob.tsv Vanilla/terms/terms-tech.tsv --corpus Vanilla/latest.tsv --key-filter on --audit-only

# 6. 单元测试
cd utility && python -m unittest -v test_termgen
```

## compose 无损抽取与审校

`compose` 从中英平行短名中抽取最小可复用条目，并逐行核验全部输入都能由条目重新拼出。条目分三类，`id` 首字母即类型：

- `u`（零件）：能反复嵌进多个名称的词素或短语，例如 `Oak`、`Deepslate`。
- `t`（模板）：带 `{0}`、`{1}` 槽位的句子骨架，例如 `cake with {0} candle` 对应 `插上{0}蜡烛的蛋糕`。模板至少需要 2 个不同填充词与 2 对以上唯一中英对照。
- `x`（整名例外）：零件与模板都无法拼出的整条名称，例如 `End Rod` 译作 `末地烛`。

**（1）抽取与无损核验**

程序先按 `Vanilla/diffs/term-key-filters.json` 筛选产品名称，再统计 1~8 字 CJK 子串并结合 Dice 系数对齐译文片段。通过分支熵和搭配强度筛选强原子后，以强原子为锚点递归发现残余前后缀并检测邻接偷字。剩余例外行用于归纳单槽或双槽模板，再补齐槽位原子并裁掉复用不足 2 次的条目。

选条阶段默认 `--budget 0` 全选；预算大于 `0` 时按最大覆盖贪心挑选，未入选条目关联的行记为 `pending`。`verify_rows` 随后对非 `pending` 行逐行回放验证：例外行核对整名一致，模板行重算英文与中文槽位，零件行核对英文实词顺序与中文拼接覆盖（片段间允许出现「的」）。

**增量更新必须传 `--focus`**。针对版本 diff 抽词时，需把全量语料（如 `Vanilla/latest.tsv`）传给 `--input`，把 diff 文件传给 `--focus`。只用几百行的 diff 作为 `--input` 会丢失全局词频与共现证据，导致切词边界退化。

**（2）审校清单与本地合并**

`compose judge`（或 `maintain --out-json`）将抽取结果整理为审校 JSON；传入 `--focus <diff.json>` 且省略 `--out` 时，默认在同目录写出 `<diff>.terms.json`。模板条目不进清单；传入 `--known` 后，`en` 命中且译文全在表内的条目记为 `skipped_known` 并跳过，`en` 未收录但译文可由已知词拼接覆盖的条目记为 `skipped_derived` 并跳过。

清单中的 `added` 每项含 `en` 与 `zh` 数组：全量语料中仅出现 1 次的条目带 `single_use: true`；不在 `block`、`item`、`entity` 域的条目带 `labels`（如 `["biome"]`、`["stat"]`）；来自 diff `changed` 段的改译条目带旧译 `origin_zh`。`updated` 固定为空数组，`removed` 保留 diff `removed` 段中属产品名称的条目。

当前 `utility/algos/compose.py` 中 `judge_cmd` 的在线 LLM（Large Language Model，大语言模型）复核处于注释停用状态，清单条目原样通过且不写 `reason`。审校时在浏览器本地打开 `utility/termgen_review.html`，导入 `Vanilla/terms/terms-*.tsv` 与 `<版本>.terms.json`。工具在本地联合查重并按 `labels` 自动分表，确认勾选后即可导出更新后的 TSV。

## 模块与自动化

- `final.py`：统一 CLI 入口，暴露工作流子命令及 `compose`、`single`、`cjk`、`prose`、`mod` 算法别名。
- `io_utils.py`：统一输入解析（自动处理 UTF-8 BOM、扁平 JSON、Minecraft diff JSON、`.lang`、`.txt`、TSV）、key 过滤与术语匹配。
- `algos/compose.py`：中英平行短名无损组合抽取、模板归纳与 `judge` 审校导出。
- `algos/single.py`：英文单语原子提取与 LPA（Label Propagation Algorithm，标签传播算法）/ 连通分量家族聚类。
- `algos/cjk.py`：CJK 单语凝固度、最长匹配剪枝与 BPE（Byte Pair Encoding，字节对编码）。
- `algos/prose.py`：多语（`en`/`zh`/`ja`/`ko`）长文本 n-gram 挖掘、双向双语对齐、分歧与术语合规检测。
- `algos/scope.py`：语料范围切片、`STYLE.md` `@scope` 筛选预览与多表合并清洗去重。
- `termgen_review.html`：浏览器端多表审校合并页面。
- `test_termgen.py`：单元测试与 `Vanilla/terms/` 结构校验。
- `.github/workflows/minecraft-vanilla-lang.yml`：每日 UTC 16:00 检查 Mojang `version_manifest_v2.json`。当最新正式版 `year.minor` 高于 `Vanilla/.latest`（或手动指定 `force=true`）时，更新 `Vanilla/latest.tsv`、`Vanilla/.latest` 与 `Vanilla/diffs/<旧>-<新>.json`。
- `.github/workflows/term-candidates.yml`：当 `Vanilla/diffs/*.json` 有新提交（排除 `term-key-filters.json` 与 `*.terms.json`）时，CI（Continuous Integration，持续集成）自动运行 `compose judge`，排除 `banner|tropical_fish|subtitles` 键名并对照主表与六张域分表去重，提交 `<版本>.terms.json`。

## 已知局限

- 模板抽取只看字面词元与中文子串共现，可能提出语义不贴合的骨架（例如 `{0} with chest` 对应 `运输{0}`），需要审校时人工否决。
- 中文候选依赖子串统计，单字或短变体容易把无关汉字误判为已覆盖。
- 只出现一次的专名和无法拆分的固定译名会进入 `x` 例外条目，条目数随语料版本增长。
