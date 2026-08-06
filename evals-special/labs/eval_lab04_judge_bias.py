#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_lab04_judge_bias.py — Judge 偏差量化与缓解
================================================

【实验目的】
    用 LLM-as-Judge 做 A/B 对比时，裁判并不是一台"理想测量仪器"：
    它会系统性地偏袒某些与质量无关的因素。本实验把裁判建模为
    「真实质量信号 + 可注入的偏差项 + 噪声」，先**量化**偏差有多大，
    再逐一验证工程上常用的**缓解手段**是否真的有效、对哪类偏差有效：
        1) 位置偏差（position bias）   —— 偏好出现在第一个位置的答案；
        2) 冗长偏差（verbosity bias）  —— 偏好更长的答案（长 ≠ 好）；
        3) 自我偏好（self-preference） —— 偏好与自己"同风格"的输出，
                                          用文本中的风格标记模拟。
    核心方法论：偏差必须被**测量**（等质量对照组的胜率偏离 50% 多少），
    而不是被**假设**（"我们的 judge 应该没偏吧"）；缓解手段必须被
    **验证**（缓解后偏差是否显著缩小），而不是被**声称**。

【对应章节】
    本特辑第 E05 章 · 评分三层之二：LLM-as-Judge 深入（偏差与缓解）

【核心概念】
    - 成对比较（pairwise comparison）：让 judge 对 (答案A, 答案B) 选出胜者，
      是竞技场（arena）与版本对比最常用的评估形式。
    - 等质量对照组：两组答案真实质量完全相同。此时任何一方的胜率显著
      偏离 50%，都只能来自裁判偏差——这是量化偏差的"零刻度"。
    - 偏差量化：bias = 胜率 - 0.5（正值表示偏向被考察的一方）。
    - 缓解手段各有适用边界：
        交换顺序取平均（swap-and-average）只能治"位置类"偏差；
        多 judge 投票依赖"不同 judge 偏差方向不同"才能对冲；
        冗长偏差要用长度受控评分（本实验实现带校准的惩罚项）；
        风格类自我偏好要靠"匿名化/去风格标记"，交换顺序完全无效。
    - 校准（calibration）：惩罚项系数不是拍脑袋设的，而是在
      等质量数据上把"长度差 -> 分差"的斜率回归出来，再用它纠偏。

【如何运行】
    cd evals-special/labs
    python3 eval_lab04_judge_bias.py
    （纯 Python 标准库、零依赖、固定随机种子，任何机器结果一致）

【思考题（面试延伸）】
    1. 为什么量化 judge 偏差要用"等质量对照组"？如果没有 ground truth，
       你还能用什么办法发现位置偏差？（提示：交换顺序后结论是否翻转。）
    2. swap-and-average 为什么治不了冗长偏差和自我偏好？这两类偏差与
       位置偏差的本质区别是什么？（提示：偏差随"位置"走还是随"内容"走。）
    3. 三个同型号 judge 投票能消除位置偏差吗？本实验的"克隆面板"
       结果说明了什么？多 judge 投票真正依赖的前提是什么？
    4. 本实验用"等质量数据回归出长度惩罚系数"，这套思路还能推广到
       哪些混杂变量（格式华丽度、引用数量、emoji 使用……）？
       如果线上没有等质量数据，系数该怎么估计？
    5. 把 MockJudge 换成真实 LLM judge 需要改哪些代码？
       （提示：只需重写 chat() 的实现，judge_pair 与全部实验代码不动。）
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. 数据结构与数据集构造：把"真实质量"控制成已知量
# ---------------------------------------------------------------------------
# 实验设计的关键：要量化偏差，就必须先让"真实质量"成为已知量。
# 因此每个答案自带一个 quality 字段（潜在真实质量，0~10）。
# 在真实系统里 judge 只能读文本、靠推理估计质量；这里我们把真实质量
# 作为"oracle 信号"直接喂给 MockJudge，目的是把偏差项从质量信号中
# 干净地分离出来——这等价于仿真实验里固定"真实能力"参数，
# 是偏差量化研究的标准做法，而不是偷懒。

QUESTION = "如何提高线上订单服务的稳定性？"   # 所有对比共用同一问题（控制变量）

STYLE_MARKERS = {"散文体": "〔散文体〕", "条列体": "〔条列体〕"}
_STYLE_RE = re.compile(r"〔(散文体|条列体)〕")   # judge 靠文本标记识别风格
_ANON_RE = re.compile(r"〔[^〕]*〕")             # 匿名化：抹掉一切风格标记

# 中立的"填充句"：只贡献长度、不贡献质量。冗长偏差实验靠它制造
# "同样正确但更长"的答案——这正是现实中 verbosity bias 的来源：
# 模型学会用堆字数讨好裁判。
FILLERS = [
    "此外，该方案在工程层面提供了相应的容错保障。",
    "从实施成本看，该方案可以复用大部分现有模块。",
    "相关参数可以依据业务场景的具体特点进行微调。",
    "同时团队对其保持持续监控与定期回滚演练。",
    "这一设计降低了关键路径上出现异常的概率。",
    "在数据层面，相关字段已统一收敛到单一事实源。",
    "接口设计保持向后兼容，调用方无需适配修改。",
    "文档中详细描述了边界条件与常见错误码。",
    "性能测试表明其延迟分布较为平稳。",
    "针对边缘情况，逻辑中包含必要的降级分支。",
    "配置项提供了合理默认值，降低部署成本。",
    "后续迭代还会进一步优化资源使用率。",
]


@dataclass
class Answer:
    """一条候选答案。quality 是潜在真实质量（对"人类实验者"可见，
    对真实 judge 不可见）；style 仅作数据集簿记，judge 必须从文本
    标记里自己识别风格——这样"抹掉标记"这个缓解动作才真正有意义。"""
    text: str
    quality: float
    style: Optional[str] = None


def build_answer(rng: random.Random, quality: float,
                 style: Optional[str] = None, n_fillers: int = 4) -> Answer:
    """构造一条答案：可选风格标记 + 固定主题句 + 随机挑若干填充句。
    相同 n_fillers 的两条答案长度几乎一致（排除长度混杂），
    这是"控制变量"在数据构造层面的体现。"""
    parts: List[str] = []
    if style is not None:
        parts.append(STYLE_MARKERS[style])
    parts.append("核心思路是先对主链路做优雅降级，再叠加限流与熔断保护。")
    parts.extend(rng.sample(FILLERS, n_fillers))
    return Answer(text="".join(parts), quality=quality, style=style)


def make_equal_quality_pairs(n: int, seed: int, b_extra_fillers: int = 0,
                             style_a: Optional[str] = None,
                             style_b: Optional[str] = None,
                             base_quality: float = 5.0,
                             ) -> List[Tuple[Answer, Answer]]:
    """等质量对照组：每对 (A, B) 真实质量完全相同。
    可选开关：让 B 更长（冗长偏差实验）、给双方不同风格标记（自我偏好实验）。
    在这组数据上，任何偏离 50% 的胜率都是裁判偏差的直接证据。"""
    rng = random.Random(seed)
    pairs = []
    for _ in range(n):
        a = build_answer(rng, base_quality, style_a, n_fillers=4)
        b = build_answer(rng, base_quality, style_b, n_fillers=4 + b_extra_fillers)
        pairs.append((a, b))
    return pairs


def make_quality_ladder_pairs(n_per_delta: int, seed: int,
                              deltas: Tuple[float, ...] = (0.6, 1.2, 2.4),
                              base_quality: float = 5.0,
                              ) -> Dict[float, List[Tuple[Answer, Answer]]]:
    """质量阶梯组：A 的真实质量 = base + delta，B = base。
    delta 越大，无偏 judge 的胜率应越高——这是 judge"有区分能力"
    的剂量-反应（dose-response）证据，也是后续偏差实验的参照基线。"""
    rng = random.Random(seed)
    ladder: Dict[float, List[Tuple[Answer, Answer]]] = {}
    for d in deltas:
        pairs = []
        for _ in range(n_per_delta):
            a = build_answer(rng, base_quality + d, None, n_fillers=4)
            b = build_answer(rng, base_quality, None, n_fillers=4)
            pairs.append((a, b))
        ladder[d] = pairs
    return ladder


# ---------------------------------------------------------------------------
# 2. MockJudge：真实质量信号 + 可注入偏差
# ---------------------------------------------------------------------------
# 打分模型（刻意为线性、可解释，方便把每一项偏差单独拆出来）：
#   score = true_quality
#           + position_bias   * [该答案在第一个位置]
#           + verbosity_bias  * (文本字符数 / 100)
#           + self_preference * [文本风格 == judge 自己的风格]
#           + N(0, noise_sd)
# 三种偏差默认全部为 0（无偏 judge），按实验需要注入。

class MockJudge:
    """确定性 mock judge。

    对外接口与主仓库 labs/llm_client.py 的 QwenLLM 同构：
    chat(messages, ...) 接收 Anthropic 风格消息列表、返回同构响应体。
    把本类换成真实 LLM 客户端时，只需重写 chat()（把 payload 渲染成
    judge prompt 发给模型、再解析模型输出），judge_pair 与全部实验
    代码一行不用改——这就是"接口可替换"的价值。
    """

    def __init__(self, name: str = "mock-judge",
                 position_bias: float = 0.0,
                 verbosity_bias: float = 0.0,
                 self_preference: float = 0.0,
                 own_style: Optional[str] = None,
                 noise_sd: float = 0.6, seed: int = 11):
        self.name = name
        self.position_bias = position_bias
        self.verbosity_bias = verbosity_bias
        self.self_preference = self_preference
        self.own_style = own_style
        self.noise_sd = noise_sd
        # 固定种子的私有随机源：只用于打分噪声，保证整个实验确定可复现
        self._rng = random.Random(seed)
        self.calls = 0
        self.input_chars = 0

    # ---- 与 QwenLLM 同构的对话接口 -------------------------------------
    def chat(self, messages: List[dict], tools=None, system=None,
             max_tokens=None, temperature=None) -> dict:
        """一次"judge 调用"。输入最后一条 user 消息里的 JSON payload：
            {"question": ..., "answer_1": {"text","true_quality"},
             "answer_2": {"text","true_quality"}}
        输出 Anthropic 风格响应，content[0].text 是结构化判决 JSON。
        true_quality 字段是仿真用的 oracle 信号（见文件头注释）。"""
        self.calls += 1
        user_msgs = [m for m in messages if m.get("role") == "user"]
        prompt = user_msgs[-1]["content"]
        self.input_chars += len(prompt)
        payload = json.loads(prompt)

        s1 = self._score_answer(payload["answer_1"], position=0)
        s2 = self._score_answer(payload["answer_2"], position=1)
        if abs(s1 - s2) < 1e-9:
            winner = "tie"
        else:
            winner = "A" if s1 > s2 else "B"

        result = {
            "winner": winner,
            "scores": [round(s1, 4), round(s2, 4)],
            "rationale": f"答案A得分={s1:.3f}，答案B得分={s2:.3f}，"
                         f"分差={s1 - s2:+.3f}，判{'A' if winner == 'A' else ('B' if winner == 'B' else '平局')}胜。",
        }
        text = json.dumps(result, ensure_ascii=False)
        return {
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": len(prompt) // 2,
                      "output_tokens": len(text) // 2},
            "model": self.name,
        }

    def simple(self, prompt: str, system: Optional[str] = None) -> str:
        """便捷接口：单轮文本进、文本出（与 QwenLLM.simple 对应）。"""
        resp = self.chat([{"role": "user", "content": prompt}])
        return "".join(b.get("text", "") for b in resp["content"]
                       if b.get("type") == "text")

    def stats(self) -> dict:
        return {"calls": self.calls, "input_chars": self.input_chars,
                "judge": self.name}

    # ---- 结构化入口：成对判决 -------------------------------------------
    def judge_pair(self, question: str, ans_a: Answer,
                   ans_b: Answer) -> dict:
        """把两个 Answer 打包成 payload，走 chat() 完整往返一次，
        返回解析后的判决 {"winner","scores","rationale"}。"""
        payload = {
            "question": question,
            "answer_1": {"text": ans_a.text, "true_quality": ans_a.quality},
            "answer_2": {"text": ans_b.text, "true_quality": ans_b.quality},
        }
        return json.loads(self.simple(json.dumps(payload, ensure_ascii=False)))

    # ---- 内部打分逻辑 ----------------------------------------------------
    @staticmethod
    def detect_style(text: str) -> Optional[str]:
        """从文本标记识别风格。judge 只看文本——所以抹掉标记
        （匿名化）就能真正切断自我偏好的信号来源。"""
        m = _STYLE_RE.search(text)
        return m.group(1) if m else None

    def _score_answer(self, ans_payload: dict, position: int) -> float:
        """线性打分模型：质量信号 + 各偏差项 + 噪声（见节首注释）。
        position=0 表示第一个位置（位置偏差作用于此）。"""
        text = ans_payload["text"]
        s = float(ans_payload["true_quality"])
        if position == 0:
            s += self.position_bias                       # 偏差 1：抢第一位
        s += self.verbosity_bias * (len(text) / 100.0)    # 偏差 2：越长越爱
        if self.own_style is not None and \
                self.detect_style(text) == self.own_style:
            s += self.self_preference                     # 偏差 3：偏袒同风格
        s += self._rng.gauss(0.0, self.noise_sd)          # 评分噪声
        return s


def anonymize(text: str) -> str:
    """去除文本中所有〔...〕风格标记——"匿名化"缓解手段的最小实现。
    真实系统里对应：送评前洗掉可识别模型身份/风格的指纹。"""
    return _ANON_RE.sub("", text)


# ---------------------------------------------------------------------------
# 3. 成对比较工具：胜率与偏差度量
# ---------------------------------------------------------------------------
# 胜率口径：A 胜记 1，B 胜记 0，平局各记 0.5。
# 偏差口径：bias = 胜率 - 0.5。等质量对照组上，bias 的绝对值就是
# 裁判系统性偏差的大小；0.5 是"公平秤"的零刻度。

def win_points(winner: str) -> float:
    return {"A": 1.0, "B": 0.0, "tie": 0.5}[winner]


def pairwise_win_rate(pairs: List[Tuple[Answer, Answer]], judge: MockJudge,
                      question: str = QUESTION) -> float:
    """标准成对比较：A 永远放第一个位置，返回 A 的胜率。"""
    total = sum(win_points(judge.judge_pair(question, a, b)["winner"])
                for a, b in pairs)
    return total / len(pairs)


def pairwise_win_rate_reversed(pairs: List[Tuple[Answer, Answer]],
                               judge: MockJudge,
                               question: str = QUESTION) -> float:
    """与上式唯一区别：把 B 放第一个位置，仍统计 A 的胜率。
    同一批答案、同一个 judge，仅仅交换出场顺序——若两个胜率天差地别，
    位置偏差就无可辩驳。"""
    total = 0.0
    for a, b in pairs:
        res = judge.judge_pair(question, b, a)   # 注意：b 在前
        total += 1.0 - win_points(res["winner"])  # 翻转成"A 视角"的得分
    return total / len(pairs)


def swap_average_win_rate(pairs: List[Tuple[Answer, Answer]],
                          judge: MockJudge,
                          question: str = QUESTION) -> float:
    """缓解 1：交换顺序取平均（swap-and-average）。
    每对比两次：(A,B) 与 (B,A)，各答案在两个方向各得一次分，
    用平均分定胜负。位置偏差对两个方向的作用大小相等、方向相反，
    平均之后被精确对消——这是它只治得了"位置类"偏差的根源：
    冗长/风格偏差随内容走，交换位置后依然跟着同一个答案，平均不掉。"""
    total = 0.0
    for a, b in pairs:
        r1 = judge.judge_pair(question, a, b)    # 方向 1：A 在前
        r2 = judge.judge_pair(question, b, a)    # 方向 2：B 在前
        avg_a = (r1["scores"][0] + r2["scores"][1]) / 2
        avg_b = (r1["scores"][1] + r2["scores"][0]) / 2
        if abs(avg_a - avg_b) < 1e-9:
            total += 0.5
        else:
            total += 1.0 if avg_a > avg_b else 0.0
    return total / len(pairs)


def panel_win_rate(pairs: List[Tuple[Answer, Answer]],
                   judges: List[MockJudge],
                   question: str = QUESTION) -> float:
    """缓解 2：多 judge 投票。每个 judge 独立判决，多数票定胜负。
    关键前提：panel 内 judge 的偏差方向/大小要**异构**
    （不同模型各有偏好），票投出来才会相互对冲；
    若全是同款 judge（克隆面板），系统性偏差只会被投票"合法化"。"""
    total = 0.0
    for a, b in pairs:
        votes = [j.judge_pair(question, a, b)["winner"] for j in judges]
        na, nb = votes.count("A"), votes.count("B")
        total += 1.0 if na > nb else (0.0 if nb > na else 0.5)
    return total / len(pairs)


# ---------------------------------------------------------------------------
# 4. 实验 1：无偏 judge 基线 —— 胜率应当只反映质量差
# ---------------------------------------------------------------------------

def experiment_baseline(n_pairs: int = 48) -> dict:
    judge = MockJudge(name="judge-unbiased", noise_sd=0.6, seed=101)
    # (a) 等质量对照：无偏 judge 的胜率必须贴着 50%
    equal_pairs = make_equal_quality_pairs(n_pairs, seed=201)
    wr_equal = pairwise_win_rate(equal_pairs, judge)
    # (b) 质量阶梯：真实差距越大，胜率越高（剂量-反应关系）
    ladder = make_quality_ladder_pairs(n_pairs, seed=202)
    wr_ladder = {d: pairwise_win_rate(pairs, judge) for d, pairs in ladder.items()}
    return {"wr_equal": wr_equal, "wr_ladder": wr_ladder}


# ---------------------------------------------------------------------------
# 5. 实验 2：注入位置偏差 —— 同等质量，先出场就赢
# ---------------------------------------------------------------------------

def experiment_position(n_pairs: int = 48) -> dict:
    judge = MockJudge(name="judge-pos-biased", position_bias=1.0,
                      noise_sd=0.6, seed=102)
    pairs = make_equal_quality_pairs(n_pairs, seed=203)
    wr_first = pairwise_win_rate(pairs, judge)            # A 放第一位
    wr_second = pairwise_win_rate_reversed(pairs, judge)  # A 放第二位
    return {"wr_first": wr_first, "wr_second": wr_second,
            "bias": wr_first - 0.5}


# ---------------------------------------------------------------------------
# 6. 缓解 1：交换顺序取平均 —— 位置偏差的对症药
# ---------------------------------------------------------------------------

def mitigation_swap(n_pairs: int = 48) -> dict:
    judge = MockJudge(name="judge-pos-biased-swapped", position_bias=1.0,
                      noise_sd=0.6, seed=103)
    pairs = make_equal_quality_pairs(n_pairs, seed=203)   # 与实验 2 同一批数据
    wr_single = pairwise_win_rate(pairs, judge)
    wr_swap = swap_average_win_rate(pairs, judge)
    return {"wr_single": wr_single, "wr_swap": wr_swap,
            "bias_single": wr_single - 0.5, "bias_swap": wr_swap - 0.5}


# ---------------------------------------------------------------------------
# 7. 缓解 2：三 judge 投票 —— 异构偏差互相抵消，同构偏差不行
# ---------------------------------------------------------------------------

def mitigation_panel(n_pairs: int = 48) -> dict:
    pairs = make_equal_quality_pairs(n_pairs, seed=203)
    # 异构面板：三个 judge 位置偏差方向/大小各不相同（模拟不同模型
    # 各有偏好：有的偏第一个、有的偏第二个、有的基本中立）。
    hetero = [
        MockJudge(name="judge-P1", position_bias=+1.0, noise_sd=0.6, seed=111),
        MockJudge(name="judge-P2", position_bias=-1.0, noise_sd=0.6, seed=112),
        MockJudge(name="judge-P3", position_bias=0.0, noise_sd=0.6, seed=113),
    ]
    # 克隆面板：三个"同款" judge（偏差完全同向），仅噪声种子不同。
    clones = [
        MockJudge(name=f"judge-clone-{i}", position_bias=+1.0,
                  noise_sd=0.6, seed=120 + i)
        for i in range(3)
    ]
    single = MockJudge(name="judge-single", position_bias=+1.0,
                       noise_sd=0.6, seed=121)
    return {
        "bias_single": pairwise_win_rate(pairs, single) - 0.5,
        "bias_panel": panel_win_rate(pairs, hetero) - 0.5,
        "bias_clone": panel_win_rate(pairs, clones) - 0.5,
    }


# ---------------------------------------------------------------------------
# 8. 实验 3 + 缓解 3：冗长偏差与长度受控评分（校准惩罚项）
# ---------------------------------------------------------------------------
# 思路分三步：
#   ① 注入冗长偏差：B 系统性更长（质量相同）→ B 胜率飙升；
#   ② 校准：在等质量校准集上回归 Δscore ~ Δlength，斜率 λ̂ 就是
#      "每多一个字骗到多少分"——系数由数据估出，不靠拍脑袋；
#   ③ 纠偏：修正分 = 原始分 - λ̂ × 长度，再定胜负。
# 因为是同一组打分、同一次噪声，纠偏前后构成严格配对比较，
# 效果归因毫无歧义。

def estimate_length_coeff(judge: MockJudge,
                          calib_pairs: List[Tuple[Answer, Answer]]
                          ) -> float:
    """最小二乘估计长度系数：λ̂ = Σ(ΔL·Δs) / Σ(ΔL²)。
    校准对双方质量相同，质量项相减对消，剩下的 Δs 只有
    长度效应 + 噪声——这正是"用等质量数据校准"的妙处。"""
    num = den = 0.0
    for a, b in calib_pairs:
        res = judge.judge_pair(QUESTION, a, b)
        ds = res["scores"][1] - res["scores"][0]
        dl = len(b.text) - len(a.text)
        num += dl * ds
        den += dl * dl
    return num / den if den > 0 else 0.0


def experiment_verbosity(n_pairs: int = 96, n_calib: int = 40) -> dict:
    true_coef = 0.8 / 100.0   # 注入的真值：每字符 +0.008 分（=每百字 +0.8）
    judge = MockJudge(name="judge-verbose", verbosity_bias=0.8,
                      noise_sd=0.6, seed=104)

    # ① 评估集：B 比 A 多 7 句填充（长 ~170 字），质量完全相同
    eval_pairs = make_equal_quality_pairs(n_pairs, seed=204, b_extra_fillers=7)

    # ② 校准集：双方长度差在 ±6 句之间随机，质量仍完全相同
    rng = random.Random(205)
    calib_pairs = []
    for _ in range(n_calib):
        k = rng.randint(-6, 6)          # B 相对 A 的填充句数差
        a = build_answer(rng, 5.0, None, n_fillers=4 + max(0, -k))
        b = build_answer(rng, 5.0, None, n_fillers=4 + max(0, k))
        calib_pairs.append((a, b))
    lambda_hat = estimate_length_coeff(judge, calib_pairs)

    # ③ 同一批打分，同时给出"朴素判决"与"长度纠偏后判决"。
    # 注意：B 是"更长的一方"，所以这里统计的是 B 的胜率
    # （1 - win_points 即 B 视角的得分）——冗长偏差表现为 B 胜率膨胀。
    wins_naive = wins_fixed = 0.0
    for a, b in eval_pairs:
        res = judge.judge_pair(QUESTION, a, b)
        wins_naive += 1.0 - win_points(res["winner"])
        sa = res["scores"][0] - lambda_hat * len(a.text)   # 修正分
        sb = res["scores"][1] - lambda_hat * len(b.text)
        if abs(sa - sb) < 1e-9:
            wins_fixed += 0.5
        else:
            wins_fixed += 1.0 if sb > sa else 0.0
    return {
        "wr_long_naive": wins_naive / n_pairs,
        "wr_long_fixed": wins_fixed / n_pairs,
        "lambda_hat": lambda_hat, "true_coef": true_coef,
        "bias_naive": wins_naive / n_pairs - 0.5,
        "bias_fixed": wins_fixed / n_pairs - 0.5,
    }


# ---------------------------------------------------------------------------
# 9. 实验 4 + 缓解 4：自我偏好 —— 交换无效，匿名化有效
# ---------------------------------------------------------------------------
# 自我偏好是"内容类"偏差：偏袒对象跟着答案本身走。
# 因此先演示 swap-and-average 对它**无效**（重要的阴性结果！），
# 再给出对症的缓解：送评前抹掉风格标记（匿名化），让 judge
# 认不出"这是不是我家的风格"。

def experiment_self_preference(n_pairs: int = 48) -> dict:
    judge = MockJudge(name="judge-self-pref", self_preference=1.0,
                      own_style="散文体", noise_sd=0.6, seed=105)
    # A 是 judge 自己的风格（散文体），B 是另一风格；等质量、等长
    pairs = make_equal_quality_pairs(n_pairs, seed=206,
                                     style_a="散文体", style_b="条列体")
    wr_raw = pairwise_win_rate(pairs, judge)
    # 交换顺序取平均：对位置偏差是解药，对自我偏好应当基本无效
    wr_swap = swap_average_win_rate(pairs, judge)
    # 匿名化：抹掉风格标记后再比，judge 失去识别风格的依据
    anon_pairs = [(Answer(anonymize(a.text), a.quality, None),
                   Answer(anonymize(b.text), b.quality, None))
                  for a, b in pairs]
    wr_anon = pairwise_win_rate(anon_pairs, judge)
    return {
        "wr_raw": wr_raw, "wr_swap": wr_swap, "wr_anon": wr_anon,
        "bias_raw": wr_raw - 0.5,
        "bias_swap": wr_swap - 0.5,
        "bias_anon": wr_anon - 0.5,
    }


# ---------------------------------------------------------------------------
# 10. 自检：断言核心结论（偏差量化数字 + 缓解前后对比）
# ---------------------------------------------------------------------------

def run_self_checks(R: dict) -> None:
    # ---- 实验 1：无偏基线必须"准" --------------------------------------
    # 等质量对照上，无偏 judge 的胜率应贴近 50%（允许抽样噪声）
    assert abs(R["e1"]["wr_equal"] - 0.5) <= 0.15, \
        f"无偏 judge 在等质量对照上胜率({R['e1']['wr_equal']:.3f})偏离 50% 过多"
    # 剂量-反应：质量差越大胜率越高，且最大差距下接近必胜
    wl = R["e1"]["wr_ladder"]
    deltas = sorted(wl)
    assert all(wl[d] > 0.5 for d in deltas), "质量更优的一方胜率必须超过 50%"
    for d_lo, d_hi in zip(deltas, deltas[1:]):
        assert wl[d_lo] < wl[d_hi], \
            f"胜率应随真实质量差单调上升：δ={d_lo}({wl[d_lo]:.3f}) ≥ δ={d_hi}({wl[d_hi]:.3f})"
    assert wl[deltas[-1]] >= 0.90, "最大质量差下胜率应 ≥ 90%"

    # ---- 实验 2：位置偏差被量化地复现 ----------------------------------
    e2 = R["e2"]
    assert e2["wr_first"] >= 0.70, \
        f"注入位置偏差后，第一位胜率({e2['wr_first']:.3f})应 ≥ 70%"
    assert e2["wr_second"] <= 0.30, \
        f"同一答案换到第二位，胜率({e2['wr_second']:.3f})应 ≤ 30%"
    assert e2["wr_first"] - e2["wr_second"] >= 0.5, \
        "仅交换顺序就造成 ≥ 50 个百分点的胜率差，位置偏差才算被坐实"
    bias_pos = e2["bias"]
    assert bias_pos >= 0.20, "位置偏差量级（胜率-0.5）应 ≥ 0.20"

    # ---- 缓解 1：swap-and-average 把位置偏差压到接近 0 -----------------
    m1 = R["m1"]
    assert abs(m1["bias_swap"]) <= 0.08, \
        f"交换取平均后残余偏差({m1['bias_swap']:+.3f})应 ≤ 0.08"
    assert abs(m1["bias_swap"]) <= 0.3 * abs(m1["bias_single"]), \
        "缓解后偏差应缩小到缓解前的 30% 以内"

    # ---- 缓解 2：异构投票有效，克隆投票无效 -----------------------------
    m2 = R["m2"]
    assert abs(m2["bias_panel"]) <= 0.3 * abs(m2["bias_single"]), \
        "异构三 judge 投票后，偏差应缩小到单 judge 的 30% 以内"
    assert abs(m2["bias_clone"]) >= 0.5 * abs(m2["bias_single"]), \
        "克隆面板（同款 judge 投票）不应消除系统性偏差"
    assert abs(m2["bias_panel"]) < abs(m2["bias_clone"]), \
        "异构面板的残余偏差必须小于克隆面板"

    # ---- 实验 3 + 缓解 3：冗长偏差被量化、被校准系数捕获、被纠偏消除 ----
    e3 = R["e3"]
    assert e3["wr_long_naive"] >= 0.75, \
        f"冗长偏差下，更长答案胜率({e3['wr_long_naive']:.3f})应 ≥ 75%"
    assert 0.004 <= e3["lambda_hat"] <= 0.012, \
        f"校准出的长度系数({e3['lambda_hat']:.5f})应在真值 0.008 附近"
    assert abs(e3["bias_fixed"]) <= 0.10, \
        f"长度纠偏后残余偏差({e3['bias_fixed']:+.3f})应 ≤ 0.10"
    assert abs(e3["bias_fixed"]) <= 0.3 * abs(e3["bias_naive"]), \
        "纠偏后偏差应缩小到纠偏前的 30% 以内"

    # ---- 实验 4 + 缓解 4：自我偏好的阴性与阳性结果 ----------------------
    e4 = R["e4"]
    assert e4["wr_raw"] >= 0.70, \
        f"自我偏好下同风格胜率({e4['wr_raw']:.3f})应 ≥ 70%"
    # 阴性结果：交换顺序治不了内容类偏差（这是本实验刻意要展示的）
    assert abs(e4["bias_swap"]) >= 0.6 * abs(e4["bias_raw"]), \
        "swap-and-average 对自我偏好应基本无效（偏差随内容走，不随位置走）"
    # 阳性结果：匿名化切断风格识别后偏差消失
    assert abs(e4["bias_anon"]) <= 0.10, \
        f"匿名化后残余偏差({e4['bias_anon']:+.3f})应 ≤ 0.10"
    assert abs(e4["bias_anon"]) <= 0.3 * abs(e4["bias_raw"]), \
        "匿名化后偏差应缩小到匿名化前的 30% 以内"


# ---------------------------------------------------------------------------
# 演示入口：分步运行全部实验并打印报告
# ---------------------------------------------------------------------------

def _bar(x: float, width: int = 24) -> str:
    """把 0~1 的胜率画成一根 ASCII 条，50% 处用 | 标出公平线。"""
    k = int(round(x * width))
    mid = width // 2
    s = ["·"] * width
    s[mid] = "|"
    for i in range(min(k, width)):
        if s[i] != "|":
            s[i] = "█"
    return "".join(s)


def main() -> None:
    print("=" * 66)
    print("LAB 04 · Judge 偏差量化与缓解（纯标准库 / 确定性仿真）")
    print("=" * 66)
    R: dict = {}

    # [1/6] 无偏基线
    print("\n[1/6] 实验 1 · 无偏 judge 基线：胜率只应反映真实质量差")
    R["e1"] = experiment_baseline()
    print(f"   等质量对照 A 胜率 = {R['e1']['wr_equal']:.3f}"
          f"（公平线 0.500）  {_bar(R['e1']['wr_equal'])}")
    for d, wr in sorted(R["e1"]["wr_ladder"].items()):
        print(f"   质量差 δ={d:<4} → A 胜率 = {wr:.3f}  {_bar(wr)}")

    # [2/6] 位置偏差
    print("\n[2/6] 实验 2 · 注入位置偏差(+1.0)：同等质量，先出场就赢")
    R["e2"] = experiment_position()
    print(f"   A 放第一位 → 胜率 {R['e2']['wr_first']:.3f}  {_bar(R['e2']['wr_first'])}")
    print(f"   A 放第二位 → 胜率 {R['e2']['wr_second']:.3f}  {_bar(R['e2']['wr_second'])}")
    print(f"   位置偏差量化 = 胜率 - 0.5 = {R['e2']['bias']:+.3f}")

    # [3/6] 缓解 1：交换顺序取平均
    print("\n[3/6] 缓解 1 · 交换顺序取平均（swap-and-average）")
    R["m1"] = mitigation_swap()
    print(f"   单次判决偏差 = {R['m1']['bias_single']:+.3f}"
          f" → 交换取平均后 = {R['m1']['bias_swap']:+.3f}")
    print("   原理：位置偏差在两个方向上大小相等、符号相反，平均即对消。")

    # [4/6] 缓解 2：三 judge 投票
    print("\n[4/6] 缓解 2 · 三 judge 投票（异构面板 vs 克隆面板）")
    R["m2"] = mitigation_panel()
    print(f"   单 judge 偏差        = {R['m2']['bias_single']:+.3f}")
    print(f"   异构面板投票后偏差   = {R['m2']['bias_panel']:+.3f}"
          f"   ← 不同 judge 偏差方向不同，互相对冲")
    print(f"   克隆面板投票后偏差   = {R['m2']['bias_clone']:+.3f}"
          f"   ← 同款 judge 偏差同向，投票只是把偏差'合法化'")

    # [5/6] 冗长偏差 + 长度受控纠偏
    print("\n[5/6] 实验 3 · 冗长偏差(+0.8/百字) 与校准长度惩罚项")
    R["e3"] = experiment_verbosity()
    print(f"   更长答案 B 的胜率：朴素判决 = {R['e3']['wr_long_naive']:.3f}"
          f"  {_bar(R['e3']['wr_long_naive'])}")
    print(f"   校准出的长度系数 λ̂ = {R['e3']['lambda_hat']:.5f}"
          f"（注入真值 {R['e3']['true_coef']:.5f} = 每百字 +0.8 分）")
    print(f"   长度纠偏后 B 胜率 = {R['e3']['wr_long_fixed']:.3f}"
          f"  {_bar(R['e3']['wr_long_fixed'])}   ← 回到公平线附近")

    # [6/6] 自我偏好 + 匿名化
    print("\n[6/6] 实验 4 · 自我偏好(+1.0 偏袒'散文体')：交换无效，匿名有效")
    R["e4"] = experiment_self_preference()
    print(f"   同风格 A 胜率：原始 = {R['e4']['wr_raw']:.3f}"
          f"  {_bar(R['e4']['wr_raw'])}")
    print(f"   交换取平均后  = {R['e4']['wr_swap']:.3f}"
          f"  ← 内容类偏差随答案走，交换位置治不了")
    print(f"   匿名化(去标记)后 = {R['e4']['wr_anon']:.3f}"
          f"  {_bar(R['e4']['wr_anon'])}   ← 认不出风格，偏差消失")

    # 汇总表
    print("\n" + "=" * 66)
    print("偏差量化与缓解汇总（bias = 等质量对照下的胜率 - 0.5）")
    print("-" * 66)
    rows = [
        ("位置偏差（单 judge）", R["e2"]["bias"], None),
        ("  ↳ 缓解1 交换取平均", R["m1"]["bias_swap"], R["e2"]["bias"]),
        ("  ↳ 缓解2 异构三judge投票", R["m2"]["bias_panel"], R["m2"]["bias_single"]),
        ("  ↳ 对照 克隆三judge投票", R["m2"]["bias_clone"], R["m2"]["bias_single"]),
        ("冗长偏差（朴素判决）", R["e3"]["bias_naive"], None),
        ("  ↳ 缓解3 校准长度惩罚", R["e3"]["bias_fixed"], R["e3"]["bias_naive"]),
        ("自我偏好（原始）", R["e4"]["bias_raw"], None),
        ("  ↳ 对照 交换取平均(无效)", R["e4"]["bias_swap"], R["e4"]["bias_raw"]),
        ("  ↳ 缓解4 匿名化去标记", R["e4"]["bias_anon"], R["e4"]["bias_raw"]),
    ]
    for name, bias, before in rows:
        shrink = "" if before is None else \
            f"   |偏差|缩小至 {abs(bias) / abs(before):.0%}"
        print(f"   {name:<26} bias = {bias:+.3f}{shrink}")
    print("=" * 66)

    # 自检
    print("\n[自检] 运行核心断言（偏差量化 + 缓解前后对比，阈值有牙齿）...")
    run_self_checks(R)
    print(f"   位置偏差 {R['e2']['bias']:+.3f} → 交换取平均 {R['m1']['bias_swap']:+.3f} ✔")
    print(f"   异构投票 {R['m2']['bias_panel']:+.3f} < 克隆投票 "
          f"{R['m2']['bias_clone']:+.3f} ✔")
    print(f"   冗长偏差 {R['e3']['bias_naive']:+.3f} → 纠偏 "
          f"{R['e3']['bias_fixed']:+.3f}（λ̂={R['e3']['lambda_hat']:.5f}） ✔")
    print(f"   自我偏好 {R['e4']['bias_raw']:+.3f} → 匿名化 "
          f"{R['e4']['bias_anon']:+.3f}（交换无效 {R['e4']['bias_swap']:+.3f}） ✔")
    print("\n✅ 自检通过：eval_lab04_judge_bias.py 全部断言成立")


if __name__ == "__main__":
    main()
