#!/bin/bash
# nas-mem-soak.sh —— NAS 内存/整机浸透监控（每 15 分钟，自动登录续期）
# systemd 用户单元默认 PATH 不含 ~/.npm-global/bin，会导致 openclaw 命令找不到、取不到 NAS 密码（2026-11-02 修）
export PATH="/home/j/.npm-global/bin:$PATH"
SIDF=/home/j/.openclaw/workspace/state/nas.sid
BASE="https://192.168.1.109:5001/webapi/entry.cgi"
LOG=/mnt/nas/quota-meta/mem-soak.log
# 本地日志先落 ext4：NAS 掉线时挂载点会硬挂起，写 NAS 会把脚本一起拖死
LOG_LOCAL=/home/j/.openclaw/workspace/state/nas-mem-soak.log
LOG_NAS=/mnt/nas/quota-meta/mem-soak.log
STATE=/home/j/.openclaw/workspace/state/nas-soak.state
# 数据源不可用告警的去重时间戳（与 STATE 分开，避免两类告警互相压掉）
SRCSTATE=/home/j/.openclaw/workspace/state/nas-soak-src-alert.ts
# 指标类告警（内存/温度/swap/崩溃/重启）：2026-11-02 改“分类型去重”——每类一个 .ts，
# 某一类恢复只清它自己，不再让“内存告警”把“温度告警”压掉（zhipu 评审建议）
MDIR=/home/j/.openclaw/workspace/state/nas-soak-alert
MET_GAP=1800
timeout 5 mkdir -p "$MDIR" 2>/dev/null
# 并发互斥：timer 每 15 分钟一次，偶发重叠时只让一个实例发告警（避免同类重复）
LOCK=/tmp/nas-mem-soak.lock
exec 8>"$LOCK" 2>/dev/null || true
flock -n 8 2>/dev/null || { printf '%s 已有实例在跑，跳过\n' "$(date '+%F %T')" >> "$LOG_LOCAL" 2>/dev/null; exit 0; }
# 数据源不可用告警的最小间隔（秒）
SRC_ALERT_GAP=1800
timeout 5 mkdir -p /mnt/nas/quota-meta 2>/dev/null
# 带超时的写 NAS：不可写就跳过，绝不让死挂载阻塞主流程
append_log(){
  printf '%s\n' "$1" >> "$LOG_LOCAL" 2>/dev/null
  if timeout 5 sh -c ": >> /mnt/nas/quota-meta/mem-soak.log" 2>/dev/null; then
    printf '%s\n' "$1" >> "$LOG_NAS" 2>/dev/null || true
  fi
}
login(){
  local P OC
  OC=$(command -v openclaw || echo /home/j/.npm-global/bin/openclaw)
  P=$("$OC" secrets store list 2>/dev/null | sed -n "s/^NAS_NEW_PASSWORD \[env\] = //p" | head -1)
  if [ -z "$P" ]; then
    printf '%s\n' "$(date '+%F %T') login: 密码不可读(openclaw=$OC)" >> "$LOG_LOCAL" 2>/dev/null
    echo "login: 密码不可读(openclaw=$OC)" >&2
    return 1
  fi
  local S
  S=$(curl -s -k --max-time 15 -G "$BASE" --data-urlencode "api=SYNO.API.Auth" --data-urlencode "version=6" --data-urlencode "method=login" --data-urlencode "account=backup" --data-urlencode "passwd=$P" --data-urlencode "session=dsm" --data-urlencode "format=sid")
  echo "$S" | sed -n "s/.*\"sid\":\"\([^\"]*\)\".*/\1/p" > "$SIDF"
  [ -s "$SIDF" ]
}
fetch(){
  local api="$1" ver="$2" meth="$3" out="$4"
  curl -s -k --max-time 15 "$BASE?api=$api&version=$ver&method=$meth&_sid=$(cat "$SIDF")" -o "$out"
  grep -q "\"success\":true" "$out" 2>/dev/null
}
SID=$(cat "$SIDF" 2>/dev/null)
[ -z "$SID" ] && login
fetch SYNO.Core.System.Utilization 1 get /tmp/s1.json || { login && fetch SYNO.Core.System.Utilization 1 get /tmp/s1.json; }
fetch SYNO.Core.System 1 info /tmp/s2.json || true
fetch SYNO.Core.System.Status 1 get /tmp/s3.json || true
out=$(python3 - <<PY
import json,time
def L(p):
    try: return json.load(open(p)).get("data",{})
    except Exception: return {}
u=L("/tmp/s1.json"); i=L("/tmp/s2.json"); s=L("/tmp/s3.json")
m=u.get("memory") or {}
avail=m.get("avail_real"); swap_free=m.get("avail_swap"); swap_total=m.get("swap_total")
# 只有 memory 块真的给了 avail_real 才算数据源有效；缺字段＝不可用，不当成 0
def num(v):
    return v if isinstance(v,int) and v>=0 else -1
def mb(v):
    return round(v/1024) if isinstance(v,int) and v>=0 else -1
print(time.strftime("%F %T"),
      "status", "ok" if num(avail)>=0 else "unavailable",
      "ram_MB", i.get("ram_size") if i.get("ram_size") is not None else -1,
      "avail_MB", mb(avail),
      "swap_free_MB", mb(swap_free),
      "swap_total_MB", mb(swap_total),
      "temp", i.get("sys_temp") if i.get("sys_temp") is not None else -1,
      "uptime", i.get("up_time") or "0:00",
      "crashed", str(s.get("is_system_crashed")).lower())
PY
)
[ -z "$out" ] && out="$(date '+%F %T') status unavailable ram_MB -1 avail_MB -1 swap_free_MB -1 swap_total_MB -1 temp -1 uptime 0:00 crashed false"
append_log "$out"
status=$(echo "$out" | sed -n "s/.*status \([a-z]*\).*/\1/p")
[ "$status" = "ok" ] || status="unavailable"   # 缺标记一律按不可用，绝不当 ok
avail=$(echo "$out" | sed -n "s/.*avail_MB \(-*[0-9]*\).*/\1/p")
swapf=$(echo "$out" | sed -n "s/.*swap_free_MB \(-*[0-9]*\).*/\1/p")
swapt=$(echo "$out" | sed -n "s/.*swap_total_MB \(-*[0-9]*\).*/\1/p")
temp=$(echo "$out" | sed -n "s/.*temp \(-*[0-9]*\).*/\1/p")
up=$(echo "$out" | sed -n "s/.*uptime \([0-9:]*\).*/\1/p")
crash=$(echo "$out" | sed -n "s/.*crashed \([A-Za-z]*\).*/\1/p")
for v in avail swapf swapt temp; do eval "x=\${$v}"; case "$x" in ''|*[!0-9-]*) eval "$v=-1";; esac; done

# 数据源不可用：单独告警 + 30 分钟去重，且发送成功才更新时间戳
src_alert(){
  local now last
  now=$(date +%s)
  last=$(cat "$SRCSTATE" 2>/dev/null || echo 0)
  case "$last" in ''|*[!0-9]*) last=0;; esac
  [ $((now-last)) -lt "$SRC_ALERT_GAP" ] && return 0
  local msg="NAS浸透监控:监控数据源不可用(API 无有效响应，内存指标本次跳过)"
  [ -s "$SIDF" ] || msg="$msg(登录失败，sid 为空)"
  if bash /home/j/.openclaw/workspace/tools/notify.sh --alert "$msg" >/dev/null 2>&1; then
    printf '%s' "$now" > "$SRCSTATE"
  fi
}
# 单类别告警：$1=类别(mem/swap/temp/crash/reboot) $2=文案；发送成功才写时间戳
alert_once(){
  local kind="$1" msg="$2" now last f
  f="$MDIR/$kind.ts"
  now=$(date +%s)
  last=$(cat "$f" 2>/dev/null || echo 0)
  case "$last" in ''|*[!0-9]*) last=0;; esac
  [ $((now-last)) -lt "$MET_GAP" ] && return 0
  if bash /home/j/.openclaw/workspace/tools/notify.sh --alert "NAS浸透监控:$msg" >/dev/null 2>&1; then
    # 原子写：tmp + mv，避免并发/中断留下半截时间戳
    printf '%s' "$now" > "$f.tmp.$$" 2>/dev/null && mv -f "$f.tmp.$$" "$f" 2>/dev/null || true
  fi
}
clear_kind(){ rm -f "$MDIR/$1.ts" 2>/dev/null || true; }

prev=$(cat "$STATE" 2>/dev/null || echo "")
if [ "$status" != "ok" ]; then
  src_alert
  append_log "$(date '+%F %T') status unavailable (skipped metric alerts)"
  exit 0
fi
# 2026-11-04 主公令：Synology 常态把内存吃进缓存，available 长期 <1G 属正常，600MB 阈值全是噪音。
# 改为只在真正接近耗尽（<120MB）时告警；其余情况只记日志，不发飞书。
if [ "$avail" -ge 0 ] && [ "$avail" -lt 120 ]; then alert_once mem "可用内存接近耗尽(${avail}MB)"; else clear_kind mem; fi
# swap 只在真的启用（total>0）时才判，避免未启用 swap 的机器天天误报
if [ "$swapt" -gt 0 ] && [ "$swapf" -ge 0 ] && [ "$swapf" -lt 1000 ]; then alert_once swap "swap将耗尽(剩${swapf}MB)"; else clear_kind swap; fi
# 2026-11-07 主公令：58C 这类温度属常态，不要推给他。>55C 只记日志，>70C 才告警。
if [ "$temp" -ge 0 ] && [ "$temp" -gt 55 ]; then
  printf '%s temp=%sC
' "$(date '+%F %T')" "$temp" >> /home/j/.openclaw/workspace/state/alert/temp-high.log 2>/dev/null || true
fi
if [ "$temp" -ge 0 ] && [ "$temp" -gt 70 ]; then alert_once temp "温度过高(${temp}C)，需立即检查风扇/通风"; else clear_kind temp; fi
if [ "$crash" = "true" ]; then alert_once crash "系统曾崩溃"; else clear_kind crash; fi
if [ -n "$prev" ] && [ -n "$up" ] && [ "$up" != "0:00" ]; then
  pm=$(echo "$prev" | cut -d: -f1); cm=$(echo "$up" | cut -d: -f1)
  if [ "$cm" -lt "$pm" ] 2>/dev/null; then alert_once reboot "检测到重启($prev->$up)"; else clear_kind reboot; fi
fi
[ -n "$up" ] && [ "$up" != "0:00" ] && echo "$up" > "$STATE"
exit 0
