"""
MCP server for SteelShop CS tools.

Run: python -m app.mcp_server
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_tools import (
    tool_cancel_order,
    tool_compare_products,
    tool_get_loyalty,
    tool_get_order_payments,
    tool_get_order_status,
    tool_get_payment_status,
    tool_get_product,
    tool_get_tracking_events,
    tool_nudge_fulfillment,
    tool_request_exchange,
    tool_request_invoice,
    tool_request_refund,
    tool_save_satisfaction,
    tool_search_company_policy,
    tool_search_products,
    tool_update_shipping_address,
)

mcp = FastMCP("steelshop-cs-bot")


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Look up order details."""
    return tool_get_order_status(order_id)


@mcp.tool()
def get_payment_status(payment_id: str) -> str:
    """Look up payment status."""
    return tool_get_payment_status(payment_id)


@mcp.tool()
def get_order_payments(order_id: str) -> str:
    """List payments for an order."""
    return tool_get_order_payments(order_id)


@mcp.tool()
def request_refund(order_id: str, reason: str = "customer_request") -> str:
    """Refund a shipped/delivered order."""
    return tool_request_refund(order_id, reason=reason)


@mcp.tool()
def cancel_order(order_id: str, reason: str = "customer_request") -> str:
    """Cancel an unshipped order."""
    return tool_cancel_order(order_id, reason=reason)


@mcp.tool()
def update_shipping_address(order_id: str, new_address: str) -> str:
    """Update address before shipping."""
    return tool_update_shipping_address(order_id, new_address)


@mcp.tool()
def get_tracking_events(order_id: str) -> str:
    """Mock carrier tracking timeline for an order."""
    return tool_get_tracking_events(order_id)


@mcp.tool()
def request_invoice(order_id: str, title: str = "Personal", tax_id: str = "") -> str:
    """Issue an e-invoice for an order."""
    return tool_request_invoice(order_id, title=title, tax_id=tax_id)


@mcp.tool()
def request_exchange(order_id: str, reason: str = "size/color change") -> str:
    """Submit an exchange request."""
    return tool_request_exchange(order_id, reason=reason)


@mcp.tool()
def nudge_fulfillment(order_id: str) -> str:
    """Ask warehouse to prioritize shipping for an unshipped order."""
    return tool_nudge_fulfillment(order_id)


@mcp.tool()
def get_loyalty(customer_id: str = "", order_id: str = "") -> str:
    """Look up loyalty points and coupons."""
    return tool_get_loyalty(customer_id=customer_id, order_id=order_id)


@mcp.tool()
def save_satisfaction(session_id: str, score: int, comment: str = "") -> str:
    """Save a 1–5 CSAT rating for the session."""
    return tool_save_satisfaction(session_id, score, comment)


@mcp.tool()
def search_company_policy(query: str) -> str:
    """RAG search over policy knowledge base."""
    return tool_search_company_policy(query)


@mcp.tool()
def get_product(query: str) -> str:
    """Get full product sheet by name or SKU."""
    return tool_get_product(query)


@mcp.tool()
def search_products(query: str = "", limit: int = 8) -> str:
    """Search the SteelShop product catalog."""
    return tool_search_products(query, limit)


@mcp.tool()
def compare_products(a: str, b: str = "") -> str:
    """Compare two products or peers in a category (e.g. earbuds)."""
    return tool_compare_products(a, b)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
