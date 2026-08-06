#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab09_rca_pipeline.py — Badcase 根因分析（RCA）流水线
==========================================================

【实验目的】
    线上 agent 出了 badcase，不能只"看一眼、改个 prompt、祈祷"。本实验动手实现一条
    完整的、可复现的 Badcase 根因分析（Root Cause Analysis）流水线，覆盖工业界
    通用的 RCA 五步：
        1) 证据汇总   —— 按 session_id 聚合散乱的 trace 日志，重建每条会话的模块 IO 链；
        2) 范围收敛   —— 用"问题现象 × 功能模块"映射表缩小候选模块（不做无差别全量分析）；
        3) 分模块诊断 —— 逐模块读 input/output，输出 PASS / SOFT_PASS / FAIL；
        4) 责任判定   —— 三层漏斗：严重模块 FAIL 直接定责 → 规则模式匹配 → LLM 兜底；
        5) 结构化落盘 —— 产出 dict 记录：问题分类/现象/枚举/责任模块/置信度/修复建议。
    并在单条 RCA 之上实现"问题簇"聚类：同根因/同场景的 badcase 自动聚簇，输出
    "场景 X 中 N 次跳过校验，集中在 vY Prompt"这类可直接驱动修复决策的结论。

【对应章节】
    本特辑第 E11 章 · Badcase 根因分析与优化闭环
    （主手册第 8 章 · Agent 评估与可观测性 为浓缩版）

【核心概念】
    - 现象 ≠ 根因：评分层产出的是"现象分类"（答非所问/事实性错误/过度承诺），
      RCA 的任务是把现象翻译到根因（哪个模块、什么失败类型、谁的 owner）。
    - 范围收敛：全模块无差别分析成本高、噪声大；映射表只缩小候选，不直接定责。
    - PASS / SOFT_PASS / FAIL：SOFT_PASS = "基本通过但轻微瑕疵"——模块自身逻辑没错，
      但输出有问题（通常是上游错误沿流水线向下传播）。这个三态判定是"责任传递"分析的基础。
    - 三层定责漏斗（确定性优先、模型辅助）：
          第 1 层  严重（关键防线）模块 FAIL → 一票否决直接定责，置信度最高；
          第 2 层  规则模式匹配 → 沿因果链归因到"最上游的非缺失型 FAIL"；
          第 3 层  LLM 兜底 → 缺失型错误（模块根本没执行）无法定责给未执行的模块本身，
                   需要跨模块推理"谁本应触发它却没有触发"，交给 LLM。
      越靠前越确定、越便宜；LLM 只处理规则搞不定的长尾。
    - 缺失型错误的归因陷阱：工具没被调用，锅不在工具本身——是决策层（Prompt/编排）
      没触发它。本实验用阿里经典案例"已发货退款未查订单状态"演示这一点。
    - 问题簇：报告不应罗列 100 条 badcase，而是聚成少数几个簇并指出共性
      （同场景/同根因/同 Prompt 版本），修复才能一次覆盖一批。

【如何运行】
    cd evals-special/labs && python3 eval_lab09_rca_pipeline.py
    （纯 Python 标准库、零依赖、固定随机种子，任何机器上输出完全一致）

【思考题（面试延伸）】
    1. 为什么"严重模块 FAIL 直接定责"要放在规则匹配之前？如果把三层顺序反过来
       （先 LLM 后规则），成本与可信度会怎样变化？
    2. "缺失型错误不能定责给未执行的模块"——如果面试官追问"那怎么判断是 Prompt
       忘了约束、还是意图识别没给出触发条件、还是工具本身不可用？"你会补充哪些证据？
    3. SOFT_PASS（错误传播态）如果不显式建模，诊断结论会出什么错？
       （提示：多个模块同时 FAIL 时，朴素地"人人有份"会导致什么修复决策？）
    4. 聚类为什么按 (场景, 责任模块) 而不是按"用户问题文本相似度"？
       根因标签"稳定、可统计、指向 owner"对聚类有什么要求？
    5. 本实验的 MockLLM 兜底与真实 LLM 客户端（labs/llm_client.py 的 QwenLLM）同构，
       换成真实 LLM 后，如何防止兜底定责"胡说"？（低置信进人工、人审结论反校准规则库）
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. 被测系统建模：客服 Agent 的模块流水线
# ---------------------------------------------------------------------------
# 为什么先定义流水线顺序？因为 RCA 的"因果链归因"依赖它：同一条会话里，
# 越靠前的模块出错，越可能是"因"，越靠后的同类异常越可能只是"果"（错误传播）。
# 没有这个顺序，"多个模块同时 FAIL"时就只能和稀泥、人人有份。

PIPELINE_ORDER: List[str] = [
    "意图识别",      # 0 用户问题 → 意图标签
    "Query改写",     # 1 结合意图改写检索词
    "知识筛选",      # 2 按意图选择知识源
    "FAQ检索",       # 3 FAQ 库检索
    "知识检索",      # 4 文档知识库检索
    "订单状态查询",  # 5 工具：退款场景的必需前置步骤
    "回复生成",      # 6 LLM 生成回复（含动作决策，受 Prompt 版本驱动）
    "风险拦截",      # 7 发出前最后一道防线（关键模块）
]

# 关键防线模块：一旦 FAIL，后果不可逆（资损/合规），必须一票否决、直接定责。
CRITICAL_MODULES = {"风险拦截"}

# 场景 → 必需前置步骤。退款类请求必须先查订单状态（未发货可直接退，已发货要先拦截物流），
# 这正是阿里那个经典 badcase 违反的 SOP。
REQUIRED_STEPS: Dict[str, List[str]] = {
    "退货退款": ["订单状态查询"],
}

# 知识库"当前版本号"登记表：诊断知识检索时用它识别"召回了过期文档"。
KB_LATEST_VERSION: Dict[str, int] = {
    "K-1024": 2,   # 手机 X1 参数表
    "K-2019": 3,   # 退货流程
    "K-3007": 2,   # 补偿规则
}

# 意图 → 合理知识源。诊断知识筛选时用：筛选结果与自己拿到的意图自洽即无本地错误。
INTENT_SOURCE_MAP: Dict[str, List[str]] = {
    "物流查询": ["物流知识库"],
    "退货退款": ["退货政策库"],
    "商品咨询": ["商品知识库", "FAQ"],
    "投诉补偿": ["补偿规则库"],
}

# 主题关键词表：用"问题里出现什么词"反推合理意图。
# 注意它只是启发式——命中唯一主题才敢判，命中 0 个或多个主题时不下结论（宁可放过）。
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "退货退款": ["退货", "退款", "退掉", "不想要"],
    "物流查询": ["物流", "快递", "到哪了", "没到"],
    "投诉补偿": ["补偿", "赔偿", "投诉", "延误"],
    "商品咨询": ["电池", "屏幕", "参数", "像素", "内存"],
}

# 诊断三态。为什么不是二态？见 SOFT_PASS 注释——它是"责任传递"分析的关键。
PASS = "PASS"            # 本模块 IO 均正常
SOFT_PASS = "SOFT_PASS"  # 基本通过但轻微瑕疵：自身逻辑没错，输出却有问题（多为上游传播）
FAIL = "FAIL"            # 本模块自身处理违反职责
SKIP = "SKIP"            # 会话未经过该模块且非必需，不计入诊断

# Query改写的最小允许重叠度：改写可以换说法，但不能换话题。
REWRITE_MIN_OVERLAP = 0.30

# 过度承诺检测词表：承诺词 × 利益词同时出现，即构成"确定性赔付承诺"风险。
COMMIT_WORDS = ("保证", "一定", "百分百", "必定", "绝对")
BENEFIT_WORDS = ("补偿", "赔偿", "现金", "免单", "退款红包")


# ---------------------------------------------------------------------------
# 2. 第一步：证据汇总 —— 按 session_id 聚合 trace 日志
# ---------------------------------------------------------------------------
# 线上日志是"乱序到达"的：多会话交错、混着心跳/指标等噪声。RCA 的第一步就是把
# 散落的日志按会话聚拢、按时间戳重建顺序。只信 ts、不信到达顺序，是日志分析的基本纪律。

def aggregate_evidence(raw_logs: List[dict]) -> Tuple[Dict[str, List[dict]], int]:
    """按 session_id 聚合日志，会话内按 ts 升序重建。

    返回 (sessions, noise_count)：
      sessions    {session_id: [span, ...]}，每个 span 是一条 module_io 日志；
      noise_count 被丢弃的噪声日志条数（心跳等不是证据）。
    """
    sessions: Dict[str, List[dict]] = {}
    noise = 0
    for log in raw_logs:
        if log.get("type") != "module_io":
            noise += 1  # 心跳/指标日志对定责没有证据价值，直接丢弃但要计数
            continue
        sessions.setdefault(log["session_id"], []).append(log)
    for spans in sessions.values():
        spans.sort(key=lambda s: s["ts"])  # 稳定排序 + ts 唯一 → 结果与输入顺序无关
    return sessions, noise


# ---------------------------------------------------------------------------
# 3. 第二步：范围收敛 —— "问题现象 × 功能模块"映射表
# ---------------------------------------------------------------------------
# 为什么不做全模块无差别分析？成本高（每模块都要读 IO、跑检查）、噪声大（无关模块
# 的 SOFT_PASS 会干扰判断）。映射表把候选缩到 2~3 个模块。
# 注意纪律：映射表只缩小候选，不直接定责——定责永远发生在诊断之后。

SCOPE_MAP: Dict[str, List[str]] = {
    "答非所问": ["意图识别", "Query改写", "知识筛选"],
    "事实性错误": ["FAQ检索", "知识检索", "回复生成"],
    "过度承诺": ["风险拦截", "回复生成"],
    # 阿里案例对应的现象：该查的校验没查。本质是工具执行问题 + 生成层决策问题。
    "跳过校验": ["订单状态查询", "回复生成"],
}


def narrow_scope(symptom: str, scenario: str) -> List[str]:
    """现象 → 候选模块（并上该场景的必需步骤，防止映射表漏掉关键工具）。
    未命中映射表时退化为全量检查；生产中此处可再挂一个 LLM 兜底缩圈。"""
    candidates = list(SCOPE_MAP.get(symptom, PIPELINE_ORDER))
    for step in REQUIRED_STEPS.get(scenario, []):
        if step not in candidates:
            candidates.append(step)
    return candidates


# ---------------------------------------------------------------------------
# 4. 第三步：分模块诊断 —— 逐模块读 IO，输出三态结论
# ---------------------------------------------------------------------------
# 每个检查器只回答一个问题："这个模块拿到它的输入后，尽到自己的职责了吗？"
# 本地检查只读本模块 IO；上游错误通过 upstream_bad 标记显式传播为 SOFT_PASS，
# 而不是让下游模块白白背锅。

_TOKEN_RE = re.compile(r"[一-鿿]|[A-Za-z][A-Za-z0-9_]*|\d+")


def tokenize(text: str) -> List[str]:
    """极简确定性分词：中文按字、英文按词、数字整体。与主仓库 lab05 同款思路。"""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def dice(set_a: set, set_b: set) -> float:
    """Dice 重叠系数，这里用于度量"改写前后还是不是同一个问题"。"""
    if not set_a and not set_b:
        return 0.0
    return 2 * len(set_a & set_b) / (len(set_a) + len(set_b))


def match_topics(query: str) -> List[str]:
    """按关键词表反推问题所属主题（可能命中 0/1/多个）。"""
    return [t for t, kws in TOPIC_KEYWORDS.items() if any(k in query for k in kws)]


def has_overpromise(draft: str) -> bool:
    """承诺词与利益词同时出现 = 确定性赔付承诺（高风险话术）。"""
    return (any(w in draft for w in COMMIT_WORDS)
            and any(w in draft for w in BENEFIT_WORDS))


def _check_module(module: str, span: Optional[dict],
                  spans_by_module: Dict[str, dict],
                  scenario: str) -> Tuple[str, str, str]:
    """单模块本地诊断。返回 (verdict, kind, reason)。
    kind ∈ {ok, error, missing, absent}——missing 专门标记"必需步骤根本没执行"，
    它在责任判定阶段会被特殊处理（不能定责给未执行的模块本身）。"""

    # ---- 模块缺席 ----
    if span is None:
        if module in REQUIRED_STEPS.get(scenario, []):
            return (FAIL, "missing",
                    f"必需步骤缺失: {module}（场景「{scenario}」要求先执行该步骤，"
                    f"trace 中无任何调用记录）")
        return SKIP, "absent", "该会话未经过此模块（非必需步骤，不计入诊断）"

    out = span["output"]

    # ---- 意图识别：输出意图必须与问题的主题词一致（唯一命中时才敢判）----
    if module == "意图识别":
        topics = match_topics(span["input"]["query"])
        if len(topics) == 1 and out["intent"] != topics[0]:
            return (FAIL, "error",
                    f"意图与问题主题不符：问题命中主题「{topics[0]}」，"
                    f"却识别为「{out['intent']}」")
        return PASS, "ok", f"意图「{out['intent']}」与问题主题一致或启发式无法证伪"

    # ---- Query改写：可以换说法，不能换话题（与原始问题的 token 重叠度兜底）----
    if module == "Query改写":
        overlap = dice(set(tokenize(span["input"]["query"])),
                       set(tokenize(out["rewritten"])))
        if overlap < REWRITE_MIN_OVERLAP:
            return (FAIL, "error",
                    f"改写严重偏离原问题：Dice 重叠度 {overlap:.2f} "
                    f"< 阈值 {REWRITE_MIN_OVERLAP}")
        return PASS, "ok", f"改写保留原问题语义（重叠度 {overlap:.2f}）"

    # ---- 知识筛选：筛选结果与自己拿到的意图自洽即无本地错误 ----
    if module == "知识筛选":
        allowed = INTENT_SOURCE_MAP.get(span["input"]["intent"], [])
        if set(out["selected_sources"]) <= set(allowed):
            return PASS, "ok", f"知识源与输入意图「{span['input']['intent']}」匹配"
        return FAIL, "error", "选择了与输入意图不符的知识源"

    # ---- FAQ检索：命中且置信高为 PASS；未命中本身不算错（允许回退知识检索）----
    if module == "FAQ检索":
        if out["hits"] and out["top_score"] >= 0.6:
            return PASS, "ok", f"FAQ 命中 {out['hits'][0]}（score={out['top_score']}）"
        return SOFT_PASS, "ok", "无 FAQ 命中或得分偏低，回退知识检索（非本模块之错）"

    # ---- 知识检索：召回文档必须是最新版本，且相关度过线 ----
    if module == "知识检索":
        latest = KB_LATEST_VERSION.get(out["doc_id"])
        if latest is not None and out["doc_version"] < latest:
            return (FAIL, "error",
                    f"命中过期版本文档：{out['doc_id']} v{out['doc_version']}，"
                    f"最新版为 v{latest}（旧版内容已失真）")
        if out["relevance"] < 0.5:
            return FAIL, "error", f"召回相关度过低：{out['relevance']}"
        return PASS, "ok", f"召回 {out['doc_id']} v{out['doc_version']}（最新版，相关度 {out['relevance']}）"

    # ---- 订单状态查询：只要被执行且返回了状态即算尽职（缺席在 span is None 分支处理）----
    if module == "订单状态查询":
        if out.get("order_status"):
            return PASS, "ok", f"已查询订单状态：{out['order_status']}"
        return FAIL, "error", "调用了工具但未取回订单状态"

    # ---- 回复生成：草稿不得包含确定性赔付承诺（话术规范是生成层的职责）----
    if module == "回复生成":
        if has_overpromise(out["draft"]):
            return FAIL, "error", "草稿包含过度承诺话术（确定性赔付承诺）"
        return PASS, "ok", f"草稿流畅合规（{out['prompt_version']}）"

    # ---- 风险拦截：有风险信号却放行 = 失职；拦下或无风险都算尽职 ----
    if module == "风险拦截":
        draft = spans_by_module.get("回复生成", {}).get("output", {}).get("draft", "")
        risky = has_overpromise(draft)
        if risky and out["decision"] == "pass":
            return FAIL, "error", "检出过度承诺风险却未拦截，直接放行"
        if risky and out["decision"] == "block":
            return PASS, "ok", "成功拦截过度承诺风险"
        return PASS, "ok", "回复无风险信号，放行正确"

    return PASS, "ok", "无专项检查规则"


def diagnose_session(spans: List[dict], scenario: str,
                     candidates: List[str]) -> Dict[str, dict]:
    """对一条会话做分模块诊断。按流水线顺序检查候选模块，并把上游错误显式传播为
    下游的 SOFT_PASS——这是区分"真凶"和"被牵连者"的关键机制。"""
    spans_by_module = {s["module"]: s for s in spans}
    required = REQUIRED_STEPS.get(scenario, [])
    to_check = [m for m in PIPELINE_ORDER if m in candidates or m in required]

    results: Dict[str, dict] = {}
    upstream_bad = False
    for module in to_check:
        verdict, kind, reason = _check_module(
            module, spans_by_module.get(module), spans_by_module, scenario)
        if verdict == PASS and upstream_bad:
            verdict = SOFT_PASS
            reason += "；上游已出错，错误可能沿流水线向下传播"
        results[module] = {"verdict": verdict, "kind": kind, "reason": reason}
        if verdict in (FAIL, SOFT_PASS):
            upstream_bad = True
    return results


# ---------------------------------------------------------------------------
# 5. MockLLM：第 3 层兜底定责器（与真实 LLM 客户端同构）
# ---------------------------------------------------------------------------
# 接口与主仓库 labs/llm_client.py 的 QwenLLM 保持一致（chat / simple / __call__，
# 返回 Anthropic 风格响应），生产中可整体替换为真实客户端。
# 它的"推理能力"用确定性模式匹配模拟：这正是实验要演示的现象——缺失型错误的定责
# 需要跨模块推理（谁本应触发却没触发），规则层处理不了，才轮到 LLM。

RCA_SYSTEM_PROMPT = """你是一名资深智能客服系统质量专家，负责对 badcase 做根因定责。
给定问题现象、场景、用户问题、最终回复与分模块诊断结论，请推断唯一的责任模块。
只输出 JSON：{"root_module": str, "confidence": float, "rationale": str}
原则：缺失型错误不能定责给未执行的模块本身，要追问"谁本应触发它却没有触发"。"""


class MockLLM:
    """确定性 mock 定责 LLM。chat() 与真实客户端同构，行为完全可复现。"""

    def __init__(self, name: str = "mock-rca-llm", seed: int = 11):
        self.name = name
        self.calls = 0
        self._rng = random.Random(seed)  # 只用于 mock 延迟，保证 trace 也确定

    def chat(self, messages: List[dict], tools=None, system: Optional[str] = None,
             max_tokens=None, temperature=None) -> dict:
        self.calls += 1
        prompt_text = (system or "") + "\n".join(
            m.get("content", "") for m in messages)
        verdict = self._reason(prompt_text)
        text = json.dumps(verdict, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": len(prompt_text), "output_tokens": len(text)},
            "latency_ms": round(self._rng.uniform(80.0, 400.0), 2),
        }

    def simple(self, prompt: str, system: Optional[str] = None) -> str:
        resp = self.chat([{"role": "user", "content": prompt}], system=system)
        return "".join(b.get("text", "") for b in resp["content"]
                       if b.get("type") == "text")

    def __call__(self, prompt: str, system: Optional[str] = None) -> str:
        return self.simple(prompt, system=system)

    # ---- 内部：确定性"推理"。生产环境里这里就是大模型本身 ----
    def _reason(self, prompt_text: str) -> dict:
        m = re.search(r"prompt_version=([A-Za-z0-9_]+)", prompt_text)
        version = m.group(1) if m else "unknown"
        # 模式 1：必需工具缺失 → 追问决策层（Prompt 驱动的工具调用决策）
        if "必需步骤缺失: 订单状态查询" in prompt_text:
            conf = 0.72 if version == "prompt_v2" else 0.55
            return {
                "root_module": "回复生成",
                "confidence": conf,
                "rationale": (
                    f"订单状态查询工具从未被调用，最终回复却直接承诺了退款结果；"
                    f"工具调用决策由回复生成层的 Prompt 驱动，证据显示 {version} "
                    f"移除了『退款前必须先查订单状态』的硬约束，属提示词回归。"),
            }
        # 兜底：证据不足时给出低置信结论，留给人工复核（而不是硬猜）
        return {"root_module": "unknown", "confidence": 0.3,
                "rationale": "证据不足，建议人工复核并补充根因知识库。"}


# ---------------------------------------------------------------------------
# 6. 第四步：责任判定 —— 三层漏斗（确定性优先、模型辅助）
# ---------------------------------------------------------------------------
# 层级设计的核心逻辑：越确定的方法越靠前。
#   第 1 层（critical_fail）  关键防线模块 FAIL，后果不可逆 → 一票否决，置信度 0.95；
#   第 2 层（rule_pattern）   沿因果链找"最上游的非缺失型 FAIL"，置信度 0.90；
#   第 3 层（llm_fallback）   剩下的都是缺失型/跨模块推理难题，交给 LLM（置信度更低）。
# 漏斗同时是成本漏斗：LLM 调用次数应远小于 badcase 总数。

CONF_CRITICAL = 0.95
CONF_RULE = 0.90


def attribute_responsibility(diagnoses: Dict[str, dict], evidence_text: str,
                             llm: MockLLM) -> dict:
    """三层定责。返回 {root_module, confidence, layer, method, rationale}。"""
    fails = [(m, d) for m, d in diagnoses.items() if d["verdict"] == FAIL]

    # 第 1 层：严重模块 FAIL → 直接定责，不再往下走
    for module, d in fails:
        if module in CRITICAL_MODULES:
            return {
                "root_module": module, "confidence": CONF_CRITICAL,
                "layer": 1, "method": "critical_fail",
                "rationale": (f"严重模块一票否决：{module} 属关键防线，其 FAIL "
                              f"（{d['reason']}）直接定责，不再做后续归因。"),
            }

    # 第 2 层：规则模式匹配 —— 因果链溯源，归因到最上游的"非缺失型" FAIL。
    # 为什么跳过 missing？模块根本没执行，定责给它没有意义——真正的锅在"没触发它的人"。
    ordered = sorted(fails, key=lambda x: PIPELINE_ORDER.index(x[0]))
    for module, d in ordered:
        if d["kind"] != "missing":
            return {
                "root_module": module, "confidence": CONF_RULE,
                "layer": 2, "method": "rule_pattern",
                "rationale": (f"因果链溯源：{module} 是流水线上最靠前的非缺失型 FAIL"
                              f"（{d['reason']}），其后异常视为传播后果。"),
            }

    # 第 3 层：剩下的 FAIL 全是缺失型 → 跨模块推理交给 LLM 兜底
    if fails:
        raw = llm.simple(evidence_text, system=RCA_SYSTEM_PROMPT)
        v = json.loads(raw)
        return {"root_module": v["root_module"], "confidence": v["confidence"],
                "layer": 3, "method": "llm_fallback", "rationale": v["rationale"]}

    return {"root_module": "unknown", "confidence": 0.0, "layer": 0,
            "method": "no_fail", "rationale": "未发现任何 FAIL，可能不是系统错误。"}


# ---------------------------------------------------------------------------
# 7. 第四步（续）+ 第五步：问题分类 / 枚举 / 结构化落盘
# ---------------------------------------------------------------------------
# 评分层给的是"现象"；定责层要补齐三个字段，报告才可消费：
#   问题分类（报告大类：语义理解/知识召回/工具执行/风险防控）
#   枚举（更细的失败类型，根因标签要稳定可统计、指向 owner）
#   修复建议（不能停留在"优化 Prompt"，要有具体动作与 owner）

def classify_issue(symptom: str, root_module: str) -> Tuple[str, str]:
    """(责任模块, 现象) → (问题分类大类, 问题枚举)。"""
    if root_module == "意图识别":
        return "语义理解", "意图误分类"
    if root_module == "Query改写":
        return "语义理解", "改写偏离原意"
    if root_module in ("FAQ检索", "知识检索", "知识筛选"):
        return "知识召回", "过期文档召回"
    if root_module == "风险拦截":
        return "风险防控", "过度承诺未拦截"
    if root_module in ("订单状态查询", "回复生成") and symptom == "跳过校验":
        return "工具执行", "关键工具未调用"
    return "待定", "待人工复核"


FIX_SUGGESTIONS: Dict[str, str] = {
    "意图识别": ("为意图分类器补充退货场景的 few-shot 示例与关键词规则；"
               "本 case 加入意图识别回归集。owner：算法需优化"),
    "知识检索": ("下线知识库中过期版本文档（如 K-1024 v1），检索后增加版本校验过滤器。"
               "owner：运营可配置"),
    "风险拦截": ("将『确定性赔付承诺』加入拦截规则库；赔付类回复一律转人工审批。"
               "owner：工程需修复"),
    "回复生成": ("在回复生成 Prompt 中补回硬约束：退款请求必须先调用订单状态查询"
               "（prompt_v2 → prompt_v3），并对『已发货退款』场景全量回归。"
               "owner：算法需优化"),
}


def build_evidence_text(bc: "Badcase", diagnoses: Dict[str, dict]) -> str:
    """把证据拼成 LLM 兜底要读的文本（真实系统里即 prompt 上下文）。"""
    lines = [
        f"[问题现象] {bc.symptom}",
        f"[场景] {bc.scenario}",
        f"[用户问题] {bc.user_query}",
        f"[最终回复] {bc.final_answer}",
        f"prompt_version={bc.prompt_version}",
        "[分模块诊断]",
    ]
    lines += [f"  {m}: {d['verdict']} — {d['reason']}" for m, d in diagnoses.items()]
    return "\n".join(lines)


def build_rca_record(bc: "Badcase", diagnoses: Dict[str, dict], attribution: dict,
                     issue_class: str, enumeration: str) -> dict:
    """第五步：结构化落盘。字段即 badcase 任务表的 schema，看板/工单系统直接消费。"""
    return {
        "case_id": bc.case_id,
        "session_id": bc.session_id,
        "scenario": bc.scenario,
        "source": bc.source,                    # 入口：离线评测集 or 线上通路
        "issue_class": issue_class,             # 问题分类（报告大类）
        "symptom": bc.symptom,                  # 现象（现象层分类）
        "enumeration": enumeration,             # 枚举（更细失败类型，即根因标签）
        "root_module": attribution["root_module"],  # 责任模块
        "confidence": attribution["confidence"],    # 置信度
        "method": attribution["method"],        # 定责路径（critical/rule/llm）
        "layer": attribution["layer"],
        "evidence": [f"{m}: {d['verdict']} — {d['reason']}"
                     for m, d in diagnoses.items()],   # 证据枚举
        "rationale": attribution["rationale"],
        "prompt_version": bc.prompt_version,
        "fix_suggestion": FIX_SUGGESTIONS.get(
            attribution["root_module"], "证据不足，转人工复核并补充根因知识库"),
    }


# ---------------------------------------------------------------------------
# 8. 聚类：同根因 / 同场景的 badcase 聚成问题簇
# ---------------------------------------------------------------------------
# 报告的价值不在罗列 N 条 badcase，而在聚成少数几个簇并指出共性。
# 聚类键选 (场景, 责任模块) 而非文本相似度：根因标签稳定、可统计、指向 owner，
# 文本相似的两条 case 完全可能是不同根因（反之亦然）。

def cluster_records(records: List[dict]) -> List[dict]:
    groups: Dict[Tuple[str, str], List[dict]] = {}
    for r in records:
        groups.setdefault((r["scenario"], r["root_module"]), []).append(r)
    clusters = []
    for (scenario, module), rs in sorted(groups.items()):
        versions = Counter(r["prompt_version"] for r in rs)
        dom_version, dom_count = sorted(
            versions.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        symptoms = Counter(r["symptom"] for r in rs)
        dom_symptom = sorted(symptoms.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        clusters.append({
            "scenario": scenario,
            "root_module": module,
            "symptom": dom_symptom,
            "count": len(rs),
            "dominant_version": dom_version,
            "dominant_count": dom_count,
            "case_ids": sorted(r["case_id"] for r in rs),
        })
    return clusters


def render_cluster_line(c: dict) -> str:
    return (f"场景 {c['scenario']} 中 {c['count']} 次{c['symptom']}，"
            f"集中在 {c['dominant_version']}（{c['dominant_count']}/{c['count']}），"
            f"责任模块：{c['root_module']}")


# ---------------------------------------------------------------------------
# 9. 实验数据：4 个 badcase + 1 个健康对照会话（原始 trace 日志）
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Badcase:
    case_id: str
    session_id: str
    scenario: str            # 真实场景（人工标注）
    symptom: str             # 现象分类（评分层产出，RCA 的入口）
    user_query: str
    final_answer: str
    expected_behavior: str
    prompt_version: str      # 出问题时回复生成所用的 Prompt 版本
    source: str              # 入口通路：离线评测集 / 线上投诉工单 / 人工质检
    expected_root_module: str  # 人工标注的责任模块（用于自检对答案）
    expected_method: str       # 预期的定责路径


BADCASES: List[Badcase] = [
    # bc-001 答非所问：意图识别把退货问题误判成物流查询，错误一路传播
    Badcase("bc-001", "sess-bc001", "退货退款", "答非所问",
            "我想退货，要怎么操作？",
            "您可以拨打快递公司电话催单，或在物流页面查看最新轨迹。",
            "识别退货意图并给出退货操作流程",
            "prompt_v1", "线上投诉工单", "意图识别", "rule_pattern"),
    # bc-002 事实性错误：知识检索召回过期文档，回复生成忠实引用了错误证据
    Badcase("bc-002", "sess-bc002", "商品咨询", "事实性错误",
            "这款手机的电池容量是多少？",
            "这款手机的电池容量是 3000mAh。",
            "回答 5000mAh（以最新版参数表为准）",
            "prompt_v1", "离线评测集", "知识检索", "rule_pattern"),
    # bc-003 过度承诺：回复生成给出确定性赔付承诺，风险拦截未拦
    Badcase("bc-003", "sess-bc003", "投诉补偿", "过度承诺",
            "快递延误了五天，你们打算怎么补偿？",
            "非常抱歉！我们保证一定给您补偿 200 元现金，百分百立刻到账。",
            "说明补偿需按规则评估并经人工审批，不得确定性承诺",
            "prompt_v2", "人工质检", "风险拦截", "critical_fail"),
    # bc-004 阿里经典案例：已发货订单直接承诺退款，全程未调用订单状态查询。
    # 真实复盘结论：归"工具覆盖与执行"、枚举"关键工具未调用"；本实验的简化模块划分
    # 中，工具调用决策由 Prompt 驱动的回复生成层负责，故责任模块为回复生成。
    Badcase("bc-004", "sess-bc004", "退货退款", "跳过校验",
            "我要退款，订单号 88213，直接帮我退了吧。",
            "好的，已为您提交退款，预计 3 个工作日内原路退回。",
            "先查订单状态：已发货应先拦截物流，不能直接承诺退款",
            "prompt_v2", "线上投诉工单", "回复生成", "llm_fallback"),
]


def _io(sid: str, ts: float, module: str, inp: dict, out: dict) -> dict:
    return {"session_id": sid, "ts": ts, "type": "module_io",
            "module": module, "input": inp, "output": out}


def _hb(sid: str, ts: float) -> dict:
    return {"session_id": sid, "ts": ts, "type": "heartbeat"}


def build_raw_logs() -> List[dict]:
    """构造 5 条会话的原始日志：多会话交错、乱序到达、混入心跳噪声——
    刻意模拟线上日志的真实形态，验证第一步聚合的健壮性。"""
    q1 = BADCASES[0].user_query
    q2 = BADCASES[1].user_query
    q3 = BADCASES[2].user_query
    q4 = BADCASES[3].user_query
    logs: List[dict] = [
        # ---- sess-bc001（答非所问）----
        _io("sess-bc001", 1001.0, "意图识别", {"query": q1},
            {"intent": "物流查询", "confidence": 0.61}),
        _hb("sess-bc001", 1001.5),
        _io("sess-bc001", 1002.0, "Query改写", {"query": q1, "intent": "物流查询"},
            {"rewritten": "快递一直没到，我该怎么催单？"}),
        _io("sess-bc001", 1003.0, "知识筛选", {"intent": "物流查询"},
            {"selected_sources": ["物流知识库"]}),
        _io("sess-bc001", 1004.0, "FAQ检索", {"rewritten": "快递一直没到，我该怎么催单？"},
            {"hits": ["FAQ-物流催单"], "top_score": 0.83}),
        # ---- sess-bc003（过度承诺）交错插入，模拟乱序 ----
        _io("sess-bc003", 3001.0, "意图识别", {"query": q3},
            {"intent": "投诉补偿", "confidence": 0.88}),
        _io("sess-bc001", 1005.0, "回复生成", {"prompt_version": "prompt_v1"},
            {"draft": BADCASES[0].final_answer, "prompt_version": "prompt_v1"}),
        _io("sess-bc003", 3002.0, "知识检索", {"intent": "投诉补偿"},
            {"doc_id": "K-3007", "doc_version": 2, "doc_title": "补偿规则（2026 版）",
             "relevance": 0.88, "snippet": "补偿以优惠券为主，上限 50 元，需人工审批"}),
        _io("sess-bc001", 1006.0, "风险拦截", {"draft": BADCASES[0].final_answer},
            {"decision": "pass", "risk_signals": []}),
        _hb("sess-bc003", 3002.5),
        _io("sess-bc003", 3003.0, "回复生成", {"prompt_version": "prompt_v2"},
            {"draft": BADCASES[2].final_answer, "prompt_version": "prompt_v2"}),
        _io("sess-bc003", 3004.0, "风险拦截", {"draft": BADCASES[2].final_answer},
            {"decision": "pass", "risk_signals": []}),
        # ---- sess-bc002（事实性错误）----
        _io("sess-bc002", 2001.0, "意图识别", {"query": q2},
            {"intent": "商品咨询", "confidence": 0.93}),
        _io("sess-bc002", 2002.0, "Query改写", {"query": q2, "intent": "商品咨询"},
            {"rewritten": "这款手机电池容量多大？"}),
        _io("sess-bc002", 2003.0, "FAQ检索", {"rewritten": "这款手机电池容量多大？"},
            {"hits": [], "top_score": 0.42}),
        _hb("sess-bc002", 2003.5),
        _io("sess-bc002", 2004.0, "知识检索", {"rewritten": "这款手机电池容量多大？"},
            {"doc_id": "K-1024", "doc_version": 1, "doc_title": "手机 X1 参数表（2024 旧版）",
             "relevance": 0.91, "snippet": "电池容量 3000mAh"}),
        _io("sess-bc002", 2005.0, "回复生成", {"prompt_version": "prompt_v1"},
            {"draft": BADCASES[1].final_answer, "prompt_version": "prompt_v1"}),
        # ---- sess-bc004（阿里案例：订单状态查询 span 整个缺失）----
        _io("sess-bc004", 4001.0, "意图识别", {"query": q4},
            {"intent": "退货退款", "confidence": 0.95}),
        _io("sess-bc004", 4002.0, "Query改写", {"query": q4, "intent": "退货退款"},
            {"rewritten": "订单 88213 如何办理退款？"}),
        _io("sess-bc004", 4003.0, "知识筛选", {"intent": "退货退款"},
            {"selected_sources": ["退货政策库"]}),
        _io("sess-bc004", 4004.0, "知识检索", {"rewritten": "订单 88213 如何办理退款？"},
            {"doc_id": "K-2019", "doc_version": 3, "doc_title": "退货流程（2026 版）",
             "relevance": 0.89,
             "snippet": "退款前必须先确认订单状态：未发货可直接退款，已发货需先拦截物流"}),
        _hb("sess-bc004", 4004.5),
        _io("sess-bc004", 4005.0, "回复生成", {"prompt_version": "prompt_v2"},
            {"draft": BADCASES[3].final_answer, "prompt_version": "prompt_v2"}),
        # ---- sess-ok-005（健康对照会话：退货流程完整执行，用于验证诊断不误报）----
        _io("sess-ok-005", 5001.0, "意图识别", {"query": "这款手机的屏幕尺寸是多少？"},
            {"intent": "商品咨询", "confidence": 0.96}),
        _io("sess-ok-005", 5002.0, "Query改写",
            {"query": "这款手机的屏幕尺寸是多少？", "intent": "商品咨询"},
            {"rewritten": "这款手机屏幕尺寸多大？"}),
        _io("sess-ok-005", 5003.0, "知识筛选", {"intent": "商品咨询"},
            {"selected_sources": ["FAQ"]}),
        _io("sess-ok-005", 5004.0, "FAQ检索", {"rewritten": "这款手机屏幕尺寸多大？"},
            {"hits": ["FAQ-X1-屏幕"], "top_score": 0.86}),
        _hb("sess-ok-005", 5004.5),
        _io("sess-ok-005", 5005.0, "回复生成", {"prompt_version": "prompt_v1"},
            {"draft": "这款手机的屏幕尺寸是 6.7 英寸。", "prompt_version": "prompt_v1"}),
        _io("sess-ok-005", 5006.0, "风险拦截",
            {"draft": "这款手机的屏幕尺寸是 6.7 英寸。"},
            {"decision": "pass", "risk_signals": []}),
        _hb("sess-ok-005", 5006.5),
    ]
    return logs


# 历史 badcase 库（脱敏后的结构化记录）：聚类时与本次新诊断的记录合并。
# 现实如此：聚类永远面向"任务表全量"，而不是只看今天这一批。
HISTORICAL_RECORDS: List[dict] = [
    {"case_id": "hist-01", "scenario": "退货退款", "symptom": "跳过校验",
     "root_module": "回复生成", "prompt_version": "prompt_v2"},
    {"case_id": "hist-02", "scenario": "退货退款", "symptom": "跳过校验",
     "root_module": "回复生成", "prompt_version": "prompt_v2"},
    {"case_id": "hist-03", "scenario": "退货退款", "symptom": "跳过校验",
     "root_module": "回复生成", "prompt_version": "prompt_v2"},
    {"case_id": "hist-04", "scenario": "退货退款", "symptom": "跳过校验",
     "root_module": "回复生成", "prompt_version": "prompt_v1"},
    {"case_id": "hist-05", "scenario": "退货退款", "symptom": "答非所问",
     "root_module": "意图识别", "prompt_version": "prompt_v1"},
    {"case_id": "hist-06", "scenario": "商品咨询", "symptom": "事实性错误",
     "root_module": "知识检索", "prompt_version": "prompt_v1"},
    {"case_id": "hist-07", "scenario": "商品咨询", "symptom": "事实性错误",
     "root_module": "知识检索", "prompt_version": "prompt_v1"},
    {"case_id": "hist-08", "scenario": "投诉补偿", "symptom": "过度承诺",
     "root_module": "风险拦截", "prompt_version": "prompt_v2"},
]


# ---------------------------------------------------------------------------
# 10. RCA 流水线编排：五步串起来
# ---------------------------------------------------------------------------

def run_rca_pipeline(badcases: List[Badcase], sessions: Dict[str, List[dict]],
                     llm: MockLLM) -> List[dict]:
    records = []
    for bc in badcases:
        spans = sessions[bc.session_id]                    # 第一步：证据汇总（已完成）
        candidates = narrow_scope(bc.symptom, bc.scenario)  # 第二步：范围收敛
        diagnoses = diagnose_session(spans, bc.scenario, candidates)  # 第三步：分模块诊断
        evidence = build_evidence_text(bc, diagnoses)
        attribution = attribute_responsibility(diagnoses, evidence, llm)  # 第四步：责任判定
        issue_class, enumeration = classify_issue(bc.symptom, attribution["root_module"])
        records.append(build_rca_record(bc, diagnoses, attribution,
                                        issue_class, enumeration))        # 第五步：落盘
    return records


# ---------------------------------------------------------------------------
# 11. 自检：断言全部核心结论（不是"跑完了"，而是"定对了"）
# ---------------------------------------------------------------------------

def run_self_checks(sessions, noise, records, clusters, llm) -> None:
    by_id = {r["case_id"]: r for r in records}

    # (a) 第一步·证据汇总：乱序日志被正确重建，噪声被丢弃
    assert set(sessions) == {"sess-bc001", "sess-bc002", "sess-bc003",
                             "sess-bc004", "sess-ok-005"}, "会话聚合数量错误"
    assert noise == 6, f"应丢弃 6 条心跳噪声，实际 {noise}"
    for spans in sessions.values():
        ts_list = [s["ts"] for s in spans]
        assert ts_list == sorted(ts_list), "会话内 span 必须按 ts 升序"
    # 顺序无关性：任意打乱输入，聚合结果完全一致（这才是"可复现"的含义）
    shuffled = list(build_raw_logs())
    random.Random(2026).shuffle(shuffled)
    s2, n2 = aggregate_evidence(shuffled)
    assert s2 == sessions and n2 == noise, "聚合结果必须与日志到达顺序无关"

    # (b) 第二步·范围收敛：映射表与规格一致，且只缩圈不定责
    assert SCOPE_MAP["答非所问"] == ["意图识别", "Query改写", "知识筛选"]
    assert SCOPE_MAP["事实性错误"] == ["FAQ检索", "知识检索", "回复生成"]
    assert SCOPE_MAP["过度承诺"] == ["风险拦截", "回复生成"]
    assert narrow_scope("跳过校验", "退货退款")[0] == "订单状态查询"

    # (c) 第三步·分模块诊断：三态结论符合预期（重跑一次诊断验证）
    d1 = diagnose_session(sessions["sess-bc001"], "退货退款",
                          narrow_scope("答非所问", "退货退款"))
    assert d1["意图识别"]["verdict"] == FAIL, "bc-001 意图识别应 FAIL"
    assert d1["Query改写"]["verdict"] == FAIL, "bc-001 改写偏离应 FAIL"
    assert d1["知识筛选"]["verdict"] == SOFT_PASS, "bc-001 知识筛选应被标记为上游传播"
    d2 = diagnose_session(sessions["sess-bc002"], "商品咨询",
                          narrow_scope("事实性错误", "商品咨询"))
    assert d2["知识检索"]["verdict"] == FAIL and "过期版本" in d2["知识检索"]["reason"]
    assert d2["回复生成"]["verdict"] == SOFT_PASS, "忠实引用错误证据应为 SOFT_PASS 而非 FAIL"
    d3 = diagnose_session(sessions["sess-bc003"], "投诉补偿",
                          narrow_scope("过度承诺", "投诉补偿"))
    assert d3["风险拦截"]["verdict"] == FAIL and d3["回复生成"]["verdict"] == FAIL
    d4 = diagnose_session(sessions["sess-bc004"], "退货退款",
                          narrow_scope("跳过校验", "退货退款"))
    assert d4["订单状态查询"]["verdict"] == FAIL and d4["订单状态查询"]["kind"] == "missing"
    assert d4["回复生成"]["verdict"] == SOFT_PASS
    # 健康对照会话：诊断器不能误报（无 FAIL）
    dok = diagnose_session(sessions["sess-ok-005"], "商品咨询", list(PIPELINE_ORDER))
    assert all(d["verdict"] != FAIL for d in dok.values()), "健康会话不允许出现 FAIL"

    # (d) 第四步·责任判定：每个 badcase 的责任模块与人工标注一致
    expect = {
        "bc-001": ("意图识别", "rule_pattern", 2),
        "bc-002": ("知识检索", "rule_pattern", 2),
        "bc-003": ("风险拦截", "critical_fail", 1),
        "bc-004": ("回复生成", "llm_fallback", 3),
    }
    for cid, (module, method, layer) in expect.items():
        r = by_id[cid]
        assert r["root_module"] == module, f"{cid} 责任模块应为 {module}，实际 {r['root_module']}"
        assert r["method"] == method and r["layer"] == layer, f"{cid} 定责路径错误"
        bc = next(b for b in BADCASES if b.case_id == cid)
        assert r["root_module"] == bc.expected_root_module, f"{cid} 与人工标注不一致"

    # (e) 置信度漏斗：越确定的层置信度越高（critical > rule > llm）
    assert by_id["bc-003"]["confidence"] == CONF_CRITICAL == 0.95
    assert by_id["bc-001"]["confidence"] == by_id["bc-002"]["confidence"] == CONF_RULE == 0.90
    assert by_id["bc-004"]["confidence"] == 0.72
    assert CONF_CRITICAL > CONF_RULE > by_id["bc-004"]["confidence"], "置信度必须随层级递减"
    # 成本漏斗：LLM 兜底只被调用了 1 次（只有规则搞不定的 case 才花这个钱）
    assert llm.calls == 1, f"LLM 兜底应只触发 1 次，实际 {llm.calls} 次"

    # (f) 第五步·结构化落盘：必备字段齐全、可 JSON 往返（看板/工单可直接消费）
    required = ("issue_class", "symptom", "enumeration",
                "root_module", "confidence", "fix_suggestion")
    for r in records:
        for k in required:
            assert k in r and r[k] not in ("", None, 0) or k == "confidence", \
                f"{r['case_id']} 缺少落盘字段 {k}"
        assert r["evidence"], f"{r['case_id']} 证据枚举不能为空"
        assert json.loads(json.dumps(r, ensure_ascii=False)) == r, "落盘记录必须可 JSON 往返"
    # 四个报告大类恰好各出现一次 —— 问题分类覆盖语义理解/知识召回/风险防控/工具执行
    assert sorted(r["issue_class"] for r in records) == ["工具执行", "知识召回", "语义理解", "风险防控"]
    assert by_id["bc-004"]["enumeration"] == "关键工具未调用", "阿里案例的枚举标签必须稳定可统计"

    # (g) 聚类：簇数量、簇大小、主导 Prompt 版本全部符合预期
    assert len(clusters) == 4, f"应聚成 4 个问题簇，实际 {len(clusters)}"
    by_key = {(c["scenario"], c["root_module"]): c for c in clusters}
    c_refund = by_key[("退货退款", "回复生成")]
    assert c_refund["count"] == 5 and c_refund["symptom"] == "跳过校验"
    assert c_refund["dominant_version"] == "prompt_v2" and c_refund["dominant_count"] == 4
    line = render_cluster_line(c_refund)
    assert "场景 退货退款 中 5 次跳过校验，集中在 prompt_v2" in line, "聚类报告措辞不符合规格"
    assert by_key[("退货退款", "意图识别")]["count"] == 2
    assert by_key[("商品咨询", "知识检索")]["count"] == 3
    assert by_key[("投诉补偿", "风险拦截")]["count"] == 2
    assert sum(c["count"] for c in clusters) == 12, "簇内记录总数应等于任务表全量（4 新 + 8 历史）"

    # (h) MockLLM 与真实客户端同构且确定：结构正确 + 同输入同输出
    probe = MockLLM(seed=99)
    sample = "必需步骤缺失: 订单状态查询\nprompt_version=prompt_v2"
    resp = probe.chat([{"role": "user", "content": sample}], system=RCA_SYSTEM_PROMPT)
    assert resp["content"][0]["type"] == "text" and resp["stop_reason"] == "end_turn"
    assert probe.simple(sample) == probe.simple(sample), "MockLLM 必须确定性可复现"


# ---------------------------------------------------------------------------
# 12. 演示入口：分步运行整条流水线并打印报告
# ---------------------------------------------------------------------------

def main() -> None:
    random.seed(20260805)  # 固定种子：本文件任何随机行为都可复现
    print("=" * 68)
    print("LAB eval_lab09 · Badcase 根因分析（RCA）流水线（纯标准库 / 确定性）")
    print("=" * 68)

    # [1/6] 证据汇总
    raw = build_raw_logs()
    sessions, noise = aggregate_evidence(raw)
    print(f"\n[1/6] 证据汇总：{len(raw)} 条乱序日志 → {len(sessions)} 条会话，"
          f"丢弃噪声 {noise} 条")
    for sid in sorted(sessions):
        mods = " → ".join(s["module"] for s in sessions[sid])
        print(f"   - {sid}: {len(sessions[sid])} 个 span | {mods}")

    # [2/6] 范围收敛
    print("\n[2/6] 范围收敛（现象 × 模块映射表，只缩圈、不定责）：")
    for symptom, modules in SCOPE_MAP.items():
        print(f"   - {symptom:<6} → {modules}")

    # [3/6] + [4/6] 分模块诊断与三层定责
    llm = MockLLM()
    print("\n[3/6] 分模块诊断 与 [4/6] 三层责任判定：")
    records = []
    for bc in BADCASES:
        candidates = narrow_scope(bc.symptom, bc.scenario)
        diagnoses = diagnose_session(sessions[bc.session_id], bc.scenario, candidates)
        evidence = build_evidence_text(bc, diagnoses)
        attribution = attribute_responsibility(diagnoses, evidence, llm)
        issue_class, enumeration = classify_issue(bc.symptom, attribution["root_module"])
        records.append(build_rca_record(bc, diagnoses, attribution,
                                        issue_class, enumeration))
        print(f"\n   ◆ {bc.case_id} [{bc.symptom}] {bc.user_query}")
        for m, d in diagnoses.items():
            print(f"      {m:<6} {d['verdict']:<9} {d['reason']}")
        print(f"      ⇒ 定责: {attribution['root_module']}"
              f"（第 {attribution['layer']} 层 {attribution['method']}，"
              f"置信度 {attribution['confidence']}）")
    funnel = Counter(r["layer"] for r in records)
    print(f"\n   三层漏斗分布：第1层(严重FAIL) {funnel.get(1, 0)} 条，"
          f"第2层(规则) {funnel.get(2, 0)} 条，第3层(LLM兜底) {funnel.get(3, 0)} 条"
          f" —— LLM 仅调用 {llm.calls} 次")

    # [5/6] 结构化落盘
    print("\n[5/6] 结构化落盘（badcase 任务表 schema）：")
    for r in records:
        print(f"   - {r['case_id']}: 分类={r['issue_class']} 现象={r['symptom']} "
              f"枚举={r['enumeration']} 责任={r['root_module']} 置信度={r['confidence']}")
    print("\n   bc-004（阿里案例）完整记录预览：")
    preview = {k: records[3][k] for k in
               ("issue_class", "symptom", "enumeration", "root_module",
                "confidence", "fix_suggestion")}
    print("   " + json.dumps(preview, ensure_ascii=False, indent=2).replace("\n", "\n   "))

    # [6/6] 聚类：面向任务表全量（4 条新诊断 + 8 条历史）
    slim_new = [{"case_id": r["case_id"], "scenario": r["scenario"],
                 "symptom": r["symptom"], "root_module": r["root_module"],
                 "prompt_version": r["prompt_version"]} for r in records]
    clusters = cluster_records(HISTORICAL_RECORDS + slim_new)
    print("\n[6/6] 问题簇聚类（全量 12 条 = 8 历史 + 4 新诊断）：")
    for c in clusters:
        print(f"   - {render_cluster_line(c)}")
        print(f"       case_ids: {c['case_ids']}")
    print("\n   结论：『退货退款 × 跳过校验』已成簇且集中在 prompt_v2 ——")
    print("   行动项：prompt_v2 → v3 补回『先查订单状态』硬约束，并对该场景全量回归。")

    # 自检
    print("\n[自检] 运行 assert 断言（五步正确性 + 定责一致性 + 聚类 + 可复现性）...")
    run_self_checks(sessions, noise, records, clusters, llm)
    print("   4 个 badcase 责任模块与人工标注全部一致 ✔")
    print("   置信度漏斗 0.95 > 0.90 > 0.72，LLM 兜底仅 1 次 ✔")
    print("   4 个问题簇（合计 12 条），退货簇 5 次集中于 prompt_v2 ✔")
    print("\n✅ 自检通过：eval_lab09_rca_pipeline.py 全部断言成立")


if __name__ == "__main__":
    main()
