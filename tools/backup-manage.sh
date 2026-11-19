#!/bin/bash
# 备份统一管理：盘点 + 保留策略 + 临时清理（默认 dry-run；--apply 才真删）
set -uo pipefail
APPLY=0; [ "${1:-}" = "--apply" ] && APPLY=1
if [ "$APPLY" = 1 ]; then MODE=执行; else MODE=演练; fi
NAS=nas; SSH='ssh -o BatchMode=yes -o ConnectTimeout=15'
F='WARNING|post-quantum|vulnerable|upgraded|openssh.com'
# 保留份数唯一来源：tools/retention.env（2026-10-18 统一）
RET_ENV=/home/j/.openclaw/workspace/tools/retention.env
[ -f "$RET_ENV" ] && . "$RET_ENV"
KEEP_L=${KEEP_L:-0}
KEEP_D=${KEEP_D:-2}
# —— 参数校验（防误删）：非正整数一律回落安全默认 ——
_ck() { v=$(eval "echo \${$1:-}"); case "$v" in ''|*[!0-9]*) echo "WARN $1 非法('$v')，回落默认 $2" >&2; eval "$1=$2";; *) [ "$v" -ge 1 ] || { echo "WARN $1<1，回落默认 $2" >&2; eval "$1=$2"; };; esac; }
_ck KEEP_D 2; _ck KEEP_EH 7; _ck KEEP_L 0; _ck KEEP_NAS 5
echo "🧰 备份统一管理 · $(date +%Y-%m-%dT%H:%M) · 模式 $MODE"
ARCH_CNT=$(timeout 60 $SSH "$NAS" "ls -1 ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null" 2>/dev/null | grep -cvE "$F")
ARCH_SZ=$(timeout 30 $SSH "$NAS" "du -sh ~/archive/jinyu/openclaw-archives 2>/dev/null | cut -f1" 2>/dev/null | grep -vE "$F" | tr -d " \r")
L1=$(timeout 30 $SSH "$NAS" "cd openclaw-repos/openclaw-backup-repo.git && git log -1 --format=%cd --date=format:%Y-%m-%d_%H:%M 2>/dev/null" 2>/dev/null | grep -vE "$F" | tr -d " \r")
WS=$(timeout 60 $SSH "$NAS" "ls -d ~/archive/jinyu/migrated-20261102/ws-*.git 2>/dev/null | wc -l" 2>/dev/null | grep -vE "$F" | tr -cd 0-9)
OLDL=$(timeout 60 $SSH "$NAS" "du -sh ~/archive/jinyu/migrated-20261102/openclaw-repos 2>/dev/null | cut -f1" 2>/dev/null | grep -vE "$F" | tr -d " \r")
TMP=$(timeout 60 $SSH "$NAS" "ls -d ~/restore-* 2>/dev/null" 2>/dev/null | grep -vE "$F")
LOC=$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null | wc -l)
LOCSZ=$(du -sh /mnt/d/openclaw-backups 2>/dev/null | cut -f1)
echo "【一】全量归档 · 群晖：${ARCH_CNT} 份 / ${ARCH_SZ}（保留：最近 ${KEEP_NAS} 份 + 每月 1 份）"
echo "【二】近实时数据库 · 群晖 openclaw-repos/openclaw-backup-repo.git：最后提交 ${L1:-?}（每 4h）"
echo "【三】工作区镜像 · 群晖 ${WS} 个 ws-*.git；旧结构 openclaw-repos/ ${OLDL:-?}"
echo "【四】D盘归档 · /mnt/d/openclaw-backups：${LOC} 份 / ${LOCSZ:-?}"
if [ -n "$TMP" ]; then
  echo "【五】临时垃圾：$(printf "%s" "$TMP" | tr "\n" " ")"
  if [ "$APPLY" = 1 ]; then
    # 2026-10-27 审查#13：先确认远端确实有 restore-*，再删；超时 120s→600s，stderr 不吞（半删可查）
    if $SSH "$NAS" "ls -d ~/restore-* 2>/dev/null" | grep -q .; then
      timeout 600 $SSH "$NAS" "rm -rf ~/restore-*" 2>&1 && echo "  → 已清理"
    else
      echo "  → 远端无 restore-* 临时目录，跳过"
    fi
  fi
else echo "【五】临时垃圾：✅ 无"; fi
# —— 保留策略轮转（最近 N 份 + 每日/每周/每月 各 1 份）——
PRUNE=/home/j/.openclaw/workspace/tools/backup-prune.py
if [ "$APPLY" = 1 ]; then
  echo "【六】保留轮转（执行）"
  # 2026-10-19 统一：/home/j/Backups 与旧 openclaw-backup/archives 已废弃；D=2 保留由 04:45 归档哈希+保留任务统一执行
else
  echo "【六】保留轮转（演练，加 --apply 才真删）"
  # （演练分支同上，已废弃本地 prune）
fi
echo "【结论】四层结构：①全量归档 ②近实时库 ③工作区镜像 ④本地副本；清理只动临时产物。"
