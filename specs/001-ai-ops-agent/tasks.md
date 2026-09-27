---

description: "Task list template for feature implementation"
---

# Tasks: 智能运维助手「小龙」（AI Ops Agent）

**Input**: Design documents from `/specs/001-ai-ops-agent/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Spec 未显式要求 TDD，但 `quickstart.md §7` 将契约测试列为验收通过标准（api.md §7 的 5 条要点），因此每个故事包含契约测试任务；集成/单元测试任务集中在 Polish 阶段。

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/src/`, `frontend/src/`（见 plan.md Project Structure）
- 测试：`backend/tests/{unit,contract,integration}/`、`frontend/tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 项目骨架、依赖与基础设施编排

- [X] T001 Create repository structure per plan.md (`backend/`, `frontend/`, `docker-compose.yml`, `.env.example`) in repository root
- [X] T002 [P] Initialize Python backend with FastAPI, SQLAlchemy 2.x, alembic, pymilvus, neo4j, minio, openai, python-multipart dependencies in `backend/pyproject.toml`
- [X] T003 [P] Initialize React 18 + TypeScript + Vite frontend scaffold in `frontend/package.json` and `frontend/vite.config.ts`
- [X] T004 [P] Author `docker-compose.yml` at repository root orchestrating mysql, milvus, neo4j, minio, backend, frontend per research.md R9
- [X] T005 [P] Define environment configuration loader (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `INGEST_ALLOWED_ROOTS`, DB/RAG connection strings) in `backend/src/core/config.py` and `.env.example`
- [X] T006 [P] Configure linting/formatting: ruff in `backend/pyproject.toml`, eslint+prettier in `frontend/.eslintrc.cjs`

**Checkpoint**: 骨架可启动，`docker compose up -d` 能拉起四个基础设施服务

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共享的地基——必须先完成

**?? CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Setup MySQL connection, SQLAlchemy `Base`, session factory and alembic migrations bootstrap in `backend/src/core/db.py` and `backend/alembic/`
- [X] T008 [P] Implement unified error response `{"error": {code, message, detail}}` with codes `400 VALIDATION / 404 NOT_FOUND / 409 CONFLICT / 422 UNPROCESSABLE / 503 LLM_UNAVAILABLE / 500 INTERNAL` per contracts/api.md §errors in `backend/src/core/errors.py`
- [X] T009 [P] Implement `GET /api/v1/health` returning per-dependency `ok/degraded` for mysql, milvus, neo4j, minio, llm per contracts/api.md §5 in `backend/src/api/routes_health.py`
- [X] T010 [P] Implement SSE emitter with `event:`/`data:` framing and 15s `: heartbeat` per contracts/events.md in `backend/src/core/sse.py`
- [X] T011 [P] Implement OpenAI-compatible chat client with streaming and configurable `base_url/model` per research.md R1 in `backend/src/llm/client.py`
- [X] T012 [P] Implement connection wrappers for Milvus, Neo4j, MinIO with health probes per research.md R2 in `backend/src/rag/clients.py`
- [X] T013 [P] Wire FastAPI app: routers, CORS, `/api/v1` prefix in `backend/src/main.py`
- [X] T014 [P] Implement frontend API client with typed request helpers and SSE subscription util (EventSource wrapper with error surfacing) in `frontend/src/services/api.ts` and `frontend/src/services/sse.ts`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 运维知识对话问答（含知识库 RAG 摄入） (Priority: P1) ?? MVP

**Goal**: 用户与「小龙」多轮问答，回复含原因分析+解决方案；管理员可上传企业背景/运维知识文档入 RAG，回复可引用来源

**Independent Test**: 无需任何项目接入，上传知识文档 → 提问 → ≤30s 收到流式回复且 `sources` 含文档标题（quickstart §2/§3）

### Tests for User Story 1（契约测试，quickstart §7 要求）

- [X] T015 [P] [US1] Contract tests for conversation endpoints (empty content → 400, list/create/delete) in `backend/tests/contract/test_conversations.py`
- [X] T016 [P] [US1] Contract tests for KB endpoints (corrupt file → 422, status transitions) in `backend/tests/contract/test_kb.py`

### Implementation for User Story 1

- [X] T017 [P] [US1] Create `Conversation` and `Message` models (role enum `user|assistant`, conversation级联删除) per data-model.md §1-2 in `backend/src/models/conversation.py`
- [X] T018 [P] [US1] Create `KbDocument` and `KbIngestJob` models (category enum `enterprise_background|ops_knowledge`, status `PENDING→INDEXED|FAILED`) per data-model.md §7-8 in `backend/src/models/kb.py`
- [X] T019 [US1] Add alembic migration creating `conversations`, `messages`, `kb_documents`, `kb_ingest_jobs` tables in `backend/alembic/versions/0001_us1_chat_kb.py`
- [X] T020 [P] [US1] Implement RAG ingestion pipeline `PARSING→CHUNKING→EMBEDDING→GRAPH_BUILD` (MinIO 原文 + 500~800 字/100 字重叠切块入 Milvus + LLM 抽实体关系入 Neo4j) per research.md R3 in `backend/src/rag/ingest.py`
- [X] T021 [P] [US1] Implement hybrid retrieval (Milvus 向量召回 + Neo4j 故障因果/实体扩展) per research.md R2 in `backend/src/rag/retrieval.py`
- [X] T022 [US1] Implement chat service: 上下文拼装、RAG 注入、原因分析+解决方案双段落输出约束 per spec FR-002/FR-003 in `backend/src/services/chat_service.py`
- [X] T023 [US1] Implement conversation routes (`POST/GET/DELETE /conversations`, `POST /conversations/{id}/messages` → 202 + stream_url) per contracts/api.md §1 in `backend/src/api/routes_conversations.py`
- [X] T024 [US1] Implement KB document routes (`POST/GET/DELETE /kb/documents`) per contracts/api.md §4 in `backend/src/api/routes_kb.py`
- [X] T025 [US1] Implement chat SSE route emitting `delta`/`sources`/`done`/`error` per contracts/events.md 流1, persisting final assistant message (FR-015) in `backend/src/api/routes_chat_stream.py`
- [X] T026 [P] [US1] Build Chat page with message list, input, streaming render, clear-history action per spec US1 acceptance scenarios in `frontend/src/pages/ChatPage.tsx`
- [X] T027 [P] [US1] Build reusable chat components (message bubble, loading/error states, source citation chips) in `frontend/src/components/ChatWindow.tsx` and `frontend/src/components/SourceCitations.tsx`
- [X] T028 [P] [US1] Build KB upload page (file picker + category select + status polling with `PENDING→INDEXED/FAILED` display) in `frontend/src/pages/KbPage.tsx`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently — **MVP 可演示**

---

## Phase 4: User Story 2 - 项目源码接入（文件夹/上传/路径） (Priority: P2)

**Goal**: 用户创建文件夹，通过上传源码或输入本地路径接入项目，可见结构概览

**Independent Test**: 创建文件夹 → 路径接入示例项目 → 状态到 READY 且展示文件结构；allowlist 外路径 → 400、重名文件夹 → 409（quickstart §4）

### Tests for User Story 2（契约测试，quickstart §7 要求）

- [X] T029 [P] [US2] Contract tests for folder/project endpoints (409 重名/重复路径, 400 allowlist 外路径, 422 损坏压缩包且无 INGESTING 残留) in `backend/tests/contract/test_projects.py`

### Implementation for User Story 2

- [X] T030 [P] [US2] Create `Folder`, `Project`, `SourceFile` models (source_type enum `upload|path`, status `INGESTING→READY|FAILED`, unique constraints) per data-model.md §3-5 in `backend/src/models/project.py`
- [X] T031 [US2] Add alembic migration creating `folders`, `projects`, `source_files` tables in `backend/alembic/versions/0002_us2_projects.py`
- [X] T032 [US2] Implement ingest service: `INGEST_ALLOWED_ROOTS` 前缀校验（默认拒绝, research R5）、zip-slip 防护、解压/扫描到 `data/projects/<id>/`、回填 `file_count`、二进制文件登记不入上下文, 状态机与失败错误信息 per data-model.md §4 and spec FR-013 in `backend/src/services/project_ingest.py`
- [X] T033 [P] [US2] Implement folder routes (`POST/GET/DELETE /folders`, 409 重名) per contracts/api.md §2 in `backend/src/api/routes_folders.py`
- [X] T034 [P] [US2] Implement project routes (`POST /projects` 路径接入, `GET /projects/{id}` 结构摘要, `GET /projects/{id}/files` 分页, `DELETE`) per contracts/api.md §2 in `backend/src/api/routes_projects.py`
- [X] T035 [US2] Implement multipart upload route `POST /projects/upload` (多文件/zip/tar.gz, 422 损坏包) per contracts/api.md §2 in `backend/src/api/routes_upload.py`
- [X] T036 [P] [US2] Build Projects page: folder list, create-folder dialog, project cards with status badge (`INGESTING/READY/FAILED`) in `frontend/src/pages/ProjectsPage.tsx`
- [X] T037 [P] [US2] Build multi-file/archive uploader component with progress feedback (FR-014) in `frontend/src/components/Uploader.tsx`
- [X] T038 [US2] Build path-connect form (source_path input, allowlist-error display, structure preview after READY) in `frontend/src/components/PathConnectForm.tsx`

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Bug 自动定位、分析与 Patch 生成 (Priority: P3)

**Goal**: 基于 READY 项目提交 Bug 描述 → 定位文件行号 → 根因解析 → 修复建议 → 可应用 Patch

**Independent Test**: 对含已知缺陷的示例项目提交描述 → SSE 阶段推进 → 展示定位/根因/Patch，`git apply --check` 通过（quickstart §5, SC-004/SC-005）

### Tests for User Story 3（契约测试，quickstart §7 要求）

- [X] T039 [P] [US3] Contract tests for analysis endpoints (非 READY → 409, 空描述 → 400, 幂等返回同一 analysis_id, 失败必填 error_message) in `backend/tests/contract/test_analyses.py`

### Implementation for User Story 3

- [X] T040 [P] [US3] Create `BugAnalysis` model with state enum `PENDING→LOCATING→GENERATING→VALIDATING→SUCCEEDED|FAILED` and result fields per data-model.md §6 in `backend/src/models/analysis.py`
- [X] T041 [US3] Add alembic migration creating `bug_analyses` table in `backend/alembic/versions/0003_us3_analyses.py`
- [X] T042 [US3] Implement analysis pipeline per research.md R4: 关键词范围收敛 Top-20 候选文件 → token 预算内上下文组装（含 RAG 运维知识）→ 结构化生成（定位/根因/建议/unified diff）→ 状态机推进 in `backend/src/services/bug_analysis.py`
- [X] T043 [P] [US3] Implement patch validator: 项目副本上 `git apply --check`（无 git 时 `patch --dry-run`），失败附错误重试一轮，结果写 `patch_applicable`/`validation_log` per research.md R4 in `backend/src/services/patch_validator.py`
- [X] T044 [US3] Implement analysis routes (`POST /projects/{id}/analyses` 幂等 409 规则, `GET /analyses/{id}`, `GET /projects/{id}/analyses`, `POST /analyses/{id}/retry`) per contracts/api.md §3 in `backend/src/api/routes_analyses.py`
- [X] T045 [US3] Implement analysis SSE route emitting `stage`/`located`/`done`/`error` (含 FR-012 `hint`) per contracts/events.md 流2 in `backend/src/api/routes_analysis_stream.py`
- [X] T046 [P] [US3] Build Bug analysis page: description textarea (含报错粘贴), stage progress indicator, located files + snippet display, root cause & fix suggestion sections in `frontend/src/pages/BugAnalysisPage.tsx`
- [X] T047 [P] [US3] Build patch viewer component with copy-to-clipboard and download actions, plus failure/hint banner per FR-012 in `frontend/src/components/PatchViewer.tsx`
- [X] T048 [US3] Create fixture project with known defect for SC-004/SC-005 validation in `backend/tests/fixtures/sample-bug-project/`

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: 跨故事的质量、验证与文档收尾

- [X] T049 [P] Add integration tests with Testcontainers (MySQL/Milvus/Neo4j/MinIO) covering 摄入→检索→对话→分析 full path per quickstart §7 in `backend/tests/integration/test_e2e_pipeline.py`
- [X] T050 [P] Add frontend component tests (Vitest + React Testing Library) for chat stream render, uploader error states, patch viewer in `frontend/tests/`
- [X] T051 Run full `quickstart.md` validation (场景 A–D + 回归清单) and record SC-001~SC-007 results in `specs/001-ai-ops-agent/quickstart.md`
- [X] T052 [P] Hardening pass: LLM/依赖不可用时中文可读错误且界面不白屏 (FR-013, Edge Cases), 默认拒绝的 path allowlist, 密钥不入日志, zip-slip 防护复核 in `backend/src/core/errors.py` and `backend/src/services/project_ingest.py`
- [X] T053 [P] Write repository `README.md` with setup steps (compose, `.env`, quickstart links)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
  - T007 → T019/T031/T041 (migrations need db bootstrap)
  - T008/T010/T011/T012/T014 是各故事服务层的直接前置
- **User Story 1 (Phase 3)**: Depends on Foundational
- **User Story 2 (Phase 4)**: Depends on Foundational；不依赖 US1
- **User Story 3 (Phase 5)**: Depends on Foundational + **US2 的 `Project.status=READY` 能力**（唯一跨故事依赖：分析以已接入项目为输入；实现上只需 US2 先完成或至少 T030-T032）
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: 可在 Foundational 后立即开始，无需其他故事
- **User Story 2 (P2)**: 可在 Foundational 后与 US1 并行
- **User Story 3 (P3)**: 需 US2 的项目接入数据（`Project`/`SourceFile`），其余可独立

### Within Each User Story

- Contract tests (T015/T016, T029, T039) 先写并验证失败
- Models → migration → services → routes → frontend → checkpoint

### Parallel Opportunities

- Phase 1: T002~T006 全部 [P]
- Phase 2: T008~T014 全部 [P]（T007 独立进行）
- Phase 3: T015/T016 并行；T017/T018 并行；T020/T021 并行；T026/T027/T028 并行
- Phase 4: T029 独立；T030 与其他并行；T033/T034 并行；T036/T037 并行
- Phase 5: T039 独立；T040 与 T043 并行；T046/T047 并行
- Phase 6: T049/T050/T052/T053 并行
- Foundational 完成后 US1 与 US2 可由不同开发者并行推进

---

## Parallel Example: User Story 1

```bash
# Contract tests together (first):
Task: "Contract tests for conversation endpoints in backend/tests/contract/test_conversations.py"
Task: "Contract tests for KB endpoints in backend/tests/contract/test_kb.py"

# Models together:
Task: "Create Conversation/Message models in backend/src/models/conversation.py"
Task: "Create KbDocument/KbIngestJob models in backend/src/models/kb.py"

# RAG layer together:
Task: "Implement RAG ingestion pipeline in backend/src/rag/ingest.py"
Task: "Implement hybrid retrieval in backend/src/rag/retrieval.py"

# Frontend together:
Task: "Build Chat page in frontend/src/pages/ChatPage.tsx"
Task: "Build chat components in frontend/src/components/ChatWindow.tsx"
Task: "Build KB upload page in frontend/src/pages/KbPage.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1（对话 + RAG 知识摄入）
4. **STOP and VALIDATE**: 按 quickstart §2/§3 独立验证
5. Deploy/demo if ready — 此时已可作为"运维问答助手"对外演示

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → 独立验证 → MVP（小龙对话 + 知识库）
3. US2 → 独立验证 → 增加源码接入（文件夹/上传/路径）
4. US3 → 独立验证 → 增加 Bug 定位与 Patch（依赖 US2 数据）
5. Polish → quickstart 全量回归 + SC 指标记录

### Parallel Team Strategy

1. 团队共同完成 Setup + Foundational
2. Foundational 结束后：
   - Developer A: US1（对话 + RAG）
   - Developer B: US2（源码接入）——与 A 并行
   - US3 在 US2 就绪后由任一方接手
3. 各故事独立完成、独立测试、互不阻塞

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable（US3 唯一需要 US2 的数据能力）
- Contract tests 写后先确认失败再实现
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- 53 tasks total: Setup 6 (T001–T006), Foundational 8 (T007–T014), US1 14 (T015–T028), US2 10 (T029–T038), US3 10 (T039–T048), Polish 5 (T049–T053)
