"""Enterprise policy ingest: section-aware chunking + rich metadata."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import get_settings
from app.rag.store import build_from_documents


def _category_from_name(name: str) -> str:
    n = name.lower()
    if "inbound" in n:
        return "inbound"
    if "outbound" in n or "cutoff" in n:
        return "outbound"
    if "carrier" in n:
        return "carrier"
    if "claim" in n or "freight" in n:
        return "claims"
    if "gst" in n or "invoice" in n or "payment" in n:
        return "invoice"
    if "return" in n or "refund" in n:
        return "return_refund"
    if "warranty" in n:
        return "warranty"
    if "catalog" in n or "finder" in n or "product" in n:
        return "product"
    if "loyalty" in n or "reward" in n:
        return "loyalty"
    if "exchange" in n or "size" in n:
        return "exchange"
    if "delivery" in n:
        return "shipping"
    if "privacy" in n or "security" in n:
        return "privacy"
    if "sla" in n or "support" in n or "company" in n:
        return "company"
    if "ship" in n:
        return "shipping"
    if "faq" in n:
        return "faq"
    if "upload" in n:
        return "upload"
    return "policy"


def collect_policy_files() -> list[Path]:
    settings = get_settings()
    files: list[Path] = []
    if settings.policies_dir.exists():
        files.extend(sorted(settings.policies_dir.glob("*.md")))
    if settings.faq_path.exists():
        files.append(settings.faq_path)
    # de-dupe by name
    seen: set[str] = set()
    unique: list[Path] = []
    for p in files:
        if p.name in seen:
            continue
        seen.add(p.name)
        unique.append(p)
    return unique


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Return (section_title, section_body) pairs preserving H2 structure."""
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"\n(?=## )", text)
    out: list[tuple[str, str]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.splitlines()
        title = "Overview"
        body = part
        if lines[0].startswith("# "):
            title = lines[0].lstrip("# ").strip()
            body = "\n".join(lines[1:]).strip()
        elif lines[0].startswith("## "):
            title = lines[0].lstrip("# ").strip()
            body = "\n".join(lines[1:]).strip()
        if not body:
            body = title
        out.append((title, body))
    return out or [("Overview", text)]


def load_documents() -> list[Document]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n### ", "\n\n", "\n", ". ", "; ", ", ", " "],
        length_function=len,
    )
    docs: list[Document] = []
    for path in collect_policy_files():
        raw = path.read_text(encoding="utf-8")
        category = _category_from_name(path.stem)
        for section_title, section_body in _split_by_headings(raw):
            # Prefix chunk with section title so embeddings carry topic signal
            prefixed = f"{section_title}\n\n{section_body}".strip()
            pieces = splitter.split_text(prefixed)
            for i, piece in enumerate(pieces):
                chunk_id = hashlib.md5(
                    f"{path.name}:{section_title}:{i}:{piece[:64]}".encode()
                ).hexdigest()[:12]
                docs.append(
                    Document(
                        page_content=piece,
                        metadata={
                            "source": path.name,
                            "category": category,
                            "section": section_title,
                            "chunk_index": i,
                            "chunk_id": chunk_id,
                            "doc_title": path.stem.replace("_", " ").title(),
                        },
                    )
                )
    return docs


def ingest_all_policies() -> dict:
    """Full rebuild: policies + catalog markdown + user uploads."""
    from app.rag.uploads import ingest_all_with_uploads

    return ingest_all_with_uploads()


def knowledge_base_stats() -> dict:
    settings = get_settings()
    files = collect_policy_files()
    chunk_count = 0
    try:
        from app.rag.store import _simple_dir, chroma_dir, get_vectorstore

        store = get_vectorstore(reset=False)
        if settings.vector_store == "chroma":
            chunk_count = store._collection.count()  # noqa: SLF001
            persist = str(chroma_dir())
        else:
            chunk_count = len(getattr(store, "docs", []) or [])
            persist = str(_simple_dir())
    except Exception:
        persist = str(settings.vector_dir)
        chunk_count = 0
    return {
        "company": settings.company_name,
        "documents": [
            {
                "name": p.name,
                "category": _category_from_name(p.stem),
                "bytes": p.stat().st_size,
            }
            for p in files
        ],
        "document_count": len(files),
        "chunk_count": chunk_count,
        "chunk_size": settings.rag_chunk_size,
        "chunk_overlap": settings.rag_chunk_overlap,
        "top_k": settings.rag_top_k,
        "embedding_backend": settings.embedding_backend,
        "vector_store": settings.vector_store,
        "persist_dir": persist,
    }


def ingest_faq() -> int:
    return int(ingest_all_policies()["chunks"])
