# SWE-agent 论文复现研究

本仓库用于完整复现与扩展研究《SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering》。研究目标是从作者工件复算、论文精确模型重跑和现代模型复验三条独立证据链，重新生成论文全部经验结果、消融和轨迹分析。

当前状态（2026-07-17）：公开工件复现已完成，论文输出清单覆盖 54/54；论文原模型严格重跑为 0/18，受退役模型、未发布精确配置、预算和正式运行资源门槛阻塞。因此整篇论文严格复现尚未完成，现代模型结果也不计作原模型替代。

## 研究范围

研究分为三个证据层：

1. 工件复算：从作者预测、轨迹和判分日志重新生成论文表图。
2. 严格重跑：使用论文指定模型、代码、数据、配置和预算完成全部正式实验。
3. 现代复验：在严格隔离的命名空间中比较当前模型并验证 ACI 结论。

正式规模至少包含 13,140 个论文对齐代理 episode。扩大实验前必须先完成版本、资产、精确配置、模型可用性、预算和 evaluator 重放门槛。

## 仓库结构

```text
05/
├── code/                 # 固定版本的第三方实现
├── conf/                 # 研究与实验配置
├── data/manifests/       # 数据与官方工件清单，不存放大型缓存
├── data/derived/         # 可由脚本重建的表格与图形底层数据
├── docs/                 # 方案、论文笔记、环境与复现协议
├── logs/                 # 受 Git 管理的实验台账与摘要
├── outputs/              # 原始轨迹、补丁、结果和图表，默认不进入 Git
├── output/pdf/           # 经过渲染检查的最终 PDF 工件
├── paper/                # 论文 PDF 与 arXiv 源码
└── scripts/              # 环境审计与实验辅助脚本
```

## 版本冻结

- 论文：arXiv `2405.15793v3`，NeurIPS 2024。
- 论文时间对齐代码快照：SWE-agent commit `658eb2842e8a8b00069b301338bc342b70538f7a`。
- 论文期评测聚合器：SWE-bench commit `cfb20092bbbee9683176177b2f59b85f522e7f27`。
- 论文期数据：Lite `81ad348adcaf3368691f4db2907f8fc97a8f7526`，Full `283547aced6224d4adbe55c678b4c9c43fe7d501`。
- SWE-agent 选择依据：`658eb284` 是 arXiv 初次提交时间 `2024-05-06 17:41:33 UTC` 之前的最后一个上游提交。
- 默认论文配置：temperature `0.0`、文件窗口 `100` 行、历史处理器 `Last5Observations`。

代码快照用于最大程度贴近论文提交时状态，但上游未在论文中声明唯一提交哈希，因此该映射属于可审计的时间对齐选择，而不是官方保证。公开 GPT-4 轨迹进一步表明，实际 prompt 由初始提交模板、Last-5 历史处理器和两个 system prompt 参数标签变体组成，不能由单一公开提交逐字生成。

## 复现门槛

只有满足以下条件后才能扩大实验规模：

- 容器化评测后端可用；
- 单个 SWE-bench Lite 实例能够稳定产生轨迹和补丁；
- 判分过程能够独立重放；
- 每次运行均记录代码哈希、配置、模型标识、时间、token、成本和退出状态；
- 开发集在正式实验前冻结。

完整方案见 [docs/full_paper_reproduction_plan.md](docs/full_paper_reproduction_plan.md)，公开工件完成审计见 [docs/public_artifact_completion_audit.md](docs/public_artifact_completion_audit.md)，现代 dev20 基线统计见 [docs/modern_dev20_baseline_analysis.md](docs/modern_dev20_baseline_analysis.md)，官方工件追溯与已复算结果见 [docs/artifact_provenance.md](docs/artifact_provenance.md)，A01–A10 实例级分析见 [docs/official_instance_analyses.md](docs/official_instance_analyses.md)，A13/A14 定性案例与运行时 prompt/ACI 审计见 [docs/official_qualitative_interface_audit.md](docs/official_qualitative_interface_audit.md)，历史评测聚合器验证见 [docs/evaluator_replay.md](docs/evaluator_replay.md)，论文期协议与缺失资产边界见 [docs/protocol_recovery_audit.md](docs/protocol_recovery_audit.md)，机器清单见 [conf/full_paper_matrix.yaml](conf/full_paper_matrix.yaml)，逐次记录见 [logs/experiment_log.md](logs/experiment_log.md)。

论文源码中的 ACI 消融、超参数、pass@k 与失败模式聚合值可用以下命令重建：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_paper_source_aggregates.py `
  --pdftotext /mnt/d/texlive/2026/bin/windows/pdftotext.exe
```

这些输出明确标为 `paper_source_aggregate`。它们验证论文最终表图数据，不替代缺失的逐实例预测、轨迹、标签或精确重跑。

论文期公开实例级工件中的 A01–A10 可用以下命令重建：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_official_instance_analyses.py
```

该命令生成 13 个 CSV 和 4 份 PDF。A01、A02、A06、A09、A10 精确匹配，A05 与 A07 完成公开轨迹重放；A03、A04、A08 的公开轨迹缺口和论文内部不一致单独保留，不能视为精确重跑。

论文四个定性案例与公开 GPT-4 运行时 prompt/ACI 可用以下命令审计：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_official_qualitative_interface.py
```

该命令核验 72/72 个论文 action、4/4 个 gold patch 与结果标签，并遍历 Full/Lite 共 2,568 条轨迹恢复两个 system prompt 变体、统一 demonstration、instance template 和 10 个命令实现。输出属于公开运行工件审计，不替代原模型重新推理。

八组官方主预测的历史聚合报告可用以下命令重放：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/replay_official_evaluator.py
```

论文期代码与数据 revision 得到 `8/8` 完整类别列表一致；固定的 2025 数据 revision 只得到 `6/8`，证明正式论文口径不能使用浮动的最新数据集。

在聚合重放之上，pytest 4.4 的一个官方 resolved 和一个官方 applied-unresolved prediction 已从原 patch 重新构建容器；两者完整测试结果 `2/2` 与历史日志相同。gold、官方 no-apply、空字符串、null 和重复行五条边界输入也得到 `5/5` 精确匹配。输入准备、运行、无效基础设施尝试与收集命令见 [docs/evaluator_replay.md](docs/evaluator_replay.md)。

## 安全与数据规则

- API 密钥只通过环境变量或未跟踪的密钥文件提供。
- 公共 benchmark 与私有代码严格分离。
- 不修改共享 conda 环境、全局配置或其他项目目录。
- 服务器操作仅限 `/public/home/mty/GeYugong/05_sweagent_repro_ser/`。
