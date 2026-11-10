#!/usr/bin/env bash
# feishu-add-butler.sh —— 一条命令接入新飞书管家（配置部分）
# 用法: feishu-add-butler.sh <agent> <appId> <SECRET_ENTRY_NAME> [--force]
set -euo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
CFG=/home/j/.openclaw/openclaw.json
LOCK=/home/j/.openclaw/workspace/state/work/feishu-config.lock
mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
flock -n 9 || { echo "另一个飞书配置写入进行中，稍后再试"; exit 5; }
AG="$1"; APPID="$2"; SEC="$3"; FORCE="${4:-}"
if [ -z "$AG" ] || [ -z "$APPID" ] || [ -z "$SEC" ]; then echo "用法: $0 <agent> <appId> <SECRET_NAME> [--force]"; exit 2; fi
case "$APPID" in cli_*) ;; *) echo "appId 必须以 cli_ 开头"; exit 2;; esac
BAK="$CFG.bak-addbutler-$(date +%Y%m%d-%H%M%S)"
cp -a "$CFG" "$BAK"; echo "备份: $BAK"
python3 /home/j/.openclaw/workspace/tools/_feishu_add.py "$CFG" "$AG" "$APPID" "$SEC" "$FORCE"
if ! openclaw config validate; then
  cp -a "$BAK" "$CFG"
  echo "❌ config validate 失败，已回滚到 $BAK"; exit 6
fi
echo "下一步:"
echo " 1) 控制台确认应用已发布版本、可用范围含本人"
echo " 2) 让对方发一条，然后跑: bash ~/.openclaw/workspace/tools/feishu-allow-id.sh $AG"
echo " 3) 验收: journalctl --user -u openclaw-gateway --since -5min | grep feishu[$AG]"
