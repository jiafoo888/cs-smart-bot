# 职责与边界总表（现行）

> 最后同步 session-id：`0892b97b-e4db-4171-bbab-89f1368dc119`  
> 日期：2026-10-10  
> 冲突时以最新 session 记录为准，并回写本文件。  
> BE/FE/PM 已按 session `0892b97b` 交付本轮。

## 前端（FE）

| 负责 | 边界（不做） |
|------|--------------|
| `static/index.html`、`static/styles.css`、`static/app.js`（及后续若引入的前端框架工程） | `app/` 内业务逻辑、agents、RAG、DB schema |
| 控制台 UX：聊天、Ops 面板、metrics 展示、Debug/BYOK UI、视觉主题（当前 Port Daylight） | 服务端密钥持久化、向量库、seed 数据内容 |
| 消费后端 REST 契约：请求体、响应渲染、错误提示 | 擅自改 API 路径/字段语义（须先与 BE 在 session 中约定） |
| 可选用前端框架（React/Vue 等）重构 UI，但须保持与现有 API 兼容直至 session 明确迁移 | 改动 `docs/MVP.md` 产品范围（须双方 + MVP 流程） |

## 后端（BE）

| 负责 | 边界（不做） |
|------|--------------|
| `app/`：FastAPI 路由、LangGraph、RAG、tools/MCP、SQLite、ingest、clarify 状态机 | `static/` 视觉与交互细节（可提供 mock JSON / OpenAPI） |
| API 契约定义与稳定性：`/chat`、`/health`、`/api/*` | 前端组件结构、CSS、浏览器侧 sessionStorage 策略细节 |
| `data/policies/`、seed、uploads 管线、`test.py` 服务端用例 | 纯 UI 文案微调（除非涉及政策事实准确性） |
| Docker / Render / CI 中与服务启动相关配置；每次可部署迭代须 **push `main`** | 未经 FE 确认的破坏性 API 变更（须 session + 兼容期） |

## 产品 / 协作（PM）

| 负责 | 边界 |
|------|------|
| `docs/MVP.md` 规格与验收口径 | 不直接绕过 collab 改契约 |
| **每次协作/迭代** 必须新增 `docs/collab/sessions/*.md` 并更新 `OWNERSHIP.md` | 不替代代码审查 |
| 部署品牌与运维说明（`DEPLOY.md`）与产品优先级 | Render Dashboard 密钥由 Ops/负责人人工配置 |

## 契约交接点（双方共责）

| 接点 | 约定 |
|------|------|
| `POST /chat` | BE 保证 response schema 稳定；clarify 解绑为行为约定；FE 负责渲染 `reply` / debug / route |
| `GET /health`、`GET /api/metrics/overview` | BE 提供字段；FE 映射到顶栏与 Ops |
| Uploads / reingest | BE 管管道与状态；FE 管文件选择与列表 UI |
| Session id（如 `care-demo-1`） | FE 发起；BE 按 session 存 logs / handoff / profile / clarify |
| Breaking change | 必须新开 collab session，写清迁移与回滚 |
| 上线 | 程序员迭代完成后 **commit + push**；session 记录补 commit hash |

## 问责

- **UI 显示错误但 API 正确** → FE  
- **API 数据错误 / 500 / schema 不符 / clarify 粘滞** → BE  
- **双方已约定但未按 session 交付** → 当次 session 记录中的责任人  
- **规格与实现不符** → 先更新 `docs/MVP.md`，再开 session 分工  
- **改了代码但未上传 / 未写 collab** → 当次工程师 + PM 补记后才能标 done
