# 组件级评估——RAG / 忠实性 / 归因 调研报告（2024–2026）

> 调研日期：2026-08-05。范围：2024-01 至 2026-08 的 arxiv 前沿工作为主，2023 年及更早的奠基工作（FActScore、AIS、ALCE 等）作为背景。除标注【未核实】外，arxiv ID 均通过 arxiv API / abs 页 / 多源交叉检索确认。

---

## 主题概述

**这一方向在解决什么问题？** RAG（检索增强生成）是 LLM 落地的主力架构，但"端到端答案不好"是个无诊断价值的信号：问题可能出在检索（召回不足、排序差、噪声多）、也可能出在生成（忽略上下文、幻觉、过度拒绝）。组件级评估（component-level evaluation）把 RAG 流水线拆开，对检索器与生成器分别给出可归因的指标；与之平行的两条线是：

1. **忠实性 / 幻觉检测**：回答是否忠于给定证据（faithfulness / groundedness），以及无证据场景下的事实性（factuality）。核心技术范式是"**声明分解（claim decomposition）+ 逐条验证**"，由 FActScore（2023）奠基，2024 年后被 SAFE、VeriScore、RAGChecker 等自动化、细粒化。
2. **归因 / 引用质量评估**：生成文本是否可溯源到具体来源（AIS 定义），引用是否真实支持论断（citation quality/recall/precision）。

**2024–2026 演进主线：**

- **2023（奠基）**：AIS 的形式化定义、FActScore 的原子事实分解、ALCE 的引用指标、Auto AIS 的 LLM 归因裁判、RGB/RAGAS/ARES 等 RAG 评测框架密集出现。
- **2024（组件级成熟 + 规模化基准）**：RAGChecker 提出"声明级 + 检索器/生成器双层诊断指标"，成为组件级评估的标杆；CRAG（Meta KDD Cup 2024）把评测推向动态、带时效、多 track 的工业级基准；RAGTruth 提供 RAG 专用幻觉语料；SAFE 把 FActScore 完全自动化并做到"与人评同级"；AttributionBench 首次系统横评归因评估方法本身。
- **2025–2026（效率化、代理化、纵深场景）**：评测成本工程（VeriFastScore 等蒸馏式事实性裁判）、agentic / 多跳检索评估（FRAMES 类）、归因信号进入 RL 训练回路（grounded RL / citation RL）、法律与科研等垂直域引用评测。同时"LLM-judge 校准"成为横切主题：裁判本身会幻觉、有偏好偏差，需要人工 gold set 校准与统计修正（PPI）。

---

## 重点论文

#### RAGAS: Automated Evaluation of Retrieval Augmented Generation
- **arxiv**: [2309.15217](https://arxiv.org/abs/2309.15217)（2023-09 首发，2024 更新；COLM 2024 收录）
- **机构**: IFIT Madras（Shahul Es 等），RAGAS 开源社区
- **贡献**: 提出免参考答案（reference-free）的 RAG 自动评测框架与指标体系：面向检索的 context relevance / context precision / context recall，面向生成的 **faithfulness**（答案声明被上下文支持的比例）与 **answer relevance**（用反向生成问题与原问题相似度度量）。用 LLM 做裁判，不需要人工标注答案即可跑通。
- **关键数字**: 指标全部可由 LLM 自动计算；后续开源实现（ragas python 库）成为事实标准工具。
- **对评测工程的意义**: 定义了业界默认的"RAG 五指标"词汇表；"faithfulness = 被支持的声明占比"这一定义被后续几乎所有框架沿用。局限是指标依赖 LLM 裁判且缺乏统计置信度。

#### ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems
- **arxiv**: [2311.09476](https://arxiv.org/abs/2311.09476)（2023-11；NAACL 2024）
- **机构**: Stanford（Jon Saad-Falcon, Omar Khattab, Christopher Potts, Matei Zaharia）
- **贡献**: 解决"LLM 裁判不可靠且贵"的问题。三件套：① 用 LLM 生成合成训练数据微调轻量裁判模型（DeBERTa 级）判 context relevance / answer faithfulness / answer relevance；② 只用约 **150–300 条人工标注**；③ 用 **PPI（Prediction-Powered Inference）** 对裁判的系统性偏差做统计修正，输出带 95% 置信区间的系统级估计。
- **关键数字**: 在 6 个数据集上，估计值与金标准偏差通常在 2–3% 以内，远小于朴素 LLM-judge 平均打分。
- **对评测工程的意义**: 给出"裁判校准"的标准范式：**合成数据训裁判 + 小规模 gold set + PPI 置信区间**。任何想把自动评测数字写进上线门禁的团队都应参考这一统计框架，而非直接信 judge 均分。

#### Benchmarking Large Language Models in Retrieval-Augmented Generation（RGB）
- **arxiv**: [2309.01431](https://arxiv.org/abs/2309.01431)（2023-09；AAAI 2024）
- **机构**: 北大/清华等（Jiawei Chen 等）
- **贡献**: 从"能力维度"而非单一 QA 准确率设计 RAG 基准，定义四个测试能力：**噪声鲁棒性**（检索结果含无关文档时不被带偏）、**负拒绝**（检索不到答案时应拒答而不是编造）、**信息整合**（跨文档聚合）、**反事实鲁棒性**（上下文与模型记忆冲突时以证据为准）。中英双语、多领域。
- **关键数字**: ChatGPT/GPT-4 在噪声鲁棒与反事实维度仍明显掉点，中文任务普遍更难。
- **对评测工程的意义**: 提供了 RAG 鲁棒性测试的"用例设计模板"——上线前除了正确率，必须注入噪声文档、空检索结果、与参数化知识冲突的文档三类对抗样本。

#### CRAG -- Comprehensive RAG Benchmark（Meta KDD Cup 2024）
- **arxiv**: [2406.04744](https://arxiv.org/abs/2406.04744)（2024-06）
- **机构**: Meta（Xiao Yang 等）+ KDD Cup 2024 组委会
- **贡献**: KDD Cup 2024 官方 RAG 基准：约 **4,409 条 QA**，覆盖 5 个领域（体育/金融/娱乐/科技/学术）、8 种问题类型（简单/复杂/多跳/带歧义/带时效等）；三个赛道——静态 Mock API、**动态** Mock API（问答随时间演化）、web search（真实互联网检索）；测试集部分不公开以防污染。评测指标为答案有效性（validity）+ 准确率。
- **关键数字**: 竞赛吸引数千支队伍；即使最强方案在动态/时效类问题上准确率也显著低于静态问题，揭示真实世界 RAG 的难点在时效与歧义消解。
- **对评测工程的意义**: 示范了"防污染（私有测试集 + 动态数据）+ 分 track（封闭语料 vs 开放网络）+ 多问题类型"的现代基准设计；其 Mock API 设计也被用于隔离检索接口变量。

#### RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation
- **arxiv**: [2408.08067](https://arxiv.org/abs/2408.08067)（2024-08；NeurIPS 2024 Datasets & Benchmarks Track）
- **机构**: Amazon（Dongyu Ru, Lin Qiu 等）
- **贡献**: **组件级评估的代表作**。把答案分解为 claim（声明）集合，与检索文档逐条对齐，输出三层指标：① 整体（faithfulness、answer relevance、noise sensitivity、positive/negative rejection 等）；② 检索器（claim recall、context precision、context recall、LTM——检索到的上下文被实际利用的比例）；③ 生成器（context utilization、noise sensitivity、hallucination）。附 25 个领域、2,700+ 样本的诊断基准。
- **关键数字**: 与人工标注的判断一致性显著高于 G-Eval 等通用评估器；论文用三个真实用例演示如何用指标组合定位"是检索差还是生成差"。
- **对评测工程的意义**: 给出可直接抄的诊断决策树：例如"faithfulness 低 + context utilization 低 → 生成器忽略上下文"；"claim recall 低 → 检索器背锅"。是目前最适合做 RAG 回归测试与故障定位的开源框架之一。

#### RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models
- **arxiv**: [2401.00396](https://arxiv.org/abs/2401.00396)（2023-12 v1；ACL 2024）
- **机构**: 中科院自动化所等（Cheng Niu 等）
- **贡献**: 首个面向 RAG 场景的**词级幻觉标注语料**：多个 LLM 在真实检索语料上生成回答，人工标注四类幻觉（unsupported 无据、factual contradiction 事实冲突、unanswerable 无法回答、task hallucination 任务幻觉），约 2,700+ 条回答样本。用于训练/评测幻觉检测器，而不是只做 benchmark。
- **关键数字**: 实验表明现有幻觉检测方法（SelfCheckGPT 等）在 RAG 场景迁移效果差，RAG 专用检测器（基于其语料微调）显著更好。
- **对评测工程的意义**: 说明"忠实性检测器"需要 RAG 场景专用训练数据；通用幻觉检测不能直接用于 grounded 场景。可作为自训 faithfulness judge 的训练/测试集。

#### FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation（背景奠基）
- **arxiv**: [2305.14251](https://arxiv.org/abs/2305.14251)（2023-05；EMNLP 2023）
- **机构**: 华盛顿大学 + Meta AI（Sewon Min, Kalpesh Krishna 等）
- **贡献**: 奠定"**原子事实分解 + 逐条证据验证**"范式：把长回答拆成原子事实（atomic facts），用检索（Wikipedia 等）验证每条，FActScore = 被支持的原子事实比例。同时给出人评协议：判断单条原子事实是否被证据支持，标注一致性高。
- **关键数字**: ChatGPT 生成的人物传记中约 77.8% 的句子完全符合事实；FActScore 与人判断一致性约 90% 级别；相比整句级判断，原子级判断的人一致性显著提高。
- **对评测工程的意义**: 一切 faithful/faithfulness 指标的方法论源头；其结论"分解粒度越细，人评越可靠、自动化越可行"被后续所有工作继承。局限：只测 precision 不测 recall（漏说不罚）、成本高、依赖知识源。

#### Long-form factuality in large language models（SAFE）
- **arxiv**: [2403.18802](https://arxiv.org/abs/2403.18802)（2024-03；ICML 2024）
- **机构**: Google DeepMind（Jerry Wei 等）
- **贡献**: 把 FActScore **完全自动化**：SAFE（Search-Augmented Factuality Evaluator）让 LLM 把回答拆成独立事实 → 对每条自动生成多步推理的搜索查询 → 用 Google 搜索结果迭代验证。同时提出 **LongFact** 基准（384 个需要长回答的开放问题）与 **F1@K** 指标（在 FActScore 精确率基础上惩罚过短回答，K 控制长度惩罚强度）。
- **关键数字**: 在单条事实判断上，SAFE 与人评一致约 72%；在两者分歧的子集上，SAFE 有约 76% 的情况经复核后被证明是对的（即达到"人评同级"）；单条长回答评测成本约 0.2 美元量级。
- **对评测工程的意义**: 证明事实性评测可以脱离人工、以可承受成本大规模运行；F1@K 提示"只测 precision 会奖励沉默模型"，必须同时考虑信息量/召回。

#### VERISCORE: Evaluating the factuality of verifiable claims in long-form text generation
- **arxiv**: [2406.19276](https://arxiv.org/abs/2406.19276)（2024-06；Findings of EMNLP 2024）
- **机构**: Meta（Yuning Song 等）
- **贡献**: 针对 FActScore 在"混合可验证/不可验证内容"上的失真问题：只抽取**可验证的声明（verifiable claims）**再逐条验证，避免把主观/模糊/无法核查的内容计入事实性分数。验证器可用搜索引擎。
- **关键数字**: 在人评相关性上优于 FActScore 与 SAFE 的朴素变体，尤其在新闻、观点类混合文本上。
- **对评测工程的意义**: 评测开放域长文时先做"可验证性过滤"是必要步骤，否则分数会被不可核查内容稀释或扭曲。

#### FacTool: Factuality Detection in Generative AI -- A Tool Augmented Framework for Multi-Task and Multi-Domain Scenarios
- **arxiv**: [2307.13528](https://arxiv.org/abs/2307.13528)（2023-07；ICLR 2024）
- **机构**: GAIR-NLP（I-Chun Chern 等）
- **贡献**: 把事实性检测做成**工具增强的多域流水线**：声明抽取 → 按域调用工具取证（知识 QA 用搜索、代码用执行、数学用计算器、文献综述用 Scholar API）→ 逐条验证。强调"事实性错误检测"要按声明类型路由到不同验证后端。
- **关键数字**: 在四个域上构建评测集，ChatGPT 生成文本的各类事实性错误率显著；工具验证优于纯 LLM 自我判断。
- **对评测工程的意义**: "不同 claim 类型需要不同 verifier"这一架构思想直接可用于 RAG/agent 评测：数值声明用计算、代码声明用单测、事实声明用检索。

#### Measuring Attribution in Natural Language Generation Models（AIS，背景奠基）
- **arxiv**: [2112.12870](https://arxiv.org/abs/2112.12870)（2021-12 首发；*Computational Linguistics* 2023, 49(4)）
- **机构**: Google Research（Hannah Rashkin 等）
- **贡献**: 提出 **AIS（Attributable to Identified Sources）** 定义：生成文本对"外部世界"的断言必须可以溯源到人类可识别的来源；标注任务简化为二值判断"该文本是否可归因于该来源"，与"文本是否真实"解耦（来源本身可以错，但只要文本忠于来源即 attributable）。
- **对评测工程的意义**: 归因/忠实性评测的概念基石。RAGAS 的 faithfulness、TruLens 的 groundedness、ALCE 的 citation quality 本质上都是 AIS 的自动化版本。"忠实性 ≠ 事实性"这一区分（忠于来源 vs 客观为真）是所有 grounded 评测设计的第一原则。

#### Enabling Large Language Models to Generate Text with Citations（ALCE）
- **arxiv**: [2305.14627](https://arxiv.org/abs/2305.14627)（2023-05；EMNLP 2023）
- **机构**: Princeton（Tianyu Gao, Howard Yen, Danqi Chen 等）
- **贡献**: 引用生成评测的标准基准 ALCE（ASQA、QAMPARI、ELI5）。定义两个可自动计算的引用指标：**citation quality**（所给引用是否被 NLI 蕴含模型判定为支持该陈述）与 **citation recall**（答案中被引用覆盖的陈述比例），外加对引用冗余度的分析。
- **关键数字**: 即使 GPT-3/GPT-4 + 强检索器，引用质量与召回也普遍不高；引用能力与模型规模、是否显式训练引用有关。
- **对评测工程的意义**: 引用评测的标准指标定义（quality/recall）与 NLI 式自动裁判（TRUE/DeBERTa 蕴含模型）来自本文；做"AI 回答必须带可核查引用"的产品（搜索、法律、医疗问答）可以直接复用。

#### Automatic Evaluation of Attribution by Large Language Models（Auto AIS）
- **arxiv**: [2305.06311](https://arxiv.org/abs/2305.06311)（2023-05；Findings of EMNLP 2023）
- **机构**: Ohio State（Xiang Yue 等）
- **贡献**: 系统回答"能否用 LLM 自动判断归因质量"：让 LLM 直接判断"生成文本是否可由来源推出"（多视角 prompting：分解、改写、多来源推理），并与人评 AIS 标注对齐；同时探索微调小模型做归因判断。提出 AttrScore。
- **关键数字**: LLM 归因裁判与人判断一致率约 0.8 量级，优于基于 NLI 的方法；但长文本、多来源场景仍有明显错误。
- **对评测工程的意义**: 验证了"LLM-as-attribution-judge"路线可行；同时给出裁判失败模式（来源过长、信息散落多处时判断退化），为裁判 prompt 设计提供依据。

#### How Hard is Automatic Attribution Evaluation?（AttributionBench）
- **arxiv**: [2402.15089](https://arxiv.org/abs/2402.15089)（2024-02；Findings of ACL 2024）
- **机构**: Ohio State NLP（Hongjin Su 等，OSU-NLP-Group）
- **贡献**: 首个**归因评估方法本身的统一基准**：把 10+ 个来源不同的归因/引用数据集（ELI5-AS、SummSci、TRUE 系列等）统一成 "(声明, 来源) → attributable?" 的二分类任务，横评 NLI 微调模型（TRUE、DeBERTa 系）与各类 LLM prompting 策略。
- **关键数字**: 微调 NLI 模型在多数数据集上仍优于通用 LLM 直接判断；LLM 方法在长输入、多句来源上退化明显；不同领域间泛化差距大。
- **对评测工程的意义**: 选 faithfulness judge 不能只看一个数据集的分数——本文证明归因判断的跨域迁移很差，**必须用自己领域的数据校准裁判**。开源的 AttributionBench 可直接当裁判回归测试集。

#### Fact, Fetch, and Reason: A Unified Evaluation of Retrieval-Augmented Generation（FRAMES）
- **arxiv**: [2409.12941](https://arxiv.org/abs/2409.12941)（2024-09）
- **机构**: Amazon（Satyapriya Krishna 等）
- **贡献**: FRAMES 基准：约 1,700 条强调**推理复杂度**的问答（多跳检索、表格/数值推理、时间/约束条件组合），专门暴露"检索到了但推理不出来"与"推理链中间步检索失败"的问题，按推理阶段拆解失败原因。
- **关键数字**: 主流 LLM + RAG 系统准确率普遍低于 40–50%，即使 GPT-4 级模型在多跳问题上大幅掉点。
- **对评测工程的意义**: 组件级评估的纵深版：不仅拆"检索 vs 生成"，还拆"推理链的哪一跳失败"；对 agentic search / deep research 类系统的评估设计有直接参考价值。

---

## 关键概念与方法论

### 1. 核心定义
- **AIS（Attributable to Identified Sources）**：人判断"该文本是否能从给定来源中被合理推出/找到依据"，二值、与客观真假解耦。忠实性评测的元定义。
- **Faithfulness / Groundedness（忠实性）**：答案忠于检索上下文（RAG 场景）；RAGAS 定义：`faithfulness = |被上下文支持的 claims| / |答案中 claims 总数|`。
- **Factuality（事实性）**：答案与客观世界一致（无需给定上下文）；FActScore 定义：`FActScore = (1/|F|) * Σ 1[atomic fact 被知识源支持]`。
- **Citation quality / recall（ALCE）**：quality = 所给引用能（NLI）蕴含对应陈述的比例；recall = 答案中"有引用支持"的陈述比例。
- **F1@K（SAFE）**：`F1@K = 2 * precision * recall_K / (precision + recall_K)`，其中长度低于 K 的回答 recall 按长度比例打折——防止"少说少错"。

### 2. 声明分解 + 逐条验证流水线（可复用模板）
```
回答 → (1) claim extraction（原子化/可验证化）
     → (2) per-claim verification（检索+NLI / LLM judge / 工具执行）
     → (3) aggregation（支持率、召回、F1@K）
     → (4) 校准（与人工 gold set 对齐，PPI 置信区间）
```
变体选择：验证器 = NLI 蕴含模型（便宜、确定性高，长文本弱）或 LLM judge（灵活、贵、有偏差）或领域工具（代码执行/计算器，最可靠但窄域）。

### 3. 检索器与生成器的解耦指标（RAGChecker/RAGAS 体系）
| 层 | 指标 | 含义 |
|---|---|---|
| 检索器 | claim recall | 答案所需声明在检索文档中的覆盖率 |
| 检索器 | context precision / recall | 上下文相关性与排序质量 |
| 检索器 | context utilization (LTM) | 检索内容被生成器实际使用的比例 |
| 生成器 | faithfulness | 答案声明被上下文支持的比例 |
| 生成器 | noise sensitivity | 注入噪声文档后答案出错率（RGB 思想） |
| 生成器 | negative/positive rejection | 该拒答时拒答 / 该回答时不拒答 |
| 整体 | answer correctness / relevance | 端到端有效性 |

### 4. 裁判校准方法（ARES 范式）
1. 合成数据（LLM 生成正负例）微调轻量裁判；
2. 小样本人工 gold（150–300 条）；
3. **PPI**：用裁判预测值 + 人工 gold 构造带 95% CI 的系统级估计，修正裁判系统性偏差。没有 PPI 这类修正的 judge 平均分不应作为上线决策依据。

### 5. 鲁棒性测试设计（RGB 模板）
- 噪声注入：top-k 里掺无关文档 → 测 noise sensitivity；
- 不可答问题：语料中无答案 → 测拒答率而非硬答率;
- 反事实注入：给与模型参数化知识冲突的证据 → 测是否以证据为准（grounded 优先 vs memory 优先）。

---

## 争议与分歧

1. **组件级 vs 端到端**：组件指标高不等于用户满意——检索 recall 高但生成器不用（低 context utilization）、faithfulness 高但答非所问都常见；反之端到端好也可能只是"模型记忆对"而非检索起作用（需 no-retrieval 消融对照）。学界共识趋向"组件指标用于诊断、端到端指标用于门禁"，但两者权重如何配比没有标准答案。
2. **LLM judge 可靠性**：judge 自身有幻觉（把未支持的 claim 判为支持）、有偏差（冗长偏好、自我偏好——GPT 判 GPT 偏高、位置偏差）。Auto AIS / AttributionBench 显示裁判跨域迁移差；工业界（TruLens、RAGAS、DeepEval 等）普遍默认用强 LLM 当裁判但很少披露与人工的一致性数据。校准（gold set + PPI / P(True) 类置信 elicitation，见延伸阅读 Just Ask for Calibration）仍是少数派实践。
3. **声明粒度的敏感性**：FActScore 分数随原子化方式变化；抽取过细会高估错误、过粗会漏检；VeriScore 进一步指出必须剔除不可验证声明。目前没有统一的 claim 抽取标准，跨论文分数不可直接比较。
4. **只测 precision 的失真**：FActScore 不惩罚遗漏，导致"短回答得分高"；SAFE 的 F1@K 是修补方案，但 K 的选择主观。
5. **NLI 裁判 vs LLM 裁判**：ALCE 用 TRUE/DeBERTa 蕴含模型判引用质量，便宜且可复现，但对长引用、改写、多句组合证据判断差；LLM 裁判灵活但贵且不稳。AttributionBench 的横评显示没有绝对赢家，领域内自建 gold 校准是唯一可靠路线。
6. **静态基准的污染与时效**：公开 QA 对易被训练数据污染；CRAG 的动态 track + 私有测试集是应对方案，但带来可复现性下降的新争议。
7. **忠实性 ≠ 正确性 的产品争议**：严格 grounded 系统会大量拒答/回答干瘪；产品侧常放松忠实性换取可用性，评测侧则坚持 grounded 优先——这是搜索/客服类产品中常见的拉锯。

---

## 对工程实践的启示

1. **分层建评测体系**：至少三层——检索层（recall@k、claim recall、context precision）、生成层（faithfulness、noise sensitivity、rejection）、端到端层（answer correctness、用户指标）。出问题时按 RAGChecker 式诊断树定位组件，避免"整体掉了 2 个点不知道改哪"。
2. **claim 级流水线落地**：用 LLM 做 claim 抽取 + 逐条支持判断是当前性价比最高方案；对数值/代码类声明路由到工具验证（FacTool 思想）。开源可直接用 RAGChecker、RAGAS、DeepEval、TruLens。
3. **裁判必须校准**：保留 100–300 条人工标注的 gold set（覆盖长上下文、多来源、反事实等难例），定期测 judge 与人的 agreement；上线门禁用 PPI 置信区间而非裸均分。用 AttributionBench 类数据做裁判回归测试，防裁判模型/prompt 变更导致分数漂移。
4. **鲁棒性用例进 CI**：固定一组噪声注入、不可答、反事实用例（RGB 式），每次改检索器/prompt 跑回归；拒答率与幻觉率要同时看，防止"为降幻觉而过度拒答"的跷跷板。
5. **引用型产品加引用指标**：citation recall/precision（ALCE 定义）+ 抽检测试"引用是否真实存在"（防 hallucinated citation）；法律/医疗/金融场景应更严（引用不可达即算失败）。
6. **防污染与时效**：内部评测集不要外泄；对时效敏感域（新闻、行情）用动态/滚动更新的问题（CRAG 思想），并单独报告"带时间约束问题"的准确率。
7. **成本工程**：大规模评测用分层采样（难例全测、易例抽测）；验证查询缓存；2025 年后可考虑蒸馏式事实裁判（VeriFastScore 类，单次前向完成分解+验证）把每条成本降 1–2 个数量级。
8. **报告口径**：同时报 precision 型忠实度与召回/信息量（F1@K 思想），并附 no-retrieval 基线，量化检索的真实增益。

---

## 参考清单

**核心论文（均已核实）**
1. RAGAS: Automated Evaluation of Retrieval Augmented Generation — [arxiv 2309.15217](https://arxiv.org/abs/2309.15217)
2. ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems — [arxiv 2311.09476](https://arxiv.org/abs/2311.09476)
3. Benchmarking Large Language Models in Retrieval-Augmented Generation (RGB) — [arxiv 2309.01431](https://arxiv.org/abs/2309.01431)
4. CRAG -- Comprehensive RAG Benchmark (Meta KDD Cup 2024) — [arxiv 2406.04744](https://arxiv.org/abs/2406.04744)
5. RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation — [arxiv 2408.08067](https://arxiv.org/abs/2408.08067)
6. RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models — [arxiv 2401.00396](https://arxiv.org/abs/2401.00396)
7. FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation — [arxiv 2305.14251](https://arxiv.org/abs/2305.14251)
8. Long-form factuality in large language models (SAFE) — [arxiv 2403.18802](https://arxiv.org/abs/2403.18802)
9. VERISCORE: Evaluating the factuality of verifiable claims in long-form text generation — [arxiv 2406.19276](https://arxiv.org/abs/2406.19276)
10. FacTool: Factuality Detection in Generative AI -- A Tool Augmented Framework — [arxiv 2307.13528](https://arxiv.org/abs/2307.13528)
11. Measuring Attribution in Natural Language Generation Models (AIS) — [arxiv 2112.12870](https://arxiv.org/abs/2112.12870)
12. Enabling Large Language Models to Generate Text with Citations (ALCE) — [arxiv 2305.14627](https://arxiv.org/abs/2305.14627)
13. Automatic Evaluation of Attribution by Large Language Models (Auto AIS) — [arxiv 2305.06311](https://arxiv.org/abs/2305.06311)
14. How Hard is Automatic Attribution Evaluation? (AttributionBench) — [arxiv 2402.15089](https://arxiv.org/abs/2402.15089)
15. Fact, Fetch, and Reason: A Unified Evaluation of Retrieval-Augmented Generation (FRAMES) — [arxiv 2409.12941](https://arxiv.org/abs/2409.12941)

**延伸阅读**
- VeriFastScore: Speeding up long-form factuality evaluation（2025，蒸馏式事实裁判）— [arxiv 2505.16973](https://arxiv.org/abs/2505.16973)
- Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence from RLHF Models（EMNLP 2023）— [arxiv 2305.14975](https://arxiv.org/abs/2305.14975)
- Evaluation of Retrieval-Augmented Generation: A Survey — [arxiv 2405.07437](https://arxiv.org/abs/2405.07437)
- A Survey on Hallucination in Large Language Models — [arxiv 2311.05232](https://arxiv.org/abs/2311.05232)
- SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection — [arxiv 2303.08896](https://arxiv.org/abs/2303.08896)
- MT-Bench / Judging LLM-as-a-Judge — [arxiv 2306.05685](https://arxiv.org/abs/2306.05685)
- BEIR: A Heterogeneous Benchmark for Zero-shot Evaluation of Information Retrieval Models — [arxiv 2104.08663](https://arxiv.org/abs/2104.08663)
- Prediction-Powered Inference（ARES 的统计基础, Science 2023）— [arxiv 2306.07543](https://arxiv.org/abs/2306.07543)
- Self-RAG（自带反思 token 的 RAG，背景）— [arxiv 2310.11511](https://arxiv.org/abs/2310.11511)
- Corrective Retrieval Augmented Generation（背景方法）— [arxiv 2401.15884](https://arxiv.org/abs/2401.15884)
- MultiHop-RAG（多跳检索评测）— [arxiv 2401.15391](https://arxiv.org/abs/2401.15391)
- Lost in the Middle（长上下文中证据位置影响，RAG 设计必读背景）— [arxiv 2307.03172](https://arxiv.org/abs/2307.03172)
- G-Eval（LLM form-filling 评估，faithfulness judge 常用实现方式）— [arxiv 2303.16634](https://arxiv.org/abs/2303.16634)
- CitationBench: Benchmarking Citation-Grounded Reasoning（Microsoft Research, 2025）【未核实：arxiv ID 未能确认，引用时请自行检索】
- SelfCite: Self-Supervised Alignment for Context Attribution（ICML 2025，归因信号进 RL 训练的代表）【未核实：未取到 arxiv ID】
- FACTS Grounding（Google DeepMind, 2025，长文档 grounded 事实性基准，无 arxiv，见 GitHub/官方博客）【未核实：无 arxiv】
