#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab02_golden_dataset.py — 黄金数据集构建与治理流水线
=========================================================

【实验目的】
    动手构建一个「可入库、可扩展、可治理、随版本演进」的黄金数据集
    （Golden Set / 评测用例集）。评测集不是一次性的静态文件，而是一条
    有生命周期的治理流水线。本实验完整实现它的五个环节：
        1) 用例结构     —— 用 dataclass 固化"一条合格用例长什么样"；
        2) 四类来源     —— 专家手写 / LLM 扩展 / 线上真实数据 / badcase 回流；
        3) 入库标准     —— 五项检查（可复现/期望明确/根因标签/代表性/已脱敏）
                           + 同簇去重，不合格的 badcase 坚决拒收；
        4) 毕业机制     —— 能力集用例连续 M 个版本通过率 100% → 毕业评审 →
                           升入回归集；回归集只增不减；
        5) 回归门禁     —— 回归集每个版本必跑，任何一条失败即拦截该版本，
                           失败本身再经 badcase 回流编码为新用例。
    学完你会明白：为什么"评测集的质量决定评测结论的质量"，以及
    "用例治理"是如何支撑 agent 迭代的 evals 闭环的。

【对应章节】
    本特辑第 E03 章 · 黄金数据集与用例设计
    （关联：主手册第 8 章 · Agent 评估与可观测性；本特辑 eval_lab10_edd_loop.py
      会复用本实验的"回归集只增不减"，搭建完整的 EDD 门禁闭环）

【核心概念】
    - Golden Set（黄金数据集）: 覆盖核心业务路径与高风险边界的固定用例集，
      是版本对比与发布门禁的基线。工业界常见规模：起步 50~200 条高质量用例。
    - 四类用例来源: 专家设计（定标准）；LLM 扩展（先定结构字段再生成自然语言）；
      线上真实数据（注意幸存者偏差）；badcase 回流（失败 → 资产）。
    - 幸存者偏差: 线上随机抽样中正常流程占多数、高风险边缘场景占比极低，
      随机采样的报告"看起来不错"但恰好漏掉关键问题；需按风险分层采样。
    - 入库标准: badcase 不天然是用例。不可复现的无法验证、期望不明的无法
      打分、无根因标签的无法归因、一次性抖动不代表一类问题、未脱敏的有
      合规风险——五项缺一不可。
    - 能力评测 vs 回归评测: 能力集回答"agent 能把什么做好"（容忍失败、
      驱动迭代）；回归集回答"原有能力是否还在"（接近 100%、防御漂移、
      只增不减）。用例连续 M 个版本 100% 通过即"毕业"进回归集。

【如何运行】
    cd evals-special/labs && python3 eval_lab02_golden_dataset.py
    （纯 Python 标准库，零依赖，固定随机种子，任何机器结果完全一致）

【思考题（面试延伸）】
    1. 为什么 LLM 扩展用例要"先定结构字段（场景/订单状态/用户诉求/期望动作），
       再生成自然语言"？让模型自由编造用例会发生什么？本实验的 MockLLM
       直接"拒绝无结构请求"，这种接口约束在真实系统里对应什么（模板/schema
       校验/结构化输出）？
    2. 线上随机采样为什么有幸存者偏差？分层采样如何缓解？对高风险样本
       过采样会带来什么代价（通过率失真），应如何在指标聚合时修正（加权）？
    3. 回归集"只增不减"会不会无限膨胀？结合毕业机制、长尾集、抽样集与
       用例执行预算，谈谈如何在"防回归"与"评测成本"之间取得平衡。
    4. 五项入库标准中，实际工作中最容易被跳过的是哪一项？放行一条
       "期望不明确"的用例进库，后续会在哪个环节付出代价（judge 误判、
       门禁噪声、RCA 无法归因）？
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# 1. 用例结构：先用代码固化"什么是一条用例"
# ---------------------------------------------------------------------------
# 为什么用强类型 dataclass 而不是随手一个 dict？因为用例的字段本身就是
# 入库标准的一部分：字段缺失 = 用例不合格。把结构显式化，入库检查器才能
# 机械化校验，而不依赖人工评审的眼力。


class CaseSource(Enum):
    """用例的四类来源——来源多样性决定数据集视角的多样性。"""
    EXPERT = "专家手写"
    LLM_EXPANSION = "LLM扩展"
    ONLINE = "线上数据"
    BADCASE_BACKFLOW = "badcase回流"


class CaseStatus(Enum):
    """用例生命周期三态。
    CAPABILITY 能力集：度量"agent 能否做好"，容忍失败，驱动迭代；
    GRADUATED  已毕业：通过毕业评审（连续 M 版本 100% 通过）、待升入回归集的
               过渡态——两阶段流转保证"评审"与"入库"是两个可审计的动作；
    REGRESSION 回归集：版本门禁，只增不减，每个版本必须全部通过。
    """
    CAPABILITY = "能力集"
    GRADUATED = "已毕业"
    REGRESSION = "回归集"


class RiskLevel(Enum):
    """风险分级决定用例的处置力度：P0 失败通常直接否决版本。"""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


@dataclass
class GoldenCase:
    """一条黄金用例。
    structured_fields 是"先结构后语言"的关键产物：场景变量（订单状态、
    用户诉求等）先被确定，自然语言输入只是它的渲染结果。
    expected_behavior 以 dict 承载期望动作/护栏，便于程序化评分器消费。
    """
    case_id: str
    source: CaseSource
    scenario: str
    user_input: str
    structured_fields: Dict[str, str]
    expected_behavior: Dict[str, str]
    risk_level: RiskLevel
    status: CaseStatus
    difficulty: float                       # 模拟用：用例难度（越高越难通过）
    created_version: int = 0
    derived_from: Optional[str] = None      # 扩展用例记录种子用例 id，保证可追溯
    graduated_version: Optional[int] = None
    consecutive_full_pass: int = 0          # 连续 100% 通过的版本数（毕业计数）
    history: List[Tuple[int, bool]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. 入库标准检查器：五项标准 + 同簇去重
# ---------------------------------------------------------------------------
# 为什么要设入库门槛？badcase 不天然是用例：
#   不可复现 → 修没修好无法验证；期望不明 → 评分器/judge 无从打分；
#   无根因标签 → 无法归因到能力域；一次性抖动 → 不代表一类问题；
#   未脱敏 → 合规风险。任何一项放行，都会污染后续所有评测结论。
# 这里用"字段存在性 + 内容扫描"来模拟五项标准（真实系统是流程 + 人工确认）。

INTAKE_CRITERIA: Tuple[str, ...] = ("可复现", "期望明确", "根因标签", "代表性", "已脱敏")

# 根因标签必须落在能力域分类表内——乱填的标签等于没有标签（无法归因聚合）
ALLOWED_ROOT_CAUSES: Set[str] = {
    "意图识别", "退款流程", "订单状态", "物流查询", "风险拦截", "回复生成", "知识检索",
}

# 手机号 / 身份证号的最小正则——脱敏检查不能只信申报标志，必须扫描内容
SENSITIVE_RE = re.compile(r"1[3-9]\d{9}|\d{17}[\dXx]")


def case_signature(scenario: str, expected_action: str, user_appeal: str = "") -> str:
    """同簇去重的簇 key：场景 × 期望动作 × 用户诉求。
    用哈希做指纹，入库时查重，防止同一类问题反复进库刷量。"""
    raw = f"{scenario}::{expected_action}::{user_appeal}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


@dataclass
class IntakeCandidate:
    """待入库的候选用例（可能来自线上会话、badcase、扩展生成）。
    注意：它携带的字段是否齐全，直接决定能否通过入库检查。"""
    candidate_id: str
    source: CaseSource
    scenario: str
    user_input: str
    structured_fields: Dict[str, str]
    expected_behavior: Dict[str, str]
    risk_level: RiskLevel
    difficulty: float
    trace_id: str = ""              # 可复现：有稳定 trace
    repro_steps: str = ""           # 可复现：或有人工确认的复现步骤
    root_cause_label: str = ""      # 根因标签
    occurrence_count: int = 1       # 代表性：出现次数
    cluster_id: str = ""            # 代表性：所属问题簇
    desensitized: bool = False      # 已脱敏：申报标志
    note: str = ""


class IntakeChecker:
    """入库标准检查器：返回 (是否通过, 未满足的标准列表)。
    拒绝时必须给出理由——拒绝本身要可审计，否则提交人不知道该补什么。"""

    def check(self, cand: IntakeCandidate,
              known_signatures: Set[str]) -> Tuple[bool, List[str]]:
        unmet: List[str] = []

        # 标准一：可复现——有 trace 或有人工确认的复现步骤
        if not (cand.trace_id or cand.repro_steps):
            unmet.append("可复现")

        # 标准二：期望明确——必须写得出可判定的期望动作
        action = (cand.expected_behavior or {}).get("expected_action", "").strip()
        if not action:
            unmet.append("期望明确")

        # 标准三：根因标签——必须落在能力域分类表内
        if cand.root_cause_label not in ALLOWED_ROOT_CAUSES:
            unmet.append("根因标签")

        # 标准四：代表性——出现 ≥2 次或已归入问题簇（排除一次性抖动）
        if not (cand.occurrence_count >= 2 or cand.cluster_id):
            unmet.append("代表性")

        # 标准五：已脱敏——申报标志为真，且内容扫描无敏感信息
        # （只信标志不扫内容是常见漏洞，这里两者都查）
        hit = SENSITIVE_RE.search(cand.user_input + " " + cand.note)
        if not (cand.desensitized and hit is None):
            unmet.append("已脱敏")

        # 同簇去重：签名已入库 → 归入"代表性"不满足（同一类问题已有代表例）
        sig = case_signature(cand.scenario, action,
                             cand.structured_fields.get("user_appeal", ""))
        if sig in known_signatures:
            unmet.append("代表性")

        return (not unmet), unmet


# ---------------------------------------------------------------------------
# 3. MockLLM：用例扩展生成器（与主仓库 labs/llm_client.py 的 QwenLLM 同构）
# ---------------------------------------------------------------------------
# 关键设计：MockLLM 只接受「结构字段 JSON」，拒绝自由发挥。
# 这就是"先定结构字段再生成自然语言"的接口级表达：场景、订单状态、
# 用户诉求、期望动作在生成前全部确定，LLM 只负责把它们渲染成接近真实
# 用户口吻的自然语言。好处是扩展用例在结构上必然保留种子用例的场景与
# 期望行为，不会跑偏；真实系统里对应"模板 + 结构化输出 + schema 校验"。


class MockLLM:
    """确定性 mock LLM。chat()/simple()/__call__ 接口与 QwenLLM 一致，
    生产环境可整体替换为真实客户端而上层代码不动。
    其"生成智能"完全由模板决定，随机源（固定 seed）只决定口吻风格，
    因此同样的调用序列永远产出同样的文本——扩展结果可复现、可断言。"""

    REFUSE_PREFIX = "REFUSE"

    # 订单状态 → 期望动作：期望行为由结构字段推导，而不是生成时现编
    EXPECTED_ACTION_BY_ORDER_STATUS = {
        "未收到货": "先核实物流状态再决定是否发起退款",
        "收到破损": "引导用户提交凭证后发起退款",
        "已退货未退款": "查询退款进度并催促",
    }
    ORDER_STATUS_DESC = {
        "未收到货": "显示已发货但一直没送到",
        "收到破损": "收到了但是商品有破损",
        "已退货未退款": "货已经退回去了但退款还没到账",
    }
    USER_APPEAL_DESC = {
        "平和": "就是想咨询一下",
        "焦急": "有点着急麻烦尽快",
        "愤怒": "已经等很久了今天必须给个说法",
    }
    _TEMPLATES = (
        "我那个订单{order_id}，{status_desc}，{appeal}，麻烦帮我处理下退款。",
        "你好，订单{order_id}{status_desc}，{appeal}，我想申请退款。",
        "帮我看下订单{order_id}，{status_desc}，{appeal}，退款什么时候能到？",
    )

    def __init__(self, name: str = "mock-case-generator-v1", seed: int = 11):
        self.name = name
        self.seed = seed
        self._rng = random.Random(seed)
        self.calls = 0

    # ---- 与 QwenLLM 同构的接口 -------------------------------------------
    def chat(self, messages: List[dict], tools=None, system=None,
             max_tokens=None, temperature=None) -> dict:
        """与 QwenLLM.chat 同签名，返回 Anthropic 风格响应结构。"""
        prompt = messages[-1]["content"] if messages else ""
        self.calls += 1
        text = self._generate(prompt)
        return {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": max(1, len(prompt) // 2),
                      "output_tokens": max(1, len(text) // 2)},
        }

    def simple(self, prompt: str, system=None) -> str:
        resp = self.chat([{"role": "user", "content": prompt}], system=system)
        return resp["content"][0]["text"]

    def __call__(self, prompt: str) -> str:
        return self.simple(prompt)

    # ---- 内部：结构字段 → 自然语言 ----------------------------------------
    def _generate(self, prompt: str) -> str:
        try:
            spec = json.loads(prompt)
        except (json.JSONDecodeError, TypeError):
            # 没有结构字段的自由请求一律拒绝——这是刻意为之的约束
            return f"{self.REFUSE_PREFIX}: 扩展请求必须提供结构字段 JSON，拒绝自由发挥"
        missing = [k for k in ("scenario", "order_status", "user_appeal", "order_id")
                   if k not in spec]
        if missing:
            return f"{self.REFUSE_PREFIX}: 缺少结构字段 {missing}"
        if spec["scenario"] != "退款":
            return f"{self.REFUSE_PREFIX}: 未开放该场景模板: {spec['scenario']}"
        if spec["order_status"] not in self.ORDER_STATUS_DESC:
            return f"{self.REFUSE_PREFIX}: 非法订单状态: {spec['order_status']}"
        tpl = self._rng.choice(self._TEMPLATES)   # 口吻随机但种子固定 → 确定
        return tpl.format(
            order_id=spec["order_id"],
            status_desc=self.ORDER_STATUS_DESC[spec["order_status"]],
            appeal=self.USER_APPEAL_DESC[spec["user_appeal"]],
        )


# ---------------------------------------------------------------------------
# 4. 四类来源之一：专家手写用例（定标准）
# ---------------------------------------------------------------------------
# 专家用例数量少但质量高：它们定义了"什么叫对"，是其它来源用例的锚点。
# R0 演示"基线快照"机制：先跑一次 → 人工确认 → 快照为基线，直接进回归集。


def make_expert_cases() -> Tuple[List[GoldenCase], GoldenCase]:
    e1 = GoldenCase(
        case_id="E1-退款进度", source=CaseSource.EXPERT, scenario="退款",
        user_input="我把货退回去了但退款还没到账，订单号 SO-20260001，帮我查下进度。",
        structured_fields={"order_status": "已退货未退款", "user_appeal": "平和",
                           "order_id": "SO-20260001"},
        expected_behavior={"expected_action": "查询退款进度并催促"},
        risk_level=RiskLevel.P1, status=CaseStatus.CAPABILITY, difficulty=0.40)
    e2 = GoldenCase(
        case_id="E2-改订单地址", source=CaseSource.EXPERT, scenario="改订单",
        user_input="订单 SO-20260002 还没发货，我想把收货地址改成公司，麻烦帮我改一下。",
        structured_fields={"order_status": "未发货", "user_appeal": "平和",
                           "order_id": "SO-20260002"},
        expected_behavior={"expected_action": "校验订单状态后更新收货地址并确认"},
        risk_level=RiskLevel.P1, status=CaseStatus.CAPABILITY, difficulty=0.60)
    e3 = GoldenCase(
        case_id="E3-投诉升级", source=CaseSource.EXPERT, scenario="投诉",
        user_input="你们这个处理结果我不接受，我要投诉，给我转负责人！",
        structured_fields={"order_status": "已退货未退款", "user_appeal": "愤怒",
                           "order_id": "SO-20260001"},
        expected_behavior={"expected_action": "安抚情绪并按升级流程转接人工负责人"},
        risk_level=RiskLevel.P2, status=CaseStatus.CAPABILITY, difficulty=0.92)
    r0 = GoldenCase(
        case_id="R0-问候红线", source=CaseSource.EXPERT, scenario="问候",
        user_input="在吗？帮我看看我的订单。",
        structured_fields={"order_status": "正常咨询", "user_appeal": "平和",
                           "order_id": "SO-20260000"},
        expected_behavior={"expected_action": "礼貌响应并核实订单，不作任何越权承诺"},
        risk_level=RiskLevel.P0, status=CaseStatus.REGRESSION, difficulty=0.20)
    return [e1, e2, e3], r0


# ---------------------------------------------------------------------------
# 5. 四类来源之二：LLM 扩展（先定结构字段，再生成自然语言）
# ---------------------------------------------------------------------------

ORDER_STATUS_KEYS = ("未收到货", "收到破损", "已退货未退款")
USER_APPEAL_KEYS = ("平和", "焦急", "愤怒")


def expand_cases(seed: GoldenCase, llm: MockLLM, count: int = 3) -> List[GoldenCase]:
    """从种子用例扩展同场景变体。
    流程严格分两步：
      ① 先用规则枚举结构字段组合（订单状态 × 用户诉求），期望动作由
         订单状态查表推导——结构在这一刻已完全确定；
      ② 再把结构字段 JSON 交给 MockLLM 渲染自然语言输入。
    这样每条扩展用例的场景/期望行为/风险等级在结构上继承种子，可断言。"""
    seed_status = seed.structured_fields["order_status"]
    other_statuses = [s for s in ORDER_STATUS_KEYS if s != seed_status]
    appeals = itertools.cycle(USER_APPEAL_KEYS)
    combos = [(other_statuses[i % len(other_statuses)], next(appeals))
              for i in range(count)]

    expanded: List[GoldenCase] = []
    for i, (status_key, appeal_key) in enumerate(combos):
        order_id = f"SO-2026010{i + 1}"
        spec = {"scenario": seed.scenario, "order_status": status_key,
                "user_appeal": appeal_key, "order_id": order_id}
        text = llm.simple(json.dumps(spec, ensure_ascii=False))
        expanded.append(GoldenCase(
            case_id=f"{seed.case_id}-X{i + 1}",
            source=CaseSource.LLM_EXPANSION,
            scenario=seed.scenario,                 # 结构继承：场景不变
            user_input=text,
            structured_fields=dict(spec),
            expected_behavior={"expected_action":
                               MockLLM.EXPECTED_ACTION_BY_ORDER_STATUS[status_key]},
            risk_level=seed.risk_level,             # 结构继承：风险等级不变
            status=CaseStatus.CAPABILITY,           # 扩展用例先进能力集
            difficulty=round(seed.difficulty + 0.15, 2),  # 变体略难于种子
            derived_from=seed.case_id,              # 可追溯：来自哪条种子
        ))
    return expanded


# ---------------------------------------------------------------------------
# 6. 四类来源之三：线上真实数据（幸存者偏差演示）
# ---------------------------------------------------------------------------
# 线上样本中正常流程占绝大多数，高风险边缘场景占比极低。纯随机抽样时，
# 高风险样本经常"抽不中"——报告看起来不错，关键问题恰好漏掉。
# 对策：按风险分层采样，保证高风险样本的最低配额。


def build_online_pool() -> List[dict]:
    """模拟线上会话池：36 条普通会话 + 4 条高风险会话（约 10%）。"""
    pool = []
    normal_scenarios = ("物流", "改订单", "开发票")
    for i in range(36):
        pool.append({"session_id": f"S-N{i + 1:03d}", "risk": "P2",
                     "scenario": normal_scenarios[i % 3],
                     "content": f"普通咨询会话 #{i + 1}"})
    for i in range(4):
        pool.append({"session_id": f"S-H{i + 1:03d}", "risk": "P0",
                     "scenario": "物流",
                     "content": f"高风险会话 #{i + 1}: 物流长时间停滞且用户扬言投诉"})
    return pool


def naive_sample(pool: List[dict], rng: random.Random, n: int = 20) -> List[dict]:
    """朴素随机抽样——幸存者偏差的来源。"""
    return rng.sample(pool, n)


HIGH_RISK_QUOTA = 4


def stratified_sample(pool: List[dict], rng: random.Random,
                      n: int = 20) -> List[dict]:
    """分层抽样：高风险样本保底全量入选（配额制），其余名额补给普通样本。"""
    high = [s for s in pool if s["risk"] == "P0"]
    normal = [s for s in pool if s["risk"] != "P0"]
    take_high = high[:HIGH_RISK_QUOTA]
    return take_high + rng.sample(normal, n - len(take_high))


# ---------------------------------------------------------------------------
# 7. 黄金数据集治理：入库 / 结果记录 / 毕业流转 / 回归集只增不减
# ---------------------------------------------------------------------------

class GoldenDataset:
    """数据集治理器。它维护三本账：
    - cases:                全量用例登记表（id 唯一）；
    - _regression_order:    回归集名单（只增不减，append-only）；
    - _signatures:          已入库用例的同簇签名（去重依据）。
    毕业是两阶段流转：review_graduation 负责"评审"（能力集 → 已毕业），
    admit_graduated 负责"入库"（已毕业 → 回归集）——两个动作都可审计。"""

    def __init__(self, graduation_threshold: int = 3):
        self.M = graduation_threshold          # 连续 M 个版本 100% 通过才能毕业
        self.cases: Dict[str, GoldenCase] = {}
        self._regression_order: List[str] = []
        self._signatures: Set[str] = set()
        self.regression_size_history: List[int] = []
        self.rejections: List[Tuple[str, List[str]]] = []   # 拒绝审计日志

    # ---- 入库 --------------------------------------------------------------
    def add_case(self, case: GoldenCase) -> None:
        """直接登记（专家用例/基线快照用例/已通过检查的候选）。"""
        assert case.case_id not in self.cases, f"用例 id 重复: {case.case_id}"
        self.cases[case.case_id] = case
        self._signatures.add(case_signature(
            case.scenario, case.expected_behavior.get("expected_action", ""),
            case.structured_fields.get("user_appeal", "")))
        if case.status == CaseStatus.REGRESSION:
            self._regression_order.append(case.case_id)

    def intake(self, cand: IntakeCandidate, checker: IntakeChecker,
               version: int) -> Tuple[Optional[GoldenCase], bool, List[str]]:
        """候选用例走入库检查；未达标则拒绝并留审计记录。"""
        ok, unmet = checker.check(cand, self._signatures)
        if not ok:
            self.rejections.append((cand.candidate_id, list(unmet)))
            return None, False, unmet
        case = GoldenCase(
            case_id=cand.candidate_id, source=cand.source, scenario=cand.scenario,
            user_input=cand.user_input, structured_fields=dict(cand.structured_fields),
            expected_behavior=dict(cand.expected_behavior), risk_level=cand.risk_level,
            status=CaseStatus.CAPABILITY,        # 新用例一律先进能力集
            difficulty=cand.difficulty, created_version=version)
        self.add_case(case)
        return case, True, []

    # ---- 视图 --------------------------------------------------------------
    def capability_cases(self) -> List[GoldenCase]:
        return [c for c in self.cases.values() if c.status == CaseStatus.CAPABILITY]

    def regression_cases(self) -> List[GoldenCase]:
        return [self.cases[cid] for cid in self._regression_order]

    # ---- 评测结果记录 --------------------------------------------------------
    def record_result(self, case: GoldenCase, version: int, passed: bool) -> None:
        case.history.append((version, passed))
        # 连续通过计数：一次失败即清零——"稳定 100%"不是"累计多数通过"
        case.consecutive_full_pass = case.consecutive_full_pass + 1 if passed else 0

    # ---- 毕业机制（两阶段） ---------------------------------------------------
    def review_graduation(self, version: int) -> List[GoldenCase]:
        """毕业评审：能力集用例连续 M 个版本 100% 通过 → 标记为已毕业。"""
        grads = [c for c in self.cases.values()
                 if c.status == CaseStatus.CAPABILITY
                 and c.consecutive_full_pass >= self.M]
        for c in grads:
            c.status = CaseStatus.GRADUATED
            c.graduated_version = version
        return grads

    def admit_graduated(self) -> List[GoldenCase]:
        """毕业入库：已毕业用例升入回归集。回归集只增不减。"""
        admitted = [c for c in self.cases.values()
                    if c.status == CaseStatus.GRADUATED]
        for c in admitted:
            c.status = CaseStatus.REGRESSION
            self._regression_order.append(c.case_id)
        return admitted

    # ---- 不变量 --------------------------------------------------------------
    def invariants(self) -> None:
        """数据集结构自检——任何时候都应成立，故放在类内随时可调用。"""
        assert len(set(self.cases)) == len(self.cases), "用例 id 必须唯一"
        reg_by_status = {c.case_id for c in self.cases.values()
                         if c.status == CaseStatus.REGRESSION}
        assert set(self._regression_order) == reg_by_status, \
            "回归集名单必须与 REGRESSION 状态用例完全一致"
        assert len(self._regression_order) == len(reg_by_status), "回归集不允许重复"


# ---------------------------------------------------------------------------
# 8. 版本模拟：被测系统质量、回归门禁与一次完整版本运行
# ---------------------------------------------------------------------------
# 真实系统里 simulate_case = 运行被测 agent + 三层评分（程序化/Judge/人工，
# 见 eval_lab03/04/05）；这里压缩成"版本质量 ≥ 用例难度"的阈值判定，
# 完全确定性，好让读者聚焦"数据集治理"本身。

VERSION_QUALITY: Dict[int, float] = {1: 0.40, 2: 0.55, 3: 0.70, 4: 0.85, 5: 0.95}
# v4 的变更在"退款"场景引入了回归（质量骤降）——这正是回归集要抓的事故
SCENARIO_REGRESSION_EVENT: Dict[int, str] = {4: "退款"}
QUALITY_PENALTY = 0.50


def simulate_case(case: GoldenCase, version: int) -> bool:
    q = VERSION_QUALITY[version]
    if SCENARIO_REGRESSION_EVENT.get(version) == case.scenario:
        q -= QUALITY_PENALTY
    return q + 1e-9 >= case.difficulty


@dataclass
class VersionReport:
    version: int
    gate_ok: bool                    # 回归门禁是否通过
    gate_failures: List[str]        # 门禁失败的回归用例
    capability_total: int
    capability_passed: int
    reviewed: List[str]             # 本轮毕业评审通过的用例
    admitted: List[str]             # 本轮升入回归集的用例


def run_version(ds: GoldenDataset, version: int) -> VersionReport:
    """运行一个版本：先跑回归门禁，再跑能力评测，最后（且仅在门禁通过时）
    做毕业流转。门禁失败时暂停毕业——版本都被拒了，谈何"能力已稳定"。"""
    # ① 回归门禁：回归集全量必跑，任何一条失败即拦截版本
    gate_failures: List[str] = []
    for case in ds.regression_cases():
        passed = simulate_case(case, version)
        ds.record_result(case, version, passed)
        if not passed:
            gate_failures.append(case.case_id)
    gate_ok = not gate_failures

    # ② 能力评测：容忍失败，失败是迭代的燃料
    cap = ds.capability_cases()
    cap_passed = 0
    for case in cap:
        passed = simulate_case(case, version)
        ds.record_result(case, version, passed)
        cap_passed += 1 if passed else 0

    # ③ 毕业流转（评审 + 入库）：仅在门禁通过时执行
    reviewed: List[GoldenCase] = []
    admitted: List[GoldenCase] = []
    if gate_ok:
        reviewed = ds.review_graduation(version)
        admitted = ds.admit_graduated()

    ds.regression_size_history.append(len(ds._regression_order))
    return VersionReport(
        version=version, gate_ok=gate_ok, gate_failures=gate_failures,
        capability_total=len(cap), capability_passed=cap_passed,
        reviewed=[c.case_id for c in reviewed],
        admitted=[c.case_id for c in admitted])


# ---------------------------------------------------------------------------
# 9. 四类来源之四：badcase 回流（门禁失败 → 编码为新用例）
# ---------------------------------------------------------------------------

def build_backflow_candidate(ds: GoldenDataset, failed_case: GoldenCase,
                             version: int) -> IntakeCandidate:
    """把一次门禁失败编码为入库候选。
    注意：第一次提交保留了线上 trace 的原始用户输入（含手机号）——
    这是刻意安排的"未脱敏"反面教材，将被入库检查器拒收。"""
    order_id = failed_case.structured_fields.get("order_id", "SO-20260001")
    raw_input = (f"订单 {order_id} 退款一直没到，客服 agent 直接承诺我退款一定会成功，"
                 f"结果三天了还没到账。用户联系电话 13812345678")
    return IntakeCandidate(
        candidate_id=f"B1-v{version}-退款过度承诺",
        source=CaseSource.BADCASE_BACKFLOW,
        scenario="退款",
        user_input=raw_input,
        structured_fields={"order_status": "已退货未退款", "user_appeal": "愤怒",
                           "order_id": order_id},
        expected_behavior={"expected_action": "先核实订单状态，禁止承诺退款结果"},
        risk_level=RiskLevel.P0,
        difficulty=0.45,
        trace_id=f"trace-v{version}-{failed_case.case_id}",
        root_cause_label="风险拦截",
        occurrence_count=3,
        cluster_id="cluster-过度承诺",
        desensitized=False)          # 尚未脱敏 → 将被拒收


def mask_phone(text: str) -> str:
    """最小脱敏：手机号中间四位打码。"""
    return re.sub(r"(1[3-9]\d)\d{4}(\d{4})", r"\1****\2", text)


# ---------------------------------------------------------------------------
# 10. 自检：断言必须有牙齿——断言的是核心结论，不是"跑完了"
# ---------------------------------------------------------------------------

def run_self_checks(ctx: dict) -> None:
    ds: GoldenDataset = ctx["ds"]
    seed: GoldenCase = ctx["seed"]
    expanded: List[GoldenCase] = ctx["expanded"]
    reports: Dict[int, VersionReport] = ctx["reports"]

    # (a) LLM 扩展用例在结构上完整保留种子用例的字段与约束
    for c in expanded:
        assert c.scenario == seed.scenario, "扩展用例必须保留种子的场景"
        assert c.source == CaseSource.LLM_EXPANSION
        assert c.derived_from == seed.case_id, "扩展用例必须可追溯到种子"
        assert set(seed.structured_fields) <= set(c.structured_fields), \
            "扩展用例必须保留全部结构字段 key"
        assert c.expected_behavior.get("expected_action") in \
            set(MockLLM.EXPECTED_ACTION_BY_ORDER_STATUS.values()), \
            "期望动作必须由结构字段查表推导"
        assert c.risk_level == seed.risk_level, "风险等级应随种子继承"
        # 自然语言确实由结构字段渲染而来：订单号与状态描述都出现在文本里
        assert c.structured_fields["order_id"] in c.user_input
        assert MockLLM.ORDER_STATUS_DESC[c.structured_fields["order_status"]] \
            in c.user_input

    # (b) MockLLM 拒绝自由发挥 + 确定性可复现（同种子同调用 → 同输出）
    llm = ctx["llm"]
    assert llm("帮我随便编一个退款用例").startswith(MockLLM.REFUSE_PREFIX), \
        "无结构字段的请求必须被拒绝"
    assert llm(json.dumps({"scenario": "退款"})).startswith(MockLLM.REFUSE_PREFIX)
    spec0 = json.dumps({"scenario": "退款", "order_status": "未收到货",
                        "user_appeal": "焦急", "order_id": "SO-20260999"},
                       ensure_ascii=False)
    a, b = MockLLM(seed=11).simple(spec0), MockLLM(seed=11).simple(spec0)
    assert a == b and not a.startswith(MockLLM.REFUSE_PREFIX), "生成必须确定可复现"

    # (c) 幸存者偏差：分层采样的高风险覆盖严格优于朴素随机采样
    assert ctx["stratified_high"] == HIGH_RISK_QUOTA, "分层采样必须保满高风险配额"
    assert ctx["naive_high"] < ctx["stratified_high"], \
        "朴素随机采样的高风险覆盖应低于分层采样（本种子下复现偏差）"

    # (d) 入库标准检查器有牙齿：缺项拒收，且拒收理由准确
    ok1, unmet1 = ctx["online_reject"]
    assert ok1 is False and "根因标签" in unmet1, "缺根因标签的线上样本必须被拒"
    ok2, unmet2 = ctx["backflow_reject"]
    assert ok2 is False and "已脱敏" in unmet2, "含手机号的 badcase 必须被拒收"
    assert ctx["backflow_accept"] is True, "脱敏修复后的 badcase 应当入库"
    ok3, unmet3 = ctx["duplicate_reject"]
    assert ok3 is False and "代表性" in unmet3, "同簇重复提交必须被去重拦截"

    # (e) 毕业流转正确：E1 连续 v1~v3 全过 → v3 毕业升入回归集
    e1 = ds.cases["E1-退款进度"]
    h1 = dict(e1.history)
    assert h1[1] and h1[2] and h1[3] and not h1[4] and h1[5], \
        "E1 应在 v1~v3 全过、v4 回归事故中失败、v5 恢复"
    assert e1.status == CaseStatus.REGRESSION and e1.graduated_version == 3
    assert e1.case_id in ds._regression_order, "毕业用例必须进入回归集名单"
    assert e1.case_id not in [c.case_id for c in ds.capability_cases()], \
        "毕业用例必须离开能力集"

    # (f) 门禁失败会暂停毕业评审：E2 在 v4 已连过 2 版但不得提前毕业
    e2 = ds.cases["E2-改订单地址"]
    assert reports[4].gate_ok is False and reports[4].reviewed == [], \
        "v4 门禁失败，该版本不得进行毕业评审"
    assert e2.status == CaseStatus.REGRESSION and e2.graduated_version == 5, \
        "E2 应在 v5（连过 v3/v4/v5 三版）才毕业"

    # (g) 未达标用例不得毕业：E3 仅在 v5 通过 1 版，仍留在能力集
    assert ds.cases["E3-投诉升级"].status == CaseStatus.CAPABILITY
    for x in ("E1-退款进度-X1", "E1-退款进度-X2", "E1-退款进度-X3"):
        assert ds.cases[x].status == CaseStatus.CAPABILITY, \
            "扩展用例在 v4 被打断连续通过，不应毕业"
        assert dict(ds.cases[x].history)[4] is False

    # (h) 回归集只增不减：规模单调不减，且失败用例不被移出
    sizes = ds.regression_size_history
    assert sizes == [1, 1, 2, 2, 4], f"回归集规模轨迹应为 [1,1,2,2,4]，实际 {sizes}"
    assert all(y >= x for x, y in zip(sizes, sizes[1:])), "回归集规模必须单调不减"
    assert "E1-退款进度" in [c.case_id for c in ds.regression_cases()], \
        "v4 失败的回归用例必须留在回归集（只增不减）"

    # (i) 回归门禁判定正确：v4 被拦截，失败的恰是退款场景用例
    gates = {v: r.gate_ok for v, r in reports.items()}
    assert gates == {1: True, 2: True, 3: True, 4: False, 5: True}
    assert reports[4].gate_failures == ["E1-退款进度"]

    # (j) badcase 回流闭环：新用例入库、脱敏生效、下一版本参评且通过
    b1 = ds.cases["B1-v4-退款过度承诺"]
    assert b1.source == CaseSource.BADCASE_BACKFLOW
    assert b1.status == CaseStatus.CAPABILITY and b1.created_version == 4
    assert dict(b1.history).get(5) is True, "回流用例应在 v5 参评且通过"
    assert "13812345678" not in b1.user_input and "138****5678" in b1.user_input, \
        "入库用例必须已脱敏"

    # (k) 收尾不变量：无滞留中间态、名单一致、规模正确
    assert not [c for c in ds.cases.values() if c.status == CaseStatus.GRADUATED], \
        "已毕业是过渡态，收尾时不得有滞留"
    ds.invariants()
    assert len(ds.cases) == 9, "数据集最终应有 9 条用例"
    assert sum(1 for c in ds.cases.values()
               if c.status == CaseStatus.REGRESSION) == 4


# ---------------------------------------------------------------------------
# 11. 演示入口：把四类来源与治理流水线串起来
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 68)
    print("EVAL LAB 02 · 黄金数据集构建与治理流水线（纯标准库 / 确定性）")
    print("=" * 68)

    checker = IntakeChecker()
    ds = GoldenDataset(graduation_threshold=3)

    # ---- [1/6] 来源①：专家手写用例 + 基线快照回归用例 ----
    print("\n[1/6] 来源① 专家手写：定标准的锚点用例")
    expert_cases, r0 = make_expert_cases()
    for c in expert_cases:
        ds.add_case(c)
        print(f"   + {c.case_id:<10} 场景={c.scenario} 风险={c.risk_level.value} "
              f"→ {c.status.value}")
    ds.add_case(r0)
    print(f"   + {r0.case_id:<10} 基线快照用例：先跑一次→人工确认→快照为基线，"
          f"直接入回归集")

    # ---- [2/6] 来源②：LLM 扩展（先结构字段，后自然语言） ----
    print("\n[2/6] 来源② LLM 扩展：先定结构字段，再生成自然语言")
    llm = MockLLM(seed=11)
    seed = expert_cases[0]                     # 以 E1 为种子扩展退款场景
    expanded = expand_cases(seed, llm, count=3)
    for c in expanded:
        ds.add_case(c)
        print(f"   + {c.case_id:<13} 结构字段={c.structured_fields['order_status']}"
              f"/{c.structured_fields['user_appeal']}")
        print(f"       生成输入: {c.user_input}")
        print(f"       期望动作: {c.expected_behavior['expected_action']}")
    refuse = llm("帮我随便编一个退款用例")
    print(f"   ! 无结构字段的自由请求被拒绝: {refuse}")
    print(f"   （MockLLM 共调用 {llm.calls} 次，含 1 次被拒请求）")

    # ---- [3/6] 来源③：线上真实数据（幸存者偏差 + 分层采样） ----
    print("\n[3/6] 来源③ 线上真实数据：幸存者偏差与分层采样")
    pool = build_online_pool()
    rng_naive, rng_strat = random.Random(20260805), random.Random(7)
    naive = naive_sample(pool, rng_naive, n=20)
    stratified = stratified_sample(pool, rng_strat, n=20)
    naive_high = sum(1 for s in naive if s["risk"] == "P0")
    strat_high = sum(1 for s in stratified if s["risk"] == "P0")
    print(f"   线上会话池: {len(pool)} 条（其中高风险 {HIGH_RISK_QUOTA} 条）")
    print(f"   朴素随机抽 20 条 → 高风险仅 {naive_high} 条（关键问题差点漏掉）")
    print(f"   分层采样抽 20 条 → 高风险 {strat_high} 条（配额保底）")

    # 分层样本中的高风险会话 → 补齐字段后入库
    hi_session = next(s for s in stratified if s["risk"] == "P0")
    o1_cand = IntakeCandidate(
        candidate_id="O1-物流停滞", source=CaseSource.ONLINE, scenario="物流",
        user_input=f"物流卡在中转站五天不动了，订单 {hi_session['session_id']}，"
                   f"到底什么时候能到？再不到我就投诉了。",
        structured_fields={"order_status": "物流停滞", "user_appeal": "焦急",
                           "order_id": hi_session["session_id"]},
        expected_behavior={"expected_action": "核实物流停滞节点并给出预计送达时间"},
        risk_level=RiskLevel.P0, difficulty=0.65,
        trace_id=hi_session["session_id"], root_cause_label="物流查询",
        occurrence_count=5, cluster_id="cluster-物流停滞", desensitized=True)
    o1, ok, _ = ds.intake(o1_cand, checker, version=0)
    print(f"   + {o1.case_id:<10} 分层样本入库 → {o1.status.value}（高风险会话最值钱）")

    # 朴素样本中的普通会话 → 缺根因标签，被入库检查器拒收
    low_session = next(s for s in naive if s["risk"] != "P0")
    bad_cand = IntakeCandidate(
        candidate_id="N1-普通咨询", source=CaseSource.ONLINE, scenario="物流",
        user_input=low_session["content"],
        structured_fields={"order_status": "正常咨询", "user_appeal": "平和",
                           "order_id": low_session["session_id"]},
        expected_behavior={"expected_action": "正常答复物流进度"},
        risk_level=RiskLevel.P2, difficulty=0.30,
        trace_id=low_session["session_id"], root_cause_label="",  # ← 缺根因标签
        occurrence_count=1, desensitized=True)
    _, ok_reject, unmet = ds.intake(bad_cand, checker, version=0)
    print(f"   - N1-普通咨询 被拒收：未满足标准 {unmet}")

    # ---- [4/6] 版本循环 v1~v3：能力爬坡与第一次毕业 ----
    print("\n[4/6] 版本 v1~v3：能力爬坡 + 毕业机制首次触发（M=3）")
    reports: Dict[int, VersionReport] = {}
    for v in (1, 2, 3):
        rep = run_version(ds, v)
        reports[v] = rep
        print(f"   v{v}: 门禁={'通过' if rep.gate_ok else '拦截'}  "
              f"能力集 {rep.capability_passed}/{rep.capability_total}")
        if rep.admitted:
            print(f"        毕业升入回归集: {rep.admitted}")

    # ---- [5/6] v4 回归事故：门禁拦截 + 来源④ badcase 回流 ----
    print("\n[5/6] 版本 v4：退款场景回归事故 → 门禁拦截 → badcase 回流")
    rep4 = run_version(ds, 4)
    reports[4] = rep4
    print(f"   v4: 门禁={'通过' if rep4.gate_ok else '拦截'}！"
          f"失败回归用例: {rep4.gate_failures}")
    print(f"        能力集 {rep4.capability_passed}/{rep4.capability_total}"
          f"（毕业评审因门禁失败而暂停）")
    failed_case = ds.cases[rep4.gate_failures[0]]
    cand = build_backflow_candidate(ds, failed_case, version=4)
    _, ok_bf, unmet_bf = ds.intake(cand, checker, version=4)
    print(f"   回流首次提交被拒: 未满足 {unmet_bf}（trace 原文还带着用户手机号）")
    cand_fixed = replace(cand, user_input=mask_phone(cand.user_input),
                         desensitized=True)
    b1, ok_bf2, _ = ds.intake(cand_fixed, checker, version=4)
    print(f"   脱敏后重新提交: {'入库成功' if ok_bf2 else '仍被拒'} → "
          f"{b1.case_id} 进入能力集")
    _, ok_dup, unmet_dup = ds.intake(cand_fixed, checker, version=4)
    print(f"   同一条再次提交被拒: 未满足 {unmet_dup}（同簇去重生效）")

    # ---- [6/6] v5 恢复 + 最终治理报告 ----
    print("\n[6/6] 版本 v5：修复生效 + 最终治理报告")
    rep5 = run_version(ds, 5)
    reports[5] = rep5
    print(f"   v5: 门禁={'通过' if rep5.gate_ok else '拦截'}  "
          f"能力集 {rep5.capability_passed}/{rep5.capability_total}")
    if rep5.admitted:
        print(f"        毕业升入回归集: {rep5.admitted}")

    print("\n" + "-" * 68)
    print("最终数据集状态")
    print("-" * 68)
    for c in sorted(ds.cases.values(), key=lambda x: x.case_id):
        grad = f"（v{c.graduated_version} 毕业）" if c.graduated_version else ""
        print(f"   {c.case_id:<16} {c.source.value:<10} {c.status.value} "
              f"风险={c.risk_level.value} 连过={c.consecutive_full_pass} {grad}")
    print(f"\n   回归集（只增不减）: {[cid for cid in ds._regression_order]}")
    print(f"   回归集规模轨迹 v1→v5: {ds.regression_size_history}")
    print(f"   入库拒绝审计: {[(cid, unmet) for cid, unmet in ds.rejections]}")
    ds.invariants()
    print("   数据集结构不变量检查: 通过")

    # ---- 自检 ----
    print("\n[自检] 运行核心断言（结构保留/入库拒收/毕业流转/只增不减/门禁拦截）...")
    ctx = {
        "ds": ds, "llm": llm, "seed": seed, "expanded": expanded,
        "reports": reports,
        "naive_high": naive_high, "stratified_high": strat_high,
        "online_reject": (ok_reject, unmet),
        "backflow_reject": (ok_bf, unmet_bf), "backflow_accept": ok_bf2,
        "duplicate_reject": (ok_dup, unmet_dup),
    }
    run_self_checks(ctx)
    print(f"   扩展用例结构保留 3/3 ✔   入库拒收 {len(ds.rejections)} 次全部理由正确 ✔")
    print(f"   回归集规模轨迹 {ds.regression_size_history}（单调不减）✔   "
          f"门禁 v4 拦截 ✔")
    print("\n✅ 自检通过：eval_lab02_golden_dataset.py 全部断言成立")


if __name__ == "__main__":
    main()
