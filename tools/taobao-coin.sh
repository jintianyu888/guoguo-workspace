#!/usr/bin/env bash
# 淘宝淘金币 每日自动签到 v2.1（2026-11-15）
# 变更原因：Kola助手新版已无「一键执行任务」按钮，且无障碍权限被 HyperOS 反复回收；改为直接驱动淘宝。
# 关键坑：Kola 常驻悬浮窗，会让 uiautomator dump 抓到 Kola 窗口 → 必须先 force-stop Kola；
#         dump 用 pull（adb shell cat XML 会截断/失败）。
set -uo pipefail
ADB="${ADB:-$HOME/.local/opt/platform-tools/adb.exe}"
ST=/home/j/.openclaw/workspace/state/phone
LOG="$ST/taobao-coin.log"
JSON="$ST/taobao-coin.json"
SHOT="$ST/taobao-coin-latest.png"
mkdir -p "$ST"
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }

dump(){
  "$ADB" shell uiautomator dump /sdcard/coin.xml >/dev/null 2>&1
  "$ADB" pull /sdcard/coin.xml /tmp/coin.xml >/dev/null 2>&1
  [ -s /tmp/coin.xml ]
}
find_tap(){ # $1=关键字（匹配 text 或 content-desc）→ 打印中心坐标
  python3 - "$1" <<'PY'
import re,sys
key=sys.argv[1]
try: x=open('/tmp/coin.xml',encoding='utf-8',errors='ignore').read()
except: sys.exit(1)
for m in re.finditer(r'<node[^>]*>',x):
    s=m.group(0)
    vals=[]
    for attr in ('text','content-desc'):
        mm=re.search(attr+r'="([^"]*)"',s)
        if mm: vals.append(mm.group(1))
    if not any(key in v for v in vals): continue
    b=re.search(r'bounds="\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]"',s)
    if not b: continue
    x1,y1,x2,y2=map(int,b.groups())
    if x2>x1 and y2>y1:
        print((x1+x2)//2,(y1+y2)//2); sys.exit(0)
sys.exit(2)
PY
}
has(){ grep -q "$1" /tmp/coin.xml 2>/dev/null; }

say "=== RUN start ==="
NDEV=$("$ADB" devices | awk '$2 ~ /^device/' | wc -l)
[ "$NDEV" -ge 1 ] || { say "ERROR 手机未连接"; exit 2; }

# 1) 清掉 Kola 悬浮窗 + 亮屏解锁
"$ADB" shell am force-stop com.xiaomi.gamecenter >/dev/null 2>&1
"$ADB" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
"$ADB" shell wm dismiss-keyguard >/dev/null 2>&1
"$ADB" shell input swipe 540 2000 540 700 200 >/dev/null 2>&1
sleep 2

# 2) 开淘宝，等首页出现「领淘金币」入口
"$ADB" shell am force-stop com.taobao.taobao >/dev/null 2>&1
"$ADB" shell monkey -p com.taobao.taobao -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
CO=""
for i in $(seq 1 8); do
  sleep 3
  if dump; then
    CO=$(find_tap "领淘金币" 2>/dev/null)
    [ -n "$CO" ] && break
  fi
done
if [ -z "$CO" ]; then
  # 兜底：首页图标位固定（1080x2378，领淘金币在顶部第一个图标）
  say "文本未命中，用固定坐标兜底 112,437"
  CO="112 437"
fi
say "入口坐标=$CO"
"$ADB" shell input tap $CO

# 3) 等淘金币页加载并确认当日已签（页面出现「连签」即已计入当日）
OK=0
for i in $(seq 1 15); do
  sleep 3
  if dump && has "连签"; then OK=1; break; fi
done
"$ADB" exec-out screencap -p > "$SHOT" 2>/dev/null
if [ "$OK" = 1 ]; then
  ts=$(date '+%F %T')
  printf '{"last_run":"%s","ok":true,"evidence":"state/phone/taobao-coin-latest.png"}\n' "$ts" > "$JSON"
  say "OK 淘金币页已进入（当日连签完成）"
  "$ADB" shell input keyevent KEYCODE_HOME >/dev/null 2>&1
  say "=== RUN end rc=0 ==="
  exit 0
fi
say "ERROR 未确认进入淘金币页"
printf '{"last_run":"%s","ok":false}\n' "$(date '+%F %T')" > "$JSON"
exit 4
