"""MCP tool handlers — shared by FastMCP server and in-process bridge."""

from __future__ import annotations

import json

from app.catalog import compare_products, get_product, search_products
from app.db.enterprise_ops import (
    get_loyalty,
    list_tracking_events,
    nudge_fulfillment,
    request_exchange,
    request_invoice,
    save_satisfaction,
)
from app.db.repository import (
    apply_refund,
    cancel_order,
    list_payments_for_order,
    lookup_order,
    lookup_payment,
    update_shipping_address,
)
from app.rag.retriever import format_context, retrieve_faq


def tool_get_order_status(order_id: str) -> str:
    data = lookup_order(order_id)
    if not data:
        return json.dumps({"error": f"Order {order_id} not found"}, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def tool_get_payment_status(payment_id: str) -> str:
    data = lookup_payment(payment_id)
    if not data:
        return json.dumps({"error": f"Payment {payment_id} not found"}, ensure_ascii=False)
    return json.dumps(data, ensure_ascii=False)


def tool_get_order_payments(order_id: str) -> str:
    data = list_payments_for_order(order_id)
    return json.dumps({"order_id": order_id, "payments": data}, ensure_ascii=False)


def tool_request_refund(order_id: str, reason: str = "customer_request") -> str:
    return json.dumps(apply_refund(order_id, reason=reason), ensure_ascii=False)


def tool_cancel_order(order_id: str, reason: str = "customer_request") -> str:
    return json.dumps(cancel_order(order_id, reason=reason), ensure_ascii=False)


def tool_update_shipping_address(order_id: str, new_address: str) -> str:
    return json.dumps(update_shipping_address(order_id, new_address), ensure_ascii=False)


def tool_get_tracking_events(order_id: str) -> str:
    return json.dumps(list_tracking_events(order_id), ensure_ascii=False)


def tool_request_invoice(order_id: str, title: str = "Personal", tax_id: str = "") -> str:
    return json.dumps(
        request_invoice(order_id, title=title or "Personal", tax_id=tax_id or None),
        ensure_ascii=False,
    )


def tool_request_exchange(order_id: str, reason: str = "size/color change") -> str:
    return json.dumps(request_exchange(order_id, reason=reason), ensure_ascii=False)


def tool_nudge_fulfillment(order_id: str) -> str:
    return json.dumps(nudge_fulfillment(order_id), ensure_ascii=False)


def tool_get_loyalty(customer_id: str = "", order_id: str = "") -> str:
    return json.dumps(
        get_loyalty(customer_id=customer_id or None, order_id=order_id or None),
        ensure_ascii=False,
    )


def tool_save_satisfaction(session_id: str, score: int, comment: str = "") -> str:
    return json.dumps(
        save_satisfaction(session_id, int(score), comment or None),
        ensure_ascii=False,
    )


def tool_search_company_policy(query: str) -> str:
    hits = retrieve_faq(query, k=4)
    return format_context(hits)


def tool_get_product(query: str) -> str:
    product = get_product(query)
    if not product:
        hits = search_products(query, limit=5)
        return json.dumps(
            {"ok": False, "error": f"No exact match for “{query}”", "suggestions": hits},
            ensure_ascii=False,
        )
    return json.dumps({"ok": True, "product": product}, ensure_ascii=False)


def tool_search_products(query: str = "", limit: int = 8) -> str:
    items = search_products(query, limit=int(limit or 8))
    return json.dumps({"ok": True, "query": query, "items": items}, ensure_ascii=False)


def tool_compare_products(a: str, b: str = "") -> str:
    return json.dumps(compare_products(a, b or None), ensure_ascii=False)


MCP_TOOL_MAP = {
    "get_order_status": lambda **kw: tool_get_order_status(kw["order_id"]),
    "get_payment_status": lambda **kw: tool_get_payment_status(kw["payment_id"]),
    "get_order_payments": lambda **kw: tool_get_order_payments(kw["order_id"]),
    "request_refund": lambda **kw: tool_request_refund(
        kw["order_id"], kw.get("reason", "customer_request")
    ),
    "cancel_order": lambda **kw: tool_cancel_order(
        kw["order_id"], kw.get("reason", "customer_request")
    ),
    "update_shipping_address": lambda **kw: tool_update_shipping_address(
        kw["order_id"], kw["new_address"]
    ),
    "get_tracking_events": lambda **kw: tool_get_tracking_events(kw["order_id"]),
    "request_invoice": lambda **kw: tool_request_invoice(
        kw["order_id"], kw.get("title", "Personal"), kw.get("tax_id", "")
    ),
    "request_exchange": lambda **kw: tool_request_exchange(
        kw["order_id"], kw.get("reason", "size/color change")
    ),
    "nudge_fulfillment": lambda **kw: tool_nudge_fulfillment(kw["order_id"]),
    "get_loyalty": lambda **kw: tool_get_loyalty(
        kw.get("customer_id", ""), kw.get("order_id", "")
    ),
    "save_satisfaction": lambda **kw: tool_save_satisfaction(
        kw["session_id"], kw["score"], kw.get("comment", "")
    ),
    "search_company_policy": lambda **kw: tool_search_company_policy(kw["query"]),
    "get_product": lambda **kw: tool_get_product(kw["query"]),
    "search_products": lambda **kw: tool_search_products(kw.get("query", ""), kw.get("limit", 8)),
    "compare_products": lambda **kw: tool_compare_products(kw["a"], kw.get("b", "")),
}
