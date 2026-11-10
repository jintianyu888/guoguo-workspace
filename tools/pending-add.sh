#!/usr/bin/env bash
# pending-add.sh - 兼容旧调用：追加一条待办（转发到 tools/tasks.sh add）
# 用法: pending-add.sh "内容" [owner]   （owner 默认 果果）
set -eu
T="${1:?用法: pending-add.sh \"内容\" [owner]}"
OWNER="${2:-果果}"
exec "$(dirname "$0")/tasks.sh" add --title "$T" --owner "$OWNER"
