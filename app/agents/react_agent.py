"""ReAct-style multi-tool loop (Thought → Action → Observation) — MVP C3/C4."""

from __future__ import annotations

import json
import re
from typing import Any

from app.mcp_bridge import call_mcp_tool
from app.rag.retriever import retrieve_faq
from app.tools.order_tools import extract_order_id


async def _act(action: str, action_input: dict) -> str:
    action = (action or "").strip()
    if action == "get_shipment_status" or action == "get_order_status":
        oid = action_input.get("shipment_id") or action_input.get("order_id") or ""
        return await call_mcp_tool("get_order_status", {"order_id": oid})
    if action == "get_tracking_events":
        oid = action_input.get("shipment_id") or action_input.get("order_id") or ""
        return await call_mcp_tool("get_tracking_events", {"order_id": oid})
    if action == "search_policy":
        q = action_input.get("query") or ""
        hits = retrieve_faq(q, k=3)
        return json.dumps({"hits": [{"source": h.get("source"), "text": h.get("text")} for h in hits]})
    if action == "get_inventory":
        from app.db import inventory as inv

        sku = action_input.get("sku") or ""
        return json.dumps(inv.lookup_sku(sku))
    return json.dumps({"error": f"unknown action {action}"})


def _plan(question: str) -> list[tuple[str, dict]]:
    """Deterministic ReAct planner for the demo (no LLM required)."""
    t = question.lower()
    oid = extract_order_id(question)
    steps: list[tuple[str, dict]] = []

    if oid and any(k in t for k in ("track", "where", "status", "shipment", "parcel")):
        steps.append(("get_shipment_status", {"shipment_id": oid}))
        steps.append(("get_tracking_events", {"shipment_id": oid}))
        return steps

    if "inventory" in t or "stock" in t or "on hand" in t or "sku-" in t:
        m = re.search(r"\bSKU-[\w-]+\b", question.upper()) or re.search(
            r"\b([A-Z]{2,6}-\d{3,5})\b", question.upper()
        )
        sku = m.group(0) if m else ""
        steps.append(("get_inventory", {"sku": sku}))
        return steps

    if oid:
        steps.append(("get_shipment_status", {"shipment_id": oid}))
        return steps

    steps.append(("search_policy", {"query": question}))
    return steps


async def run_react(question: str) -> dict[str, Any]:
    """
    Execute a short ReAct loop and return answer + trace for debug.
    Trace format mirrors Thought / Action / Observation.
    """
    trace: list[dict] = []
    observations: list[str] = []
    steps = _plan(question)

    for i, (action, payload) in enumerate(steps, start=1):
        thought = f"I need `{action}` to answer the user (step {i}/{len(steps)})."
        obs = await _act(action, payload)
        trace.append(
            {
                "thought": thought,
                "action": action,
                "action_input": payload,
                "observation": obs[:800],
            }
        )
        observations.append(obs)

    # Compose a grounded reply from observations
    answer_parts: list[str] = []
    for obs in observations:
        try:
            data = json.loads(obs)
        except Exception:
            answer_parts.append(obs[:300])
            continue
        if data.get("error"):
            answer_parts.append(str(data["error"]))
            continue
        if "order_id" in data or "status" in data:
            oid = data.get("order_id") or data.get("shipment_id")
            status = data.get("status")
            carrier = data.get("carrier")
            tracking = data.get("tracking_no")
            line = f"{oid} is **{status}**"
            if carrier:
                line += f" via {carrier}"
            if tracking:
                line += f" (AWB {tracking})"
            answer_parts.append(line + ".")
        if "events" in data:
            ev = data.get("events") or []
            if ev:
                last = ev[-1]
                answer_parts.append(
                    f"Latest scan: {last.get('description')} @ {last.get('location') or 'n/a'}."
                )
        if "sku" in data:
            if not data.get("ok"):
                answer_parts.append(data.get("error") or "SKU not found.")
            else:
                answer_parts.append(
                    f"{data['sku']}: {data.get('qty_on_hand', 0)} on hand in "
                    f"{data.get('zone')}/{data.get('bin')}."
                )
        if "hits" in data:
            hits = data.get("hits") or []
            if hits:
                snippet = (hits[0].get("text") or "")[:280]
                answer_parts.append(snippet)

    reply = " ".join(answer_parts).strip() or (
        "I ran the tools but couldn't form a clear answer. Try a SHP id or rephrase."
    )
    return {"reply": reply, "trace": trace, "observations": observations}
