# PcbKnowledge 内部介绍

## 一句话

PcbKnowledge 的目标是把“工程师脑子里、datasheet 里、规范里、历史 review 里”的 PCB 外部知识，变成 **Agent 可查询、人可审阅、结果可回到原文证据、提交可由 Git 追踪** 的工程知识库。

当前产品采用 Git-native 本机模式：Agent 先准备，人来确认，Git commit 负责发布。

## 1. 为什么需要它

PCB 软件本身知道当前板卡里有什么：元件、网络、几何、规则、DRC 结果。但大量设计决策依赖板卡之外的知识，例如：

- datasheet 的 pin function / alternate function；
- absolute maximum 与 recommended operating condition；
- 电源时序和去耦要求；
- 晶振、复位、启动配置；
- 厂商 layout/application guide；
- reference design；
- 板厂工艺能力；
- 内部设计规范；
- 历史 review、waiver、PCN、EOL 和替代关系。

这些资料数量大、会更新、经常存在不同 revision，而且工程结论必须能说明“来自哪一页、哪一段、哪个版本”。只让大模型记忆这些知识不可靠；只做“PDF 切块 + 向量搜索”又无法可靠区分 MPN、package、revision 和硬性工程条件。

PcbKnowledge 因此做两件事：

```text
保存证据
+
把关键工程结论结构化
```

## 2. PcbKnowledge 不负责什么

PcbKnowledge **不是 PCB 几何/DRC 内核**。

```text
PcbKnowledge
= 外部知识、证据、历史经验

PcbCore
= 当前板卡事实、连接、几何、规则和确定性验证

Agent Harness
= 把两边组合成任务流程
```

例如 PcbKnowledge 可以告诉 Agent：

> 某器件 datasheet 要求 VIN 推荐工作在某范围，证据位于 Rev.H 第 5 页。

但修改板卡后是否真的没有 short、clearance violation、连接错误，仍由 PcbCore/验证器判断。

## 3. 为什么当前不用 Docker、数据库和登录

最初版本按多人在线平台设计，引入了 PostgreSQL、Keycloak、对象存储、Worker、React 前端和 Docker Compose。对未来大规模服务而言这些技术并不错误，但当前真实使用方式只是少量可信内部人员共同维护一个工程知识仓库。

因此现在把 authority 移到 Git：

```text
可读 JSON
+ content-addressed PDF
+ Git diff
+ Git history
```

工程师或产品经理克隆仓库后直接打开本机 GUI；Agent 直接操作同一套文件，不需要数据库账号或服务 token。

## 4. 当前 GUI 到底在录什么

当前“建立一条可审阅的记录”页面是 **Source Corpus 录入页**。

它现在应该录：

```text
一份确定文档的一个确定 revision
```

例如：

```text
Title: TPS54331 Datasheet
Document number: SLVS839
Revision: Rev. H
Publisher: Texas Instruments
Source: 官方 URL
PDF: 官方原件
```

目前不要把下面这些工程结论全部写进“准备说明”当成知识库：

```text
Pin 3 = EN
VIN absolute maximum = ...
推荐工作范围 = ...
某电容必须放在某处
```

这些内容属于下一层 **FactRecord**。

## 5. P0.1 后数据会分成三类

### Source：资料是什么

```text
SourceRecord
= datasheet / app note / reference design / PCN / 板厂能力 / 内部规范的某个 revision
```

一份 Source 保留标题、编号、revision、发布者、来源、许可和 PDF 原件。

### Entity：资料在说谁

P0.1 第一批只做：

```text
Manufacturer
Component
Package
```

例如：

```text
Manufacturer = Texas Instruments
Component MPN = TPS54331DR
Package = SOIC-8
```

原始 MPN 永远保留；normalized key 只用于查找。系统不会根据 suffix 自动猜 package 或 silicon revision。

### Fact：资料明确说了什么

P0.1 第一批做两类：

```text
ComponentPinFactV1
ParameterLimitFactV1
```

例如：

```text
ComponentPinFact
component = TPS54331DR
package = SOIC-8
pin = 3
name = EN
function = Enable
```

或：

```text
ParameterLimitFact
component = TPS54331DR
parameter = VIN
kind = ABSOLUTE_MAXIMUM
max = ...
unit = V
```

每条 Fact 都绑定 EvidenceAnchor，所以用户和 Agent 可以从结构化结果跳回准确 PDF 页面和区域。

## 6. EvidenceAnchor 是什么

它不是“这个事实来自这本 PDF”这么粗，而是：

```text
Source revision
+ 1-based page
+ 页面归一化 bbox
+ quote/hash
```

这样无论浏览器缩放多少，Fact 都可以定位到同一块原文。

新 datasheet revision 不会自动继承旧 anchor；必须重新核验。

## 7. 人、Agent、Git 分别负责什么

### Agent

Agent 可以：

- 找官方资料；
- 建 Source/Entity/Fact 草稿；
- 填写确认过的字段；
- 添加 EvidenceAnchor；
- 报告 unknown、conflict、missing evidence；
- submit 给人审阅。

Agent不能：

- 根据相似器件猜值；
- approve/reject；
- 自动 commit/push；
- 读取许可禁止 AI 处理的原文；
- 修改 PCB board state。

### 工程师 / 产品经理

内部人员主要做：

- 核对文档版本、来源、许可；
- 检查 Fact 是否真的与原文一致；
- 退回不完整/错误候选；
- 对自己有能力负责的内容执行批准；
- 查看 Git diff；
- 决定何时提交和推送。

高风险工程事实仍应由有对应领域判断能力的人批准。

### Git

Git 不是数据库 UI 的替代品，而是当前阶段的 publication ledger。

```text
保存草稿
!= 发布

GUI 批准
!= 发布

approved data 被 commit 到 publication ref
= Published Knowledge
```

正式 Agent 查询默认只能读 committed approved 数据。

## 8. 为什么数据 commit 和代码 commit 必须分开

知识数据位于：

```text
knowledge/**
evidence/**
```

validator、schema、代码、文档等位于其他目录。

系统禁止把两类修改放进同一个 commit，避免出现：

```text
Agent 先修改“什么算合法”
+
同一个 commit 再提交依赖新规则的数据
```

这也是为什么仓库提供 `change-scope` 检查。

## 9. 许可如何理解

“官网能下载”不等于“开放许可证”。

P0.1 会明确区分：

```text
PUBLIC_REFERENCE
OPEN_LICENSE
INTERNAL
RESTRICTED
LICENSED_BLOCKED_FOR_AI
UNKNOWN
```

典型厂商 datasheet 更接近 `PUBLIC_REFERENCE`，而不是自动视为 `OPEN_LICENSE`。

IPC 和合同明确禁止 AI/TDM 的商业资料默认进入 `LICENSED_BLOCKED_FOR_AI`，Agent 不读取、不解析、不索引、不 embedding。

## 10. 软件里会出现哪些使用场景

### 器件选型 / BOM

Agent 查询：

- 工作电压；
- absolute max；
- package；
- lifecycle；
- 替代关系。

然后把来源和冲突一并返回。

### 原理图检查

对于当前器件：

- pin function 是否匹配；
- 某 pin 是否允许 alternate function；
- 电源/复位/晶振连接有没有遗漏；
- 推荐工作条件是否满足。

### PCB 布局

Agent 可以查询厂商布局指南、reference design、去耦要求等；真正坐标、间距和 DRC 仍由 PcbCore 验证。

### 自动布线 / ECO

RAG 本身不是 router。PcbKnowledge 可以提供约束依据和历史案例；router/DRC/evaluator 决定修改是否可接受。

### Design Review

以后可以把历史 review、approved waiver 和内部 guideline 变成可查询证据，使 Agent 知道“以前为什么这样做”。

### iOS / PCBAtlas 离线知识

长期可以从 Git authority 构建项目级只读 SQLite snapshot，只下发当前板卡相关 Fact/Source/evidence，而不是把完整公司语料塞进 iPhone。

## 11. 当前开发阶段

```text
Git-native MVP
    COMPLETE

P0.0 publication / evidence hardening
    IMPLEMENTED

P0.1 typed Source / Entity / Fact / EvidenceAnchor
    当前开发目标

P0.2 Agent-native ingestion
P0.3 Review Workbench
P0.4 First real dataset + golden evals
P1 SQLite exact + FTS
P2 broader PCB knowledge/integration
P3 vector retrieval only if eval proves useful
```

当前阶段最重要的不是把几万份 PDF 尽快塞进去，而是先让第一批 20–30 个器件能形成：

```text
原文
→ entity
→ typed fact
→ exact evidence
→ human review
→ Git publication
→ published query
```

这个闭环稳定以后，再批量扩数据。
