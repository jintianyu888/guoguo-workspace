#!/bin/bash
# feishu-app-icon.sh —— 换飞书自建应用图标并发布（见 tools/feishu-icon-upload.js）
set -uo pipefail
W=/home/j/.openclaw/workspace
bash "$W/tools/feishu-console.sh" status 2>/dev/null | grep -q active || bash "$W/tools/feishu-console.sh" start
sleep 3
exec node "$W/tools/feishu-icon-upload.js" "$@"
