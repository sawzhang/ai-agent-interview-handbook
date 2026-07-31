#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
Lab 01 · 从零实现 ReAct Agent 循环
============================================================================

【实验目的】
    用纯 Python 标准库手写一个完整的 ReAct（Reasoning + Acting）Agent，
    理解 Agent 主循环的四个环节：
        Thought（思考）→ Action（动作）→ Observation（观察）→ … → Final Answer
    通过一个确定性 MockLLM（不联网、不调 API、不需要 key），把"大模型"
    降维成可预测的脚本，让读者能逐行看懂 Agent 循环的每一处细节。

【对应知识域】
    第 3 章 · Agent 核心架构
    - ReAct 论文（Yao et al., 2022）提出的"边推理边行动"范式
    - Agent = LLM（大脑） + Tools（手脚） + Loop（调度器）+ Memory（轨迹）

【核心概念】
    1. 工具注册表（ToolRegistry）：把普通函数包装成 LLM 可调用的"工具"，
       名字 + 描述 + 实现缺一不可——描述是给模型看的"说明书"。
    2. 文本动作协议：LLM 输出 "Action: xxx / Action Input: yyy" 这样的
       约定格式，Agent 用正则把它解析成结构化调用。这是 function calling
       出现之前最经典的协议，面试高频考点。
    3. 确定性 MockLLM：用"规则表"（谓词 → 回复）模拟 LLM 的行为，
       规则按顺序匹配第一条命中的，等价于一个可测试的状态机。
    4. 安全护栏：最大步数限制（防死循环烧钱）+ 循环检测（同一个动作
       重复 N 次即中止）。真实 Agent 框架（LangChain/LlamaIndex）都有。

【如何运行】
    python3 lab01_react_agent.py
    会依次演示三个场景：
      场景一：两步工具调用解题（search → calculator → 给出答案）
      场景二：循环检测（模型"犯傻"重复同一动作，Agent 及时中止）
      场景三：最大步数限制（模型永不收敛，Agent 强制截断）
    结尾用 assert 自检，全部通过打印 "✅ 自检通过"。

【思考题（面试延伸）】
    1. 本实验用正则解析 "Action/Action Input" 文本。与 OpenAI function
       calling / tool_use 这类结构化 API 相比，各有什么优缺点？
       （提示：鲁棒性、可观测性、对模型的约束力、多模态工具参数……）
    2. 循环检测用"完全相同的 (action, input) 重复 N 次"作为判据。
       真实场景里模型可能每次参数都略有不同却仍在兜圈子，你会怎么
       设计更聪明的检测策略？（提示：语义相似度、状态指纹、进展度量）
    3. ReAct 每轮都把完整轨迹塞回 prompt，token 成本随步数线性增长。
       如果任务需要 50 步，你会如何压缩/管理轨迹上下文？
       （提示：摘要、滑动窗口、分层规划、外部记忆）
============================================================================
"""

import ast
import operator
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# ============================================================================
# 第一部分：工具注册表 —— Agent 的"手"
# ============================================================================

class ToolError(Exception):
    """工具执行失败的统一异常。Agent 会把它降级成 Observation 喂回模型。"""


class ToolRegistry:
    """
    工具注册表。

    设计要点：工具 = 名字 + 描述 + 可调用对象。
    - 名字和描述最终会拼进 prompt，模型靠描述决定"什么时候用什么工具"，
      所以描述质量直接决定 Agent 的表现（面试常问：如何写好工具描述？）。
    - 调用入口 call() 统一捕获异常并转成字符串，保证主循环永不因工具
      崩溃而中断——错误也是一种 Observation，模型有机会自我纠正。
    """

    def __init__(self) -> None:
        # name -> (description, function)
        self._tools: dict[str, Tuple[str, Callable[[str], str]]] = {}

    def register(self, name: str, description: str, fn: Callable[[str], str]) -> None:
        if name in self._tools:
            raise ValueError(f"工具 '{name}' 已注册，名字必须唯一")
        self._tools[name] = (description, fn)

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def describe(self) -> str:
        """生成拼进 prompt 的工具清单（给模型看的说明书）。"""
        return "\n".join(f"- {name}: {desc}" for name, (desc, _) in self._tools.items())

    def call(self, name: str, arg: str) -> str:
        if name not in self._tools:
            # 未知工具不抛异常，而是返回错误观察——让模型有机会改用正确工具
            return f"[Error] 未知工具 '{name}'，可用工具: {self.names()}"
        _, fn = self._tools[name]
        try:
            return fn(arg)
        except Exception as exc:  # noqa: BLE001 —— 故意兜底，见类 docstring
            return f"[ToolError] {type(exc).__name__}: {exc}"


# ------------------------- 内置工具 1：安全计算器 -------------------------
# 绝不用裸 eval()！用 ast 白名单只放行数字与四则运算，杜绝代码注入。
# 这是面试题"如何实现安全的 LLM 计算器"的标准答案。

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval_node(node: ast.AST):
    """递归求值 AST 节点，只允许常量与白名单运算符。"""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _safe_eval_node(node.left)
        right = _safe_eval_node(node.right)
        return _BIN_OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"表达式包含不允许的语法: {ast.dump(node)}")


def calculator(expression: str) -> str:
    """计算一个四则运算表达式，如 '215 * 2 + 1'。"""
    value = _safe_eval_node(ast.parse(expression.strip(), mode="eval").body)
    # 整数化的浮点结果展示为整数（430.0 → 430），更像人类答案
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value)


# ------------------------- 内置工具 2：Mock 搜索 -------------------------
# 用一个字典假装搜索引擎：查询命中返回"网页摘要"，否则返回无结果。
# 真实项目里这里会接搜索 API / 向量检索，接口形状完全一样。

_MOCK_KNOWLEDGE_BASE = {
    "法国首都人口": "法国首都是巴黎，市区人口约 215 万。",
    "埃菲尔铁塔高度": "埃菲尔铁塔位于巴黎，高约 300 米。",
    "光速": "真空中的光速约为 299792458 米/秒。",
}


def search(query: str) -> str:
    """模拟搜索引擎：按查询词返回一条确定性结果。"""
    return _MOCK_KNOWLEDGE_BASE.get(
        query.strip(),
        f"未找到与 '{query.strip()}' 相关的结果。",
    )


# ============================================================================
# 第二部分：MockLLM —— 用"规则脚本"模拟大模型
# ============================================================================

@dataclass
class LLMState:
    """
    MockLLM 决策所需的"世界状态"快照。

    真实 LLM 看到的是拼好的 prompt 字符串；MockLLM 直接看结构化状态，
    两者信息等价，但后者让脚本规则写起来干净利落。
    """
    question: str
    history: List["TrajectoryStep"] = field(default_factory=list)

    @property
    def used_tools(self) -> List[str]:
        """按顺序返回已调用过的工具名。"""
        return [step.action for step in self.history]

    @property
    def last_observation(self) -> str:
        return self.history[-1].observation if self.history else ""

    @property
    def num_tool_calls(self) -> int:
        return len(self.history)


@dataclass
class Rule:
    """一条 MockLLM 规则：谓词命中时，用生成函数产出 LLM 风格的文本。"""
    name: str
    predicate: Callable[[LLMState], bool]
    response: Callable[[LLMState], str]


class MockLLM:
    """
    确定性"大模型"。

    行为定义：按顺序遍历规则表，第一条谓词为 True 的规则获胜，
    返回它生成的文本。没有任何规则命中就报错（确定性失败优于沉默）。

    这本质上是一个有限状态机——面试时可以这样回答："在单测里如何替代
    不可控的 LLM？用脚本化 mock 把非确定性组件变成状态机。"
    """

    def __init__(self, rules: List[Rule]) -> None:
        self.rules = rules
        self.call_count = 0  # 记录被调用次数，便于断言 token 预算

    def generate(self, prompt: str, state: LLMState) -> str:
        # prompt 参数保留真实接口形状（真模型只用它）；MockLLM 用结构化 state 决策
        self.call_count += 1
        for rule in self.rules:
            if rule.predicate(state):
                return rule.response(state)
        raise RuntimeError("MockLLM: 没有任何规则命中，脚本写得不对")


# ============================================================================
# 第三部分：动作解析 —— 把 LLM 的文本翻译成结构化调用
# ============================================================================

@dataclass
class ParsedOutput:
    """LLM 输出的解析结果：要么是工具调用，要么是最终答案。"""
    finished: bool                      # True = 产出了 Final Answer
    thought: str = ""                   # 思考文本（可解释性的来源）
    action: str = ""                    # 工具名
    action_input: str = ""              # 工具参数
    final_answer: str = ""              # 最终答案（finished=True 时有效）
    raw: str = ""                       # 原始输出，调试用


class ParseError(Exception):
    """LLM 输出不符合 ReAct 文本协议。"""


# 三个正则即整个"协议解析器"：Thought / Action+Action Input / Final Answer
_RE_THOUGHT = re.compile(r"Thought\s*[:：]\s*(.+?)(?=\n|$)", re.S)
_RE_ACTION = re.compile(
    r"Action\s*[:：]\s*(?P<name>.+?)\s*\n\s*Action Input\s*[:：]\s*(?P<input>.+?)\s*(?:\n|$)",
    re.S,
)
_RE_FINAL = re.compile(r"Final Answer\s*[:：]\s*(?P<answer>.+)", re.S)


def parse_llm_output(text: str) -> ParsedOutput:
    """
    解析 ReAct 文本协议。优先级：Final Answer > Action > 报错。

    注意这里同时兼容中文冒号"："——真实业务里模型经常中英混用，
    协议解析器必须足够宽容，这是踩过坑的经验。
    """
    thought_match = _RE_THOUGHT.search(text)
    thought = thought_match.group(1).strip() if thought_match else ""

    final_match = _RE_FINAL.search(text)
    if final_match:
        return ParsedOutput(
            finished=True,
            thought=thought,
            final_answer=final_match.group("answer").strip(),
            raw=text,
        )

    action_match = _RE_ACTION.search(text)
    if action_match:
        name = action_match.group("name").strip()
        arg = action_match.group("input").strip()
        if not name:
            raise ParseError(f"Action 名字为空:\n{text}")
        return ParsedOutput(
            finished=False,
            thought=thought,
            action=name,
            action_input=arg,
            raw=text,
        )

    raise ParseError(f"LLM 输出既没有 Action 也没有 Final Answer:\n{text}")


# ============================================================================
# 第四部分：ReAct 主循环 —— Agent 的"调度器"
# ============================================================================

# prompt 模板：展示真实 Agent 每轮喂给模型的完整上下文长什么样。
# MockLLM 并不读它，但构建它能让读者看清"轨迹如何回填进上下文"。
REACT_PROMPT_TEMPLATE = """Answer the question using the tools below.

可用工具:
{tools}

严格使用以下格式:
Thought: 你的推理
Action: 工具名（必须是 [{tool_names}] 之一）
Action Input: 工具输入
Observation: 工具返回结果（由系统填写，你不能自己编造）
……（Thought/Action/Action Input/Observation 可以重复多次）
Thought: 我现在知道最终答案了
Final Answer: 最终答案

Question: {question}
{history}"""


class MaxStepsExceeded(Exception):
    """超过最大迭代步数——防止模型无休止地烧 token。"""


class LoopDetected(Exception):
    """同一 (action, input) 重复达到上限——模型在兜圈子。"""


@dataclass
class TrajectoryStep:
    """轨迹中的一步：一次完整的 Thought→Action→Observation。"""
    thought: str
    action: str
    action_input: str
    observation: str


@dataclass
class AgentResult:
    """Agent 运行结果：答案 + 轨迹 + 统计量（用于断言与计费审计）。"""
    answer: str
    trajectory: List[TrajectoryStep]
    llm_calls: int

    @property
    def tool_calls(self) -> int:
        return len(self.trajectory)


class ReActAgent:
    """
    ReAct Agent 主循环。

    run() 的结构就是整个实验的骨架，逐行读它：
        while 还有预算:
            1. 构建 prompt（工具说明 + 问题 + 历史轨迹）
            2. 让 LLM 生成下一步文本
            3. 解析文本 → 最终答案？收尾；工具调用？继续
            4. 护栏检查：循环检测
            5. 执行工具，把结果作为 Observation 记入轨迹
        超出预算 → MaxStepsExceeded
    """

    def __init__(
        self,
        llm: MockLLM,
        tools: ToolRegistry,
        max_iterations: int = 8,   # 最大 LLM 轮数（含最后产出答案的那轮）
        max_repeat: int = 2,       # 同一 (action, input) 允许执行的最大次数
        verbose: bool = True,      # 是否打印分步轨迹
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.max_iterations = max_iterations
        self.max_repeat = max_repeat
        self.verbose = verbose

    # ---------------- 内部：构建 prompt 与打印 ----------------

    def _build_prompt(self, question: str, trajectory: List[TrajectoryStep]) -> str:
        """把轨迹回填进 prompt——这就是 ReAct 的"上下文记忆"，朴素但有效。"""
        history_lines: List[str] = []
        for step in trajectory:
            history_lines.append(f"Thought: {step.thought}")
            history_lines.append(f"Action: {step.action}")
            history_lines.append(f"Action Input: {step.action_input}")
            history_lines.append(f"Observation: {step.observation}")
        return REACT_PROMPT_TEMPLATE.format(
            tools=self.tools.describe(),
            tool_names=", ".join(self.tools.names()),
            question=question,
            history="\n".join(history_lines),
        )

    def _log(self, *args) -> None:
        if self.verbose:
            print(*args)

    # ---------------- 主循环 ----------------

    def run(self, question: str) -> AgentResult:
        trajectory: List[TrajectoryStep] = []
        self._log(f"❓ Question: {question}\n")

        for iteration in range(1, self.max_iterations + 1):
            state = LLMState(question=question, history=trajectory)
            prompt = self._build_prompt(question, trajectory)
            raw_output = self.llm.generate(prompt, state)
            parsed = parse_llm_output(raw_output)

            self._log(f"── Step {iteration} ──")
            if parsed.thought:
                self._log(f"💭 Thought: {parsed.thought}")

            # 分支 A：模型宣布找到答案 → 收尾
            if parsed.finished:
                self._log(f"🏁 Final Answer: {parsed.final_answer}\n")
                return AgentResult(
                    answer=parsed.final_answer,
                    trajectory=trajectory,
                    llm_calls=self.llm.call_count,
                )

            # 分支 B：工具调用
            self._log(f"⚙️  Action: {parsed.action}")
            self._log(f"📥 Action Input: {parsed.action_input}")

            # 护栏 1：循环检测 —— 完全相同的调用重复太多次就中止
            repeats = sum(
                1
                for s in trajectory
                if s.action == parsed.action and s.action_input == parsed.action_input
            )
            if repeats >= self.max_repeat:
                raise LoopDetected(
                    f"动作 ({parsed.action}, {parsed.action_input!r}) 已重复 "
                    f"{repeats} 次，判定为死循环，中止。"
                )

            # 执行工具，产出 Observation
            observation = self.tools.call(parsed.action, parsed.action_input)
            self._log(f"👁  Observation: {observation}\n")
            trajectory.append(
                TrajectoryStep(
                    thought=parsed.thought,
                    action=parsed.action,
                    action_input=parsed.action_input,
                    observation=observation,
                )
            )

        # 护栏 2：最大步数 —— 循环正常走完说明预算耗尽
        raise MaxStepsExceeded(
            f"超过最大迭代步数 {self.max_iterations}，模型未给出 Final Answer。"
        )


# ============================================================================
# 第五部分：演示与自检
# ============================================================================

def build_demo_registry() -> ToolRegistry:
    """组装演示用的工具箱。"""
    registry = ToolRegistry()
    registry.register(
        "calculator",
        "计算四则运算表达式。输入形如 '215 * 2'，返回数字结果。",
        calculator,
    )
    registry.register(
        "search",
        "查询事实性信息。输入查询词，返回一条知识摘要。",
        search,
    )
    return registry


def build_two_step_llm() -> MockLLM:
    """
    为"两步解题"场景编排 MockLLM 的剧本：
      第 1 轮：还没搜过 → 调用 search 查巴黎人口
      第 2 轮：搜过了但没算过 → 调用 calculator 算两倍
      第 3 轮：算完了 → 产出 Final Answer
    谓词只看轨迹状态，与具体题目解耦，体现"状态机"本质。
    """
    return MockLLM(
        rules=[
            Rule(
                name="先查资料",
                predicate=lambda s: "search" not in s.used_tools,
                response=lambda s: (
                    "Thought: 要回答这个问题，我需要先查巴黎的人口。\n"
                    "Action: search\n"
                    "Action Input: 法国首都人口"
                ),
            ),
            Rule(
                name="再计算",
                predicate=lambda s: "calculator" not in s.used_tools,
                response=lambda s: (
                    "Thought: 搜索结果显示巴黎人口约 215 万，现在计算它的两倍。\n"
                    "Action: calculator\n"
                    "Action Input: 215 * 2"
                ),
            ),
            Rule(
                name="收尾",
                predicate=lambda s: True,  # 兜底规则：前面都走完就该交卷了
                response=lambda s: (
                    f"Thought: 计算得到 {s.last_observation}，这就是答案。\n"
                    f"Final Answer: {s.last_observation}"
                ),
            ),
        ]
    )


def demo_two_step_solving() -> AgentResult:
    """场景一：完整的两步工具调用解题。"""
    print("=" * 62)
    print("场景一：两步工具调用解题（search → calculator → 答案）")
    print("=" * 62)
    agent = ReActAgent(
        llm=build_two_step_llm(),
        tools=build_demo_registry(),
        verbose=True,
    )
    result = agent.run("巴黎人口（万）的两倍是多少？")

    print("📜 完整轨迹摘要:")
    for i, step in enumerate(result.trajectory, 1):
        print(f"   {i}. {step.action}({step.action_input!r}) → {step.observation}")
    print(f"   答案: {result.answer} | 工具调用 {result.tool_calls} 次 | "
          f"LLM 调用 {result.llm_calls} 次\n")
    return result


def demo_loop_detection() -> None:
    """场景二：模型反复做同一个动作 → 循环检测中止。"""
    print("=" * 62)
    print("场景二：循环检测（模型犯傻，重复同一动作）")
    print("=" * 62)
    confused_llm = MockLLM(
        rules=[
            Rule(
                name="鬼打墙",
                predicate=lambda s: True,  # 永远只会这一招
                response=lambda s: (
                    "Thought: 我再搜一次应该就有答案了。\n"
                    "Action: search\n"
                    "Action Input: 法国首都人口"
                ),
            )
        ]
    )
    agent = ReActAgent(
        llm=confused_llm,
        tools=build_demo_registry(),
        max_repeat=2,       # 同一调用最多执行 2 次
        max_iterations=10,  # 放宽步数上限，确保是循环检测先触发
        verbose=False,
    )
    try:
        agent.run("一个永远答不出的问题")
        raise AssertionError("应当触发 LoopDetected，却没有中止！")
    except LoopDetected as exc:
        print(f"   ✔ 循环检测生效: {exc}\n")


def demo_max_steps() -> None:
    """场景三：模型在两个不同动作间横跳、永不交卷 → 最大步数截断。"""
    print("=" * 62)
    print("场景三：最大步数限制（模型永不收敛）")
    print("=" * 62)

    def ping_pong_response(state: LLMState) -> str:
        # 交替查询两个不同词，绕开循环检测，模拟"低效但不重复"的兜圈子
        query = "光速" if state.num_tool_calls % 2 == 0 else "埃菲尔铁塔高度"
        return (
            "Thought: 信息还不够，我再查查别的。\n"
            f"Action: search\n"
            f"Action Input: {query}"
        )

    agent = ReActAgent(
        llm=MockLLM(rules=[Rule("横跳", lambda s: True, ping_pong_response)]),
        tools=build_demo_registry(),
        max_iterations=4,   # 小预算，快速触发截断
        max_repeat=10,      # 放宽循环阈值，确保是步数上限先触发
        verbose=False,
    )
    try:
        agent.run("一个信息永远不够的问题")
        raise AssertionError("应当触发 MaxStepsExceeded，却没有中止！")
    except MaxStepsExceeded as exc:
        print(f"   ✔ 最大步数护栏生效: {exc}\n")


def self_check(result: AgentResult) -> None:
    """用 assert 把"跑通"变成"跑对"：答案、步数、轨迹内容都要对。"""
    print("=" * 62)
    print("自检（assert）")
    print("=" * 62)

    # 1. 最终答案正确：215 万 × 2 = 430
    assert result.answer == "430", f"答案错误: {result.answer!r}，期望 '430'"
    print("   ✔ 最终答案正确: 430")

    # 2. 步数符合预期：恰好两次工具调用（search + calculator）
    assert result.tool_calls == 2, f"工具调用次数异常: {result.tool_calls}，期望 2"
    print("   ✔ 工具调用恰为 2 次")

    # 3. LLM 共被调用 3 轮：search 决策、calculator 决策、产出答案
    assert result.llm_calls == 3, f"LLM 调用轮数异常: {result.llm_calls}，期望 3"
    print("   ✔ LLM 调用恰为 3 轮（2 次工具决策 + 1 次收尾）")

    # 4. 轨迹顺序与内容正确：先 search 后 calculator，计算器输出 430
    first, second = result.trajectory
    assert first.action == "search" and "215" in first.observation
    assert second.action == "calculator" and second.action_input == "215 * 2"
    assert second.observation == "430"
    print("   ✔ 轨迹顺序正确: search → calculator，且 Observation 内容无误")

    # 5. 计算器安全性：拒绝注入（白名单 AST 不放行函数调用）
    injection_result = build_demo_registry().call("calculator", "__import__('os')")
    assert injection_result.startswith("[ToolError]"), injection_result
    print("   ✔ 安全计算器拒绝了代码注入")

    print("\n✅ 自检通过")


def main() -> None:
    result = demo_two_step_solving()
    demo_loop_detection()
    demo_max_steps()
    self_check(result)


if __name__ == "__main__":
    main()
