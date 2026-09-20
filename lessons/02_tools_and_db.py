"""
Lesson 02 — Tools + Database 查订单
跑：先 python -m app.bootstrap
    再 python lessons/02_tools_and_db.py

面试要点：
- 订单事实必须以 DB 为准，不能靠模型「记住」
- Tool = 给 Agent 调用的函数（有 schema / docstring）
"""

from __future__ import annotations

import json

from app.bootstrap import main as bootstrap
from app.tools.order_tools import get_order_status, request_refund


def main() -> None:
    print("=== Lesson 02: Tools + DB ===\n")
    bootstrap()

    print("\n1) Tool schema（Agent 看到的描述）:")
    print("   name:", get_order_status.name)
    print("   desc:", get_order_status.description)

    print("\n2) 调用 get_order_status('ORD-1001'):")
    print(get_order_status.invoke({"order_id": "ORD-1001"}))

    print("\n3) 调用 request_refund('ORD-1002'):")
    print(request_refund.invoke({"order_id": "ORD-1002", "reason": "lesson_demo"}))

    print("\n4) 再次查 ORD-1002（应为 refunded）:")
    print(get_order_status.invoke({"order_id": "ORD-1002"}))

    print("\n面试句：Tool calling 把副作用从文本生成里拆出去，订单状态以数据库为准。")


if __name__ == "__main__":
    main()
