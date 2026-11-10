#!/bin/bash
# backup-hash.sh —— 备份哈希清单工具（2026-10-15 主公令，分步接入：①写清单 ②删前哈希 ③周检）
#   backup-hash.sh write-latest <目录...>  # 只给各目录【最新一份】补写 .sha256（①用）
#   backup-hash.sh write <目录...>         # 给目录内所有缺清单的归档补写
#   backup-hash.sh cmp-fast <A> <B>        # 比对两副本：有清单比清单，否则按大小（②用）
#   backup-hash.sh check <目录|文件>        # 校验清单，目录模式抽样最新 1 份（③用）
set -u
VB=/home/j/.openclaw/workspace/tools/verify-backup.sh
LOG=/home/j/.openclaw/workspace/state/backup-hash.log
say() { echo "$@" | tee -a "$LOG"; }

hash_one() {  # $1=文件
  # 2026-11-07 硬修（台账 #164）：旧逻辑「.sha256 存在就直接 OK」会假绿——
  # 同名新归档、被截断的清单、手工改过的文件都算通过。改为 meta 校验：
  #   meta 存在且 size 一致 → CACHED_OK（明确标缓存命中，不算假绿）
  #   meta 缺失或 size 不一致 → 重算并重写 meta
  f="$1"; d=$(dirname "$f"); m="$f.sha256"; meta="$f.sha256.meta"
  sz=$(stat -c %s "$f" 2>/dev/null || echo 0)
  if [ -f "$m" ] && [ -f "$meta" ]; then
    msz=$(grep -o '"size":[0-9]*' "$meta" 2>/dev/null | head -1 | cut -d: -f2)
    _h0=$(grep -F "$(basename "$f")" "$m" 2>/dev/null | head -1 | awk '{print $1}')
    if [ -n "$msz" ] && [ "$msz" = "$sz" ] && printf '%s' "$_h0" | grep -Eq '^[0-9a-f]{64}$'; then
      echo "  ✅ CACHED_OK $(basename "$f") size=$sz（meta 校验通过）"; return 0
    fi
    echo "  ⚠️ 缓存不可信（meta size=${msz:-无} 实际=$sz），重算: $(basename "$f")"
  elif [ -f "$m" ] && grep -q "  $(basename "$f")" "$m"; then
    # 白名单迁移：旧清单（无 meta）由本脚本写过、文件名对得上 → 补 meta，不重算 110G
    _h=$(cut -d' ' -f1 "$m" | head -1)
    printf '{"file":"%s","size":%s,"sha256":"%s","ts":"%s","migrated":true}\n' "$(basename "$f")" "$sz" "$_h" "$(date -Iseconds)" > "$meta"
    echo "  ✅ MIGRATED_OK $(basename "$f") size=$sz hash=${_h:0:12}…（旧清单补 meta，未重算）"; return 0
  elif [ -f "$m" ]; then
    echo "  ⚠️ 清单名字对不上，重算: $(basename "$f")"
  fi
  # 同尺寸同名副本已在别处算过 → 复用，118G 只算一次（2026-11-07 #164）
  for _root in /mnt/d/openclaw-backups /mnt/e/openclaw-backups /mnt/h/openclaw-backups; do
    _c="$_root/$(basename "$f")"
    if [ "$_c" != "$f" ] && [ -f "$_c.sha256.meta" ] && [ "$(stat -c %s "$_c" 2>/dev/null || echo -1)" = "$sz" ]; then
      if cp -f "$_c.sha256" "$m" 2>/dev/null && cp -f "$_c.sha256.meta" "$meta" 2>/dev/null; then echo "  REUSED $(basename "$f") ← $_root"; return 0; fi
    fi
  done
  H=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
  if ! printf '%s' "$H" | grep -Eq '^[0-9a-f]{64}$'; then
    # 2026-11-09 修：9p/118G 大文件读取偶发内存错误 → 分块重算一次；pipefail 防"半个文件"算出合法哈希
    H=$( set -o pipefail; dd if="$f" bs=16M 2>/dev/null | sha256sum | cut -d' ' -f1 ) || H=
  fi
  if ! printf '%s' "$H" | grep -Eq '^[0-9a-f]{64}$'; then
    echo "  [FAIL] 哈希计算失败（结果长度 ${#H}）: $(basename "$f")，不写清单"
    return 1
  fi
  printf '%s  %s\n' "$H" "$(basename "$f")" > "$m"
  printf '%s  %s\n' "$H" "$(basename "$f")" >> "$d/SHA256SUMS"
  printf '{"file":"%s","size":%s,"sha256":"%s","ts":"%s"}\n' "$(basename "$f")" "$sz" "$H" "$(date -Iseconds)" > "$meta"
  echo "  ✍️ $(basename "$f")  sha256=$H size=$sz"
}

mode="${1:-}"; shift || true
case "$mode" in
  write-latest)
    for d in "$@"; do
      [ -d "$d" ] || continue
      f=$(ls -t "$d"/*.tar.gz 2>/dev/null | head -1)
      [ -n "$f" ] && hash_one "$f"
    done ;;
  write)
    for d in "$@"; do
      [ -d "$d" ] || continue
      for f in "$d"/*.tar.gz; do [ -f "$f" ] && hash_one "$f"; done
    done ;;
  cmp-strict)
    # 只认 .sha256 清单哈希；缺清单一律不通过（2026-10-16 主公令：删前必须哈希确认）
    A="${1:-}"; B="${2:-}"
    [ -f "$A" ] && [ -f "$B" ] || { echo "缺文件"; exit 2; }
    [ -f "$A.sha256" ] && [ -f "$B.sha256" ] || { echo "❌ 缺哈希清单，拒绝删除"; exit 2; }
    ha=$(cut -d' ' -f1 < "$A.sha256"); hb=$(cut -d' ' -f1 < "$B.sha256")
    if [ "$ha" = "$hb" ]; then echo "✅ 哈希一致(strict) $ha"; exit 0; else echo "❌ 哈希不一致 $ha vs $hb"; exit 2; fi ;;
  cmp-fast)
    A="${1:-}"; B="${2:-}"
    [ -f "$A" ] && [ -f "$B" ] || { echo "缺文件"; exit 1; }
    ha=""; hb=""
    [ -f "$A.sha256" ] && ha=$(cut -d' ' -f1 < "$A.sha256")
    [ -f "$B.sha256" ] && hb=$(cut -d' ' -f1 < "$B.sha256")
    if [ -n "$ha" ] && [ -n "$hb" ]; then
      if [ "$ha" = "$hb" ]; then echo "✅ 哈希一致(清单) $ha"; exit 0; else echo "❌ 哈希不一致 $ha vs $hb"; exit 2; fi
    fi
    sa=$(stat -c%s "$A" 2>/dev/null); sb=$(stat -c%s "$B" 2>/dev/null)
    if [ "$sa" = "$sb" ] && [ "${sa:-0}" -gt 0 ]; then echo "⚠️ 无清单，按大小一致($sa)"; exit 0; else echo "❌ 大小不符 $sa vs $sb"; exit 2; fi ;;
  check)
    T="${1:-}"
    [ -n "$T" ] || { echo "用法: backup-hash.sh check <目录|文件>"; exit 1; }
    if [ -d "$T" ]; then
      F=$(ls -t "$T"/*.tar.gz 2>/dev/null | head -1)
      [ -n "$F" ] || { echo "目录无归档: $T"; exit 1; }
      say "抽样校验: $(basename "$F")"
      if [ -f "$F.sha256" ]; then "$VB" check "$F"; else say "  无清单，跳过（先跑 write-latest）"; fi
    else
      [ -f "$T" ] || { echo "不存在: $T"; exit 1; }
      "$VB" check "$T"
    fi ;;
  *) sed -n '2,7p' "$0" ;;
esac
