#!/usr/bin/env bash
# run-notify.sh NAME EST CMD [args...] — 任务起止通报包装器(开始带预估,结束带用时)
set -u
W=/home/j/.openclaw/workspace
N="$W/tools/notify.sh"
if [ "$#" -lt 3 ]; then
  echo "用法: run-notify.sh NAME EST CMD [args...]" >&2
  exit 64
fi
NAME="$1"; EST="$2"; shift 2
bash "$N" "▶ 开始：$NAME｜预计 $EST"
T0=$(date +%s)
"$@"; RC=$?
T1=$(date +%s)
bash "$N" "✅ 结束：$NAME｜用时 $((T1-T0))s｜rc=$RC"
exit $RC
