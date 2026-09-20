from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    use_mock_llm: bool = True
    use_mcp_stdio: bool = False
    database_url: str = f"sqlite+aiosqlite:///{DATA_DIR / 'cs_bot.db'}"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_backend: str = "hash"  # hash | st | auto
    # simple = numpy file store (free PaaS); chroma = LangChain Chroma
    vector_store: str = "simple"

    # RAG knobs (enterprise-tunable)
    rag_chunk_size: int = 450
    rag_chunk_overlap: int = 90
    rag_top_k: int = 4
    rag_min_score: float = 0.12

    host: str = "0.0.0.0"
    port: int = 8000
    company_name: str = "SteelShop"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "cs-smart-bot"
    deepeval_api_key: str = ""

    @property
    def faq_path(self) -> Path:
        return DATA_DIR / "faq.md"

    @property
    def policies_dir(self) -> Path:
        return DATA_DIR / "policies"

    @property
    def vector_dir(self) -> Path:
        return DATA_DIR / "vector_store"

    @property
    def static_dir(self) -> Path:
        return ROOT / "static"


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()
