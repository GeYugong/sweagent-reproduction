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

恢复尝试随后产生 25 次模型调用（288,831 input tokens、3,259 output tokens），提交的 prediction 通过独立 evaluator，终态为 `RESOLVED_FULL`。因此该单元的有效结果来自唯一一次授权重试；零响应原尝试不计入模型调用或解决率分母之外的重复采样。

## R1 / 模型响应后容器基础设施失败（不重试）

- 执行日期：2026-07-17
- 配置与实例：`edit_without_linting` / `pylint-dev__astroid-1333`
- 已持久化模型调用：20（240,312 input tokens、2,342 output tokens）

该实例完成环境准备后已获得并持久化 20 次模型响应。随后 agent 容器在 trajectory、prediction 和 evaluator 评分卡生成前退出；运行器报告 Docker exec 的 `409 Conflict`（目标容器不再运行）。因此该尝试不属于零模型响应失败。

冻结规则只允许对“零模型响应或未产生模型结果”的基础设施失败进行一次重试。为保证不将已经发生的模型交互重采样，该实例被标记为 `MODEL_RESPONSE_INFRASTRUCTURE_FAILURE_NO_RETRY`，并写入 `data/manifests/nonretry_after_model_response.json`。批处理脚本会跳过该标记项，使恢复执行不会隐式重跑；该项在最终汇总中与已评分项分开报告，不计作已解决实例。

## R1 / 零模型响应环境超时：授权保留尝试的恢复

- 执行日期：2026-07-17
- 配置与实例：`edit_without_linting` / `pyvista__pyvista-4315`
- 原始运行标识：`bounded_r1_edit_without_linting_pyvista_pyvista-4315`

原始运行完成仓库克隆后，在实例环境脚本的 `apt update` 步骤等待外部软件源。运行器记录 `Timeout reached while reading from subprocess`，并列出仍在运行的 `apt` 与 `http` 子进程；随后按运行器的环境关闭路径停止容器。该尝试没有模型响应、trajectory、prediction 或 evaluator scorecard。

因此该事件被分类为 `ZERO_MODEL_RESPONSE_INFRASTRUCTURE_FAILURE`。根据冻结协议，唯一的恢复运行获授权并使用独立标识 `bounded_r1_edit_without_linting_pyvista_pyvista-4315_attempt_2`，使原始失败日志保留且不会覆盖。授权记录位于 `data/manifests/zero_model_response_retries.json`；成功评分后不得再次重试。

恢复运行完成 18 次模型调用（204,920 input tokens、3,803 output tokens），生成 prediction 且补丁成功应用。独立 evaluator 对目标 `FAIL_TO_PASS` 测试给出通过结果，终态为 `RESOLVED_FULL`；无安装、重置、补丁应用或测试超时错误。该单元的有效结果仅来自这一次保留标识的授权恢复运行。

## R1 / 模型响应后 evaluator 基础设施失败（不重试）

- 执行日期：2026-07-17
- 配置与实例：`edit_without_linting` / `sqlfluff__sqlfluff-2419`
- 已持久化模型调用：25（236,694 input tokens、3,649 output tokens）

该实例生成 prediction，补丁可由 evaluator 成功应用；但 evaluator 在恢复其内部补丁检查时执行 `git restore test/rules/std_L060_test.py`，目标 evaluation checkout 不包含该路径，导致 `CalledProcessError`。因此评分卡仅保留 `generated`，没有补丁应用后的测试终态。

这不是零模型响应失败，且任何重跑都会重采样已经发生的模型交互。该实例标记为 `MODEL_RESPONSE_EVALUATOR_INFRASTRUCTURE_FAILURE_NO_RETRY`，加入 `data/manifests/nonretry_after_model_response.json`，最终分析将把它与完整 evaluator 终态分开报告。
