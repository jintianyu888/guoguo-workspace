#!/usr/bin/env bash
# 面板截图自检（2026-11-07）：改面板后先跑这个，出图再交付
# 依赖：libasound2t64（2026-11-07 主公装好）+ chrome-headless-shell
set -euo pipefail
H=/home/j/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell
OUT=/home/j/.openclaw/workspace/state/panelshots
mkdir -p "$OUT"
F="$OUT/panel-$(date +%Y%m%d-%H%M%S).png"
timeout 90 "$H" --no-sandbox --disable-gpu --hide-scrollbars --screenshot="$F" --window-size=1400,1400 http://127.0.0.1:8899/ >/dev/null 2>&1 || true
if [ -s "$F" ]; then echo "SHOT_OK $F"; else echo "SHOT_FAIL（chrome 未出图，检查面板是否 200）"; exit 1; fi
