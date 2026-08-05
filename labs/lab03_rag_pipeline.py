#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
========================================================================
Lab 03 · 极简 RAG 全链路（纯 Python 标准库实现，零依赖）
========================================================================

【对应知识域】
    第 4 章 · Memory 与 RAG
    长期记忆的一种典型实现就是"外部知识库 + 检索"：模型不需要把
    所有知识塞进参数或上下文窗口，而是提问时现查现用。

【实验目的】
    不用任何第三方库（没有 numpy / langchain / 向量数据库 / 真实 API），
    从零实现一条完整的 RAG 流水线，让读者看清每一个环节到底在做什么：

        文档 ──①分块──▶ Chunk ──②嵌入──▶ 向量
                                          │
        问题 ──②嵌入──▶ 向量 ──③余弦相似度──▶ 候选 top-N
                                          │
                      ④Mock 精排器（reranker）──▶ top-k
                                          │
                      ⑤拼装上下文 + Prompt ──▶ ⑥MockLLM 作答

【核心概念】
    1. Chunking（分块）: 按固定字符数切块，并让相邻块保留 overlap（重叠），
       避免关键句子被拦腰切断。块太大→噪声稀释信号，块太小→事实被切碎。
    2. Embedding（嵌入）: 本实验用"词袋 + 哈希技巧（hashing trick）"：
       把每个 token 用 crc32 哈希到固定 256 维向量的某一维并累加词频。
       真实系统里这一维是深度模型学出来的语义向量，原理接口一致。
    3. Retrieval（检索）: 余弦相似度 = cos(夹角)，只看方向不看长度，
       对文档长短不敏感，是向量检索的事实标准度量。
    4. Reranker（精排）: 向量检索是"双塔"粗排（快但粗），精排器用
       query-doc 交互特征重新打分（真实系统常用 cross-encoder，慢但准）。
       这里用"查询二元词组是否在 chunk 中完整出现"来模拟这种交互信号。
    5. Generation（生成）: 把 top-k 片段拼成上下文交给 LLM。MockLLM 是
       确定性的"抽取式"模型：挑上下文中与问题重叠最大的句子作答，
       保证实验可复现、可断言。

【如何运行】
    python3 lab03_rag_pipeline.py

【思考题（面试延伸）】
    1. chunk_size 和 overlap 如何影响召回率与上下文利用率？块太大和太小
       分别会出什么问题？生产环境里除了定长切块还有哪些切法（按句子 /
       按标题的语义切块、递归切块、parent-document 小块检索大块送模型）？
    2. 本实验的"词袋哈希向量"和真实语义 embedding 的本质区别是什么？
       为什么词袋检索答不了"怎么缓解模型说胡话"这种换了说法的提问？
       （关键词匹配 vs 语义匹配；顺便聊聊稠密检索、混合检索 BM25+向量、
       查询改写 / HyDE 如何补救。）
    3. 为什么向量粗排之后还需要 reranker？双塔（bi-encoder）与交叉编码
       （cross-encoder）在速度、精度、工程部署上如何权衡？top-k 与
       上下文窗口预算之间又该如何取舍？
========================================================================
"""

import math
import re
import zlib
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

# ------------------------------------------------------------------------
# 全局常量
# ------------------------------------------------------------------------
EMBED_DIM = 256   # 哈希向量维度：真实系统常见 768 / 1536 维
TOP_K = 2         # 最终送入 LLM 的片段数
CANDIDATES = 5    # 粗排召回、交给精排器重排的候选数

# 中文单字没有空格分隔，停用"字"逐字成集合即可；英文停用"词"必须单独列表，
# 不能跟在同一个字符串字面量后面——相邻字面量会先拼成一个长串，set() 再把它
# 拆成单字符，"the"/"is"/"of" 一个都进不了集合（英文过滤会静默失效）。
STOPWORDS = set(
    "的了是在和与及或者个什它这那有不为中而且但被把将于从到也就"
    "又能会以还很"
) | {"me", "i", "a", "an", "the", "is", "are", "of", "to", "in", "on", "for", "and", "or"}

# ------------------------------------------------------------------------
# 内置小知识库：doc-2 是主问题的答案文档，doc-5 用于分块对比实验
# ------------------------------------------------------------------------
KNOWLEDGE_BASE: List[Dict[str, str]] = [
    {
        "doc_id": "doc-1",
        "title": "Transformer 架构",
        "text": "Transformer 是一种基于自注意力机制的神经网络架构，由 Vaswani "
                "等人在 2017 年发表的论文《Attention Is All You Need》中提出。"
                "它完全摒弃循环结构，仅靠注意力机制就能捕获序列的全局依赖关系，"
                "如今已成为大语言模型的主流底座。",
    },
    {
        "doc_id": "doc-2",
        "title": "RAG 技术范式",
        "text": "检索增强生成（Retrieval-Augmented Generation，简称 RAG）是一种"
                "将信息检索与语言模型结合的技术范式。RAG 先从外部知识库中检索与"
                "问题相关的文档片段，再将这些片段作为上下文提供给语言模型，从而让"
                "模型基于最新、准确的外部知识生成答案，有效缓解幻觉问题。",
    },
    {
        "doc_id": "doc-3",
        "title": "向量数据库",
        "text": "向量数据库专门存储和检索高维向量。文本、图片等数据经嵌入模型转为"
                "向量后，数据库用近似最近邻算法完成毫秒级相似性检索，因此成为 "
                "RAG 系统的核心基础设施。",
    },
    {
        "doc_id": "doc-4",
        "title": "提示工程",
        "text": "提示工程通过精心设计输入提示来引导模型输出，常见技巧包括少样本"
                "示例、思维链与角色设定，能显著提升模型任务表现。",
    },
    {
        "doc_id": "doc-5",
        "title": "星辰科技白皮书",
        "text": "星辰科技成立于2015年，是一家专注于人工智能基础设施的高科技企业，"
                "总部位于杭州，在北京和上海设有研发中心。"
                "公司自研的星云大模型于2024年3月正式发布，参数量达千亿级，发布"
                "当月即通过国家生成式人工智能服务备案。"
                "该模型采用混合专家架构与自研对齐训练框架，支持超长上下文窗口，"
                "已服务于金融、医疗、教育等多个行业。",
    },
]


# ------------------------------------------------------------------------
# ① 分块：定长字符切块 + 重叠
# ------------------------------------------------------------------------
@dataclass
class Chunk:
    doc_id: str
    title: str
    seq: int      # 在文档内的序号
    text: str
    vector: List[float] = field(default_factory=list, repr=False)


def chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    """按字符数把文本切成若干块，相邻块之间保留 overlap 个字符的重叠。

    设计要点（为什么需要 overlap）：
      定长切块必然会切到句子中间。让相邻块共享一段重叠区，被切断处的
      上下文就能在两个块里各保留一份，显著降低"关键信息正好在切口上"
      导致的漏召回。代价是索引体积略有膨胀。
    """
    if overlap >= chunk_size:
        raise ValueError("overlap 必须小于 chunk_size，否则窗口永远不会前进")
    if not text:
        return []
    step = chunk_size - overlap          # 滑动步长 = 块长 - 重叠
    chunks, i, n = [], 0, len(text)
    while i < n:
        chunks.append(text[i:i + chunk_size])
        i += step
    # 收尾技巧：最后一块如果太短（不超过 overlap），就并入前一块。
    # 否则会产生只有几个字的"碎片块"——余弦相似度对短文本有天然偏好，碎片块
    # 会挤掉真正信息丰富的块。注意成因不是"模长小"：余弦已经除以两个模长，
    # 模长恰好被归一化掉了。真实机制是碎片块 token 少，一旦命中查询词，向量
    # 方向就几乎由这个词决定、不被其余无关词稀释，于是夹角小、得分高。
    # 这也是生产中常设"最小块长"的原因。
    if len(chunks) >= 2 and len(chunks[-1]) <= overlap:
        start = (len(chunks) - 2) * step     # 倒数第二块的起点
        chunks = chunks[:-2] + [text[start:n]]
    return chunks


# ------------------------------------------------------------------------
# ② 极简 Embedding：分词 + 哈希技巧（词袋向量）
# ------------------------------------------------------------------------
def tokenize(text: str) -> List[str]:
    """极简多语言分词：中文按单字切，英文/数字按连续串切，并去停用词。

    说明：中文没有空格天然分词，工业级方案需要 jieba 等分词器；
    但单字（unigram）词袋对检索演示已经够用，而且零依赖。
    """
    text = text.lower()
    tokens = re.findall(r"[一-鿿]|[a-z0-9]+", text)
    return [t for t in tokens if t not in STOPWORDS]


def embed_tokens(tokens: List[str]) -> List[float]:
    """词袋 + 哈希技巧：把每个 token 用 crc32 映射到固定维度并累加词频。

    关键点：
      - 必须用 zlib.crc32 而不是内置 hash()——Python 内置 hash 对字符串
        每次启动都随机化（PYTHONHASHSEED），会破坏实验的可复现性。
      - 不同 token 哈希到同一维（碰撞）是有意接受的近似：维度足够大时
        碰撞率低，对相似度排序的影响很小。这正是真实 hashing embedding
        的思想，只不过真实 embedding 的维度由模型学出来。
    """
    vec = [0.0] * EMBED_DIM
    for t in tokens:
        idx = zlib.crc32(t.encode("utf-8")) % EMBED_DIM
        vec[idx] += 1.0
    return vec


# ------------------------------------------------------------------------
# ③ 余弦相似度：向量检索的度量标准
# ------------------------------------------------------------------------
def cosine_similarity(a: List[float], b: List[float]) -> float:
    """cos(theta) = (a·b) / (|a| * |b|)

    只衡量方向、不衡量长度：一篇 1000 字的文档和一篇 100 字的文档，
    只要主题一致，余弦值就高。这比点积更适合"长短不一的文档 vs 短查询"。
    """
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ------------------------------------------------------------------------
# ④ Mock Reranker：模拟 cross-encoder 精排
# ------------------------------------------------------------------------
class MockReranker:
    """模拟精排器（真实系统里通常是 cross-encoder 模型）。

    粗排（向量检索）把 query 和 doc 各自编码再算相似度，快，但两者之间
    没有"交互"；精排器把 query 和 doc 拼在一起整体打分，能捕捉细粒度的
    词组匹配，更准但更慢——所以工程上总是"粗排召大、精排选精"。

    这里的确定性启发式：查询里相邻 token 组成的二元词组，若在 chunk
    文本中作为子串完整出现，每个加 bonus 分（最多加 3 个）。
    例如问题含"幻觉"二字，含"幻觉"的 chunk 就会被精确加分，
    而只有散落的"幻"或"觉"的 chunk 不会加分。
    """

    def __init__(self, bonus: float = 0.05):
        self.bonus = bonus

    @staticmethod
    def _query_bigrams(question: str) -> List[str]:
        toks = tokenize(question)
        return [a + b for a, b in zip(toks, toks[1:])]

    def rescore(self, question: str, base_score: float, chunk_text_: str) -> float:
        hits = sum(1 for bg in self._query_bigrams(question) if bg in chunk_text_)
        return base_score + self.bonus * min(hits, 3)


# ------------------------------------------------------------------------
# ⑥ MockLLM：确定性的"抽取式"语言模型替身
# ------------------------------------------------------------------------
class MockLLM:
    """不调用任何真实 API 的确定性模型。

    生成策略（抽取式 QA 的最朴素版本）：
      1. 把上下文按句切分（。！？和换行都是句界）；
      2. 给每句打分 = 与问题共享的 token 数；
      3. 返回得分最高的句子；若几乎没有重叠则老实承认"资料不足"。

    用它的好处：输出完全由输入决定，实验可复现、assert 可稳定断言。
    它也顺便演示了 RAG 的一个关键性质——答案质量完全受限于"检索到的
    上下文里有没有正确答案"，模型本身不会凭空知道事实。
    """

    def __init__(self, name: str = "mock-llm-v1"):
        self.name = name
        self.last_prompt = ""   # 记录最后一次 prompt，便于演示观察

    def generate(self, question: str, context: str) -> str:
        self.last_prompt = (
            "你是严谨的知识助手。请只依据【资料】回答【问题】；"
            "资料不足时直接说明。\n"
            f"【资料】\n{context}\n【问题】{question}"
        )
        sentences = [s.strip() for s in re.split(r"[。！？\n]", context) if s.strip()]
        q_set = set(tokenize(question))
        best_sent, best_score = "", 0
        for sent in sentences:
            score = len(q_set & set(tokenize(sent)))
            if score > best_score:            # 严格大于 → 同分取最早出现的句子
                best_score, best_sent = score, sent
        if best_score < 2:
            return "资料不足，无法根据已有知识回答该问题。"
        return f"根据资料：{best_sent}"


# ------------------------------------------------------------------------
# 把上面所有环节串成一条流水线
# ------------------------------------------------------------------------
class RAGPipeline:
    def __init__(self, docs: List[Dict[str, str]], chunk_size: int = 60,
                 overlap: int = 15, top_k: int = TOP_K,
                 candidates: int = CANDIDATES):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.top_k = top_k
        self.candidates = candidates
        self.reranker = MockReranker()
        self.llm = MockLLM()
        # 索引阶段：所有文档 → 所有带向量的 chunk
        self.chunks: List[Chunk] = []
        for doc in docs:
            for seq, piece in enumerate(chunk_text(doc["text"], chunk_size, overlap)):
                self.chunks.append(Chunk(
                    doc_id=doc["doc_id"], title=doc["title"], seq=seq,
                    text=piece, vector=embed_tokens(tokenize(piece)),
                ))

    def retrieve(self, question: str) -> List[Tuple[Chunk, float, float]]:
        """两阶段检索：向量粗排 top-N → reranker 精排 top-k。

        返回 [(chunk, 粗排分, 精排分), ...]，按精排分降序。
        """
        q_vec = embed_tokens(tokenize(question))
        scored = [(c, cosine_similarity(q_vec, c.vector)) for c in self.chunks]
        scored.sort(key=lambda p: p[1], reverse=True)
        candidates = scored[: self.candidates]
        reranked = [
            (c, base, self.reranker.rescore(question, base, c.text))
            for c, base in candidates
        ]
        reranked.sort(key=lambda t: t[2], reverse=True)
        return reranked[: self.top_k]

    def build_prompt(self, question: str,
                     hits: List[Tuple[Chunk, float, float]]) -> str:
        """⑤ 上下文拼装：top-k 片段 → 资料块 → prompt。"""
        parts = [f"[来源 {c.doc_id}·片段{c.seq}] {c.text}" for c, _, _ in hits]
        context = "\n\n".join(parts)
        return (f"你是严谨的知识助手。请只依据【资料】回答【问题】；"
                f"资料不足时直接说明。\n【资料】\n{context}\n【问题】{question}")

    def answer(self, question: str) -> Tuple[str, List[Tuple[Chunk, float, float]]]:
        hits = self.retrieve(question)
        context = "\n\n".join(c.text for c, _, _ in hits)
        return self.llm.generate(question, context), hits


# ------------------------------------------------------------------------
# 演示辅助
# ------------------------------------------------------------------------
def section(title: str) -> None:
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


# ------------------------------------------------------------------------
# 演示入口
# ------------------------------------------------------------------------
def main() -> None:
    print("Lab 03 · 极简 RAG 全链路（纯 Python 标准库，零外部依赖）")
    print(f"知识库共 {len(KNOWLEDGE_BASE)} 篇文档；向量维度 = {EMBED_DIM}"
          f"（词袋 + 哈希技巧）")

    # ==================================================================
    # Step 1 · 分块与索引：看看文档是怎么被切碎的
    # ==================================================================
    section("Step 1 · 分块与索引（chunk_size=60, overlap=15）")
    pipe = RAGPipeline(KNOWLEDGE_BASE, chunk_size=60, overlap=15)
    print(f"全部文档共切出 {len(pipe.chunks)} 个 chunk。以 doc-2 为例：")
    doc2_chunks = [c for c in pipe.chunks if c.doc_id == "doc-2"]
    for c in doc2_chunks:
        print(f"  片段{c.seq}（{len(c.text)}字）: {c.text}")
    # 验证重叠确实存在：后一块的前 15 字 == 前一块的后 15 字
    if len(doc2_chunks) >= 2:
        print(f"  ↑ 重叠验证：片段1 前15字 = {doc2_chunks[1].text[:15]!r}")
        print(f"            片段0 后15字 = {doc2_chunks[0].text[-15:]!r}")

    # ==================================================================
    # Step 2 · 完整问答链路：检索 → 精排 → 拼装上下文 → 生成
    # ==================================================================
    section("Step 2 · 完整 RAG 问答链路")
    q1 = "什么是 RAG？它为什么能缓解大模型的幻觉问题？"
    print(f"问题：{q1}\n")

    hits = pipe.retrieve(q1)
    print("两阶段检索结果（粗排=余弦相似度，精排=粗排+二元词组加成）：")
    for rank, (c, base, final) in enumerate(hits, 1):
        print(f"  Top-{rank} [{c.doc_id}·片段{c.seq}] "
              f"粗排={base:.4f} 精排={final:.4f}")
        print(f"         {c.text}")

    prompt = pipe.build_prompt(q1, hits)
    print("\n拼装好的 Prompt（节选）：")
    print("  " + prompt.replace("\n", "\n  ")[:220] + " ...")

    ans, _ = pipe.answer(q1)
    print(f"\nMockLLM 回答：{ans}")

    # ==================================================================
    # Step 3 · 对比实验：分块大小如何影响召回
    # ==================================================================
    section("Step 3 · 对比实验：分块大小对召回的影响")
    q2 = "星云大模型什么时候发布的？参数量有多大？"
    doc5 = [d for d in KNOWLEDGE_BASE if d["doc_id"] == "doc-5"]
    print(f"问题：{q2}")
    print("关键事实所在句子：『…于2024年3月正式发布，参数量达千亿级…』"
          "（跨度 19 字）\n")

    configs = [
        ("过小 chunk_size=12, overlap=0", 12, 0),
        ("适中 chunk_size=60, overlap=15", 60, 15),
    ]
    answers: Dict[str, str] = {}
    top1_scores: Dict[str, float] = {}
    covers: Dict[str, bool] = {}
    for label, size, ov in configs:
        p = RAGPipeline(doc5, chunk_size=size, overlap=ov, top_k=2, candidates=4)
        a, hs = p.answer(q2)
        answers[label] = a
        top1_scores[label] = hs[0][2]
        # 是否存在"单个 chunk 同时覆盖两个事实"——过小分块时必然为否，
        # 因为两个事实跨度 19 字 > 12 字的块长，任何窗口都装不下
        cover = any(("2024" in c.text and "千亿" in c.text) for c in p.chunks)
        covers[label] = cover
        print(f"[{label}] 共 {len(p.chunks)} 个 chunk，"
              f"Top-1 精排分={hs[0][2]:.4f}")
        print(f"  Top-1 片段: {hs[0][0].text}")
        print(f"  是否存在同时覆盖两个事实的 chunk: {'是' if cover else '否'}")
        print(f"  回答: {a}\n")

    # ==================================================================
    # Step 4 · 自检断言
    # ==================================================================
    section("Step 4 · 自检断言")
    checks: List[Tuple[str, bool]] = []

    def check(desc: str, ok: bool) -> None:
        checks.append((desc, ok))
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")

    # —— 主问答链路 ——
    top1_doc = hits[0][0].doc_id
    check(f"检索 Top-1 命中文档 doc-2（实际：{top1_doc}）", top1_doc == "doc-2")
    check("回答包含关键事实『幻觉』", "幻觉" in ans)
    check("回答包含关键机制『缓解』", "缓解" in ans)
    check("精排后 Top-1 仍是 doc-2（reranker 未帮倒忙）",
          hits[0][0].doc_id == "doc-2")

    # —— 分块机制 ——
    check(f"doc-2 被切成 3 个 chunk（实际：{len(doc2_chunks)}）",
          len(doc2_chunks) == 3)
    overlap_ok = (len(doc2_chunks) >= 2 and
                  doc2_chunks[1].text[:15] == doc2_chunks[0].text[-15:])
    check("相邻 chunk 之间确实存在 15 字重叠", overlap_ok)

    # —— 停用词过滤（中英各测一边）——
    # 这条断言是有来历的：英文停用词曾经写在中文串后面靠字面量拼接，set() 把
    # 整串拆成了单字符，"the"/"is" 一个都没进集合，英文过滤静默失效多时——
    # 演示全是中文才没被发现。测中文过不了的东西，永远发现不了这类分叉。
    zh_ok = all(w not in tokenize("这是一个的了") for w in ("的", "了", "是"))
    en_ok = all(w not in tokenize("the model is a part of it") for w in ("the", "is", "of"))
    check("中文停用字被过滤", zh_ok)
    check("英文停用词被过滤（不是被拆成单字符）", en_ok)

    # —— 分块大小对比 ——
    small_label, good_label = configs[0][0], configs[1][0]
    small_ans, good_ans = answers[small_label], answers[good_label]
    small_ok = ("2024" in small_ans and "千亿" in small_ans)
    good_ok = ("2024" in good_ans and "千亿" in good_ans)
    check("过小分块：没有任何 chunk 能同时装下两个事实", not covers[small_label])
    check("过小分块：回答无法同时覆盖『2024』与『千亿』"
          "（事实被切口切碎）", not small_ok)
    check("适中分块：存在单个 chunk 同时覆盖两个事实", covers[good_label])
    check("适中分块：回答同时包含发布时间『2024』与规模『千亿』", good_ok)
    print()
    print("结论：块太大 → 无关内容稀释向量信号、浪费上下文窗口；")
    print("      块太小 → 关键事实被切断，任何单个片段都不完整；")
    print("      实践中常用『适中块 + 重叠』，或小块检索、大块送模型。")

    # —— 总结 ——
    failed = [d for d, ok in checks if not ok]
    print(f"\n自检结果：{len(checks) - len(failed)}/{len(checks)} 通过")
    assert not failed, f"以下断言失败：{failed}"
    print("✅ 自检通过")


if __name__ == "__main__":
    main()
