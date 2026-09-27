"""
Eval suite: LangSmith tracing + DeepEval metrics for the CS bot.

Usage:
  python -m app.bootstrap
  python test.py

Optional env (.env):
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_API_KEY=lsv2_...
  LANGCHAIN_PROJECT=cs-smart-bot
  OPENAI_API_KEY=sk-...          # enables DeepEval LLM judges
  USE_MOCK_LLM=true
  EMBEDDING_BACKEND=hash
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# LangSmith: enable before importing graph/langchain stacks when possible
if os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"):
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "cs-smart-bot"))

from langsmith import traceable

from app.bootstrap import main as bootstrap
from app.db.seed import seed_all
from app.graph.supervisor import chat
from app.mcp_bridge import call_mcp_tool, list_mcp_tools
from app.rag.retriever import retrieve_faq


CASES = [
    {
        "name": "greeting",
        "input": "hello",
        "expect_agent": "smalltalk",
        "must_include": ["SteelShop"],
    },
    {
        "name": "off_topic_after_order",
        "input": "hello",
        "expect_agent": "smalltalk",
        "must_include": ["SteelShop"],
        "setup": ["Check order ORD-1001"],
    },
    {
        "name": "policy_return_window",
        "input": "What is the return policy window?",
        "expect_agent": "faq",
        "must_include": ["7"],
        "retrieval_query": "return policy window days",
    },
    {
        "name": "order_lookup",
        "input": "Check order ORD-1001",
        "expect_agent": "order",
        "must_include": ["ORD-1001", "shipped"],
    },
    {
        "name": "payment_lookup",
        "input": "What is the status of payment PAY-9003?",
        "expect_agent": "payment",
        "must_include": ["PAY-9003", "pending"],
    },
    {
        "name": "refund_flow",
        "input": "Please refund ORD-1002",
        "expect_agent": "refund",
        "must_include": ["YES"],
    },
    {
        "name": "product_compare",
        "input": "Compare earbuds",
        "expect_agent": "product",
        "must_include": ["Compare", "Earbuds"],
    },
    {
        "name": "product_specs",
        "input": "Tell me about Wireless Earbuds Pro",
        "expect_agent": "product",
        "must_include": ["SKU-EAR-PRO", "¥299"],
    },
    {
        "name": "refund_confirm_prompt",
        "input": "Please refund ORD-1002",
        "expect_agent": "refund",
        "must_include": ["YES"],
        "setup": ["Check order ORD-1002"],
    },
    {
        "name": "refund_over_limit_approval",
        "input": "yes",
        "expect_agent": "escalate",
        "must_include": ["ticket", "SLA"],
        "setup": ["Check order ORD-1002", "Please refund ORD-1002"],
    },
    {
        "name": "escalate",
        "input": "I want to file a complaint, escalate to a human",
        "expect_agent": "escalate",
        "must_include": ["ticket"],
    },
]


@traceable(name="cs_bot_chat_eval", run_type="chain")
async def traced_chat(session_id: str, message: str) -> dict:
    return await chat(session_id, message)


def _rule_score(reply: str, must_include: list[str]) -> tuple[bool, str]:
    low = reply.lower()
    missing = [m for m in must_include if m.lower() not in low]
    if missing:
        return False, f"missing phrases: {missing}"
    return True, "ok"


async def run_functional_evals() -> list[dict]:
    results = []
    for i, case in enumerate(CASES):
        session = f"eval-{case['name']}-{i}"
        for setup_msg in case.get("setup") or []:
            await traced_chat(session, setup_msg)
        out = await traced_chat(session, case["input"])
        ok_agent = out.get("agent") == case["expect_agent"]
        ok_text, detail = _rule_score(out.get("reply") or "", case["must_include"])
        # User-facing replies must not leak retrieval scores / agent banners
        leak = any(
            bad in (out.get("reply") or "")
            for bad in ("score=", "[Policy Agent", "[Order Agent", "MCP →", "RAG via")
        )
        if leak:
            ok_text, detail = False, "reply leaked internal debug/agent labels"
        passed = ok_agent and ok_text
        row = {
            "name": case["name"],
            "passed": passed,
            "agent": out.get("agent"),
            "expect_agent": case["expect_agent"],
            "detail": detail if ok_agent else f"agent={out.get('agent')} expected={case['expect_agent']}",
            "reply_preview": (out.get("reply") or "")[:160],
            "full_reply": out.get("reply") or "",
        }
        results.append(row)
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {case['name']}: agent={out.get('agent')} | {row['detail']}")
    return results


def run_rag_retrieval_checks() -> list[dict]:
    rows = []
    for case in CASES:
        q = case.get("retrieval_query") or case["input"]
        if case["expect_agent"] not in ("faq", "refund"):
            continue
        hits = retrieve_faq(q, k=3)
        ok = len(hits) > 0
        rows.append({"name": f"rag::{case['name']}", "passed": ok, "hits": len(hits)})
        print(f"[{'PASS' if ok else 'FAIL'}] rag::{case['name']}: hits={len(hits)}")
    return rows


async def run_mcp_checks() -> list[dict]:
    tools = list_mcp_tools()
    order_raw = await call_mcp_tool("get_order_status", {"order_id": "ORD-1001"})
    policy_raw = await call_mcp_tool("search_company_policy", {"query": "refund timeline"})
    rows = [
        {"name": "mcp_tools_registered", "passed": "get_order_status" in tools, "detail": tools},
        {"name": "mcp_get_order", "passed": "ORD-1001" in order_raw, "detail": order_raw[:120]},
        {
            "name": "mcp_search_policy",
            "passed": len(policy_raw) > 20,
            "detail": policy_raw[:120],
        },
    ]
    for r in rows:
        print(f"[{'PASS' if r['passed'] else 'FAIL'}] {r['name']}")
    return rows


def run_deepeval(results: list[dict]) -> None:
    """DeepEval LLM-as-judge when OPENAI_API_KEY is present; otherwise skip gracefully."""
    if not os.getenv("OPENAI_API_KEY"):
        print("\n[SKIP] DeepEval LLM metrics (set OPENAI_API_KEY to enable)")
        return

    try:
        from deepeval import evaluate
        from deepeval.metrics import AnswerRelevancyMetric
        from deepeval.test_case import LLMTestCase
    except ImportError:
        print("\n[SKIP] deepeval not installed — pip install deepeval")
        return

    print("\n=== DeepEval (Answer Relevancy) ===")
    test_cases = []
    for case, row in zip(CASES, results):
        if not row.get("reply_preview"):
            continue
        # Re-fetch is expensive; use preview + note — better to store full reply
        test_cases.append(
            LLMTestCase(
                input=case["input"],
                actual_output=row.get("full_reply") or row["reply_preview"],
            )
        )

    # Re-run chat for full replies under DeepEval (small set)
    async def _full():
        cases = []
        for case in CASES[:3]:
            out = await chat(f"deepeval-{case['name']}", case["input"])
            cases.append(
                LLMTestCase(input=case["input"], actual_output=out["reply"])
            )
        return cases

    test_cases = asyncio.run(_full())
    metric = AnswerRelevancyMetric(threshold=0.5)
    evaluate(test_cases=test_cases, metrics=[metric])


def maybe_print_langsmith_hint() -> None:
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true" and (
        os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    ):
        project = os.getenv("LANGCHAIN_PROJECT", "cs-smart-bot")
        print(f"\nLangSmith tracing ON → project '{project}' (https://smith.langchain.com)")
    else:
        print(
            "\n[HINT] Enable LangSmith with LANGCHAIN_TRACING_V2=true and LANGCHAIN_API_KEY=..."
        )


async def async_main() -> int:
    print("=== CS Smart Bot eval (LangSmith + DeepEval + MCP/RAG checks) ===\n")
    bootstrap()
    seed_all(force=True)

    print("\n--- MCP ---")
    mcp_rows = await run_mcp_checks()

    print("\n--- RAG (Chroma) ---")
    rag_rows = run_rag_retrieval_checks()

    print("\n--- Functional agent routes ---")
    func_rows = await run_functional_evals()

    run_deepeval(func_rows)
    maybe_print_langsmith_hint()

    all_rows = mcp_rows + rag_rows + func_rows
    failed = [r for r in all_rows if not r.get("passed", True)]
    print(f"\nSummary: {len(all_rows) - len(failed)}/{len(all_rows)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))
