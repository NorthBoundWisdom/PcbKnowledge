# PcbKnowledge Git-native 架构

> 状态：P0.1 typed authority 已实现 + P0 后续演进基线
> 日期：2026-08-10
> 当前实现阶段：P0.1 complete，P0.2 next
> 主要决策：[ADR-018](docs/adr/ADR-018-git-native-local-editor.md)、[ADR-019](docs/adr/ADR-019-git-publication-boundary.md)

## 1. 产品定位

PcbKnowledge 是 PCB 工程知识与证据仓库。当前阶段服务少量可信内部使用者：Agent 负责资料准备和结构化候选，PCB 工程师或产品经理在本机 GUI 中检查、退回和批准，Git 负责差异审阅、协作、归属和最终发布。

它不是共享在线服务，也不是 PcbCore 的一部分。当前产品优先保证：

- 工程事实可以追溯到确定的来源和版本；
- 未知、冲突、受限资料不会被模型静默补全；
- 人和 Agent 操作同一套仓库文件；
- 数据变化可以直接用 Git diff 审阅；
- PcbKnowledge 不可用时，PcbCore/PCBAtlas 的板卡打开、编辑和确定性验证不受影响。

PcbKnowledge 提供“知识与证据”，PcbCore 提供“当前板卡事实与确定性验证”，Agent Harness 负责把二者组合成任务闭环。

## 2. 当前运行结构

```text
FreeCM Run
   |
   v
loopback Python editor (127.0.0.1:18080)
   |
   +--> Git-native JSON authority
   +--> evidence/sha256/*/*.pdf
   |
   v
Git diff / human review / commit
```

当前运行时只有一个 Python 进程，页面由服务端渲染，CSS 无编译步骤。没有 Node、Docker、反向代理、数据库、消息队列、对象存储、身份提供方或后台 worker。

本机文件权限和 Git 仓库权限构成当前可信小团队的访问边界；如果未来需要共享在线编辑、企业 SSO、细粒度 ACL 或法规级审计，必须另立 ADR，而不是把当前 loopback editor 暴露到网络。

## 3. Git authority 与 publication boundary

### 3.1 工作树、批准与发布是三件事

```text
working tree DRAFT / READY_FOR_REVIEW
    = 准备中，未发布

working tree APPROVED
    = 人已经批准，但尚未发布

committed APPROVED in publication ref
    = Published Knowledge
```

正式读取不能把本机工作树当知识库。published reader 必须从同一个 immutable Git ref 读取并校验：

- canonical JSON；
- 文件名与 record identity；
- supersedes/reference closure；
- 关联 PDF bytes；
- PDF SHA-256、size 和 content-addressed path。

当前 typed published reader 与 CLI 的 `list --published` 已实现这一原则，并且不会借用工作树中
尚未提交的 JSON、Schema 或 PDF。

### 3.2 数据提交与代码提交分离

Git change scope：

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

`knowledge/**` 与 `evidence/**` 是数据；其余路径是代码、Schema、文档或策略。若 Git index 非空，分类器判断下一次 commit 的实际 index；否则判断未暂存/未跟踪工作区。rename/copy 的来源和目标同时计入。

`MIXED` 不能成为一个 commit。原因是不能让同一个 Agent 在一个提交中既修改 validator/schema/policy，又提交依赖新规则才能通过的数据。

## 4. 历史 Source Corpus 过渡层（P0.0，已退役）

当前 GUI 截图中的“建立一条可审阅的记录”属于 Source Corpus 录入，不是最终 Fact Editor。

历史 Schema v2 的一条记录代表：

```text
一个确定来源
+ 一个确定文档
+ 一个确定 revision
+ 一份确定 PDF 原件
+ 审阅历史
```

当时的 authority：

```text
knowledge/records/<stable-id>.json
evidence/sha256/<prefix>/<sha256>.pdf
schemas/knowledge-record.schema.json
```

历史记录包含 title、document number、revision、publisher/locator、license、PDF、preparation note、append-only review history 与 supersedes。

这套 v2 是 Git-native MVP 的过渡 Source 模型。P0.1 已在仓库没有真实 record 的窗口一次性迁移到
正式 typed knowledge layout；validator 不读取该旧 root，也没有双写兼容层。

## 5. P0.1 正式 authority 模型（已实现）

P0.1 把“资料”和“资料中的工程事实”拆开：

```text
knowledge/
├── sources/      # 文档 revision
├── entities/     # PCB 工程实体
└── facts/        # 可审核工程事实

evidence/sha256/ # immutable PDF originals
```

### 5.1 SourceRecordV1

`SourceRecordV1` 表达一个确定文档 revision，而不是一个器件的全部知识。

字段至少包括：

- stable ID；
- `source_type`：DATASHEET / APPLICATION_NOTE / REFERENCE_DESIGN / PCN / FAB_CAPABILITY / INTERNAL_GUIDELINE；
- title、document number、revision；
- publisher、source locator；
- license policy；
- content-addressed evidence；
- review history；
- supersedes。

资料版本关系显式保存，不从文件名或标题推断。

### 5.2 EntityRecordV1

P0.1 只建立支撑 datasheet facts 的最小实体集合：

```text
ManufacturerV1
ComponentV1
PackageV1
```

核心约束：

- 原始 manufacturer/MPN/package 字符串永久保留；
- normalized key 只用于精确 lookup；
- 不根据 MPN suffix 猜 package、silicon revision 或 orderable part；
- entity identity 稳定并支持幂等创建；
- Component 明确引用 Manufacturer，Package 独立建模。

### 5.3 EvidenceAnchorV1

继续执行 ADR-013：

```text
source_id
page                 # 1-based
coordinate_space     # PDF_NORMALIZED_V1
bbox                  # x0,y0,x1,y1 in [0,1]
quote
quote_sha256
```

完整 anchor 必须满足：

```text
0 <= x0 < x1 <= 1
0 <= y0 < y1 <= 1
```

Anchor 绑定 immutable source revision，不会自动迁移到新 revision。Draft Fact 可以暂缺 bbox，但批准前必须具备完整 anchor。

### 5.4 FactRecordV1

`FactRecordV1` 表达结构化 PCB 工程事实，而不是自由文本摘要：

```text
stable identity
fact_type
subject entity IDs
payload
conditions/applicability
evidence anchors
review history
supersedes
```

P0.1 第一批仅实现两类事实：

**ComponentPinFactV1**

- component ID；
- package ID；
- pin number/name；
- primary function；
- alternate functions；
- conditions/applicability；
- one or more evidence anchors。

**ParameterLimitFactV1**

- component ID；
- parameter；
- `ABSOLUTE_MAXIMUM / RECOMMENDED_OPERATING / ELECTRICAL_CHARACTERISTIC`；
- minimum / typical / maximum；
- unit；
- conditions；
- one or more evidence anchors。

数值事实必须有单位；没有值就是 unknown，不使用相似器件或模型记忆补齐。

## 6. Review、不可变性与冲突

Source 与 Fact 都使用显式状态机：

```text
DRAFT -> READY_FOR_REVIEW -> APPROVED
  ^              |
  +-- REJECTED <-+
```

- submit/reject/approve 追加 review history；
- rejection comment 必须保留；
- committed `APPROVED` authority object 不允许原地改写或删除；
- 修正通过新 ID/new version + `supersedes`；
- unresolved conflict 必须显式存在，不能依据模型置信度静默选 winner；
- working-tree approval 不等于 publication。

P0.1 不实现复杂 Conflict Center，但 validator 必须能发现语义重复/冲突，并阻止“多个相互冲突的事实同时被当作唯一 authoritative answer”。

## 7. 许可与 Agent 处理

P0.1 SourceRecordV1 已把历史 v2 的临时许可表示替换为明确 taxonomy：

```text
UNKNOWN
PUBLIC_REFERENCE
OPEN_LICENSE
INTERNAL
RESTRICTED
LICENSED_BLOCKED_FOR_AI
```

语义：

- `PUBLIC_REFERENCE`：公开可访问，例如厂商 datasheet；不等于开放版权许可；
- `OPEN_LICENSE`：有明确开放许可；
- `INTERNAL`：组织内部允许处理；
- `RESTRICTED`：限制分发/处理，按明确 policy 执行；
- `LICENSED_BLOCKED_FOR_AI`：禁止 Agent/model 原文、解析、索引、embedding 等处理；
- `UNKNOWN`：fail closed。

IPC 与等价受限标准默认进入 `LICENSED_BLOCKED_FOR_AI`。

## 8. Evidence 生命周期

PDF 永久按实际 bytes SHA-256 内容寻址：

```text
evidence/sha256/<first-two>/<sha256>.pdf
```

写入规则：

- create-if-absent；
- 同 digest 复用；
- hash/size/path 任一不一致即失败；
- symlink、异常布局和真正 orphan evidence 使校验失败；
- 草稿替换 PDF 后，仅允许清理“当前无引用且 published ref 也无引用”的未提交原件；
- 多进程写入通过同一仓库文件锁协调。

## 9. 派生数据与检索

永久资产：

```text
source/entity/fact JSON
PDF originals
EvidenceAnchor
review/supersedes/conflict relations
Git history
```

可重建派生物：

```text
.pcbknowledge/
SQLite indexes
FTS
page text
thumbnail/preview
embedding/vector index
summary/cache
build/package
```

P0/P0.1 不需要 vector RAG。P1 才建立本机 SQLite exact index + FTS5；vector 只有在 golden eval 证明对 guideline/case retrieval 有稳定增益时才进入 P3。

## 10. Agent 边界

Agent 可以：

- 创建和修改 Draft；
- 创建 Source/Entity/Fact 候选；
- 绑定已证实的 EvidenceAnchor；
- validate；
- submit for human review；
- 输出 unknown/conflict/missing evidence/diff。

Agent 不可以：

- approve/reject；
- stage/commit/push；
- 读取 `UNKNOWN` 或 `LICENSED_BLOCKED_FOR_AI` 的受限原文；
- 根据近似 MPN、相似器件或模型先验补事实；
- 修改 PCB board state。

## 11. GUI

当前 GUI 是 Source Corpus editor：用于建立文档记录、关联 PDF、送审、批准和看 Git diff。

P0.1 只要求 authority model 与验证闭环；P0.3 再完成 Review Workbench：

```text
/sources
/entities
/facts
/review

PDF page + normalized bbox overlay
+ typed fact inspector
+ review history
+ conflicts/missing/license gate
+ Git diff
```

继续使用 Python server + 少量原生 JS，不恢复 React/Node build chain。

## 12. FreeCM 生命周期

- Config：检查 Python/Git/仓库边界并写 receipt；
- Build：编译、运行标准库测试、验证全部 authority data；
- Run：验证 build receipt 后启动 loopback editor；
- Test：完整本地门禁 + `git diff --check`；
- Package：从 validated authority 生成确定性 ZIP + manifest + SHA-256 sidecar。

所有新 P0.1 Schema 与 authority roots 必须进入 Build signature、validate 和 Package；不能成为测试未覆盖的隐藏写路径。

## 13. 与 PcbCore / PCBAtlas 的边界

PcbKnowledge 不读取、不修改 live board。它未来向 PCB Agent 提供的是 evidence-backed knowledge，例如 pin、电气限制、布局建议、waiver、板厂能力等。

PcbCore 继续负责：

- board identity；
- geometry/connectivity；
- DRC/ERC/DFM 等确定性判断；
- transaction、patch、undo/replay。

因此 RAG/knowledge retrieval 负责“应该参考什么”，PcbCore/验证器负责“修改后是否正确”。

## 14. 演进顺序

当前执行计划见 [TODO_GIT_NATIVE_KNOWLEDGE_P0.md](TODO_GIT_NATIVE_KNOWLEDGE_P0.md)：

```text
P0.0 Git-native hardening        COMPLETE except real-checkout receipt refresh
P0.1 typed authority model       COMPLETE
P0.2 Agent-native ingestion      NEXT
P0.3 Local Review Workbench
P0.4 First real dataset + evals
P1    SQLite exact + FTS
P2    broader PCB knowledge + integration
P3    vector retrieval only if eval justifies it
```
