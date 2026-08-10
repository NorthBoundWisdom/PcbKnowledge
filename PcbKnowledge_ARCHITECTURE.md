# PcbKnowledge Git-native 本机架构

> 状态：当前可执行架构
> 日期：2026-08-10
> 决策依据：[ADR-018](docs/adr/ADR-018-git-native-local-editor.md)

## 1. 产品目标

当前阶段服务两位可信内部使用者：AI Agent 完成大部分资料准备，PCB 工程师或产品经理在本机
GUI 中补充、退回和批准，最后通过 Git diff 与提交历史管理结果。

它不是共享在线服务，也不是 PcbCore 的一部分。

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

## 3. 权威数据

### 3.1 记录

每条记录是 `knowledge/records/<id>.json`。JSON 使用固定键顺序、两空格缩进、UTF-8 和末尾
换行，减少无意义 diff。`id` 稳定；Agent 创建时由调用方 idempotency key 确定性生成。

状态机：

```text
DRAFT ──submit──> READY_FOR_REVIEW ──approve──> APPROVED
  ^                         |
  |                         └──reject──> REJECTED ──edit──> DRAFT
  └─────────────────────────────────────────────────────────┘
```

草稿允许显式未知。批准要求标题、修订、来源、非 UNKNOWN 许可和经过校验的 PDF。被 Git 提交的
批准记录成为不可变事实；修正必须创建新 ID 并用 `supersedes` 指向旧记录。

### 3.2 原件

PDF 保存为 `evidence/sha256/<first-two>/<sha256>.pdf`。digest 和大小来自实际字节；写入采用
create-if-absent，同 digest 复用而不覆盖。非 PDF、路径不一致、hash 不一致、symlink、孤立原件
和异常布局都使全仓校验失败。

### 3.3 派生物

`.pcbknowledge/`、搜索索引、预览和 `build/package/` 均可删除重建，不是事实源。将来可增加
SQLite/FTS 作为本机只读缓存，但不得成为写入边界。

## 4. 人与 Agent 的边界

GUI 可创建、修改、送审、批准和退回。Agent CLI 只提供 list/show/create/update/submit/validate/
diff。二者调用同一模型与仓储代码；Agent 不拥有批准、Git add、commit 或 push 能力。

Git commit 是当前阶段的归属与协作收据。它适合可信内部协作，但不是强身份认证。需要远程并发、
细粒度权限或法规级审计时，必须新建 ADR，而不能开放当前 loopback 服务。

## 5. 安全与一致性

- 只监听 IPv4 loopback；Host 与 Origin 必须是 localhost/127.0.0.1 的实际端口。
- 进程级随机 CSRF token 保护写操作。
- 每次修改携带记录 canonical JSON 的 SHA-256 revision token，避免静默覆盖并发编辑。
- PDF 只作为字节提供，不执行、不解析为指令。
- 校验器对未知文件、非法状态、证据漂移与 committed-approved 改写 fail closed。
- GUI 内置 diff 只调用 Git 只读命令。

## 6. FreeCM 生命周期

- Config：检查 Python、Git、空 source dependency 模板，写配置 receipt。
- Build：编译、运行标准库测试、校验当前资料，写 source-bound receipt。
- Run：验证 receipts 和资料后启动一个进程并打开浏览器；不构建、不安装。
- Test：重复本机门禁并运行 `git diff --check`。
- Package：确定性 ZIP 打包 schema、被引用记录与原件，写内部 manifest 和 SHA-256 sidecar。

## 7. 系统边界与未来升级

PcbKnowledge 只管理外部工程资料和证据，不读取或修改 PCB board state。PcbCore 能在本仓库完全
不可用时正常工作。

搜索、字段抽取、证据页坐标和更多知识类型可在 Git-native 模型上逐步增加。多人共享服务、企业
身份、数据库或对象存储不属于当前 MVP；真实需求出现后再基于历史 ADR 重新设计。
