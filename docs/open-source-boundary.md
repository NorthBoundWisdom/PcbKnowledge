# Open-source distribution boundary

> 状态：ACTIVE
> 建立日期：2026-08-18
> 适用对象：PcbKnowledge public source repository、贡献者、CI、Agent 与未来 private knowledge workspace

## 1. 目标

PcbKnowledge 的软件基础设施适合公开协作，但 PCB 工程知识和证据天然具有不同的版权、商业敏感性和
许可边界。本文件把两者分开：

```text
Public PcbKnowledge source
  = code + schemas + docs + Agent skills + synthetic tests

Private knowledge workspace
  = Source / Entity / Fact authority + licensed/internal evidence + review history
```

开源不是“把当前目录所有内容都公开”。Apache-2.0 只授权本项目有权授权的软件和仓库文档，不会替
TI/ADI/ST 等厂商 datasheet、IPC 等标准、公司内部 guideline 或用户数据重新授权。

## 2. Public upstream contract

公开上游 `knowledge/**` / `evidence/**` 只保留目录占位符：

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

`configs/check_public_repo.py` 从 Git index/HEAD 的 tracked paths 验证这一合同。任何真实 JSON、PDF 或
其他文件进入这些 roots 都直接失败。CI 必须在常规测试之前运行它。

Synthetic fixtures 放在 `tests/**`，不能为了方便把真实受限文档改名后塞进 test data。

如果未来希望发布一个公共 PCB knowledge dataset，应建立独立数据仓库和独立许可审查，不要解除
public source guard。

## 3. Private knowledge workspace

生产数据建议放在单独 private Git repository，例如：

```text
PcbKnowledge/              # public software
PcbKnowledgeData/          # private authority/evidence
```

Agent CLI 已支持显式 workspace root：

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData source list
```

Agent 不得自行在 public/private workspace 之间搬运数据。调用者必须明确目标 repo，并继续执行原有
license gate、review、publication、immutability 和 `DATA_ONLY/MIXED` 规则。

当前 GUI / FreeCM editor 仍把自身 checkout 作为运行 workspace。P0.3 在开始 P0.4 大规模真实数据前
应完成“software checkout 与 selected knowledge workspace”显式分离；在此之前，真实数据只能放在
经过明确控制的 private checkout/fork，而不能进入公开上游。

## 4. License taxonomy 与再分发

SourceRecord 的 taxonomy 不因仓库开源而改变：

- `PUBLIC_REFERENCE`：可公开访问的参考资料；**不表示允许重新托管或再分发原件**；
- `OPEN_LICENSE`：存在明确开放许可，仍需遵守该许可；
- `INTERNAL`：组织内部允许处理，不进入 public upstream；
- `RESTRICTED`：受限资料，按 policy fail closed；
- `LICENSED_BLOCKED_FOR_AI`：禁止 Agent/model 原文、解析、索引、embedding 等处理；
- `UNKNOWN`：权利不明确时 fail closed。

公开测试或示例要么是 synthetic，要么必须有明确的 redistribution basis。

## 5. Pull request 与 CI

公开 PR 被视为不可信输入：

- CI 默认只有 `contents: read`；
- 普通 PR 不应获得 repository secrets；
- 不接受凭据、内部 endpoint、客户标识、生产日志或未授权 evidence；
- `check_public_repo.py` 先于核心测试执行；
- code/schema/policy 变更和 knowledge data 不混 commit；
- CodeQL 在 repository public 后启用；
- Dependabot 维护 GitHub Actions pin/version 更新。

## 6. Visibility 切换前的最后门禁

当前仓库曾经存在已退役的在线服务架构，因此 private → public 之前不能只审当前 tree。必须完成：

1. **Git history secret scan**：检查所有 reachable commits，不只是 `HEAD`；
2. **历史版权/来源检查**：确认旧代码、模板、图片、fixture 等有权公开；
3. **Actions history 检查**：确认既有 logs/artifacts 不包含敏感内容；
4. **分支与 tag 检查**：确认非 `main` ref 没有不应公开内容；
5. **第三方许可检查**：确认 vendored 文件的许可证与 attribution 完整；
6. 若发现历史 secret，先 revoke/rotate，再决定是否 rewrite history。

本仓库的 public-source guard 是持续集成门禁，不是历史扫描器，不能替代上述一次性审计。

## 7. Publication boundary 不变

对 private knowledge workspace 来说，原有三层边界仍然成立：

```text
working tree DRAFT / READY_FOR_REVIEW
    = 准备中

working tree APPROVED
    = 人已批准，尚未发布

committed APPROVED in publication ref
    = Published Knowledge
```

“Published Knowledge”指在该 knowledge workspace 的受控受众范围内发布，并不自动意味着互联网公开。
