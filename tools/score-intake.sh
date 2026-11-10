#!/usr/bin/env bash
# score-intake.sh v5 —— 乐谱自动入库（去重+编目）并在有变更时写「待通知」· 2026-10-03 主公令
set -u
SM=/home/j/openclaw-workspaces/print/scores
SRC1=/home/j/openclaw-workspaces/print/outbox-scores
SRC2=$SM/incoming
SRC3=/home/j/openclaw-workspaces/print/media/inbound
SRC4=/home/j/.openclaw/media/inbound
DEST=$SM/files; IDX=$SM/incoming-index.md; HS=$SM/.hashes; DUP=$SM/duplicates
LOG=/home/j/.openclaw/workspace/state/work/score-intake.log
PEND=/home/j/.openclaw/workspace/state/work/score-intake-pending.txt
KEYW='谱|sheet|score|music|BWV|PRAELUD|练习曲|奏鸣曲|赋格|前奏曲|圆舞曲|夜曲|协奏曲|变奏曲|\.musicxml|\.mxl'
mkdir -p "$SRC1" "$SRC2" "$DEST" "$DUP"
[ -f "$IDX" ] || echo '# 乐谱索引（管理序列）' > "$IDX"
[ -f "$HS" ] || : > "$HS"
add=0; dup=0; skip=0; NEWLIST=''
process() {
  f="$1"; mode="$2"; src="$3"; b=$(basename "$f")
  case "$b" in *.pdf|*.PDF|*.png|*.jpg|*.jpeg|*.musicxml|*.mxl|*.xml|*.mid|*.midi|*.mscz) ;; *) skip=$((skip+1)); return ;; esac
  h=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1); [ -n "$h" ] || return
  if grep -q "^$h" "$HS" 2>/dev/null; then [ "$mode" = move ] && mv -f "$f" "$DUP/$b" 2>/dev/null; dup=$((dup+1)); return; fi
  nb="$b"; i=1; while [ -e "$DEST/$nb" ]; do nb="${b%.*}-$i.${b##*.}"; i=$((i+1)); done
  if cp -p "$f" "$DEST/$nb"; then
    [ "$mode" = move ] && rm -f "$f"
    printf '%s  %s\n' "$h" "$nb" >> "$HS"
    printf -- '- %s | 文件: %s | sha256: %s | 来源: %s | 收录: %s\n' "${nb%.*}" "$nb" "$h" "$src" "$(date '+%F %H:%M')" >> "$IDX"
    add=$((add+1)); NEWLIST="${NEWLIST}${NEWLIST:+、}${nb%.*}"
  fi
}
for S in "$SRC1:move:outbox" "$SRC2:move:incoming"; do
  d=$(echo "$S" | cut -d: -f1); m=$(echo "$S" | cut -d: -f2); src=$(echo "$S" | cut -d: -f3)
  [ -d "$d" ] || continue
  find "$d" -maxdepth 1 -type f > /home/j/.openclaw/workspace/state/tmp/_si.$$ 2>/dev/null
  while IFS= read -r f; do [ -n "$f" ] && process "$f" "$m" "$src"; done < /home/j/.openclaw/workspace/state/tmp/_si.$$; rm -f /home/j/.openclaw/workspace/state/tmp/_si.$$
done
for S3 in "$SRC3" "$SRC4"; do
  [ -d "$S3" ] || continue
  find "$S3" -type f 2>/dev/null | grep -iE "$KEYW" > /home/j/.openclaw/workspace/state/tmp/_s4.$$ 2>/dev/null
  while IFS= read -r f; do [ -n "$f" ] && process "$f" copy group-inbound; done < /home/j/.openclaw/workspace/state/tmp/_s4.$$; rm -f /home/j/.openclaw/workspace/state/tmp/_s4.$$
done
TOTAL=$(ls "$DEST" 2>/dev/null | wc -l)
echo "[$(date '+%F %T')] 新增 $add · 去重 $dup · 忽略 $skip · 仓库共 $TOTAL 份" >> "$LOG"
# 2026-10-17 主公令：只有真新增才通知；纯重复不再每 15 分钟刷屏
if [ "$add" -gt 0 ]; then
  { echo "📚 乐谱库更新（$(date '+%F %H:%M')）";
    echo "• 新增收纳 $add 份：$NEWLIST";
    [ "$dup" -gt 0 ] && echo "• 重复跳过 $dup 份（与库里内容相同）";
    echo "• 当前乐谱库共 $TOTAL 份"; } >> "$PEND"
fi