#!/usr/bin/env bash
# free-review-pack.sh —— 给免费模型评审用的当日证据包（零 token，纯收集）
set -u
W=/home/j/.openclaw/workspace
D=${1:-$(date +%F)}
OUT=$W/state/review/free/pack-$D.md
mkdir -p "$(dirname "$OUT")"
ts(){ date "+%F %T"; }
{
  echo "# 评审证据包 $D（生成于 $(ts)）"
  echo
  echo "## 1) 当日工作日志（含证据/回滚）"
  echo '```'
  python3 - "$D" <<'EOF'
import json,sys
d=sys.argv[1]
p='/home/j/.openclaw/workspace/state/log/worklog.jsonl'
n=0
for line in open(p,encoding='utf-8',errors='replace'):
    try: r=json.loads(line)
    except: continue
    if str(r.get('ts','')).startswith(d):
        n+=1
        print(f"[{r.get('ts')}] {r.get('cat')} | {r.get('obj')} | {r.get('result')}")
        if r.get('evidence'): print('   evidence:', str(r['evidence'])[:400])
        if r.get('rollback'): print('   rollback:', str(r['rollback'])[:200])
print(f"\n(共 {n} 条)")
EOF
  echo '```'
  echo
  echo "## 2) 今日改过的脚本/文档（按 mtime）"
  echo '```'
  find "$W/tools" "$W/docs" -type f -newermt "$D 00:00" ! -newermt "$D 23:59" 2>/dev/null | head -60
  echo '--- config ---'
  ls -l --time-style=+%F_%T /home/j/.openclaw/openclaw.json | awk '{print $6, $7}'
  echo '```'
  echo
  echo "## 3) 今日失败的定时任务"
  echo '```'
  timeout 60 openclaw cron list 2>/dev/null | grep -E "error|failed" | head -20
  echo '```'
  echo
  echo "## 4) 今日告警增量"
  echo '```'
  tail -40 "$W/state/maint-alerts/increments-$(echo $D | tr -d '-').csv" 2>/dev/null || echo "(无)"
  echo '```'
  echo
  echo "## 5) 评审要求（给模型）"
  echo '只报具体可验证的缺陷：每条含 位置(文件:行或任务名) / 问题 / 为何是问题 / 严重级 P0-P2 / 验证方法。'
  echo '不要泛泛而谈，不要建议大重构，不要重复证据包已有事实。证据不足写"证据不足"，禁止猜测。'
} > "$OUT"
echo "PACK_OK $OUT $(wc -c < "$OUT") bytes"
