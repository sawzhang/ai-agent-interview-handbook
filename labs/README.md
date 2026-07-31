# 🧪 AI Agent 动手实验（Labs）

> 8 个**可直接运行**的实验，对应核心知识域。**纯 Python 标准库 + Mock LLM，无需安装任何依赖、无需 API key**。
> 每个实验都内置 assert 自检，运行成功会打印 `✅ 自检通过`（已全部独立实测通过）。

## 运行方式

```bash
cd labs
python3 lab01_react_agent.py                 # 任选一个直接跑
for f in lab*.py; do python3 "$f"; done      # 或一次全跑
```

## 实验一览

| # | 文件 | 对应知识域 | 你将搞懂 |
|---|---|---|---|
| 01 | `lab01_react_agent.py` | 第3章 Agent 核心架构 | 手写 Thought→Action→Observation 主循环：工具注册表、正则动作解析、AST 安全计算器、最大步数与循环检测双护栏 |
| 02 | `lab02_tool_calling.py` | 第5章 Tool Use / Function Calling | JSON Schema 工具声明、调用前参数校验、线程池并行执行、错误统一捕获为 observation 并触发恰好一次重试 |
| 03 | `lab03_rag_pipeline.py` | 第4章 Memory 与 RAG | 分块(重叠/尾块合并)→词袋嵌入→余弦粗排→精排→top-k 拼装→抽取式作答全链路，并用断言验证分块大小对召回的决定性影响 |
| 04 | `lab04_memory_system.py` | 第4章 Memory 系统 | 工作记忆(token 上限队列+超限摘要压缩)与长期记忆(bigram 倒排索引的事实写入/召回)，理解"丢细节保要点" |
| 05 | `lab05_eval_harness.py` | 第8章 评估与可观测性 | 评估集 + rubric 打分的 LLM-as-Judge + 指标聚合 + trace 记录四件套，搭一条可复现可断言的评估流水线 |
| 06 | `lab06_injection_guardrail.py` | 第9章 安全与 Guardrails | 五场景演示直接/间接注入攻防：输入过滤 + 指令-数据沙盒 + 输出校验 + 最小权限，理解"单层必可绕过、纵深才安全" |
| 07 | `lab07_multi_agent.py` | 第6章 Multi-Agent 系统 | orchestrator「分解→按依赖分派→聚合」三段式编排、带角色的 worker 与共享黑板的信息流 |
| 08 | `lab08_cache_routing.py` | 第10章 工程化与生产部署 | 词袋向量+余弦相似度的语义缓存，与关键词/长度启发式的大小模型路由，实测成本下降 70%+ 的权衡 |
| 09 | `lab09_real_llm_react.py` | 第3/5/10章 综合 | **接入真实大模型**跑原生 tool-use ReAct 循环（`get_weather`→`calculator` 自主调用）；无 Key 时自动降级为同构 Mock，两种模式共用同一循环代码 |

## 🔌 接入真实 LLM（阿里云百炼 Token Plan）

`lab09` 与 `llm_client.py` 演示如何用**真实大模型**（而非 Mock）跑 Agent，纯标准库、零依赖：

- **网关**：`https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic`（Anthropic Messages 兼容，路由到 Qwen/GLM/DeepSeek）
- **模型**：`qwen3.7-max`（默认）、`qwen3.8-max-preview`、`qwen3.7-plus`、`qwen3.6-flash`、`glm-5.2`、`deepseek-v4-pro`…

```bash
# ① 设置 Key（仅当前 shell，切勿写进代码/提交到 git）
export DASHSCOPE_API_KEY='sk-sp-....'
# 可选：覆盖模型 / 端点
export LLM_MODEL='qwen3.7-max'

# ② 运行真实实验
python3 lab09_real_llm_react.py     # 真实 tool-use ReAct
python3 llm_client.py               # 客户端连通性自检
```

> **把任意 lab 的 MockLLM 换成真实模型**：各 lab 的 Mock 都实现了 `chat()`/`__call__` 接口，
> 导入 `from llm_client import QwenLLM` 并替换实例即可（lab09 已演示真实/Mock 同构切换的标准做法）。

> ⚠️ **安全须知**：代码只从环境变量 `DASHSCOPE_API_KEY`（及 `BAILIAN_API_KEY`/`ANTHROPIC_AUTH_TOKEN`）读取 Key，
> **绝不硬编码**。请勿把 Key 贴进聊天、代码或版本库；若已泄露请立即在百炼控制台**重置**。
> 建议在 `labs/` 放一个 `.gitignore` 忽略 `.env`。

## 学习建议

- 先读每个文件顶部的 docstring（目的 / 核心概念 / 思考题），再对照代码逐行理解。
- 每个实验末尾的**思考题**是面试延伸——试着先口述答案，再用手册对应章节核对。
- 把 MockLLM 换成真实 API 调用，即可扩展成可上线的最小系统。
