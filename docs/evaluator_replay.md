# 论文期 SWE-bench 评测聚合器重放

## 1. 结论

论文主实验的八组官方预测、评测日志和 `results.json` 已完成逐列表重放。固定论文期 evaluator 源码和 2024-04-15 数据集 revision 后，八组报告的十个类别列表均与官方 JSON **完全相同**，包括列表顺序、重复实例和重复次数：

- Lite：SWE-agent GPT-4、SWE-agent Claude 3 Opus、RAG GPT-4、RAG Claude 3 Opus；
- Full：SWE-agent GPT-4、SWE-agent Claude 3 Opus、RAG GPT-4、RAG Claude 3 Opus；
- 验收结果：`8/8` full-report exact match。

这项结果证明官方工件可以在不重新调用模型的情况下稳定重建，也定位了论文期 evaluator 与后续数据 revision 之间的判分漂移。它属于**历史日志与结果聚合重放**，尚不等同于从 prediction patch 重新创建全部容器并执行全部测试。下一层代表性验证已覆盖两个核心容器结果和五条边界输入：核心逐测试结果 `2/2` 完全相同，gold、no-apply、空字符串、null 与重复行状态 `5/5` 完全相同。

## 2. 冻结输入

| 输入 | Revision | 日期 | 完整性证据 |
|---|---|---:|---|
| 官方预测、日志与结果 | `SWE-bench/experiments@a5d52722965c791c0c04d18135f906b44f716d39` | 2024-05-14 | Git blob SHA 与既有官方工件清单 |
| 历史聚合器 | `SWE-bench/SWE-bench@cfb20092bbbee9683176177b2f59b85f522e7f27` | 2024-04-16 | `get_model_report` 源码 SHA-256 `c41a4bcfb734793ff1352439e4e10de87e3c10a1714c4d7ff6ae90c8eced8173` |
| Lite 测试参考 | `princeton-nlp/SWE-bench_Lite@81ad348adcaf3368691f4db2907f8fc97a8f7526` | 2024-04-15 | Parquet SHA-256 `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1` |
| Full 测试参考 | `princeton-nlp/SWE-bench@283547aced6224d4adbe55c678b4c9c43fe7d501` | 2024-04-15 | Parquet SHA-256 `831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020` |

历史 evaluator 源码的版本字符串仍为 `1.1.0`，但使用的提交晚于 `Release 1.1.0` 提交。仅记录或安装包版本号不足以恢复相同语义，因此仓库新增 `code/SWE-bench` 子模块并直接固定源码提交。

## 3. 历史聚合语义

源码审计和完整列表比对共同确认以下行为：

1. `all_preds.jsonl` 按行、按原顺序处理，不按 `instance_id` 去重；
2. `model_patch=null` 和仅含空白的字符串均进入 `no_generation`；
3. 每条非空预测通过 `<instance_id>.<run>.eval.log` 查找日志；重复预测行复用同一日志，但会再次追加分类；
4. `pred_try` 或 `pred_minimal_try` 任一应用失败标记出现，就进入 `no_apply`；
5. 只有 `RESOLVED_FULL` 进入 `resolved`；
6. JSONL 行数、唯一实例数、数据集分母和类别列表长度是四种不同口径，不能互换。

先前“应按实例 ID 去重”的假设不符合历史实现，已经撤销。尤其是 Claude Full：官方 `resolved` 有 241 个列表条目，但只有 213 个唯一实例；241 是历史报告的真实列表长度，不能先去重后再声称复现了官方 JSON。

## 4. 八组预测与日志覆盖

| Split / run | 预测行 | 唯一实例 | 重复行 | null / 空串 | 唯一日志 | resolved 条目 / 唯一实例 | 论文期完整匹配 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Lite SWE-agent GPT-4 | 302 | 299 | 3 | 16 / 2 | 284 | 54 / 54 | 是 |
| Lite SWE-agent Claude | 300 | 300 | 0 | 26 / 3 | 271 | 35 / 35 | 是 |
| Lite RAG GPT-4 | 300 | 300 | 0 | 0 / 0 | 300 | 8 / 8 | 是 |
| Lite RAG Claude | 300 | 300 | 0 | 0 / 0 | 300 | 13 / 13 | 是 |
| Full SWE-agent GPT-4 | 2,283 | 2,266 | 17 | 124 / 30 | 2,129 | 286 / 286 | 是 |
| Full SWE-agent Claude | 2,576 | 2,266 | 310 | 233 / 0 | 2,063 | 241 / 213 | 是 |
| Full RAG GPT-4 | 2,294 | 2,294 | 0 | 0 / 0 | 2,294 | 30 / 30 | 是 |
| Full RAG Claude | 2,287 | 2,287 | 0 | 0 / 0 | 2,287 | 87 / 87 | 是 |

脚本只从旧 Git 树流式读取预测实际引用的唯一日志。八组共物化 9,928 份唯一日志，完成一组后立即删除临时副本；轨迹和无关重试日志不参与聚合。原始 Git blob、数据 Parquet 和 evaluator 源码分别进行 SHA-256 或提交哈希验证。

## 5. 数据集 revision 漂移

为验证“当前数据”是否可以替代论文数据，使用固定的 2025-03-03 快照再次执行相同聚合器：

- Lite `6ec7bb89...` 相比论文 revision 有 12 个实例的测试参考变化；
- Full `e48e2bd1...` 相比论文 revision 有 81 个实例的测试参考变化；
- 八组中只有 6 组仍与官方报告完整一致。

两组 Full 报告发生 resolved 漂移：

| Run | 官方/论文 revision | 2025 revision | 新增 resolved |
|---|---:|---:|---|
| SWE-agent Claude Full | 241 | 243 | `sympy__sympy-11384`, `sympy__sympy-12906` |
| RAG GPT-4 Full | 30 | 32 | `sympy__sympy-12906`, `sympy__sympy-13001` |

三个实例的变化均由 `PASS_TO_PASS` 参考变化触发。由此可见，直接加载 Hugging Face 最新 revision 会把历史官方结果静默改写；正式论文口径必须同时固定代码、预测、日志和数据测试参考。

## 6. 可重复执行命令

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/replay_official_evaluator.py
```

冷缓存运行约 9 分钟，主要开销为从历史 Git pack 物化日志和两次解析日志；没有模型请求、API 费用或 GPU 需求。下载后的四个固定 Parquet 及最小测试参考 JSONL 保存在 Git 忽略的 `data/cache/paper_evaluator/`。再次运行可加 `--offline`，强制只使用哈希已验证缓存。

机器可读结果为 `data/manifests/official_evaluator_replay.json`，其中包含：

- 四个数据文件的 revision、大小、SHA-256 和测试参考差异；
- 八组预测的重复行、空补丁、缺失实例和逐次 patch 哈希；
- 每个官方类别的条目数、唯一实例数及完整列表比较；
- 论文 revision 与 2025 revision 的逐实例判分差异。

### 6.1 代表实例的容器级重新执行

在聚合层通过后，固定 pytest 4.4 的两个官方 GPT-4 Lite 预测作为最小核心分支集：

| 实例 | 官方状态 | 目标测试 | 容器重放 | 逐测试列表 |
|---|---|---:|---|---|
| `pytest-dev__pytest-5227` | `RESOLVED_FULL` | F2P 3，P2P 34 | `RESOLVED_FULL` | 完全相同 |
| `pytest-dev__pytest-5221` | `RESOLVED_NO` | F2P 2，P2P 170 | `RESOLVED_NO` | 完全相同 |

两个实例来自同一 `pytest-dev/pytest` 4.4 环境，在一次 testbed 构建中顺序执行。evaluator 对两个基线提交分别完成 reset、`pred_try` 检查与回退、项目安装、benchmark test patch、prediction patch 和测试命令。所有步骤成功，新的 FAIL_TO_PASS / PASS_TO_PASS 成功与失败列表均和官方历史日志完全相同，最终状态为 `2/2` exact outcome match。

实际容器运行墙钟时间 607.6 秒，其中 Miniconda 下载、仓库 clone、环境创建和首次安装约占 529 秒；两个测试命令分别约 1.6 秒和 6.1 秒。没有模型调用或 GPU。执行命令：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_container_replay.py prepare

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/run_local_evaluation.py `
  outputs/evaluation/official_container_replay/pytest44_sweagent_gpt4/all_preds.jsonl `
  --dataset outputs/evaluation/official_container_replay/pytest44_sweagent_gpt4/tasks.jsonl `
  --results outputs/evaluation/official_container_replay/results `
  --testbed /home/gugabobo/sb `
  --timeout 900 `
  --model-alias paper_replay_pytest44_gpt4

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_container_replay.py collect
```

机器清单为 `data/manifests/official_container_replay.json`。原始新日志、scorecard、冻结预测和两行完整任务数据位于 Git 忽略的 `outputs/evaluation/official_container_replay/`；清单记录其 SHA-256 和解析后判定。

### 6.2 evaluator 边界分支

边界集由官方历史输入和论文期 Lite 数据直接构造，不改写 patch 内容：

| Profile / 输入 | 行数 | testbed 中执行 | 预期状态 | 结果 |
|---|---:|---:|---|---|
| 空字符串 `django__django-13964` | 1 | 0 | `not_generated` | 精确匹配 |
| null `psf__requests-863` | 2（重复行） | 0 | 两行均为 `not_generated` | 精确匹配，重复保留 |
| gold `pytest-dev__pytest-5227` | 1 | 1 | `generated, applied, RESOLVED_FULL` | 精确匹配，全部 F2P/P2P 通过 |
| RAG no-apply `pytest-dev__pytest-5221` | 1 | 1 | `generated` | 精确匹配，两条 patch 应用路径均失败 |

空/null profile 由 wrapper 在进入 testbed 前产生三个 scorecard，墙钟 2.7 秒；输出保持两个相同 `psf__requests-863` 行，没有去重，也没有生成评测日志。gold/no-apply profile 在同一个 pytest 4.4 testbed 中依次执行：gold patch 完成 reset、安装、test patch、prediction patch 和测试，判为 `RESOLVED_FULL`；官方 RAG patch 在 `pred_try` 与 `pred_minimal_try` 均出现应用失败标记，scorecard 只保留 `generated`。正式重试墙钟 48.7 秒。

gold/no-apply 的首次尝试在 Git clone 阶段因 HTTP/2 RPC early EOF 终止，发生在环境创建、补丁应用和测试之前，模型调用为 0。该尝试按协议标为 `EXP-ARTIFACT-006B-A`，不进入正式分母，原输入和失败 scorecard 保存在 Git 忽略的 `outputs/evaluation/official_container_replay/invalid_attempts/`。随后保持 prediction 与 task SHA-256 不变，仅为 Git 子进程临时设置 `http.version=HTTP/1.1`，`EXP-ARTIFACT-006B-B` 成功。没有修改全局 Git 配置。

执行命令：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_evaluator_edge_replay.py prepare empty_duplicate

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/run_local_evaluation.py `
  outputs/evaluation/official_container_replay/empty_duplicate/all_preds.jsonl `
  --dataset outputs/evaluation/official_container_replay/empty_duplicate/tasks.jsonl `
  --results outputs/evaluation/official_container_replay/results `
  --testbed /home/gugabobo/sb `
  --timeout 900 `
  --model-alias paper_replay_empty_duplicate

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_evaluator_edge_replay.py collect empty_duplicate
```

`gold_no_apply` 使用相同三步，把 profile 与 model alias 分别替换为 `gold_no_apply` 和 `paper_replay_gold_no_apply`。若 clone 端点再次出现 HTTP/2 传输错误，只对该次零模型响应的基础设施尝试使用进程级 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=http.version`、`GIT_CONFIG_VALUE_0=HTTP/1.1`，并保留失败尝试。

机器可读证据为：

- `data/manifests/official_evaluator_edge_replay.json`：正式/无效尝试、冻结哈希、分支覆盖与总验收；
- `data/manifests/official_empty_duplicate_replay.json`：三行 scorecard 的逐行对照；
- `data/manifests/official_gold_no_apply_replay.json`：新 evaluator 日志、应用标记与 gold 全测试判定。

### 6.3 逐仓库 gold 环境验证预注册

论文期 Lite 与 Full 均只包含同一组 12 个仓库。当前 `SWE-bench@cfb20092` 虽还带有后续扩展仓库常量，但不把数据集中不存在的仓库加入论文覆盖分母。

在执行新环境前固定以下选择规则：对每个仓库，优先在官方 GPT-4 Lite `resolved` 实例中选择 `FAIL_TO_PASS + PASS_TO_PASS` 引用最少者；若该仓库没有官方 resolved 实例，则在全部 Lite 实例中选择引用最少者；并依次以 gold patch 字节数和 instance ID 打破平局。该规则得到：

| 仓库 | 固定实例 | version | F2P + P2P | 选择来源 |
|---|---|---:|---:|---|
| astropy/astropy | `astropy__astropy-14995` | 5.2 | 1 + 179 | 官方 resolved |
| django/django | `django__django-13447` | 4.0 | 1 + 5 | 官方 resolved |
| matplotlib/matplotlib | `matplotlib__matplotlib-23964` | 3.6 | 1 + 16 | 官方 resolved |
| mwaskom/seaborn | `mwaskom__seaborn-3010` | 0.12 | 1 + 2 | 官方 resolved |
| pallets/flask | `pallets__flask-4992` | 2.3 | 1 + 18 | Lite 最小；无官方 resolved |
| psf/requests | `psf__requests-2317` | 2.4 | 8 + 133 | 官方 resolved |
| pydata/xarray | `pydata__xarray-4248` | 0.12 | 1 + 18 | Lite 最小；无官方 resolved |
| pylint-dev/pylint | `pylint-dev__pylint-5859` | 2.13 | 1 + 10 | 官方 resolved |
| pytest-dev/pytest | `pytest-dev__pytest-5227` | 4.4 | 3 + 34 | 官方 resolved；复用 EXP-ARTIFACT-006 gold |
| scikit-learn/scikit-learn | `scikit-learn__scikit-learn-13584` | 0.21 | 6 + 3 | 官方 resolved |
| sphinx-doc/sphinx | `sphinx-doc__sphinx-8713` | 4.0 | 1 + 45 | 官方 resolved |
| sympy/sympy | `sympy__sympy-24152` | 1.12 | 1 + 6 | 官方 resolved |

`scripts/official_gold_repository_replay.py prepare` 从固定 Parquet 直接写入未修改 gold patch 和完整任务行。选择清单 `data/manifests/official_gold_repository_selection.json` 记录数据/代码 revision、base commit、gold/test patch SHA-256、输入 JSONL SHA-256 和 10 份可对照的官方 resolved 日志 blob。

执行采用每仓库一个独立 evaluator 进程，避免单个依赖安装失败终止其余仓库。每次使用论文期 SWE-agent evaluator、`SWE-bench@cfb20092`、900 秒任务超时和本地临时 Miniconda；Git 仅在该进程中固定 HTTP/1.1，不修改全局配置。runner 显式移除继承环境中的模型端点与凭据变量，模型 API 调用固定为 0。每个失败尝试单独保存完整 runner 日志、scorecard、eval log、开始/结束时间和哈希，不覆盖历史尝试。

预注册验收要求为每个 gold patch 均得到 `generated, applied, RESOLVED_FULL`，F2P/P2P 引用全部通过；10 个有官方 resolved 日志的实例还要求新 gold report 与官方 report 完整相等。pytest 在预注册时已经满足要求，其余 11 个仓库随后按固定顺序执行；结果及外网例外见 6.4。

### 6.4 逐仓库 gold 环境验证结果

12 个论文期仓库的环境覆盖已经完成。10 个仓库在新建环境中得到全部 reference outcome，pytest 复用 EXP-ARTIFACT-006 的已冻结 gold 证据；Requests 的 141 个 reference outcome 中有 140 个直接通过，唯一失败项依赖不可达的公共跨站 HTTP 服务，另由相同 base/gold/test patch 上的本地双主机重定向验证确认 Authorization header 被正确剥离。

| 仓库 | reference 结果 | attempts | 最终分类 | 实例级兼容 |
|---|---:|---:|---|---|
| astropy/astropy | 180/180 | 3 | full reference | `setuptools==68.0.0` |
| django/django | 6/6 | 2 | full reference | 无 |
| matplotlib/matplotlib | 17/17 | 5 | full reference | Ghostscript、TeX、dvipng 系统包 |
| mwaskom/seaborn | 3/3 | 3 | full reference | 无 |
| pallets/flask | 19/19 | 2 | full reference | 无 |
| psf/requests | 140/141 + 1/1 semantic | 3 | external-network semantic | 本地 `127.0.0.1 → localhost` 跨主机重定向 |
| pydata/xarray | 19/19 | 6 | full reference | libmamba；官方验证版本的 NumPy/pytest/setuptools |
| pylint-dev/pylint | 11/11 | 2 | full reference | 删除已下架且仅供 typing 的 stub |
| pytest-dev/pytest | 37/37 | 复用 | full reference | 无 |
| scikit-learn/scikit-learn | 9/9 | 1 | full reference | 无 |
| sphinx-doc/sphinx | 46/46 | 2 | full reference | 官方验证使用的 `setuptools==69.5.1` |
| sympy/sympy | 7/7 | 1 | full reference | 无 |

直接 reference outcome 合计 494/495；Requests 剩余 1 项的语义验证通过后，仓库级环境覆盖为 12/12。机器清单同时保留两种结论：`exact_outcome_match_count=11`、`semantic_outcome_match_count=1`，不会把外网替代验证改写成 `RESOLVED_FULL`。

11 个新仓库共保存 30 次尝试，其中 10 次为协议有效的最终 `RESOLVED_FULL`。其余尝试包括早期错误导入已安装 SWE-bench、Git/依赖安装失败、Matplotlib 缺少排版工具、Requests 公网漂移、xarray 中断及经典 conda solver 资源保护、Pylint 下架 typing stub、Sphinx 缺失 `pkg_resources`。xarray 的经典 solver 峰值 RSS 约 19.5 GiB，系统可用内存降至 116 MiB 后按 1 GiB 保护阈值终止；后续 libmamba 在不改变依赖声明的情况下完成环境求解。每次尝试的时间、状态、return code、协议有效性、日志哈希和模型调用数均纳入汇总清单。

Requests 的公共 `httpbin.org` 与 Google 跨站端点在当前网络持续 reset/timeout。语义验证在 base commit `091991be...` 上应用同一 gold/test patch，使用 `127.0.0.1` 发起带 Basic Authorization 的 302，再重定向到 `localhost`；初始请求有 Authorization，最终请求在客户端和服务端均无 Authorization，HTTP 200、history 长度 1。该结果只补足单个外网语义，不改变原 scorecard 的 `RESOLVED_NO`。

正式命令为：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_gold_repository_replay.py run `
  --repository <owner/repo> --timeout 1800 --conda-solver libmamba

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  /home/gugabobo/.venvs/swebench-paper-eval/bin/python `
  scripts/official_gold_repository_replay.py collect
```

机器输出为 `data/manifests/official_gold_repository_replay.json`、`data/derived/official_gold_repository_replay.csv` 和 `data/manifests/requests_offhost_redirect_validation.json`。主清单另外固定官方 SWE-bench experiments 兼容性记录的 repository revision、Git object ID 和 SHA-256。原始 runner/eval 日志、scorecard、任务行和全部 attempt 目录保存在 Git 忽略的 `outputs/evaluation/official_gold_repository_replay/`。模型 API、GPU和远程服务器使用均为 0。

宿主 D 盘在本阶段约有 64–65 GB 空闲，低于正式 300/2,294 实例批量运行门槛。逐仓库环境在结束后清理，因此本阶段可安全顺序执行；WSL 稀疏虚拟磁盘显示的 944 GB 不再作为宿主真实容量证据。

## 7. 当前完成边界

已完成：

- 官方预测到官方 `results.json` 的历史聚合器重放；
- 论文期 evaluator 源码和数据 revision 的精确定位；
- 重复预测、空补丁、缺失实例与类别分母语义恢复；
- 后续数据 revision 引起的 resolved 漂移定位。
- 一个官方 resolved 和一个官方 applied-unresolved 预测的真实容器重放，逐测试结果 `2/2` 完全一致。
- gold、官方 patch-apply failure、空字符串、null 和重复行的代表边界验证，逐行状态 `5/5` 完全一致。
- 12 个论文期支持仓库的 gold 环境覆盖：11 个 full-reference outcome、1 个 Requests 外网语义验证，仓库级验证 12/12。

尚未完成：

- 全量 2,294/300 实例从 patch 开始的容器重评；
- 严格原模型重新推理。

因此 `G_EVALUATOR_REPLAY` 的论文仓库代表覆盖已经完成，但仍不等于全量 300/2,294 实例容器重评，更不能标为整个严格复现完成。
