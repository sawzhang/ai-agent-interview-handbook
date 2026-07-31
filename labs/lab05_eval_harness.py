#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lab05_eval_harness.py — LLM-as-Judge 评估 Harness
==================================================

【实验目的】
    动手实现一个最小可用、但结构完整的「LLM-as-Judge 评估 harness」，让读者理解：
    线上 agent / LLM 应用的质量不是靠"肉眼看几条"，而是靠一套可复现、可聚合、
    可追溯的评估流水线来度量的。本实验覆盖评估流水线的四个核心环节：
        1) 评估集（eval set）   —— {input, 参考答案, 待测输出} 的结构化样本；
        2) Judge + Rubric       —— 用一个"LLM"按评分标准给每个维度打 1~5 分；
        3) 指标聚合             —— 平均分、通过率、各维度分布；
        4) Trace 记录器         —— 记录每次 judge 调用的 input / output / latency，
                                   为可观测性（回放调试、成本分析）打基础。

【对应知识域】
    评估与可观测性（第 8 章）

【核心概念】
    - Eval Set（评估集）: 一组带参考答案的固定样本，是回归测试的基础。样本要同时
      覆盖"好输出"和"坏输出"，否则评估区分不出模型好坏。
    - Rubric（评分标准）: 把"答案好不好"这种主观判断操作化（operationalize）为
      若干可打分的维度。本实验用三个经典维度：
          correctness 正确性 —— 与参考答案的事实重叠程度；
          relevance   相关性 —— 输出内容是否围绕问题、不跑题；
          completeness完整性 —— 参考答案中的关键要点被覆盖了多少。
    - LLM-as-Judge: 用一个 LLM 充当裁判给另一个 LLM 的输出打分，替代昂贵且不可
      扩展的人工评估。真实场景中 judge 是一个 prompt + 模型调用；本实验用确定性
      MockLLM 模拟其"打分能力"，保证结果可复现、零依赖、零成本。
    - 聚合指标: 单条分数没有管理意义，必须聚合为平均分、通过率（综合分 ≥ 阈值）、
      分数分布（发现"双峰"等问题）才能驱动决策。
    - Trace 记录器: 可观测性的最小单元。每次模型调用落一条 span（输入、输出、
      延迟、时间戳），生产环境对应 OpenTelemetry / LangSmith 等系统。

【如何运行】
    python3 /Users/sawzhang/code/agent-interview/labs/lab05_eval_harness.py
    （纯标准库，无需安装任何依赖，无需 API key）

【思考题（面试延伸）】
    1. LLM-as-Judge 相比「人工评估」和「固定字符串匹配」各有什么优劣？judge 模型
       自身的偏差（位置偏差 position bias、冗长偏差 verbosity bias、自我偏好
       self-preference）会如何污染评估结论？有哪些缓解手段（交换顺序、多 judge
       投票、与人工标注做相关性校准）？
    2. 本实验的 MockLLM 可以无缝替换成真实 LLM judge，这种"可替换性"靠的是什么
       接口设计？当 judge 输出带有随机性时，如何保证评估的可重复性与可信度
       （固定 seed/temperature=0、多次采样取均值、记录置信区间）？
    3. 为什么 trace 对 agent 系统比对普通 Web 服务更重要？除 input/output/latency
       外，还应记录哪些字段（token 用量、工具调用链、中间推理、父 span 关系）才能
       支持回放调试与成本归因？
"""

from __future__ import annotations

import json
import random
import re
import statistics
import time
from dataclasses import dataclass
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# 1. 文本基础设施：确定性"语义相似度"的最小替身
# ---------------------------------------------------------------------------
# 真实项目里会用分词器、embedding 余弦相似度等；这里用最简单的「字符/单词 token +
# 集合重叠」来模拟语义比较。关键诉求不是"聪明"，而是确定性：同样的输入永远得到
# 同样的分数，这样评估结果才可复现、可断言。

# 中文按单字切、英文按单词切、数字整体切。例如 "LLM-as-Judge 是裁判"
# -> ['llm', 'as', 'judge', '是', '裁', '判']
_TOKEN_RE = re.compile(r"[一-鿿]|[A-Za-z][A-Za-z0-9_]*|\d+")

# 自然语言里的标点，用来把参考答案切成若干"要点片段"
_SEGMENT_RE = re.compile(r"[，。；：、！？,.;:!?…]+")

# Rubric 的三个维度（英文 key 便于程序处理，中文用于展示）
RUBRIC_DIMS: Tuple[str, ...] = ("correctness", "relevance", "completeness")
DIM_CN: Dict[str, str] = {
    "correctness": "正确性",
    "relevance": "相关性",
    "completeness": "完整性",
}


def tokenize(text: str) -> List[str]:
    """把文本切成小写 token 列表（确定性、无外部依赖）。"""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


def dice(set_a: set, set_b: set) -> float:
    """Dice 系数 = 2|A∩B| / (|A|+|B|)，衡量两个集合的整体重叠度，范围 [0, 1]。
    相比 Jaccard，Dice 对长度差异更宽容，适合比较"候选答案 vs 参考答案"。"""
    if not set_a and not set_b:
        return 0.0
    return 2 * len(set_a & set_b) / (len(set_a) + len(set_b))


def ratio_to_score(ratio: float) -> int:
    """把 [0,1] 的重叠率映射到 rubric 的 1~5 分。
    这几档阈值就是 rubric 的「操作化定义」——真实项目里它应当写在 judge prompt 里
    交给 LLM 判断；这里用阈值函数模拟，好处是完全透明、可单测。"""
    if ratio >= 0.75:
        return 5
    if ratio >= 0.55:
        return 4
    if ratio >= 0.35:
        return 3
    if ratio >= 0.15:
        return 2
    return 1


# ---------------------------------------------------------------------------
# 2. Judge 的 prompt 模板：展示"真实 LLM judge 会长什么样"
# ---------------------------------------------------------------------------
# MockLLM 并不会真的调用大模型，但它会先格式化出这份 prompt（并记录其长度），
# 让读者看到：真实系统中 judge 的行为完全由这段 prompt 定义。把模板保留在代码里，
# 将来把 MockLLM 换成真实客户端时，prompt 可以直接复用。

JUDGE_PROMPT_TEMPLATE = """你是一名严格、中立的评估专家。请依据 rubric 对候选答案打分。

[rubric] 每个维度打 1~5 分：
- correctness 正确性：候选答案与参考答案的事实一致程度；
- relevance 相关性：候选答案是否紧扣问题、不跑题；
- completeness 完整性：参考答案的关键要点被覆盖的程度。

[问题]
{question}

[参考答案]
{reference}

[候选答案]
{candidate}

只输出 JSON：{{"correctness": int, "relevance": int, "completeness": int, "rationale": str}}
"""


# ---------------------------------------------------------------------------
# 3. MockLLM：确定性模拟"LLM 裁判"
# ---------------------------------------------------------------------------

class MockLLM:
    """确定性 mock LLM。对外接口与真实 LLM 客户端一致（输入文本 -> 输出结构化结果），
    因此生产环境可以把本类整体替换成真实 API 客户端而上层不动。

    作为 judge 的"智能"用 token 重叠规则模拟，三个维度分别对应三种不同的比较方式，
    这恰好解释了 rubric 各维度到底在度量什么：
      - 正确性 = 候选与参考答案的整体重叠（Dice）；
      - 相关性 = 候选内容中有多少比例围绕"问题/参考答案"的话题；
      - 完整性 = 参考答案被标点切出的要点片段，有多少被候选覆盖。
    """

    def __init__(self, name: str = "mock-judge-v1", seed: int = 7):
        self.name = name
        # 固定 seed 的随机源只用来生成 mock 延迟，保证 trace 数据也确定可复现
        self._rng = random.Random(seed)

    def judge(self, question: str, reference: str, candidate: str) -> dict:
        """模拟一次 judge 调用：构造 prompt -> "模型推理" -> 返回结构化打分。"""
        prompt = JUDGE_PROMPT_TEMPLATE.format(
            question=question, reference=reference, candidate=candidate
        )
        scores, rationale = self._score(question, reference, candidate)
        # mock 网络/推理延迟 40~240ms；真实系统里这里就是 API 往返耗时
        latency_ms = round(self._rng.uniform(40.0, 240.0), 2)
        return {
            "scores": scores,
            "rationale": "；".join(rationale),
            "latency_ms": latency_ms,
            "prompt_chars": len(prompt),  # 真实场景对应 token 用量/成本
            "judge": self.name,
        }

    # ---- 内部：确定性打分规则 -------------------------------------------
    def _score(self, question: str, reference: str, candidate: str
               ) -> Tuple[Dict[str, int], List[str]]:
        tq, tr, tc = set(tokenize(question)), set(tokenize(reference)), set(tokenize(candidate))

        # 维度 1 —— 正确性：候选与参考答案的整体重叠
        d = dice(tr, tc)
        correctness = ratio_to_score(d)

        # 维度 2 —— 相关性：候选 token 中有多大比例命中"问题或参考答案"的话题词。
        # 用 |候选∩话题| / |候选| 而不是除以 |话题|，是因为长答案天然包含更多词，
        # 我们关心的是"它说的话里有多少是相关的"。
        on_topic = len(tc & (tq | tr)) / max(1, len(tc))
        relevance = ratio_to_score(on_topic)

        # 维度 3 —— 完整性：参考答案按标点切成要点片段，片段内 ≥50% 的词被候选覆盖
        # 就算命中该要点。要点覆盖率再映射到 1~5 分。
        segments = [s for s in _SEGMENT_RE.split(reference) if tokenize(s)]
        covered = 0
        for seg in segments:
            ts = set(tokenize(seg))
            if len(tc & ts) / len(ts) >= 0.5:
                covered += 1
        coverage = covered / max(1, len(segments))
        completeness = ratio_to_score(coverage)

        scores = {
            "correctness": correctness,
            "relevance": relevance,
            "completeness": completeness,
        }
        rationale = [
            f"正确性: Dice(候选,参考)={d:.2f}->{correctness}",
            f"相关性: 话题命中比例={on_topic:.2f}->{relevance}",
            f"完整性: 要点覆盖={covered}/{len(segments)}->{completeness}",
        ]
        return scores, rationale


# ---------------------------------------------------------------------------
# 4. Trace 记录器：可观测性的最小实现
# ---------------------------------------------------------------------------

@dataclass
class TraceSpan:
    """一次模型调用的记录。生产中可扩展 trace_id/parent_id/token 用量等字段。"""
    span_id: int
    call: str               # 调用类型，如 "llm_judge"
    input: dict             # 进入模型的输入
    output: dict            # 模型返回的输出
    latency_ms: float       # 本次调用耗时（mock）
    timestamp: float        # 落库时间（epoch 秒）


class TraceRecorder:
    """极简 trace 记录器：内存中追加 span，并可导出 JSONL。
    对应生产中的 OpenTelemetry / LangSmith / 自建日志管线。"""

    def __init__(self) -> None:
        self.spans: List[TraceSpan] = []

    def record(self, call: str, input_: dict, output: dict, latency_ms: float) -> TraceSpan:
        span = TraceSpan(
            span_id=len(self.spans) + 1,
            call=call,
            input=input_,
            output=output,
            latency_ms=latency_ms,
            timestamp=time.time(),
        )
        self.spans.append(span)
        return span

    def count(self) -> int:
        return len(self.spans)

    def summary(self) -> dict:
        """聚合 trace：调用次数、平均/总延迟、P95 延迟。
        P95 比平均值更能暴露长尾调用，是线上监控最常用的指标之一。"""
        lats = sorted(s.latency_ms for s in self.spans)
        if not lats:
            return {"calls": 0, "avg_latency_ms": 0.0, "p95_latency_ms": 0.0,
                    "total_latency_ms": 0.0}
        p95_idx = min(len(lats) - 1, int(round(0.95 * (len(lats) - 1))))
        return {
            "calls": len(lats),
            "avg_latency_ms": round(sum(lats) / len(lats), 2),
            "p95_latency_ms": lats[p95_idx],
            "total_latency_ms": round(sum(lats), 2),
        }

    def to_jsonl(self) -> str:
        """导出 JSONL（每行一条 span）——落盘后即可被日志系统采集。"""
        return "\n".join(json.dumps(s.__dict__, ensure_ascii=False) for s in self.spans)


# ---------------------------------------------------------------------------
# 5. 评估结果与指标聚合
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    """单条样本的评估结果。"""
    case_id: str
    scores: Dict[str, int]     # 每个 rubric 维度的 1~5 分
    overall: float             # 综合分 = 各维度平均
    passed: bool               # 综合分是否达到通过阈值


def aggregate_metrics(results: List[CaseResult]) -> dict:
    """把逐条结果聚合为决策级指标：
    - overall_avg      全体综合平均分（总体质量水位）；
    - dim_avg          各维度平均分（定位短板维度）；
    - pass_rate        通过率（质量门禁/回归报警的依据）；
    - dim_distribution 各维度 1~5 分布（识别双峰、天花板效应等问题）。
    """
    n = len(results)
    dim_avg = {d: statistics.mean(r.scores[d] for r in results) for d in RUBRIC_DIMS}
    pass_count = sum(1 for r in results if r.passed)
    dist = {d: {s: 0 for s in range(1, 6)} for d in RUBRIC_DIMS}
    for r in results:
        for d in RUBRIC_DIMS:
            dist[d][r.scores[d]] += 1
    return {
        "total": n,
        "overall_avg": statistics.mean(r.overall for r in results),
        "dim_avg": dim_avg,
        "pass_count": pass_count,
        "pass_rate": pass_count / n,
        "dim_distribution": dist,
    }


@dataclass
class EvalReport:
    """一次评估运行的完整报告：逐条结果 + 聚合指标。"""
    results: List[CaseResult]
    metrics: dict
    pass_threshold: float

    def render(self) -> str:
        lines = [
            "=" * 64,
            "评估报告（LLM-as-Judge）",
            "=" * 64,
            f"{_pad('案例', 12)}{_pad('正确性', 9)}{_pad('相关性', 9)}"
            f"{_pad('完整性', 9)}{_pad('综合', 8)}通过",
            "-" * 64,
        ]
        for r in self.results:
            lines.append(
                f"{_pad(r.case_id, 12)}{_pad(str(r.scores['correctness']), 9)}"
                f"{_pad(str(r.scores['relevance']), 9)}"
                f"{_pad(str(r.scores['completeness']), 9)}"
                f"{_pad(f'{r.overall:.2f}', 8)}"
                f"{'PASS' if r.passed else 'FAIL'}"
            )
        m = self.metrics
        lines += [
            "-" * 64,
            f"综合平均分 : {m['overall_avg']:.2f} / 5",
            f"通过率     : {m['pass_rate']:.1%} "
            f"({m['pass_count']}/{m['total']}，阈值={self.pass_threshold})",
            "各维度平均 : " + "  ".join(
                f"{DIM_CN[d]}={m['dim_avg'][d]:.2f}" for d in RUBRIC_DIMS),
            "各维度分布 : ",
        ]
        for d in RUBRIC_DIMS:
            dist = m["dim_distribution"][d]
            lines.append("  " + _pad(DIM_CN[d], 8) + " ".join(
                f"{s}分x{dist[s]}" for s in range(1, 6)))
        lines.append("=" * 64)
        return "\n".join(lines)


# ---- 展示辅助：中文按 2 列宽对齐 -----------------------------------------

def _display_width(s: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in s)


def _pad(s: str, width: int) -> str:
    return s + " " * max(0, width - _display_width(s))


# ---------------------------------------------------------------------------
# 6. 评估 Harness：把 judge、trace、聚合串成流水线
# ---------------------------------------------------------------------------

class EvalHarness:
    """评估流水线编排器。关注点分离：
    - judge    只负责"给一条样本打分"（可替换为真实 LLM）；
    - recorder 只负责"记录每次调用"（可替换为 OTel 上报）；
    - harness  负责遍历评估集、生成结果、聚合指标。
    """

    def __init__(self, judge: MockLLM, recorder: TraceRecorder,
                 pass_threshold: float = 3.5):
        self.judge = judge
        self.recorder = recorder
        self.pass_threshold = pass_threshold

    def evaluate(self, dataset: List[dict]) -> EvalReport:
        results: List[CaseResult] = []
        for case in dataset:
            # 1) 调用 judge（真实系统里是一次 LLM API 请求）
            judgment = self.judge.judge(
                case["input"], case["reference"], case["output"])

            # 2) 每次调用都落 trace —— 可观测性要求"凡调用必记录"
            self.recorder.record(
                call="llm_judge",
                input_={
                    "question": case["input"],
                    "reference": case["reference"],
                    "candidate": case["output"],
                },
                output={
                    "scores": judgment["scores"],
                    "rationale": judgment["rationale"],
                },
                latency_ms=judgment["latency_ms"],
            )

            # 3) 计算综合分与是否通过
            scores = judgment["scores"]
            overall = sum(scores[d] for d in RUBRIC_DIMS) / len(RUBRIC_DIMS)
            results.append(CaseResult(
                case_id=case["id"],
                scores=dict(scores),
                overall=overall,
                passed=overall >= self.pass_threshold,
            ))
        return EvalReport(results, aggregate_metrics(results), self.pass_threshold)


# ---------------------------------------------------------------------------
# 7. 评估集：3 个问题 x（好输出 + 坏输出）= 6 条样本
# ---------------------------------------------------------------------------
# 设计要点：好坏成对出现，同一问题的 reference 完全相同，只有 output 不同。
# 这样"好答案得分 > 坏答案得分"才是对 judge 区分能力的有效检验。

def build_dataset() -> List[dict]:
    return [
        # ---- Q1：LLM-as-Judge 概念题 ----
        {
            "id": "q1-good",
            "input": "什么是 LLM-as-Judge？它主要解决什么问题？",
            "reference": "LLM-as-Judge 是一种评估方法，它用大语言模型充当裁判，"
                         "按照预定义的评分标准给另一个模型的输出打分，"
                         "主要解决人工评估成本高、难以规模化的问题，"
                         "可用于自动化评估和模型对比。",
            "output": "LLM-as-Judge 是一种评估方法：用大语言模型充当裁判，"
                      "按照预定义的评分标准给另一个模型的输出打分；"
                      "主要解决人工评估成本高、难以规模化的问题，"
                      "可用于自动化评估和模型对比。",
        },
        {
            "id": "q1-bad",
            "input": "什么是 LLM-as-Judge？它主要解决什么问题？",
            "reference": "LLM-as-Judge 是一种评估方法，它用大语言模型充当裁判，"
                         "按照预定义的评分标准给另一个模型的输出打分，"
                         "主要解决人工评估成本高、难以规模化的问题，"
                         "可用于自动化评估和模型对比。",
            "output": "今天天气不错，阳光明媚，适合出去散步。",  # 完全跑题
        },
        # ---- Q2：提示词注入风险 ----
        {
            "id": "q2-good",
            "input": "提示词注入攻击有哪些主要风险？",
            "reference": "提示词注入攻击的主要风险包括：模型被诱导泄露敏感数据，"
                         "执行未授权的操作，输出有害内容，绕过系统级的安全约束。",
            "output": "提示词注入攻击的主要风险包括：模型被诱导泄露敏感数据、"
                      "执行未授权的操作、输出有害内容，以及绕过系统级的安全约束。",
        },
        {
            "id": "q2-bad",
            "input": "提示词注入攻击有哪些主要风险？",
            "reference": "提示词注入攻击的主要风险包括：模型被诱导泄露敏感数据，"
                         "执行未授权的操作，输出有害内容，绕过系统级的安全约束。",
            "output": "提示词注入是一种很有趣的技术，应用非常广泛。",  # 沾边但空洞
        },
        # ---- Q3：trace 记录器的作用 ----
        {
            "id": "q3-good",
            "input": "trace 记录器在智能体可观测性中起什么作用？",
            "reference": "trace 记录器会记录每一次模型调用的输入、输出、延迟和中间步骤，"
                         "用于问题定位、成本分析、回放调试和质量监控。",
            "output": "trace 记录器记录每一次模型调用的输入、输出、延迟与中间步骤，"
                      "可用于问题定位、成本分析、回放调试以及质量监控。",
        },
        {
            "id": "q3-bad",
            "input": "trace 记录器在智能体可观测性中起什么作用？",
            "reference": "trace 记录器会记录每一次模型调用的输入、输出、延迟和中间步骤，"
                         "用于问题定位、成本分析、回放调试和质量监控。",
            "output": "trace 记录器就是用来记录的。",  # 相关但几乎没有信息量
        },
    ]


# ---------------------------------------------------------------------------
# 8. 自检：用 assert 验证 judge 区分能力与指标聚合的正确性
# ---------------------------------------------------------------------------

def run_self_checks(report: EvalReport, recorder: TraceRecorder,
                    dataset: List[dict]) -> None:
    results = report.results
    by_id = {r.case_id: r for r in results}
    n = len(results)
    m = report.metrics

    # (a) judge 必须有区分能力：好答案组的平均分严格高于坏答案组
    good_avg = statistics.mean(
        r.overall for r in results if r.case_id.endswith("-good"))
    bad_avg = statistics.mean(
        r.overall for r in results if r.case_id.endswith("-bad"))
    assert good_avg > bad_avg, f"好答案平均分({good_avg})应高于坏答案({bad_avg})"

    # (b) 每一对同题样本：好输出分数更高、且好通过/坏不通过
    for i in (1, 2, 3):
        g, b = by_id[f"q{i}-good"], by_id[f"q{i}-bad"]
        assert g.overall > b.overall, f"q{i}: 好答案应高于坏答案"
        assert g.passed and not b.passed, f"q{i}: 好答案应通过、坏答案应失败"

    # (c) 聚合正确性：综合平均分 == 逐条综合分的均值
    expect_avg = statistics.mean(r.overall for r in results)
    assert abs(m["overall_avg"] - expect_avg) < 1e-9, "综合平均分聚合错误"

    # (d) 聚合正确性：通过率 == 通过条数 / 总条数
    pass_count = sum(1 for r in results if r.passed)
    assert m["pass_count"] == pass_count, "通过条数统计错误"
    assert abs(m["pass_rate"] - pass_count / n) < 1e-12, "通过率聚合错误"

    # (e) 聚合正确性：各维度分布之和 == 样本总数（无漏记、无重记）
    for d in RUBRIC_DIMS:
        assert sum(m["dim_distribution"][d].values()) == n, f"{d} 分布计数错误"

    # (f) 聚合正确性：各维度平均分 == 逐条该维度分数的均值
    for d in RUBRIC_DIMS:
        expect = statistics.mean(r.scores[d] for r in results)
        assert abs(m["dim_avg"][d] - expect) < 1e-9, f"{d} 维度平均分聚合错误"

    # (g) trace 完整性：凡评估必留痕，且延迟为正
    assert recorder.count() == n, "trace 条数应等于评估样本数"
    assert all(s.latency_ms > 0 for s in recorder.spans), "trace 延迟应为正"
    assert all(s.call == "llm_judge" for s in recorder.spans), "trace 调用类型错误"


# ---------------------------------------------------------------------------
# 9. 演示入口：分步运行整条流水线并打印报告
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 64)
    print("LAB 05 · LLM-as-Judge 评估 Harness（纯标准库 / 确定性 mock）")
    print("=" * 64)

    # [1/4] 构建评估集
    dataset = build_dataset()
    good_n = sum(1 for c in dataset if c["id"].endswith("-good"))
    print(f"\n[1/4] 构建评估集：共 {len(dataset)} 条样本"
          f"（好输出 x {good_n}，坏输出 x {len(dataset) - good_n}）")
    for case in dataset:
        print(f"   - {case['id']:<9} 问题: {case['input']}")

    # [2/4] judge 逐条打分
    print("\n[2/4] MockLLM judge 按 rubric（正确性/相关性/完整性）逐条打分：")
    judge = MockLLM(name="mock-judge-v1", seed=7)
    recorder = TraceRecorder()
    harness = EvalHarness(judge=judge, recorder=recorder, pass_threshold=3.5)
    report = harness.evaluate(dataset)
    for r in report.results:
        flag = "PASS" if r.passed else "FAIL"
        print(f"   - {r.case_id:<9} 正确性={r.scores['correctness']} "
              f"相关性={r.scores['relevance']} 完整性={r.scores['completeness']} "
              f"综合={r.overall:.2f} [{flag}]")

    # [3/4] 聚合 + trace 摘要
    print("\n[3/4] 聚合指标与 trace 摘要：")
    s = recorder.summary()
    print(f"   - judge 调用 {s['calls']} 次，平均延迟 {s['avg_latency_ms']} ms，"
          f"P95 {s['p95_latency_ms']} ms，总延迟 {s['total_latency_ms']} ms")
    first = json.loads(recorder.to_jsonl().splitlines()[0])
    print(f"   - 首条 trace span 示例: span_id={first['span_id']} "
          f"call={first['call']} latency_ms={first['latency_ms']} "
          f"scores={first['output']['scores']}")

    # [4/4] 打印完整报告
    print(f"\n[4/4] 评估报告：\n")
    print(report.render())

    # 自检
    print("\n[自检] 运行 assert 断言（judge 区分能力 + 指标聚合 + trace 完整性）...")
    run_self_checks(report, recorder, dataset)
    good_avg = statistics.mean(
        r.overall for r in report.results if r.case_id.endswith("-good"))
    bad_avg = statistics.mean(
        r.overall for r in report.results if r.case_id.endswith("-bad"))
    print(f"   好答案组平均={good_avg:.2f} > 坏答案组平均={bad_avg:.2f} ✔")
    print(f"   通过率={report.metrics['pass_rate']:.1%}，trace "
          f"{recorder.count()} 条 ✔")
    print("\n✅ 自检通过")


if __name__ == "__main__":
    main()
