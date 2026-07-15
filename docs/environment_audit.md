# 环境审计

审计时间：2026-07-15（Asia/Shanghai）

## 本地环境

- 工作目录：`D:\0code\Research\05`
- 初始状态：`05` 在建立研究仓库前不是 Git 仓库。
- 论文 PDF：4,963,538 bytes，文件头为 `%PDF-`。
- PDF：arXiv v3，118 页，Letter 页面尺寸，未加密。
- PDF 文本抽取：可用。
- PDF 渲染：Poppler 可用；关键页 1、6、25 已渲染并视觉检查，正文、图 1、表 1-3 与表 5 清晰无裁切。
- 主机：32 GiB 内存、32 个逻辑处理器；实验不使用本地 GPU。
- WSL：Ubuntu 24.04，WSL2，systemd 已启用；发行版物理存储位于 `D:\2software\WSL\Ubuntu`。
- WSL 资源上限：20 GiB 内存、16 个处理器、8 GiB swap。
- Docker Engine：29.6.1；`hello-world` 与 `sweagent/swe-agent:latest` 均已验证。
- SWE-agent 镜像摘要：`sha256:11206d866593874eff52bc21642db7fc1169710e9dbd775e1596469ad5a20caa`。
- Python：uv 0.11.28 管理的 Python 3.9.25；隔离环境位于 WSL 用户目录。
- 物理 D 盘剩余空间：约 59 GiB（完成基础镜像和单实例 smoke 后）。

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
- Docker socket：`/var/run/docker.sock` 与 `/run/docker.sock` 均不存在。
- Environment Modules：未发现 `module`/`modulecmd` 入口。
- 常见系统路径：`/usr/bin`、`/usr/local/bin` 与 `/opt` 常见位置未发现上述容器运行时。
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

本地 WSL2 已成为主执行环境。模型推理通过远程 API 完成，本地只负责 Docker、仓库操作、依赖安装与测试，因此不需要 GPU。`sqlfluff__sqlfluff-1625` 已完成零 API 单实例闭环，证明数据集、容器、网络、依赖与轨迹落盘链路可用。

当前主要限制是物理磁盘容量。SWE-bench 官方建议至少准备约 120GB 可用空间，而当前 D 盘余量不足以安全缓存完整评测环境。因此先执行单实例与小批量实验，服务器仅作为未来并行或扩容备选。

## 项目隔离环境补充

- 项目内 conda 环境：`.venv`；
- Python：3.9.25，与上游 `environment.yml` 一致；
- conda/pip 缓存：`.cache`，未写入共享包缓存；
- SWE-agent import：通过；
- SWE-bench：固定为 1.0.1 后 import 通过；
- CLI help：通过；
- 离线测试：16 passed，6 deselected；
- OpenAI API key：未配置；
- 正式推理：未启动，API 费用为 0。
