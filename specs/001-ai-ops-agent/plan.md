# Implementation Plan: 智能运维助手「小龙」（AI Ops Agent）

**Branch**: `001-ai-ops-agent` | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ai-ops-agent/spec.md`

## Summary

构建一个单用户（v1 无鉴权）的智能运维 Web 应用：React 前端 + Python 后端。核心能力三条线——(1) 与运维助手「小龙」的多轮对话问答（原因分析 + 解决方案）；(2) 前端创建文件夹、上传源码或填写本地源码路径完成项目接入；(3) 基于已接入项目提交 Bug，由 agent 定位代码、解析根因并产出可应用的 Patch。

技术路线（来自用户指定 + Phase 0 研究）：React (Vite) 前端；Python FastAPI 后端；MySQL 存业务数据（会话/消息/项目/文件/分析任务）；RAG 层由 **Milvus（向量检索）+ Neo4j（知识图谱关系）+ MinIO（文档对象存储）** 组成，入库内容为企业项目背景与运维技术知识；LLM 通过 OpenAI 兼容接口接入（可配置 base_url/model），Bug 分析走「代码检索 → 上下文组装 → 模型生成 Patch → 校验」流水线。

## Technical Context

**Language/Version**: Python 3.11+（backend）、TypeScript 5.x / React 18（frontend）

**Primary Dependencies**: FastAPI + Uvicorn、SQLAlchemy 2.x、pymilvus、neo4j、minio、openai(兼容客户端)、python-multipart；Vite + React + TypeScript

**Storage**: MySQL 8（业务数据）、Milvus 2.4+（向量）、Neo4j 5（知识图谱）、MinIO（原始文档/上传对象）；本地文件系统承载源码与 Patch 产物

**Testing**: pytest（unit/contract/integration）、Vitest + React Testing Library（frontend）、Testcontainers（MySQL/Milvus/Neo4j/MinIO 集成测试）

**Target Platform**: Linux/macOS/Windows 开发机，Docker Compose 编排依赖服务；桌面浏览器访问

**Project Type**: Web application（backend/ + frontend/ 双仓内子项目）

**Performance Goals**: 首条对话回复 ≤30s（SC-001）；源码接入 ≤2min（SC-003，超大仓库除外）；常规问答 p95 ≤30s

**Constraints**: 单用户/内网工具，无登录；模型服务不可用时返回可读错误不白屏（FR-013/FR-014）；Patch 仅保证在未修改副本上应用成功（Assumption）

**Scale/Scope**: v1 单用户，项目规模建议 ≤5k 文件；3 条核心用户故事；桌面端中文界面

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` 当前为**未填写的模板**（所有 `[PRINCIPLE_*]` 占位符未替换），因此**无可执行的治理原则与硬性门禁**。

以 Spec Kit 通用基线代替执行的检查项：

| Gate | 状态 | 说明 |
|------|------|------|
| 聚焦 WHAT/WHY，实现细节留在 plan 层 | PASS | spec 未含技术栈；技术栈仅出现在本 plan |
| 单一功能、范围有界 | PASS | v1 范围在 spec Assumptions 中明确（无鉴权/无批量修复/桌面端） |
| 可测试性 | PASS | FR-001~015 均有验收场景，SC-001~007 可度量 |
| 复杂度最小化 | PASS | 见 Complexity Tracking：RAG 三件套为用户明确要求，非过度设计 |
| 项目结构与需求匹配 | PASS | 双端 Web 应用 → backend/ + frontend/ 结构 |

**Post-Phase-1 Re-check**: 设计产物未引入新的治理违规；RAG 三件套按用户指定保留，未额外引入未要求的中间件。**GATE: PASS**。

> 建议后续用 `/speckit.constitution` 填写正式 constitution，使门禁可被自动执行。

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-ops-agent/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── api.md           # REST 契约（对话/项目/文件/分析）
│   └── events.md        # SSE 流式事件契约
├── checklists/
│   └── requirements.md  # /speckit.specify output
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created here)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/             # FastAPI 路由：chat、projects、files、analysis
│   ├── core/            # 配置、依赖注入、异常
│   ├── models/          # SQLAlchemy ORM（MySQL）
│   ├── services/        # chat、project_ingest、bug_analysis、patch
│   ├── rag/             # milvus 向量库、neo4j 图谱、minio 对象、ingest 管道
│   └── llm/             # OpenAI 兼容客户端、提示词模板
└── tests/
    ├── unit/
    ├── contract/
    └── integration/

frontend/
├── src/
│   ├── components/      # 对话窗、文件树、上传器、补丁查看器
│   ├── pages/           # Chat、Projects、BugAnalysis
│   └── services/        # API client、SSE 订阅
└── tests/

docker-compose.yml       # mysql, milvus, neo4j, minio, backend, frontend
```

**Structure Decision**: 采用 Web application 结构（Option 2）：`backend/` 承载 FastAPI、ORM、RAG 与 LLM 编排；`frontend/` 承载 React 页面与组件；四个基础设施服务由 docker-compose 编排。文档产物全部位于 `specs/001-ai-ops-agent/`。

## Complexity Tracking

> 仅记录 Constitution/基线门禁需要说明的取舍。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 4 个基础设施依赖（MySQL + Milvus + Neo4j + MinIO） | 用户明确指定 RAG 采用 Milvus/Neo4j/MinIO 且业务数据入 MySQL | 单库方案（仅 MySQL+pgvector）会违反用户指定的 RAG 架构 |
| 双存储路径（MySQL 元数据 + MinIO 对象） | 上传源码/文档体积大，不适合入库 | 全部入 MySQL 会导致大文件与备份成本问题 |
