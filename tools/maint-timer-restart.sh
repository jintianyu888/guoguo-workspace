#!/bin/bash
# maint-timer-restart.sh —— 维护管家 L2：只允许重启自己名下的定时器（白名单）
set -uo pipefail
UNIT="${1:?用法: maint-timer-restart.sh <unit> [--status]}"
ALLOW="oc-gateway-watchdog.timer oc-stuck-watch.timer oc-doctor.timer oc-skill-maintain.timer oc-skill-curator.timer oc-skill-capture.timer oc-butler-report.timer oc-host-guard.timer oc-stuck-watch.timer oc-backup-watch.timer"
case " $ALLOW " in
  *" $UNIT "*) ;;
  *) echo "REFUSED: $UNIT 不在维护管家白名单内" >&2; exit 92;;
esac
if [ "${2:-}" = "--status" ]; then
  systemctl --user status "$UNIT" --no-pager 2>&1 | head -20
else
  systemctl --user restart "$UNIT" && systemctl --user is-active "$UNIT"
fi
