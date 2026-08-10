# PcbKnowledge Git-native MVP TODO

> 状态：`COMPLETE`
> 建立日期：2026-08-10
> 目标：两位可信内部使用者克隆仓库后，双击根目录启动器或通过 FreeCM 打开本机 GUI；录入结果直接成为可读、可校验、可审阅的 Git 工作树差异。

## 1. 产品边界

- [x] 本轮不是在线平台，也不提供局域网或公网服务。
- [x] 不需要账号、密码、Keycloak、组织、租户或数据库管理员。
- [x] 本机操作权限来自操作系统文件权限；操作归属来自 Git 作者与提交历史。
- [x] GUI 只监听 loopback，不接受非本机连接。
- [x] AI Agent 与人类修改同一套规范化文件；Agent 不自动提交，人类通过 diff 审阅后提交。
- [x] 缺失来源、版本、许可或原件哈希的记录可以保存为草稿，但不能标记为 `APPROVED`。
- [x] PDF 和文本仍是不可信资料，不能改变工具、权限、验证器或审阅规则。

## 2. 权威仓库布局

- [x] `knowledge/records/<stable-id>.json`：一条记录一个稳定排序、UTF-8、末尾换行的 JSON 文件。
- [x] `evidence/sha256/<prefix>/<digest>.pdf`：原件按服务端实际字节 SHA-256 内容寻址；同 digest 不重复写入。
- [x] `schemas/knowledge-record.schema.json`：记录文件的可读 schema 与枚举说明。
- [x] `.pcbknowledge/`：可删除、可重建的本地索引和运行状态，全部忽略。
- [x] Git 中的记录与原件是唯一权威数据；SQLite/FTS/缩略图等只能作为派生缓存。

## 3. 最小数据模型

- [x] 稳定 ID、schema 版本、状态 `DRAFT / READY_FOR_REVIEW / APPROVED / REJECTED`。
- [x] 标题、资料编号、修订、来源 URL/说明、许可类别与备注。
- [x] 原件相对路径、SHA-256、字节数、媒体类型。
- [x] 明确的未知字段列表；禁止根据相似器件或模型先验补值。
- [x] 审阅结论、审阅说明与被取代记录 ID；已批准记录不可原地改写为另一份事实。
- [x] 对 JSON 进行确定性规范化，避免无意义 diff。

## 4. 本机 GUI

- [x] 首页显示“待准备 / 待审阅 / 已批准 / 已退回”和当前 Git 变化数量。
- [x] 支持创建、编辑、保存草稿；未知字段可以留空。
- [x] 支持选择 PDF，复制为内容寻址原件并自动计算 hash/size。
- [x] 支持提交审阅、批准和退回；批准前 fail closed 校验必需字段。
- [x] 支持记录列表、详情与原件打开。
- [x] 内置 Git diff 页面，同时显示已跟踪改动与未跟踪的新记录内容。
- [x] 不自动 `git add`、`git commit`、`git push`；最终提交始终由人决定。
- [x] 默认中文，无基础设施术语、登录页或服务健康日志刷屏。

## 5. Agent 使用面

- [x] 提供同一 Python 核心库和 CLI：list/show/create/update/submit/validate。
- [x] CLI 只读写仓库文件，不连接数据库、不读取人类凭据。
- [x] 创建使用调用方提供的稳定 idempotency key 映射 stable ID。
- [x] 输出明确的 `missing_fields`、状态与下一动作。
- [x] Agent 不提供 approve/reject/commit/push 命令。

## 6. FreeCM 本机工作流

- [x] Config：验证 Python/Git、创建轻量 receipt，不下载服务镜像。
- [x] Build：编译检查、校验全部知识文件、运行测试并写 source receipt。
- [x] Run：校验 receipt，启动单一本机进程、自动打开 GUI、Ctrl+C 干净停止。
- [x] 根目录双击启动器：首次自动完成 Config / Build，之后复用有效收据直接打开。
- [x] Test：只运行本地标准库测试，无 Docker、数据库、S3 或托管 CI。
- [x] Package：导出可复现的 Git-native 数据快照与校验清单，不打包容器镜像。
- [x] `source_roots.lock.jsonc.in` 继续保持空依赖。

## 7. 旧平台下线

- [x] 删除 Compose、Docker、Keycloak、PostgreSQL、SeaweedFS、Caddy、observability 和 migration 运行面。
- [x] 删除在线 API、后台 Worker、verifier、OIDC/RLS/outbox/job/storage 实现。
- [x] 删除 React/pnpm 构建链；GUI 改为仓库内无编译静态资源和本机 Python 服务。
- [x] 删除旧服务测试、部署脚本、锁文件与生成 OpenAPI 客户端。
- [x] 保留历史 ADR，但由 ADR-018 显式标记哪些决定已被取代。
- [x] 更新 README、AGENTS、架构与操作文档，只描述当前可执行能力。

## 8. 验收门槛

- [x] 在不运行 Docker 的情况下完成 Config → Build → Run。
- [x] Run 在 2 秒级打开 loopback GUI，终端无轮询刷屏。
- [x] GUI 完成：新建草稿 → 选择 PDF → 编辑 → 送审 → 批准 → 查看 diff。
- [x] Agent CLI 创建/修改草稿后，GUI 立即看到同一记录。
- [x] `git diff`/未跟踪预览清楚展示录入结果；JSON 重写无无意义漂移。
- [x] 非 PDF、hash/path 不一致、越界路径、非法状态和批准缺字段全部 fail closed。
- [x] 单元/纵向测试全部通过，0 skipped；FreeCM validator 通过。
- [x] 不提交、不推送本轮改动。

## 9. 运行收据

完成后记录命令、exit code、case 数、skip 数、首个失败及纠偏。未执行或截断的检查不得记为通过。

- 首轮完整门禁的唯一失败：`git diff --check` 发现架构文档 2 处行尾空格；清理后复跑通过。
- `python3 configs/pcbknowledge_workflow.py run`：首秒内 ready，自动打开 `http://127.0.0.1:18080`，首页 HTTP 200，无登录页；`Ctrl+C` 返回 130。
- Run 期间 `pcbknowledge-freecm` Docker 容器数为 0；旧容器已停止，旧卷和 `backups/` 未删除。
- 旧服务未跟踪材料可恢复地移动到 `~/.Trash/PcbKnowledge-retired-service-20260810/`。
- `python3 configs/pcbknowledge_workflow.py config`：exit 0。
- `python3 configs/pcbknowledge_workflow.py build`：exit 0，33/33 tests passed，0 skipped，0 records validated。
- `python3 configs/pcbknowledge_workflow.py test`：exit 0，33/33 tests passed，0 skipped；`git diff --check` 通过。
- `python3 configs/pcbknowledge_workflow.py package`：exit 0；快照 `build/package/PcbKnowledge_aced0464d948a291.zip`，SHA-256 `77e66577b6f2a40cd8508fe55c674875b0bbe2d4b58cf51e7139dcf545bd04de`。
- `python3 configs/validate_freecm_repo_commands.py`：exit 0，Config / Build / Run / Test / Package 五个动作均解析为 Git-native 本机命令。
- 最终真实 Run：首秒 ready；首页 HTTP 200、无登录；相关 Docker 容器数 0；`Ctrl+C` exit 130。
- 根目录启动器首次检测到过期收据后在约 4 秒完成 33 个本机检查并打开首页；第二次在首秒 ready；两次 `Ctrl+C` 均 exit 130。
