# 首个真实 API 单实例结果

## 实验对象

- 数据集：SWE-bench Lite dev；
- 实例：`sqlfluff__sqlfluff-1625`；
- agent：论文快照 `658eb2842e8a8b00069b301338bc342b70538f7a`；
- ACI：`config/default.yaml`；
- 模型：`gpt-5.6-terra`；
- 接口：OpenAI 兼容 Chat Completions；
- temperature：0.0；
- top_p：0.95。

## 8 次调用 pilot

pilot 用于验证真实模型在论文 ACI 中的行为是否稳定。模型依次完成仓库查看、问题复现、规则定位、实现阅读、fixture 阅读和 TSQL parse tree 检查，没有出现重复循环。

| 指标 | 结果 |
|---|---:|
| API 调用 | 8 |
| 输入 token | 73,004 |
| 输出 token | 848 |
| agent 步骤 | 9（含 `exit_cost`） |
| 候选补丁 | 无 |
| 状态 | `BUDGET_TRUNCATED` |

## 25 次调用基线

模型在第 25 次响应后到达冻结上限，SWE-agent 自动提交当时工作区中的候选补丁。

| 指标 | 结果 |
|---|---:|
| API 调用 | 25 |
| 输入 token | 270,910 |
| 输出 token | 3,248 |
| agent 步骤 | 26（含 `exit_cost`） |
| 推理调用窗口 | 约 177 秒 |
| 端到端墙钟时间 | 约 503 秒 |
| 修改文件 | `src/sqlfluff/rules/L031.py` |
| patch | +5 / -1 行 |
| patch apply | 成功 |
| 正式测试 | 68 passed, 1 failed |
| SWE-bench 状态 | `RESOLVED_NO` |

## 候选补丁行为

候选补丁为 `_eval()` 增加 `dialect` 参数，并在 TSQL 且不存在 `join_clause` 时跳过 L031。这个实现与 issue 文本中“无 JOIN 时不应触发”一致，但改变了 TSQL 单表别名的既有规则行为。

## 正式失败原因

FAIL_TO_PASS 测试 `test/cli/commands_test.py::test__cli__command_directed` 仍然失败。数据集中的测试补丁只把期望消息从：

```text
Avoid using aliases in join condition
```

改为：

```text
Avoid aliases in from clauses and join conditions.
```

gold patch 同样只修改 `LintResult.description`，并未取消单表别名违规。模型依据自然语言 issue 尝试修复触发逻辑，而 benchmark 期望的是修改提示语，因此出现“语义上响应 issue、测试上不匹配 gold 行为”的失败。

## 研究含义

该实例不能计为 resolved，但提供了有价值的失败案例：仅凭 issue 表述推断目标行为可能与维护者最终 patch 不一致。后续失败分类应加入“issue–gold 行为错位”，并分别记录 patch 是否合理、是否通过 benchmark，而不能只保留二元分数。
