"""Enterprise CS operations: invoice, tracking, exchange, loyalty, CSAT, handoff."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import (
    Coupon,
    Customer,
    ExchangeRequest,
    Invoice,
    Order,
    SatisfactionRating,
    SessionHandoff,
    TrackingEvent,
)
from app.db.session import SyncSessionLocal
from app.db.repository import _order_to_dict, lookup_order


def list_tracking_events(order_id: str) -> dict:
    oid = order_id.strip().upper()
    order = lookup_order(oid)
    if not order:
        return {"ok": False, "error": f"Order {oid} not found"}
    if not order.get("tracking_no"):
        return {
            "ok": True,
            "order_id": oid,
            "tracking_no": None,
            "events": [],
            "message": "No tracking number yet — order has not shipped.",
        }
    with SyncSessionLocal() as db:
        rows = db.scalars(
            select(TrackingEvent)
            .where(TrackingEvent.order_id == oid)
            .order_by(TrackingEvent.event_time.asc())
        ).all()
        events = [
            {
                "status_code": e.status_code,
                "description": e.description,
                "location": e.location,
                "event_time": e.event_time.isoformat() if e.event_time else None,
            }
            for e in rows
        ]
    return {
        "ok": True,
        "order_id": oid,
        "tracking_no": order.get("tracking_no"),
        "carrier": order.get("carrier"),
        "events": events,
    }


def request_invoice(order_id: str, title: str = "Personal", tax_id: str | None = None) -> dict:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status in ("cancelled", "processing"):
            return {
                "ok": False,
                "error": f"Order {oid} is {order.status}; invoice needs a paid/fulfilled order.",
            }
        existing = db.scalar(
            select(Invoice).where(Invoice.order_id == oid, Invoice.status == "issued")
        )
        if existing:
            return {
                "ok": True,
                "already_exists": True,
                "invoice": _invoice_dict(existing),
            }
        inv = Invoice(
            invoice_id="INV-" + secrets.token_hex(3).upper(),
            order_id=oid,
            title=(title or "Personal")[:128],
            tax_id=tax_id,
            amount=order.amount,
            status="issued",
            pdf_url=f"https://demo.steelshop.local/invoices/{oid}.pdf",
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return {"ok": True, "invoice": _invoice_dict(inv)}


def request_exchange(order_id: str, reason: str = "size/color change") -> dict:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status not in ("delivered", "shipped"):
            return {
                "ok": False,
                "error": f"Exchange requires shipped/delivered order; current status is {order.status}.",
            }
        ex = ExchangeRequest(
            exchange_id="EX-" + secrets.token_hex(3).upper(),
            order_id=oid,
            reason=(reason or "customer_request")[:256],
            status="submitted",
        )
        db.add(ex)
        order.notes = (order.notes or "") + f" | exchange {ex.exchange_id}"
        db.commit()
        db.refresh(ex)
        return {
            "ok": True,
            "exchange": {
                "exchange_id": ex.exchange_id,
                "order_id": ex.order_id,
                "reason": ex.reason,
                "status": ex.status,
            },
        }


def nudge_fulfillment(order_id: str) -> dict:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status not in ("processing", "paid"):
            return {
                "ok": False,
                "error": f"Order {oid} is already {order.status}; no need to nudge fulfillment.",
            }
        order.notes = (order.notes or "") + " | customer_nudge_fulfillment"
        order.updated_at = datetime.utcnow()
        eta = datetime.utcnow() + timedelta(days=1)
        db.commit()
        db.refresh(order)
        return {
            "ok": True,
            "order": _order_to_dict(order),
            "message": "Warehouse notified",
            "estimated_ship_by": eta.date().isoformat(),
        }


def get_loyalty(customer_id: str | None = None, order_id: str | None = None) -> dict:
    with SyncSessionLocal() as db:
        cid = (customer_id or "").strip().upper() or None
        if not cid and order_id:
            order = db.scalar(select(Order).where(Order.order_id == order_id.strip().upper()))
            if order:
                cid = order.customer_id
        if not cid:
            return {
                "ok": False,
                "error": "Share an order id (e.g. ORD-1001) so I can load the right loyalty profile.",
            }
        customer = db.scalar(select(Customer).where(Customer.customer_id == cid))
        if not customer:
            return {"ok": False, "error": f"Customer {cid} not found"}
        coupons = db.scalars(
            select(Coupon).where(Coupon.customer_id == cid).order_by(Coupon.id.desc())
        ).all()
        return {
            "ok": True,
            "customer_id": customer.customer_id,
            "name": customer.name,
            "loyalty_points": customer.loyalty_points,
            "coupons": [
                {
                    "code": c.coupon_code,
                    "title": c.title,
                    "discount": c.discount_label,
                    "status": c.status,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                }
                for c in coupons
            ],
        }


def save_satisfaction(session_id: str, score: int, comment: str | None = None) -> dict:
    score = int(score)
    if score < 1 or score > 5:
        return {"ok": False, "error": "Score must be 1–5"}
    with SyncSessionLocal() as db:
        row = SatisfactionRating(
            session_id=session_id,
            score=score,
            comment=(comment or "")[:500] or None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "ok": True,
            "rating": {
                "session_id": row.session_id,
                "score": row.score,
                "comment": row.comment,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            },
        }


def list_satisfaction(limit: int = 50) -> list[dict]:
    with SyncSessionLocal() as db:
        rows = db.scalars(
            select(SatisfactionRating).order_by(SatisfactionRating.created_at.desc()).limit(limit)
        ).all()
        return [
            {
                "session_id": r.session_id,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def pause_bot_for_human(session_id: str, ticket_id: str | None = None) -> dict:
    with SyncSessionLocal() as db:
        row = db.scalar(select(SessionHandoff).where(SessionHandoff.session_id == session_id))
        if not row:
            row = SessionHandoff(session_id=session_id, ticket_id=ticket_id, bot_paused=True)
            db.add(row)
        else:
            row.bot_paused = True
            row.ticket_id = ticket_id or row.ticket_id
            row.paused_at = datetime.utcnow()
            row.resumed_at = None
        db.commit()
        return {"ok": True, "session_id": session_id, "bot_paused": True, "ticket_id": row.ticket_id}


def get_handoff(session_id: str) -> dict | None:
    with SyncSessionLocal() as db:
        row = db.scalar(select(SessionHandoff).where(SessionHandoff.session_id == session_id))
        if not row:
            return None
        return {
            "session_id": row.session_id,
            "ticket_id": row.ticket_id,
            "bot_paused": row.bot_paused,
            "paused_at": row.paused_at.isoformat() if row.paused_at else None,
            "resumed_at": row.resumed_at.isoformat() if row.resumed_at else None,
            "last_human_reply": row.last_human_reply,
        }


def human_reply(session_id: str, message: str, resume_bot: bool = False) -> dict:
    from app.db.repository import append_chat_log

    with SyncSessionLocal() as db:
        row = db.scalar(select(SessionHandoff).where(SessionHandoff.session_id == session_id))
        if not row:
            row = SessionHandoff(session_id=session_id, bot_paused=True)
            db.add(row)
        row.last_human_reply = message
        if resume_bot:
            row.bot_paused = False
            row.resumed_at = datetime.utcnow()
        db.commit()
    append_chat_log(session_id, "human", message, agent="human_agent")
    return {
        "ok": True,
        "session_id": session_id,
        "bot_paused": False if resume_bot else True,
        "message": message,
    }


def resume_bot(session_id: str) -> dict:
    with SyncSessionLocal() as db:
        row = db.scalar(select(SessionHandoff).where(SessionHandoff.session_id == session_id))
        if not row:
            return {"ok": True, "bot_paused": False}
        row.bot_paused = False
        row.resumed_at = datetime.utcnow()
        db.commit()
        return {"ok": True, "session_id": session_id, "bot_paused": False}


def is_bot_paused(session_id: str) -> bool:
    h = get_handoff(session_id)
    return bool(h and h.get("bot_paused"))


def _invoice_dict(inv: Invoice) -> dict:
    return {
        "invoice_id": inv.invoice_id,
        "order_id": inv.order_id,
        "title": inv.title,
        "tax_id": inv.tax_id,
        "amount": inv.amount,
        "status": inv.status,
        "pdf_url": inv.pdf_url,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
    }
