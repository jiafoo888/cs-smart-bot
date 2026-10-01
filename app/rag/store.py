"""Vector store: lightweight numpy (free-tier friendly) or optional Chroma."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
from langchain_core.documents import Document

from app.config import get_settings
from app.rag.embeddings import get_embeddings

_COLLECTION = "steelhub_logistics"


class SimpleVectorStore:
    """File-backed cosine search — no Chromadb process, ideal for free PaaS."""

    def __init__(self, persist_dir: Path):
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.meta_path = self.persist_dir / "docs.json"
        self.emb_path = self.persist_dir / "embeddings.npy"
        self.docs: list[dict] = []
        self.embeddings: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if self.meta_path.exists() and self.emb_path.exists():
            self.docs = json.loads(self.meta_path.read_text(encoding="utf-8"))
            self.embeddings = np.load(self.emb_path)

    def _save(self) -> None:
        self.meta_path.write_text(
            json.dumps(self.docs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        assert self.embeddings is not None
        np.save(self.emb_path, self.embeddings)

    def reset(self) -> None:
        if self.persist_dir.exists():
            shutil.rmtree(self.persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.docs = []
        self.embeddings = None

    def add_documents(self, documents: list[Document]) -> None:
        emb = get_embeddings()
        texts = [d.page_content for d in documents]
        vectors = np.asarray(emb.embed_documents(texts), dtype=np.float32)
        # L2 normalize
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
        vectors = vectors / norms
        payload = [
            {"page_content": d.page_content, "metadata": dict(d.metadata or {})}
            for d in documents
        ]
        if self.embeddings is None or len(self.docs) == 0:
            self.docs = payload
            self.embeddings = vectors
        else:
            self.docs.extend(payload)
            self.embeddings = np.vstack([self.embeddings, vectors])
        self._save()

    def similarity_search(
        self, query: str, k: int = 3, filter: dict | None = None
    ) -> list[Document]:
        pairs = self.similarity_search_with_score(query, k=k * 3 if filter else k)
        out: list[Document] = []
        for doc, _ in pairs:
            if filter:
                meta = doc.metadata or {}
                if any(meta.get(k) != v for k, v in filter.items()):
                    continue
            out.append(doc)
            if len(out) >= k:
                break
        return out

    def similarity_search_with_score(self, query: str, k: int = 3) -> list[tuple[Document, float]]:
        if not self.docs or self.embeddings is None:
            return []
        emb = get_embeddings()
        q = np.asarray(emb.embed_query(query), dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-9)
        scores = self.embeddings @ q
        idx = np.argsort(-scores)[:k]
        out: list[tuple[Document, float]] = []
        for i in idx:
            item = self.docs[int(i)]
            # Convert cosine similarity to a distance-like value for callers
            # that expect "lower is closer"; our retriever converts distance→sim.
            # We return distance = 1 - cosine so existing converter works.
            dist = float(1.0 - scores[int(i)])
            out.append(
                (
                    Document(page_content=item["page_content"], metadata=item.get("metadata") or {}),
                    dist,
                )
            )
        return out


def _simple_dir() -> Path:
    path = get_settings().vector_dir / "simple"
    path.mkdir(parents=True, exist_ok=True)
    return path


def chroma_dir() -> Path:
    path = get_settings().vector_dir / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _use_chroma() -> bool:
    return (get_settings().vector_store or "simple").lower() == "chroma"


def get_vectorstore(*, reset: bool = False):
    if _use_chroma():
        from langchain_chroma import Chroma

        if reset:
            root = chroma_dir()
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True, exist_ok=True)
        return Chroma(
            collection_name=_COLLECTION,
            embedding_function=get_embeddings(),
            persist_directory=str(chroma_dir()),
        )

    store = SimpleVectorStore(_simple_dir())
    if reset:
        store.reset()
    return store


def build_from_documents(docs: list[Document]):
    store = get_vectorstore(reset=True)
    if docs:
        store.add_documents(docs)
    return store


def similarity_search(query: str, k: int = 3, category: str | None = None) -> list[Document]:
    store = get_vectorstore(reset=False)
    if category:
        return store.similarity_search(query, k=k, filter={"category": category})
    return store.similarity_search(query, k=k)


def similarity_search_with_score(query: str, k: int = 3) -> list[tuple[Document, float]]:
    store = get_vectorstore(reset=False)
    pairs = store.similarity_search_with_score(query, k=k)
    out: list[tuple[Document, float]] = []
    for doc, dist in pairs:
        try:
            sim = 1.0 / (1.0 + float(dist))
        except Exception:
            sim = 0.0
        out.append((doc, sim))
    return out
