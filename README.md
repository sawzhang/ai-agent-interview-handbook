# 📘 AI Agent 面试深度学习手册

> 面向资深工程师 / 面试候选人的 **AI Agent 完整知识体系 + 备考作战手册**。
> 12 大知识域 + Harness 元框架 + 应用形态专题 · 56 万字 · 结合 2024–2026 最新资料 · 含 10 个可运行动手实验 · 经多智能体对抗性评审与修订。
>
> **内容基准日：2026-08** —— 技术与法规陈述均以此为时间基准，引用前请自行核实原始出处。

---

## 📦 交付物一览

```
agent-interview/
├── index.html                     🌐 学习网站（搜索/二级导航/暗黑/打印 · 第13章交互式 ETCLOVG 分层图）
├── AI-Agent面试学习手册.md          📄 完整手册（单文件，56 万字，便于全文检索/导入笔记）
├── 考前速记表.md                    🎯 浓缩版（高频考点 TOP + 各章速记 + 答题框架）
├── 模拟面试追问链.md                🎤 11 条追问链（含行为面/项目深挖）· 递进追问（强答要点 + 红旗 + 练习锚点）
├── chapters/                      📂 按章拆分的 Markdown（15 个文件，便于精读）
│   ├── 00-开篇导读.md               （知识全景图 / 面试考察地图 / 4 周学习路线 / 答题框架）
│   └── 01 ~ 14 章 …
├── labs/                          🧪 动手实验（10 个，纯标准库可运行）
│   ├── README.md
│   ├── llm_client.py              （阿里云百炼真实 LLM 客户端，零依赖）
│   └── lab01 ~ lab10 …
└── flashcards/                    🎴 抽认卡
    ├── anki_cards.txt             （187 张，制表符分隔，可直接导入 Anki）
    └── qa_review.md               （Q&A 复习册）
```

## 🚀 快速开始

| 想做什么 | 怎么做 |
|---|---|
| **浏览学习** | 双击 `index.html`（推荐，带搜索与导航） |
| **全文检索 / 导入 Obsidian·Notion** | 打开 `AI-Agent面试学习手册.md` 或 `chapters/` |
| **动手做实验** | `cd labs && python3 lab01_react_agent.py`（详见 `labs/README.md`） |
| **接入真实大模型** | `export DASHSCOPE_API_KEY='sk-sp-..'` 后跑 `labs/lab09_real_llm_react.py` |
| **刷题** | 把 `flashcards/anki_cards.txt` 导入 Anki（Basic 类型，制表符分隔） |
| **考前冲刺** | 只看 `考前速记表.md` + 各章「易错点」 + `模拟面试追问链.md` 自追问 |

## 🗺️ 知识体系（12 域 + 1 元框架章 + 1 应用形态章）

| 层 | 章节 |
|---|---|
| 🧱 **基础层** | ① LLM 基础原理 · ② Prompt 与上下文工程 |
| 🧠 **认知层** | ③ Agent 核心架构与推理范式（枢纽）· ④ Memory 系统与 RAG |
| 🤝 **行动协作层** | ⑤ Tool Use / Function Calling / MCP · ⑥ Multi-Agent 系统 |
| 🛠️ **工程层** | ⑦ 主流框架生态 · ⑧ 评估与可观测性 · ⑨ 安全与 Guardrails · ⑩ 工程化与生产部署 |
| 🚀 **前沿综合层** | ⑪ 前沿论文与热点 · ⑫ 系统设计题与综合实战 |
| 🧩 **元框架层** | ⑬ Agent 工程分层架构与 Harness Engineering（ETCLOVG 七层 / 三阶段演进 / 三大跨层权衡）——横切 ②–⑩ 的元框架 |
| 📱 **应用形态层** | ⑭ 应用形态专题：GUI·浏览器 / 语音 / 端侧 Agent——同一内核在三大载体上的落地形态，横向承接 ③⑤⑨⑩ |

**每章固定 6 模块**：知识图谱 → 核心概念精讲 → 面试高频考点（⭐分级）→ 经典面试题与参考答案 → 易错点·反直觉点 → 推荐资源。

## 🧪 动手实验（labs/）

10 个**纯标准库、零依赖、可直接运行**的实验，内置 assert 自检：

ReAct 循环 · Function Calling 调度器 · RAG 全链路 · Memory 系统 · LLM-as-Judge 评估 ·
Prompt Injection 攻防 · 多智能体编排 · 语义缓存与模型路由 · **真实 LLM tool-use ReAct（接入阿里云百炼）** ·
自适应 RAG 的几何级数扩容与成本账。

```bash
cd labs
for f in lab*.py; do python3 "$f"; done   # 一次全跑，全部 ✅ 自检通过
```

## ✅ 质量保证流程

本手册按工程闭环生产，而非一次性生成：

1. **多智能体深度研究**：12 知识域并行检索 2024–2026 权威资料并整合。
2. **对抗性评审（evals）**：独立评审团按 5 维 rubric（准确/深度/完整/面试相关/时效）打分，
   并对每章面试题参考答案做**联网对抗性校验**——共抓出 17 条高严重度事实/时效硬伤
   （如 MCP spec 版本日期、Microsoft Agent Framework 时间线、DeepSeek-R1 vs R1-Zero、
   pass^k 数学错误、论文链接张冠李戴等）与 15 条答案纠错。
3. **逐章精确修订**：按缺陷清单逐条修正、联网复核、补全缺失主题与结构。
4. **复测**：重新校验 HTML/Markdown 结构、重跑全部实验、抽查修订效果。

> ⚠️ **安全**：代码中的 LLM Key 一律从环境变量读取，绝不硬编码；`labs/.gitignore` 已忽略密钥文件。
> 若曾在任何地方明文粘贴 Key，请立即在控制台重置。

## 📚 方法论来源

本手册的分层工程观参考《Agent Harness Engineering: A Survey》——该综述覆盖 110+ 篇论文、分析 23+ 个已部署系统：第 13 章的 **ETCLOVG 七层分类**（Execution / Tooling / Context / Lifecycle / Observability / Verification / Governance）与 **Prompt Engineering → Context Engineering → Harness Engineering** 三阶段演进即源自该综述，用于把分散在各章的可靠性关切统一为一个可控、可检查、可恢复的系统。

- 预印本全文：<https://openreview.net/pdf?id=eONq7FdiHa>
- 项目页：<https://picrew.github.io/LLM-Harness/>

> ⚠️ 该综述仍在 TMLR 审稿中（Under review），尚未经同行评议定稿，结论与分类可能随修订变化；本手册第 13 章据此加了相应说明，引用时请一并注明其预印本状态。

## 📅 建议学习路径

详见 `chapters/00-开篇导读.md`：知识全景图（分层依赖）→ 面试考察地图（按公司/级别）→
**4 周学习路线**（约 60 小时）→ 答题通用框架（概念/原理/系统设计/项目四套方法论）。

## ⚠️ 免责声明

- **独立性**：本手册为个人独立整理的学习资料，与 Anthropic、OpenAI、Google、DeepSeek、阿里巴巴及文中提及的任何公司均无关联，未获其审阅或背书。文中产品名与商标归各自权利人所有，仅作技术指代与学习讨论之用。
- **内容性质**：所有面试题均为依据公开资料自行编写的**模拟题**，不含任何公司的真实面试题或内部资料。
- **时效与准确性**：内容含大量时效性技术与法规陈述，**内容基准日：2026-08**。技术生态变化快，引用前请自行核实原始出处；发现错误欢迎提 issue。

## 📄 许可

本仓库是「文字 + 代码」的混合作品，两部分许可不同（详见 [LICENSE](LICENSE)）：

- **文字内容**（`chapters/`、合订本、速记表、追问链、`flashcards/`、章节正文）—— [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh)：可自由分享与改编，须署名、非商业、相同方式共享。
- **代码**（`labs/*.py`、`serve.py`、`build_search_index.py`）—— MIT。

---

> 📘 祝面试顺利。细节回归各章，动手验证回归 labs/。
