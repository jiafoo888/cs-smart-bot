# Collab Session — 前后端协作流程 Kickoff

| 字段 | 值 |
|------|-----|
| **session-id** | `03833c1b-4f80-44a7-b078-7b55c20b19f3` |
| **日期** | `2026-10-10` |
| **主题** | 建立 FE/BE 协作记录机制；划清现行仓库职责边界 |
| **参与人** | FE（本角色）、BE（待对接）、规格以 MVP 为准 |
| **状态** | done |

---

## 1. 本次更新了什么

- 新增协作目录 `docs/collab/`：README、模板、OWNERSHIP 总表、本 session 记录。
- 约定：之后每次前后端沟通或联调改动，都必须带 **session-id** 落盘到 `docs/collab/sessions/`。
- 摸底现行技术栈，作为边界基线：
  - **FE 现状**：`static/` 原生 HTML + CSS + JS（无框架），由 FastAPI 挂载静态资源。
  - **BE 现状**：`app/main.py` FastAPI；LangGraph / RAG / tools；SQLite + uploads。
  - **产品规格**：`docs/MVP.md`。

## 2. 责任与边界

| 角色 | 负责范围（本 session） | 不负责 / 边界外 |
|------|------------------------|-----------------|
| FE | 协作文档流程；后续所有 `static/`（及可选前端框架）改动；API **消费**与 UX | 不改 agents / RAG / DB / 服务端业务逻辑 |
| BE | 确认并维护 API 契约与 `app/`；对 FE 请求的 schema 变更给出明确回复 | 不擅自改控制台 UI；破坏性 API 变更须新 session |
| 共责 | 契约字段变更、breaking change 迁移、验收清单 | — |

详细现行总表见 [`../OWNERSHIP.md`](../OWNERSHIP.md)。

## 3. API / 契约变更（如有）

| Method | Path | 变更说明 | 由谁改 | 验收 |
|--------|------|----------|--------|------|
| — | — | 本 session **无** API 变更；仅建立流程 | — | — |

### 现行 FE 已消费的主要接点（基线，供后续 session 对照）

| Method | Path | FE 用途 |
|--------|------|---------|
| POST | `/chat` | 主对话 |
| GET | `/health` | LLM / 就绪状态 |
| GET | `/api/metrics/overview` | 顶栏 metrics |
| GET | `/api/shipments` | Ops 货件列表 |
| GET | `/api/inventory` | Ops 库存 |
| GET | `/api/tickets` | Ops 工单 |
| GET/POST | `/api/uploads` | 文档上传与列表 |
| POST | `/api/admin/reingest` | 重建向量库 |
| POST | `/api/admin/reseed` | 重灌 demo 数据 |
| GET | `/api/kb/stats` | KB 统计 |
| GET | `/api/policies/search` | 政策检索（Ops） |
| GET | `/api/sessions/{id}/profile` | 会话画像 |
| GET | `/api/sessions/{id}/assist` | 辅助信息 |
| POST | `/api/sessions/{id}/human-reply` | 人工回复 |
| POST | `/api/sessions/{id}/resume-bot` | 恢复 bot |

## 4. 文件 / 模块清单

| 路径 | 角色 | 说明 |
|------|------|------|
| `docs/collab/README.md` | FE（流程） | 协作规则入口 |
| `docs/collab/TEMPLATE.md` | FE（流程） | 新 session 模板 |
| `docs/collab/OWNERSHIP.md` | FE+BE | 现行职责总表 |
| `docs/collab/sessions/2026-10-10_kickoff-boundaries__03833c1b.md` | FE+BE | 本记录 |
| `static/*` | FE | 前端交付边界 |
| `app/*` | BE | 后端交付边界 |
| `docs/MVP.md` | 规格 | 产品与技术 SoT |

## 5. 联调约定与验收

- [x] 协作目录与模板就位
- [x] OWNERSHIP 职责总表就位
- [x] session-id 写入本文件与 OWNERSHIP「最后同步」
- [x] BE 确认 OWNERSHIP 边界（下一轮对接时勾选）— 已在 `f1481266` 确认
- [x] 下一轮功能开发开新 session，禁止无记录改契约 — 见 `f1481266`

## 6. 风险 / 已知问题 / 待跟进

- FE 仍为原生 `static/`；若引入 React/Vue 等框架，须新开 session 写清目录迁移与静态挂载方案，BE 配合确认路由/`StaticFiles`。
- 当前 chat session 硬编码 `care-demo-1`（`static/app.js`）；多会话若要做，FE 提需求，BE 确认 session API 是否够用。
- git status 中已有 `static/app.js`、`static/index.html` 未提交改动——后续功能 session 需单独说明，避免与流程 kickoff 混淆。

## 7. 关联

- 上一 session：无（首份）
- 相关 MVP 章节：§2 能力、§5 Upload UI、§6 API surface、§8 Repo layout
- 相关 PR / commit：待提交

---

## 给后端同学的沟通摘要（可贴给 BE）

1. 我们从本 session 起，用 `docs/collab/sessions/` + **session-id** 记每轮协作。
2. 请确认 [`OWNERSHIP.md`](../OWNERSHIP.md)：你管 `app/` + API；我管 `static/` + 契约消费。
3. 下一轮若要改 `/chat` 或 `/api/*` 字段，先开新 session 再改代码；breaking change 必须写迁移与验收。
4. 回复时请带回本 **session-id**：`03833c1b-4f80-44a7-b078-7b55c20b19f3`。
