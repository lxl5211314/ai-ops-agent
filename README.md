# 智能运维助手「小龙」（AI Ops Agent）

对话式运维问答 + 企业知识库 RAG + 源码接入 + Bug 自动定位/根因分析/补丁生成。

- 前端：React 18 + TypeScript + Vite
- 后端：Python FastAPI + SQLAlchemy 2.x + Alembic
- 存储：MySQL（会话/项目/分析元数据）、Milvus（向量）、Neo4j（实体/因果图）、MinIO（原文/归档）
- 规范驱动开发（Spec Kit）：`specs/001-ai-ops-agent/`

## 功能

| 能力 | 说明 |
|------|------|
| 运维知识对话 | SSE 流式回复，「原因分析 + 解决方案」结构，RAG 引用来源（`sources`） |
| 知识库摄入 | 上传企业背景/运维知识文档 → 切块入 Milvus + 实体关系入 Neo4j + 原文入 MinIO，状态 `PENDING→INDEXED\|FAILED` |
| 源码接入 | 文件夹管理；上传多文件/zip/tar.gz，或输入服务器路径（`INGEST_ALLOWED_ROOTS` 白名单，默认拒绝） |
| Bug 分析 | 定位文件行号 → 根因解析 → 修复建议 → unified diff 补丁，副本上 `git apply --check` 校验 |
| SSE 事件 | 对话流 `delta/sources/done/error`；分析流 `stage/located/done/error`（15s 心跳） |

## 快速开始

### 1. 配置

```bash
cp .env.example .env
# 填入 LLM 配置（OpenAI 兼容端点）
# 路径接入需要显式白名单：INGEST_ALLOWED_ROOTS=C:\code;D:\projects（留空 = 禁用路径接入）
```

### 2. 启动基础设施 + 应用

```bash
docker compose up -d            # mysql, etcd, minio, milvus, neo4j, backend, frontend
curl -s localhost:8000/api/v1/health   # 期望 status=ok
# 前端: http://localhost:8080  后端 API: http://localhost:8000/api/v1
```

本机 3306 已被占用时：

```bash
set "MYSQL_HOST_PORT=3307" && docker compose up -d mysql
# 并把 .env 中 DATABASE_URL 的端口改为 3307
```

### 3. 本地开发模式

```bash
# 后端
cd backend
pip install -e ".[dev]"
uvicorn main:app --app-dir src --reload --port 8000

# 前端
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 代理到 8000
```

## 测试与质量

```bash
cd backend
pytest                       # unit + contract（sqlite + 假 LLM/RAG，无需基础设施）
ruff check src tests         # lint

# 集成测试（需要 docker compose 基础设施已启动）
set "RUN_INTEGRATION=1"
set "DATABASE_URL=mysql+pymysql://xiaolong:xiaolong@127.0.0.1:3307/xiaolong?charset=utf8mb4"
pytest tests/integration

cd ../frontend
npm test                     # Vitest（React Testing Library）
npx tsc --noEmit && npx eslint src tests --ext .ts,.tsx
npm run build
```

端到端验证步骤与结果记录见 [specs/001-ai-ops-agent/quickstart.md](specs/001-ai-ops-agent/quickstart.md)。

## 目录结构

```
├── backend/
│   ├── src/
│   │   ├── api/           # 路由（health/conversations/chat-stream/kb/folders/projects/analyses）
│   │   ├── core/          # 配置、DB、统一错误、SSE
│   │   ├── llm/           # OpenAI 兼容客户端（流式 chat / chat_json / embeddings）
│   │   ├── models/        # SQLAlchemy 模型
│   │   ├── rag/           # Milvus/Neo4j/MinIO 封装、切块、摄入、混合检索
│   │   ├── services/      # 对话、源码摄入、Bug 分析、补丁校验
│   │   └── main.py
│   ├── alembic/           # 迁移（0001 chat/kb, 0002 projects, 0003 analyses）
│   └── tests/             # unit / contract / integration / fixtures
├── frontend/
│   ├── src/pages/         # Chat / Kb / Projects / BugAnalysis
│   ├── src/components/    # ChatWindow, SourceCitations, Uploader, PathConnectForm, FileTree, PatchViewer
│   └── tests/             # Vitest 组件测试
├── specs/001-ai-ops-agent/ # spec / plan / tasks / contracts / quickstart
├── docker-compose.yml
└── .env.example
```

## API 概览

Base：`/api/v1`，统一错误体 `{"error": {"code", "message", "detail"}}`（400 VALIDATION / 404 NOT_FOUND / 409 CONFLICT / 422 UNPROCESSABLE / 503 LLM_UNAVAILABLE / 500 INTERNAL）。

- `GET /health` — mysql/milvus/neo4j/minio/llm 逐项 `ok|degraded`
- `POST|GET|DELETE /conversations`、`POST /conversations/{id}/messages` → 202 + `stream_url`
- `GET /conversations/{id}/messages/{id}/stream` — SSE 对话流
- `POST|GET|DELETE /kb/documents` — 知识文档摄入/查询
- `POST|GET|DELETE /folders`、`POST /projects`、`POST /projects/upload`、`GET /projects/{id}/files`
- `POST /projects/{id}/analyses`、`GET /analyses/{id}`、`POST /analyses/{id}/retry`
- `GET /analyses/{id}/stream` — SSE 分析流

完整契约见 [specs/001-ai-ops-agent/contracts/api.md](specs/001-ai-ops-agent/contracts/api.md) 与 [events.md](specs/001-ai-ops-agent/contracts/events.md)。

## 安全说明

- 路径接入默认拒绝，仅允许 `INGEST_ALLOWED_ROOTS` 白名单前缀（防目录穿越）。
- 解压启用 zip-slip 校验（zip 与 tar/tar.gz 均拒绝越界成员）。
- 密钥仅通过环境变量注入，不写入日志；LLM/RAG 依赖不可用时返回可读中文错误（FR-013），界面不白屏。
