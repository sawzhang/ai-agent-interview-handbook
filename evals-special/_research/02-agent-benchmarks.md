# Agent 评测基准与套件全景（2024–2026）调研报告

> 调研日期：2026-08-05。核实方式：arXiv API 批量查询 + WebSearch 交叉确认；无法核实的条目标注【未核实】。
> 标注【未核实】的 arXiv ID 来自调研者既有知识，置信度高但本次会话未能联网复核（arXiv 站点访问被限流），使用前建议二次确认。

---

## 主题概述

**这个方向在解决什么问题。** 2023 年之前的 LLM 评测（MMLU、HumanEval 等）测的是"单次问答/生成"，而 Agent 评测要回答的问题是：**一个由 LLM 驱动的系统，能否在真实环境里、通过多步工具调用与交互，可靠地完成一件完整的事**（退一张机票、修一个 GitHub issue、在 Ubuntu 桌面装好一个环境、在开放网络上找到一条难以检索的信息）。这带来四个新的评测难题：

1. **环境从哪来**：需要可复现、可重置、可自动判定的交互环境（沙箱网站、虚拟机、Docker、真实浏览器）。
2. **怎么算对**：轨迹（trajectory）千变万化，不能用精确匹配轨迹判分，必须做**功能性正确判定**（执行测试、检查终态、程序化断言、或 LLM 评审）。
3. **可靠性怎么量化**：Agent 有强随机性，单次成功率（pass@1）严重高估可用性——τ-bench 提出的 **pass^k**（连续 k 次全对的比例）成为行业标杆。
4. **污染与饱和怎么办**：公开题面会进入训练语料，基准会快速饱和，必须持续造更难、更新、更私有的题集。

**2024–2026 的演进主线：**

- **2024 上半年——环境奠基期**：WebArena / VisualWebArena / OSWorld / WorkArena 确立了"自托管沙箱环境 + 程序化判定"的范式；GAIA（2023 底发布）确立了"结果精确匹配 + 难度分级"的通用助手评测范式；τ-bench 把**对话式工具 Agent**与**用户模拟器**引入评测。
- **2024 下半年——软件工程爆发期**：SWE-bench 成为事实标准，Verified（人工筛 500 题）与 Multimodal（JS + 截图）变体相继出现；Agent-as-a-Judge 开启"用 Agent 评 Agent"的趋势；WindowsAgentArena 把 Windows 桌面环境工程化。
- **2025——难度军备与可靠性转向**：SWE-bench 分数逼近 70%+ 后社区转向更难、抗污染的基准（SWE-bench Pro、Terminal-Bench 2.0 Hard、BrowseComp、HLE）；τ²-bench 引入"双控"用户模拟解决泄题；pass^k / 多次采样成为标配；合成任务生成（SWE-smith）与真实经济价值任务（SWE-Lancer）出现。
- **2026——基准工业化与信任危机并存**：Terminal-Bench 论文（ICLR 2026）把终端 Agent 评测标准化；同时社区开始系统性质疑：基准间分数相关性低（Princeton HAL / AI Agent Index）、harness（执行框架）工程对分数影响巨大、基准分数与生产表现脱节。评测重心正从"公开排行榜"转向"私有 golden set + 领域定制评测套件"。

---

## 重点论文

#### τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains

- **arXiv**: [2406.12045](https://arxiv.org/abs/2406.12045) ｜ **机构**: Sierra ｜ **时间**: 2024-06 ｜ **状态**: 已核实（arXiv API + 搜索）；作者 Shunyu Yao, Noah Shinn, Pedram Razavi, Karthik Narasimhan
- **贡献**：定义了"客服型 Agent"评测范式：Agent 需要与**LLM 扮演的用户**多轮对话、遵守长篇领域政策文档（policy）、调用工具（数据库 API）完成退票、改地址等任务。首次系统提出 **pass^k** 指标来度量可靠性，并用终态数据库比对做自动判定（无需人工评审）。
- **关键数字**：retail 域 115 任务 + airline 域 50 任务；GPT-4o 在 retail 域 pass^1 约 65%，但 pass^8 跌到约 35%（人类约 90%+）——揭示"单次看起来不错"与"可部署"之间的巨大鸿沟。
- **工程意义**：这是与生产客服/业务 Agent 最接近的评测形态。任何做领域 Agent 的团队都应仿建：政策文档 + 工具集 + 用户模拟器 + 终态断言。pass^k 是必须汇报的指标。

#### τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment

- **arXiv**: [2506.07982](https://arxiv.org/abs/2506.07982) ｜ **机构**: Sierra ｜ **时间**: 2025-06 ｜ **状态**: 已核实（arXiv API），第一作者 Victor Barré
- **贡献**：τ-bench 中用户模拟器只是按脚本提需求，且存在"用户模拟器向 Agent 泄露关键信息"的问题。τ² 引入**双控（dual-control）**：用户侧也是一个有工具（如查邮件、查日历）和场景指令的 Agent，双方信息不对称，Agent 必须通过提问获取信息，更贴近真实客服场景。
- **关键数字**：双控设定下各家模型分数相对 τ-bench 显著下降，说明此前高分部分来自用户模拟器的"配合性泄题"。
- **工程意义**：用户模拟器的设计本身就是评测效度问题——模拟器太强/太配合会高估被测 Agent。构建对话评测时必须审计信息泄露路径。

#### GAIA: A Benchmark for General AI Assistants

- **arXiv**: [2311.12983](https://arxiv.org/abs/2311.12983) ｜ **机构**: Meta AI + Hugging Face + AutoGPT ｜ **时间**: 2023-11（ICLR 2024）｜ **状态**: 已核实（arXiv API + 搜索），Mialon, Fourrier, …, LeCun, Scialom
- **贡献**：466 道"人类觉得简单、AI 觉得难"的通用助手题（需要推理 + 工具使用 + 网页浏览 + 多模态），分 L1/L2/L3 三个难度级；答案为短文本，用**精确匹配**自动判分，天然抗 LLM-judge 偏差。是"通用 Agent 助手"赛道的基石，HuggingFace 排行榜长期是 Agent 框架（AutoGPT 系、Manus 系）的打榜目标。
- **关键数字**：论文发布时人类 92% vs GPT-4+插件约 15%；到 2025 年顶级系统已到 60–70%+ 区间，L1 接近饱和。
- **工程意义**：精确匹配 + 难度分级 + 小题库（几百道）是低成本高信噪比评测的模板。但题面公开后污染风险高，适合做回归冒烟，不适合做唯一决策依据。

#### AgentBench: Evaluating LLMs as Agents

- **arXiv**: [2308.03688](https://arxiv.org/abs/2308.03688) ｜ **机构**: 清华大学（THUDM）｜ **时间**: 2023-08（ICLR 2024）｜ **状态**: 已核实（arXiv API + 搜索），Xiao Liu 等
- **贡献**：首个多环境 Agent 综合基准：将 LLM-as-Agent 形式化为 POMDP，覆盖 8 个交互环境（操作系统、数据库、知识图谱、卡牌游戏、横向思维谜题、家居任务 ALFWorld、网购 WebShop、网页浏览）。系统揭示了商用模型（GPT-4）与开源模型在长程推理与指令遵循上的巨大差距。
- **关键数字**：8 环境标准化聚合分；GPT-4 大幅领先同期开源模型（是当时"开源模型不能当 Agent"论的主要证据）。
- **工程意义**：其"多环境统一接口 + 聚合打分"的套件设计是所有 Agent 评测框架（如后续的各种 arena）的参考实现；但多数子环境如今已趋饱和，现主要作为历史基线与能力画像工具。

#### SWE-bench: Can Language Models Resolve Real-World GitHub Issues?

- **arXiv**: [2310.06770](https://arxiv.org/abs/2310.06770) ｜ **机构**: Princeton 等 ｜ **时间**: 2023-10（ICLR 2024）｜ **状态**: 已核实（arXiv API + 搜索），Carlos E. Jimenez, John Yang 等
- **贡献**：从 12 个 Python 仓库的真实 issue-PR 对中构造 2294 个任务：给 issue 文本 + 代码库，产出 patch，用**FAIL_TO_PASS / PASS_TO_PASS 测试**自动判定是否"解决"。确立了软件工程 Agent 的评测标准，催生 SWE-agent、OpenHands、R2E 等整个赛道。
- **关键数字**：发布时最好系统约 3%；SWE-agent+GPT-4 达 12.5%；Claude 3.5 Sonnet + SWE-agent 达 49%；2025 年头部系统超过 70%。**SWE-bench Verified**（OpenAI 2024-08 发布，非 arXiv 论文，博客形式）是 500 道经软件工程师人工复核的子集，剔除了有歧义/信息不足的实例，成为工业界最常引用的分数口径。
- **工程意义**：测试驱动的功能性判定是 Agent 评测的黄金标准；但"resolved"只保证过测试，不等于 patch 质量（可读性、副作用），生产中需加静态审查层。变体：Verified（质量）、Multimodal（见下）、Pro（私有测试、更长程，2025）。

#### SWE-bench Multimodal: Do AI Systems Generalize to Visual Software Domains?

- **arXiv**: [2410.03859](https://arxiv.org/abs/2410.03859) ｜ **机构**: Princeton 等 ｜ **时间**: 2024-10（ICLR 2025）｜ **状态**: 已核实（搜索确认）
- **贡献**：把 SWE-bench 扩展到视觉/前端软件域：617 个来自 17 个 JavaScript 仓库的 issue，附带截图、可视化、UI 描述。证明在 Python 文本域上强的系统在 JS + 视觉域上**大幅掉点**——暴露了"语言泛化"与"视觉推理"两个被忽略的短板。
- **关键数字**：GPT-4o + SWE-agent 在 SWE-bench Lite（Python）约 33%，在 Multimodal 上跌至个位数到 ~10% 量级（论文报告的最大落差之一）。
- **工程意义**：评测集必须覆盖生产环境的真实语言与模态分布；如果你的产品改的是 TS/前端代码，Python 基准的高分几乎没有外推性。

#### WebArena / VisualWebArena

- **arXiv**: WebArena [2307.13854](https://arxiv.org/abs/2307.13854)（已核实：CMU 等，2023-07，ICLR 2024，Shuyan Zhou, Graham Neubig 等）；VisualWebArena [2401.13649](https://arxiv.org/abs/2401.13649)【未核实】（CMU，2024-01，ACL 2024，Jingkang Koh 等）
- **贡献**：WebArena 自建可自托管、可完全重置的真实功能网站集群（电商、GitLab、Reddit 式论坛、地图、CMS），812 个任务，用**功能性检查**（URL/页面终态/数据库状态）判分而非比对轨迹；VisualWebArena 加入多模态视觉任务（按图片找商品、视觉问答式导航）扩展到 910 个任务。它们确立了"网页 Agent = 沙箱环境 + 程序化判定"的范式。
- **关键数字**：WebArena 发布时 GPT-4 系 Agent 约 14%，人类 78%；到 2025 年最佳系统超过 60%，已出现饱和压力。
- **工程意义**：自托管环境是复现性的保障（对比真实网站会漂移）；但环境搭建/维护成本高，且 DOM/可访问性树表征的选择本身显著影响分数——评测网页 Agent 时必须固定观测表征与 harness。

#### WorkArena / WorkArena++

- **arXiv**: WorkArena [2403.07718](https://arxiv.org/abs/2403.07718)【未核实】；WorkArena++ [2407.05291](https://arxiv.org/abs/2407.05291)（已核实：arXiv API，Léo Boisvert 等，2024-07）｜ **机构**: ServiceNow
- **贡献**：把 Agent 评测搬进**企业 SaaS**：在真实 ServiceNow 实例上测表单填写、列表操作、知识检索、服务目录下单等企业工作流任务（v1 约 33 任务、6 大类）；WorkArena++ 进一步引入需要**组合式规划与常识推理**的跨模块任务。这是"企业 Agent"评测的代表作。
- **关键数字**：v1 上最好的商用模型成功率也只有约两成量级，远低于网页公开基准，说明企业私有系统的隐性知识（字段语义、业务规则）是真实瓶颈。
- **工程意义**：做企业内部 Agent（IT 服务台、ERP、CRM）时，公开基准几乎不可用，必须在自己的系统实例上建 WorkArena 式评测；企业环境的任务正确性往往依赖领域专家定义的终态断言。

#### OSWorld / WindowsAgentArena

- **arXiv**: OSWorld [2404.07972](https://arxiv.org/abs/2404.07972)（已核实：XLANG Lab，2024-04，NeurIPS 2024 D&B Track，Tianbao Xie 等）；WindowsAgentArena [2409.08264](https://arxiv.org/abs/2409.08264)【未核实】（Microsoft，2024-09）
- **贡献**：OSWorld 在**真实操作系统虚拟机**（Ubuntu/Windows/macOS）里测 369 个开放式计算机操作任务，用执行脚本检查终态（文件内容、系统设置等），输入支持截图 + 可访问性树；WindowsAgentArena 提供可大规模并行的 Windows 环境（154 任务）与 Bonsai 基线 Agent，并探索用 NLU/LLM 判定替代手写脚本判定以降低标注成本。
- **关键数字**：OSWorld 人类基线 72.4%，发布时最好的多模态 Agent 约 12%；2025 年头部 computer-use 系统升至 40%+（社区另有 OSWorld-Verified 剔除模糊实例）。WindowsAgentArena 上 Bonsai（GPT-4V）约 19.5%。
- **工程意义**：OS 级评测最接近"通用桌面助理"产品形态，但单次评测的算力/时间成本极高——WindowsAgentArena 的并行化工程（评测吞吐提升一个数量级）是评测基础设施的样板。判定脚本的脆弱性（终态检查误判）是该系列已知痛点。

#### Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces

- **arXiv**: [2601.11868](https://arxiv.org/abs/2601.11868) ｜ **机构**: Stanford + Laude Institute（Snorkel AI 参与）｜ **时间**: 2026-01（ICLR 2026）｜ **状态**: 已核实（搜索确认，第一作者 M.A. Merrill）
- **贡献**：面向**终端/命令行 Agent**（Claude Code、Codex CLI 一类）的基准：每个任务是一个 Docker 容器 + 自然语言指令 + 自动验证脚本（pytest 式断言）。初版 80 个任务；2025 年 7 月发布的 v2.0 精选 **89 个高难任务**（TB 2.0 Hard），覆盖遗留系统配置、服务器搭建、模型训练、科研计算等。配套提出 **Terminus** 参考 Agent（只给一个无头终端、纯 bash 操作），把"harness 工程"与"模型能力"解耦，作为排行榜的标准评测配置。
- **关键数字**：TB 2.0 上各主流 coding agent 分数差异巨大（头部 50%+ 到长尾 <10%），且同一模型换 harness 分数变化显著——论文把"harness 效应"作为核心发现之一。
- **工程意义**：对 coding agent 团队，Terminal-Bench 是当前最接近真实 CLI 工作流的公开评测；其 Docker 化任务 + 自动验证 + 标准 harness 的三件套，是企业自建 Agent 评测的直接模板。注意：任务难度高，单次评测方差大，官方建议多次采样。

#### BrowseComp（OpenAI，无 arXiv 论文）

- **链接**: OpenAI 博客 "BrowseComp: A simple yet challenging benchmark for browsing agents"（2025-04）；无 arXiv 论文，题目**未公开**以防污染 ｜ **状态**: 以官方博客为准
- **贡献**：1266 道"答案在互联网上存在但极难检索到"的问题（设计原则：答案不在模型参数内、需要多步浏览与交叉验证、可人工验证唯一答案）。是"深度研究/浏览 Agent"赛道的难度标杆。
- **关键数字**：OpenAI Deep Research 约 51.5%，普通 GPT-4o 级浏览仅约 2%——证明"会浏览"与"会深度检索"是两种能力。
- **工程意义**：闭源题面 + 人工构造 + 唯一答案是抗污染评测的范式，但无法被第三方复现与审计，学界对其透明度有批评。做 RAG/深度研究产品评测时，应借鉴其"答案必须可验证且不在参数里"的出题原则。

#### Humanity's Last Exam (HLE)

- **arXiv**: [2501.14249](https://arxiv.org/abs/2501.14249) ｜ **机构**: CAIS（Center for AI Safety）+ Scale AI 等 ｜ **时间**: 2025-01 ｜ **状态**: 已核实（arXiv API），Long Phan 等
- **贡献**：从全球数百位专家征集约 3000 道"专家级、前沿知识"难题（覆盖 100+ 学科，约 1/4 为多模态），目标是造一个"当前 LLM 几乎做不对"的通用知识基准，作为能力上限探针。题目经专家校验与交叉审核，并持续做污染检查。
- **关键数字**：发布时最强前沿模型准确率不足 10%（远低于 MMLU 的近饱和）；2025 年内随推理模型（Gemini Deep Think 系列等）推进到 30%+，再次验证"基准两年饱和律"。
- **工程意义**：HLE 不是 Agent 基准，但它是"评测难度标定"的方法论样板（专家出题 + 难度校准 + 污染审计），且常被用作 Agent 系统中"知识检索 + 推理"子能力的探针。已知问题：部分题目被指有歧义、社区众包修订持续进行；分数快速上涨后信噪比下降。

#### WebVoyager / AssistantBench（开放网络评测双雄）

- **arXiv**: WebVoyager [2401.13919](https://arxiv.org/abs/2401.13919)【未核实】（2024-01，ACL 2024）；AssistantBench [2407.15711](https://arxiv.org/abs/2407.15711)（已核实：arXiv API，Ori Yoran 等，AI2，2024-07）
- **贡献**：WebVoyager 在**真实网站**（15 个主流站点、643 个任务）上端到端评测多模态网页 Agent（直接吃截图），并首创用 GPT-4 做自动评审（与人工一致性约 87%），是"LLM-as-judge 评 Agent"的早期代表作。AssistantBench 反其道而行：33 道**开放网络、耗时型**任务（人类平均需 15 分钟以上、需多页面综合与推理），强调任务的可行性验证与答案有效性，用准确率 + 答案支撑度评分。
- **关键数字**：WebVoyager 上 GPT-4V 自建 Agent 显著超过当时的专用管线；AssistantBench 上最好的 Web Agent 准确率仅 ~18% 量级，与人类差距巨大。
- **工程意义**：两者代表开放网络评测的两难——真实网站评测生态效度高但**不可复现**（站点改版、A/B 测试、登录墙）；沙箱化可复现但失真。AssistantBench 的"题目可行性验证"流程（先确认人能做对）值得所有自建评测集借鉴。

#### BFCL：Berkeley Function Calling Leaderboard（及 Gorilla 论文）

- **arXiv**: Gorilla 论文 [2305.15334](https://arxiv.org/abs/2305.15334)【未核实】（UC Berkeley，2023-05）；BFCL 本体以 [gorilla.cs.berkeley.edu/leaderboard.html](https://gorilla.cs.berkeley.edu/leaderboard.html) 博客/技术报告形式迭代，无单一 arXiv 论文
- **贡献**：BFCL 是函数调用（tool use）能力的标准评测：v1 用 **AST 匹配 + 可执行验证**测单轮函数调用；v2（2024-09）加入相关性检测（不该调用时不调用）、缺失参数、实时 API（Web search）；v3（2025-02）加入**多轮/多步、缺失函数/参数、幻觉检测、长尾域与网络搜索**，成为 Agent 工具使用能力的事实排行榜。
- **关键数字**：v3 榜单覆盖数十个模型；头部模型总分 85–95%，但在"缺失函数/相关性检测"子项上普遍掉 10–30 分——说明"知道何时不调用"仍是短板。
- **工程意义**：函数调用是 Agent 的最底层能力，BFCL 的子项拆分（精确参数、多函数组合、相关性、多轮状态）是工具调用单元测试的直接清单。评测 Agent 工具层时应先看这些子项而非聚合分。

#### Agent-as-a-Judge: Evaluate Agents with Agents

- **arXiv**: [2410.10934](https://arxiv.org/abs/2410.10934) ｜ **机构**: Meta 等 ｜ **时间**: 2024-10 ｜ **状态**: 已核实（arXiv API），Mingchen Zhuge 等
- **贡献**：提出用**评审 Agent**（带工具的 Agent，而非单次 LLM 调用）来评估 Agent 工作流：构建 DevAI 基准（37 个 AI 开发场景 + 36 条元评审标准），评审 Agent 可以读代码、执行检查。这是"Agent-as-benchmark"（以 Agent 作为评测器）新趋势的标志性工作。
- **关键数字**：与人类专家评估对齐度高，同时减少约 82% 的人力、约 97.7% 的时间与成本。
- **工程意义**：Agent 轨迹/中间产物的人工评审无法规模化，Agent 评审器是必经之路；但必须先用人工标注校准评审器（对齐率、误判方向），并警惕评审器自身的偏差（与被测系统同源模型的自我偏好）。

---

## 关键概念与方法论

### 1. pass^k：可靠性指标（τ-bench 定义）

- **pass@1** = 单次尝试成功的任务比例（高估可用性）。
- **pass^k** = 同一任务独立运行 k 次、**全部成功**的任务比例。公式：`pass^k = |{task : ∀ i∈[1..k], success(task, i)}| / |tasks|`。
- 直觉：若每次成功率 p 且独立，pass^k ≈ p^k；p=0.9, k=8 时仅 0.43。生产部署要求高 k 下仍有高分。
- 工程惯例：k 取 4–8；同时报告 pass@1 与 pass^k，两者差距反映系统方差。

### 2. 功能性正确判定（execution-based evaluation）

- **SWE-bench 式**：patch 必须让 FAIL_TO_PASS 测试通过且 PASS_TO_PASS 不回归（在干净环境执行）。
- **OSWorld / Terminal-Bench 式**：任务完成后运行检查脚本（文件内容、进程状态、HTTP 响应、pytest 断言）。
- **WebArena 式**：检查 URL、页面元素、数据库终态等功能性谓词。
- **GAIA 式**：短答案精确匹配（大小写/标点归一化后比对）。
- 对比面：**轨迹匹配**（脆弱、已淘汰）与 **LLM-as-judge**（灵活但有偏，需人工校准）。

### 3. 用户模拟与双控（τ-bench → τ²-bench）

- 用 LLM 扮演用户，按场景卡（persona + 目标 + 私有信息）与 Agent 对话；评测需审计模拟器是否泄题（τ² 的双控设计：用户侧也有工具与信息获取路径）。
- 用户模拟器本身是被测系统的一部分敏感性来源：换模拟器模型分数会变，报告中应固定模拟器版本。

### 4. 难度分级与动态生成

- GAIA 的 L1/L2/L3（按所需步数/工具数标定）、HLE 的专家校准、Terminal-Bench Hard 精选。
- 合成/动态任务：SWE-smith 用 bug 注入批量合成 5 万级 SWE 任务；AndroidWorld 用参数化模板生成可复测任务——对抗污染的结构性手段。

### 5. Agent-as-Judge / 评审器校准

- 评审 Agent = LLM + 工具 + 评审协议（rubric）。上线前做 meta-evaluation：与人工标注的一致性（WebVoyager 报告约 87%）、位置偏差/自我偏好检查、分领域抽查。

### 6. 污染控制手段清单

- 时间截止（只用 cutoff 后的仓库/题目）；私有 holdout（SWE-bench Pro 私有测试）；闭源题面（BrowseComp）；canary 字符串；定期刷新（基准版本化，如 Terminal-Bench 1.0 → 2.0）；合成数据（SWE-smith）。

---

## 争议与分歧

1. **污染是否已让公开排行榜失效。** SWE-bench 的 GitHub issue 文本大量出现在训练语料中，被普遍怀疑贡献了部分分数增长；GAIA/HLE 题目同样面临泄露。学界应对（Pro、闭源题面、污染审计）与工业界"照打榜"之间的信任差在扩大。共识渐成：**单一公开榜单不可作为发布决策依据**。
2. **饱和与"难度军备竞赛"。** WebArena、GAIA L1、SWE-bench Verified 相继进入 60–75%+ 区间，社区反应是不断出更难基准（SWE-bench Pro、TB Hard、BrowseComp、HLE），批评者称之为 treadmill：难度通胀掩盖了"评测到底在测什么"的问题；且难题集往往样本少、方差大、区分度未必更高。
3. **pass^k 是否过严。** 有观点认为 pass^k 假设了独立同分布重试，惩罚了"可诊断的错误"（实际系统中失败可回滚/人工接管），主张报告"失败模式分布 + 成本"而非单点可靠性数字。反方认为部署即要求高可靠性，pass^k 是最低标准。
4. **harness 工程 vs 模型能力。** Terminal-Bench 等结果反复显示同一模型换执行框架分数差异巨大（2025–2026 年开源 harness 生态爆发后尤甚）。争议：排行榜测的到底是模型还是 harness+模型组合？这直接影响"用哪个模型"的工程决策。
5. **基准分数与生产表现的相关性。** Princeton SAgE 团队的 Holistic Agent Leaderboard（HAL）/ AI Agent Index 工作（2025）发现不同 Agent 基准之间的分数相关性很低、且与真实用户满意度弱相关，动摇了"一个分数定优劣"的评测文化。【HAL 具体 arXiv ID 本次未核实】
6. **真实 vs 沙箱环境。** WebVoyager 式真实网站评测被批不可复现、不可审计；沙箱基准被批"失真"（DOM 结构、反爬机制、登录态都不像真实网络）。目前无共识解，普遍做法是两者并报。
7. **LLM 评审与用户模拟器的偏差。** LLM-as-judge 的位置偏差、冗长偏好、同源模型自我偏好均有文献记录；τ-bench 用户模拟器泄题问题直接催生了 τ²。用 LLM 组件做评测时，评测器本身需要被评测。

---

## 对工程实践的启示

1. **自建"τ-bench 式"领域评测套件优先级最高**：政策文档/知识库 + 工具（mock API 即可）+ 用户模拟器 + 终态断言。100–300 个任务、每任务 4–8 次采样、汇报 pass^k。这比打任何公开榜都更能预测生产表现。
2. **判定必须程序化**：能写测试就不用人评，能用终态断言就别判轨迹。LLM 评审只用于无法程序化的开放性输出，且需人工抽样校准（目标一致性 ≥85%）。
3. **环境要 Docker/VM 化、可重置、可并行**：参考 Terminal-Bench（Docker + pytest）与 WindowsAgentArena（并行化）；同时记录每任务成本与时长，评测频率要与成本匹配（GAIA 式轻量基准天天跑，OSWorld 式重基准发版前跑）。
4. **固定并隔离 harness**：模型对比时锁定 harness；评估 harness 改动时锁定模型；分别报告，避免归因混乱。
5. **抗污染纪律**：自建评测集分公开/私有两层，私有集只在关键决策时启用；定期注入新任务（版本化）；对疑似泄题的任务做 canary 检查。
6. **用基准组合而非单榜**：公开基准（GAIA/SWE-bench/OSWorld 等）做能力画像与回归，领域自建集做发布门禁；参考 HAL 的教训，警惕跨基准外推。
7. **覆盖生产分布**：语言（Python vs JS/TS）、模态（截图/文档）、任务时长都要对齐生产流量——SWE-bench Multimodal 的落差是前车之鉴。
8. **引入 Agent 化评审降本**：轨迹评审、代码评审可用评审 Agent 规模化（Agent-as-a-Judge，arXiv 2410.10934，Zhuge et al. ICML 2025：DevAI 55 任务/365 条分层需求；相比三位人类专家节省 97.72% 时间、97.64% 成本——场景特定值），但上线前做与人工的 meta-evaluation。
9. **可靠性与成本一起看**：报告 pass^k 时附带平均 token 成本/任务与失败重试成本；高 pass^k 但高成本的方案在单位经济学上可能不如低 pass^k + 人工兜底。

---

## 参考清单

### 核心论文（已核实，除标注外）

| # | 基准 | arXiv / 链接 | 机构 | 时间 |
|---|------|-------------|------|------|
| 1 | τ-bench | [2406.12045](https://arxiv.org/abs/2406.12045) | Sierra | 2024-06 |
| 2 | τ²-bench | [2506.07982](https://arxiv.org/abs/2506.07982) | Sierra | 2025-06 |
| 3 | GAIA | [2311.12983](https://arxiv.org/abs/2311.12983) | Meta/HF/AutoGPT | 2023-11（ICLR'24）|
| 4 | AgentBench | [2308.03688](https://arxiv.org/abs/2308.03688) | 清华 THUDM | 2023-08（ICLR'24）|
| 5 | SWE-bench | [2310.06770](https://arxiv.org/abs/2310.06770) | Princeton 等 | 2023-10（ICLR'24）|
| 6 | SWE-bench Multimodal | [2410.03859](https://arxiv.org/abs/2410.03859) | Princeton 等 | 2024-10（ICLR'25）|
| 7 | WebArena | [2307.13854](https://arxiv.org/abs/2307.13854) | CMU 等 | 2023-07（ICLR'24）|
| 8 | VisualWebArena【未核实】 | [2401.13649](https://arxiv.org/abs/2401.13649) | CMU | 2024-01（ACL'24）|
| 9 | WorkArena【未核实】 | [2403.07718](https://arxiv.org/abs/2403.07718) | ServiceNow | 2024-03 |
| 10 | WorkArena++ | [2407.05291](https://arxiv.org/abs/2407.05291) | ServiceNow | 2024-07 |
| 11 | OSWorld | [2404.07972](https://arxiv.org/abs/2404.07972) | XLANG Lab | 2024-04（NeurIPS'24）|
| 12 | WindowsAgentArena【未核实】 | [2409.08264](https://arxiv.org/abs/2409.08264) | Microsoft | 2024-09 |
| 13 | Terminal-Bench | [2601.11868](https://arxiv.org/abs/2601.11868) | Stanford + Laude | 2026-01（ICLR'26）|
| 14 | BrowseComp（无 arXiv） | [OpenAI 博客](https://openai.com/index/browsecomp/) | OpenAI | 2025-04 |
| 15 | Humanity's Last Exam | [2501.14249](https://arxiv.org/abs/2501.14249) | CAIS + Scale 等 | 2025-01 |
| 16 | WebVoyager【未核实】 | [2401.13919](https://arxiv.org/abs/2401.13919) | 2024-01（ACL'24）|
| 17 | AssistantBench | [2407.15711](https://arxiv.org/abs/2407.15711) | AI2 | 2024-07 |
| 18 | Gorilla / BFCL【未核实】 | [2305.15334](https://arxiv.org/abs/2305.15334) + [BFCL 榜单](https://gorilla.cs.berkeley.edu/leaderboard.html) | UC Berkeley | 2023-05 / 持续更新 |
| 19 | Agent-as-a-Judge | [2410.10934](https://arxiv.org/abs/2410.10934) | Meta 等 | 2024-10 |

### 延伸阅读（已核实，除标注外）

| 基准 | arXiv | 一句话 |
|------|-------|--------|
| AndroidWorld | [2405.14573](https://arxiv.org/abs/2405.14573) | Google DeepMind；参数化动态 Android 任务（116 个），支持环境重置与任务变体 |
| MLE-bench | [2410.07095](https://arxiv.org/abs/2410.07095) | OpenAI；75 个 Kaggle 竞赛测 ML 工程 Agent |
| SWE-smith | [2504.21798](https://arxiv.org/abs/2504.21798) | Princeton；bug 注入合成 5 万级 SWE 训练/评测任务 |
| SWE-Lancer | [2502.12115](https://arxiv.org/abs/2502.12115) | OpenAI；以真实自由职业平台计价任务（总额 $1M+）测工程 Agent 的经济价值 |
| SWE-bench Pro【未核实】 | [2509.16941](https://arxiv.org/abs/2509.16941) | Princeton；私有测试 + 长程任务，针对 SWE-bench 过拟合/泄露 |
| Mind2Web（背景） | [2306.06070](https://arxiv.org/abs/2306.06070)【未核实】 | 网页 Agent 早期大规模数据集（2000+ 网站） |
| Holistic Agent Leaderboard（HAL / AI Agent Index） | 见 [hal.cs.princeton.edu](https://hal.cs.princeton.edu) | Princeton SAgE；系统化运行多 Agent 基准并分析跨基准相关性 |

### 背景简述（2023 前的奠基工作）

- **WebShop**（[2207.01206](https://arxiv.org/abs/2207.01206)【未核实】）：模拟网购网站 + 奖励函数，最早的网页 Agent RL 环境之一，后被 WebArena 取代。
- **Mind2Web / OS-Copilot / ToolBench** 等早期数据集为 2024 年后的环境型基准铺路。
- MT-Bench / AlpacaEval（LLM-as-judge 的起源）虽非 Agent 基准，但其揭示的评审偏差问题直接影响了 Agent 评测中 LLM 评审器的设计（校准、去偏）。

---

*报告完。核实状态汇总：17 篇经 arXiv API 或搜索交叉确认；6 处 ID 标注【未核实】（VisualWebArena、WorkArena、WindowsAgentArena、WebVoyager、Gorilla、SWE-bench Pro、Mind2Web），均来自调研者既有知识，建议引用前复核。*
