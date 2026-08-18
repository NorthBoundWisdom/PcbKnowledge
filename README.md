# PcbKnowledge

[![CI](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml/badge.svg)](https://github.com/NorthBoundWisdom/PcbKnowledge/actions/workflows/ci.yml)

PcbKnowledge 是一个 **Git-native、Agent-native、evidence-backed** 的 PCB 工程知识仓库与本机审阅工具。
它把 datasheet、application note、reference design 等外部资料中的工程事实保存为可验证的
Source / Entity / Fact / EvidenceAnchor，并把人工审阅与 Git publication 作为显式边界。

> **开源边界：** 本仓库发布的是软件、Schema、文档和 Agent workflow，采用 Apache-2.0。
> 生产知识数据、内部规范、waiver、历史 review、第三方 PDF 原件不属于本仓库的默认开源内容。
> 公开可访问的 datasheet 也不等于允许再分发。完整规则见
> [`docs/open-source-boundary.md`](docs/open-source-boundary.md)。

## 当前状态

```text
P0.0 Git-native hardening        COMPLETE
P0.1 typed authority model       COMPLETE
P0.2 Agent-native ingestion      COMPLETE
P0.3 Local Review Workbench      NEXT
P0.4 First real dataset + evals
```

当前后端 authority 与 Agent ingestion 已贯通；现有 GUI 仍是 Source Corpus editor，P0.3 将其升级为
Fact Review Workbench。路线图见 [`TODO.md`](TODO.md)，长期架构见
[`docs/architecture.md`](docs/architecture.md)。

## 核心模型

```text
knowledge/
├── sources/       SourceRecordV1
├── entities/      ManufacturerV1 / ComponentV1 / PackageV1
└── facts/         ComponentPinFactV1 / ParameterLimitFactV1

evidence/sha256/  immutable PDF originals
```

工程 Fact 可以绑定确定的 source revision、PDF page、normalized bbox 与 quote hash。Unknown、conflict、
wrong package、wrong revision、missing evidence 和 license block 都必须显式存在，不能靠模型补值。

正式 Published Knowledge 只来自同一 immutable Git ref 中经过完整校验的 committed `APPROVED` 数据；
working-tree approval 不等于 publication。

## Agent / Human 边界

Agent 可以：

- 创建、编辑和 submit Source / Entity / Fact 草稿；
- 绑定经过许可检查的 evidence；
- validate、检查 conflict / missing anchor、生成 diff；
- 把完整 `DATA_ONLY` 变更交给人工审阅。

Agent 不可以：

- approve / reject；
- stage / commit / push；
- 绕过 Source license gate 读取受限原文；
- 根据相似 MPN、相似器件或模型先验补工程事实；
- 修改 PCB board state。

## 快速开始

要求：

- Git
- Python 3.11+

不需要 Docker、数据库、账号、Node 或在线服务。

```bash
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py run
```

也可以使用 FreeCM VS Code / Cursor 扩展执行 Config / Build / Run / Test / Package。
编辑器只监听 loopback 地址，不应暴露到 LAN、VPN 或公网。

## Agent CLI

```bash
python3 configs/pcbknowledge_agent.py source list
python3 configs/pcbknowledge_agent.py entity list
python3 configs/pcbknowledge_agent.py fact list
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_agent.py change-scope
```

CLI 已支持把知识 authority 放在另一个 Git 仓库：

```bash
python3 configs/pcbknowledge_agent.py --repo ../PcbKnowledgeData validate
```

这适合 private knowledge workspace。当前 GUI / FreeCM editor 仍以自身 checkout 为 workspace root；
完整的独立 GUI workspace 支持属于 P0.3 开源解耦的一部分，在 P0.4 大规模真实数据录入前完成。

## Public source 与 private knowledge

公开上游故意保持 data-empty：

```text
knowledge/sources/.gitkeep
knowledge/entities/.gitkeep
knowledge/facts/.gitkeep
evidence/sha256/.gitkeep
```

真实 Source/Fact JSON 与 PDF 不应提交到 public source repository。机器门禁：

```bash
python3 configs/check_public_repo.py
```

任何额外的 tracked `knowledge/**` 或 `evidence/**` 文件都会使该检查失败。公开测试数据应使用
synthetic fixture，或经过单独版权/再分发审查的数据集。

`PUBLIC_REFERENCE` 表示“可公开访问的参考资料”，**不等价于** `OPEN_LICENSE`。许可证分类仍由每条
SourceRecord 自己控制；Apache-2.0 只覆盖本仓库的软件和文档，不替第三方资料重新授权。

## 验证

本地完整门禁：

```bash
python3 configs/check_public_repo.py
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
python3 configs/pcbknowledge_workflow.py package
```

GitHub Actions 会在 push / pull request 上执行同一套核心门禁；仓库公开后还会启用跨平台矩阵和
CodeQL。CI workflow 使用最小只读仓库权限，不向普通 PR 提供项目 secrets。

## 贡献

提交 PR 前请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和
[`docs/open-source-boundary.md`](docs/open-source-boundary.md)。不要把公司内部资料、未授权 PDF、
真实凭据或生产 knowledge fixture 放进 issue、PR、Actions artifact 或 Git history。

安全问题请按 [`SECURITY.md`](SECURITY.md) 私下报告，不要先公开 exploit details。

## License

PcbKnowledge software and repository documentation are licensed under the
[Apache License 2.0](LICENSE), unless a file explicitly states otherwise.
Third-party engineering documents and knowledge datasets retain their own rights and licenses.
