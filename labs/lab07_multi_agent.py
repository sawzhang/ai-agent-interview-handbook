#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实验 07 · Orchestrator-Worker 多智能体协作
================================================================

【实验目的】
用纯 Python 标准库实现一个最小但完整的 Orchestrator-Worker（编排者-工作者）
多智能体系统，帮助理解多 Agent 协作的核心机制：
  1. Orchestrator 把一个复杂目标拆解为带依赖关系的子任务（plan）；
  2. 按角色（role）把子任务分派给不同的 Worker Agent 执行（dispatch）；
  3. Worker 之间不直接通信，而是通过共享黑板（Blackboard）传递中间结果；
  4. Orchestrator 收集各 Worker 的产出并合并为最终交付物（aggregate）。
演示场景为「调研 + 写作」：orchestrator 把目标拆成 researcher 的调研子任务
与 writer 的写作子任务（writer 依赖 researcher 的产出），最后聚合成报告。

【对应知识域】
《AI Agent 设计模式与工程实践》第 6 章 · Multi-Agent 系统
  - 协作模式对比：Orchestrator-Worker / Pipeline / Group Chat
  - 通信机制：共享黑板（shared memory）vs. 消息传递（message passing）
  - 任务分解、角色分工、依赖调度、结果聚合

【核心概念】
  - Orchestrator：负责「分解 → 分派 → 聚合」三段式编排，是系统的控制中枢；
  - Worker：只专注自己领域的执行，彼此解耦，可独立替换或扩展；
  - Blackboard：可读写的共享数据结构，让信息在 Agent 之间流动而无需直接调用；
  - MockLLM：确定性的模拟模型（基于规则），保证实验可复现、无需 API key。

【如何运行】
    python3 /Users/sawzhang/code/agent-interview/labs/lab07_multi_agent.py
运行成功后会打印分步执行日志，并在结尾输出「✅ 自检通过」。

【思考题（面试延伸）】
  1. 与流水线（Pipeline）模式相比，Orchestrator-Worker 的优势在哪？
     什么情况下 orchestrator 本身会成为瓶颈或单点故障？如何缓解？
  2. 共享黑板在大规模多智能体系统中会遇到哪些问题（写冲突、上下文膨胀、
     权限隔离）？工程上通常用什么手段解决？
  3. 如果 writer 的产出质量不达标，如何设计「orchestrator 评审 → worker
     返工」的反馈回路？终止条件与成本控制策略应该怎么定？
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# 1. MockLLM —— 确定性的模拟「大语言模型」
# ---------------------------------------------------------------------------
class MockLLM:
    """确定性的 Mock LLM。

    设计要点：
      - 真实 LLM 有随机性与网络依赖，不适合教学实验；这里用规则模拟
        「输入 prompt → 输出结果」的行为，同样输入永远得到同样输出。
      - 不同角色（role）走不同的生成规则，模拟真实系统中给不同 Agent
        配置不同 system prompt 所带来的行为差异。
      - `calls` 记录每一次调用（含当时的上下文 key），相当于单元测试中
        的 spy，方便观察系统行为并写断言。
    """

    def __init__(self, role: str):
        self.role = role
        self.calls: list[dict] = []

    def generate(self, prompt: str, context: dict[str, Any] | None = None) -> Any:
        """根据角色选择对应的规则生成结果，并记录调用历史。"""
        context = context or {}
        self.calls.append(
            {"role": self.role, "prompt": prompt, "context_keys": sorted(context.keys())}
        )
        # 约定：角色为 xxx 时，走 _gen_xxx 规则（策略模式，易于扩展新角色）
        handler = getattr(self, f"_gen_{self.role}", None)
        if handler is None:
            return f"[{self.role}] 对「{prompt}」的通用回复"
        return handler(prompt, context)

    # —— planner 角色规则：把目标拆解为带依赖关系的子任务列表 ——
    def _gen_planner(self, prompt: str, context: dict) -> list[dict]:
        m = re.search(r"『(.+?)』", prompt)
        topic = m.group(1) if m else prompt
        return [
            {
                "id": 1,
                "role": "researcher",
                "instruction": f"围绕『{topic}』主题进行调研，给出 3 条要点",
                "depends_on": [],  # 调研无前置依赖，可第一个执行
            },
            {
                "id": 2,
                "role": "writer",
                "instruction": f"基于黑板上的调研结果，撰写一篇关于『{topic}』的短文",
                "depends_on": [1],  # 写作依赖调研完成（子任务 #1）
            },
        ]

    # —— researcher 角色规则：产出结构化的调研要点 ——
    def _gen_researcher(self, prompt: str, context: dict) -> str:
        m = re.search(r"『(.+?)』", prompt)
        topic = m.group(1) if m else "未知主题"
        return "\n".join(
            [
                f"[调研要点1] {topic}正从单体 Agent 工具走向多智能体协作范式；",
                f"[调研要点2] Orchestrator-Worker 架构通过规划与执行的分工提升整体可靠性；",
                f"[调研要点3] 共享黑板机制降低了 Agent 间的通信与上下文重复成本。",
            ]
        )

    # —— writer 角色规则：读取黑板上的调研结果并组织成文 ——
    def _gen_writer(self, prompt: str, context: dict) -> str:
        # 关键点：writer 不直接调用 researcher，而是从 context（黑板快照）里
        # 读取前序产出，这正是黑板模式「间接通信」的体现。
        research = context.get("research", "")
        first_point = research.splitlines()[0].rstrip("；") if research else "（缺少调研材料）"
        return (
            f"《短文》多智能体协作是解决复杂任务的关键路径。"
            f"正如调研所指出的：{first_point}。"
            f"在 Orchestrator-Worker 架构中，编排者负责分解与聚合，"
            f"Worker 负责专业执行，黑板承载共享状态，"
            f"三者配合即可完成从目标到交付物的完整流程。"
        )


# ---------------------------------------------------------------------------
# 2. Blackboard —— 共享黑板：Agent 之间间接通信的媒介
# ---------------------------------------------------------------------------
class Blackboard:
    """共享黑板（shared memory）。

    设计要点：
      - Worker 之间不互相调用，而是「写入结果 / 读取前序结果」，实现松耦合；
      - `history` 记录 (作者, key)，让信息流向可追溯，也是自检断言的依据；
      - `snapshot()` 返回浅拷贝，Worker 拿到一致的读视图，不会误改黑板。
    """

    def __init__(self):
        self._data: dict[str, Any] = {}
        self.history: list[tuple[str, str]] = []

    def write(self, key: str, value: Any, author: str) -> None:
        self._data[key] = value
        self.history.append((author, key))

    def read(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def snapshot(self) -> dict[str, Any]:
        return dict(self._data)


# ---------------------------------------------------------------------------
# 3. WorkerAgent —— 带角色的工作者
# ---------------------------------------------------------------------------
@dataclass
class WorkerAgent:
    """单个 Worker Agent。

    属性：
      name:         实例名（如 researcher-1），用于日志与黑板署名；
      role:         角色类型，orchestrator 据此分派子任务；
      instructions: 岗位说明（相当于 system prompt，此处仅记录展示）；
      llm:          该 Worker 持有的模拟模型；
      output_key:   产出写入黑板时使用的 key（约定接口）。
    """

    name: str
    role: str
    instructions: str
    llm: MockLLM
    output_key: str

    def work(self, instruction: str, blackboard: Blackboard) -> Any:
        # 三步走：读黑板（拿前序上下文）→ 调模型生成 → 写回黑板（供后续使用）
        context = blackboard.snapshot()
        output = self.llm.generate(instruction, context)
        blackboard.write(self.output_key, output, author=self.name)
        return output


# ---------------------------------------------------------------------------
# 4. Subtask & Orchestrator —— 子任务与编排者
# ---------------------------------------------------------------------------
@dataclass
class Subtask:
    """带依赖关系的子任务。status 取 pending / running / done。"""

    id: int
    role: str
    instruction: str
    depends_on: list[int] = field(default_factory=list)
    status: str = "pending"


class Orchestrator:
    """编排者：plan（分解）→ dispatch（分派）→ aggregate（聚合）。

    与 Pipeline 的区别：执行顺序不是写死的，而是由子任务间的 depends_on
    动态决定——只要依赖已满足即可执行，天然支持并行调度（本实验串行演示）。
    """

    def __init__(self, name: str, llm: MockLLM, workers: list[WorkerAgent]):
        self.name = name
        self.llm = llm
        # 角色 → Worker 的映射表，分派时按角色查人
        self.workers_by_role: dict[str, WorkerAgent] = {w.role: w for w in workers}

    def plan(self, goal: str) -> list[Subtask]:
        """调用自己的 LLM 把目标拆解为子任务列表。"""
        raw = self.llm.generate(f"请把以下目标拆解为子任务：{goal}")
        return [Subtask(**item) for item in raw]

    def pick_next_ready(self, subtasks: list[Subtask], done_ids: set[int]) -> Subtask | None:
        """简易依赖调度器：选出依赖已全部完成、且尚未执行的下一个子任务。"""
        for st in subtasks:
            if st.status == "pending" and set(st.depends_on) <= done_ids:
                return st
        return None

    def dispatch(self, subtask: Subtask, blackboard: Blackboard) -> WorkerAgent:
        """按角色把子任务分派给对应 Worker 并执行。"""
        worker = self.workers_by_role.get(subtask.role)
        if worker is None:
            raise RuntimeError(f"没有角色为 {subtask.role} 的可用 Worker")
        subtask.status = "running"
        worker.work(subtask.instruction, blackboard)
        subtask.status = "done"
        return worker

    def run(self, goal: str, blackboard: Blackboard) -> str:
        """端到端执行：分解 → 按依赖循环分派 → 聚合。"""
        subtasks = self.plan(goal)
        done_ids: set[int] = set()
        while len(done_ids) < len(subtasks):
            st = self.pick_next_ready(subtasks, done_ids)
            if st is None:
                raise RuntimeError("子任务存在依赖环或依赖缺失，无法继续调度")
            self.dispatch(st, blackboard)
            done_ids.add(st.id)
        return self.aggregate(goal, subtasks, blackboard)

    def aggregate(self, goal: str, subtasks: list[Subtask], blackboard: Blackboard) -> str:
        """从黑板读取各 Worker 产出，合并为最终报告。"""
        sections = [f"=== 最终报告 ===\n目标：{goal}"]
        for st in subtasks:
            worker = self.workers_by_role[st.role]
            output = blackboard.read(worker.output_key)
            sections.append(f"\n--- 子任务 #{st.id} · {worker.name}（{worker.role}）---\n{output}")
        sections.append(f"\n【聚合完成】共执行 {len(subtasks)} 个子任务")
        return "\n".join(sections)


# ---------------------------------------------------------------------------
# 5. 演示入口：拆解「调研 + 写作」任务并自检
# ---------------------------------------------------------------------------
def build_team() -> tuple[Orchestrator, list[WorkerAgent]]:
    """组建一个最小团队：1 个 orchestrator + researcher / writer 两个 worker。"""
    researcher = WorkerAgent(
        name="researcher-1",
        role="researcher",
        instructions="负责围绕主题收集、整理背景资料",
        llm=MockLLM(role="researcher"),
        output_key="research",
    )
    writer = WorkerAgent(
        name="writer-1",
        role="writer",
        instructions="负责基于调研材料撰写正文",
        llm=MockLLM(role="writer"),
        output_key="draft",
    )
    orchestrator = Orchestrator(
        name="orch-1",
        llm=MockLLM(role="planner"),
        workers=[researcher, writer],
    )
    return orchestrator, [researcher, writer]


def main() -> None:
    print("=" * 62)
    print("实验 07 · Orchestrator-Worker 多智能体协作")
    print("=" * 62)

    orchestrator, workers = build_team()
    blackboard = Blackboard()
    goal = "请围绕主题『AI Agent』完成一篇报告：先调研，后写作。"

    # ---- 步骤 1：orchestrator 接收目标并拆解 ----
    print(f"\n【步骤 1】Orchestrator '{orchestrator.name}' 接收目标：\n  {goal}")
    subtasks = orchestrator.plan(goal)
    print("  拆解出的子任务：")
    for st in subtasks:
        deps = f"depends_on={st.depends_on}" if st.depends_on else "无依赖"
        print(f"    #{st.id} [{st.role}] {st.instruction}（{deps}）")

    # ---- 步骤 2：按依赖顺序分派执行，Worker 把产出写回黑板 ----
    print("\n【步骤 2】按依赖顺序分派执行（Worker 产出写回黑板）：")
    done_ids: set[int] = set()
    while len(done_ids) < len(subtasks):
        st = orchestrator.pick_next_ready(subtasks, done_ids)
        assert st is not None, "调度不应在此处卡死"
        worker = orchestrator.dispatch(st, blackboard)
        done_ids.add(st.id)
        preview = str(blackboard.read(worker.output_key)).splitlines()[0]
        print(f"  → 分派 #{st.id} 给 {worker.name}（{worker.role}）")
        print(f"    ✔ 完成，黑板写入 key '{worker.output_key}'，预览：{preview}")

    # ---- 步骤 3：查看黑板状态（共享状态的可视化）----
    print(f"\n【步骤 3】黑板当前状态 keys={sorted(blackboard.snapshot().keys())}，写入历史：")
    for author, key in blackboard.history:
        print(f"    - {author} 写入了 '{key}'")

    # ---- 步骤 4：orchestrator 聚合最终交付物 ----
    print("\n【步骤 4】Orchestrator 聚合最终报告：")
    report = orchestrator.aggregate(goal, subtasks, blackboard)
    print(report)

    # ---- 自检断言 ----
    print("\n" + "-" * 62)
    print("自检断言：")

    # (1) 目标被正确拆解，且所有子任务都执行完毕
    assert len(subtasks) == 2, "目标应被拆解为 2 个子任务"
    assert all(st.status == "done" for st in subtasks), "所有子任务都应执行完毕"
    print("  ✔ 目标拆解为 2 个子任务，且全部执行完毕")

    # (2) 黑板上包含两个 worker 的产出
    bb = blackboard.snapshot()
    assert set(bb.keys()) == {"research", "draft"}, "黑板应包含 researcher 与 writer 的产出"
    print("  ✔ 黑板包含 research 与 draft 两个 key")

    # (3) 聚合结果确实合并了各 worker 的产出
    researcher = orchestrator.workers_by_role["researcher"]
    writer = orchestrator.workers_by_role["writer"]
    assert bb["research"] in report, "聚合报告应包含 researcher 的完整产出"
    assert bb["draft"] in report, "聚合报告应包含 writer 的完整产出"
    print("  ✔ 聚合报告包含每个 worker 的产出")

    # (4) writer 生成时的上下文确实读到了 research —— 证明黑板信息流成立
    writer_ctxs = [c["context_keys"] for c in writer.llm.calls]
    assert any("research" in keys for keys in writer_ctxs), \
        "writer 应在写作前从黑板读到 research 结果"
    print("  ✔ writer 写作前从黑板读到了调研结果（黑板信息流成立）")

    # (5) orchestrator 只规划了一次，且调研产出包含主题关键词
    assert len(orchestrator.llm.calls) == 1, "orchestrator 应只规划一次"
    assert "AI Agent" in bb["research"], "调研产出应包含目标主题"
    print("  ✔ orchestrator 只规划一次，调研产出包含目标主题")

    print("\n✅ 自检通过")


if __name__ == "__main__":
    main()
