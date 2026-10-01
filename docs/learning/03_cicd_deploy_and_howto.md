# Learning path 03 — CI/CD, Render deploy, and how this rewrite was done

> Goal: ship safely and understand the **exact sequence** used to rewrite the project.

## A. How this version was built (step-by-step log)

Follow this order when you rebuild from scratch:

1. **Write `docs/MVP.md`** — capabilities, SG domain, stack, phases, change control.
2. **Replace policy corpus** — SG inbound/outbound/carrier/claims/GST markdown + FAQ.
3. **Add agent helpers** — `app/agents/clarify.py`, `consistency.py`, `react_agent.py`.
4. **Extend data model** — `InventoryLot`, `UploadedDocument`; reseed shippers + `SHP-xxxx`.
5. **Upload pipeline** — `app/rag/uploads.py` + `POST /api/uploads`.
6. **Wire LangGraph** — inventory + react nodes; clarify in `_chat_inner`; verify on FAQ/shipment.
7. **Rebrand UI** — SteelHub Logistics Care, SG chips, upload panel.
8. **CI** — `.github/workflows/ci.yml` (bootstrap + `test.py`).
9. **Learning docs** — this folder.
10. **Docker / render.yaml** — keep live URL `cs-smart-bot.onrender.com`; `VECTOR_STORE=simple` on free tier.
11. **`git push origin main`** — Render auto-redeploys.

## B. CI/CD (MVP C10)

GitHub Actions (`.github/workflows/ci.yml`):

- Trigger: push / PR to `main`
- Install `requirements-prod.txt`
- `python -m app.bootstrap`
- `python test.py`

Local same path:

```bash
export EMBEDDING_BACKEND=hash VECTOR_STORE=simple USE_MOCK_LLM=true
python -m app.bootstrap && python test.py
```

## C. Deploy to existing Render app

Live demo stays: **https://cs-smart-bot.onrender.com**

1. Commit and push `main` to `https://github.com/jiafoo888/cs-smart-bot`.
2. Render service connected to that repo rebuilds the Docker image (`Dockerfile`).
3. Health check: `GET /health` → `service: SteelHub Logistics Care`.
4. Cold start on free tier: wait 30–60s after idle.

Env (also in `render.yaml`):

```text
USE_MOCK_LLM=true
EMBEDDING_BACKEND=hash
VECTOR_STORE=simple
COMPANY_NAME=SteelHub Logistics
```

Optional later: set `VECTOR_STORE=chroma` only if the image installs `chromadb` (full `requirements.txt`) and the plan has enough memory.

## D. Interview talking points

- **Supervisor multi-agent** with LangGraph  
- **RAG** section-aware chunks + grounded answers (scores in debug only)  
- **Clarify + consistency** before/after answers  
- **ReAct** multi-tool trace in debug  
- **Upload ingest** for customer SOPs  
- **Singapore logistics** domain + SGD / SHP / carriers  

## E. Self-check exercises

1. Add a new policy file and re-ingest without restarting code — which button/API?
2. Force clarify for “inventory” without SKU — which function?
3. Change Render company name — which two files must stay aligned with MVP?

Back: [01 MVP](./01_mvp_first.md) · [02 Agent stack](./02_build_agent_stack.md)
