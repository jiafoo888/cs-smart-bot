# Collab Session — 产品优先级锁定（OpenAI / 政策 RAG / Render）

| 字段 | 值 |
|------|-----|
| **session-id** | `f1481266-0091-43b2-9b96-89d7e5b8601a` |
| **日期** | `2026-10-10` |
| **主题** | PM 确认：生产默认 OpenAI；政策问答优先调参；保留上传；继续 Render |
| **参与人** | PM / BE（本角色）；FE 知情（契约暂不变） |
| **状态** | open |

---

## 1. 本次更新了什么

- 锁定三条产品优先级（见下表）。
- 更新 `docs/MVP.md` → **MVP-1.1**（C9、§2.1、§5.3 chunk 分策略、§7 Secrets、Phase P7）。
- BE 确认 `OWNERSHIP.md` 边界（勾选 kickoff 遗留项）。

| 决策项 | 选择 |
|--------|------|
| LLM | 生产默认 OpenAI（非 mock 优先） |
| RAG | 政策问答更准；用户仍可上传 PDF/MD/TXT |
| 部署 | 继续 Render 单容器为主 |

## 2. 责任与边界

| 角色 | 负责范围（本 session） | 不负责 / 边界外 |
|------|------------------------|-----------------|
| BE | MVP 规格更新；后续 `app/config`、`llm`、RAG chunk 分策略、`render.yaml` / Dockerfile env；Render 密钥说明 | 不改 `static/` UX；不强制 FE 去掉 BYOK UI |
| FE | 知情；若 `/health` 增加 degraded 字段再开 session 消费 | 本轮不改 UI |
| PM | 优先级拍板与验收口径 | 实现细节 |

## 3. API / 契约变更（如有）

| Method | Path | 变更说明 | 由谁改 | 验收 |
|--------|------|----------|--------|------|
| GET | `/health` | **计划**：明确 `mock_llm` / 缺 key 时的 degraded 语义（非 breaking，字段已有则只文档化） | BE | health 可判断「能否真调 OpenAI」 |
| — | 其余 `/chat` `/api/uploads` | **本轮无 breaking** | — | upload + 政策问答 demo scripts 仍过 |

## 4. 文件 / 模块清单

| 路径 | 角色 | 说明 |
|------|------|------|
| `docs/MVP.md` | MVP/BE | 1.1 优先级与 chunk 分策略 |
| `docs/collab/OWNERSHIP.md` | FE+BE | 同步 session-id |
| `app/config.py` | BE | （待实现）policy/upload chunk 分 knobs；prod mock 默认策略 |
| `app/rag/ingest.py` / `uploads.py` | BE | （待实现）分策略 chunk |
| `render.yaml` / `Dockerfile` | BE | （待实现）`USE_MOCK_LLM=false` + 文档要求 secret |
| `static/*` | FE | 本轮不动 |

## 5. 联调约定与验收

- [x] MVP-1.1 写入三条锁定优先级
- [x] BE 确认 OWNERSHIP 边界
- [ ] BE 实现 P7：Render 默认 OpenAI + 政策/上传 chunk 分离
- [ ] 验收：demo「inbound SLA」等政策问答应更稳；Ops 上传 PDF 后仍可问到
- [ ] Render Dashboard 配置 `OPENAI_API_KEY` secret（人工）
- [ ] 若 `/health` 字段语义变更影响顶栏 → 新开 FE session

## 6. 风险 / 已知问题 / 待跟进

- Render free 无 key 时不能静默回 mock（产品要求默认 OpenAI）→ 需清晰错误/degraded，避免「看起来在答、实际是假 LLM」。
- Free tier 内存限制：embedding 仍可能是 `hash` / store `simple`；政策准确度主要靠 chunk + retrieval boost，不依赖立刻上 chroma。
- CI 必须继续 `USE_MOCK_LLM=true`，避免跑真实 API。

## 7. 关联

- 上一 session：`03833c1b` kickoff-boundaries
- 相关 MVP 章节：§2 C9、§2.1、§5、§7、§9 P7
- 相关 PR / commit：待实现后补
