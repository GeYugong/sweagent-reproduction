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

## 2026-07-16 — EXP-DEV20-006A：pvlib 1854 容器 EOF 竞态

第七个实例在 Agent 初始化前终止。触发命令只是对 `export SEARCH_RESULTS=()` 执行 Bash 语法检查；日志显示后台 PID 为空，退出码读取缓冲区已经包含 `0`，但第二次读取仍等待满 5 秒并抛出 TimeoutError。

旧 `read_with_timeout()` 在 `select()` 报告可读后调用 `os.read()`，却没有处理返回空字节的 EOF 情况，导致循环直到超时。运行适配补丁增加空读取立即 `break`，使已缓冲的退出码能够返回给调用方。该修改符合 pipe EOF 语义，不改变命令、输出或任务逻辑。

失败前没有 Agent 轨迹或预测，API 调用为 0，不计入 dev20 分母。

### 状态

`INFRA_FAILURE`：容器通信兼容修正完成，等待原配置重试。

## 2026-07-16 — EXP-DEV20-006：pvlib 1854 ACI 格式退出

EOF 修正后的重试成功完成环境初始化。模型计划通过最小 `PVSystem(arrays=array)` 示例复现构造错误，但首轮响应使用 `` ```sh `` 围栏并把 DISCUSSION/命令块完整重复两次。论文 ACI 要求恰好一段 discussion 和一个无语言标签的 command block，三次纠错后仍未获得可解析响应。

统计：4 次 API 调用、51,333 输入 token、1,269 输出 token、0 个实际工具动作。轨迹只有 `exit_format`，预测为 null，scorecard 为 `not_generated`。

### 状态

`COMPLETE`：resolved=0，失败类型为 `NOT_GENERATED/EXIT_FORMAT`。

## 2026-07-16 — EXP-DEV20-007A：pydicom 1139 缺失测试运行器

模型完成 16 次 API 调用，修改 `PersonName.__iter__` 并尝试运行 `pytest -q pydicom/tests/test_valuerep.py`。Agent 容器返回 `pytest: command not found`，模型仍提交候选补丁。evaluator 成功应用 benchmark test patch 与 prediction patch，但测试命令同样立即返回 `pytest: not found`，因此 FAIL_TO_PASS 3 项与 PASS_TO_PASS 38 项均未实际执行。

SWE-bench 1.0.x 的 pydicom 2.0 映射只声明 `numpy`，当前基础镜像和临时 Miniconda 又都不包含 pytest。缺少测试运行器既影响 Agent 决策，也使正式判分无效，不能只对原预测重判。

兼容层只为 pydicom 安装配置增加 pytest，同时覆盖 Agent 与 evaluator。原轨迹、预测、scorecard 和日志移入无效实验归档；16 次调用保留在资源审计中，但不进入正式 dev20 汇总。修正后以相同模型参数重新推理。

### 状态

`AGENT_ENV_INVALID`：不计入 dev20 分母，等待修正环境重跑。

## 2026-07-16 — EXP-DEV20-007B：pydicom 1139 pytest 8 无效判分

补装未固定版本的 pytest 后，第二次 Agent 运行完成 21 次调用并生成新预测。PersonName 测试类 13/13 通过，但完整 `test_valuerep.py` 中两个无关测试因 `TestBadValueRead.tag` 未初始化失败；evaluator 复现了相同失败。

冻结测试类使用 `setup(self)` 初始化属性。安装的 pytest 8.4.2 不再执行这种旧式 hook。pydicom Git 历史提交 `8de0a15ef`（2022-11-15）明确记录项目因 pytest 7.2 开始弃用该写法而迁移到 `setup_method`。benchmark 基线提交早于迁移，故将 pydicom 的测试运行器固定为 pytest 7 系列末版 7.4.4。

当前 21-call 预测保留，不重新调用模型；只在 pytest 7.4.4 evaluator 中重判。pytest 8 scorecard 标记为无效，不进入 dev20 分母。

### 状态

`EVAL_INVALID`：等待兼容 evaluator 重判。

## 2026-07-16 — EXP-DEV20-007：pydicom 1139 正式兼容重判

### pytest 版本实证

在 Python 3.9.25、NumPy 1.26.4 与冻结 pydicom 提交上分别建立 pytest 6.2.5 和 7.4.4 隔离环境。`TestBadValueRead` 的两项旧式 setup 测试在两版中均 2/2 通过。pytest 7.4.4 同时发出 `PytestRemovedIn8Warning`，明确指出 nose `setup(self)` 支持将在 pytest 8 移除，与 8.4.2 的失败完全对应。

### 正式重判

复用第二次 Agent 运行产生的原始预测，在 pytest 7.4.4 evaluator 中重判，没有模型调用：

- prediction patch：应用成功；
- benchmark test patch：应用成功；
- FAIL_TO_PASS：2/3 通过；
- PASS_TO_PASS：38/38 通过；
- 总目标测试：40/41 通过；
- scorecard：`RESOLVED_PARTIAL`。

轨迹统计为 21 次 API 调用、353,071 输入 token、2,521 输出 token、17 个 agent 步骤。模型实现 `__iter__` 后解决 iterator 和 contains，但未提供 `.next()` 方法，因此 `test_next` 失败。

### 状态

`COMPLETE`：resolved=0，partial=1。主 resolve rate 仅统计 `RESOLVED_FULL`。

## 2026-07-16 — EXP-DEV20-008A：pydicom 1256 退出码读取竞态

第九个实例在 Agent 初始化前执行 `mkdir -p /root/commands` 的 Bash 语法检查。命令已经返回退出码 `0`，读取缓冲区为 `0`，最终后台 PID 列表为空，但读取循环恰好跨过 5 秒截止时间，随后仍抛出 `TimeoutError`。失败发生在模型初始化之前，API 调用为 0，没有轨迹、预测或 evaluator 结果，不计入 dev20 分母。

运行适配补丁现在把超时时已读取的缓冲区和最终 PID 快照附加到异常。`SWEEnv` 只在第二次退出码读取处执行受限恢复：缓冲区去除空白后必须是纯数字，且最终 PID 列表必须为空；普通命令输出读取的超时继续抛出，非数字缓冲区和仍有进程运行的情况也继续失败。补丁通过完整 `git apply --check`、Python 编译检查和人工构造的“已读取 `0` 后跨过截止时间”单元探测。

### 状态

`INFRA_FAILURE`：零调用失败单独登记，等待相同配置重试。

## 2026-07-16 — EXP-DEV20-008B：pydicom 1256 启动参数中止

修复验证后的前两次启动沿用了单实例脚本默认的临时 run ID 与 8 次 API 调用上限，不符合 dev20 冻结方案的正式 run ID 和 25 次上限。两次进程分别在 Agent 配置加载和 Conda 环境创建阶段停止；日志中没有模型 HTTP POST、token 统计、轨迹或预测，API 调用均为 0。两个空的 pilot 目录和带时间戳日志保留作审计，不计入 dev20 分母。

### 状态

`ABORTED_CONFIGURATION`：零调用，随后使用显式冻结参数重启。

## 2026-07-16 — EXP-DEV20-008：pydicom 1256 嵌套 BulkDataURI

### 推理过程

模型检查 JSON 反序列化调用链，定位到 `JsonDataElementConverter.get_element_values()` 在处理 Sequence 内部元素时调用 `DataElement.from_json()`，但没有把当前 converter 的 `bulk_data_element_handler` 继续传入。补丁增加该参数，并添加嵌套 Sequence 中 `BulkDataURI` 的回归测试。Agent 侧运行 `pytest pydicom/tests/test_json.py`，23/23 通过。

### 推理统计

- API 调用：21；
- 输入 token：248,681；
- 输出 token：2,580；
- agent 步骤：19；
- exit status：`submitted`；
- 运行适配 patch：`d8d936371473`。

### 正式判分

- benchmark test patch：应用成功；
- prediction patch：应用成功；
- FAIL_TO_PASS：1/1 通过；
- PASS_TO_PASS：22/22 通过；
- 总目标测试：23/23 通过；
- scorecard：`RESOLVED_FULL`。

### 状态

`COMPLETE`：resolved=1。dev20 累计 4/9 完全解决，主 resolve rate 为 44.44%。

## 2026-07-16 — EXP-DEV20-009：pydicom 1413 二进制 VR 多值拆分

### 推理过程

问题由二进制值中的字节 `0x5c` 触发；该字节在文本 VR 中表示反斜杠多值分隔符，但在 `OL`、`OD`、`OV` 等二进制 VR 中只是数据。模型定位 `DataElement` 构造时的 VR 排除列表，只加入 `OL`，并添加 OL 文件写入回归测试。初次尝试调用容器中不存在的 `apply_patch`，随后改用可用编辑方式完成修改。目标测试 1/1 通过，完整 `pydicom/tests/test_filewriter.py` 为 164/164 通过。

### 推理统计

- API 调用：20；
- 输入 token：249,072；
- 输出 token：5,460；
- agent 步骤：18；
- exit status：`submitted`。

### 正式判分

benchmark test patch 与 prediction patch 均应用成功。PASS_TO_PASS 为 301/301；FAIL_TO_PASS 中 `OL` 通过，但 `OD` 和 `OV` 仍失败，因此为 1/3。模型修复了具体复现类型，却没有把同一规则推广到另外两个新增二进制 VR。

### 状态

`COMPLETE`：resolved=0，partial=1。dev20 累计 4/10 完全解决，主 resolve rate 为 40.0%。

## 2026-07-16 — EXP-DEV20-010：pydicom 1694 无效 raw tag 抑制

### 推理过程

模型追踪 `Dataset.to_json_dict()` 到 `Dataset.__getitem__()` 的 raw element 转换路径，发现 `self[key]` 在 `try` 块之外执行，使 `suppress_invalid_tags=True` 无法捕获转换异常。候选补丁把该取值移入 `try`，并在 `test_json.py` 增加 mock `DataElement_from_raw` 的回归测试。模型执行目标筛选和完整 JSON 测试文件，达到 25 次调用上限后以 `submitted (exit_cost)` 保存补丁。

### 推理统计

- API 调用：25；
- 输入 token：312,767；
- 输出 token：3,346；
- agent 步骤：24。

### 正式判分

干净基线上的 `pred_try` 应用及回退成功。正式 evaluator 随后应用 benchmark test patch，再应用预测时，`pydicom/dataset.py` 检查通过，但 `pydicom/tests/test_json.py` 第 7 行 import hunk 找不到原上下文。整份 prediction patch 因测试文件冲突而失败，scorecard 只有 `generated`。

冻结协议不允许人工剥离测试 hunk，因此不对生产代码单独重判。该失败与 `pvlib__pvlib-python-1154` 属于同一类提交层冲突，可作为后续无额外模型调用的补丁净化改进组。

### 状态

`COMPLETE`：resolved=0，失败类型为 `PATCH_APPLY_FAILED`。dev20 累计 4/11 完全解决，主 resolve rate 为 36.36%。

## 2026-07-16 — EXP-DEV20-011A：pydicom 901 Python 3.6 测试运行器边界

实例安装映射指定 Python 3.6。统一的 pydicom 兼容规则尝试安装 pytest 7.4.4，但该版本声明 `Requires-Python >=3.7`，pip 在 Agent 初始化前报告没有兼容分发。没有模型 HTTP POST、token 统计、轨迹或预测，API 调用为 0，不计入 dev20 分母。

此前版本矩阵已经验证 pytest 6.2.5 在冻结 pydicom 上能够执行 nose 风格 `setup(self)`。因此 Agent 与 evaluator 的选择规则同步改为：Python 3.6 固定 pytest 6.2.5，其他版本固定 pytest 7.4.4。该调整只恢复测试运行器兼容性，不改变任务代码、benchmark patch 或测试集合。

### 状态

`INFRA_FAILURE`：零调用失败单独登记，等待相同模型配置重试。

## 2026-07-16 — EXP-DEV20-011：pydicom 901 导入时日志配置

### 推理过程

模型围绕“库不应在导入时配置日志 handler”修改 `pydicom/config.py`：删除全局 `StreamHandler`、formatter、`logger.addHandler()` 和模块末尾的 `debug(False)`，并在 `test_misc.py` 添加子进程导入断言。Agent 运行了 misc 目标文件与全套 pytest，达到 25 次调用上限后以 `submitted (exit_cost)` 保存补丁。

### 推理统计

- API 调用：25；
- 输入 token：287,071；
- 输出 token：3,485；
- agent 步骤：24。

### 正式判分

Python 3.6 evaluator 成功安装 pytest 6.2.5，benchmark test patch 和 prediction patch 均应用成功。五个 FAIL_TO_PASS 全部失败：四个 handler 相关测试因补丁完全删除 `config.handler` 而在 setup/fixture 中报错，默认状态测试也得到 handler 数量 1 而非 0。目标行为需要保留 debug API 所依赖的 handler 对象并调整何时附加，而不是删除该对象。

- FAIL_TO_PASS：0/5；
- scorecard：`RESOLVED_NO`。

### 状态

`COMPLETE`：resolved=0。dev20 累计 4/12 完全解决，主 resolve rate 为 33.33%。

## 2026-07-16 — EXP-DEV20-012：astroid 1196 字典解包键查找

### 推理过程

模型在 `Dict.getitem()` 的 `DictUnpack` 分支中先尝试直接 `value.getitem()`，失败后遍历 `value.infer(context)` 的结果再次查找键，并扩展捕获 `AttributeError`。提交同时包含临时 `reproduce.py` 和 `tests/unittest_python3.py` 的两个回归测试。Agent 运行该测试文件，达到 25 次调用上限后提交。

### 推理统计

- API 调用：25；
- 输入 token：289,720；
- 输出 token：3,862；
- agent 步骤：25；
- exit status：`submitted (exit_cost)`。

### 正式判分

`pred_try` 在干净基线上应用和回退成功。benchmark test patch 应用后，正式预测检查通过 `astroid/nodes/node_classes.py` 与新增 `reproduce.py`，但 `tests/unittest_python3.py` 第 7 行 import 区域已经改变，预测测试 hunk无法应用。scorecard 只有 `generated`。

按冻结协议不剥离测试或临时文件重判。该实例是第三个提交层测试冲突案例，进一步确立后续补丁净化消融的样本基础。

### 状态

`COMPLETE`：resolved=0，失败类型为 `PATCH_APPLY_FAILED`。dev20 累计 4/13 完全解决，主 resolve rate 为 30.77%。

## 2026-07-16 — EXP-DEV20-013：astroid 1268 Unknown 字符串表示

### 推理过程

模型定位 `AsStringVisitor` 缺少 `visit_unknown()`，新增方法返回 `node.name`，并在 `tests/unittest_nodes.py` 添加自建测试，期望 `nodes.Unknown().as_string()` 为 `"Unknown"`。Agent 运行 `AsStringTest` 后在第 20 次调用主动提交。

### 正式判分

benchmark test patch 与 prediction patch 均应用成功。92 个 PASS_TO_PASS 全部通过，但 benchmark 的唯一目标测试要求 `nodes.Unknown()` 以及带位置参数的构造均返回规范字符串 `"Unknown.Unknown()"`，候选实现返回 `"Unknown"`，因此 FAIL_TO_PASS 为 0/1。

- API 调用：20；
- 输入 token：210,496；
- 输出 token：2,509；
- agent 步骤：18；
- scorecard：`RESOLVED_NO`。

模型修复了 AttributeError 路径，却没有从 Unknown 节点的语义确定目标表示，自建测试反而固化了错误输出。

### 状态

`COMPLETE`：resolved=0。dev20 累计 4/14 完全解决，主 resolve rate 为 28.57%。

## 2026-07-16 — EXP-DEV20-014：astroid 1333 搜索预算耗尽

模型调查 implicit namespace package 在缺少 `__init__.py` 时的解析问题，主要使用 `grep`、`open`、`cd` 和一次清理命令检查模块路径代码。24 个 agent 步骤中没有 `edit` 或其他代码修改。第 23 次调用使用带 `bash` 语言标签的围栏，触发旧 ACI 格式纠正；后续仍未形成修复。

### 统计与判分

- API 调用：25；
- 输入 token：303,979；
- 输出 token：3,845；
- model patch：null；
- exit status：`exit_cost`；
- scorecard：`not_generated`。

evaluator 得到零个非空预测并跳过 testbed。该实例按正式协议计为 unresolved，不属于基础设施失败。

### 状态

`COMPLETE`：resolved=0，失败类型为 `NOT_GENERATED/EXIT_COST`。dev20 累计 4/15 完全解决，主 resolve rate 为 26.67%。

## 2026-07-16 — EXP-DEV20-015A：PyVista 4315 VTK API 漂移

首次运行的 requirements 从当前索引安装 VTK 9.6.2。冻结 PyVista 0.39 在导入 `pyvista._vtk` 时请求 `vtkCompositePolyDataMapper2`，该符号已不在 VTK 9.6.2 wheel 中。Agent 的 pytest 与正式 evaluator 都在 `pytest_pyvista` 插件加载阶段抛出同一 `ImportError`，没有收集任何目标测试。

模型已完成 14 次调用并提交候选补丁，但整个推理过程中无法获得有效测试反馈，因此不能把原预测直接重判。轨迹、预测、初始 scorecard 与 evaluator 日志归入无效环境审计，不进入 dev20 分母。

运行适配对 PyVista requirements 的裸 `vtk` 添加 `<9.3` 上界，目标为 VTK 9.2 系列；Agent 与 evaluator 同步应用。修正后按相同模型参数重新推理。

### 状态

`AGENT_ENV_INVALID`：14 次调用计入资源审计，不计入正式 dev20 汇总。

## 2026-07-16 — EXP-DEV20-015B：PyVista 4315 缺失 libGL

加入 VTK 版本上界后，环境成功安装 VTK 9.2 系列，但容器缺少其 Linux OpenGL 运行库。直接执行 `import vtk, pyvista` 与 Agent 内全部 pytest 均在导入阶段抛出 `ImportError: libGL.so.1: cannot open shared object file`，依然无法收集目标测试。

发现问题时已完成 7 次模型调用，共计 101,124 input tokens 与 1,196 output tokens。随即终止推理并归档部分轨迹，避免继续消耗无有效测试反馈的调用预算。该尝试不生成正式预测，也不进入 dev20 分母。

运行适配只对 `pyvista/pyvista` 在既有容器软件源中安装 `libgl1`；任务 Python 依赖、模型配置、测试集合与 evaluator 判定逻辑均保持不变。修正后从头重新推理。

### 状态

`AGENT_ENV_INVALID`：7 次调用计入资源审计，不计入正式 dev20 汇总。

## 2026-07-16 — EXP-DEV20-015：PyVista 4315 Sequence 构造

修正 VTK 上界与 OpenGL 动态链接库后，PyVista 环境可正常导入，正式运行与 evaluator 均不再出现环境级导入错误。模型开始尝试以 Python 最小示例验证 `RectilinearGrid` 的 Sequence 构造路径。

然而四次返回都使用了带语言标签的命令围栏（如 `````bash``），与论文快照 ACI 仅接受裸三反引号围栏的解析规则不兼容。解析器累计格式错误后以 `exit_format` 终止；轨迹中没有有效补丁，evaluator 发现零个非空预测并跳过 testbed。

- 调用数：4；
- input tokens：50,758；
- output tokens：802；
- model patch：null；
- exit status：`exit_format`；
- scorecard：`not_generated`。

### 状态

`COMPLETE`：resolved=0，失败类型为 `NOT_GENERATED/EXIT_FORMAT`。dev20 累计 4/16 完全解决，主 resolve rate 为 25.00%。

## 2026-07-16 — EXP-DEV20-016A：SQLFluff 1517 中转站 502

`sqlfluff__sqlfluff-1517` 的容器、源码快照与 Conda/Python 依赖均已完成建立。Agent 发起首个 Chat Completions 请求后，中转站连续返回 HTTP 502；客户端完成其内置重试后抛出响应错误，未收到任何模型文本。

该尝试没有产生模型响应、API 调用计数、轨迹、预测或 evaluator 结果，因而属于外部推理服务基础设施失败，不计入 dev20 正式分母。保留时间戳运行日志；服务恢复后使用同一清单、模型参数与 25-call 上限重试。

### 状态

`INFRA_FAILURE`：零个有效模型调用，重试待执行。

## 2026-07-16 — EXP-DEV20-016：SQLFluff 1517 ANSI 文件终止符

中转站恢复后，模型在有效环境中完成了 17 次调用，复现并检查了 ANSI 方言文件级 grammar、终止符与相关测试。最终回复再次使用带语言标签的命令围栏，严格 ACI 解析器返回 `exit_format`；没有形成可提交 patch，evaluator 的预测文件为空。

- 调用数：17；
- input tokens：279,449；
- output tokens：3,105；
- 模型轨迹步骤：12；
- exit status：`exit_format`；
- scorecard：`not_generated`。

### 状态

`COMPLETE`：resolved=0，失败类型为 `NOT_GENERATED/EXIT_FORMAT`。dev20 累计 4/17 完全解决，主 resolve rate 为 23.53%。

## 2026-07-16 — EXP-DEV20-017：SQLFluff 1733 SELECT 换行修复

模型完成 25 次调用并提交 `L036.py` 补丁，尝试保留首个 SELECT target 前的换行后空白。正式 evaluator 成功应用预测与 benchmark 测试 patch；3/3 PASS_TO_PASS 通过，但唯一 FAIL_TO_PASS 测试仍失败。

- 调用数：25；input/output tokens：472,317 / 8,425；
- patch：`src/sqlfluff/rules/L036.py`，+17/-0；
- FAIL_TO_PASS：0/1；PASS_TO_PASS：3/3；
- exit status：`submitted (exit_cost)`。

### 状态

`COMPLETE`：`RESOLVED_NO`。dev20 累计 4/18 完全解决，主 resolve rate 为 22.22%。

## 2026-07-16 — EXP-DEV20-018：SQLFluff 1763 自动修复 CLI

模型完成固定的 25 次调用，检查 linter、`fix` 命令和 CLI 回归测试。最后一个响应不含可解析 action；ACI 尝试格式纠正时触达调用上限，运行器未能写出预测文件。零预测 evaluator 确认没有可执行 prediction。

- 调用数：25；input/output tokens：459,480 / 4,819；
- model patch：null；
- 失败位置：`FormatError: No action found in model response` 后的预算耗尽；
- scorecard：`not_generated`。

### 状态

`COMPLETE`：`NOT_GENERATED`。dev20 累计 4/19 完全解决，主 resolve rate 为 21.05%。

## 2026-07-16 — EXP-DEV20-019：SQLFluff 2419 L060 描述文本

模型在 23 次调用后提交 `L060.py` 的诊断描述改动，并新增规则测试。正式 evaluator 成功应用 benchmark test patch，但模型新增的 `test/rules/std_L060_test.py` 与 benchmark patch 修改同一测试路径，预测 patch 无法应用，因此未执行目标测试。

- 调用数：23；input/output tokens：352,492 / 3,465；
- model patch：`src/sqlfluff/rules/L060.py` 与 `test/rules/std_L060_test.py`；
- evaluator：benchmark test patch applied，prediction patch conflict；
- scorecard：`PATCH_APPLY_FAILED`。

### 状态

`COMPLETE`：resolved=0。dev20 冻结清单 20/20 已完成，最终 4/20 完全解决，resolve rate 为 20.00%。

## 2026-07-15 — EXP-DEV20-003B：pvlib 1154 镜像 clone 停滞

### 失败位置

WSL 访问恢复后按原配置重试。容器已启动，但执行
`git clone https://github.com/swe-bench/pvlib__pvlib-python.git` 时持续无输出，超过论文快照 `LONG_TIMEOUT=500` 秒。退出时仍存在 `git`、`git-remote-http` 进程。

失败发生在 Conda 环境与 agent 初始化之前：API 调用 0、轨迹未生成、预测未生成、正式 evaluator 未启动，因而不计入 dev20 分母。

### 诊断

主机与同一 Docker 镜像内的 `git ls-remote` 均成功。随后在相同网络、代理和镜像条件下完整 clone 实测耗时 31.8 秒、目录 177 MB，远低于 500 秒上限。该现象判定为瞬时网络停滞，不修改论文快照超时，也不改变实验路线。

### 状态

`INFRA_FAILURE`：零 API 调用，按原配置重试。

## 2026-07-16 — EXP-DEV20-003C：pvlib 1154 pip_packages 类型兼容

### 失败位置

镜像仓库 clone 与 Conda 基础环境创建成功。额外 pip 依赖安装立即失败，错误为 `No matching distribution found for j`。

### 根因

当前冻结环境中的 `swebench 1.0.1` 为 pvlib 0.8 返回：

```python
{
    "python": "3.9",
    "install": "pip install -e .[all]",
    "packages": "pandas scipy",
    "pip_packages": "jupyter ipython matplotlib pytest flake8",
}
```

论文 SWE-agent 快照假定 `pip_packages` 为列表并直接执行 `' '.join(...)`。当输入是字符串时，结果被拆为字符序列，pip 首先尝试安装单字符包 `j`。这是旧快照与冻结依赖之间的类型接口漂移，不是任务本身失败。

### 修正与验证

兼容层在 `pip_packages` 为字符串时先执行 `split()`，列表输入保持不变。因此实际安装集合仍为 jupyter、ipython、matplotlib、pytest、flake8，没有增加或删除实验依赖。新 patch-hash 运行副本为 `0086fb70737e`，补丁可应用且 `swe_env.py` 通过 `py_compile`。

运行器同时改为每次尝试保存 UTC 时间戳日志，并在无时间戳路径保留最新副本，避免相同 run ID 重试覆盖失败证据。

### 状态

`INFRA_FAILURE`：零 API 调用；兼容修正完成，等待按相同正式配置重试。

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

## 2026-07-16 — EXP-DEV20-003D：凭据轮换中止

`pvlib__pvlib-python-1154` 重试在 Conda 环境创建阶段因凭据轮换主动终止。进程树与 agent 容器均已清理；时间戳日志止于环境创建，没有 agent 初始化、轨迹或预测，API 调用为 0。该尝试不计入 dev20 分母。

替换后的凭据仅写入 Git 忽略的 `secrets/openai.env`。文件仍只有当前 Windows 账户拥有显式 FullControl，未继承其他 ACL。最小 Chat Completions 探测返回 HTTP 200、响应模型 `gpt-5.6-terra`、内容精确为 `OK`，消耗 4,393 输入 token、5 输出 token。该探测登记为 `EXP-API-002`，不属于正式 benchmark 调用。

## 2026-07-16 — EXP-DEV20-003：pvlib 零 GHI 除法修复

### 实例与配置

- 实例：`pvlib__pvlib-python-1154`；
- 模型：`gpt-5.6-terra`；
- ACI：论文默认配置；
- API 调用上限：25；
- temperature：0.0；
- top_p：0.95；
- 运行适配 patch：`0086fb70737e`。

### 推理过程

模型定位 `reindl()` 中 `HB / ghi` 在 `ghi=0` 时产生无效除法的问题，将其替换为带 `out` 和 `where` 的 `np.divide`。模型同时修改既有测试，把零 GHI 情形的期望值从 `np.nan` 改为 `0`。

模型侧测试：

- `test_reindl`：1/1 通过；
- `pvlib/tests/test_irradiance.py`：98/98 通过；
- agent 步骤：19；
- exit status：`submitted`。

### 推理统计

- API 调用：23；
- 输入 token：363,417；
- 输出 token：5,377；
- agent 轨迹结束时间：14:16:30；
- 端到端批处理墙钟时间：约 1,171 秒，其中包含正式 evaluator 环境构建。

### 正式判分

evaluator 成功初始化测试环境并成功应用 benchmark 测试补丁。预测补丁随后检查生产文件与测试文件；测试文件的同一断言已被 benchmark 测试补丁改变，导致预测测试 hunk 上下文不再匹配。scorecard 状态为 `generated`，没有 `applied` 或 `resolved`。

模型补丁在干净基线上的预检查可以应用，但正式协议要求在 benchmark 测试补丁之后应用整份预测补丁，因此不得只保留生产代码 hunk重新判分。该实例正式计为 resolved=0。

### 状态

`COMPLETE`：resolved=0，失败类型为 `PATCH_APPLY_FAILED`。

## 2026-07-16 — EXP-DEV20-003E：重复 evaluator 审计

批处理准备进入下一实例时没有跳过 `pvlib__pvlib-python-1154`，而是复用了已有轨迹并再次运行 evaluator。检查发现续跑脚本只把包含 `RESOLVED_*` 的 scorecard 视为已评测；`PATCH_APPLY_FAILED` 的 scorecard 只有 `generated`，因此被误判为待评测。

本次重复 evaluator 墙钟约 261 秒，API 调用为 0，没有产生新预测，也没有改变正式结果。修正后，只要实例 ID 出现在任一正式 `scorecards.json` 中，就视为已经评测并跳过；是否 applied 或 resolved 只影响结果分类，不影响完成状态。

### 状态

`DUPLICATE_EVALUATION`：不计入 dev20 分母或正式运行数；续跑规则已修正。

## 2026-07-16 — EXP-DEV20-004：pvlib 1606 ACI 格式退出

### 实例与配置

- 实例：`pvlib__pvlib-python-1606`；
- 模型：`gpt-5.6-terra`；
- ACI：论文默认配置；
- API 调用上限：25；
- temperature：0.0；
- top_p：0.95。

### 轨迹

模型计划先列出仓库文件并定位 golden-section 实现，命令为 `rg --files | head -80`。响应包含 DISCUSSION 和一个 fenced command，但围栏使用 `` ```bash ``。论文快照解析器要求三反引号后立即换行，不接受语言标签，因此将响应判为格式错误。三次格式纠正请求后响应仍保留语言标签，达到 malformat limit，未执行任何工具命令。

### 统计与判分

- API 调用：4；
- 输入 token：55,879；
- 输出 token：632；
- agent 轨迹步骤：1（`exit_format`）；
- model patch：null；
- scorecard：`not_generated`；
- resolved：0。

evaluator 正确识别到预测为空，没有创建测试任务。运行器仍从轨迹生成 `not_generated` scorecard，因此该实例具有完整正式分类并计入 dev20 分母。

### 分析

失败不是问题求解能力或基础设施故障，而是现代模型常用 Markdown 语言标签与旧 ACI 严格语法不兼容。为保持冻结基线一致，本批次不修改解析器。后续兼容改进组可只放宽 fenced command 的可选语言标签，并在同一实例上进行配对重跑。

### 状态

`COMPLETE`：resolved=0，失败类型为 `NOT_GENERATED/EXIT_FORMAT`。

## 2026-07-16 — EXP-DEV20-005A：pvlib 1707 NumPy 2 无效判分

### 推理结果

模型完成 21 次 API 调用并提交候选补丁。Agent 容器内 `pvlib/tests/test_iam.py` 为 30/30 通过。候选补丁和 benchmark 测试补丁均能在 evaluator 中应用。

### 无效判分证据

evaluator 报告 FAIL_TO_PASS 1/1 和 PASS_TO_PASS 30/30 全部失败，但 pytest 没有进入任何测试：导入 `pvlib/singlediode.py` 时，NumPy 2.0.2 对已删除的 `np.Inf` 抛出 `AttributeError`。该引用存在于冻结基线代码，与模型修改的 `pvlib/iam.py` 无关。

### 兼容决策

当前 PyPI/Conda 解析结果晚于论文环境，不能把依赖生态破坏记为模型失败。评测 wrapper 对 pvlib 实例设置 `PIP_CONSTRAINT=numpy<2`，其他仓库不受影响。保持原预测、原 benchmark test patch 和原测试集合重新判分；初次 scorecard 标记为 `EVAL_INVALID`，不进入 dev20 分母。

### 状态

`EVAL_INVALID`：等待同一预测在兼容评测环境中重新判分，API 不重跑。

## 2026-07-16 — EXP-DEV20-005：pvlib 1707 正式兼容重判

同一 `all_preds.jsonl` 在 `PIP_CONSTRAINT=numpy<2` 的新隔离 testbed 中重新评测。安装日志显示项目与依赖安装成功，benchmark test patch 和 prediction patch 均成功应用。pytest 实际收集并执行 31 个目标测试：

- FAIL_TO_PASS：1/1 通过；
- PASS_TO_PASS：30/30 通过；
- 总目标测试：31/31 通过；
- evaluator 判定：`RESOLVED_FULL`。

推理统计沿用原轨迹：21 次 API 调用、361,753 输入 token、4,612 输出 token、19 个 agent 步骤。兼容重判没有模型调用。

### 状态

`COMPLETE`：resolved=1。
