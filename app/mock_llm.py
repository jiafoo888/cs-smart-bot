"""无 API Key 时的规则型 LLM：按关键词路由意图，方便本地演示整条链路。"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class MockChatModel(BaseChatModel):
    """面试演示用：不调用外部 API，但走同一套 Agent/Tool 代码路径。"""

    model_name: str = Field(default="mock-cs-bot")

    @property
    def _llm_type(self) -> str:
        return "mock-cs-bot"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = self._last_human(messages)
        reply = self._reply(text)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _last_human(self, messages: list[BaseMessage]) -> str:
        for m in reversed(messages):
            if isinstance(m, HumanMessage):
                return str(m.content)
            if getattr(m, "type", None) == "human":
                return str(m.content)
        return str(messages[-1].content) if messages else ""

    def _reply(self, text: str) -> str:
        t = text.lower()
        # Supervisor / router 场景：返回目标 agent 名
        if "route:" in t or "选择下一个" in text or "choose next" in t:
            if any(k in t for k in ("订单", "order", "物流", "快递", "ord-")):
                return "order"
            if any(k in t for k in ("退款", "refund", "退货")):
                return "refund"
            if any(k in t for k in ("人工", "投诉", "escalate", "经理")):
                return "escalate"
            return "faq"

        if any(k in t for k in ("退款", "refund")):
            return "好的，我可以帮您处理退款。请提供订单号（例如 ORD-1002）。"
        if any(k in t for k in ("订单", "order", "ord-")):
            return "请提供订单号，我帮您查询状态与物流。"
        if any(k in t for k in ("人工", "投诉")):
            return "已为您记录转人工请求，客服会尽快联系您。"
        return (
            "根据知识库：7 天无理由退货；已发货订单可在订单页申请；"
            "运费规则以 FAQ 为准。还有什么可以帮您？"
        )
