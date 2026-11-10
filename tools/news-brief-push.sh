#!/bin/bash
# news-brief-push.sh —— 网关侧零 token 简报（2026-11-07 主公批）
# 由 cron 直接调起：抓取 → 校验 → 推送飞书。不经过任何 agent，不吃 exec 权限。
set -uo pipefail
W=/home/j/.openclaw/workspace
OUT=$W/state/tmp/news-brief.txt
LOG=$W/state/work/news-brief.log
mkdir -p "$(dirname "$OUT")" "$(dirname "$LOG")"
echo "== $(date "+%F %T") 开始" >> "$LOG"
sh "$W/tools/news-fetch.sh" > "$OUT" 2>>"$LOG" || { echo "抓取失败 rc=$?" >> "$LOG"; bash "$W/tools/notify.sh" "简报抓取失败，详见 state/work/news-brief.log" >/dev/null 2>&1; exit 1; }
BYTES=$(wc -c < "$OUT")
echo "抓取完成 ${BYTES} 字节" >> "$LOG"
if [ "$BYTES" -lt 200 ]; then echo "产出过短，跳过推送" >> "$LOG"; exit 2; fi
# 单条消息上限保护：超长截断到 3500 字并在尾部说明
python3 - "$OUT" <<"PY"
import sys
p=sys.argv[1]
t=open(p,encoding="utf-8",errors="ignore").read()
if len(t)>3500: t=t[:3500]+"\n…（过长已截断，完整版见 state/tmp/news-brief.txt）"
open(p,"w",encoding="utf-8").write(t)
PY
# 2026-11-08 修 2：改回新闻管家自己的应用投递。
# 之前失败是 99992361（open_id 跨应用）——因为用的是主应用 open_id；
# 新闻管家应用里主公的 open_id 是 ou_b8174cab…（取自 agent:news 的会话键），已验证可发。
NOTIFY_ACCOUNT=news NOTIFY_TARGET=user:ou_b8174cabf878472334b478da0a133277 \
  bash "$W/tools/notify.sh" "$(cat "$OUT")" >> "$LOG" 2>&1
RC=$?
echo "推送 rc=$RC" >> "$LOG"
exit $RC
