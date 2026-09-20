"""Structured output：用 Pydantic 约束 LLM 路由结果（替代纯文本解析）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RouteTarget = Literal["faq", "order", "refund", "escalate"]


class RouteDecision(BaseModel):
    """Supervisor/Router 的结构化输出 schema。"""

    next_agent: RouteTarget = Field(description="下一个子 Agent")
    order_id: str | None = Field(default=None, description="从用户话术中提取的 ORD-xxxx")
    confidence: float = Field(ge=0, le=1, description="路由置信度")
    rationale: str = Field(max_length=200, description="一句话理由，便于审计")


class CustomerReply(BaseModel):
    """可选：约束最终回复格式（JSON mode / tool schema）。"""

    reply: str = Field(max_length=500)
    cited_policy: bool = False
    used_database: bool = False
    escalate: bool = False
