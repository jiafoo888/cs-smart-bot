# SteelHub Logistics Care — Singapore 3PL / warehouse CS agent

Deployable multi-agent logistics desk: **LangGraph** supervisor, **LangChain RAG** (Chroma or simple), **ReAct**, **clarify + consistency**, **PDF/MD/TXT upload ingest**, FastAPI console.

**Source of truth:** [`docs/MVP.md`](./docs/MVP.md) — every code change must follow it.  
**Learn how it was built:** [`docs/learning/`](./docs/learning/)

## Live demo

```text
https://cs-smart-bot.onrender.com
```

(Free Render cold-start ~30–60s after idle.)

## Stack (MVP)

| Layer | Choice |
|-------|--------|
| Orchestration | LangGraph supervisor + agents |
| RAG | LangChain loaders/splitters + Chroma (local) / simple numpy (Render) |
| Reasoning | ReAct tool loop + clarify slots + consistency verifier |
| Tools | MCP map + in-process bridge |
| SoR | SQLite shippers · SHP shipments · inventory · tickets · uploads |
| Ship | Docker → Render · GitHub Actions CI |

## Run locally

```bash
cd /Users/jiafoo/cs-smart-bot
source .venv/bin/activate
pip install -r requirements.txt

export EMBEDDING_BACKEND=hash
# optional: export VECTOR_STORE=chroma
python -m app.bootstrap
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://127.0.0.1:8000/**

## Demo scripts

1. `What is your inbound SLA in Singapore?` → policy RAG  
2. `Track SHP-2001` → shipment tool  
3. `Where is my parcel?` → clarify for SHP id  
4. `Compare Ninja Van vs SingPost for last-mile` → carrier compare  
5. Ops → upload a PDF SOP → ask a question only that file answers  
6. `escalate` → ticket + pause bot  

## CI / deploy

- CI: `.github/workflows/ci.yml`  
- Deploy notes: [`DEPLOY.md`](./DEPLOY.md) · Blueprint: `render.yaml` (service `cs-smart-bot`)

```bash
python test.py
```
