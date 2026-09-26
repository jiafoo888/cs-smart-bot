# SteelShop Care — Enterprise Customer Service Agent

Deployable multi-agent CS platform for answering shoppers with **grounded policy RAG**, **order/payment tools**, and a **LangGraph supervisor**.

## What enterprises get

| Layer | Capability |
|-------|------------|
| Conversation UI | Full ops console (inbox, chat, KB, 360, agent assist) |
| LangGraph | Supervisor → greeting / policy / order / payment / refund / human |
| Trust | Phone/email verify, PII redaction, refund confirm, ¥300 auto-limit |
| RAG | LangChain + Chroma, section-aware chunking, tunable `chunk_size` / `overlap` / `top_k` |
| Systems of record | SQLite customers (VIP tiers) · orders · payments · SLA tickets · chat audit |
| MCP | Same tools exposed via `python -m app.mcp_server` |
| Ship | FastAPI + Docker Compose |

## Deploy (resume / interview demo)

Free public URL via **Render** (Docker + HTTPS):

1. Push this repo to GitHub  
2. Follow **[DEPLOY.md](./DEPLOY.md)** (Blueprint uses `render.yaml`)  
3. Put the live link on your resume:

```text
SteelShop Care — multi-agent CS demo (LangGraph + RAG + tools)
Live: https://cs-smart-bot.onrender.com
```

Local production image:

```bash
docker build -t steelshop-care .
docker run --rm -p 8000:8000 -e PORT=8000 steelshop-care
```

## Run locally

```bash
cd /Users/jiafoo/cs-smart-bot
source .venv/bin/activate
pip install -r requirements.txt

export EMBEDDING_BACKEND=hash
python -m app.bootstrap          # DB seed + Chroma ingest
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://127.0.0.1:8000/** — SteelShop Care console.

## Docker (production-shaped)

```bash
docker compose up --build
# http://localhost:8000/
```

## RAG knobs (`.env`)

```
RAG_CHUNK_SIZE=450
RAG_CHUNK_OVERLAP=90
RAG_TOP_K=4
RAG_MIN_SCORE=0.12
EMBEDDING_BACKEND=hash   # or st / auto with sentence-transformers
```

Re-ingest after changing policies: `POST /api/admin/reingest` or UI **Ops → Re-ingest policies**.

## Eval

```bash
python test.py
# Optional: LANGCHAIN_API_KEY + OPENAI_API_KEY for LangSmith / DeepEval
```

## Demo scripts

- `What is the return policy window?` → grounded policy answer + source chips  
- `Check order ORD-1001` → order facts, address hidden until verify  
- `verify 1001` → unlocks PII (demo last-4 = order suffix for 1001–1004)  
- `Please refund ORD-1002` → verify + YES; ¥459 is over auto-limit → SLA ticket  
- `hello` / off-topic → greeting, not stuck on prior order  

Learning notes: [LEARNING.md](./LEARNING.md)
