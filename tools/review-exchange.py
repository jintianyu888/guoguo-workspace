#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""review-exchange.py v1.0 — 管家互审唯一交换口（2026-11-24）
解决：各家自己猜路径（review.md/draft.md）→ 永远读不到 → 每天"顺延"空转。
契约：所有意见只落 state/butler/review/<date>/<target>.md，由审阅方用 submit 写入；
     被审方用 get 取（先取今天的意见，没有则回退到对家自己的自审材料）。
用法：
  review-exchange.py submit --from backup --to maint --text "意见..." [--date 2026-11-24]
  review-exchange.py get --agent backup [--days 2]
  review-exchange.py status
"""
import argparse, datetime, json, os, sys

W = "/home/j/.openclaw/workspace"
ROOT = os.path.join(W, "state/butler/review")
WS = {
    "main": W,
    "maint": "/home/j/openclaw-workspaces/maint",
    "backup": "/home/j/.openclaw/workspace-backup",
    "model": "/home/j/.openclaw/workspace-model",
    "work": "/home/j/openclaw-workspaces/work",
    "hermess": "/home/j/openclaw-workspaces/sheet-music",
    "sheet-music": "/home/j/openclaw-workspaces/sheet-music",
}
PAIRS = {"maint": "backup", "backup": "maint", "model": "work", "work": "model"}


def d(s):
    return datetime.date.fromisoformat(s) if s else datetime.date.today()


def submit(args):
    day = d(args.date).isoformat()
    dpath = os.path.join(ROOT, day)
    os.makedirs(dpath, exist_ok=True)
    target = os.path.join(dpath, args.to + ".md")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    body = (args.text or "").replace("\\n", "\n").strip()
    if not body:
        print("ERR: 意见为空", file=sys.stderr)
        return 2
    with open(target, "a", encoding="utf-8") as f:
        f.write("## 审阅意见 by %s（%s）\n\n%s\n\n" % (args.frm, ts, body))
    print("OK submit -> %s" % target)
    return 0


def get(args):
    today = datetime.date.today()
    for i in range(args.days):
        day = (today - datetime.timedelta(days=i)).isoformat()
        f = os.path.join(ROOT, day, args.agent + ".md")
        if os.path.exists(f):
            print("# 来源：%s（对家意见）" % f)
            print(open(f, encoding="utf-8").read())
            return 0
    # 无意见时，回退给对方最近的自审/报告材料，让审阅有输入
    peer = PAIRS.get(args.agent)
    cands = []
    if peer and peer in WS:
        rep = os.path.join(WS[peer], "state/reports")
        if os.path.isdir(rep):
            fs = sorted([x for x in os.listdir(rep) if x.endswith(".md")], reverse=True)
            cands = [os.path.join(rep, x) for x in fs[:1]]
    if cands:
        print("# 未收到对家审阅意见；下面是对方最近的报告材料（%s），可据此写意见" % cands[0])
        print(open(cands[0], encoding="utf-8").read()[:4000])
        print("\nACTION: 读完后用 submit 给对方写意见，不要只说'顺延'。")
        return 0
    print(json.dumps({"status": "missing", "agent": args.agent, "peer": peer,
                      "hint": "对家未提交意见且无报告；上报果果（main），不要静默顺延"},
                     ensure_ascii=False))
    return 3


def status(_a):
    today = datetime.date.today().isoformat()
    dpath = os.path.join(ROOT, today)
    rows = {}
    for k, v in PAIRS.items():
        rows[k] = {"peer": v, "review_present": os.path.exists(os.path.join(dpath, k + ".md")),
                   "peer_report": os.path.exists(os.path.join(WS.get(v, ""), "state/reports"))}
    print(json.dumps({"date": today, "rows": rows}, ensure_ascii=False, indent=1))
    return 0


p = argparse.ArgumentParser()
sub = p.add_subparsers(dest="cmd", required=True)
s = sub.add_parser("submit"); s.add_argument("--from", dest="frm", required=True)
s.add_argument("--to", required=True); s.add_argument("--text", default="")
s.add_argument("--date", default=""); s.set_defaults(fn=submit)
g = sub.add_parser("get"); g.add_argument("--agent", required=True)
g.add_argument("--days", type=int, default=2); g.set_defaults(fn=get)
st = sub.add_parser("status"); st.set_defaults(fn=status)
a = p.parse_args()
sys.exit(a.fn(a))
