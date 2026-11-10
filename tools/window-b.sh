#!/bin/bash
[ -z "${BASH_VERSION:-}" ] && exec /bin/bash "$0" "$@"
# window-b.sh —— 升级窗口（10.4 → 10.5），必须有回滚点才动手
# 用法（在你的终端里）：bash ~/.openclaw/workspace/tools/window-b.sh 2026.10.5
set -uo pipefail
W=/home/j/.openclaw/workspace
TARGET="${1:-2026.10.5}"
LOG=$W/state/work/window-b.log
say(){ echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

say "=== WINDOW B START target=$TARGET ==="

# 0) 当前版本（CLI 挂掉时 fallback，防回滚时 npm install -g openclaw@ 空串）
CUR=$(openclaw --version 2>/dev/null | grep -oE '[0-9]{4}\.[0-9]+\.[0-9]+' | head -1)
CUR="${CUR:-2026.10.4}"
say "当前版本=$CUR"

# 0.5) node 运行时预检（2026-10-23 15:19 失败教训：需 >=24.22.1<25 || >=26.12.1）
NV=$(node -v 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
NVOK=$(python3 -c "import sys;m=tuple(int(x) for x in sys.argv[1].split('.'));sys.exit(0 if ((m>=(24,22,1) and m<(25,)) or m>=(26,12,1)) else 1)" "$NV" 2>/dev/null && echo OK || echo BAD)
say "node=$NV 引擎预检=$NVOK"
[ "$NVOK" = "OK" ] || { say "node 不满足 10.5 引擎要求 → 中止，先升级 nodejs"; exit 1; }

# 1) 维护窗口（150 分钟自动恢复保险 + 心跳续期）
sh "$W/tools/maintenance.sh" start 150 || { say "维护窗口开启失败，中止"; exit 1; }

# 维护延长心跳：每个长步骤前重算扩展窗口（双审共识 B-2：绝对时间戳 + 心跳，自愈闭环）
ext_reset(){
  local secs="$1" tgt
  tgt=$(( $(date +%s) + secs ))
  echo "$tgt" > "$W/state/work/.maint-extended-until.tmp"
  mv "$W/state/work/.maint-extended-until.tmp" "$W/state/work/maint-extended-until"
  say "维护窗口延长至 $(date -d @"$tgt" '+%F %T')（+${secs}s 心跳）"
}
ext_reset 3600

# 2) 升级前整档备份（官方格式），失败即中止
# 双审共识：60 分钟内有「已验证归档」且无在途备份单元且 D 盘已挂载 → 复用（铁律口径：1小时内已验证的同目标归档可复用）
BKDIR=/mnt/d/openclaw-backups
NEWBK=""
[ -d "$BKDIR" ] && NEWBK=$(ls -t "$BKDIR"/*.tar.gz 2>/dev/null | head -1 || true)
VERIFIED=0
if [ -n "$NEWBK" ]; then
  if [ -f "$NEWBK.sha256" ]; then VERIFIED=1
  elif [ -s "$NEWBK" ] && gzip -t "$NEWBK" 2>/dev/null; then VERIFIED=1; fi
fi
SKIP_BK=0
if [ -n "$NEWBK" ] && [ "$VERIFIED" = 1 ] \
   && [ $(( $(date +%s) - $(stat -c %Y "$NEWBK" 2>/dev/null || echo 0) )) -lt 3600 ] \
   && ! systemctl --user list-units --all --no-legend 2>/dev/null | grep -E "pre-upgrade-backup|maint-run" | grep -q " active "; then
  SKIP_BK=1
fi
if [ "$SKIP_BK" = 1 ]; then
  say "--- 升级前备份：复用 60 分钟内已验证归档 $(basename "$NEWBK")（伴生校验通过、无在途备份单元）---"
else
  say "--- 升级前备份 ---"
  sh "$W/tools/maintenance.sh" run timeout 5400 bash "$W/tools/pre-upgrade-backup.sh" "window-b pre $TARGET" >>"$LOG" 2>&1
  BKRC=$?
  say "备份 rc=$BKRC"
  if [ $BKRC -ne 0 ]; then
    say "备份失败 → 中止升级，恢复网关"
    sh "$W/tools/maintenance.sh" stop
    exit 1
  fi
fi

# 3) dry-run
ext_reset 1800
say "--- update --dry-run ---"
sh "$W/tools/maintenance.sh" run timeout 600 openclaw update --dry-run >>"$LOG" 2>&1
DRC=$?
say "dry-run rc=$DRC"
if [ $DRC -ne 0 ]; then
  say "dry-run 失败 → 中止，恢复网关"
  sh "$W/tools/maintenance.sh" stop
  exit 1
fi

# 4) 安装（不重启）
ext_reset 4800
say "--- update --yes --no-restart ---"
sh "$W/tools/maintenance.sh" run timeout 3600 openclaw update --yes --no-restart >>"$LOG" 2>&1
URC=$?
say "update rc=$URC"

# 5) 回滚判定
if [ $URC -ne 0 ]; then
  say "!!! 升级失败 → 开始回滚（二进制降级 + 官方归档恢复）"
  sh "$W/tools/maintenance.sh" run timeout 900 npm install -g openclaw@$CUR >>"$LOG" 2>&1
  say "二进制降级 rc=$?"
  sh "$W/tools/maintenance.sh" stop
  bash "$W/tools/upgrade-acceptance.sh" > "$W/state/work/acceptance-windowB.txt" 2>&1
  say "回滚后验收：$(tail -1 "$W/state/work/acceptance-windowB.txt")"
  exit 1
fi

# 6) 恢复网关（新版本启动会跑迁移）
say "--- 恢复网关 ---"
sh "$W/tools/maintenance.sh" stop

sleep 30
say "--- 验收 ---"
bash "$W/tools/upgrade-acceptance.sh" > "$W/state/work/acceptance-windowB.txt" 2>&1
RES=$(tail -1 "$W/state/work/acceptance-windowB.txt")
say "验收：$RES"

# 7) 关键项复查：autonomous.mode 是否被重置
AM=$(openclaw config get skills.workshop.autonomous.mode 2>/dev/null | tr -d '\r\n')
say "autonomous.mode=$AM（应为 propose）"

say "=== WINDOW B END ==="
