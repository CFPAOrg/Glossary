# 我的世界中英术语库

本仓库维护 Minecraft 简体中文术语表、翻译风格规范、版本语言快照，以及配套的术语抽取与校对工具。

## 目录与资产

- `Vanilla/terms/terms-v1.tsv`：原版通用术语主表，收录方块、物品、实体与可复用构词零件。
- `Vanilla/terms/terms-{biome,enchantment,effect,color,mob,tech}.tsv`：六张域分表，分别对应生物群系、附魔、状态效果、颜色、生物与属性/技术词条，使用时与主表合并加载。
- `Vanilla/terms/special/terms-{pottery,subtitles,trim,tropical_fish}.tsv`：四张隔离分表。仅当语言 key 包含对应片段时加载，不并入主表。
- `Vanilla/terms/terms-version.tsv`：历史版本差异表（如 `1.12.2` 旧译），核对旧版语料时按版本号选用。
- `Vanilla/terms/STYLE.md`：原版翻译风格规范。用 `<!-- @scope {...} -->` 标记每节适用的语言 key 范围，供程序按需查询、拼接。
- `Vanilla/latest.tsv`：最新正式版多语平行记忆库，作对照与抽取基准用，不是术语表。
- `Vanilla/1.12.2.tsv`、`1.16.5.tsv`、`1.18.2.tsv`、`1.19.2.tsv`：历史版本语言快照。
- `Vanilla/diffs/`：版本语言差异（`*.json`）、候选审校清单（`*.terms.json`）与名称域键名过滤规则（`term-key-filters.json`）。
- `Archives/`：早期 1.18.2 时期保留的历史归档。
- `utility/`：只依赖 Python 标准库的术语工具套件（入口 `final.py`）。

## 常见用法

**接入翻译或 LLM 校对工作流**

按 `Docs/TERMS_SPEC.md` 加载 `terms-v1.tsv` 与六张域分表，遇到特定域 key 再挂载 `Vanilla/terms/special/` 对应分表。向 LLM 发送提示词前，解析 `Vanilla/terms/STYLE.md` 中的 `@scope` 注释，只把命中当前批语言 key 的规则块与 `global` 规则拼接进上下文。

**同步版本差异与维护术语表**

GitHub Actions 每日检查原版正式版更新并生成 `Vanilla/diffs/<旧>-<新>.json` 与 `*.terms.json`。本地也可以运行 `python utility/final.py maintain ...` 生成清单，再在浏览器打开 `utility/termgen_review.html` 联合查重并分表导出 TSV。

**语料切分、挖掘与清洗**

`utility/final.py` 提供 `scope`、`translate`、`review`、`maintain`、`clean` 五个工作流子命令，常用参数示例见 `utility/README.md`。运行测试可在 `utility/` 目录下执行：

```bash
python -m unittest -v test_termgen
```

## 文档导航

- `Docs/TERMS_SPEC.md`：术语表格式、匹配规则、分表机制与 `STYLE.md` `@scope` 解析规范。
- `utility/README.md`：`final.py` 工作流命令、`compose` 无损抽取、本地审校与 CI（Continuous Integration，持续集成）自动化说明。
