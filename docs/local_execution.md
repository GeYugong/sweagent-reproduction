# 本地执行方案

## 计算边界

模型推理由 OpenAI 兼容 API 完成，本机不加载模型权重。WSL2 中的 Docker 只负责检出任务仓库、安装历史依赖、执行 agent 命令和运行测试。实验资源按 16 个 CPU、20 GiB 内存、8 GiB swap、0 GPU 规划。

## 可复现组件

- `conf/wslconfig.swebench`：WSL2 资源配置；
- `scripts/install_docker_wsl.sh`：Docker Engine 安装；
- `scripts/configure_docker_proxy_wsl.sh`：Docker daemon 代理；
- `scripts/setup_local_wsl_env.sh`：uv、Python 3.9 与论文依赖；
- `scripts/prepare_local_runtime.sh`：从冻结提交创建临时 worktree 并应用适配补丁；
- `scripts/run_local_api_instance.sh`：安全物化密钥、限制 API 次数并保存实例级轨迹；
- `scripts/setup_local_eval_env.sh`：建立独立的论文期评测环境；
- `scripts/run_local_evaluation.py`：运行论文快照 evaluator 并处理已撤回依赖；
- `scripts/run_local_api_batch.sh`：按冻结清单逐实例执行，默认一次只新增一个实例；
- `scripts/summarize_dev20.py`：从冻结清单、正式 scorecard 与轨迹自动核算完成数、resolve rate、API 调用和 token；
- `scripts/analyze_modern_dev20_baseline.py`：固定 20 个正式 run directory，生成 Wilson 区间、结果分布和逐文件 SHA-256；
- `patches/sweagent_local_api.patch`：容器代理、现代模型注册、调用次数上限与撤回依赖兼容。

原始子模块始终固定在 `658eb2842e8a8b00069b301338bc342b70538f7a`。运行副本位于被 Git 忽略的 `tmp/runtime/`，避免把适配改动混入论文快照。

## API 与费用控制

密钥保存在被 Git 忽略且限制 ACL 的环境文件中。探测脚本不打印密钥。中转接口未公开计费单价，因而运行适配层将模型美元单价设为 0，仅用于避免伪造费用；实际控制项为 `SWE_AGENT_MAX_API_CALLS`，轨迹继续记录输入 token、输出 token 和调用次数。

## 当前范围

本机已完成 SWE-bench Lite dev20 的逐实例推理与判分闭环。物理 D 盘余量约 64 GiB，低于正式批量运行的 120 GB 门槛，因此当前只允许顺序环境验证和已经授权的小批量实验。扩大到完整 Lite 或并行批次前，必须先增加磁盘空间或迁移到具备容器后端的服务器。

`gpt-5.6-terra` 默认 ACI 基线已完成冻结 dev20 的 20/20 个实例，其中 4 个 `RESOLVED_FULL`。该结果证明本地链路可以完成从 API 推理到正式判分的端到端流程，但属于现代模型 dev 基线，不是论文原模型严格重跑。

开发批次固定在 `data/manifests/swebench_lite_dev20_seed42.json`。批处理通过正式 scorecard 跳过已评测实例，每次调用默认最多新增 1 个实例，避免一次命令意外消耗完整 20 实例额度。汇总命令如下：

```powershell
python scripts\summarize_dev20.py `
  --manifest data\manifests\swebench_lite_dev20_seed42.json `
  --trace-root outputs\traces `
  --output-json outputs\summary\dev20_summary.json `
  --output-markdown outputs\summary\dev20_summary.md

wsl -d Ubuntu --cd /mnt/d/0code/Research/05 `
  .venv-analysis/bin/python scripts/analyze_modern_dev20_baseline.py
```

最终自动核算为 4/20 完全解决，resolve rate 20.00%，Wilson 95% CI 8.07%–41.60%。轨迹持久化 397 次 API 调用、5,496,947 input tokens 和 70,405 output tokens；资源日志另确认 1 次未持久化 usage 的最终格式重试，总调用为 398，token 合计因此保持下界。
