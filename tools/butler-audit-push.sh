#!/bin/bash
# butler-audit-push.sh v1.0 — 五家自审一条推送（零 token，2026-11-15 主公令）
set -u
W=/home/j/.openclaw/workspace
cd "$W" || exit 1
D=$(date +%F)
BODY=$(python3 tools/butler-daily.py 2>/dev/null | head -6)
ART=$(python3 tools/butler-artifact-check.py 2>&1)
HITS=$(for f in /home/j/openclaw-workspaces/maint/state/self-review/*$D*.md /home/j/.openclaw/workspace-backup/state/self-review/*$D*.md /home/j/.openclaw/workspace-model/state/self-review/*$D*.md /home/j/openclaw-workspaces/work/state/self-review/*$D*.md /home/j/openclaw-workspaces/sheet-music/state/self-review/*$D*.md; do
  [ -f "$f" ] || continue
  grep -hE '(^|[[:space:]])(P0|P1)' "$f" 2>/dev/null | head -2 | sed 's/^ *//' | cut -c1-80
done | head -4)
SHORT=$(echo "$D" | cut -c6-)
MSG="【五家自审 $SHORT】
$BODY
产物核查：$ART"
if [ -n "$HITS" ]; then MSG="$MSG
要点：
$HITS"; fi
NOTIFY_ALERT=1 timeout 40 bash tools/notify.sh "$MSG" >/dev/null 2>&1 &
sleep 3
echo "pushed-ok"
