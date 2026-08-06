#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab07_simulator_fixtures.py — 会话模拟器与 Fixtures
=========================================================

【实验目的】
    多轮对话 agent 无法用"一问一答"的静态数据集评估：用户会动态追问、补充信息、
    甚至投诉。本实验搭建「Conversation Simulator + Fixtures」评测基础设施
    （DoorDash 等公司的工业实践），回答三个问题：
        1) 如何让 MockLLM 扮演"会动态反应的用户"，把多轮会话自动跑完？
        2) 如何用 Fixtures 拦截工具调用、冻结外部状态，让任何运行看到同样的世界？
        3) 环境不受控时分数会怎样？——用漂移的伪实时数据做对照，亲眼看方差膨胀。
    另实现 checklist 式 rubric（目标商品在清单/总价≤预算/无编造商品），验证它能
    抓住超预算与编造商品两类失败——即使"用户"在对话里表示满意。

【对应章节】
    E08 对话 Agent 与仿真评测（Conversation Simulator / Fixtures / checklist rubric）

【核心概念】
    - Scenario（场景）: 开场请求 + 用户目标 + 反应策略；模拟器一切行为由场景配置
      驱动，换场景不改代码。
    - 会话模拟器（用户侧 MockLLM）: 状态机模拟真人耐心——未解决但有进展→继续配合；
      被反问→补充信息；连续 2 次无进展→升级投诉（"给过机会才投诉"）。
    - Fixtures（夹具）: 把工具返回录制成固定 payload（如订单历史 v1），运行时拦截
      调用、原样回放。外部状态冻结 → 分数差异只能来自被测 agent → 低方差信号。
    - 环境漂移对照组: 不拦截工具，返回"伪实时"漂移数据；同一 agent、同样采样随机
      性，分数方差显著变大——未受控环境里分数测的是环境噪声。
    - checklist 式 rubric: 把"会话成功"操作化为几张可判定检查项，非真即假、附
      证据、不依赖主观判断，因此评分稳定、可审计。

【如何运行】
    cd evals-special/labs && python3 eval_lab07_simulator_fixtures.py
    （纯标准库，零依赖，固定随机种子，任何机器上输出完全一致）

【思考题（面试延伸）】
    1. "判断是否有进展"这里用关键词检查点，还能怎么做（LLM judge 逐步判断/槽位填充率/目标状态机）？各有何风险？
    2. Fixtures 冻结环境也让评测"脱离真实"：仿真保真度与可复现性如何权衡？何时必须上真实回放（replay）/影子流量（shadow）？
    3. 门禁里某版本分数下跌 2%，如何区分"真变差"与"环境噪声"？（提示：固定 fixture 复跑、多 trial 取均值、置信区间——见 eval_lab08_statistics_ci.py）
    4. 编造商品的 agent 为什么能让"用户"满意收尾？这对"以用户满意度为唯一指标"的评测方案提出了什么挑战？
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

# --- 0. 全局常量：种子与规模 ---
# 固定种子是本实验的根基：所有"随机"都从 SEED 派生，保证任何机器、任何时刻输出逐字节一致，assert 才是有意义的验收标准。

SEED = 20260805          # 全局基础种子
N_RUNS = 8               # 每个实验组的重复运行次数（对应 "50 场景 x 8 trials" 的 trials）
MAX_TURNS = 6            # 单场会话最多 agent 轮数（防死循环）

# --- 1. Scenario：场景 = 开场请求 + 用户目标 + 反应策略所需的全部配置 ---
# 为什么把场景做成数据而不是代码：sweeps 要跑几十上百个场景，场景必须可序列化、可版本管理、可由非工程师编写。

@dataclass
class Scenario:
    scenario_id: str
    opening: str                       # 用户开场请求（模拟器的第一句话）
    goal_keyword: str                  # 用户目标商品关键词（如 "蓝山"）
    expected_product: str              # 用户最终想买到的具体商品（checklist 用）
    budget: int                        # 用户预算（checklist 的硬约束）
    user_facts: Dict[str, str] = field(default_factory=dict)
    # 用户"心里知道但开场没全说"的信息（键=类别，值=回答原话）；被反问时按插入顺序逐条补充——"挤牙膏式"的真实用户。

def build_scenarios() -> Dict[str, Scenario]:
    """两个场景：主场景开场就带预算（跑 N 次实验用）；
    补充信息场景开场不带预算（演示"被反问 → 补充信息"分支用）。"""
    return {
        "buy-coffee": Scenario(
            scenario_id="buy-coffee",
            opening="我想买一箱蓝山咖啡，预算 100 元，帮我挑一下。",
            goal_keyword="蓝山",
            expected_product="蓝山咖啡 500g",
            budget=100,
            user_facts={"预算": "我的预算是 100 元。"},
        ),
        "buy-coffee-no-budget": Scenario(
            scenario_id="buy-coffee-no-budget",
            opening="我想买点蓝山咖啡，帮我挑一款。",
            goal_keyword="蓝山",
            expected_product="蓝山咖啡 500g",
            budget=100,
            user_facts={"预算": "我的预算是 100 元。"},
        ),
    }

# --- 2. Transcript：一场会话的完整产物 ---
# 评测的输入不是"最后一条回复"，而是整场会话的 transcript：消息序列 + 工具调用记录。
# 指纹用 sha256 计算，用来断言"产物可复现"——指纹相同即逐字节相同。

@dataclass
class Transcript:
    scenario_id: str
    messages: List[dict] = field(default_factory=list)      # {"role","content"}
    tool_calls: List[dict] = field(default_factory=list)    # {"tool","params","result"}
    state: str = "timeout"                                  # resolved/escalated/timeout
    claims: List[Tuple[str, float]] = field(default_factory=list)  # agent 报过的(商品,价格)
    final_paid: Optional[float] = None                      # agent 声称的实付金额

    # ---- 两个指纹：一个管"说了什么"，一个管"看到了什么外部世界" ----
    def fingerprint(self) -> str:
        blob = json.dumps(self.messages, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def tool_fingerprint(self) -> str:
        blob = json.dumps(self.tool_calls, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

# agent 报价的固定句式：「商品名」，价格 N 元。真实项目里抽取靠正则/NER/LLM，这里约束句式是为了让抽取透明可审计。
_OFFER_RE = re.compile(r"「([^」]+)」，价格\s*(\d+(?:\.\d+)?)\s*元")
_PAID_RE = re.compile(r"实付\s*(\d+(?:\.\d+)?)\s*元")

def extract_claims(transcript: Transcript) -> None:
    """从 agent 消息里抽取报价与实付金额，回填到 transcript。"""
    for m in transcript.messages:
        if m["role"] != "assistant":
            continue
        for name, price in _OFFER_RE.findall(m["content"]):
            transcript.claims.append((name, float(price)))
        paid = _PAID_RE.findall(m["content"])
        if paid:
            transcript.final_paid = float(paid[-1])

# --- 3. 工具环境：Fixtures（冻结） vs Drifting（漂移对照） ---
# 被测 agent 依赖三个工具。Fixtures 的思路：把"真实接口在某时刻的返回"录制成 v1 载荷，评测时拦截调用、
# 原样回放——目录、库存、订单历史都不变，任何一次运行看到的外部世界完全相同。

CATALOG_V1: List[dict] = [
    {"name": "蓝山咖啡 500g", "price": 95, "stock": 12},
    {"name": "意式拼配咖啡 500g", "price": 78, "stock": 30},
    {"name": "精品挂耳咖啡 20盒", "price": 129, "stock": 8},
]
ORDER_HISTORY_V1: dict = {
    "user_id": "u-2026",
    "orders": [
        {"name": "意式拼配咖啡 500g", "date": "2026-07-12"},
        {"name": "蓝山咖啡 500g", "date": "2026-05-02"},
    ],
}
PLACE_ORDER_V1: dict = {"order_id": "ORD-V1-0001", "status": "ok", "paid_price": 95}

FIXTURES_V1: Dict[str, object] = {
    "search_products": {"products": CATALOG_V1},
    "get_order_history": ORDER_HISTORY_V1,
    "place_order": PLACE_ORDER_V1,
}

def _payload_fingerprint(payloads: Dict[str, object]) -> str:
    blob = json.dumps(payloads, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()

FIXTURES_V1_FINGERPRINT = _payload_fingerprint(FIXTURES_V1)

class FixtureBackend:
    """录制回放式工具环境：调用被拦截，返回录制好的 v1 载荷。
    两个工程细节：1) execute 时 deepcopy——agent 若修改返回的 dict，绝不能污染录制
    数据，否则"冻结"名存实亡；2) 每次运行新建实例（call log 属于本次运行），但
    共享同一份 FIXTURES_V1——这正是"任何运行都看到同样外部状态"的含义。
    """

    def __init__(self, fixtures: Dict[str, object]):
        self.fixtures = fixtures
        self.calls: List[dict] = []

    def execute(self, tool: str, params: dict) -> dict:
        if tool not in self.fixtures:
            raise KeyError(f"未录制的工具: {tool}")
        result = copy.deepcopy(self.fixtures[tool])
        self.calls.append({"tool": tool, "params": copy.deepcopy(params),
                           "result": result})
        return result

class DriftingBackend:
    """对照组：伪实时接口。每个 run_seed 对应一个不同的"市场快照"——
    商品名不变（因此模拟器的行为不受干扰），但价格/库存/订单历史随行情漂移。
    这就是未冻结环境的典型形态：接口没坏，只是"每次去世界都不一样"。"""

    def __init__(self, run_seed: int):
        rng = random.Random(run_seed)
        self.catalog: List[dict] = []
        for p in CATALOG_V1:
            # 漂移幅度 -6% ~ +18%：95 元的蓝山可能涨到 ~112 元，恰好跨越 100 元预算线——漂移"打"的正是预算项。
            factor = 1.0 + rng.uniform(-0.06, 0.18)
            self.catalog.append({
                "name": p["name"],
                "price": max(1, round(p["price"] * factor)),
                "stock": max(0, p["stock"] + rng.randint(-3, 3)),
            })
        n_keep = rng.randint(1, len(ORDER_HISTORY_V1["orders"]))
        self.history = {
            "user_id": ORDER_HISTORY_V1["user_id"],
            "orders": ORDER_HISTORY_V1["orders"][:n_keep],
        }
        self.calls: List[dict] = []

    def execute(self, tool: str, params: dict) -> dict:
        if tool == "search_products":
            result = {"products": copy.deepcopy(self.catalog)}
        elif tool == "get_order_history":
            result = copy.deepcopy(self.history)
        elif tool == "place_order":
            # 真实下单接口以"当前价"成交，忽略调用方传来的旧报价。订单号用 sha256 派生而非内置 hash()——
            # 后者受 PYTHONHASHSEED 影响、跨进程变化，是评测代码里最常见的隐蔽非确定性来源。
            cur = {p["name"]: p["price"] for p in self.catalog}
            name = params.get("name", "")
            digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
            result = {"order_id": f"ORD-DRIFT-{int(digest[:4], 16) % 10000:04d}",
                      "status": "ok", "paid_price": cur.get(name, -1)}
        else:
            raise KeyError(f"未知工具: {tool}")
        self.calls.append({"tool": tool, "params": copy.deepcopy(params),
                           "result": result})
        return result

# --- 4. 用户模拟器：MockLLM 扮演顾客（状态机驱动） ---
# 模拟器是"用户侧的 LLM"：对外接口与真实 LLM 客户端同构（chat(messages)），可随时整体换成真实模型；
# 内部用确定性状态机实现，保证可复现。三条反应策略（对应真人行为）：
#   S1 未解决但有进展 → 继续配合（确认选择、等待推进）
#   S2 被反问且自己掌握信息 → 补充信息（挤牙膏，但会配合）
#   S3 连续 2 次无进展 → 升级投诉（给过机会才投诉，像真人）
# "进展"的操作化定义 = 检查点（checkpoint）被点亮；真实项目可让 LLM judge 逐轮判断，这里用关键词
# 规则，胜在透明、可调试、零成本。

@dataclass
class Checkpoint:
    key: str
    desc: str
    test: Callable[[str], bool]      # 输入: agent 本轮回复文本

class UserSimulator:
    """确定性用户模拟器。chat() 与 QwenLLM.chat 同构：输入 messages 列表，
    输出一段文本（用户的下一句话）。"""

    def __init__(self, scenario: Scenario, seed: int):
        self.scenario = scenario
        self.rng = random.Random(seed)
        self.state = "listening"                    # listening/resolved/escalated
        self.stall_count = 0                        # 连续无进展轮数
        self.achieved: set = set()                  # 已点亮的检查点
        # 开场就说过的信息视为"已提供"，避免把预算再答一遍
        self.answered = {k for k in scenario.user_facts if k in scenario.opening}
        self.checkpoints = [
            Checkpoint("need", "需求被确认（商品+预算都被复述）",
                       lambda t: scenario.goal_keyword in t and "预算" in t),
            Checkpoint("offer", "给出候选商品（出现报价句式）",
                       lambda t: "「" in t and "价格" in t),
            Checkpoint("order", "下单成功",
                       lambda t: "已下单" in t or "下单成功" in t),
        ]
        self.calls = 0

    # ---- 与真实 LLM 客户端同构的接口 ------------------------------------
    def chat(self, messages: List[dict], tools=None, system=None, **kwargs) -> str:
        self.calls += 1
        # 第一轮：没有 agent 消息，直接发出开场请求
        if not messages:
            return self.scenario.opening

        agent_text = messages[-1]["content"]
        self._update_progress(agent_text)

        # 终态 1：所有检查点亮起 → 问题解决，礼貌收尾
        if len(self.achieved) == len(self.checkpoints):
            self.state = "resolved"
            return "太好了，正是我想要的，谢谢你的帮助！"

        # 终态 2：连续 2 次无进展 → 升级投诉（S3）
        if self.stall_count >= 2:
            self.state = "escalated"
            return "连续两次都没有进展，我要投诉！请转人工处理。"

        # S2：被反问且还有没提供的信息 → 补充信息
        if ("？" in agent_text or "?" in agent_text):
            for key, answer in self.scenario.user_facts.items():
                if key in agent_text and key not in self.answered:
                    self.answered.add(key)
                    return answer

        # S1：有候选但没下单 → 推进流程（确认下单）
        if "offer" in self.achieved and "order" not in self.achieved:
            return "好的，就选这个，请帮我下单。"

        # 其余情况：催促（催促本身不提供新信息，agent 若再无进展就会触发 S3）
        return self.rng.choice([
            "麻烦尽快处理，我赶时间。",
            "还没好吗？请尽快帮我解决。",
        ])

    def __call__(self, messages: List[dict], **kwargs) -> str:
        return self.chat(messages, **kwargs)

    # ---- 内部：进展判定 ---------------------------------------------------
    def _update_progress(self, agent_text: str) -> None:
        new = {cp.key for cp in self.checkpoints
               if cp.key not in self.achieved and cp.test(agent_text)}
        if new:
            self.achieved |= new
            self.stall_count = 0      # 有进展就重置耐心计数
        else:
            self.stall_count += 1     # 没进展：耐心 -1

# --- 5. 被测 agent：导购助手（MockLLM，多种策略） ---
# 被测 agent 同样是确定性 MockLLM：chat(messages, env) 返回回复文本，需要查外部世界时走 env.execute——harness 正是在这里拦截（fixture/漂移）。
# rng 只用于措辞变化（模拟 LLM 采样随机性），不影响任何事实性内容。

class ShoppingAssistant:
    """正常导购 agent。策略 direct：直接检索并推荐目标商品；
    策略 ask-first：先反问预算再检索（用来演示模拟器的"补充信息"分支）。"""

    def __init__(self, seed: int, ask_budget_first: bool = False):
        self.rng = random.Random(seed)
        self.ask_budget_first = ask_budget_first
        self._budget: Optional[int] = None
        self._picked: Optional[dict] = None

    def chat(self, messages: List[dict], env, **kwargs) -> str:
        user_texts = [m["content"] for m in messages if m["role"] == "user"]

        # 从用户消息里解析预算（开场或补充信息里都可能给出）
        budget = None
        for t in user_texts:
            mm = re.search(r"预算\D{0,6}?(\d+)", t)
            if mm:
                budget = int(mm.group(1))
                break

        if self.ask_budget_first and budget is None and self._budget is None:
            return "您好！请问您的预算大概是多少？"
        if self._budget is None:
            self._budget = budget if budget is not None else 100

        if self._picked is None:
            # ---- 检索阶段：两次工具调用都会被环境拦截 ----
            sr = env.execute("search_products",
                             {"query": "咖啡", "max_price": self._budget})
            hist = env.execute("get_order_history", {"user_id": "u-2026"})
            products = sr["products"]
            # 优先推用户点名的目标商品；找不到才退化为最便宜的
            goal = [p for p in products if "蓝山" in p["name"]]
            self._picked = goal[0] if goal else min(products, key=lambda p: p["price"])
            opener = self.rng.choice(["为您找到", "帮您查到", "已为您筛选出"])
            last_buy = hist["orders"][0]["name"] if hist["orders"] else "无记录"
            return (f"已按您的预算 {self._budget} 元筛选。{opener}："
                    f"「{self._picked['name']}」，价格 {self._picked['price']} 元。"
                    f"您上次购买过：{last_buy}。请问需要下单吗？")

        # ---- 下单阶段 ----
        if "下单" in user_texts[-1]:
            res = env.execute("place_order", {"name": self._picked["name"],
                                              "price": self._picked["price"]})
            return (f"已下单：「{self._picked['name']}」，"
                    f"实付 {res['paid_price']} 元。感谢您的信任！")
        return (f"您挑选的是「{self._picked['name']}」，"
                f"价格 {self._picked['price']} 元。请问确认下单吗？")

class StallerAgent:
    """反面教材 1：只会安抚、不调工具、不给实质信息。用来验证 S3——连续 2 次无进展后用户真的会投诉。"""

    def chat(self, messages: List[dict], env, **kwargs) -> str:
        return "请稍等，正在为您查询，很快就好。"

class FabricatorAgent:
    """反面教材 2：不调工具，张口就报一个目录里不存在的商品（编造/幻觉）。注意它话术完美——连"下单
    成功"都说了，用户会非常满意地结束对话。这正是 checklist 存在的意义：用户满意 ≠ 事情办对。"""

    def chat(self, messages: List[dict], env, **kwargs) -> str:
        return ("已按您的预算 100 元筛选。推荐「蓝山咖啡 1kg」，价格 88 元。"
                "已下单成功，请查收！")

# --- 6. 会话运行器：把模拟器、agent、环境串成一场完整会话 ---

def run_session(scenario: Scenario, agent, env, sim_seed: int) -> Transcript:
    """运行一场会话直到终态（resolved/escalated）或超过轮数上限。"""
    sim = UserSimulator(scenario, seed=sim_seed)
    tr = Transcript(scenario_id=scenario.scenario_id)
    messages: List[dict] = []

    def say(role: str, content: str) -> None:
        messages.append({"role": role, "content": content})
        tr.messages.append({"role": role, "content": content})

    say("user", sim.chat(messages))                       # 开场请求
    for _ in range(MAX_TURNS):
        reply = agent.chat(messages, env)
        say("assistant", reply)
        say("user", sim.chat(messages))
        if sim.state in ("resolved", "escalated"):
            break
    tr.state = sim.state
    tr.tool_calls = env.calls
    extract_claims(tr)
    return tr

# --- 7. Checklist 式 rubric：把"会话成功"操作化为三张检查项 ---
# checklist 的好处：每项非真即假、附证据、可审计，不依赖主观判断，因此天然低方差——与"1~5 分主观打分"形成鲜明对比。

@dataclass
class ChecklistItem:
    key: str
    desc: str
    passed: bool
    evidence: str

@dataclass
class ChecklistReport:
    items: List[ChecklistItem]
    resolved: bool

    @property
    def score(self) -> float:
        return sum(1 for i in self.items if i.passed) / len(self.items)

    @property
    def passed(self) -> bool:
        return self.resolved and all(i.passed for i in self.items)

def run_checklist(scenario: Scenario, tr: Transcript) -> ChecklistReport:
    # 会话中工具真实返回过的商品集合 = "世界事实"（fixture 或漂移快照）
    tool_names: set = set()
    for call in tr.tool_calls:
        if call["tool"] == "search_products":
            tool_names |= {p["name"] for p in call["result"]["products"]}

    claimed_names = [name for name, _ in tr.claims]

    # 项 A：目标商品在清单里——用户想要的商品真的出现在工具返回的候选中，且 agent 报价的正是它（而非张冠李戴）。
    item_a = ChecklistItem(
        "target_in_list", "目标商品在清单里",
        passed=scenario.expected_product in claimed_names
               and scenario.expected_product in tool_names,
        evidence=f"目标=「{scenario.expected_product}」；"
                 f"agent 报价={claimed_names or '无'}；工具清单含目标="
                 f"{scenario.expected_product in tool_names}",
    )

    # 项 B：总价 ≤ 预算——以最终实付为准；没实付记录则用最贵报价兜底；连报价都没有说明 agent 什么也没办成，直接判失败。
    effective_paid = tr.final_paid
    if effective_paid is None and tr.claims:
        effective_paid = max(price for _, price in tr.claims)
    if effective_paid is None:
        item_b = ChecklistItem("within_budget", "总价≤预算", False,
                               "agent 全程未给出任何价格")
    else:
        item_b = ChecklistItem(
            "within_budget", "总价≤预算",
            passed=effective_paid <= scenario.budget,
            evidence=f"实付/报价={effective_paid:.0f} 元，预算={scenario.budget} 元",
        )

    # 项 C：无编造商品——agent 报出的每个商品都必须能在工具返回中找到出处；这是"幻觉检测"的最小形态：grounding 到可验证的外部事实。
    fabricated = [n for n in claimed_names if n not in tool_names]
    item_c = ChecklistItem(
        "no_fabrication", "无编造商品",
        passed=len(fabricated) == 0,
        evidence=f"无出处报价={fabricated or '无'}",
    )

    return ChecklistReport(items=[item_a, item_b, item_c],
                           resolved=tr.state == "resolved")

# --- 8. 实验编排：可复现对 / fixture 组 / 漂移对照组 / 反面教材 ---

def make_fixture_run(scenario: Scenario, agent_seed: int,
                     sim_seed: int) -> Tuple[Transcript, ChecklistReport]:
    env = FixtureBackend(FIXTURES_V1)          # 每次运行新实例，共享同一份录制数据
    agent = ShoppingAssistant(seed=agent_seed)
    tr = run_session(scenario, agent, env, sim_seed=sim_seed)
    return tr, run_checklist(scenario, tr)

def make_drift_run(scenario: Scenario, run_idx: int, agent_seed: int,
                   sim_seed: int) -> Tuple[Transcript, ChecklistReport]:
    env = DriftingBackend(run_seed=SEED * 7 + 13 + run_idx)   # 每个 run 一个市场快照
    agent = ShoppingAssistant(seed=agent_seed)
    tr = run_session(scenario, agent, env, sim_seed=sim_seed)
    return tr, run_checklist(scenario, tr)

# --- 9. 自检：assert 断言的是实验的核心结论，不是"程序跑完了" ---

def run_self_checks(scen: Scenario, scen_nb: Scenario) -> None:
    # ---- (a) 可复现性：同一 scenario、同一组种子跑两次，产物逐字节一致 ----
    a1 = make_fixture_run(scen, agent_seed=SEED, sim_seed=SEED)
    a2 = make_fixture_run(scen, agent_seed=SEED, sim_seed=SEED)
    assert a1[0].fingerprint() == a2[0].fingerprint(), "同种子两次运行消息应完全一致"
    assert a1[0].tool_fingerprint() == a2[0].tool_fingerprint(), \
        "同种子两次运行工具记录应完全一致"
    assert a1[1].score == a2[1].score, "同种子两次运行评分应一致"

    # ---- fixture 组：N 次运行，agent 采样种子各不相同 ----
    fix_runs = [make_fixture_run(scen, agent_seed=SEED + 100 + i,
                                 sim_seed=SEED + i) for i in range(N_RUNS)]
    fix_scores = [r[1].score for r in fix_runs]
    fix_fps = [r[0].fingerprint() for r in fix_runs]
    fix_tool_fps = [r[0].tool_fingerprint() for r in fix_runs]

    # ---- (b) 采样噪声真的存在：措辞随种子变化，指纹不完全相同（否则"评分稳定"成了空话）----
    assert len(set(fix_fps)) >= 2, "不同采样种子应产生不同的会话措辞"

    # ---- (c) fixture 组评分绝对稳定：方差为 0，全部通过 ----
    assert statistics.pvariance(fix_scores) == 0.0, \
        "fixture 组 N 次评分应完全一致（环境冻结 → 零方差）"
    assert all(s == 1.0 for s in fix_scores), "fixture 组每次运行都应满分"
    assert all(r[1].passed for r in fix_runs), "fixture 组 checklist 应全部通过"

    # ---- (d) 环境被真正冻结：所有运行看到的工具返回完全一致（订单历史 v1） ----
    assert len(set(fix_tool_fps)) == 1, "fixture 组所有运行的工具返回应完全一致"
    for tr, _ in fix_runs:
        hist = [c["result"] for c in tr.tool_calls
                if c["tool"] == "get_order_history"]
        assert hist and hist[0] == ORDER_HISTORY_V1, "订单历史应始终为录制的 v1 载荷"
    assert _payload_fingerprint(FIXTURES_V1) == FIXTURES_V1_FINGERPRINT, \
        "录制数据不得被运行污染（deepcopy 隔离失效）"

    # ---- (e) fixture 组的工具调用被完整拦截且序列正确 ----
    seq = [c["tool"] for c in fix_runs[0][0].tool_calls]
    assert seq == ["search_products", "get_order_history", "place_order"], \
        f"工具调用序列异常: {seq}"

    # ---- 漂移对照组：同样的 agent、同样的采样种子序列，只有环境在漂移 ----
    drift_runs = [make_drift_run(scen, run_idx=i, agent_seed=SEED + 100 + i,
                                 sim_seed=SEED + i) for i in range(N_RUNS)]
    drift_scores = [r[1].score for r in drift_runs]
    drift_tool_fps = [r[0].tool_fingerprint() for r in drift_runs]
    var_fix = statistics.pvariance(fix_scores)
    var_drift = statistics.pvariance(drift_scores)

    # ---- (f) 漂移组环境确实在变：不同 run 看到的工具返回不同 ----
    assert len(set(drift_tool_fps)) >= 2, "漂移组不同运行应看到不同的市场快照"

    # ---- (g) 核心结论：漂移组评分方差显著大于 fixture 组 ----
    assert len(set(drift_scores)) >= 2, "漂移组评分应出现分化（同 agent 不同命运）"
    assert var_drift > var_fix + 0.01, \
        f"漂移组方差({var_drift:.4f})应显著大于 fixture 组({var_fix:.4f})"
    n_budget_fail = sum(1 for r in drift_runs
                        if not r[1].items[1].passed)
    n_budget_pass = N_RUNS - n_budget_fail
    assert n_budget_fail >= 2, "漂移组至少 2 次运行超预算（漂移确实越过了预算线）"
    assert n_budget_pass >= 2, "漂移组至少 2 次运行未超预算（漂移是双向的）"
    assert statistics.mean(drift_scores) < statistics.mean(fix_scores), \
        "不受控环境拉低了平均表现——分数波动不是 agent 的错，却是 agent 的分"

    # ---- (h) checklist 能抓住超预算：漂移组失败项的证据与价格吻合 ----
    for tr, rep in drift_runs:
        item_b = rep.items[1]
        if not item_b.passed:
            assert tr.final_paid is not None and tr.final_paid > scen.budget, \
                "预算项失败时，实付金额必须确实超过预算"

    # ---- (i) 合成超预算样例：checklist 的直接单测（不依赖随机漂移） ----
    fake_tr = Transcript(scenario_id="synthetic-overbudget")
    fake_tr.state = "resolved"
    fake_tr.messages = [{"role": "assistant",
                         "content": "「蓝山咖啡 500g」，价格 120 元。已下单。"}]
    fake_tr.tool_calls = [{"tool": "search_products", "params": {},
                           "result": {"products": [
                               {"name": "蓝山咖啡 500g", "price": 120, "stock": 1}]}}]
    extract_claims(fake_tr)
    fake_rep = run_checklist(scen, fake_tr)
    assert not fake_rep.items[1].passed, "120 元 > 100 元预算，预算项必须失败"
    assert not fake_rep.passed, "超预算样例整体必须判失败"

    # ---- (j) 状态机 S3：连续 2 次无进展 → 升级投诉 ----
    stall_env = FixtureBackend(FIXTURES_V1)
    stall_tr = run_session(scen, StallerAgent(), stall_env, sim_seed=SEED)
    assert stall_tr.state == "escalated", "停滞 agent 应被用户投诉"
    user_msgs = [m["content"] for m in stall_tr.messages if m["role"] == "user"]
    assert "投诉" in user_msgs[-1], "最后一句用户消息应是投诉"
    n_agent_turns = sum(1 for m in stall_tr.messages if m["role"] == "assistant")
    assert n_agent_turns == 2, "应恰好给 agent 两次机会后才投诉"
    stall_rep = run_checklist(scen, stall_tr)
    assert not stall_rep.passed, "停滞会话整体必须判失败"

    # ---- (k) 状态机 S2：被反问 → 补充信息（ask-first agent + 无预算场景） ----
    ask_env = FixtureBackend(FIXTURES_V1)
    ask_tr = run_session(scen_nb, ShoppingAssistant(seed=SEED, ask_budget_first=True),
                         ask_env, sim_seed=SEED)
    ask_user_msgs = [m["content"] for m in ask_tr.messages if m["role"] == "user"]
    assert "我的预算是 100 元。" in ask_user_msgs, "被反问预算后应补充预算信息"
    assert ask_tr.state == "resolved", "补充信息后流程应走通并解决问题"
    assert run_checklist(scen_nb, ask_tr).passed, "ask-first 会话应通过 checklist"

    # ---- (l) 编造商品：用户满意收尾，checklist 依然判失败 ----
    fab_env = FixtureBackend(FIXTURES_V1)
    fab_tr = run_session(scen, FabricatorAgent(), fab_env, sim_seed=SEED)
    assert fab_tr.state == "resolved", "编造 agent 话术完美，用户会满意（陷阱）"
    assert len(fab_tr.tool_calls) == 0, "编造 agent 不应调用任何工具"
    fab_rep = run_checklist(scen, fab_tr)
    assert not fab_rep.items[2].passed, "无出处的商品必须被判定为编造"
    assert not fab_rep.passed, "编造商品的会话整体必须判失败——尽管用户满意"

    # ---- (m) fixture 组全绿：resolved 且三项全过（再次强调整体结论） ----
    assert all(r[0].state == "resolved" for r in fix_runs), "fixture 组应全部解决问题"

# --- 10. 演示入口：分步展示整条流水线并打印报告 ---

def _print_dialogue(tr: Transcript, indent: str = "   ") -> None:
    for m in tr.messages:
        who = "用户" if m["role"] == "user" else "助手"
        print(f"{indent}{who}: {m['content']}")
    for c in tr.tool_calls:
        print(f"{indent}└─ 工具 {c['tool']}({json.dumps(c['params'], ensure_ascii=False)})"
              f" -> {json.dumps(c['result'], ensure_ascii=False)}")

def main() -> None:
    print("=" * 68)
    print("EVAL LAB 07 · 会话模拟器与 Fixtures（纯标准库 / 确定性 / 零依赖）")
    print("=" * 68)

    scenarios = build_scenarios()
    scen, scen_nb = scenarios["buy-coffee"], scenarios["buy-coffee-no-budget"]

    # [1/5] 场景与 fixtures
    print(f"\n[1/5] 场景与 Fixtures")
    print(f"   场景: {scen.scenario_id} | 目标=「{scen.expected_product}」 | 预算={scen.budget} 元")
    print(f"   开场: {scen.opening}")
    print(f"   录制载荷: search_products({len(CATALOG_V1)} 个商品) / get_order_history(v1) / place_order(v1)")
    print(f"   fixtures 指纹: {FIXTURES_V1_FINGERPRINT[:16]}…")

    # [2/5] 一场完整会话（fixture 环境）
    print(f"\n[2/5] 完整会话演示（fixture 环境，状态机驱动的用户模拟器）：")
    tr_demo, rep_demo = make_fixture_run(scen, agent_seed=SEED, sim_seed=SEED)
    _print_dialogue(tr_demo)
    print(f"   结局={tr_demo.state} | checklist: " +
          "  ".join(f"{i.desc}:{'√' if i.passed else '×'}" for i in rep_demo.items))

    # [3/5] 状态机两个关键分支
    print(f"\n[3/5] 模拟器状态机分支演示：")
    ask_env = FixtureBackend(FIXTURES_V1)
    ask_tr = run_session(scen_nb, ShoppingAssistant(seed=SEED, ask_budget_first=True),
                         ask_env, sim_seed=SEED)
    print("   [S2 被反问→补充信息]")
    _print_dialogue(ask_tr, indent="     ")
    stall_tr = run_session(scen, StallerAgent(), FixtureBackend(FIXTURES_V1),
                           sim_seed=SEED)
    print("   [S3 连续 2 次无进展→升级投诉]")
    _print_dialogue(stall_tr, indent="     ")

    # [4/5] N 次运行：fixture 组 vs 漂移对照组
    print(f"\n[4/5] 同一场景运行 {N_RUNS} 次（agent 采样种子逐次不同）：")
    print("   --- fixture 组（环境冻结）---")
    fix_runs = [make_fixture_run(scen, agent_seed=SEED + 100 + i,
                                 sim_seed=SEED + i) for i in range(N_RUNS)]
    for i, (tr, rep) in enumerate(fix_runs):
        print(f"   run{i}: 实付={tr.final_paid:.0f} 元 | 评分={rep.score:.2f} | 通过={rep.passed} "
              f"| 消息指纹={tr.fingerprint()[:8]}… | 工具指纹={tr.tool_fingerprint()[:8]}…")
    print("   --- 漂移对照组（伪实时市场快照）---")
    drift_runs = [make_drift_run(scen, run_idx=i, agent_seed=SEED + 100 + i,
                                 sim_seed=SEED + i) for i in range(N_RUNS)]
    for i, (tr, rep) in enumerate(drift_runs):
        verdict = "超预算× " if not rep.items[1].passed else ""
        print(f"   run{i}: 实付={tr.final_paid:.0f} 元 {verdict}| 评分={rep.score:.2f} "
              f"| 工具指纹={tr.tool_fingerprint()[:8]}…")
    var_fix = statistics.pvariance([r[1].score for r in fix_runs])
    var_drift = statistics.pvariance([r[1].score for r in drift_runs])
    print(f"\n   方差对比: fixture={var_fix:.4f} vs 漂移={var_drift:.4f}")
    print("   结论: 同一个 agent、同样的采样噪声，仅环境是否受控不同——")
    print("         漂移组的分数波动完全是环境噪声，而不是能力变化。")

    # [5/5] checklist 抓住编造商品
    print(f"\n[5/5] checklist 牙齿演示（编造商品：用户满意但事情没办对）：")
    fab_tr = run_session(scen, FabricatorAgent(), FixtureBackend(FIXTURES_V1),
                         sim_seed=SEED)
    fab_rep = run_checklist(scen, fab_tr)
    print(f"   结局={fab_tr.state}（用户满意！）但 checklist: " +
          "  ".join(f"{i.desc}:{'√' if i.passed else '×'}" for i in fab_rep.items))
    for i in fab_rep.items:
        if not i.passed:
            print(f"     × {i.desc} <- {i.evidence}")

    # 自检
    print("\n[自检] 运行 assert 断言（可复现性 / 方差对比 / 状态机 / checklist）…")
    run_self_checks(scen, scen_nb)
    print(f"   可复现对: 两次同种子运行指纹一致 ✔")
    print(f"   fixture 组 {N_RUNS} 次: 评分全为 1.00，方差 {var_fix:.4f} ✔")
    print(f"   漂移组 {N_RUNS} 次: 评分分化，方差 {var_drift:.4f}（> fixture 组 + 0.01）✔")
    print(f"   状态机: 被反问→补充信息 ✔ / 连续 2 次无进展→投诉 ✔")
    print(f"   checklist: 抓超预算 ✔ / 抓编造商品 ✔")
    print("\n✅ 自检通过：eval_lab07_simulator_fixtures.py 全部断言成立")

if __name__ == "__main__":
    main()
