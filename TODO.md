# TODO — PcbKnowledge Roadmap

> 状态：`P0.2_COMPLETE_P0.2.5_NEXT`
> 更新日期：2026-08-18
> 当前公开源码基线：`efe86a360183f9fd05a0c88ace3bb3f670fde389`
> 目标：把 PcbKnowledge 从已经完成 typed authority + Agent ingestion 的 Git-native 内核，推进为可实际录入、人工审阅、检索并供 PCB Agent 消费的工程知识系统。

## 0. 文档职责

本文件是仓库根目录唯一的执行路线图，负责记录：

- 当前阶段与下一阶段；
- 未完成任务；
- 阶段完成门槛；
- 必须保持的工程边界。

长期稳定架构见 [`docs/architecture.md`](docs/architecture.md)，开源源码与私有知识数据的边界见
[`docs/open-source-boundary.md`](docs/open-source-boundary.md)。历史实现细节以 Git history / ADR 为准，不在 TODO 中维护第二份架构说明。

### 永久边界

- Public PcbKnowledge 仓库只保存代码、Schema、文档、Agent skills 和 synthetic tests。
- 真实 Source / Entity / Fact / Evidence、内部规范、review、waiver 和第三方 PDF 默认进入独立 private knowledge workspace。
- Git repository 仍是 knowledge workspace 的唯一 authority。
- PDF 继续按实际 bytes SHA-256 content addressing。
- Agent 与 GUI 共用同一 authority model / validator。
- Agent 可以创建、修改、validate、submit draft，但不能 approve / reject / stage / commit / push。
- working-tree approval 与 Git publication 分离；正式读取只使用 fully validated committed snapshot。
- unknown / conflict / wrong revision / wrong package 必须显式存在，不能靠模型补值。
- PcbKnowledge 不读取或修改 live PCB board state，也不成为 PcbCore 的运行时依赖。
- SQLite / FTS / page text / vector index 均为可删除派生物，不成为 authority。
- Vector RAG 不是 P0/P1 前置条件；只有 eval 证明增益后才进入 P3。

---

## 1. 已完成基础能力

### P0.0 — Git-native Core Hardening — COMPLETE

已完成：

- Git-native JSON/PDF authority；
- content-addressed evidence；
- canonical serialization；
- append-only review history；
- optimistic revision token；
- committed APPROVED immutability；
- supersedes closure；
- evidence orphan / shared evidence / published evidence protection；
- repository write lock；
- `CLEAN / DATA_ONLY / CODE_ONLY / MIXED` change scope；
- working-tree approval 与 committed publication 分离；
- fully validated published reader；
- deterministic Package snapshot。

### P0.1 — Typed Authority Model — COMPLETE

正式 authority 已固定为：

```text
SourceRecordV1
EntityRecordV1
  - ManufacturerV1
  - ComponentV1
  - PackageV1
FactRecordV1
  - ComponentPinFactV1
  - ParameterLimitFactV1
EvidenceAnchorV1
```

已完成：

- `knowledge/sources/` / `knowledge/entities/` / `knowledge/facts/`；
- 三份 canonical JSON Schema；
- Source license taxonomy；
- exact manufacturer / MPN / package identity；
- PDF normalized bbox + page + quote evidence anchor；
- Fact conditions / applicability / supersedes；
- referential closure validation；
- semantic conflict detection；
- synthetic vertical publication tests。

### P0.2 — Agent-native Ingestion — COMPLETE

已完成四个 repository-local skills：

```text
ingest-engineering-source
resolve-component-identity
extract-component-facts
prepare-knowledge-review
```

Agent CLI 已支持：

- typed `source / entity / fact` commands；
- stable idempotency keys；
- exact identity resolution；
- `source authorize-read` license gate；
- explicit unknown / missing anchor / conflict output；
- selected closure `review-status`；
- `DATA_ONLY + WAIT_FOR_HUMAN_REVIEW` handoff；
- `--repo <path>` 指向显式 Git repository。

Public source repository 已增加：

- Apache-2.0；
- public-source guard；
- GitHub Actions；
- CodeQL / Dependabot 配置；
- CONTRIBUTING / SECURITY / PR contract；
- `knowledge/**` / `evidence/**` 只允许 `.gitkeep` 的持续集成门禁。

---

## 2. P0.2.5 — Knowledge Workspace Boundary — NEXT

### 目标

把“PcbKnowledge 软件 checkout”和“Knowledge authority Git repository”从运行时上彻底分离。

当前 Agent CLI 已能使用 `--repo <path>`，但 GUI / FreeCM workflow 仍默认把 public source checkout 当作 knowledge workspace。进入真实数据阶段前必须关闭这个架构缺口。

目标结构：

```text
PcbKnowledge/                 # public software repository
├── src/
├── configs/
├── schemas/
├── tests/
└── ...

PcbKnowledgeData/             # private knowledge workspace
├── .git/
├── pcbknowledge.workspace.json
├── schemas/
├── knowledge/
│   ├── sources/
│   ├── entities/
│   └── facts/
└── evidence/
    └── sha256/
```

### P0.2.5.1 Workspace manifest

- [ ] 定义 `pcbknowledge.workspace.json` V1。
- [ ] 至少包含 workspace format / schema contract / schema digest。
- [ ] manifest canonical、额外字段 fail closed。
- [ ] workspace 必须是独立 Git repository。
- [ ] 不允许 runtime 隐式退回 public source checkout。

### P0.2.5.2 Workspace initialization

新增明确入口，例如：

```bash
python3 configs/pcbknowledge_workspace.py init ../PcbKnowledgeData
```

- [ ] 创建/验证 Git workspace。
- [ ] 写入 workspace manifest。
- [ ] 从 public engine 复制固定 Schema contract 到 workspace。
- [ ] 创建 typed authority roots 和 evidence root。
- [ ] 初始化后立即运行完整 validator。
- [ ] 默认不生成任何真实/示例知识数据。

### P0.2.5.3 Runtime workspace selection

- [ ] Agent CLI `--repo` 与新 workspace contract 对齐。
- [ ] FreeCM `Run/Open/Package` 增加 `--workspace <path>`。
- [ ] GUI server 明确接收 workspace root，不再固定 `REPO_ROOT`。
- [ ] Package 从 selected workspace 导出，不从 public checkout 导出生产数据。
- [ ] published reader 继续只读取 workspace 自身 immutable Git snapshot。
- [ ] Schema / Source / Entity / Fact / Evidence 仍必须在同一个 workspace publication commit 中形成 closure。

### P0.2.5.4 Schema contract upgrade boundary

- [ ] public engine Schema 更新不能静默改变 private workspace authority。
- [ ] workspace 继续使用已 pin 的 Schema copy。
- [ ] 为未来显式 `workspace upgrade` 留出 contract，不在本阶段实现复杂迁移框架。
- [ ] schema upgrade commit 与 knowledge data commit 分离。

### P0.2.5.5 Tests / completion gate

- [ ] temp public source checkout + temp private workspace vertical test。
- [ ] `workspace init -> validate -> Agent create Source/Entity/Fact -> review-status` 可运行。
- [ ] external workspace 可形成 `DATA_ONLY` diff。
- [ ] public source checkout 的 `knowledge/**` / `evidence/**` 始终只有允许的 `.gitkeep`。
- [ ] 错误 workspace / 非 Git repo / manifest drift / schema digest mismatch fail closed。
- [ ] GUI smoke 可以显式打开 external workspace。
- [ ] Package 从 external workspace 可重复生成。
- [ ] GitHub CI 与 public-source guard 全部通过。

**P0.2.5 完成后，才开始 P0.3 Review Workbench。**

---

## 3. P0.3 — Local Review Workbench

P0.3 不再把 `/sources`、`/entities`、`/facts` 当作普通 CRUD 优先实现。核心目标是先完成一个工程师可以真正审核 Agent Fact 的 `/review` vertical slice。

继续保持：

```text
loopback-only Python server
+ server-rendered HTML
+ 少量 native JS
+ no Node build chain
```

### P0.3a — Typed Workbench Foundation

#### Server/UI structure

- [ ] 从当前单体 `server.py` 拆出轻量 routing / view / view-model 边界。
- [ ] HTTP security、CSRF、Host/Origin、revision token 仍在统一 server boundary。
- [ ] GUI 只通过 `KnowledgeRepository` facade 操作 selected workspace。

建议结构：

```text
server.py
views/
  sources.py
  entities.py
  facts.py
  review.py
view_models.py
```

#### Typed navigation

- [ ] `/review`
- [ ] `/facts`
- [ ] `/sources`
- [ ] `/entities`
- [ ] Fact → Component / Package / Source 导航。
- [ ] Source / Fact supersedes 导航。
- [ ] status / prepared_by / revision token / review history 可见。

#### Typed fact inspector

- [ ] `ComponentPinFactV1` inspector。
- [ ] `ParameterLimitFactV1` inspector。
- [ ] conditions / applicability。
- [ ] unknown fields。
- [ ] missing anchors。
- [ ] semantic conflicts。
- [ ] license gate state。

### P0.3b — Evidence Review

核心审阅布局：

```text
PDF evidence                           Typed Fact
┌───────────────────────┐             ┌───────────────────────┐
│ page                  │             │ component / package   │
│ highlighted bbox      │     <->     │ payload               │
│ source revision       │             │ conditions            │
│ quote context         │             │ conflict / unknown    │
└───────────────────────┘             └───────────────────────┘
```

- [ ] vendored、版本固定的 PDF.js（如必须引入第三方资产，记录来源/许可证/version）。
- [ ] PDF page navigation。
- [ ] normalized bbox overlay。
- [ ] 多 anchor 切换。
- [ ] quote + quote hash 显示。
- [ ] Source revision / publisher / document number 同屏可见。
- [ ] source 不允许 Agent 读取时，GUI 仍按 human review policy 工作，但界面明确显示 license classification。

### P0.3c — Review Closure

- [ ] Source approve / reject。
- [ ] Fact approve / reject。
- [ ] rejection comment 必填规则与现有 state machine 对齐。
- [ ] review history timeline。
- [ ] conflict / missing evidence / wrong state 阻止 approve。
- [ ] `DATA_ONLY / MIXED` Git scope 明确显示。
- [ ] Git diff 页面显示 selected workspace diff。
- [ ] GUI 永远不执行 stage / commit / push。
- [ ] `WAIT_FOR_HUMAN_REVIEW -> human decision -> Git publication` vertical test。

### P0.3 completion gate

至少跑通一个完整 synthetic scenario：

```text
Agent ingest Source
→ resolve Manufacturer/Component/Package
→ create Fact + EvidenceAnchor
→ submit
→ engineer opens /review
→ PDF bbox 与 typed payload 同屏核对
→ approve
→ DATA_ONLY diff
→ human Git commit in temp workspace
→ published reader returns Fact
```

---

## 4. P0.4 — First Real Dataset + Evals

真实数据必须在独立 private knowledge workspace 中进行，不进入 public PcbKnowledge source repository。

### P0.4a — Pilot Dataset

先用极小真实数据集验证 Schema 和 Review UX，不直接批量导入。

目标：

- [ ] 3–5 个常用 IC。
- [ ] 20–40 个高质量 Fact。
- [ ] 至少一个 multi-package case。
- [ ] 至少一个 datasheet revision update case。
- [ ] 5–10 个 deliberately wrong / ambiguous negative cases。
- [ ] 实际由人通过 Review Workbench 审阅，而不是只依赖 Agent/validator。

重点观察是否需要修正：

- table cell / footnote evidence；
- 一条事实跨多行或多页；
- package applicability；
- 多 Source 支撑一个 Fact；
- revision anchor drift；
- electrical characteristic 的 condition 表达；
- semantic key 是否过宽/过窄；
- review UI 是否能在合理时间完成核对。

P0.4a 允许根据真实数据反馈修改 typed model；但 Schema change 必须有 migration/compatibility decision，不能静默修改已有 private workspace。

### P0.4b — First Useful Dataset

P0.4a 稳定后再扩大：

- [ ] 20–30 个常用 IC。
- [ ] >=100 pin facts。
- [ ] >=100 parameter-limit facts。
- [ ] 至少两个 datasheet revision 更新案例。
- [ ] 至少 20 个 deliberately wrong / ambiguous negative cases。
- [ ] 每个 published Fact 都可追溯到 exact source revision + evidence anchor。

恢复正式 `evals/`，至少覆盖：

- wrong MPN；
- wrong package；
- wrong revision；
- absolute max vs recommended；
- unknown；
- supersede；
- semantic conflict；
- license blocked；
- anchor drift；
- review history；
- uncommitted approval；
- mixed commit；
- workspace/schema contract mismatch。

---

## 5. P1 — Local Retrieval

目标：在不牺牲 provenance / conflict / unknown 的前提下，让 Published Knowledge 可以快速本地查询。

### P1.1 Exact index

- [ ] `.pcbknowledge/index.sqlite`，可删除重建。
- [ ] manufacturer exact index。
- [ ] MPN exact index。
- [ ] package exact index。
- [ ] fact type / subject / source revision filters。
- [ ] published snapshot 默认 index source。
- [ ] working-tree preview 必须显式 opt-in。

### P1.2 FTS5

- [ ] SQLite FTS5。
- [ ] Source metadata FTS。
- [ ] Fact conditions / applicability FTS。
- [ ] PDF page text 派生缓存。
- [ ] page text 与 immutable Source revision 绑定。

查询顺序固定为：

```text
exact entity
→ exact package/revision/fact type
→ published filters
→ FTS
→ Fact + evidence + conflict + unknown
```

### P1 completion gate

- [ ] golden queries 对 20–30 IC dataset 有明确 expected answer set。
- [ ] wrong package / wrong revision 不被 FTS fallback 偷偷放宽。
- [ ] query result 总是返回 provenance / evidence / conflict / unknown。
- [ ] index 删除后可从 Published Knowledge 完整重建。

---

## 6. P1.5 — PCB Knowledge Expansion

只有 P0.4 / P1 的真实 eval 证明基础模型稳定后，再增加更多 Fact 类型。

建议顺序：

### P1.5a — Component engineering

- [ ] PackageDimension。
- [ ] PowerSequence。
- [ ] DecouplingRequirement。
- [ ] ClockResetRequirement。

### P1.5b — Layout knowledge

- [ ] LayoutGuideline。
- [ ] ReferenceDesignRelation。
- [ ] applicability / topology / layer context 的最小结构化表达。

不要提前引入通用规则 DSL；优先根据真实 datasheet/application note case 演进 typed payload。

---

## 7. P2 — Product Integration

目标：让 PcbKnowledge 真正服务 PCB Agent，而不是让 PCB 软件直接依赖整个知识仓库。

### P2.1 Snapshot / adapter

- [ ] immutable `KnowledgeSnapshot` export。
- [ ] project/component scoped snapshot。
- [ ] read-only PcbCore adapter。
- [ ] PCBAtlas/iOS read-only snapshot。
- [ ] 不把完整公司语料下发到终端设备。

### P2.2 Broader knowledge

按需求逐步增加：

- [ ] FabCapability。
- [ ] InternalRule。
- [ ] DesignReview。
- [ ] Waiver。
- [ ] Lifecycle / PCN / EOL。
- [ ] Replacement。
- [ ] HistoricalCase。

### P2.3 Agent task boundary

最终职责保持：

```text
PcbKnowledge
  → evidence-backed engineering knowledge

PcbCore
  → live board truth + deterministic validation

Agent Harness
  → combine knowledge + board state + tools into a bounded task
```

---

## 8. P3 — Advanced Retrieval

只有 golden eval 证明 `Exact + Filters + FTS` 对开放式 guideline / historical case retrieval 明显不足时，才进入 P3。

候选：

- local embedding；
- vector index；
- hybrid retrieval；
- reranking；
- query decomposition。

进入条件：

- [ ] 有固定 golden eval dataset；
- [ ] 有 Exact+FTS baseline；
- [ ] vector/hybrid 在 correctness/recall 上有稳定可测增益；
- [ ] provenance、license、revision、package gate 不被 semantic retrieval 绕过；
- [ ] 新技术仍然只是派生 index，不成为 authority。

---

## 9. 每轮验证要求

Public source repository 代码变更至少执行：

```bash
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

P0.2.5 完成后，涉及真实/外部 knowledge workspace 的变更还必须在独立 temp Git workspace 上执行对应：

```bash
workspace init
validate
Agent vertical workflow
review-status
change-scope
package
published snapshot read
```

涉及 GUI 时增加真实 loopback smoke。

规则：

- skipped / interrupted / truncated 不算通过；
- 失败的首次检查必须记录并修复后重跑；
- public source guard 是每轮第一道门；
- 不因为测试方便把真实 knowledge/evidence 写入公开仓库；
- code/schema/policy commit 与 private knowledge publication commit 永远分离。

---

## 10. 当前开工顺序

当前唯一主线：

```text
P0.2.5 Workspace Boundary
        ↓
P0.3a Typed Workbench Foundation
        ↓
P0.3b Evidence Review
        ↓
P0.3c Review Closure
        ↓
P0.4a Real-data Pilot
        ↓
P0.4b First Useful Dataset
        ↓
P1 Exact + FTS Retrieval
        ↓
P1.5 Knowledge Expansion
        ↓
P2 Product Integration
        ↓
P3 Advanced Retrieval (only if eval justifies)
```

下一轮直接实现 **P0.2.5 Knowledge Workspace Boundary**。