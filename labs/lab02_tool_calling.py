#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
实验 02 · Function Calling 工具调度器
================================================================

【对应知识域】Tool Use / Function Calling（第 5 章）

【实验目的】
在 Agent 系统中，模型本身只负责"说出它想调用什么"（输出结构化的
tool_calls），真正把事办成的是工程侧的"工具调度器"。本实验从零实现
一个最小但完整的工具调度器，覆盖 Function Calling 的核心链路：

1. 用 JSON Schema 描述工具（name / description / parameters），这是
   业界协议（OpenAI tools、Anthropic tools、MCP）表达工具元数据的方式；
2. 参数校验：在真正调用工具前，对模型给出的参数做 必填 / 类型 / 枚举
   检查，把错误调用拦截在触达真实服务之前；
3. 并行工具调用：模型一轮返回多个 tool_calls 时，用线程池并发执行，
   并按请求顺序返回结果（顺序用于和 tool_call_id 对齐）；
4. 错误捕获与回填：无论是校验失败还是工具运行时异常，都统一捕获并
   转成结构化 observation 回传给模型，允许模型看到错误后重试一次
   （retry with correction），这是 Agent "自愈"能力的雏形；
5. MockLLM：用确定性脚本模拟一个会产出结构化 tool_calls 的模型，
   不依赖任何真实 API、不需要 API key，保证实验离线可复现。

【核心概念】
- 工具 = schema（给模型看的声明式描述）+ implementation（给代码执行的函数）
- observation：每次工具调用都恰好产生一条结构化结果（成功结果或错误描述）
- 调度器永远不让异常逃逸：错误本身就是一种"结果"，要喂回给模型
- 重试必须带预算（retry budget），否则会陷入死循环

【如何运行】
    python3 /Users/sawzhang/code/agent-interview/labs/lab02_tool_calling.py

纯 Python 标准库实现，无需联网、无需安装依赖、无需 API key。

【思考题（面试延伸）】
1. 为什么工具报错要作为 observation 回填给模型，而不是把异常直接抛到
   顶层？这个设计与 ReAct（Reason + Act）范式是什么关系？
2. 并行执行多个 tool_calls 时，如果工具之间存在依赖（B 需要 A 的结果
   作参数），调度器应该怎么处理？哪些场景必须退回串行调度？
3. 如果模型重试后仍然给出错误参数（甚至幻觉出不存在的工具名），真实
   系统里你会如何设置重试上限、如何做参数"防幻觉"与降级兜底？
================================================================
"""

import ast
import operator
import threading
from concurrent.futures import ThreadPoolExecutor


# ----------------------------------------------------------------------
# 第一部分：工具实现层（相当于真实系统里的内部服务 / SDK）
# ----------------------------------------------------------------------

# 确定性天气数据库：真实系统中这里是一次远程 API 调用
WEATHER_DB = {
    "北京": {"condition": "晴", "temp_c": 32},
    "上海": {"condition": "多云", "temp_c": 29},
}


def get_weather(city: str, unit: str = "celsius") -> dict:
    """天气查询工具的实现。"""
    if city not in WEATHER_DB:
        raise KeyError(f"城市不在数据库中: {city}")
    info = WEATHER_DB[city]
    temp = info["temp_c"]
    if unit == "fahrenheit":
        temp = temp * 9 / 5 + 32
    return {"city": city, "condition": info["condition"], "temperature": temp, "unit": unit}


def _safe_eval(expression: str):
    """基于 ast 白名单的表达式求值器。

    关键设计：绝不直接 eval() 模型给的字符串（注入风险），而是解析成
    语法树后只放行"数字 + 四则运算"这一类节点，其余一律拒绝。
    """
    binary_ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in binary_ops:
            return binary_ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = _eval(node.operand)
            return value if isinstance(node.op, ast.UAdd) else -value
        raise ValueError(f"不允许的表达式语法: {ast.dump(node)}")

    return _eval(ast.parse(expression, mode="eval"))


def calculate(expression: str) -> dict:
    """四则计算工具的实现。"""
    return {"expression": expression, "result": _safe_eval(expression)}


class FlightService:
    """模拟一个不稳定的航班查询服务：第一次调用必然超时，之后成功。

    用来演示"运行时异常被捕获 → 回填给模型 → 模型重试一次即成功"。
    真实世界里这类瞬时故障（网络抖动、服务冷启动）非常常见。
    """

    def __init__(self):
        self.attempts = 0

    def search_flights(self, origin: str, dest: str) -> dict:
        self.attempts += 1
        if self.attempts == 1:
            raise TimeoutError("模拟网络超时（首次调用故意失败，用于演示错误捕获与重试）")
        return {
            "origin": origin,
            "dest": dest,
            "cheapest": "CA1234 08:00 起飞，票价 ¥880",
            "attempt": self.attempts,
        }


# ----------------------------------------------------------------------
# 第二部分：工具的 JSON Schema 描述（这部分会被"喂"给模型）
# ----------------------------------------------------------------------
# 模型正是通过 name / description 决定"调哪个工具"，通过 parameters
# 决定"传什么参数"。schema 写得越准确，模型幻觉参数的概率越低。

TOOL_SCHEMAS = [
    {
        "name": "get_weather",
        "description": "查询指定城市的实时天气",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名，如 '北京'"},
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "温度单位，默认摄氏度",
                },
            },
            "required": ["city"],
        },
    },
    {
        "name": "calculate",
        "description": "计算数值四则表达式，如 '(10 + 2) * 3'",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "表达式字符串"},
            },
            "required": ["expression"],
        },
    },
    {
        "name": "search_flights",
        "description": "查询两个城市之间最便宜的航班",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "出发城市机场代码，如 'PEK'"},
                "dest": {"type": "string", "description": "到达城市机场代码，如 'SHA'"},
            },
            "required": ["origin", "dest"],
        },
    },
]


# ----------------------------------------------------------------------
# 第三部分：工具调度器（本实验的核心）
# ----------------------------------------------------------------------

# JSON Schema 类型名 → Python 类型的映射
_JSON_TYPE_MAP = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
}


class ToolDispatcher:
    """工具调度器：模型与工具实现之间的桥梁。

    三项职责：
    1. validate()         —— 调用前按 JSON Schema 校验参数（必填/类型/枚举）；
    2. execute_one()      —— 执行单次调用，统一捕获一切错误并转成 observation；
    3. execute_parallel() —— 同一轮的多个 tool_calls 用线程池并发执行。
    """

    def __init__(self, schemas, implementations):
        self.schemas = {s["name"]: s for s in schemas}
        self.implementations = implementations
        # 统计信息：既用于演示输出，也供结尾的 assert 自检
        self.stats = {
            "calls": 0,             # 收到的调用请求总数
            "succeeded": 0,         # 成功执行的调用数
            "runtime_errors": 0,    # 工具运行时抛异常的次数
            "validation_errors": 0, # 参数校验失败次数（未真正调用工具）
            "retries": 0,           # 模型在看到错误后重新发起的调用数
        }

    # -------------------- 参数校验 --------------------
    def validate(self, name, arguments):
        """按工具的 JSON Schema 校验参数（实现最常用的子集：required / type / enum）。

        返回 (ok, errors)：ok 为 False 时，errors 是可读的错误描述列表。
        真实系统里可以直接引入 jsonschema 库，这里手写是为了讲清原理。
        """
        errors = []
        if name not in self.schemas:
            # 模型"幻觉"出一个不存在的工具名，是最典型的故障之一
            return False, [f"未知工具名: {name}（模型可能产生了工具幻觉）"]

        schema = self.schemas[name]["parameters"]
        properties = schema.get("properties", {})

        # 1) 必填检查
        for key in schema.get("required", []):
            if key not in arguments:
                errors.append(f"缺少必填参数 '{key}'")

        # 2) 逐个检查已提供参数的类型与枚举
        for key, value in arguments.items():
            if key not in properties:
                errors.append(f"未声明的参数 '{key}'（不在 JSON Schema 中）")
                continue
            prop = properties[key]

            expected_types = _JSON_TYPE_MAP.get(prop.get("type"))
            if expected_types:
                # 注意：Python 里 bool 是 int 的子类，必须显式排除，
                # 否则 True 会通过 integer 校验，这是常见的校验漏洞。
                type_ok = isinstance(value, expected_types) and not (
                    isinstance(value, bool) and prop.get("type") in ("integer", "number")
                )
                if not type_ok:
                    errors.append(
                        f"参数 '{key}' 类型错误: 期望 {prop['type']}, "
                        f"实际 {type(value).__name__}"
                    )
                    continue  # 类型已错，再查枚举没有意义

            if "enum" in prop and value not in prop["enum"]:
                errors.append(
                    f"参数 '{key}' 取值 {value!r} 不在允许范围 {prop['enum']} 内"
                )

        return (len(errors) == 0), errors

    # -------------------- 单次调用 --------------------
    def execute_one(self, call):
        """执行一次工具调用，捕获一切异常并产出结构化 observation。

        关键设计：这个函数永远不向上抛异常。对模型来说，"调用失败"和
        "调用成功"一样，都只是一条需要纳入下一轮推理的观察结果。
        """
        call_id = call.get("id", "?")
        name = call.get("name", "")
        arguments = call.get("arguments", {})
        self.stats["calls"] += 1

        # 打印所在线程名：并行执行时可以看到多个不同的线程
        print(f"    ⚙️  [线程 {threading.current_thread().name}] 执行 {name}({arguments})")

        observation = {
            "tool_call_id": call_id,
            "name": name,
            "ok": False,
            "result": None,
            "error": None,
        }

        # 校验失败：提前拒绝，根本不触达真实实现（保护下游服务）
        ok, errors = self.validate(name, arguments)
        if not ok:
            self.stats["validation_errors"] += 1
            observation["error"] = "参数校验失败: " + "; ".join(errors)
            return observation

        # 校验通过，执行工具实现；运行时异常统一转成错误 observation
        try:
            observation["result"] = self.implementations[name](**arguments)
            observation["ok"] = True
            self.stats["succeeded"] += 1
        except Exception as exc:  # 有意捕获所有异常：错误是要回填给模型的"结果"
            self.stats["runtime_errors"] += 1
            observation["error"] = f"工具运行时错误: {type(exc).__name__}: {exc}"
        return observation

    # -------------------- 并行调用 --------------------
    def execute_parallel(self, calls):
        """并行执行同一轮返回的多个 tool_calls。

        模型在一轮里返回多个 tool_calls，语义上即声明了"这些调用彼此
        独立、可以并行"。这里用 ThreadPoolExecutor 并发执行，再按请求
        顺序收集结果——顺序很重要，模型靠 tool_call_id 把结果和调用配对。
        """
        if not calls:
            return []
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            futures = [pool.submit(self.execute_one, call) for call in calls]
            return [future.result() for future in futures]


# ----------------------------------------------------------------------
# 第四部分：MockLLM（确定性模拟模型）
# ----------------------------------------------------------------------

class MockLLM:
    """确定性模拟模型。

    接口形态与真实 LLM 一致：传入对话 messages，返回二选一：
      - {"tool_calls": [...]}  表示"我要（并行）调用这些工具"；
      - {"content": "..."}     表示"信息齐了，给出最终回答"。

    内部不做任何真实推理，而是按预设规则根据对话历史"决策"，从而输出
    确定、可断言的结果：
      1. 历史里还没有工具结果        → 发出初始并行调用计划；
      2. 最新一轮工具结果中有失败，
         且尚未重试过               → 针对失败发出重试调用；
      3. 其余情况                   → 汇总产出最终回答。
    """

    def __init__(self, initial_calls, retry_calls, final_answer):
        self.initial_calls = initial_calls
        self.retry_calls = retry_calls
        self.final_answer = final_answer
        self.retried = False        # 是否已经重试过（保证"只重试一次"）
        self.generate_count = 0     # 模型推理轮数

    def generate(self, messages):
        self.generate_count += 1
        tool_messages = [m for m in messages if m["role"] == "tool"]

        # 情况 1：还没有任何工具结果 → 初始计划
        if not tool_messages:
            return {"tool_calls": self.initial_calls}

        # 情况 2：上一轮有失败且未重试 → 重试
        latest_failures = [o for o in tool_messages[-1]["observations"] if not o["ok"]]
        if latest_failures and not self.retried:
            self.retried = True
            return {"tool_calls": self.retry_calls}

        # 情况 3：信息齐全 → 最终回答
        return {"content": self.final_answer}


# ----------------------------------------------------------------------
# 第五部分：Agent 主循环（调度模型与工具来回交互）
# ----------------------------------------------------------------------

def run_agent(llm, dispatcher, user_query, max_rounds=5, retry_budget=1):
    """ReAct 式主循环：调用 → 观察 → 决定是否继续。

    参数 retry_budget：模型看到错误后最多允许重试几轮，耗尽即止损，
    防止"报错-重试-再报错"的死循环。真实系统中这是必备的安全阀。
    """
    messages = [{"role": "user", "content": user_query}]
    rounds_used = 0

    for round_idx in range(1, max_rounds + 1):
        rounds_used = round_idx
        response = llm.generate(messages)

        # 分支 A：模型不再请求工具 → 输出最终回答，结束循环
        if not response.get("tool_calls"):
            print(f"\n【第 {round_idx} 轮】模型输出最终回答（不再请求工具）")
            messages.append({"role": "assistant", "content": response["content"]})
            return response["content"], messages, rounds_used

        calls = response["tool_calls"]

        # 判断本轮是否是"出错后的重试"：上一轮 observation 里有失败就算
        had_failure = False
        for msg in reversed(messages):
            if msg["role"] == "tool":
                had_failure = any(not o["ok"] for o in msg["observations"])
                break
        if had_failure:
            if retry_budget <= 0:
                print(f"\n【第 {round_idx} 轮】重试预算已耗尽，放弃失败调用，止损退出")
                break
            retry_budget -= 1
            dispatcher.stats["retries"] += len(calls)
            print(f"\n【第 {round_idx} 轮】检测到上轮失败 → 模型发起重试（{len(calls)} 个调用）")
        else:
            names = ", ".join(c["name"] for c in calls)
            print(f"\n【第 {round_idx} 轮】模型请求 {len(calls)} 个并行工具调用: {names}")

        # 并行执行，并把 observation 回填进对话历史
        observations = dispatcher.execute_parallel(calls)
        for obs in observations:
            status = "✔ 成功" if obs["ok"] else "✘ 失败"
            detail = obs["result"] if obs["ok"] else obs["error"]
            print(f"    ↳ {obs['name']} [{obs['tool_call_id']}] {status}: {detail}")

        messages.append({"role": "assistant", "tool_calls": calls})
        messages.append({"role": "tool", "observations": observations})

    raise RuntimeError(f"Agent 在 {rounds_used} 轮内未能给出最终回答（检查重试预算与工具可用性）")


# ----------------------------------------------------------------------
# 第六部分：演示入口 + 自检
# ----------------------------------------------------------------------

def step(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    print("实验 02 · Function Calling 工具调度器 —— 演示开始")

    # ---------------- 第 1 步：注册工具 ----------------
    step("第 1 步：注册工具（JSON Schema 描述 + Python 实现）")
    flight_service = FlightService()
    implementations = {
        "get_weather": get_weather,
        "calculate": calculate,
        "search_flights": flight_service.search_flights,
    }
    dispatcher = ToolDispatcher(TOOL_SCHEMAS, implementations)
    for schema in TOOL_SCHEMAS:
        params = ", ".join(schema["parameters"]["properties"])
        required = schema["parameters"].get("required", [])
        print(f"  🔧 {schema['name']}({params})  required={required}")
        print(f"       {schema['description']}")

    # ---------------- 第 2 步：运行 Agent ----------------
    step("第 2 步：运行 Agent —— 并行调用 3 个工具（2 成功 + 1 失败 → 重试）")

    # 模型的"初始计划"：一轮内并行请求 3 个相互独立的工具调用
    initial_calls = [
        {"id": "call_001", "name": "get_weather", "arguments": {"city": "北京"}},
        {"id": "call_002", "name": "get_weather", "arguments": {"city": "上海", "unit": "celsius"}},
        {"id": "call_003", "name": "search_flights", "arguments": {"origin": "PEK", "dest": "SHA"}},
    ]
    # 模型看到航班查询失败后的"纠错重试"
    retry_calls = [
        {"id": "call_004", "name": "search_flights", "arguments": {"origin": "PEK", "dest": "SHA"}},
    ]
    final_answer = (
        "北京晴 32°C，上海多云 29°C；"
        "PEK→SHA 最便宜的航班是 CA1234，08:00 起飞，票价 ¥880。"
    )
    llm = MockLLM(initial_calls, retry_calls, final_answer)

    answer, messages, rounds_used = run_agent(
        llm,
        dispatcher,
        user_query="告诉我北京和上海的天气，以及两城之间最便宜的航班。",
    )
    print(f"\n最终回答: {answer}")

    # ---------------- 第 3 步：参数校验演示 ----------------
    step("第 3 步：参数校验演示（拦截模型的幻觉参数 / 错误参数）")
    bad_cases = [
        ("get_weather", {}, "缺少必填"),
        ("get_weather", {"city": 123}, "类型错误"),
        ("get_weather", {"city": "北京", "unit": "kelvin"}, "枚举越界"),
        ("get_weather", {"city": "北京", "zipcode": "100000"}, "未声明参数"),
        ("ghost_tool", {}, "幻觉工具名"),
    ]
    for name, args, label in bad_cases:
        ok, errors = dispatcher.validate(name, args)
        assert not ok, f"校验用例『{label}』本应被拒绝"
        print(f"  🚫 [{label}] {name}{args}")
        print(f"        → {'; '.join(errors)}")

    # 校验失败的调用同样会转成 observation（且不会触达工具实现）
    obs = dispatcher.execute_one(
        {"id": "call_bad", "name": "get_weather", "arguments": {"city": "北京", "unit": "kelvin"}}
    )
    assert obs["ok"] is False and "参数校验失败" in obs["error"]
    print(f"  🚫 校验失败的调用 → 回填模型的 observation: {obs['error']}")

    # ---------------- 第 4 步：自检 ----------------
    step("第 4 步：自检（对关键指标做 assert 断言）")
    stats = dispatcher.stats
    print(f"  调度器统计: {stats}")
    print(f"  模型推理轮数: {llm.generate_count} | Agent 轮数: {rounds_used} | "
          f"航班服务实际被调用: {flight_service.attempts} 次")

    # 1) 业务结果正确：第一轮两个天气调用成功，航班调用失败并回填错误
    tool_messages = [m for m in messages if m["role"] == "tool"]
    first_round = {o["tool_call_id"]: o for o in tool_messages[0]["observations"]}
    assert first_round["call_001"]["ok"] and first_round["call_001"]["result"]["temperature"] == 32
    assert first_round["call_002"]["ok"] and first_round["call_002"]["result"]["condition"] == "多云"
    assert first_round["call_003"]["ok"] is False and "TimeoutError" in first_round["call_003"]["error"]

    # 2) 重试行为正确：恰好重试 1 次，且重试成功（航班服务第 2 次调用成功）
    assert stats["retries"] == 1, f"重试次数应为 1，实际 {stats['retries']}"
    retry_round = tool_messages[1]["observations"]
    assert len(retry_round) == 1 and retry_round[0]["ok"]
    assert retry_round[0]["result"]["attempt"] == 2

    # 3) 调度器统计一致：
    #    calls = 3(首轮) + 1(重试) + 1(第 3 步的校验失败演示) = 5
    assert stats["calls"] == 5
    assert stats["succeeded"] == 3         # 北京、上海、重试后的航班
    assert stats["runtime_errors"] == 1    # 首次航班超时
    assert stats["validation_errors"] == 1 # 第 3 步的 kelvin 非法调用
    assert flight_service.attempts == 2    # 航班服务共被调用 2 次

    # 4) 流程收敛：3 轮内产出预期最终回答
    assert answer == final_answer
    assert rounds_used == 3
    assert llm.generate_count == 3

    print("\n✅ 自检通过")


if __name__ == "__main__":
    main()
