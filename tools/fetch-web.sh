#!/bin/bash
# fetch-web.sh —— 经本机代理抓网页/存原文（绕 DNS 污染与墙）
# 用法: bash tools/fetch-web.sh <url> [输出文件] [--text]
set -uo pipefail
URL="${1:?url}"
OUT="${2:-}"
TEXTMODE=0; [ "${3:-}" = "--text" ] && TEXTMODE=1
source /home/j/.openclaw/workspace/tools/proxy-env.sh
[ -z "$OUT" ] && OUT="/tmp/fetch-$(date +%s).html"
code=$(curl -sSL --compressed --max-time 45 -A 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' -o "$OUT" -w '%{http_code}' "$URL")
echo "http=$code file=$OUT bytes=$(stat -c%s "$OUT" 2>/dev/null || echo 0)"
if [ "$TEXTMODE" = 1 ]; then
  python3 - "$OUT" <<'PY'
import re,sys,html
raw=open(sys.argv[1],encoding='utf-8',errors='ignore').read()
raw=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',raw)
txt=html.unescape(re.sub(r'(?s)<[^>]+>',' ',raw))
print(re.sub(r'\s+',' ',txt).strip()[:4000])
PY
fi
