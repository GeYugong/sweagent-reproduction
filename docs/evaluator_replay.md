# 论文期 SWE-bench 评测聚合器重放

## 1. 结论

论文主实验的八组官方预测、评测日志和 `results.json` 已完成逐列表重放。固定论文期 evaluator 源码和 2024-04-15 数据集 revision 后，八组报告的十个类别列表均与官方 JSON **完全相同**，包括列表顺序、重复实例和重复次数：

- Lite：SWE-agent GPT-4、SWE-agent Claude 3 Opus、RAG GPT-4、RAG Claude 3 Opus；
- Full：SWE-agent GPT-4、SWE-agent Claude 3 Opus、RAG GPT-4、RAG Claude 3 Opus；
- 验收结果：`8/8` full-report exact match。

这项结果证明官方工件可以在不重新调用模型的情况下稳定重建，也定位了论文期 evaluator 与后续数据 revision 之间的判分漂移。它属于**历史日志与结果聚合重放**，尚不等同于从 prediction patch 重新创建 2,594 个容器并执行全部测试；小样本容器级重放仍作为下一层验证单独执行。

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

## 7. 当前完成边界

已完成：

- 官方预测到官方 `results.json` 的历史聚合器重放；
- 论文期 evaluator 源码和数据 revision 的精确定位；
- 重复预测、空补丁、缺失实例与类别分母语义恢复；
- 后续数据 revision 引起的 resolved 漂移定位。

尚未完成：

- 选定 gold、resolved、unresolved、patch-apply failure、空 patch 和重复预测代表实例的容器级重新执行；
- 全量 2,294/300 实例从 patch 开始的容器重评；
- 严格原模型重新推理。

因此 `G_EVALUATOR_REPLAY` 保持“聚合层完成、容器层进行中”，不能提前标为整个严格复现完成。
