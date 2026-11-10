#!/bin/bash
# upgrade-preflight.sh —— 升级前一次到位：修依赖解析、清残留、停 agent、核对前提
# 2026-11-05 夜：五层根因逐条封堵；每次升级前跑一遍，输出 READY/NOT-READY
set -u
W=/home/j/.openclaw/workspace
OC=/home/j/.npm-global/lib/node_modules/openclaw
LOG=$W/state/work/upgrade-preflight.log
OUT=$W/state/work/upgrade-ready.txt
FAIL=""; OK=""
log(){ echo "[$(date "+%F %T")] $*" >> "$LOG"; }

# 1. yaml 深路径导出（11.1 加载器会 import yaml/dist/index.js；yaml 2.9.1 未导出该子路径）
Y=$OC/node_modules/yaml/package.json
if [ -f "$Y" ]; then
  if (cd "$OC" && node -e "import('yaml/dist/index.js').then(()=>process.exit(0)).catch(()=>process.exit(1))") 2>/dev/null; then
    OK="$OK yaml导出✓"
  else
    python3 - "$Y" <<PY
import json,sys,shutil,datetime
p=sys.argv[1]
shutil.copy2(p,p+".bak-preflight-"+datetime.datetime.now().strftime("%H%M%S"))
d=json.load(open(p,encoding="utf-8"))
ex=d.get("exports") or {}
if "./dist/index.js" not in ex:
    ex["./dist/index.js"]=dict(ex.get(".",{"node":"./dist/index.js"}))
    d["exports"]=ex
    open(p,"w",encoding="utf-8").write(json.dumps(d,indent=2,ensure_ascii=False))
PY
    if (cd "$OC" && node -e "import('yaml/dist/index.js').then(()=>process.exit(0)).catch(()=>process.exit(1))") 2>/dev/null; then OK="$OK yaml导出已修"; else FAIL="$FAIL yaml导出修不上"; fi
  fi
else FAIL="$FAIL 找不到 yaml 包"; fi

# 2. 残留 update-runtime 目录（会触发进程枚举校验）
LEFT=$(ls -d "$OC"/../openclaw-update-runtime-* 2>/dev/null | wc -l)
if [ "$LEFT" -gt 0 ]; then
  TR=/home/j/.openclaw/trash/$(date +%Y%m%d)-update-runtime-preflight; mkdir -p "$TR"
  for d in "$OC"/../openclaw-update-runtime-*; do
    b=$(basename "$d"); SZ=$(du -sb "$d" | cut -f1)
    find "$d" -type f -print0 | sort -z | xargs -0 -r sha256sum > "$TR/$b.sha256" 2>/dev/null || true
    echo "{\"time\":\"$(date +%F_%T)\",\"action\":\"trash\",\"path\":\"$d\",\"size\":$SZ,\"manifest\":\"$TR/$b.sha256\",\"reason\":\"preflight before upgrade\"}" >> $W/state/trash-ledger.jsonl
    mv "$d" "$TR/" 2>/dev/null
  done
  OK="$OK 清残留${LEFT}个"
else OK="$OK 无残留"; fi

# 3. ssh-agent（枚举 cwd 读不到会中止升级；当前无 key，可停）
systemctl --user stop ssh-agent.service ssh-agent.socket 2>/dev/null
if pgrep -x ssh-agent >/dev/null 2>&1; then FAIL="$FAIL ssh-agent仍在"; else OK="$OK agent已停"; fi

# 4. 前提核对
[ -f "$W/state/work/.upgrade-running" ] && FAIL="$FAIL 有升级标志"
[ -f "$W/state/work/.safe-restart-running" ] && FAIL="$FAIL 有安全重启标志"
[ -f "$W/state/work/.watchdog-pause" ] && FAIL="$FAIL 有看门狗暂停标志"
FREE=$(df -Pm /home/j | sed -n 2p | tr -s " " | cut -d" " -f4)
[ "${FREE:-0}" -ge 10000 ] || FAIL="$FAIL 磁盘不足(${FREE}MB)"
[ -z "$FREE" ] && FAIL="$FAIL 磁盘读不到"
H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:18789/health)
[ "$H" = "200" ] || FAIL="$FAIL health=$H"
P=$(curl -s -o /dev/null -w "%{http_code}" --max-time 6 http://127.0.0.1:8899/)
[ "$P" = "200" ] || FAIL="$FAIL 面板=$P"
BUSY=$(pgrep -a -x node 2>/dev/null | grep -E "openclaw (update|upgrade)"; pgrep -a -x npm 2>/dev/null | grep -E "(i|install) -g openclaw")
[ -n "$BUSY" ] && FAIL="$FAIL 升级进程在跑"

VER=$(openclaw --version 2>/dev/null | tail -1)
if [ -z "$FAIL" ]; then
  MSG="✅ 升级前置全部就绪（$VER，磁盘余 ${FREE}MB，health 200，面板 200）：$OK —— 可以点「升级」"
else
  MSG="⚠️ 升级前置未通过：$FAIL（已完成：$OK）"
fi
log "verdict FAIL=[$FAIL] OK=[$OK]"
echo "$MSG" > "$OUT"
echo "$MSG"
exit 0
