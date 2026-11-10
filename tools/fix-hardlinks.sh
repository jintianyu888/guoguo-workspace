#!/bin/bash
# fix-hardlinks.sh —— 打破工作区引导文件的硬链接（doctor: path must not be hardlinked）
set -u
W=/home/j/.openclaw/workspace
BK=$W/state/tmp/bootstrap-backup-$(date +%Y%m%d-%H%M)
mkdir -p "$BK"
n=0; fixed=0
for d in /home/j/openclaw-workspaces/*/; do
  [ -d "$d" ] || continue
  for f in AGENTS.md SOUL.md IDENTITY.md USER.md; do
    p="$d$f"
    [ -f "$p" ] || continue
    n=$((n+1))
    cp -p "$p" "$BK/$(basename "$d")__$f" 2>/dev/null
    h=$(stat -c %h "$p" 2>/dev/null || echo 1)
    if [ "$h" -gt 1 ]; then
      cp -p "$p" "$p.tmpfix" && mv -f "$p.tmpfix" "$p" && fixed=$((fixed+1))
    fi
  done
done
echo "scanned=$n broken_links_fixed=$fixed backup=$BK"
echo -n "remaining_hardlinked="; find /home/j/openclaw-workspaces -maxdepth 2 -name "AGENTS.md" -o -maxdepth 2 -name "SOUL.md" 2>/dev/null | while read -r f; do h=$(stat -c %h "$f" 2>/dev/null || echo 1); [ "$h" -gt 1 ] && echo "$f"; done | wc -l
