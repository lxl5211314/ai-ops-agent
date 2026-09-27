# SSE 事件契约: 对话与任务进度

**Date**: 2026-09-25 | **Related**: [api.md](./api.md) | **Spec**: FR-014, SC-001

传输：`text/event-stream`，UTF-8，服务端每 15s 发 `: heartbeat` 注释行保活。客户端（EventSource）断线后提示"连接中断，可重试"，并可通过对应 `GET` 端点恢复最终状态。

每条事件格式：`event: <type>` + `data: <json>`。**所有流以 `event: done` 或 `event: error` 结束。**

## 流 1: 对话回复

`GET /api/v1/conversations/{cid}/messages/{mid}/stream`

| event | data | 说明 |
|-------|------|------|
| `delta` | `{text: string}` | 助手回复增量片段（FR-001/014） |
| `sources` | `{items: [{title, category, snippet}]}` | RAG 命中引用（可选，一次） |
| `done` | `{message_id, finish_reason: "stop"\|"length"}` | 回复完成并已落库（FR-015） |
| `error` | `{code, message}` | 如 `LLM_UNAVAILABLE`(503 语义)、`VALIDATION`；message 为可读中文提示（FR-012/013） |

## 流 2: Bug 分析进度

`GET /api/v1/analyses/{id}/stream`

状态推进与 data-model.md 状态机一一对应：

| event | data | 对应状态 |
|-------|------|----------|
| `stage` | `{stage: "locating"}` | PENDING → LOCATING |
| `stage` | `{stage: "generating"}` | LOCATING → GENERATING |
| `stage` | `{stage: "validating"}` | GENERATING → VALIDATING |
| `located` | `{files: [{file, line_range, snippet}]}` | 定位结果回显（FR-009） |
| `done` | `{analysis_id, status: "succeeded"\|"failed", patch_applicable?: bool}` | 终态 |
| `error` | `{code, message, hint?}` | 失败说明 + 需补充信息（FR-012 的 `hint`） |

前端规则：收到 `done` 后调用 `GET /analyses/{id}` 获取完整 `root_cause / fix_suggestion / patch_text` 渲染。

## 流 3: 项目/知识摄入进度（可选订阅）

`GET /api/v1/projects/{id}/stream` · `GET /api/v1/kb/documents/{id}/stream`

| event | data |
|-------|------|
| `stage` | `{stage: "parsing"\|"chunking"\|"embedding"\|"graph_build"\|"ingesting", detail?: string}` |
| `done` | `{status: "ready"\|"indexed"}` |
| `error` | `{code, message}` |

## 客户端契约

1. 重复提交分析不新建流：以服务端返回的既有 `analysis_id` 订阅同一 URL（Edge Case 幂等）
2. 页面刷新后无法续接旧流 → 以 `GET` 轮询最终状态兜底
3. 所有 `error.message` 必须直接可展示给用户（中文、无堆栈）
