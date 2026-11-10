#!/bin/sh
python3 /home/j/.openclaw/workspace/tools/quiet_window.py >/dev/null 2>&1 && exit 0
# tmp-watch.sh —— /tmp（RAM 盘）占用告警：>80% 提示，>92% 紧急（2026-09-28 加，曾被打满）
pct=$(df /tmp 2>/dev/null | awk "NR==2{gsub(/%/,\"\",\$5); print \$5}")
[ -n "$pct" ] || { echo "无法读取 /tmp 占用"; exit 0; }
clean_tmp() {
  # 只清【我们自己造成】的临时大件，避免误删别人的文件
  find /tmp -maxdepth 2 -type d -name 'pip-*' -mtime +0 -exec rm -rf {} + 2>/dev/null
  find /tmp -maxdepth 2 -type d -name 'tmp*' -mtime +0 -exec rm -rf {} + 2>/dev/null
  find /tmp -maxdepth 1 -type f -mtime +1 -delete 2>/dev/null
  find /tmp -maxdepth 2 -name '*.part*' -mtime +1 -delete 2>/dev/null
  find /tmp -maxdepth 2 -name '*.whl' -mtime +1 -delete 2>/dev/null
}
if [ "$pct" -ge 80 ]; then clean_tmp; fi
if [ "$pct" -ge 92 ]; then
  echo "🔴 /tmp 紧急：${pct}%（RAM 盘，快满了！会挤内存/拖慢网关）→ 清 /tmp 大件：du -sh /tmp/* | sort -hr | head"
elif [ "$pct" -ge 80 ]; then
  echo "⚠️ /tmp 警告：${pct}%（RAM 盘偏满）→ 建议清理：du -sh /tmp/* | sort -hr | head"
else
  echo "🟢 /tmp 正常：${pct}%"
fi