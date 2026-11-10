#!/usr/bin/env bash
# 检查「剧本每日交付」最近一次运行是否成功投递。失败/未跑 → 输出告警（由 announce 投递给麦克）。成功 → 静默。零 token。
set -u
J=$(openclaw cron list --json 2>/dev/null | python3 -c '
import sys,json
try:
    d=json.load(sys.stdin)
    jobs=d if isinstance(d,list) else (d.get("jobs") or d.get("items") or [])
    for j in jobs:
        if (j.get("name") or "")=="script-daily-delivery":
            print(j.get("id") or j.get("jobId") or ""); break
except Exception: pass')
if [ -z "$J" ]; then echo "⚠️ 未找到「script-daily-delivery」任务，请让麦克检查。"; exit 0; fi
openclaw cron runs "$J" --json 2>/dev/null | python3 -c '
import sys,json,datetime
try:
    d=json.load(sys.stdin); es=d.get("entries") or []
except Exception:
    print("⚠️ 无法读取剧本交付任务的运行记录，请让麦克检查。"); raise SystemExit
if not es:
    print("⚠️ 今天的剧本交付任务没有运行记录（08:30 可能没触发），请让麦克检查。"); raise SystemExit
e=es[-1] if isinstance(es,list) else es
ts=str(e.get("tsIso") or "")
today=datetime.datetime.now().strftime("%Y-%m-%d")
if ts and not ts.startswith(today):
    print("⚠️ 剧本交付最近一次运行是 %s（不是今天），今天 08:30 可能没触发。请让麦克检查。" % ts[:16]); raise SystemExit
ds=(e.get("deliveryStatus") or "").lower()
if ds=="delivered": raise SystemExit
status = ds or e.get("status") or "未知"
print("⚠️ 今天的剧本交付投递状态＝%s。请让麦克立刻兜底补发。" % status)
'
