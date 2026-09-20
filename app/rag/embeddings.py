"""Embeddings for LangChain RAG: hash (offline) or sentence-transformers."""

from __future__ import annotations

import hashlib
import re

import numpy as np
from langchain_core.embeddings import Embeddings

from app.config import get_settings


def _hash_embed(texts: list[str], dim: int = 384) -> list[list[float]]:
    mats: list[list[float]] = []
    for text in texts:
        vec = np.zeros(dim, dtype=np.float32)
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
        for tok in tokens:
            for n in (1, 2, 3):
                for i in range(max(1, len(tok) - n + 1)):
                    gram = tok[i : i + n]
                    h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
                    vec[h % dim] += 1.0
        norm = float(np.linalg.norm(vec) + 1e-9)
        mats.append((vec / norm).tolist())
    return mats


class HashEmbeddings(Embeddings):
    """Deterministic offline embeddings — good enough for demo RAG + eval."""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return _hash_embed(texts, self.dim)

    def embed_query(self, text: str) -> list[float]:
        return _hash_embed([text], self.dim)[0]


def get_embeddings() -> Embeddings:
    settings = get_settings()
    backend = (settings.embedding_backend or "auto").lower()
    if backend == "hash":
        return HashEmbeddings()
    if backend in ("st", "auto"):
        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(model_name=settings.embedding_model)
        except Exception:
            if backend == "st":
                raise
            return HashEmbeddings()
    return HashEmbeddings()
