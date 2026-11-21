#!/usr/bin/env bash
# model-switch.sh v1.0 (2026-11-21) —— 单管家换模型，秒级生效
# 背景：整包 config patch 校验 39 个管家要 ~100s；单路径 config set 只要 ~2.5s。
# 用法：
#   bash tools/model-switch.sh <agent> <provider/model> [--fallbacks '["a","b"]'] [--dry-run]
#   bash tools/model-switch.sh --status
set -o pipefail
WS=/home/j/.openclaw/workspace
if [ "$1" = "--status" ] || [ -z "$1" ]; then python3 "$WS/tools/model-status.py"; exit 0; fi
# --bulk <provider/model>：全量改主力（直写配置 + 单次官方校验，约 10s；官方 patch 需 ~100s）
if [ "$1" = "--bulk" ]; then
  TGT="$2"
  FBS="$3"
  [ -z "$FBS" ] && FBS='["zai/glm-5.3-flash","ollama/gpt-oss:20b"]'
  [ -z "$TGT" ] && { echo "usage: model-switch.sh --bulk <provider/model> [fallbacks-json]"; exit 2; }
  TS=$(date +%Y%m%d-%H%M%S); BK="$WS/state/backup/config/openclaw.json.bak-$TS"
  mkdir -p "$WS/state/backup/config"; cp /home/j/.openclaw/openclaw.json "$BK"
  python3 - "$TGT" "$FBS" <<'PY'
import json,sys
tgt,fbs=sys.argv[1],json.loads(sys.argv[2])
p="/home/j/.openclaw/openclaw.json"
d=json.load(open(p))
ents=d["agents"]["entries"]
for k,v in ents.items():
    m=v.setdefault("model",{})
    m["primary"]=tgt; m["fallbacks"]=fbs
d["agents"].setdefault("defaults",{}).setdefault("model",{})["primary"]=tgt
d["agents"]["defaults"]["model"]["fallbacks"]=fbs
json.dump(d,open(p,"w"),ensure_ascii=False,indent=2)
print("已写入 %d 个管家 -> %s" % (len(ents), tgt))
PY
  if openclaw config get agents.defaults.model --json >/dev/null 2>&1; then
    python3 "$WS/tools/model-status.py"
    echo "OK 全量=$TGT 备份=$BK"
  else
    cp "$BK" /home/j/.openclaw/openclaw.json
    echo "FAIL 校验未过，已回滚到 $BK"; exit 1
  fi
  exit 0
fi
AG="$1"; MD="$2"
DRY=0; FB=""
shift; shift
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift;;
    --fallbacks) FB="$2"; shift; shift;;
    *) shift;;
  esac
done
[ -z "$MD" ] && { echo "usage: model-switch.sh <agent> <provider/model> [--fallbacks JSON] [--dry-run]"; exit 2; }
OLD=$(python3 - "$AG" <<PY
import json,sys
d=json.load(open("/home/j/.openclaw/openclaw.json"))
e=d["agents"]["entries"].get(sys.argv[1])
print(((e or {}).get("model") or {}).get("primary") or "")
PY
)
[ -z "$OLD" ] && { echo "FAIL 找不到管家 $AG（或没 model 字段）"; exit 1; }
echo "切换 $AG：$OLD → $MD"
if [ "$DRY" = "1" ]; then echo "dry-run 结束，未写入"; exit 0; fi
if [ "$OLD" = "$MD" ] && [ -z "$FB" ]; then echo "no-op：$AG 已经是 $MD"; exit 0; fi
set -e
openclaw config set "agents.entries.$AG.model.primary" "$MD" >/dev/null
if [ -n "$FB" ]; then openclaw config set "agents.entries.$AG.model.fallbacks" "$FB" >/dev/null; fi
NEW=$(python3 - "$AG" <<PY
import json,sys
d=json.load(open("/home/j/.openclaw/openclaw.json"))
print(((d["agents"]["entries"].get(sys.argv[1]) or {}).get("model") or {}).get("primary") or "")
PY
)
[ "$NEW" = "$MD" ] || { echo "FAIL 校验不一致：$NEW"; exit 1; }
python3 "$WS/tools/model-policy-ledger.py" --agent "$AG" --field model.primary --from "$OLD" --to "$MD" --reason "手动切换 model-switch.sh" --writer 果果 >/dev/null 2>&1 || true
python3 "$WS/tools/worklog.py" add change "模型切换 $AG $OLD→$MD" ok evidence="config get 校验=$NEW" rollback="model-switch.sh $AG $OLD" >/dev/null 2>&1 || true
echo "OK $AG = $NEW（已入策略账本）"