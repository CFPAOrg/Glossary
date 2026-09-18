# 术语契约

权威数据：`Vanilla/terms/terms-v1.tsv` 加 `Vanilla/terms/special/` 五张。程序只产生候选，对错由人/LLM 裁定。

## 1. 产品

| 文件 | 角色 |
|---|---|
| `Vanilla/terms/terms-v1.tsv` | 术语表 |
| `Vanilla/terms/special/terms-<token>.tsv` | key 含 token 才加载。不要并进主表 |
| `Vanilla/terms/qa-rules.tsv` | 英文结构、汉语格式（深层、墙上的、铜的「的」） |
| `Vanilla/latest.tsv` | 原版语言文件，不是术语 |

`zh` 是查词答案，不是 hash 命中并集。`reason` 给人/LLM，`comment` 给维护者，都不参与匹配。

## 2. 字段

| 字段 | 现行 |
|---|---|
| `en` | 字面英文。词边界匹配 |
| `zh` | 字面中文。无词边界，子串。同一所指表面变体用 `\|`：`深层\|深板岩` |
| `reason` | 散文。边界说明，不参与匹配，建议显示 |
| `comment` | 维护者备注，不参与匹配 |

`en`/`zh` 必填。

## 3. 匹配

英文按词切，从左扫到右，能对上的表项里取最长的，用过的词不再算。所以 `Pale Hanging Moss` 如果整段在表里，就不会再记 Pale、Hanging、Moss。对不上词边界的不算，`Chain` 打不中 `Enchant`。

中文没有词边界，`zh` 用 `|` 切开后，哪一截作为子串出现在译文里都算已译。`深层矿石` 吃「深层」，`深板岩煤矿` 吃「深板岩」。短变体很贵：写成「链」时，译文里随便一个「链」都算过了。

对不上或次数不够，只记候选，程序不判对错。下游把这条的 `en`、`zh`、非空的 `reason` 给人/LLM。有 reason 的多看一眼。

## 4. 收什么

收能反复嵌进许多名称的零件（Oak、Deepslate、Hanging），以及零件拼出来对不上的整词（末地烛不是「末地棒」；苍狼不要拆成 Pale+Wolf）。已经能由零件拼对的整词不必再收。

`|` 只表示同一所指的不同写法，不是近义词筐。短的那截会把无关译文算成已译，真漏了的反而进不了候选。Deepslate 的「深层」和「深板岩」两个都是固定用法，只留一个另一半全是假阳，才并列。`链` 这种短答案是已经拍板、愿意挨误伤的例外。

## 5. 术语 vs QA

术语管这个零件叫什么。QA 管这句话写得对不对：该用「深层」还是「深板岩」、铜氧化要不要「的」、墙上的方块要不要「墙上的」。

铜的「斑驳 / 锈蚀 / 氧化 / 涂蜡」进术语；「斑驳的铜块」里的「的」是汉语习惯，用 QA 去抓。术语表没有 `key`；`qa-rules.tsv` 自己的 `key` 用来限制扫哪些语言键。

## 6. 分表

`Vanilla/terms/special/terms-<token>.tsv`。token 字面即作用域：语言 key **包含** `<token>` 才加载这张表。不要并进主表。同 en 以所在表为准。

例：`terms-subtitles.tsv` 只打 `subtitles.entity.pig.ambient`，不打 `item.minecraft.porkchop`。文件名用 key 里的真实片段（`terms-tropical_fish.tsv`，不要 `tropical-fish`）。
