# 🧪 Evals 特辑实验（Labs）

> 11 个**可直接运行**的评估体系实验，对应特辑各章。**纯 Python 标准库 + Mock LLM/Judge，零依赖、无需 API key**。
> 每个实验固定随机种子，**两次运行输出逐字节一致**；内置 assert 自检，运行成功打印 `✅ 自检通过`（已全部实测通过）。

## 运行方式

```bash
cd evals-special/labs
python3 eval_lab01_metric_system.py            # 任选一个直接跑
for f in eval_lab*.py; do python3 "$f"; done   # 或一次全跑
```

## 实验一览

| # | 文件 | 对应章节 | 你将搞懂 |
|---|---|---|---|
| 01 | `eval_lab01_metric_system.py` | E02 指标体系 | pass@k/pass^k 无偏 vs 朴素估计、N×K 结果矩阵、"至少一次成功 vs 连续成功"的门禁哲学 |
| 02 | `eval_lab02_golden_dataset.py` | E03 黄金数据集 | 四类来源构造（专家/LLM扩展/线上/回流）、五项入库标准、能力集→回归集毕业流转 |
| 03 | `eval_lab03_programmatic_scorers.py` | E04 程序化评分 | 五类规则评分器、统一五元组输出、粗筛→精判两层流水线（实测成本节省 43.9%） |
| 04 | `eval_lab04_judge_bias.py` | E05 LLM-as-Judge | 位置/冗长/自我偏好偏差的注入-量化-缓解全流程（swap 平均、异构投票、长度回归纠偏） |
| 05 | `eval_lab05_judge_calibration.py` | E05 LLM-as-Judge | 60 条 gold set 校准闭环：一致率 0.80→0.95、κ 0.571→0.895、kappa 悖论、升级监控三件套 |
| 06 | `eval_lab06_trajectory_eval.py` | E07 轨迹评估 | step/trajectory/session 三层评分、LCS+归一化对齐、**假阳性**（outcome 满分但路径违规）一票否决 |
| 07 | `eval_lab07_simulator_fixtures.py` | E08 仿真评测 | 状态机用户模拟器、fixtures 冻结外部状态、"漂移组方差 0.0278 vs fixture 组 0.0000" |
| 08 | `eval_lab08_statistics_ci.py` | E09 统计学 | Wilson vs Wald 覆盖率、bootstrap、样本量公式、+3% 差异在 N=100 不可判 / N=2000 可判 |
| 09 | `eval_lab09_rca_pipeline.py` | E11 RCA | 五步根因分析：现象×模块映射、三态诊断、三层定责漏斗、问题簇聚类（含阿里退款案例） |
| 10 | `eval_lab10_edd_loop.py` | E10 EDD | 完整闭环：P0 门禁决策表、一次一变量纪律、回归陷阱版本被拒、badcase 回流只增不减 |
| 11 | `eval_lab11_arena_bradley_terry.py` | E09/E13 竞技场 | BT MLE（MM 迭代）、Elo 顺序依赖、bootstrap CI、风格控制回归剥离长度/位置混杂 |

## 与主仓库 labs/ 的关系

- 主仓库 `labs/lab05_eval_harness.py` 是**最小评估 harness 入门**（eval set + rubric + 聚合 + trace 四件套）。
- 本目录是**体系化深挖**：指标→数据→评分→校准→轨迹→仿真→统计→RCA→闭环→竞技场，一条龙覆盖特辑 E02-E13。
- Mock 设计同构：所有 Mock LLM/Judge 实现 `chat()`/`__call__` 接口，与主仓库 `labs/llm_client.py` 的 `QwenLLM` 可互换——把 Mock 换成真实模型即可扩展成可上线系统。

## 学习建议

- 先读每个文件顶部的 docstring（【实验目的】【核心概念】【思考题】），再对照代码逐节理解。
- 每个实验末尾的**思考题**是面试延伸——先口述答案，再对照特辑章节核对。
- 改改参数看结果怎么变（如 lab04 的偏差强度、lab08 的样本量）——直觉来自动手。
