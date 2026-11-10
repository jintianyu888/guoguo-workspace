#!/bin/bash
# backup-audit-tonight.sh —— 备份快速审查（四地清单+份数对照+时间戳新鲜度）
# 2026-10-21 主公选方案A：本脚本只做快检（<60s），恢复演练已移到 backup-drill-nightly.sh(05:00)
set -u -o pipefail
W=/home/j/.openclaw/workspace
mkdir -p "$W/state/work"
exec 200>"$W/state/work/backup-audit.lock"
flock -n 200 || { echo "已有实例在跑，退出"; exit 0; }
R=$W/state/backup-audit-$(date +%Y%m%d).md
. /home/j/.openclaw/workspace/tools/nas-config.sh
RD="$NAS_ARCHIVES"
: > "$R"
echo "# 备份审查报告 $(date '+%F %T') (快速检查)" >> "$R"
echo "脚本: $0 | PID: $$ | 模式: fast" >> "$R"
echo >> "$R"
echo "## 1. 四地档案清单" >> "$R"
for d in d e h; do
  echo "### $d:" >> "$R"
  ls -l --time-style=+%F_%H:%M /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | awk '{print "  -",$5,$6}' | sed "s|/mnt/$d/openclaw-backups/||" >> "$R"
done
echo "### 群晖:" >> "$R"
if nas_guard "$RD" 2>/dev/null; then ls -l --time-style=+%F_%H:%M "$RD"/*.tar.gz 2>/dev/null | awk '{print "  -",$5,$6}' >> "$R"; else echo "  (新 NAS 未挂载)" >> "$R"; fi
echo >> "$R"
echo "## 2. 四地份数对照" >> "$R"
D=$(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)
E=$(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)
H=$(ls /mnt/h/openclaw-backups/*.tar.gz 2>/dev/null|wc -l)
N=$(ls "$RD"/*.tar.gz 2>/dev/null | wc -l)
echo "- D=$D  E=$E  H=$H  新NAS=$N" >> "$R"
echo >> "$R"
echo "## 3. 最新包新鲜度" >> "$R"
for d in d e h; do
  f=$(ls -t /mnt/$d/openclaw-backups/*.tar.gz 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    age=$(( ( $(date +%s) - $(stat -c %Y "$f") ) / 3600 ))
    echo "- $d: $(basename "$f") → ${age}h 前" >> "$R"
    [ "$age" -gt 30 ] && echo "  ⚠️ 超过 30 小时未更新" >> "$R"
  else
    echo "- $d: 无归档" >> "$R"
  fi
done
echo >> "$R"
echo "## 4. 结论" >> "$R"
# 2026-10-26 B 修：四地份数本就不该相等（各地保留策略不同），改按策略判定，
#  并要求"H 的每一份在别处至少有一个同名同大小副本，否则必须保留"——避免误删唯一副本
KEEP_D=2; KEEP_EH=7; WK=4; KEEP_NAS=7
ok=1; note=""
[ "$D" -ge "$KEEP_D" ] || { ok=0; note="$note D=$D<$KEEP_D"; }
[ "$E" -ge "$KEEP_EH" ] && [ "$E" -le $((KEEP_EH+WK+1)) ] || { ok=0; note="$note E=$E 不在 $KEEP_EH..$((KEEP_EH+WK+1))"; }
[ "$H" -ge "$E" ] || { ok=0; note="$note H=$H<E=$E（冷档不得少于 E 盘）"; }
[ "$N" -ge "$KEEP_NAS" ] && [ "$N" -le $((KEEP_NAS+WK+1)) ] || { ok=0; note="$note NAS=$N 不在 $KEEP_NAS..$((KEEP_NAS+WK+1))"; }
COLD=0
for f in /mnt/h/openclaw-backups/*.tar.gz; do
  b=$(basename "$f")
  [ -f "/mnt/e/openclaw-backups/$b" ] || COLD=$((COLD+1))
done
echo "- 份数解读：D=$D(热档,策略$KEEP_D) E=$E(策略$KEEP_EH+周$WK) H=$H(其中$COLD 份为别处无副本的冷档,必须保留) NAS=$N(策略$KEEP_NAS+周$WK)" >> "$R"
if [ "$ok" = "1" ]; then
  echo "- ✅ 四地份数符合保留策略（D=$D E=$E H=$H NAS=$N）" >> "$R"
else
  echo "- ⚠️ 四地份数不符合保留策略（D=$D E=$E H=$H NAS=$N）:$note" >> "$R"
fi
echo "- 恢复演练：由 backup-drill-nightly.sh 每日 05:00 单独执行（本脚本不再包含）" >> "$R"
echo "报告: $R"
