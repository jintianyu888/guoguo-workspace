#!/bin/bash
# butler-fact-pack.sh v1.0 — 通用管家自审事实包（零 token）
set -u
A=${1:-}
case "$A" in
  work) WS=/home/j/openclaw-workspaces/work ;;
  hermess) WS=/home/j/openclaw-workspaces/sheet-music ;;
  model) WS=/home/j/.openclaw/workspace-model ;;
  backup) WS=/home/j/.openclaw/workspace-backup ;;
  *) echo 'usage: butler-fact-pack.sh <work|hermess|model|backup>' >&2; exit 2 ;;
esac
D=$(date +%F)
OUT="$WS/state/self-review/self-review-$D.md"
mkdir -p "$WS/state/self-review"
{
  echo "# $A 自审事实包 $(date '+%F %T')"
  echo "> 零 token 脚本生成；结论段由 agent 补写，缺失=未写结论"
  echo "## 网关"
  curl -s -o /dev/null -w 'HTTP %{http_code}\n' --max-time 5 http://127.0.0.1:18789/health 2>/dev/null || echo 'HTTP 不可达'
  echo "## 磁盘"
  df -h / /mnt/x /mnt/d /mnt/e /mnt/h 2>/dev/null | awk 'NR==1 || /^\/dev/ {print}' | head -8
  echo "## cron 错误任务"
  openclaw cron list --json 2>/dev/null | python3 -c "import json,sys;d=json.load(sys.stdin);js=d.get('jobs',d);e=[j.get('name') for j in js if j.get('enabled') and j.get('lastRunStatus')=='error'];print(chr(10).join(e[:6]) or '无')" 2>/dev/null || echo '采集失败'
  echo "## 今日在办"
  python3 /home/j/.openclaw/workspace/tools/tasks-db.py list 2>/dev/null | grep -E '\[(pending|in_progress)' | head -8
  case "$A" in
    work)
      echo "## work 队列(按 owner=work)"
      python3 /home/j/.openclaw/workspace/tools/tasks-db.py list 2>/dev/null | grep -i 'work' | head -6
      echo "## 最近工作日志(5 条)"
      tail -5 /home/j/.openclaw/workspace/state/log/worklog.jsonl 2>/dev/null | cut -c1-220
      echo "## 最近写过的文件"
      find "$WS" -type f -newermt '-2 days' 2>/dev/null | grep -v '/\.' | head -8
      ;;
    hermess)
      echo "## Hermes 任务与产出"
      python3 /home/j/.openclaw/workspace/tools/tasks-db.py list 2>/dev/null | grep -i -E 'hermess|sheet|乐谱' | head -6
      echo "## 工作区最近文件"
      find "$WS" -type f -newermt '-3 days' 2>/dev/null | grep -v '/\.' | head -8
      echo "## 最近自审文件"
      ls -t "$WS/state/self-review" 2>/dev/null | head -3
      ;;
  esac
} > "$OUT.tmp" 2>&1
mv "$OUT.tmp" "$OUT"
echo "$OUT $(wc -c < "$OUT") bytes"
