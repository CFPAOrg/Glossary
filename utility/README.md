# utility

术语候选工具和配套脚本。流水线依据、命令、实测数字见 `Docs/TERMGEN.md`。

## 选型

四个算法都要「先有语料，再挑工具」，分界是**手上有什么、语料长什么样**：

| 场景 | 算法 | 机制与门控 |
|---|---|---|
| 同一批条目带 en + zh 平行名（键值对照） | **`compose`**（生产工具） | 平行短语抽取（包含关系 + Dice）→ 分支熵/搭配强度门控 → 锚点迭代补前后缀 → 压成三类条目：`u` 零件、`t` 模板、`x` 整名例外；写完逐行**重建核验**（每行输入都能由条目拼回原文和译文）。`--known` 传已有术语表去重 |
| 只有英文，语料是**短名/键值式**显示名 | **`single`** | 词由空格给定，所以**组合纪律当主力**：支持度过滤 → 长度升序，能被更短条目拼出的不单列；**左右邻熵与搭配强度默认不当门**、只做排序特征（开门会误杀 support 高的词，例如 `Egg` 几乎总跟着 `Spawn`，邻居熵只有 0.59）。`--family` 按共现图（LPA/连通分量）分家族，木种/颜色/矿物这种成组翻译时用。key 过滤默认走原版白名单，模组 key 用 `--key-filter off` |
| 只有英文，语料**含长段落** | **`mod mine <lang 目录> en --termhood specificity`** | 全文本切子句取 n-gram（en 1~5 词）→ 凝聚度用**最小互信息**、边界熵用**左右邻接熵**，两个阈值都取候选自身分布的分位数（默认 MI≥3.0、熵≥1.5）→ 按影响条目数排序。`--termhood specificity` 用通用英语频率参照（wordfreq，只支持 en）判「这是不是领域词」，散文语料上比 `self` 分位数稳。`--ref <语言>` 给术语找同一目录里另一种语言的对应名 |
| 只有中文/日文名字表 | **`cjk`** | 中文没有空格，词要自己发现 → **凝固度当门 + 最长匹配剪碎片**（第 3 步是主力：没被最长匹配切中过的碎片全丢，实测碎片率 46.7% → 1.1%）。**自由度（左右邻熵）默认不当门**、只当输出列：名字表里后缀词右邻永远是 EOS，熵为 0，实测开门开到 1.0 词表从 1078 塌到 83、精确召回 0.43 → 0.04。`--column zh_cn` / `ja_jp` 选列 |
| 模组 `lang` 目录的整条工作流（不止挖术语） | **`mod prep` / `review` / `assemble`** | prep（只有 `en_us.json`）出组合骨架 + 待译术语表 + 一致性词表（词槽 + 语料译法票数）+ 覆盖报告；review（`en_us.json` + `zh_cn.json`）出分歧报告 + 组合文件 + 展开校验；assemble 把回填好的术语表装成最终组合文件。`mine` 与它们同一个文件 |

两条注意事项：

- `Docs/TERMGEN.md` 里的实测数字（compose 召回 0.791 / any_ok 0.977 等）都是在 **Minecraft 名字表**上量的（8559 行输入、名字型、条目短）。换成散文语料，`single`（只吃 ≤7 词无标点的名字型）与 `cjk` 的召回不能照搬——散文该走 `mod mine`。参考量级：一个 533,864 条的散文语料（TiTS，长段落占 86%）跑 `mod mine en --termhood specificity` 用时 3 分 53 秒，155.8 万候选 → 5,044 个术语，覆盖 20.9% 的条目。
- `compose` 是现行生产工具，**其余三个算法不参与 CI**，是各自场景下的备选；`termgen_scorecard.py` 只跑进程内的现行工具。

## 输入 / 输出（spec）

### 输入

`compose` / `single` / `cjk` 共用同一个读取器，按**扩展名**分派：

| 形态 | 规则 |
|---|---|
| `*.json` | **只认 Minecraft diff 形状** `{"added": {key: {"en_us": …, "zh_cn": …}}, "changed": {…}}`，只取这两段里的 `en_us` / `zh_cn`。别的 JSON（比如扁平语言包 `{key: en}`）会被**静默**当成 0 行，不报错 |
| `*.txt` | 每行一条**英文**原文；key = 行号（1 起），zh 为空 |
| 其它 | 按 TSV 读：有表头（首格是 `key` / `en_us` / `en`）就按**列名**取（`en_us` 优先于 `en`，`zh_cn` 优先于 `zh`，列名大小写不敏感、首尾空白剥掉，`key` 缺就用行号）；**没有表头就静默按位置**取第 1 列 en、第 2 列 zh。用 `csv.reader(delimiter='\t', QUOTE_NONE)` 读——**不做引号转义**，行内 `"` 原样保留；UTF-8；**带 BOM 会悄悄丢掉 `key` 列**——首格变成 `\ufeffkey` 认不出来，key 退化成行号（表头算第 1 行），`en_us` / `zh_cn` 两列不受影响 |

`mod` 走**目录**：`<dir>/en_us.json|.lang`（必需，缺则报错退出）+ `zh_cn.json|.lang`（可选，缺则找同级的 packer-policy 合并表）。`.lang` 是 1.12 的 `key=value`（`#` 注释行、key 两侧 trim、重复 key 取首个）。`mine` 的语言是位置参数（`en|zh|ja|ko`），语言码归一 `zh → zh_cn`。

**key 过滤**（`single` / `cjk`，默认开）：走 `Vanilla/diffs/term-key-filters.json` 的白/黑名单正则（黑名单命中即否，白名单命中才算）；`--key-filter off` 全收，`--keys <正则>` 顶替白名单。`off` 与 `--keys` **都不碰那个 JSON**——换到别的仓库直接可用；只有默认的 `on`（且没给 `--keys`）才读它，读不到就报错退出。

### 输出

| 命令 | 产物 |
|---|---|
| `compose extract` | stdout TSV：`id / en / zh / kind / uses / reason / score / sources / evidence`。`id ∈ u<n> / t<n> / x<n>`（零件 / 模板 / 例外，n 不补零）；`kind ∈ unit / template / exception`；`reason`——零件看「被更长条目包含 / 同一原文有多种译法 / 独立名」取 `nested_phrase` / `reusable_fragment` / `standalone_name`（另有诱导路径 `induced_atom`），模板取 `sentence_template`，例外取 `unexplained_translation`（有译法却拼不出）或 `missing_translation`（无译法、`zh` 空）；同一词多条候选译法用 `\|` 分隔；`uses` = 引用该条目的行数；`sources` = 该词命中的 key（`;` 分隔）；`evidence` = 紧凑 JSON `[{"variant","key","en","zh"}]`（每个候选译法最多 2 条）。实测 8,559 行输入 → 1,167 条候选（`u` 649 / `t` 9 / `x` 509） |
| `single extract` | stdout TSV：`en / tokens / support / prod / entropy / join / score / sources` |
| `cjk extract --out` | TSV：`unit / chars / support / cohesion / freedom` |
| `mod mine -o` | `<前缀>-mine.tsv`：`term / n / impact / long / name / mi / hmin / zh / zh_votes / zh_total / zh_src / example`（CJK 语言把 `zh*` 换成 `ref*`，并在 `example` 前多一列 `mods`）+ `<前缀>-mine.md`。文件开头若干行是 `#` 注释 |
| `mod prep -o` | `<前缀>-skeleton.json`（`{target, entries: [{templates: {键模板: 值模板}, parameters: [{token: …}, …]}]}`）+ `-terms.tsv`（`display / role / tokens / impact / example / zh`，**只填最后一列**）+ `-glossary.txt`（条目一览 + 修饰词→中文映射 + 未覆盖键）+ `-coverage.md` |
| `mod review -o` | `<前缀>-divergence.md`（只报事实）+ `-composition.json`（与 skeleton 同形，值模板已拼好）+ `-verify.md`（重现率 / 错值 / 多余键） |
| `mod assemble <骨架> --terms <填好的表> -o <文件>` | 组合文件 JSON（同 `-composition.json` 形状） |

`mod` 系命令结束时在 stdout 打一行 JSON 摘要（各产物路径 + 统计），诊断走 stderr。所有命令**同输入同输出**（遍历序与阈值都是确定的），产物可以直接进 CI 比对。

## 文件

| 路径 | 内容 |
|---|---|
| `final.py` | 统一入口，`python utility/final.py <算法> <子命令>` |
| `algos/` | 算法实现：`compose`（中英平行）、`single`（英文单语）、`cjk`（中日文单语）、`mod`（模组 lang 目录） |
| `termgen_scorecard.py` | 打分脚本，进程内跑现行工具 |
| `test_termgen.py` | 单元测试 |
| `termgen_cases.json` | 40 条评估用例 |
| `termgen_review.html` | 审校页，在浏览器里打开 |
| `LICENSE` | 本目录代码按 MIT 授权 |

## 跑起来

```bash
python utility/final.py compose extract
python utility/final.py compose judge --focus Vanilla/diffs/26.2-26.3.json --known Vanilla/terms/terms-v1.tsv
python utility/termgen_scorecard.py
cd utility && python -m unittest test_termgen
```

单语场景（按上一节选型替换输入）：

```bash
python utility/final.py single extract --input mod-en.tsv --key-filter off --family
python utility/final.py cjk extract --input Vanilla/latest.tsv --column zh_cn --out zh-terms.tsv
python utility/final.py mod mine <lang 目录> en --termhood specificity -o <输出前缀>
```

`extract` 把条目打到 stdout，`judge` 把审校 JSON 写在 diff 旁边；`mod mine` 写 `<前缀>-mine.tsv` + `<前缀>-mine.md`。
