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

## 2026-07-16 — EXP-API-CLAUDE-001：Anthropic Messages 协议与当前模型目录

### 凭据处理

Anthropic 凭据写入 Git 忽略的 `secrets/anthropic.env`。该文件继承 `secrets/openai.env` 的保护 ACL：禁用继承，仅当前 Windows 账户拥有 FullControl。受 Git 管理的配置、命令输出和实验清单均不包含密钥值。

### 目录与最小请求

`GET /v1/models` 返回四个模型：

- `claude-opus-4-6`；
- `claude-opus-4-7`；
- `claude-opus-4-8`；
- `claude-sonnet-4-6`。

使用 Anthropic Messages 协议向 `claude-sonnet-4-6` 发出一次确定性最小请求。响应为 HTTP 200，返回模型 ID 与请求一致，文本精确为 `OK`，stop reason 为 `end_turn`，usage 为 3 input tokens、1 output token，cache creation/read 均为 0。该调用只验证协议，不属于 benchmark。

目录响应没有 token 单价或请求费用字段，因此批量调用的预算门槛保持未解除。

### 状态

`COMPLETE_WITH_LIMITATIONS`：现代 Claude Messages API 可用，价格未知。

## 2026-07-16 — EXP-API-CLAUDE-002：论文 Claude 3 Opus 精确模型探测

对论文模型 ID `claude-3-opus-20240229` 发出 `max_tokens=1` 的直接 Messages 请求，以排除“目录未列出但仍可调用”的情形。端点返回 HTTP 404、错误类型 `model_not_found`，说明该模型不受当前账户组支持；响应没有 usage，未产生模型 token。

当前 Claude 端点只能用于现代模型复验，不能用于 E02/E04/E15 的严格原模型运行。

### 状态

`BLOCKED_EXACT_MODEL`：精确 Claude 3 Opus 不可用。

## 2026-07-16 — EXP-ARTIFACT-001：官方 SWE-bench 主运行历史恢复与复算

### 来源恢复

新增官方 `SWE-bench/experiments` 子模块并固定当前主分支 commit `2f15350cd32becc4569e0d826361048555b605c0`。当前主分支在 2024 年 10 月重置历史并把大型预测、日志和轨迹迁移到 S3。通过官方早期 pull request 的 base/history 追溯，恢复论文发布前提交 `a5d52722965c791c0c04d18135f906b44f716d39`。

该提交包含 GPT-4、Claude 3 Opus、RAG 的 Full/Lite `all_preds.jsonl`、评测日志、SWE-agent 轨迹和 `results/results.json`。历史对象 pack 约 681.5 MiB。为避免 Windows 超长路径，复算只读取 Git blob，不检出历史树。

### 复算结果

`scripts/reproduce_official_swebench_results.py` 从固定 revision 重新统计 resolved 集合、预测唯一实例、空 patch、重复行、日志和轨迹覆盖，并生成 SHA-256 清单。八行中六行与论文主表完全一致：

- GPT-4 SWE-agent：Lite 54/300，Full 286/2294；
- GPT-4 RAG：Lite 8/300，Full 30/2294；
- Claude RAG：Lite 13/300，Full 87/2294。

Claude SWE-agent 存在论文内部不一致：

- Lite 官方工件为 35/300，论文退出条件表也为 35；主表为 13.00%，隐含 39/300；
- Full 官方工件为 241/2294，论文退出条件表也为 241；主表 10.46% 隐含 240/2294。

该差异不通过改写工件或修改分母消除。派生 CSV 同时保存论文值、工件值和差值。

### 输出

- `data/manifests/official_swebench_artifacts.json`；
- `data/derived/official_swebench_main_results.csv`；
- `docs/artifact_provenance.md`。

### 状态

`COMPLETE_WITH_PAPER_INCONSISTENCY`：主 GPT-4/Claude/RAG 工件复算完成；Shell-only、消融和重复运行仍未纳入本项。

## 2026-07-16 — EXP-ARTIFACT-002：HumanEvalFix 表格与轮数分布复算

### 来源与语言确认

新增官方 `SWE-bench/humanevalfix-results` 子模块，固定 commit `bbd565c9035f873ba5ee2c1bd1d65c5ee2d85d1a`。发布工件包含 Python、JavaScript、Java 各 164 条轨迹和对应预测，没有 Go 目录。因此论文附录中的 Go 是笔误，严格设置固定为 Java。

### notebook 分母审计

原 `view_results.ipynb` 使用 `*.log` glob。每种语言目录中的 testbed 环境日志没有通过标记，却被计为一次失败。Python 目录还缺少实例 80、135 的评测日志，仅有 162 个实例评测日志。由此精确复现论文数字：

- Python：143/163 = 87.73006%；
- JavaScript：148/165 = 89.69697%；
- Java：145/165 = 87.87879%。

按声明的每语言 164 个任务修正分母后分别为 87.19512%、90.24390%、88.41463%。两套结果并列保留。

### 轨迹与 PDF

`scripts/reproduce_humanevalfix.py` 使用 `git cat-file --batch` 读取 492 条轨迹，将通过日志与实例 ID 关联，生成实例级 CSV 和原 notebook 的 2-turn bins。PDF 采用 Matplotlib 3.8.4、NumPy 1.26.4 与固定元数据时间戳；连续两次生成的 SHA-256 均为 `b96d4ee168b8b5ed1354227b84f69fe8da0eae68db2b457566affab21fd3d61a`。

Poppler 检查结果：单页、870.81 x 280.598 pt、PDF 1.4、无加密。160 DPI 渲染图经视觉检查，三个标题、坐标轴、刻度、柱形和页边界均完整，无裁切、重叠或不可读元素。

### 输出

- `data/manifests/official_humanevalfix_artifacts.json`；
- `data/derived/humanevalfix_summary.csv`；
- `data/derived/humanevalfix_instance_results.csv`；
- `data/derived/humanevalfix_histogram_bins.csv`；
- `output/pdf/humanevalfix_turns_artifact.pdf`。

### 状态

`COMPLETE_WITH_NOTEBOOK_METRIC_BUG`：论文表格算法、修正指标和轮数图均已工件复算；精确模型重新推理仍未执行。

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

## 2026-07-16 — EXP-WEAKACI-SMOKE-001：弱化 ACI 配置验证

在正式对照前冻结 `no_search_editor`：仅移除 `search.sh` 与 `edit_linting.sh`，保留默认提交命令、文件窗口、演示、历史处理器、模型参数与 25-call 正式预算。以 `sqlfluff__sqlfluff-1625` 进行 8-call exploratory smoke，运行器成功将外部配置复制进隔离 runtime，Agent 产生轨迹与预测文件，evaluator 成功读取该预测。

该 smoke 在 8-call 上限下退出且 prediction 为空，未用于主比较。其作用仅为验证变体配置、轨迹持久化、零预测 evaluator 和变体目录隔离；正式 dev20 对照将使用预注册的 25-call 上限与独立 `weak_aci_no_search_editor` batch id。

## 2026-07-16 — EXP-WEAKACI-001：弱化 ACI Marshmallow 1343

首个正式 `no_search_editor` 对照在与默认基线相同的模型、temperature、top-p、文件窗口、历史处理器、演示和 25-call 上限下完成。模型在前四次返回中均使用带语言标签的命令围栏，严格 ACI 解析器以 `exit_format` 退出；evaluator 检测到零个非空预测。

- 调用数：4；input/output tokens：48,017 / 1,173；
- 专用搜索与 editor 未暴露；
- model patch：null；scorecard：`not_generated`。

该结果在运行当时计划计入弱化 ACI 配对表。完整论文对齐审计随后确认该组合变体不对应论文 Shell-only 或任何单因素消融，故保留为探索性结果并排除出论文主表。

## 2026-07-16 — EXP-WEAKACI-002：弱化 ACI Marshmallow 1359

`marshmallow-code__marshmallow-1359` 使用相同冻结弱化 ACI 配置完成正式运行。模型在四次调用内重复以语言标签命令围栏响应，ACI 严格解析器以 `exit_format` 退出；零预测 evaluator 完成空预测检查。

- 调用数：4；input/output tokens：47,334 / 929；
- model patch：null；scorecard：`not_generated`；
- 该结果在运行当时计划计入弱化 ACI 配对表；完整论文对齐审计后改列探索性结果，不进入论文主表。

## 2026-07-16 — 全论文复现重新规划与组合消融纠偏

逐项核对论文源码中的主表、消融表、超参数表、pass@k、HumanEvalFix 和附录分析后，原先的“dev20 默认 ACI 与一个弱化 ACI”只覆盖现代模型开发证据，不能代表完整论文复现。完整清单至少包含 13,140 个可复用后的论文对齐代理 episode，以及 248 个失败分类请求和全部工件复算。

同时确认 `no_search_editor` 同时删除摘要搜索与 linting editor：它不是基于 InterCode Bash 的 Shell-only，也不是 no-search 或 no-edit 的单因素消融。因此 `EXP-WEAKACI-SMOKE-001`、`EXP-WEAKACI-001` 和 `EXP-WEAKACI-002` 全部改列 `P-EXPLORATORY`，历史轨迹与调用统计原样保留，不进入论文结果分母。

下一实例 `pvlib__pvlib-python-1154` 在重新规划开始时只处于容器环境创建阶段。批处理、运行进程和 agent 容器均已终止；尚未初始化 agent，没有模型响应、轨迹或预测，API 调用为 0。该尝试登记为 `EXP-WEAKACI-003A/ABORTED_REPLAN`。

当前中转服务目录不包含论文的 `gpt-4-1106-preview`、`claude-3-opus-20240229` 和失败分类使用的 `gpt-4o-2024-05-13`。正式 exact 批量运行暂停；后续先完成作者工件追溯、精确配置恢复、预算确认和 evaluator 工件重放。GPT-5.6 系列结果继续只标为 modern，不替代 exact。

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

## 2026-07-16 — EXP-ARTIFACT-003：论文源码聚合与协议恢复审计

### 输入与检索范围

- arXiv：`2405.15793v3` 源码包，SHA-256 `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab`；
- SWE-agent：冻结提交 `658eb2842e8a8b00069b301338bc342b70538f7a`、全部 822 个公开 PR head、论文期 309 个 PR head；
- SWE-bench experiments：当前提交、论文工件提交 `a5d52722965c791c0c04d18135f906b44f716d39`、2024-07-01 前 24 个 PR、公共 S3 bucket；
- 内容检索：30 行窗口、Shell-only、InterCode、iterative/next/prev、no lint、no edit、no search、dev37、pass@k 与失败类别名。

### 协议恢复结果

默认 ACI、FullHistory 配置、Last5Observations 和 100/200 行参数实现可从官方历史定位。无演示、无搜索、无编辑和 30 行窗口可依据配置机制推导，但没有论文实际运行配置或工件。全文 viewer、无 lint editor、next/prev 式迭代搜索和 Shell-only 的官方精确实现未找到。

论文主工件提交此前没有命名引用，Git 清理后会成为不可用悬空对象。该提交已从官方远端按 SHA 重新获取并固定为 `refs/paper/sweagent-artifacts`。重新检查后对象库为 0 garbage，主工件脚本输入恢复稳定。

### 聚合复现

新增脚本直接读取 arXiv tar 包，生成：

- ACI：12 个表行，其中 8 个非默认消融；
- 超参：16 个设置，每项论文口径为 37 个实例、5 个 sample；
- pass@k：六次 resolved 数分别为 52、54、54、56、52、55，论文均值 17.94、标准差 0.49，pass@6 为 32.67；
- 失败模式：9 类 schema 中 8 个非零类别，计数 99、30、58、32、5、6、12、6，Other=0，总计 248。

Other=0 由 9 类 appendix schema 与 8 个非零向量图切片已经覆盖 248 个实例共同约束，标记为推断值，不冒充逐实例标签复算。

### PDF 验证

pass@k 与 failure-mode PDF 连续两次生成哈希一致，分别为：

- `846dc422622c3f99a5456cbaa4593273d367557e661d87e958600c6bb8fc50a0`；
- `3470699737b87ef5d1206582852385f1f61f70b61b7273c71fbb02adb9a9ab13`。

两张图均为 PDF 1.4、单页、无加密。160 DPI 渲染检查确认坐标、点、扇区、比例和图例无裁切或重叠。

### 缺失资产结论

没有找到 dev37 实例 ID、80 组超参原始运行、六次 pass@k 预测矩阵、248 条失败标签、15 个验证样本与人工标签、Shell-only 原始运行或八个消融原始工件。P1 资产追溯完成，但严格实验与实例级工件复算仍未完成。

### 状态

`COMPLETE_AGGREGATES_RAW_ASSETS_MISSING`：论文最终聚合值和图可重建；缺失官方原始资产已登记为 blocker，不能替代 exact 重跑。

## 2026-07-17 — EXP-ARTIFACT-004：官方 evaluator 历史聚合重放

### 目标

从论文期官方 `all_preds.jsonl` 和评测日志重新生成八组 `results.json`，要求十个类别的完整列表、顺序与重复次数均一致；只比较 resolved 数不构成通过。实验不调用模型，API 调用与费用均为 0。

### 历史源码定位

论文快照只声明 `swebench>=1.0.1`，不能唯一确定聚合语义。PyPI 1.0.1/1.0.2 的 `get_model_report` 仍返回较早的仓库嵌套结构，而官方结果使用 `no_generation/generated/with_logs/install_fail/reset_failed/no_apply/applied/test_errored/test_timeout/resolved` 十类平面结构。对 SWE-bench 官方 Git 历史逐提交比对后，定位到：

- evaluator：`cfb20092bbbee9683176177b2f59b85f522e7f27`，主题 `Add empty patch case in eval`；
- 版本字符串：`1.1.0`，但该提交晚于 1.1.0 release 提交，因此包版本本身不足以复原源码；
- `get_model_report` 源码 SHA-256：`c41a4bcfb734793ff1352439e4e10de87e3c10a1714c4d7ff6ae90c8eced8173`。

该 revision 已作为 `code/SWE-bench` 子模块固定。

### 数据 revision 定位

用 Hugging Face 当前数据回放时，Claude Full 得到 243 而非 241，RAG GPT-4 Full 得到 32 而非 30。差异只出现在 resolved，其他九个类别完整一致，说明预测和日志读取路径正确，测试参考发生了漂移。

检索官方数据仓库历史后固定：

- Lite：`81ad348adcaf3368691f4db2907f8fc97a8f7526`，Parquet 1,176,783 bytes，SHA-256 `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1`；
- Full：`283547aced6224d4adbe55c678b4c9c43fe7d501`，Parquet 12,102,802 bytes，SHA-256 `831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020`。

两者均为 2024-04-15 的 `revalidate tests` revision，早于官方 experiments 首次提交。

### 历史行语义

完整列表比对确认原聚合器不按实例去重：

- GPT-4 Lite：302 行、299 个唯一实例；
- GPT-4 Full：2,283 行、2,266 个唯一实例；
- Claude Full：2,576 行、2,266 个唯一实例，其中 310 个重复行；
- Claude Full 官方 resolved 为 241 个条目、213 个唯一实例。

`null` 与空白字符串均归入 `no_generation`。重复行复用同一个实例日志，但每次都向类别列表追加实例 ID。`pred_try` 或 `pred_minimal_try` 任一失败即归入 `no_apply`。此前“先按实例 ID 去重”的假设不符合历史代码，已从工件说明中撤销。

### 冷启动正式重放

新增 `scripts/replay_official_evaluator.py`：

1. 下载四个固定 revision 的论文期/后论文期 Parquet 并校验 LFS SHA-256；
2. 从 experiments 旧提交通过 `git cat-file --batch` 只读取预测实际请求的唯一日志；
3. 每组分别使用论文期与 2025 数据参考运行固定源码；
4. 对所有类别执行完整列表比较；
5. 处理一组后清理临时日志，保留受 Git 忽略的哈希缓存。

冷缓存端到端墙钟时间 540.6 秒。运行发生在本地 WSL2，使用 CPU 和磁盘；GPU、远程服务器和模型 API 均未使用。

### 结果

- 论文期数据：8/8 报告完整相等；
- 固定 2025-03-03 数据：6/8 报告完整相等；
- Lite 数据有 12 个实例的测试参考变化，Full 有 81 个；
- Claude Full 新增 `sympy__sympy-11384`、`sympy__sympy-12906`；
- RAG GPT-4 Full 新增 `sympy__sympy-12906`、`sympy__sympy-13001`；
- 三个实际判分漂移实例均涉及 `PASS_TO_PASS` 参考变化。

机器清单保存于 `data/manifests/official_evaluator_replay.json`，完整方法保存于 `docs/evaluator_replay.md`。

### 状态

`COMPLETE_8_OF_8_AGGREGATION_MATCH`：历史日志到官方结果的聚合层通过。prediction patch 到新容器的代表实例重新执行尚未完成，因此总门槛保持 `PARTIAL_AGGREGATION_COMPLETE_CONTAINER_PENDING`。

## 2026-07-17 — EXP-ARTIFACT-005：pytest 4.4 官方 prediction 容器重放

### 样本冻结

从 Lite GPT-4 官方运行 `20240402_sweagent_gpt4` 选择同一 pytest 4.4 环境中的两个实例：

- `pytest-dev__pytest-5227`：官方 `RESOLVED_FULL`，F2P 3 项、P2P 34 项；
- `pytest-dev__pytest-5221`：官方 prediction 可应用但 `RESOLVED_NO`，F2P 2 项、P2P 170 项。

选择规则是在一次环境构建中同时覆盖 resolved 与 applied-unresolved 两个核心分支。预测直接从 experiments `a5d5272` 读取，任务行来自 Lite `81ad348`，未修改 model patch、test patch、base commit 或测试参考。`scripts/official_container_replay.py prepare` 生成受 Git 忽略的两行任务文件、两条原预测、官方日志和输入哈希。

### 运行环境

- 本地 WSL2；
- Docker 29.6.1；
- SWE-agent evaluator 快照 `658eb2842e8a8b00069b301338bc342b70538f7a`；
- SWE-bench runtime 1.0.2；
- Miniconda `Miniconda3-py39_23.10.0-1`；
- task environment：Python 3.9，`pip install -e .`；
- 单环境、单进程、单实例超时 900 秒；
- 模型调用 0，API 费用 0，GPU 未使用。

pytest 两个实例没有触发 pvlib、pydicom 或 pyvista 的兼容约束，因此本次 testbed 没有实例特定依赖修正。

### 执行轨迹

总墙钟时间 607.6 秒：

1. 01:00:09 开始构建 testbed；
2. 01:02:03 Miniconda 可用；
3. 01:04:08 完成 pytest 仓库 clone；
4. 01:05:26 完成 Python 3.9 环境创建；
5. 对 5227 reset 到 `2051e30b...`，`pred_try` 应用/回退成功，安装成功，test patch 与 prediction patch 应用成功，测试命令约 1.6 秒；
6. 对 5221 reset 到 `4a2fdce6...`，相同步骤成功，测试命令约 6.1 秒；
7. 01:10:13 完成测试并清理临时 testbed。

### 逐测试比对

`scripts/official_container_replay.py collect` 使用同一冻结任务参考分别解析官方历史日志和新日志，再比较四个测试结果列表与 scorecard：

| 实例 | 官方 | 新容器 | F2P/P2P 列表 | scorecard |
|---|---|---|---|---|
| 5227 | `RESOLVED_FULL` | `RESOLVED_FULL` | 完全相同 | `generated, applied, RESOLVED_FULL` |
| 5221 | `RESOLVED_NO` | `RESOLVED_NO` | 完全相同 | `generated, applied, RESOLVED_NO` |

结果为 `2/2` exact outcome match。论文快照 evaluator 最后打印的 reference report 来自 runtime 1.0.2 的旧式按仓库嵌套结构，不能用该摘要行代替论文期十类别聚合器；最终验收直接使用新旧日志的逐测试报告和已经单独通过的 `cfb20092` 聚合重放。

### 状态

`COMPLETE_2_OF_2_EXACT_TEST_OUTCOMES`：resolved 与 applied-unresolved 核心容器分支通过。gold、官方 no-apply、空 patch 和重复预测边界分支继续保留，因此总门槛更新为 `PARTIAL_AGGREGATION_AND_CORE_CONTAINER_COMPLETE`。

## 2026-07-17 — EXP-ARTIFACT-006：evaluator 边界分支重放

### 目标与冻结输入

在已通过的历史聚合层和核心容器层之上，补齐 gold、官方 patch-apply failure、空预测和重复行分支。所有输入在观察新结果前固定：

- experiments：`a5d52722965c791c0c04d18135f906b44f716d39`；
- Lite 数据：`81ad348adcaf3368691f4db2907f8fc97a8f7526`，Parquet SHA-256 `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1`；
- 空/重复预测 SHA-256：`206e5523f006c9fb2b0b38a0a5f987aaab4f19e6ef5dc9458e159584f5ea4eb3`；
- 空/重复任务 SHA-256：`88de582dd903cee9af255060bd51bbee42861cd1fc66b5f0bdd0221f086004b5`；
- gold/no-apply 预测 SHA-256：`8bef07a49c11b2bc6e5dd259c71078f19120c8a05ac686849b903ea3a6cff0ec`；
- gold/no-apply 任务 SHA-256：`e28d5ea6b1dcab4479a05aec0dbdf5802571869931e7086cc92847ee47ee37ac`。

### EXP-ARTIFACT-006A：空字符串、null 与重复行

从官方 Lite GPT-4 预测按原顺序抽取三行：

1. `django__django-13964`，`model_patch` 为空字符串；
2. `psf__requests-863`，`model_patch=null`；
3. `psf__requests-863`，同一 null 行再次出现。

wrapper 共发现 3 条预测，判定 3 条均为空，不创建 testbed、不执行测试；墙钟 2.7 秒。三个 scorecard 分别是 `not_generated`，输出保留两条相同 requests 实例，证明该路径也不按实例 ID 去重。结果为 `3/3` exact，API 调用 0、费用 0、GPU 未使用。

### EXP-ARTIFACT-006B-A：无效基础设施尝试

gold/no-apply 首次执行于 01:15:35 开始，使用：

- `pytest-dev__pytest-5227` 的未修改数据集 gold patch；
- Lite RAG GPT-4 中 `pytest-dev__pytest-5221` 的官方 no-apply patch；
- pytest 4.4、Python 3.9、900 秒实例超时。

墙钟 410.8 秒后，pytest 仓库 clone 报告 `curl 92 HTTP/2 ... CANCEL`、`early EOF` 与 `invalid index-pack output`。故障发生在环境创建前，两条 patch 均未应用，测试执行数为 0，模型/API 调用为 0。wrapper 生成的两个 `build_failure` scorecard 是基础设施状态，不能作为论文判分。该尝试按协议从正式分母排除，输入、任务和失败输出已移动到 `outputs/evaluation/official_container_replay/invalid_attempts/gold_no_apply_clone_rpc_20260717T011535Z/`，WSL wrapper 副本也单独归档。

该失败满足“零模型响应的环境构建/判分基础设施失败”重试条件。没有改变预测、任务、超时或 evaluator；只在重试进程内设置 Git `http.version=HTTP/1.1`，没有修改用户或全局 Git 配置。

### EXP-ARTIFACT-006B-B：冻结输入重试

重试前重新生成输入并核对上述两项 SHA-256 与 006B-A 完全一致。正式运行墙钟 48.7 秒：

1. Miniconda 下载、pytest clone 和 Python 3.9 环境创建成功；
2. 5227 reset 到 `2051e30b...`，gold `pred_try` 应用/回退成功，安装、test patch 与 gold patch 应用成功，测试成功；
3. 5227 所有 3 个 F2P 与 34 个 P2P 均通过，状态为 `generated, applied, RESOLVED_FULL`；
4. 5221 reset 到 `4a2fdce6...`，`pred_try` 与 `pred_minimal_try` 均出现 patch apply failed，未进入测试，scorecard 只含 `generated`。

两条结果均与预注册状态相同，`2/2` exact。合并 006A 后为 `5/5` exact edge outcomes。整个实验没有模型请求、API 费用或 GPU 使用。

### 证据与状态

- 总审计：`data/manifests/official_evaluator_edge_replay.json`；
- 空/重复逐行清单：`data/manifests/official_empty_duplicate_replay.json`；
- gold/no-apply 日志解析清单：`data/manifests/official_gold_no_apply_replay.json`；
- 可重复脚本：`scripts/official_evaluator_edge_replay.py`。

`COMPLETE_5_OF_5_EXACT_EDGE_OUTCOMES`：P2 的 evaluator 代表单元/容器分支已完成。`G_EVALUATOR_REPLAY` 更新为 `PARTIAL_AGGREGATION_AND_REPRESENTATIVE_BRANCHES_COMPLETE`，因为全量 300/2,294 prediction 容器重评和每个支持仓库至少一个 gold 环境验证仍未完成。

## 2026-07-17 — EXP-ARTIFACT-007：官方实例级分析 A01–A10 重放

### 目标

从论文期公开预测、轨迹、结果列表、冻结数据集和 arXiv 源码重新计算 A01–A10。验收要求为：所有已公开原始输入的表格单元和图形统计均可由单一脚本重建；无法精确匹配的项目必须定位到具体缺失实例或论文内部不一致，不用插值、去重变体或人工修数追配目标。

该实验属于 `artifact reproduction`，不执行代理推理，不替代论文原模型严格重跑。

### 冻结输入

- arXiv：`2405.15793v3`，源码 SHA-256 `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab`；
- experiments：`a5d52722965c791c0c04d18135f906b44f716d39`；
- Lite：`81ad348adcaf3368691f4db2907f8fc97a8f7526`，Parquet SHA-256 `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1`；
- Full：`283547aced6224d4adbe55c678b4c9c43fe7d501`，Parquet SHA-256 `831728617f006e70c9de546e15cbdb49ce27b6fe8a8e4c4cd8035e8da3de3020`；
- GPT-4 Full 轨迹树 `9c9fee3591ee9a65fc3e1eede61f7018f75bc3d1`，2,268 个文件；
- Claude Full 轨迹树 `875352db0e584909897a27df2bca4fd9ca2d833a`，2,013 个文件；
- GPT-4 Lite 轨迹树 `043a824469ff2817ec19c9d16ddedae946432d63`，300 个文件；
- Claude Lite 轨迹树 `8de1a3ea59b5af9ed4323029fa26324ab1f43908`，300 个文件。

原分析源码 blob 为 `resolved_by_repo.py@13e9c2e9`、`resolved_by_time.py@8731a0ff`、`stats_patch.py@e5350c96` 和 `calc_localization_f1.py@6f355a70`。论文目标在运行前从 arXiv 源码固定，派生结果不以论文 PDF 手工抄数作为输入。

### 环境与实现

运行环境为本地 WSL2、Python 3.11.15、NumPy 1.26.4、Matplotlib 3.8.4、PyArrow 21.0.0、unidiff 0.7.5。新增依赖只安装在受 Git 忽略的 `.venv-analysis`；没有修改系统 Python、共享 conda 环境或远程环境。

新增 `scripts/reproduce_official_instance_analyses.py`。脚本使用 `git cat-file --batch` 从固定历史提交流式读取轨迹和预测，不检出包含 Windows 超长路径的旧树。执行过程为：

1. 校验论文源码和两个 Parquet 的 SHA-256；
2. 校验四棵轨迹树的 Git object ID 和文件数量；
3. 从历史 `results.json` 读取 resolved 列表，并同时保留列表行语义和唯一实例语义；
4. 依次复算仓库/年份、退出条件、turn/cost、动作、n-gram、失败 edit、patch 和文件定位统计；
5. 写出 13 个 CSV，生成 4 份 PDF；
6. 在 JSON 清单中记录运行版本、输入 object ID、逐项状态和每个输出的字节数/SHA-256。

一次完整运行墙钟约 44–48 秒。模型 API 调用 0、费用 0、GPU 未使用、远程服务器未使用。

### A01–A02：仓库和年份表现

复算沿用历史预测行和官方结果语义，不把预测行数误作数据集分母。A01 得到 60/60 个论文表格单元精确相等；A02 得到 25/25 个单元精确相等。

### A03：退出条件

共比较 32 个“run × split × outcome × category”单元。按公开唯一轨迹计数得到 31/32 精确，按预测行权重得到 30/32 精确。唯一不可恢复的核心组是 Claude Full resolved：

- 论文：Submit 206、Exit Cost (Submit) 35；
- 公开唯一轨迹：157、35；
- 预测行加权：181、39；
- 官方结果：241 个 resolved 条目、213 个唯一实例；
- 其中 21 个唯一 resolved 实例没有公开轨迹，无法读取退出状态。

Claude Full 的全体退出条件、GPT-4 Full/Lite 和 Claude Lite 均可复现。该项状态为 `PARTIAL_CLAUDE_FULL_RESOLVED_TRAJECTORIES_MISSING`。

### A04：turn、step 与 cost

GPT-4 Full resolved 的 turn 均值/中位数/75 分位数为 14.7098/12/18，对齐论文 14.71/12/18；Claude Lite resolved 为 12.7143/13/15，对齐论文 12.71/13/15。两个发布 turn 目标 2/2 精确。

公开 GPT-4 Full 轨迹的 resolved/unresolved 成本中位数为 1.1796/2.5355，而论文正文为 1.21/2.52。turn 统计精确，成本正文存在不可由当前公开轨迹消除的轻微漂移，状态为 `PARTIAL_TURN_TARGETS_EXACT_COST_PROSE_DRIFT`。

### A05–A07：动作分析

A05 从 286 条 resolved GPT-4 Full 轨迹重建逐 turn 频率、条件占比和动作内 turn 密度。第一动作计数为 create 178、find_file 55、search_dir 50、open 2、ls 1；原始少数动作没有删除。第 5 turn 的最高频动作为 open，第 6–31 turn 均为 edit。

A06 的 top-10 三元动作计数为 10/10 精确；附录手工分类的 47 个分阶段模式计数为 47/47 精确。类别标签直接来自 `appx_tables/most_common_triples_by_index.tex` 的人工分组。

A07 生成 811 行 1–4 gram 转移数据，对论文源图抽查 10 个概率单元，10/10 精确。审计发现论文旧图的 heatmap 行按频率排序，而右侧计数仍按字典插入顺序输出，造成计数标签错位；新图按排序后的行重新绑定计数。论文正文还把 `create | edit | python` 后的 `edit/find_file/search_dir` 写作 `.39/.31/.22`，源图和公开轨迹均为 `.36/.28/.20`。

### A08：失败 edit

公开 GPT-4 Full 轨迹只有 2,268 条，论文分母为 2,294，差 26。公开轨迹中 1,159 条至少有一次失败 edit，论文写 1,185，也差 26。resolved 子集为 113/286，实际比例 39.5%；论文正文写 31.5%，与自身计数不相容。

按公开轨迹识别出 2,009 个最大连续失败 run，最终成功 1,150、未成功 859；论文写 810/555。两组平均 run 长度仍分别为 2.2009 和 5.5879，与论文 2.2/5.59 相同。恢复概率中 `n=0` 为 90.292% 对论文 90.5%，`n=1` 为 57.242% 对论文 57.2%。状态为 `PARTIAL_PUBLIC_TRAJECTORY_GAP_AND_PAPER_COUNT_INCONSISTENCY`。

### A09：patch 统计语义

32/32 个发布统计单元精确。精确匹配要求保留所有非空 JSONL 行且不按实例去重；每条保留预测都重复关联一次 gold patch；每个指标分别计算 90 分位数并保留小于等于该阈值的样本，再计算均值/中位数。

GPT-4 Full 为 2,283 个预测行、2,129 个非空行、286 个 resolved 行；Claude Full 为 2,576 个预测行、2,343 个非空行、241 个 resolved 行，后者分别只有 2,063 和 213 个唯一实例。Claude 重复行是论文统计语义的一部分。

### A10：文件定位

论文目标来自 Lite。GPT-4 SWE-agent 的 mean F1 为 59.0508%，对齐论文 59.05%；Claude 3 Opus RAG 为 45.4667%，对齐论文 45.47%。两个目标 2/2 精确。

### 输出与清单修正

最终输出为 13 个 CSV、4 份 PDF 和 `data/manifests/official_instance_analyses.json`。第一次清单生成时，转移概率 CSV 和 PDF 都使用 `transition_probabilities` 键，PDF 覆盖了清单中的 CSV 条目；两个文件内容均正确。键名改为 `transition_probabilities` 与 `transition_probabilities_figure` 后重新生成，清单完整包含 17 个输出。

### 确定性验证

在同一冻结输入上连续运行完整脚本。包括 13 个本实验 CSV 和 4 份 PDF 在内的全部新工件 SHA-256 均未变化。脚本通过 `py_compile`；机器清单解析得到 10 个 analysis、17 个 output、7 个 complete/public replay 和 3 个 partial gap。

### PDF 自动与视觉验证

四份 PDF 页数依次为 2、4、4、2，共 12 页，全部无加密。PyPDF 可提取预期标题：resolved trajectories、intentional submissions、action frequency、turn density、frequent triples、transition probabilities、failed edit actions 和 recovery probability。

Poppler 渲染第一版后，轨迹、转移与失败 edit 图均通过；动作图的共享图例过密，堆叠密度图也容易造成面积语义误读。绘图实现随后把图例移到绘图区外，并把动作内 turn 密度改为折线图。第二版 4 页动作图重新渲染后，图例、曲线、坐标和边界均清晰，无裁切或重叠。最终 PDF 与 CSV 的数值一致。

### 状态

`COMPLETE_AVAILABLE_INPUTS_7_COMPLETE_3_DOCUMENTED_GAPS`：A01–A10 的全部公开输入均已重放。A01/A02/A05/A06/A07/A09/A10 完成，A03/A04/A08 的剩余差异已经定位为公开轨迹缺失或论文内部不一致。A11、A13、A14、逐仓库 gold 验证、全量容器重评和论文原模型严格重跑仍未完成。

## 2026-07-17 — EXP-ARTIFACT-008：A13 定性案例与 A14 Prompt/ACI 运行工件审计

### 目标

验证论文附录四个定性案例是否逐项来自公开 GPT-4 Lite 运行，并恢复主 GPT-4 Full/Lite 运行实际收到的 system prompt、demonstration、instance message 和命令文档。审计明确区分模型运行时文本、SWE-agent Git 历史实现与论文排版资产，避免把时间对齐快照或说明图误用为逐字运行配置。

该实验属于 `artifact reproduction`。不执行模型推理，不改变任何 prediction，不把公开工件核验记为原模型严格重跑。

### 冻结输入

- arXiv：`2405.15793v3`，源码 SHA-256 `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab`；
- experiments：`a5d52722965c791c0c04d18135f906b44f716d39`；
- SWE-agent 初始提交：`5b143857cb7af8b22fd421a103429f76f5259f08`；
- Last-5 提交：`08e66863ac8ccf3cf8b740c243e74af15119f7b8`；
- 论文时间快照：`658eb2842e8a8b00069b301338bc342b70538f7a`；
- Lite：`81ad348adcaf3368691f4db2907f8fc97a8f7526`；
- Full：`283547aced6224d4adbe55c678b4c9c43fe7d501`。

### 环境与实现

新增 `scripts/reproduce_official_qualitative_interface.py`。脚本在本地 WSL2 的 `.venv-analysis` 中运行，使用 `git cat-file --batch` 从固定历史读取 2,568 条轨迹，不检出含 Windows 超长路径的旧工件树。脚本同时读取冻结 Parquet、arXiv tar 成员和 SWE-agent Git blob，输出逐案例、逐 action、逐 prompt 变体与逐命令表，并在 JSON 清单中记录全部输入和输出哈希。

一次完整运行墙钟约 22–27 秒。模型 API 调用 0、费用 0、GPU 未使用、远程服务器未使用。

### A13：四个定性案例

论文选择的案例为：

- 成功：`psf__requests-2317`、`pylint-dev__pylint-5859`；
- 失败：`sympy__sympy-21614`、`django__django-14411`。

四条公开轨迹、prediction、评测日志和结果均存在。论文 TeX 中 72 个 `agentbox` action 与官方 `.traj` action 达到 72/72 逐字相等；四份 `goldpatchbox` 与冻结 Lite gold patch 达到 4/4 逐字相等；两条 resolved 与两条 applied-unresolved 结果达到 4/4 一致。

Requests、Pylint 和 Django 的主动提交 model patch 均可逐字核验。SymPy 没有主动 `submit`，最后 action 为 `exit_cost`；环境状态为 `submitted (exit_cost)`，并自动提交了当时存在的 `reproduce_issue.py` patch。论文只展示 `Exited` 并描述为未提交，因此省略的是自动提交语义，而不是不存在 prediction。最终 observation 只有 2/4 逐字一致：除 SymPy 省略外，Requests 的论文展示在 patch 后额外附加 shell state。这两处属于展示层差异，不改变 action、patch 或判分。

实例级行为统计进一步确认：Requests 为 10 turns/10 calls、Pylint 为 13/13、SymPy 为 33/33、Django 为 16/16。SymPy 轨迹含 22 次 `scroll_down`，唯一源码树修改是复现脚本；Django 第一次 edit 被 lint 拒绝，第二次应用后未运行测试即提交。这些证据支持论文的成功与失败定性分析。

### A14：实际运行 Prompt

遍历 GPT-4 Full 2,268 条和 Lite 300 条轨迹后，system prompt 存在两个 SHA-256 变体：

- required 版本：Full 1,753、Lite 249，合计 2,002；SHA-256 `bcf072797e41fd3f9111b36416fdd32269c98a830fe850324e68560883641e7d`；
- optional 版本：Full 515、Lite 51，合计 566；SHA-256 `a4d3de50b84779d8b77c453db17183352e5c9b29280d12050504542dd9771db4`。

两个版本只在 `open.line_number`、`search_dir.dir`、`search_file.file` 和 `find_file.dir` 的详细参数标签上不同。命令 signature 在两版中都用方括号表示这些参数可选。初始提交的 config 与命令元数据可以逐字生成 optional 版本；把四个标签替换为 required 后可以逐字生成另一版本。变体按仓库分片集中出现，不能当作单条轨迹噪声。

全部 2,568 条 instance message 都与 `5b143857:config/default.yaml` 的模板逐字一致。全部轨迹还共享同一 demonstration message，SHA-256 为 `55f076f087bbe380ae06c6f8b624cceb56e7afa1c8589bbdfc91de0949e8e529`。`658eb284` 已改动初始模板拼写和空白，不能生成逐字运行输入。

名义运行目录包含 `last_5_history`，但 Last-5 处理器直到 `08e66863` 才公开提交。实际 prompt 仍保留初始提交的旧拼写、旧命令文档和两个标签变体。因此没有单一公开提交完整代表实际工作树；后续严格重跑需要冻结本实验导出的文本及实例到变体映射。

### ACI 实现与论文说明差异

论文命令表的 10 个命令均定位到初始提交实现。审计保留三组差异：

1. 实现中的 `scroll_down` 增加行号、`scroll_up` 减少行号，论文命令表把方向说明反写；运行时 `scroll_up` 文档本身还误写成 `scroll_down`。
2. 论文正文称搜索最多返回 50 个结果；初始 `search_file` 在超过 100 个匹配行时拒绝输出，`search_dir` 在超过 100 个匹配文件时拒绝输出，`find_file` 没有显式上限。
3. 论文 linting 图使用轨迹期旧报错首句；时间快照已改写首句，但拒绝错误 edit、展示拟应用/原始代码并恢复文件的核心语义相同。

论文 system/instance prompt 图是编辑后的说明资产，不是逐字运行文本。system 图用占位符代替完整命令文档，instance 图省略无输出复现脚本应打印成功消息的建议。

### 界面 PDF 验证

机器清单记录 21 个 prompt/interface TeX 或 PDF 资产的字节数与 SHA-256。从冻结 tar 临时提取 ACI/UI、prompt flow、components、file viewer、file editor、search comparison 和 edit comparison 七份 PDF；均为单页、未加密。Poppler 以 140 DPI 渲染后，标题、箭头、命令、代码、三栏对比和页面边界均清晰，无裁切、重叠或缺字。临时文件位于 Git 忽略目录，不重复提交论文资产。

### 确定性与实现修正

四个 CSV 与四个精确 prompt 文本连续两次生成，8/8 SHA-256 均未变化。脚本通过 `py_compile`，CSV 行数、状态计数、输入对象和清单输出均由独立校验读取。

开发期间一次只读诊断命令因遗漏 `pyarrow` 命名空间触发 `NameError`，在生成任何受管输出、调用 API 或启动容器之前终止；补全导入后确认 Full instance message 为 2,268/2,268 精确。正式脚本不含该错误，冻结输入未改变。

### 输出

- `data/manifests/official_qualitative_interface.json`；
- `data/derived/official_qualitative_cases.csv`；
- `data/derived/official_qualitative_actions.csv`；
- `data/derived/official_prompt_runtime_variants.csv`；
- `data/derived/official_command_interface_audit.csv`；
- `data/derived/official_prompt_system_required.txt`；
- `data/derived/official_prompt_system_optional.txt`；
- `data/derived/official_prompt_demonstration.txt`；
- `data/derived/official_prompt_instance_template.txt`；
- `docs/official_qualitative_interface_audit.md`。

### 状态

`COMPLETE_A13_A14_ARTIFACT_AUDIT_WITH_RUNTIME_PROMPT_VARIANTS`：A13 的全部公开 action、gold patch 和结果已核验；A14 的全部公开 GPT-4 prompt、命令实现和论文界面资产已审计。发现并冻结两个 system prompt 变体以及无法映射到单一 Git 提交的混合配置。该状态不代表论文模型重新推理、缺失消融运行或全量 evaluator 容器重评已经完成。

## 2026-07-17 — EXP-ARTIFACT-009：逐仓库 gold 环境验证预注册

### 目标

满足 evaluator 门槛中“论文期每个支持仓库至少执行一个未修改 gold patch”的覆盖要求。该实验只验证环境构建、patch 应用、测试执行与日志解析，不调用模型，不把 gold 结果计为代理解决率。

### 支持仓库边界

冻结 Lite `81ad348` 和 Full `283547a` 分别含 300 与 2,294 个实例，但两者的仓库集合完全相同，均为 12 个。`SWE-bench@cfb20092` 常量中还存在后续扩展仓库和 HumanEval 项目；由于它们不在论文 Full/Lite 数据中，不进入本实验分母。

### 执行前选择规则

每个仓库优先在官方 `20240402_sweagent_gpt4` 的 resolved 集合中，选择 `len(FAIL_TO_PASS) + len(PASS_TO_PASS)` 最小的 Lite 实例；若该仓库没有官方 resolved 实例，则从全部 Lite 实例选择最小者。依次使用 gold patch 字节数和 instance ID 打破平局。规则在新环境执行前写入脚本和机器清单，不根据后续构建成功与否更换实例。

固定实例为：

| 仓库 | instance | version | F2P/P2P | 来源 |
|---|---|---:|---:|---|
| astropy/astropy | `astropy__astropy-14995` | 5.2 | 1/179 | resolved |
| django/django | `django__django-13447` | 4.0 | 1/5 | resolved |
| matplotlib/matplotlib | `matplotlib__matplotlib-23964` | 3.6 | 1/16 | resolved |
| mwaskom/seaborn | `mwaskom__seaborn-3010` | 0.12 | 1/2 | resolved |
| pallets/flask | `pallets__flask-4992` | 2.3 | 1/18 | Lite 最小；无 resolved |
| psf/requests | `psf__requests-2317` | 2.4 | 8/133 | resolved |
| pydata/xarray | `pydata__xarray-4248` | 0.12 | 1/18 | Lite 最小；无 resolved |
| pylint-dev/pylint | `pylint-dev__pylint-5859` | 2.13 | 1/10 | resolved |
| pytest-dev/pytest | `pytest-dev__pytest-5227` | 4.4 | 3/34 | resolved；复用 EXP-ARTIFACT-006 |
| scikit-learn/scikit-learn | `scikit-learn__scikit-learn-13584` | 0.21 | 6/3 | resolved |
| sphinx-doc/sphinx | `sphinx-doc__sphinx-8713` | 4.0 | 1/45 | resolved |
| sympy/sympy | `sympy__sympy-24152` | 1.12 | 1/6 | resolved |

10 个选择具有可对照的官方 resolved 日志；Flask 与 xarray 的官方 GPT-4 Lite 运行没有 resolved 实例，因此只按最小引用规则选择。

### 冻结输入与实现

- SWE-agent evaluator：`658eb2842e8a8b00069b301338bc342b70538f7a`；
- SWE-bench evaluator/runtime：`cfb20092bbbee9683176177b2f59b85f522e7f27`；
- Lite 数据：`81ad348adcaf3368691f4db2907f8fc97a8f7526`，Parquet SHA-256 `2c0969b6fb6920f9425015563419901a4fe7fd078d143a3457fa1997b52365b1`；
- experiments：`a5d52722965c791c0c04d18135f906b44f716d39`；
- runner：`scripts/official_gold_repository_replay.py` 与 `scripts/run_local_evaluation.py`。

prepare 从冻结 Parquet 直接复制 gold patch，不做行尾、路径或最小 patch 改写。`data/manifests/official_gold_repository_selection.json` 保存每个 base commit、gold/test patch SHA-256、任务与 prediction JSONL SHA-256、官方日志 blob 和选择来源。静态核验得到仓库 12/12、选择 12/12、官方 resolved 日志 10/10、待新建环境 11、复用环境 1、字面 API 密钥 0。

### 运行隔离与重试协议

11 个新环境按仓库顺序、单进程执行；每个进程只含一个 repo/version，使用历史 evaluator 的对应 Miniconda 选择和 900 秒任务超时。Git clone 固定为进程级 HTTP/1.1，以规避已经观察到的 HTTP/2 early EOF；不修改账户级或全局 Git 配置。

runner 在子进程启动前移除继承环境中的 OpenAI、Anthropic 和 Claude 端点/凭据变量，使模型 API 调用在机制上保持 0。每个尝试保存完整 stdout/stderr、scorecard、results、eval log、时间、return code 与 SHA-256。失败后保留原尝试，再根据日志判断是冻结协议失败还是 2026 依赖/传输漂移；任何兼容修正必须实例作用域最小化并另行记录。

### 验收条件

每仓库必须满足：gold SHA-256 与预注册值相同；scorecard 为 `generated, applied, RESOLVED_FULL`；所有 F2P/P2P 引用通过。对具有官方 resolved 日志的实例，新 gold report 还必须与官方 report 完整一致。pytest 的既有 gold 运行已满足这些条件，不能重复计作新实验。

### 预注册状态

`PREPARED_SELECTION_AND_INPUT_HASHES_FROZEN`：选择、输入和验收规则已冻结，尚未读取其余 11 个新环境的结果。模型 API、GPU和远程服务器使用均为 0；本地 WSL 根文件系统可用空间约 944 GB，满足逐仓库临时环境构建需求。

## 2026-07-17 — EXP-ARTIFACT-009：逐仓库 gold 环境验证完成

### 目标与口径

在预注册选择不变的前提下，为论文期 12 个 SWE-bench 仓库各验证一个未修改 gold patch。实验只验证 evaluator 的环境构建、base commit reset、test/gold patch 应用、测试执行和 reference outcome 解析；不运行代理、不计入论文解决率。

完成判定保留两个层级：

- `full_reference_outcome`：scorecard 为 `generated, applied, RESOLVED_FULL`，全部 F2P/P2P reference tests 通过；
- `external_network_semantic`：仅当一个 reference test 因不可控公网依赖失败，并且相同 base/gold/test patch 上的本地等价语义验证通过时使用，不改写原 scorecard。

### 冻结运行时

- SWE-bench：`cfb20092bbbee9683176177b2f59b85f522e7f27`，由 `PYTHONPATH` 强制优先导入源码工作树并在 runner preflight 中验证实际模块路径；
- SWE-agent evaluator：`658eb2842e8a8b00069b301338bc342b70538f7a`；
- Lite：`81ad348adcaf3368691f4db2907f8fc97a8f7526`；
- 外层 Python：`/home/gugabobo/.venvs/swebench-paper-eval/bin/python`；
- conda solver：正式后续尝试使用 libmamba；
- 单测试命令 timeout：1,800 秒；
- 执行：本地 WSL2，单仓库顺序运行；
- 模型 API、GPU、远程服务器：全部 0。

初始尝试曾从已安装的 `swebench 1.0.2` 导入模块，无法证明使用冻结 revision。此后 runner 强制源码路径、记录实际 import source，并把旧尝试保留为协议无效诊断，不计入成功证据。

### 最终结果

| 仓库 | 直接 reference | 最终分类 | 新 attempts | 关键兼容证据 |
|---|---:|---|---:|---|
| astropy/astropy | 180/180 | full reference | 3 | `setuptools==68.0.0` |
| django/django | 6/6 | full reference | 2 | 无 |
| matplotlib/matplotlib | 17/17 | full reference | 5 | Ghostscript、TeX、dvipng |
| mwaskom/seaborn | 3/3 | full reference | 3 | 无 |
| pallets/flask | 19/19 | full reference | 2 | 无 |
| psf/requests | 140/141 | external-network semantic | 3 | 本地双主机重定向 1/1 |
| pydata/xarray | 19/19 | full reference | 6 | libmamba 与官方验证包版本 |
| pylint-dev/pylint | 11/11 | full reference | 2 | 删除下架的 typing-only stub |
| pytest-dev/pytest | 37/37 | full reference | 复用 | EXP-ARTIFACT-006 |
| scikit-learn/scikit-learn | 9/9 | full reference | 1 | 无 |
| sphinx-doc/sphinx | 46/46 | full reference | 2 | `setuptools==69.5.1` |
| sympy/sympy | 7/7 | full reference | 1 | 无 |

总计 495 个 reference outcomes，494 个在冻结 evaluator 中直接通过；剩余 1 个 Requests 公网测试完成独立语义验证。仓库级结果为 11 个 `full_reference_outcome` 和 1 个 `external_network_semantic`，`validated_outcome_match=12/12`，同时保留 `all_exact=false`。

### Requests 公网漂移

`psf__requests-2317` 的 F2P 8/8 和 P2P 132/133 直接通过。唯一失败项为 `test_auth_is_stripped_on_redirect_off_host`；当前网络访问论文测试依赖的公共 HTTP 端点持续 reset/timeout，官方历史日志中该项通过。

本地语义验证使用 base `091991be0da19de9108dbe5e3752917fea3d7fdc`、相同 gold patch SHA-256 `e6f1e638...` 和 test patch SHA-256 `ff283039...`。请求从 `127.0.0.1` 携带 Basic Authorization，经 302 重定向到 `localhost`；history 为 1、最终状态 200，初始 Authorization 存在，最终客户端和服务端 Authorization 均不存在。该结果证明目标安全语义成立，但不把公网失败的 scorecard 改写为 `RESOLVED_FULL`。

### xarray 资源保护与版本漂移

xarray 的经典 conda solver 持续计算约 14 分钟，峰值 RSS 19,531,176 KiB，占 WSL 内存约 95.3%，可用内存降至 116 MiB、swap 已使用约 1.6 GiB。达到预设 1 GiB 可用内存保护阈值后终止 attempt 4，状态为 `ENV_SOLVER_RESOURCE_GUARD`，没有 patch 应用、测试或 API 调用。

libmamba 在相同 `environment.yml` 上完成求解。冻结 harness 的 `numpy 1.25.2 + pytest 8.1.1` 使 xarray 0.16 在收集期失败；官方 `validation/lite_20240627` 对同一 base/gold/test patch 明确使用 NumPy 1.23.0、setuptools 68.0.0 并得到 19/19。实例级兼容固定 NumPy 1.23.0、pytest 7.4.0、setuptools 68.0.0 后，本地也得到 F2P 1/1、P2P 18/18。

### 其他依赖漂移

- Pylint：开发 requirements 中的 `types-pkg_resources==0.1.3` 已从 PyPI 下架；该包只提供 typing stub，删除该行后官方 11 项 reference tests 全部通过。
- Sphinx：tox 新环境安装的最新 setuptools 已删除 `pkg_resources`，导致测试插件在收集前失败；官方验证使用 setuptools 69.5.1，固定该版本后 46/46 reference tests 通过。
- Matplotlib：依次补齐 Ghostscript、LaTeX、`type1cm` 和 dvipng；每次缺失依赖均保留独立 attempt，最终 17/17。
- Requests：公网漂移按前述语义验证处理，不通过改写 hosts、跳过测试或伪造日志解决。

### Attempt 审计

11 个新仓库累计 30 个 attempt，机器清单保留每个 attempt 的时间、状态、return code、scorecard、协议有效性、solver、兼容说明、原始日志 SHA-256 和 `model_api_calls=0`。其中 10 个为协议有效的最终 `RESOLVED_FULL`；pytest 的第 11 个 full-reference 仓库复用 EXP-ARTIFACT-006。19 个未成功 attempt 与一个早期协议无效但测试通过的 Django 诊断均未覆盖、未进入最终 full-reference 计数。

### 磁盘口径纠正

预注册日志引用的 WSL 根目录约 944 GB 是稀疏虚拟磁盘视图，不能视为独立物理容量。本阶段宿主 D 盘实测只剩约 64–65 GB。逐仓库环境执行后清理，故顺序 gold 重放可安全完成；正式 300/2,294 实例批量运行仍受 120 GB 门槛阻止。

### 输出与状态

- `data/manifests/official_gold_repository_replay.json`：12 个 observation、30 个 fresh attempt 历史、环境兼容和汇总；
- `data/derived/official_gold_repository_replay.csv`：逐仓库判定；
- `data/manifests/requests_offhost_redirect_validation.json`：Requests 本地语义证据；
- `outputs/evaluation/official_gold_repository_replay/`：全部原始输入、日志、scorecard 和 attempt 文件，Git 忽略；
- `docs/evaluator_replay.md`：方法、结果和完成边界。

最终状态为 `COMPLETE_11_FULL_REFERENCE_1_EXTERNAL_NETWORK_SEMANTIC`。该状态完成了论文仓库代表环境门槛，不代表全量 Lite/Full 容器重评、原模型推理或整篇论文严格复现完成。

## 2026-07-17 — EXP-ARTIFACT-010：公开工件复现覆盖审计

### 目标

在不执行模型推理的条件下，对论文输出清单、arXiv 源码成员、全部派生文件、协议负检索终态和 evaluator 仓库覆盖做一次联合机器验收。审计只回答公开工件层是否完成，不把论文源码聚合值、现代模型结果或外部 blocker 计为原模型严格重跑。

### 验收输入

- `conf/paper_output_inventory.yaml`：54 个论文输出及其 source member、派生工件和验收口径；
- `paper/2405.15793_source.tar.gz`：arXiv v3 源码包，SHA-256 与协议恢复清单一致；
- `data/manifests/paper_protocol_recovery.json`：11 个协议组件、4 组缺失结果资产和 7 条负检索结论；
- `data/manifests/official_gold_repository_replay.json`：11 个 full-reference outcome、1 个 Requests 外网语义替代验证；
- `conf/full_paper_matrix.yaml`：13 个 gate、18 个 exact 实验和完成契约。

### 机器验收规则

1. 输出 ID 必须完整覆盖 O01–O54，状态必须属于清单定义的五种可审计终态；
2. 每个 `source_members` 条目必须存在于固定源码包，并记录解包后字节数和 SHA-256；
3. 每个 `generated_artifacts` 文件必须存在，并记录字节数和 SHA-256；
4. 协议组件与缺失结果资产不得保留 `PENDING`、`SEARCHING`、`UNKNOWN` 或 `IN_PROGRESS`；
5. 论文源码包 SHA-256 必须与协议清单一致；
6. evaluator 仓库覆盖必须保持 11 full-reference、1 semantic、12 validated；
7. 公开工件完成与原模型、现代模型和严格完成四个布尔状态必须独立保存。

### 结果

全部 54 个论文输出通过联合验收，共涉及 56 个唯一源码成员和 35 个唯一派生文件。状态分布为：

| 状态 | 数量 |
|---|---:|
| `ARTIFACT_RECOMPUTED_EXACT` | 18 |
| `ARTIFACT_RECOMPUTED_WITH_DOCUMENTED_GAP` | 7 |
| `SOURCE_AGGREGATE_REBUILT_RAW_INPUT_BLOCKED` | 8 |
| `SOURCE_ASSET_VERIFIED` | 8 |
| `ARTIFACT_AUDITED` | 13 |

15 个带缺口的输出均保留具体缺失原因，不把论文源码聚合重建写成逐实例原始运行复算。11 个协议组件和 4 组缺失结果资产均已进入恢复、可推导但未发布、或缺失官方实现的终态；7 条负检索证据保持不变。论文 source archive 哈希与协议清单一致，evaluator 仓库覆盖保持 12/12。

### 完成状态拆分

- `public_artifact_reproduction_complete=true`；
- `exact_model_rerun_complete=false`，18 个 exact 实验均未启动；
- `modern_replication_complete=false`，现有 dev20 只属于局部现代实验；
- `strict_full_paper_reproduction_complete=false`，继续执行 `public AND exact` 规则。

公开工件进度为 54/54，原模型严格重跑为 0/18。二者不合并成单一百分比。原模型、精确消融配置、dev37、失败标签、价格/预算、正式磁盘和服务器容器 runtime 门槛仍逐项保留。

### 输出

- `data/manifests/full_reproduction_coverage.json`：输入、source member、派生文件、逐输出 gate 和完成状态清单；
- `data/derived/paper_output_coverage.csv`：O01–O54 逐项覆盖表；
- `docs/public_artifact_completion_audit.md`：完成边界与严格重跑 blocker；
- `scripts/audit_full_reproduction_coverage.py`：确定性覆盖审计入口。

本阶段模型 API、GPU和远程服务器使用均为 0。最终状态为 `COMPLETE_PUBLIC_ARTIFACT_REPRODUCTION`；该状态不等于整篇论文严格复现完成。

## 2026-07-17 — EXP-MODERN-ANALYSIS-001：现代 dev20 默认 ACI 基线统计收口

### 目标与证据层

对已经完成的 `gpt-5.6-terra` 冻结 dev20 默认 ACI 运行做统计、资源和原始文件哈希收口，不新增模型请求。该实验属于 `modern` 证据层；数据来自 SWE-bench Lite dev split，不与论文 Lite test 成功率作直接显著性比较，也不替代 `gpt-4-1106-preview` 严格重跑。

### 冻结输入

- SWE-agent revision：`658eb2842e8a8b00069b301338bc342b70538f7a`；
- 模型：`gpt-5.6-terra`，Chat Completions；
- temperature：0.0；top-p：0.95；每实例最多 25 次调用；
- 数据：`princeton-nlp/SWE-bench_Lite` dev revision `6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2`；
- 选择：seed 42 冻结的 20 个实例；
- run map：`conf/modern_dev20_baseline_runs.yaml`，逐实例固定正式 trace directory 与 run ID。

### 验收方法

每个实例必须有唯一 scorecard 与 trajectory，scorecard ID 必须匹配冻结清单。结果只按 evaluator 最终状态分类；`RESOLVED_FULL` 记为解决，`RESOLVED_PARTIAL` 不计为完全解决。脚本同时读取模型调用与 token 统计、exit status、patch 生成/应用状态、patch 规模，并为 scorecard、trajectory、prediction、result、运行参数和 run manifest 中的可得文件计算 SHA-256。

19 份可得 `args.yaml` 均逐项确认模型为 `gpt-5.6-terra`、temperature 0.0、top-p 0.95。`sqlfluff__sqlfluff-1763` 在最终格式重试后未完整持久化运行目录，缺少 `args.yaml`、run manifest 和最后一次响应 usage；既有实验台账与运行日志确认该实例实际发起 25 次请求，而 trajectory 只保存 24 次。

### 主要统计

- 完全解决：4/20，20.00%；
- Wilson 95% CI：8.07%–41.60%；
- 生成 prediction：14/20；
- prediction 成功应用：10/20；
- `RESOLVED_PARTIAL`：2；
- `RESOLVED_NO`：4；
- `PATCH_APPLY_FAILED`：4；
- `NOT_GENERATED`：6。

仓库描述结果为 Marshmallow 2/2、pvlib 1/4、pydicom 1/5、Astroid 0/3、PyVista 0/1、SQLFluff 0/5。各仓库 n=1–5，不做仓库间显著性推断。

### 调用与 token

trajectory 持久化总量为 397 次 API 调用、5,496,947 input tokens 和 70,405 output tokens。加上 SQLFluff 1763 已知未持久化的最后一次格式请求，资源台账总调用为 398；由于该响应 usage 不存在，token 合计只能作为下界。端点价格未知，成本字段不写成 0。

逐实例持久化调用均值 19.85、中位数 22.5、IQR 20–25；input token 均值 274,847.35、中位数 288,395.5；output token 均值 3,520.25、中位数 3,405.5。四个成功实例共 87 次持久化调用，其余实例 310 次；该描述不解释为调用量与成功的因果关系。

### 完成边界

当前只完成现代默认 ACI 基线的统计收口。八个论文单因素 ACI 尚无同一 dev20 上的配对运行，因此不能计算 McNemar 检验，也不能把 `modern_replication_complete` 更新为真。扩大 API 调用前仍需端点价格和明确总预算。

输出为 `data/manifests/modern_dev20_baseline_analysis.json`、`data/derived/modern_dev20_baseline_instances.csv`、`docs/modern_dev20_baseline_analysis.md` 与确定性分析脚本。该分析阶段新增 API 调用、GPU与远程服务器使用均为 0。
