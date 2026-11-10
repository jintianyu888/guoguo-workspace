window.__GV={
 "generated_at": "2026-11-10 12:00:13",
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
   "level": "warn",
   "headline": "逾期 4",
   "details": [
    "未完成 13（等你 3）· 逾期 4",
    "定时任务 24h 652 跑 17 败 = 97.4%"
   ],
   "source": "tasks.db+cron_run_receipts",
   "name": "任务"
  },
  "资金": {
   "level": "ok",
   "headline": "deepseek ¥66.56",
   "details": [
    "deepseek 可用 66.56",
    "快照 1.7 小时前",
    "kimi: {\"currency\": \"CNY\", \"plan\": \"Plus 会员（K3.1 Pro）\"}",
    "zai: {\"norm\": {\"label\": \"GLM Coding（季卡）\", \"unit\": \"credits\", \"h5\": {\"used\": null, \"limit\": 2000, \"unit\": \"credits\", \"remaining\": null, \"pct\": null, \"reset_at\": \"2026-10-24T20:38:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\", \"reason\": \"5h 窗口重置时间已过期(2026-10-24T20:38:00+08:00)，页面数值属旧窗口残留\"}, \"week\": {\"used\": 6350, \"limit\": 10000, \"unit\": \"credits\", \"remaining\": 3650, \"pct\": 63.5, \"reset_at\": \"2026-10-29T20:46:00+08:00\", \"source\": \"https://open.bigmodel.cn/coding-plan/personal/overview\"}, \"plan_expire\": \"2027-01-15T00:00:00+08:00\", \"plan_expire_source\": \"页面实读\", \"plan_expire_reason\": null, \"captured_at\": {\"at\": \"2026-10-28T22:18:00+08:00\", \"kind\": \"snapshot\", \"note\": \"quotas 抓取时间\"}, \"status\": \"error\"}, \"h5_used\": 3}"
   ],
   "source": "model-econ/balances.json",
   "name": "资金"
  },
  "存储": {
   "level": "ok",
   "headline": "最紧 D 84%",
   "details": [
    "根盘 用 71%（余 298386668 KB）",
    "D 用 84%（余 108509528 KB）",
    "E 用 68%（余 1281242128 KB）",
    "H 用 59%（余 1607867528 KB）",
    "NAS 用 36%（余 3601797468 KB）",
    "最新归档 2026-11-09T01-02-01.130+08（1.4 天前）"
   ],
   "source": "df+归档 mtime",
   "name": "存储"
  },
  "安防": {
   "level": "ok",
   "headline": "NVR 在线",
   "details": [
    "NVR HTTP=200",
    "NVR 日扫 日志 3.0 小时前",
    "人脸扫描 日志 未采集",
    "新闻 日志 3.7 小时前",
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
  "warn": [
   "任务"
  ],
  "verdict": "bad"
 }
};
