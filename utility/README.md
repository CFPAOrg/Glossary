# utility

从语料里挖术语候选。四个算法共用一个入口 `utility/final.py` 和一套输入读取规则，按「手上有什么语料」挑一个用。流水线依据、实测数字、已知局限在 `Docs/TERMGEN.md`。

## 快速开始

```bash
# 现行生产工具：Minecraft 名字表 -> 候选条目（TSV 到 stdout）
python utility/final.py compose extract

# 单元测试
cd utility && python -m unittest test_termgen
```

不指定算法时打印用法；算法名之后的参数原样透传给该算法。

## 选哪个

| 手上有什么 | 用哪个 | 怎么干活 |
|---|---|---|
| 同一批条目带 en + zh 平行名 | **`compose`**（生产工具） | 平行短语抽取（包含关系 + Dice）→ 分支熵/搭配强度门控 → 锚点递归补前后缀 → 压成 `u` 零件、`t` 模板、`x` 整名例外三类；写完逐行**重建核验**，每行输入都能由条目拼回原文和译文。`--known` 传已有术语表去重 |
| 只有英文，且是短名/键值式显示名 | **`single`** | 词已由空格给定，主力是**组合纪律**：支持度过滤 → 按长度升序，能被更短条目拼出的不单列。左右邻熵和搭配强度**默认不当门**，只参与排序——开门会误杀 support 高的词（`Egg` 几乎总跟着 `Spawn`，邻居熵只有 0.59）。`--family` 用共现图（LPA/连通分量）分家族，适合木种、颜色、矿物这类成组翻译。模组 key 用 `--key-filter off` |
| 只有英文，语料**含长段落** | **`mod mine <lang 目录> en --termhood specificity`** | 切子句取 n-gram（en 1~5 词）→ 凝聚度用最小互信息、边界用左右邻接熵，阈值都取候选自身分布的分位数 → 按影响条目数排序。`specificity` 用通用英语频率参照（wordfreq，只支持 en）判断「这是不是领域词」，散文语料上比 `self` 分位数稳。`--ref <语言>` 可给术语找同目录另一种语言的对应名 |
| 只有中文/日文名字表 | **`cjk`** | 没空格，词得自己发现：**凝固度当门 + 最长匹配剪碎片**是主力（没被最长匹配切中的碎片全丢，实测碎片率 46.7% → 1.1%）。**自由度默认不当门**，只当输出列——名字表里后缀词右邻恒为 EOS，熵为 0，开门会把词表从 1078 砍到 83、精确召回从 0.43 掉到 0.04。`--column zh_cn` / `ja_jp` 选列 |
| 模组 `lang` 目录的整条工作流 | **`mod prep` / `review` / `assemble`** | prep（只有 `en_us.json`）出组合骨架 + 待译术语表 + 一致性词表 + 覆盖报告；review（`en_us.json` + `zh_cn.json`）出分歧报告 + 组合文件 + 展开校验；assemble 把回填好的术语表装成最终组合文件 |

两条适用范围：

- 选型表里的召回数字（compose 0.791 / any_ok 0.977 等）都量在 **Minecraft 名字表**（8559 行、名字型、条目短）。换散文语料不能照搬：`single` 只吃 ≤7 词无标点的名字型，散文该走 `mod mine`。参考量级：533,864 条散文语料（长段落占 86%）跑 `mod mine en --termhood specificity` 用时 3 分 53 秒，155.8 万候选收敛到 5,044 个术语，覆盖 20.9% 的条目。
- `compose` 是现行生产工具，另外三个不进 CI，是各自场景下的备选；`termgen_scorecard.py` 也只跑进程内的现行工具。

## 子命令

| 算法 | 子命令 |
|---|---|
| `compose` | `extract`（候选到 stdout）、`bench`（指标与用例）、`judge`（审校 JSON） |
| `single` | `extract`、`bench` |
| `cjk` | `extract`、`bench` |
| `mod` | `prep`、`review`、`assemble`、`mine` |

`mod` 系命令结束时在 stdout 打一行 JSON 摘要（产物路径 + 统计），诊断走 stderr。所有命令同输入同输出，遍历序和阈值都确定，产物可直接进 CI 比对。

## 输入

`compose` / `single` / `cjk` 共用一个读取器，按扩展名分派：

| 形态 | 规则 |
|---|---|
| `*.json` | **只认 Minecraft diff 形状** `{"added": {key: {"en_us": …, "zh_cn": …}}, "changed": {…}}`，只取这两段。扁平语言包 `{key: en}` 会被**静默**读成 0 行，不报错 |
| `*.txt` | 每行一条英文原文，key = 行号（1 起），zh 为空 |
| 其它 | 按 TSV 读。有表头（首格是 `key` / `en_us` / `en`）就按列名取：`en_us` 优先于 `en`，`zh_cn` 优先于 `zh`，列名大小写不敏感、首尾空白剥掉，缺 `key` 用行号；没有表头就静默按位置取第 1 列 en、第 2 列 zh。不做引号转义，行内 `"` 原样保留 |

TSV 的坑：UTF-8；**带 BOM 会丢 `key` 列**（首格变成 `\ufeffkey` 认不出来，key 退化成行号，表头算第 1 行），`en_us` / `zh_cn` 两列不受影响。

`mod` 吃目录：`<dir>/en_us.json|.lang` 必需，缺则报错退出；`zh_cn.json|.lang` 可选，缺则找同级的 packer-policy 合并表。`.lang` 是 1.12 的 `key=value`（`#` 注释行、key 两侧 trim、重复 key 取首个）。`mine` 的语言是位置参数 `en|zh|ja|ko`，`zh` 归一成 `zh_cn`。

**key 过滤**（`single` / `cjk`，默认开）：走 `Vanilla/diffs/term-key-filters.json` 的白/黑名单正则，黑名单命中即否、白名单命中才算。`--key-filter off` 全收；`--keys <正则>` 顶替白名单。`off` 和 `--keys` 都不读那个 JSON，换仓库直接可用；只有默认的 `on` 且没给 `--keys` 才读，读不到报错退出。

## 输出

| 命令 | 产物 |
|---|---|
| `compose extract` | stdout TSV：`id / en / zh / kind / uses / reason / score / sources / evidence` |
| `single extract` | stdout TSV：`en / tokens / support / prod / entropy / join / score / sources` |
| `cjk extract --out` | TSV：`unit / chars / support / cohesion / freedom` |
| `mod mine -o` | `<前缀>-mine.tsv`：`term / n / impact / long / name / mi / hmin / zh / zh_votes / zh_total / zh_src / example`（CJK 语言把 `zh*` 换成 `ref*`，`example` 前多一列 `mods`）+ `<前缀>-mine.md` |
| `mod prep -o` | `-skeleton.json`（`{target, entries: [{templates, parameters}]}`）+ `-terms.tsv`（`display / role / tokens / impact / example / zh`，**只填最后一列**）+ `-glossary.txt` + `-coverage.md` |
| `mod review -o` | `-divergence.md`（只报事实）+ `-composition.json`（与 skeleton 同形，值模板已拼好）+ `-verify.md`（重现率 / 错值 / 多余键） |
| `mod assemble <骨架> --terms <填好的表> -o <文件>` | 组合文件 JSON（同 `-composition.json` 形状） |

`compose extract` 的字段细节：`id ∈ u<n> / t<n> / x<n>`（零件 / 模板 / 例外，n 不补零）；`reason` 零件取 `nested_phrase` / `reusable_fragment` / `standalone_name`（另有诱导路径 `induced_atom`），模板取 `sentence_template`，例外取 `unexplained_translation`（有译法却拼不出）或 `missing_translation`（zh 为空）；同一英文的多个候选译法用 `|` 分隔；`uses` 是引用该条目的行数；`sources` 是命中的 key；`evidence` 是紧凑 JSON，每个候选译法最多 2 条。实测 8,559 行输入 → 1,167 条条目（`u` 649 / `t` 9 / `x` 509）。

## 文件

| 路径 | 内容 |
|---|---|
| `final.py` | 统一入口：`python utility/final.py <算法> <子命令>` |
| `algos/` | 算法实现：`compose`（中英平行）、`single`（英文单语）、`cjk`（中日文单语）、`mod`（模组 lang 目录） |
| `termgen_scorecard.py` | 打分脚本，进程内跑现行工具 |
| `test_termgen.py` | 单元测试 |
| `termgen_cases.json` | 40 条评估用例 |
| `termgen_review.html` | 审校页，浏览器直接打开 |
| `LICENSE` | 本目录代码按 MIT 授权 |

## 常用命令

```bash
# 生产：从最新 diff 抽候选，生成审校清单
python utility/final.py compose judge --focus Vanilla/diffs/26.2-26.3.json \
  --known Vanilla/terms/terms-v1.tsv

# 单语场景
python utility/final.py single extract --input mod-en.tsv --key-filter off --family
python utility/final.py cjk extract --input Vanilla/latest.tsv --column zh_cn --out zh-terms.tsv
python utility/final.py mod mine <lang 目录> en --termhood specificity -o <输出前缀>

# 质量门槛
python utility/termgen_scorecard.py
cd utility && python -m unittest test_termgen
```

`extract` 打到 stdout，`judge` 把审校 JSON 写在 diff 旁边；`mod mine` 写 `<前缀>-mine.tsv` + `<前缀>-mine.md`。
