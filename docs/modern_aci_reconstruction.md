# 现代模型 ACI 单因素消融重建与配对实验预注册

## 1. 状态与证据边界

本阶段完成论文八个 ACI 单因素消融的现代模型可执行准备，未产生模型 API 调用。冻结状态为：

- 8/8 个变体已生成完整 SWE-agent 配置；
- 8/8 个配置相对默认配置只改变一个声明路径；
- 冻结版 SWE-agent `AgentConfig` 解析通过 8/8；
- 自定义命令通过 1 项 Bash 语法检查和 3 项行为测试；
- 20 个冻结 dev 实例与八个变体形成 160 条配对运行记录；
- 配对运行 0/160，价格未知，总预算未授权；
- `modern_replication_complete=false`，`exact_model_rerun_complete=false`。

这些配置只用于 `gpt-5.6-terra` 现代复验。论文没有发布八项消融的完整原始运行配置、预测和轨迹，因此本阶段不解除 `G_EXACT_ABLATION_CONFIGS`，也不把重建配置称为论文 exact 配置。

## 2. 冻结对象

基线固定为 SWE-agent revision `658eb2842e8a8b00069b301338bc342b70538f7a` 的 `config/default.yaml`，基线文件 SHA-256 为 `6428bf45edf5bdd46478f33599a80ee2579116d8855471aab74394c035a236b5`。模型、数据和运行参数固定为：

| 对象 | 冻结值 |
|---|---|
| 模型 | `gpt-5.6-terra` |
| 数据 | `princeton-nlp/SWE-bench_Lite` dev |
| 数据 revision | `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2` |
| 实例 | `data/manifests/swebench_lite_dev20_seed42.json` 的 20 条记录 |
| temperature | 0.0 |
| top-p | 0.95 |
| 每实例调用上限 | 25 |
| 自动重试 | 禁止 |

八项变体及其证据等级如下：

| 变体 | 论文聚合值 | 单一变化 | 重建等级 | 精确配置 |
|---|---:|---|---|---|
| `edit_without_linting` | 15.0% | 用无 lint/rollback 的 `edit` 替换 linting editor | 行为重建 | 未公开 |
| `no_edit` | 10.3% | 删除 `edit_linting.sh` | 公开命令移除 | 未公开 |
| `iterative_search` | 12.0% | 用逐条结果、`next`/`prev` 搜索替换摘要搜索 | 行为重建 | 未公开 |
| `no_search` | 15.7% | 删除 `search.sh` | 公开命令移除 | 未公开 |
| `window_30` | 14.3% | `env_variables.WINDOW: 100 -> 30` | 公开参数重建 | 未公开 |
| `full_file` | 12.7% | 后置覆盖内部 `_print`，每次显示整文件 | 行为重建 | 未公开 |
| `full_history` | 15.0% | `Last5Observations -> DefaultHistoryProcessor` | 公开参考配置 | 原始运行关联未公开 |
| `no_demonstration` | 16.3% | 清空 `demonstrations` | 公开参数重建 | 未公开 |

机器定义位于 `conf/modern_aci/variants.yaml`，生成配置位于 `conf/modern_aci/generated/`。`data/manifests/modern_aci_variant_validation.json` 保存每个配置、命令资产、公开参考和观察到的结构化 diff 的 SHA-256。

## 3. 缺失行为的重建决策

### 3.1 无 lint 编辑器

重建实现保留上游 `edit` 的行范围解析、数组替换、写回、文件窗口刷新和即时反馈，删除 Python lint、备份、错误展示与回滚分支。配置层仅把 `config/commands/edit_linting.sh` 替换为 `config/commands/modern_edit_without_linting.sh`。

该实现符合论文“修改直接生效、没有 lint guardrail”的行为描述，但作者使用的逐字 shell 文件未公开，因此证据等级保持 `behavioral_reconstruction`。

### 3.2 逐条搜索

论文只说明逐条展示匹配、通过 `next`/`prev` 导航、显示匹配行与 `n` 行上下文，没有报告 `n` 的值。重建实现固定为匹配行上下各 5 行，即临时 11 行窗口；该数值是显式重建假设，不是论文事实。`find_file` 保持不变，`search_dir` 和 `search_file` 改为保存有序匹配列表并打开第一项。

如果后续获得作者命令文件或 `n` 的原始值，必须建立新 revision，不能静默覆盖本预注册配置。

### 3.3 整文件查看

重建实现保留公开的 `open`、`goto`、`scroll_up/down`、`create` 和 `submit`，只在命令文件列表末尾加载 `_modern_full_file_view.sh` 覆盖内部 `_print`。所有触发文件查看的动作因此输出完整带行号文件。该方法避免复制并改写整个 `defaults.sh`，结构化配置差异只有 `command_files` 一项。

### 3.4 Full history 公开参考

上游公开文件 `default_sys-env_window100-detailed_cmd_format-full_history-1_demos.yaml` 与生成配置在去除行尾空白后完全一致。原始文件的 `instance_template` 有一处单行末尾空格差异，因此清单保留 `public_reference_raw_diff_paths=[instance_template]`，只声明 `trailing_whitespace_normalized` 匹配，不声明逐字节相同或已证明它就是论文消融运行文件。

## 4. 离线验收

`scripts/materialize_modern_aci_variants.py` 执行以下静态检查：

1. 基线配置 SHA-256 与冻结值一致；
2. 每项转换只改变预注册路径；
3. 暴露给模型的命令名称、顺序和数量与变体定义一致；
4. 自定义资产存在且哈希被记录；
5. full-history 参考配置满足声明的规范化匹配；
6. 配对实例与已完成默认基线的 20 个实例完全相同。

`scripts/validate_modern_aci_runtime.sh` 在本地 WSL2 的隔离运行树中加载本项目补丁和自定义命令，再调用冻结版 `AgentConfig.load_yaml`。验收结果为：

| 检查 | 结果 |
|---|---:|
| 静态单因素配置 | 8/8 |
| 运行时配置解析 | 8/8 |
| Bash 语法 | 1/1 |
| iterative search 导航 | 1/1 |
| no-lint edit 写回 | 1/1 |
| full-file 输出 | 1/1 |
| 模型 API 调用 | 0 |
| GPU/服务器 | 均未使用 |

运行时证据保存在 `data/manifests/modern_aci_runtime_validation.json`。该测试只证明配置可加载和重建命令达到声明行为，不证明模型效果。

## 5. 配对运行设计与资源投影

`data/manifests/modern_aci_dev20_pairing.json` 固定八个变体与 20 个基线实例的笛卡尔积。每条计划记录包含变体、实例、配置 SHA-256、计划 run ID、配对基线 run ID、基线结果和当前状态。新增运行总量为 160 个 episode，25 次/实例的硬调用上限为 4,000 次。

用现有 dev20 基线均值进行线性外推：

| 指标 | 160 个新增 episode 投影 |
|---|---:|
| 持久化调用数 | 3,176 |
| 资源审计调用数 | 3,184 |
| input tokens | 43,975,576 |
| output tokens | 563,240 |
| 最大调用数 | 4,000 |
| 美元成本 | 未知 |

SQLFluff 1763 有一次 usage 未持久化，因此 token 与基于轨迹的调用投影均按下界解释。未核验中转输入/输出单价、缓存规则、失败请求计费和总预算前，不执行 160 条计划。

## 6. 执行门与防误触入口

只查看单个变体的计划不会调用 API：

```bash
bash scripts/run_modern_aci_batch.sh no_search gpt-5.6-terra 1 25 plan
```

`execute` 模式同时要求：

- `SWE_AGENT_PAID_RUN_AUTHORIZATION=APPROVED`；
- `SWE_AGENT_INPUT_PRICE_PER_MILLION`；
- `SWE_AGENT_OUTPUT_PRICE_PER_MILLION`；
- `SWE_AGENT_INVOCATION_BUDGET_USD`；
- 本次 ceiling 不低于按 dev20 token 均值估计费用的 1.25 倍。

上述门只防止无意启动，不把统计下界变成提供商账单上限。正式执行仍需先取得可核验定价和明确总预算授权。运行入口会把配置 SHA-256 和复制的命令资产 SHA-256 写入每条 `run_manifest.txt`，且不记录凭据。

## 7. 统计预注册

主要结果固定为 evaluator 的 `RESOLVED_FULL`。空预测、格式退出、调用上限退出、patch 冲突和真实未解决均保留在 20 个实例分母中；只有零模型响应的基础设施故障允许带后缀重试。

每个变体与冻结默认基线进行：

1. 报告绝对解决率、20 个配对结果和胜/负/平数；
2. 执行双侧 exact McNemar 检验；
3. 八个主要比较使用 Holm family-wise 校正；
4. 使用 seed 42 的 10,000 次成对 bootstrap 估计解决率差区间；
5. 单独报告 `NOT_GENERATED`、`PATCH_APPLY_FAILED`、`RESOLVED_PARTIAL` 和 `RESOLVED_NO`；
6. 报告调用、input/output token、turn 和退出条件的配对差。

样本量 20 只适合方向性现代复验。结果不得与论文 Lite test 300 条的 18.0% 直接做同分布显著性比较，也不得据此更新 exact 完成状态。

## 8. 当前终态

本阶段终态为 `READY_BLOCKED_PRICE_AND_BUDGET`：配置生成、单因素检查、冻结解析器验收和配对清单均已完成；付费运行与统计结果尚未产生。无需 GPU或服务器，阻塞项是定价与支出授权，而不是计算硬件。
