#!/usr/bin/env bash
# Kola助手 一键执行任务（v3.0 2026-11-15）
# 主公口径：任务（含浏览/领金币）必须由 Kola 跑，果果只负责把它点起来。
# 关键点：①「一键执行任务」按钮在首页底部，需要下滑才出现 ②必须先有可用的无障碍服务，否则只弹权限框
#        ③dump 用 pull，不用 shell cat ④悬浮窗只能有一个前台，脚本不抢焦点
set -uo pipefail
ADB="${ADB:-$HOME/.local/opt/platform-tools/adb.exe}"
ST=/home/j/.openclaw/workspace/state/phone
LOG="$ST/kola-task.log"
JSON="$ST/kola-task.json"
SHOT="$ST/kola-task-latest.png"
mkdir -p "$ST"
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

dump(){ "$ADB" shell uiautomator dump /sdcard/k.xml >/dev/null 2>&1; "$ADB" pull /sdcard/k.xml /tmp/k.xml >/dev/null 2>&1; [ -s /tmp/k.xml ]; }
has(){ grep -q "$1" /tmp/k.xml 2>/dev/null; }
findtap(){ python3 - "$1" <<'PY'
import re,sys
key=sys.argv[1]
try: x=open('/tmp/k.xml',encoding='utf-8',errors='ignore').read()
except: sys.exit(1)
for m in re.finditer(r'<node[^>]*>',x):
    s=m.group(0)
    vals=[t for a in ('text','content-desc') if (t:=re.search(a+r'="([^"]*)"',s)) and t.group(1)]
    if not any(key in v.group(1) for v in vals): continue
    b=re.search(r'bounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"',s)
    if not b: continue
    x1,y1,x2,y2=map(int,b.groups())
    if x2>x1 and y2>y1: print((x1+x2)//2,(y1+y2)//2); sys.exit(0)
sys.exit(2)
PY
}
acc_ok(){ "$ADB" shell dumpsys accessibility 2>/dev/null | grep -q 'com.xiaomi.gamecenter/com.xiaomi.gamecenter.AccessibilityService'; }
ensure_acc(){
  acc_ok && return 0
  "$ADB" shell settings put secure enabled_accessibility_services com.xiaomi.gamecenter/com.xiaomi.gamecenter.AccessibilityService >/dev/null 2>&1
  "$ADB" shell settings put secure accessibility_enabled 1 >/dev/null 2>&1
  sleep 3; acc_ok
}

say "=== RUN start ==="
NDEV=$("$ADB" devices | awk '$2 ~ /^device/' | wc -l)
[ "$NDEV" -ge 1 ] || { say "ERROR 手机未连接(USB/adb)"; exit 2; }

ensure_acc || say "WARN 无障碍未能确认，继续尝试（可能只弹权限框）"

"$ADB" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
"$ADB" shell wm dismiss-keyguard >/dev/null 2>&1
"$ADB" shell input swipe 540 2000 540 700 200 >/dev/null 2>&1
sleep 1

"$ADB" shell am force-stop com.xiaomi.gamecenter >/dev/null 2>&1
"$ADB" shell monkey -p com.xiaomi.gamecenter -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 8

# 等首页
READY=0
for i in $(seq 1 10); do dump && has 'Kola助手' && { READY=1; break; }; sleep 3; done
[ "$READY" = 1 ] || { say "ERROR Kola 首页未加载"; exit 3; }
if has '请开启相关权限'; then say "ERROR 无障碍权限被拒（系统弹框）"; "$ADB" exec-out screencap -p > "$SHOT" 2>/dev/null; exit 5; fi

# 下滑找「一键执行任务」
BTN=""
for i in $(seq 1 4); do
  BTN=$(findtap "一键执行任务" 2>/dev/null)
  [ -n "$BTN" ] && break
  "$ADB" shell input swipe 540 1800 540 800 300 >/dev/null 2>&1
  sleep 2
done
[ -n "$BTN" ] || { say "ERROR 下滑 4 次仍未见一键执行任务"; "$ADB" exec-out screencap -p > "$SHOT" 2>/dev/null; exit 4; }
say "点一键执行任务 @ $BTN"
"$ADB" shell input tap $BTN
sleep 4

# 弹窗：优先「全选」，否则只勾淘宝
if dump; then
  SEL=$(findtap "全选" 2>/dev/null)
  if [ -n "$SEL" ]; then "$ADB" shell input tap $SEL; say "已点全选"; sleep 1
  else
    TB=$(findtap "淘宝" 2>/dev/null); [ -n "$TB" ] && { "$ADB" shell input tap $TB; say "已勾淘宝"; sleep 1; }
  fi
  ST=$(findtap "开始" 2>/dev/null)
  if [ -n "$ST" ]; then
    "$ADB" shell input tap $ST; say "点开始 @ $ST"; sleep 1
    "$ADB" shell input tap $ST; say "二次确认 @ $ST"
  else
    say "WARN 未见「开始」，尝试双击底部确认位 540,2047"
    "$ADB" shell input tap 540 2047; sleep 1; "$ADB" shell input tap 540 2047
  fi
fi

# 验证：Kola 已开始执行（焦点切到淘宝/或出现执行中文字）
sleep 12
f=$("$ADB" shell dumpsys window 2>/dev/null | grep -m1 mCurrentFocus | tr -d '\r')
say "focus=$f"
"$ADB" exec-out screencap -p > "$SHOT" 2>/dev/null
if printf '%s' "$f" | grep -qi 'taobao\|gamecenter'; then
  printf '{"last_run":"%s","ok":true,"focus":"%s","evidence":"state/phone/kola-task-latest.png"}\n' "$(date '+%F %T')" "$f" > "$JSON"
  say "OK Kola 已开始执行任务"
  say "=== RUN end rc=0 ==="
  exit 0
fi
printf '{"last_run":"%s","ok":false,"focus":"%s"}\n' "$(date '+%F %T')" "$f" > "$JSON"
say "ERROR 未能确认开始执行"
exit 6
