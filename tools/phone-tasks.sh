#!/bin/bash
# 每日手机任务：Kola助手(小米游戏中心) 一键执行淘宝任务（淘金币/签到/浏览）
# 用法: phone-tasks.sh [--dry]
ADB=/home/j/.local/opt/platform-tools/adb.exe
LOG=/home/j/.openclaw/workspace/state/phone/tasks.log
mkdir -p "$(dirname "$LOG")"
say(){ echo "$(date -Is) $*" >> "$LOG"; }

dev_state(){ "$ADB" devices 2>/dev/null | tr -d '\r' | awk 'NR==2{print $2}'; }
if [ "$(dev_state)" != "device" ]; then say "SKIP device=$(dev_state)"; exit 0; fi

# 唤醒 + 解锁（无密码时上滑即可）
"$ADB" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
"$ADB" shell svc power stayon true >/dev/null 2>&1
"$ADB" shell settings put system screen_off_timeout 900000 >/dev/null 2>&1
sleep 1
"$ADB" shell input swipe 540 1900 540 700 150 >/dev/null 2>&1
sleep 1

# 打开 Kola助手
"$ADB" shell monkey -p com.xiaomi.gamecenter -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
sleep 6

# 记录当前焦点，确认在前台
focus=$("$ADB" shell dumpsys window 2>/dev/null | tr -d '\r' | grep -m1 mCurrentFocus)
case "$focus" in
  *xiaomi.gamecenter*) ;;
  *) say "ERROR not foreground: $focus"; exit 2;;
esac

# 打开 一键执行任务 弹窗：点 Kola助手 页底部按钮（坐标依 1080x2378）
"$ADB" shell input tap 548 2078 >/dev/null 2>&1
sleep 3

# 只选淘宝
"$ADB" shell input tap 262 1872 >/dev/null 2>&1
sleep 1

# 双击开始执行（该 App 需二次确认）
"$ADB" shell input tap 540 2047 >/dev/null 2>&1
sleep 0.6
"$ADB" shell input tap 540 2047 >/dev/null 2>&1
sleep 4

say "STARTED focus=$("$ADB" shell dumpsys window 2>/dev/null | tr -d '\r' | grep -m1 mCurrentFocus | sed 's/.*u0 //;s/}.*//')"

# 等待执行（最长 12 分钟），期间保持唤醒
for i in $(seq 1 24); do
  sleep 30
  f=$("$ADB" shell dumpsys window 2>/dev/null | tr -d '\r' | grep -m1 mCurrentFocus)
  if echo "$f" | grep -q "xiaomi.gamecenter"; then say "DONE after $((i*30))s"; break; fi
done

# 收尾：回桌面、恢复屏幕设置、熄屏
"$ADB" shell input keyevent KEYCODE_HOME >/dev/null 2>&1
"$ADB" shell input keyevent KEYCODE_BACK >/dev/null 2>&1
"$ADB" shell svc power stayon false >/dev/null 2>&1
"$ADB" shell settings put system screen_off_timeout 30000 >/dev/null 2>&1
"$ADB" shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
say "FINISHED"
exit 0
