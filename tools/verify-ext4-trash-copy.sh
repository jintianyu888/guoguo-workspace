#!/bin/bash
# verify-ext4-trash-copy.sh —— 只读校验：源 vs E 盘副本（文件名+大小+SHA256）
# 幂等、纯读，不改任何东西。
SRC=/home/j/.openclaw-trash/20261019-fast-experiment
DST=/mnt/e/openclaw-store/20261019-fast-experiment
LOG=/home/j/.openclaw/workspace/state/work/ext4-trash-verify.log
say(){ echo "$(date '+%F %T') $*" | tee -a "$LOG"; }
cd "$SRC" || exit 1
fail=0; n=0; big=0
while IFS= read -r -d '' f; do
  rel="${f#$SRC/}"; g="$DST/$rel"; n=$((n+1))
  if [ ! -f "$g" ]; then say "❌ 缺失: $rel"; fail=$((fail+1)); continue; fi
  s1=$(stat -c%s "$f"); s2=$(stat -c%s "$g")
  if [ "$s1" != "$s2" ]; then say "❌ 大小不一致 $rel: $s1 vs $s2"; fail=$((fail+1)); continue; fi
  if [ "$s1" -gt 67108864 ]; then
    big=$((big+1))
    h1=$(sha256sum "$f" | cut -d' ' -f1); h2=$(sha256sum "$g" | cut -d' ' -f1)
    if [ "$h1" != "$h2" ]; then say "❌ SHA256 不一致 $rel: $h1 vs $h2"; fail=$((fail+1)); continue; fi
    say "  ✅ $rel  ${s1}B  sha256=${h1}"
  else
    say "  ✅ $rel  ${s1}B  (小文件，比大小)"
  fi
done < <(find "$SRC" -type f -print0)

sum=$(du -sb "$DST" | awk '{print $1}')
if [ "$fail" -eq 0 ]; then
  say "✅ 全部校验通过：$n 个文件（大文件 SHA256 验证 $big 个），副本 $sum 字节 @ $DST"
  printf '{"ts":%s,"batch":"20261019-fast-experiment","src":"%s","dst":"%s","bytes":%s,"files":%s,"big_sha256_verified":%s,"mismatch":%s,"action":"copy-only-no-delete"}\n' \
    "$(date +%s)" "$SRC" "$DST" "$sum" "$n" "$big" "$fail" >> /mnt/e/openclaw-store/manifest.jsonl
  say "   源未动（删除需主公拍板）"
else
  say "❌ 有 $fail 项不一致，副本不可信"
fi
exit $fail
