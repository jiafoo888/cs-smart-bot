"""PII masking for customer-facing chat and stored audit logs."""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
PHONE_RE = re.compile(r"\b(?:\+?\d[\d\s-]{8,}\d)\b")


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, _, domain = email.partition("@")
    keep = local[:1] if local else ""
    return f"{keep}***@{domain}"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "***"
    return f"***{digits[-4:]}"


def mask_address(address: str | None) -> str | None:
    if not address:
        return address
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if not parts:
        return "***"
    return f"(hidden until verified) · {parts[-1]}"


def redact_free_text(text: str) -> str:
    text = EMAIL_RE.sub(lambda m: mask_email(m.group(0)) or "***", text)
    text = PHONE_RE.sub(lambda m: mask_phone(m.group(0)) or "***", text)
    return text


def redact_order(data: dict | None, *, verified: bool) -> dict | None:
    if not data:
        return data
    out = dict(data)
    if not verified:
        out["shipping_address"] = mask_address(out.get("shipping_address"))
        if out.get("customer_email"):
            out["customer_email"] = mask_email(out["customer_email"])
        if out.get("customer_phone"):
            out["customer_phone"] = mask_phone(out["customer_phone"])
    return out


def redact_payment(data: dict | None, *, verified: bool) -> dict | None:
    if not data:
        return data
    out = dict(data)
    if not verified and out.get("transaction_ref"):
        ref = str(out["transaction_ref"])
        out["transaction_ref"] = ref[:4] + "***" if len(ref) > 4 else "***"
    return out
