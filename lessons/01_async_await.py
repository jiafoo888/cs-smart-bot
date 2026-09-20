"""
Lesson 01 — async / await
跑：python lessons/01_async_await.py

面试要点：
- async def 定义协程；await 等待可等待对象
- 适合 I/O（网络、DB、LLM），不适合重 CPU（除非丢线程池）
- asyncio.gather 并行多个 I/O
"""

from __future__ import annotations

import asyncio
import time


async def fake_llm_call(prompt: str, delay: float = 0.4) -> str:
    """模拟调 LLM：网络等待。"""
    await asyncio.sleep(delay)  # 把控制权交回事件循环
    return f"LLM回复({prompt[:12]}...)"


async def fake_db_lookup(order_id: str, delay: float = 0.3) -> dict:
    """模拟查订单库。"""
    await asyncio.sleep(delay)
    return {"order_id": order_id, "status": "shipped"}


async def sequential() -> float:
    t0 = time.perf_counter()
    await fake_llm_call("政策问题")
    await fake_db_lookup("ORD-1001")
    return time.perf_counter() - t0


async def parallel() -> float:
    t0 = time.perf_counter()
    # 两个 I/O 同时飞 —— 客服场景常见：一边检索 FAQ，一边预取订单
    await asyncio.gather(
        fake_llm_call("政策问题"),
        fake_db_lookup("ORD-1001"),
    )
    return time.perf_counter() - t0


async def main() -> None:
    print("=== Lesson 01: async / await ===\n")
    seq = await sequential()
    par = await parallel()
    print(f"串行耗时 ≈ {seq:.2f}s")
    print(f"并行耗时 ≈ {par:.2f}s  ← gather 重叠等待")
    print("\n在 FastAPI 里你会写：")
    print("  async def chat(...):")
    print("      result = await graph.ainvoke(...)")
    print("\n记住：在 async 函数里不要用 time.sleep（会堵事件循环），用 await asyncio.sleep。")


if __name__ == "__main__":
    asyncio.run(main())
