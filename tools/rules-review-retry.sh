#!/bin/bash
# rules-review-retry.sh — 守则双审自动重跑；两路都真跑完且无否决 → 自动同步全部管家
set -uo pipefail
cd /home/j/.openclaw/workspace || exit 1
PROMPT=/tmp/rules-review-auto.txt
{
  echo '审查对象：以下守则即将硬性同步进所有管家 AGENTS.md 的只读标记块（含版本号）。'
  echo '请回答：A 哪些必须所有管家知道、哪些可删；B 有无遗漏硬性条目；C 同步机制风险。'
  echo '最后一行给结论：GO / GO-WITH-FIXES / NO-GO。'
  echo '----- 守则全文 -----'
  cat docs/管家通用守则.md
} > $PROMPT
OUT=$(timeout 900 bash tools/cross-review.sh --n 2 --task "管家通用守则自动双审" --prompt-file $PROMPT 2>&1)
echo "$OUT"
DIR=$(echo "$OUT" | grep -o '/home/j/.openclaw/workspace/state/work/cross-review/[0-9-]*' | tail -1)
N=0; GO=0; NOGO=0
for f in "$DIR"/*.txt; do
  [ -f "$f" ] || continue
  SZ=$(stat -c%s "$f")
  [ "$SZ" -lt 200 ] && continue
  N=$((N+1))
  grep -q 'NO-GO' "$f" && NOGO=1
  grep -qE 'GO-WITH-FIXES|GO' "$f" && GO=$((GO+1))
done
echo "有效评审 $N 份，GO $GO，否决 $NOGO"
if [ "$N" -ge 2 ] && [ "$NOGO" -eq 0 ]; then
  bash tools/agent-common-sync.sh --apply | tail -3
  bash tools/notify.sh "管家通用守则双审通过（$N 份），已同步到所有管家" >/dev/null 2>&1 || true
  exit 0
fi
bash tools/notify.sh --alert "管家通用守则双审未完成（有效 $N 份，否决 $NOGO），未同步；目录 $DIR" >/dev/null 2>&1 || true
exit 1
