#!/usr/bin/env bash
# pre-restart-check.sh v3 —— 重启/关机/升级前的“维护预告”（只读；不改配置、不触发动作）
# 由维护管家(maint)账号发给主公：动作+项目、原因、预计耗时与完成时间、出问题怎么办、当前快照
# 用法：
#   pre-restart-check.sh --push --action restart --item "网关重启" --reason "改配置"
#   pre-restart-check.sh --push --action shutdown --item "Windows 关机" --reason "夜间停机"
#   pre-restart-check.sh --commit <秒> --action restart --reason "原因"   成功后记录实际耗时
#   pre-restart-check.sh --dry-run
# 退出码：0 正常 / 2 参数错误 / 3 目标为空 / 4 推送失败 / 5 历史写入失败
set -u -o pipefail
export PATH="/home/j/.npm-global/bin:$PATH"
export LC_ALL=C.UTF-8 LANG=C.UTF-8

WS=/home/j/.openclaw/workspace
STATE="$WS/state/pre-restart"
mkdir -p "$STATE" 2>/dev/null || true
ACC="${MAINT_NOTICE_ACC:-maint}"
TARGET="${MAINT_NOTICE_TARGET:-user:ou_008693513eb3b36f292fcfaa7a8b57b3}"
PUSH=0
DRY=0
REASON="-"
ACTION="-invalid-"
ITEM="-"
COMMIT=""
COMMIT_GIVEN=0

usage() {
  cat <<USAGE
用法：pre-restart-check.sh [--push] [--dry-run] [--action restart|shutdown|upgrade]
                          [--item 项目名] [--reason 原因] [--commit 秒]
退出码 0 正常 / 2 参数错误 / 3 目标为空 / 4 推送失败 / 5 历史写入失败
USAGE
}

sanitize() {
  local s
  s="$(printf "%s" "${1:-}" | tr -d "\000-\037\177" | tr "|" "/" | tr -s " ")"
  if [ ${#s} -gt 120 ]; then s="${s:0:120}"; fi
  if [ -z "$s" ]; then s="-"; fi
  printf "%s" "$s"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --push) PUSH=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --reason) if [ $# -lt 2 ]; then echo "--reason 需要值" >&2; exit 2; fi; REASON="$(sanitize "$2")"; shift 2 ;;
    --action) if [ $# -lt 2 ]; then echo "--action 需要值" >&2; exit 2; fi; ACTION="$(printf "%s" "$2" | tr "A-Z" "a-z")"; shift 2 ;;
    --item) if [ $# -lt 2 ]; then echo "--item 需要值" >&2; exit 2; fi; ITEM="$(sanitize "$2")"; shift 2 ;;
    --commit) if [ $# -lt 2 ]; then echo "--commit 需要值" >&2; exit 2; fi; COMMIT="$2"; COMMIT_GIVEN=1; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数：$1" >&2; usage >&2; exit 2 ;;
  esac
done

# --- 参数互斥与取值校验 ---
case "$ACTION" in
  restart|shutdown|upgrade) ;;
  *) echo "--action 只能是 restart|shutdown|upgrade（收到：$ACTION）" >&2; exit 2 ;;
esac
if [ -n "$COMMIT" ] && { [ "$PUSH" = "1" ] || [ "$DRY" = "1" ]; }; then
  echo "--commit 不能与 --push/--dry-run 同用" >&2; exit 2
fi
now="$(date "+%Y-%m-%d %H:%M:%S")"

# --- 记录实际耗时（history.log 唯一写入口）---
if [ "$COMMIT_GIVEN" = "1" ] && [ -z "$COMMIT" ]; then echo "--commit 值不能为空" >&2; exit 2; fi
if [ "$COMMIT_GIVEN" = "1" ]; then
  case "$COMMIT" in
    *[!0-9]*) echo "--commit 需为非负整数秒" >&2; exit 2 ;;
  esac
  if [ "$COMMIT" -gt 7200 ]; then echo "--commit 超出上限 7200 秒，拒绝写入" >&2; exit 2; fi
  if ! printf "%s|%s|%s|%s\n" "$now" "$COMMIT" "$REASON" "$ACTION" >> "$STATE/history.log" 2>/dev/null; then
    echo "历史写入失败" >&2
    exit 5
  fi
  exit 0
fi

# --- 预计耗时：按动作取历史中位数（偶数取两者均值），无同类样本用默认 ---
est_for() {
  local act="$1" def="$2" v=""
  v="$(awk -F"[|]" -v act="$act" '{ if ($4==act) { gsub(/[^0-9]/,"",$2); if ($2!="") a[++n]=$2+0 } } END{ if (n==0) {print 0; exit} for(i=1;i<=n;i++) for(j=i+1;j<=n;j++) if (a[j]<a[i]) {t=a[i];a[i]=a[j];a[j]=t} if (n%2==1) print a[(n+1)/2]; else printf "%d\n", (a[n/2]+a[n/2+1])/2 }' "$STATE/history.log" 2>/dev/null)"
  case "$v" in
    ""|0|*[!0-9]*) v="$def" ;;
  esac
  printf "%s" "$v"
}
# 2026-11-08 修：原实现取的是我们自填的承诺值，不是真实耗时；改为从 safe-restart.log 实测
est_measured() {
  local act="$1" med=""
  case "$act" in
    restart)
      med="$(awk -F'[][]' '/systemctl --user restart/{c="date -d \""$2"\" +%s"; c|getline s; close(c); t=s} /OK new_pid/{c="date -d \""$2"\" +%s"; c|getline e; close(c); if(t){print e-t; t=0}}' "$WS/state/work/safe-restart.log" 2>/dev/null | sort -n | awk '{a[NR]=$1} END{ if(NR<3) exit; if(NR%2) print a[(NR+1)/2]; else printf "%d\n",(a[NR/2]+a[NR/2+1])/2 }')" ;;
  esac
  printf "%s" "$med"
}
MEAS_N="$(awk -F'[][]' '/systemctl --user restart/{t=1} /OK new_pid/{if(t){n++; t=0}} END{print n+0}' "$WS/state/work/safe-restart.log" 2>/dev/null)"
MEAS_EST="$(est_measured "$ACTION")"
SRC="历史中位数；无历史则用默认值"
case "$ACTION" in
  shutdown) EST="$(est_for shutdown 60)"; LABEL="关机" ;;
  upgrade) EST="$(est_for upgrade 300)"; LABEL="升级" ;;
  *) LABEL="重启"
     if [ -n "$MEAS_EST" ]; then EST="$MEAS_EST"; SRC="近 ${MEAS_N} 次实跑；实测中位数"; else EST="$(est_for restart 30)"; fi ;;
esac
eta="$(date -d "+${EST} seconds" "+%H:%M:%S" 2>/dev/null)"
if [ -z "${eta:-}" ]; then eta="?"; fi

# --- 当前快照（全部带超时）---
pid="$(timeout 3 systemctl --user show -p MainPID --value openclaw-gateway.service 2>/dev/null)"
if [ -z "${pid:-}" ]; then pid="?"; fi
health="$(timeout 3 curl -s -o /dev/null -m 2 -w "%{http_code}" http://127.0.0.1:18789/health 2>/dev/null)"
if [ -z "${health:-}" ]; then health="000"; fi
load="$(cut -d" " -f1 /proc/loadavg 2>/dev/null)"
mem="$(free -m 2>/dev/null | awk 'NR==2{printf "%d%%", ($3*100)/$2}')"
root="$(timeout 4 df -h / 2>/dev/null | awk 'NR==2{print $4}')"

BODY="🔧【维护预告】${LABEL}：${ITEM}
· 原因：${REASON}
· 预计耗时：约 ${EST} 秒（${SRC}）
· 预计完成：${eta}
· 当前快照：pid=${pid} /health=${health} 负载=${load} 内存=${mem} 根盘余=${root}

⚠️ 出问题怎么办：
1) 双击桌面「OpenClaw一键自救.bat」→ 选 [1] 自动自救（网关外的独立程序，网关全死也能用）
2) 或什么都不做：看门狗每 2 分钟检查，掉线自动拉起（30 分钟内最多 3 次，之后告警）
3) 仍不行：WSL 里跑 bash ${WS}/tools/desktop-rescue.sh，证据包落 state/work/rescue/
4) 随时喊果果
时间：${now}"

if [ "$DRY" = "1" ]; then
  printf "%s\n" "$BODY"
  exit 0
fi

if [ "$PUSH" = "1" ]; then
  if [ -z "$TARGET" ]; then echo "推送目标为空" >&2; exit 3; fi
  # 120 秒内已推过同类预告则跳过，防连点重复打扰
  cut="$(date -d "-120 seconds" "+%Y-%m-%d %H:%M:%S")"
  recent=0
  if [ -r "$STATE/check.log" ]; then
    recent="$(awk -F"[|]" -v c="$cut" '$1>=c && $2=="push-ok" {n++} END{print n+0}' "$STATE/check.log" 2>/dev/null)"
  fi
  if [ "${recent:-0}" -gt 0 ]; then
    echo "120 秒内已推送过预告，本次跳过"
    exit 0
  fi
  if ! timeout 60 openclaw message send --channel feishu --account "$ACC" --target "$TARGET" --message "$BODY" >/dev/null 2>>"$STATE/push-error.log"; then
    printf "%s|push-fail\n" "$now" >> "$STATE/check.log" 2>/dev/null || true
    timeout 15 sh "$WS/tools/notify.sh" --alert "【告警】维护预告推送失败 $now（$LABEL $ITEM）" >/dev/null 2>&1 || true
    echo "推送失败" >&2
    exit 4
  fi
  printf "%s|push-ok|%s|%s\n" "$now" "$LABEL" "$REASON" >> "$STATE/check.log" 2>/dev/null || true
  echo "推送成功"
else
  printf "%s\n" "$BODY"
fi
exit 0
