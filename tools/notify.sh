#!/usr/bin/env bash
# notify.sh — 任务起止/通报：给主公飞书发一条消息
# 用法: bash tools/notify.sh "文本"   (或 export NOTIFY_TARGET 覆盖目标)
set -u
# 2026-11-07 21:45 主公令：维护窗口内一切告警只记录、不推送（告警走同一条线，由本闸门统一裁决）
MAINT_FLAG=/home/j/.openclaw/workspace/state/work/.maintenance
if [ -f "$MAINT_FLAG" ]; then
  _mu=$(awk '{print $1}' "$MAINT_FLAG" 2>/dev/null)
  if [ -n "${_mu:-}" ] && [ "$(date +%s)" -lt "${_mu:-0}" ] && [ "${MAINT_NOTIFY:-0}" != "1" ]; then
    mkdir -p /home/j/.openclaw/workspace/state/alerts
    printf '%s\t%s\n' "$(date '+%F %T')" "$*" >> /home/j/.openclaw/workspace/state/alerts/maintenance-suppressed.log
    exit 0
  fi
fi
TARGET="${NOTIFY_TARGET:-user:ou_74fec7bc81cc6ec6d2b4de1c0967923b}"
# 2026-10-31: feishu open_id 按应用区分 -- maint 应用里主公是 ou_0086..., 主应用才是 ou_74fe...
MAINT_TARGET="user:ou_008693513eb3b36f292fcfaa7a8b57b3"
# 告警优先走独立 webhook（不经过网关），失败再回落网关 CLI

# 用法: NOTIFY_ALERT=1 bash tools/notify.sh "文本"   或   bash tools/notify.sh --alert "文本"

WH=/home/j/.config/feishu-alert-webhook

send_via_webhook() {

  local url payload

  [ -s "$WH" ] || return 1

  url=$(head -n 1 "$WH" | tr -d '\r\n')

  [ -n "$url" ] || return 1

  payload=$(python3 -c 'import json,sys;print(json.dumps({"msg_type":"text","content":{"text":sys.argv[1]}},ensure_ascii=False))' "$1" 2>/dev/null) || return 1

  [ -n "$payload" ] || return 1

  timeout 20 curl -s --max-time 12 -H 'Content-Type: application/json' -d "$payload" "$url" 2>/dev/null | grep -qE '"StatusCode":[[:space:]]*0|"code":[[:space:]]*0'

}

NOTIFY_ALERT="${NOTIFY_ALERT:-0}"
if [ "${1:-}" = "--alert" ]; then NOTIFY_ALERT=1; shift; fi
# 2026-10-31 主公令：所有「通告」默认交给维护管家（account=maint）；--to-owner 可强制回主公
NOTIFY_OWNER=0
if [ "${1:-}" = "--to-owner" ]; then NOTIFY_OWNER=1; shift; fi

# 2026-11-13 修：cron/systemd 的 PATH 里没有 npm-global，写死绝对路径（同一类坑：node-alive-check 报 FileNotFoundError）
OC_BIN=""
for _c in /home/j/.npm-global/bin/openclaw /home/j/.openclaw/tmp/agent-cli/openclaw; do
  [ -x "$_c" ] && { OC_BIN="$_c"; break; }
done
[ -n "$OC_BIN" ] || OC_BIN="$(command -v openclaw 2>/dev/null || echo openclaw)"

ALERT_LEDGER=/home/j/.openclaw/workspace/state/alerts/alerts.jsonl
ledger_alert(){
  # 2026-11-08 告警双审修正：同进程只记一条，防主流程与 webhook 分支双写
  [ "${_ALERT_LEDGER_DONE:-0}" = "1" ] && return 0
  _ALERT_LEDGER_DONE=1
  mkdir -p "$(dirname "$ALERT_LEDGER")"
  {
    flock -x 8
    NOTIFY_SOURCE="${NOTIFY_SOURCE:-unknown}" python3 - "$1" <<'PYL'
import sys,json,datetime,os
p="/home/j/.openclaw/workspace/state/alerts/alerts.jsonl"
rec={"ts":datetime.datetime.now().isoformat(timespec="seconds"),
     "source":os.environ.get("NOTIFY_SOURCE","unknown"),
     "text":sys.argv[1][:500],"delivered":False}
with open(p,"a",encoding="utf-8") as f: f.write(json.dumps(rec,ensure_ascii=False)+"\n")
if os.path.exists(p) and os.path.getsize(p)>2_000_000:
    cut=(datetime.datetime.now()-datetime.timedelta(days=30)).isoformat()
    keep=[]
    for l in open(p,encoding="utf-8").read().splitlines():
        try: keep.append(l if json.loads(l).get("ts","")>=cut else "")
        except Exception: keep.append("")
    with open(p,"w",encoding="utf-8") as f: f.write("\n".join([k for k in keep if k])+"\n")
PYL
  } 8>"$(dirname "$ALERT_LEDGER")/.lock"
}
mark_delivered(){
  python3 - <<'PYD'
import json
p="/home/j/.openclaw/workspace/state/alerts/alerts.jsonl"
try:
    ls=open(p,encoding="utf-8").read().splitlines()
    if ls:
        r=json.loads(ls[-1]); r["delivered"]=True
        ls[-1]=json.dumps(r,ensure_ascii=False)
        open(p,"w",encoding="utf-8").write("\n".join(ls)+"\n")
except Exception: pass
PYD
}
send_via_webhook_alert(){
  ledger_alert "$MSG"
  if send_via_webhook "【告警】$MSG"; then mark_delivered; return 0; fi
  return 1
}

MSG="$*"

# ── 2026-11-01 主公令：每条告警/通报必须写明「出处」与「归属管家」──
# 注意：NOTIFY_OWNER 是脚本内部投递开关(0/1)，勿复用；这里用 NOTIFY_FROM / NOTIFY_BELONG
# 用法：NOTIFY_FROM=maint NOTIFY_BELONG=backup bash tools/notify.sh --alert "文本"
if [ "${NOTIFY_NOFOOTER:-0}" != "1" ] && [ -n "$MSG" ]; then
  _FROMREF="${NOTIFY_FROM:-${OPENCLAW_AGENT_ID:-}}"
  _BELONGREF="${NOTIFY_BELONG:-$_FROMREF}"
  case "$_FROMREF" in
    maint) _srcl="维护管家(maint)" ;;
    backup) _srcl="备份管家(backup)" ;;
    work) _srcl="干活管家(work)" ;;
    model) _srcl="模型管家(model)" ;;
    main) _srcl="果果(main)" ;;
    "") _pn=$(cat /proc/$PPID/comm 2>/dev/null); _srcl="${_pn:-unknown}·自动" ;;
    *) _srcl="$_FROMREF" ;;
  esac
  case "$_BELONGREF" in
    maint) _ownl="维护管家(maint)" ;;
    backup) _ownl="备份管家(backup)" ;;
    work) _ownl="干活管家(work)" ;;
    model) _ownl="模型管家(model)" ;;
    main) _ownl="果果(main)" ;;
    "") _ownl="未标注" ;;
    *) _ownl="$_BELONGREF" ;;
  esac
  MSG="$MSG
—— 出处：$_srcl｜归属：$_ownl"
fi
# ── 额度页登录类噪音拦截（2026-11-07 主公令）──
# 判定：同时出现「额度页」和 登录/login/扫码 → 纯噪音，只记日志不推送
case "$MSG" in
  *额度页*)
    case "$MSG" in
      *登录*|*login*|*扫码*|*扩展已连接*)
        echo "$(date '+%F %T') suppressed-quota-login: ${MSG:0:80}" >> /home/j/.openclaw/workspace/state/notify-queue.log
        exit 0;;
    esac;;
esac

# 2026-11-01: 干跑，只打印最终消息体不发（验证出处/归属格式用）
if [ "${NOTIFY_DRYRUN:-0}" = "1" ]; then printf '%s\n' "$MSG"; exit 0; fi

# ── 静默窗(04:00–06:05)不丢消息：入队，06:10 由 notify-flush.sh 重放（P1 2026-10-26）──
QDIR=/home/j/.openclaw/workspace/state/notify-queue
enqueue() {
  mkdir -p "$QDIR" 2>/dev/null || return 1
  local ts f
  ts=$(date '+%Y%m%d-%H%M%S')-$$
  f="$QDIR/$ts.json"
  python3 - "$f" "${NOTIFY_ALERT:-0}" "$TARGET" "$MSG" <<'PY' || return 1
import json,sys,datetime
f,alert,target,msg=sys.argv[1:5]
json.dump({"ts":datetime.datetime.now().isoformat(timespec="seconds"),
           "alert":1 if str(alert)=="1" else 0,
           "target":target,"message":msg},open(f,"w",encoding="utf-8"),ensure_ascii=False)
PY
  return 0
}
if [ "${NOTIFY_NOQUEUE:-0}" != "1" ] && [ -n "$MSG" ] \
   && python3 /home/j/.openclaw/workspace/tools/quiet_window.py >/dev/null 2>&1; then
  if [ "${NOTIFY_ALERT:-0}" = "1" ] && send_via_webhook_alert >/dev/null 2>&1; then
    exit 0
  fi
  if enqueue; then
    echo "$(date '+%F %T') quiet-window queued: ${MSG:0:60}" >> /home/j/.openclaw/workspace/state/notify-queue.log
    exit 0
  fi
  # 入队失败则继续尝试直发（宁可重试也别丢）
fi
[ -z "$MSG" ] && exit 0
# 2026-10-17 修：CLI/网关 RPC 偶发挂死会把调用方一起拖死（表现为 cron command error with no output）。
# 加硬超时，失败只记账，绝不让调用方阻塞。
# 2026-11-02 主公令：告警一律走「果果告警」（主应用/独立 webhook）；维护管家只收报告，不收警报
ALERT_PENDING=0
[ "$NOTIFY_ALERT" = "1" ] && ALERT_PENDING=1 && ledger_alert "$MSG"
SENT=0
if [ "$ALERT_PENDING" = "1" ]; then
  # 2026-11-02 双审新增：告警冷却——同一文本 20 分内只发一次，防 flapping 刷屏
  ALERT_COOLDOWN=${NOTIFY_ALERT_COOLDOWN:-1200}
  if [ "$ALERT_COOLDOWN" -gt 0 ] 2>/dev/null; then
    _h=$(printf '%s' "$MSG" | sha256sum | cut -c1-16)
    _kf=/home/j/.openclaw/workspace/state/alerts/.cooldown
    _now=$(date +%s)
    _last=$(awk -v k="$_h" '$1==k{print $2}' "$_kf" 2>/dev/null | tail -1)
    if [ -n "${_last:-}" ] && [ $(( _now - _last )) -lt "$ALERT_COOLDOWN" ]; then
      echo "$(date '+%F %T') cooldown-skip($_h) ${MSG:0:60}" >> /home/j/.openclaw/workspace/state/alerts/cooldown.log
      exit 0
    fi
    mkdir -p "$(dirname "$_kf")" 2>/dev/null
    { flock -x 9; awk -v k="$_h" '$1!=k' "$_kf" 2>/dev/null; echo "$_h $_now"; } 9>"$_kf.lock" > "$_kf.t" 2>/dev/null && mv -f "$_kf.t" "$_kf" 2>/dev/null
  fi
  # ① 先走独立 webhook（不经网关，最抵故障）
  if send_via_webhook_alert >/dev/null 2>&1; then exit 0; fi
  # ② webhook 不通 → 主应用直发果果（不再投维护管家）
  ACC=""
  [ -z "${NOTIFY_TARGET:-}" ] && TARGET="user:ou_74fec7bc81cc6ec6d2b4de1c0967923b"
else
  ACC="${NOTIFY_ACCOUNT-maint}"
  [ "$NOTIFY_OWNER" = "1" ] && ACC=""
  if [ "$ACC" = "maint" ] && [ -z "${NOTIFY_TARGET:-}" ]; then TARGET="$MAINT_TARGET"; fi
fi
if [ -n "$ACC" ]; then
  # 2026-11-08 修：单次发送实测 ~12s，同一分钟多个任务并发时会被挤爆；超时 45→90 秒，并重试一次
  for _try in 1 2; do
    timeout 90 "$OC_BIN" message send --channel feishu --account "$ACC" --target "$TARGET" --message "$MSG" >/dev/null 2>&1 && { SENT=1; break; }
    [ "$_try" = 1 ] && sleep 3
  done
  [ "$SENT" = "1" ] && mark_delivered
  [ "$SENT" = "1" ] && printf '{"ts":"%s","account":"%s","msg":"%s"}\n' "$(date '+%F %T')" "$ACC" "$(printf '%s' "$MSG" | head -c 200 | tr '\n' ' ')" >> /home/j/.openclaw/workspace/state/work/maint-notices.jsonl
fi
FAILED=0
if [ "$SENT" != "1" ]; then
  _ef=/tmp/.notify-err.$$
  timeout 90 "$OC_BIN" message send --channel feishu --target "$TARGET" --message "$MSG" >/dev/null 2>"$_ef"
  _rc=$?
  if [ "$_rc" != "0" ]; then
    _err=$(tail -2 "$_ef" 2>/dev/null | tr '\n' ' ' | head -c 160)
    echo "$(date '+%F %T') notify failed/timeout: ${MSG:0:60} | rc=$_rc err=${_err:-none}" >> /home/j/.openclaw/workspace/state/notify-fail.log
    FAILED=1
  fi
  rm -f "$_ef"
fi
# 2026-11-03：严格模式，供需要"确认送达"的调用方（开机回执等）判断真实结果；默认仍 exit 0 不影响既有调用方
if [ "${NOTIFY_STRICT:-0}" = "1" ] && [ "$FAILED" = "1" ]; then exit 1; fi
exit 0
