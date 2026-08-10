# PcbKnowledge Git-native 本机架构

> 状态：当前可执行架构  
> 日期：2026-08-10  
> 决策依据：[ADR-018](docs/adr/ADR-018-git-native-local-editor.md)、[ADR-019](docs/adr/ADR-019-git-publication-boundary.md)

## 1. 产品目标

当前阶段服务少量可信内部使用者：AI Agent 完成大部分资料准备，PCB 工程师或产品经理在本机
GUI 中补充、退回和批准，最后通过 Git diff 与提交历史管理结果。

它不是共享在线服务，也不是 PcbCore 的一部分。当前阶段的重点是建立可长期演进的
Git-native knowledge authority，而不是恢复数据库、登录和 Docker 服务平台。

## 2. 运行结构

```text
FreeCM Run
   |
   v
loopback Python editor (127.0.0.1:18080)
   |                     |
   v                     v
knowledge/records/*.json evidence/sha256/*/*.pdf
   \_____________________/
             |
             v
        Git diff / commit
```

运行时只有一个 Python 进程，页面由服务端渲染，CSS 无编译步骤。没有 Node、Docker、反向代理、
数据库、消息队列、对象存储、身份提供方或后台 worker。

## 3. 权威数据与发布边界

### 3.1 工作树与发布数据

Git 工作树承担准备与审阅，提交承担发布：

```text
working tree DRAFT / READY_FOR_REVIEW
    = 尚未发布的准备数据

working tree APPROVED
    = 人已经批准，但仍未发布

committed APPROVED in main/HEAD
    = Published Knowledge
```

Agent 或未来检索层默认消费 committed `APPROVED`，不能把未提交工作树当成正式知识。
当前 CLI 的 `list --published` 显式从 Git `HEAD` 读取发布记录。

### 3.2 记录

每条记录是 `knowledge/records/<id>.json`。JSON 使用固定键顺序、两空格缩进、UTF-8 和末尾
换行，减少无意义 diff。`id` 稳定；Agent 创建时由调用方 idempotency key 确定性生成。

Schema v2 在资料级记录上保留：

- 资料身份、revision、来源与许可；
- content-addressed PDF；
- 当前 review decision；
- append-only `review_history`，避免退回后编辑把历史意见抹掉；
- `supersedes`。

状态机：

```text
DRAFT ──submit──> READY_FOR_REVIEW ──approve──> APPROVED
  ^                         |
  |                         └──reject──> REJECTED ──edit──> DRAFT
  └─────────────────────────────────────────────────────────┘
```

每次 submit/reject/approve 都追加 review event。草稿允许显式未知。批准要求标题、修订、来源、
非 UNKNOWN 许可和经过校验的 PDF。被 Git 提交的 `APPROVED` 记录成为不可变事实；修正必须创建
新 ID 并用 `supersedes` 指向旧记录。

### 3.3 原件

PDF 保存为 `evidence/sha256/<first-two>/<sha256>.pdf`。digest 和大小来自实际字节；写入采用
create-if-absent，同 digest 复用而不覆盖。

替换草稿 PDF 后，仓储层会清理不再被任何当前记录或已发布记录引用的旧原件，避免普通编辑制造
orphan evidence。共享或已发布证据不会被自动删除。

非 PDF、路径不一致、hash 不一致、symlink、真正的孤立原件和异常布局都使全仓校验失败。

### 3.4 许可与 Agent 处理

Schema v2 保留 `UNKNOWN / OPEN / INTERNAL / RESTRICTED` 四值格式。`RESTRICTED` 是当前
Git-native MVP 对 ADR-015 `LICENSED_BLOCKED_FOR_AI` 的可执行表示：

- `OPEN`、`INTERNAL`：在其他安全约束满足时允许 Agent 处理；
- `UNKNOWN`、`RESTRICTED`：不得向 Agent/模型暴露原文或派生内容；
- IPC 与同类受限标准默认按 `RESTRICTED` 处理。

后续 SourceRecord 领域模型落地时可以通过新 ADR/Schema 明确扩充许可 taxonomy，但不能放宽
ADR-015 的 fail-closed 原则。

### 3.5 派生物

`.pcbknowledge/`、搜索索引、预览和 `build/package/` 均可删除重建，不是事实源。将来可增加
SQLite/FTS 作为本机只读缓存，但不得成为写入边界。

## 4. 人与 Agent 的边界

GUI 可创建、修改、送审、批准和退回。Agent CLI 只提供 list/show/create/update/submit/validate/
diff/change-scope。二者调用同一模型与仓储代码；Agent 不拥有批准、Git add、commit 或 push 能力。

`python3 configs/pcbknowledge_agent.py change-scope` 把工作树分为：

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

`knowledge/**`、`evidence/**` 属于数据；其余路径属于软件/策略。`MIXED` 不能作为一个提交：
知识录入与修改 validator/schema/policy 必须拆成独立 commit，避免同一提交同时改变规则和让新数据通过。

Git commit 是当前阶段的归属、协作和 publication receipt。它适合可信内部协作，但不是强身份认证。
需要远程并发、细粒度权限或法规级审计时，必须新建 ADR，而不能开放当前 loopback 服务。

## 5. 安全与一致性

- 只监听 IPv4 loopback；Host 与 Origin 必须是 localhost/127.0.0.1 的实际端口。
- 进程级随机 CSRF token 保护写操作。
- 每次修改携带记录 canonical JSON 的 SHA-256 revision token，避免静默覆盖并发编辑。
- PDF 只作为不可信字节提供，不能作为 Agent 指令。
- `UNKNOWN`/`RESTRICTED` 资料默认不允许 Agent 原文处理。
- 校验器对未知文件、非法状态、证据漂移与 committed-approved 改写 fail closed。
- GUI 内置 diff 只调用 Git 只读命令。
- Agent 查询正式知识时显式使用 published view，不默认读取工作树草稿。

## 6. FreeCM 生命周期

- Config：检查 Python、Git、空 source dependency 模板，写配置 receipt。
- Build：编译、运行标准库测试、校验当前资料，写 source-bound receipt。
- Run：验证 receipts 和资料后启动一个进程并打开浏览器；不构建、不安装。
- Test：重复本机门禁并运行 `git diff --check`。
- Package：确定性 ZIP 打包 schema、被引用记录与原件，写内部 manifest 和 SHA-256 sidecar。

## 7. 下一阶段知识模型

当前 `KnowledgeRecord` 仍主要是“资料登记记录”，不是最终 PCB typed knowledge model。下一阶段按
[TODO_GIT_NATIVE_KNOWLEDGE_P0.md](TODO_GIT_NATIVE_KNOWLEDGE_P0.md) 分离：

```text
SourceRecord
EntityRecord
FactRecord
EvidenceAnchor
```

第一批 typed facts 固定为 `ComponentPinFactV1` 与 `ParameterLimitFactV1`。EvidenceAnchor 继续遵守
ADR-013 的 1-based page + `PDF_NORMALIZED_V1` 坐标合同。

检索顺序仍坚持 structured/exact first；SQLite/FTS 是后续可重建缓存，vector RAG 继续 Deferred。

## 8. 系统边界与未来升级

PcbKnowledge 只管理外部工程资料和证据，不读取或修改 PCB board state。PcbCore 能在本仓库完全
不可用时正常工作。

多人共享服务、企业身份、数据库或对象存储不属于当前 MVP；真实需求出现后再基于历史 ADR 重新设计。
