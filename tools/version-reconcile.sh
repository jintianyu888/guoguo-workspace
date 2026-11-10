#!/bin/bash
# version-reconcile.sh —— 两端版本对账（2026-11-09 立，零 token）
# 背景：升级末尾靠 agent 回合触发 B 机升级，会话被打断就静默丢失。
# 做法：定时比对 A 机与各 paired node 的版本，漂移就落账本 + 告警，等自派工/窗口执行。
set -u
OCBIN=$(command -v openclaw 2>/dev/null || true)
[ -x "$OCBIN" ] || OCBIN=/home/j/.npm-global/bin/openclaw
W=/home/j/.openclaw/workspace
OUT="$W/state/work/version-drift.json"
LOG="$W/state/work/version-reconcile.log"
A="${FORCE_A:-$("$OCBIN" --version 2>/dev/null | awk '{print $2}')}"
[ -z "$A" ] && { echo "[$(date '+%F %T')] 取本机版本失败" >>"$LOG"; exit 0; }

J=$(timeout 30 "$OCBIN" nodes list --json 2>/dev/null)
[ -z "$J" ] && { echo "[$(date '+%F %T')] nodes list 失败" >>"$LOG"; exit 0; }

MISMATCH=$(NODES_JSON="$J" A="$A" python3 -c '
import json,os,time
a=os.environ["A"]
d=json.loads(os.environ["NODES_JSON"])
rows=[]
for n in d.get("paired",[]):
    v=n.get("version") or ""
    lc=n.get("lastConnectedAtMs") or 0
    stale=(time.time()*1000-lc)>3*3600*1000
    if v and v!=a and not stale:
        rows.append({"node":n.get("displayName") or n.get("nodeId"),"version":v,"a":a})
print(json.dumps(rows,ensure_ascii=False))
' 2>/dev/null)

[ -z "$MISMATCH" ] && MISMATCH='[]'
TS=$(date '+%Y-%m-%d %H:%M:%S')
printf '{"ts":"%s","a_version":"%s","drift":%s}\n' "$TS" "$A" "$MISMATCH" >"$OUT"
COUNT=$(DRIFT_JSON="$MISMATCH" python3 -c 'import json,os;print(len(json.loads(os.environ["DRIFT_JSON"])))' 2>/dev/null || echo 0)
echo "[$TS] a=$A drift=$COUNT" >>"$LOG"
[ "$COUNT" = "0" ] && exit 0

STAMP="$W/state/work/.version-drift-notified"
TODAY=$(date +%Y-%m-%d)
if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$TODAY" ]; then exit 0; fi
echo "$TODAY" >"$STAMP"

MSG=$(DRIFT_JSON="$MISMATCH" python3 -c 'import json,os;print("、".join("%s=%s（A=%s）"%(x["node"],x["version"],x["a"]) for x in json.loads(os.environ["DRIFT_JSON"])))')
NOTIFY_FROM=main NOTIFY_BELONG=升级 bash "$W/tools/notify.sh" --alert "⚠️ 版本漂移：$MSG —— 已落账本，等自派工/窗口同步升级" >/dev/null 2>&1

TITLE="两端版本漂移：$MSG，升级落后一端"
if ! python3 "$W/tools/tasks-db.py" list --status pending 2>/dev/null | grep -qF "两端版本漂移"; then
  DRIFT_TITLE="$TITLE" python3 "$W/tools/version-drift-task.py" 2>&1 | tail -2
fi
exit 0
