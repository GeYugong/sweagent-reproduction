# 公开工件复现完成审计

审计日期：2026-07-17

## 结论

公开工件复现层已完成，覆盖论文输出清单 54/54。这一结论表示所有公开可得的论文源码成员、作者发布的预测/轨迹/评测工件及可确定性派生文件均已核验；未公开的逐实例原始运行、标签或精确实现已经完成负检索并进入明确终态。

该结论不等于整篇论文严格复现完成。论文指定的退役模型、部分精确消融配置、dev37 实例清单、失败标签、批量预算、磁盘和容器资源仍未满足；现代模型实验也不能替代原模型严格重跑。

## 输出覆盖

- 论文输出清单：54/54 处于可审计终态；
- 作者工件精确复算：18 项；
- 作者工件复算且量化公开缺口：15 项；
- 论文源码资产验证：8 项；
- prompt、命令或界面审计：13 项；
- 12 个论文期仓库 gold 环境：11 个 full-reference outcome，1 个 Requests 外网语义替代验证，仓库级 12/12。

| 输出状态 | 数量 |
|---|---:|
| `ARTIFACT_AUDITED` | 13 |
| `ARTIFACT_RECOMPUTED_EXACT` | 18 |
| `ARTIFACT_RECOMPUTED_WITH_DOCUMENTED_GAP` | 7 |
| `SOURCE_AGGREGATE_REBUILT_RAW_INPUT_BLOCKED` | 8 |
| `SOURCE_ASSET_VERIFIED` | 8 |

逐输出证据、source member 数量、派生文件状态和 gate 状态位于 `data/derived/paper_output_coverage.csv`。唯一 source member 与派生文件的字节数、SHA-256，以及输入清单哈希位于 `data/manifests/full_reproduction_coverage.json`。

## 缺失私有工件的终态

协议恢复清单中的 11 个组件和 4 组结果资产均已进入终态。未发布内容包括 Shell-only 和部分 ACI 实现、八项消融原始运行、dev37 ID、五次采样轨迹、六次 pass@k 预测、248 个失败标签及 15 个验证样本。论文聚合值可以从源码重建，但不会被表述为逐实例原始工件复算。

## 严格重跑阻塞门槛

| 门槛 | 状态 |
|---|---|
| `G_MODEL_GPT4_TURBO` | `BLOCKED_UNAVAILABLE` |
| `G_MODEL_CLAUDE_3_OPUS` | `BLOCKED_UNAVAILABLE` |
| `G_MODEL_FAILURE_LABELER` | `BLOCKED_UNAVAILABLE` |
| `G_OFFICIAL_ARTIFACTS` | `PARTIALLY_RECOVERED` |
| `G_EXACT_ABLATION_CONFIGS` | `BLOCKED_PARTIAL_RELEASE` |
| `G_EXACT_RUNTIME_PROMPTS` | `BLOCKED_PARTIAL_RELEASE` |
| `G_DEV37_MANIFEST` | `BLOCKED_MISSING_PROVENANCE` |
| `G_API_PRICING_AND_BUDGET` | `BLOCKED_UNKNOWN_PRICE` |
| `G_EXPERIMENT_BUDGET_AUTHORIZATION` | `BLOCKED_NOT_AUTHORIZED` |
| `G_FORMAL_DISK` | `BLOCKED_CAPACITY` |
| `G_SERVER_RUNTIME` | `BLOCKED_NO_CONTAINER_RUNTIME` |

严格完成判定保持为：`public_artifact_reproduction_complete AND exact_model_rerun_complete`。当前公开工件项为真，原模型重跑项为假，因此 `strict_full_paper_reproduction_complete=false`。

## 可复核命令

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /mnt/d/0code/Research/05/.venv-analysis/bin/python `
  scripts/audit_full_reproduction_coverage.py

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /mnt/d/0code/Research/05/.venv-analysis/bin/python `
  scripts/validate_full_reproduction_plan.py
```
