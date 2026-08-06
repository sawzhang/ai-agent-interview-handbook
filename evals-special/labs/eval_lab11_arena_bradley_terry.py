#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab11_arena_bradley_terry.py — 竞技场：Bradley-Terry / Elo / 风格控制
================================================================================

【实验目的】
    Chatbot Arena 式的「竞技场评测」用成对比较的胜负投票给模型排榜单。本实验用
    确定性模拟复现它的完整数据链路，回答五个问题：
        1) 一堆两两胜负数据，如何恢复每个模型的「潜在强度」？
           —— Bradley-Terry 极大似然估计（MM 迭代，纯标准库实现）；
        2) 在线增量评分 Elo 与 BT 是什么关系？
           —— 同一概率模型的两种算法：BT 是离线全局 MLE（与比赛顺序无关），
           Elo 是在线近似（依赖顺序与 K 因子）；
        3) 「两个模型差 0.3 分」是真实差距还是噪声？
           —— 对强度差做 Bootstrap 置信区间：区间不盖住 0 才算显著；
        4) 为什么榜单会「把长当强」？
           —— 位置偏差是「对内对称」的噪声，平衡调度即可抵消；长度偏差是模型
           间的系统性混杂，交换顺序消不掉，朴素 BT 会把冗长的弱模型顶到前列；
        5) 风格控制怎么做？
           —— 回归残差法（长度/位置作为协变量与强度一起拟合）与长度截断
           （设计侧直接移除偏差的作用空间），都能恢复真实排序。

【对应章节】
    本特辑第 E09 章 · 评估的统计学基础（竞技场：成对比较、Bradley-Terry / Elo 与风格控制；延伸阅读第 E13 章）
    （与 eval_lab04_judge_bias 衔接：那里量化单个 judge 的偏差，
      这里看偏差进入「排名系统」后被放大成什么样子、以及如何修正）

【核心概念】
    - Bradley-Terry 模型: P(i 胜 j) = γ_i / (γ_i + γ_j)，γ_i 是潜在强度。全体 γ
      同乘任意正常数不改变任何概率（尺度不变），估计时需约定归一化（本实验 Σγ=模型个数）。
    - MM 迭代: 每轮闭式更新 γ_i ← W_i / Σ_j n_ij/(γ_i+γ_j)（W_i 为总胜场，
      n_ij 为交手次数），单调抬升似然、无需梯度步长，几十轮收敛，是各类竞技场的标准算法。
    - Elo 评分: E = 1/(1+10^(-ΔR/400))，每场 R += K·(实际-期望)。本质是 BT 的
      随机梯度在线版：增量省内存，但结果依赖出场顺序与 K；BT MLE 与顺序无关。
    - Bootstrap 置信区间: 对比赛记录有放回重采样、每次重估 BT，取强度差分布的
      2.5%/97.5% 分位数。盖住 0 ⇒ 「证据不足」，而不是「两者相同」。
    - 位置偏差: 裁判偏爱先呈现的答案。对每一对是「对称」的：两种顺序出场次数
      相等时，偏差在聚合时相互抵消。
    - 长度偏差: 裁判偏爱更长的答案。长度是模型间的系统性差异（混杂变量），交换
      顺序无法抵消 —— 「又长又弱」的模型胜率被系统性抬高，朴素 BT 会把它误排到前列。
    - 风格控制: 统计侧把长度、位置作为协变量与强度一起做 logistic 回归，剥离风格
      效应后剩下的才是「纯实力」（回归残差思想）；设计侧截断输出长度，直接移除偏差作用空间。

【如何运行】
    cd evals-special/labs && python3 eval_lab11_arena_bradley_terry.py
    （纯 Python 标准库，零依赖，固定随机种子，任何机器结果完全一致）

【思考题（面试延伸）】
    1. 为什么不能直接用「原始胜率」排名？BT 的「赛程强度修正」如何通过 MM 迭代隐式
       完成？全败模型的 MLE 是什么（γ→0），实际系统如何用先验/正则避免它？
    2. 位置偏差能靠「交换顺序 + 平衡调度」抵消，长度偏差为什么不能？若评审 UI 把某
       模型固定在第一位（不平衡调度），位置偏差还会被抵消吗？
    3. style control 同时回归长度、Markdown 格式等协变量。若两个风格变量高度相关
       （多重共线性 → 方差膨胀），系数估计会怎样？如何用正则或先验缓解？
    4. 「差距 CI 盖住 0」不等于「两模型一样好」。要把 CI 宽度缩小一半，大约需要把
       对决场次增加到几倍？（提示：方差 ∝ 1/n。）
    5. Goodhart 定律：若某团队针对竞技场刷长度、刷格式，榜单会怎样？除风格控制外
       还有哪些防线（定期重标黄金集、人工抽检、对奖励信号本身做监控）？
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

LAB_NAME = "eval_lab11_arena_bradley_terry.py"

# ---------------------------------------------------------------------------
# 1. 常量与模型注册表：模拟世界的「上帝设定」
# ---------------------------------------------------------------------------
# 全部随机性都从 SEED 派生（各实验用不同偏移）：任何机器、任何时刻运行，
# 数据与结论完全一致 —— 这是「评测结论可复现」的最低要求。

SEED = 2026

POS_BIAS = 0.4     # 位置偏差强度：先呈现的答案在 logit 空间获得的加成
LEN_BIAS = 0.01    # 长度偏差强度：每多 1 个字符在 logit 空间获得的加成
LEN_SCALE = 100.0  # 回归里长度特征的缩放单位（每 100 字符），改善数值条件
LENGTH_CAP = 110   # 「长度截断」实验的答案长度上限（字符）

@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    cn: str
    quality: float    # 潜在真实质量（logit 尺度，越大越强）——只有「上帝」知道
    verbosity: float  # 冗长度风格：平均输出长度 = verbosity * 100 字符
    desc: str

# 6 个模型，真实质量拉开 0.5 间距（保证无偏数据下排序可被稳定恢复）。Drift 是特意
# 埋的「陷阱」：质量只排第 4、输出却最长 —— 演示长度混杂让朴素 BT 把「长」误判为「强」。
MODELS: List[ModelSpec] = [
    ModelSpec("atlas",    "Atlas",    2.0, 1.05, "质量强，长度中等"),
    ModelSpec("borealis", "Borealis", 1.5, 0.95, "稍弱于 Atlas，文风简洁"),
    ModelSpec("cascade",  "Cascade",  1.0, 1.00, "中游质量"),
    ModelSpec("drift",    "Drift",    0.5, 2.60, "质量偏弱但极冗长（陷阱模型）"),
    ModelSpec("echo",     "Echo",     0.0, 1.10, "质量偏弱"),
    ModelSpec("fable",    "Fable",   -0.5, 0.85, "质量最弱，惜字如金"),
]
MODEL_IDS: List[str] = [m.model_id for m in MODELS]
QUALITY: Dict[str, float] = {m.model_id: m.quality for m in MODELS}
CN: Dict[str, str] = {m.model_id: m.cn for m in MODELS}
SPEC: Dict[str, ModelSpec] = {m.model_id: m for m in MODELS}
# 真实排序（强 → 弱）：后文所有「排序恢复」断言的 ground truth
TRUE_ORDER: List[str] = sorted(MODEL_IDS, key=lambda m: -QUALITY[m])

# ---------------------------------------------------------------------------
# 2. 通用小工具：sigmoid / 排序 / 相关系数 / 中文对齐
# ---------------------------------------------------------------------------

def sigmoid(z: float) -> float:
    """logistic 函数。BT 与 Elo 的胜率函数本质都是它：
    P(i 胜 j) = σ(logit 差)。溢出保护避免极端 logit 下 math.exp 报错。"""
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)

def order_of(scores: Dict[str, float]) -> List[str]:
    """把 {模型: 分数} 变成 强→弱 的有序列表。"""
    return sorted(scores, key=lambda m: -scores[m])

def ranks_of(order: List[str]) -> Dict[str, int]:
    """有序列表 → {模型: 名次}，名次 1 = 最强。"""
    return {m: i + 1 for i, m in enumerate(order)}

def kendall_tau(order_x: List[str], order_y: List[str]) -> float:
    """Kendall τ：两个排序的一致程度，1 = 完全一致，-1 = 完全相反。数「任意一对模型
    在两个排序里相对位置是否一致」：τ = (一致对 - 不一致对) / 总对数。本实验用它断言
    「恢复出的排序 == 真实排序」，比肉眼看表格严格得多。"""
    pos_y = {item: i for i, item in enumerate(order_y)}
    concordant = discordant = 0
    for i in range(len(order_x)):
        for j in range(i + 1, len(order_x)):
            if pos_y[order_x[i]] < pos_y[order_x[j]]:
                concordant += 1
            else:
                discordant += 1
    return (concordant - discordant) / (concordant + discordant)

def pearson(xs: List[float], ys: List[float]) -> float:
    """皮尔逊相关系数：衡量两组数值的线性一致程度（Elo vs BT 对照用）。"""
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy)

def spearman(order_x: List[str], order_y: List[str]) -> float:
    """斯皮尔曼相关 = 名次序列的皮尔逊相关（规格要求的另一种排序一致性检验）。"""
    rx, ry = ranks_of(order_x), ranks_of(order_y)
    return pearson([rx[m] for m in order_x], [ry[m] for m in order_x])

def _display_width(s: str) -> int:
    """中文按 2 列宽计，保证表格对齐。"""
    return sum(2 if ord(ch) > 127 else 1 for ch in s)

def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _display_width(s))

# ---------------------------------------------------------------------------
# 3. 成对比较数据结构与数据生成器
# ---------------------------------------------------------------------------

@dataclass
class Match:
    """一场竞技场对决的完整记录。特意保留 a_first / len_a / len_b 等「过程信息」：
    事后做位置偏差测量、长度分桶诊断、协变量回归都要靠它们。"""
    match_id: int
    a: str          # 参战模型 1
    b: str          # 参战模型 2
    a_first: bool   # a 是否被放在第一位呈现
    len_a: int      # a 的答案长度（字符）
    len_b: int      # b 的答案长度（字符）
    winner: str     # 胜者（模型 id）
    p_a: float      # 裁判内部给 a 的胜率（教学用；真实裁判是黑盒，拿不到）

def _sample_length(rng: random.Random, spec: ModelSpec,
                   length_cap: Optional[int]) -> int:
    """采样一场对决中该模型的答案长度：围绕「风格均值」高斯抖动，模拟同一模型
    每次输出长度并不相同。length_cap 对应产品侧「长度上限」，截断发生在裁判看到之前。"""
    raw = rng.gauss(spec.verbosity * 100.0, 18.0)
    ln = max(15, int(round(raw)))
    return min(ln, length_cap) if length_cap else ln

def generate_matches(judge: "MockArenaJudge", n_per_pair: int, seed: int,
                     length_cap: Optional[int] = None, first_ratio: float = 0.5) -> List[Match]:
    """成对比较数据生成器：每对模型打 n_per_pair 场，裁判由外部注入。
    first_ratio = 0.5 表示「平衡调度」：每对模型在两种呈现顺序下出场概率相等，这是
    竞技场抵消位置偏差的标准设计；若 UI 把某模型固定放第一位（first_ratio 失衡），
    位置偏差就会渗进排名（见思考题 2）。
    """
    rng = random.Random(seed)
    matches: List[Match] = []
    mid = 0
    for i in range(len(MODELS)):
        for j in range(i + 1, len(MODELS)):
            a, b = MODELS[i].model_id, MODELS[j].model_id
            for _ in range(n_per_pair):
                mid += 1
                a_first = rng.random() < first_ratio
                len_a = _sample_length(rng, SPEC[a], length_cap)
                len_b = _sample_length(rng, SPEC[b], length_cap)
                verdict = judge(a, b, a_first, len_a, len_b)
                matches.append(Match(mid, a, b, a_first, len_a, len_b,
                                     verdict["winner"], verdict["p_a"]))
    return matches

def subsample_by_pair(matches: List[Match], n_per_pair: int) -> List[Match]:
    """每对只保留前 n_per_pair 场 —— 用确定性方式构造「小样本」对照组，
    演示样本量不足时置信区间变宽、同样的差距变得「不可判」。"""
    counts: Dict[Tuple[str, str], int] = {}
    kept: List[Match] = []
    for mt in matches:
        key = (mt.a, mt.b) if mt.a < mt.b else (mt.b, mt.a)
        c = counts.get(key, 0)
        if c < n_per_pair:
            kept.append(mt)
            counts[key] = c + 1
    return kept

def first_position_win_rate(matches: List[Match]) -> float:
    """第一位呈现的答案的胜率 —— 位置偏差最直接的观测量。
    无位置偏差且双方实力对称时它应≈50%；显著>50% 即存在位置偏差。"""
    wins = sum(1 for mt in matches if (mt.winner == mt.a) == mt.a_first)
    return wins / len(matches)

def pair_stats(matches: List[Match], x: str, y: str) -> dict:
    """x 与 y 之间对决的统计：x 的胜率、x 更长的一方所占比例。
    用来抓「弱但长的模型反而赢得多」这一混杂的现场证据。"""
    n = x_wins = x_longer = 0
    for mt in matches:
        if {mt.a, mt.b} != {x, y}:
            continue
        n += 1
        if mt.winner == x:
            x_wins += 1
        if (mt.len_a > mt.len_b) if mt.a == x else (mt.len_b > mt.len_a):
            x_longer += 1
    return {"n": n, "x_win_rate": x_wins / n, "x_longer_frac": x_longer / n}

def length_bucket_table(matches: List[Match]) -> List[dict]:
    """按 |长度差| 分桶，统计「更长一方」的胜率 —— 长度混杂的诊断表。
    若长度偏差存在，|Δlen| 越大的桶里，更长一方的胜率越高。"""
    edges = [(0, 40), (40, 80), (80, 160), (160, 10 ** 9)]
    rows = []
    for lo, hi in edges:
        bucket = [mt for mt in matches if lo <= abs(mt.len_a - mt.len_b) < hi
                  and mt.len_a != mt.len_b]  # 等长场次无「更长一方」，剔除
        if not bucket:
            rows.append({"lo": lo, "hi": hi, "n": 0, "longer_win_rate": 0.0})
            continue
        longer_wins = sum(1 for mt in bucket
                          if (mt.winner == mt.a) == (mt.len_a > mt.len_b))
        rows.append({"lo": lo, "hi": hi, "n": len(bucket),
                     "longer_win_rate": longer_wins / len(bucket)})
    return rows

# ---------------------------------------------------------------------------
# 4. MockArenaJudge：可注入偏差的裁判（与真实 LLM judge 同构）
# ---------------------------------------------------------------------------

class MockArenaJudge:
    """确定性 mock 裁判。接口与真实 LLM judge 同构：chat() 对应「给一段 prompt、返回
    判定文本」，__call__() 返回结构化判定，生产中可整体替换为真实模型调用。
    「智能」是完全透明的公式：logit = 真实质量差 + pos_bias·位置项 + len_bias·长度差，
    P(a 胜) = σ(logit)。这正是 LLM 裁判两类经典偏差的操作化：位置项模拟「第一眼印象」，
    长度项模拟「写得多显得更用心」。偏差大小是两个旋钮，便于对照实验。
    """

    def __init__(self, pos_bias: float = 0.0, len_bias: float = 0.0,
                 seed: int = 0):
        self.pos_bias = pos_bias
        self.len_bias = len_bias
        # 独立随机源只用于「按概率抽胜者」，种子固定 → 判定序列可复现
        self._rng = random.Random(seed)

    def chat(self, prompt: str) -> str:
        """与真实 LLM 客户端同构的入口。真实裁判在这里会发起一次模型调用，
        返回「A 胜，理由……」这样的文本；mock 返回判定回执。"""
        return (f"[MockArenaJudge] pos_bias={self.pos_bias}, len_bias={self.len_bias}"
                f"：已完成判定（收到 prompt {len(prompt)} 字符）")

    def __call__(self, a: str, b: str, a_first: bool,
                 len_a: int, len_b: int) -> dict:
        """执行一次成对判定。位置项取 +1/-1：a 在第一位则给 a 加 pos_bias，
        否则给 b 加 —— 与回归里的位置协变量定义严格一致。"""
        z = (QUALITY[a] - QUALITY[b]
             + self.pos_bias * (1.0 if a_first else -1.0)
             + self.len_bias * (len_a - len_b))
        p_a = sigmoid(z)
        winner = a if self._rng.random() < p_a else b
        return {
            "winner": winner,
            "p_a": p_a,
            "logit": z,
            "rationale": self.chat(f"compare {a} vs {b}"),
        }

# ---------------------------------------------------------------------------
# 5. Bradley-Terry 极大似然估计（MM 迭代）
# ---------------------------------------------------------------------------

def fit_bradley_terry(matches: List[Match], model_ids: List[str] = MODEL_IDS,
                      max_iter: int = 800, tol: float = 1e-11) -> Tuple[Dict[str, float], int]:
    """Bradley-Terry MLE（Hunter 2004 的 MM 迭代），返回 (γ, 迭代轮数)。模型：
    P(i 胜 j) = γ_i/(γ_i+γ_j)，似然在 log γ 空间是凹的但没有闭式解；MM 更新式
    γ_i ← W_i / Σ_j n_ij/(γ_i+γ_j) 每轮单调抬升似然、无需梯度步长，几十轮收敛 ——
    这就是各大竞技场榜单背后的标准算法。

    两个工程细节：① 尺度不变 —— 全体 γ 同乘常数不改变任何概率，每轮后约定 Σγ=N；
    ② 全败模型使 γ→0、log→-∞，这里用 1e-9 兜底；真实系统通常加 Beta/高斯先验
    （贝叶斯 BT）或小样本收缩来正则化。
    """
    wins = {m: 1e-9 for m in model_ids}
    pair_n: Dict[Tuple[str, str], int] = {}
    for mt in matches:
        wins[mt.winner] += 1.0
        key = (mt.a, mt.b) if mt.a < mt.b else (mt.b, mt.a)
        pair_n[key] = pair_n.get(key, 0) + 1

    gamma = {m: 1.0 for m in model_ids}
    iters = 0
    for it in range(1, max_iter + 1):
        iters = it
        nxt: Dict[str, float] = {}
        for i in model_ids:
            denom = 0.0
            for j in model_ids:
                if i == j:
                    continue
                key = (i, j) if i < j else (j, i)
                nij = pair_n.get(key, 0)
                if nij:
                    denom += nij / (gamma[i] + gamma[j])
            nxt[i] = wins[i] / max(denom, 1e-12)
        scale = len(model_ids) / sum(nxt.values())
        new_gamma = {m: nxt[m] * scale for m in model_ids}
        delta = max(abs(new_gamma[m] - gamma[m]) for m in model_ids)
        gamma = new_gamma
        if delta < tol:
            break
    return gamma, iters

def log_ratings(gamma: Dict[str, float]) -> Dict[str, float]:
    """γ → log γ。BT 的强度差在对数空间才有「胜率差」的可加解释，
    Bootstrap 置信区间也在该空间构造。"""
    return {m: math.log(g) for m, g in gamma.items()}

# ---------------------------------------------------------------------------
# 6. Elo 评分：同一模型的在线增量版
# ---------------------------------------------------------------------------

def elo_ratings(matches: List[Match], seed: int, k_factor: float = 24.0,
                initial: float = 1500.0) -> Dict[str, float]:
    """标准 Elo：期望得分 E_a = 1/(1+10^((R_b-R_a)/400))，每场 R += K·(实际-期望)。
    比赛按「到达顺序」消费：先做一次固定种子的 shuffle 模拟线上流水。换一种打乱顺序，
    最终分数就会不同 —— 顺序依赖是 Elo 作为「在线近似」的固有代价；BT MLE 用全部数据
    求全局最优，与顺序无关。K 因子控制单场影响力：K 大收敛快但噪声大，K 小平滑但追新慢。
    """
    rng = random.Random(seed)
    order = list(matches)
    rng.shuffle(order)
    r = {m: initial for m in MODEL_IDS}
    for mt in order:
        e_a = 1.0 / (1.0 + 10.0 ** ((r[mt.b] - r[mt.a]) / 400.0))
        s_a = 1.0 if mt.winner == mt.a else 0.0
        r[mt.a] += k_factor * (s_a - e_a)
        r[mt.b] += k_factor * ((1.0 - s_a) - (1.0 - e_a))
    return r

# ---------------------------------------------------------------------------
# 7. Bootstrap 置信区间：两模型的差距显著吗？
# ---------------------------------------------------------------------------

def bootstrap_strength_ci(matches: List[Match], x: str, y: str, B: int = 160,
                          seed: int = SEED + 70) -> Tuple[float, float, float]:
    """强度差 ln(γ_x/γ_y) 的 Bootstrap 95% CI，返回 (下界, 上界, 均值)。做法：把比赛
    记录当作总体，有放回重采样出同样大小的「新锦标赛」，每次重新拟合 BT，重复 B 次后取
    2.5%/97.5% 分位数。区间不盖住 0 ⇒ 差距超过统计噪声，「x 显著强于 y」。注意重采样
    单元要与独立性假设一致：这里每场比赛独立，故按场重采样；若同一 prompt 被多次投票，
    应按 prompt（聚类）重采样，否则 CI 过窄。
    """
    rng = random.Random(seed)
    n = len(matches)
    diffs: List[float] = []
    for _ in range(B):
        sample = [matches[rng.randrange(n)] for _ in range(n)]
        gamma, _ = fit_bradley_terry(sample)
        diffs.append(math.log(gamma[x] / gamma[y]))
    diffs.sort()
    lo = diffs[int(0.025 * (B - 1))]
    hi = diffs[int(0.975 * (B - 1))]
    return lo, hi, sum(diffs) / B

# ---------------------------------------------------------------------------
# 8. 风格控制（统计侧）：回归残差法 —— 带协变量的 BT
# ---------------------------------------------------------------------------

def fit_bt_with_style_covariates(matches: List[Match], epochs: int = 600, lr_scale: float = 4.0
                                 ) -> Tuple[Dict[str, float], float, float, float, float]:
    """回归残差法（style control 的简化实现），返回 (θ, g_len, g_pos, 初始/最终对数似然)。
    模型：P(a 胜 b) = σ(θ_a - θ_b + g_len·Δlen/100 + g_pos·pos)。关键思想：长度/位置能
    「解释」的那部分胜负不再记到实力账上 —— 每个参数的梯度更新恰是残差 r = y - p 与对应
    特征的协方差，收敛后 θ 就是「剥离风格效应后的纯实力」。Chatbot Arena 的
    style-controlled ranking 正是这套做法（协变量更多：格式、表情等）。

    实现要点：全批梯度上升（确定性）；学习率 lr_scale/N；每轮把 θ 减去均值以满足 Σθ=0
    的可辨识约束（与 BT 的尺度不变同理）。数据生成过程恰好是本模型（真值
    g_len=LEN_BIAS*100=1.0, g_pos=0.4），估计量应无偏逼近真值 —— 自检直接断言。
    """
    feats: List[Tuple[str, str, float, float, float]] = []
    for mt in matches:
        y = 1.0 if mt.winner == mt.a else 0.0
        dl = (mt.len_a - mt.len_b) / LEN_SCALE   # a 相对 b 的长度差（/100）
        xp = 1.0 if mt.a_first else -1.0         # a 在第一位取 +1
        feats.append((mt.a, mt.b, dl, xp, y))

    theta = {m: 0.0 for m in MODEL_IDS}
    g_len = 0.0
    g_pos = 0.0
    lr = lr_scale / len(feats)
    ll_first: Optional[float] = None
    ll_last = 0.0
    for _ in range(epochs):
        grad = {m: 0.0 for m in MODEL_IDS}
        gl = gp = 0.0
        ll = 0.0
        for a, b, dl, xp, y in feats:
            z = theta[a] - theta[b] + g_len * dl + g_pos * xp
            p = sigmoid(z)
            r = y - p                      # 残差：实际结果 - 模型预期
            grad[a] += r
            grad[b] -= r
            gl += r * dl
            gp += r * xp
            ll += math.log(max(p, 1e-12)) if y > 0.5 \
                else math.log(max(1.0 - p, 1e-12))
        for m in MODEL_IDS:
            theta[m] += lr * grad[m]
        mean_t = sum(theta.values()) / len(theta)
        for m in MODEL_IDS:                # 可辨识约束：Σθ = 0
            theta[m] -= mean_t
        g_len += lr * gl
        g_pos += lr * gp
        if ll_first is None:
            ll_first = ll
        ll_last = ll
    return theta, g_len, g_pos, ll_first, ll_last

# ---------------------------------------------------------------------------
# 9. 自检：所有断言都指向实验的核心结论
# ---------------------------------------------------------------------------

def run_self_checks(R: dict) -> None:
    """有牙齿的断言集合：每一条都对应本实验的一个核心结论。
    （约定：τ=1 表示排序完全一致；rank 1 = 最强。）"""

    # ---- 实验 1：无偏数据下，BT 完整恢复真实排序 ----
    assert R["tau_bt"] == 1.0, f"无偏数据下 BT 排序应与真实排序完全一致，实际 τ={R['tau_bt']}"
    assert R["spearman_bt"] > 0.9999, f"Spearman 检验同样要求完全一致，实际 ρ={R['spearman_bt']}"

    # ---- 实验 2：Elo 与 BT 是同一模型的两种算法 ----
    assert R["tau_elo"] == 1.0, f"无偏数据下 Elo 排序也应恢复真实排序，实际 τ={R['tau_elo']}"
    assert R["elo_bt_corr"] > 0.95, \
        f"Elo 分数应与 BT 对数强度强线性相关，实际相关={R['elo_bt_corr']:.4f}"
    assert R["elo_order_gap"] > 10.0, "Elo 应有顺序依赖性：两种出场顺序下分数应明显漂移（>10 分）"
    assert R["elo1_order"] != R["elo2_order"], "同一份数据、仅换出场顺序，Elo 排序应发生变化"
    assert R["tau_elo2"] < 1.0, "顺序 B 下 Elo 排序应失真（最弱的一对发生颠倒）"
    r1, r2 = ranks_of(R["elo1_order"]), ranks_of(R["elo2_order"])
    assert r1["echo"] < r1["fable"] and r2["fable"] < r2["echo"], \
        "被顺序翻转的应是真实差距最小的 Echo/Fable 对"

    # ---- 实验 3：Bootstrap CI 与显著性 ----
    assert R["ci_af_full"][0] > 0, "全量数据下 Atlas−Fable 差距应显著（CI 不盖 0）"
    assert R["ci_cd_full"][0] > 0, "全量数据下 Cascade−Drift 差距应显著"
    assert R["ci_cd_small"][0] <= 0 <= R["ci_cd_small"][1], \
        f"小样本下同一真实差距应变得不可判（CI 盖住 0），实际 {R['ci_cd_small']}"
    assert (R["ci_cd_small"][1] - R["ci_cd_small"][0]) > \
           (R["ci_cd_full"][1] - R["ci_cd_full"][0]), "样本量越小，CI 应越宽"

    # ---- 实验 4：位置偏差存在，但被平衡调度抵消 ----
    assert 0.52 < R["fwr_pos"] < 0.68, \
        f"注入 pos_bias=0.4 后第一位胜率应显著高于 50%，实际 {R['fwr_pos']:.3f}"
    assert 0.52 < R["fwr_biased"] < 0.68, \
        f"完全偏差数据中同样应测出位置偏差，实际 {R['fwr_biased']:.3f}"
    assert R["tau_pos_control"] == 1.0, "只有位置偏差 + 平衡调度时，BT 排序应不受影响（τ=1）"

    # ---- 实验 5：长度混杂让朴素 BT「把长当强」----
    assert R["tau_naive"] < 0.8, f"有偏数据下朴素 BT 排序应出错，实际 τ={R['tau_naive']}"
    assert R["rank_naive"]["drift"] <= 2, \
        f"陷阱模型 Drift（真实第 4）应被长度偏差顶到前 2，实际第 {R['rank_naive']['drift']}"
    assert R["rank_true"]["drift"] == 4, "真实排序里 Drift 应排第 4"
    assert R["gamma_naive"]["drift"] > R["gamma_naive"]["borealis"], \
        "朴素 BT 应把 Drift 误排在真实质量高 1.0 的 Borealis 之上"
    s3, s1 = R["pair_drift_biased"], R["pair_drift_unbiased"]
    assert s3["x_win_rate"] > 0.62, \
        f"有偏数据里弱而长的 Drift 对 Cascade 胜率应反超，实际 {s3['x_win_rate']:.3f}"
    assert s1["x_win_rate"] < 0.45, \
        f"无偏数据里 Drift 对 Cascade 胜率应低于五成，实际 {s1['x_win_rate']:.3f}"
    assert s3["x_longer_frac"] > 0.9, "Drift 应是绝大多数对决中更长的一方"

    # ---- 实验 6：风格控制恢复真实排序 ----
    assert R["tau_reg"] == 1.0, f"回归残差法修正后排序应完全恢复，实际 τ={R['tau_reg']}"
    assert abs(R["g_len_hat"] - LEN_BIAS * LEN_SCALE) < 0.3, \
        f"长度系数应逼近真值 1.0，实际 {R['g_len_hat']:.3f}"
    assert abs(R["g_pos_hat"] - POS_BIAS) < 0.2, f"位置系数应逼近真值 0.4，实际 {R['g_pos_hat']:.3f}"
    assert R["ll_last"] > R["ll_first"], "回归的对数似然应随迭代单调上升"
    assert R["tau_cap"] == 1.0, f"长度截断后朴素 BT 应恢复真实排序，实际 τ={R['tau_cap']}"

# ---------------------------------------------------------------------------
# 10. 演示入口：六步串起整条竞技场数据链路
# ---------------------------------------------------------------------------

def _print_strength_table(scores: Dict[str, float], score_label: str,
                          show_true_rank: bool = True) -> None:
    order = order_of(scores)
    rank_true = ranks_of(TRUE_ORDER)
    print("   " + _pad("模型", 12) + _pad("真实Q", 7) + _pad(score_label, 10) + _pad("估计名次", 9)
          + ("真实名次" if show_true_rank else ""))
    for rk, m in enumerate(order, start=1):
        line = ("   " + _pad(CN[m], 12) + _pad(f"{QUALITY[m]:+.2f}", 7)
                + _pad(f"{scores[m]:+.2f}", 10) + _pad(str(rk), 9))
        if show_true_rank:
            line += str(rank_true[m])
        print(line)

def main() -> None:
    print("=" * 68)
    print("LAB 11 · 竞技场：Bradley-Terry / Elo / 风格控制（纯标准库 / 确定性）")
    print("=" * 68)

    print("\n「上帝设定」（只有模拟世界知道，评测者只能看到胜负与风格）：")
    print("   " + _pad("模型", 12) + _pad("真实质量", 9) + _pad("冗长度", 8) + "说明")
    for m in MODELS:
        print("   " + _pad(m.cn, 12) + _pad(f"{m.quality:+.2f}", 9) + _pad(f"{m.verbosity:.2f}", 8) + m.desc)
    print("   ⚠ Drift 是陷阱模型：质量仅第 4 但输出最长，用于演示长度混杂。")

    # ---- [1/6] 无偏竞技场：成对比较数据 -> Bradley-Terry MLE
    print("\n[1/6] 无偏竞技场：Bradley-Terry 恢复真实强度")
    judge0 = MockArenaJudge(pos_bias=0.0, len_bias=0.0, seed=SEED + 1)
    d1 = generate_matches(judge0, n_per_pair=200, seed=SEED + 2)
    gamma1, iters = fit_bradley_terry(d1)
    logg1 = log_ratings(gamma1)
    bt_order = order_of(logg1)
    tau_bt = kendall_tau(bt_order, TRUE_ORDER)
    rho_bt = spearman(bt_order, TRUE_ORDER)
    print(f"   - 生成 {len(d1)} 场对决（15 对 × 200 场），裁判无任何偏差；MM 迭代 {iters} 轮收敛（归一化 Σγ={len(MODELS)}）。")
    _print_strength_table(logg1, "log(γ)")
    print(f"   Kendall τ(BT, 真实) = {tau_bt:.2f}，Spearman ρ = {rho_bt:.2f}")
    print("   → 判定无偏且样本充足时，BT MLE 能完整恢复真实实力排序。")

    # ---- [2/6] Elo：同一模型的在线增量版 + 顺序依赖性
    print("\n[2/6] Elo 对照：同一份数据的在线增量评分")
    elo1 = elo_ratings(d1, seed=SEED + 3, k_factor=24.0)
    elo2 = elo_ratings(d1, seed=SEED + 4, k_factor=24.0)
    tau_elo = kendall_tau(order_of(elo1), TRUE_ORDER)
    bt_scale = {m: 400.0 * math.log10(gamma1[m]) for m in MODEL_IDS}
    elo_bt_corr = pearson([elo1[m] for m in MODEL_IDS],
                          [bt_scale[m] for m in MODEL_IDS])
    elo_order_gap = max(abs(elo1[m] - elo2[m]) for m in MODEL_IDS)
    elo1_order = order_of(elo1)
    elo2_order = order_of(elo2)
    tau_elo2 = kendall_tau(elo2_order, TRUE_ORDER)
    print(f"   - Elo(K=24) 增量消费同样 {len(d1)} 场比赛（固定种子打乱出场顺序）：")
    _print_strength_table(elo1, "Elo分", show_true_rank=False)
    print(f"   - corr(Elo, 400·log10γ) = {elo_bt_corr:.4f}（同一概率模型；单遍在线近似仍带顺序/抽样噪声）；")
    print(f"   - 换一种出场顺序重跑：分数最大漂移 {elo_order_gap:.2f} 分，排序也跟着变了：")
    print("     顺序A: " + " > ".join(CN[m] for m in elo1_order))
    print("     顺序B: " + " > ".join(CN[m] for m in elo2_order))
    print(f"     （最弱的一对 Echo/Fable 在顺序 B 下颠倒，τ 从 1.00 掉到 {tau_elo2:.2f}"
          f" —— 每对 200 场也压不住相近模型的顺序敏感性）")
    print("   → Elo 是在线近似：顺序依赖、K 敏感；BT MLE 用全量数据求全局最优，与顺序无关。")

    # ---- [3/6] Bootstrap：两模型的差距显著吗？
    print("\n[3/6] Bootstrap 置信区间：差距是否超过统计噪声")
    ci_af = bootstrap_strength_ci(d1, "atlas", "fable", B=160, seed=SEED + 5)
    ci_cd_full = bootstrap_strength_ci(d1, "cascade", "drift", B=160,
                                       seed=SEED + 6)
    ci_ef = bootstrap_strength_ci(d1, "echo", "fable", B=160, seed=SEED + 7)
    # 每对只剩 12 场时，同一真实差距（0.5）的 CI 会宽到盖住 0 —— 演示
    # 「证据不足」；25 场时 CI 虽变宽但仍不盖 0，故取更小的样本量做对照。
    d1_small = subsample_by_pair(d1, 12)
    ci_cd_small = bootstrap_strength_ci(d1_small, "cascade", "drift", B=160,
                                        seed=SEED + 8)

    def _ci_line(label: str, ci: Tuple[float, float, float]) -> str:
        lo, hi, mean = ci
        verdict = "显著" if lo > 0 else ("不显著（CI 盖住 0）" if hi >= 0 else "显著")
        return (f"   {label:<22} Δ={mean:+.2f}  "
                f"95%CI [{lo:+.2f}, {hi:+.2f}]  → {verdict}")

    print(_ci_line("Atlas − Fable", ci_af))
    print(_ci_line("Cascade − Drift", ci_cd_full))
    print(_ci_line("Echo − Fable", ci_ef))
    print("   样本量对照（同一对 Cascade−Drift，真实差距 0.5）：")
    v_full = "显著" if ci_cd_full[0] > 0 else "盖住 0，不可判"
    v_small = "显著" if ci_cd_small[0] > 0 else "盖住 0，不可判"
    print(f"     每对 200 场：95%CI [{ci_cd_full[0]:+.2f}, {ci_cd_full[1]:+.2f}]"
          f" → {v_full}")
    print(f"     每对  12 场：95%CI [{ci_cd_small[0]:+.2f}, {ci_cd_small[1]:+.2f}]"
          f" → {v_small}")
    print("   → CI 盖住 0 不是「两者一样好」，而是「证据不足」；加场次可解。")

    # ---- [4/6] 位置偏差：可测、但被平衡调度抵消
    print(f"\n[4/6] 位置偏差：注入 pos_bias={POS_BIAS}")
    judge_pos = MockArenaJudge(pos_bias=POS_BIAS, len_bias=0.0, seed=SEED + 9)
    d_pos = generate_matches(judge_pos, n_per_pair=150, seed=SEED + 10)
    fwr_pos = first_position_win_rate(d_pos)
    gamma_pos, _ = fit_bradley_terry(d_pos)
    tau_pos_control = kendall_tau(order_of(log_ratings(gamma_pos)), TRUE_ORDER)

    judge_biased = MockArenaJudge(pos_bias=POS_BIAS, len_bias=LEN_BIAS,
                                  seed=SEED + 11)
    d3 = generate_matches(judge_biased, n_per_pair=300, seed=SEED + 12)
    fwr_biased = first_position_win_rate(d3)
    print(f"   - 第一位呈现的答案胜率：仅位置偏差数据 {fwr_pos:.1%}，完全偏差数据 "
          f"{fwr_biased:.1%}（>50% 即偏差存在）；")
    print(f"   - 对照实验（只有位置偏差 + 平衡调度）：BT 排序 τ = {tau_pos_control:.2f}，完全未受影响。")
    print("   → 位置偏差是「对内对称」的噪声：交换顺序 + 等量调度即可抵消。")

    # ---- [5/6] 长度混杂：朴素 BT 把「长」误判为「强」
    print("\n[5/6] 长度混杂：朴素 BT 被冗长模型带偏")
    gamma_naive, _ = fit_bradley_terry(d3)
    naive_order = order_of(log_ratings(gamma_naive))
    tau_naive = kendall_tau(naive_order, TRUE_ORDER)
    rank_naive = ranks_of(naive_order)
    rank_true = ranks_of(TRUE_ORDER)
    print(f"   - 完全偏差数据（pos={POS_BIAS}, len={LEN_BIAS}/字符，{len(d3)} 场）上的朴素 BT 排序：")
    print("   " + _pad("模型", 12) + _pad("朴素名次", 9) + _pad("真实名次", 9) + "结果")
    for m in naive_order:
        flag = "✔" if rank_naive[m] == rank_true[m] else \
            ("⬆ 被长度顶高" if rank_naive[m] < rank_true[m] else "⬇ 被挤低")
        print("   " + _pad(CN[m], 12) + _pad(str(rank_naive[m]), 9)
              + _pad(str(rank_true[m]), 9) + flag)
    print(f"   Kendall τ(朴素, 真实) = {tau_naive:.2f}（排序已失真）。")
    s1 = pair_stats(d1, "drift", "cascade")
    s3 = pair_stats(d3, "drift", "cascade")
    print(f"   - 现场证据（Cascade 真实强于 Drift 0.5）：")
    print(f"     无偏数据：Drift 胜率 {s1['x_win_rate']:.1%}（弱者本就该多输）；")
    print(f"     有偏数据：Drift 胜率 {s3['x_win_rate']:.1%}，且 Drift 在 {s3['x_longer_frac']:.1%} 的对决里是更长的一方。")
    print("   - |长度差| 分桶诊断：桶越高（长度差越大），更长一方赢得越多：")
    for row in length_bucket_table(d3):
        hi_show = "∞" if row["hi"] > 10 ** 8 else str(row["hi"])
        rate = f"{row['longer_win_rate']:.1%}" if row["n"] else "—"
        print(f"     |Δlen|∈[{row['lo']},{hi_show})  n={row['n']:<5} "
              f"更长一方胜率={rate}")
    print("   → 长度是模型间的系统性混杂：交换顺序消不掉，必须在统计上剥离。")

    # ---- [6/6] 风格控制：回归残差法 + 长度截断
    print("\n[6/6] 风格控制：把「长」从「强」里剥离")
    theta, g_len_hat, g_pos_hat, ll_first, ll_last = \
        fit_bt_with_style_covariates(d3)
    reg_order = order_of(theta)
    tau_reg = kendall_tau(reg_order, TRUE_ORDER)
    print(f"   - 回归残差法：P(a胜b)=σ(θ_a-θ_b + g_len·Δlen/100 + g_pos·pos)")
    print(f"     系数估计：g_len={g_len_hat:.3f}（真值 {LEN_BIAS * LEN_SCALE:.2f}），"
          f"g_pos={g_pos_hat:.3f}（真值 {POS_BIAS:.2f}）；")
    print(f"     对数似然 {ll_first:.1f} → {ll_last:.1f}（单调上升，收敛正常）。")
    print("     剥离风格后的纯实力排序：")
    _print_strength_table(theta, "θ(纯实力)")
    print(f"     Kendall τ(修正后, 真实) = {tau_reg:.2f} → 真实排序完全恢复。")

    judge_cap = MockArenaJudge(pos_bias=POS_BIAS, len_bias=LEN_BIAS,
                               seed=SEED + 13)
    d_cap = generate_matches(judge_cap, n_per_pair=200, seed=SEED + 14,
                             length_cap=LENGTH_CAP)
    gamma_cap, _ = fit_bradley_terry(d_cap)
    tau_cap = kendall_tau(order_of(log_ratings(gamma_cap)), TRUE_ORDER)
    print(f"   - 设计侧对照：答案长度上限 {LENGTH_CAP} 字符（截断 Drift 的冗长），重开一轮竞技场后朴素 BT：τ = {tau_cap:.2f}。")
    print("   → 风格控制两条路：统计上剥离（回归残差）/ 设计上消除（长度限制）。")

    # ---- 自检 ----
    print("\n[自检] 运行核心断言（排序恢复 / 偏差量化 / 修正效果 / CI 判定）...")
    R = {"tau_bt": tau_bt, "spearman_bt": rho_bt, "tau_elo": tau_elo,
         "elo_bt_corr": elo_bt_corr, "elo_order_gap": elo_order_gap, "tau_elo2": tau_elo2,
         "elo1_order": elo1_order, "elo2_order": elo2_order, "ci_af_full": ci_af,
         "ci_cd_full": ci_cd_full, "ci_ef_full": ci_ef, "ci_cd_small": ci_cd_small,
         "fwr_pos": fwr_pos, "fwr_biased": fwr_biased, "tau_pos_control": tau_pos_control,
         "tau_naive": tau_naive, "rank_naive": rank_naive, "rank_true": rank_true,
         "gamma_naive": gamma_naive, "pair_drift_biased": s3, "pair_drift_unbiased": s1,
         "tau_reg": tau_reg, "g_len_hat": g_len_hat, "g_pos_hat": g_pos_hat,
         "ll_first": ll_first, "ll_last": ll_last, "tau_cap": tau_cap}
    run_self_checks(R)
    print(f"   - 无偏数据：BT 与 Elo(顺序A) 均恢复真实排序（τ=1.00），corr(Elo,BT)={elo_bt_corr:.3f} ✔")
    print(f"   - Elo 顺序依赖：换顺序后分数漂移 {elo_order_gap:.1f} 分，Echo/Fable 对被翻转（τ 1.00 → {tau_elo2:.2f}）✔")
    print(f"   - Bootstrap：Cascade−Drift 全量 CI {ci_cd_full[0]:+.2f}~{ci_cd_full[1]:+.2f} 显著；"
          f"小样本 CI {ci_cd_small[0]:+.2f}~{ci_cd_small[1]:+.2f} 盖 0 ✔")
    print(f"   - 位置偏差：第一位胜率 {fwr_biased:.1%}，但平衡调度下 τ={tau_pos_control:.2f} 不受影响 ✔")
    print(f"   - 长度混杂：朴素 τ={tau_naive:.2f}，Drift 朴素第 {rank_naive['drift']}（真实第 4）✔")
    print(f"   - 回归残差修正：τ={tau_reg:.2f}，ĝ_len={g_len_hat:.2f}≈1.0，ĝ_pos={g_pos_hat:.2f}≈0.4；长度截断后 τ={tau_cap:.2f} ✔")
    print(f"\n✅ 自检通过：{LAB_NAME} 全部断言成立")

if __name__ == "__main__":
    main()
