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

时间对齐冻结代码为 `658eb2842e8a8b00069b301338bc342b70538f7a`。审计额外抓取官方仓库全部 822 个 PR head，其中论文期与紧随论文期的 PR head 共 309 个（编号不高于 621）。路径检索覆盖 `config`、`trajectories`、`evaluation`、`analysis` 和 `results`，内容检索覆盖：

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

因此，默认 ACI 命令实现和 FullHistory 配置可以直接恢复，100/200 窗口与 Last-5/Full 参数实现可以定位；但论文 16 个超参单元格与具体运行目录的映射没有公开。主运行逐字 prompt 还需要从轨迹恢复，不能直接以 `658eb284` 的 `config/default.yaml` 代替。30 行、无搜索、无编辑和无演示可以按配置架构推导，却没有论文实际运行配置可校验。全文 viewer、无 lint editor、迭代搜索和 Shell-only 缺少官方精确实现。

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
| 默认 ACI | 命令实现及主运行精确 prompt 已恢复 | 主 Full/Lite 已恢复 | 已复算 | 混合工作树，工件证据可用 |
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

## 5. 公开实例级分析输入审计

论文期 experiments 提交公开了 A01–A10 所需的大部分主运行输入，但轨迹覆盖并不等于数据集覆盖。固定提交中 GPT-4 Full 有 2,268 条轨迹、Claude Full 有 2,013 条，均少于 Full 的 2,294 个实例；两组 Lite 各有 300 条。

从这些输入完成的独立复算表明：

- A01、A02、A06、A09、A10 的全部发布目标精确相等；
- A05 与 A07 的公开轨迹统计可以完整重放，A07 同时暴露旧图右侧计数标签与排序行错位；
- A03 只有 Claude Full resolved 退出条件不能恢复，官方 213 个唯一 resolved 实例中有 21 个没有公开轨迹；
- A04 的 turn 目标精确，但公开轨迹成本中位数与论文正文轻微漂移；
- A08 的 26 条 GPT-4 Full 轨迹缺口会同步造成“至少一次失败 edit”计数少 26，论文给出的 113/286=31.5% 还存在独立算术错误，实际为 39.5%。

因此，A03/A04/A08 的剩余差异属于 `PUBLIC_ARTIFACT_GAP_OR_PAPER_INCONSISTENCY`，不是仍可通过修改公开分析脚本消除的实现偏差。完整逐项证据与机器清单分别见 `docs/official_instance_analyses.md` 和 `data/manifests/official_instance_analyses.json`。

## 6. 主运行 Prompt、ACI 与定性案例恢复

对 experiments `a5d5272` 中 GPT-4 Full 2,268 条和 Lite 300 条轨迹进行逐条 prompt 审计后，全部 instance message 可由 `SWE-agent@5b143857` 初始模板逐字生成，全部轨迹共享同一 demonstration。system prompt 存在两个字节级变体：2,002 条把四个可选参数的详细标签写成 `required`，566 条写成 `optional`；两者的命令 signature 都保留可选方括号。初始 Git 元数据只能逐字生成 optional 版本。

名义运行名称包含 `last_5_history`，但 `Last5Observations` 直到 `08e66863` 才进入公开历史。实际 prompt 又保留初始提交中的旧拼写与命令文档，且 required 版本不能由任一已知提交直接生成。因此主运行协议是可由轨迹冻结的混合工作树，不存在一个能够完整代表它的公开 commit。`658eb284` 的定位限定为论文时间对齐快照。

四个论文定性案例的 72 个 action 与公开轨迹逐字相等，四份 gold patch 与冻结 Lite 数据逐字相等，结果标签全部一致。SymPy 成本退出时存在环境自动提交而论文展示只写 `Exited` 的语义省略，Requests 最终 observation 也有排版扩展；两者不改变动作或判分。10 个命令实现、21 个 TeX/PDF 资产及 7 份界面 PDF 的渲染状态均已登记。

完整审计见 `docs/official_qualitative_interface_audit.md`，机器清单为 `data/manifests/official_qualitative_interface.json`。精确重跑应使用清单冻结的实例到 system prompt 变体映射，不能把所有 episode 强制替换为单一版本。

## 7. 后续实验边界

严格重跑仍被三个独立条件阻塞：论文模型不可用、部分官方精确实现缺失、批量预算和磁盘门槛未满足。现代 Claude 或当前 GPT 模型只能进入 `modern` 证据层；推导出的 no-search/no-edit 等配置必须标为 reconstructed，不能替代论文 exact 结果。

历史 evaluator 聚合回放已经完成：固定 `SWE-bench@cfb20092`、Lite 数据 `81ad348` 和 Full 数据 `283547a` 后，八组官方报告的完整类别列表均与 `results.json` 相同。重放同时确认历史实现不对预测行去重，并定位到后续数据 revision 会使两组 Full 结果各多判两个 resolved。完整证据见 `docs/evaluator_replay.md` 与 `data/manifests/official_evaluator_replay.json`。

代表实例的容器级重新评测已完成两个核心分支：pytest 4.4 的官方 resolved 与 applied-unresolved prediction 均成功重建环境、应用两份补丁并执行测试，完整测试结果为 `2/2` 与历史日志相同。边界验证也已完成：未修改 gold patch、官方 patch-apply failure、空字符串、null 与重复预测行得到 `5/5` 精确状态匹配。首次 gold/no-apply 尝试因 Git HTTP/2 clone 早期 EOF 在创建环境前终止，未应用补丁、未运行测试、未调用模型，作为无效基础设施尝试保留；冻结输入不变的 HTTP/1.1 重试通过。`G_EVALUATOR_REPLAY` 仍保留为部分完成，因为全量 300/2,294 实例容器重评和每个支持仓库的 gold 环境验证尚未完成；该门槛也不解除原模型、精确消融配置、预算和磁盘阻塞。
