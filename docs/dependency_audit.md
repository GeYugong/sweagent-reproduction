# 依赖审计

审计日期：2026-07-15

## 环境创建

论文快照的 `environment.yml` 指定 Python 3.9。服务器默认 Python 为 3.8.10，因此在项目目录内创建独立环境：

```text
/public/home/mty/GeYugong/05_sweagent_repro_ser/.venv
```

所有 conda 和 pip 缓存均重定向到：

```text
/public/home/mty/GeYugong/05_sweagent_repro_ser/.cache
```

没有修改共享 conda 环境、`.condarc` 或系统 Python。环境创建完成后：

- Python：3.9.25；
- `.venv` 大小：约 193 MB（仅基础环境测量时）；
- conda 缓存：约 143 MB（仅基础环境测量时）。

## 首次解析结果

上游 requirements 大部分没有版本上限。2026-07-15 直接执行 editable install 时解析到的关键版本包括：

- `sweagent==0.2.0`；
- `swebench==3.0.17`；
- `openai==2.45.0`；
- `anthropic==0.116.0`；
- `datasets==4.5.0`；
- `numpy==2.0.2`；
- `pytest==8.4.2`。

完整解析结果保存在 `logs/environment/pip_freeze_20260715.txt`，conda 基础包显式清单保存在 `logs/environment/conda_explicit_20260715.txt`。

## 已确认的不兼容

### SWE-bench 与 Python 3.9

`swebench==3.0.17` 在导入时使用 `list | None`，该语法要求 Python 3.10 及以上。论文环境固定为 Python 3.9，因此 pytest 在 collection 阶段报错：

```text
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

上游快照只声明 `swebench>=1.0.1`。为恢复论文期兼容性，研究约束文件把 SWE-bench 固定为 `1.0.1`。降级后 SWE-agent 与 SWE-bench 均可正常导入。

### Together 适配器与 Anthropic SDK

`test_models.py` 的 OpenAI mock 用例通过。Together 参数化用例在 `anthropic==0.116.0` 下失败：

```text
AttributeError: 'Anthropic' object has no attribute 'count_tokens'
```

论文主基线使用 GPT-4 Turbo，此失败不阻塞 GPT-4 路径，但会阻塞旧版 Together 模型适配器。后续若纳入 Together 对照，必须重建 2024 年 Anthropic SDK 约束或对适配层做独立兼容性修复；两种方案不能与论文基线混为一组。

## 测试结果

### 失败的混合 smoke 选择

最初选择 `test_parsing.py`、`test_models.py` 和完整 `test_utils.py`。其中 `test_utils.py` 含 GitHub API 与 clone 网络用例，不属于稳定的离线 smoke 集。运行 210 秒后仍停在网络部分，进程被明确终止并记录原因。

### 冻结的离线 smoke 选择

命令：

```bash
python -m pytest -q \
  code/SWE-agent/tests/test_parsing.py \
  code/SWE-agent/tests/test_utils.py \
  -k "not get_associated and not get_instance"
```

结果：

```text
16 passed, 6 deselected in 0.07s
```

### 模型适配首错测试

命令：

```bash
python -m pytest -q -x code/SWE-agent/tests/test_models.py
```

结果：1 passed，随后 Together 用例因 Anthropic SDK API 漂移失败。

### 导入与 CLI smoke

- `import sweagent`：通过；
- `import swebench`：通过，版本为 1.0.1；
- `run.py --help`：通过；
- `OPENAI_API_KEY`：未配置。

## 当前结论

论文代码的纯离线核心工具、OpenAI 适配器 mock 路径和本地 Docker 单实例均已通过。OpenAI 兼容中转接口已完成真实最小请求验证；费用接口未公开，因此只记录实际 token 数与 API 调用数，不把上游公开价或零值伪装成中转费用。

### 本地 Python 环境

- uv：0.11.28；
- Python：3.9.25；
- SWE-bench：1.0.1；
- OpenAI SDK：2.45.0；
- 论文快照验证：11/11 PASS。

### 2026 包生态漂移

`sqlfluff__sqlfluff-1625` 的历史 requirements 包含 `types-pkg_resources`。该包的 PyPI 版本已全部撤回，官方撤回说明要求改用 `types-setuptools`。运行适配补丁只在显式设置 `SWE_AGENT_COMPAT_YANKED_PACKAGES=1` 时替换该类型存根，不修改任务代码、基准提交或测试。

完成替换后，零 API 单实例成功生成轨迹和预测文件。该兼容项必须在所有相关实验报告中保留，不能将其描述为未经修改的 2024 环境。

### 推理与评测环境分离

论文快照的 agent 主路径在 `swebench==1.0.1` 下通过，但同一提交中的 `evaluation/evaluation.py` 导入 `get_eval_refs`；该符号从 PyPI 的 `swebench==1.0.2` 发布物开始提供。为避免把评测依赖升级混入推理环境，建立独立环境：

- 推理环境：Python 3.9.25、SWE-bench 1.0.1；
- 评测环境：Python 3.9.25、SWE-bench 1.0.2、unidiff 0.7.5；
- 评测脚本：论文快照的 `evaluation/evaluation.py`；
- 评测兼容项：与推理阶段相同的 `types-pkg_resources` → `types-setuptools` 替换。

首次正式评测在 Conda 包下载时发生代理 TLS 超时。第二次使用单线程下载、60 秒连接超时、180 秒读取超时、10 次重试和 classic solver 后完成。网络重试不改变数据、模型补丁或测试集合。

Marshmallow 评测又暴露两个旧 harness 问题：

1. 长 run ID 使临时 Miniconda 前缀达到 145 字符，安装器生成 `/usr/bin/env python` shebang，导致 `conda env list` 无法启动。评测器现在使用短哈希模型别名，并把结果复制回原始轨迹目录。
2. `MAP_VERSION_TO_INSTALL` 未提供 `packages` 时，1.0.2 harness 用 `split(" ")` 生成空命令参数，Conda 报无效 MatchSpec。运行时 wrapper 只过滤参数列表中的空字符串。

两项兼容均属于 testbed 启动修复，不改变预测 patch、官方 test patch、FAIL_TO_PASS 或 PASS_TO_PASS 集合。

### NumPy 2.x 与冻结 pvlib

`pvlib__pvlib-python-1707` 的首次 evaluator 环境从当前包索引安装了 NumPy 2.0.2。冻结提交仍在模块导入时引用 `np.Inf`，而 NumPy 2 已移除该别名，导致 FAIL_TO_PASS 与全部 PASS_TO_PASS 在 pytest 收集前统一失败。Agent 容器中的同一测试文件为 30/30 通过，说明这不是候选 patch 引入的回归。

论文实验早于该破坏性依赖组合，因而 evaluator wrapper 对 pvlib 实例写入并导出 `PIP_CONSTRAINT=numpy<2`。约束只作用于 evaluator 建立的隔离环境，不修改任务仓库、预测 patch、benchmark test patch 或测试集合；其他仓库不设置该约束。初次 NumPy 2 判分标记为无效评测，使用完全相同的预测重新判分。

### Docker attach 空读取竞态

`pvlib__pvlib-python-1854` 首次初始化时，容器命令已返回退出码 `0` 且后台 PID 列表为空，但旧 `read_with_timeout()` 在 `select()` 可读后得到空字节仍继续循环，最终把成功命令误报为 5 秒超时。适配补丁按 pipe EOF 语义在空读取时立即结束；已有缓冲区中的退出码随后正常解析。失败早于 Agent 初始化，API 调用为 0。

### Docker 退出码截止时间竞态

`pydicom__pydicom-1256` 初始化时出现与 pipe EOF 不同的边界情形：第二次读取已经得到退出码 `0`，最终后台 PID 列表为空，但读取后的固定退让使时钟恰好越过 5 秒截止点，旧实现因此丢弃有效退出码并抛出超时。日志中的 `Current buffer: 0` 与 `Running PIDs: []` 共同证明命令已完成。

适配层在 `TimeoutError` 上保留缓冲区和 PID 快照，并且只在 `SWEEnv._communicate()` 的退出码读取阶段接受“纯数字缓冲区且无运行 PID”的结果。首段命令输出读取没有恢复分支，仍有 PID、空缓冲区或非数字内容时也继续抛出，因此不会掩盖真实命令超时。该失败早于 Agent 初始化，API 调用为 0。

### pydicom 缺失 pytest

`swebench 1.0.x` 对 pydicom 2.0 的安装映射只有 Python 3.8 与 NumPy，没有测试运行器。当前 SWE-agent 镜像与 evaluator 的临时 Miniconda 均不预装 pytest：Agent 的自测命令报 `pytest: command not found`，evaluator 也在执行任何目标测试前以相同错误退出。

适配层只对 `pydicom/pydicom` 的安装配置补充 `pytest==7.4.4`，同时作用于 Agent 与 evaluator；其他仓库不变。首次 1139 推理在缺少预期测试能力的环境中完成，因此轨迹与判分标记为无效并完整归档，随后在修正环境中重新运行。

第二次运行最初安装了 pytest 8.4.2。目标 PersonName 测试能够运行，但完整文件中的旧式 `setup(self)` 不再执行，导致两个 PASS_TO_PASS 因 fixture 属性未初始化而失败。pydicom 自身 Git 历史在 2022-11-15 的提交 `8de0a15ef` 明确说明：因 pytest 7.2 开始弃用 `setup`/`teardown`，项目才改为 `setup_method`/`teardown_method`；冻结 benchmark 提交早于该迁移。因此选择最后一个 pytest 7 版本 7.4.4，而不是使用 2026 年最新版。

`pydicom__pydicom-901` 使用更早的 Python 3.6 环境，pytest 7.4.4 的 `Requires-Python >=3.7` 使安装在推理前失败。既有兼容矩阵已在冻结 pydicom 上验证 pytest 6.2.5 能执行旧式 setup 测试，因此适配规则按 Python 版本选择：3.6 使用 pytest 6.2.5，3.7 及以上使用 pytest 7.4.4。Agent 与 evaluator 使用同一选择规则；失败尝试 API 调用为 0。

### PyVista 0.39 与 VTK 9.6

`pyvista__pyvista-4315` 的未约束 requirements 在当前索引解析到 VTK 9.6.2。冻结 PyVista 0.39 导入 `_vtk.py` 时仍引用 `vtkCompositePolyDataMapper2`，而该类在当前 VTK wheel 中不存在，导致 Agent 自测与 evaluator 均在 pytest 插件加载阶段、目标测试收集之前失败。首次 14-call 轨迹受缺失测试反馈影响，标记为 Agent 环境无效并归档。

兼容层只对 `pyvista/pyvista` requirements 中的裸 `vtk` 改写为 `vtk<9.3`，使 resolver 选择仍提供该 API 的 VTK 9.2 系列。Agent 与 evaluator 使用同一约束；其他依赖、任务代码、benchmark patch 与测试集合不变。必须在修正环境中重新推理，不能只重判原预测。
