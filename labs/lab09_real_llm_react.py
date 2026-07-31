"""
======================================================================
Lab 09 · 真实 LLM 的原生 Tool-Use ReAct 循环（接入阿里云百炼）
======================================================================
对应知识域：第3章 Agent 核心架构 / 第5章 Tool Use / 第10章 工程化

【实验目的】
  用**真实大模型**（阿里云百炼 Token Plan 网关，Anthropic Messages 兼容）
  跑一个生产级的 tool-use 智能体循环，看清"模型自主决定调用哪个工具、
  拿到结果再继续推理"的完整机制。这与 lab01 的文本 ReAct 不同——这里用
  的是**原生结构化 tool_use / tool_result 协议**（不靠正则解析文本），
  正是 Function Calling / MCP 背后的真实工程形态。

【核心概念】
  1. Anthropic Messages 的 content 是 block 数组：
       - {"type":"text","text":...}        模型的文本
       - {"type":"tool_use","id":..,"name":..,"input":{..}}  模型请求调用工具
     停止原因 stop_reason="tool_use" 表示"我需要工具结果才能继续"。
  2. Agent 循环：调用模型 → 若有 tool_use → 执行工具 → 把 tool_result
     作为 user 消息回填 → 再调模型 …… 直到 stop_reason="end_turn"。
  3. 真实/降级同构：本实验把"模型"抽象成 chat(messages, tools) 接口，
     真实 QwenLLM 与本地 ScriptedMock 返回**完全相同形状**的响应，
     因此同一套循环代码两种模式都能跑——没有 Key 也能验证循环逻辑。

【如何运行】
  # ① 有百炼 Key（真实调用，强烈推荐先 export，切勿写进代码）：
  export DASHSCOPE_API_KEY='sk-sp-....'
  python3 lab09_real_llm_react.py

  # ② 没有 Key（自动降级为脚本化 Mock，验证循环逻辑）：
  python3 lab09_real_llm_react.py

【思考题】
  1. 原生 tool_use 协议相比 lab01 的"文本 ReAct + 正则解析"，在鲁棒性、
     并行调用、错误回填上有哪些优势？（对照第5章 Function Calling）
  2. 如果模型陷入"反复调用同一工具"的死循环，你会加哪些护栏？
     （提示：max_turns、重复检测、工具结果去重——对照第3章失败模式）
  3. 本实验把 LLM 抽象成统一 chat() 接口，这对"大小模型路由 / 灰度切换 /
     离线测试"意味着什么？（对照第10章与 lab08）
"""
import os
import sys
import json
import ast
import operator

# 复用统一客户端（真实 Key 时启用）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from llm_client import QwenLLM, has_api_key
except Exception:
    QwenLLM, has_api_key = None, lambda: False


# ----------------------------------------------------------------------
# 1. 工具定义（Anthropic tools schema）与实现
# ----------------------------------------------------------------------
TOOLS = [
    {
        "name": "get_weather",
        "description": "查询指定城市当前的天气与气温（摄氏度）。",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "城市的中文名，如 北京"}},
            "required": ["city"],
        },
    },
    {
        "name": "calculator",
        "description": "安全地计算一个四则运算数学表达式，返回数值结果。例如 '30*9/5+32'。",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "数学表达式"}},
            "required": ["expression"],
        },
    },
]

# 假天气数据源（确定性，便于断言）
_WEATHER_DB = {
    "北京": {"condition": "晴", "temperature_c": 32},
    "上海": {"condition": "多云", "temperature_c": 29},
}

def tool_get_weather(city):
    if city in _WEATHER_DB:
        return {"city": city, **_WEATHER_DB[city]}
    return {"city": city, "condition": "未知", "temperature_c": 25}

# 安全计算器：只允许数字与 + - * / ( ) 与空白，AST 白名单求值
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"不允许的表达式节点: {ast.dump(node)}")

def tool_calculator(expression):
    result = _safe_eval(ast.parse(expression, mode="eval"))
    return {"expression": expression, "result": round(float(result), 4)}

TOOL_IMPLS = {"get_weather": tool_get_weather, "calculator": tool_calculator}


# ----------------------------------------------------------------------
# 2. 脚本化 Mock（无 Key 时用）——返回与真实 API 完全同构的响应
# ----------------------------------------------------------------------
class ScriptedMockLLM:
    """按 messages 中已出现的 tool_result 数量推进脚本，模拟一个会规划的模型。"""
    def __init__(self):
        self.calls = 0
        self.model = "scripted-mock"
        self.input_tokens = self.output_tokens = 0

    def chat(self, messages, tools=None, system=None, **_):
        self.calls += 1
        done = sum(1 for m in messages if m["role"] == "user"
                   and isinstance(m["content"], list)
                   and any(b.get("type") == "tool_result" for b in m["content"]))
        if done == 0:      # 第一步：先查北京天气
            content = [{"type": "text", "text": "我先查询北京的天气。"},
                       {"type": "tool_use", "id": "tu_1", "name": "get_weather",
                        "input": {"city": "北京"}}]
            stop = "tool_use"
        elif done == 1:    # 第二步：拿到32°C，算华氏度
            content = [{"type": "text", "text": "北京32°C，我来换算成华氏度。"},
                       {"type": "tool_use", "id": "tu_2", "name": "calculator",
                        "input": {"expression": "32*9/5+32"}}]
            stop = "tool_use"
        else:              # 第三步：收尾
            content = [{"type": "text",
                        "text": "北京现在晴天，气温32°C；换算成华氏度约为89.6°F。"}]
            stop = "end_turn"
        return {"content": content, "stop_reason": stop,
                "usage": {"input_tokens": 0, "output_tokens": 0}}


# ----------------------------------------------------------------------
# 3. Agent 循环（真实与 Mock 共用，无任何分支）
# ----------------------------------------------------------------------
def run_agent(llm, question, max_turns=6, verbose=True):
    system = ("你是一个会使用工具的助手。需要外部信息或计算时，调用提供的工具；"
              "得到工具结果后再给出最终中文回答。")
    messages = [{"role": "user", "content": question}]
    tool_calls = []

    for turn in range(1, max_turns + 1):
        resp = llm.chat(messages, tools=TOOLS, system=system)
        content = resp["content"]
        messages.append({"role": "assistant", "content": content})  # 回填助手轮

        for b in content:
            if b.get("type") == "text" and b.get("text", "").strip() and verbose:
                print(f"   💭 [轮{turn}] {b['text']}")

        tool_uses = [b for b in content if b.get("type") == "tool_use"]
        if resp.get("stop_reason") != "tool_use" or not tool_uses:
            final = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            return final.strip(), tool_calls

        results = []
        for tu in tool_uses:
            name, inp = tu["name"], tu.get("input", {})
            tool_calls.append((name, inp))
            try:
                out = TOOL_IMPLS[name](**inp)
                res_text = json.dumps(out, ensure_ascii=False)
                results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                "content": res_text})
                if verbose:
                    print(f"   🔧 [轮{turn}] 调用 {name}({inp}) → {res_text}")
            except Exception as e:                       # 错误回填，让模型自我纠正
                results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                "content": f"工具出错: {e}", "is_error": True})
                if verbose:
                    print(f"   ⚠️ [轮{turn}] {name} 出错: {e}")
        messages.append({"role": "user", "content": results})

    # 超过 max_turns：取最后一段文本兜底
    last = messages[-1]["content"] if messages else []
    tail = "".join(b.get("text", "") for b in last if isinstance(b, dict) and b.get("type") == "text")
    return tail.strip() or "(达到最大轮数未收敛)", tool_calls


# ----------------------------------------------------------------------
# 4. 演示 + 自检
# ----------------------------------------------------------------------
def main():
    use_real = has_api_key() and QwenLLM is not None
    if use_real:
        llm = QwenLLM()
        print(f"🟢 真实模式：{llm.model} @ {llm.base_url}")
    else:
        llm = ScriptedMockLLM()
        print("🟡 降级模式：未检测到 DASHSCOPE_API_KEY，使用脚本化 Mock 验证循环逻辑。")
        print("   （设置 export DASHSCOPE_API_KEY='sk-sp-....' 即可切换为真实模型）")

    question = ("北京现在天气怎么样？如果气温超过 30 摄氏度，"
                "请帮我把它换算成华氏度（公式 F = C*9/5 + 32），并告诉我结果。")
    print("\n" + "=" * 62)
    print("用户提问：", question)
    print("=" * 62)

    final, tool_calls = run_agent(llm, question)

    print("\n" + "-" * 62)
    print("🏁 最终回答：", final)
    print("🔧 工具调用链：", " → ".join(n for n, _ in tool_calls) or "(无)")
    if use_real:
        s = llm.stats()
        print(f"📊 统计：模型 {s['model']}，调用 {s['calls']} 次，"
              f"输入 {s['input_tokens']} tok / 输出 {s['output_tokens']} tok")

    # ---------------- 自检 ----------------
    print("\n" + "=" * 62)
    print("自检断言")
    print("=" * 62)
    assert tool_calls, "应至少发生一次工具调用"
    print(f"  ✔ 发生了 {len(tool_calls)} 次工具调用")
    assert final and len(final) >= 5, "最终回答不应为空"
    print("  ✔ 最终回答非空")
    names = [n for n, _ in tool_calls]
    assert "get_weather" in names, "应调用 get_weather 获取气温"
    print("  ✔ 正确调用了 get_weather")
    # 天气工具应被问到北京
    assert any(("北京" in json.dumps(inp, ensure_ascii=False)) for n, inp in tool_calls if n == "get_weather"), \
        "get_weather 应查询北京"
    print("  ✔ get_weather 查询了北京")

    if not use_real:
        # 降级模式下脚本确定，可做更严格断言
        assert "calculator" in names, "降级模式应触发 calculator"
        assert "89.6" in final, "降级模式最终回答应含华氏度 89.6"
        print("  ✔ [降级] 触发 calculator 且答案含 89.6°F")
    else:
        # 真实模型措辞不定，断言更宽松：应体现换算结果（约 89~90）
        import re
        assert re.search(r"(89|90|华氏|°F|F)", final), "真实回答应体现华氏度换算"
        print("  ✔ [真实] 回答体现了华氏度换算")

    print("\n✅ 自检通过")


if __name__ == "__main__":
    main()
