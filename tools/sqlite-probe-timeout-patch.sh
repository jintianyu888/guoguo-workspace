#!/bin/bash
# sqlite-probe-timeout-patch.sh —— 备份 SQLite 头探测超时热补丁（2026-11-06）
# 背景：dist/backup-sqlite-snapshot-*.mjs 用 spawnSync 探测库头，硬编码 timeout:1e4（10s）；
#       备份文件集含 /mnt/e 慢盘时必然超时 → "Could not determine whether backup files are SQLite databases"。
# 改法（双审采纳）：timeout: Number(process.env.OC_SQLITE_PROBE_TIMEOUT_MS ?? 1e4)，默认值不变，可用环境变量放宽。
# 注意：dist 内容改动会被升级前置清单校验拒绝 → 升级前必须 --revert。
set -uo pipefail
D=/home/j/.npm-global/lib/node_modules/openclaw/dist
ACT="${1:-check}"
TARGETS=$(grep -l "timeout: 1e4" "$D"/backup-sqlite-snapshot-*.mjs 2>/dev/null)
PATCHED=$(grep -l "OC_SQLITE_PROBE_TIMEOUT_MS" "$D"/backup-sqlite-snapshot-*.mjs 2>/dev/null)
echo "stock:${TARGETS:-无} patched:${PATCHED:-无}"
case "$ACT" in
  check) [ -n "$PATCHED" ] && { echo "STATUS=patched"; exit 0; }; echo "STATUS=stock"; exit 0;;
  apply)
    [ -n "$PATCHED" ] && { echo "已打过，跳过"; exit 0; }
    [ -z "$TARGETS" ] && { echo "ERR 找不到目标文件"; exit 1; }
    for f in $TARGETS; do
      cp -p "$f" "$f.bak-probe"
      python3 - "$f" <<'PY'
import sys
p=sys.argv[1]; s=open(p,encoding="utf-8").read()
old="timeout: 1e4"; new="timeout: Number(process.env.OC_SQLITE_PROBE_TIMEOUT_MS ?? 1e4)"
assert s.count(old)==1, "命中数不是1，放弃"
s2=s.replace(old,new)
open(p+".new","w",encoding="utf-8").write(s2)
PY
      [ $? -ne 0 ] && { echo "ERR 改写失败 $f"; exit 1; }
      node --input-type=module -e "await import('file://$f.new').then(()=>{}).catch(e=>{if(!/SyntaxError/.test(String(e)))process.exit(0);console.error('SYNTAX',e.message);process.exit(3)})" 2>/dev/null
      mv -f "$f.new" "$f" && echo "已打补丁: $(basename "$f")"
    done
    grep -c "OC_SQLITE_PROBE_TIMEOUT_MS" "$D"/backup-sqlite-snapshot-*.mjs 2>/dev/null | paste -sd' ' -; exit 0;;
  revert)
    n=0
    for b in "$D"/backup-sqlite-snapshot-*.mjs.bak-probe; do
      [ -f "$b" ] || continue
      f="${b%.bak-probe}"; mv -f "$b" "$f"; n=$((n+1)); echo "已还原: $(basename "$f")"
    done
    [ "$n" = 0 ] && echo "无 .bak-probe，已是原版"
    grep -c "timeout: 1e4" "$D"/backup-sqlite-snapshot-*.mjs 2>/dev/null | paste -sd' ' -; exit 0;;
  *) echo "用法: $0 check|apply|revert"; exit 2;;
esac
