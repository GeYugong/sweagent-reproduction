# SWE-agent 论文复现报告

## 摘要

本研究复现并审计《SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering》（arXiv 2405.15793v3）的公开论文工件、历史 evaluator、实例级分析、定性案例、一组现代模型开发集基线及八项现代 ACI 配对实验预注册。研究将证据拆分为源码、作者工件、原模型严格重跑、现代模型复验和探索性实验五类，避免把论文源码中的最终数字或现代模型结果误写成原始模型重新推理。

截至 2026-07-17，完成状态为：

| 证据层 | 状态 | 机器判定 |
|---|---|---|
| 公开工件复现 | 完成 | 54/54 个论文输出进入可审计终态 |
| 原模型严格重跑 | 未完成 | 0/18 个 exact 实验启动 |
| 现代模型复验 | 部分完成 | 默认 ACI dev20 基线完成；八项配置与 160 条配对计划就绪，运行 0/160 |
| 整篇论文严格复现 | 未完成 | `public_artifact_complete AND exact_rerun_complete = false` |

公开工件层包含 18 项作者工件精确复算、15 项公开部分复算并量化缺口、8 项论文源码资产验证、13 项 prompt/命令/界面审计。退役模型、未发布的精确消融实现和原始运行、dev37 ID、失败标签、价格/预算与正式运行资源仍阻止原模型严格重跑。因此本报告的最终结论是“公开工件复现完成，严格重跑受阻”，而不是整篇论文 100% 严格复现完成。

## 1. 研究对象与版本冻结

| 对象 | 冻结版本 |
|---|---|
| 论文 | arXiv `2405.15793v3` |
| SWE-agent | `658eb2842e8a8b00069b301338bc342b70538f7a` |
| SWE-bench evaluator | `cfb20092bbbee9683176177b2f59b85f522e7f27` |
| SWE-bench experiments 当前树 | `2f15350cd32becc4569e0d826361048555b605c0` |
| SWE-bench experiments 论文工件历史 | `a5d52722965c791c0c04d18135f906b44f716d39` |
| HumanEvalFix 工件 | `bbd565c9035f873ba5ee2c1bd1d65c5ee2d85d1a` |
| SWE-bench Lite 论文 revision | `81ad348adcaf3368691f4db2907f8fc97a8f7526` |
| SWE-bench Full 论文 revision | `283547aced6224d4adbe55c678b4c9c43fe7d501` |

论文默认 ACI 固定为 temperature 0.0、100 行文件窗口、`Last5Observations`、一个 demonstration、摘要搜索和带 lint 的编辑器。公开 GPT-4 轨迹显示实际运行 prompt 混合了初始 instance template、后续 Last-5 处理器和两个 system-prompt 参数标签版本，不能由单个公开 Git checkout 逐字生成；该事实作为运行时工件边界保留。

论文模型标识为 `gpt-4-1106-preview`、`claude-3-opus-20240229` 和失败分类使用的 `gpt-4o-2024-05-13`。当前中转端点均不提供这些精确模型；Claude 端点对论文 Opus 标识返回 `model_not_found`，只提供更晚的模型。因此当前模型不能进入 exact 证据层。

## 2. 方法

### 2.1 证据分层

- `source`：从 arXiv 源码包恢复论文最终表格、图形和展示资产；
- `artifact`：从作者公开的 predictions、trajectories、logs 和 evaluation 结果重新计算；
- `exact`：使用论文模型、代码、数据、配置和预算重新运行；
- `modern`：使用当前模型在隔离命名空间中复验论文命题；
- `exploratory`：调试或非论文对齐变体，不进入主结果。

源码聚合不替代作者原始运行，现代模型不替代原模型，代表 evaluator 环境验证也不替代全量 300/2,294 实例重新推理。

### 2.2 输出清单与验收

论文源码中的 54 个经验、定性、prompt 和界面输出逐项登记。每项保存 source member、证据层、依赖 gate、派生文件和验收标准。完成审计固定了 56 个唯一论文源码成员和 35 个唯一派生工件的 SHA-256，并要求所有未公开输入具有明确的负检索终态。

### 2.3 运行环境

公开工件复算和 evaluator 验证在本地 Windows + WSL2 完成。模型推理由远程兼容 API 提供，本地不加载模型权重，因此无需 GPU。远程服务器目录 `/public/home/mty/GeYugong/05_sweagent_repro_ser/` 已建立，但服务器没有通过容器 runtime 验证，本研究未在服务器执行正式 evaluator。

宿主 D 盘测得 651.64 GB 总容量、约 64.07 GB 空闲，低于正式批次 120 GB 门槛。逐仓库 gold 环境采用顺序创建和清理；全量 Lite/Full 容器批次未启动。

## 3. 公开主结果复算

### 3.1 SWE-bench Full 与 Lite

作者论文期 predictions、logs 和 `results.json` 在冻结 evaluator 与数据 revision 上重新聚合。结果如下：

| split | 系统 | 模型 | 工件 resolved | 论文主表隐含值 | 结论 |
|---|---|---|---:|---:|---|
| Lite | SWE-agent | GPT-4 Turbo | 54/300（18.00%） | 54/300 | 一致 |
| Lite | SWE-agent | Claude 3 Opus | 35/300（11.67%） | 39/300（13.00%） | 主表多 4 个 |
| Lite | RAG | GPT-4 Turbo | 8/300（2.67%） | 8/300 | 一致 |
| Lite | RAG | Claude 3 Opus | 13/300（4.33%） | 13/300 | 一致 |
| Full | SWE-agent | GPT-4 Turbo | 286/2,294（12.47%） | 286/2,294 | 一致 |
| Full | SWE-agent | Claude 3 Opus | 241/2,294（10.51%） | 240/2,294（10.46%） | 主表少 1 个 |
| Full | RAG | GPT-4 Turbo | 30/2,294（1.31%） | 30/2,294 | 一致 |
| Full | RAG | Claude 3 Opus | 87/2,294（3.79%） | 87/2,294 | 一致 |

Claude 两项差异不是 evaluator 复算误差：论文的 exit-condition 表分别给出 35 和 241，与作者工件一致。主结果表与论文自身另一张表不一致，因此保留两种口径，不人工改写论文数字。

### 3.2 HumanEvalFix

官方 release 实际包含 Python、JavaScript、Java 各 164 条 trajectory，没有 Go 运行；论文附录的 Go 是文本错误。作者 notebook 用 `*.log` 数量作分母，混入每种语言一个 testbed 日志，Python 又缺少两个 evaluation log，因而得到论文百分比。

| 语言 | passes | notebook 口径 | 固定 164 分母 |
|---|---:|---:|---:|
| Python | 143 | 143/163 = 87.7% | 143/164 = 87.2% |
| JavaScript | 148 | 148/165 = 89.7% | 148/164 = 90.2% |
| Java | 145 | 145/165 = 87.9% | 145/164 = 88.4% |

两种口径均保存，论文数字被成功追溯，但报告主解释采用固定任务数分母。

## 4. 消融、超参数、pass@k 与失败模式

arXiv 源码足以确定性恢复以下最终聚合：

- 12 个 ACI 表行，其中 8 个非默认单因素消融；
- 16 个 dev37 超参数配置均值；
- 6 次 Lite 运行点和 pass@k 曲线；
- 248 个 GPT-4 Lite 未解决实例的 9 类 schema 与 8 个非零类别计数。

默认 18.0% 相对无 lint editor、无 editor、迭代搜索、无搜索、30 行窗口、全文窗口、完整历史、无 demonstration 的结果分别为 15.0%、10.3%、12.0%、15.7%、14.3%、12.7%、15.0%、16.3%。这些值与论文表图一致，但八组原始 predictions/trajectories 未发布，不能计算逐实例配对结果。

pass@k 六次运行的 resolved 数为 52、54、54、56、52、55；论文给出的运行均值为 17.94%、标准差 0.49%，pass@6 为 32.67%。六份实例级 prediction 集未公开，曲线只能从论文聚合重建。

失败模式计数为 Incorrect Implementation 99、Overly Specific 30、Failed Edit Recovery 58、Failed Edit Location 32、Failed Relevant File 5、Gave Up 6、Failed to Reproduce 12、Ran Out of Budget 6。248 个逐实例模型标签、15 个验证 ID 和人工标签未公开，因此无法独立复算论文报告的 87% 分类一致率。

超参数实验缺少随机 37 个 dev instance ID 和 16×5 原始运行，无法进行实例级重算。所有缺失项经过 SWE-agent 822 个公开 PR head、论文期 309 个 PR head、SWE-bench experiments 历史/PR、公开 S3 前缀和论文源码交叉检索，均已进入明确的 `BLOCKED_MISSING_OFFICIAL_*` 终态。

## 5. 实例级与定性分析

### 5.1 A01–A10

作者公开的 Full/Lite trajectories、predictions 和冻结数据支持 10 组实例级分析：

- A01 repository performance：60/60 单元精确匹配；
- A02 temporal performance：25/25 单元精确匹配；
- A03 exit conditions：公开 Claude Full resolved trajectory 缺口导致部分完成；
- A04 turn/step/cost：可得输入完成，论文 prose 存在 cost/计数漂移；
- A05 actions per turn：全部公开 GPT-4 trajectory 重放完成；
- A06 action triples：论文计数精确匹配；
- A07 action transitions：数值 spot checks 完成，保留 legacy label bug；
- A08 failed edits：26 条 GPT-4 Full trajectory 缺失且论文正文百分比与自身计数不相容；
- A09 patch statistics：32/32 单元精确匹配；
- A10 file localization：2/2 精确匹配。

7 项达到精确或完整公开输入重放，3 项以量化缺口终止。缺失 trajectory 不通过重复加权、去重选择或推断退出状态填补。

### 5.2 A11–A14

A11 失败模式图从源码聚合重建，逐实例标签缺失。A12 HumanEvalFix turn 分布由 492 条官方 trajectory 重建，数据和 PDF 可确定性再生。

A13 四个论文定性案例共 72 个 action，与公开 `.traj` 达到 72/72 逐字一致；四份 gold patch 与冻结 Lite 数据 4/4 一致，结果标签 4/4 一致。SymPy 案例的模型没有主动 `submit`，但运行时在 `exit_cost` 时自动提交工作区 patch；Requests 案例还有一处展示层 observation 扩展。这些属于论文展示与运行时语义差异，不改变判分。

A14 遍历 2,268 条 GPT-4 Full 与 300 条 Lite trajectory。2,002 条使用 system prompt 的 required 参数标签，566 条使用 optional 标签；2,568 条 instance template 与 demonstration 一致。10 个论文命令实现全部核验，21 个界面/prompt 资产逐项审计。

## 6. Evaluator 重放

评测证据分为四层：

1. 八组官方主 predictions 的历史聚合：论文期 references 得到 8/8 完整类别列表一致；后期数据 revision 仅 6/8，一共定位三项 SymPy resolved 漂移。
2. pytest 4.4 的一个官方 `RESOLVED_FULL` 和一个 applied-`RESOLVED_NO` 容器重放：完整测试结果 2/2 与历史日志一致。
3. gold、官方 no-apply、空字符串、null 和重复 prediction 边界：5/5 精确状态匹配。
4. 12 个论文期仓库各一个未修改 gold patch：11 个 full-reference outcome；Requests 为 140/141 直接 reference outcome，唯一公共跨站 HTTP 测试由本地 `127.0.0.1 → localhost` 双主机重定向确认 Authorization 被剥离。

12 仓库直接 reference outcome 合计 494/495；加上一个严格限定的外网语义替代验证，仓库级覆盖为 12/12。Requests 原 scorecard 保持 `RESOLVED_NO`，没有被改写成 `RESOLVED_FULL`。

逐仓库环境共保留 30 次新 attempt：10 次为协议有效的最终 full-reference 成功；pytest 复用既有 gold 环境；19 次失败和 1 次早期导入错误但测试通过的协议无效尝试均保留且不计入最终成功。模型 API 调用为 0。

该验证证明历史 evaluator 的聚合、代表核心/边界分支和每个支持仓库的环境链路，不等于全量 300/2,294 prediction 容器重新执行。

## 7. 现代模型 dev20 基线

`gpt-5.6-terra` 在冻结 SWE-bench Lite dev split 的 20 个实例上完成论文快照默认 ACI：

- `RESOLVED_FULL`：4；
- `RESOLVED_PARTIAL`：2；
- `RESOLVED_NO`：4；
- `PATCH_APPLY_FAILED`：4；
- `NOT_GENERATED`：6。

完全解决率为 4/20 = 20.0%，Wilson 95% CI 为 8.07%–41.60%。14/20 生成 prediction，10/20 成功应用。该样本来自 dev split，不能与论文 Lite test 的 18.0% 做直接显著性比较。

trajectory 持久化 397 次 API 调用、5,496,947 input tokens 和 70,405 output tokens。SQLFluff 1763 的最后一次格式纠正请求没有写入 usage，资源日志确认总调用为 398，因此 token 合计是下界。19/20 份 `args.yaml` 精确确认模型、temperature 和 top-p；该实例的缺失运行参数与 usage 单独保留。

八个论文单因素 ACI 的现代重建已经完成离线准备。相对默认配置的结构 diff 通过 8/8，冻结 `AgentConfig` 解析通过 8/8，自定义命令的语法与行为测试通过 4/4。三项未公开命令实现标为行为重建；特别是 iterative search 的上下文每侧 5 行属于显式假设。20 个基线实例与八项变体形成 160 条配对计划，25 次/实例的硬调用上限为 4,000。

按 dev20 持久化均值，160 条新增运行投影为 3,176 次调用、43,975,576 input tokens 和 563,240 output tokens；资源审计口径为 3,184 次调用。中转端点没有可核验价格，美元成本不填 0，总预算也未授权，因此实际运行仍为 0/160。尚无 McNemar 统计，`modern_replication_complete=false`。配置、配对表和预注册见 `docs/modern_aci_reconstruction.md`。

早期自定义 `no_search + no_editor` 同时改变两个因素，既不是论文 Shell-only 也不是单因素消融。两条完成轨迹只作为 exploratory 证据，后续运行已停止，不进入论文对齐结果。

## 8. 可重复性与再生成审计

六条不需要模型推理的生成链从冻结输入重新执行：主 SWE-bench、HumanEvalFix、论文源码聚合、A01–A10、A13–A14、历史 evaluator。48 个受审计文件的结果为：

- 39 个与 Git baseline 逐字节一致；
- 5 个 JSON 仅 `generated_at_utc` 或 `cache_hit` 变化；
- 4 个 CSV 仅 LF/CRLF 文本过滤差异；
- 真实语义或二进制差异 0。

全部 PDF 逐字节一致。论文期 evaluator 仍为 8/8，后期 revision 仍为 6/8。该结果证明公开工件生成链可以离线重放。

所有受 Git 管理的文件完成凭据模式扫描，未发现 API key。密钥只存在于 Git 忽略且 ACL 受限的环境文件；报告和清单不保存密钥值。

## 9. 预算与规模边界

完整 exact 矩阵包含 18 个实验，最大 13,440 个 agent episode；在证明一次 300-instance 默认 Lite 可复用后，最低唯一 episode 仍为 13,140。另有 248 次失败标签请求。按论文每实例 4 美元上限，理论 ceiling 为 52,560 美元。

现有 dev20 的轨迹持久化均值外推约为 260,829 次模型调用、36.11 亿 input tokens 和 4,625.6 万 output tokens；由于存在一条未持久化 usage，该估计是下界。当前中转价格未知，且没有明确批准总支出 ceiling，因此不启动大规模 API 批次。

这一约束不是 GPU 问题。API 推理不需要本地 GPU；主要本地负载是历史依赖安装和 evaluator。当前阻塞来自模型/协议可得性、费用授权、磁盘和容器资源。

## 10. 已知偏差与威胁

1. 论文精确模型均不可从当前端点调用；现代模型结果不能证明原模型可重复性。
2. Shell-only、部分 ACI 命令实现、八项消融原始运行、dev37、pass@k predictions 和失败标签未发布。
3. 公开 GPT-4 Full trajectory 比论文分母少 26 条，部分行为分析只能量化公开子集。
4. 上游数据 revision 会改变少量 resolved 结果，必须使用论文期 revision。
5. 历史 Python/conda/PyPI/系统包漂移需要实例级兼容修正；所有修正均保留理由与 attempt 历史。
6. Requests 的一个测试依赖已漂移的公网服务，只能提供本地等价安全语义验证，不能算作直接 full-reference outcome。
7. 现代 dev20 样本量小、仓库分布不均；配对消融只完成配置与运行预注册、尚未执行，不支持对 ACI 因果效应作正式结论。

## 11. 主要可复核入口

- 完整计划与矩阵：`docs/full_paper_reproduction_plan.md`、`conf/full_paper_matrix.yaml`；
- 论文输出清单与完成审计：`conf/paper_output_inventory.yaml`、`data/manifests/full_reproduction_coverage.json`；
- 官方结果与 provenance：`docs/artifact_provenance.md`；
- evaluator：`docs/evaluator_replay.md`；
- A01–A10：`docs/official_instance_analyses.md`；
- A13–A14：`docs/official_qualitative_interface_audit.md`；
- 协议负检索：`docs/protocol_recovery_audit.md`；
- 现代 dev20：`docs/modern_dev20_baseline_analysis.md`；
- 现代 ACI 重建与配对预注册：`docs/modern_aci_reconstruction.md`；
- 预算约束完成与停止方案：`docs/bounded_reproduction_completion_plan.md`；
- 再生成审计：`docs/zero_cost_regeneration_audit.md`；
- 全部实验过程：`logs/experiment_log.md`、`logs/experiment_registry.csv`。

## 12. 最终结论

论文公开层面的经验结果、可得实例级分析、定性案例、prompt/ACI 资产和历史 evaluator 已完成可审计复现。54/54 个论文输出具有源码或作者工件证据；公开输入缺口均被量化，不通过推断、选择性重试或现代模型结果填补。零成本生成链在重新执行后没有语义漂移。

原模型严格重跑仍为 0/18。缺失精确模型、未发布协议工件和未获授权的高额批量预算使严格复现无法诚实标为完成。若后续获得论文模型访问、精确缺失配置和明确费用 ceiling，可按已冻结矩阵直接进入 E01–E18；在此之前，最准确的终态是：

`COMPLETE_PUBLIC_ARTIFACT_REPRODUCTION / BLOCKED_EXACT_MODEL_RERUN / PARTIAL_MODERN_REPLICATION / STRICT_COMPLETE_FALSE`

后续项目终点已经另行固定为预算约束的现代复现：九配置 × dev23 × 四 repetitions，828 个单元中现有 20 个、需新增 808 个，预计新增成本为当前成本的 40.4 倍。正常预算为 50 倍，80 倍绝对硬停；完成全量评测、预注册统计、成本审计、哈希和 Git 冻结后写入 `BOUNDED_MODERN_REPRODUCTION_COMPLETE` 并停止。该标志不改变上述 exact/strict 结论。
