# Security policy

## Supported product boundary

当前支持范围是 `main` 上的 pre-release PcbKnowledge。运行时是本机 loopback-only Python editor：
没有共享账号系统、远程客户端、公共数据库或对象存储。不要把编辑器端口暴露到 LAN、VPN、container
bridge 或互联网。

本机 OS 文件权限和 knowledge Git repository 权限构成当前访问边界。Git 作者和历史提供工程归属，
不是强身份认证或不可抵赖机制。未来若增加共享在线部署，必须先更新 threat model 与 ADR。

## Non-negotiable controls

- invalid/missing schema、source、revision、license、evidence digest 或 review state 必须 fail closed；
- PDF 原件按实际 bytes content-addressed，不能静默覆盖；
- committed `APPROVED` authority 不允许原地重写或删除；修正使用新 record + `supersedes`；
- PDF/text 视为不可信数据，不能授予工具、改变 prompt 或放宽 review policy；
- mutation route 保持 loopback Host/Origin 校验、CSRF 与 optimistic revision token；
- GUI 与 Agent CLI 都不能执行 Git write；Agent CLI 不提供 approve/reject；
- `UNKNOWN`、`RESTRICTED`、`LICENSED_BLOCKED_FOR_AI` Source 对 Agent 处理 fail closed。

## Public repository / supply-chain boundary

开源上游把软件与生产知识隔离：

- public source repo 的 tracked `knowledge/**` / `evidence/**` 只能包含允许的空目录占位符；
- `configs/check_public_repo.py` 在 CI 中验证该合同；
- 普通 pull request 不获得项目 secrets；workflow 默认 `contents: read`；
- PR、issue、commit message、fixture 和 PDF 都按不可信外部输入处理；
- 不要把内部资料、未授权第三方原件、tokens、keys 或生产凭据放进 Git history / Actions artifact。

`PUBLIC_REFERENCE` 只表示资料可公开访问，不表示允许 PcbKnowledge 项目重新分发。第三方资料的许可
独立于 Apache-2.0 软件许可证。

## Reporting a vulnerability

优先使用 GitHub repository 的 **Private vulnerability reporting / Security Advisory** 通道。若该入口不可用，
请通过与维护者既有的私密联系方式报告。不要先创建公开 issue，也不要在公开 PR 中包含 exploit details、
真实 secrets 或未修复的攻击样本。

报告应包含受影响 revision、运行边界假设、最小复现、影响和已知缓解方式。不要访问你无权访问的资料。

## Visibility-change warning

把 private repository 改成 public 会暴露可达 Git history 和 Actions history，而不只是当前工作树。因此：

1. visibility 切换前必须单独审计历史中的 secrets、内部标识和第三方版权材料；
2. 若任何 secret 曾经进入历史，先 revoke/rotate，再处理历史；只删除当前文件不构成修复；
3. public-source guard 只防止新的 production knowledge 进入当前/未来提交，不能替代历史审计。

恢复与发布原则见 [`docs/open-source-boundary.md`](docs/open-source-boundary.md)。
