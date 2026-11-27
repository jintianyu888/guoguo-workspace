window.__GV={
 "generated_at": "2026-11-27 23:13:34",
 "domains": {
  "服务": {
   "level": "ok",
   "headline": "网关正常",
   "details": [
    "systemd=active pid=1140488 NRestarts=1",
    "health HTTP=200",
    "DB 真实写探针=通过"
   ],
   "source": "systemd+HTTP+sqlite",
   "name": "服务"
  },
  "任务": {
   "level": "ok",
   "headline": "逾期 1",
   "details": [
    "未完成 4（等你 1）· 逾期 1",
    "定时任务 24h 449 跑 1 败 = 99.8%"
   ],
   "source": "tasks.db+cron_run_receipts",
   "name": "任务"
  },
  "资金": {
   "level": "ok",
   "headline": "deepseek ¥58.06",
   "details": [
    "deepseek 可用 58.06",
    "快照 0.0 小时前",
    "kimi: {\"currency\": \"CNY\", \"plan\": \"Plus 会员（K3.1 Pro）\"}",
    "zai: {\"norm\": {\"label\": \"GLM Coding（季卡）\", \"unit\": \"credits\", \"h5\": {\"used\": null, \"limit\": 2000, \"unit\": \"credits\", \"remaining\": null, \"pct\": null, \"reset_at\": \"2026-10-24T20:38:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\", \"reason\": \"5h 窗口重置时间已过期(2026-10-24T20:38:00+08:00)，页面数值属旧窗口残留\"}, \"week\": {\"used\": 6350, \"limit\": 10000, \"unit\": \"credits\", \"remaining\": 3650, \"pct\": 63.5, \"reset_at\": \"2026-10-29T20:46:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\"}, \"plan_expire\": \"2027-01-15T00:00:00+08:00\", \"plan_expire_source\": \"页面实读\", \"plan_expire_reason\": null, \"captured_at\": {\"at\": \"2026-10-28T22:18:00+08:00\", \"kind\": \"snapshot\", \"note\": \"quotas 抓取时间\"}, \"status\": \"error\"}, \"h5_used\": 3}"
   ],
   "source": "model-econ/balances.json",
   "name": "资金"
  },
  "存储": {
   "level": "ok",
   "headline": "最紧 NAS 87%",
   "details": [
    "根盘 用 35%（余 653956060 KB）",
    "D 用 60%（余 264750392 KB）",
    "E 用 78%（余 894085576 KB）",
    "H 用 66%（余 1362247100 KB）",
    "NAS 用 87%（余 760609980 KB）",
    "最新归档 2026-11-27T01-01-45.967+08（0.9 天前）"
   ],
   "source": "df+归档 mtime",
   "name": "存储"
  },
  "安防": {
   "level": "ok",
   "headline": "NVR 在线",
   "details": [
    "NVR HTTP=200",
    "NVR 日扫 日志 17.1 小时前",
    "人脸扫描 日志 未采集",
    "新闻 日志 0.9 小时前",
    "今日告警 0 条（其中标 P0 0）"
   ],
   "source": "NVR HTTP+日志 mtime+alerts.db",
   "name": "安防"
  },
  "模型": {
   "level": "ok",
   "headline": "模型链 OK",
   "details": [
    "模型链体检 rc=0 MODELCHAIN_OK",
    "本地 ollama 代理 HTTP=200"
   ],
   "source": "modelchain-check+ollama",
   "name": "模型"
  }
 },
 "summary": {
  "bad": [],
  "warn": [],
  "verdict": "ok"
 }
};
