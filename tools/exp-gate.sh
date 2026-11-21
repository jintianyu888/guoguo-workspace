#!/usr/bin/env bash
# exp-gate.sh —— 复用优先闸门（2026-11-21 主公令）
# 用法：bash tools/exp-gate.sh <关键词>
# 作用：任何改动/升级/部署类动作开工前强制查经验索引，命中写回执并打印前 3 条；查不到也留痕。
set -u
W=/home/j/.openclaw/workspace
KW="${1:-通用}"
TS=$(date +%Y%m%d-%H%M%S)
DIR=$W/state/work/exp-receipts
mkdir -p "$DIR"
OUT=$(timeout 60 python3 "$W/tools/exp.py" "$KW" 2>&1 | head -40)
N=$(printf "%s\n" "$OUT" | grep -c "^- \[" || true)
printf "%s\n" "$OUT" > "$DIR/$TS-$KW.txt"
python3 - "$DIR" "$TS" "$KW" "$N" <<PY
import json,sys,os
d,ts,kw,n=sys.argv[1:5]
json.dump({"ts":ts,"keyword":kw,"hits":int(n)}, open(os.path.join(d,f"{ts}-{kw}.json"),"w"), ensure_ascii=False)
PY
echo "── 经验闸门：$KW 命中 $N 条（回执 $DIR/$TS-$KW.txt）"
printf "%s\n" "$OUT" | sed -n "1,14p"
exit 0