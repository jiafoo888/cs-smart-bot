# Production image for free PaaS (Render / Railway / Fly)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USE_MOCK_LLM=true \
    EMBEDDING_BACKEND=hash \
    VECTOR_STORE=simple \
    DATABASE_URL=sqlite+aiosqlite:///./data/cs_bot.db

COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

COPY app ./app
COPY data/policies ./data/policies
COPY data/faq.md ./data/faq.md
COPY data/catalog ./data/catalog
COPY static ./static
COPY README.md ./

# Pre-build SQLite seed + RAG vectors (hash) so cold start is faster
RUN python -m app.bootstrap

EXPOSE 8000

# Render/Railway inject $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
