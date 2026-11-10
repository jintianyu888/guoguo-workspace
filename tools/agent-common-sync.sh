#!/bin/bash
# agent-common-sync.sh — 把 docs/管家通用守则.md（单一源）写进所有管家 AGENTS.md 的只读标记块
# 用法: --check 校验一致性与版本 | --apply 写入（带备份）
set -uo pipefail
WS=/home/j/.openclaw/workspace
SRC=$WS/docs/管家通用守则.md
BASE=${AGENT_WS_BASE:-/home/j/openclaw-workspaces}
MODE=${1:---check}
[ -f "$SRC" ] || { echo "缺 $SRC"; exit 2; }
python3 - "$SRC" "$BASE" "$MODE" <<\PY
import sys, os, glob, json, time, shutil, hashlib
src, base, mode = sys.argv[1], sys.argv[2], sys.argv[3]
raw = open(src, encoding="utf-8").read()
ver = hashlib.sha256(raw.encode()).hexdigest()[:8]
body = raw.replace("<!--", "<! --").strip()
B, E = "<!-- COMMON:BEGIN", "COMMON:END -->"
B = B + " ver=" + ver + " -->"
block = B + chr(10) + body + chr(10) + E
cfg=json.load(open("/home/j/.openclaw/openclaw.json"))
ents=(cfg.get("agents") or {}).get("entries",{})
files=sorted({os.path.join((v or {}).get("workspace") or "","AGENTS.md") for v in ents.values()} - {"AGENTS.md"})
files=[f for f in files if f and os.path.isfile(f)]
ok = drift = missing = 0
bad = []
for f in files:
    s = open(f, encoding="utf-8").read()
    cur = ""
    i = s.find('<!-- COMMON:BEGIN')
    if i >= 0:
        cur = s[i:s.find('-->', i)]
    if B in s:
        ok += 1
        continue
    if cur:
        drift += 1
        bad.append((f, "旧版", cur.strip()[-20:]))
    else:
        missing += 1
        bad.append((f, "未注入", ""))
    if mode == "--apply":
        if i >= 0:
            j = s.find('COMMON:END -->', i) + len('COMMON:END -->')
            new = s[:i] + block + s[j:]
        else:
            new = s.rstrip() + chr(10) * 2 + block + chr(10)
        shutil.copy(f, f + ".bak-common-" + time.strftime("%Y%m%d-%H%M%S"))
        open(f, "w", encoding="utf-8").write(new)
print(f"守则版本 {ver}｜共 {len(files)} 个管家：一致 {ok}，旧版 {drift}，未注入 {missing}（模式 {mode}）")
for f, why, extra in bad[:10]:
    print("  ", why, os.path.basename(os.path.dirname(f)), extra)
sys.exit(0 if (drift + missing == 0) else 1)
PY
