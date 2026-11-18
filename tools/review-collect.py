#!/usr/bin/env python3
"""review-collect.py v1.0 (2026-11-17) —— 对审收票器（零 token）
扫描自己 inbox 里各管家对某主题的回复，抽取结论，算 2/3 票，推飞书，回写 loop.json。
不判断内容质量，只做结构化汇总；质量由果果人工核。
"""
import glob, json, os, re, subprocess, sys, time, datetime

WS = "/home/j/.openclaw/workspace"
INBOX = os.path.join(WS, "inbox")
NOTIFY = os.path.join(WS, "tools/notify.sh")

VERDICTS = [("否决", "reject"), ("须改", "revise"), ("合格", "pass")]

def find_verdict(txt):
    # 只在"结论"附近找，避免正文里出现"合格"字样误判
    m = re.findall(r"(?:4\)|结论[:：]?|判定[:：]?)\s*([^\n]{0,60})", txt)
    cand = " ".join(m) if m else txt[-600:]
    for kw, code in VERDICTS:
        if kw in cand:
            return code
    for kw, code in VERDICTS:
        if kw in txt:
            return code
    return None

def main():
    changed = 0
    reports = []
    for loop_path in glob.glob(os.path.join(WS, "state/review/*/loop.json")):
        loop = json.load(open(loop_path, encoding="utf-8"))
        if loop.get("closed"):
            continue
        created = loop.get("created", "2000-01-01 00:00")
        try:
            ct = datetime.datetime.strptime(created, "%Y-%m-%d %H:%M")
        except Exception:
            ct = datetime.datetime.now() - datetime.timedelta(days=3)
        topic_words = [w for w in re.split(r"[-_\s]", loop.get("topic", "")) if len(w) > 3]
        votes = loop.get("votes") or {}
        for seat in loop.get("seats", []):
            sid = seat["id"]
            if sid in votes:
                continue
            cands = sorted(glob.glob(os.path.join(INBOX, "*-%s.md" % sid)), reverse=True)
            for p in cands[:6]:
                if os.path.getmtime(p) < ct.timestamp():
                    continue
                txt = open(p, encoding="utf-8", errors="replace").read()
                if "模型分配" not in txt and not all(w in txt for w in topic_words[:1]):
                    continue
                v = find_verdict(txt)
                if not v:
                    continue
                votes[sid] = {"verdict": v, "role": seat.get("role", "voting"),
                              "file": os.path.basename(p), "at": datetime.datetime.now().strftime("%F %T"),
                              "excerpt": re.sub(r"\s+", " ", txt)[:300]}
                changed += 1
                break
        loop["votes"] = votes
        voting = [s["id"] for s in loop.get("seats", []) if s.get("role", "voting").startswith("voting")]
        got = {k: v["verdict"] for k, v in votes.items() if k in voting}
        npass = sum(1 for v in got.values() if v == "pass")
        nrej = sum(1 for v in got.values() if v == "reject")
        nrev = sum(1 for v in got.values() if v == "revise")
        need = (len(voting) // 2) + 1
        state = "pending"
        if nrej >= 1:
            state = "blocked"
        elif npass >= need:
            state = "passed"
        elif len(got) == len(voting):
            state = "needs_owner"
        loop["tally"] = {"voting_seats": voting, "got": got, "need": need,
                         "pass": npass, "revise": nrev, "reject": nrej, "state": state}
        json.dump(loop, open(loop_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        # 卡住检测：投放超过 12h 仍无人读票 -> 只提醒一次
        age_h = (datetime.datetime.now() - ct).total_seconds() / 3600.0
        if not got and age_h >= 12 and not loop.get("stuck_notified"):
            loop["stuck_notified"] = datetime.datetime.now().strftime("%F %T")
            json.dump(loop, open(loop_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            head = "【对审卡住】%s 投放 %d 小时 0 票" % (loop.get("topic"), int(age_h))
            tail = "inbox 是被动目录，不会自己叫醒管家；请用 sessions_send 催办或降级为自审"
            subprocess.run(["bash", NOTIFY, head + chr(10) + tail], timeout=60)
        if got:
            reports.append((loop.get("topic"), state, got))
    if reports:
        msg = "【对审结果】" + datetime.datetime.now().strftime("%m-%d %H:%M")
        for topic, state, got in reports:
            msg += "\n· " + topic + " → " + state + "\n  " + "；".join(k + "=" + v for k, v in got.items())
        subprocess.run(["bash", NOTIFY, msg], timeout=60)
        print(msg)
    print("collected:", changed)

if __name__ == "__main__":
    main()

