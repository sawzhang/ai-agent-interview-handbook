# -*- coding: utf-8 -*-
"""
====================================================================
实验 04：短期/长期记忆与摘要压缩
====================================================================

【实验目的】
用纯 Python 标准库从零搭建一个 Agent 记忆系统，理解三个核心问题：
1. 工作记忆（短期记忆）为什么必须有容量上限？
   —— LLM 的上下文窗口有限，且每次请求都要把全部历史发给模型，成本随长度线性增长。
2. 超限时如何"摘要压缩"，做到"丢细节、保要点"？
   —— 调用 LLM 把较旧的一批消息浓缩成一段短摘要，替换掉原始消息。
3. 长期记忆如何跨对话保存关键事实，并按需召回？
   —— 把事实写入一个带"关键词倒排索引"的存储，查询时按关键词命中打分召回。

【对应知识域】第 4 章 Memory 系统
【核心概念】
- 工作记忆 Working Memory：有容量上限（这里以 token 计）的最近消息队列；
- 摘要压缩 Summarization：容量溢出时，把"较旧的一半"消息交给 LLM 压缩成摘要，
  这正是 LangChain ConversationSummaryBufferMemory 的简化思想；
- 长期记忆 Long-Term Memory：关键词倒排索引的 fact 存储（生产环境通常换成
  embedding 向量 + 向量数据库，但"建索引 → 相似度召回"的思路完全一致）。

【模型说明】
本实验不涉及任何真实 API 调用，所有"大模型能力"由确定性的 MockLLM 模拟：
摘要 = 规则截断拼接，事实抽取 = 正则模板。确定性保证实验结果可复现。

【如何运行】
    python3 lab04_memory_system.py
运行结束若打印 "✅ 自检通过"，说明压缩降 token、长期记忆召回两项核心断言全部成立。

【思考题（面试延伸）】
1. 摘要压缩一定会丢信息（精确数字、用户原话、承诺细节）。生产环境中你会如何
   缓解信息损失？（提示：分层摘要 / 保留关键消息不压缩 / 原文落库用 RAG 检索）
2. 本实验用"中文二元词 + 英文单词"做关键词索引。与 embedding + 向量数据库相比，
   关键词召回的优缺点是什么？哪些业务场景下关键词召回就足够了？
3. 除了"token 超限就压缩"，你还能想到哪些压缩时机与策略？
   （提示：按轮数定期压缩、话题切换时压缩、空闲时异步压缩、滑动窗口 + 固定系统提示）
"""

import re
from collections import deque


# ---------------------------------------------------------------------------
# 1. Token 估算
# ---------------------------------------------------------------------------
# 教学目的不引入任何外部分词器，这里做一个粗略但稳定的估算：
#   - 每个中文字符算 1 个 token；
#   - 每段连续的英文字母 / 连续数字各算 1 个 token；
# 这与真实 BPE 分词器的量级接近，足以演示"压缩前后 token 数下降"。

_TOKEN_RE = re.compile(r"[一-鿿]|[A-Za-z]+|\d+")


def count_tokens(text: str) -> int:
    """估算一段文本的 token 数（中文按字、英文/数字按连续片段）。"""
    if not text:
        return 0
    return len(_TOKEN_RE.findall(text))


# ---------------------------------------------------------------------------
# 2. MockLLM：确定性模拟大模型的三种能力
# ---------------------------------------------------------------------------
class MockLLM:
    """确定性 mock 大模型：无随机、无网络、结果可复现。"""

    def summarize(self, messages) -> str:
        """
        摘要压缩能力：把一批旧消息压成一段短摘要。
        真实实现会把消息发给 LLM，要求"用 100 字概括要点"；
        这里用规则截断，刻意保证两件事：
          (a) 结果确定可复现；
          (b) 摘要一定明显短于被压缩的原始消息——压缩的本质就是
              "用信息损失换取上下文容量"，摘要必须更短才有意义。
        """
        snippets = [f"{m['role']}:{m['content'][:6]}" for m in messages]
        body = ";".join(snippets)
        if len(body) > 60:                      # 摘要正文最多 60 字
            body = body[:60] + "…"
        return f"[摘要，覆盖此前{len(messages)}条消息] {body}"

    # 事实抽取模板：识别用户消息中的"自我披露"型陈述句。
    # 生产环境通常让 LLM 输出结构化 JSON（{"type": "allergy", "value": ...}）。
    _FACT_PATTERNS = [
        re.compile(r"我叫(?P<v>[一-鿿\w]+)"),
        re.compile(r"我对?[一-鿿\w]+过敏"),
        re.compile(r"我(喜欢|讨厌)[一-鿿\w]+"),
        re.compile(r"我计划[^，。！？]+"),
        re.compile(r"我住在[一-鿿\w]+"),
    ]

    def extract_facts(self, text: str):
        """从一条消息中抽取值得长期保存的事实，返回事实字符串列表。"""
        facts = []
        for pat in self._FACT_PATTERNS:
            for mt in pat.finditer(text):
                facts.append(mt.group(0))
        return facts

    def chat(self, context: str, user_msg: str) -> str:
        """
        对话能力：真实场景下会把 context（摘要+最近消息）拼进 prompt 生成回复。
        这里只做简单回应以推进对话，回复长度刻意稳定，便于观察 token 变化。
        """
        return f"收到并已记录相关信息。关于“{user_msg[:8]}”，我们继续。"


# ---------------------------------------------------------------------------
# 3. 工作记忆：有容量上限的最近消息队列 + 超限摘要压缩
# ---------------------------------------------------------------------------
class WorkingMemory:
    """
    工作记忆（短期记忆）。

    关键设计：
    - messages：deque 保存最近消息，新消息从右侧追加；
    - summary：更早的历史被压缩成的摘要（压缩发生前为 None）；
    - 每次 add 之后检查 token 是否超过 capacity_tokens，超限就把
      “较旧的一半”消息（连同已有摘要）重新压缩成一段新摘要，
      循环压缩直到回落到容量以内。
    发送给模型的上下文 = summary + messages，既保留了远期要点，
    又让总长度始终受控。
    """

    def __init__(self, capacity_tokens: int, llm: MockLLM):
        self.capacity_tokens = capacity_tokens
        self.llm = llm
        self.messages = deque()        # [{"role": ..., "content": ...}, ...]
        self.summary = None            # 旧历史的压缩摘要
        self.compress_count = 0        # 累计压缩次数
        self.last_compression = None   # 最近一次压缩的 before/after 统计，供自检断言

    @staticmethod
    def _msg_tokens(m) -> int:
        return count_tokens(m["role"]) + count_tokens(m["content"])

    def total_tokens(self) -> int:
        """当前工作记忆的总占用 = 摘要 token + 所有消息 token。"""
        total = count_tokens(self.summary) if self.summary else 0
        return total + sum(self._msg_tokens(m) for m in self.messages)

    def add(self, role: str, content: str):
        """写入一条消息；若超容量则触发（可能多轮）摘要压缩。"""
        self.messages.append({"role": role, "content": content})
        # 至少保留 2 条消息，避免把队列压空；摘要足够短，循环必然收敛。
        while self.total_tokens() > self.capacity_tokens and len(self.messages) >= 2:
            self._compress()

    def _compress(self):
        """把较旧的一半消息（含已有摘要）压成新摘要。"""
        before = self.total_tokens()
        n = len(self.messages)
        old = [self.messages.popleft() for _ in range(n // 2)]
        if self.summary:
            # 旧摘要也卷入本轮压缩，防止摘要层层叠叠无限膨胀
            old = [{"role": "summary", "content": self.summary}] + old
        self.summary = self.llm.summarize(old)
        after = self.total_tokens()
        self.compress_count += 1
        self.last_compression = {
            "before": before,
            "after": after,
            "compressed_msgs": len(old),
        }
        print(f"    ⚙️ 触发摘要压缩：{len(old)} 条旧消息 → 1 段摘要，"
              f"token {before} → {after}")

    def render(self) -> str:
        """渲染成“将发给模型的上下文”：摘要在前，最近消息在后。"""
        lines = []
        if self.summary:
            lines.append(f"[历史摘要] {self.summary}")
        lines += [f"{m['role']}: {m['content']}" for m in self.messages]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. 长期记忆：关键词倒排索引的 fact 存储
# ---------------------------------------------------------------------------
class LongTermMemory:
    """
    长期记忆：fact 存储 + 关键词倒排索引。

    关键设计：
    - facts：按写入顺序保存每条事实全文；
    - _index：倒排索引“关键词 -> 事实编号集合”，与搜索引擎同一思路；
    - 关键词自动生成：中文取连续汉字的二元组（bigram，近似分词效果），
      英文取整词并小写化。
    召回 = 查询关键词与每条事实关键词的交集大小打分，取 Top-K。
    生产中一般替换为 embedding + 向量数据库（语义召回），流程一致：
    写入时建索引，查询时算相似度排序。
    """

    _CN_RUN = re.compile(r"[一-鿿]+")
    _EN_WORD = re.compile(r"[A-Za-z]+")

    def __init__(self):
        self.facts = []          # 事实全文列表
        self._index = {}         # 关键词 -> set(fact_id)

    @classmethod
    def _keywords(cls, text: str):
        """从文本生成关键词集合：中文 bigram + 英文小写整词。"""
        kws = set()
        for run in cls._CN_RUN.findall(text):
            if len(run) == 1:
                kws.add(run)
            for i in range(len(run) - 1):
                kws.add(run[i:i + 2])
        kws.update(w.lower() for w in cls._EN_WORD.findall(text))
        return kws

    def store(self, fact: str):
        """写入一条事实并更新倒排索引（去重）。"""
        if fact in self.facts:
            return
        fid = len(self.facts)
        self.facts.append(fact)
        for kw in self._keywords(fact):
            self._index.setdefault(kw, set()).add(fid)

    def recall(self, query: str, top_k: int = 3):
        """按关键词命中数打分召回，返回 [(事实, 得分), ...]，得分>0。"""
        scores = {}
        for kw in self._keywords(query):
            for fid in self._index.get(kw, ()):
                scores[fid] = scores.get(fid, 0) + 1
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [(self.facts[fid], s) for fid, s in ranked[:top_k] if s > 0]


# ---------------------------------------------------------------------------
# 5. MemoryAgent：把两种记忆组装成一个可用的 Agent
# ---------------------------------------------------------------------------
class MemoryAgent:
    """带记忆的 Agent：工作记忆管理上下文，长期记忆沉淀事实。"""

    def __init__(self, capacity_tokens: int = 200):
        self.llm = MockLLM()
        self.working = WorkingMemory(capacity_tokens, self.llm)
        self.longterm = LongTermMemory()

    def chat(self, user_msg: str) -> str:
        # ① 用户消息进入工作记忆（超限会自动压缩）
        self.working.add("user", user_msg)
        # ② 顺手抽取事实写入长期记忆（真实系统也可能异步/批量做）
        for fact in self.llm.extract_facts(user_msg):
            self.longterm.store(fact)
        # ③ 基于“摘要 + 最近消息”生成回复
        reply = self.llm.chat(self.working.render(), user_msg)
        # ④ 助手回复也进入工作记忆
        self.working.add("assistant", reply)
        return reply


# ---------------------------------------------------------------------------
# 6. 演示入口
# ---------------------------------------------------------------------------
def hr(title: str):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


if __name__ == "__main__":
    # ------------------------------------------------------------------
    # 第一部分：超长对话触发摘要压缩
    # ------------------------------------------------------------------
    hr("第一部分：工作记忆容量上限与摘要压缩（capacity=200 tokens）")

    agent = MemoryAgent(capacity_tokens=200)

    # 一段足够长的对话：前几句夹带“自我披露”事实，后面是日常闲聊，
    # 目的是把 token 推过容量上限、多次触发压缩。
    conversation = [
        "你好，我叫张三，是一名后端开发工程师。",
        "特别提醒：我对青霉素过敏，用药时务必注意。",
        "平时我喜欢编程，尤其是用 Python 写工具。",
        "我计划十二月去京都，准备在日本看枫叶。",
        "这周项目进度很顺利，核心模块已经开发完成。",
        "好的，测试覆盖率那部分请继续推进。",
        "今天外面风特别大，天气真是越来越冷了。",
        "出门记得多穿点衣服，注意保暖。",
        "我计划下周做一轮性能优化，先把接口耗时降下来。",
        "性能优化一般要先有 profiling 数据再动手。",
        "没错，我会先采集线上 CPU 火焰图。",
        "这个做法比较稳妥，有结果随时同步讨论。",
    ]

    for i, msg in enumerate(conversation, 1):
        reply = agent.chat(msg)
        wm = agent.working
        print(f"[第{i:02d}轮] 用户: {msg}")
        print(f"        助手: {reply}")
        print(f"        状态: 消息 {len(wm.messages)} 条 | "
              f"token {wm.total_tokens()}/{wm.capacity_tokens} | "
              f"累计压缩 {wm.compress_count} 次")

    wm = agent.working
    hr("压缩后，工作记忆实际发给模型的上下文")
    print(wm.render())

    # ------------------------------------------------------------------
    # 第二部分：长期记忆写入与召回
    # ------------------------------------------------------------------
    hr("第二部分：长期记忆——事实写入与关键词召回")

    ltm = agent.longterm
    print(f"对话过程中共沉淀 {len(ltm.facts)} 条长期事实：")
    for j, fact in enumerate(ltm.facts, 1):
        print(f"  {j}. {fact}")

    queries = [
        "关于张三的信息有吗？",      # 命中事实中的 bigram “张三”
        "他对药物过敏吗？",          # 命中 “过敏”
        "日本京都",                  # 命中 “京都”
    ]
    print("\n召回演示（查询 → Top 命中事实）：")
    for q in queries:
        print(f"  查询: {q}")
        hits = ltm.recall(q, top_k=2)
        for fact, score in hits:
            print(f"    ↳ (得分 {score}) {fact}")

    # ------------------------------------------------------------------
    # 第三部分：自检断言
    # ------------------------------------------------------------------
    hr("第三部分：自检断言")

    # 1) 压缩确实发生过
    assert wm.compress_count >= 1, "超长对话未触发摘要压缩"
    print(f"✔ 对话过程中触发摘要压缩 {wm.compress_count} 次")

    # 2) 最近一次压缩后 token 数下降
    assert wm.last_compression is not None, "缺少压缩统计"
    b, a = wm.last_compression["before"], wm.last_compression["after"]
    assert a < b, f"压缩后 token 未下降: before={b}, after={a}"
    print(f"✔ 最近一次压缩 token 下降: {b} → {a}（减少 {b - a}）")

    # 3) 压缩后工作记忆回落到容量以内
    assert wm.total_tokens() <= wm.capacity_tokens, "压缩后仍超容量上限"
    print(f"✔ 压缩后总 token {wm.total_tokens()} ≤ 容量 {wm.capacity_tokens}")

    # 4) 长期记忆确实写入了对话中的事实
    assert any("张三" in f for f in ltm.facts), "未抽取到姓名事实"
    assert any("过敏" in f for f in ltm.facts), "未抽取到过敏事实"
    print("✔ 长期记忆已写入姓名、过敏等事实")

    # 5) 长期记忆能按关键词召回写入的事实
    assert any("张三" in f for f, _ in ltm.recall("关于张三的信息有吗？")), "姓名事实召回失败"
    assert any("过敏" in f for f, _ in ltm.recall("他对药物过敏吗？")), "过敏事实召回失败"
    assert any("京都" in f for f, _ in ltm.recall("日本京都")), "旅行事实召回失败"
    print("✔ 三条查询均成功召回对应事实")

    print("\n✅ 自检通过")
