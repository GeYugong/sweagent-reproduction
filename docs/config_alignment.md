# 论文与代码配置对齐

## 对齐对象

- 论文：arXiv `2405.15793v3`。
- 代码：SWE-agent `658eb2842e8a8b00069b301338bc342b70538f7a`。
- 代码配置：`code/SWE-agent/config/default.yaml`。
- 模型入口默认值：`code/SWE-agent/run.py`。

## 字段核对

| 论文描述 | 代码字段或实现 | 快照值 | 结论 |
|---|---|---|---|
| GPT-4 Turbo | `gpt4` shortcut | `gpt-4-1106-preview` | 一致 |
| temperature | `ModelArguments.temperature` | CLI 默认 `0.0` | 一致 |
| top-p | `ModelArguments.top_p` | CLI 默认 `0.95` | 代码补充信息 |
| 单实例预算 | `per_instance_cost_limit` | CLI 默认 `$3.00` | 代码补充信息 |
| 文件窗口 | `env_variables.WINDOW` | `100` | 一致 |
| 上下文历史 | `history_processor` | `Last5Observations` | 一致 |
| demonstration | `demonstrations` | marshmallow 轨迹 1 条 | 一致 |
| 编辑器 | `command_files` | `edit_linting.sh` | 一致 |
| 搜索 | `command_files` | `search.sh` | 一致 |
| 动作解析 | `parse_function` | `ThoughtActionParser` | 与附录格式一致 |
| 命令文档解析 | `parse_command` | `ParseCommandDetailed` | 与附录格式一致 |

## 默认命令集合

默认 ACI 通过四个文件注入命令与辅助逻辑：

```text
config/commands/defaults.sh
config/commands/search.sh
config/commands/edit_linting.sh
config/commands/_split_string.py
```

其中编辑器的 linting guardrail、摘要式搜索结果和 100 行窗口是论文消融的直接研究对象。复现时不能只保存 prompt 文本，还必须保存这些命令文件的 Git 哈希。

## 可复现配置副本策略

第三方默认 YAML 保持只读，不在 submodule 内直接修改。正式运行前应从该文件生成研究配置副本，并在副本中只显式覆盖以下运行参数：

- 模型精确标识；
- 数据集路径、split 和实例过滤器；
- 输出目录；
- token/费用硬上限；
- 容器镜像 digest；
- 随机种子和重试策略。

任何 ACI 消融都应使用单独配置文件，并通过结构化 diff 证明只改变目标因素。

## 版本风险

上游 `v0.7.0` 的 README 已把 SWE-bench Lite 成绩更新为 23%，而论文 v3 主表仍为 18%。这说明上游 release、README 数字和论文实验不是一一对应关系。严格基线继续使用提交时间对齐快照，现代实现必须作为独立系统命名，不能覆盖 paper snapshot。
