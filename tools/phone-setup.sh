#!/bin/bash
# phone-setup.sh — Windows 侧 adb 装 SmsForwarder 并授权
set -uo pipefail
ADB=/home/j/.local/opt/platform-tools/adb.exe
APK=/home/j/.local/opt/smsf.apk
PKG=com.idormy.sms.forwarder
cmd="$1"; [ -z "$cmd" ] && cmd=check
case "$cmd" in
  check)
    [ -x "$ADB" ] || { echo "adb 未就绪: $ADB"; exit 2; }
    "$ADB" start-server >/dev/null 2>&1
    "$ADB" devices -l
    ;;
  install)
    [ -f "$APK" ] || { echo "APK 缺失: $APK"; exit 3; }
    "$ADB" install -r "$APK" 2>&1 | tail -3
    "$ADB" shell pm list packages | grep -i sms
    ;;
  perms)
    for p in android.permission.RECEIVE_SMS android.permission.READ_SMS android.permission.POST_NOTIFICATIONS android.permission.READ_PHONE_STATE; do
      "$ADB" shell pm grant "$PKG" "$p" 2>&1 | sed "s/^/  /"
    done
    "$ADB" shell appops set "$PKG" SYSTEM_ALERT_WINDOW allow 2>/dev/null
    "$ADB" shell dumpsys deviceidle whitelist +"$PKG" 2>/dev/null | tail -1
    ;;
  launch)
    "$ADB" shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
    echo launched
    ;;
  screen)
    mkdir -p /home/j/.openclaw/workspace/state/scratch
    "$ADB" exec-out screencap -p > /home/j/.openclaw/workspace/state/scratch/phone.png
    ls -l /home/j/.openclaw/workspace/state/scratch/phone.png
    ;;
  tap)
    "$ADB" shell input tap "$2" "$3"; echo "tap $2 $3"
    ;;
  text)
    "$ADB" shell input text "$2"; echo "text sent"
    ;;
  key)
    "$ADB" shell input keyevent "$2"; echo "key $2"
    ;;
  *) echo "用法: phone-setup.sh [check|install|perms|launch|screen|tap X Y|text ...|key CODE]" ;;
esac
