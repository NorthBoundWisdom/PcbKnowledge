# PcbKnowledge 文档

`docs/` 保存长期有效的产品、架构与工作流说明；仓库根目录只保留当前执行路线图 [`TODO.md`](../TODO.md)。

## 从这里开始

| 主题 | 权威文档 |
| --- | --- |
| 产品定位、Git-native authority、运行边界与演进方向 | [`architecture.md`](architecture.md) |
| 产品经理与工程师的本机操作流程 | [`local-workflow.md`](local-workflow.md) |
| Agent typed ingestion 与人工交接 | [`agent-workflow.md`](agent-workflow.md) |
| 架构决策及其当前状态 | [`adr/README.md`](adr/README.md) |
| 当前阶段、未完成项、完成门槛与里程碑收据 | [`../TODO.md`](../TODO.md) |

## 维护规则

1. 一个主题只保留一个长期 authority；相邻文档通过链接引用，不复制状态、边界或 Schema 合同。
2. 架构文档描述当前稳定事实和明确的演进边界；未完成的执行项只进入根目录 TODO。
3. 文档移动、重命名或合并时，同步 README、ADR、脚本、测试与 skill 中的仓库内引用。
4. 实现、Schema、validator、workflow 与文档不一致时视为合同漂移，应在同一变更中收敛。
5. 历史决策保留在 ADR 与 Git history；被替代的设计不能继续描述为当前运行结构。
