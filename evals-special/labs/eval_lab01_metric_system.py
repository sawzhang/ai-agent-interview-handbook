#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab01_metric_system.py — 指标体系：pass@k / pass^k / 一致性
====================================================================

【实验目的】
    「我们的模型单次准确率有 80%」——这句话是真的，但它可能严重误导决策。
    本实验用纯标准库搭建一个小而完整的「评测指标体系」，用可计算、可断言的
    方式讲清四件面试中极易混淆的事：

    1) pass@k（k 次尝试中至少 1 次成功）回答「它能不能做到」，度量的是
       能力上限（capability ceiling）；
    2) pass^k（k 次尝试全部成功）回答「它敢不敢被连续使用」，度量的是
       生产一致性（production consistency）；
    3) 两者随 k 增大迅速分道扬镳：一个 p=0.8 的 agent，pass@8 ≈ 99.9997%，
       而 pass^8 只有约 16.8%。「多试几次总有一次成功」不是卖点，而是用户
       流失的原因——用户不接受重试；
    4) 指标的选择直接决定发布结论：同一个 agent，在「关键决策」与「创意
       生成」两种门禁下会得到相反的「可发布」判定。

【对应章节】
    本特辑第 E02 章 · 评估指标体系（先说清楚什么叫「好」）
    （主仓库 lab05_eval_harness.py 解决「评估流水线怎么跑」，本讲深挖
    「流水线到底应该报哪个数」，是后续所有评测 lab 的度量基础。）

【核心概念】
    - pass@k: 同一任务独立尝试 k 次，至少 1 次成功的概率，理论值 1-(1-p)^k。
      HumanEval 等公开评测报告的就是它（pass@1 / pass@10）。
    - pass^k: 同一任务独立尝试 k 次，全部成功的概率，理论值 p^k。只有它才
      对应「用户连续使用 k 次不出错」的真实体验，p<1 时随 k 指数级恶化。
    - 无偏估计: 实际评测中每个任务只能负担 n 次运行。用 n 个样本估计 pass@k
      的无偏公式是 1 - C(n-c,k)/C(n,k)（Chen et al., 2021, HumanEval），
      c 为成功次数；pass^k 对应 C(c,k)/C(n,k)。它们对应「无放回抽 k 个」。
    - 朴素估计的偏差方向: 「n 次里有任何一次成功就算过」实际报告的是 pass@n，
      会高估 pass@k；有放回公式 (c/n)^k 会高估一致性——这是危险的方向，
      它让团队误以为系统比实际更稳定。
    - 发布门禁 Gate: 「看哪个指标 + 阈值多少」。阈值由产品形态的容错度决定：
      关键决策看 pass^k，创意生成可看 pass@k。

【如何运行】
    cd evals-special/labs
    python3 eval_lab01_metric_system.py
    （纯标准库、零依赖、固定随机种子，任何机器上输出完全相同）

【思考题（面试延伸）】
    1. pass^k = p^k 依赖「各次尝试相互独立」的假设。真实 agent 系统中哪些
       情况会破坏独立性（上下文污染、残留状态、下游限流、缓存命中）？若各次
       尝试正相关（这次挂了下次更容易挂），真实 pass^k 比 p^k 高还是低？
    2. 无偏估计为什么用「无放回组合」而不是直接 1-(1-c/n)^k？既然每个任务
       跑了 n=200 个样本，为什么报告时仍只报 pass@1/pass@10 而不报 pass@200？
       （提示：评测成本与线上成本不是一回事。）
    3. 如果要说服管理层「准确率 80% 的 agent 其实不可上线」，你会引用本实验
       的哪几个数字？把 p 从 0.8 提升到 0.97，pass^8 改善了多少倍？
    4. 创意类功能的一致性要求天然更低。如何用治理手段（风险分级、审批流、
       定期复审）防止团队以「我们是创意场景」为由逃避门禁？
"""

from __future__ import annotations

import itertools
import math
import random
from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence

# 全局固定种子：本文件所有「随机性」的唯一源头。
# 为什么要固定：评测的命脉是可复现——同一脚本跑两遍若得到不同的数，
# 任何断言都毫无意义。固定种子让「实验结果」变成「数学事实」。
SEED = 20260805


# ---------------------------------------------------------------------------
# 1. 被测对象：Task 与 MockAgent
# ---------------------------------------------------------------------------
# 为什么用 mock：本实验研究的是「指标该怎么定义、怎么估计」，而不是「模型有
# 多强」。我们构造完全透明的随机 agent——它的单次成功率 p 是已知的真值，
# 这样指标估计数值就能与理论值互相印证：估计公式写错，断言立刻报错。

@dataclass
class Task:
    """一个评测任务。p 是出题人视角的「单次成功概率」真值（生产中没有它，
    实验中保留它是为了校验估计器）。"""
    task_id: str
    scenario: str
    p: float


class MockAgent:
    """确定性 mock agent。每次 __call__(task) 执行一次尝试，返回结构化结果。

    接口形态与真实 LLM 客户端对齐（输入任务 -> 输出 dict），生产环境可把本类
    整体替换成真实实现而上层代码不动。所有随机性来自固定 seed 的
    random.Random，且按调用顺序推进——因此「同种子 + 同调用顺序 => 同结果」，
    这也是为什么后文的实验都严格按固定顺序遍历任务矩阵。
    """

    def __init__(self, name: str, seed: int):
        self.name = name
        self._rng = random.Random(seed)

    def __call__(self, task: Task) -> dict:
        roll = self._rng.random()          # 抽一个 [0,1) 均匀随机数
        return {
            "agent": self.name,
            "task_id": task.task_id,
            "success": roll < task.p,      # 以概率 p 判定成功
            "roll": round(roll, 6),
        }


# ---- 四种任务集：对应四个实验场景 ---------------------------------------

def make_hetero_tasks(n: int = 40) -> List[Task]:
    """难度不均的任务集：单次成功率散布在 0.50~0.95。
    为什么故意不均：平均通过率会掩盖最弱的任务，而生产上拖垮 agent 的往往
    正是少数低 p 任务；重复实验必须能暴露分布，而不是只报一个均值。"""
    rng = random.Random(SEED + 1)
    levels = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    return [Task(f"T{i + 1:02d}", f"场景-{i + 1:02d}", rng.choice(levels))
            for i in range(n)]


def make_uniform_tasks(n: int, p: float) -> List[Task]:
    """同成功率任务集：全部任务单次成功率都是 p。
    专门用来在数值上验证 pass^k = p^k（独立同分布假设下的理论值）。"""
    return [Task(f"U{i + 1:04d}", "同质场景", p) for i in range(n)]


def make_stable_tasks(n: int = 30) -> List[Task]:
    """「稳健型」agent 的任务集：p 集中在 0.94~0.98，均值高、方差小。"""
    ps = [0.94, 0.95, 0.96, 0.97, 0.98]
    return [Task(f"S{i + 1:02d}", "关键决策", ps[i % len(ps)]) for i in range(n)]


def make_wild_tasks(n: int = 30) -> List[Task]:
    """「抽奖型」agent 的任务集：p 在 0.50/0.65/0.85 之间大幅波动。
    均值（≈0.67）看着不算灾难，但方差大 => 一致性差，正是「偶尔惊艳、
    经常翻车」的那类系统。"""
    ps = [0.50, 0.65, 0.85]
    return [Task(f"W{i + 1:02d}", "创意脑暴", ps[i % len(ps)]) for i in range(n)]


# ---------------------------------------------------------------------------
# 2. 指标定义：pass@k 与 pass^k 的理论值 + 六个估计函数
# ---------------------------------------------------------------------------
# 约定：p 为单任务单次成功率；k 为尝试次数；估计函数的参数 (c, n) 表示
# 「n 次运行里成功了 c 次」的观测数据。

def analytic_pass_at_k(p: float, k: int) -> float:
    """理论 pass@k = 1 - (1-p)^k：k 次全部失败的对立事件。
    前提假设：各次尝试相互独立（思考题 1 讨论它何时被破坏）。"""
    return 1.0 - (1.0 - p) ** k


def analytic_pass_pow_k(p: float, k: int) -> float:
    """理论 pass^k = p^k：k 次尝试每一次都必须成功。
    p<1 时它随 k 指数级衰减——这是「一致性比能力难得多」的数学本质。"""
    return p ** k


def naive_pass_at_k(c: int, n: int, k: int) -> float:
    """朴素估计（有放回/独立假设）：1 - (1-c/n)^k。
    把 k 次抽取当成「有放回抽样」，允许同一成功样本被重复抽中。
    有限样本下它与精确的无放回组合概率存在系统性偏差（方向见实验 4）。"""
    return 1.0 - (1.0 - c / n) ** k


def naive_pass_pow_k(c: int, n: int, k: int) -> float:
    """朴素估计（有放回）：(c/n)^k。
    危险方向：有放回抽取可以重复利用同一次成功，所以它系统性高估
    「连续 k 次成功」的概率——按它做决策，团队会误以为系统比实际更稳。"""
    return (c / n) ** k


def naive_pass_at_k_all_n(c: int, n: int, k: int) -> float:
    """最常见也最隐蔽的朴素：把 n 次全跑完，「有任何一次成功」就算通过。
    这实际度量的是 pass@n（而非 pass@k）。n >= k 时尝试次数更多、成功概率
    更大，因此它系统性高估 pass@k——很多「好看」的评测数字就是这么来的。"""
    _ = k  # 该估计根本不关心 k，这正是问题所在
    return 1.0 if c > 0 else 0.0


def unbiased_pass_at_k(c: int, n: int, k: int) -> float:
    """pass@k 的无偏估计（Chen et al., 2021, HumanEval 采用）：

        pass@k = 1 - C(n-c, k) / C(n, k)

    含义：从已有的 n 个样本里无放回地抽 k 个，至少 1 个成功的概率。
    边界情形：若失败样本不足 k 个（n-c < k），C(n-c,k)=0，估计值为 1——
    怎么抽都必然抽到成功，语义自洽。
    为什么不用 1-(1-c/n)^k：那是「有放回」模型，有限样本下偏离精确值。"""
    if k > n:
        raise ValueError(f"k={k} 不能超过已有样本数 n={n}")
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def unbiased_pass_pow_k(c: int, n: int, k: int) -> float:
    """pass^k 的无偏估计（本实验按同一「无放回抽样」思路构造的对称形式）：

        pass^k = C(c, k) / C(n, k)

    含义：无放回抽 k 个样本且全部为成功的概率。
    边界情形：c < k 时 C(c,k)=0——成功样本不够凑满连续 k 次，估计为 0。"""
    if k > n:
        raise ValueError(f"k={k} 不能超过已有样本数 n={n}")
    return math.comb(c, k) / math.comb(n, k)


# ---------------------------------------------------------------------------
# 3. 暴力枚举校验器：估计器的「裁判」
# ---------------------------------------------------------------------------
# 直接枚举 C(n,k) 种组合并统计精确比例。复杂度是指数级的，只配给小样本当
# 裁判——但这已经足够：任何估计器只要与枚举值对不上，实现一定有 bug。
# 这是「用最笨的真值校验最聪明的公式」的经典自检套路。

def exact_pass_at_k(outcomes: Sequence[int], k: int) -> float:
    """枚举所有 k 元组合，统计「至少 1 个成功」的精确比例。"""
    total = hit = 0
    for combo in itertools.combinations(outcomes, k):
        total += 1
        if any(combo):
            hit += 1
    return hit / total


def exact_pass_pow_k(outcomes: Sequence[int], k: int) -> float:
    """枚举所有 k 元组合，统计「全部成功」的精确比例。"""
    total = hit = 0
    for combo in itertools.combinations(outcomes, k):
        total += 1
        if all(combo):
            hit += 1
    return hit / total


# ---------------------------------------------------------------------------
# 4. 实验 1：N 任务 x K 次重复运行 —— 能力上限与生产一致性的差距
# ---------------------------------------------------------------------------

def run_matrix(agent: MockAgent, tasks: Sequence[Task], k_runs: int
               ) -> List[List[bool]]:
    """让 agent 把每个任务各跑 k_runs 次，得到结果矩阵 matrix[任务][第几次]。
    注意遍历顺序固定：agent 的随机数流随调用次序推进，顺序一变结果就变，
    可复现性 = 固定种子 + 固定顺序，两者缺一不可。"""
    return [[agent(task)["success"] for _ in range(k_runs)] for task in tasks]


def matrix_metrics(matrix: List[List[bool]]) -> List[dict]:
    """对每个 k=1..K，跨任务计算两个指标：
      - pass_at_k : 「前 k 次里至少成功 1 次」的任务占比（能力上限）；
      - pass_pow_k: 「前 k 次每一次都成功」的任务占比（生产一致性）。
    两者都取同一矩阵的前缀（前 k 列），因此随 k 增大是同源可比的两条曲线：
    前者单调不减、后者单调不增，差距只会越拉越大。
    顺带一提：k=1 时两个指标完全相同，都等于平均单次成功率——这就是为什么
    只看 pass@1 的团队永远意识不到一致性问题的存在。"""
    n, k_max = len(matrix), len(matrix[0])
    rows = []
    for k in range(1, k_max + 1):
        at_least_one = sum(1 for row in matrix if any(row[:k]))
        all_ok = sum(1 for row in matrix if all(row[:k]))
        rows.append({
            "k": k,
            "pass_at_k": at_least_one / n,
            "pass_pow_k": all_ok / n,
            "gap": (at_least_one - all_ok) / n,
        })
    return rows


# ---------------------------------------------------------------------------
# 5. 实验 3 的工具：发布门禁与「矩阵级」无偏估计
# ---------------------------------------------------------------------------

def estimate_pass_at_k_from_matrix(matrix: List[List[bool]], k: int) -> float:
    """逐任务用无偏估计 1-C(n-c,k)/C(n,k)，再对任务取平均。
    为什么先逐任务再平均：pass@k 对任务的平均不等于「把所有运行混在一起」
    的通过率——任务难度不同，混合会掩盖分布（辛普森悖论的近亲）。"""
    vals = [unbiased_pass_at_k(sum(row), len(row), k) for row in matrix]
    return sum(vals) / len(vals)


def estimate_pass_pow_k_from_matrix(matrix: List[List[bool]], k: int) -> float:
    """逐任务用无偏估计 C(c,k)/C(n,k)，再对任务取平均。"""
    vals = [unbiased_pass_pow_k(sum(row), len(row), k) for row in matrix]
    return sum(vals) / len(vals)


@dataclass
class Gate:
    """发布门禁 = 看哪个指标 + 阈值。
    为什么把「为什么看这个指标」也写进结构：门禁不是纯技术问题，阈值背后是
    产品容错度的业务判断，写清楚理由才能防止门槛被随意挪动。"""
    name: str
    metric_fn: Callable[[List[List[bool]]], float]
    threshold: float
    why: str

    def decide(self, metric_value: float) -> bool:
        """边界语义：恰好等于阈值算通过（>=）。门禁文档必须写死边界方向，
        否则『0.7999 算不算过 0.8』会吵到上线前一天。"""
        return metric_value >= self.threshold


# 关键决策门禁：退款审批、医疗建议这类场景，错一次就是事故。
# 用户不会「再试几次」，系统必须「每次都行」——所以看一致性指标 pass^3。
CRITICAL_GATE = Gate(
    name="关键决策门禁",
    metric_fn=lambda m: estimate_pass_pow_k_from_matrix(m, 3),
    threshold=0.80,
    why="错一次即事故：要求连续 3 次全部成功的概率 >= 80%（一致性指标 pass^3）",
)

# 创意门禁：文案、头脑风暴这类场景，人工本来就要从多个候选里挑一个，
# 「3 次里有 1 次可用」即可接受——所以看能力上限指标 pass@3。
CREATIVE_GATE = Gate(
    name="创意门禁",
    metric_fn=lambda m: estimate_pass_at_k_from_matrix(m, 3),
    threshold=0.90,
    why="人工从多个草稿中挑选：3 次里至少 1 次可用的概率 >= 90%（上限指标 pass@3）",
)


def evaluate_against_gates(agent: MockAgent, tasks: Sequence[Task], k_runs: int
                           ) -> Dict[str, object]:
    """让一个 agent 跑完任务矩阵，计算两个门禁的指标估计与发布判定。"""
    matrix = run_matrix(agent, tasks, k_runs)
    mean_p = sum(sum(row) for row in matrix) / (len(matrix) * k_runs)
    pow3 = CRITICAL_GATE.metric_fn(matrix)
    at3 = CREATIVE_GATE.metric_fn(matrix)
    return {
        "agent": agent.name,
        "mean_p": mean_p,                    # 平均单次成功率（= pass^1 的观测）
        "pass_pow_3": pow3,
        "pass_at_3": at3,
        "critical_pass": CRITICAL_GATE.decide(pow3),
        "creative_pass": CREATIVE_GATE.decide(at3),
    }


# ---------------------------------------------------------------------------
# 6. 实验 4 的固定样本：用枚举给「无偏 vs 朴素」当裁判
# ---------------------------------------------------------------------------
# 8 次运行、4 次成功（c=4, n=8）。刻意选 c/n=0.5：此时各估计式的差距最直观。
SAMPLE_OUTCOMES = [1, 1, 0, 1, 0, 0, 1, 0]


def compare_estimators(outcomes: Sequence[int], k: int) -> dict:
    """对同一份观测数据，计算全部六个估计值，供展示与断言。"""
    c, n = sum(outcomes), len(outcomes)
    return {
        "c": c,
        "n": n,
        "k": k,
        "exact_at": exact_pass_at_k(outcomes, k),
        "exact_pow": exact_pass_pow_k(outcomes, k),
        "unbiased_at": unbiased_pass_at_k(c, n, k),
        "unbiased_pow": unbiased_pass_pow_k(c, n, k),
        "naive_at": naive_pass_at_k(c, n, k),
        "naive_pow": naive_pass_pow_k(c, n, k),
        "naive_all_n": naive_pass_at_k_all_n(c, n, k),
    }


# ---------------------------------------------------------------------------
# 7. 自检：assert 断言本实验的全部核心结论（不是断言「跑完了」）
# ---------------------------------------------------------------------------

def run_self_checks(hetero_rows: List[dict], hetero_ps: List[float],
                    homog_rows: List[dict], p_homog: float,
                    gate_report: Dict[str, dict]) -> None:
    # ---- (a) 估计器正确性：无偏估计必须与暴力枚举精确一致 ------------------
    # 这是整个实验的信任根基：公式若连 8 选 3 都算不对，后面全是空中楼阁。
    for outcomes, k in [(SAMPLE_OUTCOMES, 3),
                        ([1, 0, 1, 1, 0], 2),
                        ([0, 1, 1, 1, 1, 0, 1], 4)]:
        c, n = sum(outcomes), len(outcomes)
        assert abs(unbiased_pass_at_k(c, n, k)
                   - exact_pass_at_k(outcomes, k)) < 1e-12, \
            f"无偏 pass@{k} 与枚举真值不符 (c={c}, n={n})"
        assert abs(unbiased_pass_pow_k(c, n, k)
                   - exact_pass_pow_k(outcomes, k)) < 1e-12, \
            f"无偏 pass^{k} 与枚举真值不符 (c={c}, n={n})"

    # ---- (b) 朴素估计的偏差方向：用枚举钉死 --------------------------------
    cmp8 = compare_estimators(SAMPLE_OUTCOMES, 3)
    # pass@k：有放回朴素(0.875) < 无偏(≈0.929) < 「任何一次成功」(1.0=pass@8)
    assert cmp8["naive_at"] < cmp8["unbiased_at"] < cmp8["naive_all_n"], \
        "pass@k 各估计式的大小关系不符合理论"
    assert cmp8["unbiased_at"] - cmp8["naive_at"] > 0.05, \
        "有放回朴素对 pass@k 的低估幅度应可被观察到"
    assert cmp8["naive_all_n"] - cmp8["unbiased_at"] > 0.05, \
        "『任何一次成功就算过』对 pass@k 的高估幅度应可被观察到"
    # pass^k：有放回朴素(0.125) > 无偏(≈0.071)——高估一致性，危险方向
    assert cmp8["naive_pow"] > cmp8["unbiased_pow"], \
        "有放回朴素应高估 pass^k（一致性）"
    assert cmp8["naive_pow"] - cmp8["unbiased_pow"] > 0.05, \
        "对一致性的高估幅度应可被观察到"

    # ---- (c) 核心不等式：pass^k <= pass@k（一致性地不高于上限）------------
    for p in (0.2, 0.5, 0.8, 0.95):
        for k in range(1, 9):
            assert analytic_pass_pow_k(p, k) <= analytic_pass_at_k(p, k) + 1e-15, \
                f"理论上 pass^{k} 不应超过 pass@{k} (p={p})"
    for row in hetero_rows + homog_rows:
        assert row["pass_pow_k"] <= row["pass_at_k"], \
            f"经验指标在 k={row['k']} 处违反 pass^k <= pass@k"

    # ---- (d) pass^k = p^k：独立同分布假设下数值吻合 ------------------------
    for k in range(1, 9):
        # 理论侧：解析式与 p^k 恒等
        assert analytic_pass_pow_k(p_homog, k) == p_homog ** k, \
            f"解析 pass^{k} 应恒等于 p^{k}"
        # 实验侧：4000 任务 x 8 次的大样本模拟应逼近理论值
        emp_pow = homog_rows[k - 1]["pass_pow_k"]
        assert abs(emp_pow - p_homog ** k) < 0.03, \
            f"经验 pass^{k}={emp_pow:.3f} 偏离理论 p^k={p_homog ** k:.3f} 过多"
        emp_at = homog_rows[k - 1]["pass_at_k"]
        assert abs(emp_at - analytic_pass_at_k(p_homog, k)) < 0.03, \
            f"经验 pass@{k} 偏离理论值过多"

    # ---- (e) 「用户不接受多试几次」：pass^1..pass^8 严格单调下降 ----------
    curve = [analytic_pass_pow_k(p_homog, k) for k in range(1, 9)]
    assert all(curve[i + 1] < curve[i] for i in range(7)), \
        "p<1 时 pass^k 必须随 k 严格单调下降"
    assert curve[-1] < 0.17, "p=0.8 时 pass^8 应已跌到 17% 以下"
    assert 1.0 - p_homog ** 10 > 0.89, \
        "p=0.8 时连续使用 10 次至少踩坑一次的概率应超过 89%"

    # ---- (f) 差距随 K 拉开：经验差距单调不减、理论差距严格递增 ------------
    gaps = [r["gap"] for r in hetero_rows]
    assert all(gaps[i + 1] >= gaps[i] for i in range(len(gaps) - 1)), \
        "能力上限与生产一致性的差距应随 k 单调不减"
    assert gaps[-1] > gaps[0] + 0.4, \
        "k=8 时的差距应显著大于 k=1（差距要真正『拉开』）"

    def theory_gap(k: int) -> float:
        return (sum(analytic_pass_at_k(p, k) for p in hetero_ps) / len(hetero_ps)
                - sum(analytic_pass_pow_k(p, k) for p in hetero_ps) / len(hetero_ps))

    t_gaps = [theory_gap(k) for k in range(1, 9)]
    assert all(t_gaps[i + 1] > t_gaps[i] for i in range(7)), \
        "理论差距应随 k 严格递增（0<p<1 时两项一增一减）"

    # ---- (g) 门禁边界语义：恰好等于阈值 => 通过；差一点 => 拒绝 ------------
    assert CRITICAL_GATE.decide(CRITICAL_GATE.threshold) is True
    assert CRITICAL_GATE.decide(CRITICAL_GATE.threshold - 1e-4) is False
    assert CREATIVE_GATE.decide(CREATIVE_GATE.threshold) is True
    assert CREATIVE_GATE.decide(CREATIVE_GATE.threshold - 1e-4) is False

    # ---- (h) 两类 agent 的发布判定：指标选择决定结论 -----------------------
    s, w = gate_report["stable"], gate_report["wild"]
    # 稳健型：两种门禁都过；抽奖型：只能过创意门禁，绝不能进关键决策
    assert s["critical_pass"] and s["creative_pass"], "稳健型 agent 应双门禁通过"
    assert (not w["critical_pass"]) and w["creative_pass"], \
        "抽奖型 agent 应被关键决策门禁拒绝、但通过创意门禁"
    # 核心结论：上限指标看两者差距很小，一致性指标看两者天差地别
    assert abs(s["pass_at_3"] - w["pass_at_3"]) < 0.10, \
        "pass@3（上限）下两个 agent 应当难以区分"
    assert s["pass_pow_3"] - w["pass_pow_3"] > 0.40, \
        "pass^3（一致性）下两个 agent 的差距必须拉开"


# ---------------------------------------------------------------------------
# 8. 演示入口：四个实验 + 自检
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 70)
    print("EVAL LAB 01 · 指标体系：pass@k / pass^k / 一致性"
          "（纯标准库 / 固定种子 / 可复现）")
    print("=" * 70)

    # ---------- [1/4] 实验 1：结果矩阵，上限与一致性的差距 ----------
    print("\n[1/4] 实验 1：40 个任务 × 8 次重复运行——同一个 agent，两种问法")
    print("      pass@k = 前 k 次至少成功 1 次的任务占比（它能不能做到）")
    print("      pass^k = 前 k 次每次都成功的任务占比（它敢不敢被连续使用）")
    hetero_tasks = make_hetero_tasks(40)
    agent_h = MockAgent("hetero-agent", seed=SEED)
    hetero_matrix = run_matrix(agent_h, hetero_tasks, k_runs=8)
    hetero_rows = matrix_metrics(hetero_matrix)
    print(f"\n   {'k':>2} | {'pass@k(上限)':>12} | {'pass^k(一致性)':>14} | {'差距':>8}")
    print("   " + "-" * 48)
    for r in hetero_rows:
        print(f"   {r['k']:>2} | {r['pass_at_k']:>11.1%} | "
              f"{r['pass_pow_k']:>13.1%} | {r['gap']:>7.1%}")
    print(f"\n   k=1 时两个指标完全相同（都等于平均单次成功率 "
          f"{hetero_rows[0]['pass_at_k']:.1%}）；")
    print(f"   k=8 时差距拉开到 {hetero_rows[-1]['gap']:.1%}——"
          "只看 pass@1 的团队永远看不见一致性塌陷。")
    # 暴露「最弱一环」：均值掩盖的东西
    worst = min(hetero_tasks, key=lambda t: t.p)
    worst_row = hetero_matrix[hetero_tasks.index(worst)]
    print(f"   最弱任务 {worst.task_id}（p={worst.p:.2f}）8 次只成功 "
          f"{sum(worst_row)} 次——平均通过率掩盖最弱一环，"
          "线上事故专挑这种任务下手。")

    # ---------- [2/4] 实验 2：p=0.8 —— 「多试几次」不是特性 ----------
    print("\n[2/4] 实验 2：单次成功率 p=0.8 的 agent——用户不接受『多试几次』")
    p_demo, n_demo, k_runs_demo = 0.8, 4000, 8
    uniform_tasks = make_uniform_tasks(n_demo, p_demo)
    agent_u = MockAgent("uniform-agent", seed=SEED + 2)
    homog_matrix = run_matrix(agent_u, uniform_tasks, k_runs_demo)
    homog_rows = matrix_metrics(homog_matrix)
    print(f"\n   模拟 {n_demo} 个同质任务 × {k_runs_demo} 次运行"
          f"（固定种子），pass^k 的经验值与理论值 p^k 对照：")
    print(f"   {'k':>2} | {'pass^k 理论':>11} | {'pass^k 经验':>11}")
    print("   " + "-" * 34)
    for k, r in enumerate(homog_rows, start=1):
        print(f"   {k:>2} | {p_demo ** k:>10.1%} | {r['pass_pow_k']:>10.1%}")
    print(f"\n   pass^k 严格单调下降：『单次 80% 准确』的 agent，"
          f"连续 8 次全对的概率只剩 {p_demo ** 8:.1%}。")
    print(f"   对比上限指标：pass@8 = {analytic_pass_at_k(p_demo, 8):.4%}"
          "——评测里『它好像总能做对』。")
    print(f"   而用户连续使用 10 次，至少踩坑一次的概率 = 1-0.8^10 = "
          f"{1 - p_demo ** 10:.1%}。这就是『重试不是特性』的数学证明。")

    # ---------- [3/4] 实验 3：两类 agent × 两个门禁 ----------
    print("\n[3/4] 实验 3：同一个评测，两种产品形态，两个相反的发布结论")
    print(f"      {CRITICAL_GATE.name}：{CRITICAL_GATE.why}")
    print(f"      {CREATIVE_GATE.name}：{CREATIVE_GATE.why}")
    stable_report = evaluate_against_gates(
        MockAgent("稳健型 A", seed=SEED + 10), make_stable_tasks(30), k_runs=8)
    wild_report = evaluate_against_gates(
        MockAgent("抽奖型 B", seed=SEED + 20), make_wild_tasks(30), k_runs=8)
    gate_report = {"stable": stable_report, "wild": wild_report}

    def flag(ok: bool) -> str:
        return "✅ 通过" if ok else "❌ 拒绝"

    print(f"\n   {'agent':<8} | {'平均单次成功率':>14} | {'pass^3 估计':>11} | "
          f"{'pass@3 估计':>11} | {'关键决策门禁':>12} | 创意门禁")
    print("   " + "-" * 86)
    for rep in (stable_report, wild_report):
        print(f"   {rep['agent']:<8} | {rep['mean_p']:>13.1%} | "
              f"{rep['pass_pow_3']:>10.1%} | {rep['pass_at_3']:>10.1%} | "
              f"{flag(rep['critical_pass']):>11} | {flag(rep['creative_pass'])}")
    print(f"\n   关键观察：按上限指标 pass@3，两者只差 "
          f"{abs(stable_report['pass_at_3'] - wild_report['pass_at_3']):.1%}，"
          "几乎『看不出区别』；")
    print(f"   按一致性指标 pass^3，两者相差 "
          f"{stable_report['pass_pow_3'] - wild_report['pass_pow_3']:.1%}，"
          "一个能进关键决策，一个绝对不能。")
    print("   结论：不是『谁的分数高谁上线』，而是『产品容错度决定看哪个指标』。")

    # ---------- [4/4] 实验 4：无偏 vs 朴素，枚举当裁判 ----------
    print("\n[4/4] 实验 4：无偏估计 vs 朴素估计——暴力枚举一锤定音")
    cmp8 = compare_estimators(SAMPLE_OUTCOMES, k=3)
    c, n = cmp8["c"], cmp8["n"]
    print(f"\n   观测数据：{n} 次运行成功 {c} 次，取 k={cmp8['k']}。"
          f"枚举全部 C({n},{cmp8['k']})={math.comb(n, cmp8['k'])} 种组合得真值：")
    print(f"   pass@3 枚举真值 = {cmp8['exact_at']:.4f} | "
          f"pass^3 枚举真值 = {cmp8['exact_pow']:.4f}")
    print(f"\n   {'估计方法':<26} | {'pass@3':>8} | {'pass^3':>8} | 偏差方向")
    print("   " + "-" * 66)
    print(f"   {'无偏（无放回组合）':<26} | {cmp8['unbiased_at']:>8.4f} | "
          f"{cmp8['unbiased_pow']:>8.4f} | 与枚举一致 ✔")
    print(f"   {'朴素·有放回公式':<26} | {cmp8['naive_at']:>8.4f} | "
          f"{cmp8['naive_pow']:>8.4f} | 低估上限 / 高估一致性")
    print(f"   {'朴素·任何一次成功就算过':<24} | {cmp8['naive_all_n']:>8.4f} | "
          f"{'—':>8} | 实际报的是 pass@{n}，高估")
    print(f"\n   危险方向在 pass^k：朴素公式把连续成功率 "
          f"{cmp8['unbiased_pow']:.4f} 高估成 {cmp8['naive_pow']:.4f}"
          f"（+{(cmp8['naive_pow'] / cmp8['unbiased_pow'] - 1):.0%}）。"
          "按它做发布决策，等于把『不稳』误判成『稳』。")

    # ---------- 自检 ----------
    print("\n[自检] 运行核心断言（估计器正确性 / 偏差方向 / pass^k<=pass@k / "
          "p^k 吻合 / 单调性 / 门禁逻辑 / 发布判定）...")
    run_self_checks(hetero_rows, [t.p for t in hetero_tasks],
                    homog_rows, p_demo, gate_report)
    print(f"   (a) 无偏估计与暴力枚举精确一致 ✔")
    print(f"   (b) 朴素估计偏差方向与幅度已被枚举钉死 ✔")
    print(f"   (c) 全部 k 上 pass^k <= pass@k ✔")
    print(f"   (d) 经验 pass^k 与理论 p^k 在 0.03 内吻合（n={n_demo}）✔")
    print(f"   (e) p=0.8 的 pass^1..pass^8 严格单调下降，pass^8="
          f"{p_demo ** 8:.3f} ✔")
    print(f"   (f) 上限与一致性的差距随 K 单调拉开：k=1 差距 0.0% -> "
          f"k=8 差距 {hetero_rows[-1]['gap']:.1%} ✔")
    print(f"   (g) 门禁边界语义（>= 阈值即通过）正确 ✔")
    print(f"   (h) 稳健型双门禁通过；抽奖型被关键决策门禁拒绝 ✔")
    print("\n✅ 自检通过：eval_lab01_metric_system.py 全部断言成立")


if __name__ == "__main__":
    main()
