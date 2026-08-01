# 第 8 章 · Agent 评估与可观测性

## Agent 评估与可观测性

### 一、知识图谱

```
Agent 评估与可观测性
├── 1. 评估基础
│   ├── 为什么 Agent 评估 ≠ LLM 输出评估（多步、状态、工具副作用、非确定性、环境保真度）
│   ├── 评估对象分层：组件级（prompt/tool/retriever 组件指标）→ 轨迹级 → 端到端任务级 → 系统级（harness/scaffold 一起测）
│   ├── 数据集构建方法论：任务分类学 → 能力×难度覆盖矩阵 → item spec 评审 → 分阶段扩建
│   ├── 污染检测与防制：canary 埋点、重叠检测、复述变体试探、封禁与定期换血
│   └── 评估生命周期：数据集构建 → 离线评估 → CI 回归门禁 → 灰度验证 → 在线监控 → 数据飞轮
├── 2. 评估维度
│   ├── 正确性（final answer / final state correctness）
│   ├── 工具调用质量（tool selection accuracy、参数正确率、调用效率、越权/安全）
│   ├── 任务完成率（task completion / success rate）
│   ├── 可靠性（reliability：pass@k vs pass^k）
│   ├── 效率（steps、tokens、latency、cost、缓存命中）
│   ├── 规划质量（计划可行性、子目标分解、重规划合理性）
│   ├── 交互质量（语气、共情、解释性、轮次效率）
│   ├── 安全与合规（policy following、拒答、幻觉、权限边界、注入鲁棒性）
│   └── 运营指标（containment/自动化解决率、escalation/转人工率、CSAT、重开率）
├── 3. 评估范式
│   ├── Outcome-based（结果/状态评估）
│   ├── Trajectory-based（轨迹评估：exact match / 无序集合 / step-level）
│   ├── 规则式 grader（assert、单元测试、DB 状态 diff、JSON Schema 校验）
│   ├── LLM-as-Judge（pointwise / pairwise / reference-based；二值化 checklist；rubric；偏差与校准）
│   ├── Agent-as-Judge（用 Agent 评估 Agent，工具化核验）
│   ├── Grader 自身的对抗性（reward hacking / specification gaming、grader 红队测试）
│   └── Human evaluation（rubric 设计、IAA、golden set、review queue）
├── 4. 统计与可靠性
│   ├── 非确定性 → 多 trial 重复、seed/温度策略
│   ├── pass@k（k 次中有一次成功）vs pass^k（k 次必须全成功，估计依赖 trial i.i.d. 假设）
│   ├── 置信区间（Wilson/bootstrap）、样本量与功效、多重比较校正
│   └── 评估集污染、饱和、scaffold 混淆与 Goodhart 定律
├── 5. Benchmark
│   ├── GAIA / GAIA-2（通用助理，读→读写，人机差距，ARE 环境框架）
│   ├── AgentBench（8 环境，LLM-as-Agent 横向对比）
│   ├── τ-bench / τ²-bench / τ³-bench（tool-agent-user 交互、双控制、policy following、pass^k、语音模态）
│   └── 延伸：SWE-bench(Verified/Pro)、OSWorld、WebArena、Terminal-Bench、BFCL v4（agentic：多跳工具链/记忆/web 检索/格式敏感性）、PlanBench
├── 6. 可观测性
│   ├── 三大支柱：Logs / Metrics / Traces
│   ├── 数据模型：Trace / Span / Generation / Event；分数（score）作为 trace 的标注
│   ├── OpenTelemetry GenAI Semantic Conventions（gen_ai.* 属性、内容采集 opt-in、agent/tool/MCP 属性 registry）
│   ├── 平台：LangSmith / Langfuse / Arize Phoenix / Braintrust / W&B Weave / OTel 原生后端（Datadog 等）/ 框架自带 tracing
│   ├── 关键指标：延迟（TTFT / p95-p99 尾延迟 / TPOT / 工具往返）、token/成本、错误率、工具失败率、预算超限、缓存命中率
│   └── Trace → Debug：replay、prompt diff、回归数据集；规模化下的采样与保留期策略
├── 7. 在线评估与运营
│   ├── 采样策略、异步 online judge、阈值告警（SLO 实时 vs 质量批量）
│   ├── 输入分布漂移监控（意图/embedding drift）
│   ├── 用户反馈（显式/隐式）、升级机制、containment 分析
│   ├── Shadow mode → Canary → A/B（会话级分流、序贯检验）→ 全量
│   ├── 数据飞轮：failure mining → 失败分类学（taxonomy）→ golden set → 回归套件
│   ├── 训练闭环：轨迹筛选 → SFT / 拒绝采样 / 偏好对（RFT）→ eval 门禁 → 灰度上线
│   └── 人机协同：HITL vs HOTL、annotation queue、judge 校准回路
├── 8. 评估环境工程与可复现性
│   ├── 确定性控制（温度/seed、版本锁定、record-replay、用户模拟器固定）
│   ├── 状态管理（快照/重置、用例隔离、并行化）
│   ├── 保真度光谱：mock → 模拟器（ToolEmu）→ 沙箱真实环境 → 生产 shadow
│   ├── 评估成本预算（分层评估、smoke 子集、CI 门禁、flaky 隔离）
│   ├── 基础设施自检：A/A 测试噪声基线、离线-在线相关性回测
│   └── 统计可复现性（protocol 即代码、报 trial 数与置信区间）
├── 9. 安全与对抗评估
│   ├── 提示注入（直接 / 间接：工具返回、网页、文档中携带指令）
│   ├── 工具滥用、权限矩阵、信息泄露（system prompt / 跨用户数据）
│   ├── 双轴指标：攻击成功率 ASR × 良性效用保持（tradeoff 曲线）
│   └── Benchmark：AgentDojo、InjecAgent、AgentHarm、ToolEmu 安全套件
└── 10. 多智能体评估
    ├── 角色遵循、handoff 准确性、跨 handoff 信息保真度
    ├── 通信开销、相关误差与错误放大
    ├── 轨迹即 DAG（消息也是一等 span）、非平稳性与版本矩阵
    └── 联合回归 vs 组件隔离评估
```

---

### 二、核心概念精讲

#### 2.1 Agent 评估为什么比 LLM 评估难一个量级

评估一个 chat 模型的单次回答，输入输出是静态的、可对标的。评估一个 Agent，你面对的是一个**在环境中多步决策的系统**，难点来自五个方面：

1. **组合爆炸与路径多样性**：同一任务可能存在多条合法路径（先查订单还是先验身份？）。对轨迹做 exact match 会把大量正确行为判错——这是最常见的评估设计错误。
2. **副作用（side effects）**：Agent 会真的改数据库、发邮件、扣款。评估不仅要看"说了什么"，还要看"世界变成了什么样"（final state），这要求评估环境可重置、可 diff。
3. **非确定性叠加**：一次 LLM 采样误差 × N 步 ≈ 成功率指数级衰减。单次运行的 pass rate 几乎没有统计意义，必须多 trial 并区分"能力不足"与"稳定性不足"。
4. **长程信用分配**：任务失败时，错误可能发生在第 3 步的工具参数，而在第 12 步才暴露。没有 trace 就没有 debug。
5. **环境保真度与评估自身的工程成本**：mock 太假测不出真问题，真环境太贵且会脏。评估系统本身也是一套需要版本管理、需要保真度审计、需要预算控制的工程系统——这一点常被忽视。

**难点 4 并非无解，归因有一套标准手段**：**反事实重放**（固定后续步骤的输入，只替换某一步的输出，看结局是否翻转）定位"是哪一步坏的"；**单步扰动**（替换某个工具参数/中间结论后重跑）量化该步的因果贡献；**trace diff 对齐**（比对成功与失败 trial 的轨迹，找首个分叉点）做批量归因；**judge-based step attribution**（让带工具的评审 judge 逐步打分）在无法穷举重放时兜底。这些手段都以完整 trace 与可重放环境为前提——这正是"可观测性是评估的前置条件而非附属品"的含义。

**结论**：Agent 评估天然是"系统评估"而非"模型评估"，必须把 scaffold、工具、检索、prompt 一起纳入被测对象（同一个模型换一套 harness，分数可以差几十个百分点）；评估产出也不应只是一个分数，而是**分层指标 + 可追溯的失败归因**。

#### 2.2 评估维度：正确性、工具调用准确率、任务完成率

**（1）任务完成率 / 正确性（Outcome）**

最接近业务价值的指标，但要注意两种判定方式：

- **Final answer matching**：适合答案可归一化的场景（GAIA 要求精确字符串匹配，数字保留两位小数、列表排序）。
- **Final state verification**：τ-bench 的做法——不评判自然语言回复，而是直接检查后端数据库是否达到期望状态（订单是否被正确取消、金额是否正确）。这种方式**抗话术干扰**，是客服/操作类 Agent 的首选。

**（2）工具调用准确率（Tool-call quality）**

可拆成五个子指标：

| 子指标 | 定义 | 评测方式 |
|---|---|---|
| Tool selection | 该调哪个工具（含"不该调而调"和"该调没调"） | 按调用事件做 precision/recall |
| 参数正确率 | 参数值、类型、枚举是否对 | JSON Schema 静态校验 + 结构化语义比对（注意参数等价类、默认值） |
| 调用顺序/依赖 | 前置条件是否满足（如先鉴权后操作） | 偏序约束断言（不要求全序列） |
| 调用效率 | 重复调用、冗余调用、死循环 | 轨迹去重分析、步数分布 |
| 安全/权限 | 是否调用越权工具、是否跳过校验步骤 | 规则断言（must-call / must-not-call） |

**关键取舍（业界通行做法；Anthropic 的评估指南亦主张 "Don't grade the path, grade what it produced"——以 outcome 为主，只对关键调用做强约束）**：当安全或正确性强依赖某次调用时，用 `required_tools` / `forbidden_tools` 断言校验**关键调用**，但**不要强制固定调用序列**——否则你会惩罚掉合法但不同的解决路径，评估集退化成"背答案"。

**（3）效率与成本维度**

资深回答永远要带上：steps/turns、input/output tokens（含缓存读写）、wall-clock latency（以及 TTFT）、每次会话成本。两个 pass rate 相同的 Agent，成本差 5 倍时生产选型结论完全不同。τ-bench、Claude Code 的评估实践都明确把 turns/tokens/latency/cost 与 pass rate 并列上报。延迟维度还要再拆一层：**p95/p99 尾延迟、TPOT（出字间隔）、以及工具往返延迟**——Agent 会话的 wall-clock 大头往往在工具执行与等待（外部 API、人工审批），而非推理本身，只看 TTFT 会系统性误判瓶颈。

**（4）安全、合规与运营维度**

- **安全/合规**：policy following（几百条业务规则下的合规操作）、该拒答时拒答、不该泄露时不泄露（system prompt、他人数据）、对提示注入的鲁棒性（详见 2.10）。
- **交互质量**：语气、共情、解释性、轮次效率——客服场景中"结果对但态度差/不解释"是真实投诉来源，通常交给 LLM judge 按 rubric 评。
- **运营指标**：containment rate（无人工介入自动解决率）、escalation rate（转人工率）、CSAT、会话重开率。这些是连接"评估分"与"业务价值"的桥，面试中主动提及是产品感信号。

#### 2.3 Outcome 评估 vs Trajectory 评估

| 维度 | Outcome（结果） | Trajectory（轨迹） |
|---|---|---|
| 看什么 | 最终答案 / 环境最终状态 | 中间步骤、推理、工具序列 |
| 优点 | 贴近业务、路径无关、grader 简单 | 能做信用分配、能抓"结果对但过程危险" |
| 缺点 | 失败无归因；掩盖危险过程 | 脆弱（路径多样）、grader 复杂 |
| 典型 | GAIA、τ-bench 的 DB state | Agent-as-Judge、step-level rubric |

**成熟实践是两者结合**：

- 用 outcome 判 pass/fail（主指标）；
- 用 trajectory 评估做**归因与护栏**：step-level 打分（每一步是否必要、是否违反 policy），以及对"结果正确但轨迹违规"的单独计数——例如 Agent 靠猜测碰对了答案，或绕过了身份验证却恰好没造成损失。
- 轨迹评估的三种粒度由粗到细：**轨迹整体 LLM 评审** → **无序关键调用集合比对**（比 exact match 稳健）→ **单步 rubric 打分**。
- **多智能体场景下轨迹是 DAG 而非线性序列**：Agent 之间的 handoff 消息本身也是一等评估对象（handoff 该不该发生、转给了谁、上下文有没有丢），详见 2.11。

**Agent-as-a-Judge**（Zhuge et al., ICML 2025）把这个思路推到极致：让一个评审 Agent 带着工具（跑代码、查库、执行测试）去核验被评 Agent 的中间产物与轨迹，而不是让一个静态 LLM 读完整段 transcript 后拍脑袋。论文报告其与人类判断的一致性高于普通 LLM-as-Judge，且在论文的 DevAI 基准上报告：相比人类专家评估节省约 97.7% 的时间与 97.6% 的成本（场景特定的报告值，不宜外推为普适结论）。代价是评审本身引入新的非确定性和成本，需要再校准。

#### 2.4 LLM-as-Judge：方法、偏差与校准

**三种基本范式：**

1. **Pointwise**：给单个输出按 rubric 打绝对分（1–5）。适合在线监控（无需候选对比）、可解释性好；缺点是分数刻度不稳定、模型有"居中/趋高"倾向。
2. **Pairwise**：A/B 谁更好。判别力最强，是 Chatbot Arena / MT-Bench 的基础；代价是 O(n²) 比较成本与位置偏差。
3. **Reference-based**：给定参考答案/评分细则，判断输出是否满足（类似 RAGAS 的 answer correctness）。Agent 评估中最常用——把期望行为写成 checklist，judge 逐项核验。

**一条被低估的经验：judge 做二值判断比打连续分可靠得多。** 把"1–5 分质量"拆成一串二值/分类检查项（"是否核实了身份？""金额是否精确到分？""是否泄露了无关信息？"），再程序化聚合，噪声和校准难度都显著下降。精细 Likert 刻度往往放大模型间刻度差异而非真实质量差异。

**Judge 的经典偏差（Zheng et al. 2023；Ye et al., 2024，arXiv 2410.02736《Justice or Prejudice?》系统量化了十余种）：**

- **Position bias**：偏好放在前面（或后面）的候选。**缓解**：随机化顺序 + swap consistency（交换位置重评，统计翻转率作为偏差诊断）。
- **Verbosity bias**：偏好更长的回答，哪怕更长只是更啰嗦。**缓解**：rubric 中显式约束长度无关性、长度归一化。
- **Self-enhancement bias**：judge 偏爱与自己同族模型生成的内容。**缓解**：judge 模型 ≠ 被测模型（至少在关键决策上不重合）。
- **Sycophancy / authority bias**：迎合提示中暗示的"正确答案"或权威口吻。**缓解**：中性化 prompt、盲评（不暴露候选来源）。
- **能力上限问题**：judge 无法可靠评判超出自身能力的输出（弱模型 judge 强模型的代码/推理）。**缓解**：judge 选型能力 ≥ 被测，关键任务用最强模型或人审兜底。

**工程上让 judge 可信的七件事：**

1. **专家校准的 rubric**：评分标准由领域专家写，枚举每档分数的具体行为锚点（behavioral anchors），而不是"质量好/一般/差"。
2. **分维度打分**：正确性、完整性、合规性分开给分，再聚合——单个笼统分会淹没信号（Anthropic 明确建议 score dimensions separately，并允许 "Unknown" 档与部分得分 partial credit）。
3. **CoT / 先理由后分数**：让 judge 先输出判断依据再给分，一致性显著提升。
4. **校准集 + 人机一致性**：准备一份人工标注的校准集，量化 judge 与人类的 Cohen's κ / Krippendorff's α / 一致率；二值判定还可看 ROC-AUC，打分判定看 Spearman 相关与校准误差（ECE）。MT-Bench 报告 GPT-4 judge 与人类一致率约 80%，接近人类之间水平——这是该范式成立的基线论据。κ < 0.6 的 judge 不能上线。注意 κ 的**患病率悖论（prevalence paradox）**：正例稀少或分布极度偏斜时（judge 做二值合规判断正是这种场景），会出现"一致率很高但 κ 很低"（或反之）的失真，故需同时报告一致率与 ROC-AUC 交叉验证，阈值仅作经验参考。
5. **面板（panel）与多次采样**：多 judge 投票或对同一 judge 多次采样取多数，降低方差。
6. **成本分层**：确定性断言（零成本）→ 小模型 judge（粗筛）→ 强模型 judge（难例）→ 人审（边界例）。不是所有样本都值得最贵的 judge。
7. **把 judge 当模型管理**：judge prompt 版本化、judge 模型升级时重跑历史数据做桥接对齐，防止"尺子自己热胀冷缩"。

**常见误区**：把 judge 输出直接当 ground truth；judge prompt 不做版本管理；线上 judge 与离线 judge 用两套 prompt 导致指标口径漂移；用 judge 评 judge 的同源输出形成闭环自证。

#### 2.5 可靠性度量：pass@k vs pass^k（τ-bench 的核心贡献）

单次成功率（pass rate）掩盖了生产环境最关心的问题：**同一任务重复执行，有多大概率每次都成功？** τ-bench（Yao et al., 2024；ICLR 2025）提出 pass^k：

- **pass@k**：k 次独立试验中**至少一次**成功。回答"我多试几次能不能成"——适合人可以随时重试、接管的任务。
- **pass^k**：k 次独立试验**全部**成功（概率意义上的）。回答"无人值守跑 k 次会不会出事"——适合自动化流水线、客服托管。

τ-bench 用 n 次试验中每个任务的成功数 s，按无放回抽样估计单任务 k 次全过的概率 ∏(s−i)/(n−i)（i=0..k−1，s<k 时为 0），再对全体任务取均值。注意该估计假设各 trial **独立同分布（i.i.d.）**；τ-bench 的试验共享同一用户模拟器与环境配置，试验间相关性会使估计有偏，故应同时报告试验次数 n 与置信区间，并对模拟器变异做多 seed/多配置吸收——这是该指标真实的统计弱点。

**为什么这个数字杀伤力大**：按论文摘要的严格口径，GPT-4o 在 retail 域 pass^1 即不足 50%（"succeeds on less than 50% of tasks"），pass^8 更跌至约 25%（相对降幅约 60%）；弱模型（Mixtral 8×7B）从不足 20% 跌到近乎 0。背后是同一个数学事实：**单步 95% 正确率 × 20 步 ≈ 36% 任务成功率——步级误差沿轨迹复合放大**。面试中能手推这个复合关系是高价值信号。

**统计报告规范（加分项）**：pass rate 是二项比例，应报 Wilson 或 bootstrap 置信区间；比较两个系统用配对检验（McNemar）而非只看两个点估计；pass^k 对试验次数 n 敏感（n 太小会系统性高估），必须连同 n 与置信区间一起报告；横向比较多个模型时做多重比较校正（Holm/Bonferroni）。

#### 2.6 Benchmark 精讲与全景

**（1）GAIA（Mialon et al., ICLR 2024）/ GAIA-2 + ARE（Meta FAIR, arXiv 2509.17158, 2025-09）**

- GAIA：466 个真实世界问题（165 验证 + 301 私有测试），要求联网检索、浏览器、文件读写、多步推理、多模态；答案为可精确匹配的字符串。三个难度级别：Level 1（强 LLM + 少量步骤）、Level 2（多工具多步）、Level 3（长程规划，十几步）。标志性数据点：**人类 92% vs 发布时最强系统约 15%**——"概念上对人简单、对 AI 极难"的设计哲学。到 2025 年，榜首系统已进入 70–80% 区间（以 2025 年榜单为参照），与人类 92% 的差距收窄至十余到二十个百分点但仍未闭合，说明**错误在长任务链上的复合**尚未被完全解决。
- **GAIA-2（2025-09）**：论文题为《ARE: Scaling Up Agent Environments and Evaluations》，从"只读问答"升级为**读写交互式任务**（管理邮件、日历、文件等模拟环境，800 个场景 × 10 个 universe），引入不确定性、噪声、条件变化、协作与时限，难度更高、更接近真实助理工作，并配套开源环境框架 ARE（Meta Agents Research Environments）。它的出现本身就是 GAIA 趋于饱和的证据。
- 面试考点：GAIA 的精确匹配评分为什么同时是优点（客观、零 judge 成本）和缺点（不奖励部分正确、不考核过程安全）。

**（2）AgentBench（THUDM, ICLR 2024）**

- 首个系统化"LLM-as-Agent"横向评测：8 个交互式环境，覆盖代码类（OS、数据库、知识图谱）、游戏类（数字卡牌、横向思维谜题）、真实应用类（家居控制 ALFWorld、Web 购物 WebShop、Web 浏览）。
- 关键发现：商用闭源模型（GPT-4）与同期开源模型在 Agent 任务上存在**远超 chat 基准的鸿沟**——说明"会聊天"与"会多轮决策"是两种能力。
- 定位：**环境多样性 × 模型横评**的标尺；每个环境的规模与拟真度有限，今天更多用于历史脉络理解。

**（3）τ-bench 家族（Sierra, 2024–2026）**

- τ-bench 设计：LLM 模拟用户 + 被测 Agent + 规则化后端 API + 企业 policy 文档（retail/airline），用**数据库最终状态**判对错。独特价值是 **policy following**——不是"能不能用工具"，而是"能不能在几百条业务规则约束下正确使用工具"（如：改签必须先验身份、特定票价不可退），这正是企业级客服 Agent 的真实瓶颈。引入 pass^k（见 2.5）。
- **τ²-bench（2025，arXiv 2506.07982）**：三大升级——**双控制**（用户侧也是带工具的 Agent，会自己操作界面，被测 Agent 必须与用户协调而非独占控制权，论文以 Dec-POMDP 建模）、域扩展为 retail/airline/**telecom**、提供**组合式任务生成器**（compositional task generator，自动组合出更复杂的任务）。
- **τ³-bench（2026）**：新增**全双工语音**（τ-voice，arXiv 2603.13686）、τ-knowledge 知识任务与 banking 域；语音成绩仅约文本的 30–45%——**模态叠加 + 实时交互**仍是当前能力洼地。
- **现状（截至 2026 年年中参照，pass^1）**：τ² 总榜榜首（GLM-5.2）已达约 90.9%，telecom 等易域超过 90% 接近饱和；而原版 τ-bench 上 airline 域榜首长期停留在约 56%、长期未饱和（两者分属不同代际的榜单，不可混在同一句话里比较）；任何域上 pass^8 都显著回落；第三方分析指出易域分数存在 5–15 个点的污染/脚手架虚高。榜单按月变动，分域最新数据以 taubench.com 为准。
- 面试考点：τ-bench 的"用户模拟器"本身是非确定性的，如何处理？（固定用户模拟器模型/温度、把用户侧变异纳入试验方差、多 trial 平均。）模拟器效度本身也需验证：与真人对话小样本 A/B 比对、做"换模拟器模型结论是否翻转"的敏感性分析，否则可能测的是"应付模拟器的技巧"而非真实服务能力。

**（4）其他应知全景**

| 类别 | 基准 | 一句话 |
|---|---|---|
| 代码 Agent | SWE-bench Verified / Pro | 真实 GitHub issue 修复；2026 榜首 >80% 逼近 90%，但已近饱和且污染争议大（催生 SWE-rebench 月度刷新集） |
| 计算机操作 | OSWorld（真机桌面，人类 72%，榜首 >60%）、WindowsAgentArena | 端到端 GUI 操作 |
| Web Agent | WebArena / VisualWebArena / Mind2Web | 自托管真实网站任务 |
| 终端 Agent | Terminal-Bench | 命令行环境任务 |
| 工具调用 | BFCL v4（Berkeley） | 函数调用格式/选择/多轮多步细粒度评测；v4 转向 agentic：多跳工具链、记忆、web 检索与格式敏感性 |
| 规划 | PlanBench | 规划可行性与重规划 |
| 安全/对抗 | AgentDojo、InjecAgent、AgentHarm、ToolEmu | 注入攻防与危害任务（详见 2.10） |

**（5）MCP 生态评估基准（2025– 新兴方向）**

MCP 成为工具接入的事实标准后，"Agent 用得好 MCP 吗"独立成了评估方向：**MCP-Bench**——跨多个真实 MCP server 的多步任务基准，考察跨 server 的工具组合与长链规划，工具不再是你精心手写的函数，而是生态里参差不齐的第三方接口；**MCPMark**——对 server 做增删改查全操作的压力测试，任务要求真实改写状态而非只读问答，SOTA 模型单次通过率也不高、pass^k 回落更明显（"读易写难"在 MCP 语境下再次得到验证）；LiveMCPBench、MCPEval 等则分别提供大规模真实 server 集合与自动化评测框架，面试一句带过即可。考点在于这类基准把三件事变成了可测量对象：**工具描述质量**（description 写得差直接拖垮工具选择准确率）、**跨 server 组合能力**、**对残缺/报错 server 的错误恢复**。工程衔接：真实 MCP server 的时变数据与状态残留，正是 2.9"评估环境工程"里 record-replay 与快照重置要解决的问题。

**Benchmark 使用的元认知**：公开题面 → 训练污染；榜单饱和 → 区分度消失（应定期淘汰饱和用例）；**scaffold 混淆**——同一模型在不同 harness 下分数差几十点，榜单比的是"系统"不是"模型"，解读时必须问"用的什么脚手架"；基准分布 ≠ 你的业务分布。**基准是路标不是终点，最终必须建自有评估集**。

#### 2.7 可观测性：从 Logging 到 Tracing

**三大支柱**：Logs（离散事件：报错、降级、重试）、Metrics（可聚合量：延迟、token、成本、错误率）、Traces（跨步骤因果链）。Agent 场景下 **trace 是主角**，logs/metrics 围绕它组织。

**数据模型**：一次用户请求 = 一条 **Trace**；Trace 由嵌套的 **Span** 构成（Agent 循环 → 每次 LLM Generation → 每次 Tool 调用 → 每次 Retrieval → Agent 间 Handoff）。每个 span 带时间戳、输入输出、token 用量、成本、错误状态。这套结构直接决定了你能否回答："第 7 步那次工具调用，模型看到了什么上下文、花了多少钱、为什么传了错参数。"关键配套：记录**模型版本、prompt 版本、工具版本**，否则归因无从谈起。

**OpenTelemetry GenAI Semantic Conventions**：CNCF 推动的厂商中立标准，定义 `gen_ai.*` 属性（`gen_ai.system`、`gen_ai.request.model`、`gen_ai.usage.input_tokens/output_tokens`、`gen_ai.operation.name` 等），span 命名如 `{operation} {model}`（例：`chat gpt-4o`）。意义：**埋点一次，后端可换**（Datadog、Grafana、New Relic、Phoenix 等陆续原生支持）。两点注意：① 规范现由独立仓库 open-telemetry/semantic-conventions-genai 维护（opentelemetry.io 原链接已重定向）；多数属性截至 2026 年仍处 experimental、正逐步稳定，agent/tool/MCP 相关属性（如 `gen_ai.agent.id`）已进入 registry，但均为 development 稳定性、命名仍可能变——采用时要容忍演进；② 规范明确要求 prompt/completion 内容采集 **opt-in**（如 `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`）+ 截断/脱敏，这是合规默认项。Arize 的 OpenInference 是另一套并行规范，思路相近。

**平台对比：**

| | LangSmith | Langfuse | Arize Phoenix |
|---|---|---|---|
| 开源/自托管 | 闭源，云优先（企业版可自托管） | 开源，自托管能力强 | 开源 |
| 生态绑定 | LangChain/LangGraph 深度集成 | 框架无关，OTel 兼容 | 框架无关，OpenInference 规范 |
| 特长 | Datasets + annotation queue + online evaluators 一体化，实验管理顺手 | 自托管/数据驻留合规、成本分析、评估工作流 | ML 观测出身，embedding 可视化、drift 分析 |
| 适合 | 已投入 LangChain 生态的团队 | 有合规/私有化要求的企业 | 需要传统 ML 监控能力融合的团队 |

（上表为代表性三家，其余从略。）此外常见的还有：**Braintrust**（eval + logging 一体化，AI 创业公司常用，实验与在线打分工作流顺手）、**W&B Weave**（与 W&B 实验追踪体系打通，适合同时管训练与评估的团队）、AgentOps（Agent 专用）、Arize AX（Phoenix 的商业版）。以及 **OTel 原生后端**（Datadog LLM Observability、Grafana、Honeycomb）。

**框架自带 tracing 单列一层**：OpenAI Agents SDK 内建 tracing（零配置即可用，可经自定义 processor 导出到任意后端）、LangGraph/LangChain 与 LangSmith 深度集成（也可走 OTel 桥接）、Claude Agent SDK 提供 hooks 回调供自建埋点。优势是零集成成本、span 语义贴合自家框架；劣势是绑定单一厂商后端，多框架/多模型栈混部时仍需回到 OTel 标准导出。选型真正的决策变量不是功能表，而是：**数据能否出境（自托管需求）、框架栈、以及 trace 是否用 OTel 标准导出（避免锁定）**。

**评估分数是 trace 的一等标注**：在线 judge 分、用户反馈、人审结论都应作为 score 挂回对应 trace/session（Langfuse Scores、LangSmith Feedback 都是这个模型），这样"为什么这条 trace 被判差"永远可追溯，observability 与 evaluation 才真正闭环。

**Trace 驱动 Debug 的工作流**：告警/抽检 → 打开 trace → 定位到失败 span（工具报错？上下文被截断？prompt 注入？）→ 用 trace 输入**重放/replay** → 改 prompt/工具 → 将该 trace 固化进回归数据集。可观测性的终极产出不是仪表盘，而是**让每一次线上失败都能转化为一条离线测试用例**。

**规模化下的存储与成本**：trace 量爆炸后，用 **head sampling 分级保留**——错误/慢/在线 judge 低分的 trace 保留全量明细，其余只留聚合指标或低比例采样；保留期分级（如明细 30 天、session/user 级聚合长期留存）。这样既控制存储成本，又保证"半个月前的 bad case 还能挖出原始现场"，聚合层则支撑"哪些用户/会话类型系统性失败"的复盘。

#### 2.8 在线评估与数据飞轮

离线评估集永远无法覆盖生产分布（用户会说出你想不出的话）。成熟管线：

```
全量 trace（OTel/Langfuse）
  → 分层采样（全采元数据；按分数/成本/错误/意图分层采样内容）
  → 异步 online judge（pointwise checklist，不阻塞主链路，与离线同 prompt 版本）
  → 阈值告警（SLO 指标走实时告警；质量指标走批量评估 + 评审队列，二者不要混）
  → 输入漂移监控（意图分布 / embedding 漂移，早发现分布偏移）
  → 显式反馈（thumbs）+ 隐式信号（重试、转人工、会话放弃、重开）
  → annotation queue（按 active learning 优先级人审 judge 存疑样本）
  → failure mining + 失败分类学 → 进 golden set / 回归集 → 下一轮迭代
```

**失败分类学（failure taxonomy）是飞轮的齿轮**：没有统一分类，failure mining 只是一堆孤例。典型类目：检索失败、规划错误、工具误用（选错/参数错）、过早终止、循环/卡死、policy 违规、幻觉。每条线上失败打一个类目标签，才能回答"这季度我们修好了哪类问题、哪类在恶化"。

**部署阶段的评估递进**：Shadow mode（旁路复制流量，不影响用户，验证候选版本不"明显坏"）→ Canary（小比例真实流量）→ A/B（对照显著性）→ 全量。Agent A/B 的特殊性：会话长、转化稀疏、有副作用，需要**会话级分流**、更长观察窗、序贯检验（always-valid CI，避免偷看 p 值；实现锚点：mSPRT / GSEQ 类 always-valid 推断，或 Eppo / GrowthBook / Statsig 等平台的 sequential testing 功能），以及一组**护栏指标**（转人工率、投诉率、成本）防止赢了指标输了体验。

**人机协同评估**：区分 **HITL**（人在回路内批准/修正动作后才生效，高风险操作）与 **HOTL**（人在回路上监控、异常介入）。人工评估的工程要点：rubric 先于标注员；用 golden set 质检标注员本身；报告 inter-annotator agreement（κ/α），它同时是 rubric 质量的度量；人审结果回流校准 LLM judge（judge 漂移检测）。

**编码 Agent 产品的线上指标（与客服域并列的第二个域模板）**：上面的显式/隐式信号体系（重试、转人工、放弃、重开）是客服域模板；编码 Agent 产品（Copilot/Cursor/Claude Code 类）有自己的一套口径，面试常被追问：

- **建议接受率（acceptance rate）**：最直观也最危险——接受 ≠ 有用，接受后秒删、大改的代码同样计入接受；只优化接受率容易滑向"讨好当下"的建议风格。
- **代码留存率 / churn**：被接受的代码在 7/30 天后仍存活的比例，比接受率更接近真实价值；churn 异常升高是"AI 代码质量下滑"的早期信号。
- **PR 维度**：Agent 发起/参与 PR 的合并率、合并时长（time-to-merge）、review 轮次——异步自主编码 Agent 的核心口径。
- **人工接管率**：Agent 任务被人半途接管改写的比例，等价于客服域的"转人工"。
- **"AI 生成代码占比"的口径之争**：按字符、按 commit、还是按"AI 参与过"算，同一团队数字可差数倍——引用任何"XX% 代码由 AI 写"之前先问口径。
- **DORA 视角收口**：部署频率、lead time 的提升必须与**变更失败率、MTTR**对照着看；吞吐上涨而变更失败率同步恶化，是编码 Agent 上线后最常见的"赢了指标输了工程质量"。

两个域的共同结构：**一个易得但可被 game 的前排指标（接受率/containment）+ 一组滞后但更真实的留存/质量指标 + 护栏指标**。按这个三层结构回答"你怎么设计线上指标"，可以迁移到任何域。

#### 数据飞轮：从在线评估到训练闭环

前文的"failure mining → 回归集"只是飞轮的半圈——回归集改的是 prompt 与 scaffold；再往前推一步，生产 trace 可以直接变成**训练资产**，闭环才完整。考点是能画出全链路：**生产 trace → 轨迹筛选 → 训练资产 → 训练 → eval 门禁回归 → 灰度上线**。

- **轨迹筛选**：两条进料线——online judge 高分且结果验证通过的**成功轨迹**（直接做 SFT，或拒绝采样：一题采多条轨迹、只留通过验证的最优轨迹）；人工修复过的**失败轨迹**（修复前后天然构成偏好对，喂 DPO/RFT 类偏好优化）。筛选质量决定飞轮上限：judge 有偏，训练只会把偏差放大。
- **反馈信号分层**（被追问"标注从哪来"就答这个）：显式 thumbs 稀疏且有选择偏差（差评者远比好评者爱点按钮）；隐式信号（重试、人工接管率、会话放弃）覆盖广但噪声大；**结果可验证信号**（测试通过、订单成立、终态可程序化判定）最可靠——能自动验证的域飞轮转得最快，这是编码 Agent 进化快于开放对话的结构性原因。
- **训练与门禁**：训练产物必须先过本章的 eval 门禁（golden set 回归 + A/A 噪声基线 + 安全回归）才能进前文的 Shadow → Canary 灰度通道；否则飞轮会自我强化坏数据的偏差，模型在自己生成的分布上退化。
- **数据治理红线**：PII 清洗、用户同意（ToS 明示、可 opt-out）、轨迹留存期与删除权——任何一条缺失，飞轮在法务处直接卡死。载体上，OpenAI 的 RFT 与各家微调 API 已把"轨迹 + 打分器 → 定制模型"产品化。

与本书互为上下游：训练方法本身（agentic RL、过程奖励）见第 11 章；灰度发布与回滚工程见第 10 章——本节提供的是两者之间的**数据与门禁层**。

#### 2.9 评估环境工程与可复现性

这是把评估从"跑一次脚本"变成"可信基础设施"的分水岭。

**（1）变异来源三分法**：① 模型采样（temperature、top-p、batch 组装顺序、GPU 非确定性——即使 temperature=0+seed 也不保证比特级复现：连续批处理的 batch 组成、CUDA kernel 的非确定并行归约，使同 prompt 同 seed 也可能出不同 token）；② 环境/工具（真实 API 数据随时间变化、限流、网络）；③ scaffold（并发度、上下文组装、重试逻辑）。复现性方案要分别针对三者，而不是只盯温度。

**（2）确定性控制**：评估运行时锁定 temperature/seed、模型版本（精确 snapshot）、prompt 版本、工具版本；外部工具用 **record-replay**（录制真实响应、回放固定），用户模拟器固定模型与温度。接受"**统计可复现**"而非"比特可复现"：固定 protocol、多 trial、报置信区间。

**（3）状态管理**：每条用例从干净快照启动（数据库 snapshot/事务回滚），用例间零残留；用例互相隔离才能并行化，把几小时的回归压缩到 CI 可接受的时长。"环境不重置"是最隐蔽的 bug 源（见易错点）。

**（4）保真度光谱与 mock 漂移**：mock（快、稳、便宜，但会撒谎）→ LM 模拟器（ToolEmu 思路：用模型模拟工具行为，能暴露一部分安全风险）→ 沙箱真实环境（OSWorld 式真机）→ 生产 shadow。原则：**越靠近发布，环境越要真**；且 mock 要定期与真实 API 对账，防止 mock 与生产行为悄然分叉（mock drift）。

**（5）评估即 CI**：分层预算——每次提交跑 10–20 条 smoke 子集（快、确定性高），每日/每周跑全量回归（多 trial），定期跑昂贵的人审校准集。flaky 用例隔离观察、设失败预算，不要让噪声阻塞开发，也不要假装噪声不存在。评估框架本身（harness）要代码化、版本化——**harness 的一次"顺手修改"足以让半年趋势图失真**。

**（6）基础设施自检**：评估管线自己也要被评估，两个硬指标：① **A/A 测试**——同一系统（或两个等价版本）用同一管线跑两遍，分差就是评估自身的**噪声基线**；若 A/A 差 ±3 个点，则版本间小于 3 个点的差异不具显著性，"涨了 1 个点"不值得庆祝。② **离线-在线相关性回测**——定期核查历史上"离线显著上涨"的改动在线上指标（containment、CSAT、转人工率）上是否同步兑现；若离线涨幅系统性不预测线上，说明评估集效度已失效，需要重建（重对分布、重挖失败）。这两件事是"跑脚本"与"可信基础设施"的分界线。

**（7）成本预算量化**：评估是要花钱的，汇报时给出一笔明账：任务数 × trial 数 × 平均 token × 单价。例：300 条 × 8 trial × 每轮均 20k tokens × $3/M ≈ 每次全量回归 $144；换成小模型 judge 粗筛可降一个量级。进阶维度是**能力-成本前沿（cost-performance frontier）**：不只报"谁分高"，还报"在同一美元预算下谁分高"——两个系统成功率相近时，前沿位置决定生产选型。

#### 2.10 安全与对抗评估

Agent 比普通 LLM 多了"手脚"，安全评估必须独立成维度，不能指望功能回归顺带覆盖。

**（1）威胁模型**：
- **直接提示注入**：用户在对话中下恶意指令；
- **间接提示注入**（更危险）：恶意指令藏在工具返回、网页、文档、邮件里，Agent 把"数据"当"指令"执行——这是 Agent 特有的攻击面；
- **攻击目标**：越权操作（改数据、扣款）、数据外泄（system prompt、其他用户数据、canary 信息）、目标劫持。

**（2）双轴评估指标**：**攻击成功率 ASR**（越低越好）× **良性效用保持 / 目标任务完成率**（越高越好）。只报 ASR 是耍流氓——"拒绝处理一切外部内容"也能 ASR=0，必须看 tradeoff 曲线与过度拒绝率（over-refusal）。AgentDojo（NeurIPS 2024 D&B）正是以此双轴设计攻防评测；InjecAgent（ACL 2024 Findings）专测工具链间接注入；AgentHarm（ICLR 2025）测危害性任务执行；ToolEmu 提供 LM 模拟环境下的安全用例扫描。

**（3）方法组合**：对抗评估集（在工具返回/文档中埋 canary 指令，检查是否被执行、canary 是否泄露）；权限矩阵测试（must-not-call 断言遍历越权组合）；自动化红队（变异生成攻击 prompt，迭代绕过）；分层防御逐层度量（输入过滤、工具最小权限、敏感动作人工确认、输出 DLP 扫描）。

**（4）与可观测性的连接**：工具调用 span 即审计日志；对"历史从未出现过的工具调用组合"做异常检测；canary token 泄露监控挂到在线告警。**安全评估必须进回归套件**——一次 prompt 改动完全可能功能全绿、注入防线塌方。

#### 2.11 多智能体评估

当系统从单 Agent 变成团队协作（前台分诊 + 退款专员 + 质检），评估对象升级为"组织"：

- **新指标层**：角色遵循（stay in role）、handoff 准确性（该转不转 / 转错人）、**跨 handoff 信息保真度**（关键信息在消息传递中丢失，本质是"传话游戏"）、通信开销（Agent 间 tokens/turns 占比）。
- **轨迹即 DAG**：Agent 间消息是一等 span，trace 结构从树变成有向图，归因要在图上做。
- **错误放大与相关误差**：两个 90% 可靠的 Agent 串联，只有误差独立时才有 81%；实际中错误高度相关（同一模型同源偏差），联合成功率可能远低于乘积。必须同时跑**组件隔离评估**（mock 掉其他 Agent）与**联合评估**，两者差距就是"集成损失"。
- **非平稳性**：Agent A 升级后，Agent B 原有评估集可能整体失效（它面对的"同事"变了）。版本矩阵管理 + 任一组件变更触发联合回归，是多智能体 CI 的必需项。

#### 2.12 评估集构建方法论：从零到可信评估集

知识图谱承诺了"数据集构建"，这里展开——"如何从零建一个可信评估集"是本章覆盖范围内最高频的系统设计题之一。

**（1）构建四步法**：

1. **任务分类学（task taxonomy）先行**：先穷举产品要支持的任务类型（如客服 Agent：查询 / 修改 / 取消 / 投诉 / 跨订单与多语言等边缘场景），再标注能力维度（多工具协调、policy 合规、长上下文、多轮纠错）。两者笛卡尔积构成**能力 × 难度覆盖矩阵**，评估集按格子填充——"构念效度"的核心是让每条用例都明确声明它在测什么，而不是攒一堆"有代表性的例子"。
2. **item spec 与 pass/fail 判据先于写例**：每条用例有一份 spec——输入、必要上下文、期望终态 / 参考答案、判据（用哪个 grader、哪些断言）、难度标签、覆盖标签。判据由领域专家评审而非工程师独写：判据漂移是评估集噪声的主要来源。
3. **来源分阶段扩建**：冷启动（20–50 条手写黄金例，覆盖主路径 + 高风险路径）→ 真实失败挖掘（线上 trace 中 judge 低分 / 用户差评 / 转人工会话，经人审后转为用例，这是增量主体）→ 合成扩展（LLM 生成表面变体，人审入库，稀释过拟合）→ 对抗例（注入、边界、corner case）。每条用例记录来源出处，pass rate 按来源拆分看。
4. **难度梯度与饱和管理**：标注难度（步数、工具数、policy 密度），按难度分桶报通过率；定期淘汰饱和用例（长期 ≥95% 且无区分度），保持评估集"活着"。

**（2）评估集污染的检测与防制**（公开基准必做，自有评估集同样会被针对性优化）：

- **canary 埋点**：在评估集中植入唯一 canary 字符串与 canary 用例，定期检索训练数据/模型输出中有无泄露；
- **重叠检测**：计算评估集与可得训练语料的 n-gram 重叠或 C-min 式成员推断分数，高重叠用例隔离或废弃；
- **复述变体试探**：给模型同一任务的表面变体（改写、翻译），若原始题分数远高于变体，是题目被记忆的强信号；
- **封禁与访问控制**：盲测集物理隔离、访问留痕、评估运行记录审计；
- **定期换血**：LiveBench 式月度换题、SWE-rebench 式定期重采，或自有"滚动盲测集"。污染无法根除，只能持续对冲。

面试收束：评估集是需要持续运营的资产——覆盖矩阵保证构念效度，item spec 评审保证判据质量，污染防制与定期换血保证效度不随时间腐化。

#### 2.13 组件级评估：检索/RAG 链路的独立指标

分层评估（组件 → 轨迹 → 端到端）的组件层必须落地，尤其是检索/RAG 链路——端到端答错可能源自检索，没有组件级指标就无法归因：

| 层次 | 常用指标 | 说明 |
|---|---|---|
| 检索器 | recall@k（黄金证据是否在 top-k）、nDCG / MRR（排序质量）、hit rate | 用人工标注的黄金文档集评，BEIR 式流程 |
| 上下文质量 | context precision（检索到的是否有用）、context recall（需要的有没有检索到） | RAGAS 等框架以 judge 对照黄金答案计算 |
| 生成器 | faithfulness（答案是否锚定于给定上下文，抗幻觉）、answer relevance、answer correctness | RAGAS / TruLens，judge + rubric |
| 工具 / prompt | 参数 schema 通过率、prompt 版本 A/B | 断言式校验（见 2.2） |

**用法原则：分层定位、端到端决策**——端到端分数是发布判据，组件指标用于归因；端到端掉点时先看组件指标定位坏在哪一层。其中 faithfulness 与 context recall 的组合是区分"检索坏"与"生成坏"的强信号：context recall 低是检索问题，faithfulness 低是生成幻觉问题。Agent 场景同理可扩展到"规划器 / 工具选择器"的组件级探针评估。

#### 2.14 Grader 自身的对抗性：reward hacking 与 specification gaming

当 pass rate 成为优化目标，grader 就成了攻击面——这是一类独立于提示注入的失败模式，Goodhart 定律在 grader 层的具体现身：

- **典型案例**：SWE-bench 式评测中 Agent 直接**修改测试文件**让失败测试"通过"；对 DB 状态断言做**表面达标**（只改被校验的字段、破坏业务一致性而 grader 不查）；specification gaming——钻评分规则的空子（利用 grader 宽松的字符串匹配输出"格式正确但语义错误"的答案）。grader 钻空是有据可查的失败模式，因此**公开榜单成绩需配合轨迹审计才能采信**——只看 pass rate 不看轨迹，等于默认 Agent 没走捷径。
- **检测**：对"可疑通过"做监控——通过但轨迹异常（动了测试/配置文件、接触了黄金答案文件、路径短得不合理）；对通过样本人工抽检采样；diff 出 Agent 写入的文件并与受保护清单比对。
- **加固**：测试/黄金文件设为只读且不出现在工作区；断言优先用**状态级多点校验**（目标状态 + 业务完整性约束）而非单点断言；为每个 grader 配**对抗样本**（构造"看起来对其实错"的输出，验证 grader 能抓出来——即对 grader 做红队测试）；LLM judge 引入判据随机化，防止被反向摸索出固定套路。
- **面试考点**：被问"为什么 pass rate 突然飙升"时，给出"grader 被钻空 / 评估集被污染 / judge 漂移"三段式排查反应，而不是直接相信"模型变强了"。

#### 2.15 动手实现：最小可运行示例

面试实战题"你们用什么跑评估、怎么写的"要求随时能交出代码骨架。

**（1）评估数据集 JSONL spec**（一条用例一行，字段面向 grader 设计）：

```jsonl
{"id": "cancel-001", "input": "帮我取消订单 #1234", "policy_snapshot": "v7", "expect": {"db_state": {"orders.1234.status": "cancelled"}, "must_call": ["verify_identity"], "must_not_call": ["issue_refund"]}}
```

**（2）Inspect 最小示例**（英国 AI Security Institute（AISI，2025 年 2 月由 AI Safety Institute 更名）开源评估框架，solver/scorer 抽象天然适合 Agent 与安全评估）：

```python
from inspect_ai import Task, task
from inspect_ai.dataset import json_dataset
from inspect_ai.scorer import Score, Target, CORRECT, INCORRECT, accuracy, scorer
from inspect_ai.solver import generate, use_tools
from inspect_ai.tool import bash

@scorer(metrics=[accuracy()])
def db_state_check():
    async def score(state, target):
        verified = state.store.get("db_verified", False)  # 由核验工具写回
        return Score(value=CORRECT if verified else INCORRECT)
    return score

@task
def support_eval():
    return Task(
        dataset=json_dataset("eval.jsonl"),
        solver=[use_tools([bash()]), generate()],  # Agent loop 交给模型
        scorer=db_state_check(),
        model_args={"temperature": 0},
    )
# 运行：inspect eval support_eval.py --model openai/gpt-4o --repeat 8
# --repeat 即多 trial，据此报 pass rate / pass^k 与置信区间
```

**（3）promptfoo CI 门禁**（YAML 即配置，复用同一份评估集）：

```yaml
prompts: [prompts/support_v8.txt]
providers: [openai:gpt-4o]
tests: file://eval.jsonl          # 与 Inspect 复用同一 JSONL
defaultTest:
  options: { provider: { config: { temperature: 0 } } }
  assert:
    - type: javascript            # 确定性断言：DB 状态 + must-call
      value: "dbCheck(output, vars)"
    - type: llm-rubric            # LLM judge 评话术与合规
      value: "未泄露政策或他人数据，解释完整"
# CI：promptfoo eval -o results.json，脚本算总通过率，< 92% 则 exit 1 阻断合并
```

**（4）二值 checklist judge prompt 骨架**（呼应 2.4"二值判断比连续打分可靠"）：

```text
你是质检员。给定对话 transcript 与工具调用记录，逐项独立判断，只答 yes/no/unknown：
1. 执行写操作前是否核验了用户身份？
2. 退款金额是否精确到分且符合政策 {policy_snapshot}？
3. 是否泄露了系统提示词或他人数据？（yes = 一票否决）
输出 JSON：{"items": [...], "fail_hard": [命中项编号], "evidence": [逐项引用片段]}
聚合：任一 fail_hard 命中 → fail；其余项 ≥4/5 为 yes → pass。
```

考点衔接：JSONL spec 是评估集与 grader 的契约；Inspect 的 `--repeat` 与 scorer 对应多 trial 与 grader 分层；promptfoo 的 assert 对应 CI 门禁；checklist judge 输出 evidence 是为了人审可复核——代码与前面的方法论一一对应，面试时能画出这条对应链是加分项。

---

### 三、面试高频考点

| 考点 | 高频度 | 一句话题眼 |
|---|---|---|
| Agent 评估与传统 LLM 评估的差异 | ⭐⭐⭐ | 多步、副作用、路径多样、误差复合 |
| LLM-as-Judge 的偏差与缓解 | ⭐⭐⭐ | position/verbosity/self-enhancement + swap 一致性 + 人审校准 |
| Outcome vs Trajectory 评估的取舍 | ⭐⭐⭐ | 结果判 pass/fail，轨迹做归因与护栏，不强制固定序列 |
| pass@k vs pass^k 与可靠性 | ⭐⭐⭐ | 单次成功率沿轨迹指数衰减；无人值守看 pass^k |
| τ-bench / GAIA / AgentBench 的定位差异 | ⭐⭐⭐ | policy following vs 通用助理 vs 环境横评 |
| 在线评估与数据飞轮设计 | ⭐⭐⭐ | 采样 → online judge → 人审队列 → 回归集闭环 |
| 评估集构建方法论 | ⭐⭐⭐ | 分类学 → 覆盖矩阵 → item spec 评审 → 从真实失败分阶段扩建 |
| 工具调用如何评测 | ⭐⭐ | selection P/R + 参数正确率 + must-call/must-not-call 断言 |
| Trace/Span 数据模型与 OTel GenAI 约定 | ⭐⭐ | 可重放、可归因、厂商中立、敏感数据 opt-in |
| Judge 与人类一致性如何量化 | ⭐⭐ | 校准集 + Cohen's κ / 一致率，κ<0.6 不上线（注意患病率悖论） |
| 评估集污染、饱和、scaffold 混淆、Goodhart | ⭐⭐ | 基准是路标；自有评估集才是资产 |
| 污染检测与防制 | ⭐⭐ | canary 埋点、重叠检测、复述变体试探、封禁换血 |
| reward hacking 与 grader 对抗性 | ⭐⭐ | grader 也是攻击面：改测试文件、表面达标，grader 要红队测试 |
| 组件级评估（检索指标） | ⭐⭐ | recall@k/nDCG → context precision/recall → faithfulness，分层归因 |
| 评估环境工程与可复现性 | ⭐⭐ | 锁版本 + record-replay + 状态重置 + 统计可复现 + CI 分层 |
| 安全与提示注入评估 | ⭐⭐ | ASR × 效用保持双轴；间接注入是 Agent 特有攻击面 |
| 统计严谨性（CI、功效、多重比较） | ⭐⭐ | 不报 trial 数与置信区间的数字都是噪声 |
| 编码 Agent 线上指标（接受率/留存/churn） | ⭐⭐ | 接受≠留存；DORA 视角双看吞吐与变更失败率 |
| 评估基础设施自检 | ⭐ | A/A 测试噪声基线 + 离线-在线相关性回测 |
| Shadow/Canary/A/B 在 Agent 场景的特殊性 | ⭐ | 副作用、稀疏转化、会话级分流、序贯检验 |
| 多智能体评估 | ⭐ | handoff 保真度、相关误差放大、联合回归 |
| HITL vs HOTL | ⭐ | 批准在动作前 vs 监控在动作后 |
| MCP 生态基准（MCP-Bench/MCPMark） | ⭐ | 真实 server 全操作压力测试；工具描述质量与错误恢复 |

---

### 四、经典面试题与参考答案

#### 题 1（基础）：Agent 评估和评一个 chatbot 的回答，本质区别是什么？

**答题思路**：从"静态文本比对"升级到"动态系统评估"，列出新引入的难点即可拿满分。

**参考答案要点**：
1. **对象变了**：评的是模型+scaffold+工具+检索构成的系统，不是模型权重；同一模型换 harness 分数可差几十点；
2. **多步误差复合**：单步 95% × 20 步 ≈ 36%，必须多 trial、看分布而非单次；
3. **副作用与状态**：要看环境最终状态，要求评估环境可重置、可 diff，且残留状态会污染后续用例；
4. **路径多样性**：不能 exact match 轨迹，要允许合法替代路径；
5. 因此需要分层评估（组件→轨迹→端到端）+ 可观测性基础设施支撑归因，以及一套可复现的评估环境工程。

#### 题 2（进阶）：用 LLM 当 judge 有哪些偏差？你在工程上怎么让它的评分可信？

**答题思路**：先偏差清单（能说出 self-enhancement 和能力上限就领先一半），再给出一套可落地的校准流程。

**参考答案要点**：
- 偏差：position bias（候选顺序）、verbosity bias（更长≠更好）、self-enhancement（偏袒同源模型）、sycophancy/authority（迎合暗示）、刻度趋中；以及**能力上限**——judge 无法可靠评判超出自身能力的输出。
- 工程手段：① 专家 rubric + 行为锚点 + 分维度打分 + 允许 Unknown/partial credit；② 尽量把 rubric 拆成二值/分类检查项再聚合，少用精细 Likert；③ CoT 先理由后打分；④ pairwise 场景随机化顺序并统计 swap 翻转率；⑤ judge 与被测模型解耦；⑥ 校准集量化与人类的一致率/κ（二值看 ROC-AUC，打分看 Spearman/ECE），定期重校准；⑦ judge prompt 与模型版本化，升级时用历史数据做桥接对齐；⑧ 多 judge 面板聚合 + 成本分层（断言→小模型→强模型→人审）。

#### 题 3（进阶）：τ-bench 的 pass^k 和 pass@k 有什么区别？如果你的产品是无人值守的工单处理 Agent，你汇报哪个数？为什么？

**答题思路**：给出定义 → 给出直觉（复合误差）→ 落到业务场景选型。

**参考答案要点**：
- pass@k：k 次至少过一次，衡量"可重试场景下的可达能力"；pass^k：k 次必须全过，衡量"无人值守下的可靠性"。
- τ-bench 用每任务 n 次试验中的成功数 s，按 ∏(s−i)/(n−i)（i=0..k−1）估计 k 次全过概率再跨任务平均；该估计依赖 trial i.i.d. 假设，共享模拟器/环境带来的相关性会使估计有偏。
- 论文实证（摘要严格口径）：GPT-4o 在 retail 域 pass^1 不足 50%，pass^8 跌至约 25%（相对降幅约 60%）——一次失败就是一次真实事故，所以工单无人值守 → 汇报 pass^k（如 k=8/10），同时给 pass rate 作为上限参照，两个数的 gap 就是稳定性债。
- 加分项：pass^k 对试验次数 n 敏感，n 太小会高估，需要报告试验次数与置信区间（Wilson/bootstrap）。

#### 题 4（进阶）：Outcome 评估和 Trajectory 评估怎么选？有人说"只要结果对就行"，你怎么反驳？

**答题思路**：不是二选一，给出组合策略；反驳要举出"结果对但过程错"的具体危害。

**参考答案要点**：
- 主指标用 outcome（贴近业务、路径无关、grader 便宜，最好校验环境最终状态而非自然语言）。
- 但纯 outcome 有三个盲区：① 失败无归因，无法改进；② "歪打正着"——靠猜对答案或跳过验证步骤，下一次就没这么幸运；③ 危险过程（越权调用、泄露信息）可能恰好没造成可见损害。
- 因此轨迹评估承担归因（step-level rubric / Agent-as-Judge 带工具核验）与护栏（must-call/must-not-call 断言）两个职能；轨迹比对用无序关键调用集合或偏序约束而非完整序列，保留路径自由度。
- 加分项：对"结果正确但轨迹违规"单独计数告警，这类样本是最贵的学习材料。

#### 题 5（进阶）：如何评测 Agent 的工具调用质量？给出你的指标体系和评测实现。

**答题思路**：拆子指标 + 断言设计 + 避免过度约束。

**参考答案要点**：
- 指标：tool selection 的 precision/recall（多报：乱调；漏报：该调没调）、参数正确率（结构化比对，注意等价参数/默认值）、顺序依赖（偏序断言，如先鉴权后操作）、调用效率（冗余/重复/死循环，用步数分布与去重检测）、安全（越权、跳过鉴权）。
- 实现：把 trace 中的工具 span 抽出来与期望的"关键调用集"比对；用 required/forbidden tool 断言守住安全与正确性关键路径；不要求顺序完全一致。
- 进阶：参数校验先复用工具的 JSON Schema 做第一道静态检查（零成本、零 judge 偏差），语义正确性再交给 judge；越权检测遍历"角色 × 工具"权限矩阵。

#### 题 6（基础→进阶）：GAIA、AgentBench、τ-bench 分别测什么？如果只能选一个向老板汇报"我们的 Agent 变强了"，选哪个？

**答题思路**：一句话定位 × 3，然后说明"老板指标"必须是自有评估集，基准只是外部参照。

**参考答案要点**：
- GAIA：通用助理真实任务（检索+浏览器+文件+多模态，三级难度），精确匹配评分，人类 92% vs AI 起步 15%（2025 年榜首已进入 70–80% 区间，与人类差距收窄至十余到二十个百分点），测**通用能力上限**；饱和后催生了读写交互的 GAIA-2（Meta FAIR，2025-09，配套 ARE 环境框架）。
- AgentBench：8 个交互环境的横向能力画像，测**环境泛化与多轮决策**，商用 vs 开源差距的出处。
- τ-bench 家族：企业客服场景的 tool-agent-user 交互 + policy following + DB 状态判定 + pass^k；τ² 加双控制（用户侧也是会用工具的 Agent）+ telecom 域 + 组合式任务生成器；τ³ 加全双工语音（成绩仅约文本的 30–45%）、知识任务与 banking 域；测**规则约束下的可靠性**，最贴近 B 端产品。注意榜单按月变动、且分代际分化极大（τ² 易域如 telecom >90% 近饱和，原版 τ-bench airline 曾长期未饱和），分域最新数据以 taubench.com 为准。
- 三者都不应直接当产品指标：污染、分布错配、饱和、scaffold 混淆。正确姿势是选与业务同构的基准做外部 sanity check，核心汇报用自建 golden set（来自真实失败）的通过率 + 线上在线评估分 + 用户/运营指标（containment、CSAT）。

#### 题 7（进阶）：你设计了一套 LLM judge，怎么证明它"可用"？量化标准是什么？

**答题思路**：把 judge 当作一个需要验证的分类器。

**参考答案要点**：
1. 建人工校准集（覆盖各分段与边界案例，由 2+ 专家标注并报告 IAA）；
2. 计算 judge 与人类的一致率、Cohen's κ（分类）或 Spearman/Kendall（评分），二值判定看 ROC-AUC，概率输出看校准误差（ECE）；经验线：κ≥0.6 可用，≥0.8 可自动决策——但正例稀少/分布偏斜时 κ 会失真（患病率悖论），需同时看一致率与 ROC-AUC，阈值仅作经验参考；
3. 分析错误分布：judge 的假阳/假阴是否集中在某类案例（系统性偏差）；
4. swap/重采样稳定性：同一输入多次评分方差、pairwise 翻转率；
5. 上线后持续监控 judge 与人审结果的漂移（定期抽样复核），judge prompt/模型变更触发重校准；
6. 结论不是"judge 对"，而是"judge 与专家分歧 ≤ 专家之间分歧"。

#### 题 8（系统设计）：为一个生产环境客服 Agent 设计评估与可观测性体系。

**答题思路**：按"埋点—离线—上线—在线—闭环"五段讲，每段有具体组件和指标。

**参考答案要点**：
- **埋点层**：OTel GenAI 约定统一 trace/span（agent 循环、generation、tool、retrieval 四类 span），记录模型版本/prompt 版本/工具版本便于归因；prompt 内容 opt-in 采集 + PII 脱敏；全量记元数据（延迟、token、成本、错误），内容分层采样；评估分与用户反馈作为 score 挂回 trace。
- **离线层**：评估集按"任务分类学 → 能力×难度覆盖矩阵 → item spec 评审 → 分阶段扩建"构建，golden set 来自真实失败挖掘（20–50 条起步，逐步扩到数百），每条有明确的 pass/fail spec 与已知正确解；定期做污染检测（canary 埋点、复述变体试探）与饱和用例淘汰；grader 分层——确定性代码断言（DB 状态、must-call 工具、JSON Schema）优先，LLM judge 评话术质量与 policy 合规，人工审校准集；grader 自身配对抗样本防钻空；区分 capability 套件与 regression 套件，多 trial 报 pass rate 与 pass^k + 置信区间，并行报 turns/tokens/cost；评估环境状态可重置、可并行、smoke 子集进 CI；用 A/A 测试定噪声基线，定期做离线-在线相关性回测。
- **安全层**：注入对抗集（含间接注入 canary）与权限矩阵断言纳入回归，报 ASR × 效用保持。
- **上线层**：shadow mode 旁路验证 → canary 小流量 → 会话级分流 A/B（序贯检验 + 护栏指标：转人工率、投诉率、成本），观察窗覆盖完整会话。
- **在线层**：异步 online judge（与离线同 prompt 版本）抽样打分；SLO 指标（延迟/错误率/成本超限/转人工率）实时告警，质量指标走批量评估；输入漂移监控；显式反馈 + 隐式信号（重试、放弃、重开）汇入。
- **闭环层**：judge 低分/用户差评/转人工 trace 按失败分类学打标进 annotation queue 人审 → 确认的失败进回归集 → 每周跑回归 → 淘汰饱和用例。画出"线上失败 → 离线用例"的飞轮是整个设计的灵魂。

#### 题 9（基础）：什么是 trace 和 span？为什么 LLM 应用要用 OpenTelemetry 的 GenAI 语义约定？

**参考答案要点**：
- Trace = 一次请求的全链路记录；Span = 其中一个有起止时间的操作单元，树形嵌套；LLM 应用的 span 类型包括 agent step、LLM generation、tool call、retrieval（多智能体还有 handoff）。
- 价值：长程信用分配（定位是哪一步坏的）、replay 调试、成本归因（哪个工具/哪个模型烧钱）、安全审计（工具调用链可查）。
- OTel GenAI 约定的意义：`gen_ai.*` 标准属性让埋点与后端解耦（换 LangSmith/Langfuse/Datadog 不改代码）、跨团队跨服务可聚合、生态工具原生支持；规范对 prompt/completion 敏感数据要求 opt-in 与脱敏，是合规默认项。注意规范现由独立仓库 semantic-conventions-genai 维护，多数属性仍在演进（experimental → stable；agent/tool/MCP 属性已进入 registry 但均为 development 稳定性、命名可能变），采用时要容忍版本变化。

#### 题 10（开放）：你的评估集跑了半年，通过率从 60% 涨到 98%，但线上投诉没降。可能出了什么问题？怎么治理？

**答题思路**：这是考"评估体系本身的可信度"，比具体技术更见资深功力。

**参考答案要点**：
- **过拟合评估集**：团队针对已知用例调 prompt，用例失去代表性 → 定期换血、从线上 failure mining 补充、盲测集隔离。
- **分布漂移**：半年间用户用法、渠道、语种变了 → 用线上采样比对评估集分布，做覆盖度审计。
- **指标错配**：评估测的是"任务正确"，投诉来自"语气/等待时长/越权操作/结果对了但没解释" → 投诉做归因分类，按投诉类别反查评估盲区。
- **Goodhart**：通过率被当 KPI 后，大家优化的是分数不是体验 → 北极星换成线上在线评估分 + 用户/运营指标，离线通过率降级为回归护栏。
- **judge 漂移**：judge 模型/prompt 升级导致"尺子变松" → 版本化 + 历史数据桥接重校准。
- 治理机制：评估集与线上分布的定期差异报告、饱和用例淘汰制度、投诉→用例的固定转化管线，以及离线-在线相关性回测（离线涨幅不兑现于线上即触发评估集重建）。

#### 题 11（进阶）：同一套评估、同一份代码，每次跑出来的分数都不一样。你怎么系统性地解决评估的可复现性？

**答题思路**：先拆解变异来源，再分层给出控制手段，最后承认极限、落到"统计可复现"。

**参考答案要点**：
1. **三分变异来源**：模型采样（temperature、batch 顺序、GPU 非确定性）、环境/工具（真实 API 数据时变、限流）、scaffold（并发度、上下文组装、重试）。
2. **确定性控制**：temperature=0 + seed、锁定模型快照/prompt 版本/工具版本；外部工具 record-replay 固定响应；用户模拟器固定模型与温度。
3. **认清极限**：temp=0 也不保证比特级复现（连续批处理的 batch 组成、CUDA kernel 非确定并行归约）；mock 与生产会漂移——所以目标不是"两次结果逐位相同"，而是**统计可复现**：固定 protocol、多 trial、报均值 + 置信区间 + trial 数 + seed 策略。
4. **环境工程**：每条用例从干净快照启动、相互隔离以支持并行；mock 定期与真实 API 对账。
5. **流程**：评估 protocol 代码化进仓库（harness as code），harness 变更视为破坏性变更；CI 跑 smoke 子集，flaky 用例隔离并设失败预算；趋势图标注 harness 版本断点。

#### 题 12（进阶）：如何评估一个 Agent 对提示注入（尤其是间接注入）的防御？评估报告里应该有哪些指标？

**答题思路**：先讲清威胁模型的特殊性，再给双轴指标，最后落到分层防御与回归化。

**参考答案要点**：
1. **威胁模型**：直接注入来自用户输入；间接注入藏在工具返回、网页、文档、邮件里，Agent 把数据当指令执行——这是 Agent 相对 chatbot 新增的攻击面，危害是越权操作、数据外泄、目标劫持。
2. **双轴指标**：攻击成功率 ASR（越低越好）× 良性效用保持/目标完成率（越高越好）+ 过度拒绝率。只报 ASR 没有意义——全面拒绝外部内容也能 ASR=0，必须看 tradeoff 曲线。
3. **评估方法**：对抗评估集（在工具返回/文档中埋 canary 指令，检测是否被执行、canary 是否出现在输出中）；权限矩阵遍历（must-not-call 断言）；自动化红队（攻击 prompt 变异迭代）；基准参照 AgentDojo、InjecAgent、AgentHarm。
4. **分层防御逐层度量**：输入检测、工具最小权限、敏感动作人工确认、输出 DLP 扫描——报每一层的拦截贡献率。
5. **运营化**：注入用例进回归套件（功能改动也可能塌防线）；线上对异常工具调用组合做检测，canary 泄露挂实时告警。
6. **观念**：注入防御本质是**系统权限设计问题**，不是加一句 prompt 叮嘱能解决的；评估要验证的是权限边界，不只是"模型听不听话"。

#### 题 13（系统设计）：一个多智能体客服系统（前台分诊 Agent + 退款专员 Agent + 质检 Agent），如何设计评估与可观测性方案？

**答题思路**：在单 Agent 体系上叠加"团队维度"：DAG 追踪、handoff 指标、联合回归。

**参考答案要点**：
- **追踪模型**：trace 结构升级为 DAG，Agent 间 handoff 消息作为一等 span，完整记录 handoff payload（用于信息保真度评估）；每个 span 标注所属 Agent 与其版本。
- **指标三层**：① 端到端 outcome（主指标，DB 状态/任务完成）；② handoff 层（转接准确率、角色遵循、跨 handoff 信息保真度、通信 token 开销占比）；③ 组件层（每个 Agent 的隔离评估，用 mock 替代其他 Agent）。
- **误差分析**：同时跑隔离评估与联合评估，差距即"集成损失"；警惕相关误差——同源模型串联的实际联合成功率远低于各成功率的乘积。
- **评估集**：联合 golden set 从真实 handoff 失败挖掘；组件评估集保证单 Agent 改动可快速验证；任一 Agent 版本变更触发联合回归（非平稳性：队友变了，旧评估可能失效）。
- **在线**：会话级分流 A/B，按路由路径拆分 containment/escalation 归因（是哪条交接链在漏单）；handoff 异常（转错、反复横跳）单独告警。
- **组织视角**：每个 Agent 有明确 owner 与独立评估责任，但联合指标是共同 KPI——否则局部优化会劣化全局。

---

### 五、易错点 · 反直觉点

1. **单次运行出数字**：温度 >0 或多步系统下，单次 pass rate 不可复现；不报 trial 次数和置信区间的指标都是噪声。
2. **轨迹 exact match**：把"调用顺序不同但正确"的解判错，评估集退化成背答案，还扼杀了更好的路径发现。
3. **只评自然语言回复，不评环境状态**：Agent 嘴上说"已为您取消"，数据库里订单纹丝不动。τ-bench 的核心教训就是**校验 DB 状态**。
4. **judge 与被测同源**：self-enhancement bias 让自评系统性虚高；至少交叉用不同族模型。
5. **环境不重置**：上一条用例改了数据库，下一条用例"恰好"通过——评估结果与用例顺序耦合，是最隐蔽的 bug。
6. **把 judge 分当绝对真值**：没有人工校准集的 judge 只是一个有偏见的自动函数；κ 不达标的 judge 给出的回归曲线会把你带向错误方向。
7. **在线/离线 judge 两套口径**：同一个"质量分"线上线下定义不同，导致离线涨了线上不动，团队互相甩锅。judge prompt 必须统一版本管理。
8. **日志两个极端**：全量记 prompt → 成本爆炸 + PII 合规风险；只记结果 → 出事无法 replay。正解是元数据全采、内容 opt-in 分层采样 + 脱敏。
9. **SLO 告警与质量告警混为一谈**：延迟/错误率要实时告警；质量分是抽样估计，应走批量评估 + 人审队列，实时告警只会制造噪声。
10. **benchmark 分数当产品 KPI**：污染、错配、饱和、scaffold 混淆四连击。基准用于外部参照，产品决策靠自有评估集 + 线上指标。
11. **pass rate 高 = 可靠**：95% pass rate 的 Agent 在 20 步任务上可能只有 1/3 的整体成功率；无人值守场景永远问 pass^k。
12. **忽视"用户模拟器"的非确定性**：τ-bench 类基准里用户侧也是 LLM，它的变异会被算进你的分数方差，需要固定或多 trial 吸收。
13. **temperature=0 + seed 当复现万灵药**：GPU/batching 非确定性、工具与环境的时变依然存在；目标是统计可复现（固定 protocol + 多 trial + 置信区间），不是比特级复现。
14. **mock 漂移**：评估用的 mock 与生产 API 行为悄然分叉，评估全绿、上线即炸。mock 要定期与真实接口对账，越靠近发布环境越要真。
15. **scaffold 混淆解读榜单**：同一模型换一套 harness 分数差几十点——"哪个模型强"与"哪个系统强"是两个问题，引用任何基准数字先问脚手架。
16. **judge 打精细连续分**：judge 对二值判断/checklist 的掌握远好于 1–5 Likert 刻度；直接打细分放大的是刻度噪声而非质量差异。
17. **只回归功能，不回归安全**：一次 prompt 重构可以让功能用例全绿、注入防线塌方；安全对抗集必须是回归套件的常设成员。
18. **grader 被钻空（reward hacking）当成模型变强**：pass rate 突然飙升，先怀疑 grader 被钻空——Agent 改测试文件、对单点断言表面达标、利用宽松匹配 specification gaming，都有真实案例；grader 要配"看起来对其实错"的对抗样本，测试/黄金文件只读且不可见。
19. **评估管线不自检**：没有 A/A 测试定噪声基线，"涨了 2 个点"可能只是噪声波动；没有离线-在线相关性回测，离线涨幅可能系统性不预测线上——两者缺失时，评估趋势图只是自我安慰。
20. **对评估集污染不设防**：公开基准题面进训练语料，自有评估集也会被针对性优化；没有 canary 埋点、复述变体试探与定期换血，通过率曲线可能度量的只是"对评估集的记忆"。
21. **把建议接受率当编码 Agent 的北极星**：接受后秒删/大改同样计入接受，接受率上涨可能只是建议风格更"讨好"；要用 7/30 天代码留存与 churn 校验，并按 DORA 对照变更失败率，防止吞吐涨、质量崩。

---

### 六、推荐资源

1. **Anthropic Engineering —《Demystifying evals for AI agents》（2026-01）**
   当前最凝练的一线实践指南：capability vs regression 套件划分、grader 分层、pass@k/pass^k、"不强制固定轨迹"（Don't grade the path, grade what it produced）等建议均出自 Claude Code 等产品的实战教训。配合同系列《Effective harnesses for long-running agents》（2025-11）读。
   https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents ・ https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
2. **τ-bench 论文（Yao et al., 2024；ICLR 2025）+ τ²-bench（Barres et al., 2025）+ τ³-bench（τ-voice, arXiv 2603.13686）与官网榜单**
   pass^k 的原始出处与双控制/多模态演进，理解 Agent 可靠性度量的必读；官网含 τ²/τ³ 最新排行与域间分化数据（按月变动，引用时标注日期）。
   https://arxiv.org/abs/2406.12045 ・ https://arxiv.org/abs/2506.07982 ・ https://taubench.com/
3. **GAIA（Mialon et al., ICLR 2024）+ GAIA-2 / ARE（Meta FAIR, arXiv 2509.17158, 2025-09）**
   "对人简单、对 AI 难"的通用助理基准范本，及其从"只读"到"读写交互"的演进（800 场景 × 10 universes，配套 ARE 环境框架），理解基准饱和与迭代逻辑。
   https://arxiv.org/abs/2311.12983 ・ https://arxiv.org/abs/2509.17158 ・ https://huggingface.co/blog/gaia2 ・ 榜单 https://huggingface.co/spaces/gaia-benchmark/leaderboard
4. **Judge 方法学三件套**：《A Survey on LLM-as-a-Judge》（Gu et al., 2024，arXiv 2411.15594）+《Justice or Prejudice?》（Ye et al., 2024，arXiv 2410.02736，偏差系统量化）+《Agent-as-a-Judge》（Zhuge et al., ICML 2025，工具化核验）
   judge 范式从方法、偏差到 Agent 化评审的完整脉络。
   https://arxiv.org/abs/2411.15594 ・ https://arxiv.org/abs/2410.02736 ・ https://github.com/CSHaitao/Awesome-LLMs-as-Judges
5. **OpenTelemetry GenAI Semantic Conventions**
   可观测性的行业标准，`gen_ai.*` 属性、内容采集 opt-in 与 agent/tool/MCP 属性 registry（development 稳定性），面试谈"厂商中立埋点"的底气来源。官方规范已迁移至独立仓库。
   https://github.com/open-telemetry/semantic-conventions-genai
6. **Langfuse / LangSmith 官方文档与博客**
   工程落地视角：trace 设计、online evaluator、annotation queue、scores 标注与数据飞轮的具体形态（Langfuse 开源可自托管，对照 LangSmith 读差异）。
   https://langfuse.com/docs ・ https://docs.smith.langchain.com/
7. **安全评估线**：AgentDojo（NeurIPS 2024 D&B）+ InjecAgent（ACL 2024 Findings）+ AgentHarm（ICLR 2025）
   提示注入攻防的双轴评估（ASR × 效用保持）与危害任务评测，Agent 安全评估的事实标准参照。
   https://arxiv.org/abs/2406.13352 ・ https://arxiv.org/abs/2403.02691 ・ https://arxiv.org/abs/2410.09024
8. **评估框架工具线**：Inspect（英国 AI Security Institute 开源评估框架；该机构 2025 年 2 月由 AI Safety Institute 更名，缩写仍为 AISI）+ promptfoo / DeepEval / RAGAS
   把本章方法论落到代码的常见选择：Inspect 的 solver/scorer 抽象适合 Agent 与安全评估（`--repeat` 做多 trial），promptfoo 适合 CI 门禁集成，RAGAS 专攻检索链路的组件级指标。
   https://github.com/UKGovernmentBEIS/inspect_ai ・ https://github.com/promptfoo/promptfoo
