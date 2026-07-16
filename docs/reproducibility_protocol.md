# 可复现性协议

## 运行标识

运行标识格式：

```text
expNNN_<system>_<model>_<dataset>_<variant>_s<seed>
```

例如：

```text
exp001_paper_sweagent_gpt4t_dev1_default_s42
```

## 每次运行前记录

- 本仓库 Git commit；
- 第三方代码 commit；
- 数据集名称、split、revision 和实例清单哈希；
- 模型提供方、精确模型标识和可获得的版本日期；
- 配置文件 SHA-256；
- seed、temperature、最大交互步数和费用上限；
- GPU/CPU/内存/磁盘状态；
- 容器镜像名称与 digest；
- 是否允许重试及重试条件。

## 每个实例保存

```text
outputs/
├── logs/<run_id>/<instance_id>.log
├── traces/<run_id>/<instance_id>.traj
├── patches/<run_id>/<instance_id>.patch
└── results/<run_id>/<instance_id>.json
```

结果 JSON 至少包含：

- `run_id`、`instance_id`、开始与结束时间；
- 所有代码、配置、数据和镜像版本；
- 模型调用、token、成本和时长；
- patch 路径与 SHA-256；
- 推理退出状态、评测退出状态和 `resolved`；
- 标准化失败类型；
- 原始日志与轨迹的 SHA-256。

## 失败分类

- `ENV_BUILD_FAILED`：环境或镜像构建失败；
- `MODEL_REQUEST_FAILED`：模型请求失败或限流；
- `AGENT_PARSE_FAILED`：动作无法解析；
- `TOOL_EXEC_FAILED`：工具执行异常；
- `NO_PATCH`：未产生有效补丁；
- `TEST_INFRA_FAILED`：测试基础设施失败；
- `TEST_FAILED`：补丁未通过目标测试；
- `REGRESSION`：引入额外失败；
- `TIMEOUT`：超时；
- `BUDGET_EXCEEDED`：达到 token 或费用上限；
- `RESOLVED`：通过正式判分。

## Git 提交策略

- 环境与方案冻结：`chore(repro): ...`
- 新实验能力：`feat(experiment): ...`
- 复现问题修正：`fix(repro): ...`
- 纯文档与实验结论：`docs(research): ...`
- 每个正式实验批次至少有一个独立提交，提交正文列出 run_id 与结果文件。
- 原始大型缓存不进入 Git；摘要、清单、配置、脚本和哈希必须进入 Git。

## 结果有效性

只有同时具备实例清单、配置、轨迹、补丁、判分日志和版本哈希的运行才能进入主结果表。开发调试运行必须标记为 `exploratory`，不能与冻结后的正式运行混合统计。

## 变体隔离

批处理恢复只在相同 `batch_id` 的轨迹目录内查找已评测实例。不同 ACI 变体、重复批次或模型对照即使使用相同实例 ID，也必须分别运行并保存独立 scorecard；不得因另一变体的既有结果而跳过。
