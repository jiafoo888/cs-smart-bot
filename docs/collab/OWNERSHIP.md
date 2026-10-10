# 职责与边界总表（现行）

> 最后同步 session-id：`ce23755f-d7ba-4e86-989e-e4b8ed5e4513`  
> 日期：2026-10-10  
> 冲突时以最新 session 记录为准，并回写本文件。

## 前端（FE）

| 负责 | 边界（不做） |
|------|--------------|
| `static/` 控制台 UX、Port Daylight 主题、**Hubbit 左栏动效** | `app/` 业务逻辑、退款是否执行 |
| 消费 REST 契约与渲染 | 擅自改 API 语义 |

## 后端（BE）

| 负责 | 边界（不做） |
|------|--------------|
| `app/` agents / RAG / DB / tools；**退款仅状态查询 + 人工 ticket** | `static/` 视觉细节 |
| Docker / Render / CI；迭代须 **push `main`** | 未经 session 的破坏性 API |

## 产品 / 协作（PM）

| 负责 | 边界 |
|------|------|
| `docs/MVP.md`；**每次协作写 `docs/collab/sessions/`** | 不替代代码审查 |
| 退款人工化等业务规则验收 | Render Dashboard 密钥人工配置 |

## 契约交接点

| 接点 | 约定 |
|------|------|
| `POST /chat` refund | 不执行打款；status 可答；发起 → ticket + pause |
| 上线 | commit + push `main`；session 回填 hash |

## 问责

- UI / Hubbit 显示问题 → FE  
- 对话仍能 YES 退款 / 状态答错 → BE  
- 未写 collab / 未上传 → 当次工程师 + PM 补齐后才能标 done
