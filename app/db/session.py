from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base

_settings = get_settings()

# sync：脚本 / tools 简单调用
_sync_url = _settings.database_url.replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(_sync_url, future=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)

# async：FastAPI 路径
async_engine = create_async_engine(_settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(sync_engine, "connect")
def _sqlite_fk(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _sqlite_add_columns() -> None:
    """Additive migrations for existing demo SQLite files."""
    if not str(sync_engine.url).startswith("sqlite"):
        return
    specs = {
        "customers": [("tier", "VARCHAR(16) DEFAULT 'standard'")],
        "tickets": [
            ("priority", "VARCHAR(16) DEFAULT 'normal'"),
            ("sla_minutes", "INTEGER DEFAULT 30"),
            ("sla_due_at", "DATETIME"),
            ("assigned_to", "VARCHAR(64)"),
        ],
    }
    with sync_engine.begin() as conn:
        for table, cols in specs.items():
            existing = {
                row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            }
            if not existing:
                continue
            for name, ddl in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def init_db(*, reset: bool = False) -> None:
    """创建表。reset=True 时先 drop（schema 升级 / 演示重置用）。"""
    if reset:
        Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)
    _sqlite_add_columns()


def get_sync_session() -> Generator[Session, None, None]:
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
