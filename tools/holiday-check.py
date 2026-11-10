#!/usr/bin/env python3
"""节假日日历体检（零 token）。只在「需要人工核对」时输出告警，正常则静默。"""
import datetime, os, re

WS = "/home/openclaw/.openclaw/workspace"
HOL = os.path.join(WS, "state", "holidays.txt")
today = datetime.date.today()
msgs = []

dates = []
if not os.path.exists(HOL):
    msgs.append("⚠️ 节假日日历文件缺失：state/holidays.txt")
else:
    for line in open(HOL, encoding="utf-8"):
        m = re.match(r"^\s*(\d{4}-\d{2}-\d{2})\s*(.*)$", line)
        if m:
            try:
                dates.append((datetime.date.fromisoformat(m.group(1)), m.group(2).strip()))
            except Exception:
                pass

# 12 月：应核对次年官方放假安排
if today.month == 12:
    y = today.year + 1
    n = sum(1 for d, _ in dates if d.year == y)
    if n == 0:
        msgs.append(f"⚠️ 已到 12 月：请核对国务院 {y} 年放假安排并更新 state/holidays.txt（当前 0 天）")
    else:
        msgs.append(f"ℹ️ 12 月提醒：{y} 年节假日已录 {n} 天，请对照官方通知复核")

# 未来 60 天必须有覆盖（避免节前手忙脚乱）
horizon = today + datetime.timedelta(days=60)
upcoming = [(d, n) for d, n in dates if today <= d <= horizon]
if dates and not upcoming:
    msgs.append("⚠️ 未来 60 天节假日日历无条目 —— 可能未覆盖（元旦/春节易漏），请核对")

for m in msgs:
    print(m)
