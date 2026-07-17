# 官方实例级分析 A01–A10 复算记录

## 1. 目标与证据边界

本实验从论文期公开预测、轨迹、结果列表、冻结数据集和 arXiv 源码重新计算 A01–A10。实验不发起代理推理，也不使用论文表格作为派生数据输入；论文源码中的表格和图形数值只用于独立验收。

本实验属于 `artifact reproduction`。其中 7 项达到精确匹配或完整公开轨迹重放，3 项因公开轨迹缺失或论文内部算术不一致保留为部分完成。该结果不能替代论文模型的严格重跑。

## 2. 冻结输入

| 输入 | revision / SHA-256 | 用途 |
|---|---|---|
| arXiv 源码 | `2405.15793v3` / `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab` | 独立目标值、表格和图形源码 |
| SWE-bench experiments | `a5d52722965c791c0c04d18135f906b44f716d39` | 论文期预测、结果、日志、轨迹和分析源码 |
| SWE-bench Lite | `81ad348adcaf3368691f4db2907f8fc97a8f7526` / `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1` | Lite 元数据与 gold patch |
| SWE-bench Full | `283547aced6224d4adbe55c678b4c9c43fe7d501` / `831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020` | Full 元数据与 gold patch |

四棵公开轨迹树的覆盖量为：GPT-4 Full 2,268、Claude 3 Opus Full 2,013、GPT-4 Lite 300、Claude 3 Opus Lite 300。Full 数据集有 2,294 个实例，因此公开轨迹覆盖量不能直接视为完整数据集分母。

原论文分析源码的 Git blob 也写入机器清单：

- `analysis/resolved_by_repo.py`：`13e9c2e9f035de8f7b5e00ac8a1ae9e72a7f6d6f`；
- `analysis/resolved_by_time.py`：`8731a0ff316e6d5cef7d3bd3eccfd81af54b2430`；
- `analysis/stats_patch.py`：`e5350c963a8d6ffdb8e3cca7d6fd9718f73153b8`；
- `analysis/calc_localization_f1.py`：`6f355a70041630f031d5da4f4e771d19581f363f`。

## 3. 执行方法

运行环境为本地 WSL2、Python 3.11.15、NumPy 1.26.4、Matplotlib 3.8.4、PyArrow 21.0.0 和 unidiff 0.7.5。未使用远程服务器、GPU 或模型 API。

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_official_instance_analyses.py
```

脚本直接通过 Git object database 读取固定 revision 中的 blob，避免检出 Windows 超长路径。执行顺序为：读取两份冻结 Parquet、载入四组公开轨迹与结果列表、复算 A01–A10、写出 13 个 CSV、生成 4 份 PDF，最后对所有输出记录字节数和 SHA-256。完整运行约 45 秒，API 调用为 0。

## 4. 验收结果

| ID | 复算范围 | 验收结果 | 状态 |
|---|---|---|---|
| A01 | 按仓库表现 | 60/60 个表格单元精确相等 | `COMPLETE_EXACT` |
| A02 | 按年份表现 | 25/25 个表格单元精确相等 | `COMPLETE_EXACT` |
| A03 | 退出条件 | unique 口径 31/32；prediction-line 加权口径 30/32 | `PARTIAL_CLAUDE_FULL_RESOLVED_TRAJECTORIES_MISSING` |
| A04 | turn、step、cost | 两组已发布 turn 汇总 2/2 精确；论文正文成本中位数存在轻微漂移 | `PARTIAL_TURN_TARGETS_EXACT_COST_PROSE_DRIFT` |
| A05 | 每 turn 动作频率与密度 | 286 条 resolved GPT-4 Full 轨迹完整重放 | `COMPLETE_PUBLIC_TRAJECTORY_REPLAY` |
| A06 | 常见三元动作 | top triples 10/10、手工分阶段计数 47/47 精确 | `COMPLETE_EXACT_PUBLISHED_COUNTS` |
| A07 | 1–4 gram 动作转移 | 源图概率抽查 10/10 精确；确认旧图右侧计数标签错位 | `COMPLETE_NUMERIC_SPOT_CHECKS_WITH_LEGACY_LABEL_BUG` |
| A08 | 失败 edit | 公开轨迹均值可复现，但分母、run 数和论文百分比不一致 | `PARTIAL_PUBLIC_TRAJECTORY_GAP_AND_PAPER_COUNT_INCONSISTENCY` |
| A09 | patch 统计 | 32/32 个统计单元精确相等 | `COMPLETE_EXACT` |
| A10 | 文件定位 F1 | 两个论文目标 2/2 精确，并恢复目标 split 为 Lite | `COMPLETE_EXACT` |

### 4.1 A03：Claude Full resolved 轨迹缺口

论文退出条件表给出 Claude Full resolved 的 `Submit=206`、`Exit Cost (Submit)=35`。公开轨迹按唯一实例计算只能得到 157 和 35；按预测 JSONL 行权重计算得到 181 和 39。官方结果含 241 个 resolved 条目、213 个唯一 resolved 实例，其中 21 个唯一 resolved 实例没有公开轨迹。因缺失轨迹无法恢复退出状态，不能通过去重或重复加权推导出论文的 206/35。

除该组外，GPT-4 Full/Lite、Claude Lite 以及 Claude Full 全体轨迹的退出条件均可复现。A03 因此只标记部分完成，不用插值或假定状态补齐。

### 4.2 A04：turn 精确、成本正文轻微漂移

GPT-4 Full resolved 的 turn 均值/中位数/75 分位数为 `14.71/12/18`，Claude Lite resolved 为 `12.71/13/15`，均与论文精确相同。公开 GPT-4 Full 轨迹得到 resolved 成本中位数 1.1796、unresolved 2.5355；论文正文写作 1.21 和 2.52。turn 目标已复现，但成本差异不能通过当前公开轨迹精确得到。

### 4.3 A05–A07：动作序列与旧图标签问题

A05 使用 286 条 resolved GPT-4 Full 轨迹逐 turn 重新统计动作频率、到达该 turn 的条件占比和动作内 turn 密度。公开轨迹第一动作除论文主要讨论的 `create/find_file/search_dir` 外，还含 1 次 `ls` 和 2 次 `open`，原始数据按实保留。

A06 的论文 top-10 三元动作计数全部相等；附录手工分类的 47 个“动作模式 × 起始 turn”计数也全部相等。类别名称来自论文 TeX 中的人工分组，不由脚本重新分类。

A07 的概率矩阵可以重算。旧论文图先按频率排序 heatmap 行，却继续按字典插入顺序写右侧样本数，导致右侧计数与行标签错位；概率单元不受影响。新图将计数与排序后的行绑定。另有一处正文/图形差异：`create | edit | python` 之后 `edit/find_file/search_dir` 的图中概率为 `.36/.28/.20`，正文写作 `.39/.31/.22`。复算图使用公开轨迹值并保留差异记录。

### 4.4 A08：失败 edit 的公开覆盖与论文算术问题

公开 GPT-4 Full 轨迹为 2,268 条，论文使用 2,294 为分母，相差 26 条。公开轨迹中 1,159 条至少发生一次失败 edit，论文写 1,185；两者差值同为 26，说明缺失轨迹直接影响该计数。resolved 轨迹中 113/286 至少发生一次失败 edit，实际为 39.5%，而论文正文写 31.5%。该百分比与论文自身计数不相容。

公开轨迹得到 2,009 个最大连续失败 run，其中最终成功 1,150 个、未成功 859 个；论文报告 810/555。尽管 run 数不同，平均长度分别为 2.2009 和 5.5879，可复现论文的 2.2 和 5.59。恢复曲线的 `n=0` 为 90.292%（论文 90.5%），`n=1` 为 57.242%（论文 57.2%）。这些差异按原值报告，不通过改变 run 定义追配论文数字。

### 4.5 A09–A10：隐藏聚合语义恢复

A09 的 32 个 patch 统计单元只有在以下历史语义下全部相等：保留 JSONL 中每条非空预测且不按实例去重；每条预测都重复关联一次 gold patch；每个指标独立保留小于等于自身 90 分位数的样本，再计算均值和中位数。Claude Full 的重复预测行是复现论文统计所必需的输入，不能预先去重。

A10 的论文目标实际来自 Lite，而不是 Full。GPT-4 SWE-agent 为 59.0508%，四舍五入后 59.05%；Claude 3 Opus RAG 为 45.4667%，四舍五入后 45.47%，两项均精确。

## 5. 派生工件

13 个 CSV 位于 `data/derived/official_*.csv`，覆盖仓库/年份表现、退出条件、逐实例轨迹、动作、转移、失败 edit、patch 统计与文件定位。机器清单为 `data/manifests/official_instance_analyses.json`。

四份最终 PDF 为：

- `output/pdf/official_trajectory_distributions_artifact.pdf`，2 页；
- `output/pdf/official_action_analyses_artifact.pdf`，4 页；
- `output/pdf/official_transition_probabilities_artifact.pdf`，4 页；
- `output/pdf/official_failed_edits_artifact.pdf`，2 页。

## 6. 可重复性与图形验收

同一冻结输入连续运行后，13 个 CSV 与 4 份 PDF 的 SHA-256 均保持不变。四份 PDF 共 12 页，全部未加密；文本提取可识别预期标题。Poppler 渲染后的逐页检查确认标题、坐标轴、图例、曲线、heatmap 单元与页边界均无裁切或重叠。

第一次图形检查发现动作图的共享图例过密，且动作内 turn 密度用堆叠面积容易被误读。最终版本把图例移到绘图区外并将密度改为折线图，第二次渲染检查通过。该修改只改变呈现，不改变 CSV 或统计值。

## 7. 完成边界

A01–A10 的全部可公开取得输入均已重放。A03、A04 和 A08 的剩余差异由公开轨迹缺失或论文内部不一致造成，已经给出可审计的最小缺口，不能标记为精确一致。A11 缺逐实例失败标签，论文聚合值已从源码重建且缺失标签已进入不可得终态。A13–A14 的定性案例和 prompt/ACI 资产已在独立审计中完成；论文原模型严格重跑及全量容器重评仍是不同证据层的未完成项。
