# Deploy SteelShop Care (free demo for your resume)

Goal: a public HTTPS URL interviewers can open, e.g. `https://steelshop-care.onrender.com`.

## Recommended free platform: Render

Free web service · Docker · HTTPS · sleeps after ~15 min idle (first open may take 30–60s).

### A. Push this repo to GitHub

```bash
cd /Users/jiafoo/cs-smart-bot
git add -A
git commit -m "Add enterprise CS bot demo ready for free-tier deploy"

# Create empty repo on GitHub, then:
git remote add origin https://github.com/<YOUR_USERNAME>/cs-smart-bot.git
git branch -M main
git push -u origin main
```

### B. Deploy on Render (≈5 minutes)

1. Sign up at [https://render.com](https://render.com) with GitHub.
2. **New → Blueprint** (or **Web Service** → connect this repo).
3. If Blueprint: select the repo — it reads `render.yaml`.
4. If manual Web Service:
   - Runtime: **Docker**
   - Dockerfile path: `./Dockerfile`
   - Instance: **Free**
   - Health check: `/health`
5. Env (already in `render.yaml`):
   - `USE_MOCK_LLM=true`
   - `EMBEDDING_BACKEND=hash`
   - `VECTOR_STORE=simple`
6. Deploy → copy the URL, e.g. `https://steelshop-care.onrender.com`.

### C. Resume / portfolio line

```text
SteelShop Care — Multi-agent customer support demo (LangGraph + RAG + MCP tools)
Live: https://<your-render-url>  |  Code: https://github.com/<you>/cs-smart-bot
```

One-sentence pitch:

> Built a deployable multi-agent CS console: Supervisor routes to policy RAG, order/payment tools, refunds, invoices, tracking, loyalty, and human handoff; FastAPI + Docker on Render.

## Tips for interviewers

- Add a note: *“Free tier cold-starts in ~30–60s after idle.”*
- Pin a short demo script in the README (return policy → ORD-1001 tracking → escalate → resume bot).
- Optional later: set `OPENAI_API_KEY` + `USE_MOCK_LLM=false` on Render for real LLM replies (still free host; API usage billed by OpenAI).

## Alternatives

| Platform | Notes |
|----------|--------|
| **Railway** | Easy Docker; limited free credits |
| **Fly.io** | `fly launch` + Dockerfile; free allowance |
| **Hugging Face Spaces** | Good for AI demos; Docker Space |

## Local production image test

```bash
docker build -t steelshop-care .
docker run --rm -p 8000:8000 -e PORT=8000 steelshop-care
open http://127.0.0.1:8000/
```
