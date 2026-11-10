#!/usr/bin/env python3
"""review-ledger.py - 评审用量唯一账（2026-11-01 立，配合唯一台账规则）
每次评审调用写一条：谁发起、哪家模型、多少字节、耗时、是否有效。
"""
import argparse, json, os, hashlib, datetime

LEDGER = "/home/j/.openclaw/workspace/state/usage-meter/review-ledger.jsonl"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--vendor", default="")
    ap.add_argument("--bytes", type=int, default=0)
    ap.add_argument("--duration", type=int, default=0)
    ap.add_argument("--rc", type=int, default=0)
    ap.add_argument("--valid", type=int, default=0)
    ap.add_argument("--task", default="review")
    ap.add_argument("--verdict", default="")
    a = ap.parse_args()

    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    rec = {
        "ts": ts,
        "writer": "cross-review-par.sh",
        "action": "review_call",
        "task": a.task,
        "vendor": a.vendor,
        "model": a.model,
        "out_bytes": a.bytes,
        "duration_s": a.duration,
        "rc": a.rc,
        "valid": bool(a.valid),
        "verdict": a.verdict,
    }
    raw = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    rec["content_sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    rec["trace_id"] = rec["content_sha256"][:16]

    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    print(rec["trace_id"])

if __name__ == "__main__":
    main()
