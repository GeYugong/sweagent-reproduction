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
