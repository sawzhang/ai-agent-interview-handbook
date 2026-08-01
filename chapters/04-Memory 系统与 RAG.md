# 第 4 章 · Memory 系统与 RAG

## Memory 系统与 RAG

> **写在前面（方法论提示）**：RAG 已从"检索拼进 prompt"的朴素范式，演进为涵盖索引、路由、改写、检索、重排、校验、记忆管理的**复合工程系统**。2025 年以来行业进一步收敛到一个更大的框架——**上下文工程（Context Engineering）**：模型本身无状态，决定输出质量的是"在正确时刻把正确的信息以正确的形式放进上下文"，而 Memory 与 RAG 正是这件事的两大支柱。面试官真正考察的不是你能否背出"向量相似度检索"，而是你能否在 **RAG / 长上下文 / 缓存增强生成（CAG）/ 微调 / 工具调用** 之间做有依据的取舍，能否诊断"检索到了但答错"与"根本没检索到"这两类截然不同的失败。本章按"知识图谱 → 精讲 → 考点 → 真题 → 易错点 → 资源"组织，建议结合一个你亲手做过的 RAG 项目来理解。

---

### 一、知识图谱

```
Memory 系统与 RAG
│
├── A. Agent Memory（智能体记忆）
│   ├── 1. 记忆分层（认知科学映射）
│   │   ├── Sensory / Working memory（工作记忆 ≈ context window）
│   │   ├── Short-term memory（会话内，token 预算约束）
│   │   └── Long-term memory（跨会话持久化）
│   │       ├── Episodic（情节记忆：发生了什么）
│   │       ├── Semantic（语义记忆：事实与概念/用户画像）
│   │       └── Procedural（程序记忆：技能/工具用法/prompt 经验）
│   ├── 2. 上下文管理技术（上下文工程）
│   │   ├── 滑动窗口 / 截断 / 工具结果裁剪
│   │   ├── Summarization（滚动摘要、递归摘要）
│   │   ├── 外化（把状态写入文件/scratchpad，"在纸上思考"）
│   │   ├── MemGPT / Letta（OS 式虚拟内存分页：main context ↔ external storage）
│   │   ├── 上下文压缩（LLMLingua-2、Selective Context、RECOMP）
│   │   ├── Compaction（会话级自动压缩，Claude Code /compact；Anthropic 上下文工程）
│   │   └── Sleep-time agents（会话间隙离线整理/巩固记忆）
│   ├── 3. 长期记忆框架
│   │   ├── Mem0 / Mem0^g（抽取-更新-冲突消解记忆层，向量/图谱双形态）
│   │   ├── Zep / Graphiti（双时序知识图谱记忆：valid time × transaction time）
│   │   ├── A-Mem（Zettelkasten 式自组织笔记）
│   │   ├── 程序记忆范例：Voyager 技能库、Reflexion、ExpeL
│   │   └── 工程实践：CLAUDE.md / .cursor rules（静态注入的程序记忆）
│   ├── 4. 记忆生命周期：Write → Select → Retrieve → Reflect（CoALA / 记忆综述口径；"Select"非 Generative Agents 术语）
│   ├── 5. 检索信号融合：recency × importance × relevance（Generative Agents 评分）
│   └── 6. 记忆评估与安全：LOCOMO / LongMemEval；记忆投毒与注入防御（spotlighting / instruction hierarchy）、隐私与可删除性
│
├── B. Embedding 与表示
│   ├── 1. 文本嵌入模型
│   │   ├── 双塔 / Bi-encoder（query 与 doc 独立编码 → ANN）
│   │   ├── 代表：OpenAI text-embedding-3、Cohere embed-v3/v4、
│   │   │        BGE-M3（dense+sparse+多向量三态一体）、Qwen3-Embedding、
│   │   │        Gemini Embedding、NV-Embed-v2、E5-mistral、GTE、
│   │   │        nomic-embed、jina-embeddings-v4（多模态+late interaction 统一）、
│   │   │        Voyage（MongoDB）
│   │   ├── 指令式嵌入（instruction-tuned，需区分 query/passage 前缀）
│   │   └── 选型基准：MTEB / C-MTEB（中文）
│   ├── 2. 稀疏表示 / 学习型稀疏检索
│   │   ├── BM25（词频饱和 + 逆文档频率 + 长度归一化，无需训练）
│   │   ├── SPLADE（稀疏词项扩展 + FLOPS 正则）
│   │   ├── ELSER（Elastic 学习型稀疏）
│   │   └── 词袋 vs 语义的互补性
│   ├── 3. 多向量 / Late Interaction
│   │   ├── ColBERT / ColBERTv2（per-token 向量，MaxSim）
│   │   ├── ColPali / ColQwen2（文档图像直接检索，免 OCR）
│   │   └── 精度-成本权衡
│   ├── 4. 嵌入工程细节
│   │   ├── 维度与 MRL（Matryoshka Representation Learning，可截断维度）
│   │   ├── 归一化 / cosine vs dot vs L2
│   │   ├── 对称 vs 非对称检索（query≠doc 分布）
│   │   ├── 最大输入长度与静默截断（silent truncation）
│   │   └── 模型版本绑定（向量不可跨嵌入模型混用）
│
├── C. 索引与向量数据库
│   ├── 1. ANN 索引算法
│   │   ├── IVF（倒排 + 聚类，IVF-PQ；nlist/nprobe 为精度-速度旋钮）
│   │   ├── HNSW（分层可导航小世界图；M/efConstruction/efSearch；查询快、内存高）
│   │   ├── DiskANN / Vamana（SSD 友好图索引 + 内存 PQ，十亿级低内存）
│   │   └── PQ / SQ / Binary（量化：压缩换内存，过采样 + 精排回补召回）
│   ├── 2. 向量库对比
│   │   ├── FAISS（库，单机、研究基准）
│   │   ├── Milvus / Zilliz（分布式、GPU、混合检索）
│   │   ├── Pinecone（全托管、serverless）
│   │   ├── pgvector / pgvectorscale（与业务库同栈、事务一致、DiskANN）
│   │   ├── Qdrant / Weaviate / Chroma / LanceDB / Turbopuffer（对象存储 serverless）
│   │   ├── 传统搜索引擎补齐：Elasticsearch / OpenSearch / Vespa（kNN + BM25 + RRF）
│   │   └── 选型维度：规模、延迟、过滤（预/后）、运维、成本、一致性
│   ├── 摄取与解析（ingestion）：版面解析（Docling / Marker / unstructured）/ OCR / 表格图片抽取——解析质量常是第一瓶颈
│   ├── 3. Chunking 策略
│   │   ├── 固定长度 / 递归字符切分
│   │   ├── 语义切分（embedding 边界检测）
│   │   ├── 结构感知（Markdown/HTML/代码 AST）与表格处理
│   │   ├── Parent-Document / Small-to-Big（小块检索、大块返回）
│   │   ├── Proposition / 句子级索引（Dense X Retrieval）
│   │   ├── RAPTOR（递归聚类摘要树，多粒度检索）
│   │   ├── Contextual Retrieval（Anthropic：为 chunk 补上下文前缀）
│   │   └── Late Chunking（Jina：先长文编码再切，保留全局语境）
│   ├── 4. Index-time vs Query-time 计算权衡（资深视角）
│   └── 5. 元数据与过滤：metadata filtering、命名空间、多租户、ACL 预过滤
│
├── D. 检索范式
│   ├── 1. Dense / Sparse / Hybrid
│   │   └── RRF（Reciprocal Rank Fusion，k=60，只用排名、无需分数校准）
│   ├── 2. 多路召回与融合（加权融合 vs RRF vs 学习型融合）
│   ├── 3. Reranker
│   │   ├── Cross-encoder：BGE-reranker、Cohere Rerank、Jina Reranker、Qwen3-Reranker
│   │   └── LLM 重排：RankGPT / RankZephyr / RankMistral（listwise、滑动窗口）
│   ├── 4. Query 处理
│   │   ├── Query Rewriting / HyDE（假设性文档嵌入）
│   │   ├── Multi-Query / Step-back / 问题分解
│   │   └── Query Routing（路由到合适索引/工具/或直接回答）
│   └── 5. 自适应检索：FLARE / Self-RAG / CRAG / CRITIC
│
├── E. 高级 RAG 架构
│   ├── 1. Agentic RAG（检索作为 Agent 的工具/循环；MCP 化检索服务）
│   │   └── 产品化：Perplexity、OpenAI / Gemini Deep Research
│   ├── 2. GraphRAG（Microsoft：实体图谱 + Leiden 社区检测 + map-reduce 摘要）
│   ├── 3. LightRAG / KAG / HippoRAG（更轻的图式 / 神经海马式记忆检索）
│   ├── 4. Corrective RAG（CRAG）：对检索质量评估后决定 refine/rewrite/web search
│   ├── 5. Self-RAG：训练模型自生成 reflection token 控制检索与批判
│   └── 6. CAG（Cache-Augmented Generation：小型静态知识库预载进 KV 缓存）
│
├── F. RAG vs 长上下文 vs 微调
│   ├── 1. Lost in the Middle（位置偏置，U 型曲线）
│   ├── 2. RULER / Needle-in-a-Haystack / NoLiMa / HELMET（长上下文评测陷阱；context rot：有效检索随长度退化）
│   ├── 3. 三者成本/时效/可控性权衡
│   ├── 4. Prompt caching / KV cache 对长上下文经济性的改变（含写入溢价）
│   ├── 5. RAFT（检索增强微调）：RAG × 微调的组合范式
│   ├── 6. 语义缓存 / 响应缓存（GPTCache、Redis 向量相似缓存）
│   └── 7. build-vs-buy：模型自带搜索（web search 工具 / Perplexity API）vs 自建 RAG
│
└── G. 评估（RAGAS 等）
    ├── 1. 检索质量：Context Precision / Context Recall / nDCG / MRR / Recall@K
    ├── 2. 生成质量：Faithfulness（忠实度）/ Answer Relevancy / Noise Sensitivity
    ├── 3. RAGAS 指标体系（含无参考 LLM-as-judge）与 RAGChecker（claim 级细粒度）
    ├── 4. 引用质量：ALCE（citation precision / recall）
    ├── 5. ARES / TruLens / RGB 基准
    ├── 6. 记忆评估：LOCOMO / LongMemEval（含更新正确性、abstention）
    └── 7. 评估闭环：构建黄金集、监控漂移、A/B、judge 偏置校准
```

---

### 二、核心概念精讲

#### 2.1 Agent Memory：从"上下文窗口"到"记忆系统"

**是什么。** 在 Agent 语境里，"记忆"是把 LLM 有限的、无状态的 context window，扩展为**可跨轮次、跨会话、跨任务持续可用的信息存取机制**。它通常借认知科学的分层：

- **工作记忆（Working memory）**：当前真正进入 prompt 的内容，等价于 context window 的"有效载荷"。这是唯一直接影响模型输出的部分。
- **短期记忆**：单次会话内的对话历史、中间状态（scratchpad、tool results）。
- **长期记忆**：持久化到外部存储、按需检索回来的内容，又细分为：
  - *Episodic（情节）*：具体发生过的事件（"上周二用户部署失败，原因是 X"）。
  - *Semantic（语义）*：提炼后的事实与偏好（"用户偏好 TypeScript，生产环境用 Postgres"）。工程上常落地为一个**结构化用户画像**（JSON/表字段），比纯向量记忆更可控、更易全量注入。
  - *Procedural（程序）*：如何做事的知识。学术范例：**Voyager 技能库**（把验证过的代码技能存库复用）、**Reflexion / ExpeL**（从失败-重试轨迹中提炼可复用的经验法则）；工程范例：`CLAUDE.md`、`.cursor/rules` 这类"每次会话静态注入的项目规范"，本质就是程序记忆。

**为什么需要分层而不是"全塞进上下文"。** 三个硬约束：(1) **token 成本与延迟**随长度近似线性甚至更高增长；(2) **位置偏置**——即使支持 1M token，中段信息的检索准确率显著下降（见 2.6）；(3) **信噪比**——无关上下文越多，模型越容易被干扰（"上下文污染"）。因此记忆系统的本质是**一个检索/压缩/遗忘的决策系统**，而不是"存储系统"。

**怎么用——两条主流工程路线：**

1. **OS 式虚拟内存（MemGPT / Letta）**：把 context window 类比为 RAM，把外部存储类比为磁盘（recall storage 存会话史、archival storage 存任意事实）。模型通过**函数调用**（`core_memory_append/replace`、`conversation_search`、`archival_memory_insert/search` 等）主动管理"哪些信息该在 main context 里"。当对话溢出、系统发出 memory pressure 提示时，模型把旧内容分页（page out）到外部，需要时再检索回来。它把"记忆管理"变成模型的一项**可学习的技能**。
2. **结构化记忆层（Mem0、Zep/Graphiti）**：在对话流上跑一条 pipeline——**抽取**候选记忆 → **与既有记忆比对**（ADD / UPDATE / DELETE / NOOP 四种操作）→ 写入向量库或**时序知识图谱**。Mem0 的论文（2025）报告了两个**不同基线**下的结果——相较 **OpenAI Memory** 基线，在 LOCOMO 上 LLM-as-judge 分数相对提升约 **26%**；相较 **full-context（塞全量历史）** 方案，p95 延迟降约 **91%**、token 成本降 **90%+**。注意这是厂商自测、且与 Zep 的公开评测结论互相矛盾，引用前务必在自己的业务数据上复现（见易错点 17）。Zep/Graphiti 用**双时序**（事实生效时间 valid time × 写入时间 transaction time）的实体-关系图表达"事实随时间变化"，解决"用户三个月前的地址 vs 现在的地址"这类时序冲突——旧事实被置为失效而非物理删除，既支持"当时的情况"类问题，也保留审计线索。

**记忆生命周期（两套口径，别混用）。** ① **Generative Agents 的经典循环**：记忆流**写入**（观察）→ **检索**（按 **recency（指数衰减）× importance（LLM 打分）× relevance（嵌入相似度）** 加权打分）→ **反思**（定期把低层观察归纳为高层洞见，形成记忆树）→ **规划/行动**。这套"观察—反思—规划"循环是很多 Agent 记忆设计的思想源头。② **CoALA /《Memory in the Age of AI Agents》综述**的四阶段词汇 **Write → Select → Retrieve → Reflect**，与上者大体对应（Write≈写入、Select≈从长期存储挑选载入工作记忆、Retrieve≈检索、Reflect≈反思）——但"**Select**"并非 Generative Agents 的术语，引用时不要把这套四阶段挂到 Generative Agents 名下。2025 年的 **sleep-time agents**（如 Letta 提出）把反思进一步推进：在用户不交互的间隙离线跑"巩固/去重/改写/归纳"，把记忆整理的算力成本从交互路径上移走。

**工作记忆侧的实用技术**（容易被忽视但极有效）：工具结果**按需裁剪/分页**（只把摘要放进上下文，全文落盘按 id 取回）；把中间状态**外化到文件**（"在纸上思考"，代码 Agent 的通用做法）；系统提示与画像保持稳定前缀以命中 **prompt caching**。

**上下文压缩（prompt/context compression）。** 当上下文仍然过长时，可在注入前先压缩。**LLMLingua-2** 训练一个小分类器做 **token 级选择性删除**（保留信息量高的 token）；**Selective Context** 按自信息筛选保留单元；**RECOMP** 则对检索结果做**抽取式/生成式压缩**（抽关键句或先生成一段摘要再喂给模型）。典型压缩率 **2–5×**，代价是不同程度的信息损失，质量曲线必须在自己的评估集上验证。但要给一个**反趋势判断**：2025 年后上下文单价骤降 + prompt caching 普及，"无脑全量压缩"的 ROI 在下降——压缩更值得用在**长工具结果、低价值冗余上下文**上，而非默认对一切都压。

**Compaction 与上下文工程（2025 主流工程模式）。** Anthropic《Effective context engineering for AI agents》（2025）把这类实践系统化为"上下文工程"：在正确时刻把正确信息以正确形式放进上下文。其代表性落地是 **compaction（会话压缩）**——长会话接近上下文上限时，把已有轨迹**总结成一段更短的摘要**再继续（Claude Code 的 `/compact` 即此机制），常配合"保留最近访问的若干文件/状态"重建工作记忆。它与上面的 token 级压缩不同：compaction 是**会话级的语义重写**，直接服务于长程 Agent 的可持续运行。另一个配套思路是**把子 Agent 当作上下文防火墙**——将高 token 消耗的子任务交给子 Agent，只把精炼结论回传主线，避免主上下文被中间过程撑爆。

**记忆怎么评估**：学术基准有 **LOCOMO**（超长多会话对话）与 **LongMemEval**。LongMemEval 按论文口径考察五类能力：**信息抽取**（single-session-user / single-session-assistant / multi-session 三种来源）、**多会话推理**（需跨会话整合证据链，≠ 多次召回）、**时序推理**、**知识更新**、**abstention（没记住的应拒答而非编造）**。工程上务必额外测两件事：**更新正确性**（新事实能否正确覆盖旧事实）与**拒答率**（从未提及的偏好是否会被幻觉出来）。

**记忆与检索的安全：从原则到具体技术。** "检索内容是不可信数据"只是原则，落地有四层技术：① **Spotlighting（Microsoft, 2024）**——用定界符（delimiting）、数据标记（datamarking）或编码（encoding，把外部文本转成模型不易当作指令的形式）明确区分"数据"与"指令"，降低间接注入成功率；② **Instruction hierarchy**——让模型按优先级对待指令（系统 > 用户 > 工具/检索结果），使检索内容里夹带的指令不被执行；③ **写入侧清洗管线**——内容写进长期记忆前过滤指令性文本、做投毒检测（针对 AgentPoison / PoisonedRAG 类攻击），只写经验证的结论；④ **读取侧隔离与审计**——按用户 namespace 隔离、记录每条记忆的来源与被哪轮使用，便于事后追溯。这些都是"减速带"而非"墙"，需与权限最小化、不可逆操作 HITL 叠加使用。

**常见误区。**
- ❌ 把"长期记忆"等同于"向量库存聊天记录"。真正的难点是**写入什么、何时更新、如何消解冲突、如何遗忘**，而不是"存下来"。
- ❌ 忽视记忆的**一致性与陈旧性**。没有 UPDATE/DELETE 机制的记忆库会越用越"脏"。
- ❌ **盲信厂商基准**：Mem0 与 Zep 的公开对比结论彼此矛盾（各自都宣称自己更好）。选型必须在**自己的业务数据**上重放评估。
- ❌ **忽视记忆安全**：检索回来的内容、用户输入都可能携带恶意指令，一旦被写入长期记忆就形成**持久化的间接提示注入（memory poisoning，见 AgentPoison / PoisonedRAG 等研究）**；记忆里还有 PII，必须做到加密、按用户隔离、**可导出可删除**（合规刚需）。
- ❌ 在不需要时强行上记忆。很多任务用"会话内摘要 + 明确的用户画像字段"就够了，过早引入复杂记忆层会放大不可解释性。

---

#### 2.2 Embedding：检索质量的天花板

**是什么。** Embedding 模型把文本映射到向量空间，使"语义相近"近似等价于"向量相近"。它决定了**召回的上限**——如果正确文档在嵌入空间里离 query 很远，后面的 reranker/长上下文都救不回来。

**三大表示范式（必须能对比）：**

| 范式 | 原理 | 代表 | 优点 | 缺点 |
|---|---|---|---|---|
| **稀疏（Sparse）** | 词项权重向量（维度=词表） | BM25、SPLADE、ELSER | 精确匹配强（专有名词/ID/罕见词高 IDF）、可解释、便宜 | 难处理同义/改写（除非学习型扩展）；精确词项匹配，对错别字不宽容 |
| **稠密（Dense）** | 单向量，Bi-encoder 独立编码 | OpenAI text-embedding-3、Qwen3-Embedding、BGE-M3、Cohere embed-v3/v4、Gemini Embedding、NV-Embed-v2 | 语义泛化强、支持 ANN | 对罕见词/精确串匹配弱 |
| **多向量 / Late Interaction** | 每 token 一个向量，检索时 MaxSim 交互 | ColBERT/ColBERTv2、ColPali/ColQwen2 | 精度接近 cross-encoder，可预计算 | 存储/索引成本高 |

值得一提：**BGE-M3 的"三态一体"**——单个模型同时输出 dense、learned sparse、ColBERT 式多向量三种表示，一套索引天然支持 hybrid，是 2024-2026 开源侧的代表性设计。

**选型方法论（2024-2026 实操）**：看 **MTEB / C-MTEB**（中英）榜单的 **Retrieval 子集**做 shortlist，但**榜单 ≠ 你的领域**，且 **MTEB 自身亦有训练集重叠/数据污染与过拟合争议**（部分上榜分数难以复现）——排名只当 shortlist，最终判据永远是自己评估集上的 Recall@K / nDCG / 端到端答案率。权衡维度：开源（Qwen3-Embedding、BGE-M3、GTE、E5-mistral，可自部署、数据不出域）vs API（OpenAI、Cohere、Voyage、Gemini，免运维但有合规与成本账）；多语言能力；最大输入长度；单条延迟与批量吞吐。近两年的格局：开源权重（Qwen3-Embedding 0.6B/4B/8B、NV-Embed-v2）在 MTEB 上已与顶级 API 模型互有胜负，"必须用闭源 API"在 2026 年不再成立。

**关键工程细节（面试区分度高）：**

- **Bi-encoder vs Cross-encoder**：Bi-encoder 把 query 和 doc **分别**编码成向量，可离线预计算 doc 向量并建 ANN 索引，检索 O(log N)，但两者**不交互**，精度有上限。Cross-encoder 把 `[query, doc]` **拼接送入一个模型**交互打分，精度高，但**无法预计算**、必须逐对推理，所以只能做 **rerank**（对 top-K 小集合）而不能做召回。"召回用 Bi-encoder、精排用 Cross-encoder"是标准两段式。
- **对称 vs 非对称检索**：语义相似度（句A ↔ 句B）是对称任务；而"问答检索"（短 query → 长 passage）是非对称的。很多模型（E5、BGE、GTE）要求给 query 加 `"query: "`、给 passage 加 `"passage: "` 这类**指令前缀**，用错前缀会显著掉点。
- **维度与 Matryoshka（MRL）**：text-embedding-3（原生 `dimensions` 参数）、Gemini Embedding、jina-v3 等支持把高维向量**截断**到 256/512 维而几乎不损失召回——因为 MRL 训练让**前 k 维就携带大部分信息**。这是降存储/降延迟的利器，面试常考"为什么不直接 PCA"（答：MRL 是训练时优化的、截断即用的；PCA 需要你在自己的语料上重拟合且对分布敏感）。注意**并非所有模型都支持 MRL 截断**：**BGE-M3 固定 1024 维**不支持；Cohere embed 系列走的是 **int8/binary 量化**而非维度截断，二者别混为一谈。
- **归一化与度量**：对归一化向量，cosine ≡ dot ≡（单调等价于）L2，所以"用哪种距离"在归一化后基本是伪问题；真正重要的是**有没有归一化**、以及索引与查询是否用**同一度量**。
- **最大输入长度与静默截断**：嵌入模型有硬性 token 上限（老模型 512，新一代多为 8192+），**超出部分被静默丢弃、不报错**。chunk size 必须 ≤ 模型上限，否则长块尾部信息永远进不了索引——这是最隐蔽的线上事故之一。
- **模型版本绑定**：向量与生成它的嵌入模型**强绑定**，换模型必须**全量重嵌重索引**，新旧向量不可混用比对。把 `{model_name, model_version, dim}` 写进元数据是基本工程卫生。
- **领域漂移与微调**：通用嵌入在垂直领域（法律、医疗、代码）常掉点。对策顺序：换更强通用模型 → 修 chunking / query 改写 → 加（或微调）reranker → 最后才微调嵌入。确需微调用**对比学习 + 难负例**（BM25/稠密 top-K 中剔除正例得到 hard negatives；或用 cross-encoder 蒸馏伪标签），并保留通用验证集防**灾难性遗忘**。经验：**数据有限时"微调 reranker"往往比"微调 embedding"更划算**。
- **多模态**：版面复杂的 PDF/扫描件可走 **ColPali/ColQwen2** 直接对文档图像做 late-interaction 检索，绕开 OCR 误差；Cohere v4、Gemini Embedding、Voyage 等多模态嵌入可统一图文空间。

**常见误区。**
- ❌ "换个更大的嵌入模型就能解决检索差"。多数"检索差"其实是 **chunking 问题或 query-doc 措辞鸿沟**，不是嵌入模型问题。先做错误分析（到底是没召回，还是召回了但排序低）。
- ❌ 用 cosine 相似度阈值做"是否相关"的硬判定。绝对分数跨模型、跨语料不可比，**应用相对排序 + rerank**，而不是拍一个 0.78 的阈值。

#### 单向量 embedding 的理论表达上限（Google DeepMind, 2025）

**考点**：为什么 hybrid / 多向量 / rerank 不只是工程妥协，而是**理论必需**。

**机制**：DeepMind 2025 年论文《On the Theoretical Limitations of Embedding-Based Retrieval》证明：固定维度 d 的单向量嵌入，能精确表示的"top-k 相关文档组合"数量存在**数学上限**（基于 sign-rank 的论证）——一旦任务要求的相关组合复杂度超过该上限，**换更强的模型、喂更多的数据都无解**。作者据此构造 **LIMIT 基准**：查询极其简单（"谁喜欢苹果？"式），只因相关组合覆盖了文档间的所有两两配对，SOTA 单向量模型就大面积失败（recall@100 普遍很低），而 **BM25（超高维稀疏）与 ColBERT 式多向量**不受同一上限约束、表现明显更好。

**面试怎么用**：把本章的 hybrid（2.5）、BGE-M3 三态一体（2.2）、ColBERT late interaction、两段式 rerank 串成一句话——"单向量是**信息瓶颈**：可表示的相关组合随维度只多项式增长，而组合空间指数爆炸，所以稀疏 / 多向量 / 交互式打分是**补齐表达力的理论必需**，不是锦上添花"。追问"那单向量为何仍是主流"：真实查询的相关结构远比 LIMIT 的对抗构造稀疏，且 ANN 基建成熟——正确姿势正是"单向量粗召回 + sparse 兜底精确匹配 + 多向量/cross-encoder 精排"。

---

#### 2.3 Chunking：被严重低估的一环

**是什么。** 把长文档切成可索引、可检索、可塞进 prompt 的单元。切分粒度直接决定**检索精度**与**上下文噪声**的平衡。

**切分之前：摄取与解析（ingestion）。** 真实项目里，**解析质量常常是第一瓶颈**，比换嵌入模型更能决定上限。要点：① **版面解析**——PDF/扫描件用专门的版面解析器（**Docling、Marker、unstructured** 等）还原标题层级、列表、阅读顺序，而不是裸抽文本流；② **表格与图片**——表格尽量保留结构（Markdown/HTML 原样入块）、为图表生成 caption 一并嵌入，复杂版面可走 **OCR + 版面模型**，或直接用 **ColPali/ColQwen2** 对文档图像检索以绕开 OCR 误差；③ **元数据**——解析时同步抽取 `source/url/owner/updated_at/acl` 等，供后续过滤、权限与溯源。**"垃圾进、垃圾出"在 RAG 里首先体现在摄取层**——解析切碎了、表格拍平了，下游再怎么优化也救不回来。

**主流策略与取舍：**

- **固定长度 / 递归字符切分**：按 token 数（如 256–512，且 **≤ 嵌入模型上限**）+ overlap 切。简单、可预测，是强基线。overlap 防止语义被截断。
- **语义切分（semantic chunking）**：计算相邻句嵌入相似度，在"语义断裂处"切分。理论上更干净，但实测**收益常不稳定**、且引入额外超参（断点阈值）；不是银弹。
- **结构感知切分**：按 Markdown 标题、HTML 标签、代码 AST 切分，天然保留层级。对文档/代码库极有效。**表格是难点**：尽量保留表格结构（Markdown/HTML 原样入块）、为表格生成 caption 一并嵌入、大表按行组分块；把表格拍平成散文通常会让数字检索变差。
- **Parent-Document / Small-to-Big**：**用小单元检索（精准定位），返回其所属的大父块给 LLM（充足语境）**。这是解决"块太小信息不足、块太大噪声多"矛盾的经典范式。长上下文时代，"Big" 可以更大（返回整节甚至整页），但检索这一步并未消失。
- **Proposition / Dense X Retrieval**：把文档拆成**原子命题（proposition）**再索引，检索粒度最细、最精准，但索引膨胀、实现成本高。
- **RAPTOR（ICLR 2024）**：自底向上**递归聚类（软聚类）→ LLM 摘要 → 建摘要树**，检索时可"折叠树"（所有层级的块一起检索）或"树遍历"（逐层下钻）。它让同一语料同时支持**细节问题与高层总结问题**，是"多粒度索引"的代表，与 GraphRAG 的社区摘要思想相通但更轻。
- **Contextual Retrieval（Anthropic, 2024）**：给每个 chunk 用 LLM 生成一段**"这个 chunk 在整篇文档中的上下文"前缀**再嵌入/做 BM25。Anthropic 报告：Contextual Embeddings 把 top-20 检索失败率降 35%，叠加 Contextual BM25 降 49%，再叠加 reranking **共降约 67%**。它直击"chunk 脱离上下文后语义残缺"（如"这家公司 Q3 增长 5%"——"这家"是谁？）的痛点。成本用 prompt caching 摊薄。
- **Late Chunking（Jina, 2024）**：先用长上下文嵌入模型**对整篇文档编码**，再在 token 级表示上按边界池化切块——让每个 chunk 向量都"见过全文"。区别于"先切再分别编码"的朴素做法。与 Contextual Retrieval 对照：前者改**编码方式**，后者改**文本本身**（因此对 BM25 也生效）。

**Index-time vs Query-time 计算权衡（资深框架）。** Contextual Retrieval、RAPTOR、GraphRAG 本质都是**把算力前置到索引期**：离线、可并行、可缓存、不占用用户等待预算，代价是语料更新时要重建；HyDE、Multi-Query、问题分解则是**把算力放在查询期**：灵活、无重建成本，代价是每次查询的延迟与费用。成熟工程师会按"语料更新频率 × 查询频率 × 延迟预算"在这两端之间分配智能，而不是无条件追求某一端。

**chunk size 的取舍（高频问答）：**
- 块太小 → 语义不完整、需要更多块才能回答问题、检索回来一堆碎片、索引膨胀。
- 块太大 → 一个块混多个主题、检索精度下降（向量被"平均"得泛泛）、占用宝贵上下文、稀释注意力。
- 经验区间常在 **128–512 tokens**，但**必须用自己的评估集调**，没有普适最优。

---

#### 2.4 向量数据库与 ANN 索引

**ANN 核心算法（要能讲原理）：**

- **IVF（Inverted File）**：先用 k-means 把向量聚成 nlist 个簇，查询时只搜最近的 nprobe 个簇。`nprobe` 是精度/速度旋钮。常配合 **PQ（乘积量化）** 压缩 → IVF-PQ，牺牲少量召回换内存大幅下降。
- **HNSW（Hierarchical Navigable Small World）**：分层图结构，上层稀疏用于快速"跳跃"、下层稠密用于精搜，查询近似 O(log N)，**召回-延迟表现通常优于 IVF**，但**内存占用高**、删除以"墓碑"标记需定期 rebuild。三个关键旋钮：**M**（每层邻居数，默认/常用 16，经验区间 16–48，越大越准但内存与建图时间越高）、**efConstruction**（建索引候选集，决定图质量）、**efSearch**（查询候选集，**线上召回/延迟的主旋钮**）。是目前工业默认选择之一。
- **DiskANN / Vamana**：图索引落 SSD、内存只放 PQ 压缩码，以**极低内存支撑十亿级**规模、召回接近 HNSW。pgvectorscale 的 StreamingDiskANN、Milvus 的 DiskANN 索引都是此系。
- **量化（PQ/SQ/Binary）**：用码本或低比特表示压缩向量。**二值量化（binary embedding）** 把 fp32 压成 1 bit（32× 压缩），配合**过采样候选 + 原向量重排**，在 ≥1024 维的归一化嵌入上召回损失很小——是 2024-2026 降本热点（Cohere、Qdrant、Weaviate、Milvus 均支持）。**前提**：二值量化要求嵌入本身**高维且对量化鲁棒**（OpenAI、Cohere 等官方明确支持的场景）；换任意中低维开源向量直接二值化，即使过采样+重排召回也可能明显塌方，必须先在自己的评估集上验证、不可外推。

**主流向量库选型（面试要能说出差异，而非背参数）：**

- **FAISS**：是**库**不是服务，单机、贴近研究基准、灵活但需自己搭高可用。适合原型与离线批量。
- **Milvus / Zilliz Cloud**：分布式、支持 GPU 索引、混合检索（dense+sparse）、丰富索引类型，面向大规模生产。
- **Pinecone**：全托管、serverless（存算分离、按用量计费），运维零负担，闭源、成本随规模需测算。
- **pgvector / pgvectorscale**：与业务 Postgres **同栈**，支持事务、JOIN、复杂 metadata 过滤，避免双写一致性问题；pgvectorscale 补上了 DiskANN 级规模。适合"向量只是业务数据的一个字段"的场景。
- **Qdrant / Weaviate / Chroma / LanceDB / Turbopuffer**：各有侧重（Rust 性能与 payload 过滤/多模态混合检索/本地轻量/嵌入式列存/基于对象存储的 serverless、按用量计费、天然 BM25+向量混合）。
- **传统搜索引擎的回归**：Elasticsearch 8 / OpenSearch / Vespa 已内置 kNN + BM25 + **RRF** 混合检索，Elastic 还有学习型稀疏模型 ELSER。**公司已有 ES 集群时，"在现有搜索引擎上做 hybrid"往往是最务实的起点**，省掉一套新系统的运维与数据同步。

**元数据过滤：预过滤 vs 后过滤（必考细节）。** 后过滤（先 ANN 取 top-K 再按属性筛）在**过滤选择性高**（命中很少）时会 top-K 不足甚至返回空，召回不可控；预过滤（把标签/ACL 下推进索引结构，如 Qdrant payload index、Milvus bitset）召回稳定但实现更重。权限场景**必须预过滤**（见题 8）。

**选型真正的决策维度**：数据规模与 QPS、p99 延迟要求、**metadata 过滤的复杂度**、是否需要全文/混合检索、一致性要求（与业务库同事务、CDC/binlog 增量同步）、运维能力、总拥有成本。**"先问能不能用 Postgres + pgvector 或现有 ES 解决"是资深工程师的克制。**

---

#### 2.5 检索范式：从单路到混合、从静态到自适应

**Dense / Sparse / Hybrid。** 稠密检索擅长语义泛化，稀疏检索（BM25）擅长**精确关键词、专有名词、产品型号、罕见词（高 IDF）**。注意 BM25 本质是**精确词项匹配，对错别字并不宽容**（拼写容错通常要靠 fuzzy/词干化，或交由稠密向量——subword 共享与语义平均使其对拼写变体更宽容）。二者错误模式**互补**，因此 **Hybrid 检索几乎是生产默认**。融合首选 **RRF（Reciprocal Rank Fusion）**：`score(d) = Σ 1/(k + rank_i(d))`（经验常数 **k=60**），只用排名不用原始分数，**天然规避了不同检索器分数尺度不可比**的问题（BM25 分数与 cosine 分数没法直接相加）。替代方案是带权线性融合（需先做 min-max/z-score 等**分数校准**）或学习型融合，但 RRF 因零校准、零训练、稳健，是最常用的默认。

**两段式：召回（Recall）→ 重排（Rerank）。** 召回阶段用便宜的 Bi-encoder/BM25 取 top-K（如 50–100，**宁多勿少，保 recall**），再用 reranker 对这 K 个精排，取 top-N（如 3–8）进 prompt。两类 reranker：
- **Cross-encoder**（Cohere Rerank、BGE-reranker-v2、Jina Reranker v2、Qwen3-Reranker）：逐对交互打分，性价比之王。
- **LLM 重排**（**RankGPT** 及其开源蒸馏系 RankZephyr / RankMistral / RankVicuna）：以 listwise、滑动窗口方式让 LLM 对候选列表排序，zero-shot 精度常优于小 cross-encoder，可输出排序理由，但**延迟与成本高一个量级**，适合高价值、低 QPS 场景或最后一层精排。

Rerank 通常带来**最显著且最便宜**的端到端质量提升，是性价比最高的优化点；当通用 reranker 不够时，**在自己的数据上微调 reranker**（比微调嵌入模型数据效率高得多）是进阶手段。

**Query 侧处理（被低估的杠杆）：**
- **Query Rewriting**：用户 query 往往口语化、含代词、信息残缺。改写/扩展能显著缩小与文档的措辞鸿沟。
- **HyDE（Hypothetical Document Embeddings）**：先让 LLM **生成一段假设性答案**，再用这段"假答案"去检索（因为它与真实文档的分布更接近，比短 query 更容易命中）。代价是多一次生成、且假设若错误会带偏。
- **Multi-Query / 问题分解 / Step-back**：把复杂问题拆成子问题分别检索（每路各自的 top-K 合并），或先问一个更抽象的"上位问题"获取背景。
- **Query Routing**：判断该 query 该查哪个索引（FAQ vs 产品文档 vs 代码库），或根本不需要检索（直接回答 / 调工具）。

**自适应检索（Adaptive Retrieval）。** 不是每个 query 都需要检索——简单事实题检索反而引入噪声和延迟。进阶做法让模型**自己决定检不检、检什么、检索结果可不可信**：
- **FLARE**：生成时监控 token 概率，**低置信度片段触发检索**，用证据续写——"边写边查"。
- **Self-RAG**：训练模型生成特殊的 **reflection tokens**（`[Retrieve]`、`[IsREL]`、`[IsSUP]`、`[IsUSE]`），按需触发检索并自我批判答案是否被证据支持。
- **CRAG（Corrective RAG）**：用轻量评估器把检索文档判为 **Correct / Ambiguous / Incorrect** 三档，分别走"**Correct → 先用，但仍做 knowledge refinement（分解-重组、剔除无关片段后再送入生成）** / Ambiguous → 保留并触发 web search 补充 / Incorrect → 丢弃并 query 重写"路径。注意 Correct 分支并非原文照单全收，去噪这一步正是"检索到了也要去噪"的佐证。
- **CRITIC**：让模型用外部工具（搜索、代码执行）逐条**验证并修正**自己的输出。
- **Agentic RAG**：把检索作为 Agent 的一个工具，放进"思考-检索-评估-再检索"的循环，可多跳、可换源、可自我纠错。详见 2.7。

**推理模型时代的检索注记（2025-2026，以下更多是工程经验观察而非定论）：** 深度推理模型（o 系列、DeepSeek-R1/QwQ 类）在实践中对上下文噪声往往**更敏感**——塞 20 个块常常不如喂 3–5 个高相关块让它专注推理；更好的姿势是让模型**在推理链里自己规划检索**（"我需要先查 A 再查 B"）。"检索越多越保险"的直觉在推理模型上经常失效，最终进 prompt 的条数应在自己评估集上消融确定。

#### 中文检索特化：分词、归一化与 C-MTEB（国内面试特色考点）

**考点**："把 RAG 从英文语料换到中文，哪些环节要改？"多数候选人只答"换个中文 embedding"，真正的区分点在**稀疏那一路**。

**BM25 与分词**。中文无空格分隔，BM25 的词项化必须显式分词——这是英文场景不存在的额外环节，两条路线各有取舍：**词级索引**（jieba、Elasticsearch 的 IK analyzer——惯用法 `ik_max_word` 建索引、`ik_smart` 切查询）词项语义完整、精度高、索引小，但受**分词错误与 OOV**（新词、产品名、人名）拖累——查询与文档切法不一致就直接召回失败，需**自定义词典**持续维护领域专名；**字级 / 字 n-gram 索引**（单字或 bigram）零 OOV、任何新词都能召回，代价是索引膨胀、大量字面撞车的噪声命中、精度下降。工程折中是**词级为主、n-gram 兜底**（ES 同字段挂多个 analyzer 分别建索引再融合）——本质上又是一组召回-精度旋钮。

**文本归一化（隐蔽但致命）**。全角/半角（"ＡＰＩ" vs "API"）、繁简体（"臺灣" vs "台湾"）、中英混排大小写，若不在**索引与查询两侧做同一套归一化**，就会出现"同一个词、两个字符串"的隐性 miss。ES 用 char filter / ICU 插件处理，自建管线则在摄取与查询入口统一收口。

**Embedding 侧**。中文选型看 **C-MTEB**（MTEB 中文基准）而非英文榜——同一模型中英榜排名差异可能很大；开源强模型集中在 BGE 系（智源）、GTE（阿里）、Qwen3-Embedding、bce-embedding（有道）等；中英混合语料或跨语检索（中文 query 查英文文档）要选**多语对齐**模型（如 BGE-M3）。

**追问怎么答**："为什么稠密检索受分词影响小？"——嵌入模型的 tokenizer 本身就是子词/字级切分，匹配发生在向量空间、不依赖显式词边界。因此中文 hybrid 里**稀疏路是更脆弱的一路**：分词与归一化质量要单独建 bad case 监控，别把"检索差"一律怪到 embedding 头上。

---

#### 2.6 RAG vs 长上下文 vs 微调

这是**最高频的开放题**，必须给出有结构的权衡框架。

**长上下文（Long Context）的陷阱。** Gemini/GPT/Claude 已支持 128K–1M+ token，"把文档全塞进去"看似能取代 RAG，但有三个硬伤：
1. **Lost in the Middle**：Liu et al. 证明，当关键信息位于上下文中段时，多文档问答准确率显著低于放在首尾（**U 型曲线**）。模型对位置的注意力不均。
2. **评测幻觉**：Needle-in-a-Haystack（大海捞针）"通过"≠ 真能用——那只是**单跳、字面匹配**的任务。**RULER**（多跳/变量追踪/聚合）、**HELMET**（检索/推理/摘要系统化评测）、**NoLiMa**（去针化、消除表面线索）一致表明：模型的**有效长度远小于标称长度**，很多"长上下文能力"被针式测试系统性高估。2025 年 Chroma 等提出的 **context rot** 进一步刻画这一现象：随上下文增长，模型对远端信息的有效检索能力持续退化——名义窗口靠位置编码缩放（RoPE 的 YaRN/NTK 扩展）撑出来，但训练分布集中在短序列，长尾检索质量系统性变差。
3. **成本与延迟**：每次请求都带全量文档，token 成本与首 token 延迟随长度线性涨。

**Prompt caching / KV cache 改变了经济账。** Anthropic 提供**显式缓存断点**（`cache_control`，前缀 ≥1024 tokens，TTL 5 分钟/可选 1 小时），缓存命中读取约为常规输入价的 **1/10**，但**写入有溢价**（5 分钟 TTL 写入约 **1.25×**、1 小时 TTL 约 **2×** 常规输入价）——只有前缀被足够多次复用才净赚，TTL 选择直接取决于复用频率；OpenAI 对 ≥1024 tokens 的稳定前缀**自动缓存**、无写入溢价，且命中折扣随代际一路加深：4o 代约为常规输入价的 **1/2** → GPT-4.1 代 **1/4** → GPT-5 代约 **1/10**（已与 Anthropic 命中价同一量级）；Gemini 提供显式 Context Caching。共性规律：**前缀越稳定、复用次数越多，长上下文越划算**。这直接催生了 CAG：

**CAG（Cache-Augmented Generation，2024）。** 把整个知识库**一次性预载进长上下文模型并常驻 KV 缓存**，每次查询只追加 query，**完全跳过实时检索**。适用三前提：知识库**小到放得进上下文**、**准静态**（缓存能被海量查询摊销）、对每次查询的相关性过滤要求不高。优势是零检索延迟、无检索误差传导、架构极简；局限是装不下 TB 级语料、无法按查询去噪（照吃 lost-in-the-middle）、语料一变缓存即失效、按用户隔离时复用率低。**定位：CAG 是 RAG 在"小而静态"场景下的特化/互补，不是替代**（详见题 13）。

**语义缓存 / 响应缓存（成本与延迟的又一杠杆）。** 除 token 级 prompt caching 外，还有一层**查询级缓存**：对语义相近的 query 直接返回缓存答案，跳过整条检索+生成链路。实现如 **GPTCache**（把 query 嵌入后做向量相似匹配命中缓存）、Redis 等向量相似缓存、以及按精确 query 去重。它对**高频重复流量**（客服 FAQ、固定报表）降本降延迟显著；但**命中率高度依赖负载重复度**——多样化真实流量的命中率常远低于厂商宣传，且相似 query 命中同一缓存答案有"答非所问"的风险，需设相似度阈值并按租户/时间隔离。它与 CAG 的区别：CAG 缓存的是"知识库上下文"，语义缓存缓存的是"最终答案"。

**build-vs-buy：先问要不要自建（2025-2026 趋势）。** 这是设计 RAG 前的第 0 个问题。2025 年起主流厂商把**搜索内建进模型**——OpenAI/Anthropic 的服务端 web search 工具、Gemini grounding with Search、Perplexity API，开箱即给带引用的实时答案，免维护索引与 pipeline。判据：**面向公网、通用、对延迟不极端敏感**的信息需求，直接用模型自带搜索往往更划算；**私有/领域语料、需严格权限与可审计、要求定制排序与评估、数据不出域**的场景，才值得自建 RAG。这与题 8"先问要不要上系统"一脉相承——**最成熟的决策常常是不自建**。

**三者权衡框架（给出这张表就赢了）：**

| 维度 | RAG | 长上下文 / CAG | 微调（SFT/LoRA） |
|---|---|---|---|
| **知识时效** | ✅ 实时（改库即生效） | ✅ 实时（但每次都要喂/重建缓存） | ❌ 冻结在训练时 |
| **可溯源/引用** | ✅ 天然可给出处 | ✅ 可引用原文 | ❌ 知识黑盒化 |
| **成本（推理）** | 中（检索+少量上下文） | 高→中（缓存命中后骤降） | 低（无额外上下文） |
| **成本（建设）** | 索引+pipeline | 低 | 数据+训练+评估 |
| **适合学什么** | **事实性、频繁更新的知识** | 临时/一次性/需推理的长材料；小而静态的 KB（CAG） | **行为/风格/格式/技能**、固定的领域语感 |
| **可控性/防幻觉** | 高（证据约束） | 中 | 中（难精确控制） |
| **规模上限** | TB 级语料可扩展 | 受窗口限制 | 受训练数据限制 |
| **典型失败** | 检索错误/上下文污染 | 中段丢失/成本高/缓存失效 | 灾难性遗忘/过拟合/难更新 |

**结论性判断（资深视角）：**
- 需要**精确、可更新、可引用**的知识 → **RAG**。
- 需要模型**稳定地以某种方式行为**（输出格式、语气、领域推理套路、工具使用规范）→ **微调**。
- **一次性**的长文档分析、或**小而静态的高频知识库** → **长上下文 / CAG**。
- 现实中常常是**组合拳**：**RAFT（Retrieval-Augmented Fine-Tuning）** 就是范例——用"正例文档 + 干扰文档 + 链式引用推理"的数据微调模型，教会它**忽略无关 chunk、只依据证据作答**，直接降低对检索噪声的敏感度。这说明**"RAG 与微调不是竞争而是正交"**（必答点）：微调教"怎么答"，RAG 给"答什么"，长上下文/缓存管"一次性大材料"。

---

#### 2.7 GraphRAG 与 Agentic RAG

**GraphRAG（Microsoft, 2024）。** 针对"naive RAG 擅长**点状事实**，但答不好**需要跨文档聚合/总览的宏观问题**"（如"这批语料的三大主题是什么"）的痛点。流程：
1. **索引**：用 LLM 从语料抽取**实体与关系**构建知识图谱（含多轮 gleaning 提高抽取覆盖）→ 用 **Leiden 算法做分层社区检测（community detection）** → 为每个社区生成**分层摘要报告**。
2. **查询**有两种模式：
   - **Local Search**：从相关实体出发，结合邻居、关系与原文块回答"具体实体"问题。
   - **Global Search**：对宏观问题，用 **map-reduce**——把社区报告分片让 LLM 各自产出部分答案并打分（map），再加权聚合（reduce）出全局回答。

**取舍**：GraphRAG 在"多样性/总览性"问题上显著优于 naive RAG，但**索引成本高出数个数量级**（海量 LLM 抽取与摘要调用）、对实体抽取质量敏感、语料更新需增量重建。**后续演进**：**LightRAG**（HKU）用实体+主题双层检索与增量更新降本；**KAG**（蚂蚁/OpenSPG）做 chunk 与 KG 互索引、逻辑式推理引导，在专业垂直域更强；**HippoRAG / HippoRAG 2** 借鉴神经科学海马体"模式补全"思路，在 OpenIE 图上用**个性化 PageRank** 做多跳联想检索，HippoRAG 2 进一步在线学习边权提升多跳效果。

**LazyGraphRAG（Microsoft, 2024.11）——"GraphRAG 索引太贵"这个追问的最新答案。** 思路是把算力从索引期**搬回查询期**：索引期不再用 LLM 抽实体、也不预生成社区摘要，只做轻量的名词短语抽取、共现图构建与社区划分；查询期先用 **BM25 类相关性测试取种子块**，再**沿图迭代深化**（相关性评估 → 扩展到相邻社区 → 只对被选中的子集做 LLM 摘要），按查询预算逐步加深，同一套机制同时覆盖局部与全局问题。微软报告其**索引成本约为原 GraphRAG 的 0.1%**、与 naive 向量 RAG 同一量级，而答案质量持平甚至更优。面试价值：它是 2.3 节"Index-time vs Query-time 权衡"的教科书案例——社区摘要从"建索引时对全语料预付"改为"哪个查询用到哪个社区、就在那时摘要哪个"，天然契合语料高频更新的场景；被追问"GraphRAG 成本"时，答完 LightRAG 再补一句 LazyGraphRAG，层次感立现。

**Agentic RAG。** 把 RAG 从"一次性 pipeline"升级为"Agent 循环"：检索是工具之一，Agent 可以**判断检索结果够不够 → 不够就改写 query 再检 / 换一个数据源 / 分解子问题多跳检索 / 调用计算器或 API 验证 / 必要时承认不知道**。它统一了 Adaptive/Self/Corrective RAG 的思想，是 2025-2026 的主流方向，并已**产品化**：Perplexity、OpenAI Deep Research、Gemini Deep Research 本质都是"agentic 多步搜索 + 阅读 + 综合"。2024 年底起的 **MCP（Model Context Protocol）** 进一步把检索能力标准化为可插拔的 server/工具——"语料库即服务"可被任意 Agent 挂载。代价是延迟、成本、不确定性上升，需要护栏：**最大迭代次数、token/时间预算、工具白名单、每步 trace 可回放、失败回退到单次 RAG**。

#### Agentic search vs 向量索引：coding agent 为什么不建索引

**考点**：2025 年前后的一个显著风向——"给 coding agent 做代码检索，要不要建向量索引？"Claude Code、Cline 等主流 coding agent 给出的答案是**不建**：弃用 embedding 索引，靠 **grep/glob + 多轮 agentic 探索**（搜索 → 读文件 → 顺着 import/引用继续搜）完成检索。

**弃用向量索引的四个理由**：① **stale-indexing**——代码分钟级变更，"改完代码等重嵌"的索引永远落后于磁盘真相，grep 每次查的都是最新状态，零同步成本；② **权限与安全边界**——向量索引是代码的**二次拷贝**，chunk 级 ACL 难做、易泄漏，本地 grep 天然继承文件系统权限，代码不出域；③ **构建与维护成本**——增量重嵌 pipeline（监听变更 → 重切 → 重嵌 → 失效旧向量）本身就是一个需要运维的系统；④ **代码天然适合结构化检索**——命名规范、符号引用、目录层级让精确匹配信噪比极高，且 agentic loop 可**自我纠错**（第一轮没搜到就换关键词再搜），单次检索的召回压力被多轮探索摊薄。

**向量检索何时仍然赢**：自然语言语料（文档、工单、对话记录——没有符号结构可 grep）；语义模糊查询（"哪里处理了限流"，措辞与代码可能毫无字面交集）；超大规模场景（千万行级 monorepo 上多轮 grep 延迟爆炸，需要索引先收敛候选）；以及运行环境没有文件系统访问权的产品形态。

**结论口径（面试必备）**："检索方式跟**介质与任务**走——代码与强结构文本优先 agentic search（grep/AST/LSP），自然语言语料优先向量 + hybrid；**'RAG = 向量库'是 2023 年的过时等式**，如今 R 指'任意检索工具'，向量库只是选项之一。"这与第 2 章"Preloading vs Just-in-Time Retrieval"、第 13 章 C 层的 progressive disclosure / JIT 检索是同一个判断的三个侧面：上下文按需拉取，检索器按介质选型。

---

#### 2.8 评估：RAGAS 与评估闭环

**为什么 RAG 必须分两段评估。** "答错了"可能源于**检索失败**（没找到对的证据）或**生成失败**（找到了但模型没用好/幻觉）。两段必须**解耦度量**，否则无法定位优化方向。

**RAGAS 核心指标（要能说出每个度量什么、需不需要 ground truth）：**

| 指标 | 度量 | 需要 ground truth? | 针对环节 |
|---|---|---|---|
| **Faithfulness（忠实度）** | 答案能否被**检索到的 context** 支持（无幻觉） | 否（LLM 判定） | 生成 |
| **Answer Relevancy** | 答案是否切题回答了问题 | 否 | 生成 |
| **Context Precision** | 检索回的块里，**相关的排得靠不靠前**（信噪比/排序） | 是 | 检索 |
| **Context Recall** | 回答所需的证据**被检索回了多少** | 是 | 检索 |
| Context Entities Recall | 答案所需实体的召回 | 是 | 检索 |

要点：**Faithfulness 不需要标准答案**——它只检查"答案 ⊆ 检索上下文"，这正是"无参考评估"的关键，也是它能用于**在线监控**的原因。它把幻觉定义为"超出证据的陈述"。

**更细粒度：RAGChecker（Amazon, 2024，NeurIPS 2024 D&B）。** 把评估下沉到 **claim（原子陈述）级**，分三组指标：Overall（Answer F1、Faithfulness、Claim Precision/Recall）、Retrieval（Context Relevance/Precision/Recall）、Generation（Claim Recall、Contextual Precision、Faithfulness、Answer Relevancy），并引入 **Noise Sensitivity（噪声敏感度）**——度量"答案被检索到的无关块带偏的程度"，这正是"检索到了但答错"的量化指标。诊断粒度比 RAGAS 更细，且带在线 dashboard，是 2025 年后的推荐补充。

**引用质量（可溯源场景必测）：** **ALCE** 系指标度量 **citation precision**（引用的来源真的支持该陈述吗）与 **citation recall**（该引用的陈述都标来源了吗）。"答案对"与"答案对且出处对"是两件事。

**其他评估工具/基准**：**TruLens**（RAG triad：context relevance、groundedness、answer relevance，带追踪可视化）、**ARES**（LLM 合成数据 + 少量人工标注训练轻量分类器做大规模评估）、**RGB**（专测 RAG 对**噪声/无关/矛盾文档**的鲁棒性，含"拒答"能力）。

**工程闭环（体现成熟度）：**
1. 建**黄金评估集**（真实 query + 标注答案 + 关键证据），**按问题类型分层**（事实型/多跳/聚合总结/越权与越界），并刻意包含**负例**（语料里根本没有答案的问题，测拒答）；冷启动可用 LLM 从文档合成 QA 对（RAGAS testset generation）。
2. 离线跑 RAGAS/RAGChecker 得到分环节基线 → 定位瓶颈在检索还是生成。
3. 上线后**采样 + LLM-as-judge 在线监控**忠实度与检索命中率，捕获**数据漂移**（文档变了、query 分布变了、嵌入模型改了）。
4. 任何 pipeline 改动（换模型/换 chunk size/加 rerank）都跑**回归评估**，防止按下葫芦浮起瓢。
5. 警惕 **LLM-as-judge 自身的偏置**（位置偏置、冗长偏置、**偏爱与自己同源的输出**）：用打乱顺序、双盲、**异构模型交叉评审**、抽样人工复核来校准。

---

### 三、面试高频考点

| 考点 | 高频度 | 一句话要点 |
|---|---|---|
| RAG vs 长上下文 vs 微调 的取舍 | ⭐⭐⭐ | 知识更新选 RAG，行为/风格选微调，一次性长材料选长上下文，常组合使用 |
| Bi-encoder vs Cross-encoder 为何分工 | ⭐⭐⭐ | 召回要可预计算→Bi-encoder；精排要交互精度→Cross-encoder |
| Dense / Sparse / Hybrid 与 RRF | ⭐⭐⭐ | 错误模式互补，RRF 用排名规避分数不可比（k=60） |
| Chunking 策略与 chunk size 取舍 | ⭐⭐⭐ | 小块精准、大块全；Small-to-Big / Contextual Retrieval / RAPTOR |
| 检索质量 vs 生成质量的评估解耦 | ⭐⭐⭐ | Context Precision/Recall 管检索，Faithfulness/Relevancy 管生成；RAGChecker 到 claim 级 |
| Lost in the Middle / 长上下文评测陷阱 | ⭐⭐⭐ | 中段信息易丢，Needle 测试高估真实能力（RULER/NoLiMa/HELMET） |
| Reranker 的作用与性价比 | ⭐⭐⭐ | 两段式中最便宜、最显著的质量提升；RankGPT 系 LLM 重排更准更贵 |
| Prompt caching 与 CAG 的边界 | ⭐⭐⭐ | 稳定前缀缓存命中后长上下文重新划算；CAG 只适合"小而静态"的 KB，不替代 RAG |
| 记忆生命周期：写入/更新/冲突消解/遗忘 | ⭐⭐⭐ | 好记忆是决策系统不是数据库；ADD/UPDATE/DELETE/NOOP、时序有效性 |
| Embedding 选型（MTEB）与指令前缀/对称性 | ⭐⭐ | 榜单只作 shortlist，必须自己数据复核；用错 query/passage 前缀掉点；MRL 可截断维度 |
| 单向量 embedding 的理论上限（LIMIT） | ⭐⭐ | 固定维度可表示的 top-k 相关组合有数学上限（sign-rank）；hybrid/多向量/rerank 是理论必需 |
| ANN 索引（HNSW vs IVF-PQ vs DiskANN） | ⭐⭐ | HNSW 快但吃内存（efSearch 是线上旋钮），IVF-PQ 省内存损召回，DiskANN 十亿级低内存 |
| 向量库选型与预/后过滤 | ⭐⭐ | 先问 pgvector/现有 ES；高选择性过滤必须预过滤，ACL 同理 |
| Faithfulness 的定义与无参考评估 | ⭐⭐ | 答案是否被 context 支持，无需 ground truth；高忠实 ≠ 答案对 |
| Query 改写 / HyDE / Multi-Query | ⭐⭐ | 缩小 query-doc 措辞鸿沟的查询期杠杆 |
| Agentic / Self / Corrective RAG | ⭐⭐ | 让模型决定检不检、检索结果可不可信、要不要补救；产品化即 Deep Research |
| GraphRAG 原理与成本取舍 | ⭐⭐ | 实体图+社区摘要解决宏观聚合问题，索引贵、更新难 |
| MemGPT / Mem0 / Zep 等 Agent 记忆机制 | ⭐⭐ | 虚拟内存分页 / 抽取-更新-冲突消解 / 时序知识图谱 |
| Index-time vs Query-time 计算权衡 | ⭐⭐ | Contextual/RAPTOR/GraphRAG 前置算力；HyDE/多查询后置算力；按更新频率与延迟预算分配 |
| 幻觉的成因与缓解 | ⭐⭐ | 检索失败与生成失败分开治；噪声敏感度单独度量 |
| 安全：间接提示注入 / 记忆投毒 | ⭐⭐ | 检索内容是不可信数据；写入长期记忆前做清洗/校验 |
| 嵌入领域适配 / 难负例微调 | ⭐ | 先换强模型、修 chunking、调 reranker，最后才微调嵌入；优先微调 reranker |
| 嵌入版本绑定与静默截断 | ⭐ | 换模型必须全量重嵌；chunk 不能超过模型 token 上限 |
| 上下文压缩与 compaction | ⭐⭐ | LLMLingua-2/RECOMP 压缩 2–5×；Claude Code `/compact` 会话级压缩；上下文降价后 ROI 在降 |
| 文档摄取/解析是首瓶颈 | ⭐ | 版面解析（Docling/Marker）/OCR/表格抽取质量常决定 RAG 上限 |
| 语义缓存与 build-vs-buy | ⭐⭐ | 相似 query 命中缓存降本；先问要不要自建——模型自带搜索/Perplexity API 可替代简单 RAG |
| 检索注入防御的具体技术 | ⭐⭐ | spotlighting / instruction hierarchy / 写入清洗 / 读取审计，是"减速带"非"墙" |

---

### 四、经典面试题与参考答案

#### 题 1（基础）：请完整描述一个生产级 RAG 系统的数据流。

**答题思路**：分成**离线索引**与**在线查询**两条链路讲，体现"两段式检索 + 评估"的工程全貌，避免只说"嵌入后做相似度搜索"。

**参考答案要点**：
- **离线索引**：数据接入/清洗（PDF 版面解析、API 拉取）→ **Chunking**（结构感知 + overlap，块 ≤ 嵌入模型上限）→（可选）**Contextual 前缀/元数据抽取** → **Embedding**（query/doc 前缀区分）→ 写入向量库（HNSW + metadata，**记录嵌入模型与版本**）→ 同步建 **BM25 稀疏索引**；变更走增量重建（按 doc_id 失效）。
- **在线查询**：Query 理解（改写/分解/路由）→ **多路召回**（dense + sparse，各取 top-K）→ **RRF 融合** → **Cross-encoder Rerank** 取 top-N → 组装 prompt（带出处、最相关的放首尾避中段）→ LLM 生成 → （可选）**忠实度校验/引用回填** → 返回。
- **横切**：评估集回归、监控（faithfulness 采样、检索命中率、延迟成本）、缓存（query 结果缓存 + prompt cache）、护栏（拒答、越权过滤）、全链路 trace。
- 加分：点出每个环节的可调旋钮与典型失败模式，并说明"先保召回再提精度"的两段式哲学。

---

#### 题 2（基础）：BM25 和向量检索各有什么优劣？什么时候用哪个？

**答题思路**：从"错误模式互补"切入，而不是罗列公式。

**参考答案要点**：
- **BM25（稀疏）**：基于词频饱和（k1）+ 逆文档频率 + 长度归一化（b）。优点：**精确匹配强**（人名、型号、错误码、专有名词）、对**罕见词鲁棒**（高 IDF）、可解释、零训练、便宜。缺点：**词汇鸿沟**——"汽车"搜不到"轿车/automobile"；且本质是**精确词项匹配，对错别字并不宽容**（拼写容错通常靠 fuzzy/词干化，或交由稠密向量）。
- **向量检索（稠密）**：语义泛化强，能跨措辞匹配。缺点：对**精确串/罕见 token**弱（embedding 可能把罕见专有名词编码得很泛）、黑盒、需维护索引。
- **结论**：生产里**用 Hybrid**——BM25 兜精确匹配，向量兜语义泛化，RRF 融合。如果资源极受限或语料是强关键词型（日志、代码、法条编号），纯 BM25 也可能是极强的基线。
- 加分：指出 BGE-M3 这类模型单模型同时给 dense+sparse，hybrid 的工程成本已大幅降低。

---

#### 题 3（进阶）：为什么召回用 Bi-encoder、重排用 Cross-encoder？能不能反过来或只用一个？

**答题思路**：抓住"能否预计算"这个根本差异。

**参考答案要点**：
- **Bi-encoder** 把 query、doc **独立编码**，doc 向量可**离线预计算 + 建 ANN 索引**，检索 O(log N)，能在百万级里召回；代价是 query 与 doc **无交互**，精度有上限。
- **Cross-encoder** 把 `[query, doc]` **拼接联合编码**，token 间充分交互，精度高；但**无法预计算**，每对都要现跑一次推理 → **不可能在百万级上逐个打分**，只能对小集合（top-K）精排。
- 所以标准架构是：**Bi-encoder 召回（保 recall，K 取 50–100）→ Cross-encoder 重排（提 precision，取 top-N）**。只用 Bi-encoder 会损失精度；只用 Cross-encoder 不可扩展。
- 加分：① **ColBERT 式 late interaction** 是折中——token 级向量可预计算、检索时做 MaxSim，精度接近 cross-encoder、可扩展性接近 bi-encoder，代价是存储；② **RankGPT 系 LLM 重排**精度更高但更贵，常作最后一层或高价值场景；③ 召回不足时先调大 K，再谈 rerank，顺序不能反。

---

#### 题 4（进阶）：用户反馈"答案不对"，你如何系统性地定位与优化？

**答题思路**：展示**分诊（triage）方法论**——先分清是检索问题还是生成问题，再对症。这是区分背概念与真做过项目的题。

**参考答案要点**：
1. **先取证**：拿到具体 query，检查**检索回来的 chunks 是什么**、最终 prompt 长什么样、trace 里每一步的输入输出。
2. **二分定位**：
   - 若**正确证据根本没被检索回来** → **检索问题**。再细分：
     - chunk 切碎了 / 证据散落在多块 → 调 chunking、用 Parent-Document、Contextual Retrieval、RAPTOR。
     - query 与文档措辞鸿沟大 → Query Rewriting / HyDE / Multi-Query。
     - 专有名词没命中 → 加 BM25 走 Hybrid。
     - 块超过嵌入模型上限被静默截断 → 缩块或换长上下文嵌入。
     - 嵌入领域不适配 → 换更强模型 / 难负例微调。
   - 若**证据检索到了但答案仍错** → **生成问题**：
     - 上下文太长、关键信息在中段 → 重排后只放 top-N、把最相关的放首尾。
     - 上下文有矛盾/噪声（**噪声敏感度高**）→ 提高 rerank 截断、减少进 prompt 的块数。
     - 模型没遵循证据/幻觉 → 强化"仅依据上下文、无证据就说不知道"指令、加 Faithfulness 校验、换模型。
   - 若**两者都对但问题本身需要聚合/多跳推理** → 架构问题：考虑问题分解、Agentic 多跳、GraphRAG。
3. **量化**：用评估集分别看 Context Recall/Precision 与 Faithfulness/Noise Sensitivity，确认改动方向，跑回归。
- 加分：强调"没有评估集就无法判断优化是否真的有效，可能只是修好了这一个 case、弄坏了别的"。

---

#### 题 5（进阶）：chunk size 该怎么定？太大太小分别有什么问题？你怎么找到最优值？

**答题思路**：讲清取舍 + 给出"用数据而非拍脑袋"的方法。

**参考答案要点**：
- **太小**：语义不完整（代词无指代、句子被截断）、需要拼多块才能答题、检索回一堆碎片、索引膨胀。
- **太大**：一个块混杂多主题、检索精度下降（向量被"平均"得泛泛）、占用宝贵上下文、稀释模型注意力、增加成本；还可能**超过嵌入模型上限被静默截断**。
- **经验区间**：常见 128–512 tokens + 10–20% overlap，但**无普适最优**，取决于文档结构与查询类型。
- **结构缓解**：用 **Small-to-Big / Parent-Document**——用小块（或句子/命题）做检索保精度，返回其父级大块给 LLM 保语境，绕开"精度 vs 完整"的二选一；长上下文让父块可以更大。
- **找最优**：建评估集（query + 正确出处块），以 **Context Recall/Precision、端到端答案正确率**为指标，对候选 chunk size 做网格搜索；同时监控延迟/成本。语义切分可作为对照，但不迷信。

---

#### 题 6（进阶）：解释 Faithfulness（忠实度）这个指标。它需要标准答案吗？它和"答案正确"是一回事吗？

**答题思路**：精准定义 + 辨析它与 correctness 的区别，体现对幻觉本质的理解。

**参考答案要点**：
- **定义**：把答案拆成若干**陈述（claims/statements）**，逐条判断能否被**检索到的 context** 蕴含/支持；Faithfulness ≈ 被支持的陈述占比。它衡量的是"答案有没有**超出证据**乱说"。
- **不需要 ground truth**：只需 query、context、answer 三者，用 LLM 做自然语言推理判定，属于**无参考评估**。这是它能在生产在线监控的原因。
- **≠ 答案正确**：
  - 答案可以**忠实但错误**——如果检索回来的 context 本身就是错的，模型忠实复述，Faithfulness 满分但答案错。
  - 答案可以**正确但不忠实**——模型用参数知识答对了，但 context 里没有依据，Faithfulness 低（在要求"仅凭证据"的场景这仍算违规，因为不可溯源、不可控）。
- 所以评估要**分维度**：Faithfulness（是否守证据）+ Context Recall/Precision（证据对不对、全不全）+ Answer Correctness（最终对不对）+ 可溯源场景再加 **citation precision/recall**。

---

#### 题 7（进阶）：什么是 Contextual Retrieval？它解决了什么问题？代价是什么？

**答题思路**：说清痛点（chunk 脱离上下文语义残缺）与机制，并客观讲成本。

**参考答案要点**：
- **痛点**：朴素切块让 chunk **丢失文档级语境**。例如某 chunk 写"Q3 营收同比增长 8%"，单独看不知道"哪家公司、哪一年、对比什么"，导致嵌入与 BM25 都难命中。
- **机制（Anthropic, 2024）**：对每个 chunk，用 LLM **结合整篇文档**生成一段 50–100 token 的"该 chunk 所处上下文"说明，**拼到 chunk 前面**，再分别做 embedding 和 BM25 索引（因此对稠密和稀疏两路都生效）。
- **效果**：Anthropic 报告 Contextual Embeddings 使 top-20 检索失败率降 35%，叠加 Contextual BM25 降 49%，再叠加 reranking **累计降约 67%**。
- **代价**：索引阶段要对每个 chunk 调一次 LLM，**预处理成本显著上升**；用 **prompt caching**（整篇文档作为可缓存前缀，Anthropic 报告可降本 ~90%）大幅摊薄。对频繁更新的语料，重建成本需权衡。
- 加分：与 **Late Chunking**（先整篇编码再切，让块向量含全局信息，改的是编码方式）、**RAPTOR**（递归摘要树，改的是索引结构）对比——三者都是"索引期前置算力"的不同形态。

---

#### 题 8（系统设计）：为一家公司的内部知识库设计 RAG，文档包括 PDF/Confluence/代码，权限复杂，要求答案可溯源、可更新。请给出设计。

**答题思路**：系统设计要覆盖**数据接入→索引→检索→生成→权限→评估→运维**全链路，并主动点出关键设计决策与取舍。

**参考答案要点**：
- **数据接入与解析**：PDF 用版面解析（含表格保留结构/图片 caption，必要时 OCR 或 ColPali 直接图像检索）；Confluence 走 API 取结构化正文+元数据；代码用 AST 按符号切分。**统一 schema**：`{doc_id, chunk_id, text, source, url, owner, tags, updated_at, acl, embed_model_ver}`。
- **权限（必考）**：采用 **ACL 下推到检索层的预过滤**——把每个 chunk 的访问控制（用户所属 group/role）作为索引内可过滤字段，检索时**先过滤再 ANN**，**绝不**先检索全量再后置裁剪（会泄漏 + 高选择性下 top-K 直接为空）。与企业 IdP（SSO/Groups）同步，权限变更触发增量标记更新。
- **索引**：结构感知 chunking + Parent-Document；Hybrid（dense + BM25）；Contextual 前缀提升专名与残缺语境命中；HNSW（efSearch 按延迟预算调）或托管向量库；按 source 分 namespace/collection。
- **检索与生成**：Query 路由（FAQ/文档/代码分别走不同索引与块粒度）→ Hybrid 召回 + RRF → Rerank → 组装 prompt **强制带引用**（每个论断挂 source url，最相关放首尾）→ 生成 → **Faithfulness 校验 + citation 回填**，低于阈值显式说"证据不足"。
- **可更新**：文档变更 webhook → 按 doc_id 增量重切/重嵌/失效旧向量；保留版本以便回滚；嵌入模型升级时全量重嵌、双索引灰度切换。
- **可溯源**：答案引用 chunk_id → 反链原文锚点位置；前端可点开核对；日志留存便于审计。
- **评估与运维**：建分层黄金集跑 RAGAS/RAGChecker 回归；线上采样 LLM-judge 监控忠实度与命中率；query 日志回流扩充评估集（含拒答负例）；A/B 上线；全链路 trace。
- **主动讲的取舍**：多租户用 namespace 隔离防串库；代码检索用 AST 符号索引 + 嵌入混合；宏观总结类问题评估 GraphRAG/RAPTOR 但先算索引成本；若只是单个小产品的静态 FAQ，可退化为 CAG（整库预载进缓存）省掉整套 pipeline——**先问要不要上系统**。

---

#### 题 9（开放）：现在模型支持 1M token 上下文，RAG 还有必要吗？

**答题思路**：这是考察判断力的题，避免极端回答。承认长上下文的进步，但用具体证据说明 RAG 不可替代。

**参考答案要点**：
- **长上下文的进步是真的**：减少了对"切块拼 prompt"的依赖，某些一次性长文档分析可直接喂；prompt caching 又大幅改善了重复读取的经济性。
- **但 RAG 仍然必要，理由：**
  1. **成本/延迟**：每次请求都带 1M token 极贵且慢；RAG 只取相关 top-N，token 量小几个数量级。Caching 缓解但不消除（语料频繁变、按用户隔离时缓存命中率低）。
  2. **Lost in the Middle 与有效长度**：长上下文存在位置偏置；RULER/NoLiMa/HELMET 表明**有效检索长度远小于标称长度**，多跳/聚合任务尤其掉点。
  3. **可更新性**：知识库天天变，RAG 改库即生效；全量塞上下文每次都要重传、缓存频繁失效。
  4. **可溯源/可审计**：RAG 天然给出处，合规场景刚需；长上下文里定位出处更难。
  5. **规模**：企业语料是 TB 级，远超任何 context window，**必须先检索缩小范围**——这一点与上下文多长无关。
  6. **噪声控制**：相关性过滤本身是价值，全塞会稀释注意力、抬高噪声敏感度。
- **更准确的结论**：二者**互补**，且边界因缓存而弹性化——**小而静态**的 KB 可走 CAG，**大而动态**的语料必须 RAG，主流形态是：RAG 召回相关子集 → 把较大但已过滤的相关材料放进（可能很长的）上下文 → 让模型在充分语境里推理。长上下文降低了对"极致小块"的依赖（Small-to-Big 的 Big 可以更大），但**没有取消检索这一步**。

---

#### 题 10（开放/前沿）：Agentic RAG 相比传统 RAG 强在哪？带来什么新问题？你会在什么场景采用？

**答题思路**：讲清范式跃迁（pipeline → loop），并客观评估代价，体现工程成熟度。

**参考答案要点**：
- **传统 RAG 的局限**：单次、固定 pipeline——一次检索定生死；遇到**多跳问题、检索失败、需要跨源/跨工具**的情况无能为力。
- **Agentic RAG 的增强**：把检索变成 Agent 的工具（2025 年起常经 **MCP** 标准化暴露），进入"**检索 → 评估证据是否充分/可信 → 决策**"的循环：不够就改写 query 再检、分解子问题多跳、换数据源、调计算器/API 验证、必要时承认不知道。它统一了 FLARE（按置信度触发）、Self-RAG（自我反思 token）、CRAG（按检索质量纠错）的思想，产品化形态即 Perplexity / Deep Research 类深度搜索。
- **带来的新问题**：
  - **延迟与成本**：多轮检索 + 多次 LLM 调用，p99 与费用上升一个量级。
  - **不确定性/可控性**：行为路径不固定，难复现、难回归测试，需护栏（最大迭代、工具白名单、token/时间预算、失败回退单次 RAG）。
  - **错误累积**：一步检索错误可能被后续放大；需要证据校验打断。
  - **可观测性**：必须记录每步 trace（query/检索/决策）以便调试与审计。
  - **安全面扩大**：多源检索 = 更多间接提示注入入口，检索内容一律当不可信数据。
- **采用判据**：问题**复杂、多跳、多源、质量优先于延迟**时用（研究助手、复杂故障诊断、尽调）；**简单 FAQ/低延迟**场景用单次 RAG 甚至 CAG 即可，**不要为了"智能"而过度工程化**。

---

#### 题 11（记忆专题）：MemGPT 和"把对话存进向量库再检索"有什么本质区别？

**答题思路**：抓住"主动管理 vs 被动存储"的差异。

**参考答案要点**：
- **被动存储式记忆**：把历史对话切片嵌入向量库，需要时按相似度检索。问题：记忆是**死数据**，没有"什么该记、什么该忘、冲突如何更新"的机制，容易召回陈旧/矛盾内容。
- **MemGPT / Letta 的范式**：把上下文窗口当 **RAM**、外部存储当**磁盘**（recall/archival 两级），让模型通过**工具调用主动管理内存**（`core_memory_append/replace`、`archival_memory_insert/search`、`conversation_search`），memory pressure 时**分页（page out）**，需要时取回。核心区别是：**记忆管理是模型的一项可学习决策**，而非固定 pipeline。
- 进一步（Mem0/Zep）：引入**写入-更新-冲突消解**（ADD/UPDATE/DELETE/NOOP）与**双时序知识图谱**（valid time × transaction time），让记忆能随时间正确演化——旧事实失效而非删除，既解决"旧偏好覆盖新偏好"，又支持"当时的情况"类问答与审计。
- 再进一步（sleep-time agents）：把反思/巩固放到会话间隙离线执行，交互路径零额外延迟。
- 一句话：**好的记忆系统是"决策系统"（记什么/忘什么/更新什么），不是"数据库"。**

---

#### 题 12（进阶）：如何为一个新领域选择嵌入模型？什么情况下需要微调嵌入？

**答题思路**：先证伪"瓶颈在嵌入"，再给选型流程，最后才谈微调，体现"不默认微调"的克制。

**参考答案要点**：
- **先归因**：检索差常常是 chunking、query-doc 措辞鸿沟、缺稀疏路造成的，不是嵌入模型。先做 bad case 分析（没召回 vs 召回但排序低），排除上游问题。
- **选型流程**：以 **MTEB / C-MTEB 的 Retrieval 子集**做 shortlist（2025-2026 开源如 Qwen3-Embedding、BGE-M3、GTE、E5-mistral；API 如 OpenAI text-embedding-3、Cohere v4、Voyage、Gemini Embedding）→ 权衡多语言、最大输入长度、维度/MRL、自部署合规与延迟成本 → **必须在自己领域的评估集上复核**（Recall@K、nDCG、端到端答案率），榜单不等于领域表现。
- **微调的时机**：通用强模型 + chunking + query 改写 + rerank 都做到位仍不达标时。方法：**对比学习 + 难负例**（BM25/稠密 top-K 中剔除正例；或用 cross-encoder 蒸馏软标签），保留通用验证集防**灾难性遗忘**。
- **反直觉要点**：数据有限时，**微调 reranker 通常比微调 embedding 性价比更高**（pairwise 信号直接、所需数据少）；换模型必须**全量重嵌、双索引灰度切换**，向量不可跨模型混用。

---

#### 题 13（开放/前沿）：什么是 CAG（Cache-Augmented Generation）？它会取代 RAG 吗？

**答题思路**：讲清机制与适用三前提，定位成"特化而非替代"。

**参考答案要点**：
- **机制**：把整个知识库**预载进长上下文模型并常驻 KV 缓存**（利用 Anthropic/OpenAI/Gemini 的 prompt caching），每次查询只追加 query，**无实时检索环节**（Chan et al., 2024；WWW 2025，arXiv:2412.15605）。
- **优势**：零检索延迟、无检索误差传导、架构极简（无向量库/pipeline）、缓存命中后边际成本极低。
- **适用三前提**：① KB **小到放得进上下文**；② KB **准静态**，缓存能被大量查询摊销；③ 不需要按查询做强的相关性去噪。
- **局限**：装不下 TB 级语料（规模天花板）；全量进上下文照吃 **lost in the middle** 与噪声；KB 一更新缓存即失效；按用户隔离时缓存复用率低；低频查询摊销不动。
- **结论**：CAG 是 RAG 在"小而静态、高复用"场景下的**特化/互补**（如单产品 FAQ、固定规范手册），**不取代**大而动态语料上的 RAG；现实中常见混合：热门小知识库走 CAG，长尾与大规模走 RAG。它真正说明的是：**缓存改变了"上下文的经济性"，但没改变"相关性与规模需要检索来解决"这一事实**。

---

#### 题 14（系统设计）：为一个 AI 助手设计跨会话长期记忆系统（个性化陪伴/企业客服均可），要求记得住、不过时、不泄密。

**答题思路**：按记忆类型分别设计存储，写/读两条链路 + 时序一致性 + 评估 + 安全，体现"记忆是决策系统"。

**参考答案要点**：
- **分层存储（按类型选介质）**：
  - *语义/画像*：结构化 KV/表字段（偏好、语言、套餐），每轮**全量注入**系统提示，保证一致性；
  - *情节*：会话摘要 + 事件日志，向量化 + 元数据（时间、会话 id、重要性）入库，**选择性注入** top-K；
  - *程序*：验证有效的交互策略/模板，作为规则或 few-shot 库管理（类似 CLAUDE.md 机制）。
- **写链路（异步、不阻塞对话）**：会话结束/定期触发 → LLM **抽取**候选记忆 → 与既有记忆比对做 **ADD/UPDATE/DELETE/NOOP**（冲突消解：新覆盖旧、显式声明覆盖推断）→ 带 `valid_from/valid_to`（双时序）、来源链接写入。**坏记忆可回滚**。
- **读链路（预算约束下的组装）**：每轮工作记忆 = 稳定前缀（系统提示+画像，吃 prompt cache）+ 情节 top-K（按 **recency × importance × relevance** 打分）+ 当前工具结果；设 token 预算上限，宁缺毋滥。
- **时序与遗忘**：旧事实**置为失效而非删除**（支持"以前怎样"与审计）；低重要性记忆按时间衰减；定期 **reflection** 把碎片观察归纳为高层洞见（Generative Agents）；**sleep-time 离线任务**做去重、合并、冲突巡检。
- **评估**：LongMemEval 式五能力（单/多会话召回、时序推理、**知识更新**、**abstention 拒答**）+ 自有黄金集；重点测"更新正确性"与"没记住时是否编造"。
- **安全与合规**：记忆含 PII → 加密、按用户 namespace 隔离、**可导出可删除**；写入前把外部内容当**不可信数据**过滤指令性文本，防**记忆投毒/持久化注入**；读取时同样隔离，防跨用户串库。
- **可观测性**：记录每条记忆的写入来源、被哪轮使用、是否被答案采纳（记忆命中率），作为迭代依据。

---

### 五、易错点 / 反直觉点

1. **"检索到了 ≠ 能用"**：top-K 里有正确文档不代表模型答对——可能排序太低被挤出 prompt、可能在中段被忽略、可能与噪声块矛盾。**召回成功与端到端成功是两回事，必须分别度量**（RAGChecker 的 Noise Sensitivity 正是为此）。
2. **绝对相似度阈值是个坑**：cosine 0.78 在不同模型/语料下含义完全不同，跨数据集不可比。**用相对排序 + rerank，不要拍硬阈值**做"相关/不相关"判定。
3. **归一化后纠结距离度量是伪命题**：向量 L2 归一化后，cosine、dot、L2 单调等价，结果一致。真正要确认的是**有没有归一化**、以及索引构建与查询是否用了**同一度量**。
4. **Embedding 指令前缀用错直接掉点**：E5/BGE/GTE 等对 query 与 passage 要求不同前缀（如 `"query: "` vs `"passage: "`），漏加或加反会显著降召回，且报错很隐蔽。
5. **语义切分不是银弹**：理论上更干净，实测收益常不稳定、还引入断点阈值超参。**固定长度 + overlap 是极强基线**，先证明语义切分在你的评估集上真的更好。
6. **chunk 越小越精准？未必**：过小导致语义残缺、答案需跨块拼合反而失败。精度与完整性要用 Small-to-Big 之类范式同时满足。
7. **长上下文能取代 RAG 是错觉**：标称 1M ≠ 有效 1M；Needle 测试通过 ≠ 多跳/聚合任务可用；成本与可更新性也撑不住。CAG 只在小而静态的 KB 上成立。见题 9、题 13。
8. **Faithfulness 高 ≠ 答案对**：若检索来的证据本身是错的，模型忠实复述也会满分却错误。**忠实度、证据正确性、答案正确性要分开看。**
9. **RAG 与微调对立是误解**：二者正交——微调教"怎么答（行为/格式/风格）"，RAG 给"答什么（事实/最新知识）"；RAFT 证明微调还能反过来降低模型对检索噪声的敏感度。生产常组合。
10. **权限后置裁剪会泄漏且伤召回**：先全量检索 top-K 再按权限过滤，高选择性下 top-K 可能全是用户无权看的 → 召回为空；正确做法是把 ACL 作为**预过滤**下推到向量库。
11. **Rerank 是最被低估的性价比优化**：很多人花大力气换嵌入模型，其实加一个 cross-encoder rerank（或微调 reranker）往往提升更大更便宜。
12. **GraphRAG 不是万能升级**：它擅长宏观聚合问题，但索引成本极高、对实体抽取敏感、不适合高频更新语料；**naive/Hybrid RAG + rerank 在多数点状问答上已经很好**，别为了用图而上图。
13. **LLM-as-judge 自身有偏置**：位置偏置、偏好更长答案、偏爱与自己同源的输出。用它做评估要打乱顺序、双盲、**异构模型交叉评审**、抽样人工复核校准。
14. **只修单个 bad case 会按下葫芦浮起瓢**：没有回归评估集就调参，很可能修好一个、弄坏一片。**先建评估集，再谈优化。**
15. **嵌入模型会静默截断超长块**：多数嵌入模型超过最大输入（512/8192）直接丢弃尾部且不报错——长块的末尾永远进不了索引。chunk size 必须以嵌入模型上限为上界。
16. **换嵌入模型 ≠ 换配置项**：向量空间整体改变，新旧向量**不可混用**，必须全量重嵌 + 双索引灰度切换；忘记这一点会出现"改完模型召回反而崩了"。
17. **厂商记忆基准互相打架**：Mem0 与 Zep 的公开对比结论相反，各自都赢。任何记忆/检索选型都要在**自己的业务数据**上重放评估，不要引用厂商数字当结论。
18. **检索内容是不可信数据**：网页、文档、用户历史里可能埋着恶意指令；一旦被 Agent 执行或**写入长期记忆**，就形成持久化的间接提示注入（memory poisoning）。读取与写入两侧都要把内容当数据而非指令处理。
19. **"塞更多 chunk 更保险"是错的**：上下文噪声会抬高噪声敏感度、触发中段丢失；rerank 后的 top-3~8 通常优于不筛选的 top-50。对推理模型尤其如此——少而精胜过多而杂。
20. **记忆只增不减必然变脏**：没有 UPDATE/DELETE/失效机制的记忆库，陈旧偏好与矛盾事实会持续污染输出；评估记忆系统必须测"知识更新正确性"和"没记住时会不会编"。

---

### 六、推荐资源

1. **Anthropic —《Introducing Contextual Retrieval》（官方博客, 2024）**
   讲清"chunk 脱离上下文"的痛点与 Contextual Retrieval + BM25 + Reranking 的实测收益（失败率累计降约 67%），附 prompt caching 成本分析。短小、权威、直接可用于面试论述。
   https://www.anthropic.com/news/contextual-retrieval

2. **Lewis et al. —《Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks》（RAG 原始论文, NeurIPS 2020）**
   RAG 的奠基论文，理解"参数化记忆 + 非参数化记忆"结合的源头思想。读摘要与方法部分即可建立正确心智模型。
   https://arxiv.org/abs/2005.11401

3. **Microsoft —《From Local to Global: A Graph RAG Approach to Query-Focused Summarization》（2024）**
   理解实体图谱 + Leiden 社区检测 + map-reduce 全局摘要的机制，以及它针对"宏观总览问题"的设计动机与索引成本取舍。
   https://arxiv.org/abs/2404.16130

4. **RAGAS 官方文档 + RAGChecker（Amazon, NeurIPS 2024 D&B）**
   RAGAS 是 Faithfulness / Answer Relevancy / Context Precision / Context Recall 等指标的标准参考；RAGChecker 把评估细化到 claim 级并引入 Noise Sensitivity，是"如何定位 RAG 瓶颈"的现代工具。面试谈评估必引其一。
   https://docs.ragas.io/ ；https://arxiv.org/abs/2408.08067 ；https://github.com/amazon-science/RAGChecker

5. **Liu et al. —《Lost in the Middle》（TACL 2024）+ RULER（2024）+ NoLiMa（2025）+ HELMET（2024）**
   长上下文位置偏置的经典实证，及其后续系统化评测：一致表明"有效长度远小于标称长度、Needle 测试系统性高估"。回答"RAG vs 长上下文"时最有力的论据链。
   https://arxiv.org/abs/2307.03172 ；RULER: https://arxiv.org/abs/2404.06654

6. **Packer et al. —《MemGPT: Towards LLMs as Operating Systems》（2023）+ Mem0 论文（2025）**
   Agent 长期记忆的两大范式：OS 式虚拟内存分页 vs 抽取-更新-冲突消解的记忆层；配合 Zep/Graphiti 的时序知识图谱一起看，覆盖 2024-2026 记忆系统的主流设计。
   https://arxiv.org/abs/2310.08560 ；Mem0: https://arxiv.org/abs/2504.19413

7. **Sarthi et al. —《RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval》（ICLR 2024）**
   多粒度索引的代表：递归聚类摘要树如何同时服务细节问题与宏观总结，是 Contextual Retrieval、GraphRAG 之外"索引期前置算力"的第三条路。
   https://arxiv.org/abs/2401.18059

8. **自适应检索三件套：FLARE（2023）/ Self-RAG（2023）/ CRAG（2024）**
   理解"让模型自己决定检不检、检索结果可不可信、错了怎么救"的演进脉络，是答 Agentic RAG 题的思想源头。
   FLARE: https://arxiv.org/abs/2305.06983 ；Self-RAG: https://arxiv.org/abs/2310.11511 ；CRAG: https://arxiv.org/abs/2401.15884

9. **组合与替代范式：RAFT（检索增强微调, 2024）+ CAG（Chan et al., 缓存增强生成, WWW 2025）**
   一篇讲"微调如何服务于 RAG、降低噪声敏感度"，一篇讲"缓存如何让检索在小而静态场景下消失"。二者一起读，才能把"RAG / 长上下文 / 微调"三角讲出 2025 年的最新形态。
   RAFT: https://arxiv.org/abs/2403.10131 ；CAG: https://arxiv.org/abs/2412.15605

10. **Wu et al. —《LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory》（2024）**
    长期记忆能力的标准评测框架（单/多会话召回、时序推理、知识更新、拒答），设计或评估 Agent 记忆系统时的对标基准；可配合 LOCOMO 一并了解。
    https://arxiv.org/abs/2410.10813

11. **MTEB / C-MTEB（Massive Text Embedding Benchmark）**
    嵌入模型选型的公共基准与排行榜。学会"看 Retrieval 子集 shortlist、再在自己数据上复核"的方法，比记住任何具体模型名次都重要。
    https://huggingface.co/spaces/mteb/leaderboard

12. **Anthropic —《Effective context engineering for AI agents》（2025）**
    上下文工程的定义性文章：系统讲 compaction（会话压缩）、把子 Agent 当作上下文隔离、"在正确时刻放正确信息"的方法论，是本章开篇"上下文工程"框架的一手出处；Claude Code 的 `/compact` 自动压缩即其工程落地。
    https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
