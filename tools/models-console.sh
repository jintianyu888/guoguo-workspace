#!/bin/bash
# models-console.sh — 常驻 3D 模型站登录会话（2026-11-14 主公令）
# 用法: models-console.sh start|stop|status|shot [url]
# 目的: 一次登录（扫码/账号），会话长期有效；maker 与我都能复用同一登录态取模型。
set -uo pipefail
CH=/home/j/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome
PROFILE=/home/j/.openclaw/browser-models
PORT=9334
PYTHON=/home/j/.openclaw/venvs/tts312/bin/python3
case "${1:-status}" in
  start)
    mkdir -p "$PROFILE"; chmod 700 "$PROFILE"
    systemctl --user stop browser-models 2>/dev/null; systemctl --user reset-failed browser-models 2>/dev/null
    systemd-run --user --unit=browser-models --collect --setenv=DISPLAY=:0 \
      "$CH" --remote-debugging-port=$PORT "--remote-allow-origins=*" \
      --user-data-dir="$PROFILE" --disable-blink-features=AutomationControlled --lang=zh-CN --no-first-run --no-default-browser-check \
      --no-sandbox --disable-dev-shm-usage --window-size=1440,900 \
      "${2:-https://makerworld.com}" >/dev/null 2>&1
    sleep 6
    systemctl --user is-active browser-models
    ;;
  stop)
    systemctl --user stop browser-models 2>/dev/null
    echo stopped
    ;;
  status)
    systemctl --user is-active browser-models 2>/dev/null
    curl -s --max-time 4 http://127.0.0.1:$PORT/json/version >/dev/null && echo CDP_OK || echo CDP_DOWN
    ;;
  shot)
    PW=/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core
    node -e '
const {chromium}=require(process.argv[1]);
(async()=>{
  const b=await chromium.connectOverCDP("http://127.0.0.1:9334");
  const ctx=b.contexts()[0]; const p=ctx.pages()[0]||await ctx.newPage();
  const url=process.argv[2];
  if(url){ try{ await p.goto(url,{waitUntil:"domcontentloaded",timeout:45000}); }catch(e){ console.log("NAV_WARN",e.message.slice(0,80)); } await p.waitForTimeout(3000); }
  const out="/home/j/.openclaw/workspace/state/scratch/models-page.png";
  await p.screenshot({path:out});
  console.log("SHOT",out,p.url());
  await b.close();
})().catch(e=>{console.log("ERR",e.message);process.exit(1)});
' "$PW" "\${2:-}"
    ;;
  *)
    echo "usage: models-console.sh start [url] | stop | status | shot [url]"
    ;;
esac
