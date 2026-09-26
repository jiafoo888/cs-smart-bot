"""Identity verification, mutation confirmation, refund limits, SLA tickets, agent assist."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from sqlalchemy import or_, select

from app.db.models import Customer, Order, PendingAction, SessionIdentity, Ticket, ToolIdempotency
from app.db.session import SyncSessionLocal
from app.pii import mask_email, mask_phone, redact_order
from app.rag.retriever import retrieve_faq, sources_for_ui

AUTO_MUTATION_LIMIT = 300.0
SENSITIVE_MUTATIONS = frozenset({"refund", "cancel", "address"})

CONFIRM_RE = re.compile(
    r"^\s*(yes|y|ok|okay|confirm|confirmed|go ahead|do it|proceed|sure)\s*[.!]*\s*$",
    re.I,
)
DENY_RE = re.compile(
    r"^\s*(no|n|nope|cancel that|nevermind|never mind|stop|don't|dont)\s*[.!]*\s*$",
    re.I,
)
VERIFY_TOKEN_RE = re.compile(
    r"(?:verify(?:\s+with)?|last\s*4(?:\s*digits?)?|last four|pin|code)[^\d]{0,12}(\d{4})\b",
    re.I,
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
FOUR_DIGIT_RE = re.compile(r"^\s*(\d{4})\s*$")


def is_confirm(text: str) -> bool:
    return bool(CONFIRM_RE.match(text or ""))


def is_deny(text: str) -> bool:
    return bool(DENY_RE.match(text or ""))


def parse_verify_token(text: str) -> str | None:
    t = (text or "").strip()
    m = VERIFY_TOKEN_RE.search(t)
    if m:
        return m.group(1)
    m = EMAIL_RE.search(t)
    if m and any(k in t.lower() for k in ("verify", "email", "my email", "account")):
        return m.group(0).lower()
    m = FOUR_DIGIT_RE.match(t)
    if m:
        return m.group(1)
    if t.lower().startswith("verify "):
        rest = t[7:].strip()
        return rest.lower() or None
    return None


def looks_like_verify(text: str) -> bool:
    t = (text or "").lower()
    if parse_verify_token(text):
        return True
    return "verify" in t or "last 4" in t or "last four" in t


def customer_tier(customer: Customer | None) -> str:
    if not customer:
        return "standard"
    if (customer.tier or "").lower() == "vip" or customer.loyalty_points >= 2000:
        return "vip"
    if (customer.tier or "").lower() == "gold" or customer.loyalty_points >= 1000:
        return "gold"
    return (customer.tier or "standard").lower()


def sla_minutes(category: str, tier: str, *, over_limit: bool = False) -> int:
    if over_limit or category in {"complaint", "refund_approval", "security"}:
        return 5 if tier == "vip" else 10
    if tier == "vip":
        return 5
    if category in {"payment", "refund"}:
        return 15
    return 30


def get_identity(session_id: str) -> dict:
    with SyncSessionLocal() as db:
        row = db.scalar(select(SessionIdentity).where(SessionIdentity.session_id == session_id))
        if not row:
            return {
                "session_id": session_id,
                "verified": False,
                "customer_id": None,
                "customer_name": None,
                "tier": None,
                "order_id": None,
                "verified_via": None,
            }
        cust = None
        if row.customer_id:
            cust = db.scalar(select(Customer).where(Customer.customer_id == row.customer_id))
        return {
            "session_id": session_id,
            "verified": bool(row.verified),
            "customer_id": row.customer_id,
            "customer_name": cust.name if cust else None,
            "tier": customer_tier(cust) if cust else None,
            "order_id": row.order_id,
            "verified_via": row.verified_via,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
        }


def _upsert_identity(db, session_id: str) -> SessionIdentity:
    row = db.scalar(select(SessionIdentity).where(SessionIdentity.session_id == session_id))
    if not row:
        row = SessionIdentity(session_id=session_id)
        db.add(row)
        db.flush()
    return row


def bind_order(session_id: str, order_id: str) -> dict:
    oid = order_id.strip().upper()
    with SyncSessionLocal() as db:
        order = db.scalar(select(Order).where(Order.order_id == oid))
        row = _upsert_identity(db, session_id)
        row.order_id = oid
        if order:
            row.customer_id = order.customer_id
        db.commit()
    return get_identity(session_id)


def verify_session(session_id: str, token: str, order_id: str | None = None) -> dict:
    token_n = (token or "").strip()
    ident = get_identity(session_id)
    oid = (order_id or ident.get("order_id") or "").strip().upper() or None
    with SyncSessionLocal() as db:
        customer = None
        order = None
        if oid:
            order = db.scalar(select(Order).where(Order.order_id == oid))
            if order:
                customer = db.scalar(select(Customer).where(Customer.customer_id == order.customer_id))
        if customer is None and ident.get("customer_id"):
            customer = db.scalar(
                select(Customer).where(Customer.customer_id == ident["customer_id"])
            )
        # Demo-friendly: resolve by phone last-4, else ORD-{last4}
        if customer is None and token_n.isdigit() and len(token_n) == 4:
            matches = [
                c
                for c in db.scalars(select(Customer)).all()
                if re.sub(r"\D", "", c.phone or "").endswith(token_n)
            ]
            if len(matches) == 1:
                customer = matches[0]
                latest = db.scalar(
                    select(Order)
                    .where(Order.customer_id == customer.customer_id)
                    .order_by(Order.created_at.desc())
                )
                if latest:
                    oid = latest.order_id
            elif len(matches) > 1:
                return {
                    "ok": False,
                    "error": "That last-4 matches more than one account. Share an order id (e.g. ORD-1001) first.",
                }
            if customer is None:
                guess_oid = f"ORD-{token_n}"
                order = db.scalar(select(Order).where(Order.order_id == guess_oid))
                if order:
                    oid = order.order_id
                    customer = db.scalar(
                        select(Customer).where(Customer.customer_id == order.customer_id)
                    )

        if customer is None:
            return {
                "ok": False,
                "error": "Share an order id first (e.g. ORD-1001), then verify with the last 4 digits of the phone on that account.",
            }

        phone_digits = re.sub(r"\D", "", customer.phone or "")
        email = (customer.email or "").lower()
        local = email.split("@")[0] if email else ""
        token_l = token_n.lower()
        matched = False
        via = None
        if token_n.isdigit() and len(token_n) == 4 and phone_digits.endswith(token_n):
            matched, via = True, "phone_last4"
        elif token_l == email or token_l == local:
            matched, via = True, "email"

        if not matched:
            return {
                "ok": False,
                "error": f"That didn't match the account on {oid or customer.customer_id}. Use the last 4 digits of the phone, or the email on file.",
            }

        row = _upsert_identity(db, session_id)
        row.verified = True
        row.verified_via = via
        row.verified_at = datetime.utcnow()
        row.customer_id = customer.customer_id
        if oid:
            row.order_id = oid
        db.commit()
    ident = get_identity(session_id)
    ident["ok"] = True
    return ident


def get_pending(session_id: str) -> dict | None:
    with SyncSessionLocal() as db:
        row = db.scalar(select(PendingAction).where(PendingAction.session_id == session_id))
        if not row:
            return None
        payload = json.loads(row.payload_json) if row.payload_json else {}
        return {
            "session_id": row.session_id,
            "action": row.action,
            "order_id": row.order_id,
            "amount": row.amount,
            "requires_approval": row.requires_approval,
            "payload": payload,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


def set_pending(
    session_id: str,
    action: str,
    order_id: str,
    *,
    amount: float,
    requires_approval: bool,
    payload: dict | None = None,
) -> dict:
    with SyncSessionLocal() as db:
        row = db.scalar(select(PendingAction).where(PendingAction.session_id == session_id))
        if not row:
            row = PendingAction(session_id=session_id)
            db.add(row)
        row.action = action
        row.order_id = order_id
        row.amount = amount
        row.requires_approval = requires_approval
        row.payload_json = json.dumps(payload or {}, ensure_ascii=False)
        row.created_at = datetime.utcnow()
        db.commit()
    return get_pending(session_id) or {}


def clear_pending(session_id: str) -> None:
    with SyncSessionLocal() as db:
        row = db.scalar(select(PendingAction).where(PendingAction.session_id == session_id))
        if row:
            db.delete(row)
            db.commit()


def get_idempotent(key: str) -> dict | None:
    with SyncSessionLocal() as db:
        row = db.scalar(select(ToolIdempotency).where(ToolIdempotency.idem_key == key))
        if not row:
            return None
        return json.loads(row.result_json)


def save_idempotent(key: str, result: dict) -> None:
    with SyncSessionLocal() as db:
        existing = db.scalar(select(ToolIdempotency).where(ToolIdempotency.idem_key == key))
        if existing:
            existing.result_json = json.dumps(result, ensure_ascii=False)
        else:
            db.add(
                ToolIdempotency(
                    idem_key=key,
                    result_json=json.dumps(result, ensure_ascii=False),
                )
            )
        db.commit()


def mutation_requires_approval(amount: float, tier: str) -> bool:
    limit = AUTO_MUTATION_LIMIT * 1.5 if tier == "vip" else AUTO_MUTATION_LIMIT
    return float(amount or 0) > limit


def create_sla_ticket(
    session_id: str,
    summary: str,
    category: str = "other",
    order_id: str | None = None,
    *,
    over_limit: bool = False,
) -> dict:
    import secrets

    ident = get_identity(session_id)
    tier = ident.get("tier") or "standard"
    minutes = sla_minutes(category, tier, over_limit=over_limit)
    due = datetime.utcnow() + timedelta(minutes=minutes)
    if over_limit or category in {"complaint", "refund_approval"}:
        priority = "urgent" if tier == "vip" or over_limit else "high"
    elif tier == "vip":
        priority = "high"
    else:
        priority = "normal"

    tid = "T-" + secrets.token_hex(3).upper()
    with SyncSessionLocal() as db:
        ticket = Ticket(
            ticket_id=tid,
            session_id=session_id,
            order_id=order_id.upper() if order_id else None,
            category=category,
            status="open",
            summary=summary[:500],
            priority=priority,
            sla_minutes=minutes,
            sla_due_at=due,
            assigned_to="human_queue" if priority in {"high", "urgent"} else None,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return _ticket_dict(ticket, now=datetime.utcnow())


def ticket_sla_status(ticket: Ticket, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    if ticket.status in {"resolved", "closed"}:
        return "met"
    if ticket.sla_due_at and now > ticket.sla_due_at:
        return "breached"
    return "on_track"


def _ticket_dict(t: Ticket, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    return {
        "ticket_id": t.ticket_id,
        "session_id": t.session_id,
        "order_id": t.order_id,
        "category": t.category,
        "status": t.status,
        "summary": t.summary,
        "priority": t.priority or "normal",
        "sla_minutes": t.sla_minutes,
        "sla_due_at": t.sla_due_at.isoformat() if t.sla_due_at else None,
        "sla_status": ticket_sla_status(t, now),
        "assigned_to": t.assigned_to,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def customer_360(customer_id: str | None, session_id: str | None = None) -> dict | None:
    from app.db.repository import list_chat_logs

    cid = (customer_id or "").strip().upper() or None
    ident = get_identity(session_id) if session_id else None
    if not cid and ident:
        cid = ident.get("customer_id")
    if not cid:
        return None
    with SyncSessionLocal() as db:
        c = db.scalar(select(Customer).where(Customer.customer_id == cid))
        if not c:
            return None
        orders = db.scalars(
            select(Order).where(Order.customer_id == cid).order_by(Order.created_at.desc())
        ).all()
        oids = [o.order_id for o in orders]
        ticket_filters = []
        if session_id:
            ticket_filters.append(Ticket.session_id == session_id)
        if oids:
            ticket_filters.append(Ticket.order_id.in_(oids))
        tickets = []
        if ticket_filters:
            tickets = db.scalars(
                select(Ticket).where(or_(*ticket_filters)).order_by(Ticket.created_at.desc())
            ).all()
        open_tickets = [t for t in tickets if t.status == "open"]
        return {
            "customer_id": c.customer_id,
            "name": c.name,
            "email": c.email,
            "email_masked": mask_email(c.email),
            "phone": c.phone,
            "phone_masked": mask_phone(c.phone),
            "tier": customer_tier(c),
            "loyalty_points": c.loyalty_points,
            "orders_count": len(orders),
            "open_orders": [
                {"order_id": o.order_id, "status": o.status, "amount": o.amount, "product": o.product}
                for o in orders[:8]
            ],
            "open_tickets": len(open_tickets),
            "lifetime_value": round(sum(o.amount for o in orders), 2),
            "identity": ident,
        }


def build_assist(session_id: str) -> dict:
    from app.db.repository import list_chat_logs, lookup_order

    ident = get_identity(session_id)
    pending = get_pending(session_id)
    logs = list_chat_logs(session_id, limit=40)
    last_user = next((x["content"] for x in reversed(logs) if x["role"] == "user"), "")
    hits = retrieve_faq(last_user or "customer support escalation", k=3) if last_user else []
    profile = customer_360(ident.get("customer_id"), session_id=session_id)
    oid = ident.get("order_id") or (pending or {}).get("order_id")
    order = redact_order(lookup_order(oid), verified=True) if oid else None

    if pending:
        action = pending["action"]
        draft = (
            f"I can take this from here. Recap: {action} on {pending['order_id']} "
            f"(¥{pending['amount']}). "
        )
        if pending["requires_approval"]:
            draft += (
                f"This is over the bot auto-limit of ¥{AUTO_MUTATION_LIMIT:.0f}, "
                "so I'll complete it as a specialist after a quick check."
            )
        else:
            draft += "I'll process it now that identity is verified."
        recommended = [pending["action"], "resume_bot_after"]
    elif last_user:
        draft = (
            "Thanks for waiting — I'm a SteelShop specialist. "
            f"I see your last message: “{(last_user[:180])}”. "
            "I'll follow the policy notes in the knowledge panel and update you here."
        )
        recommended = ["human_reply"]
    else:
        draft = "Hi, this is SteelShop specialist support. How can I help?"
        recommended = ["human_reply"]

    if ident.get("tier") == "vip":
        draft = "[VIP] " + draft

    return {
        "session_id": session_id,
        "identity": ident,
        "pending": pending,
        "profile": profile,
        "order": order,
        "policy_sources": sources_for_ui(hits),
        "policy_preview": [
            {"section": h.get("section"), "text": (h.get("text") or "")[:220]} for h in hits
        ],
        "recommended_actions": recommended,
        "suggested_reply": draft,
        "auto_limit": AUTO_MUTATION_LIMIT,
    }


def execute_pending(session_id: str, pending: dict) -> dict:
    """Run a confirmed mutation with idempotency (same order + action returns cached result)."""
    from app.db.repository import apply_refund, cancel_order, update_shipping_address

    action = pending.get("action")
    oid = pending.get("order_id")
    payload = pending.get("payload") or {}
    key = f"{action}:{oid}"
    cached = get_idempotent(key)
    if cached:
        clear_pending(session_id)
        return {**cached, "idempotent": True}

    if action == "refund":
        result = apply_refund(oid, payload.get("reason", "customer_request"))
    elif action == "cancel":
        result = cancel_order(oid, payload.get("reason", "customer_request"))
    elif action == "address":
        result = update_shipping_address(oid, payload.get("new_address") or "")
    else:
        result = {"ok": False, "error": f"Unknown pending action: {action}"}

    if result.get("ok"):
        save_idempotent(key, result)
        clear_pending(session_id)
    return result


def update_ticket_status(ticket_id: str, status: str) -> dict | None:
    allowed = {"open", "pending_customer", "pending_ops", "resolved", "closed"}
    status = (status or "").strip().lower()
    if status not in allowed:
        return {"ok": False, "error": f"Status must be one of {sorted(allowed)}"}
    tid = ticket_id.strip().upper()
    with SyncSessionLocal() as db:
        row = db.scalar(select(Ticket).where(Ticket.ticket_id == tid))
        if not row:
            return None
        row.status = status
        if status in {"resolved", "closed"}:
            row.assigned_to = row.assigned_to or "human_queue"
        db.commit()
        db.refresh(row)
        return {"ok": True, "ticket": _ticket_dict(row)}
