# Phase 1 Data Model: 智能运维助手「小龙」

**Date**: 2026-09-25 | **Plan**: [plan.md](./plan.md) | **Source**: spec.md §Key Entities + research.md R3/R7

存储分工：MySQL 保存下列**全部业务实体**；MinIO 保存 `KbDocument.content_object_key` 与源码压缩包原文；Milvus/Neo4j 保存派生的向量与图谱数据（由摄入管道生成，非本模型权威源）。

---

## 1. Conversation（会话）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| title | varchar(120) | 默认取首条用户消息前 40 字符；可空 |
| created_at | datetime | 非空 |
| updated_at | datetime | 每次新增消息更新（用于会话排序） |

**校验**: 无必填用户输入。**关系**: 1 → N Message。

---

## 2. Message（消息）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| conversation_id | uuid | FK → Conversation.id，级联删除 |
| role | enum | `user` / `assistant`，非空 |
| content | text | 非空 |
| created_at | datetime | 非空 |
| meta | json | 可空；助手消息可携带引用来源（RAG 命中的文档/图谱实体） |

**状态**: 无（追加型）。**对应需求**: FR-001/002/003/015。

---

## 3. Folder（文件夹，界面容器）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| name | varchar(80) | 非空，同一父级下唯一（v1 只有根级 → 全局唯一） |
| created_at | datetime | 非空 |

**校验**: name 去首尾空格后非空；重复创建 → 409（Edge Case：不静默覆盖）。**关系**: 1 → N Project。
**对应需求**: FR-004。

---

## 4. Project（项目，已接入的源码）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| folder_id | uuid | FK → Folder.id，级联删除 |
| name | varchar(120) | 非空 |
| source_type | enum | `upload` / `path`，非空 |
| source_path | varchar(512) | source_type=`path` 时非空，存用户输入的绝对路径；同项目内唯一 |
| storage_dir | varchar(512) | 非空；后端归一化后的源码根目录（`data/projects/<id>/`） |
| file_count | int | 接入完成后回填；接入中为 0 |
| status | enum | `INGESTING` → `READY` / `FAILED`，默认 `INGESTING` |
| created_at | datetime | 非空 |

**校验**: `path` 接入必须通过 `INGEST_ALLOWED_ROOTS` 前缀校验（research R5），否则拒绝；重复 `source_path` → 409。
**状态迁移**: INGESTING → READY（解析完成）| FAILED（无效路径/损坏压缩包，须记录错误原因）。
**对应需求**: FR-005/006/007/013；Edge Cases（重复接入、无效路径、损坏包、超大仓库）。

---

## 5. SourceFile（源码文件索引）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | bigint | PK auto_increment |
| project_id | uuid | FK → Project.id，级联删除 |
| rel_path | varchar(512) | 项目内相对路径，与 project_id 联合唯一 |
| size_bytes | bigint | 非空 |
| is_text | bool | 是否参与文本检索；二进制文件登记但不入分析上下文 |

**说明**: 仅存元数据，文件内容留在 `storage_dir`（research R5）。**对应需求**: FR-007、Edge Case（二进制跳过并汇总）。

---

## 6. BugAnalysis（Bug 分析任务）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| project_id | uuid | FK → Project.id，删除项目则级联删除 |
| bug_description | text | 非空（可含粘贴的报错文本） |
| status | enum | 见状态机，非空，默认 `PENDING` |
| located_files | json | 可空；`[{file, line_range, snippet}]` |
| root_cause | text | 可空；根因解析 |
| fix_suggestion | text | 可空；修复建议 |
| patch_text | text | 可空；unified diff |
| patch_applicable | bool | 可空；`--check`/`--dry-run` 校验结果 |
| validation_log | text | 可空；校验输出，失败时供 FR-012 呈现 |
| error_message | text | 可空；status=FAILED 时必填 |
| created_at / finished_at | datetime | created_at 非空 |

**状态机**:

```text
PENDING → LOCATING → GENERATING → VALIDATING → SUCCEEDED
    └────────────────┴──────────────┴──────────→ FAILED（任一步，error_message 必填）
```

**校验**: 描述非空；仅当 `project.status = READY` 才接受任务（否则按 FR-012/Edge Case 引导先接入源码）；同一 description 在同一未完成项目上重复提交返回既有任务 id（幂等，Edge Case：重复点击）。
**对应需求**: FR-008~FR-012、SC-004/SC-005。

---

## 7. KbDocument（知识库文档，RAG 入库对象）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| title | varchar(200) | 非空；默认取文件名 |
| category | enum | `enterprise_background` / `ops_knowledge`，非空（对应 spec：企业项目背景 / 运维技术知识） |
| object_key | varchar(512) | 非空；MinIO 中的原文 key |
| chunk_count | int | 切块数，摄入完成后回填 |
| graph_node_count | int | 写入 Neo4j 的实体/关系数 |
| status | enum | `PENDING → INDEXED / FAILED` |
| created_at | datetime | 非空 |

**状态迁移**: PENDING → INDEXED（MinIO+Milvus+Neo4j 三处写入均成功）| FAILED（记录错误，可重试）。
**对应需求**: FR-002 的知识来源、FR-013（摄入失败提示）。

---

## 8. KbIngestJob（摄入任务日志，支撑 FR-014 进度）

| 字段 | 类型 | 约束/说明 |
|------|------|-----------|
| id | uuid | PK |
| kb_document_id | uuid | FK → KbDocument.id |
| stage | enum | `PARSING → CHUNKING → EMBEDDING → GRAPH_BUILD → DONE / FAILED` |
| detail | varchar(512) | 可空；当前阶段说明/错误 |
| updated_at | datetime | 非空 |

---

## 关系概览

```text
Conversation 1─* Message
Folder 1─* Project 1─* SourceFile
Project 1─* BugAnalysis
KbDocument 1─* KbIngestJob
KbDocument ──(派生)──> Milvus chunks / Neo4j entities+edges / MinIO object
```

## 派生数据（非 MySQL 权威，仅登记）

- **Milvus collection** `kb_chunks`: `pk, document_id, chunk_text, vector, heading, category`
- **Neo4j**: 节点 `Entity(name, type)`、`Chunk(id)`；边 `(:Entity)-[:RELATION {name}]->(:Entity)`、`(:Chunk)-[:MENTIONS]->(:Entity)`；故障链 `(:Symptom)-[:CAUSED_BY]->(:Cause)-[:SOLVED_BY]->(:Solution)`
- **MinIO buckets**: `kb-documents`（知识原文）、`source-archives`（上传压缩包）
