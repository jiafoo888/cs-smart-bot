"""RAG retrieve helpers on top of LangChain Chroma."""

from __future__ import annotations

import re

from app.config import get_settings
from app.rag.store import similarity_search, similarity_search_with_score


def retrieve_faq(query: str, k: int | None = None, category: str | None = None) -> list[dict]:
    settings = get_settings()
    top_k = k or settings.rag_top_k
    try:
        pairs = similarity_search_with_score(query, k=max(top_k * 3, 8))
    except Exception:
        docs = similarity_search(query, k=max(top_k * 3, 8))
        pairs = [(d, 0.0) for d in docs]

    q_terms = {t for t in re.findall(r"[a-z0-9]{3,}", query.lower()) if t not in {"the", "and", "for", "what", "how"}}
    q_l = query.lower()

    def _intent_boost(meta: dict) -> float:
        cat = (meta.get("category") or "").lower()
        section = (meta.get("section") or "").lower()
        boost = 0.0
        if any(w in q_l for w in ("return", "refund", "return window", "no-reason")):
            if cat == "return_refund" or "return" in section or "refund" in section:
                boost += 0.45
            if cat == "warranty":
                boost -= 0.25
        if "warranty" in q_l or "defect" in q_l:
            if cat == "warranty":
                boost += 0.45
        if any(w in q_l for w in ("ship", "tracking", "delivery", "carrier")):
            if cat == "shipping":
                boost += 0.4
        if any(w in q_l for w in ("invoice", "payment method", "duplicate charge")):
            if cat == "payment":
                boost += 0.4
        if "sla" in q_l or "response time" in q_l:
            if cat == "company":
                boost += 0.35
        return boost

    hits: list[dict] = []
    for doc, score in pairs:
        meta = doc.metadata or {}
        if category and meta.get("category") != category:
            continue
        text_l = (doc.page_content or "").lower()
        section_l = (meta.get("section") or "").lower()
        overlap = sum(1 for t in q_terms if t in text_l or t in section_l)
        hybrid = float(score or 0.0) + 0.08 * overlap + _intent_boost(meta)
        hits.append(
            {
                "text": doc.page_content,
                "source": meta.get("source", "?"),
                "category": meta.get("category", "?"),
                "section": meta.get("section", ""),
                "doc_title": meta.get("doc_title", meta.get("source", "?")),
                "chunk_id": meta.get("chunk_id", ""),
                "score": hybrid,
                "vector_score": float(score or 0.0),
                "overlap": overlap,
            }
        )

    hits.sort(key=lambda h: (h["score"], h["overlap"]), reverse=True)
    # Prefer chunks that actually mention query terms when present
    if q_terms:
        grounded = [h for h in hits if h["overlap"] > 0]
        if grounded:
            hits = grounded + [h for h in hits if h["overlap"] == 0]
    return hits[:top_k]


def format_context(hits: list[dict]) -> str:
    if not hits:
        return "(No relevant policy passages found. Try rephrasing or escalate to a human.)"
    lines = []
    for i, h in enumerate(hits, 1):
        src = h.get("source", "?")
        section = h.get("section") or h.get("category", "?")
        lines.append(f"[{i}] ({src} · {section})\n{h['text']}")
    return "\n\n".join(lines)


def sources_for_ui(hits: list[dict]) -> list[dict]:
    """Customer-safe source chips — titles only, no scores."""
    out = []
    seen = set()
    for h in hits:
        key = (h.get("source"), h.get("section"))
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "title": h.get("section") or h.get("doc_title") or h.get("source"),
                "document": h.get("source"),
                "category": h.get("category"),
            }
        )
    return out[:5]
