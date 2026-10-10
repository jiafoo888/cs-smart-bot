# Collab Session — 退款人工化 · Hubbit 小兔子

| 字段 | 值 |
|------|-----|
| **session-id** | `ce23755f-d7ba-4e86-989e-e4b8ed5e4513` |
| **日期** | `2026-10-10` |
| **主题** | 对话禁止直接 refund；可查状态；左侧动态小兔子 Hubbit |
| **参与人** | PM / BE / FE |
| **状态** | done |

---

## 1. 本次更新了什么

- **产品规则 C11**：bot 不得在对话里执行打款/退款；用户可查询 refund/payment 是否 pending / succeeded / refunded；发起退款 → `refund_approval` ticket + pause bot，由人工梳理。
- **防御**：`execute_pending` 拒绝 `action=refund`；旧 pending YES 也转人工 ticket。
- **FE**：左侧栏 Hubbit 桌面兔（`static/img/desk-bunny.jpg` + CSS 动效，非外链 GIF）；Try chips 区分「Refund status」与「Request refund review」。
- **MVP** → **1.3**；本 session 记录；push `main` 上 Render。

## 2. 责任与边界

| 角色 | 负责范围（本 session） | 不负责 / 边界外 |
|------|------------------------|-----------------|
| BE | `refund_agent`、status 文案、ticket、`trust.execute_pending` 护栏、`test.py` | 真实支付网关打款 |
| FE | Hubbit UI、chips、mascot tip JS | agent 路由 |
| PM | C11/C12 规格与验收 | Render 密钥 |

## 3. API / 契约变更

| Method | Path | 变更说明 | 由谁改 | 验收 |
|--------|------|----------|--------|------|
| POST | `/chat` | refund 意图行为变更：handoff / status，不再 YES 打款 | BE | 见 §5 |
| — | schema | 无 breaking 字段变更 | — | — |

## 4. 文件 / 模块清单

| 路径 | 角色 | 说明 |
|------|------|------|
| `app/graph/supervisor.py` | BE | refund_agent rewrite + pending 护栏 |
| `app/response.py` | BE | `compose_refund_status` / `compose_refund_staff_handoff` |
| `app/trust.py` | BE | 禁止 execute refund |
| `static/img/desk-bunny.jpg` | FE | Hubbit 形象 |
| `static/index.html` / `styles.css` / `app.js` | FE | 左栏动效 |
| `docs/MVP.md` | PM | 1.3 · C11 · C12 |
| `test.py` | BE | handoff + status 用例 |

## 5. 联调约定与验收

- [x] `Please refund SHP-2002` → agent=refund，含 ticket/specialist，bot_paused
- [x] `Is the refund for SHP-2002 pending or done?` → status，不打款
- [x] Hubbit 左栏可见、发送时 wave
- [ ] push `main` 后线上同样验收

## 6. 风险 / 已知问题 / 待跟进

- MCP `request_refund` 工具仍存在（运维/桥接），但 chat 路径不再调用；若后续开放 ops 面板打款，须新开 session。
- Hubbit 为 JPG + CSS 动画（稳定、无外链）；若要真 GIF 可后续替换同路径文件。

## 7. 关联

- 上一 session：`0892b97b` clarify-ui-deploy-upload
- 相关 MVP：C8、C11、C12、§3.2 demo scripts 7–8
- 相关 commit：`80e0380`
