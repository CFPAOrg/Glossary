# utility

术语候选工具和配套脚本。流水线依据、命令、实测数字见 `Docs/TERMGEN.md`。

## 文件

| 路径 | 内容 |
|---|---|
| `termgen.py` | 现行工具，`extract`、`bench`、`judge` 三个子命令 |
| `termgen_scorecard.py` | 打分脚本，对比各版本 |
| `test_termgen.py` | 单元测试 |
| `termgen_cases.json` | 40 条评估用例 |
| `termgen_review.html` | 审校页，在浏览器里打开 |
| `archive/` | v1 到 v4 的冻结快照，另有 v3 的 graft 和 `coverage_report.py`，只作历史参考 |
| `LICENSE` | 本目录代码按 MIT 授权 |

## 跑起来

```bash
python utility/termgen.py extract
python utility/termgen.py judge --focus Vanilla/diffs/26.2-26.3.json --known Vanilla/terms/terms-v1.tsv
python utility/termgen_scorecard.py --with-ranked
cd utility && python -m unittest test_termgen
```

`extract` 把条目打到 stdout，`judge` 把审校 JSON 写在 diff 旁边。
