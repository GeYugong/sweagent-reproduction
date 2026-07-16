# 论文期协议与缺失工件审计

## 1. 审计目的

本审计确定论文中 Shell-only、八个 ACI 单因素消融、dev37 超参数搜索、六次 pass@k 和失败模式分类是否存在可公开取得的原始配置、预测、轨迹、判分日志或实例级标签。审计结论用于划定“可从作者工件复算”“只能从论文源码恢复聚合值”和“必须重新推理但精确协议缺失”三类边界。

审计只使用作者或官方组织控制的来源作为主要证据：

- arXiv `2405.15793v3` 源码包；
- `SWE-agent/SWE-agent` 主历史、公开分支与全部 PR head；
- `SWE-bench/experiments` 当前历史、论文期历史提交、公开 PR 元数据与公共 S3 bucket；
- `SWE-bench/humanevalfix-results` 固定提交。

论文源码包 SHA-256 为 `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab`。机器审计结论保存在 `data/manifests/paper_protocol_recovery.json`。

## 2. 检索范围

### 2.1 SWE-agent 代码与 PR 历史

冻结代码为 `658eb2842e8a8b00069b301338bc342b70538f7a`。审计额外抓取官方仓库全部 822 个 PR head，其中论文期与紧随论文期的 PR head 共 309 个（编号不高于 621）。路径检索覆盖 `config`、`trajectories`、`evaluation`、`analysis` 和 `results`，内容检索覆盖：

- `WINDOW: 30` 与 window30；
- Shell-only 与 InterCode；
- iterative search、`next()` 和 `prev()`；
- no lint、no edit、no search；
- dev37、pass@k 与失败模式类别名。

公开历史中可确认：

- 初始提交 `5b143857` 已包含 100 行窗口与 FullHistory 配置；
- `08e66863` 加入 Last5Observations 配置并把默认历史切换为 Last-5；
- 冻结提交的非 cursor viewer 使用 `WINDOW: 100`；
- cursor viewer 配置虽然文件名含 `window100`，内容实际为 `WINDOW: 200`；
- 公开命令文件只有 defaults、cursor defaults、linting editor 和 summarized search；
- 未发现 30 行专用配置、全文 viewer、无 lint editor 或 next/prev 式迭代搜索实现。

因此，默认 ACI 和 FullHistory 配置可以直接恢复，100/200 窗口与 Last-5/Full 参数实现可以定位；但论文 16 个超参单元格与具体运行目录的映射没有公开。30 行、无搜索、无编辑和无演示可以按配置架构推导，却没有论文实际运行配置可校验。全文 viewer、无 lint editor、迭代搜索和 Shell-only 缺少官方精确实现。

### 2.2 SWE-bench experiments 历史与 S3

论文主工件提交为 `a5d52722965c791c0c04d18135f906b44f716d39`，提交说明为 `Add SWE-agent Claude 3 Opus results`。该提交已固定为本地引用 `refs/paper/sweagent-artifacts`，避免再次成为可被 Git 清理的悬空对象。

官方仓库共有 370 个 PR head；2024-07-01 以前共有 24 个 PR，全部是第三方榜单提交或后续 GPT-4o 结果，没有论文八项消融、dev37、pass@k 或失败标签资产。公共 bucket `s3://swe-bench-submissions` 在论文期只公开以下 20240402 运行族：

- Lite/Test 的 SWE-agent GPT-4 Turbo；
- Lite/Test 的 SWE-agent Claude 3 Opus；
- Lite/Test 的 RAG GPT-4 Turbo；
- Lite/Test 的 RAG Claude 3 Opus。

bucket 中没有以 ablation、sweep、pass@k、shell-only 或 failure-label 命名的论文期前缀。当前 `analysis/pre_v2/query_lm/outputs` 只有问题是否包含复现代码的三份输出，不是论文失败模式分类结果。

## 3. 恢复结论

| 项目 | 协议/配置 | 原始运行工件 | 聚合结果 | 结论 |
|---|---|---|---|---|
| 默认 ACI | 已恢复 | 主 Full/Lite 已恢复 | 已复算 | 工件证据可用 |
| Full history | 配置已恢复 | 未找到 | 15.0% | 仅源码聚合 |
| 200 行窗口 | 参数实现已恢复 | 未找到 | 超参表可读 | 缺运行映射 |
| 无演示 | 可从 schema 推导 | 未找到 | 16.3% | 非官方精确配置 |
| 无搜索 | 可从命令列表推导 | 未找到 | 15.7% | 非官方精确配置 |
| 无编辑 | 可从命令列表推导 | 未找到 | 10.3% | 非官方精确配置 |
| 30 行窗口 | 参数可推导 | 未找到 | 14.3% | 非官方精确配置 |
| 全文 viewer | 未恢复 | 未找到 | 12.7% | 官方实现缺失 |
| 无 lint editor | 未恢复 | 未找到 | 15.0% | 官方实现缺失 |
| Iterative search | 未恢复 | 未找到 | 12.0% | 官方实现缺失 |
| Shell-only | 仅有 InterCode-Bash 设计描述 | 未找到 | 11.00%/7.33% | 官方实现缺失 |
| dev37 sweep | 16 个设置可读，37 个 ID 缺失 | 未找到 | 16 行均值已恢复 | 无法做实例级复算 |
| 六次 pass@k | 聚合公式和六次比例可读 | 未找到 | 6 个 pass@k 点已恢复 | 无法验证实例并集 |
| 失败模式 | 9 类 schema 已恢复 | 248 标签与 15 个验证样本缺失 | 8 个非零切片已恢复 | 无法复算 87% 一致率 |

P1 的退出条件已经满足：每个目标要么具有官方来源，要么被明确登记为 `BLOCKED_MISSING_OFFICIAL_*`，并保留负检索证据。P1 完成不代表整篇论文已复现；它意味着后续不会把推导配置误称为作者精确配置，也不会把论文聚合值误称为原始工件复算。

## 4. 论文源码聚合复现

`scripts/reproduce_paper_source_aggregates.py` 直接读取 arXiv tar 包并生成：

- `data/derived/paper_aci_ablation_results.csv`：12 个表行，其中 8 个非默认消融；
- `data/derived/paper_hyperparameter_sweep.csv`：2 个模型、16 个设置；
- `data/derived/paper_pass_at_k.csv`：六次单跑比例、均值、标准差与 pass@1..6；
- `data/derived/paper_failure_mode_counts.csv`：9 类 schema、8 个非零类别与 248 个整数计数；
- `output/pdf/pass_at_k_source_aggregate.pdf`；
- `output/pdf/failure_modes_source_aggregate.pdf`。

失败模式向量图给出 39.9、12.1、23.4、12.9、2.0、2.4、4.8 和 2.4 八个比例。以论文明确的 248 为分母，唯一一致的整数计数分别为 99、30、58、32、5、6、12 和 6，总和为 248。附录定义第九类 Other，但图中八个非零切片已经覆盖全部 248 个实例，因此 Other 记为 0；该值是受总数约束的推断，不是逐实例标签复算。

复跑命令：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_paper_source_aggregates.py `
  --pdftotext /mnt/d/texlive/2026/bin/windows/pdftotext.exe
```

两张 PDF 使用固定元数据时间。连续两次生成哈希一致：

- pass@k：`846dc422622c3f99a5456cbaa4593273d367557e661d87e958600c6bb8fc50a0`；
- failure modes：`3470699737b87ef5d1206582852385f1f61f70b61b7273c71fbb02adb9a9ab13`。

Poppler 以 160 DPI 渲染后完成视觉检查。两张图均为单页 PDF，无加密；坐标、六个 pass@k 点、八个非零扇区、比例与图例均无裁切或重叠。

## 5. 后续实验边界

严格重跑仍被三个独立条件阻塞：论文模型不可用、部分官方精确实现缺失、批量预算和磁盘门槛未满足。现代 Claude 或当前 GPT 模型只能进入 `modern` 证据层；推导出的 no-search/no-edit 等配置必须标为 reconstructed，不能替代论文 exact 结果。

历史 evaluator 聚合回放已经完成：固定 `SWE-bench@cfb20092`、Lite 数据 `81ad348` 和 Full 数据 `283547a` 后，八组官方报告的完整类别列表均与 `results.json` 相同。重放同时确认历史实现不对预测行去重，并定位到后续数据 revision 会使两组 Full 结果各多判两个 resolved。完整证据见 `docs/evaluator_replay.md` 与 `data/manifests/official_evaluator_replay.json`。

代表实例的容器级重新评测已先完成两个核心分支：pytest 4.4 的官方 resolved 与 applied-unresolved prediction 均成功重建环境、应用两份补丁并执行测试，完整测试结果为 `2/2` 与历史日志相同。下一步继续覆盖 gold、patch apply failure、空 patch 和重复预测分支。只有边界分支与聚合层同时通过后，`G_EVALUATOR_REPLAY` 才能关闭；该门槛不解除原模型、精确消融配置、预算和磁盘阻塞。
