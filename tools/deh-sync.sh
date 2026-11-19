#!/bin/bash
# D->E/H 补齐今日归档 + 三端 SHA256 比对（2026-10-18）
set -uo pipefail
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/deh-sync.log
say(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
say "=== 开始 D->E/H 补齐 ==="
NEED="2026-10-18T13-09-20.879+08-00-openclaw-backup.tar.gz 2026-10-18T14-01-45.078+08-00-openclaw-backup.tar.gz"
for tgt in /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
  free_kb=$(df -P "$tgt" | awk 'NR==2{print $4}')
  say "$tgt 可用 $((free_kb/1024/1024))G"
  [ "$free_kb" -gt $((50*1024*1024)) ] || { say "空间不足，跳过 $tgt"; continue; }
  for n in $NEED; do
    src=/mnt/d/openclaw-backups/$n; dst=$tgt/$n
    [ -f "$src" ] || { say "缺源 $n"; continue; }
    if [ -f "$dst" ] && [ "$(stat -c%s "$dst")" = "$(stat -c%s "$src")" ]; then say "已有且大小一致 $tgt/$n"; continue; fi
    say "复制 -> $tgt/$n"
    cp -f "$src" "$dst.part" || { say "复制失败 $n"; rm -f "$dst.part"; continue; }
    a=$(stat -c%s "$src"); b=$(stat -c%s "$dst.part")
    if [ "$a" = "$b" ]; then mv -f "$dst.part" "$dst"; say "大小一致 $b，已落位"; else say "大小不符 $a vs $b，保留 .part"; fi
  done
done
say "=== 三端哈希比对（仅最新一份）==="
N=2026-10-18T14-01-45.078+08-00-openclaw-backup.tar.gz
for d in d e h; do
  f=/mnt/$d/openclaw-backups/$N
  if [ -f "$f" ]; then h=$(sha256sum "$f" | awk '{print $1}'); say "$d $h"; else say "$d 缺文件"; fi
done
say "=== 完成 ==="
