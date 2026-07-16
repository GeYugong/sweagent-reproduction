# A13 定性案例与 A14 Prompt/ACI 运行工件审计

## 1. 审计目标

本实验验证论文附录四个定性案例是否来自公开 GPT-4 Lite 轨迹，并恢复主 GPT-4 Full/Lite 运行实际收到的 system prompt、demonstration、instance template、命令文档和 ACI 实现。审计同时区分三类对象：

1. 模型实际收到的运行时文本；
2. SWE-agent Git 历史中的配置与命令实现；
3. 论文为排版和说明而编辑的 TeX/PDF 展示资产。

三类对象不能互相替代。论文图可以忠实说明设计，但不必与运行时 prompt 逐字相同；时间对齐代码快照也不必等于 2024 年 4 月实际运行时的未提交工作树。

## 2. 冻结输入

| 输入 | revision / SHA-256 | 用途 |
|---|---|---|
| arXiv 源码 | `2405.15793v3` / `3d2bafc2fd9e104fd204f7d4582260817c48b15133f7c1cf668dd081c2fbc1ab` | 定性案例 TeX、prompt/命令表和界面 PDF |
| experiments | `a5d52722965c791c0c04d18135f906b44f716d39` | GPT-4 Full/Lite 轨迹、预测、评测日志和结果 |
| SWE-agent 初始提交 | `5b143857cb7af8b22fd421a103429f76f5259f08` | 与实际 instance prompt 对齐的模板和 ACI 实现 |
| Last-5 提交 | `08e66863ac8ccf3cf8b740c243e74af15119f7b8` | 首次公开 `Last5Observations` 与对应命名配置 |
| 论文时间快照 | `658eb2842e8a8b00069b301338bc342b70538f7a` | 论文首次提交前的代码快照，用作差异对照 |
| Lite/Full 数据 | `81ad348...` / `283547a...` | issue、gold patch 与实例覆盖 |

审计命令：

```powershell
wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/reproduce_official_qualitative_interface.py
```

完整运行约 22–27 秒，只读取本地 Git object database、Parquet 和 arXiv tar 包。模型 API、GPU和远程服务器使用均为 0。

## 3. A13：四个定性案例

论文明确选择两个成功与两个失败的 SWE-bench Lite/GPT-4 Turbo 默认配置案例。四个实例在公开运行中均有轨迹、预测和评测日志。

| 实例 | 论文分类 | 公开结果 | turns / API calls / cost | 关键核验 |
|---|---|---|---|---|
| `psf__requests-2317` | successful | resolved | 10 / 10 / 0.94091 | 解码 bytes 后再调用 `builtin_str`；执行复现脚本；主动 submit |
| `pylint-dev__pylint-5859` | successful | resolved | 13 / 13 / 1.23616 | 两次运行 pylint；regex 修复通过评测；主动 submit |
| `sympy__sympy-21614` | unsuccessful | applied-unresolved | 33 / 33 / 4.14707 | 只创建复现脚本，连续浏览 `function.py`，成本退出 |
| `django__django-14411` | unsuccessful | applied-unresolved | 16 / 16 / 1.65296 | 第一次 edit 被 lint 拒绝，第二次 edit 应用；未执行测试 |

### 3.1 动作、结果与 patch 对齐

四个论文 TeX 轨迹共有 72 个 `agentbox`。逐 turn 提取其中 action，并与官方 `.traj` 的 action 字符串比较，得到 72/72 逐字相等。四个公开结果标签与论文“2 成功 + 2 失败”分类全部一致，四份论文 `goldpatchbox` 与冻结 Lite 数据的 gold patch 也达到 4/4 逐字相等。

三次主动 `submit` 的 model patch 都在论文轨迹中逐字出现。`sympy__sympy-21614` 没有主动提交，最后 action 为 `exit_cost`；运行时状态却是 `submitted (exit_cost)`，环境自动提交了当时仍存在的 `reproduce_issue.py` patch。论文最终 observation 只显示 `Exited`，并在文字中称“without submitting”，因此省略了自动提交语义和该 patch。严格复现应解释为“模型没有主动 submit，但环境按成本退出协议自动提交”，不能解释为没有生成 prediction。

论文最终 observation 只有 2/4 与原轨迹逐字相同。除 SymPy 的自动提交省略外，Requests 的最终展示在 patch 后额外附加了 shell state；这属于排版层差异，不改变 action、model patch 或判分。

### 3.2 四个案例的行为证据

- Requests 的 10 个动作覆盖定位、编辑、创建复现脚本、执行、清理和提交。论文关于“修复有效但未复用已有 `to_native_string` 工具”的评价可由精确 model/gold patch 对比支持。
- Pylint 的 13 个动作包含一次失败的宽泛检索、后续定位、regex 修改、修复前后两次 pylint 执行和提交。model patch 与 gold patch 的 lookahead 条件确有差异。
- SymPy 的 33 个动作中有 22 次连续 `scroll_down`，未修改目标源码；唯一 patch 是复现脚本。该轨迹直接支持“低效浏览耗尽预算”的定性结论。
- Django 有两次 edit；第一次 observation 是 lint 错误并明确声明修改未应用，第二次修改应用后立即提交，没有测试命令。公开 evaluator 将 patch 判为 applied-unresolved。

派生表 `data/derived/official_qualitative_cases.csv` 保存逐案例哈希和统计，`data/derived/official_qualitative_actions.csv` 保存 72 个 action 及逐项验收状态。

## 4. A14：实际运行 prompt 的恢复

### 4.1 同一名义运行包含两个 system prompt

对公开 GPT-4 Full 2,268 条和 Lite 300 条轨迹逐一读取 `history[0]`，得到两个 system prompt SHA-256：

| 变体 | Full | Lite | 合计 | SHA-256 |
|---|---:|---:|---:|---|
| 四个可选参数在详细文档中标为 `required` | 1,753 | 249 | 2,002 | `bcf072797e41fd3f9111b36416fdd32269c98a830fe850324e68560883641e7d` |
| 四个可选参数标为 `optional` | 515 | 51 | 566 | `a4d3de50b84779d8b77c453db17183352e5c9b29280d12050504542dd9771db4` |

两种文本只在 `open` 的 `line_number`、`search_dir` 的 `dir`、`search_file` 的 `file`、`find_file` 的 `dir` 四个参数标签上不同；命令 signature 在两种文本中仍用方括号表示可选。差异按仓库分片集中出现，例如 Matplotlib、PyData、scikit-learn 基本使用 optional 版本，多数 Django、SymPy、pytest 使用 required 版本。这不是随机单实例噪声。

SWE-agent 初始提交的 system template、命令元数据和详细文档生成算法可逐字生成 optional 版本。把其中四个 `[optional]` 标签改为 `[required]` 后可逐字生成另一版本。因此公开运行很可能来自两个不同的运行工作树或依赖/序列化状态，而不是单一干净 Git 提交。

两种精确文本分别保存为：

- `data/derived/official_prompt_system_required.txt`；
- `data/derived/official_prompt_system_optional.txt`。

后续重跑必须先冻结实例到 prompt 变体的映射。把 2,568 个 episode 全部替换成任一单一版本，会改变原始协议。

### 4.2 instance template 与 demonstration

2,568/2,568 个实际 instance message 都可由 `SWE-agent@5b143857:config/default.yaml` 的 `instance_template`、冻结 issue 文本和运行目录逐字生成。论文时间快照 `658eb284` 已修正初始模板中的拼写和空白，因此不是逐字运行模板。

全部 2,568 条轨迹使用同一 demonstration message，SHA-256 为 `55f076f087bbe380ae06c6f8b624cceb56e7afa1c8589bbdfc91de0949e8e529`。精确 demonstration 与 instance template 分别保存为：

- `data/derived/official_prompt_demonstration.txt`；
- `data/derived/official_prompt_instance_template.txt`。

论文展示的 system/instance prompt 是编辑后的说明资产：修正了运行文本中的拼写，system 图用 `{documentation}` 代替完整详细命令文档，instance 图省略了一段“无输出复现脚本应打印成功消息”的建议。它们适合解释设计，但不能作为严格重跑的逐字输入。

### 4.3 没有单一公开提交完整代表实际配置

公开运行名称包含 `last_5_history`，论文也声明保留最近五个 observation；对应 `Last5Observations` 和命名配置直到 `08e66863` 才进入 Git。与此同时，实际 system/instance prompt 保留了初始提交中的旧拼写和旧命令文档，且 system prompt 还有 required/optional 两种版本。

因此实际协议是一个可从轨迹恢复、但不能由单一公开提交 checkout 得到的混合状态：

- prompt template 和多数命令元数据对应 `5b143857`；
- Last-5 处理器对应 `08e66863` 或此前未提交工作树；
- 2,002 条轨迹的四个 required 标签不对应初始 Git 元数据；
- `658eb284` 相对 optional/required 实际 system prompt 分别改变 2/6 行。

`658eb284` 继续作为“论文首次提交前最后快照”保留，但不能再称为实际运行 prompt 的精确代码版本。严格重跑应优先使用本实验导出的运行文本和分片映射，并把无法恢复的工作树状态列为协议差异。

## 5. ACI 命令实现与论文说明差异

论文命令表中的 10 个命令均可映射到初始提交的实现，具体 blob 写入 `data/derived/official_command_interface_audit.csv`。其中有三组需要保留的文档差异：

1. `scroll_down` 实现为 `CURRENT_LINE += WINDOW - OVERLAP`，`scroll_up` 为减法；论文命令表却把两者方向说明反写。实际 system prompt 中 `scroll_up` 的 signature 和 docstring 又都误写成 `scroll_down`，这是 2024-04-19 提交 `9aed8ba4` 只部分修正的历史问题。
2. 论文正文称每个搜索查询最多返回 50 个结果。初始实现中 `search_file` 在匹配行超过 100 时拒绝输出，`search_dir` 在匹配文件超过 100 时拒绝输出且单文件内可以有多个匹配，`find_file` 没有显式上限。论文“50”不能由该实现恢复。
3. 论文 linting 图使用轨迹期旧报错文案；`658eb284` 的 `edit_linting.sh` 已将首句改写为更明确的提示。拒绝错误 edit、展示拟应用/原始代码并恢复原文件的核心语义不变。

这些差异不会改变 ACI 组件是否存在的结论，但会影响逐字 prompt、动作可发现性和严格协议声明。

## 6. 界面资产核验

机器清单记录了 21 个 prompt/interface TeX 或 PDF 成员的字节数与 SHA-256。另从冻结 tar 包临时提取以下 7 份原始 PDF 做视觉检查：

- ACI/UI 对照；
- prompt flow；
- SWE-agent viewer/search components；
- file viewer；
- file editor；
- search comparison；
- edit comparison。

七份文件均为单页、未加密。Poppler 以 140 DPI 渲染后，标题、箭头、命令、代码、三栏对比和边界均清晰，无裁切、重叠或缺字。原 PDF 保持在 arXiv tar 包中，临时提取与渲染目录受 Git 忽略，不重复提交论文资产。

## 7. 可重复性与完成边界

脚本连续运行两次，四个 CSV 和四个精确 prompt 文本的 8/8 SHA-256 均保持不变。机器清单为 `data/manifests/official_qualitative_interface.json`。

A13 的公开 action、结果和 gold patch 已完整核验；展示层的两处差异已解释。A14 的全部公开 GPT-4 运行 prompt、10 个命令实现和论文界面资产已恢复并建立哈希，但发现两个 system prompt 变体和无法映射到单一 Git 提交的混合配置。该项可标记为“公开运行工件审计完成”，不能据此声称论文原模型严格重跑完成。
