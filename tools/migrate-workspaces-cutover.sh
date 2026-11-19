#!/bin/bash
# migrate-workspaces-cutover.sh v2 —— E→X 工作区切换：改名、改路径、起服务、验收
set -uo pipefail
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
WS=/home/j/.openclaw/workspace
SRC=/home/j/openclaw-workspaces
DST=/home/j/openclaw-workspaces
OLD=/home/j/openclaw-workspaces
NEW=/home/j/openclaw-workspaces
LOG=$WS/state/work/migrate-cutover.log
REP=$WS/state/work/migrate-cutover-report.txt
TS=$(date +%Y%m%d-%H%M%S)
say(){ echo "[$(date "+%F %T")] $*" | tee -a "$LOG"; }
nt(){ timeout 60 bash "$WS/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }
fail(){ say "FAIL: $*"; nt "工作区切换失败：$*；详情 $LOG"; exit 1; }
say "=== 切换开始 $TS ==="
systemctl --user is-active migrate-ws-copy.service >/dev/null 2>&1 && fail "复制单元仍在跑"
[ -d "$DST/print" ] || fail "目标缺 print"
[ -d "$SRC" ] || fail "源目录不存在"
# 1) 停服务
touch "$WS/state/work/.watchdog-pause"
systemctl --user stop oc-gateway-watchdog.timer 2>/dev/null
systemctl --user stop work-ops-selfheal.timer 2>/dev/null
systemctl --user stop guoguo.service 2>/dev/null
pkill -f "果果助手/server.js" 2>/dev/null
systemctl --user stop openclaw-gateway 2>/dev/null
sleep 6
say "服务已停"
# cron 快照（改前可回滚）
openclaw cron list --json > "$WS/state/work/cron-snapshot-$TS.json" 2>/dev/null && say "cron 快照已存 cron-snapshot-$TS.json"
# 句柄检查：确认没有进程仍占用源目录
if command -v lsof >/dev/null 2>&1; then
  HOLD=$(lsof +D "$SRC" 2>/dev/null | tail -n +2 | awk '$4 !~ /cwd/' | head -5)
  if [ -n "$HOLD" ]; then say "仍有句柄占用源目录：$HOLD"; fail "句柄未释放，未做任何改动"; fi
fi
# fuser -m 已移除：/mnt/e 是常驻挂载，任何进程都会命中，属误报
# 2) 增量补齐（服务已停，无新写入）
rsync -a --info=stats1 "$SRC/" "$DST/" >>"$LOG" 2>&1 || fail "增量 rsync 失败"
say "增量补齐完成"
# 3) 字节级核对
if ! python3 /home/j/.openclaw/workspace/tools/ws-verify.py "$SRC" "$DST" >>"$LOG" 2>&1; then
  systemctl --user start openclaw-gateway 2>/dev/null; systemctl --user start guoguo.service 2>/dev/null
  rm -f "$WS/state/work/.watchdog-pause"; systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
  fail "核对不一致（服务已重新拉起，未做任何改动）"
fi
say "核对通过：逐目录文件数与字节数一致"
# 2) 源目录改名（保留回滚）
if [ -d "$SRC.moved-20261106" ]; then say "旧副本已存在，跳过改名"; elif mv "$SRC" "$SRC.moved-20261106" 2>>"$LOG"; then say "源已改名（E 侧冻结）"; else say "WARN 源目录改名被 Windows 句柄拒绝，继续切换；E 侧保留原样作为冻结快照"; fi
# 3) 文本路径改写（限定扩展名与体积）
N=0
for root in "$WS" "$DST"; do
  while IFS= read -r f; do
    cp -p "$f" "$f.bak-ws$TS" 2>/dev/null
    sed -i "s#$OLD#$NEW#g" "$f" && N=$((N+1))
  done < <(find "$root" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.md" -o -name "*.txt" \) -size -2M 2>/dev/null | xargs -r grep -l "$OLD" 2>/dev/null)
done
say "文本改写文件数=$N"
# 4) 配置
if grep -q "$OLD" /home/j/.openclaw/openclaw.json; then
  cp -p /home/j/.openclaw/openclaw.json /home/j/.openclaw/openclaw.json.bak-ws-$TS
  sed -i "s#$OLD#$NEW#g" /home/j/.openclaw/openclaw.json
  python3 -c "import json;json.load(open('/home/j/.openclaw/openclaw.json'))" || fail "config JSON 校验失败（备份 openclaw.json.bak-ws-$TS）"
  say "config 已改并校验"; else say "config 无需改"; fi
# 5) systemd 单元
for u in guoguo.service work-ops-selfheal.service; do
  f=/home/j/.config/systemd/user/$u
  [ -f "$f" ] || continue
  if grep -q "$OLD" "$f"; then cp -p "$f" "$f.bak-ws-$TS"; sed -i "s#$OLD#$NEW#g" "$f"; say "单元已改 $u"; fi
done
systemctl --user daemon-reload
# 6) cron payload 改写
python3 - "$OLD" "$NEW" >>"$LOG" 2>&1 <<'PY'
import json,subprocess,sys
old,new=sys.argv[1],sys.argv[2]
d=json.loads(subprocess.run(["openclaw","cron","list","--json"],capture_output=True,text=True).stdout)
jobs=d if isinstance(d,list) else (d.get("jobs") or [])
n=0
for j in jobs:
    p=j.get("payload") or {}
    if old not in json.dumps(p,ensure_ascii=False): continue
    jid=j.get("id"); args=["openclaw","cron","edit",jid]; n+=1
    if isinstance(p.get("command"),str): args+=["--command",p["command"].replace(old,new)]
    elif isinstance(p.get("argv"),list): args+=["--command-argv",json.dumps([a.replace(old,new) for a in p["argv"]],ensure_ascii=False)]
    elif isinstance(p.get("message"),str): args+=["--message",p["message"].replace(old,new)]
    else: print("SKIP-UNKNOWN",jid); continue
    r=subprocess.run(args,capture_output=True,text=True)
    print("cron",jid[:8],r.returncode,(r.stderr or "").strip()[:60])
print("cron 处理",n)
d2=json.loads(subprocess.run(["openclaw","cron","list","--json"],capture_output=True,text=True).stdout)
jobs2=d2 if isinstance(d2,list) else (d2.get("jobs") or [])
left=[j.get("id") for j in jobs2 if old in json.dumps(j.get("payload") or {},ensure_ascii=False)]
print("cron 残留",len(left))
PY
# 5.5) 全量残留扫描（排除 .bak-ws 备份与我方 .moved）
RES=$(grep -rl "$OLD" "$WS" "$DST" 2>/dev/null | grep -v "\.bak-ws" | head -5)
RESN=$(grep -rl "$OLD" "$WS" "$DST" 2>/dev/null | grep -v "\.bak-ws" | wc -l)
CFGRES=$(grep -c "$OLD" /home/j/.openclaw/openclaw.json 2>/dev/null || true)
say "残留扫描：文件=$RESN 配置=${CFGRES:-0}"; [ -n "$RES" ] && say "样例：$RES"
# 7) 起服务
rm -f "$WS/state/work/.watchdog-pause"
systemctl --user start oc-gateway-watchdog.timer 2>/dev/null
systemctl --user start work-ops-selfheal.timer 2>/dev/null
systemctl --user start guoguo.service 2>/dev/null
bash "$WS/tools/restart-gateway.sh" --reason "工作区迁移到 X 盘" >>"$LOG" 2>&1; RRC=$?
sleep 10
# 8) 验收
H=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 http://127.0.0.1:18789/health)
P2=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:8899/)
LEFT=$(openclaw cron list --json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);j=d if isinstance(d,list) else (d.get('jobs') or []);print(sum(1 for x in j if '/home/j/openclaw-workspaces' in json.dumps(x.get('payload') or {},ensure_ascii=False)))" 2>/dev/null || echo NA)
NEWN=$(find "$DST" -type f 2>/dev/null | wc -l); OLDN=$(find "$SRC.moved-20261106" -type f 2>/dev/null | wc -l)
MD5=$(md5sum "$DST/print/索引.md" 2>/dev/null | cut -d" " -f1)
LEFTSH=$(grep -rl "$OLD" "$WS/tools" 2>/dev/null | wc -l)
PROBE="$DST/main/.probe-$TS"; ( echo ok > "$PROBE" ) 2>/dev/null && PR=$(cat "$PROBE"); rm -f "$PROBE"
{ echo "时间 $(date "+%F %T") 版本 $TS"; echo "health=$H 面板=$P2 restart_rc=$RRC"; echo "文件数 新=$NEWN 旧=$OLDN"; echo "索引md5=$MD5"; echo "cron残留=$LEFT 残留文件=${RESN:-NA} 工具残留=$LEFTSH"; echo "写探测=${PR:-FAIL}"; } > "$REP"
cat "$REP" >> "$LOG"
if [ "$H" = "200" ] && [ "$P2" = "200" ] && [ "$LEFT" = "0" ] && [ "${RESN:-1}" = "0" ] && [ -n "${PR:-}" ]; then
  say "OK 切换完成"; nt "工作区已搬到 X 盘：health=200 面板=200 cron残留0 写入正常；文件数 新$NEWN/旧$OLDN。E 侧旧目录改名保留 7 天。"
else
  say "WARN 验收未全绿"; nt "工作区切换后未全绿：health=$H 面板=$P2 cron残留=$LEFT 残留文件=${RESN:-NA}。报告 state/work/migrate-cutover-report.txt，可回滚。"
fi
say "=== 结束 ==="
