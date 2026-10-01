"""Upload + ingest PDF / MD / TXT into the vector store (MVP C6)."""

from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import select

from app.config import DATA_DIR, get_settings
from app.db.models import UploadedDocument
from app.db.session import SyncSessionLocal
from app.rag.ingest import _split_by_headings, collect_policy_files


UPLOAD_DIR = DATA_DIR / "uploads"
ALLOWED_EXT = {".pdf", ".md", ".txt", ".markdown"}
MAX_BYTES = 5 * 1024 * 1024


def ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


def _extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".md", ".txt", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pypdf is required for PDF upload") from exc
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n\n".join(pages).strip()
    raise ValueError(f"Unsupported file type: {ext}")


def list_uploads() -> list[dict]:
    with SyncSessionLocal() as db:
        rows = db.scalars(
            select(UploadedDocument).order_by(UploadedDocument.created_at.desc())
        ).all()
        return [
            {
                "doc_id": r.doc_id,
                "filename": r.filename,
                "mime": r.mime,
                "bytes": r.bytes_size,
                "status": r.status,
                "chunk_count": r.chunk_count,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "error": r.error_message,
            }
            for r in rows
        ]


def save_upload(filename: str, raw: bytes, mime: str = "application/octet-stream") -> dict:
    ensure_upload_dir()
    if len(raw) > MAX_BYTES:
        raise ValueError(f"File too large (max {MAX_BYTES // (1024 * 1024)}MB)")
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise ValueError("Only .pdf, .md, .txt are allowed")

    doc_id = f"UP-{uuid.uuid4().hex[:8].upper()}"
    safe = re.sub(r"[^\w.\-]+", "_", name)
    dest = UPLOAD_DIR / f"{doc_id}_{safe}"
    dest.write_bytes(raw)

    with SyncSessionLocal() as db:
        row = UploadedDocument(
            doc_id=doc_id,
            filename=name,
            mime=mime or "application/octet-stream",
            stored_path=str(dest),
            bytes_size=len(raw),
            status="stored",
            chunk_count=0,
        )
        db.add(row)
        db.commit()

    # Auto-reingest so the file is searchable
    stats = ingest_all_with_uploads()
    # refresh chunk count for this file from latest ingest metadata
    with SyncSessionLocal() as db:
        row = db.scalar(select(UploadedDocument).where(UploadedDocument.doc_id == doc_id))
        if row:
            row.status = "ingested"
            row.chunk_count = int(stats.get("upload_chunks_by_file", {}).get(name, 0))
            db.commit()
            return {
                "doc_id": row.doc_id,
                "filename": row.filename,
                "bytes": row.bytes_size,
                "status": row.status,
                "chunk_count": row.chunk_count,
                "ingest": stats,
            }
    return {"doc_id": doc_id, "filename": name, "ingest": stats}


def _docs_from_upload(path: Path, filename: str) -> list[Document]:
    settings = get_settings()
    raw = _extract_text(path)
    if not raw.strip():
        return []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        separators=["\n### ", "\n\n", "\n", ". ", " "],
        length_function=len,
    )
    docs: list[Document] = []
    category = "upload"
    for section_title, section_body in _split_by_headings(raw):
        prefixed = f"{section_title}\n\n{section_body}".strip()
        pieces = splitter.split_text(prefixed)
        for i, piece in enumerate(pieces):
            chunk_id = hashlib.md5(
                f"upload:{filename}:{section_title}:{i}:{piece[:64]}".encode()
            ).hexdigest()[:12]
            docs.append(
                Document(
                    page_content=piece,
                    metadata={
                        "source": filename,
                        "category": category,
                        "section": section_title,
                        "chunk_index": i,
                        "chunk_id": chunk_id,
                        "doc_title": Path(filename).stem.replace("_", " ").title(),
                    },
                )
            )
    return docs


def load_upload_documents() -> tuple[list[Document], dict[str, int]]:
    ensure_upload_dir()
    docs: list[Document] = []
    by_file: dict[str, int] = {}
    with SyncSessionLocal() as db:
        rows = db.scalars(select(UploadedDocument)).all()
        for row in rows:
            path = Path(row.stored_path)
            if not path.exists():
                continue
            try:
                file_docs = _docs_from_upload(path, row.filename)
            except Exception as exc:  # noqa: BLE001
                row.status = "error"
                row.error_message = str(exc)[:500]
                continue
            docs.extend(file_docs)
            by_file[row.filename] = len(file_docs)
            row.status = "ingested"
            row.chunk_count = len(file_docs)
        db.commit()
    return docs, by_file


def ingest_all_with_uploads() -> dict:
    """Rebuild vector store from policies + uploads."""
    from app.rag.store import build_from_documents
    from app.rag.ingest import load_documents

    settings = get_settings()
    try:
        from app.catalog import ensure_catalog_markdown, reload_products

        reload_products()
        ensure_catalog_markdown()
    except Exception:
        pass

    policy_docs = load_documents()
    upload_docs, by_file = load_upload_documents()
    all_docs = policy_docs + upload_docs
    build_from_documents(all_docs)
    by_cat: dict[str, int] = {}
    for d in all_docs:
        cat = d.metadata.get("category", "policy")
        by_cat[cat] = by_cat.get(cat, 0) + 1
    return {
        "chunks": len(all_docs),
        "policy_chunks": len(policy_docs),
        "upload_chunks": len(upload_docs),
        "upload_chunks_by_file": by_file,
        "files": [p.name for p in collect_policy_files()],
        "uploads": list(by_file.keys()),
        "categories": by_cat,
        "chunk_size": settings.rag_chunk_size,
        "chunk_overlap": settings.rag_chunk_overlap,
        "backend": settings.vector_store,
        "embedding_backend": settings.embedding_backend,
    }
