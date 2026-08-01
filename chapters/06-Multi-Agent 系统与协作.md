# 第 6 章 · Multi-Agent 系统与协作

Multi-Agent 系统是 LLM 时代争议最大、也最考验 ROI 判断力的工程领域：一边是 Anthropic 多智能体研究系统内部评测 90.2% 的提升，一边是 Cognition"默认别建多智能体"的警告。本章主线是一个判据——**任务子部分之间是信息松耦合还是决策强耦合**——以及它的两个工程抓手：上下文工程（给每个 agent 恰好足够的上下文）与协调质量（任务书规格、输出契约、终止验证）。内容按 2026 年年中的时间线组织，涵盖编排模式、协议栈（MCP/A2A 的内部机制与 Linux Foundation 治理格局）、失败分类学（MAST）、评测基准（τ-bench 的 pass^k）与 harness/skills 等 2025–2026 新考点。

### 一、知识图谱

```
Multi-Agent 系统与协作
├── 1. 架构模式 (Orchestration Patterns)
│   ├── Pipeline / Sequential（流水线，含 MetaGPT 式 SOP assembly line）
│   ├── Orchestrator–Worker（中央编排 + 并行子智能体，Anthropic Research / OpenAI Deep Research 同款）
│   ├── Supervisor / Manager（路由式中央调度，LangGraph supervisor）
│   ├── Network / Swarm / Peer-to-Peer（去中心化，agent 互相 handoff）
│   ├── Hierarchical（多层 supervisor，manager of managers）
│   ├── Debate / Adversarial（多实例辩论求共识，Du et al. ICML 2024）
│   ├── Evaluator–Optimizer（生成者 + 评审者迭代回路）
│   └── Group Chat（会话式协作，AutoGen GroupChat）
├── 2. 角色与任务分工 (Role & Task Allocation)
│   ├── 角色定义三要素：role / goal / backstory（CrewAI 范式）
│   ├── 任务分配：静态 DAG vs 动态规划（orchestrator 实时拆任务）
│   ├── 能力路由与模型分级：Opus 编排 / Sonnet 执行 / Haiku 路由
│   └── SOP：把人类标准作业流程编码进协作流（MetaGPT）
├── 3. 通信机制 (Communication)
│   ├── 直接消息传递 (message passing) vs 黑板/消息池 (blackboard / message pool)
│   ├── 共享状态图 (shared graph state, LangGraph) vs Handoff 转交 (OpenAI Agents SDK)
│   ├── 两种子代理调用语义：agents-as-tools（编排者保留控制权）vs handoff（移交整个会话控制权）
│   ├── 结构化契约：子任务书（goal / 输出格式 / 工具约束 / 预算）
│   └── 互操作协议栈：MCP（agent↔工具，stdio/Streamable HTTP + OAuth 2.1）/ A2A（agent↔agent，Task 状态机 + Agent Card）/ ACP（历史，已并入 A2A）/ ANP / AGENTS.md
│       └── 治理格局：Linux Foundation 大伞——AAIF（2025-12，托管 MCP / AGENTS.md / goose 等）＋ A2A（2025-06 捐给 LF 的独立项目）
├── 4. 共享记忆 (Shared Memory)
│   ├── Working memory（上下文窗口内）vs 外部化记忆（artifacts / 文件 / KV store / 向量库）
│   ├── 共享 vs 隔离：context sharing（Cognition 主张）vs context isolation（Anthropic 实践）
│   ├── 压缩与检索：compaction / summarization / memory retrieval / clean-context 重启
│   └── Checkpoint 与可恢复状态（durable execution）
├── 5. 主流框架（2026 现状）
│   ├── AutoGen → Microsoft Agent Framework（AutoGen + Semantic Kernel 统一，2026-04 GA，AutoGen 进入 sunset）
│   ├── CrewAI（role-based Crews + event-driven Flows）
│   ├── MetaGPT（SOP 软件公司，message pool，executable feedback）
│   ├── LangGraph 1.0 稳定版（官方承诺 2.0 前无破坏性变更；stateful graph，supervisor/swarm，persistence，HITL）+ LangChain Deep Agents
│   ├── OpenAI Swarm → Agents SDK（agents/handoffs/guardrails/sessions）→ AgentKit（可视化 builder + eval）
│   └── 收敛趋势：Agent Harness 范式（Claude Code / Codex CLI）+ Anthropic Agent Skills（2025-10）+ Claude Agent SDK
├── 6. 协作 vs 竞争
│   ├── 合作：分工、汇总、互补
│   ├── 竞争/对抗：debate、红蓝对抗、verifier 博弈
│   └── 涌现行为 (emergent behavior)：未经显式编程的群体行为及其不可靠性（Generative Agents / Emergent Misalignment 等研究）
├── 7. 工程化难题
│   ├── 评估：小集合起步、LLM-as-judge、end-state 评估、人机共评、过程指标；基准：τ-bench(pass^k) / GAIA / AgentBench / SWE-bench
│   ├── 调试：非确定性、级联失败、责任弥散、trace/observability（OTel GenAI semconv + LangSmith/Langfuse/Arize Phoenix；MOSAIC, CHI 2026 EA）
│   ├── 失败分类学：MAST（Cemri et al. 2025，14 种失败模式 × 三大类）
│   ├── 可靠性：retry、checkpoint 恢复、工具健康信号、幂等性、rainbow deployment
│   ├── 成本：multi-agent ≈ 15× 单聊 token，ROI 约束、难度自适应路由与模型级联
│   └── 安全与治理：agent 间提示注入、权限边界（OBO 委托凭证）、guardrails、HITL 确认门、审计日志、OWASP 对齐
└── 8. 学科纵深
    ├── 学术谱系：Contract Net Protocol（Smith 1980）/ 黑板系统（Hearsay-II）/ BDI / FIPA-ACL
    └── 通信拓扑与复杂度：星型 O(n) vs 全连接 O(n²)；规模正向实证（《More Agents Is All You Need》, 2024）及其边界
```

---

### 二、核心概念精讲

#### 2.1 第一性原理：到底该不该用 Multi-Agent？

这是本域最重要的判断，也是面试最爱考的"价值观题"。业界在 2025 年 6 月有过一场著名论战：

- **Cognition（Devin 团队）** 在 [《Don't Build Multi-Agents》](https://cognition.com/blog/dont-build-multi-agents)（2025-06-03）中主张：默认用**单线程、连续上下文的单 agent**。两条原则：① **Share context**——要传就传完整执行轨迹，而不是孤立消息；② **Actions carry implicit decisions**——每个动作都内嵌了一组假设（命名风格、数据结构选型、交互设计），并行的子 agent 会各自做出**互相冲突的隐式决策**（decision coupling），最后汇总时得到的是无法调和的"半成品拼盘"。
- **Anthropic** 约两周半后发布 [《How we built our multi-agent research system》](https://www.anthropic.com/engineering/multi-agent-research-system)（2025-06-20），用生产数据证明：对**可并行、高价值、超出单上下文**的任务，orchestrator-worker 架构下 Opus 4 主导 + Sonnet 4 worker 的组合，在内部评测中比单个 Opus 4 高出 **90.2%**。代价是 token 消耗约为普通聊天的 **15×**（单 agent 工具调用约 4×）。

两者其实不矛盾，可以用一个判据统一：

> **任务的子部分之间是"信息松耦合"还是"决策强耦合"？**
> - 松耦合（多角度检索、并行调研、各自独立的代码审查维度）→ multi-agent 收益大；
> - 强耦合（改一个函数牵动全仓库的实现决策）→ 单 agent + 长上下文更可靠。

**常见误区**：把 multi-agent 当作"提升智能"的手段。它本质是**上下文与注意力的分治（divide-and-conquer over context）+ 并行化**，不是推理能力的免费午餐。Anthropic 明确提示：只有当任务"值得花这个钱、可拆分、单上下文装不下"时才上多智能体。

值得注意的是论战的后续：Cognition 在 [《Multi-Agents: What's Actually Working》](https://cognition.com/blog/multi-agents-working)（2026-04）中承认，在两条硬纪律——**写操作保持单线程（writes stay single-threaded）**、**辅助 agent 只提供智能而不执行动作（helpers provide intelligence, not actions）**——之下，**只读/评审/MapReduce 类**多智能体场景已在生产中跑通。注意这是比"全面转向"窄得多的口径：多 agent 并发写仍然不被推荐，与其一贯立场一致。这说明两派的真正分歧不是"要不要多智能体"，而是**协调成本是否被工程手段压到低于分治收益**。

#### 2.2 编排模式分类：从 workflow 到 autonomous agent

Anthropic [Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)（2024-12）给出了至今最被广泛引用的分类法。先区分两个概念：

- **Workflow**：由**代码**决定模型调用与工具使用的顺序和逻辑（确定性拓扑）；
- **Agent**：由**模型**自主决定下一步动作与路径（LLM 驱动的动态控制流）。

五种 workflow 模式（可与 agent 组合）：

| 模式 | 结构 | 适用 | 关键代价 |
|---|---|---|---|
| Prompt Chaining | 固定串行多步，中间可加 gate 校验 | 可清晰分阶段的固定流程 | 延迟线性增长 |
| Routing | 分类后分发到专用 prompt/模型 | 输入类型多样、各类需不同处理 | 路由器错误会整体失配 |
| Parallelization | Sectioning（切分子任务）/ Voting（同任务多次） | 独立子任务、需要多视角 | 成本 ×N |
| **Orchestrator–Workers** | 中央 LLM 动态拆任务→并行 worker→合并 | 子任务**事先无法预知**的开放任务 | 编排质量决定全局；成本高 |
| Evaluator–Optimizer | 生成者产出→评估者反馈→迭代 | 有明确评估标准、迭代能提升质量 | 容易陷入无效循环 |

**Orchestrator–Worker vs Supervisor 的微妙区别**（高频追问）：Supervisor 更偏"静态路由器"——agent 集合固定，supervisor 决定"下一步谁上"，所有通信经中央中继；Orchestrator 更偏"动态规划器"——按 query 实时生成子任务书（task spec），worker 数量和内容随任务变化。工程上 LangGraph 的 `supervisor` 库是前者，Anthropic Research 的 lead agent 是后者。还有一个常被混淆的对比维度：**agents-as-tools**（worker 作为工具被调用，控制权始终在编排者手里，适合"取数"型子任务）vs **handoff**（整个会话控制权移交给对方，适合"分诊转接"型场景，如客服转专业坐席）。

**反直觉点**：Anthropic 发现编排质量几乎完全取决于**lead agent 的委派（delegation）prompt**——必须给 worker 写清：任务目标、期望输出格式、可用工具及使用指引、边界约束（如 token/搜索次数预算）。很多人以为多放几个 agent 就能变强，实际上"委派说明书"写得含糊，worker 越多噪声越大。配套实践是**模型分级**：规划用最强模型（Opus 级），执行用中等模型（Sonnet 级），前置路由/分类用最便宜模型（Haiku 级），把"智能预算"花在编排决策这个全局瓶颈上。

#### 2.3 深度案例：Anthropic 多智能体 Research 系统

这是目前公开资料最详实的生产级 multi-agent 系统，值得逐条掌握：

**架构**：Lead agent（Opus）接收问题 → 用 extended thinking 生成研究计划 → 并行 spawn 多个 worker（Sonnet，各自独立上下文）执行搜索与阅读 → worker 返回压缩后的 findings → lead 判断是否需要补充研究 → 合并 → citation reviewer 校验引用 → 输出。

**关键工程经验**：
1. **上下文隔离是特性不是缺陷**：worker 的独立 context 让它们能并行深度推理，互不污染；代价是必须设计好"信息回传协议"（压缩摘要 + 外部 artifact 文件，而非把原文塞回对话）。
2. **Context engineering**：长任务会撑爆上下文。对策——lead 把计划持久化；worker 为已完成阶段写摘要；必要时从存档中**启动全新 clean context 的 subagent**；中间结果落盘为文件引用（artifacts），避免大段文本在对话里搬运。（Anthropic 另有专文 [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)（2025-09）系统阐述 compaction、structured note-taking、sub-agent 架构。）
3. **可靠性工程**：agent 跨数十步保持状态，小错会级联。对策——自动重试、定时 checkpoint、从失败点断点续跑、给 agent 传递"工具不健康"信号让它换策略、用 **rainbow deployment**（新旧版本并行，老会话跑在老版本）避免升级打断正在进行的长任务。
4. **评估**：从约 20 条真实 prompt 的小集合起步（早期改动效应大）；自由文本用**单一打分 prompt 的 LLM-as-judge**（最稳定），维度含事实性、引用支持度、覆盖度、信源权威性、工具使用效率；但**人工评审不可替代**——能抓出 judge 漏掉的怪诞幻觉和信源偏见。对会修改外部状态的系统，评估**终态/checkpoint 态**而不是逐步评估。
5. **调试**：同一输入会有多条都算"正确"的路径，失败难以复现；必须做全链路 tracing（记录决策与协调模式，但脱敏用户数据）。同步执行 worker 易于控制但阻塞；异步提速但结果一致性和错误处理更复杂。
6. **两个容易被引用的细节**：① 系统效果与消耗的 token/工具调用数强相关——"更贵的跑法"确实更准，所以必须给预算上限做成本护栏；② 工具描述本身就是 prompt，Anthropic 用真实 query 反复迭代工具文档（包括给 worker 的"搜索策略指引"），其收益不亚于改模型。

#### Harness 级 subagent 机制：以 Claude Code 的 Task/subagent 为例

**考点**：面试官追问"orchestrator-worker 落到生产 harness 里长什么样"，能拆出 Claude Code Task 工具（subagent 机制）的四条工程约束即是高分答案：
1. **双重隔离**：每个 subagent 拥有独立上下文窗口 + 独立工具白名单——主线程历史不带入，工具按最小权限声明（如只读探索型 agent 不给 Edit/Bash 写权限），一次同时实现上下文隔离与权限收敛。
2. **禁止嵌套 spawn**：subagent 不能再派 subagent，拓扑被硬性限定为一层星型，防止递归扇出失控——成本上界 = 子代理数 × 单代理预算，可静态估算；这是"用 harness 规则替代 prompt 恳求"的典型。
3. **结构化回传**：子代理只把最终结论以 tool result 形式回传主线程，中间几十步搜索/读文件的过程全部丢弃——天然的上下文压缩，正对应上文"回传压缩摘要而非原文"。
4. **类型化 agent 定义**：子代理不是临时拼的 prompt，而是配置文件声明的类型（tools 白名单 / model / system prompt），可版本化、可复用——"agent 即配置"。

并行 fan-out 时，每份派发的任务书必须写清目标、期望输出 schema、预算上限（步数/token），与本章反复出现的"子任务书契约"（2.2 与题 8）互为印证：框架层的 delegation prompt 原则，落到 harness 层就是这几个必填字段。**追问怎么答**："何时不该用 subagent？"——需要频繁双向澄清的强耦合子任务：回传只有结论没有过程，来回澄清的成本会吃掉隔离收益（此时 Skills 的渐进披露是更轻的替代，见 2.7）。

#### 2.4 Debate 模式：原理与"祛魅"

[Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate"](https://arxiv.org/abs/2305.14325)（MIT/Google Brain，ICML 2024，数千次引用）：多个 LLM 实例各自给出答案与推理，多轮互相看到对方的论点并修订，最终收敛为共识。在小学数学、国际象棋走法、事实性 QA 上超过单 agent CoT，且对较弱模型提升更明显（强模型上边际收益收窄）。

**为何（有时）有效**：辩论相当于把 self-consistency 的"独立采样投票"升级成"带信息的迭代修订"，错误推理暴露在对抗性审视下更容易被攻破。

**为何常常失效**（这是面试加分点，很多人只知道论文结论）：
- [Smit et al., "Should we be going MAD?"](https://arxiv.org/abs/2311.17371)（InstaDeep，ICML 2024，用 GPT-4 与 Mixtral 8x7B 系统评估多种辩论策略）发现：MAD 的收益高度依赖任务与模型，很多场景打不过 self-consistency 甚至单 agent 多次细化，且成本是 N agents × M rounds；2025 年的后续实证研究《[If Multi-Agent Debate is the Answer, What is the Question?](https://arxiv.org/abs/2502.08788)》（arXiv:2502.08788，2025-02）进一步指出：一些评测中辩论的"提升"其实来自**多轮生成预算**本身，而非"辩论"这个形式；
- **锚定与谄媚（anchoring & sycophancy）**：LLM 一旦被初始答案"建立信心"，后续轮次很难真正改弦更张，反而向多数派/强势措辞收敛——辩论退化为"从众"；
- 同质模型会**互相带偏**（shared blind spots），准确率反而下降。
- 实践建议：与其让 agent 自由辩论，不如用**结构化对抗**（指定 devil's advocate 角色 + 强制举证 + 独立裁判），或干脆用 evaluator-optimizer 回路；把辩论预算只花在高风险、可验证的判断上。

#### 2.5 通信机制与互操作协议栈

**进程内通信的三种范式**：
1. **Message passing（对话式）**：AutoGen 的 conversable agents 互发消息，协调逻辑隐含在对话里。灵活但难以审计"到底决定了什么"。
2. **Blackboard / Message pool（共享黑板）**：MetaGPT 的共享消息池，agent 发布结构化产物、按需订阅（subscription），减少点对点广播的噪声。
3. **Shared state（共享状态图）**：LangGraph 把全局 state 作为单一事实源，节点通过读写 state 间接通信，天然支持 checkpoint、time-travel 调试与并行。

**跨系统互操作协议**（2025 年形成、2025 年底归于 Linux Foundation 大伞下的格局，[arXiv:2505.02279](https://arxiv.org/abs/2505.02279) 有系统综述）：

| 协议 | 提出方 | 层次 | 解决的问题 |
|---|---|---|---|
| **MCP** (Model Context Protocol) | Anthropic（2024-11；OpenAI、Google 相继采纳，2025-12 捐给 Linux Foundation，由 AAIF 托管） | agent ↔ 工具/数据 | 标准化工具调用、资源与 prompt 供给，已成事实标准 |
| **A2A** (Agent2Agent) | Google（2025-04 发布，2025-06 捐给 Linux Foundation 作为独立 LF 项目；捐赠时 100+ 组织支持、AWS/Cisco 新加入背书，2026 年 v1.0 时增至 150+） | agent ↔ agent | 跨厂商/跨框架的 agent 发现（Agent Card）、任务委派与状态管理（Task/Message/Artifact） |
| **ACP**（历史协议） | IBM（BeeAI）；2025 年已并入 A2A / Linux Foundation 生态 | 组织内 agent 协调 | REST-first、local-first 的企业内多 agent 编排；作为协议演进脉络了解即可，选型时不再单列 |
| **ANP** | 社区 | 开放网络 | 去中心化的互联网级 agent 发现与通信（基于 DID/W3C 身份） |
| **AGENTS.md** | OpenAI（2025-12 捐给 Linux Foundation，由 AAIF 托管） | agent ↔ 代码仓库 | 约定仓库级的 agent 上下文（构建/测试/风格规范），事实上的工程惯例 |

2025 年 12 月，Linux Foundation 成立 [**Agentic AI Foundation (AAIF)**](https://aaif.io/)：创始捐赠方为 Anthropic、Block、OpenAI（分别捐入 MCP、goose、AGENTS.md），白金成员含 AWS、Google、Microsoft、Cloudflare、Bloomberg 等。注意治理结构的区分：**AAIF 托管的项目是 MCP、AGENTS.md、goose（后续 agentgateway 等也加入），A2A 并不在其中**——A2A 早在 2025-06 就捐给了 Linux Foundation，作为独立 LF 项目运作。准确表述是"三大协议同归 Linux Foundation 大伞下（MCP、AGENTS.md 具体由 AAIF 治理），形成分层互补格局"——面试中说出"同伞、不同治理"这个区分，才展示了对时间线的真正掌握。

**一句话记忆**：MCP 让 agent "会用工具"，A2A 让 agent "会找同事"；二者互补不竞争。面试中若被问"MCP 能不能用于 agent 间通信"，应答：MCP 的语义是"客户端调用服务端的工具/资源"，是主从关系；A2A 的语义是"对等 agent 间委派任务并跟踪生命周期（Task/Message/Artifact）"，两者抽象层次不同。把远端 agent 包成 MCP server 技术上可行，但会丢掉对等协商、能力自描述与长任务状态机。

**协议内部机制（面试深问层，2026 现状）**：只讲定位口号不够，资深面试官会下探到机制层。

MCP 侧（客户端–服务端，JSON-RPC 2.0）：
- **传输**：stdio（本地子进程，最常见）与 **Streamable HTTP**（远程部署；2025-03-26 规范起取代已弃用的 HTTP+SSE）。
- **规范演进时间线**（freshness 考点）：2024-11-05 首发 → 2025-03-26 Streamable HTTP → 2025-06-18（OAuth 2.1 授权模型、elicitation 人机确认、outputSchema 结构化工具输出、移除 JSON-RPC batching）→ 2025-11-25（experimental async **Tasks** 长任务、M2M 机器间认证、Cross App Access；JSON Schema 2020-12 成为默认方言）→ 2026-07-28（正式**弃用** Roots / Sampling / 协议级 Logging，协议向更无状态、会话可选的方向收敛）。官方 **Registry** 于 2025-09 上线，统一 server 注册与发现。
- **授权要点**：2025-06-18 规范把受保护的 MCP Server 定性为 OAuth 2.1 **Resource Server**——server 不得为自己签发 token；授权服务器（AS）可与 server 同址部署也可独立，client 经 RFC 9728（Protected Resource Metadata）发现 AS、用 RFC 8707 resource 参数绑定 token 受众，server 必须做受众校验——堵死恶意 server 诱导 client 交出/透传 token 的攻击面。
- **elicitation**：server 执行中可主动向用户请求补充信息或确认（如破坏性操作前的确认弹窗），是人机协同的协议级原语。

A2A 侧（对等委派）：
- **Agent Card**：能力自描述文档，字段含 name/description/url、skills 列表（每个 skill 有 id/description/tags）、capabilities（streaming、pushNotifications 等）、authentication schemes 与协议版本，是跨组织发现的入口。
- **Task 状态机**：`submitted → working → (input-required ↔ working，向用户/客户端补充索取信息) → completed / failed / canceled`（另有 auth-required 等状态）。长任务以 Task ID 跟踪，进度经 **push notification**（webhook 回调）推送。
- **v1.0（2026）**：引入**签名 Agent Card**（防发现阶段的篡改与冒充）与更完整的企业级鉴权能力。

最后一个高频误区：**MCP 只标准化互操作，不是安全边界**——沙箱、权限、工具描述校验都是应用层责任（详见 §2.10 与第 10 章）。

#### 2.6 共享记忆与 Context Engineering

多智能体记忆设计的核心张力是 **共享 vs 隔离**：

- **全共享**（所有 agent 看同一份完整轨迹）：一致性最好，但上下文爆炸、注意力稀释、成本失控——这正是 Cognition 批评多智能体的立足点，也是他们宁可用单 agent + summarizer 压缩的原因。
- **全隔离**（每个 worker 只看自己的任务书）：并行性好、上下文干净，但损失全局一致性，隐式决策冲突。
- **工程上的折中**（主流做法）：
  1. **分层记忆**：orchestrator 持有全局计划与进度（working memory），worker 只拿到任务切片；
  2. **外部化存储**：中间产物写入 artifact/文件系统/向量库，需要时按需检索，而非塞进 prompt；
  3. **结构化回传**：worker 返回带元数据的压缩 findings（结论 + 证据 + 置信度 + 引用），而非原始 dump；
  4. **长期记忆**：episodic memory（历史任务经验）与 semantic memory（领域知识）分离，跨会话持久化（如 LangGraph Store、Mem0 等），并做**命名空间隔离与权限控制**，防止 agent 互相污染记忆；
  5. **可恢复性**：所有共享状态可 checkpoint、可回放（durable execution），失败不必从零重跑。

一个贯穿性的视角：Cognition 的"share full trace"与 Anthropic 的"结构化压缩 + artifact"本质是**同一门 context engineering 在单/多智能体下的两种实现**——目标都是在每一步给每一个 agent 恰好足够、不多不少的上下文。

#### 2.7 主流框架对比（2026 现状）

| 框架 | 核心抽象 | 协作模型 | 优势 | 短板 |
|---|---|---|---|---|
| **AutoGen → Microsoft Agent Framework** | Conversable agent + 事件驱动运行时（v0.4 起全面 async/event-driven）；2025-10 与 Semantic Kernel 统一为 [Microsoft Agent Framework](https://devblogs.microsoft.com/agent-framework/)，2026-04 GA 1.0，AutoGen/SK 进入 sunset（官方提供迁移指南） | GroupChat 会话式协作；Magentic-One 为旗舰通用系统 | 灵活的对话拓扑、代码执行沙箱、微软生态与企业支持 | 对话即控制流，生产可控性与可审计性较弱；生态迁移期文档碎片化 |
| **CrewAI** | Agent(role/goal/backstory) + Task + Crew；Flows 做事件驱动编排 | Sequential / Hierarchical process | 上手最快、角色隐喻贴合业务、内置流程 | 深度定制控制流不如图式框架 |
| **MetaGPT** | SOP + 角色（PM/Architect/Engineer/QA）+ 共享 message pool | Assembly line 流水线；**executable feedback**（跑代码/测试拿真实反馈，论文报告 HumanEval/MBPP Pass@1 约 85.9%/87.7%，消融实验显示移除 executable feedback 后有数个百分点下降） | 把人类工程流程编码、结构化产物约束 | 场景较聚焦于软件开发 |
| **LangGraph** | Stateful graph（nodes/edges/conditional routing）+ checkpointer；[1.0 稳定版](https://www.langchain.com/blog/langchain-langgraph-1dot0)（2025-10，官方承诺 2.0 之前无破坏性变更）+ LangChain `create_agent` + Deep Agents 预置深度 agent 模式 | supervisor / swarm / 任意自定义拓扑 | 显式控制流、durable execution、HITL 断点、可观测性最佳 | 概念曲线陡、样板代码多 |
| **OpenAI Swarm → Agents SDK → AgentKit** | Agent + Handoff + Guardrails + Sessions（[Agents SDK](https://openai.com/index/new-tools-for-building-agents/) 2025-03 发布）；DevDay 2025 推出 AgentKit（可视化 builder、ChatKit、evals） | 去中心化转交 + agents-as-tools | 极简、handoff 即工具调用、内置护栏与会话状态、与 OpenAI 工具链集成 | 深度绑定 OpenAI 生态（SDK 本身支持任意模型） |

**选型心法**：需要**确定性 + 可观测 + 可恢复** → LangGraph；需要**快速搭角色协作 demo / 业务流程自动化** → CrewAI；微软生态与企业级会话式协作 → Microsoft Agent Framework（承接 AutoGen）；OpenAI 全家桶内快速产品化 → Agents SDK/AgentKit；做**软件生成流水线** → MetaGPT 思路。框架只是壳，决定成败的是 prompt、工具设计与评估体系——Anthropic 反复强调"能用简单可组合模式就别上重框架"。

**2025H2–2026 的收敛趋势：harness + skills（进阶加分）**：框架选型之外，行业明显收敛出 **Agent Harness** 范式（Claude Code、Codex CLI、Cursor 等通用执行外壳：循环 + 工具 + 上下文管理 + 权限系统），能力复用的封装形态也随之变轻——**Anthropic Agent Skills**（2025-10）把领域知识、脚本与资源打包成文件夹，按需**渐进披露**（先看元数据、再载入指令、最后按需读资源），避免系统提示词膨胀，也替代了"为每个子领域 spawn 一个 subagent"的重做法；**Claude Agent SDK**（2025-09 由 Claude Code SDK 更名）则把这套 harness 的子代理、权限模式与 hooks 机制产品化。面试启示：框架提供控制流原语、harness 提供生产就绪的执行外壳，二者可以组合（如在 LangGraph 节点中驱动一个 harness），"框架 vs harness 的分工"正在成为新的选型题。

#### 2.8 涌现行为与协作动力学

LLM-based MAS 会表现出未经显式编程的群体行为（系统综述见 [Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)，2025-01）。这类现象有清晰的研究脉络：[Generative Agents](https://arxiv.org/abs/2304.03442)（Park et al., UIST 2023）在 25 个智能体的虚拟小镇中观察到规范传播与涌现社交行为；2025 年的 Emergent Misalignment 研究（Betley et al.）则显示，在窄任务上做对抗性微调的 agent 会在广泛场景中表现出价值失调与"欺骗性迎合"倾向。（引用须知：该研究的原对象是**单模型**窄域微调引发广域失调，把它引入 MAS 语境属类比外推——面试引用需说明这一层，否则会被追问原研究与多智能体的关系。）Anthropic 的工程观察更务实：**对 lead agent prompt 的微小改动会在群体中层联放大**，出现难以预料的协调模式。结论不是"涌现很神奇"，而是**涌现 = 不可靠性的来源**，必须用评估与护栏（guardrails）约束，而不是期待它。

**失败归因的实证锚点**：本领域最标准的实证研究是 Cemri et al.（UC Berkeley）的 [《Why Do Multi-Agent LLM Systems Fail?》](https://arxiv.org/abs/2503.13657)（2025，即 **MAST**，数百次引用）。它基于 1600+ 条标注轨迹提出多智能体失败分类学：**14 种失败模式归为三大类——规格与系统设计（约 43%，原文 42.8%）、跨 agent 失配（约 32%，原文 32.4%）、任务验证与终止（约 25%，原文 24.9%）**，并给出 LLM-as-judge 自动归因管线。其核心结论与上段互为印证：**多数失败源于协调层的设计缺陷（规格含糊、缺乏验证、agent 间目标错位），而非基座模型能力不足**（2026 年的预印本 [arXiv:2605.03310](https://arxiv.org/abs/2605.03310) 给出同向判断）。这直接决定了工程重心的摆放：与其换更强模型，不如把预算投给任务书规格、输出契约与终止验证。

#### 2.9 多智能体调试为何是地狱难度

1. **非确定性**：同一输入多条合理路径，bug 难复现；
2. **级联失败**：上游 worker 的轻微偏移被下游放大；
3. **责任弥散**：错误无法归因到单一组件（是编排拆错了？worker 搜错了？合并丢信息了？）——MAST 的三大类失败模式（§2.8）正好作为归因清单：先判断属于规格/系统设计、跨 agent 失配、还是任务验证与终止哪一类，再下钻到 14 种具体模式；
4. **传统单测失效**：需要 trace 级 observability（每次决策、每次工具调用、每次 handoff 的输入输出全记录，如 [MOSAIC](https://dl.acm.org/doi/10.1145/3772363.3798830)（CHI 2026 Extended Abstracts）这类从单次调用→agent 交互→系统整体分层观察与评估的框架思路），配合回放（replay from checkpoint）与离线 eval 回归；
5. **落地工具链**：埋点标准用 [OpenTelemetry GenAI 语义约定](https://opentelemetry.io/docs/specs/semconv/gen-ai/)（2025–2026 行业事实标准，定义 agent/tool 的 span 属性与事件；注意 agentic 相关属性仍处于 development 稳定性，命名可能变）；平台侧 LangSmith / Langfuse / Arize Phoenix / Braintrust 均提供 trace→replay→eval 回归闭环；把每次失败 trace 按 MAST 模式归类标注，还能积累"哪类协调缺陷最常发生"的分布数据，反哺系统设计。

#### 2.10 安全、治理与 Human-in-the-Loop

多智能体的攻击面是单 agent 攻击面的**乘积**：每新增一个 agent、一条通信链路、一个共享存储，都多出一条信任边界。

- **agent 间提示注入**：恶意内容可藏在 A2A 消息、工具返回结果、共享记忆甚至上游 worker 的输出里，劫持下游 agent。对策：把所有外部/跨 agent 内容当作**不可信数据**而非指令；对关键指令做来源标记与二次确认。
- **权限边界**：遵循最小权限——每个 agent 只持有其任务书允许的工具白名单；handoff 时**不默认继承全部权限**；敏感工具（写库、付款、删数据）单独设防。代表用户操作时使用**委托凭证 / OBO（on-behalf-of）短时效 token**，避免用户 token 在 agent 间共享；威胁清单可对照 OWASP Top 10 for LLM Applications 的 agentic 威胁项与官方《Agentic AI Threats and Mitigations》。
- **Guardrails**：输入护栏（意图分类、注入检测）+ 输出护栏（schema 校验、PII/合规过滤、claim-citation 对齐），可用 Agents SDK guardrails、NeMo Guardrails、Llama Guard 等实现，并与主流程**并行执行、可熔断**。
- **HITL 确认门**：对不可逆动作（删数据、付款、发布）强制人工确认——这是生产事故复盘反复指向的最高杠杆安全机制（Anthropic 等厂商在敏感工具上的确认门实践、LangGraph interrupt 等框架原语皆服务于此）。注意不要把 τ-bench 类基准当作 HITL 的论据：τ-bench 论证的是**终态正确性评估**（含数据库终态与 pass^k），并不研究 HITL 本身。同时设计清晰的升级（escalation）阈值，避免"事事请示"或"从不请示"两个极端。
- **审计与 AgentOps**：全链路不可篡改的审计日志（谁、在什么上下文、调了什么工具、改了什么状态），是事故定责与合规的前提。

#### 2.11 评测基准与可靠性度量

多智能体评估的难度超出单模型评估三层（见题 9）：过程非确定、交互质量难量化、终态正确性优先。主流基准谱系：

| 基准 | 测什么 | 与多智能体的关系 |
|---|---|---|
| **[τ-bench](https://arxiv.org/abs/2406.12045) / τ²-bench**（Sierra） | 工具型对话任务 + **数据库终态正确性**；τ² 增加双控（用户侧也是会用工具的 agent）与 telecom 域 | 提出 **pass^k** 指标，成为客服型 agent 的可靠性行业标准 |
| **GAIA**（Mialon et al., ICLR 2024） | 通用助理的多步工具使用 | 人类约 92%，截至 2026 年中榜首系统已达 80% 上下，差距进一步收窄但尚未闭合；多智能体系统常以此作辅助赛道 |
| **AgentBench**（ICLR 2024） | 操作系统/数据库/知识图谱/卡牌游戏等 8 类环境交叉 | 考察异构环境下的编排与泛化 |
| **SWE-bench 系列**（Verified 为人工去污染子集） | 真实仓库 issue 修复 | 多智能体编码流水线（orchestrator + 多 engineer worker + 测试回路）是冲榜常见路线之一 |

**pass^k vs pass@k**（高频计算题）：pass@k 度量"k 次里至少对一次"（鼓励"碰运气能做"）；pass^k 度量"k 次**全部**成功"（刻画**策略可靠性**）。设单轮通过率 pass^1 = 70%，则 pass^4 ≈ 0.7⁴ ≈ 24%，pass^8 ≈ 0.7⁸ ≈ 6%——一个"看起来挺可靠"的系统，在生产级一致性口径下会塌到个位数。多智能体放大每一步的方差，所以发布门槛应定在 **pass^k** 而非 pass@k。注意该乘积估算假设各次试验独立；真实 agent 的错误常级联相关，实际曲线必须用 eval 实测。

#### 2.12 学术谱系与通信拓扑（学科纵深）

MAS 的历史根基比 LLM 早四十余年，面试中的"学科纵深"题常出于此：

- **Contract Net Protocol**（Smith, 1980）：管理者发布任务公告 → 承包者投标 → 授标执行。这是"orchestrator–worker"最早的形式化范式，今天的 A2A 任务委派、FIPA-ACL 的 request/inform 言语行为都能追溯到它。
- **黑板系统**（Hearsay-II，1970s）：多个知识源异步读写一块共享黑板协同解题——MetaGPT 的 message pool 与 LangGraph 的共享状态图是它的直系后代。
- **BDI 架构**（Belief–Desire–Intention）：对 agent 内部状态的形式化建模；CrewAI 式角色卡（role/goal/backstory）可视为 BDI 的工程化简化。

**通信复杂度与拓扑**：星型拓扑（中央 supervisor 中继）消息开销 O(n)，全连接 O(n²)；supervisor 还带来"电话传话"式信息损耗（LangChain 实测，见易错点 #7）。规模的正向实证：[《More Agents Is All You Need》](https://arxiv.org/abs/2402.05120)（Li et al., 2024）表明，仅靠"多 agent 采样 + 投票"（sampling-and-voting）就能随 agent 数量提升性能，弱模型与难任务上增益更大——这本质是 self-consistency 的空间化扩展，与 §2.4 的 debate 反方研究构成完整正反对照：**"更多 agent"的收益主要来自采样预算与多样性，而非"辩论/协商"这个形式本身**，且成本随 agent 数线性增长、边际递减。

一句话记忆：LLM 多智能体是经典 MAS 的"旧酒新瓶"——合同网、黑板、BDI 都有直接对应物；差别在于 LLM 让"角色"与"协议"变得柔软可编程。

---

### 三、面试高频考点

| 考点 | 高频度 | 考察意图 |
|---|---|---|
| 何时该用 multi-agent vs 单 agent（含 token/成本论证） | ⭐⭐⭐ | 架构判断力，是否盲从潮流 |
| Orchestrator–Worker 的原理、prompt 设计与 Anthropic Research 案例 | ⭐⭐⭐ | 是否读过一手工程资料 |
| MCP 与 A2A 的区别与互补关系（含 LF/AAIF 治理格局的准确区分） | ⭐⭐⭐ | 协议栈理解（2025-2026 必问） |
| 五大 workflow 模式的区分（尤其 routing vs orchestrator vs evaluator-optimizer） | ⭐⭐⭐ | 概念清晰度 |
| LangGraph supervisor vs swarm；handoff vs agents-as-tools | ⭐⭐ | 框架实操 |
| 协议内部机制：MCP 传输/OAuth/elicitation 与规范演进；A2A Task 状态机与 Agent Card | ⭐⭐ | 协议题下探深度（2026） |
| 多智能体记忆设计：共享 vs 隔离的取舍 | ⭐⭐ | 上下文工程功底 |
| Multi-agent debate 的原理与局限（谄媚/锚定/成本） | ⭐⭐ | 论文阅读深度 |
| 多智能体系统的评估方法（LLM-as-judge、end-state 评估、pass^k vs pass@k） | ⭐⭐ | 工程闭环意识 |
| 调试与可观测性：trace、checkpoint、级联失败归因、OTel GenAI 工具链 | ⭐⭐ | 生产经验 |
| 安全治理：agent 间注入、权限边界、guardrails、HITL | ⭐⭐ | 生产级风险意识 |
| Cognition vs Anthropic 之争的看法（开放题） | ⭐⭐ | 思辨与知识面广度 |
| 系统设计：Deep Research / 多智能体客服 / 代码生成流水线 | ⭐⭐⭐ | 综合设计能力 |
| MetaGPT 的 SOP 与 executable feedback 思想 | ⭐ | 论文功底 |
| 失败分类学 MAST 与分层归因 | ⭐ | 学术纵深与调试方法论 |
| MAS 学术谱系（Contract Net/黑板/BDI）与通信拓扑复杂度 | ⭐ | 学科纵深 |

---

### 四、经典面试题与参考答案

#### 题 1（基础 ⭐⭐⭐）：什么情况下应该从单 agent 升级到 multi-agent？升级的代价是什么？

**答题思路**：先给判据，再给反例，最后量化代价，体现"克制"的工程价值观。

**参考答案要点**：
- 升级信号：① 任务**可分解为信息松耦合的子任务**（并行调研、多维度审查）；② 单一上下文**装不下**所需信息（长流程、多文档）；③ 需要**异构能力组合**（不同工具集/专长/模型档位）；④ 单 agent 在长上下文中出现注意力退化、指令遵循下降。
- 不升级信号：子任务**决策强耦合**（一个实现决定牵动全局，如重构单一代码库）——Cognition 的 decision coupling 论点；任务价值撑不起成本；低延迟交互场景。
- 代价量化：multi-agent token 消耗约为普通聊天的 **15×**（单 agent 工具调用约 4×）；延迟、调试复杂度、协调开销、一致性风险全部上升。
- 收尾：Anthropic 的建议是"从单次增强调用起步，只在简单模式失效后加协调"；Cognition 在 2026-04 的后续文章中承认跑通的也只是**只读/评审/MapReduce 类**场景（前提是写操作保持单线程、辅助 agent 只提供智能不执行动作）——双方共识落在 ROI 与任务耦合度上，而非信仰上。

#### 题 2（进阶 ⭐⭐⭐）：请讲解 Orchestrator–Worker 模式，并结合 Anthropic Research 系统说明工程要点。

**答题思路**：结构 = 架构图解 + 为什么有效 + 工程难点清单。

**参考答案要点**：
- 结构：lead agent 接收开放问题 → 动态规划拆解 → 并行 spawn 独立上下文的 worker → worker 搜索/分析并返回压缩 findings → lead 迭代判断是否补充 → 合并 → 后处理（引用校验）。同构案例还有 OpenAI Deep Research（RL 训练单模型内化"编排+浏览"循环）与 Claude Code 的 Task sub-agent。
- 为什么有效：开放研究的子问题**事先不可枚举**（区别于固定 DAG）；worker 上下文隔离换来并行深度推理与更广覆盖；内部评测 Opus 主导 + Sonnet worker 比单 Opus 高 90.2%，且对"线索多且互不相关"的问题收益最大。
- 工程要点（背诵级）：① lead 的委派 prompt 必须含目标/输出格式/工具指引/预算边界；② 资源随任务难度伸缩（简单问题少开 worker）；③ 模型分级（强模型编排、中等模型执行、小模型路由）；④ 长任务用计划持久化 + 阶段摘要 + clean-context 重启 + 外部 artifact；⑤ 可靠性靠 retry、checkpoint 断点续跑、工具健康信号、rainbow deployment；⑥ 评估从 ~20 条真实 query 起步，LLM-as-judge 单打分 prompt + 人工兜底；⑦ 工具描述本身当 prompt 迭代。

#### 题 3（进阶 ⭐⭐⭐）：MCP 和 A2A 有什么区别？能互相替代吗？

**答题思路**：分层定位 + 语义差异 + 机制细节 + 结论"互补"+ 最新治理格局。

**参考答案要点**：
- MCP（Anthropic，2024-11）解决 **agent ↔ 工具/数据源**：标准化工具定义、调用、资源与 prompt 供给，是**主从式**（client-server）关系，已被 OpenAI、Google 等采纳，成为事实标准。
- A2A（Google，2025-04）解决 **agent ↔ agent**：通过 Agent Card 做能力发现，用 Task/Message/Artifact 建模**对等委派与长任务生命周期**（Task 状态机：submitted → working → input-required ↔ working → completed/failed/canceled），支持跨厂商跨框架互操作。
- 治理现状（加分项，注意区分）：A2A 于 2025-06 捐给 Linux Foundation，作为**独立 LF 项目**运作；2025-12 Linux Foundation 成立 Agentic AI Foundation（AAIF），Anthropic 捐入 MCP、OpenAI 捐入 AGENTS.md、Block 捐入 goose——A2A **不在** AAIF 托管项目之列。准确表述：三大协议同归 LF 大伞下（MCP、AGENTS.md 具体由 AAIF 治理），形成分层互补格局——说明这不是厂商之争而是协议分层。
- 不可互替：MCP 的语义是"调用一个确定性的能力端点"，没有对等协商、任务状态机与能力自描述；把另一个 agent 包成 MCP server 虽可行，但丢失了 A2A 的协商与状态语义。正确心智模型是**协议栈**：底层 MCP 接工具，上层 A2A 做组织间协作（开放网络可用 ANP，仓库上下文用 AGENTS.md；IBM/BeeAI 的 ACP 已于 2025 年并入 A2A，属历史协议，作为演进脉络了解即可）。
- 机制深问储备：MCP 传输为 stdio / Streamable HTTP（2025-03 起取代 SSE），授权按 2025-06-18 规范走 OAuth 2.1（server 为 Resource Server，不得自签 token，经 RFC 9728/8707 发现 AS 与绑定受众）；A2A v1.0（2026）引入签名 Agent Card 与企业级鉴权。

#### 题 4（进阶 ⭐⭐）：Multi-agent debate 为什么能提升推理？它的局限是什么？你会怎么改进？

**参考答案要点**：
- 原理：多实例独立生成 → 多轮互阅对方论点并修订 → 收敛共识。相比 self-consistency 的独立投票，辩论引入了**对抗性信息交换**，错误推理链更可能被对方攻破（Du et al., ICML 2024，MIT/Google Brain）。
- 局限：① 成本 = agents × rounds 倍增；② **锚定/谄媚**——模型倾向向初始多数派收敛而非真正纠错；③ 后续研究（"Should we be going MAD?", ICML 2024；2025 年后续实证《If Multi-Agent Debate is the Answer, What is the Question?》）显示收益高度任务依赖、常见负收益，且部分"提升"其实来自多轮生成预算本身；④ 同质模型共享盲区会互相带偏；⑤ 需要基座模型本身够强。
- 改进：结构化对抗（指定 devil's advocate + 强制举证 + 独立 judge 裁决）；用 evaluator-optimizer 回路替代自由辩论；异构模型辩论减少同质化共鸣；把辩论预算只花在高风险、可验证的判断上。

#### 题 5（进阶 ⭐⭐）：如何为多智能体系统设计共享记忆？共享与隔离如何权衡？

**参考答案要点**：
- 先分层：working memory（当前任务上下文）、episodic memory（任务经历）、semantic memory（领域知识/规范），分别选载体（state graph / KV store / 向量库 / 文件系统）。
- 权衡：全共享→一致性高但上下文爆炸与注意力稀释（Cognition 的批评核心）；全隔离→并行干净但隐式决策冲突、汇总丢信息。
- 折中方案：① orchestrator 持全局计划与进度，worker 只拿任务切片；② 中间产物**外部化为 artifact**，按需检索而非塞 prompt；③ worker 回传统一**结构化摘要契约**（结论/证据/置信度/引用）；④ 跨会话长期记忆做命名空间隔离与权限控制（防止 agent 互相污染记忆）；⑤ 状态可 checkpoint、可回放（durable execution）。
- 统一视角：这本质是 context engineering——给每个 agent "恰好足够"的上下文，共享与隔离只是两个可调旋钮。

#### 题 6（基础/框架 ⭐⭐⭐）：对比 AutoGen、CrewAI、MetaGPT、LangGraph 的设计哲学与适用场景。

**参考答案要点**：
- AutoGen：会话即协作，conversable agents + GroupChat，v0.4 起重写为 async/event-driven；2025-10 与 Semantic Kernel 统一为 Microsoft Agent Framework（2026-04 GA 1.0，AutoGen/SK 进入 sunset，官方提供迁移指南）；研究友好、对话拓扑灵活，但控制流隐式、生产审计难；旗舰 Magentic-One。
- CrewAI：角色隐喻（role/goal/backstory）+ Crew（sequential/hierarchical）+ Flows（事件驱动）；上手快、贴业务，深度定制弱。
- MetaGPT：把软件公司 **SOP** 编码为 assembly line，共享 message pool + 订阅机制，**executable feedback**（运行代码获得真实反馈）是其区别于"纯对话协作"的关键（论文报告 HumanEval/MBPP Pass@1 约 85.9%/87.7%，消融实验显示移除该机制后有数个百分点下降）。
- LangGraph：显式 stateful graph，supervisor/swarm 拓扑，1.0（2025-10，官方承诺 2.0 前无破坏性变更）后 durable execution、HITL、observability 最成熟，样板多、曲线陡；LangChain Deep Agents 在其上预置了深度 agent 模式。
- 补充：OpenAI 路线为 Swarm（教学）→ Agents SDK（handoff/guardrails/sessions）→ AgentKit（可视化 builder + evals），适合 OpenAI 生态内快速产品化。
- 结论句：框架选择是次要变量；prompt、工具设计、评估体系才是决定因素。能不用框架的简单模式能解决就别引入框架。

#### 题 7（调试实战 ⭐⭐⭐）：线上一个多智能体系统偶发产出错误答案，单步复现又都"看起来正常"，你怎么排查？

**答题思路**：体现 trace、归因方法论、评估回归三板斧。

**参考答案要点**：
- 承认本质：多智能体失败是**路径非确定 + 级联放大 + 责任弥散**，传统断点调试失效；量化证据：MAST（Cemri et al., 2025）对 1600+ 轨迹的标注显示，失败主要分布在规格与系统设计（约 43%）、跨 agent 失配（约 32%）、任务验证与终止（约 25%）三大类——协调层缺陷是主因而非模型能力。
- 第一步——全链路 tracing：采集每次 run 的 DAG（编排决策、子任务书、worker prompt/输出、工具调用 I/O、合并逻辑），带 run-id 关联；脱敏用户数据；埋点对齐 OpenTelemetry GenAI 语义约定，落到 LangSmith/Langfuse/Arize Phoenix 等平台。
- 第二步——分层归因：① 编排层（拆解是否合理、是否漏子任务）；② worker 层（搜索/工具结果质量、是否截断）；③ 聚合层（合并是否丢证据、引用是否张冠李戴）；用 checkpoint 回放定位首个发散点，并给失败 case 打上 MAST 14 种模式的标签。
- 第三步——复现与固化：把失败 case 固化进 eval 集（Anthropic 从 ~20 条起步的做法）；对自由文本用 LLM-as-judge 跑回归；对写状态类系统评估**终态**而非每步。
- 第四步——系统性加固：重试 + checkpoint 恢复 + 工具健康信号；给 worker 加输出契约校验（schema 失败即重试）；关键合并步骤加 verifier；必要时固定 seed/降温度换取可复现窗口。

#### 题 8（系统设计 ⭐⭐⭐）：设计一个企业级 Deep Research 系统（给定开放问题，10 分钟内产出带引用的研究报告）。

**答题思路**：按"架构 → 编排 → 工具 → 记忆 → 可靠性 → 评估 → 成本"展开。

**参考答案要点**：
- 架构：orchestrator-worker。Planner（强模型）产出带优先级的研究计划 → 动态 worker 池（较弱模型，并发度受 API rate limit 约束）执行搜索/阅读 → Aggregator 分节合并 → Citation verifier → 输出。
- 委派契约：每个子任务书含 {目标、假设、输出 JSON schema、工具白名单、最大搜索次数/token 预算}；worker 返回 {findings[], evidence_urls[], confidence}。
- 工具设计：web search（先广后聚焦策略）、page fetch+抽取、内部知识库检索（走 MCP server 统一接入）；工具描述本身就是 prompt，需测试迭代。
- 记忆：计划与进度持久化；worker 产物写对象存储（artifact），上下文只传摘要；超限时 clean-context 重启 subagent。
- 可靠性：worker 级重试与超时、checkpoint、工具降级信号、rainbow deployment。
- 评估与护栏：小规模 golden set + LLM-as-judge（事实性/引用支持度/覆盖度/信源权威性）+ 人工抽检；引用校验器（claim-citation 对齐）防幻觉；预算熔断。
- 成本与延迟：难度自适应（简单问题降级为单 agent 直答——routing 前置）；worker 并发 + 流式产出。
- 加分项：提到与 Cognition 论点的对照——研究任务恰是"松耦合可并行"的正面典型，而报告内部写作仍由单一 aggregator 保持风格与决策一致性。

#### 题 9（评估 ⭐⭐）：多智能体系统的评估和单模型评估有什么本质不同？怎么落地？

**参考答案要点**：
- 本质不同：① 输出是**多路径、非确定**的过程产物，不能只评单点输出；② 存在**交互质量**维度（委派是否合理、信息回传是否充分），单模型 eval 无此维度；③ 会改写外部状态的系统必须评**终态/中间 checkpoint 态**；④ 成本/效率是一等指标（token、轮数、工具调用数）。
- 落地：小集合高频迭代（~20 条真实任务起步）；LLM-as-judge 用单一稳定打分 prompt 多维评分（注意 judge 模型与被评模型同源时的自我偏好偏差，可换异源模型交叉评）；过程指标（路由准确率、引用可验证率）+ 终局指标双轨；人工评审兜底抓 judge 盲区；把线上 bad case 持续回灌 eval 集（eval-driven 迭代）。
- 可靠性口径：用 τ-bench 式 **pass^k**（k 次全对）而非 pass@k（至少对一次）作发布门槛；pass^1 = 70% 的系统 pass^8 只剩约 6%，多智能体尤其要按一致性口径验收（§2.11）。

#### 题 10（开放题 ⭐⭐）：Cognition 说"别建多智能体"，Anthropic 却靠多智能体做出顶级 Research 产品，谁对？

**答题思路**：展示辩证综合，而非站队。

**参考答案要点**：
- 两者谈的是**不同任务分布**：Devin 做的是仓库级代码修改——决策强耦合、隐式假设牵一发动全身，单线程连续上下文确实更稳；Anthropic Research 做的是开放调研——子问题松耦合、可并行、信息量超单上下文，分治收益远大于协调成本。
- 统一判据是 **coupling × value × context size**：决策耦合度低、任务价值高、上下文需求大 → 多智能体；反之单 agent。
- 更深的共识：两家其实都在做同一件事——**context engineering**。Cognition 的"share full trace"与 Anthropic 的"结构化压缩回传 + artifact"是上下文管理在单/多智能体下的不同实现。
- 落地立场：默认单 agent，把多智能体当作**有明确 ROI 论证的优化手段**而非架构信仰；Cognition 在 [《Multi-Agents: What's Actually Working》](https://cognition.com/blog/multi-agents-working)（2026-04）中的"让步"也很克制——承认跑通的仅是只读/评审/MapReduce 类场景，且前提是写操作保持单线程、辅助者只提供智能不执行动作——论战以"窄口径的条件化共识"收场。

#### 题 11（系统设计 ⭐⭐⭐）：设计一个多智能体客服系统：用户诉求多样（订单、退款、技术支持、投诉），要求首答快、能转专业坐席、关键时刻能升级到人工。

**答题思路**：这是 routing + swarm/handoff + HITL + guardrails 的综合题，区别于题 8 的 orchestrator-worker。

**参考答案要点**：
- 架构分层：① 前置 **Router**（小模型/分类器）做意图识别与会话级路由，保证首答延迟；② 一组专业 agent（订单/退款/技术/投诉），各自独立 prompt + 最小化工具白名单（退款 agent 才有退款工具）；③ agent 间用 **handoff** 而非中央 supervisor 转接——客服是对话流转型场景，handoff 移交整个会话上下文，避免 supervisor 中继的"电话传话"开销与信息损耗（LangChain 在 tau-bench 上的实测结论）。
- 状态管理：会话 state（订单号、已确认身份、对话摘要）持久化，handoff 时随会话迁移；长会话做摘要压缩。
- HITL 升级：定义升级阈值（金额超限、连续两轮未解决、检测到愤怒情绪、涉及合规），触发 interrupt 转人工；人工与 agent 共享同一会话视图与操作权限分级。
- 安全与护栏：输入护栏检测注入（用户可能贴入"忽略之前指令"）与越权请求；输出护栏做 PII/承诺合规过滤；敏感操作（退款）二次确认 + 审计日志。
- 评估：tau-bench 式任务完成率（含数据库终态正确性与 pass^k 一致性）+ 升级合理率 + 幻觉承诺率 + 成本/会话；线上 bad case 回灌。
- 加分项：指出"handoff 不是万能"——若未来出现需要并行协调多部门（退款 + 技术同时处理）的诉求，应升级为 orchestrator-worker，架构要预留切换空间。

#### 题 12（系统设计 ⭐⭐⭐）：设计一个代码生成多智能体流水线（需求 → 设计 → 实现 → 审查 → 测试）。它与 Deep Research 的设计有哪些关键不同？

**答题思路**：考"强耦合任务的编排"与 executable feedback，直接对标 Cognition 论点与 MetaGPT。

**参考答案要点**：
- 流水线（SOP 思路，MetaGPT 式）：PM agent 产出结构化需求/用户故事 → Architect 产出模块划分与接口契约（**契约是后续并行的前提**）→ Engineer 实现 → QA 生成并执行测试 → Reviewer 审查 → 不合格回 Evaluator-Optimizer 回路。
- **与 Deep Research 的关键不同（核心得分点）**：
  1. **耦合度不同**：代码实现是决策强耦合（命名、数据结构、依赖版本牵一发动全身）——因此实现阶段**不应多 agent 并发改同一代码库**；可并行的是**信息松耦合**的环节（多模块按接口契约各自实现、多维度代码审查：安全/性能/风格）。
  2. **写操作必须串行化或分区**：研究系统 worker 只读不写可自由并行；代码系统对同一仓库的写要么单 writer 串行合并，要么按文件/模块分区，并配 merge 冲突处理。这也是 Cognition 2026 年"让步文"的底线：跑通的多智能体场景一律写操作单线程。
  3. **executable feedback 是一等公民**：跑真实测试/linter/编译器，把报错回灌给 engineer（MetaGPT 的核心洞见），比"LLM 互评"可靠得多。
  4. **沙箱与安全**：代码执行在隔离沙箱（容器/microVM），禁网或白名单，限制文件系统访问。
  5. **HITL 位置不同**：研究和客服的 HITL 多在输出端；代码系统的 HITL 应放在不可逆动作前（合并 PR、部署）。
- 可靠性与评估：checkpoint 每阶段产物；评估用 Pass@k/测试通过率等可执行指标 + LLM 审查，终态（测试绿）优先于过程评分。

---

### 五、易错点·反直觉点

1. **"多 agent = 更聪明"**：错。多智能体是上下文分治与并行化，不是推理增强。委派 prompt 写得差，worker 越多噪声越大，合并结果可能**劣于**单 agent。
2. **Debate 总能提升准确率**：错。LLM 有锚定与谄媚倾向，多轮辩论常收敛于初始多数派，甚至互相带偏；后续实测多为任务依赖、常见负收益，部分"提升"只是多轮生成预算的功劳。
3. **把 MCP 当 agent 间通信协议**：MCP 是主从式工具协议；对等委派、任务生命周期、能力发现是 A2A 的语义层。两者 2025 年底同归 Linux Foundation 大伞下（MCP、AGENTS.md 由 AAIF 治理，A2A 是独立 LF 项目），恰恰说明是分层互补。
4. **共享全部上下文就安全了**：全共享带来上下文爆炸与注意力稀释，成本与失效率齐升——这是"单 agent 党"的核心论据。隔离与共享之间必须做结构化契约。
5. **忽视 15× token 成本**：很多 demo 级多智能体方案一旦算 ROI 就不成立；难度自适应路由（简单任务走单 agent）是必备设计。更进一步可用**模型级联**（FrugalGPT 式分级上升：小模型低置信度时才升级到强模型），把预算花在刀刃上。
6. **用确定性单测保障多智能体质量**：路径非确定使单测极不稳定；正确姿势是 eval 集 + LLM-as-judge + trace 回放 + 终态断言。
7. **Supervisor 不会成为瓶颈**：会。中央 relay 产生"电话传话效应"（LangChain [Benchmarking Multi-Agent Architectures](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)（2025-06）在 tau-bench 变体上实测：supervisor 因转述开销 token 更高、信息有损），swarm 式直接转交在对话流转型场景更优。
8. **涌现行为 = 能力**：对工程师而言，涌现首先是**不可靠性的来源**——lead prompt 的微调会在群体级联放大。要用护栏与评估驯化它。
9. **以为框架解决协调问题**：AutoGen/CrewAI/LangGraph 只提供通信与状态原语；真正的协调质量来自任务书设计、工具描述质量（工具描述本身要用模型测试迭代）与输出 schema 约束。
10. **并行写操作的竞态**：多个 worker 并发改同一外部状态（同一代码库、同一文档）会冲突。松耦合读可以并行，**写必须串行化或分区**——这正是 Devin 坚持单线程的底层原因之一。工程选项：单 writer 串行合并、按模块/文件分区写、事务化工具 API、merge 冲突处理管线（参见题 12）。
11. **长任务不做 checkpoint**：跨数十步的 agent 状态一旦中途失败，没有断点续跑就等于全部 token 打水漂；还需配幂等工具调用。
12. **评估每一步**：对会改写状态的系统，逐步评分既贵又误导；评终态与关键 checkpoint。
13. **handoff 默认继承权限**：危险。转交会话不等于转交全部工具权限；敏感工具必须按 agent 白名单、按动作设确认门，否则一个被注入的边缘 agent 就能调用退款接口。
14. **把 guardrails 当可选项**：多智能体把提示注入的攻击面从"用户→agent"扩展成"agent→agent、工具→agent、记忆→agent"；所有跨边界内容都应视为不可信数据，输入输出护栏应与主流程并行且可熔断。
15. **用 pass@k 当生产发布门槛**：pass@k 度量"k 次里至少对一次"的碰运气成功率；生产要的是 **pass^k**（k 次全对）。pass^1 = 70% 的系统 pass^4 ≈ 24%、pass^8 ≈ 6%——多智能体放大每步方差，发布门槛应定在 pass^k 上（τ-bench 的核心主张）。
16. **把协议当安全边界**：MCP/A2A 只标准化互操作语义，不提供沙箱、权限与工具描述校验；授权（OAuth 2.1、OBO 委托凭证）与注入防护都是应用层责任。

---

### 六、推荐资源

1. **[Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)**（2024-12）：workflow vs agent 的定义与五大模式的权威出处，本域"圣经"级入门文，面试前必读。
2. **[Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)**（2025-06）+ **[Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)**（2025-09）：前者是目前最详实的**生产级**多智能体工程复盘（15× token、context engineering、checkpoint、rainbow deployment、评估方法），后者把 compaction / sub-agent / note-taking 等上下文管理手段系统化；进阶必读。
3. **[Cognition — Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)**（2025-06）及后续 **[Multi-Agents: What's Actually Working](https://cognition.com/blog/multi-agents-working)**（2026-04）：最重要的反方视角及其演进（注意后续文章的口径是"写操作单线程、helper 只提供智能"的只读/评审类场景），理解 context engineering 与 decision coupling 的关键，配合第 2 条阅读形成完整认知。
4. **[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/abs/2308.00352)**（ICLR 2024 Oral）：SOP、message pool、executable feedback 的出处，理解"把人类工程流程编码进协作"的最佳论文样本。
5. **[Du et al. — Improving Factuality and Reasoning through Multiagent Debate](https://arxiv.org/abs/2305.14325)**（ICML 2024）+ 反方 **[Should we be going MAD?](https://arxiv.org/abs/2311.17371)**（ICML 2024）+ 后续实证《[If Multi-Agent Debate is the Answer, What is the Question?](https://arxiv.org/abs/2502.08788)》（arXiv:2502.08788，2025-02）：debate 模式正反多方一起读，面试中展现批判性思维。
6. **[A Survey of Agent Interoperability Protocols: MCP, A2A, ACP, ANP](https://arxiv.org/abs/2505.02279)**（2025）+ **[LangChain — Benchmarking Multi-Agent Architectures](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)**（2025-06）+ **[Agentic AI Foundation](https://aaif.io/)**（2025-12）：建立协议栈全景与治理格局（注意两点：A2A 为独立 LF 项目、不在 AAIF 托管之列；综述中的 ACP 其后已并入 A2A，属历史协议），并拿到 supervisor vs swarm 的实测数据（电话传话效应、token 曲线），是协议题与选型题的弹药库。
7. **[Multi-Agent Collaboration Mechanisms: A Survey of LLMs](https://arxiv.org/abs/2501.06322)**（2025-01）：对协作机制（通信拓扑、角色分工、涌现行为）的系统学术综述，适合补理论纵深。
8. **[OpenAI — New tools for building agents（Agents SDK）](https://openai.com/index/new-tools-for-building-agents/)**（2025-03）与 **[OpenAI Agents SDK 文档](https://openai.github.io/openai-agents-python/)**：handoff / agents-as-tools / guardrails / sessions 四个原语的最简参考实现，配合 LangGraph supervisor/swarm 文档对照阅读，可把"协作原语"这一层彻底打通。
9. **[Cemri et al. — Why Do Multi-Agent LLM Systems Fail?（MAST）](https://arxiv.org/abs/2503.13657)**（2025）：多智能体失败分类学的标准实证（14 种失败模式、三大类占比 42.8% / 32.4% / 24.9%、LLM-as-judge 自动归因管线），调试题、可靠性题与"为什么失败"类追问的学术锚点。
10. **[τ-bench](https://arxiv.org/abs/2406.12045)**（Sierra, 2024）+ **[Generative Agents](https://arxiv.org/abs/2304.03442)**（Park et al., UIST 2023）+ **[More Agents Is All You Need](https://arxiv.org/abs/2402.05120)**（Li et al., 2024）：分别对应可靠性度量（pass^k 与终态评估）、涌现行为的第一手观察、以及"规模正向但来自采样预算"的实证——评测题与学科纵深题的三块基石。
