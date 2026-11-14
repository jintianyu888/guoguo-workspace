#!/bin/bash
# news-brief-guard.sh —— 新闻简报漏档补位（2026-11-11 建）
#
# 为什么存在：cron e3bcbd06 跑在网关进程内的事件循环定时器上。实测 11-09 12:20
# （循环卡 16s）、11-10 19:20（卡 32s）、11-09 19:20（网关重启中）三次档位整体丢失：
# 没有 receipt、没有日志、没有补跑。tick 迟到即被丢弃，上游不做 catch-up。
# 本脚本在网关外（systemd user timer）每 10 分钟看一次：档位到点后 WINDOW_MIN 分钟内
# 日志里没有该档的「推送 rc=0」，就补跑一次 tools/news-brief-push.sh。幂等，不重复推。
set -uo pipefail

W=${W:-/home/j/.openclaw/workspace}
LOG=${NB_LOG:-$W/state/work/news-brief.log}
GUARDLOG=${NB_GUARDLOG:-$W/state/work/news-brief-guard.log}
PUSH="$W/tools/news-brief-push.sh"
LOCK=${NB_LOCK:-$W/state/tmp/news-brief-guard.lock}
WINDOW_MIN=${NB_WINDOW_MIN:-50}
# 2026-11-13：档位后先给 cron 留 GRACE_MIN 分钟，避免 cron 推送还在跑就被判「漏档」
# 从而与 cron 并发双推（11-13 主公反馈「发了两遍」的成因）。
GRACE_MIN=${NB_GRACE_MIN:-10}
SLOTS=${NB_SLOTS:-"08:20 12:20 19:20"}
NOW=${NB_NOW:-$(date "+%F %H:%M")}
MODE=${1:-run}

mkdir -p "$(dirname "$LOG")" "$(dirname "$LOCK")"

TODAY=${NOW%% *}
HM=${NOW##* }
now_min=$(( 10#${HM%%:*} * 60 + 10#${HM##*:} ))

# 该档是否已经成功推送过（日志里有 "== <日期> <档>:00 开始" 且其后有 "推送 rc=0"）
# 2026-11-14：补跑时 push 日志头写的是「实际开跑时刻」而非档位时刻，原实现按
# "^== 日期 档位:00 开始" 精确匹配，导致补跑完成后下一 tick 仍判「漏档」→ 再补一遍
# （2026-11-14 早 08:30、08:40 各推一次，主公收到两份）。改为窗口匹配。
slot_done() {
  local slot="$1"
  [ -f "$LOG" ] || return 1
  awk -v d="$TODAY" -v s="$slot" -v w="$WINDOW_MIN" '
    function mins(t,   a) { split(t, a, ":"); return a[1]*60 + a[2] }
    BEGIN { sm = mins(s) }
    /^== / {
      blk = 0
      if ($2 == d && $3 ~ /^[0-9][0-9]:[0-9][0-9]:[0-9][0-9]$/) {
        m = mins(substr($3, 1, 5))
        if (m >= sm && m < sm + w) blk = 1
      }
      next
    }
    blk && /推送 rc=0/ { ok = 1 }
    END { exit(ok ? 0 : 1) }
  ' "$LOG"
}

# 找出「正在窗口内」的最新档位；没有则空
target=""
for s in $SLOTS; do
  s_min=$(( 10#${s%%:*} * 60 + 10#${s##*:} ))
  if [ "$now_min" -ge $(( s_min + GRACE_MIN )) ] && [ "$now_min" -le $(( s_min + WINDOW_MIN )) ]; then
    target="$s"
  fi
done

if [ -z "$target" ]; then
  [ "$MODE" = "--check" ] && echo "OK 不在任何档位窗口（$NOW）"
  exit 0
fi

if slot_done "$target"; then
  [ "$MODE" = "--check" ] && echo "OK $TODAY $target 已推送"
  exit 0
fi

if [ "$MODE" = "--check" ]; then
  echo "MISSING $TODAY $target 未推送（窗口内应补位）"
  exit 1
fi

# 真补位：串行锁，防 timer 与 cron 抢跑
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "$(date "+%F %T") skip: 另一个补位在跑" >> "$GUARDLOG"
  exit 0
fi
# 拿锁后再确认一次，避免与刚启动的 cron 推送撞车
if slot_done "$target"; then
  exit 0
fi
echo "$(date "+%F %T") catch-up: $TODAY $target 漏档，补跑 $PUSH" >> "$GUARDLOG"
bash "$PUSH"
rc=$?
echo "$(date "+%F %T") catch-up done rc=$rc slot=$TODAY $target" >> "$GUARDLOG"
exit "$rc"
