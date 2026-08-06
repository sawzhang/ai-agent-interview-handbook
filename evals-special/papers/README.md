# 📚 前沿论文调研导读（2024–2026）

本目录是特辑的论文调研入口。**调研正文位于 `../_research/`**（写作素材目录），教学化综述见 **`../chapters/E14-前沿论文全景（2024-2026）.md`**。

## 调研概况

- **时间范围**：2024-01 ~ 2026-08 的 arxiv 前沿论文为主，奠基性更早工作作背景。
- **规模**：10 份主题报告，共 **233 个 arxiv ID**。
- **核实方式**：绝大多数经 arXiv API（id_list 批量）或 abs 页逐条核实标题与日期；调研过程中**纠正了数十个记忆中的错误 ID**（如 DyVal 2 实为 2402.14865、ASB 实为 2410.02644、"MMLU is not all it claims" 实为 "Are We Done with MMLU?" 2406.04127 等）；无法核实的条目在报告中明确标注【未核实】，引用前请自行复核。

## 十份报告索引

| 报告 | 主题 | 一句话看点 |
|---|---|---|
| [`_research/01-llm-judge.md`](../_research/01-llm-judge.md) | LLM-as-Judge | 偏差→元评估→可训练 judge→GEPA 与 judge 攻防四段演进 |
| [`_research/02-agent-benchmarks.md`](../_research/02-agent-benchmarks.md) | Agent 基准 | τ-bench/SWE-bench/GAIA/OSWorld/Terminal-Bench 全景与信任危机 |
| [`_research/03-trajectory-eval.md`](../_research/03-trajectory-eval.md) | 轨迹/过程评估 | PRM 奠基→标注自动化→Agent 化→元评估与信用分配 |
| [`_research/04-statistics.md`](../_research/04-statistics.md) | 评测统计学 | Bradley-Terry、bootstrap CI、样本量配方、Arena 可操纵性 |
| [`_research/05-benchmark-dynamics.md`](../_research/05-benchmark-dynamics.md) | 污染/饱和/动态基准 | Min-K% Prob、MMLU-Redux、LiveBench 系、GSM-Symbolic |
| [`_research/06-edd-simulation.md`](../_research/06-edd-simulation.md) | EDD 与仿真 | EDDOps 过程模型、τ-bench 系模拟器、CI 门禁、offline-online 一致性证据 |
| [`_research/07-safety-eval.md`](../_research/07-safety-eval.md) | 安全评测 | HarmBench/StrongREJECT/JailbreakBench/AgentDojo/InjecAgent |
| [`_research/08-component-rag.md`](../_research/08-component-rag.md) | 组件级/RAG | FActScore→SAFE→RAGChecker 的声明分解范式 |
| [`_research/09-self-improvement.md`](../_research/09-self-improvement.md) | 自改进闭环 | self-rewarding、reward hacking 实证、RLVR 与 Goodhart |
| [`_research/10-infra-observability.md`](../_research/10-infra-observability.md) | 基础设施/可观测性 | Inspect/HELM/lm-eval-harness、OTel GenAI semconv、trace 自动诊断 |

另有 [`_research/00-industry-practice.md`](../_research/00-industry-practice.md)：Airbnb / DoorDash / 阿里 / 腾讯四大工业实践一手精读笔记（E15 章的素材）。

## 推荐阅读顺序

1. 先读 `chapters/E14-前沿论文全景（2024-2026）.md` 建立全景（每方向演进主线 + 代表论文 + 未解问题）。
2. 对某方向感兴趣，再读对应 `_research/` 报告的「重点论文」逐篇解读与「争议与分歧」。
3. 引用任何论文前，以报告中的 arxiv 链接为准；标注【未核实】的条目请自行复核。
