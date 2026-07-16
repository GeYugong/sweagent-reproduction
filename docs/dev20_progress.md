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

## 未计入正式结果的尝试

`EXP-DEV20-003A` 尝试运行 `pvlib__pvlib-python-1154`，但容器内 Conda 在下载 Python、NumPy、Pandas、SciPy 与 OpenBLAS 时连续发生代理 TLS 超时。失败发生在 agent 初始化前：

- API 调用：0；
- 轨迹：未生成；
- 预测：未生成；
- 正式评测：未启动；
- dev20 分母：不计入。

运行适配补丁已向实验容器注入单线程下载、60 秒连接超时、180 秒读取超时、10 次重试和 classic solver。运行器也已改为必须同时检测到实例 `.traj` 与 `all_preds.jsonl`，避免把只有 `args.yaml` 的目录误判为推理成功。

后续两次重试仍均在推理前终止。`EXP-DEV20-003B` 中镜像仓库 clone 遇到瞬时网络停滞，超过论文快照固定的 500 秒长任务超时；同一容器随后完整 clone 实测为 31.8 秒、177 MB，因此保留原始超时，不改变实验配置。`EXP-DEV20-003C` 进入依赖安装后暴露旧版类型兼容问题：`swebench 1.0.1` 将 `pip_packages` 提供为字符串，论文快照却按列表执行 `join`，导致首先尝试安装单字符包 `j`。兼容层只对字符串执行空白切分，依赖集合保持不变。两次失败的 API 调用均为 0，均不计入 dev20 分母。

为保证重试审计，实例运行器从此为每次尝试保留 UTC 时间戳日志，并同步一份无时间戳的最新日志。相同 run ID 的失败记录不再被下一次重试覆盖。

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
