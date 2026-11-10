#!/bin/bash
# 安装 playwright chromium（用于生成抖音 cookie）—— 网关托管
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
export PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright
LOG=/home/j/.openclaw/workspace/state/pw-install.log
exec > >(tee -a "$LOG") 2>&1
echo "=== START $(date '+%F %T') ==="
mkdir -p /home/j/.local/pw && cd /home/j/.local/pw
npm init -y >/dev/null 2>&1
npm i playwright --no-audit --no-fund --registry=https://registry.npmmirror.com 2>&1 | tail -3
npx playwright install chromium 2>&1 | tail -8
echo "--- 结果 ---"
ls -d /home/j/.cache/ms-playwright/* 2>&1 | head -5
echo "=== DONE $(date '+%F %T') ==="
