window.__GV={
 "generated_at": "2026-11-10 19:20:16",
 "domains": {
  "服务": {
   "level": "bad",
   "headline": "网关异常",
   "details": [
    "systemd=active pid=3882668 NRestarts=0",
    "health HTTP=0",
    "DB 真实写探针=通过"
   ],
   "source": "systemd+HTTP+sqlite",
   "name": "服务"
  },
  "任务": {
   "level": "ok",
   "headline": "逾期 0",
   "details": [
    "未完成 3（等你 0）· 逾期 0",
    "定时任务 24h 655 跑 13 败 = 98.0%"
   ],
   "source": "tasks.db+cron_run_receipts",
   "name": "任务"
  },
  "资金": {
   "level": "ok",
   "headline": "deepseek ¥162.35",
   "details": [
    "deepseek 可用 162.35",
    "快照 1.0 小时前",
    "kimi: {\"currency\": \"CNY\", \"plan\": \"Plus 会员（K3.1 Pro）\"}",
    "zai: {\"norm\": {\"label\": \"GLM Coding（季卡）\", \"unit\": \"credits\", \"h5\": {\"used\": null, \"limit\": 2000, \"unit\": \"credits\", \"remaining\": null, \"pct\": null, \"reset_at\": \"2026-10-24T20:38:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\", \"reason\": \"5h 窗口重置时间已过期(2026-10-24T20:38:00+08:00)，页面数值属旧窗口残留\"}, \"week\": {\"used\": 6350, \"limit\": 10000, \"unit\": \"credits\", \"remaining\": 3650, \"pct\": 63.5, \"reset_at\": \"2026-10-29T20:46:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\"}, \"plan_expire\": \"2027-01-15T00:00:00+08:00\", \"plan_expire_source\": \"页面实读\", \"plan_expire_reason\": null, \"captured_at\": {\"at\": \"2026-10-28T22:18:00+08:00\", \"kind\": \"snapshot\", \"note\": \"quotas 抓取时间\"}, \"status\": \"error\"}, \"h5_used\": 3}"
   ],
   "source": "model-econ/balances.json",
   "name": "资金"
  },
  "存储": {
   "level": "ok",
   "headline": "最紧 D 83%",
   "details": [
    "根盘 用 52%（余 487962240 KB）",
    "D 用 83%（余 119042840 KB）",
    "E 用 56%（余 1751273560 KB）",
    "H 用 46%（余 2118371412 KB）",
    "NAS 用 37%（余 3564919564 KB）",
    "最新归档 2026-11-10T01-01-55.465+08（0.0 天前）"
   ],
   "source": "df+归档 mtime",
   "name": "存储"
  },
  "安防": {
   "level": "ok",
   "headline": "NVR 在线",
   "details": [
    "NVR HTTP=200",
    "NVR 日扫 日志 10.4 小时前",
    "人脸扫描 日志 未采集",
    "新闻 日志 7.0 小时前",
    "今日告警 0 条（其中标 P0 0）"
   ],
   "source": "NVR HTTP+日志 mtime+alerts.db",
   "name": "安防"
  },
  "模型": {
   "level": "ok",
   "headline": "模型链 OK",
   "details": [
    "模型链体检 rc=0   FAIL 本地模型未安装: ollama/qwen3:30b-a3b-instruct-2507-q4_K_M",
    "本地 ollama 代理 HTTP=200"
   ],
   "source": "modelchain-check+ollama",
   "name": "模型"
  }
 },
 "summary": {
  "bad": [
   "服务"
  ],
  "warn": [],
  "verdict": "bad"
 }
};
