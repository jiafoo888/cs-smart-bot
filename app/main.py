"""FastAPI enterprise CS console API + static UI."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db.enterprise_ops import (
    get_handoff,
    get_loyalty,
    human_reply,
    list_satisfaction,
    list_tracking_events,
    resume_bot,
    save_satisfaction,
)
from app.db.repository import (
    list_chat_logs,
    list_orders,
    list_payments,
    list_payments_for_order,
    list_tickets,
    lookup_order,
    lookup_payment,
)
from app.db.seed import seed_all
from app.db.session import init_db
from app.graph.supervisor import chat
from app.mcp_bridge import list_mcp_tools
from app.rag.ingest import ingest_all_policies, knowledge_base_stats
from app.rag.retriever import format_context, retrieve_faq


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    seed_all()
    settings = get_settings()
    store_dir = settings.vector_dir / ("simple" if settings.vector_store == "simple" else "chroma")
    if not store_dir.exists() or not any(store_dir.iterdir()):
        ingest_all_policies()
    yield


app = FastAPI(
    title="SteelShop Care — Enterprise CS Agent",
    description="Deployable multi-agent customer service: LangGraph + Chroma RAG + MCP + orders/payments",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()
static_dir = settings.static_dir
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Stable session id for multi-turn memory")
    message: str = Field(..., min_length=1)
    include_debug: bool = Field(False, description="Include router/RAG/MCP debug payload")


class SourceChip(BaseModel):
    title: str
    document: str | None = None
    category: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    agent: str | None = None
    order_id: str | None = None
    payment_id: str | None = None
    sources: list[SourceChip] = []
    bot_paused: bool = False
    debug: dict | None = None


@app.get("/")
async def root():
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"name": "SteelShop Care", "docs": "/docs"}


@app.get("/health")
async def health():
    s = get_settings()
    kb = knowledge_base_stats()
    return {
        "status": "ok",
        "service": "SteelShop Care",
        "version": "2.0.0",
        "mock_llm": s.use_mock_llm or not s.openai_api_key,
        "embedding_backend": s.embedding_backend,
        "rag": {
            "library": s.vector_store,
            "chunk_size": s.rag_chunk_size,
            "chunk_overlap": s.rag_chunk_overlap,
            "top_k": s.rag_top_k,
            "chunks": kb.get("chunk_count"),
        },
        "mcp_tools": list_mcp_tools(),
        "use_mcp_stdio": s.use_mcp_stdio,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest):
    result = await chat(body.session_id, body.message)
    if not body.include_debug:
        result = {**result, "debug": None}
    return ChatResponse(**result)


@app.get("/api/orders")
async def api_list_orders(status: str | None = None, limit: int = Query(50, le=200)):
    return {"items": list_orders(limit=limit, status=status)}


@app.get("/api/orders/{order_id}")
async def api_get_order(order_id: str):
    data = lookup_order(order_id)
    if not data:
        raise HTTPException(404, f"Order {order_id} not found")
    return data


@app.get("/api/orders/{order_id}/payments")
async def api_order_payments(order_id: str):
    if not lookup_order(order_id):
        raise HTTPException(404, f"Order {order_id} not found")
    return {"order_id": order_id.upper(), "items": list_payments_for_order(order_id)}


@app.get("/api/payments")
async def api_list_payments(limit: int = Query(50, le=200)):
    return {"items": list_payments(limit=limit)}


@app.get("/api/payments/{payment_id}")
async def api_get_payment(payment_id: str):
    data = lookup_payment(payment_id)
    if not data:
        raise HTTPException(404, f"Payment {payment_id} not found")
    return data


@app.get("/api/tickets")
async def api_list_tickets(limit: int = Query(50, le=200)):
    return {"items": list_tickets(limit=limit)}


@app.get("/api/sessions/{session_id}/logs")
async def api_session_logs(session_id: str):
    return {"session_id": session_id, "items": list_chat_logs(session_id)}


@app.get("/api/policies/search")
async def api_policy_search(q: str = Query(..., min_length=1), k: int = Query(4, le=10)):
    hits = retrieve_faq(q, k=k)
    return {
        "query": q,
        "hits": hits,
        "context": format_context(hits),
        "store": "chroma",
        "chunk_size": get_settings().rag_chunk_size,
    }


@app.get("/api/kb/stats")
async def api_kb_stats():
    return knowledge_base_stats()


@app.get("/api/metrics/overview")
async def api_metrics():
    orders = list_orders(limit=200)
    payments = list_payments(limit=200)
    tickets = list_tickets(limit=200)
    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o["status"]] = by_status.get(o["status"], 0) + 1
    pay_ok = sum(1 for p in payments if p["status"] == "succeeded")
    return {
        "orders_total": len(orders),
        "orders_by_status": by_status,
        "payments_total": len(payments),
        "payments_succeeded": pay_ok,
        "tickets_open": sum(1 for t in tickets if t["status"] == "open"),
        "tickets_total": len(tickets),
        "kb": knowledge_base_stats(),
        "agents": [
            "supervisor",
            "smalltalk",
            "faq",
            "order",
            "payment",
            "refund",
            "loyalty",
            "escalate",
            "csat",
            "handoff",
        ],
    }


@app.get("/api/orders/{order_id}/tracking")
async def api_tracking(order_id: str):
    return list_tracking_events(order_id)


@app.get("/api/loyalty")
async def api_loyalty(customer_id: str | None = None, order_id: str | None = None):
    return get_loyalty(customer_id=customer_id, order_id=order_id)


@app.get("/api/csat")
async def api_csat(limit: int = Query(50, le=200)):
    return {"items": list_satisfaction(limit=limit)}


@app.post("/api/sessions/{session_id}/csat")
async def api_post_csat(session_id: str, score: int = Query(..., ge=1, le=5), comment: str = ""):
    return save_satisfaction(session_id, score, comment or None)


@app.get("/api/sessions/{session_id}/handoff")
async def api_get_handoff(session_id: str):
    return get_handoff(session_id) or {"session_id": session_id, "bot_paused": False}


class HumanReplyRequest(BaseModel):
    message: str = Field(..., min_length=1)
    resume_bot: bool = False


@app.post("/api/sessions/{session_id}/human-reply")
async def api_human_reply(session_id: str, body: HumanReplyRequest):
    return human_reply(session_id, body.message, resume_bot=body.resume_bot)


@app.post("/api/sessions/{session_id}/resume-bot")
async def api_resume_bot(session_id: str):
    return resume_bot(session_id)


@app.get("/api/mcp/tools")
async def api_mcp_tools():
    return {"tools": list_mcp_tools(), "server": "python -m app.mcp_server"}


@app.post("/api/admin/reingest")
async def api_reingest():
    return ingest_all_policies()


@app.post("/api/admin/reseed")
async def api_reseed():
    seed_all(force=True)
    return {"ok": True, "message": "demo data reset"}
