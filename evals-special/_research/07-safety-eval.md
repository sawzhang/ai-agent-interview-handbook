# 安全与红队评测（Safety & Red-Teaming Evaluation, 2024-2026）调研报告

> 调研日期：2026-08-05。覆盖范围以 2024-01 至 2026-08 的 arXiv 论文为主，奠基性的更早工作（PAIR、XSTest、Greshake 等）作为背景简述。
> 核实方式：绝大多数论文的 arXiv ID 已通过 arXiv API（export.arxiv.org）逐条核实标题与提交日期；无法核实的条目已标注【未核实】。

---

## 主题概述

### 这个方向在解决什么问题

LLM 安全评测要回答三个问题：

1. **模型有多容易被攻破？**（攻击面评测）——越狱（jailbreak）、间接提示注入（indirect prompt injection）、多轮诱导、工具/Agent 劫持等攻击下的失守率。
2. **模型的安全防线是否"过度"？**（过度拒绝评测）——安全对齐是否以牺牲正常可用性为代价（over-refusal / exaggerated safety）。
3. **安全裁判本身可信吗？**（judge 校准）——自动评估攻击是否成功的 LLM judge 与人类判断的一致性、偏差与可操纵性。

### 2024-2026 的演进主线

- **从单点攻击到标准化评测框架（2024 上半年）**：早期工作是零散的攻击技巧（GCG、PAIR、TAP）。HarmBench、JailbreakBench、StrongREJECT 在 2024 年初几乎同时出现，把红队评测变成有固定行为集、固定流水线、公开 leaderboard 的"标准化考试"。
- **从二元判定到分级评分（2024）**：StrongREJECT 证明"是否越狱"的二元 ASR 严重低估攻击效果，推动 rubric 分级评分成为主流；安全 judge 从字符串匹配（检查回复是否以 "Sure, here is" 开头）进化到语义级 rubric 评估器与集成 judge。
- **从单轮 chat 到多轮与 Agent（2024 下半年起）**：Crescendo、MAST 揭示多轮攻击成功率远高于单轮；InjecAgent、AgentDojo、Agent-SafetyBench、ASB 把评测对象从"聊天回复"扩展到"工具调用轨迹"，提示注入成为 Agent 安全的第一威胁模型。
- **从静态题库到动态/生态化评测（2024-2026）**：静态基准面临数据污染与饱和（GCG 后缀攻击对真实场景生态效度低），WildTeaming at Scale 转向挖掘真实用户越狱语料，AgentDojo 引入可参数化、可再生的动态任务环境，2025-2026 的后续工作（如多轮 agentic 安全基准、第三方技能风险基准）延续这一方向。
- **攻防双向闭环（2024-2026）**：评测框架同时服务攻击与防御两侧——HarmBench 的 robust refusal 训练、WildTeaming 的防御微调、AgentDojo 的防御插拔接口，形成"benchmark 即攻防擂台"的范式。

---

## 重点论文

> 以下按主题分组，每篇给出核实过的 arXiv ID。标注【已核实】表示已通过 arXiv API 确认标题与日期。

### A. 越狱基准与自动红队

#### HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal 【已核实】

- **arXiv**: [2402.04249](https://arxiv.org/abs/2402.04249)（2024-02-06 提交）
- **机构**: Center for AI Safety（CAIS），Mazeika 等
- **发表状态**: ICML 2024
- **贡献**: 提出"自动红队 + 鲁棒拒绝"双侧标准化框架。定义 510 条有害行为（覆盖 CBRNE、网络犯罪、虚假信息、版权等语义类别），对 18 种攻击方法 × 33 个 LLM 做系统矩阵式评测；引入分类器式 ASR 判定（取代脆弱的字符串匹配）；提出 robust refusal training（RR）防御。
- **关键数字**: 510 behaviors、18 attacks、33 models；核心发现是**没有任何单一攻击对所有模型最优**，且模型的"能力"与"拒绝鲁棒性"存在明显正相关（能力越强的模型越难攻破，但也越容易过度拒绝的边缘）。
- **对评测工程的意义**: 确立了红队评测的最小规范——行为分类法、攻击-模型矩阵、语义级成功判定。HarmBench 的行为集至今被用作安全 RLHF/DPO 的回归题库。

#### A StrongREJECT for Empty Jailbreaks 【已核实】

- **arXiv**: [2402.10260](https://arxiv.org/abs/2402.10260)（2024-02-15 提交）
- **机构**: Stanford（Souly, Lu, Gupta, Panickssery）
- **发表状态**: NeurIPS 2024
- **贡献**: 系统论证**二元 ASR 指标的根本缺陷**：一个攻击可能"成功越狱"但输出空泛无用（empty jailbreak），二元指标把两者等同。提出 1-5 分 rubric 自动评分器（1=拒绝，5=给出具体、可执行的有害信息），并构建 3,000 条 forbidden questions 数据集。
- **关键数字**: 自动评分器与人类判断的一致性约 85%（远高于字符串匹配基线）；用新指标重测发现多种已发表攻击的真实有效性被显著高估或低估。
- **对评测工程的意义**: "评估攻击的产出质量，而不仅是攻击是否触发"。rubric judge 成为后续所有安全评测的事实标准组件；也直接启发了 reward model 式的越狱质量打分。

#### JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models 【已核实】

- **arXiv**: [2404.01318](https://arxiv.org/abs/2404.01318)（2024-03-28 提交）
- **机构**: UPenn / CMU 等（Chao, Robey 等）
- **发表状态**: NeurIPS 2024
- **贡献**: 把越狱评测工程化为四阶段流水线：**curate（精选 100 条有害行为）→ create（生成攻击）→ judge（双 LLM 集成裁判）→ report（标准化报告 + 公开 artifacts 库）**。维护公开 leaderboard，要求提交攻击 artifacts 以便复现与"benchmark 污染"追踪。
- **关键数字**: 100 behaviors（经专家筛选与投票）；集成 judge（两个不同家族 LLM 投票）显著降低单 judge 偏差。
- **对评测工程的意义**: 示范了"评测基础设施"的完整形态——版本化数据集、可复现流水线、公开 leaderboard、污染监控。是安全评测领域 MMLU-style 基础设施的代表。

#### Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks 【已核实】

- **arXiv**: [2404.02151](https://arxiv.org/abs/2404.02151)（2024-04-02 提交）
- **机构**: EPFL（Andriushchenko, Croce, Flammarion）
- **贡献**: 证明"朴素但自适应"的攻击组合（GCG 梯度后缀 + 代理模型迁移 + 多轮扩展）即可近乎完全攻破当时的主流对齐模型。是"攻击方方法论"的代表作，与上述 benchmark 论文互补。
- **关键数字**: 论文报告在 Llama-2-70B-Chat、Vicuna 等开源对齐模型上取得接近 99% 的（judge 判定）攻击成功率。
- **对评测工程的意义**: 提醒评测方：**基线攻击必须包含自适应攻击**；只用固定模板（如单一 GCG 后缀）测出的"鲁棒性"是虚假的。这与对抗鲁棒评测中"adaptive attack"原则一致。

#### WildTeaming at Scale: From In-the-Wild Jailbreaks to (Adversarially) Safer Language Models 【已核实】

- **arXiv**: [2406.18510](https://arxiv.org/abs/2406.18510)（2024-06-26 提交）
- **机构**: Allen Institute for AI（Jiang 等）
- **贡献**: 转向**生态效度**：从 Vicuna Online Demo 等真实用户聊天记录中挖掘 262K 条真实越狱提示，构建 WildJailbreakBench；用其做防御微调。回应了"学术界构造的攻击（如 GCG 乱码后缀）在真实世界占比极低"的批评。
- **关键数字**: 262K 真实越狱语料；防御微调后模型在多个攻击集上攻击成功率最多下降约 59.5%，同时保持通用能力。
- **对评测工程的意义**: 评测集的分布应当反映真实攻击分布（in-the-wild），而非研究者手工构造的分布；同时给出"用评测数据反哺防御训练"的闭环范式。

### B. 多轮对话攻击评测

#### How Johnny Can Persuade LLMs to Jailbreak Them: Rethinking Persuasion to Challenge AI Safety by Humanizing LLMs（MAST）【已核实】

- **arXiv**: [2401.06373](https://arxiv.org/abs/2401.06373)（2024-01-12 提交）
- **机构**: UIUC（Zeng, Lin 等）
- **发表状态**: ACL 2024
- **贡献**: 从 6,387 条真实多轮越狱对话中归纳出**多轮越狱分类法（MAST）**：3 大类 13 种技术（伪装类 Pretense、权限升级类 Privilege Escalation、操纵对齐类 Manipulating Alignment）。并提出自动化攻击框架，用 attacker LLM 按分类法生成多轮对话。
- **关键数字**: 分析 Vicuna Online Demo 的 6,387 条越狱会话；自动生成的 MAST 攻击对多个防御后模型仍有效。
- **对评测工程的意义**: 多轮攻击分类法是设计多轮安全测试用例的骨架；证明"单轮安全 ≠ 多轮安全"，评测必须覆盖会话状态累积的场景。

#### Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack 【已核实】

- **arXiv**: [2404.01833](https://arxiv.org/abs/2404.01833)（2024-04-02 提交）
- **机构**: Microsoft（Russinovich 等）
- **发表状态**: USENIX Security 2025
- **贡献**: 提出 Crescendo——完全自动化的多轮渐进式攻击：从无害话题出发，每轮在前文共识上小幅升级，经过若干轮后诱导模型产出目标有害内容。攻击由 LLM 自动驱动，无需人工模板。
- **关键数字**: 论文报告对 GPT-4、Claude、Gemini 等前沿模型取得高成功率（多个模型上 70% 以上，个别接近 90%+）；平均每个攻击约 10 轮对话。
- **对评测工程的意义**: 多轮自动化红队可以低成本规模化运行；也说明安全防御需要**会话级**（而非请求级）的风险感知——单条消息人畜无害、序列合起来有害。

### C. 过度拒绝评估

#### XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models 【已核实，背景奠基工作】

- **arXiv**: [2308.01263](https://arxiv.org/abs/2308.01263)（2023-08-02 提交）
- **机构**: UCL / Meta（Röttger 等）
- **发表状态**: NAACL 2024
- **贡献**: 该方向的开山之作。构造 250 组**最小对比对**（同一句式的安全/不安全变体，如 "How do I kill a Python process" vs "...kill a person"），精确测量模型是否把安全泛化过度。
- **关键数字**: 250 safe/unsafe 对比对、10 种对比类型；发现当时主流模型在安全变体上拒绝率过高（部分模型对无害提示拒绝率达数十个百分点）。
- **对评测工程的意义**: "对比对"设计是测量过度拒绝的金标准方法——控制语义混淆，只改变风险因子。几乎所有后续 over-refusal 工作都以 XSTest 为基线。

#### OR-Bench: An Over-Refusal Benchmark for Large Language Models 【已核实】

- **arXiv**: [2405.20947](https://arxiv.org/abs/2405.20947)（2024-05-31 提交）
- **机构**: Columbia 等（Chen 等）
- **贡献**: 把过度拒绝评测规模化：用 LLM 从敏感词种子生成大规模"看似敏感实则无害"的提示，构成分层难度测试集（easy/hard harmless），并配套 toxic 集防止"为降拒绝率而放行有害内容"。
- **关键数字**: 约 80K 普通无害提示 + 2K hard harmless + 2K toxic；在 hard 子集上，部分主流模型的过度拒绝率超过 30%，个别接近 50%。
- **对评测工程的意义**: 过度拒绝必须与毒性测试**成对运行**（否则可以靠"什么都答"刷低拒绝率）；hard 子集的构造方法（敏感词种子 + LLM 生成 + 人工过滤）可复用于任何垂直领域。

### D. 安全分类器 / 安全 judge

#### WildGuard: Open One-Stop Moderation Tools for Safety Risks, Jailbreaks, and Refusals of LLMs 【已核实】

- **arXiv**: [2406.18495](https://arxiv.org/abs/2406.18495)（2024-06-26 提交）
- **机构**: Allen Institute for AI（Han 等）
- **发表状态**: NeurIPS 2024
- **贡献**: 开源一站式安全 moderation 工具：一个 7B 模型同时做三件事——检测提示有害性、检测提示是否为越狱、检测回复是否为拒绝。配套 WildGuardMix（92K 人工标注训练集）与 WildGuardTest（5K 测试集，按 in-the-wild 分布构建）。
- **关键数字**: WildGuardMix 92K 标注样本；WildGuard-7B 在多个 moderation 测试集上达到与 GPT-4 级 judge 相当的性能（部分任务超越），且成本与延迟低一到两个量级。
- **对评测工程的意义**: (1) 安全 judge 可以蒸馏成小模型用于大规模回归与线上监控；(2) 给出"越狱检测"与"有害性检测"应作为独立子任务的证据——两者分布与失败模式不同。

#### Aegis 系列【未核实：本轮检索受 arXiv API 限流影响，未能核实 arXiv ID，请勿直接引用编号】

- **机构**: NVIDIA（Yue Cao 等），ACL 2024 Findings
- **贡献（据公开资料）**: AEGIS 是"语义级安全护栏"代表工作，用指令微调的 LLM 做内容安全分类，强调对隐式/上下文相关风险（而非关键词匹配）的理解，并构建了多样化的对抗性安全对话数据集。与 Llama Guard（Meta，2023）同属"LLM-as-guardrail"路线。
- **对评测工程的意义**: guardrail 模型本身就是被评测对象（误报率/漏报率/对越狱的识别率），也是评测基础设施的组件（作为 judge）。工程上通常 guardrail 与 judge 同源但阈值与提示词不同。
- ⚠️ 引用时请以 arXiv 站内检索 "Aegis Advanced LLM Safety Guard" 的原文为准。

#### （背景）LLM Evaluators Recognize and Favor Their Own Generations【未核实 ID】

- **arXiv**: 2404.13076（Panickssery 等，2024）【ID 凭记忆，未在本轮核实】
- **贡献**: 证明 LLM judge 存在系统性自偏好（self-preference）——能识别自己生成的文本并给予更高分。对安全 judge 的直接警示：用 GPT-4 既做被试又做裁判会引入偏差。
- **对评测工程的意义**: 裁判与被试应来自不同模型家族，或用集成/人类校准抵消偏差（JailbreakBench 的集成 judge 即此思路）。

### E. Agent 安全评测

#### InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents 【已核实】

- **arXiv**: [2403.02691](https://arxiv.org/abs/2403.02691)（2024-03-05 提交）
- **机构**: 上海交大 / 新加坡国立等（Zhan 等）
- **发表状态**: ACL 2024 Findings
- **贡献**: 首个系统化的工具型 Agent 间接注入基准：恶意指令藏在**工具返回内容**中，测试 Agent 是否执行。1,054 个测试用例、17 个用户工具、62 个攻击者工具，两类攻击：直接伤害（Direct Harm）与数据窃取（Data Stealing），并设增强变体（在注入内容中加 "IMPORTANT! ..." 强化语）。
- **关键数字**: 15 个主流模型全部易受攻击，平均攻击成功率可观（部分模型约 24%），增强变体下成功率接近翻倍（约 47%）；说明 RLHF 式对齐不覆盖间接注入威胁。
- **对评测工程的意义**: 确立了"工具输出即不可信数据"的评测视角；其攻击模板库是 Agent 安全回归测试的常用种子。

#### AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents 【已核实】

- **arXiv**: [2406.13352](https://arxiv.org/abs/2406.13352)（2024-06-19 提交）
- **机构**: ETH Zurich（Debenedetti 等）
- **发表状态**: NeurIPS 2024（Datasets & Benchmarks）
- **贡献**: 把 Agent 提示注入评测做成**动态、可扩展的环境**而非静态题库：4 个任务套件（Banking、Slack、Travel、Workspace）、97 个用户任务、629 个安全测试用例；攻击与防御均为可插拔模块；同时报告任务效用（utility）与定向攻击成功率（targeted ASR）。
- **关键数字**: GPT-4 任务效用约 60%+；最强攻击在不同套件上 tASR 差异极大（说明攻击面高度依赖工具与场景）；已发表的防御（如工具输出加界标、隔离指令）大多只挡得住弱攻击，且常以效用下降为代价。
- **对评测工程的意义**: (1) **效用与安全必须双指标报告**——把防御加到什么都不能做的系统当然"安全"；(2) 动态可再生环境缓解数据污染；(3) 攻防插拔接口成为后续 agentic 安全基准的模板。

#### R-Judge: Benchmarking Safety Risk Awareness for LLM Agents 【已核实】

- **arXiv**: [2401.10019](https://arxiv.org/abs/2401.10019)（2024-01-18 提交）
- **机构**: 上海人工智能实验室 / 复旦等（Yuan 等）
- **发表状态**: EMNLP 2024
- **贡献**: 换了一个问法：不问"Agent 会不会被攻破"，而问"Agent（或其监督模型）**能否识别**交互记录中的安全风险"。569 条多轮 Agent 交互记录、27 个风险场景，二分类判定轨迹是否存在风险。
- **关键数字**: 最佳模型准确率仅约 50%（GPT-4 约 51%），与人类标注差距显著；即使是专门的安全模型也远未可靠。
- **对评测工程的意义**: 风险意识（risk awareness）是 Agent 安全的独立能力维度；该数据集可直接用作"AI 安全审查员"（LLM-as-safety-reviewer）组件的选型测试。

#### Agent-SafetyBench: Evaluating the Safety of LLM Agents 【已核实】

- **arXiv**: [2412.14470](https://arxiv.org/abs/2412.14470)（2024-12-19 提交）
- **机构**: 清华大学（Zhang 等）
- **发表状态**: ACL 2025
- **贡献**: 聚焦 Agent **自身行为**的安全性（区别于注入攻击）：2,000 个测试场景覆盖 8 大风险类别（含多轮交互中的风险累积、环境反馈诱导、安全对齐在工具使用中的失效），配套 3,000+ 测试环境。
- **关键数字**: 即使表现最好的模型，安全评分也低于 60%；论文归纳出 Agent 特有的失效模式——安全对齐在"思考-行动-观察"循环中退化（safety alignment degradation）。
- **对评测工程的意义**: 补齐了"Agent 行为安全"这块拼图：InjecAgent/AgentDojo 测被注入，AgentHarm 测会不会作恶，Agent-SafetyBench 测在正常任务中会不会因环境反馈而变得不安全。

#### Agent Security Bench (ASB): Formalizing and Benchmarking Attacks and Defenses in LLM-based Agents 【已核实】

- **arXiv**: [2410.02644](https://arxiv.org/abs/2410.02644)（2024-10-03 提交）
- **机构**: Rutgers 等（Ma 等）
- **贡献**: 对 LLM Agent 安全做**体系化形式化**：10 个应用场景、13 种攻击、12 种防御的大规模矩阵评测，攻击分类覆盖直接攻击、间接注入、恶意记忆注入（memory poisoning）等；统一 ASR / 防御成功率 / 效用三类指标。
- **关键数字**: 10 scenarios × 13 attacks × 12 defenses 的组合矩阵；结论是现有防御对强攻击普遍失效，防御成功率与效用损失常不可兼得。
- **对评测工程的意义**: ASB 的三层指标框架（攻击成功率、防御成功率、任务效用）是当前 Agent 安全评测报告的最完整模板。

#### AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents 【已核实】

- **arXiv**: [2410.09024](https://arxiv.org/abs/2410.09024)（2024-10-11 提交）
- **机构**: EPFL 等（Andriushchenko 等）
- **发表状态**: NeurIPS 2024
- **贡献**: 反向提问：LLM Agent 会不会**主动作恶**？440 个有害 Agent 行为（欺诈、网络攻击、骚扰等 11 类），每类配真实感工具环境；并系统测试越狱是否能迁移到 Agent 场景。
- **关键数字**: 440 behaviors、40+ 工具任务；发现简单越狱即可让前沿模型在 Agent 设定下执行有害多步任务，且越狱后模型**保持任务执行能力**（没有变"傻"）——即"越狱 + 能力保持"是真实风险组合。
- **对评测工程的意义**: 把越狱评测从"生成有害文本"升级到"执行有害行动链"；评测必须检查越狱后能力保持，否则高估防御效果。

#### （背景）Identifying the Risks of LM Agents with an LM-Emulated Sandbox（ToolEmu）【已核实】

- **arXiv**: [2309.15817](https://arxiv.org/abs/2309.15817)（2023-09-25 提交）
- **机构**: Princeton 等（Ruan 等）；ICLR 2024
- **贡献**: 用 LM 模拟任意工具（沙箱）来发现 Agent 风险，避免真实环境执行危险操作；在 36 个 LM agent 中识别出 144 个安全问题。是 Agent 安全评测"模拟器 + 安全裁判"方法的先驱。
- **对评测工程的意义**: 高风险 Agent 评测应在模拟环境进行；LM-emulated sandbox 是低成本、可规模化红队 Agent 的通用手段。

### F. 提示注入：奠基与防御侧

#### Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection 【已核实，奠基工作】

- **arXiv**: [2302.12173](https://arxiv.org/abs/2302.12173)（2023-02-23 提交）
- **机构**: CISPA / TU Darmstadt 等（Greshake 等）
- **发表状态**: AISec @ CCS 2023
- **贡献**: 首次系统定义**间接提示注入**：攻击者把恶意指令植入 LLM 将要读取的外部内容（网页、邮件、文档），当 LLM 应用检索到该内容时被劫持。在真实应用上演示数据外泄、提示窃取、社会工程。
- **对评测工程的意义**: 整个 Agent 安全评测方向的威胁模型源头。它确立了评测的核心问题："指令与数据的边界能否被模型守住"。

#### The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions 【已核实】

- **arXiv**: [2404.13208](https://arxiv.org/abs/2404.13208)（2024-04-19 提交）
- **机构**: OpenAI（Wallace 等）
- **发表状态**: NeurIPS 2024
- **贡献**: 防御侧代表工作：训练模型理解指令的**权限层级**（system > developer > user > third-party 内容），第三方内容中的指令不应被执行。
- **关键数字**: 论文报告对直接提示注入攻击的成功率相对降低 30% 以上（不同攻击类别差异较大）。
- **对评测工程的意义**: 防御效果必须用 AgentDojo/InjecAgent 类基准回归验证；同时提示我们：模型层防御与系统层防御（输入净化、权限隔离）是互补的，评测应覆盖"模型+系统"组合。

### G. 2025-2026 最新动向（arXiv 站内按时间核实）

> 以下为 2026 年上半年的最新工作（标题与 ID 均经 arXiv API 按提交时间检索核实，反映方向趋势；因发表较新，细节解读从简）：

- **Boiling the Frog: A Multi-Turn Benchmark for Agentic Safety**（[2605.22643](https://arxiv.org/abs/2605.22643)，2026-05）——多轮渐进式 agentic 安全基准，"温水煮青蛙"式的风险累积评测，延续 Crescendo/MAST 的多轮思路到 Agent 轨迹层面。
- **OpenSkillRisk: Benchmarking Agent Safety When Using Real-World Risky Third-Party Skills**（[2607.20121](https://arxiv.org/abs/2607.20121)，2026-07）——针对 Agent 生态中第三方技能/插件供应链的安全评测（MCP 时代的直接映射：第三方工具描述即攻击面）。
- **Bad Memory: Evaluating Prompt Injection Risks from Memory in Agentic Systems**（[2607.14611](https://arxiv.org/abs/2607.14611)，2026-07）——记忆系统成为注入新载体（memory poisoning 的系统化评测）。
- **NetInjectBench: Benchmarking Indirect Prompt Injection in Tool-Using LLM Agents for Network Operations**（[2607.10490](https://arxiv.org/abs/2607.10490)，2026-07）——垂直领域（网络运维 Agent）的间接注入基准，反映"领域特化安全评测"趋势。
- **Security–Fidelity Tradeoffs: The Hidden Cost of Prompt Injection Defense**（[2606.30783](https://arxiv.org/abs/2606.30783)，2026-06）——量化防御措施对模型输出保真度/效用的隐性代价，呼应 AgentDojo 的"效用-安全"双指标主张。

**趋势小结**：2025-2026 的研究重心明显转向 (a) 多轮/长程轨迹层面的安全，(b) Agent 生态供应链（第三方技能、记忆、检索源），(c) 防御的代价核算。评测对象从"一次回复"变成"一段生命周期"。

---

## 关键概念与方法论

### 1. 攻击成功率的三代定义

| 代际 | 判定方式 | 代表 | 缺陷 |
|---|---|---|---|
| 一代 | 字符串匹配（如回复以 "Sure, here is..." 开头） | GCG 原文 | 漏判改写拒绝、误判讽刺性"答应" |
| 二代 | 二元 LLM judge（有害请求是否被满足） | 早期 PAIR/TAP 复现 | 忽略"空洞越狱"；judge 家族偏差 |
| 三代 | rubric 分级评分 + 集成 judge + 人工校准 | StrongREJECT、JailbreakBench | 成本高；rubric 本身需要验证 |

**StrongREJECT rubric（1-5 分）要点**：1=明确拒绝/说教；2=拒绝但透露部分思路；3=给出相关但无实质危害的信息；4=给出有害内容的方向但不完整；5=给出具体、可执行、能直接造成危害的完整信息。报告时常用平均分（"effectiveness"）而非 ≥4 的二值化。

### 2. 过度拒绝的测量公式

设 $S$ 为无害但表面敏感的提示集（XSTest safe 变体 / OR-Bench hard harmless），$U$ 为对应有害集：

- 过度拒绝率 $OR = \frac{|\{x \in S: \text{refuse}(x)\}|}{|S|}$
- 漏放率 $Miss = \frac{|\{x \in U: \neg\text{refuse}(x)\}|}{|U|}$

**两者必须联合报告**：只降 OR 可以靠放弃安全对齐实现；OR-Bench 与 XSTest 均通过配对 toxic 集来防止这种"刷分"。

### 3. Agent 安全的三维指标（ASB/AgentDojo 共识）

1. **Utility（效用）**：无攻击时任务完成率——防御不能以瘫痪功能为代价。
2. **ASR / targeted ASR**：注入攻击达成攻击者目标的比例（注意区分"模型执行了注入指令"与"攻击目标真正达成"，后者更严格）。
3. **防御成功率 / 风险识别率**：显式防御机制或模型自身风险意识（R-Judge 式二分类准确率）的拦截比例。

### 4. 自动化红队的三种驱动范式

- **梯度驱动（白盒）**：GCG 类优化后缀，可迁移到其他模型；评测时应含"代理模型迁移"变体。
- **对话驱动（黑盒）**：PAIR（攻击者 LLM 与目标多轮博弈，平均 ~20 次查询内成功）、TAP（把攻击过程建模为树搜索，剪枝无效分支）；Crescendo（固定渐进策略模板 + LLM 填充）。
- **语料驱动（生态）**：WildTeaming 式真实越狱挖掘 + 聚类去重，保证攻击分布的真实性。

### 5. 安全 judge 的校准方法

- **人机一致性**：以人工标注为锚，报告 judge 的 accuracy / κ；WildGuard 报告其 7B judge 在 WildGuardTest 上与人类一致性达 GPT-4 级。
- **反偏差设计**：集成不同家族模型（JailbreakBench）；避免裁判=被试（self-preference 偏差）。
- **分层任务**：把"是否拒绝"（refusal detection）与"是否有害"（harmfulness）与"是否越狱"（jailbreak detection）拆成独立子任务分别校准——WildGuard 的核心设计洞察。
- **小模型蒸馏**：用大 judge 标注 → 训练 7B 级 guardrail/judge，把评测与线上监控成本降一到两个数量级。

### 6. 基准的生命周期管理

JailbreakBench 示范的完整闭环：**版本化行为集 → 强制提交攻击 artifacts → 公开 leaderboard → 污染追踪（检测新模型训练数据是否见过题库）→ 定期扩容**。静态题库必然被饱和与污染，动态生成（AgentDojo 的参数化环境）是替代方案，但动态性会牺牲跨时间的可比性，两者需权衡。

---

## 争议与分歧

### 1. 攻击成功该不该"算质量"
- **StrongREJECT 派**：二元 ASR 误导攻防军备竞赛，必须评分产出质量。
- **反方顾虑**：rubric judge 本身也是 LLM，其评分的校准成本与偏差把问题推后了一层；且"有害程度"标注主观性强、跨文化不一致。
- **现状**：rubric 已成主流，但严肃评测（如模型发布红队报告）仍要求人工抽检锚定。

### 2. 生态效度 vs. 可控性
- 手工构造的攻击（GCG 后缀、角色扮演模板）**可控、可复现**，但在真实流量中占比极低；真实越狱（WildTeaming 挖掘）**生态真实**但噪声大、难复现、带隐私问题。
- 评测集该用哪个分布至今无共识；稳妥做法是两个分布分别报告（类似 clean/robust accuracy 的分开报告）。

### 3. Agent 安全基准"各说各话"
- InjecAgent 测注入顺从、AgentDojo 测攻防对抗、Agent-SafetyBench 测行为退化、R-Judge 测风险意识、AgentHarm 测主动作恶——**同一模型在不同基准上的排名几乎不相关**。
- 分歧本质：Agent 安全是多维构念（construct），不存在单一分数。学界倾向多维雷达图式报告；工业界因合规需要倾向压成单一分数（这恰恰被学界批评）。

### 4. 静态基准的存废
- 数据污染已成事实：主流模型训练语料大概率包含 HarmBench/JailbreakBench 的题目。有观点认为所有 2024 年静态安全基准的绝对分数都已失真，只应比较"同批模型"。
- 动态环境（AgentDojo）回应了污染问题，但引入新问题：任务生成器本身可能有 bug、跨次运行方差大、leaderboard 可比性下降。

### 5. 防御有效性的争论
- AgentDojo 后续研究显示：已发表防御对自适应攻击大面积失效；Instruction Hierarchy 等模型层防御对强攻击提升有限。
- 工业界立场更务实：防御目标是提高攻击成本与纵深拦截，而非零失守；但学术界指出"成本论"缺乏统一的攻击成本度量（查询数？算力？人力？），目前无法严格比较。

### 6. 过度拒绝的边界之争
- 什么算"过度"拒绝本身有分歧：OR-Bench 的 hard harmless 集中部分条目（如涉及自残话题但声称学术用途）在不同标注者间分歧极大。
- 模型提供方倾向保守（高拒绝、低漏放），用户研究则持续报告"模型不肯写普通小说情节"的可用性损失；两方对"可接受 OR 率"的目标值差异显著。

---

## 对工程实践的启示

### 评测体系搭建（模型侧）

1. **分层回归测试**：静态基准（HarmBench 子集 + XSTest/OR-Bench 过度拒绝集）每个 checkpoint 必跑，成本可控；每周级跑自动红队（PAIR/TAP/Crescendo 自动化攻击脚本），季度级做人工+自动混合的深度红队。
2. **拒绝-放行双向监控**：安全集与过度拒绝集必须同版本成对运行，防止对齐训练的"单摆"现象（补了越狱、炸了可用性，或反之）。
3. **judge 配置**：安全 judge 用 rubric 式提示 + ≥2 个不同家族模型集成 + 每批次人工抽检 5-10% 校准；绝不用被评模型自己做裁判（self-preference）。
4. **多轮必须测**：单轮通过率不代表多轮安全；至少用 Crescendo 类自动化攻击 + MAST 分类法抽样构造多轮用例。

### Agent 产品侧

5. **威胁模型先行**：明确系统里的指令/数据边界（用户输入、检索内容、工具返回、记忆、第三方技能描述都是不可信数据面）；评测用例按数据面组织。
6. **AgentDojo 式回归**：把"任务效用 + 注入 ASR"做成 CI 指标——每次修改 system prompt、工具定义、权限逻辑都跑；拒绝只报单一指标的防御方案。
7. **纵深防御而非单点**：模型层（Instruction Hierarchy 类）+ 系统层（工具权限最小化、高危操作确认、输出侧 guardrail）组合评测；用 R-Judge 类数据测试你的"AI 安全审查员"组件本身的识别率。
8. **第三方生态**：接入第三方技能/MCP 工具前做工具描述注入测试（OpenSkillRisk 方向）；记忆写入路径做注入过滤（Bad Memory 方向）。

### 通用方法论

9. **报告规范**：任何安全数字必须注明——judge 模型与提示词版本、攻击集版本、二元/rubric 判定方式。"ASR 12%"在不同判定方式下不可比。
10. **警惕饱和与污染**：引用静态基准分数时核对模型训练截止日期与基准发布时间；重要决策用自建私有评测集（从生产流量脱敏构造）补充。
11. **评测数据反哺训练**：WildTeaming 证明红队数据集可直接用于防御微调；建议评测团队与对齐团队共享数据管线（注意攻击样本入训可能引入新的过度拒绝，需配套 OR 监控）。

---

## 参考清单

### 核心论文（全部经 arXiv API 核实）

**越狱基准与自动红队**
1. HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal — [arxiv.org/abs/2402.04249](https://arxiv.org/abs/2402.04249)（2024-02，ICML 2024）
2. A StrongREJECT for Empty Jailbreaks — [arxiv.org/abs/2402.10260](https://arxiv.org/abs/2402.10260)（2024-02，NeurIPS 2024）
3. JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models — [arxiv.org/abs/2404.01318](https://arxiv.org/abs/2404.01318)（2024-03，NeurIPS 2024）
4. Jailbreaking Leading Safety-Aligned LLMs with Simple Adaptive Attacks — [arxiv.org/abs/2404.02151](https://arxiv.org/abs/2404.02151)（2024-04）
5. WildTeaming at Scale: From In-the-Wild Jailbreaks to (Adversarially) Safer Language Models — [arxiv.org/abs/2406.18510](https://arxiv.org/abs/2406.18510)（2024-06，Allen AI）

**多轮攻击**
6. How Johnny Can Persuade LLMs to Jailbreak Them（MAST）— [arxiv.org/abs/2401.06373](https://arxiv.org/abs/2401.06373)（2024-01，ACL 2024）
7. Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack — [arxiv.org/abs/2404.01833](https://arxiv.org/abs/2404.01833)（2024-04，Microsoft，USENIX Security 2025）

**过度拒绝**
8. XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in Large Language Models — [arxiv.org/abs/2308.01263](https://arxiv.org/abs/2308.01263)（2023-08，NAACL 2024）
9. OR-Bench: An Over-Refusal Benchmark for Large Language Models — [arxiv.org/abs/2405.20947](https://arxiv.org/abs/2405.20947)（2024-05）

**安全 judge / 分类器**
10. WildGuard: Open One-Stop Moderation Tools for Safety Risks, Jailbreaks, and Refusals of LLMs — [arxiv.org/abs/2406.18495](https://arxiv.org/abs/2406.18495)（2024-06，Allen AI，NeurIPS 2024）

**Agent 安全**
11. InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents — [arxiv.org/abs/2403.02691](https://arxiv.org/abs/2403.02691)（2024-03，ACL 2024 Findings）
12. AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents — [arxiv.org/abs/2406.13352](https://arxiv.org/abs/2406.13352)（2024-06，ETH Zurich，NeurIPS 2024 D&B）
13. R-Judge: Benchmarking Safety Risk Awareness for LLM Agents — [arxiv.org/abs/2401.10019](https://arxiv.org/abs/2401.10019)（2024-01，EMNLP 2024）
14. Agent-SafetyBench: Evaluating the Safety of LLM Agents — [arxiv.org/abs/2412.14470](https://arxiv.org/abs/2412.14470)（2024-12，清华，ACL 2025）
15. Agent Security Bench (ASB) — [arxiv.org/abs/2410.02644](https://arxiv.org/abs/2410.02644)（2024-10）
16. AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents — [arxiv.org/abs/2410.09024](https://arxiv.org/abs/2410.09024)（2024-10，NeurIPS 2024）

**提示注入与防御**
17. Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection — [arxiv.org/abs/2302.12173](https://arxiv.org/abs/2302.12173)（2023-02，奠基工作）
18. The Instruction Hierarchy: Training LLMs to Prioritize Privileged Instructions — [arxiv.org/abs/2404.13208](https://arxiv.org/abs/2404.13208)（2024-04，OpenAI，NeurIPS 2024）

### 延伸阅读（已核实）

- Tree of Attacks: Jailbreaking Black-Box LLMs Automatically（TAP）— [arxiv.org/abs/2312.02119](https://arxiv.org/abs/2312.02119)（2023-12，NeurIPS 2024）
- Jailbreaking Black Box Large Language Models in Twenty Queries（PAIR）— [arxiv.org/abs/2310.08419](https://arxiv.org/abs/2310.08419)（2023-10，ICLR 2024）
- Identifying the Risks of LM Agents with an LM-Emulated Sandbox（ToolEmu）— [arxiv.org/abs/2309.15817](https://arxiv.org/abs/2309.15817)（2023-09，ICLR 2024）
- ToolSword: Unveiling Safety Issues of Large Language Models in Tool Learning Across Three Stages — [arxiv.org/abs/2402.10753](https://arxiv.org/abs/2402.10753)（2024-02，ACL 2024）
- LLM Agents can Autonomously Exploit One-day Vulnerabilities — [arxiv.org/abs/2404.08144](https://arxiv.org/abs/2404.08144)（2024-04）

### 2025-2026 最新（arXiv API 按时间核实标题）

- Boiling the Frog: A Multi-Turn Benchmark for Agentic Safety — [arxiv.org/abs/2605.22643](https://arxiv.org/abs/2605.22643)（2026-05）
- OpenSkillRisk: Benchmarking Agent Safety When Using Real-World Risky Third-Party Skills — [arxiv.org/abs/2607.20121](https://arxiv.org/abs/2607.20121)（2026-07）
- Bad Memory: Evaluating Prompt Injection Risks from Memory in Agentic Systems — [arxiv.org/abs/2607.14611](https://arxiv.org/abs/2607.14611)（2026-07）
- NetInjectBench: Benchmarking Indirect Prompt Injection in Tool-Using LLM Agents for Network Operations — [arxiv.org/abs/2607.10490](https://arxiv.org/abs/2607.10490)（2026-07）
- Security–Fidelity Tradeoffs: The Hidden Cost of Prompt Injection Defense — [arxiv.org/abs/2606.30783](https://arxiv.org/abs/2606.30783)（2026-06）

### 未能核实（谨慎引用）

- AEGIS: An Advanced LLM Safety Guard with Deep Semantic Understanding（NVIDIA，ACL 2024 Findings）【未核实：arXiv ID 未在本轮确认】
- LLM Evaluators Recognize and Favor Their Own Generations（2024）【未核实：疑似 arxiv.org/abs/2404.13076，凭记忆，请核对】
