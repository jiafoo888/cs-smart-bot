from app.config import get_settings

settings = get_settings()

# 无 key 或显式 mock 时，走规则 LLM，保证本地可演示架构
USE_MOCK = settings.use_mock_llm or not settings.openai_api_key


def get_chat_model():
    """返回 ChatModel；mock 时返回轻量包装，接口尽量贴近 invoke/ainvoke。"""
    if USE_MOCK:
        from app.mock_llm import MockChatModel

        return MockChatModel()

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
