# SWE-agent 全论文复现总方案

> 方案版本：Revision 2（2026-07-17）
>
> 冻结论文：arXiv `2405.15793v3`
>
> 机器清单：`conf/full_paper_matrix.yaml`
>
> 论文产物清单：`conf/paper_output_inventory.yaml`

本修订版继承 `deep-research-report.md` 中的实验登记、统计检验、成本核算和分阶段交付方法，但研究范围以论文源码为准。原报告建议的“小规模部分复现”只作为现代模型扩展，不缩减 E01–E18 和全部论文表图的完整复现范围。

## 1. 目标与完成定义

本项目的最终目标是复现《SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering》中的全部可计算实验结果、消融结论和轨迹分析，而不是只跑通若干实例或只验证主结论方向。

“完整复现”同时包含四条相互独立的证据链：

1. **论文源码重建（source reconstruction）**：从冻结的 LaTeX 源码、内嵌表格和发布图形重建论文陈述，固定目标数字、图表标签和已发布聚合值。这只能证明发布内容被准确恢复，不能证明原始运行可重复。
2. **工件复算（artifact reproduction）**：使用论文作者公开的预测、轨迹、评测日志和分析输入，重新计算论文中的表格与图形。发布数字、计数和图形数据必须与论文一致；这是验证论文分析代码与报告数字的主要途径。
3. **严格重跑（exact-model replication）**：使用论文指定的模型、代码、数据、配置和预算重新执行推理与评测。由于闭源模型服务具有随机性，不要求逐 token 一致，但模型版本和协议不得替换。
4. **现代复验（modern-model replication）**：在同一论文快照和协议下使用当前可用模型，检验 ACI 结论是否仍然成立。结果必须以现代模型实验命名，不能写成论文原始模型的严格复现。

完成状态拆分为三个不可互相替代的布尔结论：

- `public_artifact_reproduction_complete`：所有公开可得源码和作者工件均已复算，缺失私有工件逐项给出检索证据和不可得终态；
- `exact_model_rerun_complete`：E01–E18 全部使用论文精确模型和协议执行、判分并通过审计；
- `modern_replication_complete`：预注册的当前模型对照已执行并独立报告。

只有前两个结论同时为真，才允许使用“整篇论文严格复现完成”或 100%。退役模型不可调用、原始配置未公开或预算未获授权时，只能报告“公开工件复现完成、严格重跑受阻”，不能把现代模型结果或源码表格替代为 exact。

只有当逐项矩阵中的全部必需工件均有可审计证据，并且所有外部不可得项都得到原始工件替代验证或恢复原模型访问后，才能标记“全论文复现完成”。以下情况均不能单独构成完整复现：

- 只完成 SWE-bench Lite 或自建开发集；
- 使用新模型替代 `gpt-4-1106-preview` 或 `claude-3-opus-20240229`；
- 只引用论文表格而没有从预测/轨迹重新计算；
- 只生成 patch 而没有使用冻结评测协议判分；
- 把探索性组合消融计入论文的单因素消融。

## 2. 论文冻结对象

| 对象 | 冻结值 | 证据 |
|---|---|---|
| 论文 | arXiv `2405.15793v3` | `paper/2405.15793_SWE-agent.pdf` 与源码包 |
| SWE-agent | `658eb2842e8a8b00069b301338bc342b70538f7a` | 初次 arXiv 提交前最后一个上游提交；时间对齐快照，不是逐字运行工作树 |
| 默认配置 | 轨迹恢复的混合配置 | 100 行窗口、`Last5Observations`、演示、摘要搜索、linting editor；精确 prompt 见 A14 清单 |
| GPT-4 模型 | `gpt-4-1106-preview` | 论文实验设置原文 |
| Claude 模型 | `claude-3-opus-20240229` | 论文实验设置原文 |
| 失败分类模型 | `gpt-4o-2024-05-13` | 论文失败模式附录脚注 |
| SWE-bench | test 2,294；Lite test 300 | 论文实验设置与数据表 |
| HumanEvalFix | 每种语言 164 | 官方运行目录确认 Python、JS、Java；附录中的 Go 为笔误 |
| 单实例预算 | 4 美元 | 论文实验设置；超限时自动提交已有修改 |
| 解码 | temperature 0.0；top-p 需由运行工件确认 | temperature 来自论文；快照 CLI 的 top-p 默认值为 0.95 |

论文附录的数据说明把 HumanEvalFix 语言写成 Python、JS、Go，而结果表写成 Python、JS、Java。官方 `humanevalfix-results` 工件已经解决该歧义：发布目录中有 Python、JavaScript、Java 各 164 条轨迹，没有 Go 运行。因此严格复现固定使用 Java，附录中的 Go 记为论文笔误。

公开 GPT-4 Full/Lite 轨迹表明，实际 instance template 对应初始提交 `5b143857`，历史处理器对应后续 `08e66863` 的 Last-5 实现，system prompt 又存在 2,002/566 条轨迹的 required/optional 参数标签变体。`658eb284` 仍作为论文提交时间对齐快照，但严格重跑的逐字 prompt 输入以 `data/manifests/official_qualitative_interface.json` 及其导出文本为准。

## 3. 全部实验清单与最小规模

### 3.1 主结果与基线

| ID | 实验 | 模型/系统 | 数据 | episode 数 | 目标工件 |
|---|---|---|---:|---:|---|
| E01 | 默认 SWE-agent Full | GPT-4 Turbo | SWE-bench test | 2,294 | 主表、仓库/年份分解、成本、轨迹分析 |
| E02 | 默认 SWE-agent Full | Claude 3 Opus | SWE-bench test | 2,294 | 主表、仓库/年份分解、成本、退出条件 |
| E03 | 默认 SWE-agent Lite | GPT-4 Turbo | Lite test | 300 | 主表、默认消融格、失败模式 |
| E04 | 默认 SWE-agent Lite | Claude 3 Opus | Lite test | 300 | 主表、Lite 分解 |
| E05 | Shell-only | GPT-4 Turbo | Lite test | 300 | 主表 11.00% |
| E06 | Shell-only 无演示 | GPT-4 Turbo | Lite test | 300 | 主表 7.33% |
| B01 | RAG 基线重算 | GPT-4 Turbo/Claude 3 Opus | Full 与 Lite | 复用 SWE-bench 官方预测 | 主表 RAG 行、定位 F1 |

Shell-only 是基于 InterCode Bash 的独立交互设置，允许标准 shell 命令，不等同于从 SWE-agent 默认配置中同时删除 `search.sh` 和 `edit_linting.sh`。其 prompt、环境封装和演示必须从作者工件或对应实现恢复。

### 3.2 ACI 单因素消融

默认配置的 18.0% 可复用 E03。其余每个变体均在 300 个 Lite test 实例上独立运行：

| ID | 因素 | 变体 | 论文目标 | episode 数 |
|---|---|---|---:|---:|
| E07 | Editor | `edit` 无 linting | 15.0% | 300 |
| E08 | Editor | 无 `edit` | 10.3% | 300 |
| E09 | Search | iterative search | 12.0% | 300 |
| E10 | Search | no search | 15.7% | 300 |
| E11 | File Viewer | 30 行窗口 | 14.3% | 300 |
| E12 | File Viewer | full file | 12.7% | 300 |
| E13 | Context | full history | 15.0% | 300 |
| E14 | Context | 无演示 | 16.3% | 300 |

所有消融必须提供相对默认配置的结构化 diff。每次只改变论文指定因素；模型、数据顺序、预算、temperature、top-p、评测器和重试规则保持不变。

### 3.3 超参数、重复运行与附加基准

| ID | 实验 | 计算方式 | episode 数 | 目标工件 |
|---|---|---:|---:|---|
| E15 | 超参数搜索 | 2 模型 × 2 temperature × 2 窗口 × 2 history × 37 dev × 5 samples | 2,960 | 附录超参数表 16 行 |
| E16 | Lite 六次重复 | GPT-4 默认配置 × 300 × 6 | 1,800 | 六次 resolve rate、均值/标准差、pass@1…6 |
| E17 | HumanEvalFix | GPT-4 默认 ACI × 164 × 3 种语言 | 492 | Python/JS/第三语言 pass@1、turn 分布 |
| E18 | 失败模式标注 | 248 个未解决 Lite 轨迹；其中 15 个手工验证 | 248 次分类请求 | 类别饼图、87% 一致率 |

若 E03 的 300 个 episode 被证明就是 E16 六次运行之一，则 E16 只新增 1,500 个 episode。按这一最小复用规则，论文对齐的代理推理总量至少为 **13,140 个 episode**；若不能证明运行复用关系，则为 13,440 个。RAG 若无法获得官方预测而必须重新生成，另增加最多 4,588 个非交互推理实例。

### 3.4 复用上述运行的分析工件

以下项目不新增代理推理，但必须从冻结轨迹、预测和判分结果重新计算：

| ID | 分析与工件 | 主要输入 |
|---|---|---|
| A01 | 按仓库表现表 | Full/Lite 判分、RAG 判分 |
| A02 | 按 issue 年份表现表 | 实例元数据与判分 |
| A03 | 四类退出条件表 | GPT-4/Claude、Full/Lite 轨迹 |
| A04 | resolved-by-turn 与提交步数/成本图 | Full 两模型轨迹 |
| A05 | 每 turn 动作频率与密度图 | GPT-4 Full 轨迹 |
| A06 | 常见三元动作及分阶段类别 | GPT-4 Full 轨迹 |
| A07 | 1/2/3/4-gram 动作转移图 | GPT-4 Full 轨迹 |
| A08 | 失败 edit 次数、恢复概率 | GPT-4 Full 轨迹 |
| A09 | patch 增删行、hunk、文件数统计 | 模型 patch 与 gold patch |
| A10 | 文件定位 F1 | 模型 patch、RAG 检索文件、gold patch |
| A11 | 失败模式类别饼图 | E18 标签 |
| A12 | HumanEvalFix resolved turn 分布 | E17 轨迹与判分 |
| A13 | 四个定性案例 | 论文指定轨迹、模型 patch、gold patch |
| A14 | prompt、ACI 命令和界面示意 | 论文快照配置与命令实现 |

## 4. 当前证据与纠偏

### 4.1 已完成

- 论文、源码和 SWE-agent 时间对齐快照已下载并固定；
- 官方 `SWE-bench/experiments` 当前版本与论文前重置历史均已固定；论文前提交 `a5d52722965c791c0c04d18135f906b44f716d39` 提供主 GPT-4、Claude 3 Opus 和 RAG 的预测、评测日志、轨迹与结果；
- 官方 HumanEvalFix 提交 `bbd565c9035f873ba5ee2c1bd1d65c5ee2d85d1a` 已复算三种语言结果和 resolved-turn 分布，并确认第三种语言为 Java；
- 主 SWE-bench 工件复算发现论文主表的 Claude 数字与官方结果及论文退出条件表不一致：Lite 主表隐含 39/300，工件与退出表均为 35/300；Full 主表隐含 240/2294，工件与退出表均为 241/2294；
- HumanEvalFix 论文数字已精确追溯到 notebook 的 `*.log` 分母：testbed 环境日志被计为失败，Python 又缺少两个评测日志；修正后的固定 164 分母结果为 Python 87.2%、JS 90.2%、Java 88.4%；
- A01–A10 的全部公开实例级分析输入已经重放：A01/A02/A06/A09/A10 精确，A05/A07 完成公开轨迹重放，A03/A04/A08 的公开轨迹缺口或论文内部不一致已量化并保留；
- A13 的四个论文定性案例达到 action 72/72、gold patch 4/4、结果标签 4/4 精确核验；A14 遍历全部 2,568 条公开 GPT-4 轨迹，恢复两个 system prompt 变体、统一 demonstration/instance template、10 个命令实现和 21 个论文界面资产；
- 本地 WSL2、Docker、Python 3.9 隔离运行与实例级恢复已经跑通；
- `gpt-5.6-terra` 在论文快照默认 ACI 上完成冻结 dev20：4/20 完全解决，20.00%；
- dev20 保存了 397 次持久化 API 调用、5,496,947 input tokens、70,405 output tokens及逐实例判分；
- 多个旧依赖漂移和评测异常已通过最小、实例作用域兼容层记录和修复。

这些结果属于 **现代模型开发集复验**，不属于 E01–E18 的严格原模型复现。

### 4.2 自定义组合消融纠偏

`conf/weak_aci_no_search_editor.yaml` 同时移除了摘要搜索与 linting editor。该变体不是论文的 Shell-only，也不是论文表中的任何一个单因素消融。已经完成的两个 Marshmallow 正式调用保留为探索性证据，但从论文主比较中排除；正在环境创建阶段的下一实例因重新规划被终止，API 调用为 0。

后续只建立以下独立配置：no-lint editor、no-edit、iterative-search、no-search、window-30、full-file、full-history、no-demo，以及经原始证据恢复的 Shell-only。未获得精确配置前不批量运行。

## 5. 外部门槛与真实性约束

所有门槛都在 `conf/full_paper_matrix.yaml` 中保存机器状态。门槛变化必须有时间、探测证据和 Git 提交；口头推测不能解除门槛。

### G1：原模型可得性

当前 OpenAI 兼容目录不包含 `gpt-4-1106-preview` 或 `gpt-4o-2024-05-13`。新增 Anthropic Messages 端点可正常调用当前 Claude 模型，但对 `claude-3-opus-20240229` 的直接请求返回 `model_not_found`；其目录只提供 Claude Opus 4.6/4.7/4.8 和 Sonnet 4.6。因此现阶段仍不能启动 E01–E18 的严格原模型重跑，也不能把现代模型替代结果标为 exact。

解除方式：

1. 获得能返回上述精确模型 ID 的有效 endpoint 与凭据；或
2. 获得作者公开的全量原始轨迹、预测、判分日志和分析数据，先完成工件复算；严格重跑仍单独保留为未完成，不能静默替代。

### G2：作者工件可得性

论文的主要原始工件已从两个官方仓库恢复。`SWE-bench/experiments` 在 2024 年 10 月重置历史并把大文件迁移到公开 S3；重置前官方提交仍可按 SHA 获取，其中 `a5d5272` 覆盖 GPT-4、Claude 3 Opus 和 RAG 主运行。`SWE-bench/humanevalfix-results` 提供评测日志、492 条轨迹、预测和原 notebook。当前尚未恢复 Shell-only、八项 ACI 消融、37-dev 五次采样、六次 pass@k 和失败分类的全部原始运行工件，因此本门槛保持部分完成。所有已恢复来源、revision、Git blob ID 和派生 SHA-256 均登记在 `docs/artifact_provenance.md` 与 `data/manifests/`。

### G3：预算与价格

论文原始协议为每实例 4 美元上限。按最小 13,140 个 episode 计算，理论预算上界为 52,560 美元。用当前 dev20 的实测均值外推约为：

- 260,829 次模型调用；
- 3,611,494,179 input tokens；
- 46,256,085 output tokens；
- 单并发、每实例 10 分钟时约 91.2 天墙钟时间。

该外推只用于资源决策，不代表原模型实际费用。当前中转服务价格未知，因此批量扩大前必须记录输入/输出单价、缓存计价、失败请求计价和项目总硬预算；未知价格不视为零成本。

### G4：评测与存储

正式 Lite/Full 前必须满足：

- 至少 120 GB 可用磁盘，或以测量数据证明顺序清理方案能保持安全余量；
- evaluator 对冻结公开预测的 resolved 数与已知结果一致；
- 每个支持仓库至少完成一个未修改 gold patch 的环境验证；
- 环境失败、模型失败和真实未解决严格分离；
- 容器、testbed、patch 应用顺序和测试集合均有哈希或完整日志。

GPU 不是 API 代理实验的必要条件。本地 CPU、内存、磁盘和 Docker 足以执行当前阶段；服务器只在需要更多并发、磁盘或本地模型时使用。若使用服务器，项目目录固定为 `/public/home/mty/GeYugong/05_sweagent_repro_ser/`，并单独初始化 Git 仓库、按同一协议提交。

2026-07-17 的本地实测为 D 盘 651.64 GB、空闲 64.07 GB，低于正式 300/2,294 实例批量运行的 120 GB 门槛。单仓库、执行后清理的 evaluator gold 重放仍可继续，但不得据此解除批量门槛。WSL 报告的稀疏虚拟磁盘容量不作为宿主机真实可用空间。

### G5：费用授权

API 凭据只证明端点可认证，不代表已授权产生任意费用。论文对齐代理运行最少 13,140 个 episode，按论文每实例 4 美元上限计算理论上界为 52,560 美元。在获得明确总预算上限、单价、失败请求计费规则和停止阈值之前，仅允许不产生 API 费用的工件复算、环境验证，以及已明确授权的小额 smoke；禁止启动 E01–E18 的批量调用。

### G6：服务器运行能力

服务器目录固定为 `/public/home/mty/GeYugong/05_sweagent_repro_ser/`。当前服务器未确认可用容器运行时，因此只可作为受控存储或 API 生成节点，不承担 SWE-bench 正式判分。解除门槛需要在该目录内完成独立 Git 初始化、容器 smoke、磁盘测量和一个 gold patch 判分；不得修改共享 conda 环境或其他项目。

## 5.1 论文产物覆盖契约

`conf/paper_output_inventory.yaml` 逐项登记正文和附录中的经验表、经验图、动作分析、提示词与界面资产、四个定性案例和概念图。每项至少包含论文标签、源码成员、证据类型、当前状态、依赖和验收标准。

覆盖率检查遵循以下规则：

- 论文源码中登记的产物不得只用一个笼统的 `A_TRAJECTORY` 状态代替；
- `SOURCE_RECONSTRUCTED` 只表示发布资产可恢复；存在原始预测或轨迹时还必须完成 `ARTIFACT_RECOMPUTED`；
- 缺失逐实例输入的聚合图必须标记 `RAW_INPUT_BLOCKED`，并保留源码聚合重建结果；
- 表图底层数据、生成脚本和渲染结果三者齐全后才可标记为可重放；
- 定性案例必须同时核对 action 序列、模型 patch、gold patch 和最终判分；
- 最终审计要求清单 ID 唯一、源码成员存在、所有派生路径存在，并且 E01–E18 与门槛引用闭合。

## 6. 执行顺序与阶段退出条件

### P0：目标与证据冻结

1. 把论文的每张经验表、图和数字登记到 `conf/paper_output_inventory.yaml`，并由 `conf/full_paper_matrix.yaml` 引用；
2. 记录论文源码路径、目标数值、输入数据和计算公式；
3. 给所有现有运行重新标注 exact/artifact/modern/exploratory；
4. 生成覆盖率审计，任何未登记工件都使 P0 失败。

退出条件：矩阵可机器校验，当前结果没有错误归类。

当前状态（2026-07-17）：`COMPLETE_REVISION_2`。E01–E18、13,140/13,440 episode 口径、全部论文产物、三类完成结论和六类外部门槛均已登记，并由 `scripts/validate_full_reproduction_plan.py` 校验。

### P1：原始资产追溯与协议恢复

1. 定位作者全量 trajectories、predictions、evaluation traces、analysis notebooks；
2. 恢复 Shell-only 和八个单因素消融的精确配置；
3. 恢复 37 个 dev 实例清单、五次 sample 的种子/调用定义；
4. 确认 HumanEvalFix 第三种语言和数据 revision；
5. 确认 RAG 预测来源和 Lite 是否由 Full 预测切片；
6. 对所有下载工件建立 SHA-256 清单。

退出条件：每项都有官方来源，或明确标为 `BLOCKED_MISSING_OFFICIAL_ARTIFACT` 并保存检索证据。

当前状态（2026-07-16）：`COMPLETE_WITH_MISSING_OFFICIAL_BLOCKERS`。默认主运行与 HumanEvalFix 工件已恢复；全部官方 Git/PR、论文源码、分析目录和公开 S3 检索已经完成。Shell-only、八项消融原始运行、dev37 ID、pass@k 六次预测和失败标签未公开，均已在 `data/manifests/paper_protocol_recovery.json` 中登记，不再保持模糊的“仍在检索”状态。

### P2：评测器与分析器重放

1. 使用 gold patch、空 patch、已知失败 patch 做 evaluator 单元验证；
2. 使用作者预测重算 Full/Lite/HumanEvalFix 指标；
3. 编写只读取冻结工件的分析脚本，逐张生成表图；
4. 数字比对报告同时列出论文值、复算值、绝对差和原因。

退出条件：工件复算的所有可得表图精确一致；不可得项不伪造。

当前状态（2026-07-17）：`IN_PROGRESS_AVAILABLE_A01_A14_REPLAYED`。官方主预测已经在论文期 `SWE-bench@cfb20092`、Lite 数据 `81ad348` 和 Full 数据 `283547a` 上重放，八组十类别完整列表均与官方 `results.json` 相同；后续数据 revision 导致的三项 SymPy resolved 漂移也已定位。pytest 4.4 的一个官方 `RESOLVED_FULL` 和一个 applied-`RESOLVED_NO` prediction 已完成新容器重放，完整测试列表 `2/2` 与历史日志一致。gold、官方 no-apply、空字符串、null 和重复行边界输入再得到 `5/5` 精确匹配，P2 第 1 项已完成。

A01–A10 的全部公开实例级输入已由单一冻结脚本重放，得到 7 项精确/完整公开重放和 3 项明确缺口；13 个 CSV 与 4 份 PDF 可确定性再生。A11 的论文聚合图已从源码重建但逐实例标签缺失，A12 已由 HumanEvalFix 官方轨迹重建。A13 的 72 个 action、4 个 gold patch 与结果标签已精确核验；A14 的 2,568 条运行 prompt、10 个命令实现与界面资产已完成审计，并明确了混合工作树边界。12 仓库 gold 覆盖已经完成：11 个仓库得到全部 reference outcome（其中 pytest 复用已冻结环境），Requests 得到 140/141 个直接 outcome，唯一公共跨站重定向测试因外网漂移失败并由本地双主机语义验证确认 Authorization 正确剥离。机器清单分别记录 11 个 full-reference 与 1 个 semantic，不把 Requests 改写为 `RESOLVED_FULL`。全量 300/2,294 实例容器重评仍作为更高成本验证保留，A11 原始逐实例标签继续登记为公开工件 blocker。

### P3：小样本严格重跑预检

1. 对每个原模型和每类数据执行 1 个不计正式结果的 smoke；
2. 验证返回模型 ID、价格、token、动作格式和 4 美元预算行为；
3. 在冻结 20 个实例上执行默认配置与单因素配置预检；
4. 禁止根据正式 test 结果调 prompt 或选超参数。

退出条件：模型与协议精确对齐，环境无系统性无效判分，成本预测获确认。

### P4：开发集超参数搜索

执行 E15 的 2,960 个 episode，完整保存五次 sample 的实例级结果。使用论文相同聚合方式生成 16 行表，并在看到 Lite/Full 新结果前锁定最终配置。

### P5：Lite 主结果、消融与重复运行

依次执行 E03–E14 和 E16。默认配置先完成一次，之后八个单因素消融与 Shell-only；六次重复采用预注册的独立运行标识。完成配对 McNemar、bootstrap 95% CI、运行间标准差与 pass@k。

### P6：Full 与 HumanEvalFix

执行 E01、E02、E17。Full 默认单并发起步，环境缓存稳定后再按资源审计结果提高并发。HumanEvalFix 使用语言特定演示，不与 SWE-bench 演示混用。

### P7：失败分类与全部分析

执行 E18 和 A01–A14。分析脚本只能使用冻结输入清单；图表文件同时保存原始数据 CSV/JSON、绘图参数和环境锁文件。

### P8：现代模型复验

在 exact 结果之外建立独立命名空间。优先完成论文八个单因素消融的 dev20 配对实验，再经预注册选择是否扩大到 Lite。现代实验不得改变论文严格重跑的完成状态。

### P9：最终审计与交付

1. 运行覆盖率检查，所有必需矩阵项必须为 `COMPLETE`；
2. 运行从干净 clone 到表图生成的自动化重放；
3. 审计 Git、submodule、数据哈希、配置哈希、容器 digest 和日志索引；
4. 输出方法、结果、偏差、失败案例、成本、时延和局限性完整报告；
5. 仅在严格满足第 1 节定义后更新为 100%。

## 7. 运行与重试规则

- 正式 run ID 必须包含证据类型、系统、精确模型、数据、变体和 repetition；
- 模型请求成功后产生的轨迹不得因结果不佳而重跑；
- 仅允许对零模型响应的网络错误、环境构建失败或判分基础设施失败重试；
- 每次重试保留原始尝试并使用后缀 `A/B/C`，同时记录是否产生 API 费用；
- evaluator 兼容修复必须是实例或仓库作用域，说明为何不改变目标测试语义；
- 空预测、格式退出、预算退出均是有效模型结果，进入分母；
- 不完整轨迹、缺失配置哈希或缺失判分日志的运行不得进入主表；
- 正式批次启动前、批次结束后和任何协议修正后分别提交 Git；
- commit message 使用英文 conventional commit 格式，实验正文和报告使用独立研究叙述。

## 8. 统计与验收

### 工件复算

- 整数计数必须完全一致；
- 论文百分比按相同分母和舍入规则后必须一致；
- 表图的底层 CSV/JSON 必须由脚本生成，禁止手工填数；
- 图形允许字体或渲染器导致像素差异，但坐标数据、分组、聚合和标签必须一致。

### 严格重跑

- 每个配置报告实例级 paired outcome；
- 成功率报告 Wilson 或 bootstrap 95% CI；
- 同一实例上的系统比较使用 McNemar 检验；
- 连续成本、token、步数和时延报告配对差与 bootstrap CI；
- 论文点估计是否落入重跑区间只作为一致性证据，不通过选择性重试追求数字吻合。

### 现代复验

- 预先写明方向性假设，例如 linting editor 是否优于无 linting editor；
- 同时报告绝对成功率、配对胜负、格式失败、无 patch、patch 冲突和环境无效数；
- 不因现代模型与旧解析器不兼容而改写论文基线；解析器兼容性只能作为单独改进组。

## 9. 进度口径

整体进度按矩阵中必需交付项加权，而不是按已消耗时间或 API 调用数估计：

- P0 规划、版本与矩阵：5%；
- P1 原始资产与精确协议：10%；
- P2 evaluator/analysis 工件重放：15%；
- P3 严格重跑预检：5%；
- P4 超参数搜索：15%；
- P5 Lite、消融、pass@k：20%；
- P6 Full 与 HumanEvalFix：20%；
- P7 全部分析和失败分类：7%；
- P8 现代复验：可选扩展，不替代上述 100%；
- P9 最终审计与报告：3%。

某阶段只有在退出条件全部满足后才计满；被外部门槛阻塞的阶段保持未完成。当前 dev20 和组合消融属于 P8 的前置探索，不提前增加 P3–P7 的严格复现进度。

进度报告必须并列给出两组数字：`public_artifact_progress` 和 `exact_rerun_progress`。不得把已经从论文源码读取出的聚合数字同时计入工件复算和严格重跑，也不得用受阻项的“已定位原因”冒充实验已完成。
