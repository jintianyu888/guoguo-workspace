#!/usr/bin/env bash
# wsl-net-guard.sh —— 「镜像网络模式」的安全网（2026-10-03 主公要求备案）
# 逻辑：开机后每 5 分钟查一次网络；若【连国内都不通】连续 3 次 → 自动回滚 .wslconfig（去掉 networkingMode=mirrored）
W=/home/j/.openclaw/workspace
S=$W/state/.netguard; LOG=$W/state/net-guard.log; CFG=/mnt/c/Users/J/.wslconfig
mkdir -p "$S" 2>/dev/null
ok=0; timeout 8 curl -s -o /dev/null https://www.baidu.com && ok=1
if [ "$ok" = "1" ]; then echo 0 > "$S/fail"; exit 0; fi
n=$(cat "$S/fail" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$S/fail"
echo "$(date '+%F %T') 第 $n 次国内不通" >> "$LOG"
if [ "$n" -ge 3 ]; then
  if grep -q 'networkingMode=mirrored' "$CFG" 2>/dev/null; then
    LOCK=/home/j/.openclaw/workspace/state/work/.wslconfig.lock
    mkdir -p /home/j/.openclaw/workspace/state/work 2>/dev/null
    ( flock -w 30 9; sed -i "/networkingMode=mirrored/d" "$CFG" ) 9>>"$LOCK"
    echo "$(date '+%F %T') 连续3次不通 → 已自动回滚 .wslconfig（去掉 mirrored），下次重开 WSL 即恢复原状" >> "$LOG"
  fi
  echo 0 > "$S/fail"
fi
exit 0