#!/bin/bash
# upgrade-auto.sh v2.0 (2026-11-17) —— 成熟度驱动的升级「挂载」，由 08:00 窗口执行
# 背景：升级策略要求目标版本发布 >=7 天才装（docs/OpenClaw升级节奏与策略-20261115.md）。
# 设计：本脚本只在 07:30 做判定，判定 upgrade 就写 state/work/.upgrade-armed（含目标版本），
#       由 08:00 的 restart-window 在同一个窗口里执行升级 —— 不额外重启、不撞早间 cron。
# 用法: bash tools/upgrade-auto.sh [--execute]   默认只挂载；--execute 立刻执行升级（人工）
# 环境: OC_UPGRADE_FROM=2026-11-20 OC_UPGRADE_TO=2026-11-30（生效日期窗口）OC_UPGRADE_TARGET=2026.11.5
set -u
export PATH=/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
LOG=$W/state/work/upgrade-auto.log
STAMP=$W/state/work/.upgrade-auto-done
ARM=$W/state/work/.upgrade-armed
EXEC=0; [ "${1:-}" = "--execute" ] && EXEC=1
FROM=${OC_UPGRADE_FROM:-2026-11-20}
TO=${OC_UPGRADE_TO:-2026-11-30}
say(){ printf '%s %s\n' "$(date '+%F %H:%M:%S')" "$*" | tee -a "$LOG"; }
notify(){ timeout 60 bash "$W/tools/notify.sh" "$1" >/dev/null 2>&1 || true; }

say "===== 升级判定开始 exec=$EXEC 窗口 $FROM..$TO ====="
TODAY=$(date +%F)
if [ "$EXEC" = "0" ]; then
  if [ "$TODAY" \< "$FROM" ] || [ "$TODAY" \> "$TO" ]; then say "不在升级窗口内（$TODAY），退出"; exit 0; fi
  if [ -f "$STAMP" ]; then say "已升级过（$(head -1 "$STAMP" 2>/dev/null)），退出"; exit 0; fi
  if [ -f "$ARM" ]; then say "已挂载（$(head -1 "$ARM" 2>/dev/null)），等 08:00 窗口执行"; exit 0; fi
fi

OUT=$(timeout 150 python3 tools/oc-upgrade-check.py --json 2>/dev/null)
# 仅测试用：OC_UPGRADE_TEST_JSON=/path/fake.json
if [ -n "${OC_UPGRADE_TEST_JSON:-}" ] && [ -f "$OC_UPGRADE_TEST_JSON" ]; then OUT=$(cat "$OC_UPGRADE_TEST_JSON"); say "（测试模式：$OC_UPGRADE_TEST_JSON）"; fi
[ -n "$OUT" ] || { say "✗ 取不到升级判定（npm 或脚本异常），今日不动"; [ "$EXEC" = "1" ] && notify "【升级】取不到 npm 版本信息，未升级"; exit 0; }
VERDICT=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("verdict","?"))' 2>/dev/null)
LATEST=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("latest","?"))' 2>/dev/null)
CUR=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("installed","?"))' 2>/dev/null)
AGE=$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(round(float(json.load(sys.stdin).get("latest_age_days",0)),2))' 2>/dev/null)
say "判定=$VERDICT 当前=$CUR 最新=$LATEST 成熟度=${AGE}天"
if [ "$VERDICT" != "upgrade" ]; then say "未达升级条件（$VERDICT），今天不动；08:00 常规重启照常"; exit 0; fi

TGT=${OC_UPGRADE_TARGET:-$LATEST}
say "目标版本 $TGT（成熟度 ${AGE} 天）"

if [ "$EXEC" = "0" ]; then
  # 2026-11-21 主公令：不再自动挂载。只生成提案，等主公批准后由人工 arm。
  PROP=$W/state/work/.upgrade-proposal.json
  printf '{"target":"%s","current":"%s","maturity_days":%s,"at":"%s","approved_by":null}\n' \
    "$TGT" "$CUR" "$AGE" "$(date '+%F %T')" > "$PROP"
  say "已生成升级提案 $PROP（未挂载，等主公批准）"
  notify "【升级待批】OpenClaw $CUR → $TGT（已发布 ${AGE} 天）。回复【批准升级 $TGT】我才会执行；不批就不动。"
  exit 0
fi

bash "$W/tools/upgrade-openclaw.sh" --version="$TGT" >> "$LOG" 2>&1
RC=$?
if [ "$RC" = "0" ]; then
  NOWV=$(timeout 120 openclaw --version 2>/dev/null | tail -1 | awk '{print $2}')
  printf '%s\n' "$(date +%F) $NOWV" > "$STAMP"
  rm -f "$ARM"
  say "升级完成 rc=0 版本=$NOWV"
else
  say "✗ 升级失败 rc=$RC（脚本内含自动回滚）"
fi
exit 0
