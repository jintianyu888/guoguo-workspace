#!/bin/bash
# wsl-image-adopt.sh -- 采纳已存在的 WSL 导出 tar（今天 12:22 那次完整导出），做完整性扫描、改名、入账、同步到 H
# 用法: wsl-image-adopt.sh <tar路径> [正式名，如 ubuntu-20261114.tar]
# 验收: 末尾打印 ADOPT_OK 且 rc=0；任何一步失败打印 ADOPT_FAIL 并 rc!=0
set -u
W=/home/j/.openclaw/workspace
LOG=$W/state/work/wsl-image.log
E=/mnt/e/wsl-backup
SRC=${1:?用法: wsl-image-adopt.sh <tar路径> [正式名]}
NAME=${2:-ubuntu-$(date +%Y%m%d).tar}
DST="$E/$NAME"
log() { echo "[$(date '+%F %T')] [adopt] $*" >> "$LOG"; echo "$*"; }
fail() { log "ADOPT_FAIL $*"; bash "$W/tools/notify.sh" "❌ WSL 镜像采纳失败" "$*（详见 state/work/wsl-image.log）" >/dev/null 2>&1; exit 1; }

[ -f "$SRC" ] || fail "源文件不存在 $SRC"
sz=$(stat -c %s "$SRC") || fail "取大小失败"
log "源 $SRC ${sz}B -> $DST"
[ "$sz" -gt 50000000000 ] || fail "源过小 ${sz}B，不像整机镜像"

# 1) 结构完整性：整包扫一遍，能读到结尾才算没被截断
log "步骤1 tar 完整性扫描（读完 ${sz}B，耗时长）"
if tar -tf "$SRC" > /dev/null 2> "$W/state/work/wsl-image-adopt-tar.err"; then
  log "✅ tar 扫描通过（无截断）"
else
  tail -3 "$W/state/work/wsl-image-adopt-tar.err" >> "$LOG"
  fail "tar 扫描失败，疑似截断"
fi

# 2) 改名为正式镜像
if [ "$SRC" != "$DST" ]; then mv -f "$SRC" "$DST" || fail "改名失败"; fi
log "✅ 已就位 $DST"

# 3) 计算 sha256 入账（E 侧）
h=$(sha256sum "$DST" | cut -d' ' -f1) || fail "sha256 失败"
log "✅ sha256 $h"
printf '{"ts":"%s","image":"%s","size":%s,"sha256":"%s","via":"adopt-probe-export"}\n' \
  "$(date -Iseconds)" "$NAME" "$sz" "$h" >> "$E/manifest.jsonl"

# 4) 同步到 H（robocopy 补齐），再复核 E/H 首尾签名一致
log "步骤2 同步到 H"
bash "$W/tools/wsl-image-sync.sh" --apply >> "$LOG" 2>&1 || log "⚠ sync --apply rc=$?"
bash "$W/tools/wsl-image-sync.sh" --check >> "$LOG" 2>&1
if tail -5 "$W/state/work/wsl-image-sync.log" | grep -q "✅ 一致 $NAME"; then
  log "✅ E/H 一致（首尾 1MB md5 + 大小）"
else
  fail "E/H 复核未通过，见 wsl-image-sync.log"
fi

log "ADOPT_OK $NAME ${sz}B"
bash "$W/tools/notify.sh" "✅ WSL 整机镜像 11 月档已落地" "$NAME（${sz} 字节），E/H 双份已校验" >/dev/null 2>&1
exit 0
