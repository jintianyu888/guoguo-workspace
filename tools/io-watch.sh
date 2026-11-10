#!/bin/sh
python3 /home/j/.openclaw/workspace/tools/quiet_window.py >/dev/null 2>&1 && exit 0
# io-watch.sh v1 —— I/O 卡死哨兵（2026-10-02 建）
# 体检：PSI io 压力 + D 状态 + swap + /tmp + 根盘水位 + drvfs 延迟探针
# 只报「异常出现/解除」各一次，绝不复读
W=/home/j/.openclaw/workspace; S=$W/state/.iowatch; mkdir -p "$S"
LF=$S/last; LAST=$(cat "$LF" 2>/dev/null)
ISSUE=""

IF=$(awk '/^full/{for(i=1;i<=NF;i++) if($i ~ /^avg300=/){sub("avg300=","",$i); print $i}}' /proc/pressure/io 2>/dev/null)
if [ -n "$IF" ]; then
  BIG=$(awk -v v="$IF" 'BEGIN{print (v>5)?1:0}')
  [ "$BIG" = "1" ] && ISSUE="$ISSUE IO压力高(full avg300=$IF%);"
fi

# 2026-10-17 双评审后改：只有「原生盘 + 无 9p 特征 + 上下文切换零增长」才算真卡死
# 9p/Windows 盘（/mnt/*）读大文件时 D 态是正常等待，不再报警
STUCK=""
for p in $(ps -eo stat=,pid=,comm= --no-headers 2>/dev/null | awk '$1 ~ /^D/ && $3 !~ /^\[/ {print $2}'); do
  W1=$(cat /proc/$p/wchan 2>/dev/null)
  C1=$(tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null)
  case "$W1" in *p9*|*v9fs*|*9p*|*rpc*) continue ;; esac
  case "$C1" in *"/mnt/"*) continue ;; esac
  CT=$(awk '/^voluntary_ctxt_switches/{print $2}' /proc/$p/status 2>/dev/null)
  PREV=$(cat "$S/d.$p" 2>/dev/null)
  printf '%s' "${CT:-0}" > "$S/d.$p"
  [ "$CT" = "$PREV" ] || continue
  STUCK="$STUCK $p"
done
if [ -n "$STUCK" ]; then
  NAMES=$(for p in $STUCK; do printf '%s(%s) ' "$p" "$(cat /proc/$p/comm 2>/dev/null)"; done)
  ISSUE="$ISSUE 真卡死候选:${NAMES};"
fi

SU=$(free 2>/dev/null | awk '/^Swap:/{if($2>0) printf "%d", $3*100/$2}')
[ -n "$SU" ] && [ "$SU" -gt 60 ] && ISSUE="$ISSUE Swap=$SU%;"

TP=$(df /tmp 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5); print $5}')
[ -n "$TP" ] && [ "$TP" -gt 80 ] && ISSUE="$ISSUE /tmp=$TP%;"

RP=$(df / 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5); print $5}')
[ -n "$RP" ] && [ "$RP" -gt 90 ] && ISSUE="$ISSUE 根盘=$RP%;"

if [ -d /mnt/d ]; then
  T0=$(date +%s%N)
  timeout 5 dd if=/dev/zero of=/mnt/d/_iowatch.tmp bs=1M count=2 conv=fsync >/dev/null 2>&1
  RC=$?
  rm -f /mnt/d/_iowatch.tmp 2>/dev/null
  T1=$(date +%s%N)
  MS=$(( (T1-T0)/1000000 ))
  if [ "$RC" -ne 0 ] || [ "$MS" -gt 1000 ]; then
    ISSUE="$ISSUE drvfs慢($MS ms);"
  fi
fi

[ "$ISSUE" = "$LAST" ] && exit 0
printf "%s" "$ISSUE" > "$LF"
if [ -n "$ISSUE" ] && [ -z "$LAST" ]; then
  echo "🧊 I/O 哨兵（$(date '+%m-%d %H:%M')）异常：$ISSUE"
  echo "—— 处置：D 卡死的同步进程我直接清；/tmp、swap、磁盘按阈值清；drvfs 慢属 Windows 端忙，等它缓。"
elif [ -z "$ISSUE" ] && [ -n "$LAST" ]; then
  echo "✅ I/O 哨兵已解除（之前：$LAST）"
fi
