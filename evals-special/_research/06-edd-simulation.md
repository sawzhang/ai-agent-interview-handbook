# 评测驱动开发（EDD）与仿真评测调研报告（2024–2026）

> 调研日期：2026-08-05。范围：2024-01 至 2026-08 的 arxiv 论文与工业界工程博客；奠基性工作（MT-Bench、DSPy、Generative Agents、Chatbot Arena）作为背景简述。全部 26 个 arxiv ID 均于 2026-08-05 通过 `export.arxiv.org/api/query?id_list=...` 或 abs 页面逐一核实（标题+日期+第一作者），2 篇 EMNLP 工业赛道论文经 ACL Anthology 页面核实；关键数字尽量对照论文摘要/官方 README 复核，修正了早期转述中的三处误差（见文末核实说明）。工业界博客：Anthropic 与 OpenAI 文档原文核实；DoorDash 原文站点反爬，要点经 ByteByteGo/InfoQ 转述交叉核实并已标注。

---

## 主题概述

**这个方向在解决什么问题。** LLM 应用与 agent 系统的行为是概率性、涌现式、随交互与数据漂移的，传统软件"写完单元测试再上线"的 QA 范式失效：bug 不总是复现，正确性常常没有唯一标准答案，模型/prompt/工具链任一组件变更都可能引起回归。评测驱动开发（Evaluation-Driven Development, EDD）主张把 evaluation 从"上线前的一次性检查点"变成贯穿全生命周期的"持续治理机制"：先定义期望行为（eval 即规约），在开发、发布、运行各阶段持续产生评测证据，并用证据驱动最小化修复与受控迭代。仿真评测（simulation-based eval）则是其核心使能技术：用 LLM 用户模拟器（persona 驱动）+ mock 后端 + LLM 裁判，端到端地自动生成/重放对话场景，使"无真实用户参与的 E2E 测试"变得可行且便宜，进而把 eval 塞进 CI 成为发布门禁。

**2024–2026 的演进主线：**

1. **方法论成型（2024 末–2025）**：EDD 从口号变成有过程模型与参考架构的工程学科。arxiv 2411.13768 于 2024-11 首发，2025-11 v3 扩展为 EDDOps，把 offline/online 评测与运行时控制环纳入同一框架。Anthropic（2026-01《Demystifying evals for AI agents》）、OpenAI（evaluation best practices 官方文档，提出 continuous evaluation）把"eval-driven development"写入官方开发指南。
2. **仿真评测标准化（2024 中–2026）**：τ-bench（2024-06）首创"LLM 用户模拟器 + 工具调用 + 数据库终态校验 + pass^k"范式；τ²-bench（2025-06）升级为"双控"（用户侧也能调工具，Dec-POMDP 建模）；DAUS、隐式画像 USP、ChatChecker、EMNLP'25 Gromada 等把 persona 驱动、非合作模拟、模拟器可靠性本身作为研究对象；ATOD（2026-01）把合成对话生成管线与多维评测框架产品化。
3. **eval 成为优化目标函数（2024–2026）**：DSPy → MIPROv2 → GEPA，prompt/程序优化器直接以 eval 分数为搜索目标，形成"eval 定义 → 自动优化 → eval 门禁"的闭环；Nubank（2026-06）甚至用 GEPA 来优化 LLM 裁判本身的一致性，eval 基础设施自身进入被优化循环。
4. **持续评测与数据飞轮（2025–2026）**：生产 trace 回流为测试用例（DoorDash、Discord AITL），eval 进 CI 成为发布门禁（2601.18827、2603.15676、2604.27789 等 SE 方向论文），OpenAI 文档把"每次变更都跑 continuous evaluation"列为标准实践，"评测资产"像代码资产一样版本化管理。
5. **offline-online 一致性出现量化证据（2026）**：Nubank 报告离线仿真指标与线上 A/B 结果强相关、eval 质量直接决定迭代速度，是"EDD 能可靠预测生产收益"的首个大规模量化证据；与之相对，OlaBench/OlaMind（2510.22143）等工作强调离线分数与可部署行为之间的 gap 仍然普遍。两派证据并存（见争议节）。
6. **学界/工业界错位被量化**：EDDOps 论文对 134 篇学术文献的统计显示约 93% 聚焦 pre-deployment、仅约 2% 覆盖 post-deployment，而工业界灰色文献中约 40% 已转向持续评测——学术供给与工程需求明显错配。

---

## 重点论文

以下 15 篇为核心论文（13 篇 arxiv + 2 篇 EMNLP 工业赛道，全部核实）。

#### 1. Evaluation-Driven Development and Operations of LLM Agents（EDD/EDDOps）

- **arxiv**: [2411.13768](https://arxiv.org/abs/2411.13768)（v1 2024-11-21；v3 2025-11-17 更名为现标题并加入 Operations）
- **机构**: University of Adelaide / CSIRO Data61 / ANU 方向的多机构合作；作者 Boming Xia, Qinghua Lu, Liming Zhu, Zhenchang Xing, Dehai Zhao, Hao Zhang
- **发表状态**: arxiv v3 标注 "Submission under review"；分类 cs.SE + cs.AI
- **贡献**: （1）通过多声源文献综述（MLR，综合学术与工业评测实践）提出 EDDOps 过程模型与三层参考架构，把评测定位为"持续治理功能"而非"终态检查点"，用闭环反馈统一 offline（开发期）与 online（运行期）评测。（2）过程模型四阶段：Plan the evaluation → Build evaluation assets → Run offline & online evaluations → Analyze & improve。（3）参考架构三层：Supply Chain Layer（评测意图/数据/模型选型证据）→ Agent Layer（暴露可评测表面与结构化 trace）→ Operation Layer（Evaluation Backbone + Control Loop：以评测证据驱动有界运行时适配与受控再开发，持续更新 safety case）。（4）明确 shadow evaluation（影子评测，不暴露给用户）与 canary rollout 在框架中的位置。
- **关键数字**（论文 MLR 统计）: 学术文献约 93.28% 只做 pre-deployment 评测、仅约 2.24% 覆盖 post-deployment、约 4.48% 是持续评测；约 92.54% 只看端到端指标、97.76% 用静态基准；工业灰色文献中约 40.74% 已是持续评测、81.48% 已用评测驱动适配。验证案例为 LLM 报税助手。
- **对评测工程的意义**: EDD 方向目前最系统的学术表述，可直接作为团队评测体系的"蓝图"：评测计划版本化、测试目录带 provenance 与 slice 标签、"最小有效变更优先"（先改 prompt/路由/护栏，再动架构/模型）。

#### 2. Building Customer Support AI Agents at 100M-User Scale: An Evaluation-Driven Framework（Nubank）

- **arxiv**: [2606.08867](https://arxiv.org/abs/2606.08867)（2026-06-07）
- **机构**: Nubank（巴西数字银行，1 亿+用户）；作者 Aman Gupta, Kevin Rossell, Edesio Alcobaça, Jose Chrystian Lima Pacheco, Carolina Baptista de Lima, Shao Tang, Luiz Paulo Rabachini, Luis Moneda
- **发表状态**: arxiv 预印本（v2）
- **贡献**: 首个超大规模（亿级用户）生产环境的 EDD 完整框架报告。四大组件：（1）面向客服 agent 的结构化上下文工程；（2）系统化 human-in-the-loop prompt 迭代；（3）严格的 LLM judge 评测——测量裁判间一致率（inter-rater agreement），并**用 GEPA 优化裁判本身的一致性**；（4）ideation-to-production 的全链路验证。中心洞见："评测流水线的质量直接决定迭代速度"（evaluation-pipeline quality directly determines iteration velocity）。
- **关键数字**: 覆盖 5 个生产部署（卡片配送、债务管理、信用额度、卡片管理、产品解释）；卡片配送场景 A/B 测试中，AI transactional NPS 提升 **+37 个百分点**、自助服务率提升 **+29 个百分点**；**离线仿真指标与线上结果强相关**；多数场景 AI 满意度距专家人工客服仅差几个百分点。
- **对评测工程的意义**: 把"eval 驱动开发能可靠预测生产影响"从口号变成有 A/B 证据的主张；同时示范了 eval 基础设施自身的优化闭环（用 prompt 优化器校准裁判），是 EDD 与 prompt 优化两条线交汇的里程碑。

#### 3. τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains

- **arxiv**: [2406.12045](https://arxiv.org/abs/2406.12045)（2024-06-17）
- **机构**: Sierra AI（Shunyu Yao, Noah Shinn, Pedram Razavi, Karthik Narasimhan）
- **发表状态**: arxiv 预印本；配套开源框架 sierra-research/tau-bench
- **贡献**: 定义"工具-智能体-用户"三方交互评测范式：LLM 扮演用户模拟器与 agent 多轮对话，agent 需遵守领域政策（retail/airline）并调用 API 工具，最终以**数据库终态与标注目标状态比对**做可验证判定（而非只看对话文本）。提出 **pass^k** 指标刻画可靠性：同一任务多次独立试验全部通过的概率。这一"模拟器 + 可验证终态 + 重试验可靠性"设计成为后续几乎所有对话 agent 仿真评测的模板，也被 DoorDash 等工业实践直接借用。
- **关键数字**（官方 README / 论文）: GPT-4o pass^1：retail 60.4%、airline 42.0%；pass^4 跌至 38.3% / 20.0%。论文摘要强调：即使 SOTA function-calling agent（如 gpt-4o）任务成功率也不足 50%，且极不稳定（retail 域 pass^8 < 25%）。
- **对评测工程的意义**: pass^k 应成为生产 agent 的发布指标之一；终态可验证性优于纯文本裁判；用户模拟器让 E2E 对话测试可以无人值守批量跑。"能做对一次"与"稳定做对"之间的巨大落差是 agent 评测最重要的洞见之一。

#### 4. τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment

- **arxiv**: [2506.07982](https://arxiv.org/abs/2506.07982)（2025-06-09）
- **机构**: Sierra AI（Victor Barres, Honghua Dong, Soham Ray 等）
- **发表状态**: arxiv 预印本；配套开源框架 sierra-research/tau2-bench
- **贡献**: 把 τ-bench 升级为"双控"（dual-control）：模拟用户不再只是说话，也能自己执行工具动作（如点击邮件链接、改路由器设置），环境建模为 Dec-POMDP，agent 必须通过对话**引导用户完成动作**并处理联合行动中的信息不对称。新增 telecom 域，并提供组合式任务生成器（从原子组件程序化生成多样、可验证的任务，保证域覆盖与难度可控）。
- **关键数字**: 论文结果显示双控任务显著难于单控：即使最强模型，在 telecom 双控设定下的成功率也大幅低于 τ-bench 单控设定（引导用户操作比直接操作难得多；具体数值以原文为准）。
- **对评测工程的意义**: 客服/支持类 agent 的真实难点在"指挥用户"而非"自己执行"；仿真评测必须让用户侧也有行为能力，否则会系统性高估 agent。组合式任务生成器也是"评测数据可程序化扩增"的范例。

#### 5. Reliable LLM-based User Simulator for Task-Oriented Dialogue Systems（DAUS）

- **arxiv**: [2402.13374](https://arxiv.org/abs/2402.13374)（2024-02-20）
- **机构**: Amazon（Ivan Sekulić, Silvia Terragni, Victor Guimarães 等）
- **发表状态**: arxiv 预印本（后收入 ACL 2024 相关活动）
- **贡献**: 直面"通用 LLM 当用户模拟器不可靠"的问题：未经对齐的模拟器会偏离用户目标、幻觉出不存在的对话事实。DAUS 用领域数据微调 + 受控解码，显著提升目标一致性（goal compliance）并抑制幻觉行为，使模拟器产出的对话更接近真实分布，可作为任务型对话系统的可靠评测/训练对手。
- **对评测工程的意义**: 用户模拟器本身需要被"评测与校准"——模拟器质量直接决定下游 agent 评测效度；领域微调/对齐模拟器是工业级仿真评测流水线的常见投资。

#### 6. Know You First and Be You Better: Modeling Human-Like User Simulators via Implicit Profiles（USP）

- **arxiv**: [2502.18968](https://arxiv.org/abs/2502.18968)（2025-02-26，v4）
- **机构**: 学术团队（Kuang Wang, Xianfei Li, Shenghao Yang 等；机构未单独核实）
- **发表状态**: arxiv 预印本
- **贡献**: 指出两类现有模拟方式的缺陷：角色扮演法缺乏话语级真实性与用户级多样性（且依赖名人等预定义画像）；直接模拟只关注文本、忽略性格等隐式特征与对话级一致性。提出 USP 框架：从真实人机交互记录中用 LLM 推断"隐式用户画像"（implicit profile：性格、表达习惯、目标倾向等未明说特征），再据此驱动模拟器，使生成的用户行为在个性化、真实性、多轮一致性上优于直接 prompt 的模拟器。
- **对评测工程的意义**: persona 不必全靠手写模板，可从生产对话中"挖掘"——这与数据飞轮天然衔接：真实日志 → 隐式画像 → 模拟器 → 回归测试。

#### 7. ChatChecker: A Framework for Dialogue System Testing and Evaluation Through Non-cooperative User Simulation

- **arxiv**: [2507.16792](https://arxiv.org/abs/2507.16792)（2025-07-22）
- **机构**: Roman Mayr, Michel Schimpf, Thomas Bohné（机构未单独核实）
- **发表状态**: arxiv 预印本
- **贡献**: 动机：现代对话系统是"多 LLM + 外部工具 + 数据库"的复合体，只评底层 LLM 不够，必须整体测试。提出三件套自动对话测试框架：（1）LLM 模拟多样化用户交互，强调**非合作**模拟（用户会不耐烦、跑题、表达模糊、中途改主意）；（2）Breakdown Detector 定位对话崩坏点；（3）Dialogue Rater 对系统质量打分。相比逐轮分析，把"对话级整体质量保证"工程化为可复用框架，并降低搭建成本。
- **对评测工程的意义**: 合作型模拟器会系统性高估 agent；测试集应包含"难缠用户"切片；崩坏检测器可定位失败轮次，服务于回归定位与缺陷归因。

#### 8. Benchmarking and Learning Real-World Customer Service Dialogue（OlaBench / OlaMind）

- **arxiv**: [2510.22143](https://arxiv.org/abs/2510.22143)（2025-10-25，v3）
- **机构**: Tianhong Gao, Jundong Shen, Jiapeng Wang 等（机构未单独核实）
- **发表状态**: arxiv 预印本
- **贡献**: 指出工业智能客服（ICS）的基准与训练管线"过度强调可验证任务成功、低估主观服务质量与真实失败模式"，导致**离线增益与可部署行为之间存在 gap**。构建"基准→优化"闭环：OlaBench 覆盖 RAG、工作流、agentic 三类设定，评测服务能力、安全与延迟敏感性；结果显示 SOTA LLM 仍不达标；OlaMind 进一步从专家对话中蒸馏可复用的推理模式与服务策略用于训练。
- **对评测工程的意义**: 是"offline-online gap"在 agent 场景的实证之一；提示团队把离线分数当必要条件而非充分条件，评测维度必须纳入主观服务质量与失败模式，并尽早引入影子/灰度验证。

#### 9. Evaluation and Benchmarking of LLM Agents: A Survey

- **arxiv**: [2507.21504](https://arxiv.org/abs/2507.21504)（2025-07-29）
- **机构**: Salesforce Research（Mahmoud Mohammadi, Yipeng Li, Jane Lo 等）
- **发表状态**: arxiv 综述预印本
- **贡献**: 用二维分类学（评什么：能力维度 × 应用领域；怎么评：静态基准/动态交互/人工/自动裁判）系统梳理 LLM agent 评测全景，指出现有评测与真实部署之间的断层（静态快照 vs 动态多轮、组件级 vs 系统级），并讨论评测如何贯穿开发-部署生命周期。
- **对评测工程的意义**: 可作为团队搭建评测体系时的"能力地图"，检查自己覆盖了哪些维度（工具调用正确性、多轮一致性、安全、成本、延迟……），以及评测形态是否跟上了 agent 的动态性。

#### 10. GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning

- **arxiv**: [2507.19457](https://arxiv.org/abs/2507.19457)（2025-07-25，v2）
- **机构**: Stanford / UC Berkeley / MIT / Databricks 等（Lakshya A Agrawal, Shangyin Tan, Dilara Soylu 等）
- **发表状态**: arxiv 预印本；开源实现 gepa-ai/gepa
- **贡献**: GEPA（Genetic-Pareto）把 prompt 优化做成"反射式进化"：对候选程序采样轨迹（推理、工具调用与输出）→ 用自然语言反思诊断失败 → 提出并验证 prompt 变异 → 用 Pareto 前沿在多次尝试间合并互补教训（按任务切片保留候选，而非只看平均分）。核心论点：语言的反射性信息量远大于稀疏标量奖励的策略梯度。全程以 eval 为目标函数，不需要梯度。
- **关键数字**（摘要核实）: 六个任务上比 GRPO 强化学习**平均高 6%（最高 20%）**，且 rollouts 用量**最多减少 35 倍**；比最强 prompt 优化器 MIPROv2 **高 10%+**（如 AIME-2025 上 +12%）；还可作为推理时搜索策略用于代码优化。
- **对评测工程的意义**: eval 质量决定优化上限——GEPA 的 Pareto 选择隐含了"按切片看指标、防止平均分掩盖退化"的评测设计原则；Nubank 用它优化裁判一致性，说明 eval 基础设施本身也可以被 eval 驱动优化。

#### 11. Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs（MIPROv2）

- **arxiv**: [2406.11695](https://arxiv.org/abs/2406.11695)（2024-06-17，v2）
- **机构**: Stanford 等 DSPy 团队（Krista Opsahl-Ong, Michael J Ryan, Josh Purtell 等）
- **发表状态**: arxiv 预印本；算法以 MIPROv2 之名集成于 DSPy（dspy.ai）
- **贡献**: 面向多阶段（multi-stage）LM 程序的自动 prompt 优化：在无模块级标签、无梯度的条件下，把问题分解为对每个模块优化自由文本指令与 few-shot 示例。三项策略：（1）程序感知 + 数据感知的指令提案生成；（2）随机小批量评测函数学习目标的代理模型（贝叶斯优化）；（3）元优化——让提案器本身随时间改进。
- **关键数字**（摘要核实）: 使用 Llama-3-8B 时，在 7 个多样化多阶段程序中 **5 个优于基线优化器，准确率最高提升 13%**。
- **对评测工程的意义**: 展示了"eval 作为目标函数"的工程闭环：一份带标注的 eval 集既当测试又当优化目标；但也意味着 eval 集泄漏/过拟合风险需要治理（留出集、定期换血、污染检测）。

#### 12. Automated Structural Testing of LLM-based Agents: Methods, Framework, and Case Studies

- **arxiv**: [2601.18827](https://arxiv.org/abs/2601.18827)（2026-01-25）
- **机构**: Jens Kohl, Otto Kruse, Youssef Mostafa 等 12 位作者（多机构团队，具体机构未单独核实）
- **发表状态**: arxiv 预印本
- **贡献**: 把软件测试的"结构测试"思想搬到 LLM agent：基于 OpenTelemetry 执行轨迹 + 模拟的模型响应 + 断言，对 agent 的控制流（工具调用序列、分支、异常路径）做系统性自动化测试，覆盖语句/分支等结构覆盖准则，而不仅是端到端行为测试。
- **对评测工程的意义**: eval 体系需要"单元层"（grader/断言）、"集成层"（轨迹/结构）与"E2E 层"（模拟对话）三级金字塔；trace 埋点（OTel）是结构测试的前提；"evals-as-tests"运动在方法论上开始与经典软件测试理论（覆盖准则）对接。

#### 13. Automated Self-Testing as a Quality Gate: Evidence-Driven Release Management for LLM Applications

- **arxiv**: [2603.15676](https://arxiv.org/abs/2603.15676)（2026-03-13，v2）
- **机构**: Alexandre Cristovão Maiorano（单一作者；机构未单独核实）
- **发表状态**: arxiv 预印本
- **贡献**: 提出发布门禁式的"自动自测"：LLM 应用在发布前自动生成并执行覆盖运行与证据信号的测试，把评测结果作为 release management 的证据链（evidence-driven），案例为内部多 agent 营销系统。门禁不只看分数，还看证据的充分性。
- **对评测工程的意义**: "evals-as-tests"运动的学术化样本：eval 结果即发布证据；CI 门禁应从"阈值判断"升级为"证据充分性判断"，与 2601.18827 的结构测试、2604.27789 的供应链门禁互为补充。

#### 14. Evaluating Conversational Agents with Persona-driven User Simulations（EMNLP'25 Industry）

- **出处**: [ACL Anthology 2025.emnlp-industry.16](https://aclanthology.org/2025.emnlp-industry.16/)（EMNLP 2025 工业赛道；无 arxiv 版本）
- **作者**: Justyna Gromada, Alicja Kasicka, Ewa Komkowska, Lukasz Krajewski, Natalia Krawczyk, Morgan Veyret, Bartosz Przybył, Lina M. Rojas-Barahona, Michał K. Szczerbak
- **发表状态**: EMNLP 2025 Industry Track（已核实）
- **贡献**: 面向真实销售 bot 的案例研究：构建 persona 驱动的 LLM 用户模拟器做端到端评测，persona 携带人口学属性、购买意向、沟通风格，模拟器驱动完整销售对话，再对转化路径质量打分。展示了"persona 切片 × 业务指标（转化、升级率）"的评测组织方式。
- **对评测工程的意义**: 工业界 persona 仿真评测的代表作之一；证明模拟器可以绑定业务 KPI 而不只是对话质量；persona 的意向分层（低意向/犹豫/高意向）是天然的测试切片维度。

#### 15. Agent-in-the-Loop: A Data Flywheel for Continuous Improvement in LLM-based Customer Support（EMNLP'25 Industry）

- **出处**: [ACL Anthology 2025.emnlp-industry.135](https://aclanthology.org/2025.emnlp-industry.135/)（EMNLP 2025 工业赛道；无 arxiv 版本）
- **作者**: Cen Zhao, Tiantian Zhang, Hanchen Su, Yufeng Zhang, Shaowei Su 等（Discord 团队）
- **发表状态**: EMNLP 2025 Industry Track（已核实）
- **贡献**: AITL（Agent-in-the-Loop）数据飞轮：用人工客服的多类在线标注持续回流，驱动 LLM 客服系统的检索/生成持续再训练，把再训练周期从月级压缩到周级；并专门分析了 offline 与 online 评测设置之间的一致性（agreement）。
- **关键数字**（论文报告）: 美国试点 recall@75 +11.7%、precision@8 +14.8%、有用性 +8.4%、采用率 +4.5%。
- **对评测工程的意义**: 数据飞轮的标准样本：人工标注→评测集→再训练→上线→新标注的闭环，且明确量化了 offline-online 一致性；说明持续评测的组织基础是"在线标注流"而不只是离线标注项目。

---

### 延伸阅读（arxiv ID 均已核实；★ 为无 arxiv 版本的会议/博客文献）

| arxiv | 标题 | 时间 | 与本主题的关系 |
|---|---|---|---|
| [2410.10934](https://arxiv.org/abs/2410.10934) | Agent-as-a-Judge: Evaluate Agents with Agents | 2024-10 | 用能看中间步骤、能执行验证的评审 agent 替代静态裁判；与 EDD 的"裁判要能访问轨迹/终态"呼应 |
| [2601.11854](https://arxiv.org/abs/2601.11854) | ATOD: An Evaluation Framework and Benchmark for Agentic Task-Oriented Dialogue Systems | 2026-01 | 合成对话生成管线 + ATOD-Eval 多维细粒度评测框架（多目标协调/依赖/记忆/主动性），仿真评测的新基建 |
| [2602.07840](https://arxiv.org/abs/2602.07840) | SAGE: Scalable AI Governance & Evaluation | 2026-02 | Policy（自然语言政策）+ Precedent（判例）+ LLM Surrogate Judge 双向校准协同进化，把人类产品判断变成可扩展评测信号；裁判治理的生产级范式 |
| [2604.27789](https://arxiv.org/abs/2604.27789) | Test Before You Deploy: Governing Updates in the LLM Supply Chain | 2026-04 | 把模型/prompt 更新当供应链风险治理，评测门禁 + 风险分组；CI eval 门禁的治理视角 |
| [2310.03714](https://arxiv.org/abs/2310.03714) | DSPy: Compiling Declarative Language Model Calls into Self-Improving Pipelines | 2023-10 | 背景：eval-as-objective 闭环的奠基框架 |
| [2306.05685](https://arxiv.org/abs/2306.05685) | Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena | 2023-06 | 背景：LLM 裁判的奠基与偏差清单（80%+ 人类一致性） |
| [2403.04132](https://arxiv.org/abs/2403.04132) | Chatbot Arena: An Open Platform for Evaluating LLMs by Human Preference | 2024-03 | online 评测的黄金标准平台；offline-online 对齐的参照系 |
| [2405.01470](https://arxiv.org/abs/2405.01470) | WildChat: 1M ChatGPT Interaction Logs in the Wild | 2024-05 | 真实用户对话语料，构建评测集/模拟器的原料 |
| [2309.11998](https://arxiv.org/abs/2309.11998) | LMSYS-Chat-1M: A Large-Scale Real-World LLM Conversation Dataset | 2023-09 | 同上，真实日志驱动评测（背景） |
| [2304.03442](https://arxiv.org/abs/2304.03442) | Generative Agents: Interactive Simulacra of Human Behavior | 2023-04 | 背景：LLM 模拟人类行为的奠基 |
| [2406.20094](https://arxiv.org/abs/2406.20094) | Scaling Synthetic Data Creation with 1,000,000,000 Personas | 2024-06 | persona 规模化生成（Tencent），可用于评测数据合成 |
| [2505.17156](https://arxiv.org/abs/2505.17156) | PersonaBOT: Bringing Customer Personas to Life with LLMs and RAG | 2025-05 | RAG 增强 persona 模拟器（KTH），提升对话准确性/有用性 |
| [2510.08621](https://arxiv.org/abs/2510.08621) | From Simulation to Strategy: Automating Personalized Interaction Planning for Conversational Agents | 2025-10 | 模拟器→策略规划的闭环（销售场景） |

**工业界博客要点（Anthropic、OpenAI 原文已核实；DoorDash 原文站点反爬，经转述核实并标注）：**

- **Anthropic《Demystifying evals for AI agents》**（2026-01-09，已核实原文）：官方定义 eval 词汇表（task/trial/grader/transcript/outcome）；主张 eval-driven development——先定义期望行为再开发，把已有的手工检查沉淀为测试用例；**起步只需 20–50 个简单任务**；eval 分两类：capability 套件（初始通过率应偏低，指引改进方向）与 regression 套件（应接近满分，用于拦截退化）；打分优先确定性检查，辅以模型 rubric 与专家判断；允许部分得分、逐条审 transcript、随能力变化更新套件；agent 非确定性下用 pass^k——文中示例：p=0.75、k=3 时 pass^3 = 0.75³ ≈ **42%**；eval 应与线上指标、用户反馈结合。数字（均原文核实）：SWE-bench Verified 一年内从 40% 提升到 80%+；CORE-Bench 上 Opus 4.5 修复任务与评分器 bug 后从 42%→95%；Bolt 约 3 个月建成 eval 体系。
- **OpenAI Evaluation best practices**（developers.openai.com 官方文档，已核实原文）：明确建议"Adopt eval-driven development: Evaluate early and often"；设置 **continuous evaluation (CE)：每次变更都跑 eval**、监控应用以发现新的非确定性案例、持续扩充 eval 集；数据来源**六类**（合成、领域专属、采购、人工精选、生产、历史数据）；模型裁判建议：用最强模型打分、控制回答长度偏差、打分前先输出推理（chain-of-thought）；示例量化目标（原文核实）：摘要任务 ROUGE-L ≥ 0.40、G-Eval 连贯性 ≥ 80%；文档问答 context recall ≥ 0.85、context precision ≥ 0.7、好评率 70%+。注意：OpenAI 托管 Evals 平台已官方宣布弃用——"Evals 将于 2026-10-31 对存量用户转只读，2026-11-30 关闭"（原文核实），开源 openai/evals registry（2023）仍是参考实现。
- **DoorDash《A Simulation and Evaluation Flywheel to Develop LLM Chatbots at Scale》**（2026-01-26；原文站点反爬，要点经 [ByteByteGo 转述](https://blog.bytebytego.com/p/how-doordash-built-a-testing-system)与 [InfoQ 报道](https://www.infoq.com/news/2026/03/doordash-llm-chatbot-simulator/)交叉核实【原文未直接核实】）：客服 bot 的仿真评测飞轮——用户模拟器 persona 从真实工单抽取（含脾气、情境叙事、期望结果），会反驳、补充细节、逐步升级而非一上来就转人工；mock 后端模拟订单/退款/时间戳以复现欺诈等边角案例；LLM 裁判读全对话 + 工具调用 + 政策后给二元判定 + 理由（"generator-verifier gap"：判定比生成容易）；裁判用人工标注样本校准到与专家一致。一次触发跑完全流程，任何变更必须通过全部 50+ 个 eval 才能上线；5 分钟内跑 200+ 场模拟对话；11 轮迭代（第 3 轮曾回落）；模拟环境幻觉率下降约 90%；离线提升与线上真实流量表现一致。
- **DoorDash《Building Ask DoorDash (Part 3): Evaluation》**（2026-06-30【原文未直接核实】）：agent 评测 harness 把上线前人工验证从小时级压到分钟级。
- **其他实践向资源**（未逐一核实链接状态）：Hamel Husain《Your AI Product Needs Evals》（hamel.dev，evals-as-tests 运动的布道文本）、Braintrust《What is eval-driven development》、Google web.dev《Evaluation-driven development》、DeepEval EDD 指南、GitHub awesome-eval-driven-development 清单。

---

## 关键概念与方法论

### 1. EDD/EDDOps 过程模型（可复用框架，出自 2411.13768 v3）

四阶段闭环：

1. **Plan**：评测计划版本化——范围、指标、切片（slice）、频率、升级规则、自适应触发条件；输入是用户目标 + 治理约束 + agent 初版设计。
2. **Build**：评测资产 = 标准基准 + 领域知识 + 专家用例 + 合成数据；每个用例带 provenance、oracle（判定标准）、slice 标签、运行模式；输出版本化测试目录。
3. **Run（offline + online）**：offline = 批量基准、精选套件、轨迹回放、缺陷定位；online = 生产信号、限流暴露（shadow/canary）、内联校验器、定时或异常触发的探针（probe）；支持混合裁判与 slice 级报告。
4. **Analyze & Improve**：优先"最小有效变更"（prompt/路由/护栏/记忆），大改动走受控 offline 再开发（架构/工具契约/检索/模型）；所有变更版本化、回归重测、更新 safety case。

三层参考架构：**Supply Chain Layer**（评测意图/数据/模型选型证据）→ **Agent Layer**（结构化 trace：prompt、计划、工具调用、中间状态全部可检视）→ **Operation Layer**（Evaluation Backbone + Control Loop：证据库 = Evaluation Results / Test Cases / Safety Cases，配 AgentOps 可观测性做触发、策略、回滚）。

Nubank 变体（2606.08867）在工业上落地为：上下文工程 + HITL prompt 迭代 + 带一致率测量的 LLM judge（GEPA 优化裁判）+ ideation-to-production 验证四支柱，核心经验是"评测流水线质量 = 迭代速度上限"。

### 2. 可靠性指标：pass@k 与 pass^k

单次试验通过率为 p，k 次独立试验：

- **pass@k = 1 − (1 − p)^k**：k 次里至少成功一次的概率（衡量能力上限）。
- **pass^k = p^k**：k 次全部成功的概率（衡量可靠性/可发布性）。

Anthropic 文档示例（原文核实）：p = 0.75、k = 3 时，pass^3 = 0.75³ ≈ **42%**——一个"看起来 75% 不错"的 agent，三连全对只有四成把握。τ-bench 数据佐证：GPT-4o retail pass^1 = 60.4%，pass^4 已跌至 38.3%，pass^8 < 25%。工程推论：**客服/金融等不可逆操作场景应以 pass^k（低 k）作为发布门槛**；pass@k 随 k 增大趋近 100% 而 pass^k 趋近 0，二者必须分开报告。终态可验证（数据库状态哈希）保证每次试验的判定是确定的，pass^k 才有意义。

### 3. 用户模拟器设计模式（综合 τ-bench/τ²-bench/DAUS/USP/ChatChecker/DoorDash/Gromada）

- **persona 组成**：人口学属性 + 情境叙事 + 目标/期望结果 + 沟通风格/脾气（DoorDash 从真实工单抽取；Gromada 绑定销售意向分层）。
- **隐式画像挖掘**：从真实日志反推未明说的用户特征（USP，2502.18968），比手写 persona 更接近真实分布。
- **非合作模拟**：用户会模糊、跑题、不耐烦、改主意（ChatChecker）；合作型模拟会系统性高估 agent。
- **双控能力**：让用户侧也能执行工具动作，agent 必须"指挥"而非"代办"（τ²-bench），否则高估 agent 的引导能力。
- **mock 后端**：订单/账户/时间戳等环境状态用受控 mock 呈现，才能稳定复现欺诈、大额退款等边角场景，并使"终态校验"可行（τ-bench、DoorDash）。
- **模拟器自身要校准**：模拟器需目标一致、不幻觉（DAUS 用领域微调 + 受控解码），并定期用真实对话做保真度抽检。
- **裁判与生成器的分离（generator-verifier gap）**：裁判是独立 LLM，输入 = 全对话 + 工具调用记录 + 适用政策，输出 = 二元判定 + 理由；用人工标注集校准裁判与专家的一致率后再上量（DoorDash）；裁判一致性本身可被 GEPA 优化（Nubank）。

### 4. eval 分层与打分体系（综合 Anthropic/OpenAI/EDDOps/SAGE）

- **套件二分**：capability 套件初始通过率要低（有改进空间、指引方向）；regression 套件要接近满分（掉分即阻断）——Anthropic 原文。
- **打分三层**：确定性代码检查（正则/终态/单测）→ 模型裁判 rubric → 人工抽检。模型裁判实践（OpenAI 文档）：用最强模型打分、控制长度偏差、打分前先输出理由/CoT、与人评对齐后再上量。
- **裁判治理**：SAGE（2602.07840）的 Policy–Precedent–Surrogate Judge 双向校准环，把主观判断转化为可执行的多维 rubric，适合大规模生产裁判的长期维护。
- **防作弊**：grader 设计要防止 agent 钻空子（如只输出固定话术骗过 rubric）；允许部分得分；逐条检查 transcript。
- **slice 报告**：按任务类型/用户群/难度/不确定性分带报告，避免平均分掩盖退化（GEPA 的 Pareto 前沿选择同样基于此）。

### 5. offline → shadow → canary → A/B → monitoring 的发布阶梯

- **Shadow evaluation**：新版本与旧版本并行处理同一输入，但结果不暴露给用户，只对比差异（EDDOps 定义）。
- **Canary rollout**：小流量放量 + 在线指标/内联校验器 + 异常触发探针，达标后扩量。
- **A/B + 生产监控**：在线真实反馈是最终裁决；Nubank 报告离线仿真指标与线上 A/B 强相关，DoorDash 报告离线提升与线上一致——但这不是普遍保证（见争议部分）。

### 6. 数据飞轮与持续评测（DoorDash / Discord AITL / OpenAI CE / EDDOps 控制环）

通用循环：**生产失败/真实 trace → 编码为测试用例（进回归集）→ 自动流水线（生成场景/模拟对话/打分）→ 修 prompt 或架构 → 重跑达标 → 发布 → 新的生产信号回流**。变体：
- **Discord AITL**：人工客服在线标注持续回流，驱动再训练（月级→周级），并量化 offline-online agreement。
- **OpenAI CE**：把"每次变更自动跑 eval + 监控非确定性 + eval 集增长"作为平台级默认实践。
- **Nubank**：eval 流水线质量直接决定迭代速度；eval 同时服务于 prompt 迭代（HITL）与裁判校准（GEPA）。

### 7. eval 作为优化目标函数（DSPy → MIPROv2 → GEPA）

- **DSPy**（2310.03714，背景）：把 LLM 程序声明为模块组合，eval metric + 少量标注即可编译出（few-shot 示例 + 指令）最优配置。
- **MIPROv2**（2406.11695）：贝叶斯优化搜索"指令提案 × 示例组合"，数据感知提案 + 小批量代理评分 + 元优化；Llama-3-8B 上 5/7 程序优于基线、最高 +13%。
- **GEPA**（2507.19457）：反射式进化——采样轨迹 → 自然语言反思失败原因 → 变异 prompt → Pareto 前沿按切片保留候选；比 GRPO 平均 +6%（最高 +20%）、rollouts 最多省 35 倍、比 MIPROv2 +10%。
- 共同点：**eval 集既是测试又是目标**；因此必须治理 eval 集过拟合（留出集、定期换血、污染检测——EDDOps 把 contamination safeguards 列为评测资产的必备属性）。Nubank 进一步表明：裁判的 rubric/prompt 也是可优化目标，裁判一致率（inter-rater agreement）是被优化的度量。

---

## 争议与分歧

1. **离线评测到底能不能代表线上表现？** 一派证据说可以（有条件）：Nubank（2606.08867）报告离线仿真指标与线上 A/B 强相关并给出 +37pp NPS 的量化证据；DoorDash 报告离线提升与线上一致；τ-bench 用可验证终态提高离线信号可信度。另一派证据说不能：2510.22143（OlaBench）明确指出现有基准"过度强调可验证任务成功、低估主观质量与真实失败模式"，离线增益与可部署行为间存在 gap；EDDOps 综述发现学术评测约 93% 停留在 pre-deployment。当前共识倾向："离线是必要不充分"，需要 shadow/canary/A-B 补最后一公里，且离线指标必须覆盖主观质量与失败模式才有预测力。
2. **LLM-as-a-Judge 的可靠性边界**：裁判存在位置偏差、冗长偏差、自我偏好（见 01-llm-judge 报告）；Anthropic 强调"裁判漏洞"（agent 钻 grader 空子）；裁判还会随模型更新漂移。工业界一致做法是"裁判必须与人评对齐后才可上量"（DoorDash 校准到专家一致、Nubank 测量 inter-rater agreement、OpenAI 要求与人评对齐），但对齐成本与裁判漂移的长期维护仍是痛点；SAGE 的政策-判例协同进化是目前较系统的治理答案。
3. **用户模拟器是不是"假用户"？** 模拟器与被测 agent 常用同族模型（同源偏差），可能互相"太好懂"；合作型模拟高估、非合作型（ChatChecker）又可能过于刁钻。学界尚无公认的"模拟器保真度"标准指标；DAUS/USP 路线试图用真实日志微调或挖掘隐式画像来校准，但校准集本身也可能过时。τ²-bench 的双控设定提示：模拟器能力不足（不能行动）会改变评测效度方向。
4. **CI eval 门禁的成本与 flakiness**：agent eval 非确定、耗时长、费用高；每变更跑全量（DoorDash 模式：任何变更须过全部 50+ eval）对大公司可行，对小团队昂贵。2604.27789 等论文专门讨论门禁的计算开销与治理复杂度。折衷方案：回归集精简+每日全量、能力集抽样+按需触发、分层门禁（单元 grader 必过、E2E 抽测）。
5. **平台化还是自建？** OpenAI 托管 Evals 平台（2025 年随 AgentKit 推出）已官方宣布 2026-11-30 关闭（原文核实），说明"评测即平台"的商业模式未定型；Braintrust/LangSmith/Langfuse/Arize/DeepEval 等第三方与自建 harness（DoorDash、Bolt、Nubank）并存。评测资产的可移植性（数据集 + grader 与平台解耦）正成为工程选型关注点。
6. **pass@k vs pass^k 的发布哲学**：能力导向（demo 友好）还是可靠性导向（生产可用）？τ-bench 与 Anthropic 主张可靠性指标进发布门槛，但多数公开 leaderboard 仍只报 pass@1/平均分，学界对"可靠性排行榜"尚无标准。
7. **eval 集污染与过拟合**：eval 一旦成为优化目标（MIPROv2/GEPA）或公开 leaderboard，就会被拟合与污染；EDDOps 要求评测资产带污染防护与 provenance，但具体做法（换血频率、污染检测器）仍不成熟。
8. **eval 优化器会不会"奖励作弊"**：GEPA/RL 以 eval 分数为目标，agent 可能学会钻裁判空子而非真正改进（Anthropic 的 grader-hacking 警告）。Pareto 多切片选择、终态可验证判定、人工抽检是对冲手段，但"优化目标与真实意图的错位"是 EDD 闭环的固有风险。

---

## 对工程实践的启示

1. **起步最小可行**：不要等 1000 条标注集。拿 20–50 个真实失败/边角案例（来自人工验证、线上 bug、用户投诉）就能开始 eval-driven 迭代（Anthropic 官方建议）；把每次手工检查的动作沉淀为可复跑的 test case。
2. **先写期望，再写 agent**：像 TDD 一样，把"该做什么/不该做什么"写成带参考答案的用例（含正反例），再开发/调 prompt；EDDOps 的"最小有效变更优先"避免一上来就换模型。
3. **搭建三级评测金字塔**：单元层（grader/断言/单步检查，快且确定性）→ 集成层（轨迹/结构测试，OTel trace + 模拟响应，参考 2601.18827）→ E2E 层（persona 模拟器 + mock 后端 + 终态校验，τ-bench 模式）。CI 里前两层必过，E2E 层按预算抽样或定时全量。
4. **把用户模拟器当资产管理**：persona 从真实日志挖掘（含隐式画像，USP 路线），覆盖合作/非合作/模糊/易怒等切片（ChatChecker）；需要时给用户侧也加上行动能力（τ²-bench）；模拟器定期与真实对话做保真度抽检；裁判独立于模拟器与被测 agent，并用人工标注校准一致率后才允许自动放量（DoorDash），有条件时用 GEPA 优化裁判一致性（Nubank）。
5. **发布门禁双轨制**：regression 套件近满分才放行（掉分即阻断），capability 套件作为观察指标；高风险场景用 pass^k（k=3~8）而不是 pass@1 定发布线；保留 shadow 对比与 canary 灰度作为离线之外的第二道闸；门禁可升级为"证据充分性"判断（2603.15676）。
6. **建立数据飞轮的组织流程**：生产 trace 采样 → 失败归因 → 编码用例（带 provenance/slice 标签）→ 进回归集 → 优化（手工或 MIPROv2/GEPA 自动）→ 重跑达标 → 发布 → 回流。明确谁对"用例增长"与"裁判校准"负责（Discord AITL 证明了周级迭代的可行性；OpenAI CE 把"每次变更跑 eval"设为默认）。
7. **警惕评测自身的退化**：eval 集需要版本化、污染检测与定期换血；裁判要防被 agent"钻空子"（检查 transcript、防固定话术骗分）；平均分不可信，按 slice 报告并监控方差；eval 成为优化目标后尤其要防过拟合。
8. **评测资产与平台解耦**：OpenAI 平台关闭的教训——数据集、grader、用例定义用开放格式（JSON/YAML + 代码）托管在自家仓库，平台只做运行与可视化，避免迁移成本。
9. **把指标写进产品语言**：向业务方汇报时用"三连全对率 42%"这类 pass^k 表述，而不是单次通过率；把 eval 证据（通过率、幻觉率、升级率、NPS 相关性）纳入发布单，像 Nubank 那样用离线-线上相关性为 eval 体系本身争取信任与预算。

---

## 参考清单

### 核心论文（15 篇；arxiv ID 均于 2026-08-05 通过 arxiv API/abs 页面核实，★ 为 ACL Anthology）

1. Xia, Lu, Zhu, Xing, Zhao, Zhang. *Evaluation-Driven Development and Operations of LLM Agents: A Process Model and Reference Architecture*. [arxiv 2411.13768](https://arxiv.org/abs/2411.13768)（2024-11 首发，2025-11 v3）
2. Gupta, Rossell, Alcobaça, et al. (Nubank). *Building Customer Support AI Agents at 100M-User Scale: An Evaluation-Driven Framework*. [arxiv 2606.08867](https://arxiv.org/abs/2606.08867)（2026-06）
3. Yao, Shinn, Razavi, Narasimhan. *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*. [arxiv 2406.12045](https://arxiv.org/abs/2406.12045)（2024-06）
4. Barres, Dong, Ray, et al. *τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment*. [arxiv 2506.07982](https://arxiv.org/abs/2506.07982)（2025-06）
5. Sekulić, Terragni, Guimarães, et al. *Reliable LLM-based User Simulator for Task-Oriented Dialogue Systems (DAUS)*. [arxiv 2402.13374](https://arxiv.org/abs/2402.13374)（2024-02）
6. Wang, Li, Yang, et al. *Know You First and Be You Better: Modeling Human-Like User Simulators via Implicit Profiles (USP)*. [arxiv 2502.18968](https://arxiv.org/abs/2502.18968)（2025-02）
7. Mayr, Schimpf, Bohné. *ChatChecker: A Framework for Dialogue System Testing and Evaluation Through Non-cooperative User Simulation*. [arxiv 2507.16792](https://arxiv.org/abs/2507.16792)（2025-07）
8. Gao, Shen, Wang, et al. *Benchmarking and Learning Real-World Customer Service Dialogue (OlaBench/OlaMind)*. [arxiv 2510.22143](https://arxiv.org/abs/2510.22143)（2025-10）
9. Mohammadi, Li, Lo, et al. *Evaluation and Benchmarking of LLM Agents: A Survey*. [arxiv 2507.21504](https://arxiv.org/abs/2507.21504)（2025-07）
10. Agrawal, Tan, Soylu, et al. *GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning*. [arxiv 2507.19457](https://arxiv.org/abs/2507.19457)（2025-07）
11. Opsahl-Ong, Ryan, Purtell, et al. *Optimizing Instructions and Demonstrations for Multi-Stage Language Model Programs (MIPROv2)*. [arxiv 2406.11695](https://arxiv.org/abs/2406.11695)（2024-06）
12. Kohl, Kruse, Mostafa, et al. *Automated Structural Testing of LLM-based Agents: Methods, Framework, and Case Studies*. [arxiv 2601.18827](https://arxiv.org/abs/2601.18827)（2026-01）
13. Maiorano. *Automated Self-Testing as a Quality Gate: Evidence-Driven Release Management for LLM Applications*. [arxiv 2603.15676](https://arxiv.org/abs/2603.15676)（2026-03）
14. ★ Gromada, Kasicka, Komkowska, et al. *Evaluating Conversational Agents with Persona-driven User Simulations based on Large Language Models: A Sales Bot Case Study*. EMNLP 2025 Industry. [ACL 2025.emnlp-industry.16](https://aclanthology.org/2025.emnlp-industry.16/)
15. ★ Zhao, Zhang, Su, et al. (Discord). *Agent-in-the-Loop: A Data Flywheel for Continuous Improvement in LLM-based Customer Support*. EMNLP 2025 Industry. [ACL 2025.emnlp-industry.135](https://aclanthology.org/2025.emnlp-industry.135/)

### 延伸阅读（arxiv ID 均已核实）

- Zhuge, Zhao, Ashley, et al. *Agent-as-a-Judge: Evaluate Agents with Agents*. [2410.10934](https://arxiv.org/abs/2410.10934)（2024-10）
- Zhang, Nayyeri, Khaziev, Yilmaz, Tur, Hakkani-Tür, Thadakamalla. *ATOD: An Evaluation Framework and Benchmark for Agentic Task-Oriented Dialogue Systems*. [2601.11854](https://arxiv.org/abs/2601.11854)（2026-01）
- Le, Lu, Stern, et al. *SAGE: Scalable AI Governance & Evaluation*. [2602.07840](https://arxiv.org/abs/2602.07840)（2026-02）
- Chishti, Oyinloye, Li. *Test Before You Deploy: Governing Updates in the LLM Supply Chain*. [2604.27789](https://arxiv.org/abs/2604.27789)（2026-04）
- Khattab, et al. *DSPy*. [2310.03714](https://arxiv.org/abs/2310.03714)（2023-10，背景）
- Zheng, et al. *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*. [2306.05685](https://arxiv.org/abs/2306.05685)（2023-06，背景）
- Chiang, et al. *Chatbot Arena*. [2403.04132](https://arxiv.org/abs/2403.04132)（2024-03）
- Zhao, et al. *WildChat: 1M ChatGPT Interaction Logs in the Wild*. [2405.01470](https://arxiv.org/abs/2405.01470)（2024-05）
- Zheng, et al. *LMSYS-Chat-1M*. [2309.11998](https://arxiv.org/abs/2309.11998)（2023-09，背景）
- Park, et al. *Generative Agents*. [2304.03442](https://arxiv.org/abs/2304.03442)（2023-04，背景）
- Ge, et al. *Scaling Synthetic Data Creation with 1,000,000,000 Personas*. [2406.20094](https://arxiv.org/abs/2406.20094)（2024-06）
- Rizwan, Carlsson, et al. *PersonaBOT*. [2505.17156](https://arxiv.org/abs/2505.17156)（2025-05）
- Chang, et al. *From Simulation to Strategy*. [2510.08621](https://arxiv.org/abs/2510.08621)（2025-10）

### 工业界博客与文档

- Anthropic Engineering: [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)（2026-01-09，原文已核实）
- Anthropic Engineering: [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents)（2024-12-19）
- DoorDash Engineering: [A Simulation and Evaluation Flywheel to Develop LLM Chatbots at Scale](https://careersatdoordash.com/blog/doordash-simulation-evaluation-flywheel-to-develop-llm-chatbots-at-scale/)（2026-01-26；原文抓取受限，要点经 [ByteByteGo 转述](https://blog.bytebytego.com/p/how-doordash-built-a-testing-system)与 [InfoQ 报道](https://www.infoq.com/news/2026/03/doordash-llm-chatbot-simulator/)交叉核实）
- DoorDash Engineering: [Building Ask DoorDash (Part 3): Evaluation](https://careersatdoordash.com/blog/building-ask-doordash-part-three-evaluation/)（2026-06-30）
- OpenAI: [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)（原文已核实，含 Evals 平台弃用时间表）；[openai/evals](https://github.com/openai/evals)（2023 开源 registry）；[Introducing AgentKit](https://openai.com/index/introducing-agentkit/)（2025-10，含托管 Evals）
- Hamel Husain: [Your AI Product Needs Evals](https://hamel.dev/notes/llm/evals/)
- Braintrust: [What is eval-driven development](https://www.braintrust.dev/articles/eval-driven-development)
- Google web.dev: [Evaluation-driven development](https://web.dev/learn/ai/evaluation-driven-development)
- DeepEval: [Eval Driven Development](https://deepeval.com/blog/eval-driven-development)
- GitHub: [awesome-eval-driven-development](https://github.com/itsderek23/awesome-eval-driven-development)

### 核实说明

- 全部 26 个 arxiv ID（核心 13 + 延伸阅读 13）均于 2026-08-05 通过 `export.arxiv.org/api/query` 或 abs 页面核实（标题与 v1 日期一致）；2 篇 EMNLP 工业赛道论文经 ACL Anthology 页面核实。
- 本次复核修正了早期转述中的三处数字：（1）τ-bench GPT-4o airline pass^1 实为 **42.0%**（官方 README），早期误记约 35%；retail pass^1 为 60.4%、pass^4 为 38.3%/20.0%；摘要仅断言"<50% 与 retail pass^8<25%"。（2）GEPA 相对 GRPO 为**平均 +6%**（早期误记约 10%），最高 +20%，rollouts 最多省 35 倍，比 MIPROv2 +10%+。（3）MIPROv2 摘要口径为"5/7 程序优于基线、最高 +13%"（Llama-3-8B），"30+ 任务平均 +5%"系 DSPy 文档口径，未见于摘要，故不采。
- Anthropic 博客（20-50 起步、pass^3=42% 示例、SWE-bench 40%→80%+、CORE-Bench 42%→95%、Bolt 3 个月）与 OpenAI 文档（eval-driven/continuous evaluation、六类数据来源、ROUGE-L≥0.40/G-Eval≥80%/recall≥0.85/precision≥0.7/好评 70%+、Evals 平台 2026-10-31 转只读/2026-11-30 关闭）均逐条对照原文核实。
- DoorDash 两篇博客原文站点反爬（HTTP 403），数字经第三方转述交叉核实并已标注【原文未直接核实】；2601.18827、2603.15676、2507.16792、2510.22143、2602.07840 的作者机构未逐一核实；EDDOps 的 MLR 百分比引自论文正文（摘要不含该统计）。
