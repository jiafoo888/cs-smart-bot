"""
Lesson 06 — ReAct、CoT、Function Calling、Prompt Caching
跑：python -m app.bootstrap && python lessons/06_react_cot_function_calling.py

ReAct = Reason + Act 交替：Thought → Action(tool) → Observation → ...
CoT  = Chain-of-Thought：先让模型「一步步想」，再答（或隐式在 tool 决策里）
Function calling = 模型输出结构化 tool_call，运行时执行后把结果塞回 messages
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.bootstrap import main as bootstrap
from app.prompts.cs_prompts import CACHED_STATIC_PREFIX
from app.tools.order_tools import get_order_status


def demo_cot_prompt() -> None:
    print("--- 1) Chain-of-Thought（Prompt 层）---")
    cot = """用户：ORD-1001 发货了吗？

请按步骤思考（可不展示给用户）：
1. 是否需要订单事实？→ 是
2. 应调用哪个工具？→ get_order_status
3. 再组织简短中文回复。"""
    print(cot)
    print("  面试：CoT 提高多步推理；生产可用「隐式 CoT」或专用 reasoning 模型。\n")


def demo_react_loop() -> None:
    print("--- 2) ReAct 手工一轮（与 LangGraph 节点等价）---")
    user = "帮我查 ORD-1001"
    thought = "用户要给订单号查状态，应调用 get_order_status。"
    action = {"name": "get_order_status", "args": {"order_id": "ORD-1001"}}
    observation = get_order_status.invoke(action["args"])
    final = f"根据系统查询：{observation}"
    print("Thought:", thought)
    print("Action:", json.dumps(action, ensure_ascii=False))
    print("Observation:", observation[:120], "...")
    print("Final:", final[:120], "...\n")


def demo_function_calling_messages() -> None:
    print("--- 3) Function calling 消息形态（OpenAI / LangChain 通用）---")
    messages = [
        SystemMessage(content=CACHED_STATIC_PREFIX),
        HumanMessage(content="查 ORD-1001"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "get_order_status",
                    "args": {"order_id": "ORD-1001"},
                }
            ],
        ),
        ToolMessage(
            content=get_order_status.invoke({"order_id": "ORD-1001"}),
            tool_call_id="call_1",
        ),
        AIMessage(content="您的订单 ORD-1001 已发货，物流信息见上文。"),
    ]
    for i, m in enumerate(messages):
        print(f"  [{i}] {type(m).__name__}: {str(m.content)[:60]}{'...' if m.content else '(tool_calls)'}")
    print(
        "\n  本项目 Order Agent 直接 lookup_order（简化）；LangChain @tool 见 app/tools/order_tools.py"
    )
    print("  LangGraph 可把 tool 节点 + LLM 节点连成 ReAct 环。\n")


def demo_prompt_caching() -> None:
    print("--- 4) Prompt caching ---")
    print(
        f"  静态前缀 {len(CACHED_STATIC_PREFIX)} 字符：system + constraints + tools 定义")
    print("  多轮对话仅追加 user/assistant；云厂商对重复前缀计费更低、首 token 更快。")
    print("  工程要点：system 放最前且稳定；不要把 session 特有订单号写进 system。\n")


def main() -> None:
    print("=== Lesson 06: ReAct / CoT / Function calling ===\n")
    bootstrap()
    demo_cot_prompt()
    demo_react_loop()
    demo_function_calling_messages()
    demo_prompt_caching()
    print("面试句：ReAct 是推理与工具交替；function calling 是 API 层的 ReAct Action；")
    print("Supervisor 负责选 Agent，Agent 内可再 ReAct 调多个 tool。")


if __name__ == "__main__":
    main()
