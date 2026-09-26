"""数据访问层：订单 / 支付 / 工单 / 聊天审计。"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.models import ChatLog, Customer, Order, Payment, Ticket
from app.db.session import SyncSessionLocal


def lookup_order(order_id: str) -> dict | None:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(
            select(Order)
            .options(joinedload(Order.customer), joinedload(Order.payments))
            .where(Order.order_id == oid)
        )
        return _order_to_dict(order, include_payments=True)


def list_orders(limit: int = 50, status: str | None = None) -> list[dict]:
    with SyncSessionLocal() as db:
        q = select(Order).options(joinedload(Order.customer)).order_by(Order.created_at.desc())
        if status:
            q = q.where(Order.status == status)
        orders = db.scalars(q.limit(limit)).unique().all()
        return [_order_to_dict(o) for o in orders]


def lookup_payment(payment_id: str) -> dict | None:
    pid = payment_id.strip().upper()
    with SyncSessionLocal() as db:
        pay = db.scalar(select(Payment).where(Payment.payment_id == pid))
        return _payment_to_dict(pay)


def list_payments_for_order(order_id: str) -> list[dict]:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        pays = db.scalars(
            select(Payment).where(Payment.order_id == oid).order_by(Payment.created_at.desc())
        ).all()
        return [_payment_to_dict(p) for p in pays]


def list_payments(limit: int = 50) -> list[dict]:
    with SyncSessionLocal() as db:
        pays = db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(limit)).all()
        return [_payment_to_dict(p) for p in pays]


def lookup_customer(customer_id: str) -> dict | None:
    cid = customer_id.strip().upper()
    with SyncSessionLocal() as db:
        c = db.scalar(select(Customer).where(Customer.customer_id == cid))
        if not c:
            return None
        return {
            "customer_id": c.customer_id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }


def apply_refund(order_id: str, reason: str = "customer_request") -> dict:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status == "refunded":
            return {"ok": False, "error": f"Order {oid} is already refunded"}
        if order.status in ("processing", "cancelled"):
            return {
                "ok": False,
                "error": f"Order {oid} is {order.status}; cancel instead of refunding",
            }

        order.status = "refunded"
        order.notes = (order.notes or "") + f" | refund: {reason}"
        order.updated_at = datetime.utcnow()

        # 同步支付记录：最近一笔成功支付标记为 refunded
        pay = db.scalar(
            select(Payment)
            .where(Payment.order_id == oid, Payment.status == "succeeded")
            .order_by(Payment.created_at.desc())
        )
        if pay:
            pay.status = "refunded"
            pay.notes = (pay.notes or "") + f" | refunded via bot: {reason}"

        db.commit()
        db.refresh(order)
        return {
            "ok": True,
            "order": _order_to_dict(order),
            "payment": _payment_to_dict(pay) if pay else None,
        }


def cancel_order(order_id: str, reason: str = "customer_request") -> dict:
    """Cancel unshipped orders (processing / paid)."""
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status == "cancelled":
            return {"ok": False, "error": f"Order {oid} is already cancelled"}
        if order.status not in ("processing", "paid"):
            return {
                "ok": False,
                "error": (
                    f"Order {oid} is {order.status} and cannot be cancelled. "
                    "Use return/refund after shipping."
                ),
            }
        order.status = "cancelled"
        order.notes = (order.notes or "") + f" | cancelled: {reason}"
        order.updated_at = datetime.utcnow()
        # pending payments → failed/cancelled note
        pay = db.scalar(
            select(Payment)
            .where(Payment.order_id == oid, Payment.status.in_(["pending", "succeeded"]))
            .order_by(Payment.created_at.desc())
        )
        if pay and pay.status == "pending":
            pay.status = "failed"
            pay.notes = (pay.notes or "") + " | order cancelled"
        db.commit()
        db.refresh(order)
        return {"ok": True, "order": _order_to_dict(order), "payment": _payment_to_dict(pay) if pay else None}


def update_shipping_address(order_id: str, new_address: str) -> dict:
    """Update address only before shipment."""
    oid = order_id.strip().upper()
    addr = (new_address or "").strip()
    if len(addr) < 5:
        return {"ok": False, "error": "Please provide a full shipping address."}
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        if not order:
            return {"ok": False, "error": f"Order {oid} not found"}
        if order.status not in ("processing", "paid"):
            return {
                "ok": False,
                "error": f"Order {oid} is {order.status}; address can only change before shipping.",
            }
        old = order.shipping_address
        order.shipping_address = addr[:256]
        order.notes = (order.notes or "") + f" | address {old} → {addr}"
        order.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(order)
        return {"ok": True, "order": _order_to_dict(order), "previous_address": old}


def create_ticket(
    session_id: str,
    summary: str,
    category: str = "other",
    order_id: str | None = None,
    *,
    over_limit: bool = False,
) -> dict:
    from app.trust import create_sla_ticket

    return create_sla_ticket(
        session_id,
        summary,
        category=category,
        order_id=order_id,
        over_limit=over_limit,
    )


def list_tickets(limit: int = 50) -> list[dict]:
    from app.trust import _ticket_dict

    with SyncSessionLocal() as db:
        rows = db.scalars(select(Ticket).order_by(Ticket.created_at.desc()).limit(limit)).all()
        return [_ticket_dict(t) for t in rows]


def append_chat_log(
    session_id: str,
    role: str,
    content: str,
    agent: str | None = None,
    meta: dict | None = None,
) -> None:
    from app.pii import redact_free_text

    stored = redact_free_text(content) if role != "system" else content
    with SyncSessionLocal() as db:
        db.add(
            ChatLog(
                session_id=session_id,
                role=role,
                agent=agent,
                content=stored,
                meta_json=json.dumps(meta, ensure_ascii=False) if meta else None,
            )
        )
        db.commit()


def list_chat_logs(session_id: str, limit: int = 100) -> list[dict]:
    with SyncSessionLocal() as db:
        rows = db.scalars(
            select(ChatLog)
            .where(ChatLog.session_id == session_id)
            .order_by(ChatLog.created_at.asc())
            .limit(limit)
        ).all()
        return [
            {
                "role": r.role,
                "agent": r.agent,
                "content": r.content,
                "meta": json.loads(r.meta_json) if r.meta_json else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]


def _order_to_dict(order: Order | None, include_payments: bool = False) -> dict | None:
    if not order:
        return None
    data = {
        "order_id": order.order_id,
        "customer_id": order.customer_id,
        "customer_name": order.customer.name if order.customer else None,
        "customer_email": order.customer.email if order.customer else None,
        "customer_phone": order.customer.phone if order.customer else None,
        "customer_tier": (
            order.customer.tier
            if order.customer and getattr(order.customer, "tier", None)
            else None
        ),
        "product": order.product,
        "quantity": order.quantity,
        "amount": order.amount,
        "currency": order.currency,
        "status": order.status,
        "shipping_address": order.shipping_address,
        "tracking_no": order.tracking_no,
        "carrier": order.carrier,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
        "notes": order.notes,
    }
    if include_payments:
        data["payments"] = [_payment_to_dict(p) for p in (order.payments or [])]
    return data


def _payment_to_dict(pay: Payment | None) -> dict | None:
    if not pay:
        return None
    return {
        "payment_id": pay.payment_id,
        "order_id": pay.order_id,
        "amount": pay.amount,
        "currency": pay.currency,
        "method": pay.method,
        "status": pay.status,
        "transaction_ref": pay.transaction_ref,
        "paid_at": pay.paid_at.isoformat() if pay.paid_at else None,
        "created_at": pay.created_at.isoformat() if pay.created_at else None,
        "notes": pay.notes,
    }


# 兼容旧工具签名
def _get(db: Session, order_id: str) -> Order | None:
    return db.scalar(select(Order).where(Order.order_id == order_id))
