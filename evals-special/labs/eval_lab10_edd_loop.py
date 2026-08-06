#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab10_edd_loop.py — EDD 全闭环：门禁 / 回归 / 一次一变量
=====================================================================

【实验目的】
    EDD（Eval-Driven Development，评测驱动开发）是 GenAI 功能迭代的工程纪律：
    任何变更（改 prompt / 换模型）都必须先过门禁评测才能上线。本实验用一个
    电商客服 GenAI 功能模拟完整闭环：
        ① golden set（含线上 badcase 回流的坏样本）+ P0 门禁：通过率 ≥ 90%、
           0 个 P0 风险用例失败、对既有回归集零回归；
        ② 候选变更队列：prompt_v1 基线 / prompt_v2 修 A 类"未核实即承诺"错误
           / prompt_v3 修 B 类"答非所问"但改坏旧场景（回归陷阱）/ model_swap；
        ③ 一次一变量：变更队列每个条目只改一个维度，打包变更直接拒绝不评估；
        ④ 回归检测：候选版本必须同时通过新增用例与既有回归集，v3 应被拒绝；
        ⑤ badcase 回流：被拒版本暴露的新失败模式编码为新用例进回归集（只增不减）。

【对应章节】
    Evals 知识体系特辑 · 第 E10 章「EDD 闭环：评测驱动开发的门禁与回归」
    （承接 eval_lab02 用例治理与 eval_lab03 程序化评分；主仓库 lab05 是最小入门。）

【核心概念】
    - 门禁（gate）：通过率阈值 + P0 一票否决。只看通过率会让"整体 95% 但
      资金类用例挂了"的变更蒙混过关，P0 风险用例必须零容忍。
    - 回归检测：用例级 diff（基线通过 → 候选失败）比聚合通过率灵敏得多：
      "修 3 条坏 3 条"时总通过率纹丝不动，回归被完全掩盖。
    - 一次一变量：一次评估只允许一个维度变化，评测差异才可归因。
    - 回归集只增不减：删除"很久没失败的用例"等于悄悄解除防线，旧 bug 复活。
    - badcase 回流：失败模式 → 新用例 → 回归集，线上问题永不二次放过；
      探针集模拟线上抽样，是回流的来源，本身不参与门禁。

【如何运行】
    cd evals-special/labs && python3 eval_lab10_edd_loop.py
    （纯 Python 标准库、零依赖、固定随机种子，任何机器上输出与断言完全一致）

【思考题（面试延伸）】
    1. 门禁为什么要在通过率之外再加"P0 一票否决"？P0 名单该由谁维护、如何防腐化？
    2. v3"修好 B 类却改坏 A 类"：只看总通过率时，什么条件下回归会被完全掩盖？
    3. "这条用例连续 10 个版本全绿、删了省事"错在哪里？（联系 lab02 毕业机制）
    4. 换模型为什么也要走完整门禁？model_swap 的失败模式（保守拒答）为什么人工
       抽查容易漏？业务要求"prompt 和模型一起上"时如何保住可归因性（拆两步/消融）？
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

# --- 0. 全局常量：固定种子与门禁参数 ---
# 固定种子保证随机量可复现；"模型行为"全由确定性行为表驱动——系统行为 = f(变更变量)，评测差异才能归因到变更本身。

SEED = 20260805

MODEL_BASE = "model-base"        # 基线模型
MODEL_STRONG = "model-strong"    # 大参数模型（model_swap 的候选）
GATE_PASS_THRESHOLD = 0.90       # 门禁阈值：通过率 ≥ 90%

# P0 红线词：未经核实订单状态就承诺退款到账时间。来自真实线上事故（已发货订单
# 被直接承诺"24 小时到账"导致钱货两空），事后编码进用例即 badcase 回流。
FORBIDDEN_PROMISE = "24小时内退款到账"

# 大参数模型独有新错误模式：对"时间预测类"问题保守拒答——换模型不是免费午餐。
STRONG_REFUSAL_TOPICS = {"发货时效承诺", "退款到账具体时间"}

# --- 1. 场景设定：系统配置与变更的定义 ---
# EDD 第一性原理：把"要评测的东西"显式建模成 (prompt 版本, 模型) 二元组；
# 配置空间定义清楚了，"一次一变量"才有可操作的含义。

@dataclass(frozen=True)
class SystemConfig:
    """被测系统的一个完整配置：prompt 版本 + 模型。"""
    prompt_version: str
    model: str

    def label(self) -> str:
        return f"{self.prompt_version} + {self.model}"

@dataclass(frozen=True)
class CandidateChange:
    """变更队列条目：从哪个配置来、到哪个配置去、想解决什么问题。
    一次一变量的判定落在 changed_dims：合法变更（非基线）必须恰好改 1 维。"""
    change_id: str
    description: str
    prompt_from: Optional[str]
    prompt_to: str
    model_from: Optional[str]
    model_to: str
    is_baseline: bool = False   # 基线是"初始建立"，没有对照物，不参与纪律校验

    @property
    def changed_dims(self) -> Tuple[str, ...]:
        dims = []
        if self.prompt_from != self.prompt_to:
            dims.append("prompt")
        if self.model_from != self.model_to:
            dims.append("model")
        return tuple(dims)

    def to_config(self) -> SystemConfig:
        return SystemConfig(prompt_version=self.prompt_to, model=self.model_to)

# 三个 prompt 版本。注意 v2 → v3 的 diff：v3 为"精简"删掉了 v2 的两条硬约束——
# 回归陷阱不是玄学，它就写在 prompt 的 diff 里，评审变更时应当逐行看。
PROMPTS: Dict[str, str] = {
    "prompt_v1": "你是电商客服助手。根据用户问题给出回应，优先安抚用户情绪，尽快给出可执行的承诺，提升用户满意度。",
    "prompt_v2": (
        "你是电商客服助手。根据用户问题给出回应，优先安抚用户情绪。\n"
        "【约束一】任何涉及退款/订单的结论，必须先说明已核实的订单状态，"
        "禁止在未核实的情况下承诺退款到账时间。\n"
        "【约束二】用户问题包含多个诉求时，必须逐条回应，不得遗漏。"
    ),
    "prompt_v3": (
        "你是电商客服助手。根据用户问题给出回应。\n"
        "【规则】用户问题中出现『物流/快递/包裹』相关表述时，直接用物流口径回答。\n"
        "（版本说明：为精简提示词，v2 的订单状态核实约束与逐条回应约束在本版被移除）"
    ),
}

# --- 2. 用例：golden set（含坏样本）与探针集 ---
# golden set 是门禁的裁判依据；探针集模拟"线上抽样"，是 badcase 回流的来源、本身
# 不参与门禁——分开才能区分"门禁内失败"与"线上新失败模式"。

@dataclass(frozen=True)
class TestCase:
    """一条评测用例。期望行为用 must_include / must_not_include 操作化，
    交给程序化评分器判定（呼应 eval_lab03：能用规则的绝不靠肉眼）。"""
    case_id: str
    scenario: str          # 退款 / 物流 / 政策 / 混合
    risk: str              # P0（资金风险）/ P1 / P2
    origin: str            # 专家手写 / 线上badcase回流 / 探针采样
    question: str
    order_status: str = "-"
    topic: str = "-"
    must_include: Tuple[str, ...] = ()
    must_not_include: Tuple[str, ...] = ()

def _case(cid, scenario, risk, origin, question, status="-", topic="-",
          must=(), must_not=()):
    return TestCase(cid, scenario, risk, origin, question, status, topic,
                    tuple(must), tuple(must_not))

def build_golden_set() -> List[TestCase]:
    """golden set：20 条 = 退款 6（P0）+ 物流 5（P1）+ 政策 9（P2）。
    gs-r4/r5/r6 是历史线上事故回流入库的坏样本——golden set 必须包含系统
    最易翻车处，否则量出的只是虚假安全感。"""
    cases: List[TestCase] = []
    # ---- 退款场景（全部 P0：涉及资金操作）----
    # 未发货：直接承诺退款是正确行为（v1 也能做对）
    cases.append(_case("gs-r1", "退款", "P0", "专家手写", "下单两小时了不想要了，能退款吗？",
                       "未发货", must=("退款",), must_not=(FORBIDDEN_PROMISE,)))
    cases.append(_case("gs-r2", "退款", "P0", "专家手写", "还没发货，我想取消订单并退款。",
                       "未发货", must=("退款",), must_not=(FORBIDDEN_PROMISE,)))
    cases.append(_case("gs-r3", "退款", "P0", "专家手写", "拍错了规格，趁没发货帮我退款。",
                       "未发货", must=("退款",), must_not=(FORBIDDEN_PROMISE,)))
    # 已发货：必须先核实订单状态——这 3 条来自线上 badcase 回流
    cases.append(_case("gs-r4", "退款", "P0", "线上badcase回流", "商品已经发货了，但我想退款，怎么处理？",
                       "已发货", must=("订单状态",), must_not=(FORBIDDEN_PROMISE,)))
    cases.append(_case("gs-r5", "退款", "P0", "线上badcase回流", "快递在路上了，我不想要了，马上给我退款。",
                       "已发货", must=("订单状态",), must_not=(FORBIDDEN_PROMISE,)))
    cases.append(_case("gs-r6", "退款", "P0", "线上badcase回流", "显示已发货，但我现在想退款，能不能立刻退给我？",
                       "已发货", must=("订单状态",), must_not=(FORBIDDEN_PROMISE,)))
    # ---- 物流场景（P1）：前两条是 B 类错误（答非所问）的高发区 ----
    cases.append(_case("gs-s1", "物流", "P1", "专家手写", "快递好几天没更新了，到底什么情况？", must=("物流",)))
    cases.append(_case("gs-s2", "物流", "P1", "专家手写", "物流一直没更新，卡在中转站三天了。", must=("物流",)))
    cases.append(_case("gs-s3", "物流", "P1", "专家手写", "我的包裹什么时候能到？", must=("物流",)))
    cases.append(_case("gs-s4", "物流", "P1", "专家手写", "能帮我修改收货地址吗？包裹还没到。", must=("物流",)))
    cases.append(_case("gs-s5", "物流", "P1", "专家手写", "我的快递是哪家承运的？", must=("物流",)))
    # ---- 政策咨询（P2）：9 个 FAQ 话题，期望答案来自 FACTS 知识库 ----
    for i, (topic, kw) in enumerate(FACT_KEYWORDS, start=1):
        cases.append(_case(f"gs-p{i}", "政策", "P2", "专家手写", f"请问{topic}是什么？", topic=topic, must=(kw,)))
    return cases

# 政策知识库：话题 -> (标准答案, 关键词)。标准答案必须含关键词，
# "答案含关键词"就是可程序化判定的期望行为。
POLICY_FACTS: Dict[str, Tuple[str, str]] = {
    "会员积分规则": ("会员积分规则：每消费 1 元积 1 分，积分可在积分商城兑换优惠券。", "积分"),
    "发票开具": ("发票开具：支持电子发票，订单完成后可在订单页申请开具。", "发票"),
    "退换货政策": ("退换货政策：签收后 7 天内支持无理由退货，15 天内支持换货。", "换货"),
    "客服工作时间": ("客服工作时间：人工客服服务时间为每日 9:00-21:00。", "工作时间"),
    "优惠券使用规则": ("优惠券使用规则：每张优惠券有使用门槛与有效期，下单时自动匹配可用券。", "优惠券"),
    "支付方式": ("支付方式：支持支付宝、微信支付与银行卡支付。", "支付"),
    "账号注销流程": ("账号注销流程：在设置-账号安全中提交注销申请，审核通过后 7 日内完成注销。", "注销"),
    "发货时效承诺": ("发货时效承诺：现货商品付款后 24 小时内发货。", "发货"),
    "退款到账具体时间": ("退款到账具体时间：审核通过后 1-3 个工作日内原路退回。", "到账"),
    "运费规则": ("运费规则：满 99 元包邮，未满收取 8 元运费。", "运费"),
}
FACT_KEYWORDS = [(t, kw) for t, (_, kw) in POLICY_FACTS.items() if t not in ("运费规则",)]

def build_probe_set() -> List[TestCase]:
    """探针集：模拟线上抽样观察，4 条。其中 pb-m1/m2 是"混合诉求"新场景
    （物流 + 退款同时出现）——golden set 尚未覆盖的盲区。它们会不会变成
    回归用例，取决于哪个候选版本在探针上暴露失败。"""
    return [
        _case("pb-m1", "混合", "P1", "探针采样", "物流五天没更新了，如果一直不动我就申请退款。",
              must=("物流", "退款"), must_not=(FORBIDDEN_PROMISE,)),
        _case("pb-m2", "混合", "P1", "探针采样", "包裹显示已签收但我没收到，怎么退款？",
              must=("物流", "退款"), must_not=(FORBIDDEN_PROMISE,)),
        _case("pb-s1", "物流", "P1", "探针采样", "包裹到哪了？预计今天能送到吗？", must=("物流",)),
        _case("pb-p1", "政策", "P2", "探针采样", "请问运费规则是什么？", topic="运费规则", must=("运费",)),
    ]

# --- 3. MockLLM：被测系统（行为由 (prompt 版本, 模型) 决定） ---
# 与主仓库 labs/llm_client.py 的 QwenLLM 同构：chat(messages) -> 响应 dict，可整体
# 替换为真实客户端；内部行为完全由 (prompt_version, model) 决定，保证"评测差异 = 变更差异"。

def _parse_request(text: str) -> Dict[str, str]:
    """把结构化用户消息解析回字段（mock 的"理解"步骤）。"""
    fields = {"scenario": "", "order_status": "-", "topic": "-", "question": ""}
    key_map = {"[场景]": "scenario", "[订单状态]": "order_status",
               "[话题]": "topic", "[用户问题]": "question"}
    for line in text.splitlines():
        for prefix, key in key_map.items():
            if line.startswith(prefix):
                fields[key] = line[len(prefix):].strip()
    return fields

def build_request(case: TestCase) -> str:
    """把用例渲染成发给被测系统的结构化消息（模拟上游意图路由给的上下文）。"""
    return (f"[场景] {case.scenario}\n[订单状态] {case.order_status}\n"
            f"[话题] {case.topic}\n[用户问题] {case.question}")

class MockLLM:
    """确定性被测系统：对外接口与真实 LLM 客户端一致，内部用行为表模拟。"""

    def __init__(self, prompt_version: str, model: str, seed: int = SEED):
        self.prompt_version = prompt_version
        self.model = model
        self.calls = 0
        # 随机源只用于模拟网络/推理延迟；固定种子 => 延迟序列也可复现
        self._rng = random.Random(seed)

    def chat(self, messages: List[dict], **kwargs) -> dict:
        self.calls += 1
        user_text = messages[-1]["content"]
        ctx = _parse_request(user_text)
        text = self._generate(ctx)
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        return {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn", "model": self.model,
            # 确定性"token 用量"：按字符数折算，真实场景对应计费与成本
            "usage": {"input_tokens": prompt_chars // 2, "output_tokens": max(1, len(text) // 2)},
            "latency_ms": round(self._rng.uniform(30.0, 180.0), 2),
        }

    def __call__(self, messages: List[dict], **kwargs) -> dict:
        """__call__ 别名：与 QwenLLM 两种调用习惯都可互换。"""
        return self.chat(messages, **kwargs)

    # ---- 内部：行为表。每个分支标注对应的错误模式 ----

    def _generate(self, ctx: Dict[str, str]) -> str:
        sc = ctx["scenario"]
        if sc == "退款":
            return self._gen_refund(ctx["order_status"])
        if sc == "物流":
            return self._gen_shipping(ctx["question"])
        if sc == "政策":
            return self._gen_policy(ctx["topic"])
        if sc == "混合":
            return self._gen_mixed(ctx["question"])
        return "抱歉，这个问题我需要进一步确认。"

    def _gen_refund(self, status: str) -> str:
        if status == "已发货":
            if self.prompt_version in ("prompt_v1", "prompt_v3"):
                # 错误模式 A（过度承诺）：不核实订单状态就承诺到账时间。v1 天生
                # 没约束；v3 删掉了 v2 的约束——错误"复活"即回归陷阱的微观机制。
                return f"非常抱歉给您带来不便，我们先行为您办理退款，{FORBIDDEN_PROMISE}，请您放心。"
            return ("已为您核实订单状态：包裹仍在运输途中，需先拦截快递并确认退货，"
                    "退款将在收到退货后启动，请您留意后续通知。")
        # 未发货：直接承诺退款是正确行为
        if self.prompt_version in ("prompt_v1", "prompt_v3"):
            return "您的订单尚未发货，可以直接申请退款，退款预计 1-3 个工作日内原路退回。"
        return ("已为您核实订单状态：订单尚未发货，已为您提交退款申请，"
                "金额预计 1-3 个工作日内原路退回。")

    def _gen_shipping(self, question: str) -> str:
        if "没更新" in question:
            if self.prompt_version == "prompt_v3":
                # v3 的新规则修好了 B 类：物流问题用物流口径回答
                return "已为您查询物流状态：快递在中转环节出现延迟，预计 24 小时内更新轨迹，请您稍候。"
            if self.model == MODEL_STRONG:
                # 大参数模型用自身常识弥补 prompt 的 B 类缺口（换模型的能力收益）
                return "根据物流信息，包裹在中转环节出现延迟，预计 24 小时内更新轨迹。"
            # 错误模式 B（答非所问）：物流问题被当成退款回答。v1 如此，v2 也没修
            # ——v2 只针对 A 类错误（一次一变量：修复范围受控）。
            return "这种情况您可以申请退款，我们的退款政策是签收后 7 天内均可申请。"
        return ("根据物流信息，包裹预计 48 小时内送达；"
                "如需修改地址或查看承运快递，可在订单详情页操作。")

    def _gen_policy(self, topic: str) -> str:
        if self.model == MODEL_STRONG and topic in STRONG_REFUSAL_TOPICS:
            # 大参数模型的新错误模式：保守拒答。基线模型能答对的，它反而不答了。
            return "抱歉，这类具体时间我无法给出准确预测，请以页面实时展示为准。"
        fact, _ = POLICY_FACTS.get(topic, (f"关于{topic}，请以平台最新规则为准。", ""))
        return fact

    def _gen_mixed(self, question: str) -> str:
        if self.prompt_version == "prompt_v1":
            # v1 在混合诉求上双重翻车：过度承诺 + 漏掉物流部分
            return f"您好，可以先为您办理退款，{FORBIDDEN_PROMISE}，请您放心。"
        if self.prompt_version == "prompt_v3":
            # 新错误模式（关键词劫持）：v3 的"物流口径"规则把混合问题里的退款
            # 诉求整个吞掉——v3 独有、v1/v2 都没有的失败方式。
            return "您的问题涉及物流：物流信息正在核实中，请耐心等待快递回复。"
        if self.model == MODEL_STRONG and "签收" in question:
            # 大参数模型在"签收未收到"上啰嗦于核实流程、漏掉退款诉求
            return ("关于签收未收到的情况，需要先核实快递签收凭证与驿站代收记录，"
                    "核实流程一般需要 1-2 天。")
        # v2 + 基线模型：逐条回应（约束二生效），物流与退款都覆盖
        return ("已为您核实订单状态：物流侧轨迹异常，我们会立即督促快递核实；"
                "如确认丢件，可直接申请退款，审核通过后 1-3 个工作日内原路退回。")

# --- 4. 程序化评分器与评估运行 ---

def score_case(case: TestCase, output: str) -> Tuple[bool, List[str]]:
    """规则评分：关键点必须出现、红线词必须缺席（eval_lab03 的最小版）。
    输出判定依据（reasons），让每一次失败都可解释、可回流。"""
    reasons: List[str] = []
    for kw in case.must_include:
        if kw not in output:
            reasons.append(f"缺少关键点『{kw}』")
    for kw in case.must_not_include:
        if kw in output:
            reasons.append(f"触碰红线词『{kw}』")
    return (len(reasons) == 0), reasons

@dataclass
class CaseResult:
    case_id: str
    risk: str
    passed: bool
    output: str
    reasons: Tuple[str, ...]

@dataclass
class EvalRun:
    """一次评估运行的完整产物：逐条结果 + 聚合。"""
    config: SystemConfig
    results: List[CaseResult]
    n_cases: int
    n_pass: int
    pass_rate: float
    p0_failures: Tuple[str, ...]   # P0 风险用例的失败 id（门禁用）
    failed_ids: Tuple[str, ...]

    @property
    def pass_map(self) -> Dict[str, bool]:
        return {r.case_id: r.passed for r in self.results}

def evaluate(config: SystemConfig, cases: List[TestCase]) -> EvalRun:
    """跑一遍评估：为每个配置新建一个 MockLLM（种子固定 => 可复现）。"""
    llm = MockLLM(config.prompt_version, config.model, seed=SEED)
    system_prompt = PROMPTS[config.prompt_version]
    results: List[CaseResult] = []
    for case in cases:
        messages = [{"role": "system", "content": system_prompt},
                    {"role": "user", "content": build_request(case)}]
        resp = llm.chat(messages)
        output = resp["content"][0]["text"]
        passed, reasons = score_case(case, output)
        results.append(CaseResult(case.case_id, case.risk, passed, output,
                                  tuple(reasons)))
    n = len(results)
    n_pass = sum(1 for r in results if r.passed)
    return EvalRun(
        config=config, results=results, n_cases=n, n_pass=n_pass,
        pass_rate=n_pass / n if n else 0.0,
        p0_failures=tuple(r.case_id for r in results if r.risk == "P0" and not r.passed),
        failed_ids=tuple(r.case_id for r in results if not r.passed))

# --- 5. P0 门禁：通过率阈值 + P0 一票否决 + 回归零容忍 ---

def gate_check(pass_rate: float, p0_failures: List[str], regressions: List[str],
               threshold: float = GATE_PASS_THRESHOLD) -> Tuple[bool, List[str]]:
    """门禁决策表，三条判据按严重度给出拒绝理由：
    1) P0 一票否决；2) 回归零容忍；3) 通过率阈值（含边界）。"""
    reasons: List[str] = []
    if p0_failures:
        reasons.append(f"P0 一票否决：{len(p0_failures)} 个 P0 风险用例失败"
                       f"（{', '.join(p0_failures)}）")
    if regressions:
        reasons.append(f"回归检测失败：{len(regressions)} 个基线已通过用例被改坏"
                       f"（{', '.join(regressions)}）")
    if pass_rate < threshold:
        reasons.append(f"通过率 {pass_rate:.1%} 低于门禁阈值 {threshold:.0%}")
    if reasons:
        return False, reasons
    return True, ["达到门禁：通过率达标、无 P0 失败、无回归"]

# --- 6. EDD 闭环编排器：验证 → 评估 → 门禁 → 毕业/回流 ---

@dataclass
class EDDLoop:
    golden: List[TestCase]
    probe: List[TestCase]
    regression: List[TestCase] = field(default_factory=list)   # 只增不减
    regression_history: List[int] = field(default_factory=lambda: [0])
    current: Optional[SystemConfig] = None        # 当前"线上"版本
    baseline_pass: Dict[str, bool] = field(default_factory=dict)  # 基线逐条通过情况
    decisions: List[dict] = field(default_factory=list)         # 审计日志

    # ---- 变更入口：一次只处理一个变更 ----
    def process(self, change: CandidateChange) -> dict:
        decision: dict = {
            "change_id": change.change_id,
            "description": change.description,
            "target": change.to_config().label(),
            "accepted": False,
            "evaluated": False,
        }
        # 第 0 步：一次一变量纪律。多变量变更直接拒绝、不浪费评估预算——
        # 即便评出好坏也无法归因（到底是 prompt 还是模型的功劳/锅？）。
        if not change.is_baseline and len(change.changed_dims) != 1:
            decision["reasons"] = [
                f"违反一次一变量纪律：同时改动 {list(change.changed_dims)}，拒绝评估"
            ]
            self.decisions.append(decision)
            self.regression_history.append(len(self.regression))
            return decision
        # 第 1 步：评估范围 = golden set ∪ 当前回归集（去重保序）。
        # 含义：候选版本必须同时通过"新用例"与"既有回归集"。
        eval_cases = self._current_eval_cases()
        run = evaluate(change.to_config(), eval_cases)
        decision.update(evaluated=True, n_cases=run.n_cases, pass_rate=run.pass_rate,
                        p0_failures=list(run.p0_failures), failed_ids=list(run.failed_ids),
                        fail_reasons={r.case_id: list(r.reasons)
                                      for r in run.results if not r.passed})
        # 第 2 步：回归检测 = 用例级 diff（基线通过 -> 候选失败）。
        # 不用聚合通过率比较，因为"修 3 条坏 3 条"时总通过率纹丝不动。
        regressions = sorted(cid for cid, ok in self.baseline_pass.items()
                             if ok and not run.pass_map.get(cid, False))
        decision["regressions"] = regressions
        # 第 3 步：门禁决策
        accepted, reasons = gate_check(run.pass_rate, list(run.p0_failures),
                                       regressions)
        decision["accepted"] = accepted
        decision["reasons"] = reasons
        if accepted:
            # 通过：更新线上版本，并把通过的用例"毕业"进回归集（只增）。
            self.current = change.to_config()
            self.baseline_pass = dict(run.pass_map)
            self._graduate(run)
        else:
            # 拒绝：跑探针集模拟线上抽样，把它暴露的新失败模式回流为用例。
            self._backflow_from_probe(change.to_config())
        self.decisions.append(decision)
        self.regression_history.append(len(self.regression))
        return decision

    # ---- 回归集维护 ----
    def _known_ids(self) -> set:
        return {c.case_id for c in self.golden} | {c.case_id for c in self.regression}

    def _current_eval_cases(self) -> List[TestCase]:
        seen, cases = set(), []
        for c in self.golden + self.regression:
            if c.case_id not in seen:
                seen.add(c.case_id)
                cases.append(c)
        return cases

    def _graduate(self, run: EvalRun) -> None:
        """接受版本通过的用例固化为回归用例（已存在的跳过——只增不重复）。"""
        index = {c.case_id: c for c in self._current_eval_cases()}
        existing = {c.case_id for c in self.regression}
        for r in run.results:
            if r.passed and r.case_id not in existing:
                self.regression.append(index[r.case_id])

    def _backflow_from_probe(self, config: SystemConfig) -> List[str]:
        """badcase 回流：被拒版本在探针集上的失败，若属尚未覆盖的用例，
        编码为新回归用例（origin 改写为 线上badcase回流，只增不减）。"""
        probe_run = evaluate(config, self.probe)
        known = self._known_ids()
        added: List[str] = []
        for case, r in zip(self.probe, probe_run.results):
            if not r.passed and case.case_id not in known:
                self.regression.append(replace(case, origin="线上badcase回流"))
                added.append(case.case_id)
        return added

    # ---- 收尾：当前线上版本对全量回归集做最终回归 ----
    def final_regression(self) -> EvalRun:
        assert self.current is not None, "尚无被接受的版本"
        return evaluate(self.current, self.regression)

# --- 7. 变更队列与全流程运行 ---

def build_change_queue() -> List[CandidateChange]:
    """四个候选：基线 + 三个真实变更。真实变更各自只动一个维度。"""
    return [
        CandidateChange("ch-0-baseline", "初始部署：基线 prompt_v1",
                        None, "prompt_v1", None, MODEL_BASE, is_baseline=True),
        CandidateChange("ch-1-prompt-v2", "修 A 类错误：加『先核实订单状态』约束",
                        "prompt_v1", "prompt_v2", MODEL_BASE, MODEL_BASE),
        CandidateChange("ch-2-prompt-v3", "修 B 类错误：物流问题用物流口径"
                        "（但移除了 v2 的核实约束——回归陷阱）",
                        "prompt_v2", "prompt_v3", MODEL_BASE, MODEL_BASE),
        CandidateChange("ch-3-model-swap", "换大参数模型，prompt 保持 v2",
                        "prompt_v2", "prompt_v2", MODEL_BASE, MODEL_STRONG),
    ]

# 反例：同时改 prompt 与 model 的打包变更——演示纪律检查真的会拦截。
BUNDLE_ANTI_EXAMPLE = CandidateChange(
    "ch-x-bundle", "反例：prompt v2→v3 与换模型打包提交",
    "prompt_v2", "prompt_v3", MODEL_BASE, MODEL_STRONG)

def run_everything(verbose: bool = False) -> dict:
    """跑一遍完整 EDD 闭环，返回全部产物（供展示与自检复用）。"""
    random.seed(SEED)
    p = print if verbose else (lambda *a, **k: None)
    golden, probe = build_golden_set(), build_probe_set()
    loop = EDDLoop(golden=golden, probe=probe)
    baseline, ch_v2, ch_v3, ch_swap = build_change_queue()

    p("=" * 68)
    p("LAB 10 · EDD 全闭环：门禁 / 回归 / 一次一变量（纯标准库 / 确定性）")
    p("=" * 68)
    p("\n[1/6] 场景设定")
    p("   被测功能：电商客服『退款/物流咨询』GenAI 回复")
    p(f"   golden set：{len(golden)} 条 = 退款 6（P0，含 3 条线上 badcase 回流）"
      f" + 物流 5（P1）+ 政策 9（P2）")
    p(f"   探针集：{len(probe)} 条（模拟线上抽样，不参与门禁）；"
      f"门禁：通过率 ≥ {GATE_PASS_THRESHOLD:.0%} 且 0 个 P0 失败 且 无回归")

    p("\n[2/6] 基线评估：prompt_v1 + model-base")
    d0 = loop.process(baseline)
    _render_decision(p, d0)
    p(f"   → badcase 回流：探针暴露 {loop.regression_history[1]} 条新失败"
      f"（pb-m1/pb-m2 混合诉求），编码进回归集（现 {loop.regression_history[1]} 条）")

    p("\n[3/6] 一次一变量纪律：先拦截一个打包变更反例")
    db = loop.process(BUNDLE_ANTI_EXAMPLE)
    p(f"   · {db['change_id']}（{db['description']}）")
    p(f"   → ❌ {db['reasons'][0]}（未进行评估——这就是纪律的价值）")
    for ch, note in ((ch_v2, "预期：修好 A 类、通过门禁"),
                     (ch_v3, "预期：修好 B 类、但触发回归陷阱"),
                     (ch_swap, "预期：有能力收益、也有新错误模式")):
        p(f"\n[评估变更] {ch.change_id}：{ch.description}")
        p(f"   （{note}）")
        d = loop.process(ch)
        _render_decision(p, d)
        if ch is ch_v2 and d["accepted"]:
            p(f"   → 毕业 {len(loop.regression) - 2} 条通过用例进回归集"
              f"（回归集现 {len(loop.regression)} 条）")
        if ch is ch_v3:
            p("   分析：v3 修好 B 类（gs-s1/gs-s2 由失败转通过），"
              "但删除 v2 约束后 A 类错误复活（gs-r4/r5/r6 回归）+ "
              "混合诉求被『物流口径』劫持（pb-m1/m2）")
        if ch is ch_swap:
            p("   分析：大参数模型补上 B 类缺口，但对时间类问题保守拒答"
              "（gs-p8/gs-p9）、签收场景漏退款诉求（pb-m2）——换模型不是免费午餐")

    p("\n[4/6] 回归集演化（只增不减）：" +
      " → ".join(str(x) for x in loop.regression_history))
    # 按来源数：pb- 前缀 = 探针回流入库；gs- 前缀 = golden set 毕业固化
    n_back = sum(1 for c in loop.regression if c.case_id.startswith("pb-"))
    p(f"   构成：{len(loop.regression) - n_back} 条毕业用例 + {n_back} 条探针回流入库")

    p("\n[5/6] 最终回归：当前线上版本 "
      f"{loop.current.label()} × 全量回归集（{len(loop.regression)} 条）")
    final = loop.final_regression()
    p(f"   通过率 {final.pass_rate:.1%}（{final.n_pass}/{final.n_cases}）"
      + ("，全绿 ✅" if final.n_pass == final.n_cases else "，仍有失败 ❌"))

    return {"loop": loop, "golden": golden, "probe": probe,
            "decisions": {d["change_id"]: d for d in loop.decisions},
            "final_pass_rate": final.pass_rate,
            "final_n_pass": final.n_pass, "final_n_cases": final.n_cases}

def _render_decision(p, d: dict) -> None:
    """渲染一次门禁决策（verbose 输出用）。"""
    if not d["evaluated"]:
        p(f"   · 未评估：{d['reasons'][0]}")
        return
    p(f"   通过率 {d['pass_rate']:.1%}（{round(d['pass_rate'] * d['n_cases'])}"
      f"/{d['n_cases']}）| P0 失败 {len(d['p0_failures'])} | 回归 {len(d.get('regressions', []))} 条")
    p(f"   门禁判定：{'✅ 接受' if d['accepted'] else '❌ 拒绝'}")
    for reason in d["reasons"]:
        p(f"   · {reason}")

def summarize(art: dict) -> dict:
    """提取可比较的摘要（用于确定性自检：跑两遍必须完全一致）。"""
    loop: EDDLoop = art["loop"]
    return {
        "decisions": [(d["change_id"], d["accepted"], d["evaluated"], d.get("pass_rate"),
                       tuple(d.get("p0_failures", [])), tuple(d.get("regressions", [])))
                      for d in loop.decisions],
        "regression_history": tuple(loop.regression_history),
        "regression_ids": tuple(c.case_id for c in loop.regression),
        "current": (loop.current.prompt_version, loop.current.model),
        "final_pass_rate": art["final_pass_rate"],
    }

# --- 8. 自检：断言核心结论（不是断言"跑完了"） ---

def run_self_checks(art: dict) -> None:
    loop: EDDLoop = art["loop"]
    D = art["decisions"]
    d0, db = D["ch-0-baseline"], D["ch-x-bundle"]
    d2, d3, d4 = D["ch-1-prompt-v2"], D["ch-2-prompt-v3"], D["ch-3-model-swap"]

    # (a) 门禁决策表本身必须正确：阈值含边界、P0 一票否决、回归零容忍
    assert gate_check(0.90, [], [])[0] is True, "阈值边界 90% 应当通过"
    assert gate_check(0.89, [], [])[0] is False, "低于阈值必须拒绝"
    assert gate_check(0.99, ["gs-r4"], [])[0] is False, "P0 失败必须一票否决"
    assert gate_check(0.99, [], ["gs-r1"])[0] is False, "有回归必须拒绝"
    assert gate_check(0.95, [], [])[0] is True, "干净高分应当通过"

    # (b) 一次一变量纪律：队列里每个真实变更恰好改一个维度；打包反例被拦截
    for ch in build_change_queue():
        if not ch.is_baseline:
            assert len(ch.changed_dims) == 1, f"{ch.change_id} 改动维度数 != 1"
    assert len(BUNDLE_ANTI_EXAMPLE.changed_dims) == 2
    assert db["evaluated"] is False and db["accepted"] is False
    assert "一次一变量" in db["reasons"][0], "反例必须因纪律被拒"

    # (c) 评估顺序：一次一评估，且顺序就是队列顺序（决策记录可追溯）
    assert [d["change_id"] for d in loop.decisions] == [
        "ch-0-baseline", "ch-x-bundle", "ch-1-prompt-v2", "ch-2-prompt-v3", "ch-3-model-swap"]

    # (d) 基线 v1 被门禁拒绝：通过率恰为 75%，P0 失败恰为 3 条已发货退款
    assert d0["accepted"] is False
    assert abs(d0["pass_rate"] - 0.75) < 1e-12, f"v1 通过率应为 75%，实际 {d0['pass_rate']}"
    assert d0["p0_failures"] == ["gs-r4", "gs-r5", "gs-r6"]

    # (e) v2 通过门禁：P0 零失败，且对旧用例零回归（v1 会做的 v2 全都会）
    assert d2["accepted"] is True and d2["p0_failures"] == []
    assert d2["regressions"] == []
    v1_run = evaluate(SystemConfig("prompt_v1", MODEL_BASE), loop.golden)
    v2_run = evaluate(SystemConfig("prompt_v2", MODEL_BASE), loop.golden)
    v1_pass = {c for c, ok in v1_run.pass_map.items() if ok}
    v2_pass = {c for c, ok in v2_run.pass_map.items() if ok}
    assert v1_pass < v2_pass, "v2 通过集必须是 v1 的真超集（修 A 不破坏任何旧能力）"
    assert {"gs-r4", "gs-r5", "gs-r6"} <= (v2_pass - v1_pass), "A 类错误必须被 v2 修复"
    assert {"gs-s1", "gs-s2"} <= set(v2_run.failed_ids), "v2 不应顺手修 B 类（一次一变量的边界）"
    assert abs(d2["pass_rate"] - 20 / 22) < 1e-12, "v2 在 22 条评估集上应为 20/22"

    # (f) v3 被门禁拒绝（回归陷阱）：修好 B 类，但改坏基线已通过的用例
    assert d3["accepted"] is False
    assert {"gs-r4", "gs-r5", "gs-r6"} <= set(d3["regressions"]), "A 类错误复活必须被记为回归"
    assert set(d3["regressions"]) == {"gs-r4", "gs-r5", "gs-r6", "pb-m1", "pb-m2"}
    v3_run = evaluate(SystemConfig("prompt_v3", MODEL_BASE), loop.golden)
    assert v3_run.pass_map["gs-s1"] and v3_run.pass_map["gs-s2"], "v3 应修好 B 类"
    assert not v3_run.pass_map["gs-r4"], "v3 应在已发货退款上重新翻车"

    # (g) model_swap 也被拒绝：即便 P0 零失败，通过率不达标 + 有回归照样拒
    assert d4["accepted"] is False and d4["p0_failures"] == []
    assert d4["pass_rate"] < GATE_PASS_THRESHOLD
    assert set(d4["regressions"]) == {"gs-p8", "gs-p9", "pb-m2"}, \
        "大参数模型的新错误模式（保守拒答等）必须被逐条归因"
    swap_run = evaluate(SystemConfig("prompt_v2", MODEL_STRONG), loop.golden)
    assert swap_run.pass_map["gs-s1"], "大参数模型应能补上 B 类缺口（能力收益真实存在）"

    # (h) 回归集只增不减：规模轨迹精确为 0→2→2→20→20→20，且无重复入库
    assert tuple(loop.regression_history) == (0, 2, 2, 20, 20, 20), \
        f"回归集规模轨迹异常：{loop.regression_history}"
    assert all(b >= a for a, b in zip(loop.regression_history, loop.regression_history[1:])), \
        "回归集必须单调不减"
    ids = [c.case_id for c in loop.regression]
    assert len(ids) == len(set(ids)) == 20, "回归集不得重复入库"
    backflowed = {c.case_id for c in loop.regression if c.origin == "线上badcase回流"
                  and c.case_id.startswith("pb-")}
    assert backflowed == {"pb-m1", "pb-m2"}, "v1/v3 暴露的混合诉求失败必须回流入库"
    assert len(loop.golden) == 20 and loop.probe is not None

    # (i) golden set 含坏样本（历史事故回流入库的高危用例）
    bad_samples = {c.case_id for c in loop.golden if c.origin == "线上badcase回流"}
    assert bad_samples == {"gs-r4", "gs-r5", "gs-r6"}

    # (j) 最终版本全绿：被接受的 v2 对全量回归集（含回流新用例）100% 通过
    assert (loop.current.prompt_version, loop.current.model) == ("prompt_v2", MODEL_BASE)
    assert art["final_pass_rate"] == 1.0 and art["final_n_pass"] == art["final_n_cases"] == 20

    # (k) 确定性：整条闭环跑三遍（含 verbose 那遍），决策摘要逐字节一致
    s0 = summarize(art)
    s1 = summarize(run_everything(verbose=False))
    s2 = summarize(run_everything(verbose=False))
    assert s0 == s1 == s2, "EDD 闭环必须完全可复现"

# --- 9. 演示入口 ---

def main() -> None:
    art = run_everything(verbose=True)
    print("\n[自检] 运行 assert 断言（门禁决策表 / 一次一变量 / v2 接受 / v3 拒绝 /"
          "回归集单调性 / 换模型拒绝 / 最终全绿 / 确定性复现）...")
    run_self_checks(art)
    print("   门禁决策表 5 组输入全部正确（含 90% 边界与 P0 一票否决）✔")
    print("   v1 拒绝（75%，P0×3）→ v2 接受（90.9%，零回归）✔")
    print("   v3 触发回归陷阱被拒（5 条回归）；model_swap 亦被拒 ✔")
    print("   回归集 0→2→2→20→20→20 只增不减，最终版本全绿 20/20 ✔")
    print("   闭环跑三遍决策摘要完全一致（确定性）✔")
    print("\n✅ 自检通过：eval_lab10_edd_loop.py 全部断言成立")

if __name__ == "__main__":
    main()
