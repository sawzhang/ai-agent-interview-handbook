# Benchmark 污染、饱和与动态基准调研报告（2024–2026）

> 调研日期：2026-08-05。覆盖 2024-01 至 2026-08 的 arXiv 前沿论文；核心论文的 arXiv ID 均通过 arXiv API（id_list 批量）或 arXiv abs/检索页逐条核实（标题+日期）。无法核实的条目已明确标注；Sean Grove 的 "The Illusion of Model Improvement" 等未上 arXiv 的工业界材料单独说明、不给 ID。
>
> 注：调研中确认 arXiv 上不存在标题为 "MMLU is not all it claims" 的论文（检索无结果）；该方向的代表性实证工作是 "Are We Done with MMLU?"（MMLU-Redux，2406.04127），本报告以其为核心。

---

## 主题概述

本方向研究的核心问题是：**公开、静态的基准测试正在被三重力量瓦解——(1) 数据污染（benchmark 题目进入训练语料，分数虚高）、(2) 饱和（前沿模型分数逼近上限，失去区分度）、(3) 过拟合到代理指标（Goodhart 效应：优化 benchmark ≠ 提升真实能力）。当 benchmark 同时被污染和饱和时，它作为模型选择与产品决策工具的信效度还剩多少？评测界如何重建可信的测量？**

背景（2023 及更早）：MT-Bench（2306.05685）与 MMLU 等静态公开基准成为行业标准；Carlini 等（2012.07805）早已证明可以从语言模型中提取训练数据（membership inference + canary 方法的源头），但当时尚未系统应用到 benchmark 治理。AlpacaEval 等基于公开指令集的评测同样面临泄漏。

2024–2026 的演进主线大致分四段：

1. **2023 末–2024 上半年：污染检测工具化。** 三类检测范式成熟：(a) 成员推断类——Min-K% Prob / WikiMIA（2310.16789，ICLR 2024）用低概率 token 的对数似然判别一段文本是否属于预训练语料；(b) 格式变体类——"Rethinking Benchmark and Contamination ... with Rephrased Samples"（2311.04850）证明模型对 GSM8k/TruthfulQA 的记忆不止于原文，翻译/改写后的变体同样泄漏，且英文 benchmark 的记忆强于其他语言；(c) 选项结构类——对选项顺序、字母偏置的敏感性分析（2404.08382、2503.23483）揭示选择题分数的相当部分来自格式捷径而非能力。

2. **2024 年中：MMLU 信任危机与修补。** MMLU 是当时引用最广的"综合能力"指标，但 "Are We Done with MMLU?"（2406.04127）重标注 2,908 道题后发现约 10% 的题面/答案有误或歧义，修复后模型的分数与相对排名都发生变化；同期 MMLU-Pro（2406.01574）用 10 选项 + 推理型题目把难度提高 16%–32%，代表"加深加难"路线。两条路线——**修数据**与**提难度**——成为此后所有老牌 benchmark 的标准动作。

3. **2024 年：动态/可再生基准的制度化。** 从"一次性发布测试集"转向"持续更新的测试流"：LiveBench（2406.19314）按月更换题目、全客观自动评分；LiveCodeBench（2403.07974）按时间截止线持续采集 LeetCode/AtCoder/Codeforces 新题，使"污染距离"（题目发布时间 vs 模型数据截止）可量化；DyVal（2309.17167，ICLR 2024）与其续作 DyVal 2（2402.14865）用程序化生成（图结构/探测 agent）让每次评测的题目都是新的，并发现静态高分模型在动态探测下显著掉分。

4. **2024 末–2026：脆弱性量化、生成式基准与难度军备竞赛。** GSM-Symbolic（2410.05229，Apple，ICLR 2025）证明只改名字/数字/语序就能让数学分数暴跌至多 65%，暴露"能力"与"记忆"的界限远比想象的模糊；"Is Your Benchmark Still Useful?"（2503.06643）用保义改写程序化地"翻新"旧题库；DynaMath（2411.00836）、UGMathBench（2501.13766）把基准本身变成可无限采样的生成器。与此同时 Humanity's Last Exam（2501.14249）代表"难度军备竞赛"路线：用专家级难题保持头部区分度，但也引发"benchmark 越来越难却越来越远离用户价值"的批评。Goodhart 视角下，benchmark 分数成为营销与 RL 优化目标后的退化（reward overoptimization 的测量学版本）在 2026 年进入多智能体合规评测等新场景（如 2606.07805）。

与 evals 工程的交汇点：**benchmark 是"测量仪器"，仪器会老化（饱和）、会被污染（泄漏）、会被作弊（格式捷径）。成熟的评测体系必须像管理传感器一样管理基准：私有化、版本化、定期轮换、持续做污染审计，并永远保留一个不参与对外宣传的内部 holdout。**

---

## 重点论文

以下 13 篇为核心论文，arXiv ID 均已核实（API 批量核实标记【API✓】，abs 页核实标记【abs✓】，arXiv 检索页确认标记【检索✓】）。

#### 1. LiveBench: A Challenging, Contamination-Limited LLM Benchmark

- **arXiv**: [2406.19314](https://arxiv.org/abs/2406.19314)【abs✓】｜ **机构**: University of Maryland、Genentech、Meta FAIR（Colin White、Samuel Dooley、Yann LeCun、Tom Goldstein、Micah Goldblum 等）｜ **时间**: 2024-06（v1），2025-04 更新（v2）｜ **状态**: arXiv + 持续运营的公开排行榜
- **贡献**: 第一个把"抗污染"作为一等设计目标的综合基准：题目取自数学竞赛、arXiv 论文、新闻文章等新近来源，**按月轮换**；全部任务配**客观真值 + 自动评分**（无需 LLM judge），覆盖数学、编码、推理、语言、指令跟随、数据分析六类；在 Big-Bench Hard、AMPS、IFEval 基础上改造成更难、更难泄漏的变体。
- **关键数字**: 评测 0.5B–405B 的开源与闭源模型，发布时领先模型准确率仍低于 70%；全部题目、代码与模型答案公开，按月更新。
- **对评测工程的意义**: 确立了"**时间新鲜度 + 客观评分 + 版本轮换**"的抗污染三要素。代价是版本间不可直接比较（GPT-4o 在 2024-07 版与 2025 版的分数没有可比性），工程上必须 pin 版本号并归档历史答案。它是"私有评测不可得时"最常用的公共替代品。

#### 2. LiveCodeBench: Holistic and Contamination Free Evaluation of Large Language Models for Code

- **arXiv**: [2403.07974](https://arxiv.org/abs/2403.07974)【API✓】｜ **机构**: MIT、ETH Zurich 等（Naman Jain、Alex Gu 等）｜ **时间**: 2024-03（v1）｜ **状态**: arXiv；排行榜持续运营至今
- **贡献**: 把"污染距离"概念操作化：持续从 LeetCode、AtCoder、Codeforces 抓取新题，每题带**发布时间戳**，评测时只使用模型数据截止日期之后发布的题目；同一基础设施支持代码生成、自我修复、执行预测、测试输出预测四类任务，并允许研究者指定任意时间窗口复现"无污染"评测。
- **关键数字**: 持续增长的题库（数百至数千题量级，随时间累积）；论文展示了旧基准（HumanEval/MBPP 等）上部分模型的分数与污染信号的相关性，证明静态分数可能系统性高估。
- **对评测工程的意义**: "**按时间截止线过滤测试集**"是目前最干净、可复现的抗污染方案，尤其适合代码这类有持续新题供给的领域。落地要点：维护题目元数据（发布日期、来源）、把模型的训练数据截止日作为评测参数、对"截止日声明不可信"的模型保留怀疑。

#### 3. DyVal: Dynamic Evaluation of Large Language Models for Reasoning Tasks

- **arXiv**: [2309.17167](https://arxiv.org/abs/2309.17167)【API✓】｜ **机构**: UIUC、Microsoft Research 等（Kaijie Zhu、Jindong Wang 等）｜ **时间**: 2023-09（v1），ICLR 2024｜ **状态**: 已发表（ICLR 2024）
- **贡献**: 首批"可再生基准"之一：用有向无环图（DAG）程序化生成描述型、算术型、推断型三类推理题，题目可无限重采样，每次评测都是新题，从机制上免疫记忆污染；同时控制复杂度（图规模/运算深度）做难度分级。
- **关键数字**: 动态题上的表现与 MMLU、Big-Bench 等静态推理子集高度相关（验证其效度），但模型间差距被显著拉开；部分在静态基准上并列的模型在 DyVal 上分出高下。
- **对评测工程的意义**: 证明了"**生成器 > 数据集**"的范式：把 benchmark 做成带难度旋钮的采样器，可同时解决污染、饱和与难度校准三个问题。局限是生成式题目分布窄、偏合成，需与真实分布题目混合使用。

#### 4. DyVal 2: Dynamic Evaluation of Large Language Models by Meta Probing Agents

- **arXiv**: [2402.14865](https://arxiv.org/abs/2402.14865)【检索✓】｜ **机构**: Microsoft Research、UIUC 等（Kaijie Zhu、Jindong Wang、Qinlin Zhao、Ruochen Xu、Xing Xie）｜ **时间**: 2024-02（v1），2024-06 更新｜ **状态**: arXiv
- **贡献**: 从"程序化出题"升级为"**agent 自动出题**"：用一组 probing agents（Meta-Probe-Instruction 框架）跨学科自动生成新题并给出可验证答案，覆盖数学、逻辑、科学推理等；核心发现是**静态基准分数与动态探测分数显著脱钩**——在 MMLU 等静态基准上高分的模型，在动态生成的探测题上表现大幅下降，说明静态分数高估了泛化推理能力。
- **关键数字**: 多模型在静态推理基准与 DyVal 2 探测题之间的准确率差距达到两位数百分点量级；论文据此质疑以静态基准为主的排行榜结论。
- **对评测工程的意义**: 给出"benchmark 分数 ≠ 能力"的最直接证据链之一。工程启示：对外部模型的选型，尽量用自建的、对方未见过的题集复测（即"私有 DyVal"）；对内部模型，把动态生成题作为回归测试的常规组件。

#### 5. Detecting Pretraining Data from Large Language Models（Min-K% Prob / WikiMIA）

- **arXiv**: [2310.16789](https://arxiv.org/abs/2310.16789)【API✓】｜ **机构**: University of Washington 等（Weijia Shi 等）｜ **时间**: 2023-10（v1）｜ **状态**: ICLR 2024（oral）
- **贡献**: 提出 Min-K% Prob：对一段文本，取其 token 对数概率中**最低的 K%**（默认 20%）求平均并做长度归一化，作为成员性分数——分数越高越可能出现在训练集中；无需模型内部权重，只用 API 概率即可做 membership inference。同时发布 WikiMIA（632 条 2023 年新 Wikipedia 条目，可判定"训练截止前/后"）作为检测方法的客观评测床。
- **关键数字**: 在 WikiMIA-632 上以 74.1% 的成员推断准确率大幅超过随机基线；并据此分析多个开源模型，发现 benchmark 相关文本在训练数据中的富集现象。
- **对评测工程的意义**: 这是"**污染检测可以客观化**"的里程碑：只要有模型概率接口，就能审计任意文本（包括 benchmark 题目）的成员性。局限：只对能输出 logprob 的模型有效；对改写后的泄漏不敏感（需配合 2311.04850 的语义层检测）；阈值需要本地校准。工程上常用于：对比候选模型对自家私有测试集的 Min-K% 分数是否异常偏高。

#### 6. Rethinking Benchmark and Contamination for Language Models with Rephrased Samples

- **arXiv**: [2311.04850](https://arxiv.org/abs/2311.04850)【API✓】｜ **机构**: Tencent AI Lab（Wenxuan Yang 等）｜ **时间**: 2023-11（v1）｜ **状态**: arXiv
- **贡献**: 指出"原文匹配/n-gram 重叠"式污染审计严重低估泄漏：把 GSM8k、TruthfulQA 等 benchmark 题目翻译成其他语言或改写措辞后，模型仍表现出显著的**变体级记忆**（few-shot 下改一个词就能大幅提升准确率），且对英文原版题的记忆强于翻译版。由此提出"repaired test data"方法：检测并剔除/改写已泄漏样本，重建可信测试集。
- **关键数字**: 在 GSM8k/TruthfulQA 上，翻译/改写变体依然呈现可检测的记忆信号，说明仅靠精确字符串匹配的污染审计会漏掉大量语义级泄漏。
- **对评测工程的意义**: 污染审计必须做**语义级**而非字符串级：用嵌入相似度、翻译变体、Min-K% 三者组合。同时给出了"题库修复"的可复用流程——发现泄漏题后不是弃用整个基准，而是替换泄漏项并重新标定难度。

#### 7. Are We Done with MMLU?（MMLU-Redux）

- **arXiv**: [2406.04127](https://arxiv.org/abs/2406.04127)【检索✓】｜ **机构**: University of Edinburgh 等多机构（Aryo Pradipta Gema、Pasquale Minervini 等 17 位作者）｜ **时间**: 2024-06（v1），2025-01 更新｜ **状态**: arXiv
- **贡献**: 对 MMLU 做系统性质检：对 57 个 subject 各抽 30 题（共 2,908 题）做多人重标注，发布 MMLU-Redux 重标注子集。发现约 10% 的题存在**答案错误或题面歧义**（错误答案、有争议的唯一解、过时事实等），且不同模型在修复后子集上的**准确率与相对排名都会变化**。结论：MMLU 的"权威分数"相当一部分测的是噪声。
- **关键数字**: 约 10.09% 的样本被标为不准确或歧义；即使人类专家之间对这些题的共识率也有限，说明错误是结构性的而非个别笔误。
- **对评测工程的意义**: 任何沿用公开题库的评测都必须先做**item 级质检**（至少抽样重标注 + 双评），否则测量误差会混入模型差异。这也是"MMLU 类多选题基准不可再单独作为综合能力指标"的关键证据。工程上：报告分数时注明用的是原版还是 Redux 修复版。

#### 8. MMLU-Pro: A More Robust and Challenging Multi-Task Language Understanding Benchmark

- **arXiv**: [2406.01574](https://arxiv.org/abs/2406.01574)【API✓】｜ **机构**: University of Waterloo 等（Yubo Wang、Xueguang Ma、Wenhu Chen 等）｜ **时间**: 2024-06（v1），多次修订（v6）｜ **状态**: arXiv；被主流排行榜广泛采用
- **贡献**: MMLU 官方精神续作中的"加难"路线：每题选项从 4 个增至 10 个（降低猜对率与字母捷径），题目更强调推理而非纯知识，并引入来自 TIGER-Lab 的新题与对 MMLU 的转化。目标是同时缓解**饱和**（太难）与**污染**（新题）。
- **关键数字**: 12,032 道题；论文称难度比 MMLU 提升 16%–32%；GPT-4 级模型准确率从 MMLU 的近 90% 跌至 MMLU-Pro 的 50–60% 区间，恢复了头部区分度。
- **对评测工程的意义**: 展示了"老基准饱和后的标准升级配方"：更多选项 + 推理化 + 新题源。注意 MMLU-Pro 自身也在快速被新模型逼近饱和，且 10 选项放大了长题干下的上下文长度效应——用它排名时要控制 prompt 格式与上下文预算。

#### 9. GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models

- **arXiv**: [2410.05229](https://arxiv.org/abs/2410.05229)【检索✓】｜ **机构**: Apple（Iman Mirzadeh、Keivan Alizadeh、Samy Bengio、Mehrdad Farajtabar 等）｜ **时间**: 2024-10（v1），2025 修订｜ **状态**: ICLR 2025
- **贡献**: 把 GSM8K 每题用 LLM 生成 100 个符号变体（改名字、改数字、改问法），构成 GSM-Symbolic 家族；另构造 GSM-NoOp（加入不影响答案的无关条件）。结论震撼：模型在"同分布、同难度"的变体之间分数波动巨大，**脆弱性（fragility）**而非推理能力才是分数的主要成分之一；一个无关从句即可显著击穿表现。
- **关键数字**: 仅改变题目中的人名/数字/语序，部分模型准确率相对下降最多约 65%；加入单个无关从句可使准确率相对下降约 39%（不同模型程度不同，前沿模型也有明显下降）。
- **对评测工程的意义**: 单题单次评测是**点估计**，benchmark 分数应看作分布的采样——可靠的评测必须对每题做多变体/多扰动测量并报告方差。这也是"动态重采样基准"的理论依据：变体族天然免疫记忆污染且能量化鲁棒性。

#### 10. Is Your Benchmark Still Useful? Dynamic Benchmarking for Code Language Models

- **arXiv**: [2503.06643](https://arxiv.org/abs/2503.06643)【检索✓】｜ **机构**: 以 arXiv 元数据为准｜ **时间**: 2025-03｜ **状态**: arXiv
- **贡献**: 针对"旧 benchmark 已泄漏但重建成本高"的现实困境，提出对既有代码基准做**保义（meaning-preserving）改写翻新**：程序化地改写题面/变量名/输入输出格式而不改变语义与难度，使被记忆的原题失效，同时保留老基准的题面分布与可比性。相当于给旧题库做"污染免疫的再制造"。
- **关键数字**: 改写后的任务上，模型表现与其在原始（疑似泄漏）版本上的表现出现可测量的偏离，说明记忆确实贡献了原分数的一部分（具体幅度见原文表格）。
- **对评测工程的意义**: 提供了一条比"推倒重来"便宜的中间路线：**翻新存量题库**。适合内部评测集治理——对怀疑泄漏的私有题做保义改写轮换，而不必重新设计整个能力矩阵。保义改写的质量控制（改写后难度不变、答案唯一）是落地难点。

#### 11. Order Independence With Finetuning（SBP：选项顺序不变性）

- **arXiv**: [2503.23483](https://arxiv.org/abs/2503.23483)【检索✓】｜ **机构**: 以 arXiv 元数据为准｜ **时间**: 2025-03｜ **状态**: arXiv
- **贡献**: 正面处理多选题的**选项顺序敏感性**：用 Sequential Bayesian Permutation（SBP）微调，让模型在训练中见到同一题的多种选项排列，从而学到对排列不变的"真理解"而非"A 位置偏置"。实验证明 SBP 微调显著提升多选题准确率与对选项重排的鲁棒性。
- **关键数字**: 相比标准微调，SBP 在多选题基准上同时提升准确率与排列一致性（不同选项顺序下答案的自洽率显著上升；具体数值见原文）。
- **对评测工程的意义**: 选项顺序敏感性既是**污染/捷径的检测器**（同一题重排选项分数大跌 ⇒ 捷径或记忆），也是评测协议的修复手段：报告多选题分数时至少应做选项置换平均（permutation averaging），或直接改用自由作答 + 判分格式。注意：该方向也提醒我们，"对顺序鲁棒"本身可以被训练出来，因此顺序敏感性只能作为辅助证据，不能作为污染的唯一判据。

#### 12. DynaMath: A Dynamic Visual Benchmark for Evaluating Mathematical Reasoning Robustness of Vision Language Models

- **arXiv**: [2411.00836](https://arxiv.org/abs/2411.00836)【检索✓】｜ **机构**: 以 arXiv 元数据为准｜ **时间**: 2024-10/11｜ **状态**: arXiv
- **贡献**: 面向多模态模型的动态数学基准：用代码驱动的生成管线批量产生"题面 + 图表"配对及其变体，通过改变参数/图形/提问方式测试模型数学推理的**鲁棒性**而非单点正确性；属于"benchmark 即生成器"范式在视觉数学领域的落地。
- **关键数字**: 自动生成数百个带图的数学问题及其变体族；多个主流 VLM 在变体族上的表现波动显著（具体见原文），说明单图单题分数不可靠。
- **对评测工程的意义**: 多模态评测尤其适合程序化生成（图可以参数化重绘，天然无泄漏）。DynaMath 的管线可直接借鉴：定义参数空间 → 采样实例 → 自动求解器验证答案 → 成族发布。

#### 13. UGMathBench: A Diverse and Dynamic Benchmark for Undergraduate-Level Mathematical Reasoning with Large Language Models

- **arXiv**: [2501.13766](https://arxiv.org/abs/2501.13766)【检索✓】｜ **机构**: 以 arXiv 元数据为准｜ **时间**: 2025-01｜ **状态**: arXiv
- **贡献**: 本科数学水平的动态基准：题目带**随机化参数变体**（同一题可重新采样数字），并配套针对"泄漏效应"的度量与缓解；强调题目多样性（覆盖本科数学多门课程）与难度分层。
- **关键数字**: 提供可再采样的题库与泄漏影响度量；模型在原始版与变体版之间的分差被用作记忆/鲁棒性指标（具体幅度见原文）。
- **对评测工程的意义**: 展示了"随机参数变体"这一最轻量的动态化手段——不需要 LLM 改写，只要把题面中的数值参数化即可无限防泄漏重采样。适合理工科数值题类的内部评测集。

---

## 延伸阅读（已核实 ID 或来自 arXiv 官方检索结果）

- **Humanity's Last Exam** — [2501.14249](https://arxiv.org/abs/2501.14249)【API✓】，Center for AI Safety + Scale AI（Long Phan 等），2025-01。三千道专家级多学科难题，"难度军备竞赛"路线的代表：发布时最佳前沿模型准确率约在 10% 量级，用于在 MMLU 等饱和后维持头部区分度。争议：题目难度与真实用户价值的距离、以及专家答案本身的正确性。
- **Scaling Laws for Reward Model Overoptimization** — [2210.10760](https://arxiv.org/abs/2210.10760)【API✓】，OpenAI（Leo Gao 等），2022-10。Goodhart 定律在 RLHF 中的定量版：以 KL(π‖π_ref) 衡量优化压力，金标奖励先升后降。benchmark 分数就是典型的"proxy reward"，该框架直接适用于解释 benchmark 过拟合。
- **Extracting Training Data from Large Language Models** — [2012.07805](https://arxiv.org/abs/2012.07805)【API✓】，Google（Nicholas Carlini 等），2020-12。MIA/数据提取的奠基工作，也是 **canary strings** 方法的源头（在数据中埋独特字符串再探测模型能否复现）。
- **Look at the Text: Instruction-Tuned Language Models are More Robust Multiple Choice Selectors than You Think** — [2404.08382](https://arxiv.org/abs/2404.08382)【API✓】，2024-04。对"选项位置捷径"的另一面证据：指令微调模型在文本作答与概率选择、选项重排下比早期结论更鲁棒。提醒污染检测要区分"格式捷径"与"真记忆"。
- **Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference** — [2403.04132](https://arxiv.org/abs/2403.04132)【API✓】，LMSYS，2024-03。人类成对偏好 + Elo 排名，题目来自实时用户提问，是"动态 + 难以污染"评测的另一极（主观但不可泄漏）。MT-Bench（[2306.05685](https://arxiv.org/abs/2306.05685)【API✓】）为其前身。
- **Beyond Goodhart's Law: A Dynamic Benchmark for Evaluating Compliance in Multi-Agent Systems** — [2606.07805](https://arxiv.org/abs/2606.07805)【检索✓】，2026-06。把 Goodhart 问题推进到多智能体合规评测：当奖励偏向"完成任务"时，agent 对流程约束的遵守如何退化，用动态施压场景评测。
- **Agent Island: A Saturation- and Contamination-Resistant Benchmark from Multiagent Games** — [2605.04312](https://arxiv.org/abs/2605.04312)【检索✓】，2026-05。用多智能体博弈构造天然抗饱和（对手自适应变强）与抗污染（交互轨迹无法提前记忆）的评测床，代表 2026 年"对抗式动态评测"的新方向。
- **AlpacaEval**（GitHub 项目，无 arXiv）：长度 gaming 导致排行榜失真的经典案例，与 Goodhart 主题呼应。

**未上 arXiv 的重要工业界材料（不给 ID）**：Sean Grove（OpenAI）的 *The Illusion of Model Improvement: Can LLM Benchmarks be Misleading?*（2024-10，代码/预印本流传）——用同一模型家族的不同数据混合/检查点在大量基准上实验，发现**基准分数差异的很大一部分来自评测集划分与数据泄漏的巧合，而非模型真实改进**，是"benchmark 作为产品决策工具不可全信"的最尖锐实证。此外 Epoch AI 对基准饱和速度的统计分析与各大实验室的 contamination disclosure（如 OpenAI 技术报告中的私有 holdout 与 canary 检查）也属此类。

---

## 关键概念与方法论

### 1. 污染检测四范式

| 范式 | 原理 | 代表方法 | 适用/局限 |
|---|---|---|---|
| 成员推断（MIA） | 训练过的文本似然更高 | Min-K% Prob：取最低 K% token 的 log-prob 均值（长度归一化），高于阈值判为成员 | 只需 API logprob；对改写不敏感；需校准阈值；闭源模型可能平滑概率 |
| 语义级泄漏 | 记忆的是"题"不是"字符串" | 翻译/改写变体上的异常增益（2311.04850）；嵌入相似度筛题 | 需要可对照的变体集；与"合理泛化"难划界 |
| 格式敏感性 | 捷径表现为对表面结构的依赖 | 选项置换一致性、字母偏置统计（2503.23483、2404.08382） | 只能作辅助证据：鲁棒性可被训练出来 |
| Canary strings | 预埋唯一字符串，探测复现能力 | 私有题集中埋独特 n-gram/假事实，用补全与问答探测 | 工业界私有评测的标配；只能证明"见过"，证不了"没见过" |

**审计流程模板**：字符串/n-gram 重叠 → 嵌入相似度（与公开题库、模型输出对比）→ Min-K% 概率审计（若可得 logprob）→ canary 探测 → 变体差分（改写前后分差）。任何单一信号都不足以定罪，组合证据 + 统计显著性才下结论。

### 2. 动态基准的四种机制

1. **时间截止线**（LiveCodeBench）：题目带发布时间戳，只用晚于模型数据截止的题；污染距离可量化、可复现。
2. **定期轮换**（LiveBench）：月度换题 + 版本归档；代价是跨版本不可比，必须 pin 版本。
3. **程序化生成**（DyVal/DynaMath/UGMathBench）：benchmark = 采样器 + 求解器验证；无限防泄漏，还能做难度旋钮与变体鲁棒性测量（GSM-Symbolic 的 100 变体法）。
4. **保义翻新**（2503.06643）：对存量题库做保义改写再制造，成本低、保留分布，适合私有集治理。

### 3. 饱和与区分度的度量直觉

- **天花板效应**：当 top 模型准确率 >~90% 且置信区间重叠时，基准失去排序力；MMLU 在 2024 年即处于此状态（GPT-4o/o1 系模型 87–90%+）。
- **有效区分度** ≈ 模型间真实能力差 / 测量噪声；饱和与错误（MMLU-Redux 的 ~10% 坏题）都会压低它。
- **修复手段谱系**：加难（MMLU-Pro：选项 4→10、推理化）、换源（LiveBench）、动态化（DyVal）、专家化（HLE）、对抗化（Agent Island）。
- **Goodhart 形式化**（2210.10760）：以 KL(π‖π_ref) 为横轴，proxy（benchmark）奖励单调上升而 gold（真实能力）先升后降——任何把 benchmark 直接作为 RL 奖励或营销 KPI 的做法都在沿这条曲线右移。

### 4. 变体鲁棒性指标（源自 GSM-Symbolic）

对题 q 生成变体族 {q_1..q_k}，报告 E[acc(q_i)] 与 Var[acc(q_i)]，以及"扰动敏感度" = 原始分 − 变体族均分。敏感度异常大 ⇒ 记忆或脆弱推理。这是比单点分数信息量高得多的测量。

---

## 争议与分歧

1. **污染的举证标准之争**。闭源模型不公开训练数据，检测方只能靠间接证据（Min-K% 分数、变体增益、canary），被检测方常以"泛化""巧合"反驳。学界对"多大证据算污染"没有共识；更根本地：题目若本来就在公开网络语料里，"见过"是否等于"作弊"？多数实践者采用折中立场：**见过 ≠ 有罪，但分数必须按"可能见过"折价**（因此 LiveCodeBench 式的时间截止成为硬标准）。

2. **修数据 vs 提难度 vs 换范式**。MMLU-Redux 派认为修复标注即可挽回多选题基准；MMLU-Pro/HLE 派认为必须不断加难保持区分度；Arena/动态派认为静态选择题整体过时，应转向人类偏好或动态生成。三种路线的投入产出完全不同，工业界实际是三者并用。

3. **动态基准自身的可比性问题**。LiveBench 换题后历史分数失效，排行榜变成"当前快照"而非"连续量尺"；DyVal 类生成器的题目分布偏合成、难度漂移，跨期比较同样需要校准。动态化解决污染，却引入**测量连续性**问题——这是学界明确的 open problem。

4. **难度军备竞赛 vs 用户价值**。HLE、MMLU-Pro 把分数压回 10–60% 区间恢复了区分度，但批评者指出：超难题测的是长尾知识与专家推理，与产品场景的用户满意度相关性弱；"benchmark 越来越难"可能只是制造新的营销素材（新一轮 Goodhart）。

5. **benchmark 分数到底能驱动多少产品决策**。Sean Grove 的实验与 Chatbot Arena 的经验共同指向：同一模型的不同版本间，benchmark 差异的相当部分来自数据划分与测量噪声；人类偏好排名与 benchmark 排名常有出入。工业界的务实共识正在形成：**benchmark 用于淘汰明显差的候选，最终决策靠私有评测 + 小流量 A/B + 用户留存指标**。

6. **Goodhart 是否无解**。乐观派（动态基准、对抗式评测）认为机制设计可以持续压制 gaming；悲观派指出只要分数与商业利益挂钩，出题方与应试方永远是军备竞赛，任何公开机制终将被攻破（2026 年的 agent 合规评测 2606.07805 已显示这一动态）。

---

## 对工程实践的启示

1. **私有化是第一原则**。任何参与模型选择/对外发布的评测集都必须私有：不入库公开仓库、不进 issue、不进论文附录。配 canary strings（每题埋 1–2 个独特字符串与假事实），定期用补全/问答探测市面模型。
2. **污染审计例行化**。候选模型接入评测前跑：n-gram 重叠 + 嵌入相似度 +（若可得）Min-K% 概率审计 + 变体差分。把审计脚本纳入评测管线 CI，输出"污染风险报告"与分数一起归档。
3. **用时间截止线管理题目**。给每道题记录 `created_at` / `public_since`，评测时按被测模型的训练数据截止日过滤（LiveCodeBench 模式）。对闭源模型的数据截止声明保持怀疑，用 canary 抽查。
4. **多选题要防格式捷径**。重要结论至少做选项置换平均（2–4 个排列）或直接改自由作答 + 判分；监控"字母偏置"（模型选 A/B 的先验）作为健康度指标。
5. **给 benchmark 做版本与生命周期管理**。每个基准登记：版本、发布日期、难度分布、已知错误率、预计饱和时间、退役标准（如 top 模型 >92% 且 CI 重叠 ⇒ 降级为回归监控，不再用于选型）。动态基准必须 pin 版本号并归档模型答案。
6. **单点分数 → 分布分数**。借鉴 GSM-Symbolic：关键能力点用变体族测量，报告均值 ± 方差与扰动敏感度；题量不足时至少报告 bootstrap 置信区间（参见本系列统计篇）。
7. **存量私有题库的治理**。怀疑泄漏的题先做保义改写轮换（2503.06643 路线）而不是整套废弃；改写后做小规模等难度校准（新旧题在锚点模型上的分数对齐）再上线。
8. **抗 Goodhart 制度设计**。(a) 保留一个永不对外宣传的内部 holdout 基准，只用于内部决策；(b) 不把任何单一 benchmark 设为团队 KPI，改用基准组合 + 人评 + 线上指标的多信号决策；(c) 定期核对 proxy 指标（benchmark 分）与 gold 指标（用户满意度/留存）的相关性，相关性衰减即触发评测集更换。
9. **选型决策流程建议**：公开排行榜（LiveBench/LiveCodeBench/Arena）做初筛 → 自建私有集（含 canary 与变体族）复测 → 小流量 A/B / 影子模式验证 → 决策。明确每一步排除的是哪类风险（饱和、污染、分布不匹配、Goodhart）。

---

## 参考清单

**核心论文（13 篇，均已核实）**

1. LiveBench: A Challenging, Contamination-Limited LLM Benchmark — https://arxiv.org/abs/2406.19314 （2024-06）
2. LiveCodeBench: Holistic and Contamination Free Evaluation of Large Language Models for Code — https://arxiv.org/abs/2403.07974 （2024-03）
3. DyVal: Dynamic Evaluation of Large Language Models for Reasoning Tasks — https://arxiv.org/abs/2309.17167 （2023-09，ICLR 2024）
4. DyVal 2: Dynamic Evaluation of Large Language Models by Meta Probing Agents — https://arxiv.org/abs/2402.14865 （2024-02）
5. Detecting Pretraining Data from Large Language Models — https://arxiv.org/abs/2310.16789 （2023-10，ICLR 2024）
6. Rethinking Benchmark and Contamination for Language Models with Rephrased Samples — https://arxiv.org/abs/2311.04850 （2023-11）
7. Are We Done with MMLU?（MMLU-Redux）— https://arxiv.org/abs/2406.04127 （2024-06）
8. MMLU-Pro: A More Robust and Challenging Multi-Task Language Understanding Benchmark — https://arxiv.org/abs/2406.01574 （2024-06）
9. GSM-Symbolic: Understanding the Limitations of Mathematical Reasoning in Large Language Models — https://arxiv.org/abs/2410.05229 （2024-10，ICLR 2025）
10. Is Your Benchmark Still Useful? Dynamic Benchmarking for Code Language Models — https://arxiv.org/abs/2503.06643 （2025-03）
11. Order Independence With Finetuning — https://arxiv.org/abs/2503.23483 （2025-03）
12. DynaMath: A Dynamic Visual Benchmark for Evaluating Mathematical Reasoning Robustness of Vision Language Models — https://arxiv.org/abs/2411.00836 （2024-10/11）
13. UGMathBench: A Diverse and Dynamic Benchmark for Undergraduate-Level Mathematical Reasoning — https://arxiv.org/abs/2501.13766 （2025-01）

**延伸与背景（已核实）**

14. Humanity's Last Exam — https://arxiv.org/abs/2501.14249 （2025-01）
15. Scaling Laws for Reward Model Overoptimization — https://arxiv.org/abs/2210.10760 （2022-10）
16. Extracting Training Data from Large Language Models — https://arxiv.org/abs/2012.07805 （2020-12）
17. Look at the Text: Instruction-Tuned Language Models are More Robust Multiple Choice Selectors than You Think — https://arxiv.org/abs/2404.08382 （2024-04）
18. Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference — https://arxiv.org/abs/2403.04132 （2024-03）
19. Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena — https://arxiv.org/abs/2306.05685 （2023-06，背景）
20. Beyond Goodhart's Law: A Dynamic Benchmark for Evaluating Compliance in Multi-Agent Systems — https://arxiv.org/abs/2606.07805 （2026-06）
21. Agent Island: A Saturation- and Contamination-Resistant Benchmark from Multiagent Games — https://arxiv.org/abs/2605.04312 （2026-05）

**无 arXiv 的工业界材料**：Sean Grove, *The Illusion of Model Improvement: Can LLM Benchmarks be Misleading?*（2024-10，OpenAI，代码/预印本）；AlpacaEval（GitHub）；各大实验室技术报告中的 contamination disclosure 章节。
