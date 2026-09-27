"""LangGraph multi-agent CS graph with natural replies (RAG scores stay in debug)."""

from __future__ import annotations

import json
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.db.enterprise_ops import (
    is_bot_paused,
    pause_bot_for_human,
    save_satisfaction,
)
from app.db.repository import append_chat_log, create_ticket, lookup_order
from app.mcp_bridge import call_mcp_tool
from app.pii import redact_order, redact_payment
from app.rag.retriever import retrieve_faq, sources_for_ui
from app.response import (
    compose_address_answer,
    compose_approval_hold,
    compose_cancel_answer,
    compose_confirm_mutation,
    compose_csat_answer,
    compose_denied_mutation,
    compose_exchange_answer,
    compose_greeting,
    compose_handoff_hold,
    compose_handoff_waiting,
    compose_invoice_answer,
    compose_loyalty_answer,
    compose_nudge_answer,
    compose_off_topic,
    compose_order_answer,
    compose_payment_answer,
    compose_payments_list,
    compose_pending_reminder,
    compose_policy_answer,
    compose_refund_answer,
    compose_tracking_answer,
    compose_verify_fail,
    compose_verify_ok,
    compose_verify_prompt,
    is_follow_up,
    is_greeting,
    parse_csat_score,
)
from app.tools.order_tools import extract_new_address, extract_order_id, extract_payment_id
from app.llm import llm_mode, reset_request_api_key, set_request_api_key
from app.trust import (
    bind_order,
    clear_pending,
    execute_pending,
    get_identity,
    get_pending,
    is_confirm,
    is_deny,
    looks_like_verify,
    mutation_requires_approval,
    parse_verify_token,
    set_pending,
    verify_session,
)

AgentName = Literal[
    "smalltalk", "faq", "order", "payment", "refund", "loyalty", "escalate", "finish"
]


class CSState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    next_agent: str
    order_id: str | None
    payment_id: str | None
    last_agent: str
    session_id: str
    sources: list
    debug: dict


def _last_user_text(state: CSState) -> str:
    for m in reversed(state["messages"]):
        if isinstance(m, HumanMessage) or getattr(m, "type", None) == "human":
            return str(m.content)
    return ""


def _finish(
    msg: str,
    agent: str,
    *,
    order_id: str | None = None,
    payment_id: str | None = None,
    sources: list | None = None,
    debug: dict | None = None,
) -> dict:
    out: dict = {
        "messages": [AIMessage(content=msg)],
        "last_agent": agent,
        "next_agent": "finish",
        "sources": sources or [],
        "debug": debug or {},
    }
    if order_id is not None:
        out["order_id"] = order_id
    if payment_id is not None:
        out["payment_id"] = payment_id
    return out


def _gate_mutation(state: CSState, action: str, oid: str, payload: dict, agent: str) -> dict:
    sid = state.get("session_id") or "unknown"
    bind_order(sid, oid)
    ident = get_identity(sid)
    if not ident.get("verified"):
        return _finish(
            compose_verify_prompt(oid),
            agent,
            order_id=oid,
            debug={"gate": "verify", "action": action},
        )
    order = lookup_order(oid)
    if not order:
        return _finish(
            f"I couldn't find {oid}. Double-check the id and try again.",
            agent,
            order_id=oid,
        )
    amount = float(order.get("amount") or 0)
    pending = set_pending(
        sid,
        action,
        oid,
        amount=amount,
        requires_approval=mutation_requires_approval(amount, ident.get("tier") or "standard"),
        payload=payload,
    )
    return _finish(
        compose_confirm_mutation(pending),
        agent,
        order_id=oid,
        debug={"gate": "confirm", "pending": pending, "tier": ident.get("tier")},
    )


def route_intent(state: CSState) -> dict:
    text = _last_user_text(state)
    t = text.lower().strip()

    oid_in_msg = extract_order_id(text)
    pid_in_msg = extract_payment_id(text)
    remembered_oid = state.get("order_id") if is_follow_up(t) else None
    remembered_pid = state.get("payment_id") if is_follow_up(t) else None
    oid = oid_in_msg or remembered_oid
    pid = pid_in_msg or remembered_pid

    asking_policy = any(
        k in t
        for k in (
            "policy",
            "how many days",
            "how long",
            "how do i",
            "how to",
            "can i return",
            "can i get a refund",
            "timeline",
            "free shipping",
            "return window",
            "refund take",
            "what is your",
            "what's your",
            "what are your",
            "warranty",
        )
    )
    wants_invoice = any(k in t for k in ("invoice", "e-invoice", "fapiao")) and not asking_policy
    # "invoice policy" stays FAQ; "issue invoice for ORD" is order tool
    if "invoice" in t and ("policy" in t or "how" in t or "what is" in t):
        wants_invoice = False
        asking_policy = True

    if is_greeting(t):
        nxt: AgentName = "smalltalk"
    elif any(k in t for k in ("human", "agent", "escalate", "complaint", "manager", "lawyer")):
        nxt = "escalate"
    elif any(k in t for k in ("points", "loyalty", "coupon", "coupons", "rewards")):
        nxt = "loyalty"
    elif wants_invoice or any(
        k in t
        for k in (
            "tracking events",
            "tracking timeline",
            "track package",
            "where is my package",
            "exchange",
            "nudge",
            "hurry",
            "ship sooner",
            "催发货",
            "cancel order",
            "cancel my",
            "cancel ord",
            "update address",
            "change address",
            "new address",
        )
    ) or ("cancel" in t and ("order" in t or oid_in_msg)):
        nxt = "order"
    elif any(k in t for k in ("refund", "return my", "i want to return", "give me my money")) or (
        "return" in t and oid and not asking_policy
    ):
        nxt = "faq" if asking_policy and not oid_in_msg else "refund"
    elif pid or any(k in t for k in ("payment", "paid", "charge", "transaction", "pay-")):
        nxt = "payment"
    elif oid or any(
        k in t for k in ("order", "tracking", "shipment", "shipping", "where is my")
    ):
        nxt = "order"
    elif asking_policy or any(
        k in t for k in ("policy", "return", "refund", "shipping", "warranty")
    ):
        nxt = "faq"
    else:
        nxt = "smalltalk"

    debug = {
        "router_input": text,
        "next_agent": nxt,
        "order_id_in_msg": oid_in_msg,
        "order_id_used": oid,
        "payment_id_used": pid,
        "follow_up": is_follow_up(t),
        "tool_layer": "mcp",
        "rag_library": "langchain_chroma",
    }
    return {
        "next_agent": nxt,
        "order_id": oid_in_msg or state.get("order_id"),
        "payment_id": pid_in_msg or state.get("payment_id"),
        "debug": debug,
    }


async def smalltalk_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    if is_greeting(text):
        msg = compose_greeting()
        kind = "greeting"
    else:
        msg = compose_off_topic()
        kind = "off_topic"
    return {
        "messages": [AIMessage(content=msg)],
        "last_agent": "smalltalk",
        "next_agent": "finish",
        "sources": [],
        "debug": {"kind": kind},
    }


async def faq_agent(state: CSState) -> dict:
    q = _last_user_text(state)
    hits = retrieve_faq(q)
    _ = await call_mcp_tool("search_company_policy", {"query": q})
    answer = compose_policy_answer(q, hits)
    return {
        "messages": [AIMessage(content=answer)],
        "last_agent": "faq",
        "next_agent": "finish",
        "sources": sources_for_ui(hits),
        "debug": {
            "rag_via": "chroma+grounded_generate",
            "pipeline": ["retrieve", "ground", "respond"],
            "llm_mode": llm_mode(),
            "hits": [
                {
                    "source": h.get("source"),
                    "section": h.get("section"),
                    "score": h.get("score"),
                    "preview": (h.get("text") or "")[:120],
                }
                for h in hits
            ],
        },
    }


async def order_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    t = text.lower()
    oid = extract_order_id(text) or (state.get("order_id") if is_follow_up(t) else None)

    # Cancel unshipped order
    if any(k in t for k in ("cancel order", "cancel my order", "cancel ord")) or (
        "cancel" in t and (oid or "order" in t)
    ):
        if not oid:
            return _finish(
                "I can cancel an unshipped order — please share the order id (e.g. ORD-1003).",
                "order",
            )
        return _gate_mutation(
            state, "cancel", oid, {"reason": "customer_request_via_bot"}, "order"
        )

    # Update shipping address
    if any(k in t for k in ("update address", "change address", "new address", "shipping to")) or (
        "address" in t and ("update" in t or "change" in t or " to " in t)
    ):
        if not oid:
            return _finish(
                "I can update the address before shipping — send ORD-xxxx and the new address.",
                "order",
            )
        new_addr = extract_new_address(text)
        if not new_addr:
            return _finish(
                f"What should the new address be for {oid}?",
                "order",
                order_id=oid,
            )
        return _gate_mutation(
            state, "address", oid, {"new_address": new_addr}, "order"
        )

    # Tracking timeline (carrier mock)
    if any(
        k in t
        for k in (
            "tracking events",
            "tracking timeline",
            "track package",
            "where is my package",
            "tracking detail",
            "logistics",
        )
    ) or ("tracking" in t and oid):
        if not oid:
            msg = "Share an order id (e.g. ORD-1001) and I'll pull the carrier timeline."
            return {
                "messages": [AIMessage(content=msg)],
                "last_agent": "order",
                "next_agent": "finish",
                "sources": [],
            }
        raw = await call_mcp_tool("get_tracking_events", {"order_id": oid})
        result = json.loads(raw)
        return {
            "messages": [AIMessage(content=compose_tracking_answer(result))],
            "last_agent": "order",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "get_tracking_events", "result": result},
        }

    # E-invoice
    if any(k in t for k in ("invoice", "e-invoice", "fapiao")):
        if not oid:
            msg = "I can issue an e-invoice — please send the order id (e.g. ORD-1002)."
            return {
                "messages": [AIMessage(content=msg)],
                "last_agent": "order",
                "next_agent": "finish",
                "sources": [],
            }
        raw = await call_mcp_tool(
            "request_invoice",
            {"order_id": oid, "title": "Personal", "tax_id": ""},
        )
        result = json.loads(raw)
        return {
            "messages": [AIMessage(content=compose_invoice_answer(result))],
            "last_agent": "order",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "request_invoice", "result": result},
        }

    # Exchange
    if "exchange" in t:
        if not oid:
            msg = "I can submit an exchange — please send ORD-xxxx and the reason."
            return {
                "messages": [AIMessage(content=msg)],
                "last_agent": "order",
                "next_agent": "finish",
                "sources": [],
            }
        raw = await call_mcp_tool(
            "request_exchange",
            {"order_id": oid, "reason": "customer_request_via_bot"},
        )
        result = json.loads(raw)
        return {
            "messages": [AIMessage(content=compose_exchange_answer(result))],
            "last_agent": "order",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "request_exchange", "result": result},
        }

    # Nudge fulfillment
    if any(k in t for k in ("nudge", "hurry", "ship sooner", "催发货", "expedite")):
        if not oid:
            msg = "Which order should I nudge? Example: ORD-1004"
            return {
                "messages": [AIMessage(content=msg)],
                "last_agent": "order",
                "next_agent": "finish",
                "sources": [],
            }
        raw = await call_mcp_tool("nudge_fulfillment", {"order_id": oid})
        result = json.loads(raw)
        return {
            "messages": [AIMessage(content=compose_nudge_answer(result))],
            "last_agent": "order",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "nudge_fulfillment", "result": result},
        }

    if not oid:
        msg = "Sure — what's the order id? It looks like ORD-1001."
        return {
            "messages": [AIMessage(content=msg)],
            "last_agent": "order",
            "next_agent": "finish",
            "sources": [],
        }

    sid = state.get("session_id") or "unknown"
    bind_order(sid, oid)
    ident = get_identity(sid)
    raw = await call_mcp_tool("get_order_status", {"order_id": oid})
    data = json.loads(raw)
    if data.get("error"):
        return {
            "messages": [AIMessage(content=f"I couldn't find {oid}. Double-check the id and try again.")],
            "last_agent": "order",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "get_order_status", "error": data},
        }

    pays = data.get("payments") or []
    if not pays:
        pay_raw = await call_mcp_tool("get_order_payments", {"order_id": oid})
        pays = json.loads(pay_raw).get("payments") or []
    pays = [redact_payment(p, verified=bool(ident.get("verified"))) or p for p in pays]
    data = redact_order(data, verified=bool(ident.get("verified"))) or data

    msg = compose_order_answer(data, pays, verified=bool(ident.get("verified")))
    return {
        "messages": [AIMessage(content=msg)],
        "last_agent": "order",
        "order_id": oid,
        "next_agent": "finish",
        "sources": [],
        "debug": {
            "mcp_tool": "get_order_status",
            "order": data,
            "verified": ident.get("verified"),
            "tier": ident.get("tier"),
        },
    }


async def payment_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    t = text.lower()
    pid = extract_payment_id(text) or (state.get("payment_id") if is_follow_up(t) else None)
    oid = extract_order_id(text) or (state.get("order_id") if is_follow_up(t) else None)

    if pid:
        raw = await call_mcp_tool("get_payment_status", {"payment_id": pid})
        data = json.loads(raw)
        ident = get_identity(state.get("session_id") or "")
        if data.get("error"):
            msg = f"I couldn't find payment {pid}."
        else:
            data = redact_payment(data, verified=bool(ident.get("verified"))) or data
            msg = compose_payment_answer(data)
            oid = data.get("order_id") or oid
            if oid:
                bind_order(state.get("session_id") or "unknown", oid)
        return {
            "messages": [AIMessage(content=msg)],
            "last_agent": "payment",
            "payment_id": pid,
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "get_payment_status", "payment": data if not data.get("error") else None},
        }

    if oid:
        raw = await call_mcp_tool("get_order_payments", {"order_id": oid})
        pays = json.loads(raw).get("payments") or []
        msg = compose_payments_list(oid, pays)
        return {
            "messages": [AIMessage(content=msg)],
            "last_agent": "payment",
            "order_id": oid,
            "next_agent": "finish",
            "sources": [],
            "debug": {"mcp_tool": "get_order_payments", "payments": pays},
        }

    msg = "I can check a payment if you share PAY-xxxx, or an order id like ORD-1001."
    return {
        "messages": [AIMessage(content=msg)],
        "last_agent": "payment",
        "next_agent": "finish",
        "sources": [],
    }


async def refund_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    oid = extract_order_id(text) or (state.get("order_id") if is_follow_up(text.lower()) else None)
    if not oid:
        return _finish(
            "I can start a refund — please send the order id (for example ORD-1002).",
            "refund",
        )
    return _gate_mutation(
        state, "refund", oid, {"reason": "customer_request_via_bot"}, "refund"
    )


async def loyalty_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    sid = state.get("session_id") or "unknown"
    oid = extract_order_id(text) or state.get("order_id")
    ident = get_identity(sid)
    if oid:
        bind_order(sid, oid)
        ident = get_identity(sid)
    if not ident.get("verified"):
        return _finish(
            compose_verify_prompt(oid or ident.get("order_id")),
            "loyalty",
            order_id=oid,
            debug={"gate": "verify", "action": "loyalty"},
        )
    raw = await call_mcp_tool(
        "get_loyalty",
        {"customer_id": ident.get("customer_id") or "", "order_id": oid or ident.get("order_id") or ""},
    )
    result = json.loads(raw)
    return {
        "messages": [AIMessage(content=compose_loyalty_answer(result))],
        "last_agent": "loyalty",
        "order_id": oid or ident.get("order_id"),
        "next_agent": "finish",
        "sources": [],
        "debug": {"mcp_tool": "get_loyalty", "result": result},
    }


async def escalate_agent(state: CSState) -> dict:
    text = _last_user_text(state)
    session_id = state.get("session_id") or "unknown"
    ticket = create_ticket(
        session_id=session_id,
        summary=text[:200],
        category="complaint",
        order_id=state.get("order_id"),
    )
    pause_bot_for_human(session_id, ticket_id=ticket["ticket_id"])
    msg = compose_handoff_hold(ticket["ticket_id"])
    if state.get("order_id"):
        msg += f" Linked order: {state.get('order_id')}."
    return {
        "messages": [AIMessage(content=msg)],
        "last_agent": "escalate",
        "next_agent": "finish",
        "sources": [],
        "debug": {"ticket": ticket, "bot_paused": True},
    }


def supervisor(state: CSState) -> dict:
    return route_intent(state)


def _dispatch(state: CSState) -> str:
    return state.get("next_agent") or "faq"


def build_graph(checkpointer: MemorySaver | None = None):
    g = StateGraph(CSState)
    g.add_node("supervisor", supervisor)
    g.add_node("smalltalk", smalltalk_agent)
    g.add_node("faq", faq_agent)
    g.add_node("order", order_agent)
    g.add_node("payment", payment_agent)
    g.add_node("refund", refund_agent)
    g.add_node("loyalty", loyalty_agent)
    g.add_node("escalate", escalate_agent)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _dispatch,
        {
            "smalltalk": "smalltalk",
            "faq": "faq",
            "order": "order",
            "payment": "payment",
            "refund": "refund",
            "loyalty": "loyalty",
            "escalate": "escalate",
        },
    )
    for node in ("smalltalk", "faq", "order", "payment", "refund", "loyalty", "escalate"):
        g.add_edge(node, END)

    memory = checkpointer or MemorySaver()
    return g.compile(checkpointer=memory)


_memory = MemorySaver()
_app = None


def get_graph():
    global _app
    if _app is None:
        _app = build_graph(_memory)
    return _app


def reset_graph() -> None:
    global _app, _memory
    _memory = MemorySaver()
    _app = build_graph(_memory)


async def chat(session_id: str, message: str, openai_api_key: str | None = None) -> dict:
    key_token = set_request_api_key(openai_api_key)
    try:
        return await _chat_inner(session_id, message)
    finally:
        reset_request_api_key(key_token)


async def _chat_inner(session_id: str, message: str) -> dict:
    append_chat_log(session_id, "user", message)
    ident = get_identity(session_id)
    pending = get_pending(session_id)

    def _pack(reply: str, agent: str, *, order_id=None, payment_id=None, sources=None, debug=None, bot_paused=None):
        ident_now = get_identity(session_id)
        pend = get_pending(session_id)
        paused = is_bot_paused(session_id) if bot_paused is None else bot_paused
        # Never put API keys into meta / chat_logs
        safe_meta = {**(debug or {}), "llm_mode": llm_mode()}
        append_chat_log(session_id, "assistant", reply, agent=agent, meta=safe_meta)
        return {
            "session_id": session_id,
            "reply": reply,
            "agent": agent,
            "order_id": order_id or ident_now.get("order_id"),
            "payment_id": payment_id,
            "sources": sources or [],
            "bot_paused": paused,
            "verified": bool(ident_now.get("verified")),
            "customer_tier": ident_now.get("tier"),
            "pending_action": (pend or {}).get("action"),
            "llm_mode": llm_mode(),
            "debug": safe_meta,
        }

    score = parse_csat_score(message)
    if score is not None:
        result = save_satisfaction(session_id, score)
        return _pack(compose_csat_answer(result), "csat", debug={"csat": result})

    if looks_like_verify(message) and not is_confirm(message):
        token = parse_verify_token(message)
        if not token:
            return _pack(compose_verify_prompt(ident.get("order_id")), "verify")
        result = verify_session(session_id, token)
        if not result.get("ok"):
            return _pack(compose_verify_fail(result.get("error") or "mismatch"), "verify", debug=result)
        reply = compose_verify_ok(result)
        if pending:
            reply += " " + compose_pending_reminder(pending)
        return _pack(reply, "verify", debug={"identity": {k: v for k, v in result.items() if k != "ok"}})

    if is_bot_paused(session_id):
        return _pack(compose_handoff_waiting(), "handoff", bot_paused=True, debug={"bot_paused": True})

    if pending:
        if is_confirm(message):
            if pending.get("requires_approval"):
                ticket = create_ticket(
                    session_id=session_id,
                    summary=f"{pending['action']} approval for {pending['order_id']} (¥{pending['amount']})",
                    category="refund_approval",
                    order_id=pending.get("order_id"),
                    over_limit=True,
                )
                pause_bot_for_human(session_id, ticket_id=ticket["ticket_id"])
                clear_pending(session_id)
                reply = compose_approval_hold(ticket, pending)
                return _pack(
                    reply,
                    "escalate",
                    order_id=pending.get("order_id"),
                    bot_paused=True,
                    debug={"ticket": ticket, "pending": pending},
                )
            result = execute_pending(session_id, pending)
            policy_hits = retrieve_faq("refund timeline return policy") if pending["action"] == "refund" else []
            if pending["action"] == "refund":
                reply = compose_refund_answer(result, policy_hits)
            elif pending["action"] == "cancel":
                reply = compose_cancel_answer(result)
            else:
                reply = compose_address_answer(result)
            return _pack(
                reply,
                pending["action"] if pending["action"] != "address" else "order",
                order_id=pending.get("order_id"),
                sources=sources_for_ui(policy_hits),
                debug={"executed": pending["action"], "result": result, "idempotent": result.get("idempotent")},
            )
        if is_deny(message):
            clear_pending(session_id)
            return _pack(compose_denied_mutation(), "order", order_id=pending.get("order_id"))
        if not looks_like_verify(message):
            return _pack(compose_pending_reminder(pending), "order", order_id=pending.get("order_id"))

    graph = get_graph()
    config = {"configurable": {"thread_id": session_id}}
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=message)],
            "session_id": session_id,
        },
        config=config,
    )
    last = result["messages"][-1]
    reply = str(last.content)
    agent = result.get("last_agent") or result.get("next_agent")
    debug = result.get("debug") or {}
    return _pack(
        reply,
        agent,
        order_id=result.get("order_id"),
        payment_id=result.get("payment_id"),
        sources=result.get("sources") or [],
        debug=debug,
    )
