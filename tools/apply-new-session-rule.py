#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply-new-session-rule.py — 把「新会话提醒规则 v1」块幂等注入每个管家工作区的 AGENTS.md

真源：docs/新会话提醒规则-20261101.md
用法：
  python3 tools/apply-new-session-rule.py --dry-run   # 只看会改哪些
  python3 tools/apply-new-session-rule.py             # 实际注入（自动备份 .bak-YYYYMMDD）
"""
import json, os, shutil, subprocess, sys, tempfile
from datetime import datetime

BEGIN = "<!-- NEW-SESSION-RULE:v1 BEGIN"
END = "<!-- /NEW-SESSION-RULE:v1 -->"
MARK = "<!-- NEW-SESSION-RULE:v1"
MCOUNT = "NEW-SESSION-RULE:v1"

BLOCK = """<!-- NEW-SESSION-RULE:v1 BEGIN （自动注入，勿手改；真源 docs/新会话提醒规则-20261101.md） -->
## 新会话提醒（强制 · 主公 2026-11-01 令）
在适当的时候主动提醒主公输入 /new 开新会话，别把旧会话用到冻结。判断：
1. 收到会话体积告警（14k 事件/14MB）或冻结（20k/20MB）→ 立刻提醒。
2. /status 或运行时可查 token ≥ 120k（压缩线 150k 之前）→ 提醒；**查不到数字就用轮次/时长/话题判断，绝不编数**。
3. 语义时机：长任务收尾（跨 5 轮以上）／换到无关话题／同一件事来回 20 轮以上／连续 60 分钟以上／准备开重活前／察觉上下文开始丢细节。
提醒格式：一句话 + 续用建议（新会话第一句），≤3 行，单独成段。
先落盘：提醒前必须把任务 id／当前状态／下一步写进账本或 state，并在提醒里给出位置；没落盘不许建议 /new。
克制：同一会话最多 3 次，两次间隔须同时 ≥15 分钟且 ≥10 轮；主公说「不用/先这样」后本会话不再提；刚 /new 前 5 轮不提；紧急排查中不提。
不适用：cron／心跳／子代理等无人值守会话；单问单答闲聊不提醒。
<!-- /NEW-SESSION-RULE:v1 -->
"""

def workspaces():
    try:
        out = subprocess.run(["openclaw", "agents", "list", "--json"], capture_output=True, text=True, timeout=120).stdout
        data = json.loads(out)
        ws = [a.get("workspace") for a in data if isinstance(a, dict) and a.get("workspace")]
    except Exception as e:
        print("WARN agents list 失败：%s" % e)
        ws = []
    extra = ["/home/j/.openclaw/workspace"]
    for p in extra + ws:
        pass
    seen, res = set(), []
    for p in (extra + ws):
        p = os.path.abspath(os.path.expanduser(p))
        if p in seen:
            continue
        seen.add(p)
        res.append(p)
    return res

def inject(path, dry):
    if not os.path.isfile(path):
        return "NOFILE"
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if not src.strip():
        return "EMPTY-SKIP"
    if MARK in src:
        i = src.index(BEGIN) if BEGIN in src else src.index(MARK)
        j = src.index(END) + len(END)
        new = src[:i] + BLOCK.strip() + src[j:]
        action = "REPLACE"
    else:
        lines = src.split("\n")
        if lines and lines[0].startswith("#"):
            new = lines[0] + "\n\n" + BLOCK + "\n" + "\n".join(lines[1:])
        else:
            new = BLOCK + "\n" + src
        action = "INSERT"
    if dry:
        return action + "(dry)"
    if new == src:
        return "UNCHANGED"
    bak = path + ".bak-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, bak)
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".agents-", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    with open(path, "r", encoding="utf-8") as f:
        check = f.read()
    if len(check) < len(new) - 5 or check.count(MCOUNT) < 2 or check.count("<!-- /NEW-SESSION-RULE:v1 -->") < 1:
        shutil.copy2(bak, path)
        return "VERIFY-FAIL-ROLLBACK"
    return action

def main():
    dry = "--dry-run" in sys.argv
    rows = []
    for ws in workspaces():
        ap = os.path.join(ws, "AGENTS.md")
        rows.append((ws, inject(ap, dry)))
    ok = [r for r in rows if r[1] in ("INSERT", "REPLACE", "UNCHANGED", "INSERT(dry)", "REPLACE(dry)")]
    bad = [r for r in rows if r not in ok]
    for ws, st in rows:
        print("%-10s %s" % (st, ws))
    print("\n合计 %d 个工作区：可写 %d，跳过/异常 %d" % (len(rows), len(ok), len(bad)))
    return 0 if not bad else 1

if __name__ == "__main__":
    sys.exit(main())
