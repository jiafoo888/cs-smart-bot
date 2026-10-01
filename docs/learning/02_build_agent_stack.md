# Learning path 02 — Build the agent stack

> Goal: reproduce the core AI path: RAG → supervisor → tools → clarify → verify → ReAct.

## Step 1 — RAG corpus (LangChain + store)

1. Put Singapore policies under `data/policies/` (inbound SLA, carriers, claims, GST notes…).
2. `app/rag/ingest.py` loads markdown, splits by `##` headings, chunks with `RecursiveCharacterTextSplitter`.
3. `app/rag/store.py` writes either:
   - `VECTOR_STORE=simple` → numpy cosine store (Render-friendly)
   - `VECTOR_STORE=chroma` → LangChain Chroma collection `steelhub_logistics`

Bootstrap:

```bash
export EMBEDDING_BACKEND=hash
python -m app.bootstrap
```

## Step 2 — LangGraph supervisor

Read `app/graph/supervisor.py`:

1. `route_intent` picks an agent (`faq`, `order`, `inventory`, `react`, `escalate`…).
2. Each agent returns an `AIMessage` + `debug` (scores stay out of user text).
3. Graph: `START → supervisor → agent → END` with `MemorySaver` per `session_id`.

## Step 3 — Tools (MCP bridge)

Shipment / payment tools live in `app/mcp_tools.py` and are callable via:

- In-process `call_mcp_tool(...)` from agents
- Optional stdio MCP server: `python -m app.mcp_server`

IDs: prefer **`SHP-xxxx`** (ORD- still accepted for aliases).

## Step 4 — Clarify loop (ReAct-adjacent, slot filling)

`app/agents/clarify.py`:

- Ambiguous “where is my parcel?” → ask for `SHP-xxxx` (max 2 turns).
- Wired in `_chat_inner` **before** the graph runs.

Try in UI: chip **Ambiguous track**.

## Step 5 — Consistency verifier

`app/agents/consistency.py` scans the draft for IDs/amounts not present in RAG/tool evidence and soft-rewrites + asks for confirmation.

Policy path: retrieve → compose → **verify** → reply (`faq_agent` debug shows `consistency_ok`).

## Step 6 — ReAct agent

`app/agents/react_agent.py` runs Thought → Action → Observation with a deterministic planner (works offline without an LLM). Enable via chip **ReAct multi-tool** or phrases like “use tools to…”.

## Step 7 — Document upload ingest

1. UI Ops → choose PDF/MD/TXT → Upload.
2. `POST /api/uploads` → `app/rag/uploads.py` extracts text (`pypdf` for PDF) → chunks → rebuilds vector store with policies + uploads.
3. Ask a question only that SOP answers.

## Step 8 — Local run

```bash
source .venv/bin/activate
pip install -r requirements.txt
python -m app.bootstrap
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/

Next: [03 — CI/CD, deploy, and how this was written](./03_cicd_deploy_and_howto.md)
