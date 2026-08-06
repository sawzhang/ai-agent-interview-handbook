# 轨迹级/过程级评估与信用分配（Trajectory-level / Process-level Evaluation & Credit Assignment）调研报告

> 调研时间：2026-08-05。调研范围：2024-01 至 2026-08 的 arXiv 论文为主，奠基性工作（PRM800K 等）作为背景。
> 核实说明：所有核心论文的 arXiv ID、标题、日期均通过 arXiv API（id_list）或 abs 页交叉核实；其中 Agent-as-a-Judge、τ-bench、Math-Shepherd、StepAgent 四篇通过 WebFetch 精核摘要与日期。

---

## 主题概述

**这个方向在解决什么问题？** 无论是数学推理还是多步 Agent 任务，只看"最终答案对不对"（outcome-based evaluation）有三个致命缺陷：

1. **诊断盲区**：一条 20 步的失败轨迹，错误可能发生在第 3 步，但最终结果评估无法定位它；
2. **奖励稀疏**：用 RL 训练 Agent 时，只有终局标量奖励，信用分配（credit assignment）困难，长 horizon 任务几乎学不动；
3. **捷径与欺骗**：最终状态"看起来对"不代表过程正确——Agent 可能绕过规则、伪造输出、reward hacking；反之，过程合理也可能因一次环境抖动而失败。过程级信号能区分这两类情况。

**2024–2026 的演进主线**可以概括为四段：

- **2023–2024 上半年：PRM 奠基与标注自动化。** OpenAI 的 Let's Verify Step by Step（PRM800K）证明"逐步验证"优于"只看结果"，但依赖 80 万条人工步骤标注。随后 Math-Shepherd（2023-12）用蒙特卡洛 rollout 自动估计每步"后续成功率"，OmegaPRM（2024-06，DeepMind）用二分搜索把自动标注成本降到 O(log n)，过程奖励模型（PRM）摆脱人工标注瓶颈。
- **2024 下半年：形式多样化。** Generative Verifiers 把验证器变成"生成式批评分数"（critique + verdict），VinePPO 把信用分配做进 RL 训练本身（中间状态重采样、无偏优势估计），Step-DPO 等工作把步骤级偏好引入对齐。
- **2024 末–2025：反思与落地到 Agent。** Qwen 团队的 PRM Lessons 系统披露 PRM 的局限（reward hacking、分布外失效）；PRIME 证明"无需步骤标签也能拿到过程奖励"（implicit reward）；rStar-Math 让 PRM 随 MCTS 自进化。同时过程评估从数学题扩展到 Agent：Agent-as-a-Judge（2024-10）提出用带工具的 Judge Agent 对开发型 Agent 做步骤级评估；AgentBoard（2024-01）用 progress rate 度量中间进展；τ-bench（2024-06）用"数据库终态比对 + pass^k"做 tool-call 的执行式验证。
- **2025–2026：元评估与信用分配体系化。** AgentRewardBench（2025-04）专门评估"自动轨迹评估器本身"，揭示 LLM 判别器的高误报率；SPA-RL、StepAgent 等把 stepwise 奖励/进展归因用于 Agent RL 训练；Terminal-Bench（2026-01）把执行式验证推到 CLI 长程任务；2026 年出现信用分配专题综述（From Reasoning to Agentic）把推理与 Agent 两条线的信用分配方法统一成体系。

一句话总结：**从"给步骤打分"（PRM）到"给 Agent 轨迹打分"（trajectory scoring）再到"给打分器打分"（meta-evaluation），同时把同一套信号反哺给训练（RL credit assignment）与推理时搜索（verifier-guided search）。**

---

## 重点论文

#### 1. Let's Verify Step by Step（PRM800K）

- **arXiv**: [2305.20050](https://arxiv.org/abs/2305.20050)（2023-05-31，背景/奠基）
- **机构/状态**: OpenAI；ICLR 2024
- **贡献**: 提出用过程监督（逐步标注正确/错误/无关步骤）训练过程奖励模型 PRM，并开源 80 万条步骤级人工标注数据集 PRM800K。核心发现：在 MATH 上，PRM 作为 best-of-N 选择器在 N 增大时全面优于结果奖励模型 ORM，且步骤级标签的信息密度远高于轨迹级标签（达到同等性能所需样本量约低 100 倍）。
- **关键数字**: GPT-4 直接解题 MATH 52.9%；PRM best-of-1250 达 78.2%（ORM 约 72%）。
- **评测工程意义**: 确立了"过程级监督 > 结果级监督"的实证基础与标注 schema（correct/incorrect/neutral 三标签），后续几乎所有 PRM 工作都以此为参照系；其标注成本问题也直接催生了后续自动标注研究线。

#### 2. Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations

- **arXiv**: [2312.08935](https://arxiv.org/abs/2312.08935)（2023-12-14，v3 2024-02）
- **机构/状态**: 北京大学、清华大学等；ACL 2024
- **贡献**: 提出全自动的过程奖励标注管线：对某一步之后的续写做多次蒙特卡洛 rollout，用"该步之后能走到正确答案的比例"作为该步的软标签，完全去掉人工标注。同一框架下验证器用于两个下游：(a) 推理时对候选解重排序（verification），(b) 作为逐步奖励做 PPO 强化。
- **关键数字**（WebFetch 核实自摘要）: Mistral-7B 上 GSM8K 77.9%→84.1%（逐步 RL），加验证后 89.1%；MATH 28.6%→33.0%，加验证后 43.5%。
- **评测工程意义**: "蒙特卡洛完成率 = 步骤质量"这一标注范式成为自动 PRM 的事实标准（OmegaPRM、rStar-Math 均是变体）；也展示了过程分数同时服务"评测（重排序）"与"训练（RL）"两个用途。

#### 3. Improve Mathematical Reasoning in Language Models by Automated Process Supervision（OmegaPRM）

- **arXiv**: [2406.06592](https://arxiv.org/abs/2406.06592)（2024-06-05）
- **机构/状态**: Google DeepMind；arXiv 预印本
- **贡献**: 解决自动标注的成本问题。朴素蒙特卡洛标注一步需要 O(n) 次 rollout，OmegaPRM 用**二分搜索定位第一个错误步骤**：先整条轨迹估计成功率，若非全对则取中间步重采样，根据两半的成功率估计递归二分，把单条轨迹的标注成本从 O(n) 降到 O(log n)。配合 MCTS rollout 自动收集过程监督数据。
- **关键数字**: 无任何人工干预，MATH 上 rollout 正确率相对 SFT 基线提升约 24%；标注成本较朴素蒙特卡洛降低约两个数量级（~100×，论文口径）。
- **评测工程意义**: 给出了"过程标注预算分配"的工程范式——把评估算力集中到信息量大的分叉点上。对评测平台的启示：给轨迹打分不必逐步全量打分，先粗粒度二分定位可疑区间再细查。

#### 4. Generative Verifiers: Reward Modeling as Next-Token Prediction

- **arXiv**: [2408.15240](https://arxiv.org/abs/2408.15240)（2024-08-27）
- **机构/状态**: Google DeepMind（多伦多）等；ICLR 2025
- **贡献**: 指出现有判别式验证器（输出一个标量分数）无法利用生成式 LLM 的两大红利：指令微调带来的语义理解与推理时 scaling。提出 GenRM：把验证做成**生成任务**——先生成对每一步的自然语言批注（critique），再输出 verdict，打分即条件生成概率。GenRM-CoT 在无需大规模步骤标注数据的情况下超过判别式 PRM（包括 PRM800K 训练的模型），并能与 majority-vote、ensemble 等测试时策略叠加。
- **关键数字**: MATH/GSM8K/GPQA 上 best-of-N 选择准确率系统性高于判别式基线（各基准数个百分点量级）；标注数据需求显著低于 PRM800K。
- **评测工程意义**: "批注式验证"（verbalized/critique-out-loud）为评测提供了**可解释的打分依据**，也天然接上 LLM-as-a-Judge 工程栈；是当前做步骤级 rubric 评估（如 Agent-as-a-Judge 的 criteria 打分）最常用的打分形式。

#### 5. Free Process Rewards without Process Labels（PRIME）

- **arXiv**: [2412.01981](https://arxiv.org/abs/2412.01981)（2024-12-02）
- **机构/状态**: 清华大学 NLP、上海人工智能实验室等；ICML 2025
- **贡献**: 质疑"显式步骤标签"的必要性。PRIME 用隐式奖励（implicit reward）：在 token 级训练一个价值头（value head），从结果奖励出发通过 RL 目标反推出每个 token 的过程价值，从而把过程监督无缝集成进 PPO 训练，完全不需要步骤级标注，也不需要先训好再冻结一个 PRM。隐式奖励还避免了显式 PRM 与策略分布不匹配的问题。
- **关键数字**: 在多个数学基准上稳定优于仅用结果奖励的 RL 基线；验证器与策略共同在线演化，缓解分布漂移。
- **评测工程意义**: 说明"过程信号"未必需要"过程标注"，可以从结果反馈中蒸馏出来；对评测的启示是：当你只有终局真值（如单元测试通过与否）时，仍可通过价值估计获得步骤级归因。

#### 6. The Lessons of Developing Process Reward Models in Mathematical Reasoning

- **arXiv**: [2501.07301](https://arxiv.org/abs/2501.07301)（2025-01-13）
- **机构/状态**: 阿里 Qwen 团队；arXiv 技术报告
- **贡献**: 一份难得的"PRM 失败学"系统报告，四个核心结论：(1) 步骤级标签确实比轨迹级标签更高效；(2) **PRM 的分数可以被利用/被 hack**——在 best-of-N 选择中，模型会生成恰好骗过 PRM 的解（PRM800K 尤其明显）；(3) PRM 在**难度外推与分布漂移**下性能显著退化（训练分布偏简单，测试分布变难时打分不可靠）；(4) PRM 与 ORM 组合使用效果更好。
- **关键数字**: 论文以 Qwen2.5 系列系统实验，展示 PRM 在 OOD 测试集上相对 in-distribution 的显著掉点，以及 best-of-N 下被 hacking 的具体比例（详见原文图表）。
- **评测工程意义**: 对"把 PRM 当评测器"的当头棒喝：任何验证器都要做**对抗性审计**（hacking 红队）与**难度分层校准**；评测报告中应区分 in-dist 与 OOD 的验证器可信度。

#### 7. rStar-Math: Small LLMs Can Master Math Reasoning with Self-Evolved Deep Thinking

- **arXiv**: [2501.04519](https://arxiv.org/abs/2501.04519)（2025-01-08）
- **机构/状态**: Microsoft Research 等；ICML 2025
- **贡献**: 小模型（7B）数学推理的系统方案，其中 PRM 部分解决"标注分布漂移"问题：用 MCTS 迭代生成搜索轨迹，从搜索树中提取步骤级标签训练 PRM，PRM 又反过来指导下一轮 MCTS——**PRM 与策略共同自进化**，使验证器始终贴近策略当前的分布。
- **关键数字**: Qwen2.5-Math-7B 在 AIME24 上达 58.8%，超过 o1-preview（40.0%）；MATH-500 96.4%。
- **评测工程意义**: 验证器必须"跟着被测系统一起进化"。评测工程上对应：当被测 Agent 升级后，旧验证器的分数不可直接比较，需要重新校准或共同迭代。

#### 8. VinePPO: Refining Credit Assignment in RL Training of LLMs

- **arXiv**: [2410.01679](https://arxiv.org/abs/2410.01679)（2024-10-02）
- **机构/状态**: Mila、Google DeepMind 等；ICLR 2025
- **贡献**: 直接针对 LLM RL 中的信用分配问题。指出 GRPO/PPO 依赖"同一 prompt 的 rollout 组内比较 + 价值函数 bootstrapping"，在长序列上优势估计有偏。VinePPO 在轨迹中间状态**重新采样 K 条续写**，用续写的实际回报构造无偏的 token 级优势估计（不依赖 critic bootstrap），从而把奖励精确归因到真正影响结果的步骤。
- **关键数字**: 在 GSM8K、MATH 等数学基准上相对 GRPO/PPO 稳定提升（论文报告最高约 +4 个百分点），且在 rollout 数较少时优势更明显。
- **评测工程意义**: "从中间状态重采样看最终成功率"本身就是一个通用的**步骤重要性评估方法**——不训练任何模型也能回答"这一步到底值多少分"，可用于离线轨迹归因分析。

#### 9. AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents

- **arXiv**: [2401.13178](https://arxiv.org/abs/2401.13178)（2024-01-24）
- **机构/状态**: 港大、上交大、上海 AI Lab 等；NeurIPS 2024（Datasets & Benchmarks）
- **贡献**: 首个面向多轮 Agent 的细粒度分析型评测板。9 个任务环境、统一观测接口，核心创新是 **progress rate（进展率）**：为每个任务定义子目标集合，用归一化加权距离衡量轨迹"走了多远"，把 0/1 的成功率拆成连续的进展曲线，从而回答"模型卡在哪一步"。
- **关键数字**: 即便最强模型总体成功率也仅约 40% 出头；progress rate 与 success rate 的结合揭示了不同模型在规划、探索、利用子能力上的分化。
- **评测工程意义**: 子目标分解 + progress rate 是长程 Agent 评测的标准做法之一：它让"失败"变得可诊断，也为 RL 提供了稠密的中间奖励信号来源。

#### 10. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains

- **arXiv**: [2406.12045](https://arxiv.org/abs/2406.12045)（2024-06-17）
- **机构/状态**: Sierra AI、普林斯顿；ICLR 2025
- **贡献**: tool-call 正确性评估的代表作。设定"用户模拟器对话 + 领域 API 工具 + 领域规则"的零售/航空场景；**评估不靠看对话文本，而是比对对话结束时数据库状态与目标状态是否一致**——纯执行式（execution-based）验证。提出 **pass^k**：衡量 k 次独立试验全部成功的可靠性（对随机性敏感的 Agent 比 pass@1 严苛得多）。
- **关键数字**（WebFetch 核实自摘要）: GPT-4o 级模型成功率 <50%；零售域 pass^8 <25%。
- **评测工程意义**: 定义了 Agent 评测的黄金标准组合：**状态比对（而非文本判断）+ 多次重复（可靠性）+ 规则合规性检查**。"终态数据库 diff"成为后续 tool-using Agent 评测的默认验证方式。

#### 11. Agent-as-a-Judge: Evaluate Agents with Agents

- **arXiv**: [2410.10934](https://arxiv.org/abs/2410.10934)（2024-10-14）
- **机构/状态**: DeepWisdom（MetaGPT 团队）等；ICML 2025
- **贡献**: 提出用"会执行工具的 Agent"来评估 Agent：Judge Agent 拿到被测 Agent 的完整代码库/产物后，可以运行代码、做静态分析、逐步对照分层需求（hierarchical requirements）打分，并给出过程性反馈。配套 **DevAI** 基准：55 个真实自动化 AI 开发任务、365 条分层用户需求。
- **关键数字**（论文摘要口径）: 与人工评估同等可靠；相比三位人类专家评估节省 97.72% 的时间、97.64% 的成本（场景特定报告值，不宜外推）；显著优于 LLM-as-a-Judge（纯文本判读）的评估质量。DevAI = 55 个任务 + 365 条分层用户需求。
- **评测工程意义**: 把"评估"本身变成 Agent 任务——rubric 驱动 + 工具增强 + 步骤级打分，是当前对"开放式产物（代码库、报告）"做过程级评估的主流范式；其成本数字是"自动评估替代人工评估"最常被引用的论据。

#### 12. AgentRewardBench: Evaluating Automatic Evaluations of Web Agent Trajectories

- **arXiv**: [2504.08942](https://arxiv.org/abs/2504.08942)（2025-04-11）
- **机构/状态**: Mila 等（Xing Han Lù、Kazemnejad、Peter Shaw 等）；arXiv 预印本
- **贡献**: 本方向最重要的"元评估"工作：收集 197 条 Web Agent 轨迹（含成功与人工确认的失败案例），系统测试各类自动评估器（LLM 判别器、critic 模型、代码检查器）识别"轨迹真正成功"的能力。核心发现：**多数评估器的 false positive 率极高**——把明显失败的轨迹判为成功；纯 LLM 判别尤其不可靠；结合代码/执行检查与分步核对的方案明显更好。
- **关键数字**: 多个常用评估器在失败轨迹上的误报率超过 50%（详见原文）；论文还给出统一评估 harness 供后续评估器对比。
- **评测工程意义**: "评估器本身必须被评估"。落地建议：任何 LLM-judge 上线前，先在已知成败的轨迹集上测其 FPR/FNR；优先选择有执行式依据的评估器；把评估器准确率作为评测基础设施的一级指标。

#### 13. From Novice to Expert: LLM Agent Policy Optimization via Step-wise Reinforcement Learning（StepAgent）

- **arXiv**: [2411.03817](https://arxiv.org/abs/2411.03817)（2024-11-06，v3 2024-12）
- **机构/状态**: 中国人民大学、17.AI 等；arXiv 预印本
- **贡献**: 针对 Agent 任务终局奖励稀疏的问题，提出自动构造**中间步骤奖励**：通过比较专家动作与 Agent 动作的分布差异自动生成步骤级奖励（借鉴逆强化学习的隐式奖励思想），并用 LLM 识别轨迹中的关键步骤给予额外奖励；理论上证明多轮迭代后 Agent 动作分布可逼近专家分布。
- **关键数字**: 相对 SFT 平均成功率 +3.93%，相对 RL 基线 +9.03%（ALFWorld、WebShop 等真实场景）。
- **评测工程意义**: "关键步骤识别"（LLM 找出轨迹里真正重要的几步）是一种低成本的轨迹评估代理指标，适合没有完整子目标定义的场景。

#### 14. SPA-RL: Reinforcing LLM Agents via Stepwise Progress Attribution

- **arXiv**: [2505.20732](https://arxiv.org/abs/2505.20732)（2025-05-27）
- **机构/状态**: 香港理工大学等；arXiv 预印本
- **贡献**: 把 Agent RL 的信用分配问题形式化为**逐步进展归因（stepwise progress attribution）**：用 LLM 对每一步估计其对任务目标的进展增量（progress score），把稀疏终局奖励分解为稠密步骤奖励，再经组内归一化后用于 RL。相比 VinePPO 的重采样方案，SPA-RL 不需要额外环境交互，成本更低。
- **评测工程意义**: 代表"用 LLM 做步骤归因"这条低成本路线（对照 VinePPO 的"用环境重采样"高保真路线），两条路线的取舍——成本 vs 无偏性——正是轨迹评估工程的核心权衡。

#### 15. Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces

- **arXiv**: [2601.11868](https://arxiv.org/abs/2601.11868)（2026-01-17）
- **机构/状态**: 多机构合作（Google DeepMind、Hugging Face 等）；arXiv 预印本
- **贡献**: 80 个高难度、真实感 CLI 长程任务（构建系统、科学计算、安全分析等），每个任务配 **pytest 风格的功能测试 + oracle 参考解**——典型的执行式验证：不看过程文本，跑测试定成败。其任务难度显著高于此前的终端类基准，主流模型 + agent 组合大面积失败。
- **关键数字**: 最强模型 + agent 组合成功率约 35%（多数任务失败）；后续还有 Long-Horizon-Terminal-Bench（2026-07）引入 dense reward-based grading 做更细粒度打分。
- **评测工程意义**: 执行式验证在"无标准答案、开放路径"任务上的规模化实践：oracle 解 + 测试套件 + 沙箱执行 = 可自动化、可复现、抗文本欺骗的评估闭环。

---

## 关键概念与方法论

### 1. PRM 与 ORM 的形式化定义

- **ORM**（outcome reward model）：对完整解给一个分数 r_ORM(y)。
- **PRM**（process reward model）：对每个步骤给分数 r_PRM(s_1..i)，整解分数通常取
  `score(y) = Σ_i log r_i`（对数似然加和）或 `∏_i r_i`。
- **用途**：best-of-N 重排序（选 argmax score）、束搜索/树搜索的节点估值、RL 的稠密奖励、评测的分数报告。
- **标注三范式**：人工步骤标注（PRM800K）→ 蒙特卡洛完成率标注（Math-Shepherd：第 i 步标签 = 从该步 rollout 到正确答案的频率 E[1{correct}]）→ 二分搜索加权标注（OmegaPRM：O(log n) rollout）。

### 2. 生成式验证（GenRM）

把验证写成条件生成：`p(verdict | problem, solution, critique)`。打分时先生成批注再输出判定，相比判别式标量分数：可解释、可迭代（self-correction）、可 ensemble、随推理算力 scaling。代价是推理成本高。

### 3. 无偏信用分配（VinePPO）

在中间状态 s_t 重采样 K 条续写，优势估计
`A(s_t, a_t) ≈ (1/K) Σ_k R(s_t, a_t, c_k) − V(s_t)`
不使用 critic bootstrap，故无偏。工程含义：**"从某步出发的成功率"本身就是该步质量的无偏评估**——可脱离 RL 单独用作轨迹归因工具。

### 4. pass^k（τ-bench）

`pass^k = E_task[ ∏_{i=1..k} (1 − 1{第 i 次试验成功}) ]`，即 k 次独立试验**全部失败**的概率（越低越好）。它惩罚"偶尔成功"的不可靠 Agent，与生产环境"每次请求都要对"的要求对齐；代价是对采样温度敏感，需要固定试验协议。

### 5. progress rate（AgentBoard）

为任务定义子目标集合 G，轨迹状态映射为已达成子目标的加权覆盖：
`progress = Σ_{g∈G} w_g · 1{g 达成} / Σ w_g`（配合归一化编辑距离处理顺序）。把二值成功率扩展为 [0,1] 进展分数，支持失败诊断与能力画像。

### 6. Agent-as-a-Judge 评估管线

rubric（分层需求/criteria 列表）→ Judge Agent 用工具（运行、静态分析、检索）逐条核验 → 步骤级打分 + 定性反馈 → 汇总。与 LLM-as-a-Judge 的本质区别：**评估者有环境交互能力**，能核验而非仅阅读。

### 7. 执行式验证（execution-based verification）

τ-bench 的终态数据库 diff、Terminal-Bench 的测试套件、SWE 类基准的单元测试，共同模式：`可执行的真值判定程序 + 沙箱`。优点：客观、可复现、抗"看起来对"的文本欺骗；代价：需要为每个任务写判定程序，覆盖面受限于能写成断言的部分。

### 8. 信用分配分类学（依据综述 2604.09459）

- **粒度**：token 级（PRIME）/ 步骤级（Math-Shepherd）/ 片段级（Step-DPO）/ 轨迹级（ORM）；
- **信号来源**：人工标注 / 模型标注（GenRM、Agent-as-a-Judge）/ 自动估计（MC rollout、VinePPO 重采样）/ 规则式（单元测试、状态 diff）；
- **用途**：训练时奖励（RL credit assignment）vs 推理时选择（best-of-N、树搜索）vs 纯评测（报告与诊断）。

---

## 争议与分歧

1. **PRM 是否值得做？** PRM800K 的结论（PRM 全面优于 ORM）在 2025 年被多次质疑：Qwen Lessons 报告 PRM 会被 best-of-N hacking、难度外推差、依赖大规模高质量标注；不少团队发现"ORM + 更多采样"性价比更高。当前共识趋于"PRM 有用但娇贵"，需要与 ORM 组合、定期重校准。
2. **显式步骤标签是否必要？** PRIME/VinePPO 路线认为不需要（隐式奖励/重采样即可）；GenRM/rStar-Math 路线认为显式（哪怕是生成的）批注带来可解释性与更好的 scaling。这直接影响评测数据建设：要不要花钱标步骤。
3. **LLM 判别器能否可信地评估轨迹？** AgentRewardBench 的实证结果相当悲观（失败轨迹误报率普遍 >50%），而 Agent-as-a-Judge 报告与人工相当的可信度——分歧的根源在于**评估器是否拥有执行/核验工具**以及是否有 rubric 约束。"纯阅读式"轨迹 LLM-judge 正在被工业界降级使用。
4. **过程正确 ≠ 结果正确，该信谁？** 存在双向背离：过程全对但终局失败（环境抖动、最后一步失误），以及终局成功但过程违规（τ-bench 中的规则违反案例）。工业界（如客服 Agent）倾向"终态正确 + 规则合规双门槛"，学界 PRM 研究则更关注前者。
5. **pass^k 是否过于严苛？** 有观点认为 pass^8 等指标放大随机性、低估可用模型；支持者认为它如实反映生产可靠性。折中做法是同时报告 pass@1 与 pass^k 并固定温度。
6. **验证器的分布漂移问题**：验证器在旧策略数据上训练，评估新策略时系统性失准（Qwen Lessons、rStar-Math 都以此立论）。评测平台必须回答"验证器多久重训一次"。

---

## 对工程实践的启示

1. **评估器分层**：规则/执行式验证（单元测试、状态 diff、schema 校验）为主，Agent/LLM judge 为辅，人工抽检校准。AgentRewardBench 的教训：上线任何自动评估器前，先在已知成败的轨迹集上测 FPR/FNR。
2. **结构化轨迹日志是一切的前提**：每步记录（状态/观测、动作、工具调用参数与返回、模型意图），否则无法做事后过程级分析与归因。
3. **失败诊断用子目标分解**：借鉴 AgentBoard，为核心任务定义子目标/检查点，报告 progress rate 而不只是成功率——这直接决定你能不能回答"模型卡在哪"。
4. **可靠性必须多次试验**：对工具调用类 Agent 报告 pass@1 + pass^k（k≥4），固定温度与用户模拟协议。
5. **建 PRM 的工程清单**：优先蒙特卡洛/二分自动标注（成本可控）；验证器训练分布要覆盖目标难度；上线前做 reward hacking 红队（生成专门骗验证器的样本）；OOD 分层报告验证器准确率；验证器与策略共同迭代（rStar-Math 模式）。
6. **没有步骤标签也能有过程信号**：结果真值 + 价值头（PRIME）或中间状态重采样（VinePPO）可得到 token/步骤级归因，适合只有单元测试真值的代码 Agent 场景。
7. **推理时利用过程分数**：best-of-N 重排序是最便宜的收益；预算充足时用验证器引导树搜索（MCTS + PRM）。注意 N 增大时验证器过拟合风险。
8. **Agent RL 的信用分配**：长 horizon 任务不要只用终局奖励；低成本路线用 LLM 进展归因（SPA-RL/StepAgent），高保真路线用重采样优势估计（VinePPO），并把 progress rate 直接作为稠密奖励来源。
9. **开放式产物评估**：对代码库/报告类产物采用 Agent-as-a-Judge 范式——分层 rubric + 可执行核验 + 步骤级反馈，并保留 97% 成本优势背后的前提（rubric 质量、Judge 的工具权限）。
10. **把评估器当资产管理**：版本化、定期元评估（对标 AgentRewardBench 式基准）、记录验证器与被测模型的配对兼容性（策略升级后旧验证器分数不可比）。

---

## 参考清单

### 核心论文（15 篇，全部核实 ID/标题/日期）

1. Let's Verify Step by Step — [arxiv.org/abs/2305.20050](https://arxiv.org/abs/2305.20050)（2023-05）
2. Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations — [arxiv.org/abs/2312.08935](https://arxiv.org/abs/2312.08935)（2023-12）
3. Improve Mathematical Reasoning in Language Models by Automated Process Supervision（OmegaPRM）— [arxiv.org/abs/2406.06592](https://arxiv.org/abs/2406.06592)（2024-06）
4. Generative Verifiers: Reward Modeling as Next-Token Prediction — [arxiv.org/abs/2408.15240](https://arxiv.org/abs/2408.15240)（2024-08）
5. VinePPO: Refining Credit Assignment in RL Training of LLMs — [arxiv.org/abs/2410.01679](https://arxiv.org/abs/2410.01679)（2024-10）
6. Free Process Rewards without Process Labels（PRIME）— [arxiv.org/abs/2412.01981](https://arxiv.org/abs/2412.01981)（2024-12）
7. The Lessons of Developing Process Reward Models in Mathematical Reasoning — [arxiv.org/abs/2501.07301](https://arxiv.org/abs/2501.07301)（2025-01）
8. rStar-Math: Small LLMs Can Master Math Reasoning with Self-Evolved Deep Thinking — [arxiv.org/abs/2501.04519](https://arxiv.org/abs/2501.04519)（2025-01）
9. AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents — [arxiv.org/abs/2401.13178](https://arxiv.org/abs/2401.13178)（2024-01）
10. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains — [arxiv.org/abs/2406.12045](https://arxiv.org/abs/2406.12045)（2024-06）
11. Agent-as-a-Judge: Evaluate Agents with Agents — [arxiv.org/abs/2410.10934](https://arxiv.org/abs/2410.10934)（2024-10）
12. From Novice to Expert: LLM Agent Policy Optimization via Step-wise Reinforcement Learning（StepAgent）— [arxiv.org/abs/2411.03817](https://arxiv.org/abs/2411.03817)（2024-11）
13. AgentRewardBench: Evaluating Automatic Evaluations of Web Agent Trajectories — [arxiv.org/abs/2504.08942](https://arxiv.org/abs/2504.08942)（2025-04）
14. SPA-RL: Reinforcing LLM Agents via Stepwise Progress Attribution — [arxiv.org/abs/2505.20732](https://arxiv.org/abs/2505.20732)（2025-05）
15. Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces — [arxiv.org/abs/2601.11868](https://arxiv.org/abs/2601.11868)（2026-01）

### 延伸阅读（ID 均经 arXiv API/搜索交叉确认，2508.02994 仅经搜索确认）

- ProcessBench: Identifying Process Errors in Mathematical Reasoning — [2412.06559](https://arxiv.org/abs/2412.06559)（2024-12，步骤级错误定位基准）
- Step-DPO: Step-wise Preference Optimization for Long-chain Reasoning of LLMs — [2406.18629](https://arxiv.org/abs/2406.18629)（2024-06，片段级偏好对齐）
- OVM, Outcome-supervised Value Models for Planning in Mathematical Reasoning — [2311.09724](https://arxiv.org/abs/2311.09724)（2023-11，结果监督的价值模型变体）
- AgentRM: Enhancing Agent Generalization with Reward Modeling — [2502.18407](https://arxiv.org/abs/2502.18407)（2025-02，轨迹奖励模型 + 搜索）
- Agent Q: Advanced Reasoning and Learning for Autonomous AI Agents — [2408.07199](https://arxiv.org/abs/2408.07199)（2024-08，MCTS + 自我批评的 Agent 学习）
- Tree Search for Language Model Agents — [2407.01476](https://arxiv.org/abs/2407.01476)（2024-07，Agent 的验证器引导搜索）
- Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters — [2408.03314](https://arxiv.org/abs/2408.03314)（2024-08，验证器引导的测试时算力分配）
- Reasoning with Language Model is Planning with World Model（RAP）— [2305.14992](https://arxiv.org/abs/2305.14992)（2023-05，背景：过程评估用于规划）
- Identifying the Risks of LM Agents with an LM-Emulated Sandbox（ToolEmu）— [2309.15817](https://arxiv.org/abs/2309.15817)（2023-09，背景：沙箱模拟执行评估 Agent 风险）
- Search-R1: Training LLMs to Reason and Leverage Search Engines with RL — [2503.09516](https://arxiv.org/abs/2503.09516)（2025-03，多轮 RL 的代表）
- RAGEN: Understanding Self-Evolution in LLM Agents via Multi-Turn RL — [2504.20073](https://arxiv.org/abs/2504.20073)（2025-04，多轮 RL 信用分配困境的动机文献）
- From Reasoning to Agentic: Credit Assignment in RL for Large Language Models（综述）— [2604.09459](https://arxiv.org/abs/2604.09459)（2026-04）
- A Survey of Process Reward Models: From Outcome Signals to Process Supervisions — [2510.08049](https://arxiv.org/abs/2510.08049)（2025-10）
- AJ-Bench: Benchmarking Agent-as-a-Judge for Environment-Aware Evaluation — [2604.18240](https://arxiv.org/abs/2604.18240)（2026-04）
- Offline Preference-Based Trajectory Evaluation — [2606.17541](https://arxiv.org/abs/2606.17541)（2026-06）
- The Rise of Agent-as-a-Judge Evaluation for LLMs（综述）— [2508.02994](https://arxiv.org/abs/2508.02994)（2025-08，仅经搜索交叉确认）
