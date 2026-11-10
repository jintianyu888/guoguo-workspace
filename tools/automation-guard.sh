#!/usr/bin/env bash
# 忙时顺延守卫：主公正在被服务时，把本任务顺延 +N 分钟（克隆成一次性任务），本次跳过。
# 用法: automation-guard.sh <jobId> [deferMin]
# 输出: FREE（继续执行正文）| SKIP（已顺延，勿执行正文）
set -eo pipefail
W=/home/j/.openclaw/workspace
ID="$1"; DEFER="$2"; [ -z "$DEFER" ] && DEFER=15
if [ -z "$ID" ]; then echo "usage: automation-guard.sh <jobId> [deferMin]"; exit 2; fi
U=$(cat "$W/state/user-busy.until" 2>/dev/null || echo 0)
if [ "$(date +%s)" -ge "$U" ]; then echo FREE; exit 0; fi
python3 - "$ID" "$DEFER" <<'PY'
import sys, json, subprocess, datetime
jid, defer = sys.argv[1], int(sys.argv[2])
try:
    r = subprocess.run(["openclaw","automations","get",jid,"--json"], capture_output=True, text=True, timeout=30)
    j = json.loads(r.stdout)
except Exception as e:
    print("SKIP(read job failed: %s)" % e); sys.exit(0)
p = j.get("payload") or {}; d = j.get("delivery") or {}
iso = (datetime.datetime.now() + datetime.timedelta(minutes=defer)).strftime("%Y-%m-%dT%H:%M:%S")
args = ["openclaw","automations","add","--name",(j.get("name") or "job")+"-deferred",
        "--at",iso,"--tz","Asia/Shanghai","--agent",j.get("agentId") or "main","--delete-after-run"]
if p.get("message"): args += ["--message", p["message"]]
if p.get("model"): args += ["--model", p["model"]]
if d.get("to"):
    args += ["--channel", d.get("channel") or "feishu","--to",d["to"],"--announce"]
else:
    args += ["--best-effort-deliver"]
try:
    res = subprocess.run(args, capture_output=True, text=True, timeout=30)
    print("SKIP deferred %d min (%s)" % (defer, "ok" if res.returncode==0 else "rc=%d" % res.returncode))
except Exception as e:
    print("SKIP defer failed: %s" % e)
PY
