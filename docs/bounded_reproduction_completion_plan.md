# 预算约束下的 SWE-agent 复现完成方案

## 1. 采用的完成定义

本项目不再把“调用已经退役且当前端点不可用的论文模型”作为预算内必须达到的终点。预算内终点固定为：

> 完成全部公开论文工件复现，并使用当前可用模型在冻结 SWE-agent 快照上完成默认 ACI 与八个论文单因素 ACI 的 dev23、四重复配对实验、评测、统计分析、成本审计和 Git 冻结。

全部条件满足后写入唯一完成标志：

`BOUNDED_MODERN_REPRODUCTION_COMPLETE`

该标志允许表述“公开工件与预算约束的现代 ACI 复现完成”，不允许表述“论文原模型严格复现完成”或“整篇论文 exact reproduction 完成”。退役模型、未公开原始消融配置和私有运行工件仍作为明确限制保留。

## 2. 为什么在这里停止

现有公开工件层已经达到 54/54，继续投入费用最有研究价值的部分是论文核心命题：ACI 设计是否会改变软件工程代理的成功率。八项现代配置已经完成 8/8 单因素检查、8/8 冻结解析器加载和 4/4 命令行为测试，下一步不再需要扩大配置范围。

完整论文 exact 矩阵至少需要 13,140 个 episode，约为现有 20-episode 基线的 657 倍，而且论文模型目前不可调用。该目标既超过 50–80 倍预算，也无法仅靠增加费用解除模型与私有工件门槛。相反，九个配置在全部 23 个 dev 实例上执行四次，共 828 个有效实验单元，可以在预算内形成独立、成对、可重复的现代结论。

四重复完成后不再增加第五次重复、不切换模型、不增加 prompt 变体、不进入 300 条 Lite test，也不因结果不显著或方向与论文不同而追加样本。这样可以避免结果驱动扩展，并给出明确停止点。

## 3. 实验矩阵

冻结数据为 SWE-bench Lite dev 的全部 23 个实例。`data/manifests/swebench_lite_dev23_full.json` 在观察任何 ACI 消融结果前，把原 dev20 选择和三个已冻结 holdout 合并为完整 dev23。

九个配置为：

1. 默认 ACI；
2. edit without linting；
3. no edit；
4. iterative search；
5. no search；
6. 30-line window；
7. full-file view；
8. full history；
9. no demonstration。

每个“配置 × 实例”执行四次独立 repetition：

| 项目 | 数量 |
|---|---:|
| 配置 | 9 |
| dev 实例 | 23 |
| repetitions | 4 |
| 总实验单元 | 828 |
| 已完成且可复用的默认基线 | 20 |
| 新增 episode | 808 |
| 每 episode 调用硬上限 | 25 |
| 新增调用绝对上限 | 20,200 |

现有默认 dev20 作为 default-ACI repetition 1 的 20 个单元。第一轮只需补三个 default holdout，并运行八个变体的全部 23 个实例；后续三轮各运行 9 × 23 = 207 个 episode。

## 4. 分阶段预算

定义 `C0` 为现有 20 个默认 ACI episode 的可核验实际账单成本。现有使用量为 398 次资源审计调用、5,496,947 input tokens 和 70,405 output tokens；其中 token 是下界。

| 阶段 | 内容 | 本阶段新增 | 累计新增 | 预计累计成本 |
|---|---|---:|---:|---:|
| R1 | 补齐全部配置的 repetition 1 | 187 | 187 | 9.35 × C0 |
| R2 | 全部配置 repetition 2 | 207 | 394 | 19.70 × C0 |
| R3 | 全部配置 repetition 3 | 207 | 601 | 30.05 × C0 |
| R4 | 全部配置 repetition 4 | 207 | 808 | 40.40 × C0 |

新增 token 下界投影为约 222,076,659 input tokens 和 2,844,362 output tokens，资源审计调用投影约 16,079 次。按每 episode 10 分钟、单并发估算，代理运行约需 134.7 小时，即 5.6 天；环境构建与 evaluator 时间另计。

常规剩余预算上限为 50 × C0，目标矩阵预计使用 40.4 × C0，保留 9.6 × C0 处理 token 波动、计费失败请求和基础设施重试。50 × C0 以上不得启动新 repetition；只有已经开始的预注册整轮需要收尾时才允许动用应急空间。80 × C0 是绝对硬停线，不得因任何结果或工程原因突破，也不得用剩余预算增加新实验。

当前中转单价和 `C0` 的实际美元值仍未核验。相对预算已经确认，因此 R1–R4 可以按 `C0` 使用量倍数、每 episode 25 调用硬上限和每轮检查点执行；美元账单仍必须持续记录，未知价格不得被写成零。启动 R1 前和每轮结束后必须记录：

- 现有 20 个 episode 的实际账单成本 `C0`；
- input/output 单价及缓存计价；
- 失败请求是否计费；
- 50 × C0 常规 ceiling 与 80 × C0 硬 ceiling 的美元值；
- 每轮开始前的已用金额和剩余额度。

## 5. 每轮执行与检查点

每轮按配置和实例的冻结顺序顺序执行，最大并发保持 1。每个 episode 完成后立即保存 trajectory、prediction、运行参数、配置 SHA-256、命令资产 SHA-256 和 API usage；随后运行 evaluator 并保存 scorecard。

每轮结束后必须完成：

1. 检查计划单元是否全部有且只有一个有效结果；
2. 把环境失败、零模型响应、格式退出、空 prediction、patch 冲突和真实未解决分开；
3. 只允许对零模型响应或未产生模型结果的基础设施失败重试，原 attempt 必须保留；
4. 汇总实际费用与 `C0` 倍数，确认下一轮不会越过预算规则；
5. 生成轨迹、预测、scorecard 和配置的 SHA-256 清单；
6. 更新实验日志并提交 Git。

R1–R3 只是检查点，不是完成标志。即使中间结果已经显著或方向一致，也继续执行到 R4；即使结果不显著或方向相反，也不扩大 R4 之后的样本。

## 6. 统计预注册

主要结果固定为 `RESOLVED_FULL`。每个配置的分母为 23 × 4 = 92；空 prediction、格式退出、调用上限退出、patch 应用失败和 evaluator 判定未解决都进入分母。

八个变体分别与 default ACI 比较：

- 按 instance 与 repetition 配对，执行双侧 exact McNemar；
- 八个主要检验使用 Holm family-wise 校正；
- 以 instance 为 cluster 做 10,000 次 bootstrap，cluster 内保留四次 repetition，seed 固定为 42；
- 报告绝对解决率、配对胜/负/平、效应差区间和校正前后 p 值；
- 单独报告 `NOT_GENERATED`、`PATCH_APPLY_FAILED`、`RESOLVED_NO`、`RESOLVED_PARTIAL`、退出条件、调用、token 与 turn。

完成与结果方向、显著性或论文点估计是否落入区间无关。只要预注册数据完整、评测有效、分析按计划生成，就进入完成判定。

## 7. 唯一停止点与验收清单

以下条件必须同时满足：

- 公开论文输出仍为 54/54 可审计终态；
- 八个现代 ACI 配置的静态和运行时验证仍为 8/8；
- 九配置 × 23 实例 × 4 repetitions 的 828 个单元全部存在，其中新增 808 个；
- 828 个单元全部有 evaluator 终态，基础设施失败已按规则处理；
- 原始轨迹、预测、配置、usage 和 scorecard 均有哈希与索引；
- McNemar、Holm、cluster bootstrap 和失败分解全部生成；
- 实际费用、失败计费和重试成本形成完整台账，且不超过 80 × C0；
- 综合报告明确区分 public、modern、exact 三类证据；
- 最终验证通过、凭据扫描为 0、Git 工作区干净并完成英文 conventional commit。

满足全部条件后，将 `conf/bounded_modern_reproduction.yaml` 的完成字段更新为真，在报告中写入 `BOUNDED_MODERN_REPRODUCTION_COMPLETE`，随后停止本实验。未获得论文精确模型与私有工件时，`exact_model_rerun_complete` 和 `strict_full_paper_reproduction_complete` 永远保持 false。

## 8. 当前状态

当前状态为 `RELATIVE_BUDGET_AUTHORIZED_PRICE_UNVERIFIED`。实验范围、四轮顺序、统计方法、正常预算和绝对硬停线已经冻结；尚未执行任何新增付费 episode。R1 按使用量倍数和调用硬上限启动；在获得中转定价后补充美元 ledger，但不改变已冻结矩阵。
