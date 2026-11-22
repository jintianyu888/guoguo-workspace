#!/usr/bin/env bash
# r32-skill-pack.sh —— R32 完成即打包：当天有交付类动作（deploy/change/fix），
# 当天必须有技能包动作（新建/更新共享技能，或技能使用记录）。零 token。
# 可用 R32_DATE=YYYY-MM-DD 指定日期做测试。
set -uo pipefail
WS=/home/j/.openclaw/workspace
SHARED=/home/j/.openclaw/shared-skills
DAY=$(printenv R32_DATE 2>/dev/null)
[ -n "$DAY" ] || DAY=$(date +%F)

python3 - "$WS" "$SHARED" "$DAY" <<'PY'
import json, os, sys, datetime, pathlib
ws, shared, day = sys.argv[1], sys.argv[2], sys.argv[3]

deliv = []
wl = os.path.join(ws, "state/log/worklog.jsonl")
if os.path.exists(wl):
    for line in open(wl, encoding="utf-8", errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        ts = str(r.get("ts") or r.get("time") or "")
        cat = str(r.get("category") or r.get("cat") or "")
        if ts[:10] == day and cat in ("deploy", "change", "fix"):
            deliv.append((ts, cat, str(r.get("target") or r.get("object") or "")))

pack = []
for p in pathlib.Path(shared).iterdir():
    if not p.is_dir() or p.name.startswith("."):
        continue
    try:
        mt = datetime.date.fromtimestamp(p.stat().st_mtime).isoformat()
    except Exception:
        continue
    if mt == day:
        pack.append("dir:" + p.name)
usage = os.path.join(ws, "state/skills/usage.jsonl")
if os.path.exists(usage):
    for line in open(usage, encoding="utf-8", errors="ignore"):
        if day in line:
            pack.append("use")

n, m = len(deliv), len(set(pack))
if n == 0:
    print("✅ R32 %s：当天无交付类动作，无需打包" % day)
    sys.exit(0)
if m > 0:
    print("✅ R32 %s：交付 %d 项，技能包动作 %d 个（%s）" % (day, n, m, ", ".join(sorted(set(pack))[:4])))
    sys.exit(0)
print("❌ R32 %s：当天有 %d 项交付（deploy/change/fix）但没有任何技能包动作" % (day, n))
for ts, cat, tgt in deliv[:6]:
    print("   - %s [%s] %s" % (ts[11:19], cat, tgt[:50]))
print("   → 补：bash tools/skill-new.sh <名称> \"<描述>\"，填完 --publish")
sys.exit(1)
PY
