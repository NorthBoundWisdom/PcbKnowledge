# Contributing to PcbKnowledge

感谢你改进 PcbKnowledge。这个项目的首要约束不是“尽量多收资料”，而是保持工程知识的来源、许可、
证据和人工发布边界可验证。

## 1. 不要向 public source repo 提交生产知识

以下内容默认不接受进入公开上游：

- 真实 `knowledge/sources/**`、`knowledge/entities/**`、`knowledge/facts/**` 数据；
- datasheet、标准、内部文档或其他真实 `evidence/**` PDF；
- 公司内部 guideline、review、waiver、historical case；
- credentials、tokens、private keys、生产 URL 或可识别的内部基础设施信息；
- 你没有权利公开或再分发的测试 fixture。

公开上游的 `knowledge/**` 与 `evidence/**` 只允许仓库定义的 `.gitkeep` 占位符。
`python3 configs/check_public_repo.py` 会执行这个合同。

需要测试数据时优先使用 synthetic fixture。若确实需要公开第三方数据，必须在 PR 中说明来源、许可和
再分发依据，并单独接受维护者审核。

## 2. 开发边界

- 不要让 PcbKnowledge 成为 PcbCore 的运行时依赖，也不要修改 PCB board state。
- 当前 runtime 保持 loopback-only、Python standard library-first。
- Agent 可以 prepare / edit / submit，但不能 approve / reject / stage / commit / push。
- Unknown、conflict、wrong revision、wrong package、license block 必须 fail closed。
- `knowledge/**` / `evidence/**` 数据提交不能和 code/schema/policy/documentation 混成一个 commit。

更完整的仓库约束见 [`AGENTS.md`](AGENTS.md) 和 [`docs/architecture.md`](docs/architecture.md)。

## 3. 本地验证

至少运行：

```bash
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
```

涉及 Package 合同时再运行：

```bash
python3 configs/pcbknowledge_workflow.py package
```

涉及 GUI 时做真实 loopback smoke。跳过、截断或中断的检查不能记为通过。

## 4. Pull request

PR 应保持单一目的，并说明：

- 改了什么合同或行为；
- 为什么需要改；
- 哪些测试覆盖了它；
- 是否影响 Source / Entity / Fact / EvidenceAnchor schema；
- 是否影响 license gate、publication boundary 或 Agent 权限。

不要通过降低 validator、放宽 fail-closed policy、跳过测试或把数据与 policy 放进同一提交来让 fixture
“通过”。

## 5. Contribution license

除非你明确书面声明某次提交不是 Contribution，向本项目提交并被合并的贡献将按照仓库的
Apache License 2.0 条款提供。提交者必须确认自己有权提供相关代码、文档和测试材料。

安全漏洞请按照 [`SECURITY.md`](SECURITY.md) 私下报告。
