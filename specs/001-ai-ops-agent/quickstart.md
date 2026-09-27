# Quickstart 验证指南: 智能运维助手「小龙」

**Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md) | **Contracts**: [contracts/api.md](./contracts/api.md)

目的：端到端跑通三条核心链路，验证 SC-001~SC-007。**不含实现代码**；实现细节由 `tasks.md` 承载。

## 前置条件

- Docker + Docker Compose
- Python 3.11+、Node 20+（本地开发模式）
- 一个 LLM 的 OpenAI 兼容端点（`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`）
- 一个用于路径接入测试的小型示例项目（含 1 个已知缺陷），以及 1~2 份知识文档（企业背景/运维知识，md 或 pdf）

## 1. 启动

```bash
cp .env.example .env          # 填入 LLM 配置、INGEST_ALLOWED_ROOTS=<示例项目父目录>
docker compose up -d          # mysql, milvus, neo4j, minio, backend, frontend
curl -s localhost:8000/api/v1/health | jq   # 期望：所有依赖 ok
```

**预期**: `status=ok`；任一依赖缺失时该项 `degraded` 且界面显示可读提示（FR-013）。

## 2. 场景 A — 对话问答（P1，SC-001/SC-002）

1. 打开前端 → 进入对话页
2. 提问：`服务响应突然变慢，应该如何排查？`
3. 观察：增量输出（SSE `delta`），≤30s 出首字（SC-001）
4. 追问：`那如果是磁盘导致的呢？` → 检查上下文连贯（FR-003）
5. 提问无关问题（如`今天天气`）→ 得到澄清/拒答而非编造（FR-012）
6. 清空历史 → 界面回到初始态（Acceptance US1-4）

**契约依据**: api.md §1、events.md 流 1。

## 3. 场景 B — 知识库摄入（RAG）

1. 上传一份"企业项目背景"文档（category=`enterprise_background`）与一份"运维排障手册"（`ops_knowledge`）
2. 轮询 `GET /kb/documents/{id}` → status `PENDING → INDEXED`，`chunk_count > 0`（FR-014 进度可见）
3. 回到场景 A 提问与文档内容相关的问题 → 回复 `sources` 中出现该文档标题（证明 RAG 生效）

**预期失败路径**: 上传损坏文件 → `422` 且 status=FAILED 带错误信息。

## 4. 场景 C — 源码接入（P2，SC-003）

1. 创建文件夹 `demo`（重名再建 → 409 提示）
2. **路径接入**: 填入示例项目路径 → 项目 `INGESTING → READY`，可见结构摘要与文件数
3. **上传接入**: 另建文件夹，上传 zip → 同样到 READY
4. 负例：填入 allowlist 外路径 → 400 中文提示，且不产生项目记录
5. 重复提交同一路径 → 409（不静默覆盖）

**契约依据**: api.md §2；Edge Cases（无效路径/重复接入/损坏包）。

## 5. 场景 D — Bug 定位与补丁（P3，SC-004/SC-005）

1. 在 READY 项目上提交：`描述：<示例缺陷现象>，报错：<粘贴报错>`
2. 观察 SSE `stage` 推进：locating → generating → validating → done（FR-014）
3. 结果页展示：定位文件+行号、根因解析、修复建议、可复制/下载的 Patch（FR-009/010/011）
4. **补丁校验**: 将 Patch 应用于项目副本 → `git apply --check` 通过（`patch_applicable=true`）
5. 负例：在空项目/未接入项目提交 → 409 并引导先接入（FR-012）
6. 负例：构造无法定位的描述 → status=failed，`error_message`/`hint` 说明需补充的信息，无编造补丁
7. 幂等：分析进行中重复点击提交 → 返回同一 analysis_id（Edge Case）

## 6. 回归检查清单

| 检查项 | 期望 | 对应 |
|--------|------|------|
| 停掉 LLM 服务再提问 | 中文错误提示，界面不白屏 | FR-013, Edge Cases |
| 停掉 Milvus 再上传知识文档 | 摄入 FAILED 且提示；对话仍可用（降级） | FR-013 |
| 分析中刷新页面 | 通过 `GET /analyses/{id}` 恢复状态 | events.md 客户端契约 |
| 会话历史 | 重启后端后仍在 | FR-015 |

## 7. 自动化验证

```bash
# 基础设施（真实 MySQL/Milvus/Neo4j/MinIO）
docker compose up -d mysql etcd minio milvus neo4j   # 3306 被占用时: MYSQL_HOST_PORT=3307 docker compose up -d mysql

cd backend && pytest                                 # unit + contract（无需基础设施，默认 sqlite + 假 LLM/RAG）
RUN_INTEGRATION=1 DATABASE_URL=mysql+pymysql://xiaolong:xiaolong@127.0.0.1:3307/xiaolong?charset=utf8mb4 \
  pytest tests/integration                           # 真实基础设施端到端（LLM 仍为假实现）
cd ../frontend && npm test                           # Vitest
```

**通过标准**: 契约测试覆盖 api.md §7 的 5 条要点；示例缺陷项目全量用例达到 SC-004（≥80% 定位正确）与 SC-005（≥80% 补丁可应用）。

## 8. 验证结果记录（2026-09-26）

| 项 | 结果 |
|----|------|
| `backend: pytest`（unit + contract） | 23 passed, 2 skipped（集成用例默认跳过） |
| `backend: pytest tests/integration`（RUN_INTEGRATION=1，真实 MySQL/Milvus/Neo4j/MinIO） | 2 passed（health 全绿 + 摄入→检索→对话流） |
| `frontend: npm test`（Vitest：ChatWindow/PatchViewer/PathConnectForm/Uploader） | 9 passed |
| `frontend: tsc --noEmit` / `eslint` / `npm run build` | 全部通过 |
| `backend: ruff check src tests` | All checks passed |
| 端到端冒烟（场景 A/C/D + 健康检查，19 项断言） | **19/19 PASS**：health 全 ok；文件夹 201/409/400；路径接入 READY、重复 409、越界 400、文件列表；上传接入 READY；知识库 202→INDEXED（真实 MinIO/Milvus/Neo4j）；对话 SSE `delta`+结构化「原因分析/解决方案」；分析 202→SUCCEEDED 且 `patch_applicable=true`（`git apply --check` 通过）、定位到 `app.py` |

冒烟说明：

- 环境限制下使用 OpenAI 兼容 mock LLM（embeddings/chat 兼容端点，`EMBEDDING_DIM=8`，独立 collection `kb_chunks_smoke`）；LLM 依赖的断言（SC-001 首字时延、真实语义质量）需填入真实 `LLM_API_KEY` 后按 §2 场景 A 复测。
- 本机 3306 已被原生 `mysqld.exe` 占用，compose MySQL 映射到 3307（`MYSQL_HOST_PORT=3307`）。
- 回归清单 §6 中"停掉依赖"类项通过契约用例的降级断言（FakeRAG/FakeLLM 故障注入）覆盖。

### 真实 LLM 端到端（2026-09-26，DeepSeek `deepseek-chat` + 硅基流动 `BAAI/bge-m3`）

| 项 | 结果 |
|----|------|
| `GET /health` | `status=ok`（mysql/milvus/neo4j/minio/llm 全 ok） |
| 场景 A：对话流（SC-001） | 首字 **2.15s**（≤30s 达标），回复 2213 字，含「原因分析/解决」结构 |
| 场景 B：知识库摄入 | `202 → INDEXED`（真实 embedding 1024 维入 Milvus，原文入 MinIO） |
| 场景 C：路径接入 | fixtures 示例项目 → `READY`（重复路径 409 并复用 project_id） |
| 场景 D：Bug 分析（SC-004/SC-005） | **2.4s** `SUCCEEDED`；定位到 `app.py`；`patch_applicable=true`（`git apply --check` 通过） |

配置：`backend/src/core/config.py` 支持 `EMBEDDING_BASE_URL`/`EMBEDDING_API_KEY` 独立于 LLM（DeepSeek 无 embeddings 接口）。Milvus `kb_chunks` 已按 `EMBEDDING_DIM=1024` 重建。
