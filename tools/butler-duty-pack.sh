#!/bin/bash
# butler-duty-pack.sh v1.0 — 产出模型探活/队列清算/待办盘点三份事实包（零 token）
set -uo pipefail
W=/home/j/.openclaw/workspace
D=$(date +%F); mkdir -p "$W/state/work"

# 1) 模型探活：从 model-econ 取额度/可用性摘要
{
  echo "# 模型探活 $D"
  out=$(cd "$W" && timeout 90 bash tools/model-econ.sh 2>&1 | head -40)
  if [ -n "$out" ]; then echo "$out"; else echo "⚠ model-econ 无输出（脚本故障或超时）"; fi
  echo
  echo "## 回退链检查"
  python3 - <<'PY'
import json
try:
    d=json.load(open('/home/j/.openclaw/openclaw.json'))
    a=d.get('agents',{}).get('defaults',{}).get('model',{})
    print('default:',a.get('name') or a.get('model'),'fallbacks:',a.get('fallbacks'))
except Exception as e:
    print('读取失败',e)
PY
} > "$W/state/work/model-probe-$D.md" 2>&1

# 2) 队列清算：过期未办
{
  echo "# 队列清算 $D"
  python3 - <<'PY'
import json,datetime,subprocess
try:
    out=subprocess.run(['python3','/home/j/.openclaw/workspace/tools/tasks-db.py','list','--open'],capture_output=True,text=True,timeout=60).stdout
except Exception as e:
    out=f'读取失败 {e}'
print(out[:2000] if out.strip() else '⚠ 任务库无输出')
PY
} > "$W/state/work/queue-clear-$D.md" 2>&1

# 3) Hermess 待办盘点：工作室里 3 天内新增/变化的文档
{
  echo "# Hermess 待办盘点 $D"
  root=/home/j/openclaw-workspaces/sheet-music
  n=$(find "$root" -maxdepth 3 -type f \( -iname '*.pdf' -o -iname '*.docx' -o -iname '*.md' -o -iname '*.musicxml' \) -mtime -3 2>/dev/null | grep -v 'self-review\|/state/' | head -20)
  tot=$(find "$root" -maxdepth 3 -type f 2>/dev/null | grep -v '/state/' | wc -l)
  echo "工作区文件总数: $tot"
  if [ -n "$n" ]; then echo "近 3 天变动:"; echo "$n"; else echo "近 3 天无新文件：本日无新交付，等待主公投料"; fi
  echo "待办任务(hermess/sheet-music):"
  python3 /home/j/.openclaw/workspace/tools/tasks-db.py list --open 2>/dev/null | grep -i 'hermess\|乐谱\|sheet' | head -10 || echo "  无"
} > "$W/state/work/hermess-intake-$D.md" 2>&1

# 4) 备份盘位事实包（供 07:10 报告与自审共用，唯一事实源=脚本）
mkdir -p /home/j/.openclaw/workspace-backup/state/reports
{
  echo "# 备份盘位体检 $D"
  timeout 120 bash "$W/tools/backup-butler-check.sh" 2>&1 | head -40
} > "/home/j/.openclaw/workspace-backup/state/reports/backup-$D.md" 2>&1
printf '%-16s %sB\n' backup-report "$(stat -c%s /home/j/.openclaw/workspace-backup/state/reports/backup-$D.md 2>/dev/null || echo 0)"

for f in model-probe queue-clear hermess-intake; do
  p="$W/state/work/$f-$D.md"; printf '%-16s %sB\n' "$f" "$(stat -c%s "$p" 2>/dev/null || echo 0)"
done
