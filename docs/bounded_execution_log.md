# 有界现代复现执行日志

本日志记录冻结方案启动后的阶段性、不可变检查点。完整逐步轨迹、预测、评测输出和运行日志保存在本地 `outputs/`；其中包含实例级参数、配置与命令资产哈希、API usage 和 evaluator 输出。

## R1 / 默认 ACI 补齐批次

- 执行日期：2026-07-17
- 冻结清单：`data/manifests/bounded_r1/default_aci_missing3.json`
- 配置：默认 ACI（`config/default.yaml`）
- 数据集：`princeton-nlp/SWE-bench_Lite`，revision `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`，`dev` split
- 样本：`pvlib__pvlib-python-1072`、`pylint-dev__astroid-1866`、`pylint-dev__astroid-1978`
- 并发：1；每个 episode 的模型调用硬上限：25。

### 结果

| 实例 | 模型调用 | 输入 tokens | 输出 tokens | evaluator 终态 |
|---|---:|---:|---:|---|
| `pvlib__pvlib-python-1072` | 22 | 259,232 | 3,322 | `RESOLVED_FULL` |
| `pylint-dev__astroid-1866` | 23 | 258,777 | 2,915 | `RESOLVED_NO` |
| `pylint-dev__astroid-1978` | 24 | 276,171 | 9,139 | `RESOLVED_NO` |

三个 prediction 均已生成，补丁均可应用，三个 evaluator 均完成测试且不存在安装、重置、补丁应用或测试超时错误。批次解决数为 1/3。

### 预算检查点

本批次合计 69 次持久化调用、794,180 input tokens 和 15,376 output tokens。相对于既有基线 `C0`（398 次调用、5,496,947 input tokens、70,405 output tokens），调用、输入和输出的相对倍数分别为 0.1734、0.1445 和 0.2184；保守最大值为 0.2184 × `C0`，低于 R1 常规阈值与 80 × `C0` 绝对硬停线。

中转单价与美元计费仍未核验，因此该检查点只报告由 trajectory 直接恢复的资源使用量，未将未知价格记为零。预算脚本判定为 `WITHIN_RELATIVE_BUDGET`，随后启动 R1 的 `edit_without_linting` 配置批次。

## R1 / 零模型响应基础设施重试

- 执行日期：2026-07-17
- 配置与实例：`edit_without_linting` / `marshmallow-code__marshmallow-1359`
- 原始尝试：`attempt 1`

环境初始化、仓库克隆和代理 shell 建立均已完成，但首次模型请求在超过 12 分钟后仍未返回，trajectory 中没有模型调用记录、prediction 或持久化轨迹。运行进程维持到本地代理的 TCP 连接；无凭据的连通性探针返回 HTTP 401，说明代理与目标服务可达而该请求未获得响应。

该尝试被分类为 `ZERO_MODEL_RESPONSE_INFRASTRUCTURE_FAILURE`，原始元数据保存在该 run 的本地 trace 目录。根据冻结方案中“仅零模型响应基础设施失败可重试”的例外，终止卡死进程后允许一次人工恢复运行；这不是对已有模型结果的重采样，也不产生可计费的已记录模型调用。
