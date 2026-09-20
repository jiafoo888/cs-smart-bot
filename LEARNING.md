# 学习手册：从零到可部署客服 Bot

按章节读 + 跑对应 `lessons/*.py`。每章结束都有「面试怎么答」。

---

## 第 0 章：这个项目在解决什么

真实客服系统不是「一个大 Prompt」，而是：

1. **分流**：用户是问政策、查订单、查支付、还是要退款？
2. **专用能力**：政策用 RAG；订单/支付必须查数据库，不能瞎编。
3. **会话**：同一 `session_id` 下记得「刚才说的订单号」。
4. **可控**：能转人工、能审计 tool 调用与 chat_logs。
5. **可部署**：HTTP API + Demo UI + Docker。

### 本仓库已实现的「接近市面」能力

| 模块 | 内容 |
|------|------|
| DB | customers / orders / payments / tickets / chat_logs |
| 政策 ingest | `data/policies/*.md` + `faq.md` → 向量库（带 source/category） |
| Agents | faq · order · payment · refund · escalate |
| API | `/chat` + `/api/orders` + `/api/payments` + `/api/policies/search` |
| Demo UI | http://127.0.0.1:8000/ 左对话右订单/支付/工单 |
| 调试 | `include_debug=true` 或 UI 勾选调试信息 |

启动：`python -m app.bootstrap && uvicorn app.main:app --reload --port 8000`

---

## 第 1 章：async / await（必须会）

### 核心直觉

- **同步**：做完 A 才能做 B；等数据库时 CPU 闲着。
- **异步**：等 I/O 时，事件循环可以去干别的活。
- `async def` 定义协程；`await` 把控制权交回事件循环。

### 客服 Bot 为什么要用

FastAPI 本身是 async；查 DB、调 LLM、向量检索都是 I/O。不会 async，接口一堵就挂。

### 跑

```bash
python lessons/01_async_await.py
```

### 面试怎么答

> async/await 用在 I/O 密集场景。客服 Bot 里 LLM、DB、向量库调用都 await；用 `asyncio.gather` 可并行拉订单和检索 FAQ。

---

## 第 2 章：Tools + Database

LLM **不能**可靠记住订单状态。正确做法：

- 把「查订单」「申请退款」封装成 **Tool**
- Agent 决定何时调用；结果再喂回模型生成自然语言

本项目用 SQLite（可换成 Postgres），表：`orders`。

### 跑

```bash
python lessons/02_tools_and_db.py
```

### 面试怎么答

> Tool calling 把副作用和事实查询从生成里拆出去。订单号、金额、物流以 DB 为准；模型只负责理解意图和措辞。

---

## 第 3 章：RAG

FAQ / 政策文档：

1. **Chunk**：切成小段
2. **Embed**：向量化
3. **Retrieve**：问句向量 → Top-K 相似段落
4. **Generate**：把段落塞进 Prompt 让模型回答（有依据）

本项目默认用本地 `sentence-transformers`（无 key 也能学）；有 `OPENAI_API_KEY` 时可切 OpenAI embedding。

### 跑

```bash
python lessons/03_rag.py
```

### 面试怎么答

> RAG 解决知识更新与幻觉：政策不进权重，进向量库。检索召回 + 引用生成，比 fine-tune FAQ 更合适。

---

## 第 4 章：LangChain / LangGraph / Router / Supervisor / session

| 概念 | 含义 |
|------|------|
| LangChain | 组装 Prompt、Model、Tool、Retriever 的积木 |
| LangGraph | 用**状态图**编排多步 Agent（可循环、可分支） |
| Router | 根据意图选下一个节点 |
| Supervisor | 中央调度：看状态 → 派给子 Agent → 汇总 |
| session_id | 会话主键；对话历史、订单上下文挂在它上面 |
| Different agents | FAQ / Order / Refund / Escalate 各司其职 |

### 跑

```bash
python lessons/04_langgraph_agents.py
```

### 面试怎么答

> 单 Agent 容易把工具乱调。Supervisor + 专用 Agent 把路由和执行分开；`session_id` 对应 checkpointer thread_id，支持多轮。

---

## 第 5 章：LLM 参数与 Prompt 工程

### top_k / top_p / temperature（别和 RAG 的 k 搞混）

| 名字 | 用在哪 | 含义 |
|------|--------|------|
| **检索 top_k** | RAG | 取向量库最相似的 k 段（`retrieve_faq(q, k=3)`） |
| **采样 top_k** | 文本生成 | 每步只在概率最高的 k 个 token 里采样 |
| **top_p** | 文本生成 | Nucleus：累计概率到 p 为止的 token 集合里采样 |
| **temperature** | 文本生成 | 越高越随机；客服查事实建议 **0～0.3** |

### embedding + vector store

1. 文本切块 → 2. `SentenceTransformer` 得到向量 → 3. 存入 `data/vector_store/`  
4. 问句 embed → 与库内向量 **余弦相似度** → 取 top_k → 拼进 Prompt  

代码：`app/rag/ingest.py`、`app/rag/store.py`、`app/rag/retriever.py`

### role / behaviour

**System prompt** 定义人设与边界（不编造订单、可转人工）。见 `app/prompts/cs_prompts.py` 的 `CS_SYSTEM_ROLE`。

### zero-shot vs few-shot

- **Zero-shot**：只有任务说明，无示例 → 省 token，小任务够用  
- **Few-shot**：给 2～3 个「用户话 → 路由标签」示例 → 路由/分类更稳  

路由模板：`build_router_prompt(..., few_shot=True/False)`

### structured output + constraints

- **Structured output**：让模型输出符合 JSON Schema / Pydantic（如 `RouteDecision`）  
- **Constraints**：在 prompt 里写硬规则 + schema 字段上限（`max_length`）  

见 `app/schemas/routing.py`。生产里可用 `model.with_structured_output(RouteDecision)` 替换 `supervisor.py` 里的关键词路由。

### ReAct / CoT / function calling（与第 6 课衔接）

- **CoT**：先推理步骤再行动/回答（可显式写在 prompt 或模型内置 reasoning）  
- **ReAct**：Thought → Action(tool) → Observation → 循环  
- **Function calling**：Action 的标准化 API（`tool_calls` + `ToolMessage`）  

### prompt caching

把 **不变的** system、tools 定义、政策摘要放在请求 **最前面**；多轮只追加 user/assistant。云 API 可对重复前缀缓存，降延迟与费用。见 `CACHED_STATIC_PREFIX`。

### fine-tuning vs RAG（面试必问）

| | Fine-tuning | RAG |
|---|-------------|-----|
| 改什么 | 模型权重 | 外挂知识库 |
| 适合 | 语气、格式、稳定分类 | FAQ/政策常更新 |
| 不适合 | 「记住所有订单」 | 代替实时 DB |

**订单事实永远走 Database + Tool**，不要靠 fine-tune 或长 context「记订单」。

### 跑

```bash
python lessons/05_llm_core_concepts.py
python lessons/06_react_cot_function_calling.py
```

---

## 第 6 章：FastAPI

- `POST /chat`：`{session_id, message}` → `{reply, agent, session_id}`
- `GET /health`
- Swagger：`/docs`

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 第 7 章：Docker

```bash
docker compose up --build
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo-1","message":"查一下订单 ORD-1001"}'
```

---

## 建议你准备的面试故事（2 分钟）

1. 痛点：客服重复答政策、查单慢、模型会编造订单。
2. 方案：Supervisor 分流；RAG 政策；Tool 查库；session 多轮。
3. 工程：FastAPI + SQLite/Postgres + Docker；mock LLM 保证本地可演示。
4. 扩展：换真实 LLM、加鉴权、加评价反馈、加 tracing（LangSmith）。
