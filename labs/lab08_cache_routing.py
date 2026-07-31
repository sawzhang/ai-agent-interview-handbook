#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab08_cache_routing.py —— 语义缓存与大小模型路由

【对应知识域】工程化与生产部署（第10章）
【主题】Semantic Cache（语义缓存）与 Model Routing（大小模型路由）

## 实验目的
LLM 调用是生产环境 AI 应用中最大的成本与延迟来源。本实验用纯 Python 标准库实现
两个最常用的生产优化组件，让读者读懂原理而不只是跑通：

1. 语义缓存：传统缓存靠「prompt 字符串精确相等」命中，稍改几个字就失效。
   语义缓存把问题向量化（embedding），用向量相似度判断「是否问过差不多的问题」，
   命中即直接返回历史答案、跳过模型调用 → 省钱、降延迟。
2. 大小模型路由器：并非所有问题都需要大模型。用启发式（关键词 + 文本长度）
   估计任务难度，简单任务交给小模型（便宜、快），难任务才路由到大模型（贵、强）。

## 核心概念
- 向量化 / embedding：生产环境用专门的 embedding 模型（如 text-embedding-3-small）；
  本实验为教学用极简「字/词 词袋向量」代替，原理完全一致：文本 → 高维稀疏向量。
- 余弦相似度：cos = A·B / (|A|·|B|)，取值 [0, 1]，越接近 1 语义越相近。
- 缓存阈值（threshold）：太高 → 命中少、省不到钱；太低 → 误命中、答非所问（质量事故）。
- 路由启发式：关键词 + 长度是最朴素实现；生产中常用「难度小分类器」或
  「级联 cascade：小模型先答，置信度不足再升级大模型」。

## 如何运行
    python3 /Users/sawzhang/code/agent-interview/labs/lab08_cache_routing.py
无第三方依赖、无网络、无 API key。所有「模型」均为确定性 MockLLM：
相同输入永远得到相同输出，保证缓存复用的一致性与实验可复现。

## 思考题（面试延伸）
1. 语义缓存依赖 embedding 模型，而 embedding 本身也有成本、还要多一次网络往返。
   如何评估「加缓存」的 ROI？相似度阈值该如何选取与调优？阈值过低会引发什么生产事故？
2. 关键词 + 长度的启发式路由很粗糙、容易误判。请给出至少两种改进方案
   （提示：难度分类器、小模型先答 + 置信度升级的级联、按用户等级 / SLA 路由）。
3. 在多轮对话或 Agent 场景下引入语义缓存，会多出哪些难题？
   （提示：答案依赖上下文，缓存 key 如何包含对话状态？时效性问答如何失效？一致性如何保证？）
"""

import hashlib
import math
import re
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# 第 1 部分：极简「向量化」工具
# ---------------------------------------------------------------------------
# 生产里这一步由 embedding 模型完成（文本 → 稠密向量）。
# 教学中用「词袋向量 Bag-of-Words」代替：
#   - 中文按「字」切分，英文/数字按「词」切分；
#   - 统计每个 token 的出现次数，得到一个稀疏字典向量。
# 它已经能抓住「用词重叠程度」这一语义相似度的主要信号，足以演示缓存命中。
_TOKEN_RE = re.compile(r"[一-龥]|[A-Za-z0-9]+")


def tokenize(text: str) -> list:
    """中文按字、英文按词切分，并统一小写。"""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def bow_vector(text: str) -> dict:
    """词袋向量：{token: 出现次数}。"""
    vec = {}
    for t in tokenize(text):
        vec[t] = vec.get(t, 0) + 1
    return vec


def cosine_similarity(a: dict, b: dict) -> float:
    """余弦相似度 = 点积 / (模长之积)。遍历较短的向量以省时。"""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# 第 2 部分：MockLLM —— 确定性模拟模型（零依赖、零网络）
# ---------------------------------------------------------------------------
class MockLLM:
    """
    模拟一个大语言模型。
    - cost_per_call：每次调用的美元成本（大模型远贵于小模型）；
    - latency_ms：每次调用的模拟耗时（大模型远慢于小模型）；
    - generate() 用输入哈希生成「签名」，保证确定性：
      同一 prompt + 同一模型 ⇒ 永远相同的答案，这样缓存复用才合理且实验可复现。
    """

    def __init__(self, name: str, cost_per_call: float, latency_ms: int, quality_tag: str):
        self.name = name
        self.cost_per_call = cost_per_call
        self.latency_ms = latency_ms
        self.quality_tag = quality_tag
        self.calls = 0  # 统计真实被调用次数

    def generate(self, prompt: str) -> str:
        self.calls += 1
        sig = hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8]
        return f"[{self.name}·{self.quality_tag}答案 sig={sig}] 针对「{prompt}」的要点回答：……"


# ---------------------------------------------------------------------------
# 第 3 部分：SemanticCache —— 语义缓存
# ---------------------------------------------------------------------------
class SemanticCache:
    """
    语义缓存：
    - lookup()：把新问题和库里每条历史问题算余弦相似度，取最大值；
      若 >= threshold 判定「语义命中」，直接返回历史答案（跳过模型调用）。
    - store()：未命中时，把新问题及其答案连同向量一起存入库。
    注意阈值权衡：threshold 越高越严格（省钱少但安全），越低越激进（省得多但可能答非所问）。
    """

    # 本地向量计算的「象征性延迟」，远小于任何真实模型调用
    LOCAL_LOOKUP_MS = 1

    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold
        self.entries = []  # 每项: (prompt, vector, response)
        self.hits = 0
        self.misses = 0

    def lookup(self, prompt: str):
        """返回 (response 或 None, 最高相似度, 命中的原问题)。"""
        vec = bow_vector(prompt)
        best_sim, best_entry = 0.0, None
        for entry in self.entries:
            sim = cosine_similarity(vec, entry["vector"])
            if sim > best_sim:
                best_sim, best_entry = sim, entry
        if best_sim >= self.threshold and best_entry is not None:
            self.hits += 1
            return best_entry["response"], best_sim, best_entry["prompt"]
        self.misses += 1
        return None, best_sim, None

    def store(self, prompt: str, response: str) -> None:
        self.entries.append(
            {"prompt": prompt, "vector": bow_vector(prompt), "response": response}
        )


# ---------------------------------------------------------------------------
# 第 4 部分：ModelRouter —— 大小模型路由器
# ---------------------------------------------------------------------------
# 「难任务」信号词：出现这些词，通常意味着需要推理/分析能力 → 大模型。
HARD_KEYWORDS = (
    "分析", "设计", "证明", "推导", "评估", "比较", "对比",
    "架构", "推理", "为什么", "原理", "优化",
)


class ModelRouter:
    """
    启发式难度估计 + 路由：
      score = 2 × 命中难词数 + min(文本长度 // 25, 2)  # 长 prompt 往往更复杂
      score >= hard_threshold ⇒ 路由到大模型(expensive)，否则小模型(cheap)。
    生产改进方向：用一个小分类器预测难度，或「级联」——小模型先答，
    自评置信度低再升级大模型（用一次廉价调用换取质量兜底）。
    """

    def __init__(self, cheap: MockLLM, expensive: MockLLM, hard_threshold: int = 2):
        self.cheap = cheap
        self.expensive = expensive
        self.hard_threshold = hard_threshold
        self.route_log = []  # (prompt, score, 命中难词, 选中模型名)

    def difficulty_score(self, prompt: str):
        hit_kw = [kw for kw in HARD_KEYWORDS if kw in prompt]
        score = 2 * len(hit_kw) + min(len(prompt) // 25, 2)
        return score, hit_kw

    def route(self, prompt: str) -> MockLLM:
        score, hit_kw = self.difficulty_score(prompt)
        model = self.expensive if score >= self.hard_threshold else self.cheap
        self.route_log.append((prompt, score, hit_kw, model.name))
        return model


# ---------------------------------------------------------------------------
# 第 5 部分：OptimizedPipeline —— 组装生产路径「先查缓存，未命中再路由」
# ---------------------------------------------------------------------------
@dataclass
class HandleResult:
    prompt: str
    from_cache: bool
    model_name: str     # 命中的模型名；缓存命中时为 "-"
    response: str
    cost: float
    latency_ms: int
    similarity: float   # 与最相似历史问题的相似度
    difficulty: int     # 路由难度分（缓存命中时不路由，记 -1）


class OptimizedPipeline:
    """
    请求处理主链路（生产中最常见的顺序）：
      1) 先查语义缓存：命中 ⇒ 0 成本、~1ms 返回；
      2) 未命中 ⇒ 由路由器决定用大/小模型，真实产生成本与延迟；
      3) 把新答案写回缓存，供后续相似问题复用。
    """

    def __init__(self, cache: SemanticCache, router: ModelRouter):
        self.cache = cache
        self.router = router
        self.total_cost = 0.0
        self.total_latency_ms = 0

    def handle(self, prompt: str) -> HandleResult:
        # ① 缓存优先
        cached, sim, _hit_prompt = self.cache.lookup(prompt)
        if cached is not None:
            latency = SemanticCache.LOCAL_LOOKUP_MS
            self.total_latency_ms += latency
            return HandleResult(prompt, True, "-", cached, 0.0, latency, sim, -1)

        # ② 未命中 → 路由到合适模型
        model = self.router.route(prompt)
        score = self.router.route_log[-1][1]
        response = model.generate(prompt)
        self.total_cost += model.cost_per_call
        self.total_latency_ms += model.latency_ms

        # ③ 写回缓存
        self.cache.store(prompt, response)
        return HandleResult(prompt, False, model.name, response,
                            model.cost_per_call, model.latency_ms, sim, score)


# ---------------------------------------------------------------------------
# 第 6 部分：演示与自检
# ---------------------------------------------------------------------------
def main():
    print("=" * 68)
    print("实验 lab08：语义缓存 + 大小模型路由（纯标准库 / MockLLM）")
    print("=" * 68)

    # 两个模拟模型：小模型便宜快，大模型贵而强
    cheap = MockLLM("small-1B", cost_per_call=0.001, latency_ms=200, quality_tag="简版")
    expensive = MockLLM("large-70B", cost_per_call=0.030, latency_ms=2500, quality_tag="深度")

    cache = SemanticCache(threshold=0.80)
    router = ModelRouter(cheap, expensive, hard_threshold=2)
    pipe = OptimizedPipeline(cache, router)

    # 一批请求：故意包含
    #   - 完全重复 / 措辞相近的问题 → 触发语义缓存命中；
    #   - 简单任务（寒暄/翻译/短句）→ 路由到小模型；
    #   - 复杂任务（分析/证明/比较）→ 路由到大模型。
    requests = [
        "法国的首都是什么？",
        "请问，法国的首都到底是什么",                      # 与上一句语义相近 → 期望命中缓存
        "法国的首都是什么？",                              # 完全重复 → 必定命中缓存
        "分析微服务架构的优缺点，并为高并发电商系统设计一套演进方案",  # 难 → 大模型
        "请分析微服务架构的优缺点，并设计一套演进方案",        # 与上一句语义相近 → 期望命中缓存
        "翻译：hello world",                              # 简单 → 小模型
        "推荐一本书",                                     # 简单 → 小模型
        "证明素数有无穷多个，并推导素数定理相关的估计界",    # 难 → 大模型
        "今天的天气怎么样",                                # 简单 → 小模型
        "比较 Python 与 Rust 的差异，并评估它们在 AI 基础设施中的适用性",  # 难 → 大模型
        "请问今天的天气怎么样呢",                          # 与第 9 句相近 → 期望命中缓存
        "写一首诗",                                       # 简单 → 小模型
    ]

    # ---- 步骤 1：逐条处理，打印每一步决策 ----
    print("\n【步骤 1】逐条处理请求（缓存优先，未命中再路由）")
    print("-" * 68)
    results = []
    for i, prompt in enumerate(requests, 1):
        r = pipe.handle(prompt)
        results.append(r)
        short = prompt if len(prompt) <= 26 else prompt[:26] + "…"
        if r.from_cache:
            print(f"  [{i:2d}] ⚡缓存命中 sim={r.similarity:.3f} | 成本 $0.0000 "
                  f"| {r.latency_ms}ms | {short}")
        else:
            print(f"  [{i:2d}] 🤖调用 {r.model_name:<9} | 成本 ${r.cost:.4f} "
                  f"| {r.latency_ms}ms | 难度分={r.difficulty} | {short}")

    # ---- 步骤 2：成本节省报告 ----
    n = len(requests)
    hit_rate = cache.hits / n
    baseline_cost = n * expensive.cost_per_call        # 无优化：全部走大模型、无缓存
    # 假想「只路由、不缓存」：对全部请求做难度路由（difficulty_score 是纯函数，可离线重算）
    routing_only_cost = sum(
        (expensive if router.difficulty_score(p)[0] >= router.hard_threshold else cheap).cost_per_call
        for p in requests
    )
    baseline_latency = n * expensive.latency_ms
    avg_latency = pipe.total_latency_ms / n
    saved = baseline_cost - pipe.total_cost
    saved_pct = saved / baseline_cost * 100

    print("\n【步骤 2】成本节省报告")
    print("-" * 68)
    print(f"  总请求数          : {n}")
    print(f"  缓存命中          : {cache.hits} 次（命中率 {hit_rate:.1%}，阈值 {cache.threshold}）")
    print(f"  真实模型调用      : {cheap.calls + expensive.calls} 次"
          f"（小模型 {cheap.calls} 次 + 大模型 {expensive.calls} 次）")
    print(f"  ① 无优化(全大模型): ${baseline_cost:.4f}，总延迟 {baseline_latency}ms")
    print(f"  ② 仅路由(无缓存)  : ${routing_only_cost:.4f}")
    print(f"  ③ 缓存+路由(本方案): ${pipe.total_cost:.4f}，平均延迟 {avg_latency:.0f}ms/请求")
    print(f"  >>> 相对基线节省  : ${saved:.4f}（{saved_pct:.1f}%），"
          f"平均延迟下降 {(1 - avg_latency / expensive.latency_ms) * 100:.1f}%")

    # ---- 步骤 3：自检（assert）----
    print("\n【步骤 3】自检断言")
    print("-" * 68)

    # (a) 缓存命中率 > 0，确实省下了成本
    assert cache.hits > 0 and hit_rate > 0, "缓存应当至少命中一次"
    print(f"  [1] 缓存命中率 = {hit_rate:.1%} > 0 ✓")

    # (b) 优化后总成本严格低于「全部走大模型」的基线
    assert pipe.total_cost < baseline_cost, "优化后成本应低于无优化基线"
    print(f"  [2] 优化成本 ${pipe.total_cost:.4f} < 基线 ${baseline_cost:.4f} ✓")

    # (b2) 缓存是在路由之上的额外节省：缓存+路由 ≤ 仅路由
    assert pipe.total_cost < routing_only_cost, "缓存应在路由基础上进一步降本"
    print(f"  [2b] 缓存+路由 ${pipe.total_cost:.4f} < 仅路由 ${routing_only_cost:.4f} ✓")

    # (c) 所有被判定为「难」的请求都被路由到大模型
    hard = [(p, s, m) for (p, s, _kw, m) in router.route_log if s >= router.hard_threshold]
    assert hard, "应当存在被判定为难的请求"
    assert all(m == expensive.name for (_p, _s, m) in hard), "难任务必须路由到大模型"
    print(f"  [3] {len(hard)} 个难任务全部路由到 {expensive.name} ✓")
    for p, s, m in hard:
        short = p if len(p) <= 22 else p[:22] + "…"
        print(f"        - 难度分 {s} → {m}：{short}")

    # (d) 缓存复用一致性：命中返回的答案与原始写入答案一致（MockLLM 确定性保证）
    assert results[2].from_cache and results[2].response == results[0].response, \
        "完全相同的问题命中缓存后，答案应与首次调用一致"
    print("  [4] 缓存复用答案与首次生成一致 ✓")

    # (e) 大模型实际调用次数 = 难任务数（简单任务没有浪费大模型）
    assert expensive.calls == len(hard), "大模型只应被难任务调用"
    print(f"  [5] 大模型调用 {expensive.calls} 次 == 难任务数 {len(hard)}，简单任务零浪费 ✓")

    print("\n✅ 自检通过")


if __name__ == "__main__":
    main()
