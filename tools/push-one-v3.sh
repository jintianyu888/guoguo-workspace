#!/bin/bash
# push-one.sh v3 —— 单实例推送一份归档到「新群晖」CIFS 挂载点（2026-11-02 老 NAS 退役改造）
# 变更点：ssh 推送改为本地 CIFS 写（新 NAS 未开 SSH）。
# 双审要点已落实（2026-11-02 20:44 zhipu+minimax，两家均判"需修改"）：
#   1) cp 后先 sync 落盘再复读校验，避免命中本地 page cache 造成假成功
#   2) sidecar 写入同样 sync + 校验，写失败不得记成功
#   3) 空间余量由 1GiB 提到 5GiB；df 解析改用 -Pk 稳定格式
set -uo pipefail
SRC=/mnt/d/openclaw-backups
DST=/mnt/nas/archive/jinyu/openclaw-archives
WS=/home/j/.openclaw/workspace
LOG=$WS/state/work/nas-push.log
MARGIN_KB=$((5*1024*1024))   # 5GiB 余量
mkdir -p "$WS/state/work"
say(){ printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }

N=${1:?用法: push-one.sh <文件名>}
F="$SRC/$N"
[ -f "$F" ] || { say "源不存在 $F"; exit 2; }

# 目标挂载健康检查（CIFS 掉挂时写目录会假成功，必须先探测可写）
[ -d "$DST" ] || { say "❌ 目标目录不存在 $DST"; exit 7; }
PROBE="$DST/.write-probe.$$"
if ! ( : > "$PROBE" ) 2>/dev/null; then say "❌ 目标不可写（挂载掉线？）$DST"; exit 7; fi
rm -f "$PROBE" 2>/dev/null

exec 9>"$WS/state/work/nas-push.lock"; flock -n 9 || { say "已有推送在跑，跳过 $N"; exit 0; }

SZ=$(stat -c%s "$F")
H=$(sha256sum "$F" | awk '{print $1}')

# 远端已一致（sidecar 哈希 + 大小）→ 跳过
if [ -f "$DST/$N" ]; then
  RH=$(awk '{print $1}' "$DST/$N.sha256" 2>/dev/null)
  RS=$(stat -c%s "$DST/$N" 2>/dev/null)
  if [ "${RH:-}" = "$H" ] && [ "${RS:-0}" = "$SZ" ]; then say "⏩ 远端已一致，跳过 $N"; exit 0; fi
fi

# 空间预检
AV=$(df -Pk "$DST" 2>/dev/null | awk 'NR==2{print $4}')
case "${AV:-}" in ''|*[!0-9]*) say "❌ 取目标可用空间失败"; exit 3;; esac
if [ "$AV" -le $((SZ/1024+MARGIN_KB)) ]; then
  say "❌ 新群晖空间不足 可用 ${AV}KB 需要 $((SZ/1024+MARGIN_KB))KB"; exit 3
fi

say "=== 推送 $N ($SZ 字节) → 新NAS ==="
if ! cp --sparse=always "$F" "$DST/$N.part"; then say "❌ 复制失败 $N"; rm -f "$DST/$N.part"; exit 4; fi
# 关键：先把脏页刷到 NAS，再复读校验（否则哈希读的是本机缓存，等于自证）
sync "$DST/$N.part" 2>/dev/null || sync
LSZ=$(stat -c%s "$DST/$N.part" 2>/dev/null)
LH=$(sha256sum "$DST/$N.part" 2>/dev/null | awk '{print $1}')
if [ "$LH" = "$H" ] && [ "$LSZ" = "$SZ" ]; then
  mv -f "$DST/$N.part" "$DST/$N" || { say "❌ 改名失败（保留 .part）"; exit 5; }
  printf '%s  %s\n' "$H" "$N" > "$DST/$N.sha256.tmp" || { say "❌ sidecar 写入失败 $N"; exit 6; }
  sync "$DST/$N.sha256.tmp" 2>/dev/null || sync
  if [ "$(awk '{print $1}' "$DST/$N.sha256.tmp" 2>/dev/null)" = "$H" ]; then
    mv -f "$DST/$N.sha256.tmp" "$DST/$N.sha256"
  else
    say "❌ sidecar 复读不符 $N"; exit 6
  fi
  sync "$DST" 2>/dev/null || true
  say "✅ 校验一致已落位 $N"
else
  say "❌ 校验不符 本地=$H/$SZ 目标=${LH:-空}/${LSZ:-空}（保留 .part）"; exit 6
fi
