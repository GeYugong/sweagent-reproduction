# 环境审计

审计时间：2026-07-15（Asia/Shanghai）

## 本地环境

- 工作目录：`D:\0code\Research\05`
- 初始状态：`05` 在建立研究仓库前不是 Git 仓库。
- 论文 PDF：4,963,538 bytes，文件头为 `%PDF-`。
- PDF：arXiv v3，118 页，Letter 页面尺寸，未加密。
- PDF 文本抽取：可用。
- PDF 渲染：Poppler 可用；关键页 1、6、25 已渲染并视觉检查，正文、图 1、表 1-3 与表 5 清晰无裁切。

## 服务器环境

- SSH 主机：`A40_Cluster_1`
- 用户：`mty`
- 项目边界：`/public/home/mty/GeYugong/`
- 计划目录：`/public/home/mty/GeYugong/05_sweagent_repro_ser/`
- GPU：节点可见 6×NVIDIA A40，每卡 46,068 MiB，驱动 535.230.02。
- 研究资源约束：只按 2 张 A40 设计，不占用额外可见 GPU。
- 内存：251 GiB，总可用约 213 GiB（审计时刻）。
- CPU：30 个逻辑核可见。
- Python：3.8.10。
- Git：2.25.1。
- conda：可用，但不得修改共享环境。
- Docker：命令不可用。
- Podman/Apptainer/Singularity/Enroot：命令均未发现。
- SLURM：`srun`、`sbatch`、`sinfo` 均未发现。
- 文件系统：`/public/home/mty` 总计 72 TiB，已用 71 TiB，可用约 2.0 TiB，使用率 98%。
- GPU 占用：审计时已有 4 个约 17-21 GiB 的计算进程，说明节点为共享状态。

## 阻塞与影响

### 容器后端缺失

论文版 SWE-agent 和 SWE-bench 官方评测都依赖 Docker 隔离任务仓库。当前服务器没有可直接调用的容器运行时，因此不能宣称已具备正式判分条件。

允许的后续路径：

1. 确认集群是否提供未加入 PATH 的 rootless Docker 或管理员维护的远程 Docker 服务；
2. 由管理员提供项目范围内可用的 Apptainer/Singularity；
3. 在具备 Docker 的另一台授权机器执行评测，服务器仅承担本地模型推理；
4. 仅为开发调试使用无容器模式，但不得把其结果作为 SWE-bench 正式分数。

未经授权不得安装系统级 Docker、修改 daemon、修改共享 conda 环境或全局配置。

### 磁盘接近满载

SWE-bench 镜像缓存可能占用 120GB 以上。当前文件系统使用率为 98%，即使显示仍有约 2TiB，也必须在拉取镜像和模型前确认个人配额、缓存位置和清理策略。

### Python 版本偏旧

服务器默认 Python 3.8.10 低于论文快照 `pyproject.toml` 的 Python >=3.9 要求。必须在项目目录内创建隔离环境或使用个人 conda 环境，不能修改共享环境。

## 当前结论

GPU、内存和 CPU 足以开展两卡本地模型实验，但容器后端是单实例正式闭环的首要阻塞项。环境解决前可以继续完成论文配置核对、数据清单设计、轨迹分析脚本和无模型测试，不能开始大规模评测。
