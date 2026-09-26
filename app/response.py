"""Turn internal tool/RAG data into natural customer-facing replies.

Scores, agent labels, and raw chunk dumps stay in debug only — never in user text.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.llm import USE_MOCK, get_chat_model


GROUNDING_SYSTEM = """You are SteelShop customer support.
Answer ONLY using the POLICY CONTEXT below. Be concise, friendly, and natural.
Do NOT mention retrieval scores, chunk ids, vector stores, agents, MCP, or RAG.
Do NOT invent order/payment facts. If context is insufficient, say so briefly.
Keep the reply under 120 words."""


def _clean_policy_text(text: str) -> str:
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def compose_policy_answer(question: str, hits: list[dict]) -> str:
    """RAG generate step: grounded answer without exposing scores."""
    if not hits:
        return (
            "I couldn't find that in our help docs. "
            "I can help with orders, payments, shipping, returns, or invoices — "
            "or say \"talk to a human\" to escalate."
        )

    context = "\n\n".join(
        f"- {_clean_policy_text(h.get('text', ''))}" for h in hits[:3] if h.get("text")
    )

    if not USE_MOCK:
        model = get_chat_model()
        msg = model.invoke(
            [
                SystemMessage(content=GROUNDING_SYSTEM),
                HumanMessage(
                    content=f"POLICY CONTEXT:\n{context}\n\nCUSTOMER QUESTION:\n{question}"
                ),
            ]
        )
        return str(msg.content).strip()

    # Offline mock: turn top substantial chunk into a short spoken answer
    body = ""
    for h in hits:
        top = _clean_policy_text(h.get("text", ""))
        lines = [
            ln.strip()
            for ln in top.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        # Drop short title-only lines
        body_lines = [
            ln
            for ln in lines
            if len(ln) > 40 or (len(ln) > 20 and any(ch in ln for ch in ".;:"))
        ]
        candidate = " ".join(body_lines) if body_lines else " ".join(lines[1:] if len(lines) > 1 else lines)
        candidate = " ".join(candidate.split())
        if len(candidate) >= 60:
            body = candidate
            break
    if not body:
        body = " ".join(_clean_policy_text(hits[0].get("text", "")).split())
    if len(body) > 320:
        body = body[:317].rsplit(" ", 1)[0] + "..."
    return f"{body}\n\nAnything else I can help with — an order, payment, or return?"


def compose_order_answer(data: dict, pays: list[dict] | None = None, *, verified: bool = False) -> str:
    pays = pays or data.get("payments") or []
    tracking = data.get("tracking_no")
    carrier = data.get("carrier")
    ship = (
        f"{carrier} tracking {tracking}"
        if tracking
        else "no tracking number yet (not shipped)"
    )
    pay_bit = ""
    if pays:
        p0 = pays[0]
        pay_bit = (
            f" The latest payment {p0['payment_id']} is {p0['status']} "
            f"(¥{p0['amount']})."
        )
    addr = data.get("shipping_address") or "n/a"
    verify_nudge = ""
    if not verified:
        verify_nudge = (
            " Full address is hidden until you verify — reply with the last 4 digits "
            "of the phone on this order (demo: 1001 for ORD-1001)."
        )
    return (
        f"Here's what I see for {data['order_id']}: "
        f"{data['product']} (x{data.get('quantity', 1)}) for "
        f"¥{data['amount']} {data.get('currency', 'CNY')}, status {data['status']}. "
        f"Shipping: {ship}. "
        f"Address on file: {addr}."
        f"{pay_bit}{verify_nudge}"
    )


def compose_payment_answer(data: dict) -> str:
    return (
        f"Payment {data['payment_id']} for order {data['order_id']} is "
        f"{data['status']}. Amount ¥{data['amount']} via {data['method']}. "
        f"Reference: {data.get('transaction_ref') or 'n/a'}. "
        f"Paid at: {data.get('paid_at') or 'not completed yet'}."
    )


def compose_payments_list(order_id: str, pays: list[dict]) -> str:
    if not pays:
        return f"I don't see any payments on file for {order_id}."
    lines = [
        f"{p['payment_id']}: ¥{p['amount']} via {p['method']} — {p['status']}" for p in pays
    ]
    return f"Payments for {order_id}:\n- " + "\n- ".join(lines)


def compose_refund_answer(result: dict, policy_hits: list[dict]) -> str:
    if not result.get("ok"):
        return (
            f"I couldn't process that refund: {result.get('error')}. "
            "If the order isn't shipped yet, we usually cancel instead of refunding. "
            "Share the order id if you'd like me to check again."
        )
    o = result["order"]
    p = result.get("payment")
    timing = ""
    for h in policy_hits[:2]:
        text = (h.get("text") or "").lower()
        if "1–3" in text or "1-3" in text or "business day" in text:
            timing = " Wallet refunds usually land in 1–3 business days; cards may take 3–7."
            break
    pay_line = (
        f" Payment {p['payment_id']} is now marked {p['status']}." if p else ""
    )
    return (
        f"I've submitted the refund for {o['order_id']} (¥{o['amount']}). "
        f"Order status is now {o['status']}.{pay_line}{timing} "
        "You'll see it on the original payment method."
    )


def compose_cancel_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't cancel that order: {result.get('error')}"
    o = result["order"]
    return (
        f"Order {o['order_id']} is cancelled. "
        "If a payment was still pending, it won't be captured. "
        "Anything else I can help with?"
    )


def compose_address_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't update the address: {result.get('error')}"
    o = result["order"]
    return (
        f"Updated shipping address for {o['order_id']} to: {o.get('shipping_address')}. "
        "This only works before the parcel ships."
    )


def compose_greeting() -> str:
    return (
        "Hi! I'm SteelShop support. I can help with orders, payments, tracking, "
        "invoices, exchanges, cancellations, loyalty points, returns, and policies. "
        "For refunds, cancellations, or address changes I'll verify the account first "
        "(last 4 of the phone on the order). What do you need today?"
    )


def compose_tracking_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't load tracking: {result.get('error')}"
    events = result.get("events") or []
    if not result.get("tracking_no"):
        return (
            f"Order {result.get('order_id')} doesn't have a tracking number yet — "
            "it hasn't shipped. I can nudge fulfillment if you'd like."
        )
    if not events:
        return (
            f"Tracking {result.get('tracking_no')} ({result.get('carrier') or 'carrier'}) "
            "is on file, but no scan events yet."
        )
    lines = []
    for e in events:
        when = (e.get("event_time") or "")[:16].replace("T", " ")
        loc = f" · {e['location']}" if e.get("location") else ""
        lines.append(f"- {when}: {e['description']}{loc}")
    return (
        f"Tracking for {result['order_id']} ({result.get('carrier')} {result.get('tracking_no')}):\n"
        + "\n".join(lines)
    )


def compose_invoice_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't issue an invoice: {result.get('error')}"
    inv = result["invoice"]
    prefix = "There's already an invoice on file" if result.get("already_exists") else "E-invoice issued"
    return (
        f"{prefix}: {inv['invoice_id']} for {inv['order_id']} "
        f"(¥{inv['amount']}, {inv['title']}, status {inv['status']}). "
        f"Download link: {inv.get('pdf_url') or 'n/a'}."
    )


def compose_exchange_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't start an exchange: {result.get('error')}"
    ex = result["exchange"]
    return (
        f"Exchange request {ex['exchange_id']} submitted for {ex['order_id']} "
        f"(reason: {ex['reason']}). Status: {ex['status']}. "
        "We'll email next steps within 1 business day."
    )


def compose_nudge_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't nudge fulfillment: {result.get('error')}"
    return (
        f"I've flagged {result['order']['order_id']} for priority picking. "
        f"Estimated ship-by: {result.get('estimated_ship_by')}. "
        "You'll get tracking as soon as it leaves the warehouse."
    )


def compose_loyalty_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"I couldn't load loyalty info: {result.get('error')}"
    coupons = result.get("coupons") or []
    active = [c for c in coupons if c.get("status") == "active"]
    if active:
        lines = "\n".join(
            f"- {c['code']}: {c['title']} ({c['discount']})"
            + (f", expires {c['expires_at'][:10]}" if c.get("expires_at") else "")
            for c in active
        )
        coupon_bit = f"Active coupons:\n{lines}"
    else:
        coupon_bit = "No active coupons right now."
    return (
        f"{result['name']} ({result['customer_id']}) has "
        f"{result['loyalty_points']} loyalty points. {coupon_bit}"
    )


def compose_csat_answer(result: dict) -> str:
    if not result.get("ok"):
        return f"Couldn't save that rating: {result.get('error')}"
    score = result["rating"]["score"]
    return (
        f"Thanks — recorded a {score}/5 satisfaction score for this chat. "
        "We use this to improve SteelShop Care."
    )


def compose_handoff_hold(ticket_id: str | None = None) -> str:
    tid = f" Ticket {ticket_id}." if ticket_id else ""
    return (
        f"I've paused the bot and handed this chat to a human specialist.{tid} "
        "Please wait — an agent will reply here. "
        "(Ops can resume the bot from the console.)"
    )


def compose_handoff_waiting() -> str:
    return (
        "A human agent is handling this conversation, so I'm paused for now. "
        "Hang tight — or Ops can resume the bot from the console."
    )


def parse_csat_score(text: str) -> int | None:
    import re

    t = text.lower().strip()
    m = re.search(r"(?:rate|rating|score|csat|stars?)[^\d]{0,12}([1-5])\b", t)
    if m:
        return int(m.group(1))
    m = re.fullmatch(r"([1-5])\s*(?:/5|stars?)?", t)
    if m:
        return int(m.group(1))
    return None


def compose_off_topic() -> str:
    return (
        "I'm here for SteelShop shopping support (orders, payments, shipping, returns). "
        "I can't help with unrelated topics — want to check an order or a policy instead?"
    )


def compose_verify_prompt(order_id: str | None = None) -> str:
    target = f" for {order_id}" if order_id else ""
    return (
        f"I need to verify the account{target} before I can show personal details "
        "or change the order. Reply with the last 4 digits of the phone on file, "
        "or the account email. (Demo: ORD-1001 → 1001, ORD-1002 → 1002, VIP ORD-1005 → 1004.)"
    )


def compose_verify_ok(ident: dict) -> str:
    name = ident.get("customer_name") or ident.get("customer_id") or "the account"
    tier = ident.get("tier") or "standard"
    extra = " VIP routing is on." if tier == "vip" else ""
    return (
        f"Verified — thanks, {name} ({tier} tier).{extra} "
        "I can now show full order details and take actions like refund, cancel, or address change."
    )


def compose_verify_fail(error: str) -> str:
    return f"Verification didn't go through: {error}"


def compose_confirm_mutation(pending: dict) -> str:
    action = pending.get("action")
    oid = pending.get("order_id")
    amount = pending.get("amount")
    from app.trust import AUTO_MUTATION_LIMIT

    if pending.get("requires_approval"):
        return (
            f"I can start a {action} for {oid} (¥{amount}). "
            f"That's over the bot auto-limit of ¥{AUTO_MUTATION_LIMIT:.0f}, so a specialist "
            "must approve it after you confirm. Reply YES to open a priority ticket, or NO to cancel."
        )
    return (
        f"Please confirm: I will {action} {oid} (¥{amount}). "
        "This can't be undone from chat. Reply YES to proceed, or NO to cancel."
    )


def compose_denied_mutation() -> str:
    return "Okay — I cancelled that pending action. Nothing was changed."


def compose_approval_hold(ticket: dict, pending: dict) -> str:
    return (
        f"Confirmed. {pending['action'].title()} on {pending['order_id']} (¥{pending['amount']}) "
        f"needs specialist approval. Opened ticket {ticket['ticket_id']} "
        f"({ticket.get('priority')} priority, first-response SLA {ticket.get('sla_minutes')} min). "
        "I've paused the bot so an agent can finish this."
    )


def compose_escalate(ticket_id: str, order_id: str | None = None) -> str:
    base = (
        f"I've opened ticket {ticket_id} for a human specialist. "
        "They'll follow up using this conversation."
    )
    if order_id:
        return f"{base} I also linked order {order_id}."
    return base


def compose_pending_reminder(pending: dict) -> str:
    return (
        f"There's still a pending {pending.get('action')} for {pending.get('order_id')} "
        f"(¥{pending.get('amount')}). Reply YES to continue, or NO to cancel it."
    )


def is_greeting(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    greetings = {
        "hi",
        "hello",
        "hey",
        "hiya",
        "yo",
        "good morning",
        "good afternoon",
        "good evening",
        "thanks",
        "thank you",
        "thx",
        "bye",
        "goodbye",
        "ok",
        "okay",
    }
    if t in greetings:
        return True
    return bool(re.fullmatch(r"(hi|hello|hey)[!?.,\s]*", t))


def is_follow_up(text: str) -> bool:
    """True when the user refers to the previous order without restating intent broadly."""
    t = text.lower()
    cues = (
        "that order",
        "my order",
        "the order",
        "same order",
        "this order",
        "track it",
        "tracking",
        "its status",
        "it's status",
        "refund it",
        "cancel it",
        "what about payment",
        "and the payment",
    )
    return any(c in t for c in cues)
