#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""third-eye.py v1.0 — 第三视角验收（2026-11-24 主公令）
原则：自己说完成不算，必须由"非执行者"复核：
  machine  —— 独立进程复跑命令，记录 rc/输出哈希（防虚假完成）
  model    —— 换一家厂商的模型审证据链（防自说自话）
  human    —— 主公抽检（等主公类）
用法：
  third-eye.py record --task <no|delivery-id> --cmd "<命令>"
  third-eye.py review --task <id> --text "<交付说明或文件路径>" [--provider glm|qwen]
  third-eye.py status --task <id>
  third-eye.py list [--days 7]
"""
import hashlib, json, os, subprocess, sys, time, argparse

W = "/home/j/.openclaw/workspace"
LOG = os.path.join(W, "state/verify/third-eye.jsonl")


def append(rec):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + chr(10))


def cmd_record(a):
    t = time.time()
    p = subprocess.run(a.cmd, shell=True, capture_output=True, text=True, timeout=600)
    out = (p.stdout or "") + (p.stderr or "")
    rec = {"ts": time.strftime("%F %T"), "task": a.task, "kind": "machine",
           "cmd": a.cmd, "rc": p.returncode, "ms": int((time.time() - t) * 1000),
           "sha256": hashlib.sha256(out.encode()).hexdigest()[:16],
           "tail": out.strip().splitlines()[-4:]}
    append(rec)
    print("machine 验收 %s rc=%s %sms sha=%s" % (a.task, p.returncode, rec["ms"], rec["sha256"]))
    for l in rec["tail"]:
        print("   ", l[:160])
    return 0 if p.returncode == 0 else 1


def cmd_review(a):
    text = a.text
    if os.path.exists(text):
        text = open(text, encoding="utf-8").read()[:6000]
    prompt = ("你是独立验收人，不参与该任务执行。请判断下面的'完成声明+证据'是否真实可核验。"
              "只输出 JSON：{\"verdict\":\"通过|驳回\",\"reasons\":[\"...\"],\"missing\":[\"...\"]}。"
              "规则：只写'已完成'而没有可复跑命令/产物路径/数字的，一律驳回；含糊、顺延、'应该没问题'一律驳回。\n\n"
              "声明与证据：\n" + text)
    out = subprocess.run([sys.executable, os.path.join(W, "tools/advice-ask.py"),
                          "--plan", "-", "--advisor", a.provider, "--goal", "第三视角验收"],
                         input=prompt, capture_output=True, text=True, timeout=180)
    body = (out.stdout or "").strip()
    verdict = "驳回"
    if "通过" in body and "驳回" not in body[:40]:
        verdict = "通过"
    rec = {"ts": time.strftime("%F %T"), "task": a.task, "kind": "model",
           "provider": a.provider, "verdict": verdict, "raw": body[-1200:]}
    append(rec)
    print("model 验收 %s provider=%s verdict=%s" % (a.task, a.provider, verdict))
    print(body[:600])
    return 0 if verdict == "通过" else 1


def load(task=None, days=None):
    if not os.path.exists(LOG):
        return []
    rows = [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    if task:
        rows = [r for r in rows if str(r.get("task")) == str(task)]
    if days:
        cut = time.strftime("%F", time.localtime(time.time() - days * 86400))
        rows = [r for r in rows if r["ts"][:10] >= cut]
    return rows


def cmd_ack(a):
    rec={"ts":time.strftime("%F %T"),"task":a.task,"kind":"human","by":a.by,"note":a.note,"verdict":"通过"}
    append(rec); print("human 验收 %s by=%s"%(a.task,a.by)); return 0

def cmd_status(a):
    rows = load(a.task)
    if not rows:
        print("无第三视角记录：%s" % a.task); return 1
    for r in rows:
        print("%s %-8s %s %s" % (r["ts"], r["kind"], r.get("verdict") or ("rc=%s" % r.get("rc")), r.get("cmd", "")[:70]))
    return 0


def cmd_list(a):
    rows = load(days=a.days)
    print("近 %s 天第三视角记录 %d 条" % (a.days, len(rows)))
    for r in rows[-15:]:
        print("  %s %-8s %-10s %s" % (r["ts"], r["kind"], r.get("task"), (r.get("verdict") or "rc=%s" % r.get("rc"))))
    return 0


p = argparse.ArgumentParser()
s = p.add_subparsers(dest="cmd", required=True)
a1 = s.add_parser("record"); a1.add_argument("--task", required=True); a1.add_argument("--cmd", required=True); a1.set_defaults(fn=cmd_record)
a2 = s.add_parser("review"); a2.add_argument("--task", required=True); a2.add_argument("--text", required=True); a2.add_argument("--provider", default="glm"); a2.set_defaults(fn=cmd_review)
a5 = s.add_parser("ack"); a5.add_argument("--task", required=True); a5.add_argument("--by", default="owner"); a5.add_argument("--note", default=""); a5.set_defaults(fn=cmd_ack)
a3 = s.add_parser("status"); a3.add_argument("--task", required=True); a3.set_defaults(fn=cmd_status)
a4 = s.add_parser("list"); a4.add_argument("--days", type=int, default=7); a4.set_defaults(fn=cmd_list)
x = p.parse_args()
sys.exit(x.fn(x))
