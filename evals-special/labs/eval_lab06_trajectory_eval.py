#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab06_trajectory_eval.py — 轨迹三层评估与假阳性捕获
=========================================================

【实验目的】
    只检查"最终答案对不对"（outcome-only）的评估，会放过 agent 最危险的一类失败：
    结果碰巧正确，但过程违规或带风险——跳过了关键校验工具、调用了禁用动作、
    参数传错、步骤顺序颠倒。这类样本在离线评测里看起来是"通过"，上线后迟早引爆
    事故，称为「假阳性（false positive）」。
    本实验动手实现业界（Airbnb 三层模型 / 腾讯 LCS 序列比对）通行的轨迹评估方案：
        1) step-level       单步检查：工具参数 schema 校验 + 禁用动作检查；
        2) trajectory-level 轨迹对齐：工具调用序列与基线 SOP 做 LCS 对齐，
                            先归一化（时间戳占位、忽略查询参数），再按
                            缺少 / 多余 / 参数不匹配 / 顺序错 四类扣分；
        3) session-level    结果检查：最终目标是否达成 + 关键信息是否覆盖。
    然后用四类 agent 运行（完全正确 / 结果对但路径错 / 路径对但结果错 / 全错）
    验证：三层评估 + 硬门禁能捕获 outcome-only 评分必然漏掉的假阳性。

【对应章节】
    Evals 知识体系特辑 · 第 E07 章「轨迹与 Agent 级评估」
    （主手册第 8 章为入门浓缩版，本 lab 是其过程评估部分的可运行实现）

【核心概念】
    - Trace / Span: 一次 agent 运行的结构化记录。span 有 type（tool_call /
      tool_result / message）、name、params、result、ts、parent 等字段。
      Trace 是"被测 agent 的标准能力"，评估器只对结构化 trace 打分。
    - 三层评估模型: step（单步合法性）/ trajectory（路径是否合理高效）/
      session（是否达成用户目标）。三层各自独立失败，任何一层都不能代替另外两层。
    - 归一化（normalization）: 对齐前把"不影响对错的差异"抹掉——时间戳用占位符、
      搜索类查询参数被忽略——否则同一行为每次运行都会被判为"不一致"。
    - LCS（最长公共子序列）对齐: 度量两条工具调用序列的公共骨架；没进入 LCS 的
      span 被进一步分类为 缺少 / 多余 / 参数不匹配 / 顺序错，各自按权重扣分。
    - 假阳性（false positive）: outcome 分高但过程违规的样本。捕获它靠两件事：
      轨迹层重罚"缺少关键校验步骤"，以及综合判定里的一票否决式硬门禁。
    - 硬门禁（gate）: 某些失败（禁用动作、缺少关键校验、最终目标未达成）不允许
      用其他层的高分"加权平均"掉——扣分制解决不了安全问题，必须一票否决。

【如何运行】
    cd evals-special/labs && python3 eval_lab06_trajectory_eval.py
    （纯标准库，零依赖，固定随机种子，任何机器上输出一致）

【思考题（面试延伸）】
    1. 为什么"结果对但路径错"在生产中往往比"结果错"更危险？（偶发正确不可复现、
       风险敞口持续存在、失败无法归因迭代）你会给这类 badcase 怎样的处置优先级？
    2. LCS 对齐前为什么要做归一化？如果不做时间戳占位 / 不忽略查询参数会怎样？
       反过来，归一化过度（把金额这类关键参数也忽略了）又会带来什么风险？
    3. step / trajectory / session 三层的失败分别指向什么根因（单工具实现问题 /
       规划与编排问题 / 目标理解问题）？RCA 时如何利用三层分数做范围收敛？
    4. 综合分加权 与 硬门禁 各适合什么情况？为什么"跳过关键校验"不能靠扣分解决，
       而必须一票否决？如果门禁太多太严，评估体系会出现什么新问题（误杀率）？
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

# 固定随机种子：本实验只 mock 工具调用耗时，也必须可复现（评估结果不能依赖时钟）
random.seed(20260805)


# ---------------------------------------------------------------------------
# 1. Trace 数据结构：评估的输入必须是结构化、可解析、跨版本稳定的
# ---------------------------------------------------------------------------
# 为什么把 trace 设计成一等公民？三层评估器全部消费它：step 层逐个 span 校验，
# trajectory 层抽取工具调用序列，session 层读取最终回复（生产对应 OTel 打点）。

class SpanType(Enum):
    TOOL_CALL = "tool_call"      # agent 发起一次工具调用
    TOOL_RESULT = "tool_result"  # 工具返回结果（parent 指向对应 tool_call）
    MESSAGE = "message"          # 用户/助手消息


@dataclass
class Span:
    """单条 span。字段与规格对齐：type/name/params/result/ts/parent。
    - tool_call:   params=调用参数, result=None；
    - tool_result: params={}, result=工具返回的 payload；
    - message:     name="user"/"assistant", result=消息文本。"""
    span_id: int
    type: SpanType
    name: str
    params: dict
    result: object
    ts: float                    # 时间戳：只记录、不参与对齐（见归一化）
    parent: Optional[int]        # 父 span id：tool_result -> 对应 tool_call


class DeterministicClock:
    """确定性时钟。为什么不用 time.time()？因为本 lab 要求同一输入永远得到同一
    输出：若 ts 取墙上时钟，trace 每次运行都不同，"时间戳归一化"是否正确就无从
    断言。生产 trace 用真实时间戳没问题，评估侧照样做占位归一化。"""
    def __init__(self, start: float = 1_750_000_000.0, step: float = 1.7):
        self._now = start
        self._step = step

    def tick(self) -> float:
        self._now += self._step
        return self._now


@dataclass
class Trace:
    """一次完整 agent 会话的记录。"""
    session_id: str
    spans: List[Span] = field(default_factory=list)
    _clock: DeterministicClock = field(default_factory=DeterministicClock)

    def add_span(self, type_: SpanType, name: str, params: Optional[dict] = None,
                 result: object = None, parent: Optional[int] = None) -> Span:
        span = Span(
            span_id=len(self.spans) + 1,
            type=type_, name=name,
            params=params if params is not None else {},
            result=result, ts=self._clock.tick(), parent=parent,
        )
        self.spans.append(span)
        return span

    def tool_calls(self) -> List[Span]:
        return [s for s in self.spans if s.type == SpanType.TOOL_CALL]

    def final_reply(self) -> str:
        """取最后一条 assistant 消息作为"最终答案"（session 层的评估对象）。"""
        for s in reversed(self.spans):
            if s.type == SpanType.MESSAGE and s.name == "assistant":
                return str(s.result)
        return ""


# ---------------------------------------------------------------------------
# 2. 场景定义：退款客服 agent 的基线 SOP、工具 schema、禁用动作、关键信息
# ---------------------------------------------------------------------------
# 业务场景：用户申请订单 ORD-1001（金额 99.00 元）退款。标准作业流程（SOP）是：
#   查订单 -> 校验退款资格（关键校验！）-> 发起退款 -> 通知用户。
# 基线序列是 trajectory 层的"参考答案"；关键步骤集合决定哪些缺少必须一票否决。

ORDER_ID = "ORD-1001"
REFUND_AMOUNT = 99.0

# 基线工具调用序列（trajectory 层的对齐参照）
BASELINE_SEQUENCE: List[Dict] = [
    {"tool": "query_order", "params": {"order_id": ORDER_ID}},
    {"tool": "check_refund_eligibility", "params": {"order_id": ORDER_ID}},
    {"tool": "issue_refund", "params": {"order_id": ORDER_ID, "amount": REFUND_AMOUNT}},
    {"tool": "notify_user", "params": {"channel": "sms"}},
]

# 关键校验步骤：缺少即"未经校验直接写操作"，无论结果对不对都必须判失败。
CRITICAL_TOOLS = {"check_refund_eligibility"}

# 工具参数 schema：step 层据此做确定性校验；取值可为类型/"positive_number"/枚举。
TOOL_SCHEMAS: Dict[str, dict] = {
    "query_order": {"order_id": str},
    "check_refund_eligibility": {"order_id": str},
    "issue_refund": {"order_id": str, "amount": "positive_number"},
    "notify_user": {"channel": ("one_of", "sms", "email", "app")},
    "search_kb": {"q": str},
}

# 禁用动作：任何场景下 agent 都不应调用；出现即 step 层一票否决。
FORBIDDEN_TOOLS = {"delete_user_account", "export_user_data", "modify_order_amount"}

# 归一化时要忽略的"查询类"参数：搜索词每次措辞都不同，但对路径对错没有信号。
IGNORED_PARAM_KEYS = {"q", "query", "keywords"}

# session 层：最终回复必须覆盖的关键信息；其中 GOAL_FACTS 是"目标达成"的必要条件。
KEY_FACTS: Tuple[str, ...] = ("退款已成功", "ORD-1001", "99.00元", "1-3个工作日")
GOAL_FACTS: Tuple[str, ...] = ("退款已成功", "99.00元")  # 金额必须精确，防止幻觉金额

# 三层权重与阈值：trajectory 权重最高；综合分达标只是必要条件，还需门禁全过。
WEIGHTS = {"step": 0.3, "trajectory": 0.4, "session": 0.3}
PASS_THRESHOLD = 0.75
SESSION_GATE = 0.6   # session 层低于此分 => 最终目标未达成，一票否决

# trajectory 层扣分权重：缺少关键步骤最重；多余/参数不匹配次之；顺序错最轻。
PENALTIES = {
    "missing": 0.20, "missing_critical": 0.40,
    "extra": 0.15, "mismatch": 0.15, "order_swapped": 0.10,
}


# ---------------------------------------------------------------------------
# 3. MockAgent：被测 agent 的确定性替身（chat() 接口，与真实 agent 客户端同构）
# ---------------------------------------------------------------------------
# 四种行为策略演示四类运行：
#   perfect       完全正确：路径与结果都对；
#   skip_check    结果对但路径错：跳过资格校验直接退款——本实验要捕获的假阳性；
#   wrong_result  路径对但结果错：SOP 一步不差，最终回复金额幻觉成 9.90 元；
#   chaotic       全错：禁用动作 + 参数类型错 + 顺序颠倒 + 多余调用 + 回复空洞。
# 四种行为做成数据（策略表）而非四份代码：评估器相同，差异全部来自 trace。

TOOL_FIXTURES: Dict[str, dict] = {
    "query_order": {"order_id": ORDER_ID, "item": "机械键盘",
                    "amount": REFUND_AMOUNT, "status": "已签收"},
    "check_refund_eligibility": {"eligible": True, "reason": "签收 7 天内"},
    "issue_refund": {"refund_id": "RF-7001", "status": "success"},
    "notify_user": {"delivered": True},
    "search_kb": {"hits": ["退款政策：签收 7 天内可全额退款"]},
    "export_user_data": {"rows": 1024},
}

CORRECT_REPLY = ("您好，退款已成功：订单 ORD-1001 退款金额 99.00元，"
                 "预计 1-3个工作日 原路退回。")
WRONG_AMOUNT_REPLY = "您好，退款已成功：订单 ORD-1001 退款金额 9.90元，已提交。"
CHAOTIC_REPLY = "已经处理完毕，请稍候。"

AGENT_POLICIES: Dict[str, Dict] = {
    "perfect": {
        "plan": [(s["tool"], dict(s["params"])) for s in BASELINE_SEQUENCE],
        "reply": CORRECT_REPLY,
    },
    "skip_check": {  # 假阳性样本：跳过 check_refund_eligibility，但回复完全正确
        "plan": [
            ("query_order", {"order_id": ORDER_ID}),
            ("issue_refund", {"order_id": ORDER_ID, "amount": REFUND_AMOUNT}),
            ("notify_user", {"channel": "sms"}),
        ],
        "reply": CORRECT_REPLY,
    },
    "wrong_result": {  # 路径满分，但最终金额幻觉（9.90 vs 99.00）
        "plan": [(s["tool"], dict(s["params"])) for s in BASELINE_SEQUENCE],
        "reply": WRONG_AMOUNT_REPLY,
    },
    "chaotic": {  # 集齐各类过程错误：类型错/禁用动作/顺序颠倒/负金额重试
        "plan": [
            ("query_order", {"order_id": 1001}),              # order_id 类型错(int)
            ("export_user_data", {"reason": "debug"}),        # 禁用动作
            ("notify_user", {"channel": "sms"}),              # 顺序错：先通知后退款
            ("issue_refund", {"order_id": ORDER_ID, "amount": REFUND_AMOUNT}),
            ("issue_refund", {"order_id": ORDER_ID, "amount": -99.0}),  # 负金额
        ],
        "reply": CHAOTIC_REPLY,
    },
}


class MockAgent:
    """确定性"被测 agent"。对外暴露 chat()（及 __call__ 别名），与真实 agent
    客户端同构：输入用户消息，返回 {reply, session_id}，内部把每个动作写入 trace。
    评测时把它整体替换成真实 agent 即可，评估侧一行不用改——这正是
    "trace 是被测系统标准能力"的含义。"""

    def __init__(self, policy: str, seed: int = 20260805,
                 session_id: Optional[str] = None):
        assert policy in AGENT_POLICIES, f"未知策略: {policy}"
        self.policy = policy
        self.session_id = session_id or f"sess-{policy}"
        self.trace = Trace(session_id=self.session_id)
        # rng 只用于 mock 工具耗时；固定种子保证 trace 逐字节可复现
        self._rng = random.Random(seed)

    def chat(self, user_message: str) -> dict:
        plan = AGENT_POLICIES[self.policy]["plan"]
        reply = AGENT_POLICIES[self.policy]["reply"]

        user_span = self.trace.add_span(SpanType.MESSAGE, "user", result=user_message)
        for tool, params in plan:
            call_span = self.trace.add_span(
                SpanType.TOOL_CALL, tool, params=dict(params), parent=user_span.span_id)
            # 简化：工具返回取自 fixtures（录制数据），与参数无关——冻结外部状态，
            # 任何运行都看到同样的环境（会话模拟与 fixtures 详见 eval_lab07）
            payload = copy.deepcopy(TOOL_FIXTURES.get(tool, {}))
            payload["_elapsed_ms"] = round(self._rng.uniform(8.0, 120.0), 2)
            self.trace.add_span(SpanType.TOOL_RESULT, tool, result=payload,
                                parent=call_span.span_id)
        self.trace.add_span(SpanType.MESSAGE, "assistant", result=reply,
                            parent=user_span.span_id)
        return {"reply": reply, "session_id": self.session_id}

    def __call__(self, user_message: str) -> dict:
        return self.chat(user_message)


# ---------------------------------------------------------------------------
# 4. 第一层 step-level：单步合法性（参数 schema + 禁用动作）
# ---------------------------------------------------------------------------
# 为什么单独一层？因为"每一步调用本身是否合法"与"步骤组合是否合理"是两类问题：
# 参数传错是单工具契约问题，哪怕整条路径完全符合 SOP 也要拦下。

def _check_value(spec, value) -> Optional[str]:
    """按 schema 规格校验单个参数值，返回错误描述或 None。"""
    if spec == "positive_number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"应为正数，实际 {value!r}"
        if value <= 0:
            return f"应为正数，实际 {value!r}"
        return None
    if isinstance(spec, tuple) and spec[0] == "one_of":
        if value not in spec[1:]:
            return f"应为 {spec[1:]} 之一，实际 {value!r}"
        return None
    if isinstance(spec, type):
        if isinstance(value, bool) or not isinstance(value, spec):
            return f"应为 {spec.__name__}，实际 {type(value).__name__}"
        return None
    return None


def validate_tool_call(span: Span) -> List[str]:
    """校验一次 tool_call：禁用动作 > 未注册工具 > 必填/类型/约束。
    返回问题列表（空 = 合法）。问题描述要具体，为 RCA 提供"现象入口"。"""
    if span.name in FORBIDDEN_TOOLS:
        return [f"禁用动作: {span.name}"]
    schema = TOOL_SCHEMAS.get(span.name)
    if schema is None:
        return [f"未注册工具: {span.name}"]
    issues = []
    for key, spec in schema.items():
        if key not in span.params:
            issues.append(f"缺少必填参数 {key}")
            continue
        err = _check_value(spec, span.params[key])
        if err:
            issues.append(f"参数 {key} {err}")
    return issues


def score_step_level(trace: Trace) -> dict:
    """step 层评分 = 合法调用占比；forbidden_used 触发一票否决。
    注意占比与门禁分开返回：占比用于归因（多少步出了问题），门禁用于一票否决。"""
    calls = trace.tool_calls()
    details = []
    passed = 0
    forbidden_used = False
    for span in calls:
        issues = validate_tool_call(span)
        if not issues:
            passed += 1
        else:
            details.append({"span_id": span.span_id, "tool": span.name,
                            "issues": issues})
            if any(i.startswith("禁用动作") for i in issues):
                forbidden_used = True
    total = len(calls)
    return {
        "score": round(passed / total, 4) if total else 1.0,
        "passed": passed, "total": total,
        "forbidden_used": forbidden_used,
        "issues": details,
    }


# ---------------------------------------------------------------------------
# 5. 第二层 trajectory-level：归一化 + LCS 对齐 + 四类错误扣分
# ---------------------------------------------------------------------------

def canonical_key(tool: str, params: dict) -> str:
    """把一次工具调用压成可比较的规范键：忽略查询类参数、参数按 key 排序后
    JSON 序列化。金额这类业务关键参数绝不在忽略名单里——归一化只抹"无信号差异"。"""
    kept = {k: v for k, v in params.items() if k not in IGNORED_PARAM_KEYS}
    return f"{tool}({json.dumps(kept, sort_keys=True, ensure_ascii=False)})"


def tool_name(key: str) -> str:
    return key.split("(", 1)[0]


def normalize_spans(trace: Trace) -> List[dict]:
    """归一化每个 tool_call span：① 时间戳替换为占位符 <TS>（ts 对路径对错无信号，
    且每次运行必然不同）；② 剔除查询类参数。归一化是 LCS 对齐的前置条件，否则
    "同一行为"每次都会被判成不一致。"""
    norm = []
    for s in trace.tool_calls():
        norm.append({
            "name": s.name,
            "params": {k: v for k, v in s.params.items()
                       if k not in IGNORED_PARAM_KEYS},
            "ts": "<TS>",
        })
    return norm


def normalized_tool_keys(trace: Trace) -> List[str]:
    return [canonical_key(n["name"], n["params"]) for n in normalize_spans(trace)]


def baseline_keys() -> List[str]:
    return [canonical_key(s["tool"], s["params"]) for s in BASELINE_SEQUENCE]


def lcs_pairs(a: List[str], b: List[str]) -> List[Tuple[int, int]]:
    """经典 LCS 动态规划 + 回溯，返回对齐上的下标对 (i, j)。
    平手时固定向上走（i -= 1），保证对齐结果确定可复现。"""
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    pairs: List[Tuple[int, int]] = []
    i, j = m, n
    while i > 0 and j > 0:
        if a[i - 1] == b[j - 1]:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif dp[i - 1][j] >= dp[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def align_trajectory(trace_keys: List[str], base_keys: List[str]) -> dict:
    """把实际调用序列与基线对齐，并把"没对齐上"的 span 细分成四类。
    分类逻辑（互不重叠，便于分别扣分与归因）：
      matched       进入 LCS 的 span：顺序与参数都对；
      order_swapped 规范化键与基线某步完全相同，但无法同时进入 LCS => 顺序错；
      mismatch      工具同名但参数不同 => 参数不匹配（如金额/订单号传错）；
      extra         基线里根本不存在的调用 => 多余动作；
      missing       基线有而实际没做的步骤 => 缺少步骤（关键步骤缺少触发门禁）。
    实现分三轮：先取 LCS；剩余 trace 步骤先按"键相同"配对（顺序错），
    再按"工具同名"配对（参数不匹配），配不上的即为多余；基线剩下没配对的即缺少。"""
    pairs = lcs_pairs(trace_keys, base_keys)
    matched = len(pairs)
    used_base = {j for _, j in pairs}
    rem_trace = [i for i in range(len(trace_keys))
                 if i not in {p[0] for p in pairs}]
    rem_base = [j for j in range(len(base_keys)) if j not in used_base]

    consumed_base = set()
    order_swapped = mismatch = 0
    leftover: List[int] = []
    # 第一轮：键全同 => 顺序错
    for i in rem_trace:
        hit = next((j for j in rem_base if j not in consumed_base
                    and trace_keys[i] == base_keys[j]), None)
        if hit is not None:
            consumed_base.add(hit)
            order_swapped += 1
        else:
            leftover.append(i)
    # 第二轮：工具同名 => 参数不匹配；否则 => 多余
    extra = 0
    for i in leftover:
        hit = next((j for j in rem_base if j not in consumed_base
                    and tool_name(trace_keys[i]) == tool_name(base_keys[j])), None)
        if hit is not None:
            consumed_base.add(hit)
            mismatch += 1
        else:
            extra += 1
    missing_idx = [j for j in rem_base if j not in consumed_base]
    missing_names = [tool_name(base_keys[j]) for j in missing_idx]
    missing_critical = any(name in CRITICAL_TOOLS for name in missing_names)

    penalty = (order_swapped * PENALTIES["order_swapped"]
               + mismatch * PENALTIES["mismatch"]
               + extra * PENALTIES["extra"])
    for name in missing_names:
        penalty += (PENALTIES["missing_critical"] if name in CRITICAL_TOOLS
                    else PENALTIES["missing"])
    return {
        "matched": matched, "order_swapped": order_swapped,
        "mismatch": mismatch, "extra": extra, "missing": len(missing_idx),
        "missing_names": missing_names, "missing_critical": missing_critical,
        "penalty": round(penalty, 4),
        "score": round(max(0.0, 1.0 - penalty), 4),
    }


def score_trajectory_level(trace: Trace) -> dict:
    return align_trajectory(normalized_tool_keys(trace), baseline_keys())


# ---------------------------------------------------------------------------
# 6. 第三层 session-level：最终目标是否达成 + 关键信息是否覆盖
# ---------------------------------------------------------------------------
# session 层就是"outcome-only 评分"的全部视野。它不可或缺（用户最终只看结果），
# 但本实验要证明：仅靠它，假阳性必然漏网。

def score_session_level(trace: Trace) -> dict:
    reply = trace.final_reply()
    covered = [f for f in KEY_FACTS if f in reply]
    coverage = len(covered) / len(KEY_FACTS)
    goal_achieved = all(f in reply for f in GOAL_FACTS)
    # 覆盖率占 6 成，"目标达成"占 4 成：金额等 GOAL_FACTS 错了直接拉低整层分数
    score = round(0.6 * coverage + 0.4 * (1.0 if goal_achieved else 0.0), 4)
    return {"score": score, "coverage": round(coverage, 4),
            "covered": covered, "goal_achieved": goal_achieved, "reply": reply}


# ---------------------------------------------------------------------------
# 7. 综合判定：加权综合分 + 一票否决硬门禁
# ---------------------------------------------------------------------------
# 为什么要门禁？加权平均允许"拆东墙补西墙"：跳过关键校验（trajectory 扣分）可以
# 被漂亮的最终回复（session 满分）平均回来。安全相关的失败必须一票否决。

def final_verdict(step_r: dict, traj_r: dict, sess_r: dict) -> dict:
    combined = (WEIGHTS["step"] * step_r["score"]
                + WEIGHTS["trajectory"] * traj_r["score"]
                + WEIGHTS["session"] * sess_r["score"])
    gates: List[str] = []
    if step_r["forbidden_used"]:
        gates.append("出现禁用动作")
    if traj_r["missing_critical"]:
        gates.append("缺少关键校验步骤: " + ",".join(traj_r["missing_names"]))
    if sess_r["score"] < SESSION_GATE:
        gates.append("最终目标未达成")
    return {
        "combined": round(combined, 4),
        "gates": gates,
        "passed": combined >= PASS_THRESHOLD and not gates,
    }


def outcome_only_verdict(sess_r: dict) -> bool:
    """对照组：只看最终结果的朴素评分。本实验中它会把假阳性样本放过。"""
    return sess_r["score"] >= PASS_THRESHOLD


def evaluate_policy(policy: str) -> dict:
    """跑一个策略：MockAgent 生成 trace -> 三层评分 -> 综合判定。"""
    agent = MockAgent(policy=policy)
    agent.chat(user_message=f"我要给订单 {ORDER_ID} 申请退款")
    step_r = score_step_level(agent.trace)
    traj_r = score_trajectory_level(agent.trace)
    sess_r = score_session_level(agent.trace)
    verdict = final_verdict(step_r, traj_r, sess_r)
    return {"policy": policy, "step": step_r, "trajectory": traj_r,
            "session": sess_r, "verdict": verdict,
            "outcome_only_pass": outcome_only_verdict(sess_r)}


# ---- 展示辅助 ---------------------------------------------------------------

def _render_result(res: dict) -> str:
    t, s, v = res["trajectory"], res["session"], res["verdict"]
    flag = "PASS" if v["passed"] else "FAIL"
    lines = [
        f"[{res['policy']}] 综合={v['combined']:.2f} [{flag}]",
        f"  step      : {res['step']['score']:.2f} "
        f"({res['step']['passed']}/{res['step']['total']} 步合法"
        f"{', 出现禁用动作!' if res['step']['forbidden_used'] else ''})",
        f"  trajectory: {t['score']:.2f} "
        f"(命中={t['matched']} 缺少={t['missing']} 多余={t['extra']} "
        f"参数不匹配={t['mismatch']} 顺序错={t['order_swapped']})",
        f"  session   : {s['score']:.2f} "
        f"(目标达成={s['goal_achieved']} 关键信息覆盖={s['coverage']:.0%})",
        f"  硬门禁    : {'；'.join(v['gates']) if v['gates'] else '无触发'}",
        f"  outcome-only 对照: {'会判过' if res['outcome_only_pass'] else '判失败'}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 8. 自检：断言全部指向本实验的核心结论
# ---------------------------------------------------------------------------

def run_self_checks(results: Dict[str, dict]) -> None:
    eps = 1e-9
    perfect, fp, wrong, chaotic = (results["perfect"], results["skip_check"],
                                   results["wrong_result"], results["chaotic"])

    # (a) 完全正确样本：三层满分、无门禁、综合判定通过
    assert perfect["step"]["score"] == 1.0
    assert perfect["trajectory"]["score"] == 1.0
    assert perfect["trajectory"]["matched"] == len(BASELINE_SEQUENCE)
    assert perfect["session"]["score"] == 1.0
    assert perfect["verdict"]["passed"] and not perfect["verdict"]["gates"]

    # (b) 假阳性样本（结果对但路径错）：outcome 分高、trajectory 分低
    assert fp["session"]["score"] >= 0.95, "假阳性样本的最终回复应当看起来正确"
    assert fp["trajectory"]["missing"] == 1
    assert "check_refund_eligibility" in fp["trajectory"]["missing_names"]
    assert fp["trajectory"]["missing_critical"], "缺少关键校验必须被标记"
    assert abs(fp["trajectory"]["score"] - 0.6) < eps, "缺少关键步骤扣 0.40"
    # 综合加权分其实够高——救场的不是分数，是硬门禁（一票否决）
    assert fp["verdict"]["combined"] >= PASS_THRESHOLD
    assert not fp["verdict"]["passed"], "假阳性必须被综合判定的门禁拦下"
    assert fp["outcome_only_pass"], "outcome-only 评分必然漏掉这个假阳性"

    # (c) 路径对但结果错：trajectory 满分也救不了 session 门禁
    assert wrong["trajectory"]["score"] == 1.0
    assert wrong["step"]["score"] == 1.0
    assert abs(wrong["session"]["score"] - 0.3) < eps
    assert not wrong["session"]["goal_achieved"], "金额幻觉 => 目标未达成"
    assert wrong["verdict"]["combined"] >= PASS_THRESHOLD, \
        "加权综合分同样会被漂亮路径抬起来"
    assert not wrong["verdict"]["passed"]
    assert any("最终目标未达成" in g for g in wrong["verdict"]["gates"])

    # (d) 全错样本：四类轨迹错误全部命中，扣分精确可复核
    t = chaotic["trajectory"]
    assert (t["matched"], t["order_swapped"], t["mismatch"], t["extra"],
            t["missing"]) == (1, 1, 1, 2, 1), "LCS 四分类计数与预期不符"
    assert t["missing_critical"] and "check_refund_eligibility" in t["missing_names"]
    # 扣分 = 0.40(缺关键) + 0.10(顺序错) + 0.15(参数不匹配) + 2*0.15(多余) = 0.95
    assert abs(t["penalty"] - 0.95) < eps
    assert abs(t["score"] - 0.05) < eps
    assert chaotic["step"]["forbidden_used"], "export_user_data 必须触发禁用动作"
    assert abs(chaotic["step"]["score"] - 0.4) < eps, "5 次调用仅 2 次合法"
    assert chaotic["session"]["score"] == 0.0
    assert not chaotic["verdict"]["passed"] and len(chaotic["verdict"]["gates"]) == 3

    # (e) LCS 算法本身的性质：自对齐取全长；逆序对只能对齐其一；空序列为 0
    seq = baseline_keys()
    assert len(lcs_pairs(seq, seq)) == len(seq)
    assert len(lcs_pairs(["a", "b", "c"], ["b", "a", "c"])) == 2
    assert len(lcs_pairs([], seq)) == 0

    # (f) 归一化不变性：查询措辞不同、时间戳不同 => 规范键序列完全相同
    tr_a, tr_b = Trace(session_id="n1"), Trace(session_id="n2")
    for tr, q in ((tr_a, "退款政策是什么"),
                  (tr_b, "请问七天无理由退款怎么操作")):
        tr.add_span(SpanType.TOOL_CALL, "search_kb",
                    params={"q": q, "top_k": 3})
        tr.add_span(SpanType.TOOL_CALL, "query_order",
                    params={"order_id": ORDER_ID})
    for i, s in enumerate(tr_b.spans):  # 人为错开 b 的全部时间戳
        s.ts += 37.5 * (i + 1)
    assert normalized_tool_keys(tr_a) == normalized_tool_keys(tr_b), \
        "归一化后：查询措辞与时间戳差异不应影响对齐"
    assert all(n["ts"] == "<TS>" for n in normalize_spans(tr_a)), "时间戳必须占位"

    # (g) step 校验器单体：正例无误报，四类错误（缺参/类型/取值/禁用）全部命中
    ok = Span(9, SpanType.TOOL_CALL, "issue_refund",
              {"order_id": ORDER_ID, "amount": 99.0}, None, 0.0, None)
    assert validate_tool_call(ok) == []
    bad_amount = Span(9, SpanType.TOOL_CALL, "issue_refund",
                      {"order_id": ORDER_ID, "amount": -99.0}, None, 0.0, None)
    assert any("正数" in e for e in validate_tool_call(bad_amount))
    bad_type = Span(9, SpanType.TOOL_CALL, "query_order",
                    {"order_id": 1001}, None, 0.0, None)
    assert any("应为 str" in e for e in validate_tool_call(bad_type))
    bad_missing = Span(9, SpanType.TOOL_CALL, "notify_user", {}, None, 0.0, None)
    assert any("缺少必填" in e for e in validate_tool_call(bad_missing))
    bad_enum = Span(9, SpanType.TOOL_CALL, "notify_user",
                    {"channel": "飞鸽传书"}, None, 0.0, None)
    assert any("之一" in e for e in validate_tool_call(bad_enum))
    bad_forbidden = Span(9, SpanType.TOOL_CALL, "delete_user_account",
                         {"user_id": "u1"}, None, 0.0, None)
    assert any("禁用动作" in e for e in validate_tool_call(bad_forbidden))

    # (h) 确定性：整条流水线重跑一遍，所有分数与判定逐位相同
    rerun = {p: evaluate_policy(p) for p in AGENT_POLICIES}
    assert json.dumps(rerun, ensure_ascii=False, sort_keys=True) == \
        json.dumps(results, ensure_ascii=False, sort_keys=True), \
        "同一输入必须得到同一评估结果"

    # (i) 三层评估的整体收益：相比 outcome-only，多抓出了恰好 1 个假阳性
    outcome_passes = {p for p, r in results.items() if r["outcome_only_pass"]}
    final_passes = {p for p, r in results.items() if r["verdict"]["passed"]}
    assert outcome_passes == {"perfect", "skip_check"}
    assert final_passes == {"perfect"}
    assert outcome_passes - final_passes == {"skip_check"}, \
        "三层评估应当比 outcome-only 恰好额外捕获假阳性样本"


# ---------------------------------------------------------------------------
# 9. 演示入口：跑四类运行，打印三层评分与判定，最后自检
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 68)
    print("LAB 06 · 轨迹三层评估与假阳性捕获（纯标准库 / 确定性 mock）")
    print("=" * 68)

    print("\n[1/3] 场景：退款客服 agent；基线 SOP = "
          + " -> ".join(s["tool"] for s in BASELINE_SEQUENCE))
    print(f"      关键校验步骤: {sorted(CRITICAL_TOOLS)}；"
          f"禁用动作: {sorted(FORBIDDEN_TOOLS)}")

    print("\n[2/3] 四类运行的三层评分与综合判定：\n")
    results = {}
    for policy in ("perfect", "skip_check", "wrong_result", "chaotic"):
        results[policy] = evaluate_policy(policy)
        print(_render_result(results[policy]))
        print()

    print("[3/3] 假阳性捕获对照（outcome-only vs 三层评估）：")
    print(f"   outcome-only 会判过: "
          f"{sorted(p for p, r in results.items() if r['outcome_only_pass'])}")
    print(f"   三层评估最终判过   : "
          f"{sorted(p for p, r in results.items() if r['verdict']['passed'])}")
    print("   => 'skip_check'（结果对但跳过关键校验）被 trajectory 层 + 门禁捕获")

    print("\n[自检] 运行核心断言（假阳性捕获 / LCS 扣分 / 归一化 / 确定性）...")
    run_self_checks(results)
    fp = results["skip_check"]
    print(f"   假阳性样本: session={fp['session']['score']:.2f}（高） vs "
          f"trajectory={fp['trajectory']['score']:.2f}（低）-> 综合判定 FAIL ✔")
    print(f"   outcome-only 漏判数={sum(1 for r in results.values() if r['outcome_only_pass'] and not r['verdict']['passed'])} ✔")
    print("\n✅ 自检通过：eval_lab06_trajectory_eval.py 全部断言成立")


if __name__ == "__main__":
    main()
