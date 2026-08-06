# 📗 Evals 知识体系特辑

> 主手册（AI Agent 面试学习手册）的**评估专题深度卷**：把 evals 体系讲透彻。
> 16 章知识体系 + 11 个可运行实验 + 2024–2026 前沿论文调研（10 份报告，233 个已核实 arxiv ID）+ 四大厂工业实践精读。
>
> **内容基准日：2026-08**。主手册第 8 章是面试浓缩版；本特辑是全景深挖版。

---

## 📦 交付物一览

```
evals-special/
├── README.md                 📍 你在这里
├── CHECKLIST-Agent评测体系建设.md ✅ 可直接套用的建设清单（Phase 0-10 + 30/90 天路线图）
├── chapters/                 📂 16 章知识体系（E00-E15，固定 6 模块结构）
├── labs/                     🧪 11 个纯标准库实验（零依赖、assert 自检、确定性可复现）
├── _research/                🔬 调研报告（00 工业实践精读 + 01~10 前沿论文调研）
├── papers/                   📚 前沿论文调研导读（指向 _research/ 与 E14）
└── _design/                  🛠️ 设计文档（蓝图/规格书/写作规范，生产流程记录）
```

## 🗺️ 知识体系结构

**为什么评 → 评什么 → 拿什么评 → 谁来评 → 评什么形态 → 分数怎么可信 → 怎么用评测驱动开发 → 外部坐标**

| 模块 | 章节 |
|---|---|
| 🧭 导读 | E00 特辑导读：Evals 体系全景 |
| 🧱 为什么 | E01 为什么评估是 GenAI 工程的生命线 |
| 🎯 评什么 | E02 评估指标体系（P0/P1/P2 · 五维度 · pass@k/pass^k） |
| 📦 拿什么评 | E03 黄金数据集与用例设计 |
| ⚖️ 谁来评（三层） | E04 程序化评分 · E05 LLM-as-Judge 深入 · E06 人工评估与评分路由 |
| 🔬 评什么形态 | E07 轨迹与 Agent 级评估 · E08 对话 Agent 与仿真评测 |
| 📐 分数可信 | E09 评估的统计学基础（CI / 样本量 / Bradley-Terry） |
| 🔄 驱动开发 | E10 评测驱动开发（EDD）· E11 Badcase 根因分析与优化闭环 · E12 在线评估与数据飞轮 |
| 🌐 外部坐标 | E13 Benchmark 全景与前沿争议 · E14 前沿论文全景（2024-2026）· E15 工业实践案例研究 |

**每章固定 6 模块**：知识图谱 → 核心概念精讲 → 面试高频考点（⭐分级）→ 经典面试题与参考答案 → 易错点·反直觉点 → 推荐资源。

## 🧪 动手实验（labs/）

11 个纯 Python 标准库实验，零依赖、固定种子、内置 assert 自检（全部实测通过，两次运行输出逐字节一致）：

| # | 文件 | 你将搞懂 |
|---|---|---|
| 01 | `eval_lab01_metric_system.py` | pass@k/pass^k 无偏估计、能力上限 vs 生产一致性、门禁哲学 |
| 02 | `eval_lab02_golden_dataset.py` | golden set 四类来源、入库标准、能力集→回归集"毕业"机制 |
| 03 | `eval_lab03_programmatic_scorers.py` | 规则评分器家族、粗筛→精判分层流水线与成本节省 |
| 04 | `eval_lab04_judge_bias.py` | 位置/冗长/自我偏好偏差量化 + swap、投票、长度纠偏缓解 |
| 05 | `eval_lab05_judge_calibration.py` | 校准闭环：一致率、Cohen's κ、分歧分析、rubric 迭代（一致率 0.80→0.95、κ 0.571→0.895 复现） |
| 06 | `eval_lab06_trajectory_eval.py` | step/trajectory/session 三层评估、LCS 对齐、假阳性（结果对路径错）捕获 |
| 07 | `eval_lab07_simulator_fixtures.py` | 会话模拟器 + fixtures：环境不受控时"分数测量的是噪声" |
| 08 | `eval_lab08_statistics_ci.py` | Wilson/bootstrap CI、样本量公式、配对显著性与"N=100 不可判、N=2000 可判" |
| 09 | `eval_lab09_rca_pipeline.py` | RCA 五步：现象×模块映射、分模块诊断、三层定责、问题簇聚类 |
| 10 | `eval_lab10_edd_loop.py` | EDD 全闭环：P0 门禁、一次一变量、回归陷阱拦截、badcase 回流 |
| 11 | `eval_lab11_arena_bradley_terry.py` | BT MLE、Elo、bootstrap 强度差 CI、风格控制回归 |

```bash
cd evals-special/labs
for f in eval_lab*.py; do python3 "$f"; done   # 一次全跑，全部 ✅ 自检通过
```

## 🔬 前沿论文调研（_research/）

| 报告 | 主题 |
|---|---|
| `00-industry-practice.md` | Airbnb / DoorDash / 阿里 / 腾讯四大工业实践一手精读笔记 |
| `01-llm-judge.md` | LLM-as-Judge：偏差、元评估、可训练 judge、GEPA、judge 攻防 |
| `02-agent-benchmarks.md` | Agent 基准全景：τ-bench、SWE-bench、GAIA、OSWorld、Terminal-Bench… |
| `03-trajectory-eval.md` | 轨迹/过程评估：PRM、Agent-as-a-Judge、信用分配 |
| `04-statistics.md` | 评测统计学：Bradley-Terry、Arena 方法论、样本量、可操纵性 |
| `05-benchmark-dynamics.md` | 污染检测、MMLU 危机、动态基准、生成式基准 |
| `06-edd-simulation.md` | EDD/EDDOps、用户模拟器、CI 门禁、offline-online 一致性 |
| `07-safety-eval.md` | 红队评测：HarmBench、StrongREJECT、AgentDojo、InjecAgent… |
| `08-component-rag.md` | 组件级评估：FActScore、SAFE、RAGChecker、归因评估 |
| `09-self-improvement.md` | self-rewarding、RLAIF、reward hacking、RLVR 与 Goodhart |
| `10-infra-observability.md` | 评测框架（Inspect/HELM）、OTel GenAI semconv、trace 自动诊断 |

共 233 个 arxiv ID，绝大多数经 arXiv API / abs 页逐条核实；未能核实的条目在报告中明确标注【未核实】。

## 🚀 学习路线

- **面试冲刺（2h）**：E02 → E05 → E07 → E09 → E15 的面试题区 + 各章「易错点」。
- **从零搭建评测体系（工程师）**：E01 → E03 → E04 → E05 → E06 → E10 → E11 → E12，配 labs 01→10 顺序动手；落地行动项直接对照 `CHECKLIST-Agent评测体系建设.md`（Phase 0-10 + 30/90 天路线图）。
- **研究跟进**：E14（全景）→ `_research/` 感兴趣方向的报告原文。

## ✅ 质量保证流程

1. **多智能体并行调研**：10 路主题并行检索 2024–2026 arxiv，逐条核实 arxiv ID（纠正了数十个记忆中的错误 ID）。
2. **蓝图先行**：`_design/BLUEPRINT.md`（16 章 brief）+ `_design/LAB_SPECS.md`（11 个 lab 规格）先定结构再写作。
3. **章节写作**：分三波多智能体并行，素材强制引用（数字与论文 ID 必须来自 `_research/`）。
4. **对抗性验证**：结构审查（6 模块/标题格式/面试题量）、arxiv 引用追溯（章节引用 100% 可回溯到素材）、labs 复跑 + 确定性双跑比对、交叉引用完整性——全部通过。
5. **工业数字忠实性**：Airbnb/DoorDash/阿里/腾讯数字全部引自原文精读笔记并注明公司。

## 📄 许可

沿用主仓库：文字内容 CC BY-NC-SA 4.0，代码（`labs/*.py`）MIT。
