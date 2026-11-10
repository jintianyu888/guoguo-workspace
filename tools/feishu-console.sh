#!/bin/bash
# feishu-console.sh — 常驻飞书开放平台会话（2026-11-10）
# 用法: feishu-console.sh start|stop|status|qr|shot|run <js-file>
set -uo pipefail
CH=/home/j/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome
PROFILE=/home/j/.openclaw/browser-feishu
PORT=9333
PW=/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core
case "${1:-status}" in
  start)
    mkdir -p "$PROFILE"; chmod 700 "$PROFILE"
    systemctl --user stop browser-feishu 2>/dev/null; systemctl --user reset-failed browser-feishu 2>/dev/null
    systemd-run --user --unit=browser-feishu --collect \
      --setenv=DISPLAY=:0 --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=XDG_RUNTIME_DIR=/run/user/1000 \
      "$CH" --remote-debugging-port=$PORT --remote-allow-origins=* \
      --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check \
      --no-sandbox --disable-dev-shm-usage --window-size=1280,900 \
      "${2:-https://open.feishu.cn/app}" >/tmp/browser-feishu.log 2>&1
    sleep 4; curl -s -m 5 "http://127.0.0.1:$PORT/json/version" | head -c 40; echo
    ;;
  stop) systemctl --user stop browser-feishu 2>/dev/null; echo stopped ;;
  status)
    systemctl --user is-active browser-feishu
    curl -s -m 5 "http://127.0.0.1:$PORT/json/list" | python3 -c "import sys,json;d=json.load(sys.stdin);[print(p[\"url\"][:100]) for p in d if p.get(\"type\")==\"page\"]" 2>/dev/null
    ;;
  qr|shot)
    node -e 'const{chromium}=require("'"$PW"'");(async()=>{const b=await chromium.connectOverCDP("http://127.0.0.1:'"$PORT"'");const p=b.contexts().flatMap(c=>c.pages()).find(x=>x.url().includes("feishu"));if(!p){console.log("NOPAGE");return}const c=p.locator("canvas").first();const box=await c.boundingBox().catch(()=>null);const out="/home/j/.openclaw/workspace/state/scratch/feishu-qr.png";if(box&&box.width>120){await c.screenshot({path:out})}else{await p.screenshot({path:out})}console.log("SAVED",out,"URL",p.url().slice(0,80));await b.close()})()' 
    ;;
  run) node "${2:?js file}" ;;
  *) echo "用法: $0 start|stop|status|qr|run <js>"; exit 2 ;;
esac
