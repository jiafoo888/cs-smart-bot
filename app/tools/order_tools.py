"""LangChain Tools wrapping the MCP tool surface (same schemas as MCP server)."""

from __future__ import annotations

import asyncio
import json
import re

from langchain_core.tools import tool

from app.mcp_bridge import call_mcp_tool


def extract_order_id(text: str) -> str | None:
    m = re.search(r"ORD-\d{4}", text.upper())
    return m.group(0) if m else None


def extract_payment_id(text: str) -> str | None:
    m = re.search(r"PAY-\d{4}", text.upper())
    return m.group(0) if m else None


def extract_new_address(text: str) -> str | None:
    """Pull address after 'to ...' / 'address ...' phrases."""
    m = re.search(
        r"(?:update address(?:\s+for\s+ORD-\d{4})?\s+to|change address(?:\s+for\s+ORD-\d{4})?\s+to|new address[:\s]+|ship(?:ping)? to)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(" .")
    m = re.search(r"\bto\s+(.+)$", text, flags=re.IGNORECASE)
    if m and "ord-" not in m.group(1).lower():
        return m.group(1).strip(" .")
    return None


def _run(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Already in async loop (FastAPI): run in a thread with a fresh loop
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


@tool
def get_order_status(order_id: str) -> str:
    """Look up order details including customer, shipping, and linked payments."""
    return _run(call_mcp_tool("get_order_status", {"order_id": order_id}))


@tool
def get_payment_status(payment_id: str) -> str:
    """Look up a payment by PAY-xxxx id."""
    return _run(call_mcp_tool("get_payment_status", {"payment_id": payment_id}))


@tool
def get_order_payments(order_id: str) -> str:
    """List all payments for an order."""
    return _run(call_mcp_tool("get_order_payments", {"order_id": order_id}))


@tool
def request_refund(order_id: str, reason: str = "customer_request") -> str:
    """Request a refund for a shipped or delivered order."""
    return _run(call_mcp_tool("request_refund", {"order_id": order_id, "reason": reason}))


@tool
def cancel_order(order_id: str, reason: str = "customer_request") -> str:
    """Cancel an unshipped order (processing or paid)."""
    return _run(call_mcp_tool("cancel_order", {"order_id": order_id, "reason": reason}))


@tool
def update_shipping_address(order_id: str, new_address: str) -> str:
    """Update shipping address before the order ships."""
    return _run(
        call_mcp_tool(
            "update_shipping_address",
            {"order_id": order_id, "new_address": new_address},
        )
    )


@tool
def search_company_policy(query: str) -> str:
    """RAG search over company policies stored in Chroma."""
    return _run(call_mcp_tool("search_company_policy", {"query": query}))


ORDER_TOOLS = [get_order_status, get_order_payments, cancel_order, update_shipping_address]
PAYMENT_TOOLS = [get_payment_status, get_order_payments]
REFUND_TOOLS = [get_order_status, request_refund]
POLICY_TOOLS = [search_company_policy]
ALL_TOOLS = [
    get_order_status,
    get_payment_status,
    get_order_payments,
    request_refund,
    cancel_order,
    update_shipping_address,
    search_company_policy,
]
