# TODO — PcbKnowledge 第一轮 MVP：Evidence-first 纵向闭环

> 状态：`IN_PROGRESS` — M0 已于 2026-08-08 完成，M1 已于 2026-08-09 完成，M2 尚未开始
> 创建日期：2026-08-08  
> 目标阶段：第一轮 MVP，属于正式架构 P0 的最小可运营子集  
> 执行入口：本文件  
> 长期产品说明：[PcbKnowledge_INTERNAL_OVERVIEW.md](PcbKnowledge_INTERNAL_OVERVIEW.md)  
> 架构基线：[PcbKnowledge_ARCHITECTURE.md](PcbKnowledge_ARCHITECTURE.md)

---

## 1. 本 TODO 的职责

本文件把架构基线收敛为第一轮可以实现、验证和演示的纵向切片。它负责记录：

- MVP 的边界、顺序和依赖；
- 每个里程碑的交付物与验收门槛；
- Current 与 Target 的外部系统假设；
- 实施期间尚未完成的工作和验证收据。

本文件不是新的架构 authority。若它与正式架构文档、生产代码、数据库迁移、OpenAPI、测试或已提交的
checker 不一致，以后者为准，并在同一变更中修正本 TODO。

实施过程中，每完成一项即更新 checkbox，并在“运行台账”记录非平凡验证命令、退出码、case 数和首个失败。
MVP 完成后，将长期结论移入 `README.md`、`docs/`、ADR、OpenAPI 和运维文档，然后删除本执行 TODO；历史由 Git
保留。

---

## 2. MVP 结果定义

第一轮 MVP 必须让一份获准处理的公开 PDF 完成以下闭环：

```text
合法上传
→ 服务端 SHA-256 校验与不可变保存
→ 建立 Document / DocumentRevision
→ 解析页面、文本与缩略图
→ 绑定 Manufacturer / Component / OrderablePart / Package
→ 在 PDF 页面框选 EvidenceAnchor
→ 创建结构化候选事实
→ Data Curator 核验证据
→ Domain Reviewer 批准并发布
→ typed API 与全文检索返回同一事实
→ 用户从结果跳回准确页码和区域
→ 全流程具有权限检查、审计事件和可重复的 golden test
```

MVP 的演示结果必须证明：

1. Published 事实不是模型自由文本，而是经过 Schema 校验、证据绑定和人工审核的不可变版本；
2. 相似 MPN、不同 package、旧 document revision 和无资料查询不会被静默混合；
3. 查询可以返回 `FOUND`、`CONFLICTED`、`UNKNOWN`、`ACCESS_DENIED` 或 `STALE`，未知不会被补猜；
4. PcbKnowledge 停止运行不会影响 PCBAtlas/PcbCore 的本地板卡打开、编辑或验证能力；
5. MVP 不以向量数据库或 LLM 为前置条件。

---

## 3. 第一轮范围

### 3.1 必须实现

- 模块化单体 API、独立 Worker、Curator Web；
- PostgreSQL 作为唯一事务事实源；
- SeaweedFS S3 API 作为内容寻址 Evidence Vault；
- Keycloak OIDC 身份和最小角色/项目隔离；
- PDF 上传、hash、去重、解析、页元数据与缩略图；
- Manufacturer、Component、OrderablePart、Package、Pin 的最小实体目录；
- `EvidenceAnchor` 的页码和 `[0,1]` 归一化区域；
- 两个正式知识 Schema：
  - `ComponentPinFactV1`；
  - `PackageDimensionFactV1`；
- Draft、Curator Verify、Engineer Approve、Publish、Supersede 的审核主链；
- Published record 不可原地修改；
- exact metadata lookup、identifier lookup 和 PostgreSQL FTS；
- 以下最小 Agent typed API：
  - `resolve-component`；
  - `get-pin-spec`；
  - `get-package-dimensions`；
  - `search-evidence`；
- 最小 `EvidenceBundle`，包含 resolved subject、事实、冲突/缺失、证据和 retrieval trace；
- append-only audit、PostgreSQL job queue、transactional outbox；
- extraction/retrieval/permission golden fixtures 与可重复回归；
- Docker Compose 本地开发环境、迁移、备份/恢复 smoke 和基础可观测性。

### 3.2 明确不实现

- embedding、pgvector、dense retrieval、reranker；
- LLM 自动抽取、自动摘要或自动发布；
- OCR 质量承诺；纯扫描 PDF 进入 `NEEDS_MANUAL_PREPARATION`；
- MCP Adapter、通用 `/agent/ask` 或新的 Agent executor；
- KnowledgeSnapshot 和正式长任务 pinning；在该能力完成前不得宣称支持可复现生产 Agent run；
- BoardPatch、ValidationReport 回写、自动布局、自动布线或 PCB mutation；
- DesignMission、RequirementGraph、EngineeringSkill、EvidenceGraph、SignoffMatrix runtime；
- Conflict Center 的完整裁决 UI；MVP 只做冲突检测、阻断默认 authoritative result 和基础详情展示；
- PCN/lifecycle、替代料、waiver、板厂 profile、历史案例；
- 微服务、Kubernetes、Kafka、Redis/Celery、OpenSearch、Neo4j、Temporal；
- 付费 IPC 标准的解析、全文索引、embedding 或模型处理；
- 面向公众的多租户 SaaS 和移动端 UI。

### 3.3 MVP 数据集

仓库内只放可合法再分发的 synthetic/open fixtures，不提交受限厂商全文：

- 2 个 synthetic 或明确开放许可的 component；
- 每个 component 至少 1 个 PDF revision，其中 1 个 component 具有前后两个 revision；
- 1 个同 family 不同 MPN 的负例；
- 1 个同 MPN 不同 package 的负例；
- 1 组有意冲突的 pin 或 dimension 候选；
- 1 个重复上传样本；
- 1 个 encrypted/corrupt/unsupported PDF 负例；
- 2 个隔离 project，用于跨项目权限负例；
- 不少于 10 个 golden extraction/retrieval/permission cases。

真实 datasheet 只通过开发环境导入，不默认纳入 Git fixture。

---

## 4. 外部仓库边界

### 4.1 当前可以依赖的事实

- PcbCore 拥有 live board、canonical identity、精确几何、DRC/connectivity、transaction 和 history；
- PcbCore 的 `ComponentLibraryCore` 当前消费 caller 已经新鲜核验的 typed evidence receipt；
- PCBAtlas 已有 `CommandGateway`、AI tool catalog、provider runtime、审批和运行 trace；
- PCBAtlas/PcbCore 的协议与 source-root 状态由各自仓库的生产代码、manifest、checker 和 DevDocs 管理。

### 4.2 不能当作当前能力的目标

- PCBAtlas `BoardPatch` 仍是待实现产品合同；
- raw `PcbDomainPatch` 是 PcbCore 内部底层结构，不是 Agent 或知识平台 wire contract；
- 通用 `BoardContext`、`ValidationReport`、DesignStateGraph、EvidenceGraph 和 SignoffMatrix 尚不能按名字推断为已发布跨仓 API。

### 4.3 MVP 集成政策

- PcbCore 和 PCBAtlas 均不链接、不导入、不等待 PcbKnowledge；
- MVP 只发布独立 REST/OpenAPI contract，不修改兄弟仓库；
- 不在 PcbKnowledge 发明 PcbCore mutation schema；
- PcbKnowledge 的 `EvidenceAnchor` 是文献证据定位，不冒充 PcbCore 的 domain-exact validation receipt；
- 后续对接 `ComponentLibraryCore` 时，通过独立 adapter 将已发布事实和 source/anchor digest 转换为调用方核验的
  evidence receipt；不得声称 C++ pure-value struct 已经存在通用 JSON wire codec；
- 开始任何跨仓实现前，重新读取兄弟仓库当时的 Current 文档、生产类型、manifest 和 checker，不能依赖本 TODO
  的历史快照。

---

## 5. 固定工程原则

- Evidence-first：Published record 至少绑定一个有效 `EvidenceAnchor`；
- Structured-first：精确事实先走 typed schema 和 exact filter，FTS 只做证据发现；
- Unknown is valid：不存在资料时返回 UNKNOWN，不使用相似器件或模型常识补齐；
- Immutable publication：Published version 只允许 supersede/withdraw，不允许 UPDATE payload；
- No silent conflict resolution：冲突显式保存和返回；
- Security before ranking：ACL、license、project、MPN/package/revision 过滤先于全文排名；
- Source bytes are untrusted data：PDF 内容不能改变系统提示、权限、工具或审核政策；
- Permanent vs derived：原文件、版本、anchor、record、review、audit 为永久资产；解析块、缩略图、FTS 为可重建资产；
- Fail closed：hash、schema、权限、revision、evidence、review 或 audit 任一失败均不得发布；
- Contract-first：OpenAPI/Pydantic 是 API 真源，TypeScript client 自动生成，前端不手写重复 DTO；
- No hidden fallback：不得用 SQLite、内存对象存储、匿名管理员或自由文本记录替代生产路径并宣称 MVP 通过。

---

## 6. 里程碑与执行顺序

里程碑必须按 `M0 → M1 → M2 → M3 → M4 → M5` 推进。允许在同一里程碑内并行，但后续里程碑不得绕过前置
completion gate。

### M0 — 仓库、契约和开发基线

目标：形成可重复启动、可静态验证、没有业务假实现的 monorepo 骨架。

- [x] 建立架构文档规定的 `apps/`、`packages/`、`src/pcbknowledge/`、`migrations/`、`deploy/`、
  `knowledge-schemas/`、`evals/`、`docs/` 目录；
- [x] 建立根 `README.md`、`AGENTS.md`、`.gitignore`、许可证与安全说明；
- [x] 初始化 Python 3.14 + `uv`，提交 `pyproject.toml` 与 `uv.lock`；
- [x] 初始化 Node.js 24 LTS + `pnpm` workspace，提交 lockfile；
- [x] 初始化 React/TypeScript/Vite/MUI Web shell；
- [x] 初始化 FastAPI API 与 Worker 入口；
- [x] 固定 Ruff、mypy、pytest、ESLint、TypeScript、Vitest 和 Playwright 的入口；
- [x] 建立 OpenAPI 生成 TypeScript client 的唯一流程；
- [x] 建立 configuration schema，secret 只来自受控运行时注入，不进入 Git；
- [x] 把架构基线列出的 ADR-001 至 ADR-017 建立为独立文件；MVP 无关 ADR 可以保持 Accepted/Deferred，
  但不得缺失决策状态；
- [x] 建立基础 CI：格式、lint、type check、unit test、migration smoke、frontend build；
- [x] 校验架构文档中的固定依赖在当前日期仍兼容；需要改变时先写 ADR，不静默漂移。

M0 completion gate：

- [x] 空数据库环境可以通过单一文档化命令启动；
- [x] API、Worker、Web 均有健康检查；
- [x] OpenAPI client 可重复生成且 `git diff` 为空；
- [x] 所有 lint/type/unit/build 基线通过；
- [x] 尚无伪造的业务 success endpoint 或内存 fallback。

### M1 — 平台脊柱：数据库、对象存储、身份、任务和审计

目标：先建立所有后续领域功能共用的可靠边界。

- [x] Compose 启动 PostgreSQL、SeaweedFS、Keycloak、Caddy、API、Worker、Web 和 OTel Collector；
- [x] 建立 UUIDv7、UTC `timestamptz`、RFC 3339 和统一错误类型；
- [x] 建立 organization/project/external subject mapping；
- [x] 实现 OIDC Authorization Code + PKCE 和 service account 校验；
- [x] 实现 `DATA_CURATOR`、`DOMAIN_REVIEWER`、`KNOWLEDGE_ADMIN`、`AUDITOR`、`AGENT_SERVICE`；
- [x] 建立 RBAC + organization/project/access-scope 应用层授权；
- [x] 建立 PostgreSQL RLS 纵深防御和跨项目 negative tests；
- [x] 建立 source organization、license policy、access scope；
- [x] 建立 append-only `audit_event`，应用角色无 UPDATE/DELETE 权限；
- [x] 建立 `knowledge_job` 的 lease、`FOR UPDATE SKIP LOCKED`、幂等、重试和 dead letter；
- [x] 建立 transactional outbox；
- [x] 建立对象存储 adapter、content-addressed key 和预签名上传；
- [x] 接入结构化日志、trace ID 和基础指标；日志禁止包含 token、原文全文和机密 payload。

M1 completion gate：

- [x] 两个 project 的用户不能互查对象、原文、审计或 job；
- [x] service account 与浏览器用户权限边界不同且可测试；
- [x] job lease 超时可恢复，同一 idempotency key 不重复产生领域副作用；
- [x] 审计写失败会使受审计业务事务失败；
- [x] 对象读取必须经过授权和审计，不能通过 object key 绕过 API。

### M2 — Intake 与不可变 Evidence Vault

目标：可靠地接收 PDF 并生成可审核的页面资产，不创建知识事实。

- [ ] 建立 `Document`、`DocumentRevision`、`DocumentAsset`、`DocumentPage`、`ParsedDocument`；
- [ ] 实现五步上传向导的 MVP 版本：文件、来源/许可、文档身份、实体候选、确认；
- [ ] 浏览器直传 staging，完成后由 Worker 流式计算 SHA-256；
- [ ] 实现 organization 内字节级去重，但保留逻辑文档/revision alias 和审计；
- [ ] 校验 MIME/magic bytes、大小、页数、加密、嵌入附件和 PDF action；
- [ ] 解析器在无网络、只读输入、CPU/内存/时长受限的进程或容器中执行；
- [ ] 用内部 `CanonicalDocumentV1` 包装 Docling 结果，不向领域层泄漏第三方格式；
- [ ] 用 pypdfium2 生成页级 WebP 缩略图和兜底页面检查；
- [ ] 原生文本 PDF 生成 page text/block；
- [ ] 纯扫描、加密、损坏和不支持文档进入明确失败/人工准备状态；
- [ ] 保存 parser name/version/config hash/artifact hash 和 warnings；
- [ ] 原始文件按 SHA-256 内容寻址，不允许原地覆盖。

M2 completion gate：

- [ ] 相同 bytes 重复上传不会产生第二份原始对象；
- [ ] revision metadata 仍能表达两个逻辑引用，且不会删除已被引用 revision；
- [ ] hash 不匹配、encrypted/corrupt/oversized 输入 fail closed；
- [ ] 任一页面可以加载原始 PDF、缩略图和解析文本；
- [ ] 删除全部解析/缩略图派生物后可以从原始 PDF 重建。

### M3 — 实体、EvidenceAnchor、审核与不可变发布

目标：把页面证据变成最小的已审核 typed knowledge。

- [ ] 建立 Manufacturer、Component、OrderablePart、Package、Pin、Alias；
- [ ] 保留原始 MPN 字符串；标准化键只用于查询，不覆盖原值；
- [ ] family/base part/orderable part/package 分离，不从 suffix 猜 silicon/package 事实；
- [ ] 建立实体解析任务、候选评分、人工确认和 merge redirect 审计；
- [ ] 建立 `EvidenceAnchor`：1-based page、`PDF_NORMALIZED_V1`、bbox、section/table/row/column、quote hash；
- [ ] 服务端验证 `0 <= x0 < x1 <= 1`、`0 <= y0 < y1 <= 1` 和 page/revision 一致性；
- [ ] PDF.js + SVG overlay 实现缩放/旋转不漂移的 anchor 展示与框选；
- [ ] 定义并版本化 `ComponentPinFactV1`、`PackageDimensionFactV1` JSON Schema/Pydantic union；
- [ ] 数值和单位结构化保存，MVP 使用 UCUM 可表达单位；
- [ ] 建立 `KnowledgeRecord` 稳定身份与 immutable `KnowledgeRecordVersion`；
- [ ] 建立 record subject/evidence/condition/applicability/relation；
- [ ] 建立 review task、assignment、decision、risk policy 和 ETag/`If-Match`；
- [ ] Pin 和 package dimension 必须经过 Curator Verify 与 Engineer Approve；
- [ ] Published 事务同时写 record version、review decision、audit 和 outbox；
- [ ] 修正只能创建新 version 并 supersede，不能覆盖 Published payload；
- [ ] 按语义键检测冲突；unresolved conflict 阻止默认 authoritative result；
- [ ] Review Workbench 实现 page rail、PDF canvas、record inspector、evidence/history/audit bottom dock 的最小闭环。

M3 completion gate：

- [ ] 数据库约束和应用策略都禁止“无 evidence 发布”；
- [ ] Data Curator 无法批准高风险事实；
- [ ] 并发编辑产生可见 ETag conflict，不静默覆盖；
- [ ] anchor 在不同窗口尺寸和 PDF zoom 下指向同一区域；
- [ ] Published version 的 UPDATE 被数据库权限或领域层拒绝；
- [ ] 新旧 revision 的证据不自动迁移；
- [ ] conflict 不被 authority score 静默隐藏。

### M4 — Exact/FTS 检索与 typed Agent API

目标：让人和未来 Agent 精确查询已审核事实，并解释命中、冲突和缺失。

- [ ] 建立 identifier normalization，MPN/package/document number 不做自然语言 stemming；
- [ ] 建立 English/simple FTS 与 Unicode bigram 派生索引；
- [ ] 搜索候选先经过 organization/project/license/effective time/entity/package/review state hard filter；
- [ ] 实现 cursor pagination、bounded result 和 retrieval trace；
- [ ] 实现 `POST /api/v1/agent/resolve-component`；
- [ ] 实现 `POST /api/v1/agent/get-pin-spec`；
- [ ] 实现 `POST /api/v1/agent/get-package-dimensions`；
- [ ] 实现 `POST /api/v1/agent/search-evidence`；
- [ ] 定义最小 `EvidenceBundleV1`，显式返回 status、resolved subjects、facts、conflicts、missing information、evidence；
- [ ] evidence item 返回 document revision、1-based page、bbox、quote、authority、review state 和 source hash；
- [ ] 默认不返回整本 PDF；原页读取使用独立授权、页数预算和审计；
- [ ] 建立 Knowledge Explorer、Search、record history、source preview 和 JSON export；
- [ ] API 使用 `application/problem+json`、snake_case、UUID、OpenAPI 3.1；
- [ ] 前端所有请求使用生成 client 和 TanStack Query，不在组件直接 `fetch`。

M4 completion gate：

- [ ] 精确 MPN + package 查询不会返回同 family 的其他器件；
- [ ] 旧 revision/effective time 不会混入当前结果；
- [ ] 无数据返回 `UNKNOWN`，不返回模型补全或近似 fact；
- [ ] unresolved conflict 返回 `CONFLICTED` 并列出冲突成员；
- [ ] 无权访问时不泄漏对象是否存在、标题、snippet、count 或 timing-sensitive detail；
- [ ] 查询结果可以从 UI 准确打开原文页面和 anchor。

### M5 — Golden eval、恢复与 MVP 发布门禁

目标：用可重复证据证明整条链成立，而不是只完成页面演示。

- [ ] 建立 synthetic/open PDF fixtures、manifest、hash 和许可说明；
- [ ] 建立 extraction、retrieval、permission golden case schema；
- [ ] 建立 Eval Center 最小结果页和失败分类；
- [ ] 建立 API/Worker 领域单元测试；
- [ ] 使用真实 PostgreSQL 和 S3-compatible 服务做 integration tests，不以 SQLite 替代；
- [ ] 建立 migration forward/backward smoke；
- [ ] 建立 RLS/ACL、job lease/idempotency、object hash/integrity 测试；
- [ ] 建立 PDF overlay screenshot regression；
- [ ] 建立 Playwright 纵向流程：上传 → 解析 → 实体 → anchor → 候选 → 双角色审核 → 发布 → typed query → 原文回跳；
- [ ] 建立 wrong-MPN、wrong-package、wrong-revision、unknown、conflict 和 cross-project negative cases；
- [ ] 建立 PostgreSQL 备份/PITR 配置和一次隔离恢复 smoke；
- [ ] 恢复后随机重算原始对象 SHA-256，并验证 Published evidence 和审计链；
- [ ] 删除并重建 FTS/thumbnail/parsed-derived 资产，证明永久资产独立；
- [ ] 建立基础容量 smoke：至少 100 revisions、10,000 parsed blocks、10,000 record versions；
- [ ] 生成一份不含机密内容的 MVP 验收报告。

M5 completion gate：

- [ ] Published record 无 evidence 数量为 0；
- [ ] cross-project leakage 数量为 0；
- [ ] wrong-entity/wrong-package/wrong-revision golden failures 数量为 0；
- [ ] unsupported-answer 数量为 0；
- [ ] 纵向 Playwright 流程通过；
- [ ] backup restore smoke 通过；
- [ ] FTS/派生物重建后 typed query 语义结果一致；
- [ ] API p95、FTS p95 和 draft-save p95 在架构基线目标内；
- [ ] 未运行的 heavy、外部语料或真实厂商数据验收被明确列出，不能记作通过。

---

## 7. MVP 数据模型最小集合

以下表必须通过 Alembic migration 建立；可以按模块拆表，但不能用一个通用 JSON 文档表代替全部领域关系：

```text
identity.organization
identity.project
identity.external_subject

source.source_organization
source.license_policy
source.access_scope

document.document
document.document_revision
document.document_asset
document.document_page
document.parsed_document
document.parsed_block
document.evidence_anchor

catalog.manufacturer
catalog.component_family
catalog.component
catalog.orderable_part
catalog.package
catalog.component_package
catalog.pin
catalog.entity_alias
catalog.entity_resolution_task
catalog.entity_redirect

knowledge.knowledge_record
knowledge.knowledge_record_version
knowledge.record_subject
knowledge.record_evidence
knowledge.record_condition
knowledge.record_applicability
knowledge.record_relation

workflow.review_task
workflow.review_assignment
workflow.review_decision
workflow.knowledge_conflict

search.search_document
search.search_chunk
search.index_version
search.retrieval_run

evaluation.golden_case
evaluation.evaluation_run
evaluation.evaluation_result

audit.audit_event
platform.knowledge_job
platform.outbox_event
```

所有 organization/project-scoped 表都必须显式携带或可无歧义关联 access scope；不得只靠前端过滤。

---

## 8. MVP UI 最小路由

```text
/dashboard                 任务、审核、失败和冲突摘要
/intake                    上传队列
/intake/new                五步上传向导
/documents                 文档库
/documents/:revisionId     文档详情与 revision 链
/review                    审核队列
/review/:taskId            Review Workbench
/entities/resolve          Entity Resolver
/knowledge                 Knowledge Explorer
/knowledge/:recordId       记录、证据、版本和冲突
/search                    Evidence Search
/evals                     Golden eval 结果
/audit                     Audit Explorer
/admin/jobs                Job Monitor
```

MVP 不要求完整视觉打磨，但必须满足 1440 × 900、键盘可达、加载/空/失败/无权状态明确，以及 anchor 的视觉准确性。

---

## 9. 发布门禁

以下任一失败阻止 MVP 标记完成：

- migration、schema 或 OpenAPI compatibility 失败；
- Published record 缺 evidence、subject、license、access scope、review decision 或 audit；
- Curator 可以绕过 Engineer approval 发布高风险事实；
- 相似 MPN、不同 package、旧 revision 或跨项目数据被错误返回；
- conflict 被静默选成唯一事实；
- unknown 被相似器件或自由文本补全；
- 原始对象 hash/readback 不一致；
- job 重试产生重复领域副作用；
- ETag conflict 被覆盖；
- backup restore 或派生索引重建失败；
- PDF/解析文本可以改变权限、审核或工具策略；
- 前端存在绕过生成 client 的业务 `fetch`；
- 任何测试使用 production fallback，而实际部署路径未被覆盖。

---

## 10. Definition of Done

第一轮 MVP 只有同时满足以下条件才算完成：

- [ ] M0–M5 所有 completion gate 关闭；
- [ ] 至少一份开放/synthetic PDF 完成完整纵向闭环；
- [ ] 至少一条 `ComponentPinFactV1` 和一条 `PackageDimensionFactV1` 被双角色审核并发布；
- [ ] 发布后的事实可以通过 typed API 精确查询并跳回原文；
- [ ] supersede、conflict、unknown、access denied、stale 都有 executable negative coverage；
- [ ] 所有永久资产可备份恢复，所有 MVP 派生资产可删除重建；
- [ ] 本地环境从空目录/空 volume 按 README 可以重复启动；
- [ ] OpenAPI、数据库迁移、Schema、UI 和 tests 对同一状态机与字段语义一致；
- [ ] 安全、许可证、审计和数据外发策略已文档化；
- [ ] 没有 LLM、vector、MCP、BoardPatch 或 sibling-repo mutation 被暗中纳入完成口径；
- [ ] MVP 验收报告列出命令、版本、fixture hash、case 数、耗时、失败和未运行项；
- [ ] 长期结论已迁移到稳定文档，本 TODO 已删除。

---

## 11. 已知风险与预先决策

| 风险 | MVP 决策 |
|---|---|
| 技术版本在开工时发生变化 | M0 核对官方兼容性；变化通过 ADR，不静默升级或降级 |
| PDF parser 对复杂表格不稳定 | 原文件和 anchor 为 authority；解析结果可重建，允许人工录入 |
| 扫描 PDF OCR 误差 | MVP 不承诺 OCR，进入人工准备状态 |
| MPN/package 错配 | exact entity/package filter 是 hard guard，不用相似度修复 |
| 许可证或 AI/TDM 限制 | 上传时必填策略；禁止处理的资料不进入 parser/index/model |
| 审核者并发覆盖 | ETag/If-Match + 字段 diff，禁止 silent merge |
| 对象存储与数据库不一致 | staging + hash verify + transaction/outbox + orphan reconciliation |
| Published 事实后来发现错误 | withdraw 或新 version supersede，保留历史和引用 |
| 与 PcbCore Evidence 概念重名 | 文献 anchor 与 domain validation receipt 分层，adapter 显式转换 |
| MVP 被误当生产 Agent 知识快照 | KnowledgeSnapshot 未实现前明确禁止正式长任务 pinning 声明 |
| cleanup scope 超过单轮上限时固定排序可能饥饿后序租户 | M1 记录为非阻断扩展债务；生产规模前改为按最老待办排序或持久游标并增加公平性回归 |

---

## 12. 运行台账

开始实施后按以下格式追加当前未完成阶段的验证收据；不要把截断、中断或未运行记为通过：

```text
日期：
里程碑/任务：
命令：
退出码：
case 数：
耗时：
结果：
首个失败：
下一步：
```

```text
日期：2026-08-08
里程碑/任务：M0 版本兼容性基线
命令：Python/uv/Node/pnpm/PostgreSQL/Docker Compose 版本检查；官方发布页复核
退出码：0
case 数：7 个运行时/工具版本
耗时：< 2s（不含网页复核）
结果：Python 3.14.6 host / 3.14.7 image、uv 0.12.3、Node 24.19.0
      validation / 24.11.1 image、pnpm 11.20.0、PostgreSQL 18.4、Compose 5.3.1；
      架构固定 major 均保留。OpenAPI generator 要求 TypeScript 5.x，因此锁定 5.9.3；
      架构未固定 TypeScript major，无 ADR 漂移。
首个失败：无
下一步：以 lockfile 和镜像实际构建验证兼容性

日期：2026-08-08
里程碑/任务：M0 后端、契约和迁移
命令：uv sync --frozen --all-groups；ruff format/check；mypy src apps tests；pytest；
      pcbknowledge-openapi --check；Alembic downgrade base / upgrade head（真实 PostgreSQL）
退出码：全部 0
case 数：17 pytest；1 个 migration round trip；2 个 contract drift check
耗时：pytest 0.24s；migration round trip 2.8s
结果：通过；OpenAPI 3.1 仅含 health/readiness，server 为 /api/v1；迁移 head 为
      20260808_0001。
首个失败：无
下一步：验证浏览器生成合同和部署路径

日期：2026-08-08
里程碑/任务：M0 Curator Web 与生成 client
命令：pnpm install --frozen-lockfile；pnpm check:generated；pnpm lint；pnpm typecheck；
      pnpm test；pnpm build；pnpm test:e2e
退出码：全部 0
case 数：25 Vitest + 2 Playwright
耗时：Vitest 1.48s；build 0.58s；Playwright 1.3s
结果：通过；生成合同 SHA-256 为
      2cd16d33d34c118b562ea04c7fa684a9ca4d1973db57ad7da0acb724fbc01663。
      组件业务 fetch 调用为 0。Vite 报告约 675 KB 首包警告，M0 不宣称性能达标。
首个失败：Playwright 初次缺 Chromium；安装匹配版本后 2/2 通过
下一步：从空 volume 验证真实栈

日期：2026-08-08
里程碑/任务：M0 空 volume Compose、健康和失败关闭
命令：删除本轮专用四个 Compose volume 后执行 ./deploy/scripts/dev-up.sh；curl health/ready；
      Keycloak discovery；Prometheus/Grafana/OTel health；SeaweedFS anonymous request；
      停止/恢复 PostgreSQL 后重复 API 与 Worker probe
退出码：最终冷启动及恢复全部 0；依赖中断时 Worker 预期退出 1
case 数：9 services；4 API health paths；1 migration head；2 fail-closed probes
耗时：缓存镜像后的最终空 volume 启动约 34s
结果：最终单命令冷启动通过；API/Worker/Web/Caddy/PostgreSQL/SeaweedFS healthy；
      Keycloak realm 可发现；Prometheus、Grafana、OTel ready；匿名 S3 返回 403；
      PostgreSQL 中断时 liveness=200、readiness=503 problem+json、Worker not_ready，
      恢复后均重新 ready。
首个失败：首次发现 PostgreSQL 18 旧数据挂载路径；随后发现 BusyBox grep 长参数和
      Prometheus false flag；均已修正，最终从新建 volume 重跑通过
下一步：M0 提交/推送后进入 M1 平台脊柱

日期：2026-08-09
里程碑/任务：M1 后端静态门禁、hermetic 回归与合同漂移
命令：ruff format --check .；ruff check .；mypy src apps tests；排除明确外部依赖用例的 pytest；
      pcbknowledge-openapi --check；git diff --check
退出码：全部 0
case 数：112 pytest，0 skipped；mypy 检查 102 个 source files；1 个 OpenAPI drift check
耗时：hermetic pytest 0.57s；其余命令未单独记录总耗时
结果：通过；队列 metadata 拒绝 float 与敏感 payload；job/outbox 在 claim、effect、complete、publish
      边界重算 payload digest，损坏载荷 fail closed；OpenAPI 与生成 client 一致。
首个失败：最终稳定门禁无失败
下一步：以真实 PostgreSQL 18、实际 runtime login 和 SeaweedFS 3.85 验证权限与副作用边界

日期：2026-08-09
里程碑/任务：M1 PostgreSQL、runtime role、outbox worker 与对象存储真实依赖验收
命令：CI 同款 PostgreSQL integration suites；分别以 pcbknowledge_app / pcbknowledge_worker LOGIN
      运行 test_database_contract_postgres.py；运行 storage cleanup worker PostgreSQL + SeaweedFS E2E；
      运行 test_storage_seaweedfs.py；执行 fresh 0001→0008、0008→0007→0008 和 legacy 0006→0008
退出码：全部 0；带 verified receipt 的 0008→0007 downgrade 按合同返回 SQLSTATE 23514
case 数：17 jobs/outbox/security PostgreSQL + 4 cleanup E2E + 2 app contract + 2 worker contract
      + 1 SeaweedFS；全部 0 skipped
耗时：cleanup E2E 4 cases 为 0.61s；其余命令未单独记录总耗时
结果：通过；旧 receipt 的 lease attempt/owner 保持 UNKNOWN，不猜历史；新 receipt 必须绑定仍有效的
      worker lease。应用与 worker 角色无 owner/RLS bypass/membership；worker 在同 scope 也看不到或更新不了
      非 cleanup outbox。staging 清理、失败重试、过期 sweep 和跨 project negative path 均由真实依赖覆盖。
首个失败：真实 PG 首轮有 2 个测试 SQL JSON literal 被 SQLAlchemy 当 bind 解析；改为参数化 JSONB 后
      17/17 通过，生产逻辑与数据库合同未放宽
下一步：验证浏览器、Keycloak、可观测性和空卷部署

日期：2026-08-09
里程碑/任务：M1 Curator Web、OIDC bootstrap 与生成 client
命令：Node 24 / pnpm 11 下运行 pnpm check:generated；pnpm lint；pnpm typecheck；pnpm test；
      pnpm build；pnpm test:e2e
退出码：全部 0
case 数：42 Vitest + 3 Playwright
耗时：本轮未单独记录总耗时
结果：通过；生成合同 SHA-256 为
      980e5dde0bb05251ade88eba24d2b33ee632c934eaed523bc4c25e898c9560be。
      浏览器使用 Authorization Code + PKCE，`/session` 通过同一 typed Bearer middleware 加载；
      capability 仅来自数据库可信 membership/grant。Vite 仍报告约 765 KB 首包警告，列为非阻断性能债务。
首个失败：最终 Node 24 工具链门禁无失败；宿主默认 Node 20 不作为有效验证环境
下一步：从独立空 volume 执行完整单命令启动

日期：2026-08-09
里程碑/任务：M1 独立空卷 Compose、Keycloak、可观测性与安全路由验收
命令：以 COMPOSE_PROJECT_NAME=pcbknowledge-m1-acceptance 和独立端口运行 ./deploy/scripts/dev-up.sh；
      curl health/readiness/metrics/Keycloak discovery；Prometheus targets API；数据库 catalog receipt；
      test-reconcile-realm.sh；smoke-keycloak.sh
退出码：最终全部 0
case 数：10 个长期服务；7 个显式 Docker health checks；4 个 readiness dependency checks；
      5 个 Prometheus targets；13 个 FORCE RLS relations；3 个 queue integrity triggers；
      1 次 realm drift convergence + second-run idempotency；1 组 PKCE/service-token claims smoke
耗时：未单独计时（包含当前代码的 API/Worker/Web 镜像构建）
结果：全新 PostgreSQL 从 0001 连续升级至 0008；API、Worker、Web、Caddy、PostgreSQL、SeaweedFS、
      Keycloak healthy，OTel/Prometheus/Grafana running，Prometheus 全 targets UP。`/healthz` 与
      `/readyz` 为 200；公网 `/metrics`、`/api/v1/metrics` 为 404，API 内部 `/metrics` 为 200；
      runtime roles 安全且双向 membership 为 0；Keycloak realm 漂移可收敛，service token 只有
      AGENT_SERVICE、SERVICE_ACCOUNT、正确 issuer/audience/azp。
首个失败：初次额外运行 Keycloak 漂移测试时漏带隔离端口环境，随后 smoke curl 退出 7；恢复同一
      隔离端口并重跑后两项均通过。基础空卷 dev-up 本身无失败。
下一步：提交并推送 M1；M2 尚未开始，不把 intake、PDF parsing、知识审核或检索算作当前能力
```
