#!/usr/bin/env bash
# session-guard-watch.sh v1.1 —— 哨兵的哨兵（2026-11-01）
# 只读检查：last-run.json 新鲜度、crontab 条目、脚本可执行位。
# 双审 2026-11-01：zai/glm-5.3 + qianwen/qwen3.8-max 均「有条件通过」，Must 已落地。
# 退出码恒 0；判定写 state/session-guard/watch-last.json
set -u
WS=${OPENCLAW_WS:-/home/j/.openclaw/workspace}
STATE="$WS/state/session-guard"
LAST="$STATE/last-run.json"
OUT="$STATE/watch-last.json"
LOCK="$STATE/.watch.lock"
NOTIFY="$WS/tools/notify.sh"
MAX_AGE=2700
DEDUPE=21600
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PATH=/usr/local/bin:/usr/bin:/bin:$PATH

now=$(date +%s)
problems=""

# 1) 新鲜度
if [ ! -f "$LAST" ]; then
  problems="last-run.json 不存在（哨兵从未成功运行）"
else
  if mtime=$(stat -c %Y "$LAST" 2>/dev/null); then
    age=$(( now - mtime ))
    [ "$age" -gt "$MAX_AGE" ] && problems="哨兵 $(( age / 60 )) 分钟没跑（上限 $(( MAX_AGE / 60 )) 分钟）"
  else
    problems="无法读取 last-run.json 的时间戳（文件存在但 stat 失败）"
  fi
fi

# 2) cron 条目（精确匹配哨兵本身，排除本看门狗自己的条目）
if command -v crontab >/dev/null 2>&1; then
  if crontab -l 2>/dev/null | grep -vF "session-guard-watch" | grep -qF "/tools/session-guard.sh"; then
    :
  else
    problems="${problems:+$problems；}crontab 里没有 session-guard 条目"
  fi
else
  problems="${problems:+$problems；}无法检查 cron（crontab 命令不可用）"
fi

# 3) 可执行位
if [ ! -x "$WS/tools/session-guard.sh" ]; then
  problems="${problems:+$problems；}tools/session-guard.sh 不可执行"
fi

# 可写目录判断：state 不可写时降级到 /tmp，避免去重失效导致告警风暴
if [ -d "$STATE" ] && [ -w "$STATE" ]; then
  FLAG="$STATE/watch-last.flag"
else
  FLAG="${TMPDIR:-/tmp}/session-guard-watch-$(id -u).flag"
fi

status="ok"; alerted=0
if [ -n "$problems" ]; then
  status="problem"
  # flock 保护 读-判-写，避免并发重复告警
  exec 9>"$LOCK" 2>/dev/null || exec 9>/tmp/session-guard-watch.lock
  flock -w 5 9 2>/dev/null || true
  last_alert=0
  [ -f "$FLAG" ] && last_alert=$(cut -d'|' -f1 "$FLAG" 2>/dev/null || echo 0)
  case "$last_alert" in ''|*[!0-9]*) last_alert=0 ;; esac
  if [ $(( now - last_alert )) -ge "$DEDUPE" ]; then
    if timeout -k 5 30 bash "$NOTIFY" --alert "🛑 会话哨兵停摆：$problems
处置：检查 crontab -l、tools/session-guard.sh 可执行位、state 目录权限；必要时手动跑 tools/session-guard.sh --json。" >/dev/null 2>&1; then
      alerted=1
      printf '%s|%s\n' "$now" "$problems" > "$FLAG" 2>/dev/null || true
    fi
  fi
  exec 9>&- 2>/dev/null || true
else
  rm -f "$FLAG" 2>/dev/null || true
fi

# JSON 用 python 生成，避免引号/反斜杠破坏文件
python3 - "$OUT" "$now" "$status" "$problems" "$alerted" <<'PY' 2>/dev/null || true
import json,sys
out,ts,status,problems,alerted=sys.argv[1:6]
try: d={"ts":int(ts),"status":status,"problems":problems,"alerted":int(alerted)}
except ValueError: d={"ts":0,"status":status,"problems":problems,"alerted":0}
open(out,"w",encoding="utf-8").write(json.dumps(d,ensure_ascii=False)+"\n")
PY

echo "session-guard-watch: status=$status alerted=$alerted problems=${problems:-none}"
exit 0
