#!/bin/bash
# 2026-11-10 告警修复：重做 2026-11-10 归档的 X 盘复制 + NAS 推送（原复制中途失败）
export PATH=/usr/local/bin:/usr/bin:/bin
set -u
L=/home/j/.openclaw/workspace/state/work/archive-resume-20261110.log
B=2026-11-10T01-01-55.465+08-00-openclaw-backup.tar.gz
S=117070992806
SRC=/home/j/backup-stage/$B
X=/mnt/x/openclaw-backups
N=/mnt/nas/archive/jinyu/openclaw-archives
say(){ echo "$(date '+%F %T') $*" >> "$L"; }
[ -f "$SRC" ] || { say "源不存在，退出"; exit 1; }
say "开始：源 $(stat -c%s "$SRC") 字节"
mkdir -p "$X" "$N"
if [ -f "$X/$B.part" ]; then mv -f "$X/$B.part" "$X/$B.part.bad-20261110"; say "旧 .part(68488790016) 改名 .part.bad-20261110"; fi
if [ ! -f "$X/$B" ]; then
  cp -f "$SRC" "$X/$B.part" && mv -f "$X/$B.part" "$X/$B" || { say "X 复制失败"; exit 1; }
  XS=$(stat -c%s "$X/$B" 2>/dev/null || echo 0)
  [ "$XS" = "$S" ] || { say "X 大小不符 $XS"; exit 1; }
  say "已落 X: $B ($XS)"
else
  say "X 已有同名归档，跳过"
fi
if [ ! -f "$N/$B" ]; then
  cp -f "$X/$B" "$N/$B.part" && mv -f "$N/$B.part" "$N/$B" || { say "推 NAS 失败"; exit 1; }
  RS=$(stat -c%s "$N/$B" 2>/dev/null || echo 0)
  [ "$RS" = "$S" ] || { say "NAS 大小不符 $RS"; exit 1; }
  say "已推 NAS: $B ($RS)"
else
  say "NAS 已有同名归档，跳过"
fi
say "完成"
