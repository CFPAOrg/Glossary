# termgen 术语候选生成

`utility/termgen.py` 是现行的术语候选工具。它读 `Vanilla/latest.tsv`、diff JSON（`added`/`changed` 两段）或纯文本清单，按语言 key 过滤出产品名称，压成可复用的卡片，供 LLM（Large Language Model，大语言模型）或人审校后转成术语表。单文件，只用标准库。

## 产出

`extract` 把全部卡片按 TSV 打到 stdout：id、en、zh 候选、kind、uses、reason、来源 key、证据；统计打到 stderr。不落盘。

`judge` 写给人审的 JSON，结构见下。

卡片分三类，id 首字母即类型：

- u（零件）：能反复嵌进别的名称的片段，如 Oak、Deepslate。
- t（模板）：带槽位的句子骨架，如 `cake with {0} candle` ↔ `插上{0}蜡烛的蛋糕`。
- x（整名例外）：零件拼不出来的整名，如「末地烛」不能由「末地棒」推出。

### 无损

每一行输入都能由卡片拼回原文和译文，工具写完卡片后逐行核验（`verify_rows`）。统计里的 `reconstructed_rows` 等于 `accounted_rows`，拼不回的行进 `failed_keys`。三类行各有核验方式：

- 例外行：整名卡片与输入完全一致。
- 模板行：英文按模式重新匹配，中文按槽位重新切分，槽位内容再逐张卡核对。
- 零件行：英文词按序拼回原句，中文按卡片候选切分覆盖，允许「的」和连词。

核验只查 `pending` 为空的行。默认预算 0，全部行都查。

## 流水线

| 步骤 | 代码 | 依据 |
|---|---|---|
| 过滤 key，取产品名称 | `load_input_rows`、`is_product_key` | key 白名单/黑名单，见 `Vanilla/diffs/term-key-filters.json` |
| 从平行名称挑中文片段 | `translations` | 平行语料短语抽取（Koehn 等，2003）；包含关系加 Dice 系数 |
| 分支熵与搭配强度门控 | `strong_atoms`、`qualified` | 分支熵（Jin 等，2006）；accessor variety（Feng 等，2004）；搭配显著性（El-Kishky 等，2015） |
| 锚点递归发现残余前后缀 | `build` 里的 `discovered` | Espresso 的模式迭代（Pantel 等，2006）；Basilisk 的精度门控（Thelen 等，2002） |
| 跨上下文核对译文 | `verify_nested` | 自举方法要求独立证据（Pantel 等，2006；Thelen 等，2002） |
| 抽取句子模板并补齐槽位 | `extract_templates`、`confirmed`、`induce`、`prune` | 层次短语模型 Hiero（Chiang，2005） |
| 预算内选卡 | `select_cards` | 最大覆盖贪心（Nemhauser 等，1978；Lin 等，2011）；预算版（Khuller 等，1999） |
| 重建核验 | `verify_rows` | 本项目自定：每条输入都要能由卡片重新拼出 |

模板的门槛：至少 2 个不同填充词、2 对不同的 en/zh。槽位里缺的零件由 `induce` 补出来，`prune` 再删掉只用了一两次的模板和零件。模板会改变语序，核验单独走 `verify_template`。

## 命令

```bash
python utility/termgen.py extract
python utility/termgen.py judge --focus Vanilla/diffs/26.2-26.3.json \
  --known Vanilla/terms/terms-v1.tsv \
  --out Vanilla/diffs/26.2-26.3.terms.json
python utility/termgen.py bench
python utility/termgen_scorecard.py --with-ranked
cd utility && python -m unittest test_termgen
```

`extract` 把卡片打到 stdout，用来查卡片，要留档就重定向。生产走 `judge`：它自己跑一遍抽取，直接出审校用的 JSON。`--budget` 默认 0，全部卡片都送审；给正整数时只送审这么多张，其余留在 extract 的输出里。`--exclude-keys` 是正则，命中 key 的行直接丢弃。`--focus` 收 diff JSON 或 key 清单：对齐仍用整份 `--input` 语料，只输出这些 key 的行和卡片。单跑一份 diff 时语料只有几百行，零件边界会退化（例如把 `Blue` 切成「蓝」、`Concrete Slab` 切成「色混凝土台阶」，两处互相抵消，行级核验看不出来），所以走 `--focus` 而不是把 diff 当输入。`bench` 打印统计、gold 指标、评估用例和重建核验。

## judge 与 LLM

`judge` 把卡片整理成一份给人审的 JSON；LLM 复核暂停期间，卡片全部按原样通过。给 diff 时文件名默认是 `<diff>.terms.json`，写在 diff 旁边。审校用 `utility/termgen_review.html`：贴入 `terms-v1.tsv` 和这份 JSON，勾选后导出新的 v1。

产出结构跟 `Vanilla/diffs/*.terms.json` 一致：

```json
{
  "from": "26.2",
  "to": "26.3",
  "source_diff": "Vanilla/diffs/26.2-26.3.json",
  "added_count": 36,
  "added": [
    {"en": ["Dappled Forest"], "zh": ["斑驳森林"], "labels": ["biome"], "reason": "与官方中文译名一致"},
    {"en": ["Shelf Mushroom"], "zh": ["层孔菇"], "single_use": true, "reason": "与官方中文译名一致"},
    {"en": ["Distance by Happy Ghast"], "zh": ["骑快乐恶魂移动距离"],
     "labels": ["stat"], "origin_zh": ["骑乘快乐恶魂移动距离"]}
  ],
  "updated_count": 0,
  "updated": [],
  "removed_count": 0,
  "removed": []
}
```

`zh` 是候选数组，对应卡片里的 `|` 变体。`single_use` 标在整份语料里只出现一次的术语上（不看本次 diff 的范围，`Door` 这种老词不会因为 diff 里只有一行就被标）——本仓库照收这类词，标记只是让审校看得见，不是筛除条件。`labels` 只在术语不落在 block/item/entity 域时给（biome、stat 之类）。`origin_zh` 是本次改过译文的行的旧值，取自 diff 的 `changed`。`reason` 是模型的一句话理由；LLM 复核暂停期间不写。`updated` 恒空；`removed` 收 diff `removed` 段里过滤后仍属产品名称的行。

LLM 复核暂停：`judge` 不读 `LLM_*` 环境变量、不调模型，卡片全部按原样通过（恢复时取消 `utility/termgen.py` 里 `judge_cmd` 的注释）。模板卡不送审，它只是句子骨架。`--known` 传已有的术语表：en 命中且译文全在表内的卡跳过（记 `skipped_known`），en 没命中但译文能由表里的词拼出来的也跳过（记 `skipped_derived`，例如 `Concrete Slab` = `Concrete` + `Slab`），只传 `terms-v1.tsv`。`--batch-size` 与 `batches_failed` 只在 LLM 复核启用时生效。

## 文件

| 路径 | 内容 |
|---|---|
| `utility/termgen.py` | 现行生产工具 |
| `utility/archive/` | v1 到 v4 的冻结快照，`termgen.py` 是 v1；另有 v3 的 graft 和 `coverage_report.py` |
| `utility/termgen_cases.json` | 40 条评估用例 |
| `utility/test_termgen.py` | 11 条单元测试 |
| `utility/termgen_scorecard.py` | 打分脚本，对比各版本；v1、v4 用临时目录现跑 |
| `utility/termgen_review.html` | 单页审校工具：贴入 `terms-v1.tsv` 和 `<版本>.terms.json`，勾选后导出新的 v1 |
| `Vanilla/diffs/<from>-<to>.terms.json` | CI 跑 `judge` 生成的审校清单，人工过一遍后合并 |

CI（Continuous Integration，持续集成）在 `.github/workflows/term-candidates.yml`：`Vanilla/diffs/*.json` 有新提交时选最新一份，跑一条 `judge --input Vanilla/latest.tsv --focus <diff> --exclude-keys 'banner|tropical_fish|subtitles' --known Vanilla/terms/terms-v1.tsv`，产物按默认命名落在 diff 旁边（`<版本>.terms.json`），由 bot 提交回 main。手动触发时可以指定 diff 路径。

## 实测数字

`python utility/termgen.py extract`（2026-10-04，本机）：

- 8559 行输入 → 过滤后 2636 行 / 2457 对唯一 en-zh → 1167 张卡：649 零件、9 模板、509 例外。
- 送审 54,922 字符，输入 133,872 字符，减少 59%。
- 50 行由模板派生；例外行 603；重建核验 2636/2636 通过；耗时约 4 s。

`python utility/termgen_scorecard.py --with-ranked`：

| 版本 | 召回 | any_ok |
|---|---|---|
| termgen（现行） | 0.791（519/656） | 0.977（512/524） |
| v4 | 0.782（513/656） | 0.973（514/528） |
| v1 | 0.953（625/656） | 0.893（576/645） |
| v2 | 0.916（601/656） | 0.841（307/365） |

召回的分母是 656 条可达 gold，即术语表 735 条里在语料中出现过的那些。any_ok 的分母是抽到的卡片：termgen 和 v4 算全部卡片，v1、v2 只算查过译名的卡片。v1、v2 走宽召回，卡片多，译名通过率低。

## 已知局限

- 模板可能语义不贴。卡 t4 是 `{0} with chest` ↔ `运输{0}`，零件都对，整句不一定对。工具只提出候选，由审校的 LLM 或人否掉。
- 中文候选按子串统计选出，短变体会把无关译文算成已译（见 `Docs/TERMS_SPEC.md` 第 3 节）。LLM 复核暂停期间，这类变体由人审收掉。
- 零件卡要求片段至少出现两次；拼不出来的整名进例外卡，卡片数随语料增长。
- `--known` 比 en 也比译文：en 命中且卡片译文全在表内才跳过；同形但译文超出的（`Snowy` 表里是「积雪的|雪」，26.3 的卡片给「雪原」）照常送审。`special/` 里的同形词（陶片的 `Explorer` 是「探险」，地图的是「探险家」）同理。
- 预算裁剪后，未选中的行带 `pending`，重建核验不查这些行。默认预算 0 时全部核验。

## 评估过但未采用

| 方法 | 链接 | 原因 |
|---|---|---|
| MDL（Minimum Description Length，最小描述长度）成本加严格漂移规则 | `utility/archive/termgen_v4.py` | 把 516 条本来能由零件拼出的行判成整名例外；召回 0.782、any_ok 0.973，都低于现行 |
| MMR（Maximal Marginal Relevance） | https://dl.acm.org/doi/10.1145/290941.291025 | 去冗余的方向与「零件复用」相反；不是单调 submodular，贪心没有近似保证 |
| KeyBERT | https://github.com/MaartenGr/KeyBERT | 面向「文档到关键词」，本语料是 1:1 平行词典；相似度不能当作可合并 |
| SimAlign | https://aclanthology.org/2020.findings-emnlp.147/ | 短名与单次专名上信号弱，需要下载模型 |
| fast_align | https://github.com/clab/fast_align | 同上；现有对齐够用 |
| AutoPhrase | https://github.com/shangjingbo1226/AutoPhrase | 没有 Windows 路径；只借鉴了统一排序 |
| C-value 作为选择目标 | https://doi.org/10.1007/s007999900023 | 嵌套折扣会压低高复用零件，与覆盖目标冲突 |

## 参考文献

| 文献 | 链接 |
|---|---|
| Koehn, Och, Marcu. Statistical Phrase-Based Translation. NAACL 2003 | https://aclanthology.org/N03-1017/ |
| El-Kishky 等。Scalable Topical Phrase Mining from Text Corpora. PVLDB 2015 | http://www.vldb.org/pvldb/vol8/p305-ElKishky.pdf |
| Jin, Tanaka-Ishii. Unsupervised Segmentation of Chinese Text by Use of Branching Entropy. 2006 | https://aclanthology.org/P06-2056/ |
| Feng 等。Accessor Variety Criteria for Chinese Word Extraction. Computational Linguistics 2004 | https://aclanthology.org/J04-1004/ |
| Frantzi, Ananiadou, Mima. Automatic Recognition of Multi-word Terms: the C-value/NC-value Method. 2000 | https://doi.org/10.1007/s007999900023 |
| Pantel, Pennacchiotti. Espresso: Leveraging Generic Patterns for Automatically Harvesting Semantic Relations. 2006 | https://aclanthology.org/P06-1015/ |
| Thelen, Riloff. A Bootstrapping Method for Learning Semantic Lexicons using Extraction Pattern Contexts. 2002 | https://aclanthology.org/W02-1028/ |
| Chiang. A Hierarchical Phrase-Based Model for Statistical Machine Translation. ACL 2005 | https://aclanthology.org/P05-1033/ |
| Nemhauser, Wolsey, Fisher. An analysis of approximations for maximizing submodular set functions (Part I). 1978 | https://doi.org/10.1007/BF01588971 |
| Lin, Bilmes. A Class of Submodular Functions for Document Summarization. 2011 | https://aclanthology.org/P11-1052.pdf |
| Khuller, Moss, Naor. The budgeted maximum coverage problem. 1999 | https://doi.org/10.1016/S0020-0190(99)00031-9 |
| Carbonell, Goldstein. The Use of MMR, Diversity-Based Reranking for Reordering Documents. SIGIR 1998 | https://dl.acm.org/doi/10.1145/290941.291025 |
