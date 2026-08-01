# 第 5 章 · Tool Use / Function Calling / MCP

## Tool Use / Function Calling / MCP

### 1. 知识图谱

```
Tool Use / Function Calling / MCP
├── 1. Function Calling 原理
│   ├── 执行模型：模型生成"调用意图"，宿主程序执行（关注点分离）
│   ├── Agentic Loop：tool_use → 执行 → tool_result → 继续生成
│   │   ├── Anthropic：content blocks（tool_use / tool_result），stop_reason="tool_use"
│   │   ├── OpenAI：tool_calls 数组（arguments 为字符串）+ role="tool" 消息，finish_reason="tool_calls"
│   │   └── 循环托管：OpenAI Agents SDK（Runner 托管完整 loop）/ Claude Agent SDK（原 Claude Code SDK，2025-09 更名）；
│   │       Responses API 仅在厂商侧执行 server-side 工具，client 函数仍需调用方自己跑循环（语义不变）
│   ├── 工具的两类执行位置：client-side 自定义工具 vs 厂商托管 server-side 工具
│   │   （web search / code execution / memory / web fetch：厂商基础设施执行、按次计费、带缓存语义）
│   ├── 模型如何获得该能力：SFT/RL 工具轨迹训练 + 特殊控制 token（可微调增强，OpenAI 支持）
│   ├── 开源/自托管：原生工具格式（Llama-3.1 / Qwen / GLM）vs 模板式（ChatML / Hermes）；vLLM / llama.cpp 内建 grammar 约束生成
│   ├── 输出合规保障：best-effort vs strict（constrained decoding：CFG→FSM→logit masking）
│   ├── 流式工具调用：工具参数以增量 JSON 到达（Anthropic input_json_delta / OpenAI tool_calls delta），
│   │   块完整（收到 stop_reason/finish_reason）后才能执行
│   ├── 与扩展思考协同：interleaved thinking（工具调用之间插入思考块）；多轮往返须原样回传 thinking 块
│   └── 调用控制：tool_choice（auto / any≡required / 指定 tool / none）、强制调用、并行开关
├── 2. JSON Schema 工具定义
│   ├── 结构：name / description / input_schema（JSON Schema 子集）
│   ├── description 的双重作用：工具选择 + 参数填充（改 description ≈ 改模型行为）
│   ├── 设计原则：少而高价值、动作聚合、onboarding 式描述、精确命名、enum、可修复错误
│   ├── strict 模式（grammar-constrained decoding）：OpenAI strict:true 强制所有字段 required + additionalProperties:false，
│   │   一律不支持 minLength/pattern/format 等校验关键字；Anthropic 现已支持 strict:true（不强制 required-all）；两家均只保结构不保语义
│   ├── 复杂工具：input_examples / tool use examples 提供 few-shot 约定
│   └── Token 经济学：工具定义计入 input tokens + 自动注入的启用 system prompt（数百 token）；
│       tools 段位于缓存顺序最前，用 prompt caching 缓存；厂商对超大工具输出有默认截断
├── 3. 并行工具调用与编排
│   ├── 模型侧：单轮输出多个 tool_use block（parallel_tool_calls / disable_parallel_tool_use）
│   ├── 客户端侧：并发执行、依赖分析、部分失败、幂等、限流
│   ├── Programmatic / Code-based Tool Calling：模型写沙箱代码编排，中间结果不进上下文
│   └── 收益量化：延迟下降（实测可达数倍，报告值 ~3.7x）、token 下降（实测 ~37%）
├── 4. 工具选择与大规模工具管理
│   ├── 工具数量 vs 性能：上下文膨胀、选择混淆、注意力稀释
│   ├── 手段：命名空间/分组、embedding/BM25 两阶段检索、Tool Search（lazy loading）
│   ├── 能力打包的互补范式：Agent Skills（渐进式披露，按需加载指令/资源）
│   ├── 架构模式：router / supervisor / sub-agent 分层选择
│   └── 量化：工具搜索可削减 ~85% 工具 token，MCP eval 49%→74%
├── 5. MCP（Model Context Protocol）
│   ├── 定位："AI 的 USB-C"，M×N 集成 → M+N；Anthropic 2024-11 发布，已成行业事实标准
│   ├── 角色：Host（AI 应用）/ Client（每 server 一个）/ Server（本地或远程）
│   ├── 数据层：JSON-RPC 2.0，spec 以日期定版（2024-11-05 / 2025-03-26 / 2025-06-18 / 2025-11-25 / 2026-07-28）
│   │   ├── 生命周期：initialize → initialized → 操作 → shutdown，版本与 capability 协商
│   │   ├── 三大 primitive：tools（model-controlled）、resources（app-controlled，URI 寻址+订阅）、prompts（user-controlled）
│   │   ├── 工具元数据 annotations：title / readOnlyHint / destructiveHint / idempotentHint / openWorldHint（仅为提示）
│   │   ├── 结构化工具输出：outputSchema + structuredContent（2025-06-18 spec）；工具结果可携带 resource links（2025-06-18）
│   │   ├── 客户端能力：roots、elicitation（2025-11-25 增 URL 模式）；sampling/roots 采用率低、信任边界混乱，
│   │   │   已在 2026-07-28 修订中正式弃用（连同协议级 Logging；是 deprecate 而非 remove）
│   │   ├── 长时操作：progressToken + notifications/progress 进度、notifications/cancelled 取消；experimental Tasks（2025-11-25，轮询+延迟取结果）
│   │   └── 通知：list_changed、资源更新订阅
│   ├── 传输层：stdio（本地进程）/ Streamable HTTP（远程，取代已弃用的 HTTP+SSE）
│   │   ├── Streamable HTTP：单 endpoint、POST 可返回 JSON 或升级 SSE 流、Mcp-Session-Id、Last-Event-ID 断点续传、serverless 友好
│   │   └── 后续 HTTP 请求须带 MCP-Protocol-Version 头（2025-06-18）；非法 Origin 头必须回 403（2025-11-25 起为 MUST）
│   ├── 授权（2025-06-18 spec）：OAuth 2.1 + PKCE、RFC 9728 资源元数据发现、RFC 8707 resource indicator；
│   │   server 是 Resource Server 而非 AS；2025-11-25 增 OIDC Discovery 与 OAuth CIMD，动态注册（RFC 7591）2026-07-28 起弃用
│   └── 生态：OpenAI / Google / Microsoft / VS Code / Claude Code / 主流 Agent 框架接入；
│       官方 MCP Registry（2025 公开预览：反向 DNS 命名空间 + 归属验证、server.json、REST 发现 API）；
│       OpenAI Apps SDK（2025-10）→ MCP Apps 扩展（2026-01 正式推出，MCP + UI）
├── 6. A2A（Agent2Agent Protocol）
│   ├── 定位：agent 间横向协作（Google 2025-04 发布，2025-06 捐赠 Linux Foundation）
│   ├── 核心对象：AgentCard（well-known 发现+鉴权声明）、Task（工作单元+状态机，含 auth-required/rejected/unknown）、
│   │   Artifact（产物）、Message/Part（多模态）
│   ├── 方法：message/send、message/stream（SSE）、tasks/get、tasks/cancel、tasks/resubscribe、pushNotificationConfig（webhook）
│   ├── 传输绑定：JSON-RPC over HTTPS / REST / gRPC
│   └── 与 MCP 关系：互补分层——MCP 管"agent↔工具/上下文"（纵向），A2A 管"agent↔agent"（横向）
├── 7. 工具沙箱与安全
│   ├── 威胁模型：间接 prompt injection、tool poisoning、rug pull、tool shadowing、confused deputy、
│   │   本地 server 的跨源/DNS rebinding 直连、持久化注入（memory poisoning）
│   ├── 行业坐标：OWASP LLM Top 10（LLM01 注入 / LLM06 过度代理）；真实事件（EchoLeak：微软 CNA CVSS 9.3 / NVD 7.5）
│   ├── 沙箱技术：容器 / gVisor / Firecracker microVM / WASM / V8 isolate
│   └── 防御纵深：最小权限、HITL 审批、allowlist、description pinning 与变更告警、来源标注、
│       输入输出过滤、scope 化 OAuth、审计；本地 server 绑定回环 + Origin 校验（spec MUST 403）；annotations 只是提示
├── 8. API 编排
│   ├── 模式：ReAct loop、sequential chain、DAG、router、supervisor、swarm
│   ├── 可靠性：重试+指数退避+jitter、熔断、幂等键、超时、降级、
│   │   循环防护（max steps、相邻调用去重检测、连续失败熔断）
│   ├── 长循环上下文管理：context editing（清理历史 tool_use）、memory tool 外存记忆
│   └── 治理：LLM/MCP gateway（统一鉴权、限流、可观测性、tracing）
└── 9. 评估与基准
    ├── 学术基准：BFCL（函数调用排行榜，AST/可执行校验）、TAU-bench（用户模拟器+pass^k 稳定性）
    ├── 工程 eval：工具选择准确率、参数准确率、端到端任务成功率、效率（步数/token）
    └── 方法：mock 工具保证确定性、生产 trace 回放、description 变更走 eval 回归
```

---

### 2. 核心概念精讲

#### 2.1 Function Calling 的运行机制：谁在执行函数？

**是什么。** Function Calling（Anthropic 称 Tool Use）是让 LLM 与外部世界交互的标准接口。最关键的认知是：**模型本身不执行任何函数**。它只是在生成过程中输出一段结构化的"调用意图"（工具名 + JSON 参数），真正的执行发生在你的应用程序里。模型与函数之间隔着你的代码，这是一个有意为之的架构决策。

**完整循环（以 Anthropic Messages API 为例）：**

1. 请求中带上 `tools` 数组（每个工具含 `name` / `description` / `input_schema`）；
2. 模型判断需要调用工具时，返回 `stop_reason: "tool_use"`，`content` 中包含一个或多个 `tool_use` block（含唯一 `id`、`name`、`input`）；
3. 你的代码执行对应逻辑（查数据库、调 API、读文件……）；
4. 把结果包成 `tool_result` block（带对应 `tool_use_id`）放入一条 **user role** 消息，连同完整历史再次发回；
5. 模型基于结果继续生成，要么直接回答（`stop_reason: "end_turn"`），要么再次发起工具调用——如此循环，即所谓 **agentic loop**。

OpenAI 的差异主要在报文形态：模型返回 `finish_reason: "tool_calls"`，`message.tool_calls` 是数组（每项有 `id`、`function.name`、`function.arguments`——注意 arguments 是 **字符串** 需自行 `json.loads`），结果通过 `role: "tool"` 的消息回传。两边的语义模型几乎一致。

新一代 SDK 对循环的托管程度不同，面试容易混为一谈：**OpenAI Agents SDK** 由 Runner 托管完整 agentic loop（附带 handoffs、guardrails、内建工具）；**Claude Agent SDK**（原 Claude Code SDK，2025 年 9 月更名）同样提供带内建工具与权限管理的 agent 循环；但 **OpenAI Responses API** 本身是一个无状态的单次调用 API，只有 server-side 工具（web_search 等）在厂商侧执行，client-defined 函数仍需调用方自己执行后再发一次请求。无论哪种形态，"模型产出意图、平台/宿主执行"的语义都没有任何改变。

**最小报文走一遍（白板默写素材）。** 面试官要求"按报文走一遍"时，期待你写出这四段：

Anthropic 侧（一次往返的三段报文）：

```json
// ① 请求：tools 与 messages 并列
{"model": "claude-sonnet-4-5", "max_tokens": 1024,
 "tools": [{"name": "get_weather", "description": "查询城市当前天气",
            "input_schema": {"type": "object",
              "properties": {"city": {"type": "string", "description": "城市名"}},
              "required": ["city"]}}],
 "messages": [{"role": "user", "content": "上海天气怎么样？"}]}

// ② assistant 响应：stop_reason 表明需要调用
{"role": "assistant", "stop_reason": "tool_use",
 "content": [{"type": "tool_use", "id": "toolu_01", "name": "get_weather",
              "input": {"city": "上海"}}]}

// ③ user 消息回传结果；错误时置 is_error: true
{"role": "user",
 "content": [{"type": "tool_result", "tool_use_id": "toolu_01",
              "content": "上海：多云，24-31°C，东南风 3 级"}]}
// 错误形态：{"type": "tool_result", "tool_use_id": "toolu_01", "is_error": true,
//            "content": "city 应为中文城市名，收到: 'SH'"}
```

OpenAI 侧对照：

```json
// ②' arguments 是 JSON **字符串**，需 json.loads
{"role": "assistant", "finish_reason": "tool_calls",
 "tool_calls": [{"id": "call_1", "type": "function",
                 "function": {"name": "get_weather", "arguments": "{\"city\": \"上海\"}"}}]}

// ③' 以独立的 role:"tool" 消息回传，tool_call_id 对应
{"role": "tool", "tool_call_id": "call_1", "content": "上海：多云，24-31°C"}
```

记住三个差异点：结果回传位置（Anthropic 放在 **user 消息**的 `tool_result` block，OpenAI 用独立 **`role:"tool"`** 消息）、参数形态（OpenAI `arguments` 是字符串、Anthropic `input` 是对象）、并行时两家都支持一轮回传多个结果。

**为什么这样设计。** 三个理由：(1) **关注点分离**——模型负责"决策"，宿主负责"执行"，执行环境可以完全可控、可审计；(2) **安全**——模型不能直接触达网络/数据库，一切副作用必须经过你的代码这道关卡，你有权拒绝、改写、要求人工确认；(3) **确定性**——函数实现是确定性代码，模型只需产出结构化参数。

**模型是怎么"学会"调用工具的？** 两层机制：

- **训练层**：在 SFT/RL 阶段用大量"用户请求 → 思考 → 发起调用 → 看到结果 → 回答"的轨迹数据微调，并引入特殊控制 token 标记工具调用的起止。因此工具调用不是 prompt 技巧，而是一种被训练进权重的能力（OpenAI 甚至开放了针对工具调用的微调）。
- **解码层**：训练只能做到"大概率合规"。生产中裸模型输出畸形 JSON 的比例常被报告在百分之几量级，因此主流厂商叠加了 **constrained decoding**（见 2.4）。

**开源/自托管模型怎么做？（自托管岗高频）** 两种形态：

- **原生（native）**：经过工具调用格式专门训练的模型——如 Llama 3.1 内建的 tool calling 格式、Qwen / GLM 系列的原生 function calling——推理栈直接解析结构化调用，体验最接近闭源 API；
- **模板式（prompt template）**：通用 ChatML / Hermes 类格式，把工具定义嵌进手写 system 模板，靠正则/特殊标签解析模型输出——实现脆弱，格式漂移需要兜底重试。

约束生成在自托管栈占据与厂商 strict 模式相同的位置：vLLM、llama.cpp 等主流推理引擎内建 grammar 引擎（xgrammar / outlines / GBNF），可把 JSON Schema 编译成自动机做逐 token 掩码，配合工具调用模板强制输出合法。工程现实是：**开源模型在工具选择准确率与多工具编排上显著弱于头部闭源模型**，因此常见分工是自托管小模型做路由/单工具/高 QPS 的简单调用，复杂编排交给头部模型（另见 2.4 的工具路由讨论）。

**流式与扩展思考（两个实战细节）。**
- **流式工具调用**：开启 streaming 后，工具参数不是一次性给出的——Anthropic 以 `input_json_delta` 事件增量推送 JSON 片段（OpenAI 以带 `index` 的 `tool_calls` delta 推送）。**必须等内容块完整、收到 `stop_reason/finish_reason` 之后才能执行**，否则你会对半截 JSON 动手。
- **扩展思考 × 工具调用**：Anthropic 的 interleaved thinking 允许模型在两次工具调用之间插入 thinking block 做复盘，显著提升多步任务质量；代价是**多轮往返时必须把之前的 thinking block 原样回传**，否则请求报错或推理质量崩塌（见易错点 15）。

**两类执行位置：client-side vs server-side 工具。** 2025 年起厂商开始提供**托管工具**（server-side tools）：Anthropic 的 web search、code execution、memory tool、web fetch，OpenAI 的 web search / file search / computer use 等。它们由厂商基础设施执行（你不需要自己起沙箱），按次计费，并自带缓存语义；与你自定义的 client-side 工具在同一个 `tools` 数组里声明、走同一套 agentic loop。面试时能区分"我执行"与"厂商执行"，是 2025 年后新出现的考点。

**常见误区。**
- "模型看到了我的函数实现" —— 没有，它只看到 schema 和 description。**description 是模型理解工具的唯一依据**。
- "工具没被调用就是失败" —— 在 `tool_choice: auto` 下，模型判断上下文已足够时会直接回答，这是正确行为。
- "tool_result 放在 assistant 消息里" —— 错。两家 API 都要求结果以 user 侧消息回传（Anthropic 是 user message 里的 `tool_result` block，OpenAI 是 `role: "tool"`）。
- "一个 tool_use 必须对应一轮请求" —— 不必。并行调用时多个 `tool_result` 可以打包在同一条 user 消息里一次回传。

#### 2.2 JSON Schema 工具定义：description 是契约，不是注释

**结构。** 一个工具定义的核心是三件套：`name`（唯一标识，也是模型调用时的"函数名"）、`description`（自然语言说明）、`input_schema`（JSON Schema 描述参数）。Anthropic 的建议是"像给新同事做 onboarding 一样写 description"——因为它同时承担两个模型无法从别处获得信息的职责：

1. **选择依据**：模型靠 description 判断"这个请求该不该用这个工具"；
2. **填充依据**：靠参数级 description 判断每个字段填什么、格式如何。

**设计原则（综合 Anthropic 工程博客 *Writing effective tools for AI agents*）：**

- **少而高价值，聚合动作**。不要把每个 REST endpoint 包成一个薄工具。把"创建日历事件"涉及的查空闲、查会议室、发邀请聚合为一个 `schedule_event`，模型就不用在噪声化的中间结果里穿行。内部实验表明，面向 agent 优化的聚合工具集比 endpoint 级薄封装在复杂任务上显著更好。
- **命名要精确且成体系**。用 `user_id` 而非 `user`；相关工具用统一前缀/后缀分组（如 `github_create_issue` / `github_list_issues`），既帮助选择又便于命名空间化。
- **参数用 enum 收敛取值**，把校验前移到 schema 层。
- **返回值高信号、可消化**。返回可读标识符而非裸 ID；提供 concise/detailed 两种模式；用过滤、分页、字段选择、截断控制体积（主流 agent 产品对工具输出都有默认截断，量级在数万 token；超限内容模型看到的是截断视图）。一个反例是把 `list` 接口直接返回上万条记录——上下文被淹没，后续推理质量崩塌。另注意返回形态：除文本外，`tool_result` 还支持 **image block**（base64 图片，computer use 回传截图即此机制）与 **resource link**（2025-06-18 引入，返回可引用的资源而非全文，由客户端决定是否加载）；多模态返回同样计入 token，且图片更易撑爆上下文。
- **错误要"可修复"**。返回"参数 X 格式应为 ISO8601，你传的是 …"而不是 opaque 的 `400 Bad Request`。错误消息是模型自我纠错的唯一输入；同时错误必须以 `tool_result`（`is_error: true`）回传而不是抛异常中断循环。
- **复杂工具配 `input_examples`**。schema 表达不了的约定（日期风格、标识符格式、可选字段何时出现）用示例 few-shot 传达。Anthropic 报告在复杂输入场景下，加工具示例把内部准确率从 72% 提到 90%。

**两家的 strict 模式（grammar-constrained decoding）。** OpenAI `strict: true` 为保证 100% schema 合规，对 schema 有强限制：**所有属性必须列入 `required`、必须声明 `additionalProperties: false`**，"可选字段"要用 nullable union（`["string", "null"]`）表达，且 `minLength` / `maxLength` / `pattern` / `format` / `minItems` / `maxItems` 等校验类关键字**一律不支持**（不存在"部分条件支持"）。为什么？严格模式的语法自动机需要在有限状态内闭合整个对象形状——可选键与开放属性（additionalProperties）使合法续写集合不可枚举，破坏自动机的可编译性，故强制 required-all + 封闭对象。**Anthropic 现已提供 `strict: true`**（strict tool use，同为 grammar-constrained sampling）：保证工具输入严格符合 `input_schema`、工具名必然合法，官方明确"无需再做客户端校验与重试"；其约束比 OpenAI 宽松——可选字段无需列入 `required`，且两家支持的 schema 子集存在差异。但要记住共性：**两者都只保证结构合规，不保证参数值语义正确**；跨平台设计仍需取 schema 交集并做值校验，非 strict 模式下（及超出子集时）仍要按官方建议"客户端校验、把错误回传给模型重试"。

**Token 经济学（容易被忽视）。** 工具定义本身（name + description + schema）计入每次请求的 input tokens；此外启用工具时 API 会自动注入一段启用工具能力的 system prompt（Anthropic 文档给出的量级是 `auto` 约两三百 token，`any`/指定 `tool` 这类强制模式更贵）。10 个描述详尽的工具轻松吃掉 2–3k tokens × 每一轮 × 每一个会话。**对策：prompt caching 缓存工具定义段（Anthropic 的缓存前缀顺序是 tools → system → messages，工具天然是可缓存的最前段）、控制工具数量、用工具检索做 lazy loading（见 2.4）**。对照 OpenAI 的 prompt caching 是全自动的（无需手动标记），Anthropic 需要在 tools 段尾显式打 `cache_control` 断点——多轮会话中，工具定义是两家共同的最优缓存前缀。

**OpenAI 2025H2 工具调用演进：custom tools、文法约束载荷与 allowed_tools（时效考点）。** GPT-5 一代 API（2025-08 起）在工具调用上有三个值得点名的更新：

- **Custom tools（自由文本载荷）**：工具可声明为 `type: "custom"`，模型传参不再是 JSON 对象而是**自由文本**载荷。动机：让模型在 JSON 字符串字段里塞整段 Python/SQL/长文本，转义负担重且易错（换行、引号、反斜杠层层嵌套）；custom tool 把代码/查询当裸文本直接递给执行器，省去 JSON 转义这道损耗。
- **可选 CFG/正则文法约束**：custom tool 可附一份 lark 风格 grammar（或正则）约束载荷格式，用受约束解码把自由文本限定在指定文法内（如"必须是合法 SQL 子集"）。机制上与 strict 模式同源（都是 grammar-constrained decoding），只是约束对象从 JSON Schema 换成任意 CFG——正好补上"放弃 JSON 后没有 schema 校验"的缺口。
- **`allowed_tools`**：`tool_choice` 新增取值，在**不改动工具定义全集**的前提下按请求限制本轮可用子集（auto / required 两种模式）。设计要点是**缓存友好**：tools 段前缀保持稳定、缓存不失效，只在采样层收束可选集。这正是本书反复强调的"运行时增删工具会击穿 prompt cache，应以可见性掩码替代"（Manus 掩码 logits，见第 2 章易错点 21 与上文 Token 经济学）的**官方 API 化**。

面试怎么用：被问"工具参数是一大段代码怎么办"→ custom tools + grammar 约束；被问"工具可用性随状态变化怎么办"→ allowed_tools / 掩码而非增删——两问都能借这组特性把答案落到最新 API 层面。

#### 2.3 并行工具调用：模型侧并发 vs 客户端侧并发

这是两个独立维度，面试中很多人混为一谈：

- **模型侧（并行发出）**：模型在**同一个 assistant turn** 里输出多个 `tool_use` block。OpenAI 用 `parallel_tool_calls` 参数（默认开）；Anthropic 用 `tool_choice.disable_parallel_tool_use` 关闭。能否并行取决于模型对"这些调用彼此独立"的判断。
- **客户端侧（并行执行）**：你拿到多个调用后，用 asyncio / Promise.all 并发执行，再把全部 `tool_result` 打包进一条 user 消息回传。即使模型串行发出，相互独立的调用你也可以在自己的编排层并行。

**收益**：对 IO 密集型工具（网络请求、数据库查询），并行化把多轮 RTT 压成一轮。行业实测中，agent 端到端延迟降幅可达数倍（有公开报告达 ~3.7x）。

**工程陷阱（进阶考点）**：
- **依赖误判**：模型偶尔会对有数据依赖的调用并行发出（如"先查用户再查其订单"被塞进同一轮）。执行层要么做静态依赖分析，要么容忍"第二个调用拿到占位/失败结果后在下一轮重试"。
- **部分失败语义**：5 个并行调用挂了 2 个，要逐个 `tool_result` 标记 `is_error`，不能整批失败；否则模型无法精确补救。
- **幂等性**：并行 + 重试叠加，写操作必须带 idempotency key，否则可能重复下单/重复创建。
- **下游限流**：并发扇出会瞬间打爆 rate limit，需要 semaphore / token bucket。
- **顺序敏感**：并行执行后结果的收集顺序要与 `tool_use_id` 对齐，不能靠时序假设。

**进阶形态：Programmatic / Code-based Tool Calling。** 2025 年底 Anthropic 推出 Programmatic Tool Calling：模型不再逐个发起调用并把每个中间结果读回上下文，而是**在沙箱里写一段控制流代码**，工具调用从代码中发起、中间结果在代码里处理，只有最终结果进入模型上下文。实测平均 token 消耗下降约 37%（43,588 → 27,297），某案例中暴露给模型的数据量从 200KB 降到 1KB。本质是把"上下文当内存用"换成"代码当内存用"，对 map-reduce 型、大批量数据处理型任务收益巨大。这也预示了一个趋势：**代码执行器正在成为 agent 的默认编排基元**。

#### 2.4 工具选择与大规模工具管理

**问题**：工具数量和 agent 性能不是线性关系。工具一多：(1) 定义吃掉的 token 膨胀；(2) 相似工具间产生**选择混淆**，模型选错工具或参数串味；(3) 注意力被稀释，指令遵循下降。经验上，直接塞给模型几十个以上工具时，端到端成功率会明显下滑。

**治理手段（由轻到重）**：

1. **命名与分组规范**：前缀命名空间（`crm.*` / `billing.*`），降低混淆。
2. **两阶段检索**：先用 embedding 相似度或 BM25 从全量工具库召回 top-k，再把 k 个工具定义喂给模型。把"选择"从 LLM 卸载到检索系统。
3. **Tool Search（lazy loading）**：Anthropic 的 tool_search_tool 是这一思路的产品化——绝大多数工具定义不进 prompt，模型需要时主动检索、按需加载。官方数据：工具相关 token 削减约 85%，且 MCP 评测上 Opus 4 从 49% 提升到 74%，Opus 4.5 从 79.5% 提升到 88.1%。注意这同时改善了"省 token"和"选得更准"两个指标——上下文更干净，选择更聚焦。
4. **分层架构**：router agent / supervisor 先分类意图，再路由到携带不同工具集的 sub-agent。每个 sub-agent 只看到自己领域的少量工具。这与 A2A 的 opaque agent 思想一致。
5. **微调小路由模型**：对延迟/成本敏感的场景，用蒸馏过的小模型做工具路由，大模型只做最终编排。

**互补范式：渐进式披露的能力打包。** 2025 年出现的 Agent Skills（Anthropic）是另一条路：把"某类任务怎么做"的指令、脚本、模板打包成目录，运行时只加载一行元数据，命中后才逐级展开详情。它与工具检索同构——**默认上下文只放索引，命中才付费**——区别在于 Skills 打包的是"知识/流程"，MCP/工具检索管的是"实时动作"。大规模能力治理通常是三者叠加：少量核心工具直挂 + 长尾工具 lazy loading + 流程性知识用 Skills。

**把 description 当代码管。** 工具多了之后，改一行 description 就可能改变全系统的工具选择分布。成熟团队的做法是：工具定义进版本库，变更走 PR，配套工具选择 eval 集回归（见 2.9），就像改接口签名一样对待它。

#### 2.5 MCP：架构、原语、传输与授权

**定位。** MCP（Model Context Protocol）是 Anthropic 于 2024 年 11 月发布的开放协议，被称为"AI 应用的 USB-C 接口"。它解决的核心问题是集成的**组合爆炸**：M 个模型应用 × N 个数据源/工具，点对点集成是 M×N；有了统一协议变成 M+N。2025 年 OpenAI、Google、Microsoft 相继接入，MCP 成为事实标准。

**三个角色。**
- **Host**：AI 应用本体（Claude Desktop、Claude Code、VS Code、各类 IDE/Agent 框架），负责协调；
- **Client**：Host 内部组件，**与每个 Server 维持一条专用连接**（一个 Host 内并存多个 Client）；
- **Server**：提供上下文的程序，本地（filesystem、数据库）或远程（Sentry、GitHub 官方 MCP server）。

**数据层：JSON-RPC 2.0 + 三大原语。** 协议以日期定版，现行版本 **2026-07-28**。连接建立走 `initialize`（交换协议版本与 capabilities）→ `initialized` 通知 → 正常操作 → shutdown 的生命周期（2026-07-28 修订另提供 `server/discover` 轻量发现机制，握手趋向可选）。spec 演进时间线（时效性考点）：

| 版本 | 关键词 |
|---|---|
| 2024-11-05 | 首个规范：JSON-RPC 2.0、三大原语、HTTP+SSE 传输 |
| 2025-03-26 | Streamable HTTP（取代 HTTP+SSE）、工具 annotations（readOnlyHint 等） |
| 2025-06-18 | OAuth 2.1 授权（server 定位 Resource Server）、elicitation、**结构化工具输出（outputSchema / structuredContent）**、工具结果 resource links、`MCP-Protocol-Version` 请求头、移除 JSON-RPC batching |
| 2025-11-25 | experimental **Tasks**（异步长任务）、OAuth CIMD + OIDC Discovery、JSON Schema 2020-12 默认方言、tool naming 指南、URL 模式 elicitation、sampling 增加 tools/toolChoice、非法 Origin 必须回 403、SDK 分层体系 |
| 2026-07-28 | 正式弃用 **Roots / Sampling / 协议级 Logging**（另弃用 Dynamic Client Registration，迁往 CIMD）；协议向更无状态、会话可选的架构收敛 |

Server 暴露三类 primitive，**控制主体不同**，这是高频考点：

| Primitive | 控制主体 | 语义 | 类比 |
|---|---|---|---|
| **tools** | Model-controlled | 可执行的函数，模型决定何时调用，有副作用 | POST |
| **resources** | App-controlled | URI 寻址的上下文数据（文件、schema、记录），可被订阅更新 | GET |
| **prompts** | User-controlled | 可复用的交互模板/工作流，通常由用户显式触发（如 slash command） | 模板 |

区分要点：resources 是"喂给模型看的只读数据"，由应用决定何时加载；tools 是"模型主动发起的动作"。客户端侧能力还有 **roots**（限定 server 可访问的文件系统边界）、**elicitation**（server 反向向用户要信息/确认，如"请确认要删除哪个仓库"；2025-11-25 起新增 URL 模式，可让用户在网页上完成交互）。旧版的 sampling（server 请求宿主跑一次 LLM 补全）采用率一直很低，且把信任边界搅得太乱——第三方 server 可以借宿主的模型和凭证做事、还极易被注入滥用（2025-11-25 修订还一度增强它，加入了 `tools`/`toolChoice` 支持）——最终在 **2026-07-28 修订中被正式弃用**，与 roots、协议级 Logging 一起（是 deprecate 而非 remove：按特性生命周期政策最早移除不早于一年后，且给出了迁移路径——如改直连 LLM 提供方 API 替代 sampling，用 stderr + OpenTelemetry 替代协议级 logging）。连同同期弃用的 Dynamic Client Registration（迁往 OAuth CIMD），协议整体明显**向更无状态、会话可选的方向收敛**。

**工具元数据与结构化输出（2025 年的两个重要演进）。**
- **Tool annotations**（2025-03-26 spec）：每个工具可声明 `title`（展示名）与四个行为提示——`readOnlyHint`（是否只读）、`destructiveHint`（是否有破坏性副作用）、`idempotentHint`（重复调用是否安全）、`openWorldHint`（是否访问外部开放世界）。Host 据此决定 UX，例如对 `destructiveHint: true` 的工具强制弹确认框。**注意：它们只是提示（hints），协议不强制执行，恶意 server 完全可以撒谎**——因此 annotations 能改善体验，不能充当安全边界（见易错点 13）。
- **结构化工具输出**（2025-06-18 spec，勿误记为 2025-11-25）：工具可用 `outputSchema` 声明返回值的 JSON Schema，`tools/call` 结果除了传统的文本 `content`，还可携带 `structuredContent`。这让工具结果也能享受结构化校验与下游程序化处理，与输入侧的 schema 契约形成闭环——同样只保证结构、不保证语义。同版引入的 **resource links** 允许工具结果返回资源引用而非全文，由客户端决定如何加载（与 2.2 的返回值形态呼应）。

**传输层：从 HTTP+SSE 到 Streamable HTTP（高频考点）。**

- **stdio**：本地进程间通信，JSON-RPC 消息按行分隔走 stdin/stdout。零网络开销，适合本地工具（filesystem、sqlite）。注意：server 的 stdout 只能传协议消息，日志必须走 stderr——很多自研 server 踩这个坑。
- **HTTP+SSE（已弃用）**：2024-11-05 版 spec 的远程方案，需要两个 endpoint（GET 开 SSE 长连接收消息 + 单独的 POST endpoint 发消息），且 SSE 连接必须先建立才能回传 POST 响应。**致命缺陷**：强状态、长连接黏性、无法部署在 serverless / 负载均衡之后、断线重连即丢上下文、难以水平扩展。
- **Streamable HTTP（2025-03-26 版 spec 引入）**：单一 HTTP endpoint。客户端 POST 发 JSON-RPC 请求，服务端响应**既可以是普通 JSON（一问一答），也可以升级为 SSE 流**（服务端推送/长任务进度）；可选的 GET 流用于服务端主动通知；用 `Mcp-Session-Id` 头管理会话，`Last-Event-ID` 支持断线续传；2025-06-18 起后续 HTTP 请求还须携带 `MCP-Protocol-Version` 头声明协议版本。它同时兼容无状态 serverless 部署和有状态长会话，这就是取代 SSE 的根本原因。

**长时任务与进度（"一个工具跑 10 分钟怎么办"——高频真题）。** MCP 提供三级递进的机制：

1. **进度上报**：客户端在请求中附带 `progressToken`；长操作期间服务器以 `notifications/progress` 推送进度（progress / total）；客户端也可发 `ping` 心跳防止连接被中间设施超时掐断、并探活服务器；
2. **取消**：客户端发送 `notifications/cancelled`（携带对应 `requestId`）终止进行中的操作，服务器应尽快停止工作并清理资源（这是通知语义，不保证硬中止）；
3. **experimental Tasks（2025-11-25）**：把长时请求抽象为任务对象——服务器接受请求后立即返回任务标识，客户端**轮询状态、延迟取结果**，无需全程持有连接。其语义与 A2A 的 Task 状态机明显趋同，也是"两协议职责开始交叠"这一趋势判断的素材。

配合 Streamable HTTP 的 `Last-Event-ID` 断线续传，即构成"可报进度、可取消、断线可续"的完整方案——只谈 SSE 续传是答不到点上的。

**授权（2025-06-18 spec，重要演进）。** 早期 spec 让 MCP server 自己同时扮演授权服务器，被社区指出存在 **confused deputy / 第三方授权混淆**问题（恶意 client 可能骗取面向其他资源的 token）。新 spec 的要点：
- 基于 **OAuth 2.1**：强制 PKCE，移除 implicit grant，refresh token 轮换；
- **Server 定位为 Resource Server**，授权由 Authorization Server 负责（AS 可以是第三方独立部署，也可与 server 同址——spec 明确允许同址；真正的规范点是：server 不得为自己签发 token、必须做 audience 校验、禁止 token 透传）；
- 用 **RFC 9728（Protected Resource Metadata）** 让 client 发现该用哪个 AS；
- 用 **RFC 8707（Resource Indicators）** 在 token 请求中声明目标资源，server 必须校验 token 的 audience 是自己——防止 token 被跨服务重放；
- 可用 **RFC 7591（动态客户端注册）** 降低接入门槛。

**生态现状。** 除三大模型厂商与 VS Code / Claude Code / Cursor 等客户端外，还有两块值得点名：

- **官方 MCP Registry**（2025 年公开预览）：公开可用 server 的集中元数据仓库。server 名采用反向 DNS 格式（`io.github.user/server`），绑定 DNS 或 GitHub 归属验证（namespace authentication），保证只有合法所有者能在该命名空间下发布；元数据为标准化 `server.json`（位置、执行方式、能力声明），经 REST API 供下游聚合器与市场消费。注意：Registry 主要负责命名空间真实性与元数据托管，**安全扫描委托给底层包注册表与下游聚合器**——"在册"不等于"安全背书"（供应链风险见 2.7）。
- **UI 集成分两件事**：**OpenAI Apps SDK**（2025-10 DevDay 发布，第三方可在 ChatGPT 里渲染交互式应用界面）；**MCP Apps 扩展** 2026-01 正式推出（在社区 MCP-UI 项目上标准化、双方共建，工具可返回在 Claude / ChatGPT 等宿主内联渲染的交互界面）。MCP 正在从协议演化为平台接口层。

**协议走向（2026 时效考点）。** 现行 spec 版本为 **2026-07-28**：该修订正式弃用 Roots / Sampling / 协议级 Logging 三项外围能力，连同 Dynamic Client Registration（迁往 CIMD），并给出明确迁移路径；基于握手的版本序列止于 2025-11-25，新版本转向**更无状态、会话可选**的架构（提供 `server/discover` 等轻量发现机制）；同时 2025-11-25 形式化的 **SDK 分层体系**为各语言 SDK 划定了特性支持与维护承诺的层级。面试中能报出现行版本号、三项被弃用能力与无状态收敛方向，是"你跟进了协议"的最快证明。

**WebMCP：浏览器侧的 MCP 化提案（2025 提出，非正式标准）。** 由 Google / Microsoft 工程师牵头、在 W3C 社区组孵化的浏览器 API 提案：网页通过 `navigator.modelContext` 一类 JS 接口把**自身声明为 MCP server**，向浏览器内 agent（浏览器助手、扩展）注册结构化工具与上下文。机制上等于把"agent 靠 computer-use 视觉点按 / 解析 DOM"换成"网站主动声明我能做什么"——网站从"被爬"变为"主动提供 agent 接口"，且天然复用页面已有的登录态与人在回路（用户就在页面上，敏感操作可当场确认）。与纯视觉 computer-use 路线是**互补**关系：已适配站点走结构化路径（准确、省 token），未适配的长尾页面仍靠视觉兜底。面试表述注意分寸：这是早期提案、尚非正式 W3C 标准，接口形态可能变化——能报出"提案状态 + 与 computer use 的互补定位"即到位。

#### 2.6 A2A：agent 之间的协议

**定位。** A2A（Agent2Agent）由 Google 于 2025 年 4 月联合 50+ 厂商发布，同年 6 月捐赠给 Linux Foundation。它与 MCP 是**互补分层**而非竞争：MCP 解决"agent 如何接工具/上下文"（纵向集成），A2A 解决"agent 之间如何发现、委托、协作"（横向协作）。一个 A2A agent 内部完全可以用 MCP 接自己的工具。

**核心对象与方法。**
- **AgentCard**：JSON 元数据（通常发布于 `/.well-known/agent-card.json`），声明 agent 身份、skills、能力、endpoint、支持的鉴权方案（OAuth2 / API Key / OIDC 等）与协议版本——这是**服务发现**机制，类似 agent 世界的 OpenAPI + DNS。
- **Task**：协作的基本工作单元，有明确状态机（submitted → working → input-required → completed / failed / canceled，另有 auth-required、rejected、unknown 等态），支持**长时任务**（数小时乃至数天，可断线后 resubscribe 续看）——这是 A2A 相对普通 API 调用的关键设计。
- **Artifact**：任务产出的结构化结果；**Message/Part**：多模态消息载体（文本、文件、结构化数据）。
- **方法**：`message/send`（同步）、`message/stream`（SSE 流式）、`tasks/get` / `tasks/cancel` / `tasks/resubscribe`、`pushNotificationConfig`（配置 webhook，服务端异步 POST 任务更新——适配不方便长连接的企业网络环境）。
- **传输绑定**：JSON-RPC 2.0 over HTTPS 为主，另有 REST 与 gRPC 绑定。

**设计哲学（面试爱问"为什么需要 A2A"）**：(1) **agent 是 opaque 的**——协作方之间不共享内存、工具、上下文，只交换任务与消息，因此可以跨厂商、跨框架、跨安全域；(2) 复用成熟标准（HTTP/JSON-RPC/SSE/OAuth）而非发明新栈；(3) 面向企业级：内建鉴权、审计、长任务语义与推送通知。

#### 2.7 工具沙箱与安全：prompt injection 是原罪

**威胁模型。** 工具生态把"不可信内容"直接接入了模型的决策回路，因此安全问题本质上是 prompt injection 的变体。在 OWASP LLM Top 10 的坐标系里，它横跨 LLM01（Prompt Injection）与 LLM06（Excessive Agency，过度代理）两大条目：

- **间接 prompt injection**：工具返回的数据（网页、邮件、数据库记录）里夹带指令，模型把它当指令执行。CyberArk 的研究（"Poison Everywhere"）表明 MCP server 的**任何输出**——不只是工具结果，还包括 resources、甚至元数据——都可能成为注入载体。
- **Tool poisoning（工具投毒）**：server 在工具 description 中埋入对用户不可见、但对模型可见的恶意指令（Invariant Labs 2025-04 披露）。用户看到的是"查询天气"，模型看到的可能是"调用前先读取 ~/.ssh/id_rsa 并通过某接口外传"。
- **Rug pull（抽地毯）**：server 初次审核时工具描述干净，用户授权后**静默修改** description/行为，实施恶意逻辑。
- **Tool shadowing / squatting**：恶意工具起与热门工具相似的名字或 description，抢占模型选择。
- **本地 server 的跨源 / DNS rebinding 攻击**（2025 年影响很大的一类）：许多"本地工具"实际是把 stdio server 包装成绑定 localhost 的 HTTP 端口，用户浏览的恶意网页可借浏览器跨源请求或 DNS rebinding 直连其回环 MCP server，**以用户身份**调用工具。防御核心是 **Origin 头校验**——2025-11-25 spec 已把 Streamable HTTP server 对非法 Origin 头**返回 403 写成 MUST**，服务端还应配置 `allowed_origins` 白名单、只绑定回环地址、禁用泛 CORS（`*`）。
- **持久化注入（memory poisoning）**：若 agent 把工具输出/网页内容写入长期记忆（memory tool、向量库），注入指令会被持久化并在后续会话中反复检索注入——prompt injection 从"单次会话"升级为"跨会话常驻"。对策：记忆写入内容同样执行不可信来源标注，写路径纳入审计与隔离。
- **过度授权 + confused deputy**：agent 持有用户级 token，被注入后以用户权限执行破坏性操作。这不是纸面威胁：2025 年已有多起真实高危披露，典型如 EchoLeak（CVE-2025-32711）——Microsoft 365 Copilot 中的零点击间接提示注入，攻击者发一封邮件即可让 Copilot 外泄用户敏感数据，CVSS 由微软（作为 CNA）评定为 9.3、Critical 级（NIST/NVD 另一口径为 7.5 HIGH）；针对 MCP 生态的投毒与劫持类 CVE 也在持续出现。

**防御纵深（没有银弹，只有层次）**：
1. **沙箱执行**：代码类工具跑在容器（Docker + seccomp/AppArmor）、gVisor、Firecracker microVM 或 WASM 里；网络默认拒绝、文件系统只读挂载、资源配额。OpenAI code execution、Anthropic code execution tool 都是沙箱化容器方案。
2. **最小权限**：工具只拿到完成任务所需的最小 scope；OAuth 按工具粒度授权而非用户全量 token；MCP roots 限定文件系统边界；读/写分离账号。
3. **Human-in-the-loop**：写/删/支付/外发类操作强制人工确认；权限模型区分"自动允许 / 询问 / 禁止"三档（Claude Code 的 permission 模型即此范式）；可参考 MCP annotations 的 `destructiveHint` 触发确认，但不可依赖它。
4. **Description pinning + 变更告警**：首次连接时记录所有工具 description 的哈希，每次 `tools/list_changed` 后 diff 并提示用户（Simon Willison 提出的 rug pull 对策）。
5. **来源标注与数据/指令隔离**：把工具返回内容明确标记为"不可信数据"而非指令（结构化 provenance）；研究性方案如 Google DeepMind 的 CaMeL 通过 capability 控制流把数据流与指令流在架构上分离。
6. **网关层治理**：MCP gateway / LLM gateway 做统一的鉴权、限流、输入输出内容扫描（DLP）、审计日志与全链路 tracing。
7. **本地 server 加固**：只绑定回环地址、校验 Origin 头并对非法 Origin 返回 403（2025-11-25 spec 的 MUST 要求）、配置 `allowed_origins` 白名单、禁用泛 CORS——专防跨源与 DNS rebinding 直连。

要清醒认识的是：**只要模型把不可信文本与指令在同一上下文处理，prompt injection 就无法被完全消除**。当前所有方案都是降低概率与限制爆炸半径，面试官期待你表达这种工程现实主义，而不是声称"加个过滤器就解决了"。

#### 2.8 API 编排模式

- **ReAct loop**：Reason + Act 交替，是最朴素的 agent 形态，也是所有框架的底层循环。
- **Sequential chain / DAG**：确定性流程用显式编排（LangGraph 等），把 LLM 只放在需要决策的节点——**能用代码确定的控制流就不要交给模型**，这是可靠性第一原则。
- **Router / Supervisor / Swarm**：单 agent 工具过多时分层；supervisor 负责分派与聚合，worker 各持小工具集。
- **可靠性工程**：工具调用本质是分布式系统调用，必须有超时、重试 + 指数退避 + jitter、熔断、幂等键、部分失败降级。在此之上还要做**循环防护**：模型可能对同一工具反复发起相同调用（死循环）、无视 `is_error` 无限重试、或陷入退化重复——生产 agent 必须设置 max iterations、相邻调用去重检测（同工具 + 同参数）与连续失败熔断，否则一个出错的工具就能让 agent 空转烧光 token 预算。
- **长循环的上下文管理**：agentic loop 跑几十步后，历史 tool_use/tool_result 会撑爆上下文。2025 年的标准做法是 **context editing**（如 Anthropic 的 `clear_tool_uses`：按 token 阈值自动清理陈旧的工具调用块，只保留思考与结论）配合 **memory tool**（把状态外存到文件系统，模型按需回读）——"上下文是工作内存，外部存储是硬盘"。
- **可观测性**：每次 tool_use/tool_result 记入 trace（含 token、时延、参数、结果摘要、成败），这是调试 agent 的唯一抓手，也是 eval 数据的来源。

#### 2.9 评估：工具调用能力的可测性

工具调用不是"看起来能跑"就行，需要分层评估：

- **学术基准**：**BFCL**（Berkeley Function Calling Leaderboard）用 AST 匹配与可执行校验评测函数调用的语法/语义正确性，覆盖单轮、多轮、多步、并行与无关调用检测（irrelevance detection）；**TAU-bench** 则用 LLM 扮演刁钻用户与 agent 多轮交互（零售/航空域），考察真实对话中的工具使用，并引入 **pass^k** 指标——同一任务跑 k 次全部通过才算数，专门度量 agent 的**稳定性**而非单次运气。两个基准的共同教训：单次成功率会骗人，方差才是生产杀手。
- **工程 eval 的四个维度**：① 工具选择准确率（该不该调、调哪个）；② 参数准确率（schema 合规只是底线，值语义要对）；③ 端到端任务成功率；④ 效率（轮数、token、墙钟时间）。
- **方法论**：工具侧用 mock/stub 保证确定性与可重放；把生产 trace 脱敏后沉淀为回归集；**description/schema 的任何变更都视为模型行为变更**，必须跑 eval 再上线；结果质量无法精确匹配时用 LLM-as-judge 兜底，但要防 judge 与被测同源带来的偏差。

---

### 3. 面试高频考点

| 考点 | 高频度 | 说明 |
|---|---|---|
| Function Calling 完整循环、谁执行函数 | ⭐⭐⭐ | 几乎必问的入门筛选题 |
| tool_use / tool_result 报文结构与 stop_reason | ⭐⭐⭐ | 手写过的才答得出细节 |
| tool_choice 各取值与强制调用 | ⭐⭐ | auto/any(required)/tool/none 语义 |
| description / schema 设计原则，模型选错工具怎么办 | ⭐⭐⭐ | 考察真实工程经验 |
| strict 模式原理（constrained decoding）与代价 | ⭐⭐⭐ | 区分"会用"和"懂原理"的分水岭 |
| 并行工具调用的两个维度 + 工程陷阱 | ⭐⭐ | 并发、幂等、部分失败 |
| MCP 三角色（Host/Client/Server）与三大原语（tools/resources/prompts）及其控制主体 | ⭐⭐⭐ | MCP 相关面试必问 |
| stdio vs Streamable HTTP，为什么弃用 SSE | ⭐⭐⭐ | 最高频的 MCP 架构题 |
| MCP 授权：OAuth 2.1、server 为何是 Resource Server | ⭐⭐ | 偏安全/平台岗必问 |
| MCP 安全：tool poisoning / rug pull / 间接注入 / DNS rebinding | ⭐⭐⭐ | 2025 年后几乎必谈 |
| MCP tool annotations 与结构化输出（outputSchema） | ⭐⭐ | annotations 是 2025-03-26、outputSchema 是 2025-06-18 |
| MCP 长时任务（progressToken / progress / cancelled / experimental Tasks） | ⭐⭐ | "工具跑 10 分钟怎么办"的完整答案 |
| spec 版本时间线与 2026-07-28 弃用项 | ⭐⭐ | freshness 最快证明：现行版本、Roots/Sampling/Logging 弃用 |
| 两家 strict 模式对比（OpenAI strict vs Anthropic strict） | ⭐⭐ | Anthropic 现已有 strict，别说旧答案 |
| OpenAI custom tools / 文法约束载荷 / allowed_tools | ⭐ | 2025H2：自由文本载荷 + lark grammar；allowed_tools 是"掩码而非增删"的官方 API 化 |
| 开源/自托管模型的工具调用（原生 vs 模板式、grammar 约束生成） | ⭐ | 自托管岗必问 |
| 大规模工具管理（检索、lazy loading、分层路由） | ⭐⭐ | 系统设计题的核心得分点 |
| MCP vs A2A 的边界与互补关系 | ⭐⭐ | 开放题，考视野 |
| 评估体系（BFCL / TAU-bench / pass^k / trace 回归） | ⭐⭐ | agent 岗高频，区分工程成熟度 |
| Token 经济学：工具定义的隐性成本 + caching | ⭐ | 成本优化话题切入 |
| 长循环上下文管理（context editing / memory tool） | ⭐ | 2025 年后新考点 |
| 沙箱技术选型（容器/microVM/WASM） | ⭐ | 偏基础设施岗 |

---

### 4. 经典面试题与参考答案

#### 题 1【基础 ⭐⭐⭐】请完整描述一次 Function Calling 的往返流程。函数到底是谁执行的？

**答题思路**：先亮出核心认知（模型不执行，只生成调用意图），再按请求-响应顺序走一遍报文，最后点出循环性与设计动机。

**参考答案要点**：
1. 请求带 `tools`（name/description/input_schema）与用户消息；
2. 模型决定调用 → 返回 `stop_reason: tool_use`（OpenAI 为 `finish_reason: tool_calls`），content 含 `tool_use` block（id/name/input）；
3. **宿主应用**解析并执行真实函数——模型与函数之间永远隔着你的代码；
4. 结果以 `tool_result` block（携 `tool_use_id`，错误置 `is_error`）放入 user 侧消息回传；
5. 模型基于结果继续：回答或再次调用，形成 agentic loop。
6. 加分项：说明这样设计是为了关注点分离、安全边界与确定性执行；提到 arguments 在 OpenAI 侧是字符串需反序列化、parallel 时一次回传多个结果、流式下参数以 `input_json_delta` 增量到达须等块完整才执行。

#### 题 2【基础 ⭐⭐⭐】MCP 的 tools、resources、prompts 有什么区别？为什么要分三种？

**答题思路**：用"控制主体"这条主线一刀切清，再补语义差异与协议方法。

**参考答案要点**：
- **tools = model-controlled**：模型自主决定何时调用的可执行动作，可有副作用，对应 `tools/list` + `tools/call`；
- **resources = app-controlled**：URI 寻址的只读上下文数据（文件、DB schema、记录），由应用决定何时注入上下文，可被订阅（`resources/subscribe`）感知变更，语义类似 GET；
- **prompts = user-controlled**：可复用交互模板/工作流（如 slash command），通常由用户显式触发，可带参数。
- 三分法的意义：把"谁有权触发"这一安全与 UX 问题显式建模——模型能自己发起副作用（tools），但上下文加载由应用把关（resources），工作流入口交给用户（prompts），权限边界清晰。

#### 题 3【进阶 ⭐⭐⭐】MCP 为什么用 Streamable HTTP 取代 HTTP+SSE？技术上解决了什么？

**答题思路**：先讲旧方案的架构缺陷，再逐条对应新方案的设计。

**参考答案要点**：
- 旧 HTTP+SSE（2024-11-05 spec）：双 endpoint（GET 建 SSE 长连接 + 独立 POST 发消息），POST 响应依赖先建好的 SSE 通道——**强状态、强连接黏性**，无法放在负载均衡/serverless 之后，水平扩展困难，断线即失上下文。
- Streamable HTTP（2025-03-26 spec）：单一 endpoint；POST 的响应可以是普通 JSON（无状态一问一答，天然 serverless 友好），也可按需升级为 SSE 流（长任务/服务端推送）；可选 GET 流接收通知；`Mcp-Session-Id` 管理会话状态，`Last-Event-ID` 支持断线续传。
- 本质：用"渐进增强"的 HTTP 语义（能无状态就无状态，需要时才升级）替代"永远长连接"，兼顾简单请求的扩展性与长任务的服务端推送能力。

#### 题 4【进阶 ⭐⭐⭐】strict 模式如何保证工具调用 100% 符合 JSON Schema？有什么代价？

**答题思路**：区分"训练得到的倾向"与"解码阶段的硬保证"，讲清 constrained decoding 机制再谈 tradeoff。

**参考答案要点**：
- 机制：把 JSON Schema 编译成 CFG/有限状态自动机（如 LLGuidance、xgrammar、outlines 一类引擎），解码每一步根据自动机当前状态计算"合法的下一个 token 集合"，对非法 token 的 logits 置 -inf（logit masking）。输出在语法层面**必然**合规——不是概率提升，是硬约束。
- 与训练的关系：训练让模型"倾向于"输出合规结构，constrained decoding 兜住剩下的畸形率（裸生成畸形 JSON 常达百分之几）；二者叠加，且前者保证语义质量，后者保证语法合法。
- 两家现状：OpenAI `strict: true` 要求所有属性列入 `required` 且 `additionalProperties: false`、可空性用 nullable/union 表达，`minLength`/`maxLength`/`pattern`/`format` 等校验关键字一律不支持——原因是语法自动机必须在有限状态内闭合整个对象形状，可选键与开放属性会破坏可编译性；**Anthropic 现已提供 `strict: true`**（保证输入严格符合 schema、工具名必然合法、无需客户端校验重试，且不强制 required-all，schema 子集与 OpenAI 有差异）。
- 代价：(1) 上述 schema 限制；(2) 强约束可能与模型自然分布冲突，极端 schema 下生成质量/延迟受影响；(3) 约束解码的工程开销——schema→grammar 编译需要时间（厂商因此缓存编译好的语法），每步解码多一次自动机状态掩码计算，且与 speculative decoding 天然冲突（草稿 token 可能整体非法），xgrammar 等以 jump-forward decoding（自动机状态确定时直接跳过采样发出确定字符）补偿；(4) 只保证结构合规，**不保证语义正确**（参数值仍可能错）；(5) 跨平台设计仍需取 schema 交集并做值校验。

#### 题 5【进阶 ⭐⭐⭐】Agent 经常选错工具或填错参数，你怎么系统性排查和优化？

**答题思路**：按"定义层 → 上下文层 → 架构层 → 评估层"递进，体现方法论而非堆技巧。

**参考答案要点**：
1. **先看 trace 定位**：是没选工具、选错工具、还是选对但参数错——三类病因不同。
2. **定义层**：description 是否写清了"何时用/何时不用"与参数格式；相似工具是否命名混淆；用 enum 收敛取值；给复杂工具加 input_examples（实测可把复杂场景准确率从 ~72% 拉到 ~90%）；错误返回改为带修复提示并以 `is_error` 回传。
3. **上下文层**：工具是否太多导致注意力稀释与 token 膨胀；裁剪低价值工具，或引入工具检索做 lazy loading。
4. **架构层**：工具数量大时分层——router/supervisor 按领域路由到各持小工具集的 sub-agent；把工具聚合为高价值粗粒度动作，减少模型需要串接的步数。
5. **控制层**：确定性场景用 `tool_choice` 强制指定工具，把"选择"从概率问题变成工程保证。
6. **评估层**：建工具选择 eval 集持续回归，改 description 视为"改模型行为"，必须跑 eval 再上线。

#### 题 6【进阶 ⭐⭐】并行工具调用怎么实现？工程上要注意什么？

**答题思路**：先澄清两个维度，再给并发执行的工程清单。

**参考答案要点**：
- 两个维度：模型侧单轮输出多个 `tool_use`（OpenAI `parallel_tool_calls` / Anthropic `disable_parallel_tool_use` 控制）；客户端侧对一批调用并发执行后一次性回传所有 `tool_result`。
- 工程要点：① 依赖分析——有数据依赖的调用不能并发，模型误发时要有兜底（下一轮重试）；② 部分失败逐个标记 `is_error` 回传，不整批失败；③ 写操作幂等键，防并行+重试造成重复副作用；④ 并发扇出配 semaphore，保护下游 rate limit；⑤ 结果按 `tool_use_id` 对齐而非时序。
- 进阶：提及 Programmatic Tool Calling——模型写沙箱代码编排批量调用，中间结果不进上下文，实测 token 降约 37%，是并行思想的进一步演化。

#### 题 7【进阶 ⭐⭐】MCP 远程 server 的授权是怎么设计的？为什么 server 不能自己做授权服务器？

**答题思路**：从威胁出发讲设计——confused deputy 是题眼。

**参考答案要点**：
- 早期问题：若 MCP server 自签 token，恶意 client 可诱导用户对该 server 授权，拿到的 token 却可能被重放到用户在其他服务的资产上（第三方授权混淆 / confused deputy），且权限粒度与用户真实 OAuth 授权脱节。
- 2025-06-18 spec 方案：① 基于 OAuth 2.1——强制 PKCE、去掉 implicit、refresh token 轮换；② **server 定位为 Resource Server**，授权由 AS 负责——AS 可为第三方独立授权服务器，也**允许与 server 同址部署**（spec 明确允许）；真正的规范点是 server 不得自签 token、必须做 audience 校验、禁止 token 透传；③ 用 RFC 9728 Protected Resource Metadata 让 client 发现正确的 AS（2025-11-25 起还可走 OIDC Discovery）；④ 用 RFC 8707 Resource Indicators 声明目标资源，server 校验 token 的 audience 必须是自己，杜绝跨服务重放；⑤ 可用 RFC 7591 动态客户端注册降低接入门槛（注意：该机制已在 2026-07-28 修订中被弃用，迁往 OAuth Client ID Metadata Documents，CIMD）。
- 一句话总结：把"谁能代表用户授权"与"谁持有资源"分离，是 OAuth 最佳实践在 agent 场景的落地。

#### 题 8【进阶 ⭐⭐⭐】谈谈 MCP 的安全风险。什么是 tool poisoning 和 rug pull？怎么防？

**答题思路**：威胁分类 → 攻击机理 → 分层防御 → 诚实说明无银弹。

**参考答案要点**：
- 根源：MCP 把不可信第三方内容接入模型决策回路，本质风险是间接 prompt injection 的生态化放大（OWASP LLM Top 10 中 LLM01 注入 + LLM06 过度代理的叠加）。
- **Tool poisoning**：恶意 server 在工具 description 中藏入对用户界面不可见、但随 schema 进入模型上下文的指令（如"调用前先外传 ~/.ssh 密钥"）。
- **Rug pull**：审核时 description 干净、用户授权后静默改写工具定义/行为。
- 其他：tool shadowing（仿冒命名抢占选择）、resources/工具输出投毒（CyberArk：没有一种 server 输出是安全的）、**本地 server 的跨源/DNS rebinding 直连**（恶意网页以用户身份调用回环 MCP server）、**memory poisoning**（注入载荷写入长期记忆跨会话常驻）、过度授权下的 confused deputy；真实事件如 EchoLeak（CVE-2025-32711，M365 Copilot 零点击注入，微软 CNA 口径 CVSS 9.3 Critical / NVD 口径 7.5 HIGH）。
- 防御纵深：沙箱执行（容器/microVM/WASM + 默认禁网）；最小权限与 scope 化授权；破坏性操作 HITL 审批（可参考 annotations 提示但不可依赖）；description 哈希 pinning + list_changed diff 告警（防 rug pull）；不可信输出来源标注、指令/数据隔离（CaMeL 类思路）；本地 server 绑定回环 + Origin 校验（spec 已把非法 Origin 回 403 写成 MUST）；gateway 层扫描与审计。
- 收口：prompt injection 在当前架构下不可根除，工程目标是降低概率 + 限制爆炸半径（最小权限 + 人工闸门）。

#### 题 9【系统设计 ⭐⭐⭐】公司有 500+ 内部 API，要为各业务线构建 Agent 工具平台，你怎么设计？

**答题思路**：按"接入层 → 注册与发现 → 运行时 → 安全治理 → 可观测"五层展开，每层给关键取舍。

**参考答案要点**：
1. **接入层**：从 OpenAPI spec 自动生成工具骨架（name/description/schema），人工润色 description——500 个 API 不可能纯手写；按域划分命名空间（`crm.*`、`billing.*`）。
2. **协议选型**：内部以 MCP server 形态暴露（域级别拆分 server，而非一个巨型 server），吃 MCP 生态红利（Claude Code / IDE / 各框架直连）；跨组织 agent 协作预留 A2A AgentCard。
3. **发现与选择**：全量工具不进 prompt。建工具索引（embedding + BM25 混合检索），两阶段召回 top-k；或采用 tool_search 式 lazy loading；上层按业务线配置 sub-agent，每个 agent 默认只挂载本域工具；流程性知识用 Skills 式渐进披露打包。
4. **运行时**：agentic loop 服务化——并行执行池（带依赖检测）、统一超时/重试/熔断、幂等键注入；code execution 沙箱支撑 programmatic 编排；长循环配 context editing + 外存记忆。
5. **安全治理**：gateway 统一 OAuth（按工具 scope）、权限三档（auto/ask/deny）、写操作审批流、description 变更审计、输入输出 DLP 扫描、全量审计日志。
6. **可观测与评估**：每次 tool_use/tool_result 全链路 trace（token、时延、成败）；建工具选择/端到端任务两级 eval 集，description 变更走 eval 回归；成本看板（工具定义 token 占比 + caching 命中率）。
7. 加分取舍：粗粒度聚合工具 vs endpoint 级薄封装——平台提供"动作聚合"工具套件给高频流程；长尾 API 保留自动生成通道。

#### 题 10【开放 ⭐⭐】MCP 和 A2A 会互相取代吗？设计多 agent 系统时你怎么选？

**答题思路**：先否定替代关系，给出分层模型，再落到选型判据。

**参考答案要点**：
- 不会取代，是不同层：MCP 是**纵向**的"agent↔工具/上下文"集成协议（model-controlled tools、app-controlled resources）；A2A 是**横向**的"agent↔agent"协作协议（AgentCard 发现、Task 委托、opaque agent 不共享内部状态）。A2A agent 内部照常用 MCP 接工具。
- 判据：需要给 agent 接数据/动作 → MCP；需要跨团队/跨厂商/跨信任域把任务委托给另一个**自主体**（对方有自己的规划与工具，且可能长时运行数小时）→ A2A。
- 反思视角：很多"多 agent"需求用单 agent + 好的工具集 + sub-agent 模式即可满足，A2A 的真正价值在**组织边界**（不同公司/不同框架/不同安全域的 agent 互操作），而非进程内编排——避免为了用协议而用协议。

#### 题 11【进阶 ⭐⭐】MCP 的 tool annotations 和结构化工具输出（outputSchema）分别解决什么问题？Host 应该怎么用？

**答题思路**：分别说清输入侧元数据与输出侧契约的动机，再点明"提示≠强制"这一关键边界。

**参考答案要点**：
- **annotations（输入侧元数据，2025-03-26 spec）**：`title` 提供展示名；`readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` 描述工具的行为特征。用途：Host 据此做 UX 与风控决策——如 destructive 工具弹确认、只读工具静默执行、幂等工具放心重试。
- **结构化输出（输出侧契约，2025-06-18 spec）**：工具用 `outputSchema` 声明返回值 JSON Schema，`tools/call` 返回 `structuredContent`。解决"工具结果是一段自由文本、下游难以程序化消费与校验"的问题，与输入 schema 形成输入输出双向契约。
- **关键边界**：两者都只保证**结构/元数据层面**——annotations 是 server 自述的提示，协议不校验真伪（恶意 server 可以把写操作标成 readOnly），**不能当安全边界**，破坏性操作的闸门必须在 Host 侧（HITL + 最小权限）；outputSchema 也只约束 JSON 形状，值的语义正确性仍由模型和工具逻辑保证。
- 加分：把 annotations 接入平台治理——例如 gateway 对 `destructiveHint=true` 的工具强制审计与审批流，对 `openWorldHint=true` 的工具叠加输出扫描。

#### 题 12【进阶 ⭐⭐】怎么评估一个 agent 的工具调用能力？你了解哪些基准和方法？

**答题思路**：先给评估维度框架，再谈基准及其局限，最后落到工程闭环。

**参考答案要点**：
- **四个维度**：① 工具选择（该不该调、调哪个，含 irrelevance detection——不该调时别硬调）；② 参数正确性（schema 合规是底线，值语义对才是目标）；③ 端到端任务成功率；④ 效率（轮数、token、时延、成本）。
- **基准**：**BFCL**（Berkeley Function Calling Leaderboard）用 AST/可执行校验测调用正确性，覆盖多轮多步与并行；**TAU-bench** 用 LLM 模拟真实用户在零售/航空域多轮博弈，并用 **pass^k**（k 次全过才算通过）度量稳定性——单跑成功率会被运气放大，方差才是生产环境的真实体验。
- **基准的局限**：公开基准易被针对性优化、域覆盖窄，不能替代业务 eval；必须自建领域任务集。
- **工程闭环**：工具侧 mock 保证确定性与可重放；生产 trace 脱敏回流成回归集；description/schema 变更走 eval 门禁（CI）；开放性结果用 LLM-as-judge 兜底但注意同源偏差；同时监控线上工具失败率、重试率、HITL 触发率作为 eval 的线上对照。

#### 题 13【进阶 ⭐⭐】一个 MCP 远程工具要执行数分钟，客户端如何拿到进度、如何取消、断线如何续？

**答题思路**：按"进度 → 取消 → 任务化 → 传输层续传"四级递进，体现对 spec 工具集的完整掌握，最后点出与 A2A 的职责交叠。

**参考答案要点**：
- **进度**：客户端在请求里附带 `progressToken`，服务器处理期间以 `notifications/progress`（progress / total）推送进度；超长任务客户端定期发 `ping` 保活并探活——防止中间设施掐断空闲连接。
- **取消**：客户端发 `notifications/cancelled` 通知（携带要取消的 `requestId`），服务器应尽快停止操作并清理；注意这是通知语义而非硬中止。
- **长任务任务化（experimental Tasks，2025-11-25）**：不让客户端全程挂连接——服务器接受请求后创建任务对象并返回任务标识，客户端轮询状态、延迟取结果，"提交 → 轮询 → 取结果"取代"长连接等待"。其语义与 A2A 的 Task 状态机明显趋同（趋势判断：两协议在长任务上的职责开始交叠）。
- **断线续传**：Streamable HTTP 的 SSE 流携带事件 ID，客户端重连后以 `Last-Event-ID` 补回错过的事件；`Mcp-Session-Id` 头维持会话状态；2025-11-25 起还允许服务器主动断开 GET 流、由客户端轮询重连。
- 加分：结合安全面——远程长任务工具必须叠加 scope 化授权与超时预算，且服务器对非法 Origin 头必须回 403（spec MUST）。

---

### 5. 易错点 · 反直觉点

1. **"Function Calling 是模型在执行函数"** —— 最普遍的错误认知。模型只产出 JSON 调用意图，执行永远在你的代码里；模型甚至看不到函数实现，只看 schema 与 description。
2. **"strict 模式让模型更聪明"** —— 不。它只是解码层的语法硬约束（logit masking），保证结构合法，**不保证参数值语义正确**。两家现已都提供：OpenAI strict:true 要求所有字段 required + `additionalProperties: false`、一律不支持 minLength/pattern/format 等校验关键字；Anthropic 也已支持 strict:true（不强制 required-all、schema 子集不同）——"Anthropic 没有硬约束"的旧答案已经过时。
3. **"工具越多 agent 越强"** —— 反直觉：工具一多，token 膨胀 + 选择混淆 + 注意力稀释，成功率反而下降。Anthropic 实测工具检索在削掉 ~85% 工具 token 后，eval 分数不降反升（49%→74%）。
4. **"description 是给人看的注释"** —— 它是模型选择工具与填充参数的**唯一依据**，改 description ≈ 改模型行为，应纳入 eval 回归。
5. **"tool_result 放在 assistant 消息里回传"** —— 两家 API 都要求放在 user 侧（Anthropic：user message 内 `tool_result` block；OpenAI：`role: "tool"`）。
6. **"并行工具调用 = 客户端并发执行"** —— 这是两个独立维度：模型单轮发出多个调用是一个维度，你并发执行是另一个维度；且模型偶尔会对有依赖的调用并行发出，执行层要有兜底。
7. **"MCP 的 SSE 被废弃是因为性能差"** —— 真正原因是架构性的：双 endpoint + 强状态长连接导致无法负载均衡、无法 serverless、断线丢上下文；Streamable HTTP 用"按需升级流"解决了这些。
8. **"MCP server 自己发 token 做鉴权更简单"** —— 这正是早期 spec 的坑：server 应只做 Resource Server，否则有 confused deputy / token 重放风险；2025-06-18 spec 已改为 OAuth 2.1 + RFC 9728/8707。
9. **"stdio MCP server 可以随便 print 日志"** —— stdout 是协议通道，任何非 JSON-RPC 输出都会毒化连接；日志必须走 stderr。
10. **"工具审核通过就安全了"** —— rug pull：授权后 server 可静默改 description/行为；必须做 description pinning + 变更告警。
11. **"给工具输出加个关键词过滤就能防 prompt injection"** —— 注入载荷可以任意变形；只要不可信文本与指令共享上下文，就没有过滤型银弹，只能靠权限隔离 + HITL + 限制爆炸半径。
12. **"MCP 和 A2A 是竞品"** —— 互补分层：一个管接工具（纵向），一个管 agent 互操作（横向），可同栈共存。
13. **"MCP tool annotations 是协议强制的约束"** —— 它们只是 server 自述的提示（readOnlyHint / destructiveHint 等），协议不校验真伪，恶意 server 完全可以把危险操作标成只读。annotations 改善 UX 可以，充当安全边界不行——破坏性操作的闸门必须在 host 侧。
14. **"工具返回了，模型就看到了全部"** —— 超大工具输出会被宿主/框架默认截断（数万 token 量级），模型是在截断视图上推理的；大结果集必须分页、摘要，或交给 programmatic tool calling 在沙箱代码里处理，只回传结论。反过来，`tool_result` 还支持 image block（base64，computer use 截图机制）与 resource link（2025-06-18）等多模态返回形态，且多模态返回同样计入 token、图片更易撑爆上下文。
15. **"扩展思考的内容往返时可以丢掉"** —— 使用 extended / interleaved thinking 配合工具调用时，Anthropic 要求把历史 thinking block 原样回传，否则请求报错或多步推理质量显著退化；thinking 不是可选装饰，是推理链的一部分。
16. **"单次任务跑通 = 能力达标"** —— agent 行为有方差。TAU-bench 的 pass^k 揭示：同一任务跑 10 次可能只过 4 次。评估必须度量稳定性（多次通过率、重试率），单次 demo 成功什么都证明不了。
17. **"outputSchema 是 2025-11-25 的 spec"** —— 不，结构化工具输出是 **2025-06-18** 引入的；2025-11-25 的头条是 experimental Tasks、OAuth CIMD / OIDC Discovery、JSON Schema 2020-12 默认方言、tool naming 指南等。现行 spec 版本是 **2026-07-28**，该版弃用了 Roots / Sampling / 协议级 Logging（是 deprecate 而非 remove）。版本号记串是 freshness 题最高频的坑。
18. **"模型报错重试几次总会停"** —— 不要赌。模型无视 `is_error` 无限重复相同调用是常见生产失败模式（死循环/退化重复）；编排层必须兜 max steps、相邻调用去重检测与连续失败熔断——循环防护是工程职责，不是模型自觉。

---

### 6. 推荐资源

1. **Anthropic 官方文档：Tool use with Claude** — 最权威的 tool use 机制参考：agentic loop、tool_choice、parallel use、token 计费表、server-side tools（web search / code execution / memory）一应俱全。[platform.claude.com/docs/en/agents-and-tools/tool-use/overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
2. **MCP 官方规范与架构文档** — 协议原文，现行版本 2026-07-28。重点读 Transports（stdio / Streamable HTTP / 长时任务）、Authorization（2025-06-18 + 2025-11-25 的 CIMD/OIDC）、Tool Annotations（2025-03-26）与结构化输出（2025-06-18）、版本变更日志与弃用特性注册表——freshness 考点几乎都出自这里。[modelcontextprotocol.io/specification](https://modelcontextprotocol.io/specification)
3. **Anthropic Engineering 三部曲** — *Writing effective tools for AI agents*（工具设计圣经：聚合、命名、错误修复提示）、*Introducing advanced tool use*（Tool Search / Programmatic Tool Calling / Tool Use Examples 及量化收益，"大规模工具管理"题的弹药库）、*Effective context engineering for AI agents*（长循环的上下文管理：context editing 与 memory tool）。[anthropic.com/engineering/writing-tools-for-agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
4. **Invariant Labs：MCP Security Notification — Tool Poisoning Attacks** — 首次系统披露 tool poisoning 的研究，配合 Simon Willison 关于 rug pull 与 prompt injection 的系列博文，构成 MCP 安全题的标准答案来源。[invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks)、[simonwillison.net/2025/Apr/9/mcp-prompt-injection/](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/)
5. **A2A 官方规范** — AgentCard / Task / Artifact / push notification 的权威定义，理解 agent 互操作层的必读。[a2a-protocol.org/latest/specification](https://a2a-protocol.org/latest/specification/)
6. **OpenAI 官方文档：Function calling** — 与 Anthropic 对照阅读，掌握 `parallel_tool_calls`、`strict: true`、`tool_choice: required` 的差异，双厂商对照是面试加分项。[developers.openai.com/api/docs/guides/function-calling](https://developers.openai.com/api/docs/guides/function-calling)
7. **评估基准：BFCL 与 TAU-bench** — BFCL（Berkeley Function Calling Leaderboard）是函数调用能力的标准横评；TAU-bench 论文（*τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains*）讲透了为什么用 pass^k 度量 agent 稳定性——评估题的答案骨架。[gorilla.cs.berkeley.edu/leaderboard.html](https://gorilla.cs.berkeley.edu/leaderboard.html)、[arxiv.org/abs/2406.12045](https://arxiv.org/abs/2406.12045)
8. **OWASP Top 10 for LLM Applications** — 把工具安全放进行业标准坐标系（LLM01 Prompt Injection、LLM06 Excessive Agency），安全岗面试引用它显得有体系而非背案例。[genai.owasp.org](https://genai.owasp.org/)
9. **MCP 官方 Registry** — 官方 server 元数据仓库：反向 DNS 命名空间归属验证、`server.json` 格式、REST 发现 API、与下游聚合器的生态分工——"供应链信任"讨论题的一手材料。[modelcontextprotocol.io/registry](https://modelcontextprotocol.io/registry)
