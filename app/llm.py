"""LLM access: mock by default, optional per-request BYOK (Bring Your Own Key)."""

from __future__ import annotations

from contextvars import ContextVar

from app.config import get_settings

settings = get_settings()

# Per-request OpenAI key from the browser — never written to DB / chat_logs.
_request_api_key: ContextVar[str | None] = ContextVar("request_api_key", default=None)

# Legacy flag: server-wide mock when no BYOK key is present
USE_MOCK = settings.use_mock_llm or not settings.openai_api_key


def set_request_api_key(api_key: str | None):
    cleaned = (api_key or "").strip() or None
    return _request_api_key.set(cleaned)


def reset_request_api_key(token) -> None:
    _request_api_key.reset(token)


def get_request_api_key() -> str | None:
    return _request_api_key.get()


def llm_mode() -> str:
    """mock | byok | server — for UI / debug only (never echo the key)."""
    if get_request_api_key():
        return "byok"
    if settings.use_mock_llm or not settings.openai_api_key:
        return "mock"
    return "server"


def should_use_live_llm() -> bool:
    if get_request_api_key():
        return True
    if settings.use_mock_llm:
        return False
    return bool((settings.openai_api_key or "").strip())


def get_chat_model():
    """Return a chat model for this request. BYOK overrides server mock."""
    byok = get_request_api_key()
    if byok:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_model,
            api_key=byok,
            temperature=0,
        )

    if settings.use_mock_llm or not settings.openai_api_key:
        from app.mock_llm import MockChatModel

        return MockChatModel()

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
