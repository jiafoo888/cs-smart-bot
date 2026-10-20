# SteelHub Logistics Care — MVP Specification (Source of Truth)

> **权威文档**：本文件是本仓库唯一产品与技术 MVP 规格。  
> **规则**：任何 plan、代码修改、UI、部署、CI 变更都必须对齐本文件；冲突时以本文件为准并先更新本文件再改代码。  
> **版本**：MVP-1.4 · Singapore logistics / warehouse CS agent  
> **Live demo**：`https://cs-smart-bot.onrender.com`（Render 服务名保持既有部署）  
> **产品优先级锁定**（2026-10-10 / collab `f1481266`）：生产默认 OpenAI；RAG 优先政策问答准确；上传 PDF/文档保留；部署继续 Render 单容器。  
> **Changelog 1.2**（collab `0892b97b`）：C4 clarify 意图解绑；控制台明亮化；collab 强制记录；DEPLOY SteelHub。  
> **Changelog 1.3**（collab `ce23755f`）：退款禁止对话内打款（仅状态查询 / 人工 ticket）；左侧 Hubbit 动态小兔子客服。  
> **Changelog 1.4**（collab `e47fa285`）：控制台视觉对齐 portfolio HUD（jiafoo-cho.netlify.app）— 深色网格、石灰绿、开机序列、自定义光标。

---

## 1. Product vision

### 1.1 Who it is for
新加坡 **3PL / warehouse / manufacturer logistics desk** 的内部与外部客服场景：

| Persona | Needs |
|---------|--------|
| Shipper / brand ops | ASN、入库、库存、出库 SLA、异常赔付政策 |
| Warehouse CS agent | 用 bot 查单、查政策、起草回复、升级人工 |
| Interviewer / hiring manager | 看到可运行的 LangGraph + RAG + tools + upload ingest |

### 1.2 Brand (demo)
- **Product name**：SteelHub Logistics Care  
- **Region**：Singapore (SGT, GST-aware copy, local carriers: Ninja Van, SingPost, GrabExpress mock)  
- **Currency / units**：SGD · kg · cm · postal codes (e.g. `640903`)

### 1.3 Out of scope (MVP)
- Real carrier APIs / live customs filing  
- Multi-tenant auth / SSO  
- Persistent paid vector DB in cloud (Chroma on local disk / container volume is enough)  
- Full bilingual UI (English primary; SG English tone)

---

## 2. User-facing capabilities (MVP must-have)

| # | Capability | Acceptance |
|---|------------|------------|
| C1 | Multi-agent chat console | Supervisor routes to specialized agents |
| C2 | Policy RAG (Chroma) | Answers cite KB sources; no score dumps in user text |
| C3 | ReAct-style tool use | Order/shipment/inventory tools via MCP or in-process tools |
| C4 | Clarification loop | Ambiguous asks → bot asks follow-ups until slots filled OR user confirms |
| C5 | Consistency check | Before final sensitive answer, a verifier step checks reply vs retrieved context / tool facts |
| C6 | Document upload ingest | User uploads `.pdf` / `.md` / `.txt` → chunk → embed → Chroma → searchable |
| C7 | Shipment / warehouse demo data | Seeded SG shipments, WMS locations, exceptions |
| C8 | Human handoff + SLA tickets | Pause bot, ticket with priority/SLA |
| C9 | Server OpenAI (default) + optional BYOK | Production: `USE_MOCK_LLM=false` + server `OPENAI_API_KEY`. BYOK still allowed per-request override; never stored in DB. CI/local tests may keep mock. |
| C10 | CI/CD | GitHub Actions: lint/tests on PR/push; Render auto-deploy from `main` |
| C11 | Refunds are staff-only | Chat may **query** refund/payment status (pending / succeeded / refunded). Chat must **not** execute payouts. Initiate refund → `refund_approval` ticket + pause bot for human. |
| C12 | Desk mascot (Hubbit) | Left rail animated bunny buddy; livens console without looking like generic AI chrome. |
| C13 | HUD console visual | Same motion language as [jiafoo-cho.netlify.app](https://jiafoo-cho.netlify.app): dark ops HUD, lime `#e8ff3d`, Syne/Outfit/IBM Plex Mono, boot sequence, grid/scan/beam, custom cursor. `prefers-reduced-motion` skips boot. |

### 2.1 Locked product priorities (PM + BE)

| Decision | Choice | Backend implication |
|----------|--------|---------------------|
| LLM | **Production default = OpenAI** | Render env: `USE_MOCK_LLM=false` + secret `OPENAI_API_KEY`. No key → `/health` reports degraded; chat returns clear config error (no silent mock in prod). CI/dev may still use mock. |
| RAG focus | **Policy Q&A accuracy first**; upload PDF/MD/TXT remains required | Split chunk knobs: policy vs upload. Tune policy chunk/overlap/top_k/min_score first; upload keeps usable defaults. |
| Deploy | **Render single Docker container** (primary) | Keep `Dockerfile` + `render.yaml`; local `docker compose` is secondary for smoke tests. Free-tier may keep `VECTOR_STORE=simple` / `EMBEDDING_BACKEND=hash` unless memory allows chroma/st. |

---

## 3. Singapore logistics domain model

### 3.1 Core entities (SQLite)
- `Customer` — shipper accounts (SG company / contact)  
- `Shipment` — AWB / SHP-xxxx, origin/destination postal, status, carrier  
- `InventoryLot` — SKU, qty, zone/bin, expiry (optional)  
- `Asn` — inbound ASN-xxxx  
- `Ticket` / `ChatLog` / `SessionHandoff` / `PendingAction` — keep enterprise CS patterns  
- `UploadedDocument` — filename, mime, bytes, ingest status, chunk count  

### 3.2 Demo scripts (must work after seed)
1. “What is your inbound SLA in Singapore?” → policy RAG  
2. “Track SHP-2001” → shipment tool  
3. “Compare Ninja Van vs SingPost for last-mile” → policy/catalog RAG  
4. Upload a PDF SOP → re-ingest → ask a question that only that SOP answers  
5. Ambiguous “where is my parcel?” → clarify (need SHP id or phone/postal) → then answer  
6. Escalate → ticket + pause  
7. “Is the refund for SHP-2002 pending or done?” → status only (no payout)  
8. “Please refund SHP-2002” → staff review ticket + pause (no YES→refund)  

### 3.3 Seed policy corpus (`data/policies/`)
Must include SG-flavoured docs, e.g.:
- inbound receiving SLA  
- outbound cut-off (Jurong / Tuas mock DC)  
- GST / invoice notes (high-level, not tax advice)  
- damaged freight claims window  
- peak period (e.g. 11.11 / CNY) handling  
- carrier matrix (Ninja Van, SingPost, GrabExpress)

---

## 4. AI architecture (market-aligned)

```text
Browser console
    │  POST /chat  (+ optional BYOK key)
    ▼
FastAPI
    │
    ├─ Clarifier (slots / ambiguity)
    ├─ LangGraph Supervisor
    │     ├─ policy_rag_agent   (retrieve → ground → optional LLM)
    │     ├─ shipment_agent     (tools)
    │     ├─ inventory_agent    (tools)
    │     ├─ react_tool_agent   (Thought→Action→Observation loop for multi-tool)
    │     ├─ escalate_agent
    │     └─ smalltalk_agent
    ├─ ConsistencyVerifier      (answer ↔ context/tool facts)
    ▼
Chroma (VECTOR_STORE=chroma) + SQLite SoR + uploads/
```

### 4.1 Required stack (do not regress)
| Layer | Choice |
|-------|--------|
| Orchestration | **LangGraph** supervisor + agents |
| RAG | **LangChain** loaders/splitters + **Chroma** |
| Embeddings | `hash` on free Render; `st` / OpenAI embeddings when configured |
| Tools | MCP map + in-process bridge (same schemas) |
| Reasoning pattern | **ReAct** in `react_tool_agent` (explicit Thought/Action/Observation in debug) |
| Clarification | Slot-filling state on session until required fields present |
| Consistency | Verifier node: if mismatch → ask user to confirm or re-retrieve |

### 4.2 Clarification rules
Ambiguous intents that **must** clarify before tools:
- “where is my parcel/shipment” without SHP-/AWB id  
- inventory ask without SKU  
- claim/damage without shipment id + brief description  

Max **2** clarifying turns, then best-effort or escalate.

**Intent abandon (sticky-session fix):** if a clarify loop is open and the next user message is a **clear pivot** (policy / carrier compare / escalate / payment / refund / complete tool ask), **clear** the pending clarify state and route normally. Do **not** keep asking for SHP id. Genuine slot fills (e.g. reply `SHP-2001`) still complete the loop.

### 4.3 Consistency verifier
After policy or tool-backed reply draft:
1. Collect evidence: top RAG chunks and/or tool JSON  
2. Check: draft does not invent IDs/amounts/dates absent from evidence  
3. If fail → rewrite with grounded composer OR ask user one confirmation question  

---

## 5. Document upload & ingest

### 5.1 API
- `POST /api/uploads` — multipart file (pdf|md|txt), max 5MB MVP  
- `GET /api/uploads` — list  
- `POST /api/admin/reingest` — rebuild Chroma from policies + uploads  
- Store files under `data/uploads/` (gitignored content; metadata in DB)

### 5.2 Pipeline
1. Save raw file  
2. Extract text (pdf via `pypdf`; md/txt utf-8)  
3. Section-aware / recursive chunk (**upload** knobs, separate from policy)  
4. Upsert into vector store with metadata `{source, category: "upload", filename}`  
5. Return chunk count  

### 5.3 Chunk strategy (policy vs upload)
| Corpus | Default knobs (tunable via env) | Rationale |
|--------|----------------------------------|-----------|
| Policy (`data/policies/`, faq) | Prefer slightly larger chunks that keep H2 sections intact; higher priority in retrieval boost when `category != upload` | User-facing policy answers must be accurate and citeable |
| Upload (PDF/MD/TXT) | Slightly smaller chunks / modest overlap | Long SOPs; recall over perfect phrasing |

Shared: section-aware split before recursive splitter; embeddings backend unchanged by corpus type.

### 5.4 UI
Ops tab: upload control + list + Re-ingest button.

---

## 6. API surface (MVP)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Console |
| GET | `/health` | Ready + chroma + catalog counts |
| POST | `/chat` | Main dialogue |
| GET/POST | `/api/uploads` | List / upload |
| POST | `/api/admin/reingest` | Full ingest |
| GET | `/api/shipments` | Demo list |
| GET | `/api/tickets` | Tickets |
| GET | `/api/sessions/{id}/logs` | Audit |

---

## 7. Non-functional

| Area | MVP bar |
|------|---------|
| Deploy | Docker on Render free (primary); health `/health`; local compose secondary |
| Config | `VECTOR_STORE=chroma` preferred locally; Render free may use `simple` if chroma OOM |
| Secrets | Production **requires** server `OPENAI_API_KEY`; BYOK optional override in request body only |
| Tests | `test.py` functional routes + RAG smoke + upload ingest smoke (mock LLM in CI) |
| CI | `.github/workflows/ci.yml` — install, bootstrap, `test.py` |

---

## 8. Repo layout (target)

```text
docs/MVP.md                 ← this file (source of truth)
docs/learning/01_...md      ← learning path
docs/learning/02_...md
docs/learning/03_...md
app/graph/supervisor.py     ← LangGraph
app/rag/                    ← Chroma + ingest + upload
app/agents/                 ← clarify + verify + react helpers
data/policies/              ← SG logistics corpus
data/uploads/               ← user uploads (ignored)
.github/workflows/ci.yml
render.yaml
```

---

## 9. Implementation phases (execute in order)

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| P0 | This MVP.md committed | File exists and README points to it |
| P1 | SG policies + shipment seed + UI copy rebrand | Demo scripts 1–3 pass |
| P2 | Clarifier + consistency verifier in graph | Ambiguous track asks for SHP id |
| P3 | Upload ingest PDF/MD/TXT | Upload → ask → grounded hit |
| P4 | ReAct agent path + Chroma default in config/Docker | `/health` shows chroma when available |
| P5 | CI workflow + learning docs | CI green; tutorials readable |
| P6 | Push `main` → Render redeploy | Live URL serves new console |
| P7 | Prod OpenAI default + policy/upload chunk split | Render uses real LLM with key; policy answers measurably better on demo scripts 1/3; upload still works |

---

## 10. Change control

1. Update **this MVP** section that changes.  
2. Implement code to match.  
3. Update `test.py` / learning docs if behaviour changes.  
4. Commit message should reference MVP capability ids (e.g. `C4 clarifier`).  

---

## 11. Glossary

| Term | Meaning |
|------|---------|
| Supervisor | LangGraph router node selecting next agent |
| ReAct | Interleaved reasoning and tool calls |
| Clarifier | Asks until required slots filled |
| Verifier | Checks draft vs evidence before user sees final text |
| BYOK | Bring Your Own Key — per-request OpenAI key |

---

*End of MVP-1.0*
