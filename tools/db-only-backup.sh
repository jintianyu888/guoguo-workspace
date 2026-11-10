#!/bin/bash
# db-only-backup.sh —— doctor 前定向备份：只备 agent SQLite 库 + 配置，校验 sha256
set -u
export PATH="/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin"
BK="${1:-/mnt/e/openclaw-predanger-doctor-20261101}"
FAIL=0
mkdir -p "$BK"
for f in /home/j/.openclaw/agents/*/agent/openclaw-agent.sqlite; do
  a=$(basename $(dirname $(dirname "$f")))
  mkdir -p "$BK/$a"
  timeout 900 rsync -a --inplace "$f" "$BK/$a/" || FAIL=1
  s1=$(sha256sum "$f" | cut -d' ' -f1)
  s2=$(sha256sum "$BK/$a/openclaw-agent.sqlite" 2>/dev/null | cut -d' ' -f1)
  if [ "$s1" = "$s2" ] && [ -n "$s1" ]; then echo "OK $a"; else echo "MISMATCH $a"; FAIL=1; fi
done
cp -a /home/j/.openclaw/openclaw.json "$BK/" 2>/dev/null || true
du -sh "$BK"
exit $FAIL
