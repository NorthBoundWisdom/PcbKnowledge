# TODO — Git-native PCB Knowledge P0

> 状态：`IN_PROGRESS`
> 建立日期：2026-08-10
> 前置里程碑：[`TODO_GIT_NATIVE_MVP.md`](TODO_GIT_NATIVE_MVP.md) 已完成
> 目标：在不恢复 Docker、登录、数据库和在线服务的前提下，把当前“资料登记器”推进为
> Git-native PCB structured knowledge repository。

## 1. 不变边界

- Git 仓库文件仍是唯一 authority。
- PDF 继续使用 SHA-256 content addressing。
- GUI 继续是 loopback-only Python editor，不恢复 React/Node 服务栈。
- Agent 与 GUI 共用同一文件模型和 validator。
- Agent 可以准备/修改/送审，不能批准、提交或推送。
- working-tree approval 与 Git publication 分离；formal read 只使用 committed approved。
- knowledge/evidence 数据 commit 与 code/schema/policy commit 分离。
- PcbKnowledge 不读取或修改 PCB board state，不成为 PcbCore 运行时依赖。
- Vector RAG、数据库服务和 MCP 均不是 P0 前置条件。

## 2. P0.0 — Git-native Core Hardening

- [x] 修复替换/清空草稿 PDF 后遗留 orphan evidence 的一致性缺陷。
- [x] 共享 evidence 不被清理；committed approved evidence 受保护。
- [x] Schema 升级到 v2，增加 append-only `review_history`。
- [x] reject → edit → resubmit 不再丢失退回原因。
- [x] 明确 `RESTRICTED` 为当前 ADR-015 AI-processing-blocked 可执行表示。
- [x] CLI 输出 `agent_processing_allowed`。
- [x] 建立 committed-approved published view；CLI 增加 `list --published`。
- [x] 建立 `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change-scope classifier。
- [x] `MIXED` 被定义为非法单 commit。
- [x] 新增 ADR-019 固化 publication 与 change-scope 边界。
- [ ] 在真实 checkout 运行完整 FreeCM Config / Build / Test / Package / GUI smoke，并记录收据。

## 3. P0.1 — Knowledge Schema v3

当前 `KnowledgeRecord` 仍主要表达“一份资料的登记和审阅”。P0.1 不继续向它堆领域字段，而是
建立四类独立 authority 对象：

```text
knowledge/
├── sources/
├── entities/
└── facts/

EvidenceAnchor 作为 Fact → Source 的证据关系
```

### 3.1 SourceRecord

- [ ] `SourceRecordV1` 独立 schema、model、repository。
- [ ] `source_type`：
  - `DATASHEET`
  - `APPLICATION_NOTE`
  - `REFERENCE_DESIGN`
  - `PCN`
  - `FAB_CAPABILITY`
  - `INTERNAL_GUIDELINE`
- [ ] 保留 title/document number/revision/publisher/locator/license/evidence。
- [ ] revision/supersedes 仍是显式关系，不根据文件名猜测。
- [ ] 旧 `knowledge/records/` 在零真实数据阶段完成一次破坏性迁移/更名，不维护双写兼容层。

### 3.2 EntityRecord

P0 只实现能支撑第一批 datasheet facts 的最小实体集合：

- [ ] `ManufacturerV1`
- [ ] `ComponentV1`
- [ ] `PackageV1`
- [ ] 原始 MPN 与 normalized lookup key 分离。
- [ ] 不从 MPN suffix 猜 package、silicon revision 或 orderable-part 事实。
- [ ] entity ID 稳定，可由 Agent idempotent create。

### 3.3 EvidenceAnchor

继续遵守 ADR-013：

- [ ] 1-based `page`。
- [ ] `coordinate_space = PDF_NORMALIZED_V1`。
- [ ] `0 <= x0 < x1 <= 1`、`0 <= y0 < y1 <= 1`。
- [ ] `quote` + `quote_sha256`。
- [ ] 绑定 immutable source revision。
- [ ] anchor 不自动迁移到新 revision。
- [ ] Draft 可暂缺 bbox；Fact approval 前必须具备完整 anchor。

### 3.4 FactRecord

- [ ] `FactRecordV1` 稳定 identity、subject、payload、conditions、anchors、review、supersedes。
- [ ] Fact 与 Source 分开审核/版本化。
- [ ] unresolved conflict 显式存在，不静默选 winner。
- [ ] unknown 是合法查询结果。

第一批 fact type：

#### `ComponentPinFactV1`

- [ ] component ID
- [ ] package ID
- [ ] pin number/name
- [ ] function / alternate functions
- [ ] conditions/applicability
- [ ] evidence anchors

#### `ParameterLimitFactV1`

- [ ] component ID
- [ ] parameter
- [ ] `ABSOLUTE_MAXIMUM / RECOMMENDED_OPERATING / ELECTRICAL_CHARACTERISTIC`
- [ ] minimum / typical / maximum
- [ ] unit
- [ ] conditions
- [ ] evidence anchors

P0.1 completion gate：

```text
1 个 datasheet
→ 1 个 component
→ ≥5 ComponentPinFactV1
→ ≥3 ParameterLimitFactV1
→ 每条 fact 均可定位到具体 source/page/bbox
→ reject/resubmit 历史保留
→ approval 后 commit
→ published reader 只能看到 commit 后事实
```

## 4. P0.2 — Agent-native ingestion

- [ ] 增加 `.codex/skills/ingest-engineering-source/SKILL.md`。
- [ ] 增加 `.codex/skills/resolve-component-identity/SKILL.md`。
- [ ] 增加 `.codex/skills/extract-component-facts/SKILL.md`。
- [ ] 增加 `.codex/skills/prepare-knowledge-review/SKILL.md`。
- [ ] CLI 增加 source/entity/fact typed commands。
- [ ] Agent 输入稳定业务 key 时全部 create 幂等。
- [ ] Agent 输出 conflicts / unknowns / missing anchors，不自由补值。
- [ ] restricted source 在任何原文读取前 fail closed。
- [ ] 一条用户任务可以产生一个 review-ready Git data diff，但不能自动 approve/commit。

目标体验：

```text
用户：
“把 TPS54331 的 datasheet、pin 和供电限制录进去。”

Agent：
官方来源定位
→ license gate
→ SourceRecord
→ Component/Package
→ Pin/Limit facts
→ EvidenceAnchor
→ validate
→ submit
→ 输出 unknown/conflict/diff
→ 停止等待人工审核
```

## 5. P0.3 — Local Review Workbench

继续使用当前 Python server + 少量原生 JS；不引入 Node build chain。

- [ ] `/sources`
- [ ] `/entities`
- [ ] `/facts`
- [ ] `/review`
- [ ] vendored、版本固定的 PDF.js viewer。
- [ ] PDF page + normalized bbox overlay。
- [ ] 右侧 typed fact inspector。
- [ ] review history 可视化。
- [ ] source/fact/entity/supersedes 导航。
- [ ] 批准前显示 missing/conflict/license gate。
- [ ] Git diff 页面区分 data-only 与 mixed workspace。

## 6. P0.4 — First Real Dataset + Evals

只有 P0.1–P0.3 关闭后，才开始批量录入真实数据。

首批：

- [ ] 20–30 个常用 IC。
- [ ] ≥100 pin facts。
- [ ] ≥100 parameter-limit facts。
- [ ] 至少两个 datasheet revision 的更新案例。
- [ ] 至少 20 个 deliberately wrong/ambiguous negative cases。

恢复 `evals/`，至少覆盖：

- [ ] wrong MPN
- [ ] wrong package
- [ ] wrong revision
- [ ] absolute maximum vs recommended operating
- [ ] unknown
- [ ] supersede
- [ ] unresolved conflict
- [ ] restricted/license blocked
- [ ] evidence anchor drift
- [ ] review history
- [ ] uncommitted approval not visible in published view
- [ ] mixed data/code commit rejected

## 7. P1 — Local Retrieval

P0 数据真实运转后再做，不提前建设 vector stack。

- [ ] `.pcbknowledge/index.sqlite`，可删除重建。
- [ ] exact manufacturer/MPN/package/fact-type index。
- [ ] SQLite FTS5。
- [ ] PDF page text 派生缓存。
- [ ] published view 是默认 index source。
- [ ] working tree preview 必须显式 opt-in。
- [ ] 加入 PackageDimension / PowerSequence / Decoupling / ClockReset / LayoutGuideline facts。

查询顺序：

```text
exact entity
→ exact package/revision/fact type
→ published + effective filters
→ FTS
→ return fact/evidence/conflict/unknown
```

## 8. P2/P3

P2：

- FabCapability
- InternalRule
- DesignReview
- Waiver
- Lifecycle
- Replacement
- HistoricalCase
- KnowledgeSnapshot
- PCBAtlas/PcbCore adapter
- iOS read-only knowledge snapshot

P3：

仅在 golden eval 证明 `Exact + FTS + Vector` 对开放式 guideline/case retrieval 有稳定增益后，
再用新 ADR 选择本地 vector/embedding 技术。ADR-010 的旧 pgvector 方案不得因历史文档自动复活。

## 9. 验证要求

每一轮结束至少执行：

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py change-scope
python3 configs/pcbknowledge_workflow.py package
python3 configs/validate_freecm_repo_commands.py
```

涉及 GUI 时再做真实 loopback smoke。未运行、被截断或 skipped 的检查不能记为通过。
