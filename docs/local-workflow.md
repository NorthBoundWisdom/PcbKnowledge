# 本机使用流程

## 首次准备

```bash
git submodule update --init --recursive FreeCM
python3 configs/pcbknowledge_workflow.py config
python3 configs/pcbknowledge_workflow.py build
```

Config 不创建账号或密钥。Build 不联网、不下载、不运行 Docker，通常几秒完成。

## 打开与关闭

```bash
python3 configs/pcbknowledge_workflow.py run
```

默认浏览器会打开 <http://127.0.0.1:18080>。如果系统阻止自动打开，复制终端打印的 URL。
按 `Ctrl+C` 关闭；终端没有健康轮询日志。

## 提交一批资料

1. 新建或打开草稿；未知项留空。
2. 选择 PDF，保存。
3. 信息完整后提交审阅。
4. 工程师核对并批准，或写明原因退回。
5. 打开“查看变化”，确认 JSON 和二进制 receipt。
6. 使用团队熟悉的 Git GUI 完成 add/commit/push。

应用本身不会执行第 6 步。

## 协作建议

- 每个小批次单独 commit，说明来源或任务编号。
- 录入前先 pull，避免两个人同时修改同一记录。
- 不要手工重命名 evidence；路径由 digest 决定。
- 要更正已提交的批准记录，建立新记录并填写旧 ID 到 `supersedes`。

## 本地门禁

```bash
python3 configs/pcbknowledge_workflow.py test
python3 configs/pcbknowledge_agent.py validate
```

两者都应 exit 0，且测试不能有 skip。
