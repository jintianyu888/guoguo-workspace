#!/bin/bash
# wsl-image-export.sh —— 导出 WSL 整机镜像到 E 和 H，写时算 SHA256，保留 2 份/盘
# 用法：--check 只检查环境；--hash 导出后计算哈希（默认开）
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/wsl-image.log
WSLX=/mnt/c/Windows/System32/wsl.exe
E=/mnt/e/wsl-backup
H=/mnt/h/wsl-backup
KEEP=3
now=$(date +%Y%m%d-%H%M)
name="ubuntu-$now.tar"
mkdir -p "$E" "$H" "$W/state/work"
log() { echo "[$(date "+%F %T")] $*" >> "$LOG"; }

if [ "${1:-}" = "--check" ]; then
  echo "wsl.exe: $([ -x "$WSLX" ] && echo OK || echo MISSING)"
  echo "E 剩余: $(df -h /mnt/e | awk "NR==2{print \$4}")  H 剩余: $(df -h /mnt/h | awk "NR==2{print \$4}")"
  echo "现有: E $(ls "$E"/*.tar 2>/dev/null | wc -l) 份 / H $(ls "$H"/*.tar 2>/dev/null | wc -l) 份"
  exit 0
fi

log "开始导出 Ubuntu -> $name"
rc=0
"$WSLX" --export Ubuntu "$(wslpath -w "$E/$name.part")" >> "$LOG" 2>&1 || rc=1
[ $rc -eq 0 ] && mv -f "$E/$name.part" "$E/$name" || { log "❌ 导出中断，保留 .part 供排查"; exit 1; }
if [ $rc -ne 0 ]; then log "❌ E 盘导出失败 rc=$rc"; bash "$W/tools/notify.sh" "❌ WSL 整机镜像导出失败（E 盘）" "详见 state/work/wsl-image.log"; exit 1; fi
sz=$(stat -c %s "$E/$name" 2>/dev/null || echo 0)
if [ "$sz" -lt 50000000000 ]; then log "❌ E 盘产物过小 ${sz}B，判定失败"; exit 1; fi
log "✅ E 盘完成 ${sz}B"

cp -f "$E/$name" "$H/$name" && log "✅ H 盘复制完成" || { log "❌ H 盘复制失败"; exit 1; }

hs=$(sha256sum "$E/$name" | cut -d" " -f1)
hh=$(sha256sum "$H/$name" | cut -d" " -f1)
if [ "$hs" = "$hh" ]; then log "✅ 两端哈希一致 ${hs:0:16}"; else log "❌ 两端哈希不一致 E=${hs:0:16} H=${hh:0:16}"; exit 1; fi
printf '{"ts":"%s","image":"%s","size":%s,"sha256":"%s"}\n' "$(date -Iseconds)" "$name" "$sz" "$hs" >> "$E/manifest.jsonl"
printf '{"ts":"%s","image":"%s","size":%s,"sha256":"%s"}\n' "$(date -Iseconds)" "$name" "$sz" "$hs" >> "$H/manifest.jsonl"

# 轮转：每盘只留 KEEP 份；删旧份必须在另一盘找到同名+同大小+同哈希的副本
for D in "$E" "$H"; do
  if [ "$D" = "$E" ]; then O="$H"; else O="$E"; fi
  n=0
  for f in $(ls -t "$D"/ubuntu-*.tar 2>/dev/null); do
    n=$((n+1)); [ "$n" -le "$KEEP" ] && continue
    bn=$(basename "$f"); of="$O/$bn"
    if [ ! -f "$of" ]; then log "⚠️ 保留 $bn（另一盘无副本）"; continue; fi
    s1=$(stat -c %s "$f"); s2=$(stat -c %s "$of")
    if [ "$s1" != "$s2" ]; then log "⚠️ 保留 $bn（大小不一致）"; continue; fi
    h1=$(sha256sum "$f" | cut -d" " -f1); h2=$(sha256sum "$of" | cut -d" " -f1)
    if [ "$h1" = "$h2" ]; then
      mkdir -p /mnt/e/openclaw-trash/wsl-image 2>/dev/null
      mv "$f" /mnt/e/openclaw-trash/wsl-image/ && log "🗑 移入回收站 $bn（另一盘同哈希 $h1）"
    else log "⚠️ 保留 $bn（哈希不一致）"; fi
  done
done
log "完成"
bash "$W/tools/notify.sh" "✅ WSL 整机镜像已导出" "E+H 各一份：$name（${sz} 字节）"