# Phase 0 Research: 智能运维助手「小龙」（AI Ops Agent）

**Date**: 2026-09-25 | **Plan**: [plan.md](./plan.md)

目的：消除 plan.md Technical Context 中的未知项，所有决策均可追溯到 spec 需求或用户指定约束。

---

## R1. LLM 接入方式

**Decision**: 通过 **OpenAI 兼容 Chat Completions 接口**接入，`base_url` 与 `model` 由配置文件/环境变量决定；客户端封装为 `llm/client.py`，支持流式输出。

**Rationale**: 用户未指定模型供应商；OpenAI 兼容协议是当前事实标准，可同时覆盖 OpenAI、DeepSeek、Qwen、vLLM/Ollama 本地部署，v1 无需改代码即可切换；流式输出支撑 FR-014（进度反馈）与 SC-001（30s 首响）。

**Alternatives considered**:
- 绑定单一供应商 SDK：切换成本高，用户未指定供应商 → 否决
- 完全本地小模型：质量不足以支撑根因解析 → 保留为部署选项而非默认

**未决残留**: 默认模型名与供应商不在 plan 阶段锁定，quickstart 中以占位配置交付。

---

## R2. RAG 架构分工（Milvus / Neo4j / MinIO）

**Decision**: 三库各司其职，通过统一的 `rag/` 服务层封装：

| 组件 | 职责 | 存什么 |
|------|------|--------|
| MinIO | 原始对象存储 | 上传的企业项目背景/运维知识原文档（pdf/docx/md/txt）、源码压缩包 |
| Milvus | 语义检索 | 文档切块后的向量 + chunk 元数据（来源、标题、业务域标签） |
| Neo4j | 关系检索 | 实体图谱：`服务/组件 —(属于/依赖/部署于)→ …`、`故障现象 —(根因)→ 原因 —(解决)→ 方案`，以及 chunk 与实体的 `MENTIONS` 边 |

**Rationale**: 满足用户「RAG 中上传的是企业项目背景和运维技术知识」的定位：向量库负责"找相似段落"，图谱负责"顺着企业拓扑/故障因果链扩展"（例如从现象扩展到同服务的历史故障），MinIO 保证原文可追溯（引用回链）。查询采用 **向量召回 + 图谱扩展的混合检索**，再由 LLM 归纳。

**Alternatives considered**:
- 只用 Milvus：无法表达企业项目结构与故障因果关系，退化为纯语义搜索 → 否决
- 只用 Neo4j + 全文索引：长文本语义召回弱 → 否决
- 引入 LangChain/LlamaIndex 全家桶：v1 只需两条检索路径，框架抽象反而增加排障成本 → 否决（仅借鉴其 chunking 思路）

---

## R3. RAG 文档摄入管道

**Decision**: 上传文档 → 存 MinIO → 解析为纯文本 → 规则化分块（按标题/段落，约 500~800 字、100 字重叠）→ 批量写入 Milvus；同时用 LLM 对每篇文档抽取实体与关系候选，经人工可忽略的简单校验后写入 Neo4j。摄入为**同步 v1**（文档量小），任务状态记录在 MySQL `kb_ingest_jobs`。

**Rationale**: v1 文档量有限，同步管道最简单且状态可见；LLM 抽实体是图谱冷启动的最低成本方式。

**Alternatives considered**: 异步任务队列（Celery/Redis）——v1 数据量不需要，列入后续演进。

---

## R4. Bug 定位与 Patch 生成流水线

**Decision**: 四步流水线（`services/bug_analysis.py`）：

1. **范围收敛**：根据 Bug 描述 + 项目文件树，用关键词/BM25 式文本匹配筛出候选文件（Top-N，默认 20），避免整库塞入上下文
2. **上下文组装**：读取候选文件（截断至 token 预算），与 Bug 描述、报错文本、RAG 检索到的相关运维知识一起构成提示
3. **模型生成**：要求模型输出结构化结果：`定位文件:行号` + `根因解析` + `修复建议` + **unified diff 格式的 Patch**
4. **补丁校验**：在项目副本上执行 `git apply --check`（无 git 时用 `patch --dry-run`），成功则标记"可应用"，失败则自动重试一轮（附错误信息），仍失败则按 FR-012 明确告知失败与所需补充信息

**Rationale**: unified diff 是通用可应用格式（对应 spec Assumption「可直接复制应用」）；`--check` 干跑校验以最低成本兑现 SC-005（80% 应用成功率的可度量前提）；范围收敛解决超大上下文问题（也回应 Edge Case 中的超大仓库）。

**Alternatives considered**:
- 向量检索代码（code embedding）：需额外索引与语料调优，v1 关键词召回已能覆盖 → 列为 v2
- Agent 多轮自主改码（读-改-测循环）：复杂度高、v1「先跑通核心」不匹配 → 否决
- 只给建议不给补丁：违背 FR-011 核心需求 → 否决

---

## R5. 源码接入的两种方式与安全边界

**Decision**:
- **上传**：前端多选文件/压缩包 → 后端解压至 `data/projects/<project_id>/`（防 zip-slip：规范化路径并校验前缀）
- **路径接入**：用户在页面填写本地绝对路径，**后端进程需与该路径同机或挂载可达**；后端校验路径存在、可读、且位于允许的根目录列表 `INGEST_ALLOWED_ROOTS`（环境变量，默认空 = 拒绝一切路径接入，需显式配置）

**Rationale**: 「在页面输入项目源码路径」的自然语义是读取服务器/本机路径，因此必须有 allowlist 否则等同任意文件读取漏洞；allowlist 默认拒绝符合最小权限原则。

**Alternatives considered**: 前端通过浏览器直接读本地目录（File System Access API）——兼容性与体验不稳，且用户明确要求"页面端输入路径" → 否决。

---

## R6. 流式交互协议

**Decision**: **SSE（HTTP 单向流）** 用于（a）对话回复增量输出、（b）分析任务进度事件。命令类操作用普通 REST。心跳 + 断线后前端提示"连接中断，可重试"。

**Rationale**: 交互均为服务端→客户端单向推送，SSE 比 WebSocket 简单、可被标准 HTTP 中间件/代理承载、前端 EventSource 免手动断线重连管理；符合 FR-014 与 Edge Case「分析中离开页面/重复提交」的幂等处理（任务有 id，重复提交返回同一任务）。

**Alternatives considered**: WebSocket——双向能力用不到，复杂度更高 → 否决；轮询——首响与进度体验差 → 否决。

---

## R7. 数据一致性与状态机

**Decision**: 业务数据全部落 MySQL，InnoDB 事务；Bug 分析任务状态机：`PENDING → LOCATING → GENERATING → VALIDATING → SUCCEEDED | FAILED`，状态迁移仅由后端推进，前端只读渲染。项目接入幂等：同名文件夹/重复路径以唯一约束 + 409 提示（对应 Edge Case）。

**Alternatives considered**: 无状态全内存——服务重启丢失会话与分析结果，违背 FR-015 → 否决。

---

## R8. 测试与验证策略

**Decision**: pytest 三层（unit：services/rag 纯逻辑；contract：FastAPI TestClient 验证 `contracts/api.md`；integration：Testcontainers 拉起 MySQL/Milvus/Neo4j/MinIO 跑通摄入+检索+分析）；前端 Vitest 测组件与 API client。端到端验收以 `quickstart.md` 的手工脚本 + 一个含已知缺陷的示例项目为准（支撑 SC-004/SC-005）。

**Rationale**: 契约测试直接锚定本阶段产出的 contracts，防止前后端漂移；示例缺陷项目是 SC-004/005 的唯一可复现载体。

---

## R9. 部署与配置

**Decision**: `docker-compose.yml` 编排 mysql、milvus(含 etcd/minio 依赖)、neo4j、minio、backend、frontend；配置统一走环境变量（`.env`），包含 LLM key/base_url/model、INGEST_ALLOWED_ROOTS、各服务连接串。开发模式允许后端本地直跑 + compose 只起基础设施。

**Rationale**: 四个基础设施是本地开发的主要摩擦点，compose 一键起；环境变量是 Python/容器生态的最低共识配置方式。

**Alternatives considered**: K8s/Helm——单用户 v1 过度 → 否决。
