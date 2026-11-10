#!/usr/bin/env python3
"""语音转写兜底监听：登记每条入站语音，转不出来的自动补转。
用法: asr-ledger.py backfill [N] | list [N] | stats
"""
import glob
import json
import os
import subprocess
import sys
import time

WS = "/home/j/.openclaw/workspace"
LED = WS + "/state/asr/ledger.jsonl"
IN = "/home/j/.openclaw/media/inbound"
MODEL = WS + "/tools/models/faster-whisper-medium"
ASR = WS + "/tools/asr"


def load():
    d = {}
    if os.path.exists(LED):
        with open(LED, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                    d[r["file"]] = r
                except Exception:
                    pass
    return d


def transcribe(path):
    try:
        p = subprocess.run(["nice", "-n", "15", ASR, path, "--language", "zh", "--model", MODEL],
                           capture_output=True, text=True, timeout=300)
        txt = (p.stdout or "").strip()
        return txt, p.returncode
    except Exception as e:
        return "", -1


def backfill(n=3):
    known = load()
    files = sorted(glob.glob(os.path.join(IN, "*.ogg")),
                   key=os.path.getmtime, reverse=True)[:int(n)]
    rows = []
    for f in files:
        if known.get(f, {}).get("status") == "ok":
            continue
        txt, rc = transcribe(f)
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": f,
               "mtime": time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(f))),
               "size": os.path.getsize(f), "rc": rc,
               "status": "ok" if txt else "empty", "text": txt[:2000]}
        with open(LED, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + chr(10))
        rows.append(rec)
        print(rec["mtime"], rec["status"], "|", rec["text"][:80])
    if not rows:
        print("无待补转条目")
    return rows


def show(n=10):
    d = load()
    rows = sorted(d.values(), key=lambda r: r.get("mtime", ""))[-int(n):]
    for r in rows:
        print(r.get("mtime"), r.get("status"), "|", (r.get("text") or "")[:70])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    arg = sys.argv[2] if len(sys.argv) > 2 else 10
    if cmd == "backfill":
        backfill(arg)
    else:
        show(arg)
