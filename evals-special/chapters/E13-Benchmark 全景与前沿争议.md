# 第 E13 章 · Benchmark 全景与前沿争议

> 一句话导读：公开 benchmark 是 evals 体系的"外部坐标"，但坐标会老化（饱和）、会被污染（泄漏）、会被作弊（Goodhart）。本章回答三个问题——**主流 benchmark 各自测什么、怎么判**；**污染 / 饱和 / 过拟合三大威胁的机理与对策**；**如何把公开基准、私有 golden set、在线信号组合成可信的选型与发布决策**。学完你能画出一张 2024–2026 的 benchmark 全景图，并能在面试中回答"只能选一个向老板汇报，选哪个"这类系统设计题。

---

## 一、知识图谱

```
Benchmark 全景与前沿争议
│
├─ 1. 分类轴（怎么认识一个 benchmark）
│   ├─ 更新形态：静态固定集 ←→ 动态可再生集
│   ├─ 定位：能力型（单项能力）/ 领域型（行业环境）/ 应用型（端到端产品形态）
│   └─ 交互形态：单轮问答 / 多轮对话 / 环境交互（Web / OS / CLI）
│
├─ 2. 全景速览（谁在测什么）
│   ├─ 对话工具型：τ-bench / τ²-bench（pass^k + 终态 DB 断言）
│   ├─ 通用助手型：GAIA（精确匹配 + L1/L2/L3）/ AgentBench（8 环境聚合）
│   ├─ 软件工程型：SWE-bench 家族（测试驱动）/ Terminal-Bench（Docker + pytest）/ BFCL（函数调用）
│   ├─ Web / OS / SaaS：WebArena 家族 / OSWorld / WindowsAgentArena / WorkArena(++)
│   ├─ 深度浏览型：BrowseComp（闭源题面）/ AssistantBench / WebVoyager
│   └─ 知识天花板探针：HLE（专家级难题）
│
├─ 3. 判定方式谱系（怎么算对）
│   ├─ 短答案精确匹配 → 执行测试（FAIL_TO_PASS）→ 终态断言 → LLM/Agent-as-Judge
│   └─ 轨迹精确匹配：已淘汰（惩罚合法替代路径）
│
├─ 4. 三大威胁（为什么分数会失真）
│   ├─ 污染：题目进训练语料 → 虚高
│   │   └─ 检测四范式：成员推断（Min-K%）/ 语义级变体 / 格式敏感性 / canary
│   ├─ 饱和：分数逼近天花板 → 失去区分度（MMLU 教训、"两年饱和律"）
│   └─ Goodhart：优化代理指标 ≠ 提升真实能力（reward overoptimization）
│
├─ 5. 动态基准（四种机制与代价）
│   ├─ 时间截止线（LiveCodeBench）／ 定期轮换（LiveBench）
│   └─ 程序化生成（DyVal / DynaMath / UGMathBench）／ 保义翻新（2503.06643）
│
├─ 6. 选型与决策（怎么用）
│   ├─ 三层互补：公开 benchmark（外部坐标）+ 私有 golden set（业务真值）+ 在线信号（地面真值）
│   ├─ Arena vs 静态 benchmark：各测什么、何时信谁
│   └─ 统计纪律：CI / 重复实验 / BT / style control（详见第 E9 章）
│
└─ 7. 前沿争议
    ├─ 排行榜是否已被污染失效 · 难度军备竞赛是不是 treadmill · harness 效应
    └─ benchmark 分数与生产表现的相关性（HAL / AI Agent Index、Sean Grove 实证）
```

---

## 二、核心概念精讲

### 2.1 Benchmark 分类学：三条轴

拿到任何一个 benchmark，先用三条轴给它定位，才能判断"它的分数对我意味着什么"。

**轴一：更新形态——静态 vs 动态**

| 维度 | 静态基准 | 动态基准 |
|---|---|---|
| 题目集 | 一次发布、固定不变 | 持续更新或可无限生成 |
| 代表 | GAIA、SWE-bench、OSWorld、MMLU | LiveBench、LiveCodeBench、DyVal、Chatbot Arena |
| 优点 | 跨期完全可比、运行便宜、可沉淀基线 | 抗污染、能持续保持区分度 |
| 缺点 | 污染 + 饱和双重退化 | 跨版本不可直接比较、运营成本高 |
| 典型结局 | 两年内逼近饱和（见 2.5） | 变成"当前快照"而非"连续量尺" |

**轴二：定位——能力 / 领域 / 应用**

| 类型 | 测什么 | 代表 | 与业务的距离 |
|---|---|---|---|
| 能力型 | 单项基础能力（函数调用、知识、数学） | BFCL、HLE、MMLU-Pro | 最远：只能拼能力画像，不能预测端到端表现 |
| 领域型 | 特定行业/环境内的任务完成 | SWE-bench（开源仓库修 issue）、WorkArena（企业 SaaS） | 中等：环境相似但业务规则不同 |
| 应用型 | 端到端产品形态 | τ-bench（客服）、GAIA（通用助手）、OSWorld（桌面助理） | 最近：仍是代理，分布不等于你的流量 |

**轴三：交互形态——单轮 / 多轮 / 环境**

| 形态 | 判定特点 | 代表 | 工程含义 |
|---|---|---|---|
| 单轮问答 | 精确匹配 / 选择题判分，天然抗 judge 偏差 | GAIA、HLE、MMLU | 便宜、可高频跑，但测不了规划与工具 |
| 多轮对话 | 终态断言 + 政策遵循；需用户模拟器 | τ-bench / τ²-bench | 模拟器本身是效度来源（见 2.4 与易错点 7） |
| 环境交互 | 沙箱环境 + 终态检查脚本 | WebArena、OSWorld、Terminal-Bench、SWE-bench | 环境搭建/重置成本高，需 Docker/VM 化与并行 |

多数 agent benchmark 是三轴的复合体：τ-bench = 静态 × 应用型 × 多轮对话；Terminal-Bench = 静态（版本化）× 领域型 × 环境交互。**定位三轴之后，还要追问两件事：它怎么判分（2.3）、它的分数还新鲜吗（2.4–2.6）。**

### 2.2 主流 Agent Benchmark 全景速览

**演进时间线（2024–2026，来自 `_research/02-agent-benchmarks.md`）：**

- **2024 上半年 · 环境奠基期**：WebArena / VisualWebArena / OSWorld / WorkArena 确立"自托管沙箱环境 + 程序化判定"范式；GAIA（2023 底发布）确立"结果精确匹配 + 难度分级"的通用助手范式；τ-bench 把对话式工具 Agent 与用户模拟器引入评测。
- **2024 下半年 · 软件工程爆发期**：SWE-bench 成为事实标准，Verified / Multimodal 变体相继出现；Agent-as-a-Judge 开启"用 Agent 评 Agent"；WindowsAgentArena 把 Windows 桌面环境工程化。
- **2025 · 难度军备与可靠性转向**：SWE-bench 分数逼近 70%+ 后，社区转向更难、抗污染的基准（SWE-bench Pro、Terminal-Bench 2.0 Hard、BrowseComp、HLE）；τ²-bench 用"双控"解决模拟器泄题；pass^k / 多次采样成为标配。
- **2026 · 工业化与信任危机并存**：Terminal-Bench 论文（ICLR 2026）把终端 Agent 评测标准化；同时 HAL / AI Agent Index 等系统性结论动摇了"一个分数定优劣"的文化——评测重心从公开排行榜转向私有 golden set + 领域定制套件。

**主表：12 个必须认识的 benchmark**（数字均出自素材调研报告）

| Benchmark（arXiv，年份） | 机构 | 测什么 | 怎么判 | 核心指标 | 关键数字 / 已知问题 |
|---|---|---|---|---|---|
| τ-bench（[2406.12045](https://arxiv.org/abs/2406.12045)，2024） | Sierra | 客服型 Agent：多轮对话 + 遵守政策文档 + 调用工具 | 终态数据库比对，无需人评 | **pass^k** | retail 115 + airline 50 任务；GPT-4o retail pass^1 ≈60%（官方榜单 60.4%；摘要口径不足 50%），pass^8 ≈25%（摘要 <25%） |
| τ²-bench（[2506.07982](https://arxiv.org/abs/2506.07982)，2025） | Sierra | 双控对话：用户侧也是有工具的 Agent，信息不对称 | 同上 | pass^k | 各家分数相对 τ-bench 显著下降——此前高分部分来自模拟器"配合性泄题" |
| GAIA（[2311.12983](https://arxiv.org/abs/2311.12983)，2023，ICLR'24） | Meta AI + HF + AutoGPT | 通用助手："人类觉得简单、AI 觉得难"的 466 题，L1/L2/L3 | 短答案精确匹配 | 准确率 | 发布时人类 92% vs GPT-4+插件 ≈15%；2025 年顶级系统进入 70–80% 区间（榜单按月变动），L1 接近饱和 |
| AgentBench（[2308.03688](https://arxiv.org/abs/2308.03688)，2023，ICLR'24） | 清华 THUDM | LLM-as-Agent 综合能力，8 个交互环境（POMDP 形式化） | 各环境原生判定 + 标准化聚合 | 聚合分 | GPT-4 大幅领先同期开源模型；多数子环境如今已饱和，主要作历史基线 |
| SWE-bench（[2310.06770](https://arxiv.org/abs/2310.06770)，2023，ICLR'24） | Princeton 等 | 真实 GitHub issue → patch（12 个 Python 仓库、2294 任务） | FAIL_TO_PASS / PASS_TO_PASS 测试 | resolved 率 | 发布时最好 ≈3%；SWE-agent+GPT-4 12.5%；Claude 3.5 Sonnet+SWE-agent 49%；2025 头部 >70% |
| SWE-bench Multimodal（[2410.03859](https://arxiv.org/abs/2410.03859)，2024，ICLR'25） | Princeton 等 | JS / 前端视觉软件域（17 仓库、617 issue + 截图） | 同上 | resolved 率 | GPT-4o+SWE-agent 在 Python Lite 约 33%，在 Multimodal 跌至个位数~10%——语言/模态分布不外推 |
| Terminal-Bench（[2601.11868](https://arxiv.org/abs/2601.11868)，2026，ICLR'26） | Stanford + Laude Institute | 终端/命令行 Agent：Docker 容器 + 自然语言指令 | 自动验证脚本（pytest 式断言） | 任务成功率 | 初版 80 任务；2025-07 的 TB 2.0 Hard 精选 89 个高难任务；头部 50%+ 到长尾 <10%，**harness 效应**为核心发现 |
| BFCL（Gorilla [2305.15334](https://arxiv.org/abs/2305.15334)【未核实】，2023 起） | UC Berkeley | 函数调用能力：v1 AST+可执行验证；v3（2025-02）加多轮、缺失函数/参数、幻觉检测 | AST 匹配 + 可执行验证 | 总分 / 子项分 | 头部总分 85–95%，但"缺失函数/相关性检测"子项普遍掉 10–30 分——"知道何时不调用"仍是短板 |
| WebArena（[2307.13854](https://arxiv.org/abs/2307.13854)，2023，ICLR'24） | CMU 等 | 自托管真实功能网站集群（电商/GitLab/论坛/地图/CMS），812 任务 | 功能性检查（URL/页面终态/DB 状态） | 成功率 | 发布时 GPT-4 系 ≈14%，人类 78%；2025 最佳 >60%，出现饱和压力 |
| OSWorld（[2404.07972](https://arxiv.org/abs/2404.07972)，2024，NeurIPS'24） | XLANG Lab | 真实 OS 虚拟机（Ubuntu/Windows/macOS）369 个开放式操作任务 | 执行脚本检查终态（文件/系统设置） | 成功率 | 人类基线 72.4%，发布时最好多模态 Agent ≈12%；2025 头部 40%+（369 题全集口径；OSWorld-Verified/厂商口径下 Sonnet 4.5/Opus 4.5 已达 61.4%/66.3%，2025.9/11，见主手册第 8 章）；判定脚本脆弱是已知痛点 |
| WorkArena / ++（[2403.07718](https://arxiv.org/abs/2403.07718)【未核实】/ [2407.05291](https://arxiv.org/abs/2407.05291)，2024） | ServiceNow | 企业 SaaS 工作流：表单/列表/知识检索/服务目录下单；++ 加组合式规划 | 领域专家定义的终态断言 | 成功率 | v1 约 33 任务；最好商用模型仅约两成——企业私有系统的隐性知识是真实瓶颈 |
| HLE（Humanity's Last Exam，[2501.14249](https://arxiv.org/abs/2501.14249)，2025） | CAIS + Scale AI 等 | 约 3000 道专家级前沿知识难题（100+ 学科，约 1/4 多模态） | 精确匹配 + 污染审计 | 准确率 | 发布时最强前沿模型 <10%；2025 年内推理模型推到 30%+，再验"基准两年饱和律"；部分题目有歧义，社区众包修订中 |

**补充速览**（开放网络与企业桌面两条支线）：

| Benchmark | 测什么 | 关键数字 / 已知问题 |
|---|---|---|
| BrowseComp（OpenAI 博客，2025-04，无 arXiv） | 1266 道"答案在互联网上但极难检索到"的题；题面不公开以防污染 | Deep Research ≈51.5%，普通 GPT-4o 级浏览仅 ≈2%；闭源题面无法被第三方审计 |
| AssistantBench（[2407.15711](https://arxiv.org/abs/2407.15711)，2024） | 33 道开放网络耗时型任务（人类平均 15 分钟+） | 最好的 Web Agent 准确率仅 ~18%；"题目可行性验证"流程值得借鉴 |
| WebVoyager（[2401.13919](https://arxiv.org/abs/2401.13919)【未核实】，2024） | 真实网站（15 站点、643 任务）端到端多模态网页 Agent | 首创 GPT-4 自动评审（与人工一致性约 87%）；真实网站不可复现（改版/登录墙） |
| WindowsAgentArena（[2409.08264](https://arxiv.org/abs/2409.08264)【未核实】，2024） | 可大规模并行的 Windows 环境，154 任务 + Bonsai 基线 | Bonsai（GPT-4V）≈19.5%；并行化工程把评测吞吐提升一个数量级 |
| VisualWebArena（[2401.13649](https://arxiv.org/abs/2401.13649)【未核实】，2024） | WebArena 的多模态视觉扩展，910 任务 | 按图找商品、视觉问答式导航 |
| MLE-bench（[2410.07095](https://arxiv.org/abs/2410.07095)，2024） | 75 个 Kaggle 竞赛测 ML 工程 Agent | 竞赛式长程任务 |
| SWE-Lancer（[2502.12115](https://arxiv.org/abs/2502.12115)，2025） | 以真实自由职业平台计价任务（总额 $1M+）测工程 Agent 的经济价值 | "任务值多少钱"口径 |

**速览表的使用方式**：面试被问"你了解哪些 agent benchmark"时，不要背清单，而是按 2.1 的三轴归类 + 每个给一句"测什么 / 怎么判 / 一个数字 / 一个坑"。

### 2.3 判定方式谱系：benchmark 怎么给 agent 判分

Agent 轨迹千变万化，**精确匹配轨迹已淘汰**——会把大量合法但不同的解决路径判错。2024 年后的共识是**功能性正确判定**（execution-based evaluation）：

| 判定方式 | 机制 | 代表 | 优点 | 缺点 |
|---|---|---|---|---|
| 短答案精确匹配 | 归一化（大小写/标点）后字符串比对 | GAIA、HLE | 零 judge 偏差、零成本 | 只适合唯一答案题 |
| 执行测试 | patch 让 FAIL_TO_PASS 通过且 PASS_TO_PASS 不回归 | SWE-bench | 功能性判定的黄金标准 | "resolved"只保证过测试，不保证 patch 质量（可读性/副作用） |
| 终态断言 | 任务后跑检查脚本：文件内容、DB 状态、HTTP 响应、pytest 断言 | OSWorld、Terminal-Bench、WebArena、τ-bench | 抗话术干扰、全自动 | 判定脚本脆弱（终态检查误判）、环境搭建成本高 |
| LLM-as-a-Judge | rubric + judge 模型 | WebVoyager（与人工一致性 ~87%）【未核实】 | 覆盖开放性输出 | 位置/冗长/自我偏好偏差，需人工校准（详见第 E5 章） |
| Agent-as-a-Judge | 带工具的评审 Agent（可读代码、执行检查） | Agent-as-a-Judge（[2410.10934](https://arxiv.org/abs/2410.10934)，Zhuge et al.，ICML 2025）：DevAI 基准 55 个 AI 开发任务 + 365 条分层用户需求 | 与人类对齐度高，相比三位人类专家节省 97.72% 时间、97.64% 成本（场景特定值） | 需先人工校准；警惕与被测系统同源的自我偏好 |

**终态断言长什么样**（Terminal-Bench / τ-bench 式判定的最小示例，示意代码）：

```python
# 任务：在沙箱里取消订单 #A1024 并退款到原支付方式
# 判分不读 agent 的自然语言回复，只检查世界变成了什么样
def test_task_resolved(env):
    order = env.db.get_order("A1024")
    assert order.status == "CANCELLED"          # 终态：订单状态
    assert order.refund_amount == order.paid     # 终态：全额退款
    assert order.refund_channel == order.pay_channel  # 终态：原路退回
    assert env.mail.outbox_count(user=order.uid,
                                 subject_contains="取消确认") == 1  # 副作用：通知
    # 反向断言：不该发生的副作用
    assert not env.db.any_new_orders(user=order.uid)
```

对照 SWE-bench：`FAIL_TO_PASS` 测试必须转绿、`PASS_TO_PASS` 测试不得回归，两者都在干净环境执行——这就是"resolved"的操作性定义。

三条工程纪律：

1. **确定性优先**：能写测试就不用人评，能用终态断言就别判轨迹；LLM 评审只用于无法程序化的开放性输出，且人工抽样校准目标一致率 ≥85%（素材口径）。
2. **判分与能力解耦**：Terminal-Bench 配套 Terminus 参考 Agent（只给一个无头终端、纯 bash），把"harness 工程"与"模型能力"分开——排行榜必须声明用的是哪套 harness。
3. **可靠性与成本并报**：pass^k 要附带平均 token 成本/任务与失败重试成本；高 pass^k 但高成本的方案，单位经济学上可能不如低 pass^k + 人工兜底。

**pass^k 是 agent benchmark 的招牌指标**（τ-bench 提出）：同一任务独立运行 k 次**全部成功**的比例，`pass^k = |{task : ∀ i∈[1..k], success}| / |tasks|`；工程惯例 k 取 4–8，同时报告 pass@1 与 pass^k，两者差距反映系统方差。直觉：若每次成功率 p 且独立，pass^k ≈ p^k（p=0.9, k=8 时仅 0.43）。τ-bench 上 GPT-4o retail 域 pass^1≈60%（官方榜单 60.4%）→ pass^8≈25%（摘要 <25%）——这就是"单次看起来不错"与"可部署"之间的鸿沟。统计细节（iid 假设、不可从 pass@1 外推、必须报 n 与 CI）见第 E9 章 · 评估的统计学基础。争议面：有观点认为 pass^k 惩罚了"可诊断、可回滚的错误"，主张改报"失败模式分布 + 成本"；反方认为无人值守部署就是要高可靠性，pass^k 是最低标准。

### 2.4 污染：机理、检测四范式与军备竞赛

**机理**：公开题面进入训练语料 → 模型"背过题" → 分数虚高。SWE-bench 的 GitHub issue 文本大量出现在训练语料中，被普遍怀疑贡献了部分分数增长；GAIA / HLE 题目同样面临泄露。根本难题是举证：闭源模型不公开训练数据，且题目若本来就在公开网络语料里，"见过"是否等于"作弊"？实践者的折中立场是：**见过 ≠ 有罪，但分数必须按"可能见过"折价**——这正是 LiveCodeBench 式时间截止成为硬标准的原因。

**检测四范式**（来自 `_research/05-benchmark-dynamics.md`）：

| 范式 | 原理 | 代表方法（arXiv，年份） | 适用与局限 |
|---|---|---|---|
| 成员推断（MIA） | 训练过的文本似然更高 | Min-K% Prob（[2310.16789](https://arxiv.org/abs/2310.16789)，2023，ICLR'24 oral）：取最低 K%（默认 20%）token 的 log-prob 均值做成员性分数，只用 API 概率即可 | 在 WikiMIA-632 上 74.1% 成员推断准确率；对改写不敏感；需校准阈值；闭源模型可能平滑概率 |
| 语义级泄漏 | 模型记的是"题"不是"字符串" | 翻译/改写变体上的异常增益（[2311.04850](https://arxiv.org/abs/2311.04850)，Tencent AI Lab，2023）：GSM8k/TruthfulQA 翻译成其他语言后仍有记忆信号，且英文原版记忆强于翻译版 | 需可对照的变体集；与"合理泛化"难划界 |
| 格式敏感性 | 捷径表现为对表面结构的依赖 | 选项置换一致性、字母偏置（[2503.23483](https://arxiv.org/abs/2503.23483)，2025）；另一面证据：指令微调模型其实比想象中鲁棒（[2404.08382](https://arxiv.org/abs/2404.08382)，2024） | 只能作辅助证据——"对顺序鲁棒"本身可以被训练出来 |
| Canary strings | 预埋唯一字符串，探测复现能力 | 源头是 Carlini 等的训练数据提取（[2012.07805](https://arxiv.org/abs/2012.07805)，Google，2020）；私有题集每题埋 1–2 个独特字符串/假事实，定期用补全与问答探测市面模型 | 工业界私有评测标配；**只能证明"见过"，证不了"没见过"** |

**审计流程模板**：字符串/n-gram 重叠 → 嵌入相似度（与公开题库、模型输出对比）→ Min-K% 概率审计（若可得 logprob）→ canary 探测 → 变体差分（改写前后分差）。**任何单一信号都不足以定罪，组合证据 + 统计显著性才下结论。**

**污染军备竞赛与对决策的扭曲**：

- 防守方的结构性手段：时间截止（只用 cutoff 后的题）、私有 holdout（SWE-bench Pro，[2509.16941](https://arxiv.org/abs/2509.16941)【未核实】，私有测试 + 长程任务）、闭源题面（BrowseComp）、canary、定期版本化刷新（Terminal-Bench 1.0 → 2.0）、合成数据（SWE-smith，[2504.21798](https://arxiv.org/abs/2504.21798)，bug 注入批量合成 5 万级任务）。
- 对决策的扭曲：Sean Grove（OpenAI）*The Illusion of Model Improvement*（2024-10，未上 arXiv）用同一模型家族的不同数据混合/检查点在大量基准上实验，发现**基准分数差异的很大一部分来自评测集划分与数据泄漏的巧合，而非模型真实改进**。
- 学界与工业界的信任差在扩大，共识渐成：**单一公开榜单不可作为发布决策依据**。

### 2.5 饱和与崩塌：MMLU 教训与 Goodhart

**饱和的判定**：当 top 模型准确率 >~90% 且置信区间重叠时，基准失去排序力（天花板效应）。MMLU 在 2024 年即处于此状态（GPT-4o/o1 系 87–90%+）。**"基准两年饱和律"**在各处被验证：GAIA 15% → 70–80%（2023→2025）、WebArena 14% → 60%+、SWE-bench 3% → 70%+、HLE <10% → 30%+（仅一年内）。

**MMLU 的双重崩塌**——不只是饱和，还有质量：

| 事件 | 内容 | 数字 |
|---|---|---|
| MMLU-Redux（[2406.04127](https://arxiv.org/abs/2406.04127)，2024） | 对 57 个 subject 各抽 30 题（共 2,908 题）多人重标注 | 约 **10.09%** 的题存在答案错误或题面歧义；修复后模型的准确率**与相对排名都变化**——"权威分数"相当一部分测的是噪声 |
| MMLU-Pro（[2406.01574](https://arxiv.org/abs/2406.01574)，2024） | "加难"路线：选项 4→10 个、题目推理化、新题源 | 12,032 题，难度提升 16%–32%；GPT-4 级模型从 MMLU 近 90% 跌至 50–60%，恢复头部区分度 |

两条路线——**修数据**与**提难度**——成为此后所有老牌 benchmark 的标准动作。但注意 MMLU-Pro 自身也在快速逼近饱和，且 10 选项放大了长题干下的上下文长度效应。

**Goodhart：benchmark 崩塌的第三重力量**。当 benchmark 分数成为营销 KPI 或 RL 奖励，优化压力会绕开真实能力：Scaling Laws for Reward Model Overoptimization（[2210.10760](https://arxiv.org/abs/2210.10760)，OpenAI，2022）给出定量形态——以 KL(π‖π_ref) 为横轴，proxy（benchmark）奖励单调上升而 gold（真实能力）**先升后降**。AlpacaEval 的长度 gaming（把输出调啰嗦就能刷分）是经典案例；2026 年这一动态已进入多智能体合规评测（Beyond Goodhart's Law，[2606.07805](https://arxiv.org/abs/2606.07805)，2026：当奖励偏向"完成任务"时，agent 对流程约束的遵守退化）。

**修复手段谱系**（按投入从低到高）：

| 手段 | 代表 | 一句话 |
|---|---|---|
| 加难 | MMLU-Pro、HLE | 把分数压回 10–60% 区间恢复区分度；代价：难题样本少、方差大、与用户价值相关性弱 |
| 换源 | LiveBench | 用新近来源（竞赛/论文/新闻）换题 |
| 动态化 | DyVal、LiveCodeBench | 让题目可再生（见 2.6） |
| 专家化 | HLE | 专家出题 + 难度校准 + 污染审计 |
| 对抗化 | Agent Island（[2605.04312](https://arxiv.org/abs/2605.04312)，2026） | 多智能体博弈：对手自适应变强（抗饱和）、交互轨迹无法提前记忆（抗污染） |

**生命周期管理**（把基准当传感器管理）：每个基准登记版本、发布日期、难度分布、已知错误率、预计饱和时间、退役标准——例如 **top 模型 >92% 且 CI 重叠 ⇒ 降级为回归监控，不再用于选型**。

### 2.6 动态基准：四种机制与代价

动态化是对抗污染与饱和的结构性解法，但每种机制都有自己的代价：

| 机制 | 代表（arXiv，年份） | 原理 | 优点 | 代价 |
|---|---|---|---|---|
| 时间截止线 | LiveCodeBench（[2403.07974](https://arxiv.org/abs/2403.07974)，2024） | 持续从 LeetCode/AtCoder/Codeforces 抓新题，每题带发布时间戳；只用晚于模型数据截止日的题 | "污染距离"可量化、可复现；支持代码生成/自我修复/执行预测/测试输出预测四类任务 | 依赖领域的新题供给；闭源模型的"数据截止声明"不可尽信，需 canary 抽查 |
| 定期轮换 | LiveBench（[2406.19314](https://arxiv.org/abs/2406.19314)，2024） | 题目取自数学竞赛/arXiv/新闻等新近来源，按月换题；全客观真值 + 自动评分（无 LLM judge），覆盖六类任务 | 抗污染三要素（时间新鲜度 + 客观评分 + 版本轮换）；发布时领先模型仍 <70% | **跨版本不可直接比较**（2024-07 版与 2025 版分数无可比性），必须 pin 版本号并归档历史答案 |
| 程序化生成 | DyVal（[2309.17167](https://arxiv.org/abs/2309.17167)，ICLR'24）、DyVal 2（[2402.14865](https://arxiv.org/abs/2402.14865)，2024）、DynaMath（[2411.00836](https://arxiv.org/abs/2411.00836)，2024）、UGMathBench（[2501.13766](https://arxiv.org/abs/2501.13766)，2025） | benchmark = 采样器 + 求解器验证；DAG/参数模板/探测 agent 自动出题 | 机制上免疫记忆污染；带难度旋钮；可做变体族鲁棒性测量 | 题目分布窄、偏合成，需与真实分布题目混合 |
| 保义翻新 | Is Your Benchmark Still Useful?（[2503.06643](https://arxiv.org/abs/2503.06643)，2025） | 对存量题库做保义（meaning-preserving）改写再制造 | 比推倒重来便宜，保留题面分布与可比性；适合私有集治理 | 改写质量控制难（难度不变、答案唯一），需锚点模型校准 |

**动态化的关键证据链**：

- DyVal 上动态题表现与 MMLU、Big-Bench 静态子集高度相关（效度成立），但模型间差距被显著拉开——静态并列的模型在动态题上分出高下。
- DyVal 2 的核心发现：**静态基准分数与动态探测分数显著脱钩**——静态高分模型在动态生成的探测题上准确率差距达两位数百分点，说明静态分数高估了泛化推理能力。
- GSM-Symbolic（[2410.05229](https://arxiv.org/abs/2410.05229)，Apple，ICLR'25）：把 GSM8K 每题生成 100 个符号变体（改名字/数字/语序），部分模型准确率**相对下降最多约 65%**；加入单个无关从句（GSM-NoOp）可使准确率相对下降约 39%。**脆弱性而非推理能力，才是相当一部分分数的主要成分。**
- 由此的测量升级：对题 q 生成变体族 {q₁..q_k}，报告 E[acc] 与 Var[acc]，以及扰动敏感度 = 原始分 − 变体族均分；敏感度异常大 ⇒ 记忆或脆弱推理。变体族天然免疫记忆污染。

**动态化的未解难题**：测量连续性。LiveBench 换题后历史分数失效，排行榜变成"当前快照"；生成器的难度漂移同样需要校准。动态化解决污染，却引入跨期可比性问题——引用动态基准分数时永远带上版本号。

### 2.7 选型策略：三层互补与"只选一个汇报"

**核心框架：公开 benchmark（外部坐标）+ 私有 golden set（真实业务）+ 在线信号（地面真值），三层各司其职、互相校验。**

| 层 | 角色 | 代表 / 做法 | 局限 |
|---|---|---|---|
| 公开 benchmark | 外部坐标：能力画像、行业对标、候选初筛 | GAIA / SWE-bench Verified / LiveBench / Arena | 污染与饱和、分布不匹配（SWE-bench Multimodal：Python 33% → JS 个位数）、跨基准相关性低 |
| 私有 golden set | 发布门禁：真实业务分布、对齐产品目标 | 自建"τ-bench 式"套件：政策文档/知识库 + 工具（mock API 即可）+ 用户模拟器 + 终态断言；100–300 任务、每题 4–8 次采样、汇报 pass^k | 建设与维护成本高；需抗污染纪律（分层公开/私有、canary、版本化注新） |
| 在线信号 | 地面真值：用户与业务的最终裁决 | 转人工率、重复追问率、投诉率、满意度、任务完成率、工单闭环率（详见第 E12 章） | 延迟大、混淆因素多、不可完全归因到模型 |

**选型决策流程**（每一步排除一类风险）：

```
公开排行榜（LiveBench / LiveCodeBench / Arena）初筛   —— 排除明显落后的候选（抗饱和/污染由榜单自身机制保证）
        ↓
自建私有集复测（含 canary 与变体族）                   —— 排除分布不匹配与"见过题"的候选
        ↓
小流量 A/B / 影子模式                                  —— 排除离线-线上不一致
        ↓
决策（以业务指标为准）                                 —— Goodhart 防线：分数只用于淘汰，不用于加冕
```

**"只能选一个向老板汇报，选哪个"的答题框架**（面试高频开放题）：

1. **有私有集时**：选私有 golden set 上的业务口径指标（任务完成率 / pass^k，带 CI）。理由：它是唯一分布与业务一致、判定与产品目标对齐、且抗污染的测量；公开榜单分数只作为附录里的能力画像。
2. **没有私有集时**（诚实的第二答案）：选与产品形态最接近的公开基准——客服选 τ-bench（报 pass^k 而非 pass@1）、代码选 SWE-bench Verified、通用助手选 GAIA——并**主动声明它是代理指标**，同时把"建设私有集"列为下一步。
3. **永远不做的事**：拿单一公开榜单的聚合分当发布决策依据——HAL / AI Agent Index（Princeton SAgE，2025）发现不同 agent 基准之间分数相关性很低、且与真实用户满意度弱相关（HAL 具体 arXiv ID 待核实）；跨基准外推不成立。

**抗 Goodhart 制度设计**（三条）：(a) 保留一个永不对外宣传的内部 holdout，只用于内部决策；(b) 不把任何单一 benchmark 设为团队 KPI，改用基准组合 + 人评 + 线上指标的多信号决策；(c) 定期核对 proxy（benchmark 分）与 gold（用户满意度/留存）的相关性，相关性衰减即触发评测集更换。

### 2.8 Arena vs 静态 Benchmark：各测什么、何时信谁

| 维度 | Chatbot Arena（人类偏好竞技场） | 静态 benchmark |
|---|---|---|
| 测什么 | 真实分布用户提问下的人类偏好（有用性 + 风格） | 预定义任务的正确率 |
| 题目来源 | 实时用户提问，天然难以污染（主观但不可泄漏） | 固定题集，有污染与饱和风险 |
| 指标 | Bradley-Terry + bootstrap CI（[2403.04132](https://arxiv.org/abs/2403.04132)，LMSYS，ICML'24；论文时 240K+ 投票，如今数百万级） | 准确率 / pass 率 |
| 已知偏差 | 风格偏好（长度/markdown）；可被少量操纵票影响排名（[2501.17858](https://arxiv.org/abs/2501.17858)，2025）；丢一小撮票顶部排名就可能变（[2508.11847](https://arxiv.org/abs/2508.11847)，2025） | 污染、饱和、格式捷径、单点方差（GSM-Symbolic） |
| 典型 CI | bootstrap CI 通常宽 5–15 Elo 分 | 依题量而定（见第 E9 章样本量公式） |
| 适用 | 开放式对话、写作、助手体验的相对排序 | 能力下限、回归监控、硬任务（代码/数学/工具） |

**静态榜单与竞技场的桥梁：Arena-Hard**（[2406.11939](https://arxiv.org/abs/2406.11939)，LMSYS，ICML'25）：BenchBuilder 流水线从 Arena 真实投票与 WildChat 中聚类蒸馏出 500 道高难度 prompt（Arena-Hard-Auto），用强模型 judge 做成对比较、再用 BT 把胜率转化为分数——与 Chatbot Arena 人类排名相关性 **98.6%**，区分度约为 MT-Bench 的 3 倍，成本 **<$20**。这是"离线自动评测对齐在线竞技场"的模板：固定一个参考模型，报告其他模型的 BT 分数而非裸胜率。

**风格之争与"指标必须声明语义"**：judge 与人类都系统性偏好更长回答，Length-Controlled AlpacaEval（[2404.04475](https://arxiv.org/abs/2404.04475)，Stanford，2024）用回归把长度固定在参考值后计算边际胜率：与 Arena 的 Spearman 相关性从 0.94 升到 **0.98**，verbosity 操纵的胜率增益从 ~12% 压到 ~3%。去偏派认为风格是认知偏差必须剔除；保留派认为排版详尽度本身就是产品价值。LMSYS 的解法是**同时发布 overall 与 style-controlled 两个榜单**——引用任何 Arena 类分数，先问清它是哪个口径。

**何时信谁（决策表）**：

| 场景 | 优先信 | 原因 |
|---|---|---|
| 两个模型谁写代码更强 | 静态（SWE-bench Verified / LiveCodeBench） | 有执行测试的客观判定，偏好投票测不出正确性 |
| 两个模型谁聊天体验更好 | Arena（style-controlled 口径） | 偏好本就是被测对象 |
| 候选模型初筛 | 公开静态榜（LiveBench 类抗污染榜） | 便宜、快、可复现 |
| 发布门禁 | 都不是——用私有集 + 在线信号 | 见 2.7 三层互补 |
| 相邻两名分差 2–5 分 | 都不信——视为统计不可区分 | bootstrap CI 常宽 5–15 Elo 且重叠；CI 重叠的排名应报告为"不可区分组" |

统计纪律（详见第 E9 章）：报告 CI 而非点估计；用 BT 联合估计而非增量 Elo；比较用配对 bootstrap 直接看分差；重复 ≥3 次——单次运行的排名翻转概率不可忽略（[2509.24086](https://arxiv.org/abs/2509.24086)，2025），即使 temperature=0 + 固定 seed 仍存在非确定性（[2410.03492](https://arxiv.org/abs/2410.03492)，2024）。

---

## 三、面试高频考点

| # | 考点 | 分级 | 一句话考察意图 |
|---|---|---|---|
| 1 | Benchmark 三轴分类学：静态/动态 × 能力/领域/应用 × 单轮/多轮/环境 | ⭐ | 能否拿到一个陌生 benchmark 先定位再使用，而不是背清单 |
| 2 | 主流 agent benchmark 速览：τ-bench / GAIA / SWE-bench / OSWorld / Terminal-Bench 各测什么、怎么判 | ⭐ | 知不知道每个基准的判定方式与一个标志性数字 |
| 3 | 判定方式谱系：精确匹配 → 执行测试 → 终态断言 → judge；轨迹匹配为何淘汰 | ⭐⭐ | 是否理解"功能性正确判定"与"grade the outcome, not the path" |
| 4 | pass^k：τ-bench 60%→25% 的鸿沟，为什么必须与 pass@1 并报 | ⭐⭐ | 能否区分"单次看起来不错"与"可部署"，知不知道 k 取 4–8 的惯例 |
| 5 | 污染检测四范式：Min-K%（74.1%）/ 语义变体 / 格式敏感性 / canary | ⭐⭐ | 知不知道字符串匹配审计会漏掉语义级泄漏，canary 只能证"见过" |
| 6 | MMLU 崩塌双路线：Redux 修数据（~10% 坏题）vs MMLU-Pro 提难度（+16–32%） | ⭐⭐ | 能否讲清"饱和 + 质量"双重问题与两条修复路线的代价 |
| 7 | 动态基准四机制：时间截止 / 轮换 / 程序化生成 / 保义翻新，各自代价 | ⭐⭐ | 是否理解 LiveBench 牺牲跨版本可比性、生成器分布偏合成 |
| 8 | GSM-Symbolic 脆弱性：变体掉 65%、无关从句掉 39%，单点分数不可信 | ⭐⭐ | 能否从"点估计"升级到"变体族均值 ± 方差"的测量观 |
| 9 | Arena vs 静态 benchmark：各测什么、何时信谁；Arena-Hard 98.6% 相关性 | ⭐⭐⭐ | 能否给出场景化的"信谁"决策表，知道 style control 与两套榜单 |
| 10 | 三层互补选型：公开 benchmark + 私有 golden set + 在线信号；决策流程每步排除什么风险 | ⭐⭐⭐ | 是否具备"分数只用于淘汰、不用于加冕"的决策架构 |
| 11 | Goodhart 与基准生命周期：holdout、KPI 反模式、退役标准（top>92% 且 CI 重叠） | ⭐⭐⭐ | 有没有"benchmark 是传感器，会老化会被作弊"的治理意识 |
| 12 | harness 效应与跨基准低相关：Terminal-Bench 同一模型换 harness 分数大变；HAL 结论 | ⭐⭐⭐ | 能否批判"排行榜测的是模型还是 harness+模型"，拒绝一个分数定优劣 |

---

## 四、经典面试题与参考答案

#### 题 1（基础）：你会怎么给 benchmark 分类？静态与动态的本质区别是什么？

**参考答案：** 我用三条轴定位一个 benchmark。①**更新形态**：静态（固定题集，如 GAIA、SWE-bench、OSWorld）vs 动态（持续更新或可生成，如 LiveBench、LiveCodeBench、DyVal、Chatbot Arena）。②**定位**：能力型测单项能力（BFCL、HLE）、领域型测行业环境（SWE-bench、WorkArena）、应用型测端到端产品形态（τ-bench、GAIA、OSWorld）。③**交互形态**：单轮问答 / 多轮对话 / 环境交互。静态与动态的本质区别是**题目的时间属性**：静态集一旦公开就进入"污染倒计时"，且分数逼近天花板后失去区分度；动态集用轮换、时间截止或程序化生成保持新鲜度，代价是跨版本不可直接比较——所以引用动态基准必须 pin 版本号。分类的用途是判断外推性：一个静态、能力型、单轮的基准分数，对"我的客服 agent 能不能上线"几乎没有直接发言权。

#### 题 2（基础）：τ-bench、GAIA、SWE-bench、OSWorld 分别测什么？怎么判分？各给一个标志性数字。

**参考答案：** 四个基准覆盖四种形态。①**τ-bench**（Sierra，2024，arXiv 2406.12045）：客服型 agent——与 LLM 扮演的用户多轮对话、遵守政策文档、调用工具完成退票改址；判分用**终态数据库比对**；标志性数字：GPT-4o 在 retail 域 pass^1≈60%（官方榜单 60.4%；摘要口径不足 50%）但 pass^8 跌到 ≈25%（摘要 <25%）。②**GAIA**（Meta/HF/AutoGPT，2023，arXiv 2311.12983）：466 道"人类觉得简单、AI 觉得难"的通用助手题，L1/L2/L3 分级，**短答案精确匹配**；发布时人类 92% vs GPT-4+插件 ≈15%，2025 年顶级系统进入 70–80% 区间（榜单按月变动）。③**SWE-bench**（Princeton，2023，arXiv 2310.06770）：真实 GitHub issue 产出 patch，用 **FAIL_TO_PASS / PASS_TO_PASS 测试**判定；发布时最好系统 ≈3%，2025 年头部 >70%。④**OSWorld**（XLANG，2024，arXiv 2404.07972）：真实 OS 虚拟机里 369 个计算机操作任务，**执行脚本检查终态**；人类基线 72.4%，发布时最好 agent ≈12%，2025 年头部 40%+（369 题全集口径；Verified 口径更高，见主手册第 8 章）。判分方式的共同点是功能性判定——没有一个靠比对轨迹。

#### 题 3（进阶）：什么是 benchmark 污染？有哪些检测方法？为什么只做字符串匹配审计不够？

**参考答案：** 污染指题目进入训练语料导致分数虚高。检测有四类范式：①**成员推断**——Min-K% Prob（arXiv 2310.16789，ICLR 2024 oral）取一段文本中最低 K%（默认 20%）token 的对数概率均值做成员性分数，只需 API logprob，在 WikiMIA-632 上达到 74.1% 的推断准确率；②**语义级泄漏检测**——把题目翻译或改写后测分差，Tencent AI Lab（arXiv 2311.04850，2023）证明 GSM8k/TruthfulQA 的翻译变体上仍有可检测的记忆信号，且英文原版记忆强于翻译版；③**格式敏感性**——选项置换一致性、字母偏置（arXiv 2503.23483、2404.08382），但鲁棒性可以被训练出来，只能作辅助证据；④**canary strings**——私有题集埋独特字符串/假事实，定期探测（源头 arXiv 2012.07805）。字符串匹配不够，是因为模型记的是"题"不是"字符串"：改一个词、换个语言，记忆信号仍在。所以审计流程是组合拳：n-gram 重叠 → 嵌入相似度 → Min-K% → canary → 变体差分，任何单一信号都不定罪。实践立场：见过 ≠ 有罪，但分数必须按"可能见过"折价。

#### 题 4（进阶）：MMLU 出了什么问题？社区修复的两条路线各有什么代价？

**参考答案：** MMLU 是"饱和 + 质量"双重崩塌。质量侧：MMLU-Redux（arXiv 2406.04127，2024）对 57 个 subject 各抽 30 题、共 2,908 题重标注，发现约 **10.09%** 的题答案错误或题面歧义，修复后模型的准确率与相对排名都会变化——说明"权威分数"相当一部分测的是噪声。饱和侧：2024 年 GPT-4o/o1 系模型已到 87–90%+，天花板效应让基准失去排序力。两条修复路线：①**修数据**（Redux 派）：重标注、剔除坏题——代价是工作量随题库线性增长，且只解决质量不解决饱和；②**提难度**（MMLU-Pro 派，arXiv 2406.01574）：选项 4→10 个、题目推理化、引入新题，12,032 题，难度提升 16%–32%，GPT-4 级模型从近 90% 跌回 50–60%——代价是 10 选项放大上下文长度效应，且新基准照样会快速饱和。更深的教训：任何沿用公开题库的评测都要先做 item 级质检（抽样重标注 + 双评），否则测量误差会混入模型差异；报告分数时注明用的是原版还是修复版。

#### 题 5（进阶）：动态基准有哪几种机制？各自的代价是什么？

**参考答案：** 四种机制。①**时间截止线**（LiveCodeBench，arXiv 2403.07974，2024）：题目带发布时间戳，只用晚于模型数据截止日的题，"污染距离"可量化可复现；代价是依赖领域的新题供给，且闭源模型的截止声明不可尽信，要 canary 抽查。②**定期轮换**（LiveBench，arXiv 2406.19314，2024）：按月换题、全客观自动评分，发布时领先模型仍 <70%；代价是**跨版本不可比**，必须 pin 版本号归档答案。③**程序化生成**（DyVal arXiv 2309.17167，DyVal 2 arXiv 2402.14865，DynaMath arXiv 2411.00836，UGMathBench arXiv 2501.13766）：benchmark = 采样器 + 求解器验证，机制上免疫记忆，还带难度旋钮；代价是分布偏合成，需与真实分布题目混合。④**保义翻新**（arXiv 2503.06643，2025）：对存量题库做保义改写再制造，成本低、保留分布，适合私有集治理；代价是改写质量控制难，需在锚点模型上做等难度校准。共同代价是测量连续性：动态化解决污染，却让排行榜从"连续量尺"变成"当前快照"，这是明确的 open problem。

#### 题 6（进阶）：Terminal-Bench 发现的"harness 效应"对"模型 A 比模型 B 强"这类结论意味着什么？评测设计上怎么隔离？

**参考答案：** Terminal-Bench（arXiv 2601.11868，ICLR 2026）在 TB 2.0 上观察到：各主流 coding agent 分数差异巨大（头部 50%+ 到长尾 <10%），且**同一模型换 harness（执行框架）分数变化显著**——排行榜测的其实是"harness + 模型"的组合，不是模型本身。这意味着跨团队、跨榜单比较时，"A 比 B 强"的结论可能完全由 harness 工程质量驱动；2025–2026 年开源 harness 生态爆发后，这直接影响"用哪个模型"的工程决策。隔离办法有四条：①模型对比时锁定 harness，harness 改动评估时锁定模型，分别报告；②采用标准参考 harness（如 Terminal-Bench 的 Terminus：只给无头终端、纯 bash），把执行框架与模型能力解耦；③报告时声明完整配置（harness 版本、观测表征、采样参数）——WebArena 的经验是 DOM/可访问性树表征的选择本身显著影响分数；④自建评测中把 harness 纳入被测系统整体，承认"我们测的是系统不是模型"，对外沟通时不偷换概念。

#### 题 7（进阶）：Chatbot Arena 和静态 benchmark 各测什么？你会在什么场景下信谁？

**参考答案：** 两者测的是不同构念。Arena（arXiv 2403.04132，LMSYS，ICML 2024）测**真实分布用户提问下的人类偏好**——有用性 + 风格的混合体，题目来自实时用户，天然难以污染；指标是 Bradley-Terry + bootstrap CI（论文时 240K+ 投票，CI 通常宽 5–15 Elo）。静态 benchmark 测**预定义任务的正确率**，有客观判定但面临污染与饱和。信谁的决策表：比较写代码能力，信静态（SWE-bench Verified / LiveCodeBench），因为偏好投票测不出正确性；比较聊天体验，信 Arena 且优先 style-controlled 口径——长度偏好是已知偏差，LC-AlpacaEval（arXiv 2404.04475）回归去偏后与 Arena 相关性 0.94→0.98，verbosity 刷分收益从 ~12% 压到 ~3%；候选初筛信抗污染的公开静态榜；发布门禁两者都不信，用私有集 + 在线信号。两个注意事项：相邻两名差 2–5 分在 CI 重叠时应视为统计不可区分；Arena 排名可被少量操纵票影响（arXiv 2501.17858）、丢一小撮票即可改变顶部排名（arXiv 2508.11847），排名是激励面，必须配审计。

#### 题 8（进阶）：GSM-Symbolic 的实验说明了什么？它对你设计内部评测有什么具体影响？

**参考答案：** GSM-Symbolic（arXiv 2410.05229，Apple，ICLR 2025）把 GSM8K 每题用 LLM 生成 100 个符号变体（只改名字、数字、语序），发现部分模型准确率相对下降最多约 65%；构造 GSM-NoOp 加入单个无关从句，又可使准确率相对下降约 39%。结论：**相当一部分"能力分"其实是记忆 + 脆弱模式匹配**——单题单次评测只是点估计，同分布同难度的变体之间分数波动巨大。对内部评测的三点影响：①关键能力点改用**变体族测量**：对题 q 生成变体族，报告 E[acc] ± Var[acc] 与"扰动敏感度"（原始分 − 变体族均分），敏感度异常大就标记为记忆或脆弱推理；②变体族天然免疫记忆污染，可把私有集的数值题参数化（UGMathBench 式随机参数，arXiv 2501.13766），实现无限防泄漏重采样；③报告纪律上，任何分数都要带 CI 与重复次数——这与 DyVal 2（arXiv 2402.14865）"静态高分模型在动态探测下掉两位数百分点"的证据链一致：对外部模型选型，尽量用自建的、对方未见过的题集复测。

#### 题 9（系统设计）：你负责为公司的客服 Agent 建立 benchmark 选型与评测策略。给出完整方案：用什么公开基准、怎么建私有集、怎么防污染、怎么判定、怎么汇报、怎么做决策。

**参考答案：** 分五层设计。①**公开基准（外部坐标）**：τ-bench / τ²-bench（arXiv 2406.12045 / 2506.07982）作为形态最接近的对照——它测的正是政策遵循 + 工具调用 + 多轮对话；函数调用底层能力用 BFCL 子项做画像（看"缺失函数/相关性"子项而非聚合分）。只用于行业对标与初筛，不进门禁。②**私有 golden set（发布门禁）**：仿 τ-bench 四件套自建——政策文档/知识库 + mock API 工具集 + LLM 用户模拟器（固定版本）+ 终态数据库断言；100–300 任务，覆盖触发/核心逻辑/产物质量/异常容错四场景（详见第 E3 章）；每题 4–8 次采样，汇报 pass@1 与 pass^k 及两者差距。③**抗污染纪律**：私有集永不入公开仓库/论文；每题埋 1–2 个 canary 字符串与假事实，定期探测；给每题记录 created_at，版本化注新；怀疑泄漏的题做保义改写轮换（arXiv 2503.06643）而非整套废弃。④**判定**：确定性优先——终态断言为主，开放性话术维度用 LLM judge，人工校准目标一致率 ≥85%（详见第 E5 章）；审计用户模拟器的泄题路径（τ² 的教训）。⑤**汇报与决策**：所有分数带 CI、重复 ≥3 次；门禁同时要求统计显著与最小可感知变化（第 E9 章）；发布决策 = 私有集门禁 + 灰度期在线信号（转人工率、重复追问率、投诉率，第 E12 章）双确认，离线升线上降则回滚。公开榜分只出现在能力画像附录里。

#### 题 10（开放）："如果只能选一个指标向老板汇报我们的 Agent 变强了，你选哪个？"

**参考答案：** 答题框架分三步。第一步，**先问有没有私有评测集**：有，就选私有 golden set 上的业务口径——客服 agent 选"任务完成率 + pass^8"（带 CI），因为它是唯一分布与业务一致、判定与产品目标对齐、抗污染的测量；公开榜单分数放附录做能力画像。第二步，没有私有集时给诚实的第二答案：选与产品形态最接近的公开基准——客服选 τ-bench（报 pass^k：GPT-4o retail pass^1≈60% 但 pass^8 只有 ≈25%，单报 pass@1 会系统性误导）、代码选 SWE-bench Verified、通用助手选 GAIA——并主动声明这是代理指标，把"两周内建私有集"列为行动项。第三步，**讲清为什么不选别的**：不选单一公开榜单——HAL / AI Agent Index（Princeton SAgE，2025）发现跨基准分数相关性低、与真实用户满意度弱相关；不选 Arena 名次——风格偏差 + CI 重叠 + 可操纵；不选离线 judge 均分——Goodhart 风险，benchmark 分数只用于淘汰候选、不用于加冕发布（arXiv 2210.10760 的 proxy-gold 曲线）。这道题的得分点是展示"指标选择 = 决策链路设计"，而不是报一个数字。

---

## 五、易错点 · 反直觉点

1. **误区：公开 benchmark 分数高 = 生产表现好。** 真相：跨基准分数相关性很低、与真实用户满意度弱相关（HAL / AI Agent Index，Princeton SAgE，2025）；分布也不外推——SWE-bench Multimodal（arXiv 2410.03859，2024）上 GPT-4o+SWE-agent 在 Python Lite 约 33%，到 JS+视觉域跌至个位数~10%。**记忆锚点：公开榜单是外部坐标，不是发布门禁。**
2. **误区：污染审计就是拿题面做字符串匹配。** 真相：模型记的是"题"不是"字符串"——翻译/改写变体上仍有可检测的记忆信号（arXiv 2311.04850，2023），必须做语义级审计（嵌入相似度 + 变体差分 + Min-K%）。**记忆锚点：背题背的是意思，不是原文。**
3. **误区：canary 没被探测出来，说明题目没泄漏。** 真相：canary 只能证明"见过"，证不了"没见过"——阴性结果不构成清白证据；私有集的保密纪律（不入库、不进 issue、不进论文附录）才是第一道防线。**记忆锚点：canary 是烟雾报警器，不是安检仪。**
4. **误区：基准饱和了，出更难的题就能解决。** 真相：难度军备竞赛是 treadmill——HLE（arXiv 2501.14249）发布时最强模型 <10%，一年内就被推理模型推到 30%+；且超难题测的是长尾知识，与用户价值相关性弱，难题集还样本少、方差大。**记忆锚点：更难 ≠ 更有用，只是把饱和推迟两年。**
5. **误区：动态基准解决了污染问题，可以放心用。** 真相：动态化用测量连续性换抗污染——LiveBench（arXiv 2406.19314）换题后历史分数失效，2024-07 版与 2025 版不可比；引用动态基准不 pin 版本号等于没引用。**记忆锚点：动态基准是快照，不是尺子。**
6. **误区：MMLU 分数仍然可以当"综合能力"指标。** 真相：约 10.09% 的题答案错误或歧义（MMLU-Redux，arXiv 2406.04127，2024），修复后排名都会变；且头部模型 87–90%+ 已近饱和。报告 MMLU 必须注明原版还是修复版。**记忆锚点：十分之一的尺子刻度本身是错的。**
7. **误区：用户模拟器配合得好，agent 分数高就是能力强。** 真相：τ-bench 的用户模拟器会向 agent 泄露关键信息，τ²-bench（arXiv 2506.07982，2025）引入双控后各家分数显著下降——此前高分部分来自"配合性泄题"。模拟器本身是被测系统的效度来源，换模拟器模型分数就会变，报告必须固定模拟器版本。**记忆锚点：考官递答案，考高分不算数。**
8. **误区：把 benchmark 分数直接设为团队 KPI 或 RL 奖励，分数涨了就是进步。** 真相：这是教科书级 Goodhart——proxy 奖励单调上升的同时 gold（真实能力）先升后降（arXiv 2210.10760，2022）；AlpacaEval 的长度 gaming 是现成案例。制度防线：永不宣传的内部 holdout、多信号决策、定期核对 proxy-gold 相关性。**记忆锚点：分数一旦成为目标，就不再是好测量。**
9. **误区：单次跑出的分数（或排行榜名次）就是模型的真实水平。** 真相：只改人名/数字/语序，分数相对掉最多 65%（GSM-Symbolic，arXiv 2410.05229）；单次运行排名翻转概率不可忽略（arXiv 2509.24086）；temperature=0 + 固定 seed 也仍有非确定性（arXiv 2410.03492）。可靠测量 = 重复 ≥3 次 + 变体族 + CI。**记忆锚点：单次分数是照片，分布才是本人。**

---

## 六、推荐资源

**核心论文**（来自 `_research/02-agent-benchmarks.md`、`05-benchmark-dynamics.md`、`04-statistics.md` 已核实清单；标注【未核实】者素材中未联网复核，引用前请二次确认）：

*Agent benchmark 全景*

| arXiv | 基准 | 年份 | 本章用到 |
|---|---|---|---|
| [2406.12045](https://arxiv.org/abs/2406.12045) | τ-bench（Sierra） | 2024 | 客服型评测范式、pass^k、终态 DB 断言；60%→25% |
| [2506.07982](https://arxiv.org/abs/2506.07982) | τ²-bench（Sierra） | 2025 | 双控用户模拟、泄题审计 |
| [2311.12983](https://arxiv.org/abs/2311.12983) | GAIA（Meta/HF/AutoGPT，ICLR'24） | 2023 | 精确匹配 + 难度分级；人类 92% vs 15% |
| [2308.03688](https://arxiv.org/abs/2308.03688) | AgentBench（清华，ICLR'24） | 2023 | 多环境聚合评测的套件范式 |
| [2310.06770](https://arxiv.org/abs/2310.06770) | SWE-bench（Princeton，ICLR'24） | 2023 | FAIL_TO_PASS/PASS_TO_PASS 测试驱动判定；3%→70%+ |
| [2410.03859](https://arxiv.org/abs/2410.03859) | SWE-bench Multimodal（ICLR'25） | 2024 | 语言/模态分布不外推：33%→个位数 |
| [2307.13854](https://arxiv.org/abs/2307.13854) | WebArena（CMU，ICLR'24） | 2023 | 自托管沙箱 + 功能性检查；14%→60%+ |
| [2401.13649](https://arxiv.org/abs/2401.13649) | VisualWebArena【未核实】 | 2024 | 多模态网页任务 |
| [2404.07972](https://arxiv.org/abs/2404.07972) | OSWorld（XLANG，NeurIPS'24） | 2024 | OS 级终态脚本判定；人类 72.4% vs 12% |
| [2409.08264](https://arxiv.org/abs/2409.08264) | WindowsAgentArena【未核实】（Microsoft） | 2024 | 并行化评测基础设施样板 |
| [2403.07718](https://arxiv.org/abs/2403.07718)【未核实】/ [2407.05291](https://arxiv.org/abs/2407.05291) | WorkArena / WorkArena++（ServiceNow） | 2024 | 企业 SaaS 评测；最好模型仅约两成 |
| [2601.11868](https://arxiv.org/abs/2601.11868) | Terminal-Bench（Stanford + Laude，ICLR'26） | 2026 | Docker + pytest + Terminus；harness 效应 |
| [2501.14249](https://arxiv.org/abs/2501.14249) | Humanity's Last Exam（CAIS + Scale 等） | 2025 | 专家出题 + 难度标定方法论；<10%→30%+ |
| [2407.15711](https://arxiv.org/abs/2407.15711) | AssistantBench（AI2） | 2024 | 题目可行性验证流程；最好 agent ~18% |
| [2401.13919](https://arxiv.org/abs/2401.13919) | WebVoyager【未核实】 | 2024 | 真实网站评测 + GPT-4 judge（与人工 ~87% 一致） |
| [2305.15334](https://arxiv.org/abs/2305.15334)【未核实】 | Gorilla / BFCL（UC Berkeley） | 2023 | 函数调用子项拆分：相关性/缺失函数是短板 |
| [2410.10934](https://arxiv.org/abs/2410.10934) | Agent-as-a-Judge（Zhuge et al.，ICML 2025） | 2024 | 带工具评审 Agent：DevAI 55 任务/365 需求；相比三位人类专家节省 97.72% 时间、97.64% 成本 |
| [2509.16941](https://arxiv.org/abs/2509.16941)【未核实】 | SWE-bench Pro（Princeton） | 2025 | 私有测试 + 长程任务的抗污染路线 |

*污染、饱和与动态基准*

| arXiv | 标题 | 年份 | 本章用到 |
|---|---|---|---|
| [2310.16789](https://arxiv.org/abs/2310.16789) | Detecting Pretraining Data from LLMs（Min-K% Prob / WikiMIA，ICLR'24 oral） | 2023 | 成员推断；WikiMIA-632 上 74.1% |
| [2311.04850](https://arxiv.org/abs/2311.04850) | Rethinking Benchmark and Contamination with Rephrased Samples（Tencent AI Lab） | 2023 | 语义级泄漏；翻译/改写变体记忆 |
| [2012.07805](https://arxiv.org/abs/2012.07805) | Extracting Training Data from LLMs（Carlini 等，Google） | 2020 | canary strings 方法源头 |
| [2406.04127](https://arxiv.org/abs/2406.04127) | Are We Done with MMLU?（MMLU-Redux） | 2024 | ~10.09% 坏题；修复后排名变化 |
| [2406.01574](https://arxiv.org/abs/2406.01574) | MMLU-Pro | 2024 | 加难路线：10 选项、+16–32%、90%→50–60% |
| [2406.19314](https://arxiv.org/abs/2406.19314) | LiveBench | 2024 | 月度轮换 + 客观评分；跨版本不可比 |
| [2403.07974](https://arxiv.org/abs/2403.07974) | LiveCodeBench | 2024 | 时间截止线与"污染距离" |
| [2309.17167](https://arxiv.org/abs/2309.17167) | DyVal（ICLR'24） | 2023 | 程序化生成基准的范式 |
| [2402.14865](https://arxiv.org/abs/2402.14865) | DyVal 2 | 2024 | 静态-动态分数脱钩，两位数百分点差距 |
| [2410.05229](https://arxiv.org/abs/2410.05229) | GSM-Symbolic（Apple，ICLR'25） | 2024 | 变体脆弱性：65% / 39%；变体族测量 |
| [2503.06643](https://arxiv.org/abs/2503.06643) | Is Your Benchmark Still Useful? | 2025 | 保义翻新存量题库 |
| [2503.23483](https://arxiv.org/abs/2503.23483) | Order Independence With Finetuning | 2025 | 选项顺序敏感性与置换平均 |
| [2404.08382](https://arxiv.org/abs/2404.08382) | Look at the Text | 2024 | 格式捷径检测的反面证据 |
| [2411.00836](https://arxiv.org/abs/2411.00836) | DynaMath | 2024 | 视觉数学的参数化生成管线 |
| [2501.13766](https://arxiv.org/abs/2501.13766) | UGMathBench | 2025 | 随机参数变体：最轻量的动态化 |
| [2210.10760](https://arxiv.org/abs/2210.10760) | Scaling Laws for Reward Model Overoptimization（OpenAI） | 2022 | Goodhart 的定量版：gold 先升后降 |
| [2605.04312](https://arxiv.org/abs/2605.04312) | Agent Island | 2026 | 多智能体博弈的对抗式动态评测 |
| [2606.07805](https://arxiv.org/abs/2606.07805) | Beyond Goodhart's Law（多智能体合规） | 2026 | 奖励偏向任务完成时流程遵守退化 |

*Arena 与统计纪律（详见第 E9 章）*

| arXiv | 标题 | 年份 | 本章用到 |
|---|---|---|---|
| [2403.04132](https://arxiv.org/abs/2403.04132) | Chatbot Arena（LMSYS，ICML'24） | 2024 | BT + bootstrap CI；240K+ 投票；CI 宽 5–15 Elo |
| [2406.11939](https://arxiv.org/abs/2406.11939) | Arena-Hard / BenchBuilder（ICML'25） | 2024 | 500 题蒸馏；与 Arena 相关性 98.6%；成本 <$20 |
| [2404.04475](https://arxiv.org/abs/2404.04475) | Length-Controlled AlpacaEval（Stanford） | 2024 | 长度回归去偏：0.94→0.98；verbosity 12%→3% |
| [2410.03492](https://arxiv.org/abs/2410.03492) | Quantifying Uncertainty in LLM Benchmark Scores | 2024 | temperature=0 仍非确定 |
| [2509.24086](https://arxiv.org/abs/2509.24086) | Do Repetitions Matter? | 2025 | 单次运行排名翻转不可忽略；重复 3–5 次 |
| [2501.17858](https://arxiv.org/abs/2501.17858) | Vote Rigging on Chatbot Arena | 2025 | 影响函数投票操纵 |
| [2508.11847](https://arxiv.org/abs/2508.11847) | Dropping a Handful of Preferences Changes Rankings | 2025 | 丢票敏感性；比较图均衡 |

**延伸阅读**（素材已核实）：SWE-smith（[2504.21798](https://arxiv.org/abs/2504.21798)，bug 注入合成 5 万级任务）；SWE-Lancer（[2502.12115](https://arxiv.org/abs/2502.12115)，$1M+ 计价任务）；MLE-bench（[2410.07095](https://arxiv.org/abs/2410.07095)）；AndroidWorld（[2405.14573](https://arxiv.org/abs/2405.14573)，参数化动态任务）；WebShop（[2207.01206](https://arxiv.org/abs/2207.01206)【未核实】，背景）；Mind2Web（[2306.06070](https://arxiv.org/abs/2306.06070)【未核实】，背景）；MT-Bench / LLM-as-a-Judge 起源（[2306.05685](https://arxiv.org/abs/2306.05685)，2023）。

**非 arXiv 材料**：

- BrowseComp：OpenAI 博客 "BrowseComp: A simple yet challenging benchmark for browsing agents"（2025-04），1266 题、闭源题面，无 arXiv 论文。
- BFCL 榜单：[gorilla.cs.berkeley.edu/leaderboard.html](https://gorilla.cs.berkeley.edu/leaderboard.html)，以博客/技术报告形式持续迭代。
- HAL / AI Agent Index（Princeton SAgE）：[hal.cs.princeton.edu](https://hal.cs.princeton.edu)，系统化运行多 agent 基准并分析跨基准相关性（具体论文 arXiv ID 待核实）。
- Sean Grove（OpenAI），*The Illusion of Model Improvement: Can LLM Benchmarks be Misleading?*（2024-10）：基准分数差异很大一部分来自数据划分与泄漏巧合，未上 arXiv。
- AlpacaEval（GitHub 项目）：长度 gaming 导致排行榜失真的经典案例。

**动手 labs**（纯标准库、固定种子、可复现）：

| lab | 你将验证 | 运行 |
|---|---|---|
| eval_lab08_statistics_ci.py | 分数带 CI 的必要性：Wilson 区间、bootstrap、样本量速查 | `cd evals-special/labs && python3 eval_lab08_statistics_ci.py` |
| eval_lab11_arena_bradley_terry.py | BT vs Elo、bootstrap 分差 CI、风格控制如何恢复真实排序 | `cd evals-special/labs && python3 eval_lab11_arena_bradley_terry.py` |
| eval_lab01_metric_system.py | pass@k 与 pass^k 随 K 分道扬镳（τ-bench 鸿沟的最小复现） | `cd evals-special/labs && python3 eval_lab01_metric_system.py` |
| eval_lab02_golden_dataset.py | 私有 golden set 的构建与治理流水线（入库标准、去重、版本化） | `cd evals-special/labs && python3 eval_lab02_golden_dataset.py` |

**章节交叉引用**：指标体系与 pass^k 口径（第 E2 章 · 评估指标体系）；私有集的用例设计与生命周期治理（第 E3 章 · 黄金数据集与用例设计）；judge 偏差与校准（第 E5 章 · 评分三层之二：LLM-as-Judge 深入）；用户模拟器与 fixtures 的工程实现（第 E8 章 · 对话 Agent 与仿真评测）；CI、bootstrap 与样本量公式（第 E9 章 · 评估的统计学基础）；在线信号与离线-线上对齐（第 E12 章 · 在线评估与数据飞轮）；本章全部论文的教学化综述（第 E14 章 · 前沿论文全景）；Airbnb/DoorDash/阿里/腾讯的私有评测实践（第 E15 章 · 工业实践案例研究）；主手册第 8 章 · Agent 评估与可观测性（Benchmark 一节的浓缩版）。
