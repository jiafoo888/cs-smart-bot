"""
Lesson 03 — RAG
跑：python lessons/03_rag.py

面试要点：
Chunk → Embed → Retrieve → Generate（本课演示前三步 + 拼 context）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import main as bootstrap
from app.rag.retriever import format_context, retrieve_faq


def main() -> None:
    print("=== Lesson 03: RAG ===\n")
    bootstrap()

    queries = [
        "退货几天内可以申请？",
        "退款多久到账？",
        "怎么开发票？",
    ]
    for q in queries:
        hits = retrieve_faq(q, k=2)
        print(f"\nQ: {q}")
        print(format_context(hits))

    print("\n面试句：政策进向量库不进权重；检索召回后 grounded 生成，减少幻觉。")


if __name__ == "__main__":
    main()
