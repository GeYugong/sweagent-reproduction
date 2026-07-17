# 现代模型 dev20 基线统计

## 结论

`gpt-5.6-terra` 在冻结 SWE-bench Lite dev20 上完成 20/20 个实例，完全解决 4 个，resolve rate 为 20.0%，Wilson 95% CI 为 [8.1%, 41.6%]。该结果属于现代模型开发集基线，不是论文 `gpt-4-1106-preview` 的严格重跑，也不能与论文 Lite test 点估计作直接显著性比较。

原始轨迹持久化 397 次 API 调用、5,496,947 input tokens 和 70,405 output tokens。`sqlfluff__sqlfluff-1763` 的最终格式纠正请求没有写入轨迹 usage；资源台账确认总调用为 398，因此 token 总数只能解释为下界。中转端点未提供可核验价格，成本不填 0。

## 结果分布

| evaluator 结果 | 实例数 |
|---|---:|
| `NOT_GENERATED` | 6 |
| `PATCH_APPLY_FAILED` | 4 |
| `RESOLVED_FULL` | 4 |
| `RESOLVED_NO` | 4 |
| `RESOLVED_PARTIAL` | 2 |

14/20 个实例生成 prediction，10/20 成功应用，4/20 完全解决。6 个未生成 prediction，4 个 prediction 在 benchmark test patch 叠加阶段应用失败。该分布表明现代模型与论文期严格 ACI 的格式接口、测试文件修改和提交协议是当前主要工程边界，不能只用 resolve rate 概括。

## 仓库分层

| 仓库 | n | resolved | rate | calls | input tokens | output tokens |
|---|---:|---:|---:|---:|---:|---:|
| `marshmallow-code` | 2 | 2 | 100.0% | 45 | 543,072 | 8,155 |
| `pvlib` | 4 | 1 | 25.0% | 52 | 832,382 | 11,890 |
| `pydicom` | 5 | 1 | 20.0% | 112 | 1,450,662 | 17,392 |
| `pylint-dev` | 3 | 0 | 0.0% | 70 | 804,195 | 10,216 |
| `pyvista` | 1 | 0 | 0.0% | 4 | 50,758 | 802 |
| `sqlfluff` | 5 | 0 | 0.0% | 114 | 1,815,878 | 21,950 |

仓库样本量为 1–5，仅用于描述，不作仓库间显著性推断。20 个实例来自 dev split，选择清单在运行前由 seed 42 固定。

## 资源分布

- API calls：均值 19.85，中位数 22.5，IQR [20.0, 25.0]；
- input tokens：均值 274,847.35，中位数 288,395.5；
- output tokens：均值 3,520.25，中位数 3,405.5；
- 成功实例持久化调用 87 次，失败实例 310 次；调用量不解释为因果因素。

## 证据完整性

20 份 scorecard、20 份 trajectory、prediction/result 文件及可得运行参数均记录路径、字节数和 SHA-256。19/20 份 `args.yaml` 逐项确认模型、temperature 和 top-p；`sqlfluff__sqlfluff-1763` 缺少 `args.yaml`、run manifest 和最终 usage，已作为持久化缺口保留。该缺口不改变其 `NOT_GENERATED` 判分，但阻止把 token 合计写成精确总成本。

## 完成边界

本分析完成已有现代默认 ACI 基线的统计收口。八个论文单因素 ACI 已完成配置重建、冻结解析器验收和 160 条配对运行预注册，详见 `docs/modern_aci_reconstruction.md`；配对运行仍为 0/160，因而 `modern_replication_complete=false`，也不存在可计算的配对 McNemar 检验。扩大 API 实验前仍需明确总预算上限和端点价格。

机器清单位于 `data/manifests/modern_dev20_baseline_analysis.json`，逐实例数据位于 `data/derived/modern_dev20_baseline_instances.csv`。
