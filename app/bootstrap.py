from app.config import get_settings
from app.db.seed import seed_all
from app.db.session import init_db
from app.rag.ingest import ingest_all_policies


def main() -> None:
    settings = get_settings()
    settings.vector_dir.mkdir(parents=True, exist_ok=True)
    settings.policies_dir.mkdir(parents=True, exist_ok=True)

    print("→ init database")
    init_db()
    print("→ seed customers / orders / payments")
    seed_all(force=True)
    print("→ ingest policies into vector store")
    info = ingest_all_policies()
    print(
        f"✓ bootstrap done. chunks={info['chunks']} files={info['files']} "
        f"backend={info['backend']}"
    )
    print(f"  DB: {settings.database_url}")
    print(f"  Policies: {settings.policies_dir}")
    print(f"  MCP server: python -m app.mcp_server")
    print(f"  Demo UI: http://127.0.0.1:{settings.port}/")


if __name__ == "__main__":
    main()
