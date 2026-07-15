# SWE-bench Lite dev20 进度

## 数据冻结

- 数据集：`princeton-nlp/SWE-bench_Lite`；
- revision：`6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`；
- split：dev；
- 原始实例数：23；
- 实验实例数：20；
- 选择方法：对 instance ID 排序后，使用 `random.Random(42).sample(ids, 20)`，再对结果排序；
- 保留实例数：3。

Dataset Viewer `/splits` 与 `/rows` 在冻结时连续返回 503，因此使用本机已缓存的同一 Hub revision 生成清单。脚本重新计算后，20 个实验实例与 3 个保留实例均完全匹配清单。

## 已正式评测实例

| run_id | instance | calls | input tokens | output tokens | patch | result |
|---|---|---:|---:|---:|---|---|
| EXP-API-BASELINE-001 | `sqlfluff__sqlfluff-1625` | 25 | 270,910 | 3,248 | applied | RESOLVED_NO |
| EXP-DEV20-001 | `marshmallow-code__marshmallow-1343` | 22 | 243,975 | 2,750 | applied | RESOLVED_FULL |
| EXP-DEV20-002 | `marshmallow-code__marshmallow-1359` | 23 | 299,097 | 5,405 | applied | RESOLVED_FULL |

当前累计：

- 已评测：3/20；
- resolved：2；
- 未 resolved：1；
- 暂时 resolve rate：66.7%。

该比例只有三个样本，不报告置信区间，也不用于模型间比较。至少完成冻结的 20 个实例后再计算主指标与 bootstrap 置信区间。

## Marshmallow 成功案例

模型首先用最小脚本复现 nested schema 输入类型错误与 field validator 的交互，随后定位 `BaseSchema._do_load()`。候选修复只在 `result is not None` 时调用 field validators，并添加回归测试。

正式 evaluator 结果：

- patch apply：成功；
- FAIL_TO_PASS：1/1 通过；
- PASS_TO_PASS：24/24 通过；
- 总目标测试：25/25 通过；
- 判定：`RESOLVED_FULL`。

模型在第 22 次调用主动提交，未触发 25 次预算上限。端到端墙钟时间约 678 秒，其中 API 响应窗口约 173 秒，其余主要为容器冷启动、依赖安装和测试。

## Marshmallow 1359 成功案例

问题涉及容器字段内部 `DateTime` 无法继承根 schema 的 `datetimeformat`。模型复现 List/Tuple 场景后，将格式读取对象从直接父 schema 改为 `self.root.opts`，并增加 List 与 Tuple 的回归测试。

正式 evaluator 结果：

- patch apply：成功；
- FAIL_TO_PASS：1/1 通过；
- PASS_TO_PASS：76/76 通过；
- 总目标测试：77/77 通过；
- 判定：`RESOLVED_FULL`。

模型在第 23 次调用主动提交，输入 299,097 token、输出 5,405 token，未触发 25 次预算上限。API 响应窗口约 171 秒。
