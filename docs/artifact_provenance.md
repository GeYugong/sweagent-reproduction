# 官方实验工件追溯与复算记录

## 1. 审计目标

本记录固定论文主实验与 HumanEvalFix 的官方来源、历史 revision、复算算法和已发现的报告不一致。所有数字均由脚本读取官方 Git blob 重新计算，不从论文 PDF 手工抄入派生结果。

本阶段属于工件复算，不等同于使用论文闭源模型重新推理。严格原模型运行仍由 `conf/full_paper_matrix.yaml` 中的 exact 门槛单独管理。

## 2. 官方来源与冻结版本

| 工件 | 官方来源 | 冻结 revision | 用途 |
|---|---|---|---|
| SWE-bench 主运行 | `https://github.com/SWE-bench/experiments` | 当前树 `2f15350cd32becc4569e0d826361048555b605c0` | 当前元数据、公开 S3 指针、仓库结构 |
| SWE-bench 论文期历史 | 同上 | `a5d52722965c791c0c04d18135f906b44f716d39` | GPT-4、Claude 3 Opus、RAG 的预测、日志、轨迹和 `results.json` |
| HumanEvalFix | `https://github.com/SWE-bench/humanevalfix-results` | `bbd565c9035f873ba5ee2c1bd1d65c5ee2d85d1a` | 三种语言的预测、评测日志、492 条轨迹和原 notebook |

`SWE-bench/experiments` 在 2024 年 10 月重置主分支历史并把大型工件迁移到 `swe-bench-submissions` S3 bucket。论文期历史仍可从官方仓库按对象 SHA 获取。提交 `a5d5272` 由论文作者 John Yang 于 2024-05-14 提交，主题为 `Add SWE-agent Claude 3 Opus results`，位于论文首次公开之前，并包含主表所需的八组 SWE-agent/RAG Full/Lite 工件。

历史树包含 Windows 不宜直接检出的超长日志路径。复算脚本通过 `git show <revision>:<path>` 和 `git cat-file --batch` 读取 blob，不切换子模块工作树，从而保留当前官方主分支并避免长路径失败。

## 3. SWE-bench 主表复算

运行命令：

```powershell
git -C code/SWE-bench-experiments fetch origin a5d52722965c791c0c04d18135f906b44f716d39
python scripts/reproduce_official_swebench_results.py
```

复算结果：

| Split | 系统 | 模型 | 论文主表 | 官方工件 | 论文退出条件表 | 判定 |
|---|---|---|---:|---:|---:|---|
| Lite | SWE-agent | GPT-4 Turbo | 54/300 = 18.00% | 54/300 = 18.00% | 54 | 一致 |
| Lite | SWE-agent | Claude 3 Opus | 39/300 = 13.00% | 35/300 = 11.67% | 35 | 主表与工件相差 4 |
| Lite | RAG | GPT-4 Turbo | 8/300 = 2.67% | 8/300 = 2.67% | - | 一致 |
| Lite | RAG | Claude 3 Opus | 13/300 = 4.33% | 13/300 = 4.33% | - | 一致 |
| Full | SWE-agent | GPT-4 Turbo | 286/2294 = 12.47% | 286/2294 = 12.47% | 286 | 一致 |
| Full | SWE-agent | Claude 3 Opus | 240/2294 = 10.46% | 241/2294 = 10.51% | 241 | 主表与工件相差 1 |
| Full | RAG | GPT-4 Turbo | 30/2294 = 1.31% | 30/2294 = 1.31% | - | 一致 |
| Full | RAG | Claude 3 Opus | 87/2294 = 3.79% | 87/2294 = 3.79% | - | 一致 |

Claude 差异不能解释为当前仓库重评造成的漂移：论文期提交中的 `results.json`、当前官方结果和论文附录退出条件表均给出 Lite 35、Full 241。只有论文主表给出 Lite 39、Full 240。因此两组数值均保留：论文主表值用于忠实报告，35/241 用于官方工件复算和后续轨迹分析。

### 3.1 工件覆盖与异常

| Split/run | 预测行/唯一实例 | 空 patch | 日志 | 轨迹 | 树大小 |
|---|---:|---:|---:|---:|---:|
| Lite SWE-agent GPT-4 | 302/299 | 18 | 284 | 300 | 75.83 MiB |
| Lite SWE-agent Claude | 300/300 | 29 | 333 | 300 | 74.22 MiB |
| Lite RAG GPT-4 | 300/300 | 0 | 300 | 0 | 15.45 MiB |
| Lite RAG Claude | 300/300 | 0 | 300 | 0 | 11.36 MiB |
| Full SWE-agent GPT-4 | 2283/2266 | 154 | 2243 | 2268 | 643.83 MiB |
| Full SWE-agent Claude | 2576/2266 | 233 | 2178 | 2013 | 533.84 MiB |
| Full RAG GPT-4 | 2294/2294 | 0 | 2420 | 0 | 183.90 MiB |
| Full RAG Claude | 2287/2287 | 0 | 2413 | 0 | 209.32 MiB |

原始预测存在重复行、缺失实例和多次评测日志。源码与完整列表重放确认：论文期 `get_model_report` 按 JSONL 行顺序处理，**不按实例 ID 去重**；重复行会复用同名日志并重复追加类别。因此不能把 JSONL 行数、唯一实例数、类别列表长度或数据集大小互相替代。完整语义与逐组证据见 `docs/evaluator_replay.md`。

机器清单：

- `data/manifests/official_swebench_artifacts.json`：revision、提交元数据、结果类别计数、文件 SHA-256、树覆盖；
- `data/derived/official_swebench_main_results.csv`：主表逐行复算与差值。

### 3.2 历史 evaluator 与数据 revision 重放

官方报告不是只由预测和日志决定，还依赖当时的 `SWE-bench` 聚合源码与测试参考。精确输入已恢复为：

- evaluator：`SWE-bench/SWE-bench@cfb20092bbbee9683176177b2f59b85f522e7f27`；
- Lite 数据：`princeton-nlp/SWE-bench_Lite@81ad348adcaf3368691f4db2907f8fc97a8f7526`；
- Full 数据：`princeton-nlp/SWE-bench@283547aced6224d4adbe55c678b4c9c43fe7d501`。

`scripts/replay_official_evaluator.py` 从旧 experiments 提交按需流式物化日志，在上述 revision 上重算十个类别的完整列表。八组运行均与官方 `results.json` 完全相同。若将数据替换为固定的 2025-03-03 revision，则只有 6/8 完整一致：Claude Full 多判 2 个 resolved，RAG GPT-4 Full 多判 2 个 resolved，涉及三个 SymPy 实例。这一对照排除了预测或日志变化，证明数据 revision 是差异来源。

机器清单为 `data/manifests/official_evaluator_replay.json`。该结果验证的是历史日志聚合层；从 prediction patch 重新创建容器并执行测试的验证仍单独保留。

干净 clone 中当前主线不包含论文期历史，需要显式取回并固定旧提交：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_official_swebench_results.py `
  --fetch-missing
```

命令只从官方 `origin` 按固定 SHA 获取输入，并建立本地 `refs/paper/sweagent-artifacts`，防止历史对象被 Git 垃圾回收。

## 4. HumanEvalFix 复算

官方工件包含以下三个运行目录：

- Python：164 条轨迹，`install-1`；
- JavaScript：164 条轨迹，`install-0`；
- Java：164 条轨迹，`install-0`。

不存在 Go 运行。因此主表中的 Java 是实际第三种语言，附录数据说明中的 Go 是笔误。

### 4.1 论文 notebook 的分母问题

原 notebook 使用 `glob(..., "*.log")`，而不是只匹配 `*.eval.log`。每种语言目录还包含一个 `testbed_*.log` 环境日志，该文件没有 `>>>>> All Tests Passed` 标记，因而被计为一个失败样例。Python 发布目录另缺少实例 80 和 135 的评测日志，只保留 162 个实例评测日志。

| 语言 | 通过标记 | 实例评测日志 | testbed 日志 | notebook 分母 | 论文/notebook | 固定 164 分母 |
|---|---:|---:|---:|---:|---:|---:|
| Python | 143 | 162 | 1 | 163 | 87.73006% -> 87.7% | 87.19512% -> 87.2% |
| JavaScript | 148 | 164 | 1 | 165 | 89.69697% -> 89.7% | 90.24390% -> 90.2% |
| Java | 145 | 164 | 1 | 165 | 87.87879% -> 87.9% | 88.41463% -> 88.4% |

论文的 87.7/89.7/87.9 可以由原 notebook 算法精确复现，但不是固定 164 个任务上的标准 pass@1。后续报告并列给出原论文算法和修正算法，不选择性覆盖原数值。

### 4.2 resolved-turn 图

通过日志中的实例 ID与同 revision 下的轨迹文件关联，分别获得 143、148、145 条 resolved 轨迹。轮数统计如下：

| 语言 | 均值 | 中位数 | 最小 | 最大 |
|---|---:|---:|---:|---:|
| Python | 6.091 | 5 | 5 | 20 |
| JavaScript | 6.574 | 6 | 5 | 32 |
| Java | 7.393 | 6 | 4 | 27 |

绘图严格采用原 notebook 的语言顺序 JS/Java/Python、颜色和 `numpy.arange(0, 40, 2)` bins。PDF 使用固定元数据时间戳，两次生成 SHA-256 均为 `b96d4ee168b8b5ed1354227b84f69fe8da0eae68db2b457566affab21fd3d61a`。Poppler 以 160 DPI 渲染后完成视觉检查，标题、坐标、柱形和边界均无裁切或重叠。

复算命令：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_humanevalfix.py `
  --figure output/pdf/humanevalfix_turns_artifact.pdf
```

派生工件：

- `data/manifests/official_humanevalfix_artifacts.json`；
- `data/derived/humanevalfix_summary.csv`；
- `data/derived/humanevalfix_instance_results.csv`；
- `data/derived/humanevalfix_histogram_bins.csv`；
- `output/pdf/humanevalfix_turns_artifact.pdf`。

## 5. Claude API 可用性审计

Anthropic Messages 端点完成最小协议验证：

- 模型目录：`claude-opus-4-6`、`claude-opus-4-7`、`claude-opus-4-8`、`claude-sonnet-4-6`；
- `claude-sonnet-4-6` 最小请求返回 HTTP 200、文本 `OK`、3 input tokens、1 output token；
- 论文模型 `claude-3-opus-20240229` 直接请求返回 HTTP 404 `model_not_found`，没有 token usage；
- endpoint 没有返回价格字段，批量运行前的价格门槛仍未解除。

凭据只保存在 Git 忽略的 `secrets/anthropic.env`，ACL 与现有密钥文件一致，仅当前 Windows 账户拥有 FullControl。任何受 Git 管理的日志、清单和提交均不包含密钥值。

## 6. 当前完成边界

已完成：

1. 主 GPT-4、Claude、RAG Full/Lite 官方结果复算；
2. 主运行预测、日志和轨迹覆盖审计；
3. HumanEvalFix 实际语言确认、论文数字复算、分母缺陷定位；
4. HumanEvalFix 492 个实例级结果、resolved-turn 数据与 PDF 图生成；
5. 精确 Claude 3 Opus 不可用性实测。

尚未完成：

1. Shell-only 与无演示 Shell-only 原始工件；
2. 八个 ACI 单因素消融工件；
3. 37 个 dev 实例与 16x5 超参数运行工件；
4. 六次 Lite 重复和 pass@k 的实例级工件；
5. 失败分类请求、标签和人工验证集；
6. 对官方主预测执行冻结 evaluator 的容器级重新执行；历史日志聚合层已实现 8/8 完整列表一致；
7. 论文精确 GPT-4、Claude 3 Opus、GPT-4o 模型重新推理。

这些未完成项继续保留在全论文矩阵中，不能由本次工件复算自动标记为严格复现完成。

## 7. 论文源码聚合与协议负检索

对 SWE-agent 全部 822 个公开 PR head、论文期 309 个 PR head、SWE-bench experiments 的论文期 PR 元数据、公开 S3 前缀和 arXiv 源码包完成交叉审计。默认 ACI、FullHistory 以及 100/200 窗口参数实现可以定位；Shell-only、全文 viewer、无 lint editor、迭代搜索、dev37 实例 ID、六次 pass@k 预测和失败模式逐实例标签没有公开工件。

arXiv 源码仍足以恢复并自动校验四组最终聚合结果：12 个 ACI 表行、16 个超参设置、6 个 pass@k 点和 248 个失败实例的类别计数。对应 CSV、两张确定性 PDF 和负检索边界由 `scripts/reproduce_paper_source_aggregates.py` 生成。

完整方法、证据范围和每项 blocker 见 `docs/protocol_recovery_audit.md`；机器清单见 `data/manifests/paper_protocol_recovery.json` 与 `data/manifests/paper_source_aggregate_manifest.json`。
