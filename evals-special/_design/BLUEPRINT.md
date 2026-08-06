# Evals 特辑章节蓝图（BLUEPRINT）

写作智能体：先读 `_design/STYLE.md`（规范），再读本文件中你负责章节的 brief，
然后阅读 brief 指定的素材文件（`_research/` 下），最后写章节到指定路径。

章节文件命名：`chapters/E<NN>-<中文标题>.md`

---

## E00 特辑导读：Evals 体系全景
路径：chapters/E00-特辑导读：Evals 体系全景.md
Brief：
- 全特辑知识地图：为什么评（E01）→ 评什么（E02）→ 拿什么评（E03）→ 谁来评（E04-E06）→
  评什么形态（E07-E08）→ 怎么让分数可信（E09）→ 怎么用评测驱动开发（E10-E12）→
  外部坐标（E13-E15）。用一张 ASCII 全景图 + 一张"问题→章节"对照表。
- 与主手册第 8 章的关系（浓缩 vs 深挖）、与 labs 的对应表（11 个 eval labs 一览）。
- 三条学习路线：① 面试冲刺路线（2h）② 从零搭建评测体系路线（工程师，配 labs）③ 研究跟进路线（论文读者）。
- evals 领域 2024-2026 的"一张时间线"：关键论文与工业实践节点（从 _research/ 提炼 10-15 个节点）。
- 本导读同样遵循 6 模块结构（知识图谱=特辑地图；核心概念=evals 全局术语表 20 词；
  面试考点=全局高频 10 问；面试题=3 道宏观题；易错点=全局 8 大误区；资源=全特辑索引）。

## E01 为什么评估是 GenAI 工程的生命线
路径：chapters/E01-为什么评估是 GenAI 工程的生命线.md
Brief：
- 三大根本难题：非确定性、黑盒化、错误级联放大（用多步 agent 的具体例子展开级联放大）。
- 三大陷阱（Airbnb）：虚假信心（浅层 helpfulness 分）、未发现的回归、指标与产品目标脱节。
- 评估 vs 传统软件测试：输入空间/判定方式/回归语义/通过标准的差异对照表。
- "跑几条 case 感觉还行"为什么不够：四个具体失效场景（同 prompt 一次跑通≠稳定；
  改 prompt 改坏旧场景；前步小偏差被放大；结果对但路径错的假阳性）。
- 评估的四重身份：质量度量 / 发布门禁 / 迭代指南针 / 数据飞轮入口。
- 评估经济学：eval 成本 vs 线上失败成本的粗算框架。
- 素材：_research/00-industry-practice.md（Airbnb 背景节、腾讯痛点表）；_research/06-edd-simulation.md。

## E02 评估指标体系
路径：chapters/E02-评估指标体系.md
Brief：
- 指标分层：P0 上线门禁 / P1 版本比较 / P2 体验观察（阿里），配各层实例表。
- 五大维度（腾讯）：功能正确性 / 过程质量 / 效率与成本 / 鲁棒性与安全 / 体验与对齐——
  每个维度给子维度、评测方法、典型指标、落地优先级（照抄腾讯表格并扩充例子）。
- 核心指标精讲：pass@1/pass@k/pass^k（含数学定义与适用场景）、任务完成率、工具调用准确率、
  groundedness/幻觉率、误拒率/漏拒率、延迟 p50/p95/p99、成本 ¥/task。
- 一致性双指标：至少一次成功率 vs 连续成功率；生产系统为何看后者。
- 指标设计原则：可量化/可比较/可回归/可归因；门禁要带统计口径（置信区间+显著性+最小可感知变化）。
- 反模式：万能 helpfulness、Goodhart 定律实例（指标被刷爆的案例）。
- 素材：_research/00-industry-practice.md；_research/04-statistics.md（指标统计口径）。

## E03 黄金数据集与用例设计
路径：chapters/E03-黄金数据集与用例设计.md
Brief：
- 线上随机抽样的幸存者偏差；为什么"报告看起来不错"但关键问题漏掉。
- 四类来源：专家设计（定标准）/ LLM 扩展（先定结构字段再生成自然语言）/ 线上真实数据 / badcase 回流。
- 用例组织范式：触发→核心逻辑→产物质量→异常容错（腾讯四场景 + 正负向用例表）；
  核心逻辑用例量=其余三类之和的 2-3 倍；负向触发用例为什么必不可少（过度触发更难发现）。
- checklist 式场景 rubric（DoorDash：素食 taco 清单案例）：低方差信号，小样本也能迭代。
- Golden Set 规模经验：50-100（Airbnb）/ 50-200（阿里）/ 基线快照机制（腾讯：先跑一次→人工确认→快照为基线）。
- 数据集生命周期治理：入库标准（可复现/期望明确/根因清楚/代表性/已脱敏）、同簇去重、
  能力评测→回归评测的"毕业"机制、只增不减、长尾集/对抗集。
- 隐私合规：去标识化、用途限定（Airbnb 隐私注记）。
- 素材：_research/00-industry-practice.md；_research/02-agent-benchmarks.md（公开基准与私有集互补）。

## E04 评分三层之一：程序化评分
路径：chapters/E04-评分三层之一：程序化评分.md
Brief：
- 原则：确定性优先——"能用代码判断的绝不用模型"；三类评分器的成本/稳定性/覆盖对照表。
- 程序化检查清单：schema/格式校验、空输出与异常长度、关键词/正则、P/R/F1（分类任务）、
  语义相似度（有参考答案时）、工具调用断言、执行指标（调用次数/token 阈值）、基线对比。
- 结构化输出是前提：JSON schema 强类型 vs 靠 prompt 措辞的脆弱性。
- 分层筛查流水线（阿里）：粗筛层（低成本规则快速分流）→ 精判层（完整规则+Judge）→ 人工复核层。
- 评分输出规范：不止 pass/fail，还要问题分类（现象层）/问题现象/置信度/判定依据——为 RCA 提供"现象入口"。
- expected_behavior DSL 实例（腾讯 YAML 风格）+ 各检查项适用场景表。
- 边界讨论：哪些东西规则永远判不了（语义/语气/策略合理性）→ 引出 E05。
- 素材：_research/00-industry-practice.md（腾讯评分器、阿里评分章）。

## E05 评分三层之二：LLM-as-Judge 深入
路径：chapters/E05-评分三层之二：LLM-as-Judge 深入.md
Brief（本章是全特辑核心章之一，可以写到 800+ 行）：
- Judge 的 anatomy：rubric + 证据切片 + verdict + rationale；每维一个 judge、
  judge 与生成模型不同源、few-shot、输出 schema、清晰打分指令（Airbnb 规则）。
- Rubric 工程：二元检查 vs 分级打分；eligibility 适用性前置（DoorDash）；
  rubric 描述"成功长什么样"而非指定唯一答案；"人用不一致的 rubric，模型也用不一致"。
  附完整 rubric 实例（Airbnb 房源 listing 语气判 0/1）。
- Judge 偏差全景：位置偏差/冗长偏差/自我偏好/style 偏好——机理、量化方式、缓解手段
  （交换顺序、去长度化、多 judge、对抗打分）。引用 2024-2026 论文（_research/01-llm-judge.md）。
- Judge 校准完整流程：50-100 gold 集（含坏样本）→ 跑 judge → 目标一致率 high-80s~90s →
  Cohen's kappa / Krippendorff's alpha → 分析分歧改 rubric → 重复；失败模式变化时重新校准。
  阿里口径：~85% 后进自动化；腾讯口径：≥85% 可用。
- Judge 的持续运营：金标校准集、升级时三项统计（与人工一致性/高风险漏判率/边界稳定性）；
  Judge 版本化。
- 前沿：GEPA 反射式 prompt 优化（DoorDash 用于 judge 校准）、生成式 judge、
  reward model as judge、judge 被操纵风险。
- 素材：_research/00-industry-practice.md；_research/01-llm-judge.md（主力素材）。

## E06 评分三层之三：人工评估与评分路由
路径：chapters/E06-评分三层之三：人工评估与评分路由.md
Brief：
- 人工的六个高杠杆场景（腾讯）：校准 judge（最核心）/主观任务打分/诊断 0%-100% 异常/
  建 ground truth（前 20-50 参考解）/Trace 采样审查/高风险 100% 复核。
- 专家时间分配经验法则：60%+ 花在校准与诊断，坚决不做日常全量打分。
- 标注工程：标注指南、专家分歧处理（先停下解决分歧再谈自动化，Airbnb）、
  标注者间一致性 IAA、从 20-100 专家样本起步再到规模化标注。
- 人工评分路由（阿里）：不是只看分数阈值——边界分/低置信/reason 含糊/多 judge 分歧/
  新模型新 prompt 新 schema 上线抽样/规则与 judge 冲突 → 人工终判并回收口径。
- 人工结论反哺：校准规则、judge prompt、根因标签体系。
- 人机分工决策表：什么维度永远留给人（政策口径、价值判断、高风险）。
- 素材：_research/00-industry-practice.md；_research/01-llm-judge.md（校准部分）。

## E07 轨迹与 Agent 级评估
路径：chapters/E07-轨迹与 Agent 级评估.md
Brief（核心章之二）：
- 为什么只看最终答案不够：假阳性（结果对、路径错/带风险）的具体案例；
  推理路径/工具参数/工作流可能独立失败。
- 三层评估模型（Airbnb）：step-level（单工具调用/推理步）/ trajectory-level（路径合理高效）
  / session-level（整体达成用户目标）；配阿里对话 agent 的 Turn/Session/Trace/Outcome 四层。
- Trace 基础设施：OpenTelemetry 打点 + span 记录（用户输入/模型输出/工具调用与返回/widgets）
  + ClickHouse 存储（DoorDash）；Trace 是被测 agent 的标准能力而非事后补救（阿里/腾讯）；
  结构化 trace 三要求：可解析、内容完整、跨版本格式稳定。
- Transcript Builder（DoorDash 独创）：原始 trace 完整但难判→重组分散 span、
  删无信号 token、裁超大载荷→每条标准声明依赖证据、judge 只拿那一片
  （grounding 检查拿论断+工具输出；多样性检查拿推荐+原始请求）。
- 序列比对技术：LCS 最长公共子序列对齐 + 归一化（时间戳占位/忽略查询参数/写入只留路径）——腾讯实现。
- 评测镜像运行时架构（DoorDash）：Orchestrator 路由层评路由、护栏贯穿全流程、领域 agent 评任务能力。
- 前沿：credit assignment、过程奖励模型、Agent-as-a-Judge（_research/03-trajectory-eval.md）。
- 素材：_research/00-industry-practice.md；_research/03-trajectory-eval.md；_research/10-infra-observability.md。

## E08 对话 Agent 与仿真评测
路径：chapters/E08-对话 Agent 与仿真评测.md
Brief：
- 对话评测五个特殊难点：上下文累积、目标切换、情绪回应、人工接管、多轮引导；
  "每轮都答得还行但没解决问题仍是失败"。
- Conversation Simulator（DoorDash）：LLM 扮演用户；scenario=开场请求+用户目标+反应策略；
  完整配置实例（evalId/sessionInput/conversationScenario）。
- Fixtures：录制工具返回替代实时调用，冻结外部状态（reorder_history_v1 完整 JSON 实例）；
  避免目录变化/门店库存/测试账号漂移；可构造欺诈/大额退款等难例。
- 模拟用户的行为真实性：动态判断是否解决/是否有进展/是否需要更多信息/是否在绕圈；
  升级行为像真人（给几次机会、反复答差才投诉）。
- 全量 sweep 的成本账：50 场景 × 8 trials = 400 对话；人工 6h+ → 模拟器 20min。
- checklist 式离线 rubric 与低方差信号。
- 仿真的局限：模拟≠真实用户、离线-线上相关性需持续验证、成本。
- 素材：_research/00-industry-practice.md（DoorDash 细节最全）；_research/06-edd-simulation.md（学术侧）。

## E09 评估的统计学基础
路径：chapters/E09-评估的统计学基础.md
Brief：
- 点估计→区间估计：二项置信区间（Wilson score interval 公式与直觉）、bootstrap。
- 样本量计算：要检出 x% 差异需要多少样本（给公式+速查表）；为什么 100 条 golden set 是常见起点。
- 版本对比的显著性：配对比较、最小可感知变化阈值（阿里"门禁不只看差了多少，还看是否超过统计噪声"）。
- pass^k 的估计与方差；重复试验设计（N=5/8/10 的取舍）。
- Arena 方法论：Elo/Bradley-Terry 原理、bootstrap CI、风格控制回归
  （length-controlled AlpacaEval、Chatbot Arena 的风格控制）。
- 噪声与可复现：seed/temperature/多次 trial 取均值；同模型多次评测的方差研究。
- 面试计算题专区：给场景让读者算 CI/样本量。
- 素材：_research/04-statistics.md（主力）；_research/00-industry-practice.md（阿里统计口径）。

## E10 评测驱动开发（EDD）
路径：chapters/E10-评测驱动开发（EDD）.md
Brief（核心章之三）：
- EDD = GenAI 版 TDD：不预测所有失败，而是发现→捕获→反复检查失败模式（Airbnb 定义）。
- Airbnb 五原则：尽早定目标与门槛/从观察到的错误推导指标/少而精的 judge（3-5 个）/
  指定人类终判者/产品伙伴持续参与。
- 核心习惯 "When in doubt, look at your data"：100 样本人工精读法（跑 100 prompt→
  读输出与 trace→归类错误→围绕它们建测试）。
- 迭代纪律：一次只改一个变量（固定模型变 prompt → 固定 prompt 变模型 → 都固定变 serving 配置）；
  judge 筛候选、优秀候选反哺 judge 直到双方稳定。
- 完整案例演练（Airbnb 旅行客服）：探索（100 prompt 发现 15 groundedness 失败/8 啰嗦/5 不当拒答/3 JSON 失败）
  → 建测试 → 校准（78%→88%，发现 judge 误罚正确改述）→ 规模化（5000 样本、每日 5% 抽样、每周 PM 评审）。
- CI 门禁与回归：PR 触发回归、回归集只增不减、能力评测 100% 毕业进回归集（腾讯）；
  Anthropic 口径：确定性任务 100%、非确定性 ≥95%。
- DoorDash 反馈闭环：失败按 rubric 标准聚类→coding agent 检查 trace/代码路径/近期变更→
  明确修复直接起草 PR→工作流沉淀为 Agent Skills（skill 出错就更新 skill 而非打补丁）。
- 素材：_research/00-industry-practice.md；_research/06-edd-simulation.md。

## E11 Badcase 根因分析与优化闭环
路径：chapters/E11-Badcase 根因分析与优化闭环.md
Brief：
- Badcase 双通路入口：离线评测集 + 线上（会话/质检/工单/低满意度/回归失败/告警）→ 同一任务表。
- RCA 五步（阿里，本章主体）：① 证据汇总（sessionId/traceId 聚合全链路）→
  ② 范围收敛（"问题现象 × 功能模块"映射表实例；命中走确定性路径，未命中 LLM 兜底）→
  ③ 分模块诊断（逐模块读 IO/prompt/工具返回，输出 PASS/SOFT_PASS/FAIL；事实性错误案例演练）→
  ④ 责任判定（三层策略：严重模块直接定责→规则引擎匹配→LLM 汇总责任传递）→
  ⑤ 结构化落盘（问题分类/现象/枚举/责任层/责任模块/置信度/修复建议；看板渐进展示）。
- 根因标签体系：稳定、可统计、指向 owner（运营可配置/算法需优化/工程需修复/业务需定口径）；
  支持聚类成问题簇（"退款已发货场景 23 次跳过订单状态校验，集中在 v1.8 Prompt"）。
- RCA 工程实现：异步 Multi-Agent Workflow；确定性优先→模型辅助→人审兜底。
- 从原因到动作：结构化行动项（失败范围/证据/具体动作/owner/验收方式/优先级）——
  拒绝"优化 Prompt"式泛化建议；证据链展开实例。
- 素材：_research/00-industry-practice.md（阿里第 7/8 章内容最全）。

## E12 在线评估与数据飞轮
路径：chapters/E12-在线评估与数据飞轮.md
Brief：
- 在线抽样：每日 5% 去标识化流量（Airbnb）；分层抽样优先高风险/低置信/新意图。
- 离线-线上同一套打分（DoorDash 原则三）：同一 rubric + 同一校准 judge，两边分数才可对齐；
  各自调 judge 会以难调和的方式背离。
- 发布联动：离线门禁+线上灰度；三类信号（离线质量/线上体验：转人工率、重复追问率、投诉率、
  满意度/业务结果：任务完成率、工单闭环率、退款成功率）；离线升线上降→回滚或降级（阿里）。
- 漂移检测：分布漂移/指标漂移；监控图与告警。
- 数据飞轮：badcase→评测集→训练数据→模型更新；反馈生产线三条线（评测集/训练数据/知识修订）；
  入库标准与样本治理（同簇留代表例、P0/P1 长期保留、稳定通过降级抽样集、主动学习抽低置信）。
- 质量资产库终局：用例库/Trace 库/根因标签库/修复建议库/Judge 校准集/回归集。
- DoorDash 双向案例：reasoning leakage（线上评分发现→修 prompt→离线验证→泄漏率降 11%）
  与底座模型迁移（离线 harness 发现兼容性差距→小修→35% 延迟下降）。
- 素材：_research/00-industry-practice.md；_research/10-infra-observability.md。

## E13 Benchmark 全景与前沿争议
路径：chapters/E13-Benchmark 全景与前沿争议.md
Brief：
- Benchmark 分类学：静态 vs 动态；能力 vs 领域 vs 应用；交互形态（单轮/多轮/环境）。
- 主流 agent benchmark 速览表（τ-bench/GAIA/SWE-bench/WebArena/OSWorld/terminal-bench/HLE 等）：
  测什么/怎么测/核心指标/已知问题。全部来自 _research/02-agent-benchmarks.md。
- 污染：检测方法（成员推断/perplexity/选项顺序敏感性/canary）、污染军备竞赛、对决策的扭曲。
- 饱和与崩塌：MMLU 教训、benchmark collapse、Goodhart。
- 动态基准：LiveBench/DyVal/LiveCodeBench 等方案与代价。
- 选型策略：公开 benchmark（外部坐标）+ 私有 golden set（真实业务）+ 在线信号（地面真值）三层互补；
  "只能选一个向老板汇报选哪个"的答题框架。
- Arena vs 静态 benchmark：各测什么、何时信谁。
- 素材：_research/02-agent-benchmarks.md；_research/05-benchmark-dynamics.md；_research/04-statistics.md。

## E14 前沿论文全景（2024-2026）
路径：chapters/E14-前沿论文全景（2024-2026）.md
Brief：
- 本章是 _research/ 全部 10 份调研的"教学化综述"：按九个方向（judge/agent 基准/轨迹评估/
  统计方法/benchmark 动态/EDD 与仿真/安全评测/组件级评估/自改进与基础设施）组织，
  每方向给：演进主线（2-3 段）→ 代表论文 3-5 篇（一句话贡献）→ 未解问题。
- 末尾：趋势判断（3-5 条，如 judge 校准成为一等公民、轨迹级评估崛起、评测与训练闭环融合、
  仿真评测平台化、安全评测前置）。
- 所有论文条目必须来自 _research/*.md（保留 arxiv ID），不得凭记忆新增。
- 素材：全部 _research/*.md。

## E15 工业实践案例研究
路径：chapters/E15-工业实践案例研究.md
Brief：
- 四大案例深挖（全部数字以 _research/00-industry-practice.md 为准）：
  ① Airbnb：EDD 方法论与纪律（五原则、100 样本法、一次一变量、judge 校准 78→88 全程）。
  ② DoorDash：eval harness 工程架构（四组件+挑战需求表+GEPA+transcript builder+
     fixtures+Agent Skills 闭环+两个实战案例 reasoning leakage/模型迁移）。
  ③ 阿里：评测平台治理体系（P0/P1/P2 指标、RCA 五步、行动项、反馈生产、质量资产库、九能力模块）。
  ④ 腾讯：落地模板（三类评分器、五维、四场景用例、扣分制 80 分线、基线快照、
     稳定性容忍阈值分级、能力→回归毕业、TPerf 实战 LCS/30+用例×7模型）。
- 横向对比大表：共识（三难题/三层评分/85% 校准线/golden set 规模/过程评估/闭环）vs 各自独创贡献。
- "如果你从零开始"的落地路线图：30 天/90 天两个里程碑（综合四家实践）。
- 素材：_research/00-industry-practice.md（唯一主力素材，务必忠实引用）。
