# SWE-agent 论文复现研究

本仓库用于复现与扩展研究《SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering》。研究目标是建立可审计的论文版基线，比较现代代理实现与本地模型，并在严格控制变量的前提下验证一项 ACI 改进。

## 研究范围

研究分为三个阶段：

1. 论文版部分复现：在固定代码、配置和数据子集上跑通端到端轨迹、补丁生成与判分。
2. 现代对照实验：比较论文版 SWE-agent、现代实现、API 模型与本地代码模型。
3. 单因素改进：从上下文压缩、错误恢复或工具调用约束中选择一个因素进行消融。

第一阶段不直接运行完整 SWE-bench。必须先完成环境检查、单实例重放和小型开发集验证。

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

详细方案见 [docs/research_plan.md](docs/research_plan.md)，逐次记录见 [logs/experiment_log.md](logs/experiment_log.md)。

## 安全与数据规则

- API 密钥只通过环境变量或未跟踪的密钥文件提供。
- 公共 benchmark 与私有代码严格分离。
- 不修改共享 conda 环境、全局配置或其他项目目录。
- 服务器操作仅限 `/public/home/mty/GeYugong/05_sweagent_repro_ser/`。
