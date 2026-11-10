#!/bin/bash
# bg-download.sh —— 白名单内的下载/安装一律走 systemd 托管后台（2026-11-07 #191）
# 用法: bg-download.sh <url> [输出目录]        断点续传，日志 state/dl/<时间>.log
#       bg-download.sh --cmd "<命令>" [名字]     托管任意安装命令（同样要求命中白名单）
set -uo pipefail
WS=/home/j/.openclaw/workspace
DL=$WS/state/dl; mkdir -p "$DL"
ALLOW='hf-mirror\.com|huggingface\.co|pypi\.org|files\.pythonhosted\.org|registry\.npmjs\.org|npmjs\.com|github\.com|codeload\.github\.com|objects\.githubusercontent\.com|mirrors\.aliyun\.com|pypi\.tuna\.tsinghua\.edu\.cn|github\.com\.cn'
check(){ printf '%s' "$1" | grep -qiE "$ALLOW" || { echo "✗ 不在白名单，拒绝后台托管：$1"; echo "  白名单：HF镜像/pypi/npm/github/阿里云镜像/清华源"; exit 2; }; }
TS=$(date +%Y%m%d-%H%M%S)
if [ "${1:-}" = "--cmd" ]; then
  CMD=${2:?命令}; NAME=${3:-cmd-$TS}
  check "$CMD"
  LOG=$DL/$NAME-$TS.log
  systemd-run --user --unit=bgdl-$TS --collect --working-directory="$WS" /bin/bash -lc "$CMD" >>"$LOG" 2>&1 \
    || { echo "✗ 启动失败"; exit 1; }
  echo "✓ 已托管：unit=bgdl-$TS 日志=$LOG"
  echo "  看进度：journalctl --user -u bgdl-$TS -f"
  exit 0
fi
URL=${1:?url}; OUT=${2:-$WS/state/dl}
check "$URL"
mkdir -p "$OUT"
LOG=$DL/dl-$TS.log
systemd-run --user --unit=bgdl-$TS --collect --working-directory="$OUT" /bin/bash -lc \
  "wget -c --tries=20 --timeout=30 --waitretry=5 -q --show-progress '$URL' -P '$OUT'" >>"$LOG" 2>&1 || { echo "✗ 启动失败"; exit 1; }
echo "✓ 已托管下载：unit=bgdl-$TS 目录=$OUT 日志=$LOG"
