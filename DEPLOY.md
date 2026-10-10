# Deploy SteelHub Logistics Care (Render)

Goal: a public HTTPS URL for demos / company trial, e.g. `https://cs-smart-bot.onrender.com`.

## Recommended free platform: Render

Free web service · Docker · HTTPS · sleeps after ~15 min idle (first open may take 30–60s).

### A. Push this repo to GitHub

```bash
cd /Users/jiafoo/cs-smart-bot
git add -A
git commit -m "Ship SteelHub Logistics Care for Render"

# Create empty repo on GitHub if needed, then:
git remote add origin https://github.com/<YOUR_USERNAME>/cs-smart-bot.git
git branch -M main
git push -u origin main
```

Every engineer iteration that should hit production **must** be pushed to `main` (Render auto-deploys) and recorded under `docs/collab/sessions/`.

### B. Deploy on Render (≈5 minutes)

1. Sign up at [https://render.com](https://render.com) with GitHub.
2. **New → Blueprint** (or **Web Service** → connect this repo).
3. If Blueprint: select the repo — it reads `render.yaml` (service name `cs-smart-bot`).
4. If manual Web Service:
   - Runtime: **Docker**
   - Dockerfile path: `./Dockerfile`
   - Instance: **Free**
   - Health check: `/health`
5. Env (already in `render.yaml` for free demo):
   - `USE_MOCK_LLM=true`
   - `EMBEDDING_BACKEND=hash`
   - `VECTOR_STORE=simple`
   - `COMPANY_NAME=SteelHub Logistics`
6. Deploy → open `https://cs-smart-bot.onrender.com`.

### C. Company trial — real OpenAI replies (P2)

Free demo stays on mock. For **real policy wording** on Render:

1. Render Dashboard → `cs-smart-bot` → **Environment**
2. Add secret `OPENAI_API_KEY` = `sk-…`
3. Set `USE_MOCK_LLM=false`
4. Save → wait for redeploy
5. Check `GET /health` → `mock_llm` should be `false`

Alternatively, Ops panel **BYOK**: paste a key in the browser tab only (never stored in DB).

CI must keep `USE_MOCK_LLM=true` so GitHub Actions never bills OpenAI.

### D. Resume / portfolio line

```text
SteelHub Logistics Care — Multi-agent Singapore 3PL desk (LangGraph + RAG + MCP tools)
Live: https://cs-smart-bot.onrender.com  |  Code: https://github.com/<you>/cs-smart-bot
```

One-sentence pitch:

> Built a deployable multi-agent logistics CS console: supervisor routes to policy RAG, shipment/inventory tools, clarify + handoff; FastAPI + Docker on Render.

## Tips for interviewers / ops

- Free tier cold-starts in ~30–60s after idle.
- Demo script: inbound SLA → Track SHP-2001 → ambiguous parcel (clarify) → pivot to carrier compare → escalate.
- After backend changes: `python test.py` locally → push `main` → re-check `/health` + 2–3 chats.

## Alternatives

| Platform | Notes |
|----------|--------|
| **Railway** | Easy Docker; limited free credits |
| **Fly.io** | `fly launch` + Dockerfile; free allowance |
| **Hugging Face Spaces** | Good for AI demos; Docker Space |

## Local production image test

```bash
docker build -t steelhub-care .
docker run --rm -p 8000:8000 -e PORT=8000 steelhub-care
open http://127.0.0.1:8000/
```
