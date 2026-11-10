#!/usr/bin/env bash
# 用户忙碌窗口（供定时任务判断是否顺延）
# 用法: user-busy.sh mark [秒] | clear | check
W=/home/j/.openclaw/workspace
F="$W/state/user-busy.until"
cmd="$1"; [ -z "$cmd" ] && cmd=check
case "$cmd" in
  mark) d="$2"; [ -z "$d" ] && d=300; echo $(( $(date +%s) + d )) > "$F"; echo "busy for $d seconds";;
  clear) rm -f "$F"; echo cleared;;
  check) u=$(cat "$F" 2>/dev/null || echo 0); if [ "$(date +%s)" -lt "$u" ]; then echo BUSY; exit 0; else echo FREE; exit 1; fi;;
  *) echo "usage: user-busy.sh mark [sec] | clear | check"; exit 2;;
esac
