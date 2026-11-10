#!/bin/bash
# ds-tools.sh —— DeepSeek Search / Fetch 原始 API 封装（2026-10-17 接入）
# 用法:
#   ds-tools.sh search "query" [--count N] [--content]   # 返回 JSON
#   ds-tools.sh fetch "https://..." [--md]               # 返回 JSON 或 Markdown 正文
# 计费: 各 5 元 / 1000 次成功请求（失败/无结果不计费）
set -u
BASE="https://api.deepseek.com/v1/tools"

resolve_key() {
  python3 - <<'PY'
import json, sqlite3, os
cfg = json.load(open(os.path.expanduser('~/.openclaw/openclaw.json')))
db  = os.path.expanduser('~/.openclaw/state/openclaw.sqlite')
key = ''
try:
    ak = cfg.get('models',{}).get('providers',{}).get('deepseek',{}).get('apiKey')
    if isinstance(ak, str):
        if ak.startswith('sk-'):
            key = ak
        elif ':' in ak:
            c = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
            row = c.execute("select value_json from config_machine_state where state_key='authProfiles.store'").fetchone()
            if row:
                key = (json.loads(row[0]).get('profiles',{}).get(ak) or {}).get('key') or ''
    elif isinstance(ak, dict) and ak.get('id'):
        key = ak.get('value') or ''
except Exception:
    pass
print(key)
PY
}

KEY="$(resolve_key)"
if [ -z "${KEY:-}" ]; then
  KEY=""  # 2026-10-30 双审修正：摘除欠费美元 key（sk-5d96...，USD -0.04）fallback，只走 provider key
fi
if [ -z "${KEY:-}" ]; then echo '{"error":{"message":"no deepseek key resolvable"}}'; exit 2; fi

cmd="${1:-}"; shift || true
case "$cmd" in
  search)
    q="${1:-}"; shift || true
    count=10; need=false
    while [ $# -gt 0 ]; do
      case "$1" in
        --count) count="${2:-10}"; shift 2 ;;
        --content) need=true; shift ;;
        *) shift ;;
      esac
    done
    [ -z "$q" ] && { echo '{"error":{"message":"query required"}}'; exit 2; }
    body=$(python3 -c 'import json,sys; print(json.dumps({"query":sys.argv[1],"count":int(sys.argv[2]),"need_content":sys.argv[3]=="true"}))' "$q" "$count" "$need")
    curl -sS -m 90 "$BASE/search" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$body"
    ;;
  fetch)
    url="${1:-}"; shift || true
    md=false; [ "${1:-}" = "--md" ] && md=true
    [ -z "$url" ] && { echo '{"error":{"message":"url required"}}'; exit 2; }
    body=$(python3 -c 'import json,sys; print(json.dumps({"url":sys.argv[1]}))' "$url")
    out=$(curl -sS -m 90 "$BASE/fetch" -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' -d "$body")
    if [ "$md" = true ]; then
      printf '%s' "$out" | python3 -c 'import json,sys
try:
    d=json.load(sys.stdin); print("# "+ (d.get("title") or "")); print(); print(d.get("content") or "")
except Exception: print(sys.stdin.read() if False else "parse error")'
    else printf '%s' "$out"; fi
    ;;
  *)
    echo '{"error":{"message":"usage: ds-tools.sh search|fetch ..."}}'; exit 2 ;;
esac
