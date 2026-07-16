# SWE-agent 论文复现研究

本仓库用于完整复现与扩展研究《SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering》。研究目标是从作者工件复算、论文精确模型重跑和现代模型复验三条独立证据链，重新生成论文全部经验结果、消融和轨迹分析。

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
├── data/manifests/       # 数据子集清单，不存放大型缓存
├── docs/                 # 方案、论文笔记、环境与复现协议
├── logs/                 # 受 Git 管理的实验台账与摘要
├── outputs/              # 原始轨迹、补丁、结果和图表，默认不进入 Git
├── paper/                # 论文 PDF 与 arXiv 源码
└── scripts/              # 环境审计与实验辅助脚本
```

## 版本冻结

- 论文：arXiv `2405.15793v3`，NeurIPS 2024。
- 论文版代码快照：SWE-agent commit `658eb2842e8a8b00069b301338bc342b70538f7a`。
- 选择依据：该提交是 arXiv 初次提交时间 `2024-05-06 17:41:33 UTC` 之前的最后一个上游提交。
- 默认论文配置：temperature `0.0`、文件窗口 `100` 行、历史处理器 `Last5Observations`。

代码快照用于最大程度贴近论文提交时状态，但上游未在论文中声明唯一提交哈希，因此该映射属于可审计的时间对齐选择，而不是官方保证。

## 复现门槛

只有满足以下条件后才能扩大实验规模：

- 容器化评测后端可用；
- 单个 SWE-bench Lite 实例能够稳定产生轨迹和补丁；
- 判分过程能够独立重放；
- 每次运行均记录代码哈希、配置、模型标识、时间、token、成本和退出状态；
- 开发集在正式实验前冻结。

完整方案见 [docs/full_paper_reproduction_plan.md](docs/full_paper_reproduction_plan.md)，机器清单见 [conf/full_paper_matrix.yaml](conf/full_paper_matrix.yaml)，逐次记录见 [logs/experiment_log.md](logs/experiment_log.md)。

## 安全与数据规则

- API 密钥只通过环境变量或未跟踪的密钥文件提供。
- 公共 benchmark 与私有代码严格分离。
- 不修改共享 conda 环境、全局配置或其他项目目录。
- 服务器操作仅限 `/public/home/mty/GeYugong/05_sweagent_repro_ser/`。
