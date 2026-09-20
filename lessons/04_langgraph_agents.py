"""
Lesson 04 — LangGraph：Router / Supervisor / Multi-Agent / session_id
跑：python lessons/04_langgraph_agents.py

面试要点：
- Supervisor 调度，子 Agent 执行
- session_id == checkpointer thread_id → 多轮记住 order_id
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import main as bootstrap
from app.db.seed import seed_all
from app.graph.supervisor import chat


async def demo() -> None:
    print("=== Lesson 04: LangGraph multi-agent ===\n")
    bootstrap()
    seed_all(force=True)

    session = "interview-demo-session"

    turns = [
        "What is your return policy?",
        "Check order ORD-1001",
        "Please refund ORD-1002",
        "I want to file a complaint, escalate to a human",
    ]

    for msg in turns:
        print(f"\nUser[{session}]: {msg}")
        result = await chat(session, msg)
        print(f"Agent={result['agent']} | order_id={result['order_id']}")
        print(result["reply"][:400])

    print("\nSame session follow-up:")
    result = await chat(session, "Check tracking again for ORD-1001")
    print(result["reply"][:400])

    print(
        "\nInterview line: LangGraph state graph + Supervisor routes to "
        "FAQ/Order/Payment/Refund/Escalate; session_id maps to thread_id; "
        "tools go through MCP; policies live in Chroma RAG."
    )


if __name__ == "__main__":
    asyncio.run(demo())
