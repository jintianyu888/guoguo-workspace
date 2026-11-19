#!/usr/bin/env bash
# inbox-sync.sh —— 扫群晖投递区 openclaw-inbox/<管家>/，把新文件拉到对应工作区 inbox/
# 2026-09-26 老板指定：管家要定期自查仓库，有新文件自己就知道
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"
NAS=nas
W=/home/j/.openclaw
NEW=0; LINES=""
map_ws(){
  case "$1" in
    main) echo "$W/workspace";;
    乐谱|sheet-music) echo "$W/workspace-sheet-music";;
    *) echo "$W/workspace-$1";;
  esac
}
for d in $($SSH "$NAS" 'ls -1 ~/openclaw-inbox 2>/dev/null' 2>/dev/null | tr -d '\r' | grep -vE 'WARNING|post-quantum|openssh|upgraded'); do
  WS=$(map_ws "$d"); [ -d "$WS" ] || continue
  DEST="$WS/inbox"; mkdir -p "$DEST"
  FILES=$($SSH "$NAS" "ls -1 ~/openclaw-inbox/$d 2>/dev/null" 2>/dev/null | tr -d '\r' | grep -vE 'WARNING|post-quantum|openssh|upgraded')
  [ -z "$FILES" ] && continue
  n=0
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -e "$DEST/$f" ] && continue
    if $SSH "$NAS" "cat ~/openclaw-inbox/$d/\"$f\"" > "$DEST/$f" 2>/dev/null; then
      n=$((n+1)); NEW=$((NEW+1))
    fi
  done <<< "$FILES"
  [ "$n" -gt 0 ] && { LINES="${LINES}  · $d → $n 个新文件（已进 $WS/inbox/）\n"; date '+%F %T' >> "$DEST/.sync.log"; echo "$n 个新文件" >> "$DEST/.sync.log"; }
done
if [ "$NEW" -gt 0 ]; then
  echo "📥 投递区有新东西（共 $NEW 个）"
  printf "$LINES"
  echo "—— 各管家请注意：先看你工作区的 inbox/ 处理"
fi

# 2026-10-03 补：收纳打印管家送来的乐谱
bash /home/j/.openclaw/workspace/tools/score-intake.sh >/dev/null 2>&1 || true
