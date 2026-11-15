#!/usr/bin/env python3
"""五大管家常用信息卡生成（零 token）"""
import json, os, glob, datetime

WS = "/home/j/.openclaw/workspace"
NOW = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
BUTLERS = [
    ("maint", "维护管家", "/home/j/openclaw-workspaces/maint", "系统/磁盘/备份巡检，只读只出建议"),
    ("backup", "备份管家", "/home/j/.openclaw/workspace-backup", "备份链路、NAS 推送、台账"),
    ("model", "模型管家", "/home/j/.openclaw/workspace-model", "模型选型/测评/额度/备用接替"),
    ("work", "干活管家", "/home/j/openclaw-workspaces/work", "通用执行、批量处理"),
    ("sheet-music", "Hermess", "/home/j/openclaw-workspaces/sheet-music", "乐谱、文档、翻译"),
]

def last_artifact(ws):
    files = []
    for pat in ("state/self-review/*.md", "state/reports/*.md"):
        files += glob.glob(os.path.join(ws, pat))
    if not files:
        return None
    f = max(files, key=os.path.getmtime)
    return f, os.path.getsize(f), datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%m-%d %H:%M")

rows = []
for aid, name, ws, duty in BUTLERS:
    a = last_artifact(ws)
    rows.append({"id": aid, "name": name, "duty": duty, "workspace": ws,
                 "last": ({"path": a[0], "size": a[1], "mtime": a[2]} if a else None)})

lines = ["# 五大管家常用信息（" + NOW + " 自动生成）", ""]
for r in rows:
    last = (r["last"]["mtime"] + "（" + str(r["last"]["size"]) + "B）") if r["last"] else "无产出"
    lines.append("- **" + r["name"] + "（" + r["id"] + "）** · " + r["duty"])
    lines.append("  工作区 " + r["workspace"] + " · 最近自审 " + last)
lines += ["", "- 自审节奏：12:40–13:14 各自出报告 → 13:26 汇总 → 13:35 一条合并推送",
          "- 告警只走果果一处：服务挂 / 数据风险 / 安全 / 花钱 / 要你决定"]

os.makedirs(os.path.join(WS, "state/butler"), exist_ok=True)
open(os.path.join(WS, "docs/五大管家常用信息-20261115.md"), "w").write("\n".join(lines) + "\n")
json.dump({"generated": NOW, "butlers": rows},
          open(os.path.join(WS, "state/butler/cards.json"), "w"), ensure_ascii=False, indent=2)
print("\n".join(lines))