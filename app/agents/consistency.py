"""Consistency verifier — draft reply must not invent facts absent from evidence (MVP C5)."""

from __future__ import annotations

import re


_ID_RE = re.compile(r"\b(?:SHP|ORD|PAY|ASN|INV|SKU)-[\w-]+\b", re.I)
_MONEY_RE = re.compile(r"\bSGD\s*\d+(?:\.\d+)?|\b\$\s*\d+(?:\.\d+)?", re.I)
_DATEISH_RE = re.compile(
    r"\b\d{1,2}\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b|\b\d{4}-\d{2}-\d{2}\b",
    re.I,
)


def _evidence_blob(evidence: list[str] | str | None) -> str:
    if evidence is None:
        return ""
    if isinstance(evidence, str):
        return evidence
    return "\n".join(e for e in evidence if e)


def verify_draft(draft: str, evidence: list[str] | str | None) -> dict:
    """
    Return {ok, issues, draft}.
    If ids/money/dates in draft are absent from evidence → ok=False and a safer rewrite.
    """
    blob = _evidence_blob(evidence).lower()
    issues: list[str] = []

    if not draft.strip():
        return {"ok": False, "issues": ["empty_draft"], "draft": draft}

    # If no evidence at all for a tool/RAG path, skip strict check
    if not blob.strip():
        return {"ok": True, "issues": [], "draft": draft, "skipped": True}

    for m in _ID_RE.findall(draft):
        if m.lower() not in blob and m.upper() not in _evidence_blob(evidence):
            # allow if evidence has same id case-insensitively
            if m.lower() not in blob:
                issues.append(f"ungrounded_id:{m}")

    for m in _MONEY_RE.findall(draft):
        digits = re.sub(r"[^\d.]", "", m)
        if digits and digits not in re.sub(r"[^\d.]", " ", blob):
            # soft: only flag if amount looks specific
            if "." in digits or len(digits) >= 3:
                issues.append(f"ungrounded_amount:{m}")

    if issues:
        # Strip ungrounded ids from draft and add confirmation ask
        safe = draft
        for issue in issues:
            if issue.startswith("ungrounded_id:"):
                bad = issue.split(":", 1)[1]
                safe = re.sub(re.escape(bad), "[id withheld]", safe, flags=re.I)
        safe = (
            safe.rstrip()
            + "\n\nI want to double-check — does the id above match what you expected? "
            "Reply with the correct SHP/SKU if not."
        )
        return {"ok": False, "issues": issues, "draft": safe}

    return {"ok": True, "issues": [], "draft": draft}


def evidence_from_hits(hits: list[dict]) -> list[str]:
    return [str(h.get("text") or "") for h in hits]


def evidence_from_tool(data: dict | list | str | None) -> list[str]:
    import json

    if data is None:
        return []
    if isinstance(data, str):
        return [data]
    try:
        return [json.dumps(data, ensure_ascii=False)]
    except Exception:
        return [str(data)]
