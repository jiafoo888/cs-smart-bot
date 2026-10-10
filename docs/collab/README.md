# 前后端协作记录（Collab Sessions）

本目录用于记录 **Frontend ↔ Backend** 每次沟通与迭代，便于追溯「改了什么 / 谁负责 / 边界在哪 / 出问题找谁」。

## 规则

1. **每次**沟通、联调、或完成一轮前后端相关改动后，必须新增一份 session 记录。
2. 每份记录必须包含唯一 **`session-id`**（UUID），并写入文件名与正文。
3. 产品规格以 [`docs/MVP.md`](../MVP.md) 为准；本目录只记录协作边界与变更，不替代 MVP。
4. 出问题先查本目录最近 session，再按「责任边界」找对应角色。
5. **程序员每次可部署迭代必须上传**：`commit` + `push` 到 `main`（触发 Render），并在 session「关联」里回填 commit hash；未上传不得标 `done`。

## 目录

| 路径 | 用途 |
|------|------|
| [`TEMPLATE.md`](./TEMPLATE.md) | 新建 session 时复制此模板 |
| [`sessions/`](./sessions/) | 按时间排序的历史 session |
| [`OWNERSHIP.md`](./OWNERSHIP.md) | 当前生效的职责与边界总表（随 session 更新） |

## Session 命名

```text
sessions/YYYY-MM-DD_<short-slug>__<session-id前8位>.md
```

示例：`sessions/2026-10-10_kickoff-boundaries__03833c1b.md`

## 角色约定（本仓库）

| 角色 | 代号 | 主要负责 |
|------|------|----------|
| 前端工程师 | **FE** | `static/`（HTML / CSS / JS 或后续前端框架）、控制台 UX、调用后端 API 的客户端契约消费 |
| 后端工程师 | **BE** | `app/`（FastAPI、agents、RAG、DB、tools）、API 契约、seed/ingest、部署配置中与服务相关部分 |
| 产品 / 规格 | **MVP** | `docs/MVP.md` — 冲突时先改 MVP 再改代码 |

跨边界事项（如「新字段要同时改 UI + API」）必须在当次 session 的「联调约定」里写清双方各自交付物与验收标准。
