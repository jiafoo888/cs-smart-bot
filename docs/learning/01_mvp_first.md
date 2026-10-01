# Learning path 01 — From idea to MVP doc

> Goal: understand **why** we wrote `docs/MVP.md` before coding, and how to use it as the source of truth.

## Step 1 — Name the buyer and the region

We pivoted from a generic e‑commerce CS bot to a **Singapore logistics / warehouse 3PL** desk because:

- Interviewers in SG recognise Ninja Van, SingPost, GrabExpress, Jurong / Tuas, GST language.
- Warehouse ops ask about **ASN inbound SLA**, **outbound cut-off**, **SHP tracking**, **inventory bins**, **claims** — not earbuds.

Write that down as personas and demo scripts **before** touching LangGraph.

## Step 2 — Write the MVP file first

Open [`docs/MVP.md`](../MVP.md). It locks:

| Section | Why it matters |
|---------|----------------|
| Capabilities C1–C10 | Acceptance checklist (clarify, verify, upload, CI…) |
| Stack table | Chroma / LangChain / LangGraph / ReAct — no random frameworks |
| Change control | Update MVP → then code |
| Phases P0–P6 | Build order |

**Rule for you when coding:** if a feature is not in MVP, either add it to MVP first or do not build it.

## Step 3 — Map MVP → folders

```text
docs/MVP.md                 ← contract
app/graph/supervisor.py     ← LangGraph multi-agent
app/agents/                 ← clarify + consistency + ReAct
app/rag/                    ← ingest + Chroma/simple + uploads
data/policies/              ← SG corpus
.github/workflows/ci.yml    ← C10
```

## Step 4 — Self-check

1. Can you explain C4 (clarify) and C5 (consistency) in one sentence each?
2. Which demo script proves upload ingest (C6)?
3. Why does free-tier Render keep `VECTOR_STORE=simple` while local can use `chroma`?

Next: [02 — Build the agent stack](./02_build_agent_stack.md)
