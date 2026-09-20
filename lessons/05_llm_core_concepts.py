"""
Lesson 05 — LLM 核心概念（面试高频）
跑：python lessons/05_llm_core_concepts.py

涵盖：
- top_k（检索 vs 采样）、top_p、temperature
- embedding + vector store（与 RAG 的关系）
- role / zero-shot / few-shot / constraints
- structured output（Pydantic）
- fine-tuning vs RAG（何时用哪个）
- prompt caching（工程概念）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.prompts.cs_prompts import (
    CACHED_STATIC_PREFIX,
    CS_SYSTEM_ROLE,
    build_router_prompt,
)
from app.rag.store import LocalVectorStore
from app.schemas.routing import RouteDecision


def demo_decoding_params() -> None:
    print("--- 1) top_k / top_p / temperature ---")
    print(
        """
  【两个 top_k 别混】
  · RAG 检索 top_k：从向量库取最相似的 k 段（见 app/rag/store.py search(k=3)）
  · 生成采样 top_k：每步只从概率最高的 k 个 token 里抽（OpenAI 等 API 参数）

  top_p（nucleus）：按概率从高到低累加，直到累计概率 ≥ p，只在这批 token 里采样。
  · 客服事实类回复：temperature=0~0.3，减少胡编
  · 创意文案：temperature 更高，或 top_p=0.9

  本项目 config：openai 侧见 app/llm.py（temperature=0）；RAG 侧 k 见 retrieve_faq(k=...)
"""
    )


def demo_embedding_vector_store() -> None:
    print("--- 2) vector_store + embedding ---")
    store = LocalVectorStore()
    print(f"  chunks 数量: {len(store.chunks)}")
    if store.chunks:
        hits = store.search("退款多久到账", k=2)
        for h in hits:
            print(f"  score={h['score']:.3f} | {h['text'][:60]}...")
    print(
        "  流程：文本 → embedding 向量 → 存 vector store → 问句向量与库内做点积/余弦 → top_k 段落\n"
    )


def demo_prompting() -> None:
    print("--- 3) role / zero-shot / few-shot / constraints ---")
    print("  [Role 片段]", CS_SYSTEM_ROLE[:80], "...")
    print("  [Zero-shot 路由]", build_router_prompt("发票怎么开", few_shot=False)[:120], "...")
    print("  [Few-shot 路由]", build_router_prompt("ORD-1001 物流", few_shot=True)[:120], "...")
    print("  [Caching 静态前缀长度]", len(CACHED_STATIC_PREFIX), "chars（多轮可缓存）\n")


def demo_structured_output() -> None:
    print("--- 4) structured output + constraints ---")
    # 模拟 LLM 应返回的 JSON（真实环境用 with_structured_output(RouteDecision)）
    raw = {
        "next_agent": "order",
        "order_id": "ORD-1001",
        "confidence": 0.92,
        "rationale": "用户询问物流，含订单号",
    }
    decision = RouteDecision.model_validate(raw)
    print("  Pydantic 校验通过:", decision.model_dump())
    print(
        "  面试句：Router 用 structured output 替代正则，便于监控 confidence 与 rationale。\n"
    )


def demo_finetuning_vs_rag() -> None:
    print("--- 5) fine-tuning vs RAG ---")
    print(
        """
  Fine-tuning：改模型权重，适合固定语气、分类、格式、领域术语。
  RAG：不改权重，外挂知识库，适合 FAQ/政策频繁变更。

  客服项目典型分工：
  · 政策/退货说明 → RAG（本项目 data/faq.md + vector store）
  · 订单状态 → 绝不 fine-tune「记住订单」，必须 DB + Tool
  · 可选 fine-tune：路由小模型、礼貌话术风格（在 RAG+Tool 架构之上）
"""
    )


def main() -> None:
    print("=== Lesson 05: LLM core concepts ===\n")
    demo_decoding_params()
    demo_embedding_vector_store()
    demo_prompting()
    demo_structured_output()
    demo_finetuning_vs_rag()
    print("面试 30 秒：检索用 top_k 段；生成用 temperature/top_p 控随机性；")
    print("事实靠 Tool+DB；知识靠 RAG；路由靠 structured output + few-shot。")


if __name__ == "__main__":
    main()
