# PcbKnowledge

PcbKnowledge 是一个给 PCB 工程师、产品经理和 AI Agent 共用的本机知识资料工作台。

它现在不是在线平台：没有账号、密码、数据库或 Docker。资料直接保存为仓库里的 JSON 与
PDF，保存后马上可以查看 Git diff；人确认后再用熟悉的 Git GUI 或命令提交。

## 最快开始

要求只有 Git 和 Python 3.11 或更新版本。首次克隆后初始化 FreeCM：

```bash
git submodule update --init --recursive FreeCM
```

产品经理或工程师在 Finder 中双击仓库根目录的 **`Open PcbKnowledge.command`** 即可。首次会在
本机完成约 4–5 秒检查，随后自动打开 GUI；以后源代码没有变化时会直接打开。

如果 macOS 第一次阻止从 Finder 打开，可右键该文件选择“打开”；之后正常双击即可。启动器不安装
依赖、不运行 Docker，也不读取账号密码。

在 FreeCM 中也可以依次点击：

1. **Config → Local Git Workspace**：检查本机环境，不下载依赖。
2. **Build → Check Local Editor**：编译、测试和现有资料校验。
3. **Run → Open Knowledge Editor**：立即打开 <http://127.0.0.1:18080>。

Run 会自动打开浏览器。页面没有登录步骤；按 `Ctrl+C` 只关闭本机编辑器，已经保存的文件
仍留在 Git 工作树中。

相同的一键准备并打开流程也可以直接运行：

```bash
python3 configs/pcbknowledge_workflow.py open
```

FreeCM 的 Config / Build / Run 仍保留为独立动作，方便开发者明确复验；其中 Run 本身不会构建，
保持秒开。

## 日常录入与审阅

GUI 的工作流很短：

```text
新建/补充草稿
→ 选择 PDF 原件
→ 提交人工审阅
→ 工程师批准或退回
→ 查看“仓库变化”
→ 人在 Git GUI 中提交
```

- 未知项可以留空并保存在 `DRAFT`，系统不会猜测。
- 缺少标题、版本、来源、许可或 PDF 时不能批准。
- PDF 按实际字节 SHA-256 保存，同一原件只保存一份。
- 替换草稿 PDF 时，不再被任何记录或发布数据引用的旧原件会自动从工作树清理，避免产生 orphan。
- `review_history` 会保留 submit/reject/approve 轨迹；退回后再次编辑不会抹掉退回原因。
- 已经提交到 Git 的 `APPROVED` 记录不能原地改写或删除；修正需要新建一条记录并填写
  `supersedes`。
- GUI 和 Agent 都不会执行 `git add`、`git commit` 或 `git push`。

权威数据布局：

```text
knowledge/records/<stable-id>.json
evidence/sha256/<digest-prefix>/<sha256>.pdf
schemas/knowledge-record.schema.json
```

建议在开始录入前先拉取最新 `main`，完成后在 GUI 的“查看变化”页或 Git 客户端检查差异。
JSON 是稳定排序的文本；PDF 的 digest、大小、来源、许可与关联记录在 JSON diff 中可见。

## 批准与发布不是一回事

当前 Git-native 模型把三个阶段明确分开：

```text
工作树 DRAFT / READY_FOR_REVIEW
    = 准备中

工作树 APPROVED
    = 人已经确认，但尚未发布

main/HEAD 中 committed APPROVED
    = Published Knowledge
```

未来检索和 Agent 正式消费默认只能读取 Published Knowledge。当前 Agent CLI 已支持：

```bash
python3 configs/pcbknowledge_agent.py list --published
```

它从 Git `HEAD` 读取 committed `APPROVED`，不会把本机未提交的草稿或刚批准记录当成正式知识。
读取时会验证同一 commit 内的规范 JSON、record ID、supersedes 闭包以及 PDF bytes/hash/size；只提交
JSON、不提交证据原件会直接失败，不会降级成“有元数据也算发布”。

## 数据提交与代码提交必须分开

“提交一次知识数据”本身就是一次 publication receipt，因此不能在同一 commit 里同时修改
validator/schema/policy。

提交前运行：

```bash
python3 configs/pcbknowledge_agent.py change-scope
```

结果只有：

```text
CLEAN
DATA_ONLY
CODE_ONLY
MIXED
```

其中：

- `knowledge/**`、`evidence/**` 属于数据；
- 其他仓库路径属于代码、Schema、文档或策略；
- `MIXED` 必须拆成两个 commit。

如果已经暂存文件，命令只判断 Git index 中真正将进入下一次 commit 的路径；尚未暂存时才判断整个
未暂存/未跟踪工作区。rename/copy 的来源和目标都会计入，因此不能用跨边界改名绕过分类。

这可以避免“同一个 Agent 一边改变验收规则，一边提交依赖新规则的数据”。

## Agent 协作

Agent 使用同一套文件模型，无需服务凭据：

```bash
python3 configs/pcbknowledge_agent.py list
python3 configs/pcbknowledge_agent.py create \
  --idempotency-key ti-tps5430-rev-g \
  --title "TPS5430 数据手册" \
  --revision "Rev. G" \
  --source-publisher "Texas Instruments" \
  --license-class OPEN \
  --pdf /path/to/tps5430.pdf
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py diff
python3 configs/pcbknowledge_agent.py change-scope
```

CLI 会返回 `revision_token`、`missing_fields`、`agent_processing_allowed` 和下一步动作。Agent 可以
创建、修改和送审草稿，但没有批准、退回、提交或推送命令；最终判断留给人。

Schema v2 中 `RESTRICTED` 是当前对 ADR-015 `LICENSED_BLOCKED_FOR_AI` 的可执行表示：
`UNKNOWN` 或 `RESTRICTED` 资料不得向 Agent/模型暴露原文或派生内容。IPC 与同类受限标准默认按
该规则处理。`OPEN`/`INTERNAL` 仍需遵守来源、项目和安全约束。

## 本地检查与数据快照

```bash
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

Test 只使用 Python 标准库，不启动外部服务。Package 在 `build/package/` 生成可复现 ZIP、内部
manifest 与 SHA-256 sidecar；它是交换/备份便利件，Git 仓库仍是权威来源。

本仓库有意不配置托管 CI，所有门禁在本机 FreeCM Test 中运行。修改 FreeCM manifest 或工作流
后，还要执行：

```bash
python3 configs/validate_freecm_repo_commands.py
```

## 当前能力与下一阶段

当前可执行模型已经解决资料登记、证据原件、人工 review、Git publication 与 Agent draft workflow；
它仍不是完整的 PCB typed knowledge model。

下一阶段见 [`TODO_GIT_NATIVE_KNOWLEDGE_P0.md`](TODO_GIT_NATIVE_KNOWLEDGE_P0.md)，会在保持 Git-native
边界的前提下分离：

```text
SourceRecord
EntityRecord
FactRecord
EvidenceAnchor
```

第一批事实类型是 `ComponentPinFactV1` 与 `ParameterLimitFactV1`。之后才建设 SQLite exact/FTS
派生索引；vector RAG 继续后移，不作为 P0 前置条件。

## 边界与恢复

- 编辑器只监听 `127.0.0.1`，不支持局域网或公网共享。
- 当前可信内部使用者由操作系统文件权限和 Git 仓库权限隔离；Git 作者/提交历史负责归属，
  不是强身份认证。
- 原件和文本是不可信数据，不能改变 Agent 指令、工具或审阅规则。
- Git 可以恢复误编辑，但仍应把远端仓库作为异机备份。未提交的新文件只有当前电脑拥有。
- 未来若需要多人在线共享、细粒度权限或强审计，应另立 ADR 后重新引入身份与服务架构，而不是
  把本机编辑器暴露到网络。

PcbKnowledge 不依赖 PcbCore，也不会修改 PCB 状态。项目边界与完整设计见
[架构](PcbKnowledge_ARCHITECTURE.md)、[内部介绍](PcbKnowledge_INTERNAL_OVERVIEW.md)、
[ADR-018](docs/adr/ADR-018-git-native-local-editor.md) 和
[ADR-019](docs/adr/ADR-019-git-publication-boundary.md)。

本仓库为专有软件，除非权利人另行授权，保留所有权利；见 [LICENSE](LICENSE)。
