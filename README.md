# 智能运维助手「小龙」（AI Ops Agent）

> 对话式运维问答 · 企业知识库 RAG · 源码接入 · Bug 自动定位 / 根因解析 / 补丁生成

一个开箱即用的运维 AI 助手：用自然语言问运维问题，得到带**引用来源**的结构化答案；把企业的项目背景和运维文档喂给知识库；接入自己的源码仓库，粘贴一段报错就能拿到**定位到行号的根因分析和可直接 `git apply` 的修复补丁**。

- **前端**：React 18 + TypeScript + Vite
- **后端**：Python 3.11+ / FastAPI + SQLAlchemy 2.x + Alembic
- **存储**：MySQL（元数据）、Milvus（向量）、Neo4j（实体/因果图）、MinIO（原文对象）
- **大模型**：任意 OpenAI 兼容端点（默认 DeepSeek 对话 + 硅基流动 `BAAI/bge-m3` 向量）
- **开发方式**：Spec Kit 规范驱动（`specs/001-ai-ops-agent/`，53 个任务全部完成）

---

## 目录

- [一、核心功能](#一核心功能)
- [二、系统架构](#二系统架构)
- [三、环境要求](#三环境要求)
- [四、快速开始](#四快速开始)
- [五、系统使用教程](#五系统使用教程)
- [六、配置项参考](#六配置项参考)
- [七、API 速查](#七api-速查)
- [八、测试与质量](#八测试与质量)
- [九、常见问题排查](#九常见问题排查)
- [十、安全说明](#十安全说明)
- [十一、目录结构](#十一目录结构)

---

## 一、核心功能

| 模块 | 能力 | 说明 |
|------|------|------|
| **对话问答** | SSE 流式回答 | 回复固定输出「原因分析 + 解决方案」结构；RAG 命中时展示可点击的**引用来源**卡片；支持多轮会话、历史列表 |
| **知识库** | 文档摄入 → 三路入库 | 上传文档 → 切块 → 向量入 Milvus + 实体关系（LLM 抽取）入 Neo4j + 原文入 MinIO；状态 `PENDING → INDEXED / FAILED` |
| **项目源码** | 两种接入方式 | ① 上传多文件 / zip / tar.gz；② 输入服务器路径（受 `INGEST_ALLOWED_ROOTS` 白名单保护，默认禁用） |
| **Bug 分析** | 四阶段流水线 | 定位代码（关键词+检索 Top-20）→ 根因解析 → 修复建议 → unified diff 补丁，在副本上执行 `git apply --check` 校验 |
| **可观测** | 健康检查 + SSE 事件 | `GET /health` 逐项显示 mysql/milvus/neo4j/minio/llm 状态；事件流带 15s 心跳防断连 |

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│  浏览器 (React SPA)                                             │
│  /chat 对话问答 │ /kb 知识库 │ /projects 源码 │ /analysis 分析  │
└────────────┬────────────────────────────────────────────────────┘
             │ REST + SSE (/api/v1)
┌────────────▼────────────────────────────────────────────────────┐
│  FastAPI 后端                                                    │
│  ├─ api/       路由（health/conversations/kb/projects/analyses）│
│  ├─ services/  对话编排 · 源码摄入 · Bug 分析 · 补丁校验        │
│  ├─ rag/       切块 · 摄入 · 混合检索（向量 + 图谱）            │
│  ├─ llm/       OpenAI 兼容客户端（chat 流式 / JSON / embed）     │
│  └─ core/      配置 · DB · 统一错误 · SSE                        │
└──┬───────┬───────┬───────┬──────────────┬───────────────────────┘
   │       │       │       │              │
┌──▼──┐ ┌─▼───┐ ┌─▼───┐ ┌─▼────┐   ┌─────▼──────────┐
│MySQL│ │Milvus│ │Neo4j│ │MinIO │   │ LLM 提供商      │
│元数据│ │向量  │ │图谱 │ │原文  │   │ DeepSeek(对话) │
│3306/│ │19530 │ │7687 │ │9000  │   │ 硅基流动(embed)│
│ 3307│ │      │ │     │ │      │   └────────────────┘
└─────┘ └──────┘ └─────┘ └──────┘
   全部由 docker-compose.yml 编排
```

**Bug 分析流水线状态机**：`PENDING → LOCATING → GENERATING → VALIDATING → SUCCEEDED | FAILED`

---

## 三、环境要求

| 软件 | 版本 | 用途 |
|------|------|------|
| Docker + Docker Compose | 20.10+ | 拉起 MySQL/Milvus/Neo4j/MinIO/后端/前端 |
| Python | 3.11+（开发机用 3.10 亦可） | 本地开发后端 |
| Node.js | 18+ | 本地开发前端 |
| Git | 2.x | 补丁校验（`git apply --check`）依赖它 |

外网访问：需要能访问你配置的 LLM/Embedding 服务商 API。

---

## 四、快速开始

### 方式 A：Docker 一键启动（推荐演示/部署）

```bash
git clone https://github.com/lxl5211314/ai-ops-agent.git
cd ai-ops-agent

# 1. 配置
cp .env.example .env        # Windows: copy .env.example .env
#    编辑 .env，至少填 LLM_API_KEY / EMBEDDING_API_KEY（见「六、配置项参考」）

# 2. 启动全部（含基础设施）
docker compose up -d

# 3. 验证
curl -s localhost:8000/api/v1/health     # 期望 {"status":"ok",...}
# 前端: http://localhost:8080   后端 API: http://localhost:8000/api/v1
```

> **本机 3306 已被占用怎么办**（常见：装过 MySQL）：
> ```bash
> set "MYSQL_HOST_PORT=3307"     # bash: export MYSQL_HOST_PORT=3307
> docker compose up -d mysql
> # 同时把 .env 里 DATABASE_URL 的端口改成 3307
> ```

### 方式 B：本地开发模式（边改边跑）

```bash
# --- 后端（终端 1）---
cd backend
pip install -e ".[dev]"
uvicorn main:app --app-dir src --reload --port 8000

# --- 前端（终端 2）---
cd frontend
npm install
npm run dev        # http://localhost:5173，/api 已代理到 8000

# --- 基础设施（终端 3，仍需 Docker）---
docker compose up -d mysql etcd minio milvus neo4j
```

> 本地模式下打开 **http://localhost:5173**；Docker 全栈模式打开 **http://localhost:8080**。

### 方式 C：一键启停脚本（Windows，推荐日常使用）

```bat
service.bat start        :: 启动 基础设施 + 后端(:8000) + 前端(:5173)，并等待健康检查
service.bat stop         :: 停止 后端 + 前端（Docker 容器保留，数据不丢）
service.bat stop all     :: 停止 后端 + 前端 + 基础设施容器
service.bat restart      :: 重启 后端 + 前端
service.bat status       :: 查看容器和端口状态
```

日志写入 `logs/backend.log`、`logs/frontend.log`（已 gitignore）。脚本会自动跳过已启动的组件，重复执行安全。

### 数据库迁移

`AUTO_CREATE_TABLES=true`（默认）会在启动时自动建表。使用 Alembic 的话：

```bash
cd backend
alembic upgrade head       # 建迁移  0001 chat/kb → 0002 projects → 0003 analyses
alembic downgrade base     # 回滚
```

---

## 五、系统使用教程

启动后打开前端，顶部导航有四个页面：**对话问答 / 知识库 / 项目源码 / Bug 分析**。

| 对话问答 | 知识库 |
|:---:|:---:|
| ![对话问答](docs/screenshots/01-chat.png) | ![知识库](docs/screenshots/02-kb.png) |

| 项目源码 | Bug 分析 |
|:---:|:---:|
| ![项目源码](docs/screenshots/03-projects.png) | ![Bug 分析](docs/screenshots/04-analysis.png) |

### 5.1 对话问答（/chat）

1. 点左上角 **「+ 新建会话」**。
2. 在底部输入框描述问题（**Enter 发送，Shift+Enter 换行**），例如：
   > 服务器磁盘空间满了，该怎么排查和清理？
3. 回复**流式输出**，固定包含两段：
   - **原因分析** — 为什么会出现这个问题
   - **解决方案** — 分步骤的处理动作
4. 若回答命中了知识库/文档，输入框上方会出现**引用来源卡片**（来源标题 + 摘录），点开可查看出处。
5. 左侧是会话历史，点击可切换；同一会话保留上下文多轮对话。

> 💡 想让回答更准，先去「知识库」上传你们的运维文档，RAG 会带着文档上下文回答并给出引用。

### 5.2 知识库（/kb）

1. 选择分类：
   - **运维技术知识**（`ops_knowledge`）：故障处置手册、运维 SOP、排障记录
   - **企业项目背景**（`enterprise_background`）：系统架构、服务清单、业务背景
2. 选择文件（**`.md` / `.txt` 文本文件**，≤20MB）→ 点 **「上传文档」**。
3. 返回 `202` 后，列表中该文档状态为 `PENDING`，后台自动执行：
   `切块 → 向量入库(Milvus) → LLM 抽取实体关系(Neo4j) → 状态 INDEXED`
   通常几秒内变 `INDEXED`；失败会显示 `FAILED` 和原因（如 embedding 服务不可用）。
4. 可点 **删除** 移除文档（同时清向量与图谱数据）。

> ⚠️ **仅支持纯文本**（`.md`/`.txt`，UTF-8/GBK 自动识别）。PDF/DOCX 是二进制格式，后端不解析——请先转成 Markdown 再上传。

### 5.3 项目源码（/projects）

先把代码弄进来，分三步：

**① 新建文件夹**（对项目做分组，比如按业务线）
- 输入名称 → 点「新建文件夹」

**② 接入项目（二选一）**

- **按路径接入**（需管理员配置白名单，见 5.5）：
  1. 选择文件夹
  2. 填服务器上的绝对路径，如 `D:\code\my-service`
  3. 点接入 → 状态 `READY` 即成功（重复路径会提示 409 并复用已有项目）
- **上传文件/压缩包**：
  1. 选择文件夹
  2. 拖拽或选择多个源码文件，或一个 `zip` / `tar.gz`
  3. 后端解压（带 zip-slip 防护）→ 逐文件解析

**③ 查看**
- 项目列表显示 `文件数` 和状态（`PENDING → READY / FAILED`）
- 点 **「预览」** 看文件树

### 5.4 Bug 分析（/analysis）— 核心亮点

前提：项目已在 5.3 中接入且状态为 `READY`。

1. **选择已就绪项目**（下拉只列 `READY` 项目）。
2. 在文本框**描述 Bug**，尽量包含报错信息，例如：
   > 调用 /api/login 时报 KeyError: 'token'，用户无法登录
3. 点提交，界面显示四个阶段进度条：
   - **定位代码** → 实时列出命中的文件和行号（SSE `located` 事件）
   - **生成分析** → LLM 输出结构化 JSON
   - **校验补丁** → 在临时副本执行 `git apply --check`（失败自动重试一次）
   - **完成**
4. 结果分四块展示：
   - **定位到的代码** — 文件路径 + 行号 + 代码片段
   - **根因解析** — 为什么会出这个问题
   - **修复建议** — 修复思路说明
   - **Patch 补丁** — unified diff 视图，可复制走 `git apply`
5. 底部 **「历史分析」** 可回看该项目过往分析；**「重试」** 可对同一问题重新生成。

**成功标准**：`patch_applicable = true` 表示补丁通过 `git apply --check` 校验，可直接应用。

### 5.5 管理员：开启路径接入白名单（可选）

路径接入默认**拒绝**（防目录穿越）。要使用它，编辑 `.env`：

```ini
INGEST_ALLOWED_ROOTS=D:\code          # 多个用分号: D:\code;D:\project
```

重启后端生效。之后只有这些根目录**及其子目录**的路径可以接入，其余返回 `400 VALIDATION`。

### 5.6 一个完整的工作流示例

```
1. /kb        上传「支付系统运维手册.md」           → INDEXED
2. /projects  新建文件夹「支付」，接入 D:\code\pay  → READY
3. /chat      问「支付回调超时怎么排查？」           → 流式回答 + 引用刚才的手册
4. /analysis  选「pay」，粘贴报错                    → 定位 → 根因 → 补丁（可 git apply）
```

---

## 六、配置项参考

`.env` 完整变量说明（模板见 `.env.example`）：

| 变量 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `DATABASE_URL` | ✅ | `mysql+pymysql://...@localhost:3306/xiaolong` | MySQL 连接串；本机 3306 被占改 3307 |
| `AUTO_CREATE_TABLES` | | `true` | 启动时自动建表（开发用；生产建议改跑 Alembic） |
| `LLM_BASE_URL` | ✅ | `https://api.openai.com/v1` | OpenAI 兼容端点；DeepSeek 用 `https://api.deepseek.com` |
| `LLM_API_KEY` | ✅ | | 对话用 API Key |
| `LLM_MODEL` | | `gpt-4o-mini` | 如 `deepseek-chat` |
| `EMBEDDING_BASE_URL` | | 空（回落到 LLM 配置） | 向量服务端点，独立于对话模型 |
| `EMBEDDING_API_KEY` | | 空（回落到 LLM 配置） | 向量服务 Key（如硅基流动） |
| `EMBEDDING_MODEL` | | `text-embedding-3-small` | 如 `BAAI/bge-m3` |
| `EMBEDDING_DIM` | | `1536` | 向量维度，必须与模型一致（bge-m3=1024）；**改动后需删除 Milvus collection 重建** |
| `MILVUS_URI` | | `http://localhost:19530` | Milvus 地址 |
| `MILVUS_COLLECTION` | | `kb_chunks` | 向量集合名 |
| `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` | | `bolt://localhost:7687` / `neo4j` / `xiaolong-dev` | 图数据库连接 |
| `MINIO_ENDPOINT` 等 | | `localhost:9000` / `xiaolong` / `xiaolong123` | 对象存储（`MINIO_ACCESS_KEY`… 见 `.env.example`） |
| `INGEST_ALLOWED_ROOTS` | | 空 = 禁用路径接入 | 白名单根目录，`;` 分隔 |
| `DATA_DIR` | | `./data` | 本地暂存目录（解压/副本补丁校验） |
| `CORS_ORIGINS` | | `http://localhost:5173` | 允许的前端来源 |
| `MYSQL_HOST_PORT` | | `3306` | compose 侧宿主机 MySQL 端口（3306 冲突时用） |

> 原则：**密钥只放 `.env`，永不提交**。`.env` 已在 `.gitignore` 中。

---

## 七、API 速查

Base：`http://localhost:8000/api/v1`
统一错误体：`{"error": {"code", "message", "detail"}}`
错误码：`400 VALIDATION` · `404 NOT_FOUND` · `409 CONFLICT` · `422 UNPROCESSABLE` · `503 LLM_UNAVAILABLE` · `500 INTERNAL`

```bash
# 健康检查
curl localhost:8000/api/v1/health

# 建会话 → 发消息 → 拿流
curl -X POST localhost:8000/api/v1/conversations -H "Content-Type: application/json" -d '{"title":"t1"}'
curl -X POST localhost:8000/api/v1/conversations/<id>/messages \
     -H "Content-Type: application/json" -d '{"content":"磁盘满了怎么办"}'
#   → {"message_id":"...","stream_url":"/api/v1/conversations/.../messages/.../stream"}
curl -N localhost:8000/api/v1/conversations/.../stream     # SSE: sources/delta/done/error

# 知识库上传 → 查询状态
curl -X POST localhost:8000/api/v1/kb/documents -F category=ops_knowledge -F "file=@manual.md"
curl localhost:8000/api/v1/kb/documents/<id>

# 项目：路径接入 / 上传 / 文件列表
curl -X POST localhost:8000/api/v1/projects -H "Content-Type: application/json" \
     -d '{"folder_id":"<fid>","name":"pay","source_type":"path","source_path":"D:\\code\\pay"}'
curl -X POST localhost:8000/api/v1/projects/upload -F folder_id=<fid> -F "files=@a.py"
curl localhost:8000/api/v1/projects/<pid>/files

# Bug 分析 → SSE 流 → 查结果
curl -X POST localhost:8000/api/v1/projects/<pid>/analyses \
     -H "Content-Type: application/json" -d '{"description":"KeyError: token 无法登录"}'
curl -N localhost:8000/api/v1/analyses/<id>/stream   # SSE: stage/located/done/error
curl localhost:8000/api/v1/analyses/<id>
```

完整契约（含字段表、事件 schema、状态机）：
[`specs/001-ai-ops-agent/contracts/api.md`](specs/001-ai-ops-agent/contracts/api.md) ·
[`events.md`](specs/001-ai-ops-agent/contracts/events.md)

---

## 八、测试与质量

```bash
# 后端单元 + 契约测试（内存 SQLite + 假 LLM/RAG，无需任何基础设施）
cd backend
pytest
# 23 passed, 2 skipped

# Lint
ruff check src tests

# 集成测试（需要基础设施已启动：docker compose up -d）
set RUN_INTEGRATION=1                                      # bash: export RUN_INTEGRATION=1
set DATABASE_URL=mysql+pymysql://xiaolong:xiaolong@127.0.0.1:3307/xiaolong?charset=utf8mb4
pytest tests/integration
# 2 passed（真实 MySQL/Milvus/Neo4j/MinIO：摄入 → 检索 → 对话全链路）

# 前端
cd ../frontend
npm test                      # Vitest：9 passed
npx tsc --noEmit              # 类型检查
npx eslint src tests --ext .ts,.tsx
npm run build
```

**已验证记录**（真实环境，DeepSeek + 硅基流动）见
[`specs/001-ai-ops-agent/quickstart.md`](specs/001-ai-ops-agent/quickstart.md) §8：
对话首字 2.15s、知识库 `202→INDEXED`、Bug 分析 2.4s `SUCCEEDED` 且 `patch_applicable=true`。

---

## 九、常见问题排查

| 现象 | 原因 / 解决 |
|------|------------|
| `health` 里 `mysql: degraded` | MySQL 端口不对。3306 被本机原生 MySQL 占用 → compose 用 3307，同步改 `.env` 的 `DATABASE_URL` |
| `llm: degraded` | `LLM_API_KEY`/`LLM_BASE_URL` 错误，或 `uvicorn` 未读到 `.env`（改完 `.env` 要重启） |
| 知识库上传后 `FAILED` | embedding 服务不通，或 `EMBEDDING_DIM` 与模型不一致（bge-m3=1024）。改维度后需删除 Milvus `kb_chunks` 集合重建 |
| 知识库文档变乱码 | 上传了 PDF/DOCX。只支持纯文本，先转 `.md`/`.txt` |
| 路径接入返回 400「路径不在允许的根目录范围内」 | `INGEST_ALLOWED_ROOTS` 未配置或路径不在白名单内 |
| 分析页项目下拉是空的 | 项目还没到 `READY`，或接入失败——回「项目源码」页看状态和错误信息 |
| 补丁 `patch_applicable=false` | LLM 生成的 diff 与实际代码不匹配（文件版本/上下文差异），点「重试」或补充更精确的报错信息 |
| Docker Hub 拉不动镜像 | 使用镜像前缀拉取再改名：`docker pull docker.1panel.live/library/mysql:8.0 && docker tag docker.1panel.live/library/mysql:8.0 mysql:8.0` |
| 前端接口 404/CORS | 本地开发请走 `http://localhost:5173`（已配 `/api` 代理），或把 `CORS_ORIGINS` 加上你的来源 |
| 端口被占 | 后端 8000 / 前端 5173：`netstat -ano | findstr 8000` 找 PID 结束进程 |

---

## 十、安全说明

- **路径接入默认拒绝**：仅 `INGEST_ALLOWED_ROOTS` 白名单前缀可接入，防目录穿越。
- **解压防护**：zip 与 tar/tar.gz 均做 zip-slip 校验，越界成员直接 422 拒绝。
- **密钥管理**：API Key 仅经环境变量注入，不写日志、不入库；`.env` 被 gitignore，仓库只含 `.env.example` 占位模板。
- **降级友好**：LLM/RAG 依赖不可用时返回可读中文错误（`FR-013`），界面不白屏。
- **补丁永不自动执行**：只在临时副本 `git apply --check`，实际应用由人工决定。

---

## 十一、目录结构

```
ai-ops-agent/
├── README.md
├── docker-compose.yml            # mysql/etcd/minio/milvus/neo4j/backend/frontend
├── .env.example                  # 配置模板（复制为 .env 后填写）
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml            # 依赖 + ruff 配置
│   ├── alembic/                  # 迁移 0001 chat/kb → 0002 projects → 0003 analyses
│   ├── src/
│   │   ├── main.py               # 应用入口
│   │   ├── api/                  # 路由：health/conversations/chat-stream/kb/
│   │   │                         #       folders/projects/analyses/analysis-stream
│   │   ├── core/                 # config · db · errors(统一错误) · sse
│   │   ├── llm/                  # OpenAI 兼容客户端（流式 chat / chat_json / embeddings）
│   │   ├── models/               # SQLAlchemy 模型
│   │   ├── rag/                  # Milvus/Neo4j/MinIO 封装 · 切块 · 摄入 · 混合检索
│   │   └── services/             # chat_service · project_ingest
│   │                             #           bug_analysis · patch_validator
│   └── tests/                    # unit / contract / integration / fixtures
├── frontend/
│   ├── Dockerfile + nginx.conf
│   ├── src/
│   │   ├── App.tsx               # 路由与顶栏导航
│   │   ├── pages/                # ChatPage · KbPage · ProjectsPage · BugAnalysisPage
│   │   ├── components/           # ChatWindow · SourceCitations · Uploader
│   │   │                         # PathConnectForm · FileTree · PatchViewer
│   │   ├── services/             # api(REST) · sse(SSE 客户端)
│   │   └── styles.css
│   └── tests/                    # Vitest 组件测试
├── specs/001-ai-ops-agent/       # Spec Kit 规范产物
│   ├── spec.md  plan.md  tasks.md(53/53 完成)
│   ├── contracts/api.md  contracts/events.md
│   └── quickstart.md             # 端到端验证步骤 + 结果记录
└── .specify/ .opencode/          # Spec Kit 脚本与命令
```

---

## 测试结果总览

| 检查项 | 结果 |
|--------|------|
| 后端 `pytest`（unit + contract） | ✅ 23 passed, 2 skipped |
| 后端 `pytest tests/integration`（真实基础设施） | ✅ 2 passed |
| 后端 `ruff check` | ✅ All checks passed |
| 前端 `npm test` | ✅ 9 passed |
| 前端 `tsc --noEmit` / `eslint` / `build` | ✅ 全部通过 |
| 真实 LLM 端到端（DeepSeek + 硅基流动） | ✅ 9/9（首字 2.15s，补丁 `git apply` 通过） |

## License

MIT
