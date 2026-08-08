# TODO — Git-native PCB Knowledge

> 状态：`P0.2_COMPLETE_P0.3_NEXT`
> 建立日期：2026-08-10
> 更新日期：2026-08-14
> P0.1 起始基线：`c5fe01bfb4cf3a23f8315427443f8358b79736ef`
> 前置里程碑：Git-native MVP（第 2 节）已完成
> 目标：在不恢复 Docker、登录、数据库和在线服务的前提下，把当前 Source Corpus 登记器推进为 Git-native PCB structured knowledge repository。

## 1. 文档职责与不变边界

本文件是仓库根目录唯一的 Git-native knowledge 执行路线图：维护当前阶段、未完成工作、完成门槛和必要的里程碑收据。长期产品与技术合同由 [`docs/architecture.md`](docs/architecture.md) 负责，不在这里复制为第二份架构 authority。

- Git 仓库文件仍是唯一 authority。
- PDF 继续使用实际 bytes SHA-256 content addressing。
- GUI 继续是 loopback-only Python editor，不恢复 React/Node 服务栈。
- Agent 与 GUI 共用同一 authority model 和 validator。
- Agent 可以准备/修改/送审，不能批准、提交或推送。
- working-tree approval 与 Git publication 分离；formal read 只使用 fully validated committed approved snapshot。
- `knowledge/**`/`evidence/**` 数据 commit 与 code/schema/policy commit 分离。
- PcbKnowledge 不读取或修改 PCB board state，不成为 PcbCore 运行时依赖。
- Unknown、conflict、wrong revision、wrong package 必须显式处理，不能靠模型补值。
- Vector RAG、数据库服务、MCP 均不是 P0 前置条件。

## 2. Git-native MVP — COMPLETE（历史里程碑）

MVP 完成了本机 Git-native Source Corpus editor，并关闭了旧共享服务平台。它不再是当前开发阶段，也不再使用独立 TODO；以下收据保留在本路线图中，后续状态以 P0.0–P0.4 和架构文档为准。

### 2.1 当时完成的产品边界

- [x] 产品只提供 loopback 本机 GUI，不提供局域网或公网服务，也不需要账号、密码、Keycloak、租户或数据库管理员。
- [x] 操作系统文件权限与 Git 仓库权限构成访问边界；Agent 与人类修改同一套规范化文件。
- [x] Agent 不批准、不自动 commit/push；人通过 diff 审阅后决定发布。
- [x] 缺失来源、版本、许可或原件的记录可以保持 Draft，但不能批准。
- [x] PDF 与提取文本按不可信数据处理，不能改变工具、权限、validator 或审阅规则。

### 2.2 历史 authority 与当前迁移结果

MVP 当时使用以下过渡布局：

```text
knowledge/records/<stable-id>.json
evidence/sha256/<prefix>/<digest>.pdf
schemas/knowledge-record.schema.json
```

- [x] JSON 使用 UTF-8、canonical 字段顺序和末尾换行；PDF 按实际 bytes SHA-256 内容寻址并去重。
- [x] `.pcbknowledge/`、索引、预览与 package 是可删除派生物，SQLite/FTS 不作为 authority。
- [x] 过渡记录支持 stable ID、状态机、source/license/evidence、explicit unknown、review decision、supersedes 与 canonical serialization。

`knowledge/records/` 和 Schema v2 只是历史里程碑形态。P0.0 后续增加 append-only review history、严格 published snapshot、evidence/reference concurrency hardening 和 code/data commit isolation；P0.1 已在零真实数据窗口迁移到 `knowledge/sources|entities|facts`，没有双写兼容路径。

### 2.3 GUI、Agent 与本机工作流

- [x] GUI 完成 Draft 创建/编辑、PDF 导入、submit/approve/reject、记录详情和 Git diff/untracked preview；GUI 不执行 `git add`、`git commit` 或 `git push`。
- [x] 当前这套页面的产品含义固定为 **Source Corpus editor**，不是最终 Fact Review Workbench。
- [x] 初版 CLI 完成 list/show/create/update/submit/validate/diff、稳定 idempotency key、missing fields 和 next action；后续 typed Agent 能力由 P0.2 接管。
- [x] FreeCM Config/Build/Run/Test/Package 使用本机 Python/Git，不依赖 Docker、数据库、S3 或 source dependency。
- [x] 旧 Compose、Keycloak、PostgreSQL、SeaweedFS、Caddy、在线 API、Worker、OIDC/RLS/outbox/job/storage、React/pnpm 和部署链已退役；历史 ADR 保留并由 ADR-018 标注 superseded decisions。

### 2.4 MVP completion receipt（2026-08-10）

- 首轮完整门禁唯一失败：`git diff --check` 发现架构文档 2 处行尾空格；修复后通过。
- `config`：exit 0。
- `build`：exit 0，33/33 tests passed，0 skipped，0 records validated。
- `test`：exit 0，33/33 tests passed，0 skipped；`git diff --check` 通过。
- `package`：exit 0；生成 `build/package/PcbKnowledge_aced0464d948a291.zip`，SHA-256 为 `77e66577b6f2a40cd8508fe55c674875b0bbe2d4b58cf51e7139dcf545bd04de`。
- 当时 repository-pinned FreeCM validator：exit 0，Config/Build/Run/Test/Package 五个动作均解析为 Git-native 命令；该 Node/submodule 校验链后来已从协议型仓库移除。
- 真实 Run 首秒 ready，`http://127.0.0.1:18080` 返回 HTTP 200、无登录、相关 Docker 容器数为 0，`Ctrl+C` 返回 130。
- 根启动器首次约 4 秒完成当时 33 个检查并打开首页，第二次首秒 ready。
- 旧服务未跟踪材料可恢复地移动到 `~/.Trash/PcbKnowledge-retired-service-20260810/`。

## 3. P0.0 — Git-native Core Hardening

状态：**COMPLETE**。P0.1 完成时已刷新真实 checkout 门禁 receipt。

- [x] 修复替换/清空草稿 PDF 后遗留 orphan evidence 的一致性缺陷。
- [x] 共享 evidence 不被清理；published evidence 受保护。
- [x] 仓储写入增加跨进程 lock，引用写入与 evidence cleanup 不发生静默竞态。
- [x] Schema v2 增加 append-only `review_history`。
- [x] review history 强制 `SUBMITTED -> APPROVED/REJECTED` 序列；approve 后不能继续伪造历史。
- [x] reject → edit → resubmit 不再丢失退回原因。
- [x] v2 `RESTRICTED` 作为 ADR-015 AI-processing-blocked 临时执行表示。
- [x] CLI 输出 `agent_processing_allowed`。
- [x] published reader 从同一 Git ref 校验 canonical JSON、record ID、supersedes closure、PDF bytes/hash/size。
- [x] CLI 增加 `list --published`。
- [x] change-scope 优先判断 Git index；index 为空才判断 unstaged/untracked workspace。
- [x] rename/copy 来源和目标同时参与 `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` 分类。
- [x] `MIXED` 被定义为非法单 commit。
- [x] ADR-019 固化 publication 与 change-scope 边界。
- [x] 在真实 checkout 重新执行 Config / Build / Test / Package / FreeCM validator / GUI smoke，并把新 case 数记录到本文件。

## 4. P0.1 — Typed Authority Model

状态：**COMPLETE**。自动化验收入口为
`tests.git_native.test_p01_vertical.P01SyntheticVerticalTests`。

P0.1 的目标不是做新 UI，而是把 authority 从“资料登记记录”升级为正式的 Source / Entity / Fact / EvidenceAnchor，并让 validator、published view、package 和测试全部使用同一模型。

### 4.1 Authority layout

目标布局：

```text
knowledge/
├── sources/
│   └── <source-id>.json
├── entities/
│   └── <entity-id>.json
└── facts/
    └── <fact-id>.json

evidence/sha256/<prefix>/<sha256>.pdf

schemas/
├── source-record.schema.json
├── entity-record.schema.json
└── fact-record.schema.json
```

- [x] `knowledge/records/` 在仓库零真实 record 的窗口一次性退役；不建立双写兼容路径。
- [x] legacy v2 代码只允许作为迁移提交前的内部实现历史；P0.1 completion 后 authority 只认新 roots。
- [x] `KnowledgeRepository.validate_all()` 或新的统一 repository facade 同时验证 Source/Entity/Fact 的 referential closure。
- [x] FreeCM Build/Test/Package 都覆盖新 roots 和三份 Schema。
- [x] package manifest 包含被引用 PDF，且不依赖工作树之外的隐藏状态。

### 4.2 SourceRecordV1

- [x] 独立 model、canonical JSON、stable ID、schema version。
- [x] `source_type`：DATASHEET / APPLICATION_NOTE / REFERENCE_DESIGN / PCN / FAB_CAPABILITY / INTERNAL_GUIDELINE。
- [x] title/document number/revision/publisher/locator。
- [x] 正式 license taxonomy：
  - `UNKNOWN`
  - `PUBLIC_REFERENCE`
  - `OPEN_LICENSE`
  - `INTERNAL`
  - `RESTRICTED`
  - `LICENSED_BLOCKED_FOR_AI`
- [x] 明确 `agent_processing_allowed` policy；UNKNOWN 与 LICENSED_BLOCKED_FOR_AI fail closed。
- [x] content-addressed PDF evidence。
- [x] append-only review history + current decision。
- [x] explicit supersedes，不从文件名猜 revision relation。
- [x] committed APPROVED Source 不允许原地改写/删除。

### 4.3 EntityRecordV1

P0.1 只实现能支撑第一批 datasheet facts 的最小集合。

- [x] `ManufacturerV1`：raw name + normalized key。
- [x] `ComponentV1`：manufacturer ID + raw MPN + normalized MPN key + optional family text。
- [x] `PackageV1`：raw package name + normalized lookup key。
- [x] 原始 manufacturer/MPN/package 永远保留；normalized key 仅用于 exact lookup。
- [x] 不从 MPN suffix 猜 package、silicon revision、orderable part。
- [x] entity ID 稳定，可从 Agent idempotency key 确定性创建。
- [x] entity JSON canonical、额外字段 fail closed。
- [x] 删除/改写被 Fact 引用的 entity 必须失败。

### 4.4 EvidenceAnchorV1

继续执行 ADR-013。

- [x] `source_id` 指向 SourceRecordV1。
- [x] 1-based `page`。
- [x] `coordinate_space = PDF_NORMALIZED_V1`。
- [x] bbox 满足 `0 <= x0 < x1 <= 1`、`0 <= y0 < y1 <= 1`。
- [x] `quote` 与 `quote_sha256` 一致；quote 允许 Draft 暂缺，但不能伪造 hash。
- [x] anchor 永远绑定确定 Source revision；不自动迁移。
- [x] Draft Fact 可使用 page-only/incomplete anchor；Fact approval 前每个 anchor 必须完整。

### 4.5 FactRecordV1

公共字段：

- [x] stable ID / schema version / status / prepared_by。
- [x] `fact_type` + typed payload。
- [x] subject entity IDs。
- [x] conditions/applicability 作为结构化字符串列表；P0.1 不引入规则 DSL。
- [x] one or more `EvidenceAnchorV1`。
- [x] append-only review history + current decision。
- [x] supersedes。
- [x] committed APPROVED Fact 不允许原地改写/删除。
- [x] APPROVED Fact 必须引用 APPROVED Source 和存在的 Entity。
- [x] APPROVED Fact 至少一个完整 EvidenceAnchor。
- [x] unresolved semantic conflict 必须被 validator/query layer 暴露，不能静默选 winner。

第一批 fact type：

#### ComponentPinFactV1

- [x] component ID。
- [x] package ID。
- [x] pin number/name。
- [x] primary function。
- [x] alternate functions。
- [x] conditions/applicability。
- [x] evidence anchors。

#### ParameterLimitFactV1

- [x] component ID。
- [x] parameter。
- [x] `ABSOLUTE_MAXIMUM / RECOMMENDED_OPERATING / ELECTRICAL_CHARACTERISTIC`。
- [x] minimum / typical / maximum；至少一个值存在。
- [x] unit 必填；数值使用 JSON number，不把 `30 V` 存成自由文本。
- [x] conditions。
- [x] evidence anchors。

### 4.6 P0.1 repository operations

P0.1 要提供可测试的 repository API，不要求完成 P0.2 Agent UX。

- [x] create/load/list/save Source。
- [x] create/load/list Entity。
- [x] create/load/list/save/submit/approve/reject Fact。
- [x] unified `validate_all()`：layout、canonical、identity、supersedes、evidence、entity/source refs、approval invariants。
- [x] published snapshot reader 能从一个 Git ref 返回 Source/Entity/Fact，并验证完整 closure。
- [x] content-addressed evidence cleanup 以所有 Source refs 为准，不因 Fact 改写误删 PDF。
- [x] data change scope 继续覆盖整个 `knowledge/**` 与 `evidence/**`。

### 4.7 P0.1 tests / completion gate

必须使用 synthetic/minimal fixtures；本提交不把真实厂商 PDF 当测试依赖。

- [x] Source canonical round-trip、license gate、review history。
- [x] Entity raw/normalized 分离、错误 ref/重复 ID fail closed。
- [x] EvidenceAnchor bbox/page/quote hash negative tests。
- [x] Pin Fact 和 ParameterLimit Fact payload schema tests。
- [x] Fact approval 缺 source/entity/anchor 时 fail closed。
- [x] wrong component / wrong package / wrong source ref fail closed。
- [x] supersedes missing/cycle/self reference fail closed。
- [x] committed approved Source/Fact immutable。
- [x] published reader 不读取 working-tree Draft/Approval/PDF。
- [x] package 从新 authority roots 可重复生成。

P0.1 代码完成门槛：

```text
synthetic datasheet Source
→ Manufacturer + Component + Package
→ >=5 ComponentPinFactV1
→ >=3 ParameterLimitFactV1
→ 每条 Fact 有 Source/page/bbox evidence
→ reject/resubmit history 被测试覆盖
→ Source/Fact approve
→ commit fixture in temp Git repo
→ published reader 只返回 commit 后 authority
→ validate/package 全部通过
```

说明：这是自动化 synthetic vertical test，不要求在产品仓库提交真实器件数据。

### 4.8 P0.1 completion receipt（2026-08-10）

- `python3 configs/pcbknowledge_workflow.py config`：exit 0。
- `python3 configs/pcbknowledge_workflow.py build`：exit 0；53 tests passed，0 failures，
  0 errors，0 skips；working authority 为 0 Source / 0 Entity / 0 Fact。
- `python3 configs/pcbknowledge_workflow.py test`：exit 0；53 tests passed，0 failures，
  0 errors，0 skips；`git diff --check` passed。
- `python3 configs/pcbknowledge_workflow.py package`：exit 0；生成
  `PcbKnowledge_a2f89fd66a6f5cea.zip`，SHA-256
  `c6406225fe0835ea5c995907b984d35edce06d4f04c90cd8ca0ba12ead214420`。
- 当时的 repository-pinned FreeCM validator：exit 0；FreeCM `0.1.141` validator/TypeScript
  compile passed。该 Node/submodule 校验链后来已从协议型仓库移除。
- real loopback GUI smoke：`run --port 18082 --no-browser` ready；`/healthz` 返回 `ok`；
  首页 HTTP 200，包含 CSP / `X-Frame-Options: DENY`，无登录步骤；`SIGINT` 后 exit 130。

## 5. P0.2 — Agent-native ingestion

状态：**COMPLETE**。自动化验收入口为
`tests.git_native.test_p02_agent_ingestion.P02AgentCliTests` 与
`P02SkillContractTests`。

- [x] `.codex/skills/ingest-engineering-source/SKILL.md`。
- [x] `.codex/skills/resolve-component-identity/SKILL.md`。
- [x] `.codex/skills/extract-component-facts/SKILL.md`。
- [x] `.codex/skills/prepare-knowledge-review/SKILL.md`。
- [x] CLI 增加 source/entity/fact typed commands。
- [x] Agent 输入稳定业务 key 时 create 幂等；Source/Fact 送审后 replay 不重写 review state。
- [x] 输出 conflict / unknown / missing anchor，不自由补值。
- [x] license gate 在 Agent 读取 source bytes 之前执行；普通 Source 投影不暴露 evidence path，
  `source authorize-read` 只有在 policy 与 bytes 均通过后才返回路径。
- [x] Published Fact 许可门禁与 published reader 使用同一 Git snapshot，不借用工作树许可状态。
- [x] `review-status` 验证选中 Source/Entity/Fact closure、完整锚点、许可、冲突、送审状态和
  change scope；一条任务形成 review-ready DATA_ONLY diff 后只输出 `WAIT_FOR_HUMAN_REVIEW`。
- [x] Agent CLI 不提供 approve/reject/delete/stage/commit/push 命令。
- [x] 四个 skill 进入 Build signature，并由聚焦契约测试检查无越权命令。

### 5.1 P0.2 completion receipt（2026-08-13）

- 四次 `quick_validate.py .codex/skills/<skill>`：全部 exit 0，四个 skill 均为 valid。
- `python3 configs/pcbknowledge_workflow.py config`：exit 0。
- `python3 configs/pcbknowledge_workflow.py build`：exit 0；60 tests passed，0 failures，
  0 errors，0 skips；working authority 为 0 Source / 0 Entity / 0 Fact。
- `python3 configs/pcbknowledge_workflow.py test`：exit 0；60 tests passed，0 failures，
  0 errors，0 skips；`git diff --check` passed。
- `python3 configs/pcbknowledge_agent.py validate`：exit 0；working/published authority 均为
  0 Source / 0 Entity / 0 Fact，0 conflicts。
- `python3 configs/pcbknowledge_agent.py change-scope`：exit 0；真实 checkout 为 `CODE_ONLY`，
  `valid_for_single_commit: true`；synthetic Agent vertical test 另行验证最终 handoff 为
  `DATA_ONLY + WAIT_FOR_HUMAN_REVIEW`。
- `python3 configs/pcbknowledge_workflow.py package`：exit 0；生成
  `PcbKnowledge_a2f89fd66a6f5cea.zip`，SHA-256
  `c6406225fe0835ea5c995907b984d35edce06d4f04c90cd8ca0ba12ead214420`。
- real loopback GUI smoke：`run --port 18083 --no-browser` ready；`/healthz` 与 `/` 均 HTTP 200；
  CSP 为 `default-src 'none'` 且 `X-Frame-Options: DENY`；`SIGINT` 后 exit 130。
- 迭代阶段首次直接运行三模块 unittest 时漏设 `PYTHONPATH=src`：exit 1，loader 报 2 个
  `ModuleNotFoundError`；按仓库运行环境补齐后 exit 0，18 tests passed。该环境调用错误未作为门禁
  pass，最终 Build/Test receipt 均使用 workflow 固化的正确环境。

## 6. P0.3 — Local Review Workbench

继续 Python server + 少量原生 JS，不引入 Node build chain。

- [ ] `/sources`
- [ ] `/entities`
- [ ] `/facts`
- [ ] `/review`
- [ ] vendored、版本固定的 PDF.js viewer。
- [ ] PDF page + normalized bbox overlay。
- [ ] typed fact inspector。
- [ ] review history。
- [ ] source/entity/fact/supersedes 导航。
- [ ] missing/conflict/license gate。
- [ ] Git diff 显示 DATA_ONLY/MIXED 状态。

## 7. P0.4 — First Real Dataset + Evals

只有 P0.1–P0.3 关闭后才开始批量录入真实数据。

首批目标：

- [ ] 20–30 个常用 IC。
- [ ] >=100 pin facts。
- [ ] >=100 parameter-limit facts。
- [ ] 至少两个 datasheet revision 更新案例。
- [ ] 至少 20 个 deliberately wrong/ambiguous negative cases。

恢复 `evals/`，至少覆盖 wrong MPN、wrong package、wrong revision、absolute max vs recommended、unknown、supersede、conflict、license blocked、anchor drift、review history、uncommitted approval、mixed commit。

## 8. P1 — Local Retrieval

- [ ] `.pcbknowledge/index.sqlite`，可删除重建。
- [ ] exact manufacturer/MPN/package/fact-type index。
- [ ] SQLite FTS5。
- [ ] PDF page text 派生缓存。
- [ ] published snapshot 是默认 index source。
- [ ] working-tree preview 显式 opt-in。
- [ ] 增加 PackageDimension / PowerSequence / Decoupling / ClockReset / LayoutGuideline facts。

查询顺序：

```text
exact entity
→ exact package/revision/fact type
→ published filters
→ FTS
→ fact/evidence/conflict/unknown
```

## 9. P2 / P3

P2：FabCapability、InternalRule、DesignReview、Waiver、Lifecycle、Replacement、HistoricalCase、KnowledgeSnapshot、PCBAtlas/PcbCore adapter、iOS read-only snapshot。

P3：只有 golden eval 证明 Exact+FTS+Vector 对开放式 guideline/case retrieval 有稳定增益后，再写新 ADR 选择本地 vector 技术。ADR-010 的历史 pgvector 方案不会自动复活。

## 10. 验证要求

每一轮至少执行：

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py change-scope
python3 configs/pcbknowledge_workflow.py package
```

涉及 GUI 时再做 loopback smoke。FreeCM manifest 由 workflow tests 覆盖，并由已安装扩展加载时
执行协议校验；仓库不携带独立 validator。未运行、被截断或 skipped 的检查不能记为通过。
