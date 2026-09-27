# API 契约: 智能运维助手「小龙」

**Date**: 2026-09-25 | **Spec**: [spec.md](../spec.md) | **Data model**: [data-model.md](../data-model.md)

- Base URL: `/api/v1`；请求/响应均为 JSON（上传除外）；日期时间 ISO-8601 UTC
- 错误响应统一结构：`{"error": {"code": "...", "message": "...", "detail": null}}`
- 常用错误码：`400 VALIDATION`、`404 NOT_FOUND`、`409 CONFLICT`、`422 UNPROCESSABLE`、`503 LLM_UNAVAILABLE`、`500 INTERNAL`
- 流式端点见 [events.md](./events.md)；本文件仅覆盖普通 REST

## 1. 对话（FR-001/003/015）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/conversations` | 新建会话。Body: `{title?: string}` → 201 `Conversation` |
| GET | `/conversations` | 列出会话（按 updated_at 倒序）→ `Conversation[]` |
| GET | `/conversations/{id}` | 会话详情（含消息）→ `Conversation & {messages: Message[]}` |
| DELETE | `/conversations/{id}` | 删除会话（级联消息）→ 204 |
| POST | `/conversations/{id}/messages` | 发送用户消息并触发回复。Body: `{content: string}` → `202 {message_id, stream_url: "/api/v1/conversations/{id}/messages/{message_id}/stream"}` |

- `content` 去空白后必为空校验：空 → `400 VALIDATION`
- 助手回复经 SSE 增量写入，最终落库为一条 `role=assistant` 消息（FR-015）

## 2. 文件夹与项目接入（FR-004~FR-007, FR-013）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/folders` | 创建文件夹。Body: `{name: string}` → 201 `Folder`；重名 → `409 CONFLICT` |
| GET | `/folders` | 列出文件夹及其中项目概览 → `[{...Folder, projects: ProjectSummary[]}]` |
| DELETE | `/folders/{id}` | 删除文件夹（级联项目/文件索引，不删除已生成补丁文本）→ 204 |
| POST | `/projects` | 路径接入。Body: `{folder_id, name, source_type:"path", source_path}` → `202 Project(INGESTING)`；路径非法/不在 allowlist → `400 VALIDATION`（message 说明原因）；重复路径 → `409` |
| POST | `/projects/upload` | 上传接入。`multipart/form-data`：`folder_id`, `name`, `files[]`（多文件或 zip/tar.gz）→ `202 Project(INGESTING)`；压缩包损坏 → `422 UNPROCESSABLE` |
| GET | `/projects/{id}` | 项目状态与结构摘要 → `Project & {tree_preview: string[], files_count}` |
| GET | `/projects/{id}/files` | 文件列表（分页 `?page=&size=`）→ `SourceFile[]` |
| DELETE | `/projects/{id}` | 删除项目 → 204 |

`ProjectSummary = {id, name, source_type, status, file_count, created_at}`

## 3. Bug 分析（FR-008~FR-012）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/projects/{id}/analyses` | 提交 Bug。Body: `{description: string}` → `202 {analysis_id, stream_url}`；项目非 READY → `409 CONFLICT`（引导先接入）；同项目未完成的相同 description → 返回既有 `analysis_id`（幂等） |
| GET | `/analyses/{id}` | 查询分析结果 → `BugAnalysis`（含状态与各阶段字段） |
| GET | `/projects/{id}/analyses` | 该项目分析历史 → `BugAnalysis[]` |
| POST | `/analyses/{id}/retry` | 失败后重跑 → `202 {analysis_id, stream_url}` |

进度经 SSE 推送（见 events.md）；`GET /analyses/{id}` 供页面刷新后恢复状态。

## 4. 知识库管理（RAG，支撑 FR-002 知识来源）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/kb/documents` | 上传知识文档。`multipart/form-data`：`title?`, `category`(`enterprise_background`\|`ops_knowledge`), `file` → `202 KbDocument(PENDING)` |
| GET | `/kb/documents` | 文档列表与摄入状态 → `KbDocument[]` |
| GET | `/kb/documents/{id}` | 单文档状态（含 `KbIngestJob.stage`）→ `KbDocument & {job}` |
| DELETE | `/kb/documents/{id}` | 删除文档并清理 Milvus/Neo4j/MinIO 派生数据 → 204 |

## 5. 健康检查

| Method | Path | 说明 |
|--------|------|------|
| GET | `/health` | → `{status, mysql, milvus, neo4j, minio, llm}` 各项 `ok/degraded` |

## 6. 核心 Schema

```text
Conversation {id, title, created_at, updated_at}
Message      {id, conversation_id, role, content, created_at, meta?}
Folder       {id, name, created_at}
Project      {id, folder_id, name, source_type, source_path?, storage_dir, file_count, status}
SourceFile   {id, project_id, rel_path, size_bytes, is_text}
BugAnalysis  {id, project_id, bug_description, status, located_files?, root_cause?,
              fix_suggestion?, patch_text?, patch_applicable?, validation_log?,
              error_message?, created_at, finished_at?}
KbDocument   {id, title, category, object_key, chunk_count, graph_node_count, status, created_at}
KbIngestJob  {id, kb_document_id, stage, detail, updated_at}
```

## 7. 契约测试要点（供 /speckit.tasks 引用）

1. 空消息/空描述 → 400；重名文件夹/重复路径 → 409；非 READY 项目提交分析 → 409
2. 路径接入使用 allowlist 外路径 → 400 且不产生 Project 记录
3. 重复提交同一未完成分析 → 返回同一 analysis_id
4. 损坏压缩包 → 422 且项目状态不残留 INGESTING（应为 FAILED 并有 error）
5. `/health` 中任一依赖不可达 → 对应项 `degraded` 而非整体 500
