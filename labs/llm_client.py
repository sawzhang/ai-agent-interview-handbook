"""
labs/llm_client.py — 可复用的真实 LLM 客户端（纯 Python 标准库，零依赖）

============================================================
接入：阿里云百炼「Token Plan 套餐专属」API Key
============================================================
该套餐 Key（sk-sp- 前缀）不走标准 DashScope 端点，而是走一个
**Anthropic Messages API 兼容网关**，路由到 Qwen / GLM / DeepSeek 等模型。

  端点 : https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/messages
  鉴权 : Authorization: Bearer <KEY>
  格式 : Anthropic Messages API（content 为 block 数组，支持 tool_use / tool_result）
  模型 : qwen3.7-max / qwen3.8-max-preview / qwen3.7-plus / qwen3.6-flash / glm-5.2 / deepseek-v4-pro …

============================================================
⚠️ 安全：永远不要把 API Key 写进代码或提交到版本库！
============================================================
本模块只从环境变量读取 Key，按以下优先级查找：
  DASHSCOPE_API_KEY → BAILIAN_API_KEY → ANTHROPIC_AUTH_TOKEN → TOKENPLAN_API_KEY

使用前在终端设置（二选一）：
  export DASHSCOPE_API_KEY='sk-sp-....'        # 当前 shell 有效
  # 或在运行命令前临时注入：
  DASHSCOPE_API_KEY='sk-sp-....' python3 lab09_real_llm_react.py

也可用环境变量覆盖端点与模型：
  export LLM_BASE_URL='https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic'
  export LLM_MODEL='qwen3.7-max'
"""
import os
import json
import urllib.request
import urllib.error

DEFAULT_BASE_URL = "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic"
DEFAULT_MODEL = "qwen3.7-max"
_KEY_ENVS = ("DASHSCOPE_API_KEY", "BAILIAN_API_KEY", "ANTHROPIC_AUTH_TOKEN", "TOKENPLAN_API_KEY")


def get_api_key():
    """从环境变量读取 API Key；找不到返回 None（绝不硬编码）。"""
    for name in _KEY_ENVS:
        v = os.environ.get(name)
        if v:
            return v.strip()
    return None


def has_api_key():
    return get_api_key() is not None


class QwenLLM:
    """阿里云百炼 Token Plan（Anthropic Messages 兼容网关）客户端。

    返回值与 Anthropic Messages API 完全一致：
      resp["content"]      -> [{"type":"text","text":...}, {"type":"tool_use",...}]
      resp["stop_reason"]  -> "end_turn" | "tool_use" | "max_tokens" ...
      resp["usage"]        -> {"input_tokens":.., "output_tokens":..}
    """

    def __init__(self, api_key=None, base_url=None, model=None,
                 max_tokens=1024, temperature=0.0, timeout=120):
        self.api_key = api_key or get_api_key()
        if not self.api_key:
            raise RuntimeError(
                "未找到 API Key。请先设置环境变量，例如：\n"
                "  export DASHSCOPE_API_KEY='sk-sp-....'")
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("LLM_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        # 统计
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0

    def chat(self, messages, tools=None, system=None, max_tokens=None, temperature=None):
        """发起一次对话。messages 为 Anthropic 格式的消息列表。"""
        body = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "messages": messages,
        }
        if system:
            body["system"] = system
        if tools:
            body["tools"] = tools
        t = self.temperature if temperature is None else temperature
        if t is not None:
            body["temperature"] = t

        req = urllib.request.Request(
            self.base_url + "/v1/messages",
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise RuntimeError(f"LLM 调用失败 HTTP {e.code}: {detail[:300]}") from e

        self.calls += 1
        u = resp.get("usage", {})
        self.input_tokens += u.get("input_tokens", 0)
        self.output_tokens += u.get("output_tokens", 0)
        return resp

    def simple(self, prompt, system=None):
        """便捷：单轮纯文本问答，直接返回字符串。"""
        resp = self.chat([{"role": "user", "content": prompt}], system=system)
        return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")

    def stats(self):
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "model": self.model}


if __name__ == "__main__":
    # 自检：python3 llm_client.py  —— 需要已设置 DASHSCOPE_API_KEY
    if not has_api_key():
        print("未检测到 API Key（环境变量 DASHSCOPE_API_KEY 等），跳过真实调用自检。")
        print("设置后重试：export DASHSCOPE_API_KEY='sk-sp-....'")
        raise SystemExit(0)
    llm = QwenLLM()
    print(f"模型: {llm.model}  端点: {llm.base_url}")
    ans = llm.simple("用一句话介绍什么是 ReAct 框架。")
    print("回复:", ans)
    print("统计:", llm.stats())
    assert ans.strip(), "回复不应为空"
    print("✅ llm_client 真实调用自检通过")
