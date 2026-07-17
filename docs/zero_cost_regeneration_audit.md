# 零成本论文工件再生成审计

## 结论

从冻结输入重新执行六条公开工件生成链后，48 个受审计文件中 39 个与提交基线逐字节相同，5 个 JSON 仅变化生成时间或 cache-hit 运行元数据，4 个 CSV 仅因 Git/Windows 文本过滤产生 LF/CRLF 差异；真实内容差异为 0。

重新执行的核心结果保持不变：SWE-bench 主结果八组报告在论文期 evaluator 上 8/8 匹配；HumanEvalFix 三种语言计数与修正分母不变；ACI/超参/pass@k/失败模式源码聚合不变；A01–A10 和 A13–A14 状态不变。

## 执行命令

- `.venv-analysis/bin/python scripts/reproduce_official_swebench_results.py`
- `.venv-analysis/bin/python scripts/reproduce_humanevalfix.py --figure output/pdf/humanevalfix_turns_artifact.pdf`
- `.venv-analysis/bin/python scripts/reproduce_paper_source_aggregates.py --pdftotext /mnt/d/texlive/2026/bin/windows/pdftotext.exe`
- `.venv-analysis/bin/python scripts/reproduce_official_instance_analyses.py`
- `.venv-analysis/bin/python scripts/reproduce_official_qualitative_interface.py`
- `/home/gugabobo/.venvs/swebench-paper-eval/bin/python scripts/replay_official_evaluator.py --offline`

全部命令在本地 WSL2 执行，模型 API、GPU和远程服务器使用均为 0。

## 规范化后相同的非语义变化

| 文件 | 规范化时忽略字段 |
|---|---|
| `data/derived/humanevalfix_histogram_bins.csv` | line_endings |
| `data/derived/humanevalfix_instance_results.csv` | line_endings |
| `data/derived/humanevalfix_summary.csv` | line_endings |
| `data/derived/official_swebench_main_results.csv` | line_endings |
| `data/manifests/official_evaluator_replay.json` | generated_at_utc, cache_hit |
| `data/manifests/official_humanevalfix_artifacts.json` | generated_at_utc |
| `data/manifests/official_instance_analyses.json` | generated_at_utc |
| `data/manifests/official_qualitative_interface.json` | generated_at_utc |
| `data/manifests/official_swebench_artifacts.json` | generated_at_utc |

`generated_at_utc` 记录本次执行时间；evaluator 的 `cache_hit` 只表示本地 parquet 是否已存在；`line_endings` 表示工作区 CRLF 与 Git blob LF 的文本过滤差异。三者均不参与论文数值、实例集合或分析结论比较，PDF 等二进制工件仍要求逐字节一致。

## 验收边界

该审计证明当前工作区能从已冻结的公开输入重新生成工件层结果，不证明退役模型可以重新推理，也不补足未发布的消融轨迹、dev37 ID、pass@k 六次预测或失败标签。原模型严格重跑仍保持未完成。

机器清单位于 `data/manifests/zero_cost_regeneration_audit.json`。
