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
