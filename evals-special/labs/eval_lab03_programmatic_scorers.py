#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab03_programmatic_scorers.py — 程序化评分与分层筛查
==========================================================

【实验目的】
    动手实现一族「程序化评分器（deterministic scorers）」和一条「粗筛 → 精判」
    两层评估流水线，让读者理解：Agent 评测不是"肉眼看答案像不像对"，而是用
    确定性规则把"好/坏"拆成可检查、可分类、可聚合的工程信号；并通过分层路由，
    把昂贵的判定能力只花在真正需要的样本上。本实验覆盖三个要点：
        1) 评分器家族 —— JSON schema 校验、空/异常长度检测、关键词黑白名单、
           工具调用断言（是否调用 + 参数正确性）、执行指标（调用次数上限、耗时预算）；
        2) 评分输出规范 —— 每个评分器统一返回 {score, pass/fail, 问题分类,
           置信度, 判定依据}，而不只是布尔值：问题分类是下游 RCA 的"现象入口"，
           置信度与判定依据决定样本要不要升级人工复核；
        3) 分层筛查流水线 —— 粗筛层（便宜规则）拦截"明确失败"，精判层
           （昂贵规则 + LLM Judge）确认"边界样本"，并用调用次数与成本单元
           定量验证路由正确性和成本节省。

【对应章节】
    本特辑第 E04 章 · 评分三层之一：程序化评分
    （对应方法论：规则主判、Judge 辅助、人工兜底；粗筛层 → 精判层 → 人工复核层）

【核心概念】
    - 程序化评分器: 把"硬条件"（格式、字段、工具、状态、禁用词）写成代码断言。
      优点是零成本、零漂移、可单测；边界是只能判"能写成规则的东西"，语义合理性
      要留给 LLM Judge / 人工。评委选择顺序：确定性 > Rubric > 人工。
    - 评分输出规范: 评分结果不止 pass/fail。问题分类（现象层，如"工具未调用"）
      用于 badcase 聚类与根因路由；置信度决定"自动采信还是升级复核"；判定依据
      让每条失败可解释、可回放。现象分类 ≠ 最终根因，它只是进入 RCA 的入口。
    - 分层筛查: 粗筛层用便宜规则快速分离"明确失败 / 继续检查"；精判层用昂贵
      手段（trace 解析、LLM 语义判定）确认边界样本。关键纪律：粗筛已明确失败的
      样本绝不进精判——否则昂贵判定被垃圾样本稀释，评测成本随样本量线性恶化。
      生产上精判之后还有人工复核层（高风险/低置信/口径未固化），本实验聚焦前两层。
    - 成本模型: 每个评分器带 cost_units（相对成本）。粗筛是微秒级纯文本操作；
      精判要解析完整 trace 并可能触发一次 LLM 往返，贵 1~2 个数量级。"成本节省"
      不是感觉，而是 baseline（全量走全套）与实际分层开销的比值。

【如何运行】
    cd evals-special/labs && python3 eval_lab03_programmatic_scorers.py
    （纯 Python 标准库、零依赖、固定随机种子；任何机器上结果一致）

【思考题（面试延伸）】
    1. 为什么评分输出必须带"问题分类 / 置信度 / 判定依据"，只报 pass/fail 会失去
       什么？（提示：badcase 聚类、RCA 的现象入口、人工复核路由、误报申诉。）
    2. 粗筛 / 精判的分层依据是什么？把"执行指标（调用次数、耗时）"放粗筛层合理吗？
       （提示：分层的不仅是耗时，更是"依赖的信息范围"——只看输出文本本身的规则
       最便宜，需要完整 trace / 上下文 / LLM 的判定最贵。）
    3. 各举一个"规则能判但 LLM 判不稳"与"LLM 能判但规则写不出"的检查项。
       规则主判、Judge 辅助、人工兜底的边界怎么划？口径由谁来定？
    4. 评分器自己也会有 bug（误杀正确样本 / 放过坏样本）。你会用哪些手段给
       "评分器本身"做质量保障？（提示：golden 正负样本、评分器变更走回归、
       线上抽检与评分器结论的一致率监控。）
    5. 本实验的 MockJudge 可以无缝替换成真实 LLM Judge 客户端，这种可替换性靠
       什么接口设计保证？如果 Judge 输出带随机性，评测如何保持可复现？
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- 1. 评分输出规范：绝不止 pass/fail ---
# 设计动机：一条失败样本如果只告诉你"fail"，下游什么都做不了——不知道是哪个环节
# 坏了（无法聚类）、不知道判定有多可靠（无法决定要不要人工复核）、不知道为什么失败
# （无法回放调试）。所以每个评分器都必须输出同样的五元组：
#   score 连续分（便于灰度阈值与漂移观察）/ passed 门禁硬判定 /
#   issue 问题分类（现象层标签，RCA 入口，现象 ≠ 根因）/
#   confidence 本评分器对结论的把握度（低置信升级人工）/ evidence 判定依据。

# 问题分类常量（现象层）。用常量而不是裸字符串，是为了让分类体系可枚举、
# 可统计、可被下游 RCA 映射表消费。
ISSUE_NONE = "none"                              # 通过，无问题
ISSUE_EMPTY_OUTPUT = "empty_output"              # 空输出
ISSUE_TOO_SHORT = "too_short"                    # 异常过短
ISSUE_TOO_LONG = "too_long"                      # 异常过长（疑似失控/冗余刷屏）
ISSUE_INVALID_JSON = "invalid_json"              # JSON 损坏，无法解析
ISSUE_MISSING_FIELD = "missing_field"            # 缺少必填字段
ISSUE_TYPE_ERROR = "type_error"                  # 字段类型错误
ISSUE_BLACKLIST_HIT = "blacklist_hit"            # 命中黑名单（过度承诺/注入回声等）
ISSUE_WHITELIST_MISSING = "whitelist_missing"    # 缺少白名单要求的必备内容
ISSUE_TOOL_NOT_CALLED = "tool_not_called"        # 关键工具未调用
ISSUE_TOOL_PARAM_ERROR = "tool_param_error"      # 工具调用了但参数错误
ISSUE_TOO_MANY_CALLS = "too_many_calls"          # 工具调用次数超上限
ISSUE_TIME_BUDGET_EXCEEDED = "time_budget_exceeded"  # 总耗时超预算

ALL_ISSUES = (
    ISSUE_NONE, ISSUE_EMPTY_OUTPUT, ISSUE_TOO_SHORT, ISSUE_TOO_LONG,
    ISSUE_INVALID_JSON, ISSUE_MISSING_FIELD, ISSUE_TYPE_ERROR,
    ISSUE_BLACKLIST_HIT, ISSUE_WHITELIST_MISSING, ISSUE_TOOL_NOT_CALLED,
    ISSUE_TOOL_PARAM_ERROR, ISSUE_TOO_MANY_CALLS, ISSUE_TIME_BUDGET_EXCEEDED,
)

# 中文展示名（报告给人看；程序内部一律用英文常量）
ISSUE_CN: Dict[str, str] = {
    ISSUE_NONE: "通过", ISSUE_EMPTY_OUTPUT: "空输出", ISSUE_TOO_SHORT: "异常过短",
    ISSUE_TOO_LONG: "异常过长", ISSUE_INVALID_JSON: "JSON损坏",
    ISSUE_MISSING_FIELD: "缺必填字段", ISSUE_TYPE_ERROR: "字段类型错误",
    ISSUE_BLACKLIST_HIT: "命中黑名单", ISSUE_WHITELIST_MISSING: "缺白名单内容",
    ISSUE_TOOL_NOT_CALLED: "关键工具未调用", ISSUE_TOOL_PARAM_ERROR: "工具参数错误",
    ISSUE_TOO_MANY_CALLS: "调用次数超限", ISSUE_TIME_BUDGET_EXCEEDED: "耗时超预算",
}


@dataclass
class ScoreResult:
    """统一的评分输出。任何评分器（规则或 LLM Judge 包装）都必须返回它。"""
    scorer: str        # 评分器名：便于追溯"这条结论是谁下的"
    score: float       # [0,1] 连续分；失败取低分，通过取 1.0
    passed: bool       # 门禁硬判定
    issue: str         # 问题分类（ALL_ISSUES 之一；通过时为 ISSUE_NONE）
    confidence: float  # [0,1] 本评分器对结论的把握度
    evidence: str      # 判定依据（人可读，可回放核对）


# --- 2. 样本结构与评分器基类 ---
# 场景设定：电商客服 Agent 的「退款处理」任务。Agent 的最终输出必须是一段
# JSON（answer/action/order_id/amount），执行过程以 tool_calls（trace 摘要）
# 形式给出。评分器家族围绕这两类产物展开检查。

@dataclass
class Sample:
    id: str
    output_text: str          # Agent 的最终输出文本（约定为 JSON 字符串）
    tool_calls: List[dict]    # trace: [{"name", "params", "duration_ms"}, ...]
    context: dict             # 业务上下文：order_id / order_amount / required_tools
    # 期望结果（出题人视角）：自检用它逐条核对流水线判定是否正确。
    # expect_blocked: "coarse"=应在粗筛被拦；"fine"=应进精判层才被拦；None=应通过
    expect_blocked: Optional[str]
    expect_issue: str         # 期望的问题分类（通过样本为 ISSUE_NONE）


class Scorer:
    """评分器基类：声明所属层与成本，强制统一的输出规范。

    cost_units 是相对成本而非真实毫秒：粗筛是纯文本/JSON 操作（微秒级），
    精判要解析完整 trace、还可能触发一次 LLM 往返（贵 1~2 个数量级）。
    分层与成本统计都建立在这个声明上——这也是面试常考点："你怎么给评分器定价？"
    """
    name: str = "base"
    tier: str = "coarse"      # "coarse"（粗筛）或 "fine"（精判）
    cost_units: int = 1

    def score(self, sample: Sample) -> ScoreResult:
        raise NotImplementedError

    @staticmethod
    def ok(scorer: str, evidence: str, confidence: float = 0.8) -> ScoreResult:
        """通过结果。注意通过也不给满置信：单项通过不代表整体没问题。"""
        return ScoreResult(scorer, 1.0, True, ISSUE_NONE, confidence, evidence)

    @staticmethod
    def fail(scorer: str, issue: str, evidence: str,
             confidence: float = 1.0, score: float = 0.0) -> ScoreResult:
        """失败结果。确定性规则给高置信；语义判定（LLM）应适当调低。"""
        return ScoreResult(scorer, score, False, issue, confidence, evidence)


# --- 3. 粗筛层：三个便宜规则评分器 ---
# 粗筛的共同特点：只看 output_text 本身，不碰 trace、不调外部服务，微秒级完成。
# 使命是把"明确失败"的样本在花大钱之前拦下来。顺序也有讲究：
# 最便宜、命中率最高的检查放最前面（长度 → JSON → 关键词）。

class LengthAnomalyScorer(Scorer):
    """空 / 过短 / 过长检测。成本最低（一次 len），放流水线第一位。
    为什么长度异常要单独设分类：空输出多半是生成崩溃或超时截断，过长多半是
    失控复读——两者根因完全不同，混在一个 fail 里就丢了信息。"""
    name, tier, cost_units = "length_anomaly", "coarse", 1
    MIN_LEN, MAX_LEN = 16, 400

    def score(self, sample: Sample) -> ScoreResult:
        text = sample.output_text.strip()
        if not text:
            return self.fail(self.name, ISSUE_EMPTY_OUTPUT,
                             "输出为空（或仅空白字符），疑似生成崩溃/超时截断")
        if len(text) < self.MIN_LEN:
            return self.fail(self.name, ISSUE_TOO_SHORT,
                             f"输出仅 {len(text)} 字符 < 下限 {self.MIN_LEN}，"
                             f"连最小 JSON 结构都装不下")
        if len(text) > self.MAX_LEN:
            return self.fail(self.name, ISSUE_TOO_LONG,
                             f"输出 {len(text)} 字符 > 上限 {self.MAX_LEN}，"
                             f"疑似失控复读/冗余刷屏", score=0.2)
        return self.ok(self.name, f"长度 {len(text)} ∈ [{self.MIN_LEN},{self.MAX_LEN}]")


class JsonSchemaScorer(Scorer):
    """JSON 可解析性 + 必填字段 + 类型校验（最小 schema 实现）。
    为什么规则先于语义：解析失败/缺字段的样本根本谈不上"内容对不对"，
    让它们进入精判层纯属浪费 LLM 调用。"""
    name, tier, cost_units = "json_schema", "coarse", 2

    # 输出契约：客服 Agent 最终回复必须是这个结构
    REQUIRED_FIELDS: Dict[str, Tuple[type, ...]] = {
        "answer": (str,), "action": (str,),
        "order_id": (str,), "amount": (int, float),
    }

    def score(self, sample: Sample) -> ScoreResult:
        try:
            data = json.loads(sample.output_text)
        except ValueError:
            head = sample.output_text.strip()[:30]
            return self.fail(self.name, ISSUE_INVALID_JSON,
                             f"JSON 解析失败，开头为「{head}…」，疑似被截断")
        if not isinstance(data, dict):
            return self.fail(self.name, ISSUE_INVALID_JSON,
                             f"顶层应为 JSON 对象，实际是 {type(data).__name__}")
        missing = [k for k in self.REQUIRED_FIELDS if k not in data]
        if missing:
            return self.fail(self.name, ISSUE_MISSING_FIELD, f"缺少必填字段: {missing}")
        for key, types in self.REQUIRED_FIELDS.items():
            value = data[key]
            # bool 是 int 的子类，必须显式排除——这是 JSON 校验的经典陷阱
            if isinstance(value, bool) or not isinstance(value, types):
                want = "/".join(t.__name__ for t in types)
                return self.fail(self.name, ISSUE_TYPE_ERROR,
                                 f"字段 {key} 期望 {want}，实际 "
                                 f"{type(value).__name__}={value!r}")
        return self.ok(self.name, f"JSON 合法且 {len(self.REQUIRED_FIELDS)} 个必填字段类型正确")


# 黑名单：出现即拦截。模拟三类生产常见禁用内容：
#   过度承诺（资损风险）、灰色渠道话术（合规风险）、提示注入回声（安全风险）。
BLACKLIST: List[str] = ["百分百赔付", "内部员工通道", "忽略以上指令"]

# 白名单规则：(触发词, 必备内容, 业务原因)。与黑名单"出现即失败"相反，
# 白名单是"一旦触发某场景，就必须包含某内容"——本质是把业务 SOP 写成断言。
WHITELIST_RULES: List[Tuple[str, str, str]] = [
    ("退款", "1-3个工作日", "提及退款时必须明示到账时效承诺，否则属过度承诺边缘"),
]


class KeywordListScorer(Scorer):
    """关键词黑白名单。黑名单优先于白名单（命中黑名单直接返回）。"""
    name, tier, cost_units = "keyword_list", "coarse", 1

    def score(self, sample: Sample) -> ScoreResult:
        text = sample.output_text
        for word in BLACKLIST:
            if word in text:
                return self.fail(self.name, ISSUE_BLACKLIST_HIT,
                                 f"命中黑名单词「{word}」（禁用话术）")
        for trigger, required, reason in WHITELIST_RULES:
            if trigger in text and required not in text:
                return self.fail(self.name, ISSUE_WHITELIST_MISSING,
                                 f"出现「{trigger}」但缺少必备内容「{required}」"
                                 f"（{reason}）", confidence=0.95)
        return self.ok(self.name, "未命中黑名单；白名单触发项均满足")


# --- 4. 精判层：MockJudge + 两个昂贵规则评分器 ---
# 精判层检查依赖完整 trace 与业务上下文，参数正确性属于"语义级"判定，交给
# MockJudge（模拟 LLM Judge 的一次昂贵调用）。生产中把 MockJudge 换成真实
# LLM 客户端即可——接口同构（chat() 收 messages 返回字符串）。

JUDGE_SYSTEM_PROMPT = (
    "你是工具调用审查员。给定业务上下文与实际工具调用序列，"
    "逐个核对关键工具的参数是否与上下文一致、数值是否在合法范围内。"
    "只输出 JSON：{\"valid\": bool, \"problems\": [...], \"confidence\": float}"
)


class MockJudge:
    """确定性 Mock LLM Judge。
    - chat(messages) 与真实 LLM 客户端同构：收 role/content 消息列表，返回字符串；
    - __call__(task) 是便捷入口：直接吃 dict，返回解析后的结构；
    - 判定逻辑完全确定（字段比对 + 数值范围），随机源只用于模拟网络延迟，
      因此评测结论可复现，连延迟数据也确定可复现。
    """
    def __init__(self, name: str = "mock-judge-v1", seed: int = 23):
        self.name = name
        self._rng = random.Random(seed)
        self.call_count = 0          # 被调用次数——成本核算的关键观测值
        self.total_latency_ms = 0.0  # 累计模拟延迟

    def chat(self, messages: List[dict]) -> str:
        """与 QwenLLM.chat 同构的入口：messages -> str（这里是 JSON 字符串）。"""
        self.call_count += 1
        task = json.loads(messages[-1]["content"])
        verdict = self._judge_tool_params(task["context"], task["tool_calls"])
        # 模拟一次 LLM 往返 120~350ms；真实系统里这就是 API 成本与延迟
        self.total_latency_ms += round(self._rng.uniform(120.0, 350.0), 2)
        return json.dumps(verdict, ensure_ascii=False)

    def __call__(self, task: dict) -> dict:
        """便捷入口：直接传任务 dict，内部走标准 chat 协议。"""
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(task, ensure_ascii=False)},
        ]
        return json.loads(self.chat(messages))

    # ---- 内部：确定性参数审查逻辑 ----
    @staticmethod
    def _judge_tool_params(context: dict, tool_calls: List[dict]) -> dict:
        problems: List[str] = []
        order_id, order_amount = context["order_id"], context["order_amount"]
        for call in tool_calls:
            params = call.get("params", {})
            # 规则 1：任何工具都必须作用于正确的订单（串单是资损级事故）
            if "order_id" in params and params["order_id"] != order_id:
                problems.append(f"{call['name']} 的 order_id={params['order_id']!r} "
                                f"与上下文 {order_id!r} 不一致")
            # 规则 2：退款金额必须在 [0, 订单金额] 内（超额退款 = 资损）
            if call["name"] == "refund":
                amount = params.get("amount")
                if not isinstance(amount, (int, float)) or isinstance(amount, bool):
                    problems.append(f"refund.amount 类型非法: {amount!r}")
                elif not (0 <= amount <= order_amount):
                    problems.append(f"refund.amount={amount} 超出合法范围 "
                                    f"[0, {order_amount}]（超额退款）")
        return {
            "valid": not problems,
            "problems": problems,
            # 语义判定不敢给满置信：这正是"低置信升级人工复核"的数据来源
            "confidence": 0.95 if not problems else 0.9,
        }


class ToolCallAssertionScorer(Scorer):
    """工具调用断言：关键工具是否被调用（结构性，便宜）+ 参数是否正确
    （语义性，委托 MockJudge 的一次"LLM 调用"）。

    这就是"假阳性"防线：只看最终回复文本完全发现不了"没查订单就退款"
    "退错了订单"——回复可以写得非常漂亮，路径却是错的。"""
    name, tier, cost_units = "tool_call_assertion", "fine", 30

    def __init__(self, judge: MockJudge):
        self.judge = judge

    def score(self, sample: Sample) -> ScoreResult:
        called = {c["name"] for c in sample.tool_calls}
        required = sample.context.get("required_tools", [])
        # 第一步：结构性检查——关键工具缺席直接失败，不必浪费 Judge 调用
        missing = [t for t in required if t not in called]
        if missing:
            return self.fail(self.name, ISSUE_TOOL_NOT_CALLED,
                             f"关键工具 {missing} 未被调用"
                             f"（实际调用: {sorted(called) or '空'}）")
        # 第二步：语义级参数审查，委托 Judge（一次昂贵的"LLM 往返"）
        verdict = self.judge({"type": "tool_param_check",
                              "context": sample.context,
                              "tool_calls": sample.tool_calls})
        if not verdict["valid"]:
            return self.fail(self.name, ISSUE_TOOL_PARAM_ERROR,
                             "；".join(verdict["problems"]),
                             confidence=verdict["confidence"])
        return self.ok(self.name, f"关键工具 {required} 均已调用且参数审查通过",
                       confidence=verdict["confidence"])


class ExecutionBudgetScorer(Scorer):
    """执行指标：调用次数上限 + 总耗时预算。
    为什么要单独设这类检查：这类问题不是"做错了"，而是"做得太贵/太慢"——
    结果可能完全正确，但循环重试、无效调用会拖垮线上成本与延迟。
    它要聚合整条 trace，故归入精判层（成本相对粗筛更高）。"""
    name, tier, cost_units = "execution_budget", "fine", 12
    MAX_TOOL_CALLS = 6
    TIME_BUDGET_MS = 8000

    def score(self, sample: Sample) -> ScoreResult:
        n = len(sample.tool_calls)
        if n > self.MAX_TOOL_CALLS:
            return self.fail(self.name, ISSUE_TOO_MANY_CALLS,
                             f"工具调用 {n} 次 > 上限 {self.MAX_TOOL_CALLS}"
                             f"（疑似循环重试/无效调用）")
        total_ms = sum(c["duration_ms"] for c in sample.tool_calls)
        if total_ms > self.TIME_BUDGET_MS:
            return self.fail(self.name, ISSUE_TIME_BUDGET_EXCEEDED,
                             f"工具总耗时 {total_ms}ms > 预算 {self.TIME_BUDGET_MS}ms")
        return self.ok(self.name, f"调用 {n} 次 ≤ {self.MAX_TOOL_CALLS}，"
                                  f"总耗时 ≤ {self.TIME_BUDGET_MS}ms")


# 单样本跑全套评分器的成本（baseline 口径）：粗筛 1+2+1=4，精判 30+12=42。
# 精判比粗筛贵一个数量级——这正是"明确失败必须拦在粗筛"的成本动机。
PER_SAMPLE_FULL_COST = (LengthAnomalyScorer.cost_units + JsonSchemaScorer.cost_units
                        + KeywordListScorer.cost_units
                        + ToolCallAssertionScorer.cost_units
                        + ExecutionBudgetScorer.cost_units)


# --- 5. 两层流水线：粗筛拦截明确失败，精判确认边界样本 ---

@dataclass
class Verdict:
    """单条样本的最终判定 + 完整路由记录。"""
    sample_id: str
    passed: bool
    blocked_at: Optional[str]       # "coarse"/"fine"；None 表示最终通过
    issue: str
    evidence: str
    results: List[ScoreResult] = field(default_factory=list)  # 沿途每次评分


@dataclass
class PipelineStats:
    total: int = 0
    coarse_blocked: int = 0         # 在粗筛层被拦截的样本数
    fine_entered: int = 0           # 进入精判层的样本数
    fine_scorer_calls: int = 0      # 精判评分器被执行的次数（精判调用计数）
    coarse_cost: int = 0            # 粗筛层累计成本单元
    fine_cost: int = 0              # 精判层累计成本单元
    issue_dist: Dict[str, int] = field(default_factory=dict)  # 问题分类分布


class TieredPipeline:
    """粗筛 → 精判两层流水线。核心纪律：
    1) 任一层出现 fail 立即短路返回，失败样本不再消耗后续评分器；
    2) 粗筛明确失败的样本绝不进精判（昂贵判定不被垃圾样本稀释）；
    3) 凡评分必留痕（results 序列），每条判定可回放、可申诉。
    """
    def __init__(self, coarse: List[Scorer], fine: List[Scorer]):
        self.coarse, self.fine = coarse, fine
        self.stats = PipelineStats()

    def evaluate(self, sample: Sample) -> Verdict:
        self.stats.total += 1
        results: List[ScoreResult] = []

        # ---- 粗筛层：便宜规则快速分流 ----
        for scorer in self.coarse:
            self.stats.coarse_cost += scorer.cost_units
            r = scorer.score(sample)
            results.append(r)
            if not r.passed:
                self.stats.coarse_blocked += 1
                self._count_issue(r.issue)
                return Verdict(sample.id, False, "coarse", r.issue, r.evidence, results)

        # ---- 精判层：昂贵规则 + Judge 确认边界样本 ----
        self.stats.fine_entered += 1
        for scorer in self.fine:
            self.stats.fine_scorer_calls += 1
            self.stats.fine_cost += scorer.cost_units
            r = scorer.score(sample)
            results.append(r)
            if not r.passed:
                self._count_issue(r.issue)
                return Verdict(sample.id, False, "fine", r.issue, r.evidence, results)

        self._count_issue(ISSUE_NONE)
        return Verdict(sample.id, True, None, ISSUE_NONE,
                       f"全部 {len(results)} 项检查通过", results)

    def _count_issue(self, issue: str) -> None:
        self.stats.issue_dist[issue] = self.stats.issue_dist.get(issue, 0) + 1

    def savings(self) -> float:
        """成本节省比例 = 1 - 实际成本 / baseline（不分层不短路全量跑）。
        baseline 不需要真的运行——分层与否改变的是开销，不是结论。"""
        actual = self.stats.coarse_cost + self.stats.fine_cost
        return 1.0 - actual / (self.stats.total * PER_SAMPLE_FULL_COST)


def build_pipeline(judge: MockJudge) -> TieredPipeline:
    """组装流水线：层内顺序 = 便宜且命中率高的在前。"""
    return TieredPipeline(
        coarse=[LengthAnomalyScorer(), JsonSchemaScorer(), KeywordListScorer()],
        fine=[ToolCallAssertionScorer(judge), ExecutionBudgetScorer()],
    )


# --- 6. 样本集：明显失败 / 边界样本 / 通过样本 ---
# 设计要点：每条样本自带"出题人答案"（expect_blocked / expect_issue），
# 自检时逐条核对流水线判定——评测系统本身也要被评测。

def _good_output(answer: str, action: str, order_id: str, amount: float) -> str:
    return json.dumps({"answer": answer, "action": action,
                       "order_id": order_id, "amount": amount}, ensure_ascii=False)


def _call(name: str, oid: str, ms: int, amount: Optional[float] = None) -> dict:
    """构造一条工具调用 trace 记录（含耗时）。"""
    params = {"order_id": oid}
    if amount is not None:
        params["amount"] = amount
    return {"name": name, "params": params, "duration_ms": ms}


def build_dataset() -> List[Sample]:
    def ctx(oid: str, amt: float) -> dict:
        return {"order_id": oid, "order_amount": amt, "required_tools": ["query_order"]}

    samples: List[Sample] = []

    # ==== A. 明显失败：应当在粗筛层被拦截，且分类正确 ====
    samples.append(Sample(
        "bad-broken-json",                       # 被截断的 JSON
        '{"answer": "您的退款申请已通过，金额将原路退回',
        [_call("query_order", "ORD-1", 200)],
        ctx("ORD-1", 100.0), "coarse", ISSUE_INVALID_JSON))
    samples.append(Sample(
        "bad-empty", "   ", [], ctx("ORD-2", 50.0), "coarse", ISSUE_EMPTY_OUTPUT))
    samples.append(Sample(
        "bad-too-short", '{"ok":1}', [], ctx("ORD-3", 50.0), "coarse", ISSUE_TOO_SHORT))
    samples.append(Sample(
        "bad-too-long",
        _good_output("处理结果如下：" + "重复内容" * 120, "refund_approved", "ORD-4", 10.0),
        [], ctx("ORD-4", 10.0), "coarse", ISSUE_TOO_LONG))
    samples.append(Sample(
        "bad-missing-field",                     # 缺 amount
        json.dumps({"answer": "退款将在1-3个工作日内退回", "action": "refund_approved",
                    "order_id": "ORD-5"}, ensure_ascii=False),
        [], ctx("ORD-5", 60.0), "coarse", ISSUE_MISSING_FIELD))
    samples.append(Sample(
        "bad-type-error",                        # amount 类型错误
        json.dumps({"answer": "退款将在1-3个工作日内退回", "action": "refund_approved",
                    "order_id": "ORD-6", "amount": "很多"}, ensure_ascii=False),
        [], ctx("ORD-6", 60.0), "coarse", ISSUE_TYPE_ERROR))
    samples.append(Sample(
        "bad-blacklist",
        _good_output("已为您走内部员工通道加急办理退款，1-3个工作日内到账。",
                     "refund_approved", "ORD-7", 88.0),
        [_call("query_order", "ORD-7", 200)],
        ctx("ORD-7", 88.0), "coarse", ISSUE_BLACKLIST_HIT))
    samples.append(Sample(
        "bad-whitelist-missing",                 # 提了退款却不给到账时效
        _good_output("您的退款已处理，金额将原路退回。", "refund_approved", "ORD-8", 39.0),
        [_call("query_order", "ORD-8", 200)],
        ctx("ORD-8", 39.0), "coarse", ISSUE_WHITELIST_MISSING))

    # ==== B. 边界样本：粗筛拦不住（输出体面），要靠精判层抓住 ====
    samples.append(Sample(
        "edge-no-tool",                          # 回复漂亮但从没查过订单——典型假阳性
        _good_output("您的退款申请已通过，款项将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-9", 129.0),
        [],                                      # trace 为空！
        ctx("ORD-9", 129.0), "fine", ISSUE_TOOL_NOT_CALLED))
    samples.append(Sample(
        "edge-wrong-order",                      # 查了订单，但查的是别人的订单（串单）
        _good_output("您的退款申请已通过，款项将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-10", 199.0),
        [_call("query_order", "ORD-9999", 210), _call("refund", "ORD-10", 300, 199.0)],
        ctx("ORD-10", 199.0), "fine", ISSUE_TOOL_PARAM_ERROR))
    samples.append(Sample(
        "edge-over-refund",                      # 超额退款：退得比订单金额还多（资损）
        _good_output("退款已为您加急办理，将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-11", 150.0),
        [_call("query_order", "ORD-11", 180), _call("refund", "ORD-11", 320, 300.0)],
        ctx("ORD-11", 150.0), "fine", ISSUE_TOOL_PARAM_ERROR))
    samples.append(Sample(
        "edge-many-calls",                       # 参数都对，但反复无效调用（循环重试）
        _good_output("退款已处理完毕，款项将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-12", 79.0),
        ([_call("query_order", "ORD-12", 100) for _ in range(8)]
         + [_call("refund", "ORD-12", 150, 79.0)]),
        ctx("ORD-12", 79.0), "fine", ISSUE_TOO_MANY_CALLS))
    samples.append(Sample(
        "edge-slow",                             # 每一步都对，但整体慢得不可接受
        _good_output("退款已处理，款项将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-13", 259.0),
        [_call("query_order", "ORD-13", 6000), _call("refund", "ORD-13", 5500, 259.0)],
        ctx("ORD-13", 259.0), "fine", ISSUE_TIME_BUDGET_EXCEEDED))

    # ==== C. 通过样本：手写 3 条覆盖不同正确路径 ====
    samples.append(Sample(
        "good-standard",                         # 标准全额退款
        _good_output("已为您办理退款，款项将在1-3个工作日内原路退回。",
                     "refund_approved", "ORD-14", 199.0),
        [_call("query_order", "ORD-14", 220), _call("refund", "ORD-14", 310, 199.0)],
        ctx("ORD-14", 199.0), None, ISSUE_NONE))
    samples.append(Sample(
        "good-reject",                           # 查询后发现不符合条件：正确拒绝也是通过
        _good_output("订单已发货，暂不满足无条件退回条件，建议先申请退货，"
                     "仓库签收后将为您处理。", "refund_reject", "ORD-15", 89.0),
        [_call("query_order", "ORD-15", 190)],
        ctx("ORD-15", 89.0), None, ISSUE_NONE))
    samples.append(Sample(
        "good-followup",                         # 信息不足先追问（未提退款，不触发白名单）
        _good_output("请提供退回原因与商品照片，我们核实后将尽快为您处理。",
                     "ask_user", "ORD-16", 0.0),
        [_call("query_order", "ORD-16", 205)],
        ctx("ORD-16", 45.0), None, ISSUE_NONE))

    # ==== D. 通过样本：固定种子批量扩展，模拟 golden set 的规模化生产 ====
    # 关键点：扩展样本同样受确定性约束——随机源只负责取值，结构由代码保证，
    # 因此任何机器上生成的样本集完全一致（这正是"可复现评测集"的要求）。
    rng = random.Random(42)
    for i in range(3):
        oid = f"ORD-2024-{1000 + rng.randint(0, 8999)}"
        amount = round(rng.uniform(20.0, 800.0), 2)
        samples.append(Sample(
            f"good-gen-{i + 1}",
            _good_output("退款成功，款项将在1-3个工作日内原路退回。",
                         "refund_approved", oid, amount),
            [_call("query_order", oid, rng.randint(150, 900)),
             _call("refund", oid, rng.randint(150, 900), amount)],
            ctx(oid, amount), None, ISSUE_NONE))
    return samples


# --- 7. 报告渲染辅助 ---

def _display_width(s: str) -> int:
    """中文按 2 列宽对齐（与主仓库 lab05 同样的小技巧）。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _display_width(s))


def render_report(dataset: List[Sample], verdicts: List[Verdict],
                  stats: PipelineStats, judge: MockJudge) -> str:
    lines = ["=" * 78, "分层筛查评测报告（粗筛规则 -> 精判规则 + Judge）", "=" * 78,
             _pad("样本", 22) + _pad("路由结果", 17) + _pad("问题分类", 16) + "判定依据",
             "-" * 78]
    by_id = {v.sample_id: v for v in verdicts}
    for sample in dataset:
        v = by_id[sample.id]
        route = "通过" if v.passed else f"{v.blocked_at}层拦截"
        lines.append(_pad(sample.id, 22) + _pad(route, 17)
                     + _pad(ISSUE_CN[v.issue], 16) + v.evidence[:34])
    actual = stats.coarse_cost + stats.fine_cost
    baseline = stats.total * PER_SAMPLE_FULL_COST
    lines += [
        "-" * 78,
        f"样本总数 {stats.total}：粗筛拦截 {stats.coarse_blocked}，"
        f"进入精判 {stats.fine_entered}（精判评分器执行 {stats.fine_scorer_calls} 次），"
        f"最终通过 {stats.issue_dist.get(ISSUE_NONE, 0)}",
        f"Judge(LLM) 调用 {judge.call_count} 次，"
        f"累计模拟延迟 {round(judge.total_latency_ms, 2)} ms",
        f"成本：实际 {actual} 单元 vs 全量精判 baseline {baseline} 单元"
        f" → 节省 {(1 - actual / baseline):.1%}",
        "问题分类分布: " + "  ".join(
            f"{ISSUE_CN[k]}x{v}" for k, v in sorted(stats.issue_dist.items())),
        "=" * 78,
    ]
    return "\n".join(lines)


# --- 8. 自检：断言核心结论，而不是"跑完了" ---

def run_pipeline(dataset: List[Sample], seed: int = 23
                 ) -> Tuple[List[Verdict], PipelineStats, MockJudge]:
    """一次完整评测运行。每次新建 judge/评分器，保证可重复实验。"""
    judge = MockJudge(seed=seed)
    pipeline = build_pipeline(judge)
    verdicts = [pipeline.evaluate(s) for s in dataset]
    return verdicts, pipeline.stats, judge


def run_self_checks(dataset: List[Sample], verdicts: List[Verdict],
                    stats: PipelineStats, judge: MockJudge) -> None:
    by_id = {v.sample_id: v for v in verdicts}

    # (a) 评分输出规范：沿途每个 ScoreResult 都必须是合规的五元组
    all_results = [r for v in verdicts for r in v.results]
    assert all_results, "流水线应产生评分记录"
    for r in all_results:
        assert 0.0 <= r.score <= 1.0, f"{r.scorer}: score 越界"
        assert 0.0 <= r.confidence <= 1.0, f"{r.scorer}: confidence 越界"
        assert r.issue in ALL_ISSUES, f"{r.scorer}: 未知问题分类 {r.issue}"
        assert r.evidence, f"{r.scorer}: 判定依据不能为空"
        assert r.passed == (r.issue == ISSUE_NONE), f"{r.scorer}: pass 与分类矛盾"

    # (b) 逐样本核对"出题人答案"：坏样本在粗筛被拦且分类正确；边界样本在精判
    #     被拦且分类正确；好样本最终通过。这是分层路由正确性的核心断言。
    for s in dataset:
        v = by_id[s.id]
        if s.expect_blocked is not None:
            assert v.blocked_at == s.expect_blocked, \
                f"{s.id}: 应在 {s.expect_blocked} 层被拦截，实际 {v.blocked_at}"
            assert v.issue == s.expect_issue, \
                f"{s.id}: 问题分类应为 {s.expect_issue}，实际 {v.issue}"
        else:
            assert v.passed and v.blocked_at is None and v.issue == ISSUE_NONE, \
                f"{s.id}: 应当最终通过"

    # (c) 分层路由的数量关系：粗筛拦截 + 进入精判 == 总样本数，无一漏路由
    expect_coarse = sum(1 for s in dataset if s.expect_blocked == "coarse")
    assert stats.coarse_blocked + stats.fine_entered == stats.total == len(dataset)
    assert stats.coarse_blocked == expect_coarse
    assert stats.fine_entered == len(dataset) - expect_coarse, "进入精判层的样本数不符"

    # (d) 成本节省必须有牙齿：分层策略至少省下 35% 的评分开销
    actual = stats.coarse_cost + stats.fine_cost
    baseline = stats.total * PER_SAMPLE_FULL_COST
    assert actual < baseline, "分层后成本必须低于全量精判"
    assert 1.0 - actual / baseline >= 0.35, "成本节省不足 35%，分层路由未生效"

    # (e) 精判调用计数精确可预测：
    #     - Judge(LLM) 只在"工具都到场、需要参数语义审查"时才被触发，
    #       验证"结构检查先行，替昂贵调用省门"的设计；
    #     - 精判评分器执行次数 == 进入精判的样本中"首项即失败"者 x1 + 其余 x2。
    expect_judge_calls = sum(
        1 for s in dataset if s.expect_blocked != "coarse"
        and {c["name"] for c in s.tool_calls} >= {"query_order"})
    assert judge.call_count == expect_judge_calls, \
        f"Judge 调用 {judge.call_count} 次，期望 {expect_judge_calls} 次"
    assert judge.call_count < stats.fine_entered, \
        "Judge 调用次数应少于进入精判层的样本数（结构性失败不花 LLM 钱）"
    first_fine_issues = {ISSUE_TOOL_NOT_CALLED, ISSUE_TOOL_PARAM_ERROR}
    expect_fine_calls = sum(1 if s.expect_issue in first_fine_issues else 2
                            for s in dataset if s.expect_blocked != "coarse")
    assert stats.fine_scorer_calls == expect_fine_calls, \
        f"精判评分器执行 {stats.fine_scorer_calls} 次，期望 {expect_fine_calls} 次"

    # (f) 问题分类分布与逐条判定自洽：分布计数之和 == 样本总数
    fail_count = sum(1 for v in verdicts if not v.passed)
    assert sum(stats.issue_dist.values()) == stats.total
    assert stats.total - stats.issue_dist.get(ISSUE_NONE, 0) == fail_count

    # (g) 确定性：同一数据集重跑一遍，逐样本判定完全一致（评测系统可复现）
    verdicts2, stats2, judge2 = run_pipeline(dataset)
    for v1, v2 in zip(verdicts, verdicts2):
        assert (v1.sample_id, v1.passed, v1.blocked_at, v1.issue) == \
               (v2.sample_id, v2.passed, v2.blocked_at, v2.issue), \
               f"{v1.sample_id}: 两次运行判定不一致"
    assert judge2.call_count == judge.call_count, "Judge 调用次数不可复现"
    assert stats2.coarse_cost + stats2.fine_cost == actual, "成本不可复现"


# --- 9. 演示入口 ---

# 名册展示用：每个评分器代表性的问题分类
_SCORER_SPOTLIGHT = {
    "length_anomaly": ISSUE_EMPTY_OUTPUT, "json_schema": ISSUE_INVALID_JSON,
    "keyword_list": ISSUE_BLACKLIST_HIT, "tool_call_assertion": ISSUE_TOOL_NOT_CALLED,
    "execution_budget": ISSUE_TOO_MANY_CALLS,
}


def main() -> None:
    print("=" * 78)
    print("EVAL LAB 03 · 程序化评分与分层筛查（纯标准库 / 确定性 / 零依赖）")
    print("=" * 78)

    # [1/4] 构建样本集
    dataset = build_dataset()
    n_bad = sum(1 for s in dataset if s.expect_blocked == "coarse")
    n_edge = sum(1 for s in dataset if s.expect_blocked == "fine")
    print(f"\n[1/4] 样本集：共 {len(dataset)} 条（明显失败 x {n_bad} / "
          f"边界样本 x {n_edge} / 通过样本 x {len(dataset) - n_bad - n_edge}）")

    # [2/4] 评分器名册：层、成本、职责一目了然
    judge_demo = MockJudge(seed=23)
    demo_pipeline = build_pipeline(judge_demo)
    roster = demo_pipeline.coarse + demo_pipeline.fine
    print("\n[2/4] 评分器名册（层 / 成本单元 / 代表性问题分类）：")
    for s in roster:
        print(f"   - [{'粗筛' if s.tier == 'coarse' else '精判'}] {_pad(s.name, 24)} "
              f"cost={s.cost_units:<3} 抓 {ISSUE_CN[_SCORER_SPOTLIGHT[s.name]]}")

    # [3/4] 运行两层流水线
    print("\n[3/4] 运行两层流水线（粗筛拦截明确失败 -> 精判确认边界样本）：")
    verdicts, stats, judge = run_pipeline(dataset)
    print(render_report(dataset, verdicts, stats, judge))

    # [4/4] 自检
    print("\n[4/4] 自检：断言核心结论（分层路由 / 问题分类 / 成本节省 / 可复现）...")
    run_self_checks(dataset, verdicts, stats, judge)
    print(f"   粗筛拦截 {stats.coarse_blocked}/{stats.total} 条，"
          f"全部在粗筛层给出正确问题分类 ✔")
    print(f"   Judge 仅调用 {judge.call_count} 次（少于进入精判层的 "
          f"{stats.fine_entered} 条），昂贵判定不被垃圾样本稀释 ✔")
    print(f"   成本节省 {1 - (stats.coarse_cost + stats.fine_cost) / (stats.total * PER_SAMPLE_FULL_COST):.1%} "
          f"≥ 35%，两次运行判定完全一致 ✔")
    print("\n✅ 自检通过：eval_lab03_programmatic_scorers.py 全部断言成立")


if __name__ == "__main__":
    main()
