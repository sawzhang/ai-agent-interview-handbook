# 第 1 章 · LLM 基础原理

> 本章覆盖 Transformer 架构、注意力机制、位置编码、KV Cache、预训练与后训练（SFT/RLHF/DPO/GRPO/蒸馏/PRM）、Tokenizer、Scaling Laws、推理解码策略、MoE 与新架构。这是所有 LLM/Agent 岗位面试的"地基"——上层 RAG、Agent、微调的问题最终都会回溯到这些原理。本章按 2024–2026 年的最新认知校准：预训练 scaling 放缓、数据墙（data wall）逼近、推理时计算（test-time compute）与可验证奖励 RL 成为主线；架构侧亚二次/混合路线（Mamba 系、扩散 LM）与 FP8 低精度训练成为新考点。

---

### 一、知识图谱

```text
LLM 基础原理
├── 1. Transformer 架构
│   ├── 整体结构：Encoder-only / Decoder-only / Encoder-Decoder
│   ├── 核心组件：Token Embedding → N × (Attention + FFN) + Residual + Norm → LM Head
│   ├── 现代 Decoder-only 标配（LLaMA 栈）：Pre-RMSNorm / SwiGLU / RoPE / GQA / MLA（大模型不绑定权重）
│   ├── 训练稳定性组件：QK-Norm（Qwen3/Gemma 3/OLMo 2）、logit soft-capping（Gemma 2）、z-loss
│   ├── 机理视角：残差流（residual stream）、FFN 存知识、Attention 做路由、induction head
│   └── 为什么赢：并行化、长程依赖、可扩展性（对比 RNN/CNN）
├── 2. 注意力机制
│   ├── Scaled Dot-Product Attention：QK^T/√d_k → softmax → ×V
│   ├── Multi-Head：多头子空间、因果 Mask
│   ├── 显存/吞吐变体：MHA → MQA → GQA → MLA
│   ├── 稀疏/局部化：Sliding Window Attention、Attention Sink（StreamingLLM）
│   ├── 工程实现：FlashAttention（IO-aware、online softmax、tiling）
│   └── 复杂度：计算 O(n²d)、KV 缓存 O(n)
├── 3. 位置编码
│   ├── 为什么需要：Attention 本身置换不变（permutation invariant）
│   ├── 绝对 PE：正弦式 / 可学习式（无法外推）
│   ├── RoPE：旋转矩阵编码相对位置、频率分解
│   ├── ALiBi：注意力偏置、零样本外推
│   ├── 长上下文扩展：Position Interpolation → NTK-aware → YaRN → LongRoPE/LongRoPE2
│   └── 训练侧长上下文：序列/上下文并行（Ring Attention、DeepSpeed-Ulysses）
├── 4. KV Cache 与推理
│   ├── 自回归生成、Prefill vs Decode 两阶段
│   ├── 显存核算公式、为何 Decode 是 memory-bandwidth bound
│   ├── PagedAttention / 连续批处理 / chunked prefill / Prefix Caching
│   ├── KV 量化（FP8/INT4）、MLA 低秩压缩、KV 驱逐（H2O）、attention sink 流式
│   ├── 权重量化：AWQ / GPTQ / GGUF
│   └── 投机采样（Speculative Decoding / EAGLE / Medusa）
├── 5. Tokenizer
│   ├── 算法：BPE / WordPiece / Unigram(SentencePiece) / Byte-level BPE + 预分词
│   ├── 词表大小取舍、中英文效率、o200k / 128k vocab
│   └── 工程问题：token 计费、数字/拼写缺陷、chat template、一致性
├── 6. 训练流程
│   ├── 预训练：Next-token Prediction、交叉熵/困惑度、数据工程、C≈6ND、稳定性
│   ├── 低精度训练：FP8（blockwise scaling、DeepGEMM）；推理 FP8 主流、FP4 进入主流（GPT-OSS 的 MXFP4 发布精度、Blackwell 上 NVFP4 规模化 serving）
│   ├── 显存与并行：≈16 字节/参数（混合精度 AdamW）、梯度检查点、ZeRO-1/2/3（FSDP）、TP/PP/3D 并行
│   ├── 数据墙：高质量语料约 2026–2032 见底（Villalobos et al. 外推、有争议）、合成数据与 model collapse
│   ├── SFT：指令格式、质量 > 数量（LIMA）
│   ├── PEFT：LoRA（W'=W+BA、r≪d、可合并零延迟）/ QLoRA（NF4 + 双重量化 + paged optimizer）、multi-LoRA serving
│   ├── 蒸馏（Distillation）：教师 logits / 输出迁移；GKD、on-policy 蒸馏
│   ├── RLHF：Reward Model(Bradley-Terry) + PPO + KL 惩罚、四模型并存、奖励过优化
│   ├── DPO/SimPO/ORPO：闭式解、隐式奖励、离线、去 reference、失效模式
│   ├── GRPO/DAPO：组内相对优势、去 Critic、可验证奖励（推理模型路线）
│   ├── R1-Zero（纯 RL + 规则奖励）vs R1（冷启动 SFT → 多阶段 RL 流水线）
│   ├── PRM vs ORM：步级过程奖励 vs 终局结果奖励
│   ├── RL 基建：veRL / OpenRLHF、异步 rollout
│   └── RLAIF / Constitutional AI
├── 7. Scaling Laws
│   ├── Kaplan (2020)：参数优先
│   ├── Chinchilla (2022)：N 与 D 协同，≈20 tokens/param
│   ├── 推理感知缩放：服务成本下小模型更优
│   ├── 数据约束：多 epoch 收益递减、数据墙
│   ├── 评测信号：基准饱和（MMLU-Pro / HLE / LiveCodeBench）、污染检测（Min-K%++）
│   └── 2024-2026：预训练 scaling 放缓 → 推理时计算（test-time compute）新轴
├── 8. 解码策略
│   ├── Greedy / Temperature / Top-k / Top-p(nucleus) / Min-p / Typical
│   ├── Beam Search（翻译场景、开放生成退化）
│   ├── 重复抑制：repetition / frequency / presence penalty
│   └── 结构化输出：constrained decoding、JSON Schema、logit_bias
├── 9. MoE（Mixture of Experts）
│   ├── Top-k 路由 / expert-choice 路由 + 容量因子 + 负载均衡损失
│   ├── 参数与 FLOPs 解耦：大参数、低激活、专家专门化
│   ├── DeepSeek-V3：细粒度专家、共享专家、无辅助损失负载均衡
│   └── 工程挑战：全专家驻留显存、All-to-All 通信、专家并行
└── 10. 亚二次与新架构（2024-2026）
    ├── SSM：Mamba/Mamba-2（选择性机制、O(n) 复杂度、常数状态）
    ├── 线性注意力：GLA / DeltaNet / RWKV（去 softmax、RNN 式递推）
    ├── 可训练稀疏注意力：NSA（DeepSeek）、MoBA（Moonshot）、DSA（V3.2 lightning indexer）——保精确检索的亚二次路
    ├── 混合架构：Jamba / Nemotron-H / Kimi Linear / Qwen3-Next（少量注意力层 + 线性层）
    └── 扩散 LM：LLaDA / Dream / Mercury（掩码扩散、双向、块并行解码）
```

---

### 二、核心概念精讲

#### 2.1 Transformer：为什么是它

**是什么。** Transformer（Vaswani et al., 2017）用纯注意力机制替代了循环与卷积。一个 decoder-only 模型的数据流：`token ids → embedding (+ 位置编码) → N 层 [Self-Attention + FFN，各带残差与归一化] → RMSNorm → LM Head (vocab 投影) → logits → next token`。LM Head 权重可以与 embedding 矩阵共享（**weight tying**，省一份 `V×d_model` 参数）——**小模型普遍采用**（GPT-2、Gemma、Qwen-0.5B 等），但 LLaMA-1/2/3、Mistral、DeepSeek 等大模型**均不绑定**（`tie_word_embeddings=False`），以避免 embedding 主导梯度、并为 LM Head 留出独立容量。注意它不是"LLaMA 栈标配"，面试中说反会被当场纠正。

**为什么赢 RNN/CNN。**
- **并行性**：RNN 必须按时间步串行，无法吃满 GPU；Attention 对序列内所有位置并行计算，训练吞吐天差地别——这是 Scaling Law 能成立的硬件前提。
- **长程依赖**：任意两个 token 之间只隔一次 Attention（路径长度 O(1)），而 RNN 是 O(n)，梯度在长距离上衰减。
- **可扩展性**：结构规整、计算全是稠密矩阵乘，参数/数据/算力三者可以近乎线性地堆。

**现代 decoder-only 栈的演进（面试加分项）。** 原始 Transformer 之后几乎每个组件都被替换过，现在主流模型（LLaMA 系、Qwen、Mistral、DeepSeek）的标配是：
- **Pre-Norm + RMSNorm**：归一化放在子层之前，训练更稳定、可支撑更深网络；RMSNorm 省掉均值计算。
- **SwiGLU 激活的 FFN**：`FFN(x) = (Swish(xW₁) ⊙ xW₃)W₂`，比 ReLU/GELU 效果更好（代价是多一个投影矩阵，FFN 隐藏层相应缩小为约 2/3）。
- **RoPE 位置编码**（见 2.3）。
- **GQA**（见 2.2）。

**训练稳定性组件（2024-2026 增量，"Qwen3 相比 Qwen2 架构改了什么"的答案锚点）。** 规模与深度上去后 attention logits 会失控增长，引发 loss spike，新一代模型的应对：
- **QK-Norm**：计算注意力分数前对 q、k 各做一次 RMSNorm，从源头压制 attention logit 爆炸——已是 Qwen3、Gemma 3、OLMo 2 的标配；"Qwen3 相比 Qwen2 改了什么"的标准答案就是"去掉 QKV bias、加上 QK-Norm"。
- **logit soft-capping**：Gemma 2 用 `cap·tanh(logit/cap)` 给注意力/输出 logits 设软上限；因与 FlashAttention 类 kernel 适配不佳，Gemma 3 已改用 QK-Norm 替代。
- **z-loss** 一句话：对 softmax 配分函数加 `log²Z` 惩罚、防止 logits 整体漂移（PaLM、MoE 训练常用）。

**机理视角（区分"会用"和"懂"的分水岭）。** 把模型看成在一条**残差流（residual stream）**上读写：
- **FFN 占模型参数约 2/3、占算力大头**，各层 FFN 以键值存储方式编码事实性知识（"FFN as key-value memory"，Geva et al. 2021）；而可解释的"概念方向/特征"主要来自对**残差流（residual stream）**本身的研究（Anthropic 的特征抽取、sparse autoencoder / dictionary learning 工作），不要把两者混成"第一层 FFN 输出概念方向"。
- **Attention 更像"上下文路由器"**，负责在位置间搬运信息；典型结构如 **induction head**（"前文出现过 AB，现在见到 A 就预测 B"），这是 in-context learning 的关键电路之一。
- 问"知识存在哪里 / 模型怎么学会 in-context"时，这套"Attention 路由 + FFN 存储"的分工是答题主干，也是机器可解释性（mechanistic interpretability）的出发点。

**常见误区**：以为 Transformer = "Attention 取代一切"。实际上 FFN 才是参数与知识的大头，Attention 主要做信息整合。

#### 2.2 注意力机制及其工程变体

**数学核心。**

```
Attention(Q, K, V) = softmax(QKᵀ / √d_k) · V
```

每个 head 把输入投影到 Q/K/V 三个子空间；Multi-Head 把 `d_model` 切成 `h` 个 `d_k` 维子空间并行做注意力再拼接。**softmax 是逐行（逐 query）归一化**，使每个 query 对所有 key 的权重和为 1。**因果（causal）mask** 把未来位置置为 -∞，保证训练时一次前向等价于对所有前缀做 next-token 预测。

**为什么除以 √d_k（高频题）。** 假设 q、k 各分量独立、均值 0 方差 1，则点积 `q·k = Σ q_i k_i` 的方差为 d_k。d_k 越大点积绝对值越大，softmax 进入饱和区（梯度 ≈ 0，且输出近似 one-hot 失去区分度）。除以 √d_k 把方差拉回 1，使 softmax 处于敏感区。

**MHA → MQA → GQA → MLA 的演进（必考）。** 这条线的驱动力是**推理显存**，不是训练质量：

| 变体 | KV 头数 | 动机 | 代表 |
|---|---|---|---|
| MHA | = Query 头数 h | 原始设计 | GPT-3, BERT |
| MQA (Multi-Query) | 1 | KV cache 压到极致 | PaLM, Falcon |
| GQA (Grouped-Query) | g（1 < g < h），每 g 个 query 头共享一组 KV | 质量与显存的折中 | LLaMA-3, Mistral |
| MLA (Multi-head Latent Attention) | 不缓存逐头 KV，缓存低秩潜变量 | 质量接近 MHA、显存较 MHA 降 93%+（仍高于 MQA，胜在质量-显存比） | DeepSeek-V2/V3 |

以 LLaMA-3-70B 为例（80 层、GQA 8 个 KV 头、d_head=128、FP16）：**每 token 的 KV cache = 2(K+V) × 80 × 8 × 128 × 2B = 320 KiB**；8K 上下文单请求即 2.5 GiB。若用 MHA（64 KV 头）则是 20 GiB——GQA 直接省 8×。这个量级解释了为什么"长上下文"本质上是显存工程问题。

**稀疏/局部化注意力（补充考点）。**
- **Sliding Window Attention**：每个 token 只看前后 W 个位置——**每 token 注意力计算与每层 KV 缓存从 O(n) 降到 O(W)**（全序列训练计算从 O(n²) 降到 O(nW)）；通过多层堆叠，感受野逐层扩张到 `L×W`，长程信息靠"接力"传递。早期代表是 Mistral-7B（v0.1，注意 Mistral 后续版本已弃用 SWA）；当前代表实践是**滑窗层与全局层混合**：Gemma 2 以 1:1、Gemma 3 以 5:1 交替"局部滑窗:全局"层（Gemma 3 滑窗仅 1024），GPT-OSS 每隔一层用 128-token 滑窗层——**混合滑窗 + 全局层是当前主流形态**：少数全局层买回长程整合能力，多数滑窗层把 KV 压成常数。
- **Attention Sink**（Xiao et al., StreamingLLM, 2023）：流式/无限长推理中发现，**最初几个 token（尤其第一个）会吸收大量注意力分数，成为"注意力沉淀"**——即使语义无关，一旦从窗口滑出，perplexity 就崩。保留"开头几个 sink token + 最近的滑动窗口"即可稳定做百万 token 级流式推理。这把"位置编码外推"问题部分转化成了"哪些 KV 必须留下"的工程问题。

**MLA 的原理（2024-2026 新考点）。** DeepSeek 的做法（[技术报告 arXiv:2412.19437](https://arxiv.org/abs/2412.19437)）：
1. 不把逐头的 K/V 存下来，而是将隐状态下投影到一个低秩潜向量 `c_kv`（约 512 维）并缓存它；推理时再上投影还原出各头的 K/V。
2. **关键细节：解耦的 RoPE key**。RoPE 旋转会破坏低秩压缩的结构（旋转随位置变化，使 K 难以被低秩表示），因此 MLA 额外缓存一个小的、专门承载旋转位置信息的 key（64 维），与压缩部分分开。
3. 官方数据（DeepSeek-V2）：相比标准 MHA，**KV cache 减少 93.3%（压缩至约 1/15），最大生成吞吐提升约 5.76×**，质量几乎无损。注意按官方配置（512 维潜向量 + 64 维解耦 key = 每 token 每层 576 个元素）MLA 的每 token KV 仍约为 MQA（256 个元素）的 2 倍——它的卖点是"MHA 级质量 + 远低 MHA 显存"，而不是压过 MQA。MLA 是当前"用结构换显存"最成功的工程范例。

**FlashAttention。** 朴素实现的瓶颈不是算力而是 **HBM 访存**：N×N 的注意力矩阵要反复读写显存。FlashAttention（[Dao et al., 2022](https://arxiv.org/abs/2205.14135)）是**精确**（非近似）算法，核心三点：
- **Tiling**：把 Q/K/V 分块载入 SRAM，在片上完成计算；
- **Online softmax**（Milakov & Gimelshein 技巧）：增量维护 running max 与归一化分母，无需看到整行即可流式计算 softmax；
- 不落地 N×N 矩阵，注意力显存从 O(N²) 降到 O(N)，长序列训练速度提升数倍。FlashAttention-2/3 进一步优化了并行切分与对 Hopper 架构（TMA/WGMMA、异步 pipeline）的适配。**面试陷阱**：有人说"FlashAttention 用稀疏/近似换速度"——错，它是 IO 优化，数值等价。

#### 2.3 位置编码：从绝对 PE 到 RoPE 与长上下文

**为什么需要。** Self-Attention 对输入是**置换不变**的（打乱 token 顺序，输出只是同步打乱），不含任何位置信息；而语言强依赖语序，必须显式注入位置信号。

**RoPE 的本质（高频且易答浅）。** RoPE（Su et al., 2021）不给 embedding "加上"位置向量，而是对 Q、K 按位置施加**旋转**：位置 m 处的 query 变为 `q_m = R(θ, m) · q`，其中 R 是作用在相邻维度对 (2i, 2i+1) 上的二维旋转块，旋转角 `m·θ_i`，频率 `θ_i = 10000^(-2i/d)`。

妙处在于：`⟨R(θ,m)q, R(θ,n)k⟩` 只依赖**相对位置 m−n**（旋转保内积）。于是模型学到的是"距离感"而非"绝对坐标"，天然支持相对位置建模，且推理时位置可以连续编号。

**频率分解视角**（理解所有外推方法的钥匙）：低维对应高频（编码细粒度局部位置），高维对应低频（编码粗粒度长距离关系）。训练长度内的相位分布是模型"见过"的；超出训练长度，低频维度的相位进入未见区间，注意力崩溃——这就是 RoPE 的长度外推失败。

**ALiBi。** 完全不修改 embedding，直接在注意力分数上加一个距离惩罚偏置 `-m·|i−j|`（m 为逐头斜率）。优点是零样本外推能力强、实现极简（BLOOM、MPT 采用）；缺点是表达能力略逊，业界最终倒向了 RoPE + 缩放路线。

**长上下文扩展技术演进（2023-2025 热点）。** 核心共识：**压缩低频、保留高频**，把目标长度的相位"挪回"训练分布内：

| 方法 | 思路 | 代价 |
|---|---|---|
| Position Interpolation (PI) | 位置线性压缩 `m → m/s` | 需较多继续训练 |
| NTK-aware Scaling | 调大频率基数 θ（等价于非均匀压缩，低频压得多、高频不动） | 可免微调，提升有限 |
| YaRN | 按频率把维度分三段（高频不缩放 / 低频全插值 / 中频渐变）+ attention 温度补偿；比 PI 少用约 10× token、2.5× 训练步数（[arXiv:2309.00071](https://arxiv.org/abs/2309.00071)） | 少量微调，主流默认 |
| LongRoPE / LongRoPE2 (2024-2025) | 放弃公式，用进化搜索/needle-driven 逐维搜索最优缩放因子，近无损扩展到 2M+ | 需要搜索工程（[LongRoPE2](https://arxiv.org/abs/2502.20082)） |

**与推理工程的呼应。** 长上下文的另一条路线不改位置编码，而改"保留哪些 KV"：attention sink（StreamingLLM，见 2.2）+ 滑动窗口做无限流式；KV 驱逐（H2O）按重要性丢弃；InfLLM / Infini-attention 一类"稀疏/检索式注意力"把冷 KV 外置、按需取回，是同一问题的第三种解法。它们与频率缩放互补。**训练侧**的长上下文则是另一个问题：单卡放不下长序列的激活与注意力矩阵，需要**序列并行 / 上下文并行**——Ring Attention（Liu et al., 2023）沿序列维把 KV 分块环形传递、与计算流水线重叠，DeepSpeed-Ulysses 按注意力头切分再 all-to-all 重组，二者常与张量并行 / ZeRO 组合使用。

**常见误区**：① 以为"上下文窗口 = 能力"——窗口扩到 1M，但"大海捞针"(NIAH) 通过 ≠ 长程推理能力强，且 **"lost in the middle"**（中段信息利用率下降）至今部分存在；② 以为 RoPE 是"位置向量相加"；③ 外推时 perplexity 不炸 ≠ 可用，要看下游任务。

#### 2.4 KV Cache：推理性能的第一性原理

**Prefill vs Decode。** 自回归生成分两阶段，性能画像完全不同：
- **Prefill（预填充）**：一次性并行处理整个 prompt，是**计算密集（compute-bound）**的大矩阵乘，GPU 利用率高；延迟指标 TTFT（Time To First Token）主要取决于它。
- **Decode（解码）**：每步只生成 1 个 token，却要把**全部权重 + 全部历史 KV** 从 HBM 读一遍。算术强度约 ~1 FLOP/Byte，是**内存带宽受限（memory-bandwidth bound）**；TPOT/ITL（每 token 延迟）主要由带宽决定。

**这一区分是几乎所有推理优化题的答题起点**：权重加载成本固定 → **batch 越大摊薄越多**（吞吐换延迟）；KV cache 随序列线性增长 → 长上下文 + 高并发时 KV 显存超过权重显存，成为第一瓶颈。

**PagedAttention 与 vLLM。** 传统实现为每个请求预分配连续显存放 KV，碎片和预留浪费巨大。[vLLM](https://arxiv.org/abs/2309.06180) 借鉴操作系统虚拟内存：把 KV cache 切成固定大小的 block，按页表非连续分配、按需增长，碎片趋近于零；block 还可被多请求**共享**（beam search 的公共前缀、相同 system prompt）。配合**连续批处理（continuous batching）**——请求完成即换入新请求，而非等一批全结束——吞吐可提升一个数量级。**chunked prefill** 则把长 prompt 的 prefill 切成小块、与 decode token 混在同一批里跑，压住长 prompt 造成的 TTFT 毛刺与 decode 停顿。[vLLM 官方文档](https://docs.vllm.ai/en/latest/)是工程面试的一手材料。

**Prefix Caching（前缀缓存）。** Agent 场景下同一 system prompt + 工具定义会在海量请求中重复出现。SGLang 的 RadixAttention、vLLM 的 Automatic Prefix Caching 把公共前缀的 KV 缓存起来复用，命中后 prefill 成本骤降——这是 Agent 基建里 ROI 最高的优化之一。

**其他 KV 优化。**
- **KV 量化**：FP8 KV cache 相比 FP16 省 2× 显存（相比 FP32 约 4×），质量损失小，vLLM 已原生支持；INT4/FP4 KV 量化也已走出论文、进入主流推理框架的生产选项（LMDeploy 的 INT4 KV cache、TensorRT-LLM 在 Blackwell 上的 FP4 KV cache 等），再省一半显存，代价是对长上下文精确召回更敏感，上线前需按任务实测。
- **KV 驱逐**：H2O 等观察到注意力高度集中于少数"heavy-hitter" token，可丢弃低重要性 KV。
- **KV offload**：把冷 KV 卸到 CPU/NVMe，需要时换回，用带宽换显存容量。
- **结构级**：MLA（见 2.2）从根上把每 token KV 压到几百字节量级。

**权重量化（模型侧，与 KV 量化并列）。** 部署侧最常见的是 **AWQ**（按激活分布保护"显著"权重通道）与 **GPTQ**（逐层二阶误差补偿），INT4 下对大模型常可做到近无损；llama.cpp 的 **GGUF** 格式把量化模型推向 CPU/端侧。面试中区分"权重量化（一次性、离线）"与"KV 量化（在线、随序列增长）"是加分项。

**投机采样（Speculative Decoding，高频）。** 用小模型（draft model）一次猜 γ 个 token，大模型**一次前向并行验证**这 γ+1 个位置，接受概率 `min(1, p_target/p_draft)`，拒绝则从校正分布重采样。两个关键点：① 数学上**保证输出分布与直接用大模型完全一致**（无损加速，这是和"小模型直接生成"的本质区别）；② 收益来自"把串行的 γ 次大模型 decode 压成 1 次"，acceptance rate 越高越赚。变体：Medusa（给大模型加多个解码头自猜）、EAGLE（在特征层做 draft，接受率更高，代码类任务可达 0.8+）。**限定（易被追问）**：无损保证只属于带拒绝采样校正的标准方案（Leviathan et al. / Chen et al.）；Medusa 默认的 typical acceptance 是**近似无损的启发式**，严格保分布需切到拒绝采样模式（Medusa-2、EAGLE 的重采样路径）。

#### 2.5 Tokenizer：被低估的基础设施

**算法谱系。**
- **BPE**（GPT 系）：从字节/字符出发，反复合并语料中最高频的相邻 pair，合并表即词表。Byte-level BPE（GPT-2 起）以 256 个字节为基底，**任何语言、任何字符都能编码、永无 UNK**。
- **WordPiece**（BERT）：类似 BPE 但按似然增益选合并。
- **Unigram**（T5、ALBERT）：概率模型，从大词表出发反向剪枝得到最优子词集。
- **SentencePiece 框架**（注意：它是框架，不是算法）：以原始字节流为输入的独立分词器，内置 BPE 与 Unigram 两种算法可选，对中日韩等无空格语言友好；早期 LLaMA-1/2 用的是它的 **BPE** 模式，不是 Unigram。
- **预分词（pre-tokenization）别忽视**：BPE 合并发生在"词边界"之内，GPT 系用正则把文本先切成词块（如 `'ĠApple'` 带前导空格标记）——这决定了空格、标点、数字如何被切分，也是"为什么多个空格会被合并""为什么词首/词中拼写不同"的根源。

**词表大小的取舍（进阶题）。**
- 大词表（GPT-4o 的 [o200k](https://github.com/openai/tiktoken) ≈ 20 万、LLaMA-3 的 128k = 100k tiktoken 基底 + 28k 非英语 token）：同样文本消耗更少 token → 上下文更"耐装"、注意力与序列长度相关成本下降、非英语效率显著提升（LLaMA-3 英文压缩率由 3.17→3.94 字符/token、整体约省 15% token，非英语因专门补充 token 收益更大）。
- 代价：embedding 矩阵与 LM Head 均为 `V × d_model`，V 越大参数越多；低频 token 训练不充分；每步 logits 的 softmax/采样成本随 V 线性增长。

**工程常识与典型缺陷。**
- 经验比例：英文约 1 token ≈ 4 字符 ≈ 0.75 词；中文分三档——**中文原生大词表（Qwen、GLM、DeepSeek）约 0.6–1 token/字**（大量多字 token），LLaMA-3 级非英语优化词表约 1–1.5 token/字，旧词表（GPT-3.5）曾高达 2–3 token/字——**同一任务中文 API 成本可能是英文两倍**，做预算时必须按目标语言实测 token（用对应模型的 tokenizer 计数，而非拍脑袋）。
- **tokenization 解释了 LLM 的一类经典失败**：数不清 "strawberry" 里有几个 r（模型看到的是子词 token，不是字母）；算术进位错误、倒拼单词困难、罕见词被切碎。缓解手段之一是推理时对字符级任务显式拼空格/分字。
- 训练与推理**必须用同一个 tokenizer**；微调换了词表等于换了模型（embedding 与新 token 未对齐）。
- Chat 模型有专用 chat template（角色标记、特殊 token），直接拼裸文本会显著降质；微调时务必用目标模型同款 template 打包数据。
- 跨模型的 perplexity **不可比**——分词不同，NLL 的"每单位"不一样（比较要在字节级 BPC 或统一分词下进行）。

#### 2.6 预训练：目标、数据与算力核算

**目标。** 就是 next-token prediction：最大化 `Σ log p(x_t | x_<t)`，损失为交叉熵，perplexity = exp(平均 NLL)。看似简单，但"预测下一个词"在足够大的数据上逼近了对世界的压缩建模——这是整个领域的经验信仰。

**算力核算（必须会口算）。** 训练 FLOPs ≈ **6ND**（N 参数量、D token 数；前向 2ND + 反向 4ND）。推理每生成一个 token ≈ 2N FLOPs。例：70B 模型训 15T token ≈ 6.3×10²⁴ FLOPs。面试给一个 GPU 数×时长让你估模型/token 规模，就用这个；反过来给 FLOPs 预算估"能训多大、训多久"也是同一公式。（注意 6ND 是近似：忽略 embedding、注意力中相对 d_model 的 O(n²) 项；长上下文训练时后者不可忽略。）

**数据 > 参数，且正在见底。** 高质量语料在 2024 年后被普遍视为最稀缺资源：去重（exact + fuzzy/MinHash）、质量过滤、领域配比、课程式混合、**基准去污染（decontamination，剔除与评测集重叠样本，否则评测虚高）**。Villalobos et al.（Epoch AI，[arXiv:2211.04325](https://arxiv.org/abs/2211.04325)，ICML 2024）按历史消耗速率外推：**高质量语言数据约在 2026–2032 年间耗尽（中点约 2028）**，低质量数据可撑到 2035–2050——这就是"数据墙（data wall）"。注意这是趋势性外推、学界有争议，引用时重在趋势而非具体年份。应对：
- 多 epoch 训练收益递减，约 4 epoch 内损失影响可接受（Muennighoff et al., 2023）；
- **合成数据**（模型蒸馏/改写/自我生成）已成主流补充，但要警惕 **model collapse**（在自生成数据上反复训练导致分布尾部丢失、质量退化）；
- 新训练目标如 **multi-token prediction**（一次预测多个未来 token，兼作训练目标与投机解码 draft）已进入一线模型。

**稳定性工程。** warmup + cosine 衰减、梯度裁剪、bf16 混合精度（bf16 动态范围大、不易溢出，已取代 fp16 成为训练默认）；loss spike 的常见处置是回滚到上一个健康 checkpoint 并跳过问题数据批次。

**Muon 优化器（前沿岗加分题："K2 为什么不用 AdamW"）。** Muon 对**矩阵形参数**不再走 Adam 的逐元素自适应，而是把动量矩阵先做**正交化**（Newton-Schulz 迭代近似求正交因子）再更新——直觉是让更新在各方向上"等强度"推进、避免少数奇异方向主导；embedding/LM Head 等非矩阵参数仍配 AdamW。Kimi K2 用 **MuonClip**（Muon + **qk-clip**：按 attention logit 超限比例回缩 q/k 投影权重，压制 logit 爆炸这一 Muon 大规模训练的主要不稳因素）完成了 **1T 总参 MoE 的全程无 loss spike 训练**，官方口径是 token 效率（同数据量下的损失下降）优于 AdamW。面试一句话：**Muon 赢在矩阵结构感知带来的 token 效率，MuonClip 补上大规模稳定性短板**。

**低精度训练与推理（2024-2026 新考点）。** 训练侧，**FP8 混合精度**已进入一线：DeepSeek-V3 在 671B 规模上用 FP8（E4M3 前向 / E5M2 反向梯度）+ **细粒度 blockwise scaling**（激活按 1×128、权重按 128×128 分块缩放）+ 自研 DeepGEMM 算子验证了稳定性——粗粒度（per-tensor / per-channel）缩放在大模型的离群激活面前会发散，**分块缩放是 FP8 训练可用的关键**。推理侧，FP8（E4M3）已是 Hopper / Blackwell 上的主流 serving 精度（vLLM、TensorRT-LLM 原生支持，DeepSeek-V3 即以此部署）；FP4 也已跨过"起步"阶段进入主流：OpenAI 的 **GPT-OSS** 直接以 **MXFP4** 作为发布权重精度（MoE 权重 4-bit，120B 单卡 80GB 可跑），**NVFP4** 在 Blackwell 上进入规模化 serving（TensorRT-LLM / vLLM 支持，NVIDIA 官方放出多款模型的 NVFP4 checkpoint）；BF16/FP16 退为兜底精度。面试口径：低精度的核心矛盾是**离群激活（outliers）与缩放粒度的取舍**。

**训练显存口算与分布式并行（与 6ND FLOPs 配对的第二道必会口算）。** 混合精度 AdamW 全参训练的**静态显存 ≈ 16 字节/参数**：bf16 权重 2 + bf16 梯度 2 + fp32 master 权重 4 + fp32 一阶矩 4 + fp32 二阶矩 4；另加激活显存（随 batch×序列长度×层数增长，长上下文下会反超静态项）。经典演算题"**70B 全参要多少卡**"：70B×16B ≈ **1.12 TB 静态状态**——80GB 卡（A100/H100）光放静态态就要 ≥14 张，加上激活、通信 buffer 与并行开销，实践中 **16–32 张起步**。省显存三板斧：
- **梯度检查点（activation checkpointing）**：只存层边界激活、反向时重算，省掉激活大头，代价约 **+30% 计算**（多一次前向）；
- **ZeRO 三档**（DeepSpeed）：ZeRO-1 只切分**优化器状态**（16 字节里的 12 字节 ÷ DP 卡数）；ZeRO-2 再切**梯度**；ZeRO-3 连**参数**也切、用时 all-gather——显存最省但通信量增约 50%。**FSDP ≈ ZeRO-3** 的 PyTorch 原生实现；
- 量化底模 + PEFT（QLoRA 路线，见 2.7）。

**并行三件套（怎么把一个放不下的模型切开）。**

| 并行 | 切什么 | 通信特征 | 适用域 |
|---|---|---|---|
| **TP 张量并行** | 层内：权重矩阵按行/列切 | 每层前/反向各 2 次 all-reduce，高频大流量 | 限高带宽域（NVLink），一般 ≤8 卡节点内 |
| **PP 流水线并行** | 层间：按层切成 stage | 相邻 stage 点对点传激活，流量小 | 可跨节点；有 pipeline bubble，需 micro-batch（1F1B/interleaved）填充 |
| **DP/ZeRO 数据并行** | 切数据（ZeRO 再切训练状态） | 梯度 all-reduce/reduce-scatter | 扩吞吐主力，规模最自由 |

**选型口诀**：**节点内 TP、跨节点 PP/DP、显存不够上 ZeRO**；万卡级训练即 TP×PP×DP 的 **3D 并行**（Megatron-LM），超长序列再叠序列/上下文并行（见 2.3）。

#### 2.7 后训练：SFT → 蒸馏 → RLHF → DPO → GRPO

对齐与能力激发的流水线，面试几乎必问其一。

**SFT（监督微调）。** 用 (指令, 回答) 示范教模型"格式与风格"。核心经验：**质量远比数量重要**——LIMA（Meta, 2023）证明约 1000 条精挑数据即可接近 RLHF 模型的表现；SFT 主要改变行为分布（怎么说），知识增量有限（知识主要靠预训练或 RAG）。

**参数高效微调（PEFT）：LoRA / QLoRA（微调落地的默认起点，Agent 岗必会）。** 全参微调 70B 要 16–32 张卡（见 2.6 显存口算），多数场景负担不起——PEFT 用"冻结底模、只训小增量"把门槛降两个数量级：
- **LoRA**（Hu et al., 2021）：冻结 W，训练低秩增量 `W' = W + (α/r)·BA`（`B∈ℝ^{d×r}`、`A∈ℝ^{r×k}`、秩 r≪d；A 高斯初始化、B 零初始化，保证训练起点等价原模型）。可训参数常仅 0.1–1%，优化器状态随之骤减；**推理前可把 BA 合并回 W——零额外延迟**。常见取值 r=8–64、α=16–32（经验上 α≈2r，缩放系数 α/r 控制增量幅度）；**加在哪些矩阵**：原论文只加 q/v 投影即有效，实践中加满全部线性层（q/k/v/o + FFN 三矩阵）效果更强（QLoRA 的结论之一）。
- **QLoRA**（Dettmers et al., 2023）：底模量化为 **4-bit NF4**（按正态权重分位数设计的量化格式）+ **双重量化**（把量化常数再量化，每参数再省约 0.37 bit）+ **paged optimizer**（显存尖峰时把优化器状态换页到 CPU），LoRA 增量仍以 bf16 训练。经典账：**单张 48GB 卡微调 65B**（Guanaco）——对照全参的 16 字节/参数（65B ≈ 1TB），省了约两个数量级。
- **LoRA vs 全参（必答取舍）**：数据少、任务窄（格式/风格/领域话术对齐）、多租户定制 → LoRA；大幅行为改变、注入大量新能力、长程 agent 轨迹训练 → 全参或 RFT。**为什么低秩有效**：任务适配的权重增量本身近似低秩（intrinsic dimension 低），低秩分解足以覆盖；但也因此 **LoRA 学新知识弱，更像"格式/风格适配器"**——Agent 的 tool-call 格式对齐用 LoRA 通常够，推理能力提升要靠 RL/全参。
- **multi-LoRA serving**：S-LoRA / vLLM 支持共享一份底模、按请求动态挂载不同 adapter（unified paging 管理 adapter 显存），一张卡可服务成百上千个租户定制——"可合并（零延迟）"与"可热插拔（多租户）"是 LoRA 的两种部署形态。
- 变体一句：**DoRA** 把权重更新分解为幅值 + 方向两部分分别学习，低秩下常比 LoRA 更接近全参效果。

**蒸馏（Distillation，2024-2026 小模型路线的关键）。** 用强模型（teacher）生成回答或输出 logits，训练弱模型（student）模仿：
- **输出级**：直接学 teacher 的回答文本（本质是高质量合成数据 SFT）——DeepSeek-R1-Distill 把推理能力蒸馏到 1.5B–70B（Qwen2.5-1.5B/7B/32B 与 Llama-3.1-8B/70B），是"用 RL 造教师、用蒸馏铺学生"的范例；
- **logits 级**：学 teacher 的软分布（soft label，温度 T 平滑），比硬标签携带更多"类间关系"信息（经典 Hinton 蒸馏）。
- 蒸馏能把昂贵的 RL/推理能力廉价扩散到可部署的小模型，是"小模型超训 + 大模型当教师"范式的落地手段；局限是 student 难以超越 teacher 的能力上界。

**RLHF（PPO 路线）。** InstructGPT 确立的三件套：
1. 收集人类偏好对 (prompt, y_win, y_lose)；
2. 训练 **Reward Model**（Bradley-Terry 排序损失）；
3. 用 **PPO** 优化 policy：`max E[r(x,y)] − β·KL(π‖π_ref)`，KL 惩罚防止模型跑偏/钻奖励漏洞。
痛点（DPO 出现的动机）：训练时同时驻留 policy、reference、reward、value 四个模型，显存爆炸；PPO 超参敏感、工程链路长、不易收敛。
**奖励过优化（必知的失效模式）**：RM 本身是学出来的代理目标，policy 越强越会钻它的空子（Goodhart 定律）。Gao et al. (2023) 给出经验缩放律：KL 约束下，真实质量先升后降，与代理奖励的差距随优化强度拉大——所以"reward 曲线一路上涨"往往是危险信号，需要 KL 调控、RM 集成与持续 red-teaming。

**DPO（Direct Preference Optimization，2023）及其家族。** 关键推导：KL 约束下的最优策略有闭式解，奖励可写成 `r = β·log(π/π_ref)`（隐式奖励）。把它代回 Bradley-Terry，整个 RL 问题坍缩成一个**二分类偏好损失**：

```
L_DPO = − E[ log σ( β·log π(y_w)/π_ref(y_w) − β·log π(y_l)/π_ref(y_l) ) ]
```

优点：无需独立 RM 与 PPO，只需 policy + reference 两个模型，稳定、便宜、易复现，被 LLaMA-3、Qwen 等广泛采用（常与少量 PPO 混用）。
变体：**SimPO**（用序列平均 log 概率作隐式奖励、**去掉 reference 模型**并加长度归一化，更省更稳）、**ORPO**（把偏好对比直接并进 SFT 损失、单阶段无 reference）、KTO（只需"好/坏"二元标签而非成对数据）。
**失效模式（进阶必答）**：① **likelihood displaced**——被拒答案与偏好答案高度相似时，DPO 会连带压低偏好答案的似然（Smaug, Pal et al. 2024）；② 离线方法的分布外弱点：综合评测（[Is DPO Superior to PPO?, arXiv:2404.10719](https://arxiv.org/abs/2404.10719)）显示 PPO 在 OOD 泛化上常常更好；③ 对 reference 模型与数据偏移敏感。答"DPO 全面优于 RLHF"会被扣分。

**GRPO（Group Relative Policy Optimization）与推理模型路线。** DeepSeekMath / [DeepSeek-R1](https://arxiv.org/abs/2501.12948) 的核心算法：对同一 prompt 采样一组（group）输出，用**组内归一化** `(r_i − mean)/std` 作为优势估计，**砍掉 PPO 的 critic/value 网络**——显存与工程大幅简化。配套两大转变：
- **可验证奖励（verifiable rewards）取代人类偏好**：数学题判对错、代码跑测试用例，奖励客观且稠密，专为"推理能力"设计；
- **DAPO**（ByteDance, 2025）等后续改进：clip-higher（放宽上探幅度鼓励探索）、dynamic sampling（过滤全对/全错的无信息组）、token-level loss、超长 shaping。
这条线解释了 2025 年"推理模型"（o1/R1 系）为何集体转向 RL：**有标准答案的任务上，RL + 可验证奖励能自发涌现出长思维链**。

**R1-Zero vs R1：推理模型的训练管线（2025 高频，勿混为一谈）。**
- **DeepSeek-R1-Zero**：**完全不做 SFT**，直接在 base 模型上用 GRPO + **规则化奖励（rule-based rewards：答案正确性校验 + 思维链格式约束，不训练 RM）**。推理行为（长思维链、反思、验证）**自发涌现**，并出现可读性先降后升的"aha moment"——证明纯 RL 足以激发推理能力；
- **DeepSeek-R1**（发布的成品）：是**四阶段流水线**——① 冷启动 SFT（数千条长思维链示范，提升可读性与格式）→ ② 推理导向 RL → ③ 拒绝采样 + 约 80 万样本 SFT（推理 + 通用任务）→ ④ 面向全场景的 RL；长度惩罚与截断等工程细节也塑造了思维链形态。
面试口径：**纯 RL 能涌现推理，但冷启动 SFT 让推理更可读、更可控；R1 = R1-Zero 路线 + 数据工程**。R1-Zero 与 R1 一并开源，Distill 系列再把轨迹蒸馏到小模型（见上条）。

**PRM vs ORM（推理模型奖励设计的高频新考点）。** 奖励"打在哪"决定了信用分配（credit assignment）质量：
- **ORM（Outcome RM）**：只对最终答案给一个奖励（对/错）。标注便宜，但一步走错整条链零信号，长思维链下梯度稀疏、难以定位"哪一步错"；
- **PRM（Process RM）**：对**每一个推理步骤**给奖励（如 PRM800K、Math-Shepherd 用蒙特卡洛估计每步"通向正确答案的概率"、ThinkPRM 用生成式验证）。信号稠密、信用分配好，还能直接用于**搜索/重排（best-of-N、beam search over steps）**；代价是步级标注昂贵、误差会沿链累积。
- 实践共识：可验证任务上"ORM 起步 + 逐步引入过程监督"是性价比路线；纯人类标注 PRM 难规模化，**自动化过程奖励（用验证器/模型生成步级标签）**是主流方向。

**RLAIF / Constitutional AI**（Anthropic, 2022）：用模型自己按"宪法原则"生成偏好、自我批评修订，减少人工标注依赖，是规模化对齐的现实路径。

**RL 基建与蒸馏新范式（工程岗加分）。** 大规模 RL 的系统瓶颈在 rollout 与权重同步：**veRL**（字节，hybrid-flow 架构，把训练与采样在同集群内灵活编排）与 **OpenRLHF**（基于 Ray 的分离式架构）是两套主流开源框架；异步 rollout 与 staleness 控制（允许多旧的 off-policy 样本）是核心工程权衡。蒸馏侧的两个新词：**GKD**（Generalized Knowledge Distillation，Agarwal et al. 2024）让学生在**自生成输出**上匹配教师分布，缓解"训练看教师轨迹、推理用自己分布"的错配；**on-policy distillation**（Thinking Machines, 2025）把"学生自采样 + 教师逐 token 打分"做成规模化流程，被描述为介于 SFT 与 RL 之间的低成本能力迁移路径。

#### 幻觉的机理成因（"为什么大模型会幻觉"必考，浅答扣分）

浅答只说"训练数据有错/覆盖不全"——这只是次要因素。深答分三层：
- **训练目标层**：next-token MLE 奖励的是"在训练分布下最流畅的续写"，而非"真实"。事实断言在语料中往往只出现一次（singleton），模型没有足够统计量把"记住的"与"编得像的"区分开——生成一个高概率但错误的实体名，在交叉熵意义上几乎不受惩罚。叠加解码期的**采样随机性**，低概率的错误延续总有机会被采出来，并被后文"自圆其说"。
- **知识边界层**：预训练没有显式的"我不知道"监督信号——语料里几乎没有"这个问题我答不上来"的自然示范，模型对自身知识边界**缺乏校准**，到了边界外仍按同样的方式流畅外推。
- **评测激励层**（OpenAI 2025《Why Language Models Hallucinate》的核心论点）：主流基准**二值评分**——答对得分、答错与弃权同样零分（弃权甚至更亏），这在统计上**激励猜测**：即使一个校准良好、知道自己不确定的模型，在这种记分规则下的最优策略也是硬答而非弃权。幻觉因此被制度性地固化——不改评分规则（给"恰当弃权"记分、对自信错误重罚），训练侧的修补是逆水行舟。

**缓解分层**：训练侧（拒绝/弃权数据、校准感知的奖励设计）→ 解码侧（事实性任务降温、自洽采样交叉验证）→ 检索侧（RAG 用外部证据落地，见第 4 章）→ 校验侧（引用核查、评估与可观测性，见第 8 章）。面试口径：**浅答训练数据，深答"训练目标 + 评测激励 + 校准"三层，再顺出分层缓解**。

#### 2.8 Scaling Laws：从 Chinchilla 到推理时计算

**三代认知。**
1. **Kaplan et al. (2020)**：损失随 N、D、C 呈幂律下降，指数上参数更"划算"，结论是堆参数（催生了 GPT-3 175B 只训 300B token、约 1.7 tokens/param 的"欠训练"做法）。
2. **[Chinchilla](https://arxiv.org/abs/2203.15556) (Hoffmann et al., 2022)**：更严谨的实验证明**算力应在参数 N 与数据 D 间大致均分**——最优分配下 N、D 随计算预算近似按 0.5 次方同速增长，经验法则 **≈20 tokens/参数**。70B 的 chinchilla-optimal 训练量约 1.4T token。而 LLaMA-3-70B 训了 15T（≈214 tokens/param）——严重"超训"。
3. **为何业界集体超训？** 因为 Chinchilla 只优化**训练算力**，而模型要服务海量请求。[Should We Prioritize Research on Small Language Models?（Sardar et al. 2024, arXiv:2401.00448）](https://arxiv.org/abs/2401.00448)（其 inference-aware scaling laws 一节）把推理成本纳入总账：总成本 = 训练 + 查询量×单 token 推理成本（∝ N），最优解偏向**更小、超训的模型**——同样的训练预算产出推理便宜得多的产品。这是"小模型+大数据"范式（Phi、Llama-3-8B、GPT-4o-mini）的理论依据。

**边际收益、数据墙与"撞墙"论。** 按 Chinchilla 指数，训练算力翻倍仅换来**总损失约 5–6% 的相对改善**（指数口径约 5.7%；若看 excess loss，相对改善约 20%）；叠加 2.6 节的**数据墙**（高质量语料约 2026–2032 见底的外推值），2024 年起业界共识是**纯预训练 scaling 的边际曲线明显放缓**。

**新坐标轴：推理时计算（test-time / inference-time scaling）。** 2024-2026 的增量主要来自推理阶段投入更多算力：长思维链、自洽采样（self-consistency）、best-of-N、搜索/验证循环（o1、R1、Deep Research 类产品）。[Snell et al. (2024)](https://arxiv.org/abs/2408.03314) 证明：在固定"总计算预算"下，存在一个"最优分配"——难题更该把算力投到推理时（多采样+验证）而非一味放大模型；s1（budget forcing）等工作进一步展示用少量样本 + 控制思考长度即可显著提升推理。其 learning-curve 形态不同于预训练 scaling，是当前 scaling 叙事的主战场。

**两个面试纠偏点。** ① **Emergent abilities 部分是度量幻觉**（Schaeffer et al., 2023）：用连续指标（而非阶梯式 exact-match）评测，"突变"往往变成平滑曲线；② perplexity 下降 ≠ 下游能力提升，尤其是指令遵循、对齐相关能力由后训练主导。

**基准饱和与污染检测（2025-2026 高频）。** 与"scaling 放缓"互为表里：MMLU 等经典基准已被前沿模型做到接近上限、失去区分度。应对两条线：① **更难的升级基准**——MMLU-Pro（10 选项 + 推理强化）、GPQA Diamond、**LiveCodeBench**（滚动收录竞赛新题，天然抗污染）、**HLE**（Humanity's Last Exam，专家级跨学科难题，发布时最强模型也仅个位数到低两位数百分比，其后随模型迭代快速爬升但仍远未饱和）；② **污染检测**——Min-K% / Min-K%++（以低概率 token 占比判断样本是否出自训练集）、成员推断攻击、参考无关的 CDD 等方法。面试口径：引用"模型 X 在基准 Y 上得 Z 分"之前，先问**这个分数还可信吗**（是否已饱和 / 被污染）。

#### 2.9 解码策略：采样是产品决策

**各参数的真实含义。**
- **Temperature**：softmax 前对 logits 除以 T。T<1 分布变尖（更确定），T>1 变平（更发散），T→0 退化为 greedy argmax。它是**熵旋钮**，不是玄学"创造力开关"——而且很多 serving 栈在 T=0 时走专门的 argmax 路径。
- **Top-k**：只保留概率最高的 k 个再归一化。缺陷：k 是常数，但分布的"合理候选数"随上下文剧烈变化（函数名后往往只有 1 个合理 token，开放句首可能有上百个）。
- **Top-p (nucleus, Holtzman et al. 2020)**：按概率降序累加到 p 截断。动态候选集，是目前默认方案。
- **Min-p**：丢弃概率 < p × 最高概率的 token，比 top-p 更简单稳定，开源社区流行。
- **Beam search**：维护 B 条假设、按长度归一化打分。适合翻译等有标准答案的生成；在**开放生成中系统性退化**——偏好短、安全、重复的"无聊"文本（这正是 nucleus sampling 论文要解决的问题）。
- **重复抑制**：repetition_penalty（缩放已出现 token 的 logits）、frequency/presence penalty（OpenAI API 形式）。过强会逼出乱码近义词。
- **Typical sampling**：优先选"局部信息量接近期望熵"的 token，增强连贯性，用得较少。

**参数交互（易错）。** temperature 先于 top-p/top-k 生效；两者同时调会互相干扰，OpenAI 官方建议只动一个。GPU 上的"同 seed 确定性"在批大小/内核变化时并不保证，不要把可复现押在 seed 上。

**Agent 场景的实战配方（结合岗位方向）。**
- 工具调用、JSON 输出、结构化抽取：**T≈0～0.3、top-p=1**，追求确定性；
- 但纯 greedy 有**陷入重复循环**的风险（死循环调用同一工具），实践中留一点随机性 + `stop` 序列 + 最大重试更稳；
- **结构化输出不要靠 prompt 祈祷**，要用 constrained decoding（outlines / xgrammar / GBNF）或 API 的 JSON Schema / tool_choice 强制合法；
- 失败重试时**提高温度重采样**比原样重试有效（相同输入+greedy 只会复现同一错误）。

#### 2.10 MoE：参数与算力的解耦

**机制。** 把 Transformer 的 FFN 换成多个"专家 FFN"，每个 token 由 router（一个小线性层 + softmax）选出 **top-k 个专家**加权求和。好处：**总参数巨大（容量/知识）但每 token 激活参数小（FLOPs 低）**——[DeepSeek-V3](https://arxiv.org/abs/2412.19437) 总参 671B、激活仅 37B，训练推理成本接近一个 37B dense 模型。专家会自发**专门化**（不同专家偏好不同领域/语言/句法模式），这是容量收益的来源。

**路由与负载均衡（高频）。**
- **token-choice（主流）**：token 选 top-k 专家。天然出现路由塌缩：少数专家被反复选中（赢者通吃），其余"饿死"。经典解法（Switch Transformer）是**辅助损失** `L_aux ∝ N·Σ f_i·P_i`（f_i 为专家被分配比例、P_i 为平均路由概率）+ 容量因子限制单专家 token 数。
- **expert-choice**（Zhou et al., 2022）：反过来让专家选 token，天然均衡负载，但对"某 token 不被任何专家选"需要兜底。
- **DeepSeek-V3 的改进**（[Auxiliary-Loss-Free Load Balancing](https://openreview.net/pdf?id=y1iU5czYpE)）：给每个专家维护一个**动态 bias** 加到 router logits 上——过载专家 bias 下调、饥饿专家上调，序列级统计驱动、**避免辅助损失对主干梯度的干扰**；配合细粒度专家（更多更小的专家）与共享专家（承载公共模式、保证基础能力），实现近均衡且不掉点。

**工程挑战（区分背没背过的关键）。**
- **显存不省**：所有专家权重必须全部驻留——671B FP16 ≈ 1.3TB，单机放不下，MoE 推理天然是多卡/多机问题；
- **通信瓶颈**：token 要跨卡送到对应专家，All-to-All 集合通信成为新瓶颈（EP，专家并行）；
- **批处理不友好**：专家负载不均导致算力浪费与 padding，需要 capacity 管理与 token drop/重分配策略；
- 训练不稳定（路由早期噪声大），需要更谨慎的初始化与损失配比。

#### 2.11 亚二次、混合与新范式架构（2024–2026 新考点）

**动机。** Attention 的 O(n²) 复杂度与随序列线性增长的 KV cache，是长上下文两大成本来源。一批"亚二次（sub-quadratic）"架构试图从根上解决它——"为什么不用 Mamba / attention 与状态空间怎么取舍"已是 2025–2026 的高频面试题。

**SSM 与线性注意力。**
- **状态空间模型（SSM）**：把序列建模成状态方程的离散化（`x_t = A·x_{t−1} + B·u_t`），每步只维护一个**固定大小的隐状态**——复杂度 O(n)、状态显存常数、可像 RNN 一样流式推理。**Mamba**（Gu & Dao, 2023, [arXiv:2312.00752](https://arxiv.org/abs/2312.00752)）的关键是**选择性机制**：参数 B/C 与步长 Δ 依赖输入内容，让模型能按内容取舍信息（这是它超越传统 LTI SSM 的地方），并用硬件感知的并行扫描完成训练；**Mamba-2**（2024）将其等价重构为"结构化半可分矩阵"（State Space Duality），与注意力共享更多算子、GPU 利用率更高。
- **线性注意力**：去掉 softmax，把 `QKᵀV` 改成右结合的 `φ(Q)·(φ(K)ᵀV)`，复杂度降为 O(n)，并可写成 RNN 式递推（推理时只维护一个 d×d 状态矩阵）。代表：Gated Linear Attention（**GLA**）、**DeltaNet**（用 delta 规则对联想记忆做"擦除-写入"更新）、**RWKV**。

**系统性短板（面试必答的取舍）。** 固定大小状态是对序列的**有损压缩**：亚二次模型在**精确召回（associative recall）、in-context copy（"复述前文出现过的字符串"）类任务上系统性弱于 Transformer**，多篇 2024 年的实证研究反复验证了这一点；纯 Mamba 模型的 in-context learning 能力也明显受限。这正是它们没有取代 Attention 的原因。

**可训练稀疏注意力：保精确检索的亚二次路线（2025 增量考点）。** 与"把历史压进固定状态"的线性路线正交：**不压缩，而是精确地选**——每个 query 只对被选中的 KV 块做标准 softmax 注意力，整体复杂度亚二次，但被选中 token 的信息**无损**：
- **NSA**（DeepSeek，Native Sparse Attention，ACL 2025 最佳论文）：压缩粗粒度 token + 选择性保留细粒度 token 块 + 滑动窗口，三分支门控融合；**端到端可训练**（而非推理期事后稀疏化），且按 GPU block 对齐设计、拿得到真实加速；
- **MoBA**（Moonshot）：上下文切块、gate 为每个 query 选 top 块——**MoE 思想搬进注意力**，可与全注意力无缝切换；
- **DSA**（DeepSeek-V3.2 的 lightning indexer）：轻量索引头为历史 token 打分、每个 query 只取 top-k 进注意力，把 MLA 稀疏化，已在生产模型落地——NSA→MoBA→DSA 是同一条线从论文走向生产。
与线性注意力的对比口径：**线性/SSM 是有损压缩状态，稀疏注意力是保留全部 KV、按需精确选取**——前者状态常数、省得更狠，后者保住精确召回能力，正面回应上一段的"系统性短板"。

**业界收敛到"混合架构"。** 主流做法是**少量注意力层 + 大量 SSM/线性层**：注意力层负责精确召回与 in-context 能力，线性层承担廉价的逐 token 处理，整体接近 O(n) 成本与常数级状态显存。代表：
- **Jamba**（AI21, 2024）：Mamba + Transformer 混合，支持 256K 上下文；
- **Nemotron-H**（NVIDIA, 2025）：Mamba-2 + 注意力混合家族；
- **Kimi Linear**（Moonshot, 2025）：自研 KDA（Kimi Delta Attention）线性注意力 + 稀疏 MLA 的混合；
- **Qwen3-Next**（2025）：大部分层用 Gated DeltaNet 线性注意力，按约 3:1 插入 Gated Attention 层。

**面试口径**："不是 Attention 不好，而是全 Attention 太贵；混合架构用少数注意力层买回精确检索能力，其余层走 O(n)。"

**另一条轴：扩散语言模型（非自回归）。** 与"亚二次"正交的新范式是**掩码扩散 LM**：训练时随机掩码 token、让模型用**双向注意力**并行去噪，推理时按 block 迭代解码（而非逐 token 自回归）。代表：**LLaDA**（2025，8B 开源掩码扩散 LM）、**Dream**（2025，开源扩散 LM，块并行解码吞吐显著高于同规模自回归模型）、**Mercury**（Inception Labs, 2025，面向代码，主打超高 tokens/s）。优势：天然双向上下文、块级并行解码、适合代码编辑与"挖空填充"式任务；短板：缺乏成熟的 KV cache / prefix cache 生态，可控生成与长程连贯性仍弱于自回归主流。目前是自回归路线的有力补充，而非替代。

#### VLM 架构基础（多模态 / GUI Agent 岗的前置知识）

**主流拼接范式（LLaVA 范式，先答这个）。** 绝大多数开源 VLM 是三段拼接：**视觉编码器**（CLIP/SigLIP 系 ViT，用图文对比学习预训练，输出的 patch 特征天然与语言语义对齐）→ **投影层**（把视觉特征映射进 LLM 的 embedding 空间：最简是 **MLP**（LLaVA 路线）；或用 **cross-attention Resampler**（Q-Former / Perceiver Resampler 类，用固定数量的可学习 query 把任意多 patch 压成定长 token，控制序列开销）→ **LLM 主干**（视觉 token 与文本 token 拼在同一序列里走标准自回归）。对 LLM 而言，图像就是"一段外语 token"。

**图像的 token 账与分辨率策略。** 一张图经 ViT 切 patch 后是**数百至数千个 token**（如 336×336、patch 14 → 576 token），高分辨率是主要成本来源。主流做法：**AnyRes / 切片**（LLaVA-NeXT 路线：原图切成若干子图各自过编码器 + 一张全局缩略图拼接）；**Qwen-VL 系的原生动态分辨率**：不切片、按原始分辨率直接产出变长 patch 序列，并用 **M-RoPE** 把位置编码分解为**时间 / 高 / 宽三个分量**——图像按二维坐标、视频再加时间维编码，文本退化为普通一维 RoPE，一套位置编码统一三种模态。

**两条路线之争。** **适配器路线**（上述拼接，复用成熟视觉编码器与 LLM，训练便宜，是主流）vs **早期融合**（Fuyu：不要独立视觉编码器，图像 patch 线性投影后直接进 LLM，结构最简、天然任意分辨率，但训练代价高、效果长期未成为主流）。

**训练两阶段。** ① **对齐预训练**：冻结视觉编码器与 LLM，只训投影层（图文 caption 对）；② **多模态指令微调**：解冻 LLM（常连同投影层，视觉编码器可选解冻），用多模态指令数据教会"看图对话/推理"。

**为什么 Agent 面试考这个**：GUI Agent 岗必问 VLM 结构，且**高分辨率支持是 GUI grounding 的前提**——截图里的按钮/输入框只占几十像素，低分辨率编码后信息直接丢失，AnyRes / 原生动态分辨率决定了模型"看不看得清屏幕"（GUI grounding 与坐标预测详见第 14 章）。

---

### 三、面试高频考点

| 考点 | 频率 | 考察重点 |
|---|---|---|
| Self-Attention 完整计算流程 + 为什么除 √d_k | ⭐⭐⭐ | 手推公式、复杂度、梯度视角 |
| KV Cache 原理 + 显存估算 + 优化手段全家桶 | ⭐⭐⭐ | 能当场算出 70B@8K 的 KV 大小；GQA/MLA/量化/Paged/投机采样 |
| Prefill vs Decode、compute-bound vs memory-bound | ⭐⭐⭐ | 一切推理优化问题的第一性原理 |
| RoPE 原理与长上下文扩展（PI/NTK/YaRN） | ⭐⭐⭐ | "相对位置怎么编码的"、频率分解直觉 |
| MQA/GQA/MLA 演进逻辑 | ⭐⭐⭐ | 显存视角、质量-成本折中 |
| Chinchilla 定律 + 为什么业界超训 | ⭐⭐⭐ | 训练 vs 推理成本的全局观 |
| RLHF vs DPO vs GRPO 的差异与取舍 | ⭐⭐⭐ | 目标函数、工程代价、各自失效模式 |
| 推理模型 RL：可验证奖励、PRM vs ORM | ⭐⭐⭐ | 信用分配、涌现思维链、2024-2026 主线 |
| FlashAttention 为什么快（且精确） | ⭐⭐ | IO-aware、online softmax |
| Tokenizer（BPE）原理、词表取舍、对成本/缺陷的影响 | ⭐⭐ | byte-level、中文效率、strawberry 类问题 |
| 解码参数（temperature/top-p）语义与 Agent 场景选型 | ⭐⭐ | 参数交互、结构化输出、循环问题 |
| Scaling Laws 三代演进 + 推理时计算 + 数据墙 | ⭐⭐ | 边际收益、新 scaling 轴 |
| MoE 路由/均衡 + 工程代价 | ⭐⭐ | 显存不减、All-to-All、DeepSeek 做法 |
| 投机采样为何无损 | ⭐⭐ | 接受-拒绝的数学保证、Medusa 近似无损的限定 |
| 亚二次与混合架构（Mamba/线性注意力）的取舍 | ⭐⭐ | O(n)+常数状态 vs 精确召回弱；为何收敛到混合 |
| R1-Zero vs R1 训练管线、规则化奖励 | ⭐⭐ | 纯 RL 涌现 vs 冷启动 SFT；R1 四阶段 |
| LoRA/QLoRA 原理与全参微调的取舍 | ⭐⭐ | 低秩假设、NF4/双重量化、单卡 48GB 调 65B 的账、multi-LoRA serving |
| 训练显存口算（16 字节/参数）与 ZeRO/TP/PP 选型 | ⭐⭐ | "70B 全参要多少卡"；节点内 TP、跨节点 PP、显存不够 ZeRO |
| FP8/FP4 低精度、基准饱和与污染检测 | ⭐ | blockwise scaling；MMLU-Pro/HLE/LiveCodeBench、Min-K%++ |
| 蒸馏 / SFT 数据量质量经验（LIMA）/ perplexity 的局限 | ⭐ | 对齐直觉、小模型路线 |

---

### 四、经典面试题与参考答案

#### Q1（基础）：请完整描述 self-attention 从输入到输出的计算流程，并解释为什么要除以 √d_k？

**答题思路**：按"投影 → 打分 → 缩放 → mask → softmax → 加权"六步走，顺带给复杂度，最后解释缩放。

**参考答案要点**：
1. 输入 X∈ℝ^(n×d) 经三个权重投影得 Q、K、V（多头则切 h 份并行）；
2. 打分 `S = QKᵀ`，除以 √d_k；
3. causal 场景加 mask（上三角置 −∞）；
4. 逐行 softmax 得注意力权重 A；
5. 输出 `O = A·V`，多头拼接后再过 W_O；
6. 复杂度：计算 O(n²d)；KV 缓存单层 O(n·d_head·H_kv)、全模型 O(n·L·H_kv·d_head)（完整显存公式见 Q2，注意不要只给单层口径）；
7. **缩放原因**：q、k 分量独立单位方差时点积方差为 d_k，值过大 → softmax 饱和 → 梯度消失、分布退化为 one-hot；除 √d_k 使方差回到 1。可补充：bf16 训练中这一步对数值稳定尤其关键。

#### Q2（基础/高频）：什么是 KV Cache？请估算 LLaMA-3-70B 在 8K 上下文下的 KV 显存，并列举优化手段。

**答题思路**：先讲"为什么需要"（自回归逐 token 生成，历史 K/V 重复计算太贵），再给公式，再分门别类列优化。

**参考答案要点**：
- **原理**：decode 阶段每步只有新 token 的 Q 是新的，历史 K/V 不变 → 缓存复用，**避免历史 K/V 的重复投影**：无缓存时每步要对整个前缀重算（注意力 O(t²d) + 投影 O(t·d²)），有缓存后降为注意力 O(t·d) + 投影 O(d²)。注意每步成本**仍随序列长度线性增长**（新 query 要对全部 t 个缓存 key 算点积）——缓存省的是重复计算，换来的是显存随序列线性增长，而非每步零成本。
- **公式**：`2 × L × H_kv × d_head × seq × bytes`。LLaMA-3-70B：2×80×8×128×8192×2B ≈ **2.5 GiB / 请求**（GQA 8 KV 头）；若是 MHA（64 头）则 20 GiB。
- **优化全家桶**：
  1. 结构层：GQA（共享 KV 头）、MLA（低秩潜变量缓存，省 ~93%）；
  2. 精度层：KV FP8（2×）/INT4 量化；
  3. 管理层：PagedAttention 去碎片、prefix caching 跨请求复用、KV 驱逐（H2O）、attention-sink 流式、CPU offload；
  4. 系统层：连续批处理、chunked prefill、prefill/decode 分离（DistServe）。
- **点睛**：长上下文 + 高并发下 KV 显存 > 权重显存，是推理系统第一瓶颈。

#### Q3（进阶/高频）：RoPE 和 BERT 的可学习绝对位置编码有什么本质区别？RoPE 为什么对相对位置友好？如何把 4K 模型扩展到 128K？

**答题思路**：从"置换不变性需要位置信号"起，讲清 RoPE 是"旋转 Q/K"而非"加向量"，相对位置来自旋转保内积，扩展方法按演进线讲。

**参考答案要点**：
- 可学习绝对 PE：位置向量直接加到 embedding，位置数固定（超出即越界），编码的是绝对坐标，两个位置的"关系"靠模型自己学；
- RoPE：按位置 m 对 Q/K 施加频率 `10000^(−2i/d)` 的旋转，`⟨q_m, k_n⟩` 只依赖 m−n → **相对位置内建于点积**；
- 扩展（核心共识：压低频、保高频）：PI 线性插值（需较多微调）→ NTK-aware 调基数（免微调、有限）→ **YaRN 分段频率处理 + attention 缩放**（少量微调，业界默认）→ LongRoPE/LongRoPE2 搜索式逐维因子（近无损到 2M）；
- 加分：提醒"窗口扩展 ≠ 长程能力"，要用 needle-in-a-haystack 与真实任务双重验证；并提另一条路线——attention sink + 滑动窗口做无限流式（StreamingLLM）。

#### Q4（进阶）：MQA、GQA、MLA 解决什么问题？各自代价是什么？

**参考答案要点**：
- 共同动机：decode 是带宽受限，KV cache 是显存大头，压缩 KV 直接提吞吐、降显存；
- MQA：1 组 KV 头，压得最狠但大模型上常见质量下降；
- GQA：分组共享，质量几乎无损 + 显存大幅下降，是性价比最优的工程默认（Llama-3、Mistral）；
- MLA：缓存低秩潜变量 + 解耦 RoPE key，实现 MHA 级质量 + 较 MHA 省 93.3% 显存（约 15× 压缩、最大生成吞吐提升约 5.76×；每 token KV 仍约为 MQA 的 2 倍，卖点是质量-显存比而非压过 MQA）；代价是算子复杂、需要定制 kernel，且上投影增加部分计算；
- 一句话总结：**这条演进线全部由推理经济学驱动，而非训练质量**。

#### Q5（进阶/高频）：讲讲 Chinchilla scaling law。既然最优是 ~20 tokens/param，为什么 LLaMA-3-70B 训了 200+ tokens/param？

**答题思路**：先陈述定律，再指出"定律的优化目标只含训练算力"，引出推理成本视角。

**参考答案要点**：
- Chinchilla：固定训练预算 C≈6ND，N 与 D 应同速扩展（≈20 tokens/param）；此前 GPT-3（约 1.7 tokens/param）严重欠训；
- 但 Chinchilla **不计算服务成本**。模型上线后推理 FLOPs ∝ N × 查询量，通常远超训练成本；
- 推理感知缩放（Sardar et al.《Should We Prioritize Research on Small Language Models?》, arXiv:2401.00448）：把推理纳入总账后，最优模型**更小、训得更久**——同等训练预算下，小模型的每 token 服务成本低得多，全生命周期更优；
- 附加：超训还有产品价值（小模型能端侧/低成本部署）；数据层面多 epoch 收益递减（~4 epoch 内可接受），且高质量数据接近"数据墙"（Villalobos et al. 外推：高质量语料约 2026–2032 耗尽、中点约 2028，属趋势性外推、有争议）；
- 现状：纯预训练 scaling 边际放缓（算力翻倍 ≈ 总损失相对降 5–6%），增量转向数据质量、后训练与**推理时计算**。

#### Q6（进阶/高频）：DPO 的核心思想是什么？相比 RLHF 省掉了什么？它有什么已知缺陷？

**答题思路**：从 RLHF 的 KL 约束最优解有闭式讲起，推出隐式奖励，给出损失式；然后讲工程收益与三个失效模式。

**参考答案要点**：
- 推导：KL 约束下最优策略 `π* ∝ π_ref·exp(r/β)` ⇒ `r = β·log(π/π_ref)`；代入 Bradley-Terry 偏好模型，RL 坍缩为二分类损失 `−log σ(βΔlogπ_w − βΔlogπ_l)`；
- 收益：砍掉独立 reward model 与 PPO 循环，训练只需 policy + reference 两个模型，超参少、稳定、便宜；家族扩展：SimPO（去 reference、长度归一化）、ORPO（并进 SFT 单阶段）；
- 缺陷：① likelihood displacement（相似的被拒/偏好答案对会误伤偏好答案）；② 离线方法，OOD 泛化常逊于在线 PPO（arXiv:2404.10719 的系统研究）；③ 对 reference 与数据分布偏移敏感，β 与数据质量调不好会过拟合偏好噪声；
- 实践：大厂常混用（LLaMA-3：在线 PPO + 离线 DPO）。

#### Q7（进阶）：GRPO 为什么去掉 critic？为什么它成了推理模型（R1 系）的标配？

**参考答案要点**：
- PPO 需要 value 网络估计优势，对 LLM（序列长、词表大）critic 与 policy 同量级，显存翻倍且难训；GRPO 对同一 prompt 采样一组输出，用**组内 z-score** `(r−μ)/σ` 直接当优势——**无需 critic/value 网络**（显存与工程大幅简化）。注意 GRPO 仍需要奖励信号：R1 路线下用规则化可验证奖励取代学习的 RM，但 GRPO 本身也可配合学出来的 RM；
- 与"可验证奖励"天然契合：数学/代码任务的对错可程序判定，奖励稠密客观，组内对比即可提供梯度信号；
- 结果：在大规模 RL 下自发涌现长思维链（反思、回溯、验证），这是 SFT 模仿不来的——**SFT 教格式，RL 教探索**；
- 加分：提 DAPO 的改进（clip-higher 鼓励探索、dynamic sampling 过滤无信息组、token-level loss）。

#### Q8（进阶）：投机采样为什么能保证输出分布与目标模型完全一致？什么情况下收益大/小？

**参考答案要点**：
- 机制：draft 模型猜 γ 个 token，target 一次前向并行验证；逐 token 以 `min(1, p_t/p_d)` 接受，首个拒绝处从 `norm(max(0, p_t − p_d))` 重采样，之后全部丢弃重生成；
- 该接受-拒绝方案（Leviathan et al. 2023）数学上证明合成分布恰为 p_target，**无损**；
- 收益 = 把 γ 次串行大模型 decode（每次读全部权重）压成 1 次；acceptance rate 越高越赚；
- 收益大：长输出、draft 与 target 分布接近（同族小模型）、代码/格式化文本（可预测性强，EAGLE 接受率可达 0.8+）；收益小：高温度采样、高熵开放生成、draft 太弱；
- 变体：Medusa（多头自猜，免 draft 模型）、EAGLE（特征层 draft）。**限定**：无损保证只属于带拒绝采样校正的标准方案；Medusa 的 typical acceptance 是近似无损的启发式，严格保分布需切到拒绝采样模式。

#### Q9（进阶）：MoE 相比 dense 模型的优势是什么？部署一个 671B MoE 有哪些工程难点？

**参考答案要点**：
- 优势：激活 37B 获得 671B 容量，FLOPs/质量比极高；细粒度专家 + 共享专家提升表达与均衡；专家自发专门化带来容量收益；
- 难点四连：① **显存不减**——全部专家须驻留，FP16 约 1.3TB，必须多机；② **All-to-All 通信**——token 跨卡路由，带宽与拓扑敏感；③ **负载不均**——专家并行下不均 = 算力浪费 + padding，需要 capacity 管理与（无辅助损失的）动态 bias 均衡；④ 训练不稳与 checkpoint/弹性扩缩容复杂；
- 结论：MoE 是"用通信和显存换算力效率"，推理侧尤其吃基建。

#### Q10（系统设计）：设计一个高并发 LLM 推理服务（支撑 Agent 产品），你会如何优化延迟与吞吐？

**答题思路**：先拆指标（TTFT / TPOT / 吞吐 / SLO 达成率），再按 prefill/decode 两阶段的物理约束分层给方案，最后落到 Agent 场景特性。

**参考答案要点**：
- **指标与物理约束**：prefill compute-bound（决定 TTFT），decode memory-bandwidth-bound（决定 TPOT）；batch 提吞吐但伤单请求延迟——一切权衡围绕它展开；
- **调度层**：连续批处理（请求级动态进出）；chunked prefill（长 prompt 切片与 decode 混跑，压 TTFT 毛刺）；prefill/decode 物理分离部署（DistServe/Splitwise，两类负载硬件画像不同）；
- **显存层**：PagedAttention 去碎片；**prefix caching**（Agent 的 system prompt + 工具 schema 高度重复，命中即省整个 prefill）；KV FP8 量化；超长请求 KV offload；
- **模型层**：权重量化（AWQ/GPTQ INT8/INT4）；GQA/MLA 模型选型；投机采样（对长输出 Agent 任务收益显著）；
- **Agent 专属**：低温度 + constrained decoding（xgrammar/JSON Schema）保证工具调用合法；多轮对话做 KV 复用与会话级缓存；失败重试升温重采样；
- **运维层**：按 SLO（P95 TTFT/TPOT）自动扩缩容；分优先级队列；token 级计量与成本看板。

#### Q11（开放）：temperature=0 时输出一定确定吗？Agent 的工具调用应该怎么设置解码参数？

**参考答案要点**：
- 不一定：T=0 多数框架走 argmax，但 GPU 浮点非结合性、batch 大小变化、不同 kernel/驱动都会导致 logits 微小差异，从而在接近的候选间翻转；同 seed 也不保证跨批确定性；
- 工具调用配方：T≈0～0.3、top-p=1、结构化约束（tool_choice / JSON Schema / grammar）兜底合法性、设置 stop 序列与最大工具调用轮数；
- 反直觉：纯 greedy 可能**死循环重复同一错误调用**——留微小随机性 + 重试时升温 + 幂等与去重，比一味追求确定性更稳；
- 可复现的正确姿势：固定 prompt 版本、模型版本、参数，记录 logprobs 做事后审计，而不是指望逐 bit 复现。

#### Q12（开放）："模型 perplexity 下降了，但下游评测没涨"，可能有哪些原因？

**参考答案要点**：
- 评测数据与预训练分布不匹配：损失降在被高频刷到的语料上，能力评测考察的是别处；
- **能力与对齐分离**：指令遵循、拒答、格式由后训练决定，预训练 loss 感知不到；
- 评测指标阶梯化造成"未到阈值不见涨"（emergence 幻觉的反面：连续指标可能一直在涨）；
- 过拟合 benchmark 风格的反面：数据污染会让评测虚高，loss 与评测双涨反而要警惕（去污染是否失效）；
- 分词差异：跨模型比 PPL 本身无效；
- 正确姿势：loss 只作训练健康度信号，决策以保留集任务评测 + 人工抽检为准。

#### Q13（进阶/热点）：推理模型的奖励该怎么设计？PRM 和 ORM 有什么区别？为什么 RL 能让模型"涌现"出思维链？

**答题思路**：从"奖励打在结果还是过程"切入讲清 ORM/PRM 的信用分配差异，再落到可验证奖励 + GRPO 为什么催生长思维链。

**参考答案要点**：
- **ORM**：只对最终答案给奖励。便宜、可程序判定（数学对答案、代码跑测试），但长链下信号稀疏，一步错整条链零梯度，难定位错误位置；
- **PRM**：对每个推理步骤给奖励（PRM800K 人工标、Math-Shepherd 蒙特卡洛估"该步通向正确解的概率"、ThinkPRM 生成式验证）。信号稠密、信用分配好，还能驱动 best-of-N / 步级搜索；代价是标注贵、误差沿链累积；
- **实践**：可验证任务上"ORM 起步 + 自动化过程监督增强"是主流；纯人工 PRM 难规模化；
- **为何涌现思维链**：GRPO + 可验证奖励下，模型为拿到稀疏的终局奖励，会自发把"思考"写成长链以增加成功率——探索（试错、回溯、自我验证）被奖励塑造出来，这是只模仿示范的 SFT 给不了的（**SFT 教格式，RL 教探索**）；
- 加分：提 DAPO 的 clip-higher/dynamic sampling 防止探索坍缩、reward hacking（Goodhart）与奖励过优化（Gao et al.）需要 KL 调控与 red-teaming。

---

### 五、易错点 · 反直觉点

1. **"Attention 取代了一切"**：FFN 占约 2/3 参数，大量事实知识存在 FFN 里；Attention 主要做上下文信息路由。
2. **RoPE 是"把位置向量加到 embedding 上"**：错。它旋转 Q/K，相对位置来自旋转保内积；这也是所有长上下文扩展方法操作"频率"而非"位置"的原因。
3. **FlashAttention 是近似算法**：错。它数值精确，加速来自减少 HBM 访存（IO-aware）与 online softmax，不是稀疏化。
4. **KV Cache 最大的受益者是训练**：KV Cache 是纯推理技术；训练用 teacher forcing 一次前向覆盖所有前缀。
5. **长上下文 = 会用长上下文**：NIAH 通过不代表跨文档推理强；"lost in the middle"（中段信息利用率下降）至今部分存在。
6. **MoE 省显存**：省的是 FLOPs 不是显存，全部专家必须驻留；671B MoE 比 37B dense 难部署得多。
7. **DPO 全面优于 RLHF/PPO**：DPO 更便宜稳定，但有 likelihood displacement 等失效模式，OOD 泛化常不如在线 PPO；大厂多为混用。
8. **Chinchilla 最优 = 生产最优**：Chinchilla 不算推理账；考虑服务成本后"小模型超训"才是全局最优——这也是业界集体违反 Chinchilla 比例的原因。
9. **Scaling 出 emergent abilities 是质变**：相当部分"涌现"是阶梯式指标造成的人为不连续（Schaeffer et al., 2023），换连续指标多为平滑曲线。
10. **temperature 是"创造力旋钮"、和 top-p 可以一起调**：它本质是熵缩放；与 top-p/top-k 存在交互，官方建议只调其一；T=0.01 采样 ≠ greedy。
11. **beam search 总是更好的解码**：在开放生成中它系统性产出短、重复、安全的退化文本；它属于翻译/受控生成时代。
12. **投机采样会牺牲质量换速度**：无损——接受-拒绝方案保证目标分布精确一致，只是把串行验证变并行。
13. **中文和英文"字数相同则 token 成本相同"**：不同词表差异巨大，旧词表中文可达英文 2–3 倍 token 消耗；做成本估算必须实测。
14. **perplexity 可以跨模型比较**：分词不同，NLL 的"单位"不同，直接比没有意义（应比 BPC 或统一分词）。
15. **SFT 教给模型新知识**：SFT 主要对齐行为分布与格式（LIMA：千条精数据近似 RLHF 效果）；知识增量主要靠预训练、RAG 或蒸馏。
16. **RLHF 训完模型就"安全"了**：reward hacking（Goodhart 定律）——模型会学会讨好 reward model 而非真正符合意图；代理奖励一路上涨往往是过优化信号，需要 KL 调控、RM 集成与持续 red-teaming。
17. **INT4/INT8 量化一定明显掉点**：现代 AWQ/GPTQ 在大模型上常可做到近无损（尤其 INT8）；真正脆弱的是小模型与极端 2–3bit。区分权重量化（离线一次性）与 KV 量化（在线随序列增长）。
18. **推理模型思考越长越好**：思维链长度与正确率并非单调正相关，过度思考会退化；s1 等用 budget forcing 主动截断，"最优推理预算"随问题难度变化（Snell et al.）。
19. **蒸馏只是"抄答案"**：logits 级蒸馏传递的是教师分布的类间结构信息；它能把昂贵的 RL/推理能力廉价铺到端侧小模型，但学生难超教师上界。
20. **PRM 一定比 ORM 好**：PRM 信号更稠密，但步级标注贵、误差沿链累积、且"过程正确"未必等价"答案正确"；可验证任务上 ORM + 自动化过程监督往往是更省的工程选择。
21. **"Mamba 会取代 Transformer" / "R1 是纯 RL 不要 SFT"**：亚二次架构在精确召回 / in-context copy 上系统性弱于注意力，业界收敛到"少量注意力层 + 线性层"的混合架构；同理，纯 RL 涌现推理的是 **R1-Zero**，发布的 **R1** 用的是含冷启动 SFT 的四阶段流水线。
22. **KV Cache 让每步计算变成 O(1)**：它只消除历史 K/V 的重复投影（投影 O(t·d²)→O(d²)），新 query 对全部历史 key 的注意力仍是 O(t·d)——每步成本仍随序列线性增长，这也是 decode 带宽受限的根源。
23. **权重绑定是大模型标配**：恰恰相反，LLaMA/Mistral/DeepSeek 等大模型均不绑定（`tie_word_embeddings=False`）；绑定是 GPT-2、Gemma 等小模型的常见做法。
24. **LoRA 与全参微调只差在"省不省钱"**：LoRA 的本质是低秩适配器——任务增量低秩假设成立时（格式、风格、领域话术对齐）效果接近全参，但**学新知识、提升推理能力偏弱**；Agent 的 tool-call 格式对齐用 LoRA 通常够，推理能力提升要靠全参/RL；把 r 调大也不等价于全参（优化动态不同）。

---

### 六、推荐资源

1. **《Attention Is All You Need》+ The Annotated Transformer** — 原始论文（arXiv:1706.03762）配合 Harvard NLP 的逐行代码注释，是手推 Attention 的最佳组合。
   [http://nlp.seas.harvard.edu/annotated-transformer/](http://nlp.seas.harvard.edu/annotated-transformer/)
2. **Andrej Karpathy：Let's build GPT / Intro to LLMs（视频）+ nanoGPT** — 从零手写一个 GPT，涵盖 tokenization、attention、KV cache、采样；面试前过一遍代码胜过读十篇博客。
   [https://github.com/karpathy/nanoGPT](https://github.com/karpathy/nanoGPT)
3. **DeepSeek-V3 Technical Report（arXiv:2412.19437）** — 一篇同时覆盖 MLA、MoE、无辅助损失负载均衡、FP8 训练的工业级报告，2024-2026 架构题的"标准答案出处"。
   [https://arxiv.org/abs/2412.19437](https://arxiv.org/abs/2412.19437)
4. **Chinchilla 论文 + 推理感知缩放 follow-up** — 理解 scaling 争论的两篇对读材料：Hoffmann et al. 2022《Training Compute-Optimal Large Language Models》（arXiv:2203.15556）与 Sardar et al. 2024《Should We Prioritize Research on Small Language Models?》（[arXiv:2401.00448](https://arxiv.org/abs/2401.00448)）；再配 Villalobos et al. 的数据墙外推（[arXiv:2211.04325](https://arxiv.org/abs/2211.04325)，ICML 2024）理解"为何纯预训练 scaling 放缓"。
5. **FlashAttention 论文 + vLLM/PagedAttention 论文** — 训练侧与推理侧各一篇奠基工程论文：Dao et al. 2022（arXiv:2205.14135）、Kwon et al. SOSP'23（[arXiv:2309.06180](https://arxiv.org/abs/2309.06180)），配合 [vLLM 官方文档](https://docs.vllm.ai/en/latest/)动手跑一遍。
6. **DeepSeek-R1（arXiv:2501.12948）+ PRM 综述** — 推理模型路线的一手材料：GRPO、可验证奖励、思维链涌现，配 [A Survey of Process Reward Models（arXiv:2510.08049）](https://arxiv.org/abs/2510.08049) 理解 PRM/ORM 的信用分配之争。
7. **Stanford CS336: Language Modeling from Scratch（2025）/ Hugging Face LLM Course** — 2025 年最好的系统课程之一，从数据、训练到推理全链路手搓；HuggingFace 的[后训练算法指南](https://huggingface.co/blog/karina-zadorozhny/guide-to-llm-post-training-algorithms)是 PPO/DPO/GRPO 对比的高质量速读。
   [https://stanford-cs336.github.io/spring2025/](https://stanford-cs336.github.io/spring2025/) ｜ [https://huggingface.co/learn/llm-course](https://huggingface.co/learn/llm-course)
