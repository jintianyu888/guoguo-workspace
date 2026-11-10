#!/bin/bash
# backup-ext4-trash-batch.sh —— 把 ext4 内的回收站大批次复制到 E 盘备份站（只复制，不删源）
# 背景（2026-10-22）：/home/j/.openclaw-trash/20261019-fast-experiment = 72 GiB
#   - 2×~19.5G tar.zst（fast 实验归档）
#   - 4×~9.2G .openclaw-backup-publish-*/archive.tar.gz.tmp（发布中断残留）
#   - fast-snap/ 2 个 sqlite 快照
#   ⚠️ NAS 回收站无副本、每日备份不含 trash → 唯一副本在此
#   ⚠️ d-junk-clean.sh 的 7 天规则会在 2026-10-26 自动清掉它 → 先落 E 盘备份站
# 本脚本：只 cp -a + 校验（文件名/大小/SHA256），**绝不删源**。删源需主公另行拍板。
set -euo pipefail  # 2026-10-27 审查#12：cp/校验失败即停，避免静默放过
SRC=/home/j/.openclaw-trash/20261019-fast-experiment
DST=/mnt/e/openclaw-store/20261019-fast-experiment
LOG=/home/j/.openclaw/workspace/state/work/ext4-trash-backup.log
LOCK=/home/j/.openclaw/workspace/state/work/ext4-trash-backup.lock
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
exec 9>"$LOCK"; flock -n 9 || { say "已有实例在跑，退出"; exit 0; }
[ -d "$SRC" ] || { say "源不存在: $SRC"; exit 1; }
mkdir -p "$DST"

# 1) 复制（rsync 可断点续传；9p 上不用 --checksum，太慢）
say "开始复制 $SRC -> $DST"
rsync -a --partial --inplace --no-whole-file \
  --exclude='.entered-at' "$SRC"/ "$DST"/ >>"$LOG" 2>&1
rc=$?
say "rsync 结束 rc=$rc"
[ $rc -ne 0 ] && { say "❌ 复制未成功，退出（源未动）"; exit $rc; }

# 2) 三重校验：文件名 + 大小 + SHA256
say "开始三重校验（文件名/大小/SHA256）"
fail=0; n=0
cd "$SRC" || exit 1
while IFS= read -r -d '' f; do
  rel="${f#$SRC/}"
  g="$DST/$rel"
  n=$((n+1))
  if [ ! -f "$g" ]; then say "❌ 缺失: $rel"; fail=$((fail+1)); continue; fi
  s1=$(stat -c%s "$f"); s2=$(stat -c%s "$g")
  if [ "$s1" != "$s2" ]; then
    say "❌ 大小不一致 $rel: $s1 vs $s2"; fail=$((fail+1)); continue
  fi
  # 大文件(>64M)算 SHA256；小文件（.index/.err/.sha256 等）比大小即可
  if [ "$s1" -gt 67108864 ]; then
    h1=$(sha256sum "$f" | cut -d' ' -f1)
    h2=$(sha256sum "$g" | cut -d' ' -f1)
    if [ "$h1" != "$h2" ]; then
      say "❌ SHA256 不一致 $rel: $h1 vs $h2"; fail=$((fail+1)); continue
    fi
    say "  ✅ $rel  ${s1}B  sha256=${h1:0:16}…"
  else
    say "  ✅ $rel  ${s1}B  (小文件，比大小)"
  fi
done < <(find "$SRC" -type f -print0)

# 3) 落台账（manifest.jsonl 一行，便于以后追溯/回滚）
sum=$(du -sb "$DST" | awk '{print $1}')
ts=$(date +%s)
printf '{"ts":%s,"batch":"20261019-fast-experiment","src":"%s","dst":"%s","bytes":%s,"files_checked":%s,"mismatch":%s,"sha256_verified":true,"action":"copy-only-no-delete"}\n' \
  "$ts" "$SRC" "$DST" "$sum" "$n" "$fail" \
  >> /mnt/e/openclaw-store/manifest.jsonl 2>/dev/null || true

if [ "$fail" -eq 0 ]; then
  say "✅ 全部校验通过：$n 个文件，$sum 字节，副本在 $DST"
  say "   源未动（删除需主公拍板）"
else
  say "❌ 有 $fail 项不一致，副本不可信，请人工复核"
fi
exit $fail
