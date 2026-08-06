#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab08_statistics_ci.py — 评测统计学：置信区间 / 样本量 / 显著性
========================================================================

【实验目的】
    「v2 通过率 85%，v1 通过率 82%，所以 v2 更好？」——不一定。通过率是从有限
    评测集上算出来的统计量，会随抽样波动；没有误差范围的对比结论可能只是噪声。
    本实验用确定性模拟回答评测人的三个核心问题：
        1) 如何给比例（通过率）加上「误差范围」——置信区间（CI）：
           手写 Wilson 区间，对比朴素 Wald 区间在小样本下的越界与低覆盖问题；
        2) 多大的差异才算「超过统计噪声」——显著性判断：
           配对设计（两版本跑同一批评测集）+ 差异 CI + McNemar 检验；
        3) 要可靠检出某个差异，评测集需要多大——样本量 / 功效分析：
           实现双比例样本量公式并打印速查表。
    全部结论用「覆盖率模拟」（固定种子重复 1000 次实验）来验证：
    声称 95% 的区间，是否真的在约 95% 的实验里盖住真值。

【对应章节】
    本特辑第 E09 章 · 评估的统计学基础（与主仓库 lab05 评估 harness 的
    「指标聚合」衔接：聚合出通过率之后，下一步就是给它加上统计学的严谨）

【核心概念】
    - 抽样波动: 通过率 p̂ 是随机变量。n 条样本时 p̂ 的标准误约为 √(p(1-p)/n)，
      差异小于约 2 个标准误时，肉眼看到的「提升」无法与噪声区分。
    - Wald 区间: p̂ ± z·√(p̂(1-p̂)/n)。公式最简单，但小样本/极端比例时
      会算出负数下界或 >1 的上界，且真实覆盖率远低于名义水平。
    - Wilson 区间（score interval）: 对 p̂ 做收缩修正，端点永远落在 [0,1]，
      小样本覆盖率明显更好，是上报通过率 CI 的默认推荐。
    - 覆盖率（coverage）: 评价 CI 好坏的唯一硬指标——重复做实验，区间盖住
      真值的频率。声称 95% 的 CI 若实际只覆盖 46%，就是「假安全感」。
    - Bootstrap: 不依赖分布公式，对已有样本有放回重采样，用统计量分布的
      分位数直接构造 CI；适用于几乎任何指标（均值、分位数、差值……）。
    - 显著性水平 α / 功效 1-β / 最小可检出差异 δ: 样本量由三者共同决定。
      δ 减半，所需样本量约翻两番（1/δ² 关系）。
    - 配对设计: 两个版本跑同一批案例，案例难度这一最大噪声源被「钉死」，
      只剩「同一案例上的版本差异」，检出同样 δ 所需样本量显著更小
      （经典检验为 McNemar，只关心两版本判定不一致的案例）。

【如何运行】
    cd evals-special/labs && python3 eval_lab08_statistics_ci.py
    （纯 Python 标准库，零依赖，固定随机种子，任何机器结果完全一致）

【思考题（面试延伸）】
    1. 为什么 Wald 区间在 n 小或 p̂ 接近 0/1 时不可信？Wilson 区间凭什么更好？
       如果 k=0（全失败）或 k=n（全通过），Wald 给出什么区间？这合理吗？
    2. 门禁要求「通过率提升 ≥3% 才准发布」，你如何确定评测集大小？样本不足时
       会分别犯什么错（漏放真提升 / 误放噪声）？功效（power）描述的是哪一种？
    3. 为什么「两版本跑同一批案例」的配对设计比各自独立抽样更灵敏？McNemar
       检验为什么只看不一致样本（A 对 B 错、A 错 B 对）？
    4. Bootstrap CI 与公式法 CI 各自的假设是什么？重采样次数 B 太少会引入
       什么误差？样本非独立（同题多轮对话）时 Bootstrap 应该怎么改？
    5. CI 很宽但业务要结论，你如何向产品经理解释「统计上尚不可区分」，
       并给出可执行的下一步（加样本 / 换配对设计 / 接受更小的检验精度）？
"""

from __future__ import annotations

import math
import random
import statistics
from statistics import NormalDist
from typing import Callable, List, Sequence, Tuple

# ---------------------------------------------------------------------------
# 全局固定种子：每个实验段使用独立的随机源，互不干扰，整机结果确定可复现
# ---------------------------------------------------------------------------
SEED_COVERAGE_MAIN = 801      # 覆盖率主模拟（n=50, p=0.70）
SEED_COVERAGE_EXTREME = 802   # 覆盖率极端场景（n=15, p=0.95）
SEED_BOOT_DATA = 803          # Bootstrap 演示数据的生成
SEED_BOOT_RESAMPLE = 42       # Bootstrap 重采样本身
SEED_CASES = 6                # 配对实验的评测集生成


# ---------------------------------------------------------------------------
# 1. 基础工具：z 值与二项抽样
# ---------------------------------------------------------------------------
# 置信区间与显著性检验都依赖标准正态分布的分位数。Python 标准库的
# statistics.NormalDist 自带精确的 cdf / inv_cdf，无需手写近似公式，
# 也无需任何第三方依赖。

def z_value(alpha: float) -> float:
    """双侧检验/区间在显著性水平 alpha 下的临界 z 值。
    例如 alpha=0.05 -> z≈1.95996（95% 区间把两侧各 2.5% 的尾部切掉）。"""
    return NormalDist().inv_cdf(1.0 - alpha / 2.0)


def bernoulli_count(rng: random.Random, n: int, p: float) -> int:
    """模拟 n 次成功率为 p 的独立伯努利试验，返回成功次数 k。
    这就是「n 条评测用例、单条通过率 p」时通过条数的生成过程。"""
    return sum(1 for _ in range(n) if rng.random() < p)


# ---------------------------------------------------------------------------
# 2. 比例的两种置信区间：朴素 Wald vs Wilson（score）
# ---------------------------------------------------------------------------
# 评测最常见的指标是通过率 = k/n。问题：这个点估计离真值有多远？
# 答案是一个区间 [lo, hi]，并声明「该构造方法以 1-alpha 的概率盖住真值」。

def wald_interval(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wald 区间：p̂ ± z·SE(p̂)。
    教科书最简单的形式，但有两大硬伤（本实验都会用断言钉住）：
      1) 小样本/极端比例时上下界会越出 [0,1]（概率怎么能为负？）；
      2) k=0 或 k=n 时退化成单点区间 [0,0]/[1,1]，
         等于宣称「绝对确定」，这是典型的假安全感。"""
    z = z_value(alpha)
    p_hat = k / n
    half = z * math.sqrt(p_hat * (1.0 - p_hat) / n)
    return p_hat - half, p_hat + half


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wilson score 区间：解「|p̂-p| ≤ z·√(p(1-p)/n)」这个关于 p 的不等式得到。
    直观理解：把 p̂ 向 1/2 做了一点收缩（样本越少收缩越强），并据此重算半径。
    性质：端点永远在 [0,1] 内；k=0 时上界 >0、k=n 时下界 <1，
    诚实地承认「没见过的失败/成功仍可能存在」；小样本覆盖率远优于 Wald。
    这也是上报评测通过率 CI 时的默认推荐实现。"""
    z = z_value(alpha)
    p_hat = k / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p_hat * (1.0 - p_hat) / n + z * z / (4.0 * n * n)) / denom
    # 理论上 Wilson 端点必在 [0,1] 内；这里的钳位只是抹掉浮点误差
    # （如 k=0 时 center-half 理论上恰为 0，浮点下可能是 -2.8e-17）。
    return max(0.0, center - half), min(1.0, center + half)


# ---------------------------------------------------------------------------
# 3. 覆盖率模拟：判断 CI 好坏的唯一硬指标
# ---------------------------------------------------------------------------
# 区间构造方法好不好，不看公式漂不漂亮，而看：固定真值 p，重复做实验，
# 每次用该方法算一个 95% CI，长期来看有多少比例盖住了 p。
# 名义 95% 的区间若实际覆盖率只有约 54%（Wald 在 n=15、p=0.95 的理论值），
# 基于它做的所有门禁决策都建立在假安全感之上。

def simulate_coverage(interval_fn: Callable[[int, int, float], Tuple[float, float]],
                      n: int, p_true: float, experiments: int,
                      alpha: float, seed: int) -> float:
    """重复 experiments 次「抽样 -> 算区间 -> 检查是否盖住真值」，返回覆盖率。
    用独立的 Random(seed)，保证该段结果与主流程其它随机实验互不耦合。"""
    rng = random.Random(seed)
    covered = 0
    for _ in range(experiments):
        k = bernoulli_count(rng, n, p_true)
        lo, hi = interval_fn(k, n, alpha)
        if lo <= p_true <= hi:
            covered += 1
    return covered / experiments


# ---------------------------------------------------------------------------
# 4. Bootstrap 置信区间：不推公式，直接重采样
# ---------------------------------------------------------------------------
# 思想：手上这 n 条样本就是我们对总体的最佳猜测；那就有放回地反复重采样，
# 看统计量（这里是通过率）会如何波动，直接取波动分布的分位数当区间端点。
# 优点：几乎不挑统计量（均值、中位数、两版本差值都行）；
# 代价：结果依赖样本的代表性（iid 假设），且 B 太小会引入蒙特卡洛误差。
# 注意重采样必须「成对/按抽样单元」进行——本实验后文的配对 bootstrap
# 重采样的是 (v1 结果, v2 结果) 整对，而不是各自打乱，否则案例级相关性被破坏。

def _percentile(sorted_vals: Sequence[float], q: float) -> float:
    """在升序序列上取 q 分位数（线性插值法）。"""
    pos = q * (len(sorted_vals) - 1)
    lo_i = math.floor(pos)
    hi_i = math.ceil(pos)
    if lo_i == hi_i:
        return sorted_vals[lo_i]
    frac = pos - lo_i
    return sorted_vals[lo_i] * (1.0 - frac) + sorted_vals[hi_i] * frac


def bootstrap_ci(data: Sequence[float], stat_fn: Callable[[List[float]], float],
                 n_boot: int, alpha: float, seed: int) -> Tuple[float, float]:
    """百分位法 bootstrap CI：重采样 n_boot 次，每次算一个统计量，
    取 [alpha/2, 1-alpha/2] 分位数。固定 seed -> 完全可复现。"""
    rng = random.Random(seed)
    n = len(data)
    stats: List[float] = []
    for _ in range(n_boot):
        sample = [data[rng.randrange(n)] for _ in range(n)]
        stats.append(stat_fn(sample))
    stats.sort()
    return _percentile(stats, alpha / 2.0), _percentile(stats, 1.0 - alpha / 2.0)


# ---------------------------------------------------------------------------
# 5. 样本量计算器：做实验之前先算清楚要多少样本
# ---------------------------------------------------------------------------
# 门禁场景：基线通过率 p，要求能检出最小 δ 的提升，误报率 α、功效 1-β。
# 双比例、两组等样本量的经典公式（每组合计）：
#     n = [ z_{1-α/2}·√(2·p̄(1-p̄)) + z_{1-β}·√(p1(1-p1)+p2(1-p2)) ]² / δ²
# 其中 p1=p、p2=p+δ、p̄=(p1+p2)/2。第一项管「误报控制」，第二项管「漏报控制」。
# 关键直觉：n 与 1/δ² 成正比——想检出的差异减半，样本量要翻约 4 倍。
# 这就是「为什么 +1% 的门禁需要上万条评测集」的数学根源。

def required_sample_size_two_proportions(p_baseline: float, delta: float,
                                         alpha: float = 0.05,
                                         power: float = 0.80) -> int:
    """返回检出「p_baseline -> p_baseline+delta」差异所需的每组样本数（向上取整）。"""
    if not (0.0 < p_baseline < 1.0) or not (0.0 < delta < 1.0 - p_baseline):
        raise ValueError("需要 0 < p_baseline < 1 且 0 < delta < 1 - p_baseline")
    z_a = z_value(alpha)                 # 控制误报（第一类错误）
    z_b = NormalDist().inv_cdf(power)    # 控制漏报（第二类错误）
    p1, p2 = p_baseline, p_baseline + delta
    p_bar = (p1 + p2) / 2.0
    numerator = (z_a * math.sqrt(2.0 * p_bar * (1.0 - p_bar))
                 + z_b * math.sqrt(p1 * (1.0 - p1) + p2 * (1.0 - p2))) ** 2
    return math.ceil(numerator / (delta ** 2))


def print_sample_size_table(p_baseline: float, deltas: Sequence[float],
                            alpha: float = 0.05, power: float = 0.80) -> None:
    """打印样本量速查表：门禁评审时直接拿这张表谈「要检出 δ，得备多少用例」。"""
    print(f"   基线通过率 p={p_baseline:.2f}，α={alpha}，功效={power}（双侧检验）")
    for d in deltas:
        n = required_sample_size_two_proportions(p_baseline, d, alpha, power)
        print(f"   - 想检出 +{d:.0%} 的差异：每组需要 {n:>6d} 条样本")


# ---------------------------------------------------------------------------
# 6. 被测系统的确定性替身 MockLLM + 配对版本对比
# ---------------------------------------------------------------------------
# 场景：v2 prompt 宣称比 v1 通过率提升约 3 个百分点，门禁要不要放行？
# 评测纪律：两个版本跑同一批案例（配对设计）。案例难度是通过率最大的
# 噪声源；配对把难度因素在版本间完全对齐，剩下的方差只来自
# 「同一案例上的版本差异」，因此远比各自独立抽样灵敏。
#
# MockLLM 的接口与真实 chat 客户端同构（chat(messages) -> str），
# 将来可无缝替换成真实 API 客户端。它的「能力」由版本与案例决定：
#   - 每条案例自带潜在通过率 p（难度）和一个录制好的随机数 u（相当于
#     把采样结果固化进 fixture）：回答正确 ⇔ u < p + 版本增量。
#   - v1 增量恒为 0；v2 在 80% 案例上 +0.04（修好一批），
#     在 20% 案例上 -0.01（改坏一小撮）——期望提升 0.8*0.04-0.2*0.01 = +3%。
#   同一个 u 作用于两个版本，保证观测到的差异 100% 来自版本本身。

IMPROVED_FRAC = 0.8        # v2 相对 v1 有改善的案例占比
DELTA_IMPROVED = +0.04     # 改善案例上的通过率增量
DELTA_REGRESSED = -0.01    # 回归案例上的通过率增量（新 prompt 改坏旧场景）


class MockLLM:
    """确定性被测系统。接口 chat() 与真实 LLM 客户端同构，可直接替换。"""

    def __init__(self, name: str, prompt_version: str = "v1"):
        assert prompt_version in ("v1", "v2"), "仅支持 v1/v2 两个 prompt 版本"
        self.name = name
        self.prompt_version = prompt_version

    def chat(self, messages: List[dict]) -> str:
        """读入最后一条消息里附带的案例元信息（p/u/improved），
        按「u < p + 版本增量」给出 PASS/FAIL。"""
        meta = messages[-1].get("meta", {})
        delta = 0.0
        if self.prompt_version == "v2":
            delta = DELTA_IMPROVED if meta["improved"] else DELTA_REGRESSED
        return "PASS" if meta["u"] < meta["p"] + delta else "FAIL"


def make_cases(rng: random.Random, n: int, start_id: int = 0) -> List[dict]:
    """生成 n 条评测案例。p 在 0.55~0.95 均匀分布（平均 0.75），
    u 与 improved 一并录制，保证任何版本、任何次运行看到完全相同的世界。"""
    cases = []
    for i in range(n):
        cases.append({
            "id": f"case-{start_id + i:04d}",
            "text": f"任务 #{start_id + i}",
            "p": 0.55 + 0.40 * rng.random(),     # 案例难度（潜在通过率）
            "u": rng.random(),                   # 录制好的采样随机数
            "improved": rng.random() < IMPROVED_FRAC,
        })
    return cases


def run_version(model: MockLLM, cases: List[dict]) -> List[int]:
    """让一个版本跑完整套评测集，返回 0/1 结果序列（顺序与 cases 对齐）。"""
    results = []
    for c in cases:
        reply = model.chat([{
            "role": "user",
            "content": c["text"],
            "meta": {"p": c["p"], "u": c["u"], "improved": c["improved"]},
        }])
        results.append(1 if reply == "PASS" else 0)
    return results


def paired_diff_ci(diffs: Sequence[float], alpha: float = 0.05
                   ) -> Tuple[float, float, float, float]:
    """配对差异的正态近似 CI。
    输入 diffs[i] = v2 结果 - v1 结果（同一条案例，取值 -1/0/+1），
    对「差异均值」做区间估计：均值 ± z·(样本标准差/√n)。
    返回 (均值, 下界, 上界, 标准误)。"""
    n = len(diffs)
    m = statistics.fmean(diffs)
    se = statistics.stdev(diffs) / math.sqrt(n)
    z = z_value(alpha)
    return m, m - z * se, m + z * se, se


def mcnemar_test(diffs: Sequence[float]) -> Tuple[int, int, float, float]:
    """McNemar 检验：配对二元结果的经典显著性检验。
    只统计两版本判定不一致的案例：b = v1 错 v2 对，c = v1 对 v2 错。
    两版本一致（都对/都错）的案例对「谁更好」没有信息量，直接丢弃——
    这正是配对检验比非配对检验灵敏的原因。
    统计量 z = (b-c)/√(b+c)，双侧 p 值用标准正态计算。"""
    b = sum(1 for d in diffs if d > 0)
    c = sum(1 for d in diffs if d < 0)
    if b + c == 0:
        return b, c, 0.0, 1.0
    z = (b - c) / math.sqrt(b + c)
    p_value = 2.0 * (1.0 - NormalDist().cdf(abs(z)))
    return b, c, z, p_value


def significance_verdict(lo: float, hi: float, alpha: float) -> str:
    """根据差异 CI 与 0 的关系给出业务化结论。
    - 区间整体 >0：提升超过噪声，可以放行；
    - 区间包含 0：不可区分，结论只能是「证据不足」，而不是「没有差异」；
    - 区间整体 <0：显著变差，直接拦截。"""
    if lo > 0:
        return f"显著（{1 - alpha:.0%} 置信下 v2 优于 v1，可放行）"
    if hi < 0:
        return f"显著（{1 - alpha:.0%} 置信下 v2 劣于 v1，应拦截）"
    return "不显著（差异未超过统计噪声，证据不足，不能下结论）"


# ---------------------------------------------------------------------------
# 7. 自检：所有断言都指向本实验的核心结论
# ---------------------------------------------------------------------------

def run_self_checks(ctx: dict) -> None:
    # (a) Wilson 区间边界永远合法：多组 (n, k) 全面扫描，0 ≤ lo ≤ hi ≤ 1
    for n in (10, 25, 50):
        for k in range(n + 1):
            lo, hi = wilson_interval(k, n)
            assert 0.0 <= lo <= hi <= 1.0, \
                f"Wilson 越界: n={n}, k={k}, [{lo}, {hi}]"

    # (b) Wilson 在极端样本下「诚实」：全失败时仍承认成功可能存在，反之亦然
    lo0, hi0 = wilson_interval(0, 20)
    assert lo0 == 0.0 and hi0 > 0.0, "k=0 时 Wilson 上界应 >0（承认未见过的可能）"
    lon, hin = wilson_interval(20, 20)
    assert hin == 1.0 and lon < 1.0, "k=n 时 Wilson 下界应 <1"

    # (c) Wald 的两大硬伤必须被复现：小样本越界 + 极端样本退化成假安全感
    wl, _ = wald_interval(1, 10)
    assert wl < 0.0, "Wald 在 n=10,k=1 时应当算出负下界（越界问题）"
    _, wh = wald_interval(9, 10)
    assert wh > 1.0, "Wald 在 n=10,k=9 时应当算出 >1 的上界"
    assert wald_interval(0, 10) == (0.0, 0.0), "k=0 时 Wald 退化成单点 [0,0]"

    # (d) 覆盖率是 CI 的硬道理：
    #     Wilson 95% CI 的模拟覆盖率必须落在名义水平附近 [0.92, 0.98]；
    #     Wald 在极端场景（n=15, p=0.95）严重欠覆盖（理论值约 54%）；
    #     同一场景下 Wilson 覆盖率必须高于 Wald。
    assert 0.92 <= ctx["wilson_cov_main"] <= 0.98, \
        f"Wilson 覆盖率 {ctx['wilson_cov_main']} 偏离名义 95% 太多"
    assert ctx["wald_cov_extreme"] < 0.70, \
        "Wald 在极端场景的覆盖率应当远低于名义水平"
    assert ctx["wilson_cov_extreme"] >= 0.90, "Wilson 在极端场景仍应接近名义水平"
    assert ctx["wilson_cov_extreme"] > ctx["wald_cov_extreme"], \
        "同场景下 Wilson 覆盖率应高于 Wald"

    # (e) Bootstrap：同种子严格可复现；区间非退化且包含点估计与真值
    assert ctx["boot_ci_run1"] == ctx["boot_ci_run2"], "相同种子 bootstrap 必须可复现"
    blo, bhi = ctx["boot_ci_run1"]
    assert blo < bhi, "bootstrap 区间不应退化"
    assert blo <= ctx["boot_p_hat"] <= bhi, "bootstrap 区间应包含样本点估计"
    assert blo <= ctx["boot_p_true"] <= bhi, "本例 bootstrap 区间应覆盖真值 0.7"

    # (f) 样本量公式：经典数值校验 + 三重单调性 + 与配对实验的呼应
    n_check = required_sample_size_two_proportions(0.50, 0.05)
    assert n_check == 1565, f"p=0.50, δ=5% 的每组样本量应为 1565，实际 {n_check}"
    deltas = [0.01, 0.02, 0.03, 0.05]
    ns = [required_sample_size_two_proportions(0.75, d) for d in deltas]
    assert all(ns[i] > ns[i + 1] for i in range(len(ns) - 1)), \
        "样本量应随 δ 减小而严格增大"
    powers = [required_sample_size_two_proportions(0.75, 0.03, power=pw)
              for pw in (0.70, 0.80, 0.90)]
    assert powers[0] < powers[1] < powers[2], "样本量应随功效提高而严格增大"
    alphas = [required_sample_size_two_proportions(0.75, 0.03, alpha=a)
              for a in (0.10, 0.05, 0.01)]
    assert alphas[0] < alphas[1] < alphas[2], "样本量应随 α 收紧而严格增大"
    assert required_sample_size_two_proportions(0.75, 0.03) > 2000, \
        "独立双抽样检出 3% 需要 >2000/组——反衬配对设计用 2000 对即可检出"

    # (g) 配对版本对比的核心结论（对应门禁统计口径）：
    #     3% 的真实提升，在 N=100 下 CI 包含 0 -> 不可判；
    #     同一批评测集扩到 N=2000 后 CI 整体 >0 -> 可判；
    #     区间宽度随 √n 收缩；McNemar 与 CI 结论一致。
    assert ctx["lo100"] <= 0.0 <= ctx["hi100"], \
        "N=100 时差异 CI 应包含 0：3% 差异在小样本下不可判"
    assert ctx["lo2000"] > 0.0, "N=2000 时差异 CI 应整体 >0：3% 差异可判"
    assert ctx["lo2000_boot"] > 0.0, "N=2000 配对 bootstrap CI 同样应整体 >0"
    assert ctx["halfwidth_2000"] * 2.0 < ctx["halfwidth_100"], \
        "样本量 x20 后区间半宽应明显收缩（约 1/√20）"
    assert 0.02 <= ctx["mean_diff_2000"] <= 0.04, \
        "N=2000 时观测到的平均差异应接近设计的 +3%"
    assert ctx["mcnemar_p_2000"] < 0.05, "N=2000 时 McNemar 应判显著"
    assert ctx["mcnemar_p_100"] > 0.05, "N=100 时 McNemar 应判不显著"


# ---------------------------------------------------------------------------
# 8. 演示入口：分段运行并打印结论
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 68)
    print("LAB 08 · 评测统计学：置信区间 / 样本量 / 显著性（纯标准库/确定性）")
    print("=" * 68)

    # ---- [1/6] Wald vs Wilson：同一次抽样，两种区间的差距 ----
    print("\n[1/6] 同一次抽样下的两种 CI（n=10，95% 置信）：")
    print("   k/n      Wald 区间            Wilson 区间")
    for k in (0, 1, 2, 5, 8, 9, 10):
        wl, wh = wald_interval(k, 10)
        sl, sh = wilson_interval(k, 10)
        flag = "  <- Wald 越界!" if (wl < 0 or wh > 1) else ""
        print(f"   {k:>2}/10   [{wl:+.3f}, {wh:.3f}]      "
              f"[{sl:.3f}, {sh:.3f}]{flag}")
    print("   结论：Wald 会把概率算成负数/超过 1，且 k=0、k=10 时给出")
    print("   单点区间（假安全感）；Wilson 端点永远合法，应作为默认上报口径。")

    # ---- [2/6] 覆盖率模拟：95% CI 真的覆盖 95% 吗 ----
    print("\n[2/6] 覆盖率模拟（固定种子，各重复 1000 次实验）：")
    wilson_cov_main = simulate_coverage(
        wilson_interval, n=50, p_true=0.70, experiments=1000,
        alpha=0.05, seed=SEED_COVERAGE_MAIN)
    wald_cov_main = simulate_coverage(
        wald_interval, n=50, p_true=0.70, experiments=1000,
        alpha=0.05, seed=SEED_COVERAGE_MAIN)
    print(f"   主场景 n=50, p=0.70 : Wilson 覆盖率={wilson_cov_main:.3f}，"
          f"Wald 覆盖率={wald_cov_main:.3f}（名义 0.95）")
    wilson_cov_extreme = simulate_coverage(
        wilson_interval, n=15, p_true=0.95, experiments=1000,
        alpha=0.05, seed=SEED_COVERAGE_EXTREME)
    wald_cov_extreme = simulate_coverage(
        wald_interval, n=15, p_true=0.95, experiments=1000,
        alpha=0.05, seed=SEED_COVERAGE_EXTREME)
    print(f"   极端 n=15, p=0.95  : Wilson 覆盖率={wilson_cov_extreme:.3f}，"
          f"Wald 覆盖率={wald_cov_extreme:.3f}")
    print("   结论：极端场景下 Wald 名义 95% 实际只盖住约一半实验——")
    print("   用它做门禁，等于拿假安全感在赌发布决策。")

    # ---- [3/6] Bootstrap：不推公式，重采样直接分位数 ----
    print("\n[3/6] Bootstrap 置信区间（n=200，真值 p=0.70，B=2000 次重采样）：")
    rng_boot = random.Random(SEED_BOOT_DATA)
    boot_data = [1.0 if rng_boot.random() < 0.70 else 0.0 for _ in range(200)]
    boot_p_hat = statistics.fmean(boot_data)
    k_boot = int(sum(boot_data))
    boot_ci_1 = bootstrap_ci(boot_data, statistics.fmean,
                             n_boot=2000, alpha=0.05, seed=SEED_BOOT_RESAMPLE)
    boot_ci_2 = bootstrap_ci(boot_data, statistics.fmean,
                             n_boot=2000, alpha=0.05, seed=SEED_BOOT_RESAMPLE)
    wilson_ref = wilson_interval(k_boot, 200)
    print(f"   样本通过率 p̂={boot_p_hat:.3f}")
    print(f"   Wilson   CI: [{wilson_ref[0]:.3f}, {wilson_ref[1]:.3f}]")
    print(f"   Bootstrap CI: [{boot_ci_1[0]:.3f}, {boot_ci_1[1]:.3f}]")
    print(f"   同种子重跑 bootstrap：{boot_ci_2[0]:.3f}, {boot_ci_2[1]:.3f}"
          f"（与第一次完全一致 -> 可复现）")
    print("   结论：bootstrap 与公式法区间高度接近；它的价值在于对任意")
    print("   统计量（如两版本配对差值）都能照样构造 CI。")

    # ---- [4/6] 样本量计算：门禁之前先算要多少用例 ----
    print("\n[4/6] 样本量速查表（独立双抽样、双侧检验）：")
    print_sample_size_table(p_baseline=0.75, deltas=(0.01, 0.02, 0.03, 0.05))
    n_check = required_sample_size_two_proportions(0.50, 0.05)
    print(f"   公式校验：p=0.50、δ=5%、α=0.05、功效 0.8 -> 每组 {n_check} 条")
    print("   结论：n ∝ 1/δ²。想检出的差异减半，样本量翻约 4 倍——")
    print("   这就是 '+1% 门禁' 需要上万条用例的数学根源。")

    # ---- [5/6] 配对版本对比：3% 差异，N=100 vs N=2000 ----
    print("\n[5/6] 配对版本对比（v2 真实提升 +3%，两版本跑同一批评测集）：")
    rng_cases = random.Random(SEED_CASES)
    cases_100 = make_cases(rng_cases, 100)
    # 在同一个随机源上继续生成：2000 条集合是 100 条的超集，
    # 对应现实中「同一批评测集扩容」而不是换一批新题。
    cases_2000 = cases_100 + make_cases(rng_cases, 1900, start_id=100)

    v1 = MockLLM("mock-llm-v1", prompt_version="v1")
    v2 = MockLLM("mock-llm-v2", prompt_version="v2")

    def compare(cases: List[dict], label: str) -> dict:
        r1 = run_version(v1, cases)
        r2 = run_version(v2, cases)
        diffs = [b - a for a, b in zip(r1, r2)]
        m, lo, hi, se = paired_diff_ci(diffs)
        b, c, z_m, p_m = mcnemar_test(diffs)
        print(f"   [{label}] v1={statistics.fmean(r1):.3f} "
              f"v2={statistics.fmean(r2):.3f} 差异={m:+.3f} "
              f"95%CI=[{lo:+.3f}, {hi:+.3f}]")
        print(f"          McNemar: v2 救回 {b} 条 / 改坏 {c} 条，"
              f"z={z_m:.2f}，p={p_m:.4f}")
        print(f"          判定: {significance_verdict(lo, hi, 0.05)}")
        return {"mean": m, "lo": lo, "hi": hi, "p_mcnemar": p_m, "diffs": diffs}

    res100 = compare(cases_100, "N=100 ")
    res2000 = compare(cases_2000, "N=2000")
    # 配对 bootstrap：整对 (v1 结果, v2 结果) 一起重采样（diffs 已按案例对齐），
    # 不能把两列各自打乱——那样会破坏案例级相关性，等于退回独立抽样。
    boot_paired_2000 = bootstrap_ci(
        [float(d) for d in res2000["diffs"]],
        statistics.fmean, n_boot=800, alpha=0.05, seed=SEED_BOOT_RESAMPLE)
    print(f"          N=2000 配对 bootstrap CI: "
          f"[{boot_paired_2000[0]:+.3f}, {boot_paired_2000[1]:+.3f}]")
    print("   结论：N=100 时观测差异恰好就是 +3%（点估计完全正确！），")
    print("   但 CI 跨过 0 -> 依然不可判；扩到 N=2000 后 CI 整体 >0 -> 可判。")
    print("   点估计对了不等于能下结论。门禁里任何 '+x%' 口径")
    print("   都必须配上样本量，否则比较的只是噪声。另注意：独立双抽样")
    print("   公式要求每组 3000+ 条才能检出 3%，而配对设计 2000 对就够——")
    print("   「同一批案例跑两个版本」本身就是免费的精度提升。")

    # ---- [6/6] 自检 ----
    print("\n[6/6] 运行自检断言（核心结论全部带阈值，不是走流程）...")
    ctx = {
        "wilson_cov_main": wilson_cov_main,
        "wilson_cov_extreme": wilson_cov_extreme,
        "wald_cov_extreme": wald_cov_extreme,
        "boot_ci_run1": boot_ci_1,
        "boot_ci_run2": boot_ci_2,
        "boot_p_hat": boot_p_hat,
        "boot_p_true": 0.70,
        "lo100": res100["lo"],
        "hi100": res100["hi"],
        "lo2000": res2000["lo"],
        "hi2000": res2000["hi"],
        "lo2000_boot": boot_paired_2000[0],
        "halfwidth_100": (res100["hi"] - res100["lo"]) / 2.0,
        "halfwidth_2000": (res2000["hi"] - res2000["lo"]) / 2.0,
        "mean_diff_2000": res2000["mean"],
        "mcnemar_p_100": res100["p_mcnemar"],
        "mcnemar_p_2000": res2000["p_mcnemar"],
    }
    run_self_checks(ctx)
    print(f"   Wilson 覆盖率={wilson_cov_main:.3f} ∈ [0.92, 0.98] ✔")
    print(f"   Wald 极端场景覆盖率={wald_cov_extreme:.3f} < 0.70 ✔")
    print(f"   N=100 CI 含 0（不可判）；N=2000 CI=[{res2000['lo']:+.3f}, "
          f"{res2000['hi']:+.3f}]（可判）✔")
    print(f"   样本量公式单调性 & 经典值 1565 ✔")
    print()
    print("✅ 自检通过：eval_lab08_statistics_ci.py 全部断言成立")


if __name__ == "__main__":
    main()
