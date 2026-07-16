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
| EXP-DEV20-003 | `pvlib__pvlib-python-1154` | 23 | 363,417 | 5,377 | apply failed | unresolved |
| EXP-DEV20-004 | `pvlib__pvlib-python-1606` | 4 | 55,879 | 632 | not generated | unresolved |
| EXP-DEV20-005 | `pvlib__pvlib-python-1707` | 21 | 361,753 | 4,612 | applied | RESOLVED_FULL |
| EXP-DEV20-006 | `pvlib__pvlib-python-1854` | 4 | 51,333 | 1,269 | not generated | unresolved |
| EXP-DEV20-007 | `pydicom__pydicom-1139` | 21 | 353,071 | 2,521 | applied | RESOLVED_PARTIAL |
| EXP-DEV20-008 | `pydicom__pydicom-1256` | 21 | 248,681 | 2,580 | applied | RESOLVED_FULL |
| EXP-DEV20-009 | `pydicom__pydicom-1413` | 20 | 249,072 | 5,460 | applied | RESOLVED_PARTIAL |

当前累计：

- 已评测：10/20；
- resolved：4；
- 未 resolved：6；
- 暂时 resolve rate：40.0%。

当前样本仍未完成，不报告置信区间，也不用于模型间比较。至少完成冻结的 20 个实例后再计算主指标与 bootstrap 置信区间。

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

`EXP-DEV20-003D` 在替换 API 凭据时于 Conda 环境创建阶段主动终止。时间戳日志确认 agent 尚未初始化，API 调用为 0；该尝试不计入 dev20 分母。新凭据随后以最小 Chat Completions 请求验证，`gpt-5.6-terra` 返回 HTTP 200 和精确 `OK`，共消耗 4,398 token。探测只验证认证与协议，不计入正式实验。

## pvlib 1154 正式结果

兼容修正后的 `EXP-DEV20-003` 完成了推理与正式 evaluator。模型将 `HB / ghi` 改为带 `where=ghi != 0` 的 `np.divide`，并把既有测试在零 GHI 时的期望值从 `np.nan` 改为 `0`。模型侧验证结果：

- 单个目标测试：1/1 通过；
- `pvlib/tests/test_irradiance.py`：98/98 通过；
- API 调用：23；
- 输入 token：363,417；
- 输出 token：5,377；
- exit status：`submitted`。

正式 evaluator 先成功应用 benchmark 测试补丁，随后预测补丁在同一测试断言处发生上下文冲突。生产代码 hunk 能单独应用，但正式协议要求整份预测补丁可应用，因此 scorecard 只有 `generated`、没有 `applied`，该实例计为 unresolved。该失败揭示了一个可用于改进实验的方向：提交前自动剔除测试文件改动，避免正确的生产代码修复因测试 hunk 冲突而失效。

首次恢复批处理时发现续跑判断只将含 `RESOLVED_*` 状态的 scorecard 视为已评测，因而对该 `generated`-only 结果重复执行了一次 evaluator。重复判分没有调用模型、没有改变 scorecard，也不作为新实例计数。续跑规则已改为：冻结实例只要出现在任一正式 `scorecards.json` 中，无论 applied 或 resolved 状态如何，均直接跳过。

## pvlib 1606 正式结果

`EXP-DEV20-004` 在 Agent 的首个动作前退出。模型返回的意图和命令本身合理，但把命令围栏写成 `` ```bash ``；论文快照 ACI 的严格解析器只接受没有语言标签的三反引号围栏。连续三次格式纠正仍保留语言标签，第四次 API 调用后触发 malformat limit：

- API 调用：4；
- 输入 token：55,879；
- 输出 token：632；
- 实际工具动作：0；
- patch：未生成；
- exit status：`exit_format`；
- scorecard：`not_generated`。

该实例按正式协议计为 unresolved。它进一步说明现代模型与 2024 年论文 ACI 之间存在语法接口漂移，可在完成基线后将“允许代码围栏语言标签”作为独立兼容改进，而不能在当前 dev20 基线中途启用。

## pvlib 1707 正式结果

模型在 `physical()` 的 IAM 计算后将绝对入射角不小于 90 度的结果置为 0，并恢复 pandas Series 的索引类型；Agent 侧 `test_iam.py` 为 30/30 通过。首次 evaluator 使用 NumPy 2.0.2，冻结代码在收集阶段因 `np.Inf` 被移除而使全部测试失败，该 scorecard 已标记为无效。

同一预测在仅增加 `numpy<2` 约束的隔离 evaluator 中重新判分：

- patch apply：成功；
- FAIL_TO_PASS：1/1；
- PASS_TO_PASS：30/30；
- 总目标测试：31/31；
- API 调用：21；
- 输入 token：361,753；
- 输出 token：4,612；
- 正式判定：`RESOLVED_FULL`。

重判没有再次调用模型，预测 patch、benchmark test patch 和测试集合均未改变。

## pvlib 1854 正式结果

EOF 通信竞态修复后，`EXP-DEV20-006` 正常进入 Agent。模型首个计划是用最小示例复现 `PVSystem(arrays=array)` 构造失败，但响应既使用 `` ```sh `` 语言标签，又重复了整段 DISCUSSION 与命令块。严格 ACI 解析器连续拒绝格式，达到 malformat limit：

- API 调用：4；
- 输入 token：51,333；
- 输出 token：1,269；
- 工具动作：0；
- model patch：null；
- scorecard：`not_generated`；
- 正式判定：unresolved。

这与 1606 的语言标签失败构成第二个独立样本，但 1854 还包含响应块重复，后续改进组需要分别统计“仅允许语言标签”能否恢复，而不能假设所有格式失败均由单一原因造成。

## pydicom 1139 正式结果

首次运行缺少 pytest，第二次运行安装 pytest 8.4.2 后又因旧式 nose `setup(self)` 不执行而使两个 PASS_TO_PASS 失败，两次均标记为环境无效。兼容性矩阵在同一冻结提交上验证：

- pytest 6.2.5：目标旧式 setup 测试 2/2 通过；
- pytest 7.4.4：目标测试 2/2 通过，并明确警告 nose setup 支持将在 pytest 8 移除。

保留第二次运行的原始 21-call 预测，在 pytest 7.4.4 evaluator 中重新判分：

- patch apply：成功；
- FAIL_TO_PASS：2/3 通过；
- PASS_TO_PASS：38/38 通过；
- 总目标测试：40/41 通过；
- API 调用：21；
- 输入 token：353,071；
- 输出 token：2,521；
- 正式判定：`RESOLVED_PARTIAL`。

模型实现 `PersonName.__iter__`，修复 iterator 与 contains，但没有实现 Python 2 风格的 `.next()`，所以剩余 FAIL_TO_PASS `test_next` 合理失败。主 resolve rate 只把 `RESOLVED_FULL` 计为成功，因此该实例记为 unresolved；部分修复率单独保留。

## pydicom 1256 正式结果

退出码截止时间竞态修复后，模型定位到嵌套 Sequence 反序列化路径没有继续传递 `bulk_data_element_handler`。候选补丁在递归 `DataElement.from_json()` 调用中加入该 handler，并为嵌套 `BulkDataURI` 增加回归测试。Agent 侧完整 `pydicom/tests/test_json.py` 为 23/23 通过。

正式 evaluator 使用固定的 pytest 7.4.4，benchmark test patch 与 prediction patch 均成功应用：

- FAIL_TO_PASS：1/1 通过；
- PASS_TO_PASS：22/22 通过；
- 总目标测试：23/23 通过；
- API 调用：21；
- 输入 token：248,681；
- 输出 token：2,580；
- agent 步骤：19；
- 正式判定：`RESOLVED_FULL`。

累计 9 个正式实例为 4 个完全解决、1 个部分解决和 4 个无有效解决，主 resolve rate 为 44.44%。

## pydicom 1413 正式结果

模型发现 `DataElement` 对包含反斜杠字节的二进制值执行多值拆分，并把 `OL` 加入不拆分的 VR 列表，同时添加 OL 写入回归测试。Agent 先修正了一次不存在的 `apply_patch` 命令，最终目标测试 1/1、完整 `test_filewriter.py` 164/164 通过。

正式 evaluator 表明修复方向正确但覆盖不完整：

- FAIL_TO_PASS：1/3 通过；
- PASS_TO_PASS：301/301 通过；
- 总目标测试：302/304 通过；
- 未解决 VR：`OD`、`OV`；
- API 调用：20；
- 输入 token：249,072；
- 输出 token：5,460；
- agent 步骤：18；
- 正式判定：`RESOLVED_PARTIAL`。

模型只把 `OL` 加入排除列表，没有从问题的一般规律归纳到同为二进制数值 VR 的 `OD` 与 `OV`。该实例不计为完全解决，但保留为第二个部分解决样本。

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
