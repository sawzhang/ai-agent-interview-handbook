#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================
Lab 10 · 自适应 RAG：让 top-K 随问题难度动态伸缩（几何级数扩容）
========================================================================

【对应知识域】
    第 4 章 · Memory 系统与 RAG —— §2.5「动态上下文规模」

【实验目的】
    大多数 RAG 实现把 top-K 拍成一个常数（top-5 之类），但**问题难度是
    逐 query 变化的**：简单事实题一个块就够，疑难题给十个块也未必够。
    固定 K 必然两头不讨好——对简单题浪费 token，对难题召回不足。

    本实验用纯标准库跑通"拒答驱动的几何级数扩容"，并**把省下来的
    token 真正算出来**，让"自适应比固定 K 便宜"从口号变成数字：

        k=1 作答 ──不知道──▶ k=2 ──不知道──▶ k=4 ──不知道──▶ k=8 …

【核心概念】
    1. 几何级数扩容（geometric expansion）：每次重试把文档数**翻倍**而
       不是加一。三个性质：
         · 基线成本极低——多数问题在 k=1 就收敛；
         · 串行调用数对最终规模呈**对数**（扩到 64 块只要 7 次调用：
           k=1,2,4,8,16,32,64——log₂64=6 是扩容次数，首次调用要另算）；
         · 总成本被最后一次摊掉——几何级数下累计约为最后一次的
           k/(k-1) 倍（k=2 时 ≈ 2 倍）。线性递增则是 O(n) 次调用、
           累计成本爆炸，本实验第 3 个场景会把这个对比跑出来。
    2. 拒答信号（refusal）：扩容的触发器不是某个置信度分数，而是**模型
       自己说"我不知道"**。等于把置信度估计外包给了模型的拒答校准。
    3. **校准依赖 = 本方法的失效条件（本实验最重要的一课）**：如果模型
       倾向于"瞎猜也不承认不知道"，扩容将**永不触发**，机制静默退化成
       "永远只用 1 个块"——而且成功率指标看上去可能还更好看。场景四用
       一个"过度自信"的 MockLLM 复现这个陷阱。
    4. 与另一个同名概念区分：学术界的 Adaptive-RAG（Jeong et al.,
       NAACL 2024）是**用小分类器按 query 复杂度路由**"不检索/单步/
       多步"，调的是检索策略、发生在检索之前、需要训练；本实验的
       几何扩容调的是**上下文规模**、发生在生成之后、零训练。
       两者正交，可叠加。面试提到 "Adaptive RAG" 务必指明是哪一种。

【如何运行】
    cd labs && python3 lab10_adaptive_rag.py
    依次演示四个场景：
      场景一：简单题在 k=1 收敛（自适应的省钱来源）
      场景二：难题逐级扩容 1→2→4→8（自适应的召回来源）
      场景三：整套评估集上 自适应 vs 固定K=8 vs 线性+1 的 token 账
      场景四：模型拒答校准失效时，机制如何静默退化（反面教材）
    结尾用 assert 自检，全部通过打印 "✅ 自检通过"。

【思考题（面试延伸）】
    1. 为什么是"翻倍"而不是"每次加一"？场景三已经把 `linear_schedule`
       的账跑出来了；再把 `geometric_schedule` 的 ratio 从 2 改成 3 试试，
       看调用次数与累计 token 各自怎么变。
       （提示：调用次数 ∝ log_r(K)，累计成本 ∝ r/(r-1)，二者反向——
       倍率越大越省调用次数，但每次多带的文档也越多。）
    2. 场景四暴露的失效是"静默"的——线上怎么发现？本实验记录了
       `expansion_rate`（扩容触发率），为什么说它突然归零就是校准坏了？
       你还会加哪些监控？（提示：拒答率、k 的分布、人工抽检忠实度。）
    3. 每次重试都把上一轮的文档一起重发（overlapping），能不能改成
       "只发没试过的新文档"以省 token？想想为什么原论文实测**非重叠
       策略更差**——最相关的那几篇即使不够用，也仍然是必需的。
    4. 本实验的重试是串行的，延迟随扩容次数线性增长。高价值/低延迟
       容忍的场景该怎么改？（提示：对预判为难的 query 直接从 k=4 起步，
       即"复杂度路由 + 几何扩容"的叠加——正好是上面两个 Adaptive RAG
       的组合。）
========================================================================
"""

import math
import re
import zlib
from dataclasses import dataclass, field

# ── 语料：每篇文档一个知识点，doc_id 用于精确断言 ──────────────────────

CORPUS: list[tuple[str, str]] = [
    ("d01", "RAG 的全称是检索增强生成，把外部知识检索回来拼进提示词再让模型作答。"),
    ("d02", "向量检索用余弦相似度衡量语义接近程度，只看方向不看长度。"),
    ("d03", "BM25 是稀疏检索的代表，靠词频饱和与逆文档频率打分，擅长专有名词。"),
    ("d04", "混合检索把稠密与稀疏两路召回结果用 RRF 融合，经验常数取 60。"),
    ("d05", "重排器是交叉编码器，逐对打分精度高，是性价比最高的一环。"),
    ("d06", "分块大小的经验区间是 128 到 512 个 token，必须在自己的评估集上调。"),
    ("d07", "幻觉指模型生成了没有证据支持的内容，忠实度指标专门度量这件事。"),
    ("d08", "上下文中段的信息容易被忽略，这个位置偏置现象叫做 lost in the middle。"),
    ("d09", "嵌入模型升级必须全量重嵌，新旧向量不可混用，否则召回会莫名塌方。"),
    ("d10", "索引里删除传播最容易遗漏，残留的幽灵块会把已下线的内容当证据引用。"),
    ("d11", "提示词缓存让稳定前缀的重复读取变便宜，命中价约为常规输入价的十分之一。"),
    ("d12", "图检索先抽实体建图再做社区摘要，擅长需要跨文档聚合的宏观问题。"),
]

DOC_TEXT = dict(CORPUS)
REFUSAL = "我无法从给定材料中找到答案。"

# ── 极简检索器：词袋 + 哈希技巧 + 余弦（与 lab03 同构，零依赖）──────────

DIM = 256


def tokenize(text: str) -> list[str]:
    """中文按字切、英文数字按词切——中文无空格，字级切分零 OOV。"""
    return re.findall(r"[a-zA-Z]+|\d+|[一-鿿]", text.lower())


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    for tok in tokenize(text):
        vec[zlib.crc32(tok.encode("utf-8")) % DIM] += 1.0
    return vec


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return 0.0 if na == 0 or nb == 0 else dot / (na * nb)


class Retriever:
    """一次性算好文档向量，检索时返回按相似度降序的 doc_id 列表。"""

    def __init__(self, corpus: list[tuple[str, str]]) -> None:
        self.doc_ids = [d for d, _ in corpus]
        self.vectors = {d: embed(t) for d, t in corpus}

    def rank(self, query: str) -> list[str]:
        qv = embed(query)
        scored = [(d, cosine(qv, self.vectors[d])) for d in self.doc_ids]
        # 相似度降序；同分时按 doc_id 保证结果确定可复现
        scored.sort(key=lambda x: (-x[1], x[0]))
        return [d for d, _ in scored]

    def top_k(self, query: str, k: int) -> list[str]:
        return self.rank(query)[:k]


# ── Mock LLM：证据在上下文里就答，不在就拒答 ──────────────────────────

def count_tokens(text: str) -> int:
    """token 计数的教学代理：中文近似按字计。真实系统请用模型自带 tokenizer。"""
    return len(tokenize(text))


@dataclass
class Question:
    text: str
    evidence: str       # 回答本题所必需的 doc_id
    answer: str


class MockLLM:
    """确定性 Mock：上下文含 evidence 才作答，否则**如实拒答**。

    与 llm_client.QwenLLM 同构（chat/__call__），可直接替换成真实模型。
    """

    name = "校准良好"

    def __init__(self) -> None:
        self.calls = 0
        self.prompt_tokens = 0     # 整条 prompt（含每次都要重发的固定指令前缀）
        self.context_tokens = 0    # 只算检索material，即"上下文规模"本身

    def chat(self, question: Question, doc_ids: list[str]) -> str:
        context = self.build_context(doc_ids)
        prompt = self.build_prompt(question, doc_ids)
        self.calls += 1
        self.prompt_tokens += count_tokens(prompt)
        self.context_tokens += count_tokens(context)
        return self.respond(question, doc_ids)

    __call__ = chat

    @staticmethod
    def build_context(doc_ids: list[str]) -> str:
        return "\n".join(f"[{d}] {DOC_TEXT[d]}" for d in doc_ids)

    @classmethod
    def build_prompt(cls, question: Question, doc_ids: list[str]) -> str:
        return (
            "仅依据以下材料回答；材料不足以支撑答案时，必须回答"
            f"「{REFUSAL}」，不要猜测。\n\n材料：\n{cls.build_context(doc_ids)}"
            f"\n\n问题：{question.text}"
        )

    def respond(self, question: Question, doc_ids: list[str]) -> str:
        return question.answer if question.evidence in doc_ids else REFUSAL


class OverconfidentLLM(MockLLM):
    """过度自信的模型：证据不足时不拒答，而是拿手上第一篇material硬编一个。

    这不是虚构的病症——越新的模型越倾向"给个答案"而不是承认不知道，
    而几何扩容的触发器恰恰是拒答。它一坏，整套机制静默失效。
    """

    name = "校准失效（过度自信）"

    def respond(self, question: Question, doc_ids: list[str]) -> str:
        if question.evidence in doc_ids:
            return question.answer
        return f"根据材料，{DOC_TEXT[doc_ids[0]][:12]}……（编造，无证据支持）"


# ── 三种上下文规模策略 ────────────────────────────────────────────────

@dataclass
class RunResult:
    question: Question
    answer: str
    correct: bool
    k_sequence: list[int] = field(default_factory=list)   # 实际用过的 k
    llm_calls: int = 0
    prompt_tokens: int = 0

    @property
    def expanded(self) -> bool:
        return len(self.k_sequence) > 1


def _run(question: Question, retriever: Retriever, llm: MockLLM,
         k_schedule: list[int]) -> RunResult:
    """按给定的 k 序列依次尝试，一旦不是拒答就返回。"""
    res = RunResult(question=question, answer=REFUSAL, correct=False)
    before_calls, before_tokens = llm.calls, llm.prompt_tokens
    for k in k_schedule:
        docs = retriever.top_k(question.text, k)
        res.k_sequence.append(k)
        out = llm.chat(question, docs)
        if out != REFUSAL:
            res.answer = out
            res.correct = out == question.answer
            break
    res.llm_calls = llm.calls - before_calls
    res.prompt_tokens = llm.prompt_tokens - before_tokens
    return res


def geometric_schedule(max_k: int, start: int = 1, ratio: int = 2) -> list[int]:
    """1, 2, 4, 8 … —— 翻倍扩容的 k 序列。"""
    schedule, k = [], start
    while k < max_k:
        schedule.append(k)
        k *= ratio
    schedule.append(max_k)
    return schedule


def linear_schedule(max_k: int) -> list[int]:
    """1, 2, 3, 4 … —— 反面对照：每次只加一个文档。"""
    return list(range(1, max_k + 1))


def adaptive_rag(question, retriever, llm, max_k=8) -> RunResult:
    return _run(question, retriever, llm, geometric_schedule(max_k))


def linear_rag(question, retriever, llm, max_k=8) -> RunResult:
    return _run(question, retriever, llm, linear_schedule(max_k))


def fixed_k_rag(question, retriever, llm, k=8) -> RunResult:
    return _run(question, retriever, llm, [k])


# ── 评估集：证据文档在检索排名里的位置各不相同，构造出难度梯度 ──────────

#     难度不是人为标注的，而是**问题与证据文档的词汇鸿沟**自然造成的：
#     照抄原文措辞的问题，证据一检就在第一位；换一套说法去问，证据就
#     沉到第 4、第 8 位——这正是真实 RAG 里"简单题/疑难题"的成因。
QUESTIONS = [
    # ── 证据排第 1：k=1 即可收敛（约六成问题属于此类）──
    Question("余弦相似度衡量的是什么", "d02", "衡量语义方向的接近程度，不看向量长度。"),
    Question("两路结果怎么合并成一份榜单", "d04", "用 RRF 融合，经验常数取 60。"),
    Question("重复发送同样的开头部分费用能不能降下来", "d11", "能，命中价约为常规输入价的十分之一。"),
    Question("要回答一个需要把很多份资料汇总起来才能说清的大问题该用什么办法",
             "d12", "用图检索：抽实体建图再做社区摘要。"),
    Question("已经作废的旧内容为什么还会出现在答案里", "d10", "删除传播漏了，残留的幽灵块被当成了证据。"),
    # ── 证据排第 2：需要扩到 k=2 ──
    Question("粗筛之后还要再精细排一遍值得吗", "d05", "值得，交叉编码器逐对打分是性价比最高的一环。"),
    # ── 证据排第 4：需要扩到 k=4 ──
    Question("换了一个新的表示模型之后为什么旧的结果全乱了", "d09", "嵌入模型升级必须全量重嵌，新旧向量不可混用。"),
    # ── 证据排第 8：需要扩到 k=8 ──
    Question("材料排布顺序会不会影响模型注意到哪一句", "d08", "会，中段信息容易被忽略，即 lost in the middle。"),
]


def evaluate(strategy, retriever: Retriever, llm_factory, **kw):
    llm = llm_factory()
    results = [strategy(q, retriever, llm, **kw) for q in QUESTIONS]
    return llm, results


def summarize(tag: str, llm: MockLLM, results: list[RunResult]) -> dict:
    correct = sum(r.correct for r in results)
    expanded = sum(r.expanded for r in results)
    stats = {
        "tag": tag,
        "accuracy": correct / len(results),
        "llm_calls": llm.calls,
        "prompt_tokens": llm.prompt_tokens,
        "context_tokens": llm.context_tokens,
        "expansion_rate": expanded / len(results),
    }
    print(f"  {tag:<22} 准确率 {stats['accuracy']:>5.0%} │ "
          f"调用 {llm.calls:>3} 次 │ 上下文 {llm.context_tokens:>5} tok │ "
          f"整条 prompt {llm.prompt_tokens:>5} tok │ "
          f"扩容触发率 {stats['expansion_rate']:>4.0%}")
    return stats


# ── 场景演示 ──────────────────────────────────────────────────────────

def demo_easy(retriever: Retriever) -> RunResult:
    print("\n【场景一】简单题：证据排在第一，k=1 直接收敛")
    print("-" * 68)
    q = QUESTIONS[0]
    res = adaptive_rag(q, retriever, MockLLM())
    print(f"  问题：{q.text}")
    print(f"  检索排名前 3：{retriever.top_k(q.text, 3)}（证据 {q.evidence}）")
    print(f"  k 序列：{res.k_sequence} → 1 次调用、{res.prompt_tokens} tokens 即答出")
    print(f"  答案：{res.answer}")
    print("  ⟹ 这就是自适应省钱的来源：多数问题根本用不到 top-8。")
    return res


def demo_hard(retriever: Retriever) -> RunResult:
    print("\n【场景二】难题：证据排名靠后，逐级扩容直到够用")
    print("-" * 68)
    q = next(q for q in QUESTIONS if retriever.rank(q.text).index(q.evidence) >= 3)
    rank = retriever.rank(q.text).index(q.evidence) + 1
    llm = MockLLM()
    res = adaptive_rag(q, retriever, llm)
    print(f"  问题：{q.text}")
    print(f"  证据 {q.evidence} 排在第 {rank} 位——k=1 时它根本不在上下文里")
    for i, k in enumerate(res.k_sequence, 1):
        verdict = "答出" if i == len(res.k_sequence) and res.correct else "拒答 → 翻倍"
        print(f"    第 {i} 次：k={k:<2} 文档={retriever.top_k(q.text, k)} → {verdict}")
    print(f"  ⟹ 扩容 {res.llm_calls} 次后答对；串行调用数对最终规模是**对数级**。")
    return res


def demo_cost(retriever: Retriever) -> tuple[dict, dict, dict]:
    print("\n【场景三】整套评估集的 token 账：三种策略正面对比")
    print("-" * 68)
    ada = summarize("自适应（1→2→4→8）", *evaluate(adaptive_rag, retriever, MockLLM))
    fix = summarize("固定 K=8", *evaluate(fixed_k_rag, retriever, MockLLM))
    lin = summarize("线性 +1（反面对照）", *evaluate(linear_rag, retriever, MockLLM))
    ctx_saved = 1 - ada["context_tokens"] / fix["context_tokens"]
    saved = 1 - ada["prompt_tokens"] / fix["prompt_tokens"]
    print(f"\n  ⟹ 自适应 vs 固定 K=8：准确率持平，**上下文** token 省 {ctx_saved:.0%}，"
          f"整条 prompt 省 {saved:.0%}。")
    print("  ⟹ 两个数字为什么不一样？固定的指令前缀被每次重试**重发**了一遍——")
    print(f"     自适应发了 {ada['llm_calls']} 次 vs 固定 K 的 {fix['llm_calls']} 次，"
          "这部分开销吃掉了一部分节省。")
    print("     真实系统里它正是**提示词缓存**的用武之地（稳定前缀命中价约十分之一），")
    print("     缓存一开，实际节省会更接近上面那个上下文口径的数字。")
    print(f"  ⟹ 线性 +1 在两个维度上都更差：{lin['llm_calls']} 次调用、"
          f"{lin['context_tokens']} 上下文 token（自适应 {ada['llm_calls']} 次 / "
          f"{ada['context_tokens']} tok）。")
    print("     **这就是必须几何扩容而非线性递增的原因**：调用次数决定串行延迟，")
    print("     线性策略把延迟从对数级拖回线性级，还没换来任何准确率。")
    return ada, fix, lin


def demo_miscalibration(retriever: Retriever) -> tuple[dict, dict]:
    print("\n【场景四】反面教材：模型不肯说\"不知道\"时，机制静默失效")
    print("-" * 68)
    good = summarize("校准良好", *evaluate(adaptive_rag, retriever, MockLLM))
    bad = summarize("过度自信", *evaluate(adaptive_rag, retriever, OverconfidentLLM))
    print(f"\n  ⟹ 过度自信的模型扩容触发率降到 {bad['expansion_rate']:.0%}："
          "拒答信号没了，扩容永不触发，")
    print(f"     机制退化成\"永远只用 1 个块\"，准确率从 {good['accuracy']:.0%} "
          f"掉到 {bad['accuracy']:.0%}，token 反而更少——")
    print("     **成本指标看上去更漂亮，质量却在裸奔**。这正是它最危险的地方。")
    print("  ⟹ 工程对策：把\"扩容触发率\"本身做成线上监控项，突然归零即校准失效告警。")
    return good, bad


# ── 自检 ──────────────────────────────────────────────────────────────

def self_check(retriever: Retriever, easy: RunResult, hard: RunResult,
               ada: dict, fix: dict, lin: dict,
               good: dict, bad: dict) -> None:
    print("\n" + "=" * 68)
    print("自检")
    print("=" * 68)

    # 1. 几何序列本身：翻倍且以 max_k 收尾
    assert geometric_schedule(8) == [1, 2, 4, 8], geometric_schedule(8)
    assert geometric_schedule(64) == [1, 2, 4, 8, 16, 32, 64]
    assert len(geometric_schedule(64)) == 7 == int(math.log2(64)) + 1
    print("   ✔ 几何序列正确：扩到 64 块只需 7 次调用（对数级）")

    # 2. 简单题在 k=1 收敛，不发生扩容
    assert easy.k_sequence == [1] and easy.correct and not easy.expanded
    print("   ✔ 简单题 k=1 即收敛，未触发任何扩容")

    # 3. 难题确实逐级扩容，且序列是 1→2→4…的前缀
    assert hard.expanded and hard.correct
    assert hard.k_sequence == geometric_schedule(8)[:len(hard.k_sequence)]
    print(f"   ✔ 难题按 {hard.k_sequence} 逐级扩容后答对")

    # 4. 成本性质：几何扩容累计 ≈ 最后一次的 2 倍以内（k/(k-1)，k=2）
    for q in QUESTIONS:
        r = adaptive_rag(q, retriever, MockLLM())
        final_k = r.k_sequence[-1]
        assert sum(r.k_sequence) <= 2 * final_k, (q.text, r.k_sequence)
    print("   ✔ 累计取用文档数 ≤ 2×最后一次——成本被最后一次调用摊掉")

    # 5. 省钱是真的：准确率不降，上下文与整条 prompt 双双下降
    assert ada["accuracy"] == fix["accuracy"] == 1.0
    ctx_saved = 1 - ada["context_tokens"] / fix["context_tokens"]
    saved = 1 - ada["prompt_tokens"] / fix["prompt_tokens"]
    assert ctx_saved > 0.4, f"上下文仅省了 {ctx_saved:.0%}"
    assert saved > 0.15, f"整条 prompt 仅省了 {saved:.0%}"
    print(f"   ✔ 与固定 K=8 相比准确率持平：上下文省 {ctx_saved:.0%}、"
          f"整条 prompt 省 {saved:.0%}")

    # 6. 重发的固定前缀是两个口径的差额来源——真实系统靠提示词缓存消化
    assert saved < ctx_saved, "整条 prompt 的节省应小于上下文口径（前缀被重发）"
    print("   ✔ 整条 prompt 的节省小于上下文口径——重试重发固定前缀的开销被如实计入")

    # 7. 几何 vs 线性：线性在调用次数与 token 两个维度上都更差
    assert lin["accuracy"] == ada["accuracy"]
    assert lin["llm_calls"] > ada["llm_calls"], (lin["llm_calls"], ada["llm_calls"])
    assert lin["context_tokens"] > ada["context_tokens"]
    print(f"   ✔ 线性 +1 需 {lin['llm_calls']} 次调用 vs 几何 {ada['llm_calls']} 次，"
          "且上下文 token 更多——几何级数在延迟与成本上双赢")

    # 7. 校准失效：扩容归零、准确率下滑，而 token 反而更低（最危险的信号组合）
    assert bad["expansion_rate"] == 0.0
    assert bad["accuracy"] < good["accuracy"]
    assert bad["prompt_tokens"] < good["prompt_tokens"]
    print("   ✔ 过度自信模型：扩容触发率归零、准确率下滑、token 反降——静默失效复现")

    print("\n✅ 自检通过")


def main() -> None:
    print("=" * 68)
    print("Lab 10 · 自适应 RAG：拒答驱动的几何级数扩容")
    print("=" * 68)
    retriever = Retriever(CORPUS)
    easy = demo_easy(retriever)
    hard = demo_hard(retriever)
    ada, fix, lin = demo_cost(retriever)
    good, bad = demo_miscalibration(retriever)
    self_check(retriever, easy, hard, ada, fix, lin, good, bad)


if __name__ == "__main__":
    main()
