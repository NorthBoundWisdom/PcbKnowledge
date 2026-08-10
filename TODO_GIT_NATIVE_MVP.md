# PcbKnowledge Git-native MVP TODO

> 状态：`COMPLETE`（历史里程碑收据）
> 建立日期：2026-08-10
> 完成基线：Git-native local editor milestone
> 当前后续计划：[`TODO_GIT_NATIVE_KNOWLEDGE_P0.md`](TODO_GIT_NATIVE_KNOWLEDGE_P0.md)

## 0. 文档定位

本文件只记录 **Git-native 本机编辑器 MVP** 当时完成了什么，不再作为当前开发计划或最终知识模型 authority。

MVP 完成后又发生了两类演进：

1. P0.0 对 publication snapshot、review history、evidence cleanup、并发写入与 change-scope 做了 hardening；
2. P0.1 已把过渡性的 `knowledge/records/` 资料登记模型迁移为正式 `sources/entities/facts` typed authority。

因此本文件中的 `knowledge/records/`、Schema v2 等描述应理解为“该历史里程碑的可执行形态”，不能覆盖最新 [架构文档](PcbKnowledge_ARCHITECTURE.md) 和 P0 TODO。

## 1. 当时的产品边界

- [x] 不是在线平台，也不提供局域网或公网服务。
- [x] 不需要账号、密码、Keycloak、组织、租户或数据库管理员。
- [x] 本机权限来自操作系统文件权限；协作归属来自 Git 作者与提交历史。
- [x] GUI 只监听 loopback。
- [x] Agent 与人类修改同一套规范化仓库文件。
- [x] Agent 不自动提交；人通过 diff 审阅后决定 commit/push。
- [x] 缺失来源、版本、许可或原件的记录可以 Draft，但不能批准。
- [x] PDF/文本是不可信数据，不能改变工具、权限、validator 或审阅规则。

## 2. MVP authority layout

当时完成：

```text
knowledge/records/<stable-id>.json
evidence/sha256/<prefix>/<digest>.pdf
schemas/knowledge-record.schema.json
```

- [x] JSON canonical、UTF-8、稳定键顺序、末尾换行。
- [x] PDF 按实际 bytes SHA-256 内容寻址并去重。
- [x] `.pcbknowledge/`、索引、预览、package 都是可删除派生物。
- [x] SQLite/FTS 不作为 authority。

说明：`knowledge/records/` 是 MVP 的资料级过渡模型；P0.1 已在零真实数据窗口迁移到 `knowledge/sources|entities|facts`，没有保留双写格式。

## 3. MVP 最小记录模型

当时完成：

- [x] stable ID、schema version、`DRAFT / READY_FOR_REVIEW / APPROVED / REJECTED`。
- [x] title、document number、revision、source、license、notes。
- [x] PDF path/SHA-256/size/media type。
- [x] explicit unknown；禁止根据相似器件或模型先验补值。
- [x] review decision 与 supersedes。
- [x] canonical serialization。

MVP 后的 P0.0 已进一步加入 append-only review history、严格 published Git snapshot、evidence/reference concurrency hardening 和 code/data commit isolation；这些更新以当前代码和架构为准。

## 4. 本机 GUI

- [x] 首页显示待准备/待审阅/已批准/已退回与 Git change count。
- [x] 创建、编辑、保存 Draft。
- [x] 选择 PDF 并自动导入 content-addressed evidence。
- [x] submit/approve/reject 基础状态流。
- [x] 记录列表、详情、打开原件。
- [x] Git diff / untracked preview。
- [x] GUI 不执行 `git add`、`git commit`、`git push`。
- [x] 默认中文，不出现登录和服务基础设施页面。

当前这套页面的产品含义是 **Source Corpus editor**，不是最终 Fact Review Workbench。

## 5. Agent 使用面

- [x] 提供本地 CLI：list/show/create/update/submit/validate/diff。
- [x] CLI 读写仓库文件，不依赖数据库或人类凭据。
- [x] idempotency key 生成稳定 ID。
- [x] 输出 missing fields、状态和 next action。
- [x] Agent 没有 approve/reject/commit/push。

MVP 以后增加的 published read、change-scope、license processing gate 不属于本里程碑原始完成口径，但属于当前 P0.0 已实现能力。

## 6. FreeCM 本机工作流

- [x] Config：验证 Python/Git并写轻量 receipt。
- [x] Build：编译、测试、validate 数据并写 source-bound receipt。
- [x] Run：校验 receipt，启动一个 loopback editor，并自动打开浏览器。
- [x] 双击根启动器完成首次 Config/Build，后续复用 receipt。
- [x] Test：纯本地标准库测试，无 Docker/数据库/S3。
- [x] Package：导出确定性 Git-native snapshot + manifest + SHA-256 sidecar。
- [x] `source_roots.lock.jsonc.in` 保持空依赖。

## 7. 旧服务平台下线

- [x] 删除 Compose、Docker、Keycloak、PostgreSQL、SeaweedFS、Caddy、observability、migration runtime。
- [x] 删除在线 API、后台 Worker、OIDC/RLS/outbox/job/storage 实现。
- [x] 删除 React/pnpm build chain；GUI 改为本机 Python + repository-owned static assets。
- [x] 删除旧部署脚本、锁文件和生成 OpenAPI client。
- [x] 历史 ADR 保留，但 ADR-018 标注 superseded decisions。
- [x] README/AGENTS/架构/操作文档更新为 Git-native 边界。

## 8. MVP 验收门槛

- [x] 无 Docker 完成 Config → Build → Run。
- [x] Run 秒级打开 loopback GUI。
- [x] GUI 完成 Draft → PDF → edit → submit → approve → diff。
- [x] Agent CLI 修改后 GUI 看到同一文件。
- [x] Git diff/untracked preview 可审阅。
- [x] 非 PDF、hash/path 不一致、非法状态、批准缺字段 fail closed。
- [x] 单元/纵向测试 0 skipped；FreeCM validator 通过。
- [x] MVP 实现任务本身按当时要求未自动提交/推送。

## 9. 当时的运行收据

以下保持为历史事实，不因后续增加测试而重写 case 数：

- 首轮完整门禁唯一失败：`git diff --check` 发现架构文档 2 处行尾空格；修复后通过。
- `python3 configs/pcbknowledge_workflow.py run`：首秒内 ready，自动打开 `http://127.0.0.1:18080`，HTTP 200，无登录；`Ctrl+C` 返回 130。
- Run 期间 `pcbknowledge-freecm` Docker 容器数为 0。
- 旧服务未跟踪材料可恢复地移动到 `~/.Trash/PcbKnowledge-retired-service-20260810/`。
- `config`：exit 0。
- `build`：exit 0，33/33 tests passed，0 skipped，0 records validated。
- `test`：exit 0，33/33 tests passed，0 skipped；`git diff --check` 通过。
- `package`：exit 0；`build/package/PcbKnowledge_aced0464d948a291.zip`；SHA-256 `77e66577b6f2a40cd8508fe55c674875b0bbe2d4b58cf51e7139dcf545bd04de`。
- `validate_freecm_repo_commands.py`：exit 0，Config/Build/Run/Test/Package 五个动作均解析为 Git-native 命令。
- 最终真实 Run：首秒 ready；HTTP 200；无登录；相关 Docker 容器数 0；Ctrl+C exit 130。
- 根启动器首次约 4 秒完成当时 33 个检查并打开首页；第二次首秒 ready。

## 10. 后续不在本文件追踪

以下均由 [`TODO_GIT_NATIVE_KNOWLEDGE_P0.md`](TODO_GIT_NATIVE_KNOWLEDGE_P0.md) 负责：

- publication snapshot hardening；
- review history hardening；
- SourceRecord/EntityRecord/FactRecord/EvidenceAnchor；
- typed PCB facts；
- Agent-native ingestion skills；
- Review Workbench；
- real dataset / evals；
- SQLite exact/FTS；
- PCBAtlas/PcbCore/iOS integration。
