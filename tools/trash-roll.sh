#!/bin/bash
# trash-roll.sh v2 —— 群晖回收站【1 年】滚动检查（2026-09-30 老板令）
# 规则：回收文件都放群晖回收站；保存 1 年；【超期删除必须先问老板】—— 默认只报告，不删
# 用法：bash tools/trash-roll.sh            # 演练+报告（默认，安全）
#       bash tools/trash-roll.sh --apply    # 真删（仅在你明确说删之后用）
[ -n "${BASH_VERSION:-}" ] || { echo "需用 bash 运行: bash $0" >&2; exit 1; }
DAYS=365
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1
NASR=/var/services/homes/guoguonas/trash
NAS=nas
S="ssh -n -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=15"
MODE=演练; [ "$APPLY" = 1 ] && MODE=真删
echo "🗑️ 群晖回收站滚动检查 · 保留 ${DAYS} 天 · 模式 $MODE · $(date '+%F %H:%M')"
cutoff=$(( $(date +%s) - DAYS*86400 ))
n=0; keep=0
LIST=$($S "$NAS" "find '$NASR' -mindepth 1 -maxdepth 2 2>/dev/null" 2>/dev/null | tr -d '\r' | grep -v 'WSL\|ubuntu-20260929.tar' || true)
while IFS= read -r f; do
  [ -z "$f" ] && continue
  mt=$($S "$NAS" "stat -c%Y '$f' 2>/dev/null || echo 0" 2>/dev/null | tr -dc '0-9'); mt=${mt:-0}
  if [ "$mt" -gt 0 ] && [ "$mt" -lt "$cutoff" ]; then
    age=$(( ( $(date +%s) - mt ) / 86400 ))
    echo "  ⏰ 超期 ${age} 天: $(basename "$f")"
    n=$((n+1))
    if [ "$APPLY" = 1 ]; then
      # 2026-10-17 双模型复核加固：删前校验（路径必须在回收站内、非根、无 ..）+ 先记台账
      case "$f" in
        "$NASR"/*) ;;
        *) echo "     ⛔ 跳过：路径不在回收站内 ($f)"; keep=$((keep+1)); continue ;;
      esac
      case "$f" in
        *".."*) echo "     ⛔ 跳过：路径含 .. ($f)"; keep=$((keep+1)); continue ;;
      esac
      if [ "$f" = "$NASR" ] || [ "$f" = "$NASR/" ]; then echo "     ⛔ 跳过：目标是回收站根"; keep=$((keep+1)); continue; fi
      sz=$($S "$NAS" "stat -c%s \"$f\" 2>/dev/null || echo 0" 2>/dev/null | tr -dc "0-9"); sz=${sz:-0}
      echo "$(date +%F\ %T) $f ${sz}B age=${age}d" >> "$W/state/trash-roll-deleted.log" 2>/dev/null || true
      $S "$NAS" "rm -rf \"$f\"" 2>/dev/null && echo "     🗑 已删（已记台账）"
    fi
  else keep=$((keep+1)); fi
done <<< "$LIST"
echo "   → 超期 ${n} 项 · 未到期 ${keep} 项"
[ "$n" = 0 ] && echo "   ✅ 没有超过 ${DAYS} 天的回收项"
[ "$n" -gt 0 ] && [ "$APPLY" = 0 ] && echo "   ⚠️ 超期项【等你确认才删】—— 回复「删回收站超期项」我再用 --apply"
exit 0
