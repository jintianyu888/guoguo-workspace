# DeepSeek 应用 API 评估：服务端联网搜索/读链接 vs 现有搜索链

日期：2026-11-14　作者：果果　状态：实测完成（A/B 20/20 题，无失败）
数据：state/work/ds-ab-20261114-072622.csv（逐题 token/耗时/引用/抓取字符）
脚本：tools/ds-ab-test.sh（v2，Anthropic 格式）　临时运行脚本：state/work/dsab3.py

## 一、结论

1. 值得用的只有两样：**服务端联网搜索 / 读链接**，以及（非私有文件）**版面识别 PDF 解析**。
2. **不要搬**：ASR、TTS、文件存储、会话历史、前端 demo。本地 ASR 1.3–1.6s 零 token，声纹属 P0 隐私；demo 前端我们已有面板。
3. 真实收益不是省钱，是**轮次**：现有链 3 轮模型调用 + 自己写编排（搜什么、抓哪篇、失败重试）；服务端版 1 轮出结果，自带引用。

## 二、实测数据（20 题均值，deepseek-flash）

- 服务端一次调用：输入 10,032 tok / 输出 1,234 tok / 9.0 秒 / 引用 10.2 条 / 自动读 3 篇
- 现有链等价成本：抓同样 3 篇正文 = 8,732 字符 ≈ 4,958 tok 塞进上下文，且需 3 轮
- 折算（peak 价：输入 $0.30/M、输出 $1.20/M、搜索 $0.75/1000 次）
  - 服务端版：约 $0.0068/题（≈¥0.049），off-peak 约 $0.0045
  - 现有链：约 $0.018/题（含 tavily 单次约 $0.008）
  - 差价约 2.6 倍，延迟 9s vs 约 20–30s

## 三、接入要点

- 端点是 **Anthropic 兼容**：`POST https://api.deepseek.com/anthropic/v1/messages`，头 `x-api-key` + `anthropic-version: 2023-06-01`。
- 工具声明：`{"type":"deepseek_web_search","name":"deepseek_web_search"}`、`{"type":"deepseek_read_url","name":"deepseek_read_url"}`；返回含 `server_tool_use`、`web_search_tool_result`、thinking 块。
- OpenClaw 侧要新增 provider：`api: "anthropic"`、`baseUrl: https://api.deepseek.com/anthropic`、复用 store 里的 DEEPSEEK_API_KEY。属配置改动，按 L2 双审。
- 其他接口（独立 REST）：`/files`、`/messages`、`/api/asr`、`/api/tts`、`/api/ocr`、`/api/search`、`/api/fetch`。

## 四、风险与限制

1. **时效性**：样张问题（台风）答案标注「截至 11-10」，而当天是 11-14 —— 服务端索引有时间差，涉及最新状态的查询必须显式要求核对日期，或与现有链交叉验证。
2. **隐私**：搜索词与读取的页面内容会经 DeepSeek 服务器；私有文档、账本、声纹音频一律不走。
3. **计费口径**：搜索/抓取按次单独计费，与 token 分开；批量任务要估算次数。
4. **格式差异**：Anthropic 格式与现有 openai-completions provider 不通用，混用要分 provider 条目，注意 fallback 链不要交叉。
5. **引用不等于准确**：引用条数多不代表内容对；结论类任务仍需抽查。

## 五、建议路线

1. 先试点 2 个任务：news 每日摘要、情报检索类（可对照验证，不影响主链）。
2. 试点期 1 周，记录每任务 token/耗时/错误率，与现有链同题对比。
3. 试点通过再切默认搜索工具；ASR/TTS/OCR 保持本地不动。

## 六、回滚

- 试点只新增 provider 条目与 2 条任务指向，不动现有 provider/fallback；删除条目即回滚。
- 测试脚本与结果保留在 state/work/，可复现。


## 七、试点落地（2026-11-14 07:5x，主公批「推」）

- provider 条目已加：`models.providers.deepseek-anthropic`（api=anthropic-messages，baseUrl=https://api.deepseek.com/anthropic，复用 DEEPSEEK_API_KEY），`openclaw models list` 可见 `deepseek-anthropic/deepseek-flash`。
- 工具侧新增 `tools/ds-search.py`：一条命令完成搜索+读页，输出答案与来源；密钥取 `DEEPSEEK_APP_KEY`（env-kind，可读）或环境变量。
- 试点范围：**仅 agent 侧调研调用**，不改任何 cron 任务。原因：news 简报链（news-fetch.sh）本身就是零 token 的 RSS/API 聚合，替换成服务端搜索只会倒贴钱。

## 八、实测踩到的两个坑（重要）

1. **`thinking: disabled` 会让服务端工具完全失效**：请求返回 14 输入 token、0 搜索、模型直接说"我无法实时获取"。服务端工具依赖 thinking 模式；关了省不了钱，只会白跑。
2. **不注入日期会答错时间**：未给当前日期时，模型把 11 月答成 7 月（上海天气）。显式写"今天是 YYYY-MM-DD、答案必须标数据日期"后，答案正确标注 2026-11-14 08:00 来源。
3. `openclaw secrets store get` 默认输出是带省略号的展示值，脚本必须加 `--plain` 才能拿到完整值（否则 header 编码报 latin-1 错）。

## 九、试点验收口径（一周）

- 记录每次调用的 in/out token、耗时、引用条数（脚本已回显）。
- 抽查 10% 答案与来源一致性，重点看日期。
- 与同期 tavily+web_fetch 链路的人工估算对照，误差超 30% 即复盘。

