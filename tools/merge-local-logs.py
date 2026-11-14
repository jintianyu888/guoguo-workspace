#!/usr/bin/env python3
"""merge-local-logs.py — 把各管家工作区里的本地台账合并进统一账本（零 token）
来源: /home/j/openclaw-workspaces/<agent>/state/worklog-local-YYYY-MM-DD.jsonl
去向: python3 tools/worklog.py add <类别> <对象> <结果> actor=<agent> task=local-merge
幂等: 已合并过的 (agent, ts, 内容指纹) 记在 state/log/local-merge.json，不重复写
用法: merge-local-logs.py [--dry-run] [--days 3]
"""
import os, sys, json, glob, hashlib, subprocess, datetime, argparse

W = "/home/j/.openclaw/workspace"
LED = os.path.join(W, "tools", "worklog.py")
SEEN = os.path.join(W, "state", "log", "local-merge.json")
ROOTS = "/home/j/openclaw-workspaces"


def load_seen():
    try:
        return set(json.load(open(SEEN)))
    except Exception:
        return set()


def save_seen(s):
    os.makedirs(os.path.dirname(SEEN), exist_ok=True)
    json.dump(sorted(s), open(SEEN, "w"), ensure_ascii=False, indent=0)


def flatten(entry):
    if isinstance(entry, dict):
        parts = []
        for k, v in entry.items():
            if k in ("ts", "time"):
                continue
            if isinstance(v, (str, int, float)):
                parts.append(f"{k}={v}")
            else:
                parts.append(f"{k}={json.dumps(v, ensure_ascii=False)}")
        return "; ".join(parts)
    return str(entry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--days", type=int, default=3)
    a = ap.parse_args()
    seen = load_seen()
    added = skipped = 0
    cutoff = datetime.date.today() - datetime.timedelta(days=a.days)
    for agentdir in sorted(glob.glob(os.path.join(ROOTS, "*"))):
        agent = os.path.basename(agentdir)
        for f in glob.glob(os.path.join(agentdir, "state", "worklog-local-*.jsonl")):
            datepart = f.rsplit("worklog-local-", 1)[1][:10]
            try:
                d = datetime.date.fromisoformat(datepart)
            except Exception:
                d = None
            if d and d < cutoff:
                continue
            for line in open(f, encoding="utf-8", errors="replace"):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    rec = {"raw": line}
                for e in (rec.get("entries") or [rec]):
                    text = flatten(e)
                    if not text.strip():
                        continue
                    fp = hashlib.sha256((agent + "|" + text[:400]).encode()).hexdigest()[:16]
                    if fp in seen:
                        skipped += 1
                        continue
                    obj = "本地台账合并(%s)" % agent
                    res = text[:400]
                    cmd = [sys.executable, LED, "add", "note", obj, res,
                           f"actor={agent}", "task=local-merge"]
                    if a.dry_run:
                        print("[dry]", agent, res[:80])
                    else:
                        r = subprocess.run(cmd, capture_output=True, text=True)
                        if r.returncode != 0:
                            print("[fail]", agent, r.stderr[-120:])
                            continue
                    seen.add(fp)
                    added += 1
    if not a.dry_run:
        save_seen(seen)
    print(f"合并 {added} 条，跳过重复 {skipped} 条")


if __name__ == "__main__":
    main()
