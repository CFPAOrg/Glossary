# 原版术语与风格规范

本规范定义 `Vanilla/terms/` 下的术语表格式、匹配语义与 `STYLE.md` 作用域规则，供词库维护者和接入程序使用。

## 数据资产与加载分工

- `Vanilla/terms/terms-v1.tsv`：原版通用术语主表，收录方块、物品、实体与可复用构词零件。
- `Vanilla/terms/terms-{biome,enchantment,effect,color,mob,tech}.tsv`：六张域分表，分别收录生物群系、附魔、状态效果、16 种基本颜色、生物（含村民职业）与属性/技术词条，读取时与主表合并加载。
- `Vanilla/terms/special/terms-<token>.tsv`：四张隔离分表（`pottery`、`subtitles`、`trim`、`tropical_fish`）。仅当待处理条目的语言 key 包含 `<token>` 时加载，不并入主表；同一个 `en` 以所在隔离分表为准。文件名必须取 key 中的真实片段，例如 `terms-tropical_fish.tsv`。
- `Vanilla/terms/terms-version.tsv`：历史版本差异表，记录 `1.12.2` 等旧版本的译名差异。核对旧版本语料时按 `versions` 列选用，避免用新版术语误判旧译。
- `Vanilla/terms/STYLE.md`：原版翻译风格规范，以自然语言记录构词体例、语序变化、整类不译与标点规则，并用 `@scope` 注释声明每段规则的适用键名范围。
- `Vanilla/latest.tsv` 与版本快照（`1.12.2.tsv` 等）：从游戏语言文件提取的多语平行记忆库，不是术语表。

## 术语表格式与字段

术语文件采用 UTF-8 编码、无引号制表符分隔（TSV）。除 `terms-version.tsv` 外，其余主表与分表统一使用四列表头 `en\tzh\treason\tcomment`：

- `en`（必填）：字面英文。
- `zh`（必填）：字面中文。同一所指在不同语境下的固定写法变体用 `|` 分隔，例如 `深层|深板岩`。
- `reason`：边界说明（如「可能过于严格，允许发挥」），供审校人员与 LLM（Large Language Model，大语言模型）参考，不参与匹配。
- `comment`：维护者备注（词条来源、跨表互指或关联规则），不参与匹配。

`terms-version.tsv` 在首列增加适用版本号 `versions`，表头为 `versions\ten\tzh\treason\tcomment`。

## 匹配规则与收词边界

- 英文匹配按词边界切分并做词形归一化（小写、去除 `'s` 与单数化），从左到右取最长匹配。已匹配的词不再拆开计入，例如 `Pale Hanging Moss` 整条在表内时，不再单独计入 `Pale`、`Hanging` 或 `Moss`。非词边界不触发命中，`Chain` 不会命中 `Enchant`。
- 中文没有词边界，程序将 `zh` 按 `|` 切分后逐项做子串匹配，任一变体出现在译文中即算命中。单字或过短变体（如 `链`、`竹`）容易把无关汉字算成已译，只在固定减字构词且接受误命中代价时才保留。
- 匹配程序只输出候选和标记未命中，不对译文做硬性裁决。下游应把未命中词条的 `en`、`zh` 与非空 `reason` 一并交给人工或 LLM 判断。
- 收词优先收录跨条目复用的构词零件（如 `Oak`、`Deepslate`、`Hanging`），以及无法由零件字面推出的整词（如 `End Rod` 译作 `末地烛`、`Pale Wolf` 译作 `苍狼`）。已经能由零件按常规语序直拼且译文无偏差的复合词不必重复收入。
- 跨表同名异义词（如 `Armor`、`Infested`、`Luck`、`Speed`、`Wither`）在各自域分表中只保留本域义项，并在 `comment` 中互相标注。`|` 只用于同一所指的固定表面变体，不用于堆砌近义词。

## STYLE.md 与 @scope 规则拼接

术语表解决「某个英文词翻成什么中文词」，具体不译词（如 `TNT`）也收进主表。`Vanilla/terms/STYLE.md` 负责记录依赖语境的规则，涵盖矿石与常规方块的用词切换、助词「的」的取舍、材料块倒装、旗帜颜色嵌槽、整类保留原文与标点间距。

例如 `Exposed`（斑驳）与 `Waxed`（涂蜡）收在 `terms-v1.tsv`；而「单独修饰铜制品带『的』，叠加外层 `Waxed` 时省略内层『的』」这类构词规则写进 `STYLE.md`。

**（1）`@scope` 声明语法**

每个按条件选取的规则块，由二级或三级 Markdown 标题引出，并在标题下一行放置一条单行 HTML 注释：

```markdown
## 基础方块、物品与实体
<!-- @scope {"id": "scope.block_item", "include": ["block.minecraft.*", "item.minecraft.*", "entity.minecraft.*"]} -->
```

注释的作用范围从当前标题开始，延续到下一个同级或更高级标题为止。不带 `@scope` 的标题本身不成块；其下带 `@scope` 的三级标题各自独立成块。JSON 负载支持两种定义：

- 条件作用域：包含 `id`（规则块唯一标识）与 `include`（语言 key 的 glob 通配模式数组）。待处理条目的 key 命中其中任一模式时选中对应规则块。
- 全局作用域：包含 `id` 与 `"apply": "always"`（当前为 `global` 节），表示无论输入什么语言 key 都必须拼入提示词。

**（2）程序选择性拼接流程**

- 解析 `Vanilla/terms/STYLE.md` 时，按带有 `<!-- @scope ... -->` 的标题切分出各个规则块，并剥除 `@scope` 注释行本身以减少提示词冗余字符。
- 处理一批待译或待校对条目时，提取这批条目的全部语言 key，选出所有 `"apply": "always"` 的全局块，再选出 `include` 中任一 glob 能匹配本批至少一个 key 的域规则块。
- 将选中的规则块按文档原有顺序去重拼接，放入 LLM 的系统提示词或上下文中（文件开头的简短说明可按需保留）。
- 当上游任务只有纯文本片段、没有语言 key 时，回退为只加载 `"apply": "always"` 块，或由调用方显式指定目标 `id`，避免把旗帜、字幕、键盘按键等特定域规则混入无关上下文。

本地可用 `python utility/final.py scope --style --key <语言key>` 预览实际命中的规则拼接结果。
