# 额度对账表（自动生成 2026-10-28T23:07:01+08:00）

| 家 | 页面/接口值 | 入库(归一) | 面板 | 判定 |
|---|---|---|---|---|
| 智谱 | 5h None/2000 None% | reset 2026-10-24T20:38:00+08:00 | None | 待校准：5h 窗口重置时间已过期(2026-10-24T20:38:00+08:00)，页面数值属旧窗口残留 |
| 智谱 | 周 6350/10000 (63.5%) | 2026-10-29T20:46:00+08:00 | 周=63.5% | 一致 |
| DeepSeek | 可用 ¥199.73 | 官方 API | ¥199.73 | 以 API 为权威 |
| Kimi | 月 6.92% · 钱包 33.91617 | 页面 | 月 6.92% | 0 兜底已禁用 |
| MiniMax | 5h 0% · 周 4% · 到期 2026-11-20T00:00:00+08:00 | /console/plan | 同上 | 两源冲突已裁定 |

## 冲突清单

- **zai · h5.used**：{"quotas.json": 737, "balances.json": 3} → 窗口已重置 → 旧 used 作废（resolved=None）
- **deepseek · available**：{"official_api": 199.73, "page": 201.87} → 官方 API 为权威（resolved=199.73）
- **minimax · plan**：{"quotas.json": "钱包为空/未购买套餐", "balances.json": "M Plan Explore 月度会员（月卡）"} → /console/plan 为准（resolved=M Plan Explore 月度会员（月卡））
