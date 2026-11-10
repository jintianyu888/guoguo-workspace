#!/bin/bash
# cron-detached.sh —— 把长任务交给 systemd --user 独立运行，cron 立即返回
# 背景：网关"命令型自动化任务"有 600 秒硬超时（实测 lastDurationMs=600359 被杀），
#       加密备份 ~2700s、NVR 扫描 ~1800s 必然被杀。systemd-run 分离后不受此限。
# 用法: cron-detached.sh <unit-name> <命令...>
# 行为: ① 同名 unit 已在跑 → 跳过（防重叠）② 输出落 state/work/<unit>-<时间>.log
#       ③ 退出码非 0 → 飞书告警（notify.sh）④ 成功后结果首行也写进日志尾部
set -uo pipefail
UNIT=${1:-}
[ -n "$UNIT" ] && shift
if [ -z "$UNIT" ] || [ $# -lt 1 ]; then
  echo "用法: cron-detached.sh <unit-name> <命令...>"; exit 2
fi
W=/home/j/.openclaw/workspace
LOGD="$W/state/work"
mkdir -p "$LOGD"
STAMP=$(date +%Y%m%d-%H%M%S)
LOG="$LOGD/$UNIT-$STAMP.log"

if systemctl --user is-active --quiet "$UNIT" 2>/dev/null; then
  echo "SKIP: $UNIT 已在运行（防重叠），本次不启动"; exit 0
fi

CMD=$(printf '%q ' "$@")
RUN="cd $W && { $CMD ; } ; rc=\$?; "
RUN="$RUN"'echo "[detached] 结束 rc='"\$rc"' 时间 $(date +%F\ %T)" >> "'"$LOG"'"; '
RUN="$RUN"'if [ '"\$rc"' -ne 0 ]; then bash '"$W"'/tools/notify.sh "❌ 长任务 '"$UNIT"' 失败 rc='"\$rc"'（日志 '"$LOG"'）" >/dev/null 2>&1 || true; fi; exit '"\$rc"

if systemd-run --user --unit="$UNIT" --collect \
     --property=TimeoutStartSec=infinity \
     --property=StandardOutput=append:"$LOG" \
     --property=StandardError=append:"$LOG" \
     bash -lc "$RUN" >/dev/null 2>&1; then
  echo "🚀 已分离启动 $UNIT（unit=$UNIT，日志 $LOG）"
  exit 0
fi

# 兜底：unit 名残留或被占用 → 用带时间戳的名字重试一次
UNIT2="$UNIT-$STAMP"
if systemd-run --user --unit="$UNIT2" --collect \
     --property=TimeoutStartSec=infinity \
     --property=StandardOutput=append:"$LOG" \
     --property=StandardError=append:"$LOG" \
     bash -lc "$RUN" >/dev/null 2>&1; then
  echo "🚀 已分离启动 $UNIT2（原 unit 名不可用，日志 $LOG）"
  exit 0
fi
echo "❌ systemd-run 启动失败（$UNIT）"; exit 1
