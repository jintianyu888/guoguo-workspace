#!/bin/bash
# dl-fast.sh v2 —— 多连接分段（curl + Range；修正 -C 与 -r 冲突）
set -u
U="$1"; O="$2"; N="${3:-8}"
D=$(dirname "$O"); mkdir -p "$D"
TOT=$(curl -sI "$U" | tr -d '\r' | awk -F': ' 'tolower($1)=="content-length"{print $2; exit}')
[ -n "$TOT" ] || { echo "取不到长度"; exit 1; }
echo "总大小 $TOT 字节，分 $N 段"
SEG=$(( (TOT + N - 1) / N ))
pids=""
for i in $(seq 0 $((N-1))); do
  A=$(( i * SEG )); B=$(( A + SEG - 1 )); [ $B -ge $TOT ] && B=$((TOT-1))
  P="$O.part$i"; LEN=$((B - A + 1))
  HAVE=$(stat -c %s "$P" 2>/dev/null || echo 0)
  [ "$HAVE" -ge "$LEN" ] && { echo "段$i 已完成"; continue; }
  C=$((A + HAVE))
  ( curl -s -r ${C}-${B} "$U" -o "$P" ) & pids="$pids $!"
done
for p in $pids; do wait $p; done
: > "$O"
for i in $(seq 0 $((N-1))); do cat "$O.part$i" >> "$O" 2>/dev/null; done
SZ=$(stat -c %s "$O" 2>/dev/null || echo 0)
if [ "$SZ" = "$TOT" ]; then echo "✅ 完成 $SZ 字节"; rm -f "$O".part*; else echo "⚠️ $SZ / $TOT（可再跑续传）"; fi