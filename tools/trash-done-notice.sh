#!/bin/bash
# 回收站搬运完成通告（一次性；有结果才说话，其余时候静默）
W=/home/j/.openclaw/workspace
D=$W/state/trash-to-nas.done
[ -f "$D" ] || exit 0
RS=$(awk '{print $2}' "$D" 2>/dev/null)
echo "✅ 果果回收站 · 22G 搬运完成"
echo "· 远端 tgz：${RS} 字节"
echo "· D 盘：$(df -h /mnt/d 2>/dev/null | tail -n1 | awk '{print $3" used, "$4" free ("$5")"}')"
echo "· 本地 items 已清空、软链保留"
mv "$D" "$D.announced" 2>/dev/null
