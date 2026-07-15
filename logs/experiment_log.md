# 实验日志

## 2026-07-15 — EXP-SETUP-001：研究仓库与版本冻结

### 目的

建立 SWE-agent 复现研究的本地与服务器工作边界，固定论文与论文期代码，确认正式实验前的基础设施条件。

### 输入

- 论文：arXiv `2405.15793v3`。
- 研究方案：部分复现、现代对照与单因素改进。
- 本地根目录：`D:\0code\Research\05`。
- 服务器项目根：`/public/home/mty/GeYugong/`。

### 执行过程

1. 校验 PDF 文件头为 `%PDF-`，大小为 4,963,538 bytes。
2. 使用 Poppler/pypdf 确认 PDF 共 118 页且未加密。
3. 渲染第 1、4、6、8、25 页；视觉检查第 1、6、25 页。
4. 下载 arXiv 源码包，大小为 4,825,857 bytes。
5. 拉取 SWE-agent 上游仓库并检查 tag 时间与论文首次提交时间。
6. 找到首次提交前最后一个上游提交 `658eb2842e8a8b00069b301338bc342b70538f7a`。
7. 核对该提交中 `config/default.yaml` 使用 `Last5Observations`，并存在 100 行窗口配置。
8. 审计服务器 GPU、内存、CPU、磁盘、Python、Git、conda、容器与调度器。

### 观察

- `v0.7.0` 的 README 报告 Lite 23%，与论文主表 18% 不一致，不能作为严格论文基线。
- 论文首次提交前快照与论文描述的默认 ACI 结构一致，选为 paper snapshot。
- 服务器可见 6 张 A40，但研究资源约束固定为 2 张。
- 服务器没有可用 Docker 或其他容器命令，无法立即执行正式 SWE-bench 判分。
- 文件系统使用率为 98%，大规模镜像与权重下载存在空间风险。
- 默认 Python 3.8.10 不满足论文快照 Python >=3.9 的要求。

### 决策

- 论文版代码固定到 `658eb2842e8a8b00069b301338bc342b70538f7a`。
- 容器问题解决前不运行 SWE-bench 正式评测。
- 服务器只在独立目录 `05_sweagent_repro_ser` 中工作。
- 所有正式批次在执行前冻结实例清单、配置与预算。

### 状态

`PARTIAL`：版本与研究协议已冻结；正式单实例闭环受容器后端缺失阻塞。

## 2026-07-15 — EXP-SETUP-002：论文配置逐字段核对

### 目的

确认论文附录中的模型、上下文、窗口和 ACI 组件能够映射到论文期代码快照中的具体字段。

### 执行过程

1. 读取 `config/default.yaml` 的 system、instance、demonstration 和 next-step 模板。
2. 核对 `WINDOW=100`、`Last5Observations`、`edit_linting.sh` 和 `search.sh`。
3. 检查 `run.py` 中模型、temperature、top-p 和单实例费用上限的默认值。
4. 检查 `models.py` 中 `gpt4` shortcut 的 API 模型映射。

### 结果

- `gpt4` 映射到 `gpt-4-1106-preview`。
- temperature 为 0.0，top-p 为 0.95，单实例费用上限为 3 美元。
- 文件窗口、最近五次观察、demonstration、linting 编辑器和摘要式搜索均与论文描述一致。
- 逐字段结果写入 `docs/config_alignment.md`。

### 状态

`COMPLETE`：论文配置与代码字段的静态对齐已完成。

## 2026-07-15 — EXP-SETUP-003：服务器隔离环境与依赖漂移审计

### 目的

在不修改共享环境的前提下建立论文声明的 Python 3.9 环境，并验证 2026 年依赖解析能否直接运行论文快照。

### 执行过程

1. 将 conda 和 pip 缓存重定向到项目内 `.cache`。
2. 在项目内 `.venv` 创建 Python 3.9 环境。
3. editable 安装论文快照与 pytest。
4. 保存 pip freeze 与 conda explicit 清单。
5. 运行静态导入与 pytest smoke。

### 首次失败

pip 将无上限的 `swebench>=1.0.1` 解析为 3.0.17。该版本使用 Python 3.10 类型语法，在 Python 3.9 下导入失败。失败发生在测试 collection 阶段，不是 SWE-agent 逻辑失败。

### 修正

新增 `conf/paper_requirements_constraints.txt`，将 SWE-bench 固定为 1.0.1。修正后 `sweagent`、`swebench` 和 CLI help 均通过。

### 其他发现

- OpenAI mock 用例通过。
- Together 适配器与 2026 年 Anthropic SDK 不兼容，首错为缺少 `count_tokens`。
- 初始混合 smoke 集误含 GitHub 网络测试，210 秒后终止；后续冻结为纯离线选择。
- 纯离线测试结果为 16 passed、6 deselected。
- 服务器未配置 `OPENAI_API_KEY`，没有产生 API 调用或费用。

### 状态

`COMPLETE_WITH_LIMITATIONS`：论文主路径可导入且离线工具测试通过；Together 适配器仍存在依赖漂移，正式评测仍缺容器后端。

## 2026-07-15 — EXP-SMOKE-001：论文快照自动验证

### 目的

自动验证本地与服务器均处于论文期提交，并防止配置在后续实验中静默漂移。

### 方法

执行 `scripts/verify_paper_snapshot.py`，核对上游 commit、100 行窗口、最近五次观察、命令集合、demonstration、解析器、模型映射、temperature、top-p 和费用上限。

### 结果

本地与服务器均通过全部 11 项检查，状态为 `PASS`。

### 状态

`COMPLETE`。

## 2026-07-15 — EXP-SETUP-004：容器后端兜底检查

### 目的

排除容器运行时已安装但未加入 PATH 的情况。

### 检查项

- `/var/run/docker.sock` 与 `/run/docker.sock`；
- `module`/`modulecmd` 及可加载的容器模块；
- `/usr/bin`、`/usr/local/bin` 和 `/opt` 下常见 Docker、Podman、Apptainer、Singularity 路径；
- 当前用户组。

### 结果

未发现 Docker socket、Environment Modules 或任何常见容器运行时可执行文件。当前用户组也不包含 docker 类组。容器后端缺失被确认为外部基础设施阻塞，而不是 PATH 配置问题。

### 状态

`BLOCKED_EXTERNAL`：需要管理员提供容器后端，或把正式评测迁移到另一台已授权的 Docker 主机。

## 2026-07-15 — EXP-LOCAL-001：本地 WSL2 与 Docker 环境

### 目的

建立不依赖服务器权限、无需本地模型显卡的单实例执行环境。

### 执行过程

1. 将 Ubuntu WSL2 发行版迁移到 `D:\2software\WSL\Ubuntu`，迁移前导出备份。
2. 将 WSL2 限制为 20 GiB 内存、16 个处理器和 8 GiB swap。
3. 按 Docker 官方 Ubuntu 安装流程部署 Docker Engine 29.6.1。
4. 为 Docker daemon 配置本机 HTTP 代理，完成 `hello-world` 拉取与运行。
5. 拉取论文快照所需 `sweagent/swe-agent:latest`，记录镜像摘要。
6. 使用 uv 0.11.28 安装 Python 3.9.25，创建隔离环境并固定 `swebench==1.0.1`。
7. 运行论文快照验证脚本，11 项检查全部通过。

### 结果

本地容器与 Python 环境可用。模型推理被明确放在远程 API，RTX 4060 未参与实验。

### 状态

`COMPLETE`。

## 2026-07-15 — EXP-API-001：OpenAI 兼容接口验证

### 目的

验证中转接口是否兼容论文快照使用的 Chat Completions 调用方式。

### 方法

- 探测 `/v1/models` 和 `/models`；
- 对候选模型发送固定最小请求：`temperature=0.0`、`top_p=0.95`；
- 只保存接口状态、模型名、响应结构和 token 统计，不保存密钥。

### 结果

- 模型列表接口返回 OpenAI 兼容结构；
- `gpt-5.4-mini`、`gpt-5.4` 与 `gpt-5.6-terra` 均通过旧版 Chat Completions；
- `gpt-5.6-terra` 返回 HTTP 200 和精确文本 `OK`；
- 该请求使用 307 个输入 token、5 个输出 token，共 312 个 token；
- 中转价格未通过公开接口获得，因此不报告推测费用。

### 决策

现代复现实验主模型使用 `gpt-5.6-terra`，低成本连通 smoke 使用 `gpt-5.4-mini`。论文原始结果仍标注为 `gpt-4-1106-preview`，不得把现代模型结果称为原论文分数复现。

### 状态

`COMPLETE`。

## 2026-07-15 — EXP-LOCAL-002：零 API 单实例闭环

### 目的

在产生模型费用前验证 SWE-bench Lite 的本地完整执行链路。

### 实例与配置

- 实例：`sqlfluff__sqlfluff-1625`；
- split：dev；
- 模型：`instant_empty_submit`；
- API 费用上限：0；
- 预期 API 调用数：0。

### 失败 1：基础镜像缺失

论文快照不会自动拉取 `sweagent/swe-agent:latest`。首次运行在创建容器前失败。拉取固定摘要镜像后进入容器初始化。

### 失败 2：容器内 GitHub 超时

Docker daemon 能通过代理拉取镜像，但实验容器没有继承代理。`git clone` 在 500 秒读取窗口内超时。运行补丁通过 `--network host` 注入大小写代理环境变量；独立命令 `git ls-remote` 随后通过。

### 失败 3：撤回的历史依赖

SQLFluff 历史 requirements 使用 `types-pkg_resources`，当前 PyPI 已撤回其全部版本。依据官方撤回说明，显式启用兼容开关，将其替换为 `types-setuptools`。

### 最终结果

- 容器初始化：通过；
- GitHub clone：通过；
- Conda 环境与项目安装：通过；
- 任务 reset 与 agent loop：通过；
- 轨迹、patch 与 `all_preds.jsonl`：均成功落盘；
- `api_calls=0`、`tokens_sent=0`、`tokens_received=0`；
- 最终成功轮墙钟时间：约 336 秒（冷启动）。

### 状态

`COMPLETE`。本地单实例链路具备进入真实 API 试运行的条件。

## 2026-07-15 — EXP-API-PILOT-001：8 次调用真实 API pilot

### 目的

验证 `gpt-5.6-terra` 在论文 ACI 中的真实交互质量，并在低调用上限下观察是否出现循环、接口错误或格式错误。

### 配置

- 实例：`sqlfluff__sqlfluff-1625`；
- temperature：0.0；
- top_p：0.95；
- API 调用上限：8；
- 费用字段：0，仅表示中转价格未知；
- 预算证据：调用次数与 token。

### 结果

模型完成问题复现、L031 定位、实现与 fixture 阅读以及 TSQL parse tree 检查。8 个模型响应均有推进，没有重复循环。累计输入 73,004 token、输出 848 token。第 9 个 agent 步骤在请求前触发调用上限，以 `exit_cost` 结束，没有生成 patch。

### 状态

`BUDGET_TRUNCATED`。接口和 ACI 行为正常，预算不足以完成修改。

## 2026-07-15 — EXP-API-BASELINE-001：25 次调用真实 API 基线

### 目的

在冻结的正式单实例预算内生成补丁，并用论文快照 evaluator 判断是否 resolved。

### 推理结果

- API 调用：25；
- 输入 token：270,910；
- 输出 token：3,248；
- agent 步骤：26；
- 首次到末次 API 响应窗口：约 177 秒；
- 端到端墙钟时间：约 503 秒；
- exit status：`submitted (exit_cost)`；
- patch：成功生成，修改 `src/sqlfluff/rules/L031.py`，+5/-1 行。

候选补丁在 TSQL 且不存在 JOIN 时直接跳过 L031。该实现响应了 issue 的自然语言描述，但没有修改违规消息。

### 评测环境发现

论文快照 evaluator 依赖 `get_eval_refs`，而推理环境的 SWE-bench 1.0.1 没有该导出。逐版本核对 PyPI 发布物后，建立 SWE-bench 1.0.2 独立评测环境，并补入直接依赖 unidiff 0.7.5。

首次评测在 Conda 下载阶段因代理 TLS 超时失败，没有执行测试。使用单线程下载、延长超时、10 次重试和 classic solver 后，第二次评测完成。

### 正式判分

- patch apply：成功；
- 测试总数：69；
- 通过：68；
- 失败：1；
- FAIL_TO_PASS 失败项：`test/cli/commands_test.py::test__cli__command_directed`；
- SWE-bench 判定：`RESOLVED_NO`。

### 失败归因

官方 test patch 和 gold patch 都只要求把 L031 的描述改为“from clauses and join conditions”，而不是停止对无 JOIN 查询报告违规。模型按 issue 文本改变触发逻辑，与 benchmark 的实际目标不一致。失败分类为 `ISSUE_GOLD_BEHAVIOR_MISMATCH`，同时保留 `BUDGET_LIMIT_AUTOSUBMIT` 标签。

### 状态

`COMPLETE`：推理、patch、正式测试与失败归因均已完成；resolved=0。

## 2026-07-15 — EXP-DEV20-SETUP-001：dev20 清单冻结

### 目的

在扩大实验前固定实例集合，防止按运行结果临时挑选任务。

### 数据获取

Hugging Face Dataset Viewer 的 `/splits` 与 `/rows` 连续返回 HTTP 503。改用本机已缓存的 `princeton-nlp/SWE-bench_Lite` revision `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`，未切换数据版本。

### 选择方法

1. 读取 dev split 的 23 个 instance ID；
2. 按字符串排序；
3. 使用 `random.Random(42).sample(ids, 20)`；
4. 对选中结果排序；
5. 将剩余 3 个实例记录为 holdout。

重新计算验证通过。清单保存在 `data/manifests/swebench_lite_dev20_seed42.json`。

### 状态

`COMPLETE`。

## 2026-07-15 — EXP-DEV20-001：Marshmallow 正式基线

### 实例与配置

- 实例：`marshmallow-code__marshmallow-1343`；
- 模型：`gpt-5.6-terra`；
- ACI：论文默认配置；
- API 调用上限：25；
- temperature：0.0；
- top_p：0.95。

### 推理结果

- API 调用：22；
- 输入 token：243,975；
- 输出 token：2,750；
- agent 步骤：20；
- API 响应窗口：约 173 秒；
- 端到端墙钟时间：约 678 秒；
- exit status：`submitted`。

模型复现 nested schema 错误后，在 `BaseSchema._do_load()` 中增加 `result is not None` 条件，并添加回归测试。agent 自测通过后主动提交。

### 评测失败尝试 1：Miniconda 前缀过长

原始 run ID 进入 testbed 路径后，Miniconda 前缀长度达到 145 字符。生成的 conda 脚本使用 `/usr/bin/env python`，但系统 PATH 中没有可用于该前缀的 `python`，评测在执行测试前失败。

修正：以预测目录名的 SHA-256 前 8 位生成短模型别名，使用短 testbed 根，并在结束后把 scorecard/results 复制回原始轨迹目录。

### 评测失败尝试 2：空 package 参数

SWE-bench 1.0.2 对 Marshmallow 2.20 未配置额外 Conda packages。旧 harness 将命令字符串按空格拆分，向 `conda create` 传入空字符串，产生无效 MatchSpec。

修正：运行时只从 list 形式的 subprocess 参数中移除空字符串。

### 正式判分

- patch apply：成功；
- FAIL_TO_PASS：1/1；
- PASS_TO_PASS：24/24；
- 总目标测试：25/25；
- SWE-bench 判定：`RESOLVED_FULL`。

### 状态

`COMPLETE`：resolved=1。

## 2026-07-15 — EXP-DEV20-003A：pvlib 1154 环境失败

### 目标

运行冻结清单中的下一个实例 `pvlib__pvlib-python-1154`，保持 `gpt-5.6-terra`、论文 ACI 与 25 次调用上限不变。

### 失败位置

任务仓库 clone 成功，失败发生在容器内创建 Conda 环境。Conda 并行下载 Python、NumPy、Pandas、SciPy、OpenBLAS 等包时，代理多次出现 TLS handshake timeout，最终返回 ProxyError。

失败早于 agent 推理：没有 API 调用，没有实例轨迹，没有预测 patch，也没有启动正式 evaluator。因此该尝试不进入 dev20 的已评测分母。

### 同时发现的运行器缺陷

SWE-agent 在环境失败后仍创建了 run 目录和 `args.yaml`。旧运行器只检查目录是否存在，随后把空目录复制为实验输出，可能误报成功。

### 修正

1. agent 容器增加 `CONDA_REMOTE_CONNECT_TIMEOUT_SECS=60`；
2. 增加 `CONDA_REMOTE_READ_TIMEOUT_SECS=180`；
3. 增加 `CONDA_REMOTE_MAX_RETRIES=10`；
4. 设置 `CONDA_DEFAULT_THREADS=1` 与 `CONDA_SOLVER=classic`；
5. 运行器必须同时找到非空的 `<instance_id>.traj` 与 `all_preds.jsonl` 才接受推理完成。

修正已提交。当前宿主执行会话随后无法访问 WSL 服务，最小 `wsl ... echo` 返回 `Wsl/Service/E_ACCESSDENIED`；Windows 侧也没有 Docker、Podman 或 nerdctl 备用入口。本次重试保持 pending，不改变实验路线。

### 状态

`INFRA_FAILURE`：零 API 调用，等待本地 WSL 执行权限恢复后按相同 run ID 重试。

## 2026-07-15 — EXP-DEV20-002：Marshmallow 容器字段格式继承

### 实例与配置

- 实例：`marshmallow-code__marshmallow-1359`；
- 模型：`gpt-5.6-terra`；
- ACI：论文默认配置；
- API 调用上限：25；
- temperature：0.0；
- top_p：0.95。

### 推理过程

模型构造最小 schema，复现 List 内部 DateTime 未继承 `Meta.datetimeformat` 的行为；随后检查 `Field.root`、List/Tuple bind 流程和既有格式测试。修复把 `DateTime._bind_to_schema()` 的格式来源从直接父 schema 改为根 schema，并覆盖 List 和 Tuple 回归场景。

### 推理统计

- API 调用：23；
- 输入 token：299,097；
- 输出 token：5,405；
- agent 步骤：21；
- API 响应窗口：约 171 秒；
- exit status：`submitted`。

### 正式判分

- patch apply：成功；
- FAIL_TO_PASS：1/1；
- PASS_TO_PASS：76/76；
- 总目标测试：77/77；
- SWE-bench 判定：`RESOLVED_FULL`。

### 批处理验证

批处理通过 1343 的正式 scorecard 将其跨 run ID 跳过，随后只启动 1359。推理完成后自动执行 evaluator，短别名、空参数过滤与 Conda 下载稳健性配置均正常工作。

### 状态

`COMPLETE`：resolved=1。
