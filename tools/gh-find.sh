#!/bin/bash
# gh-find.sh —— 从 GitHub 找现成轮子（零 token、不需要账号、24h 本地缓存）
# 用法：bash tools/gh-find.sh "关键词" [--min-stars 200] [--limit 8] [--json] [--fresh]
set -u
Q="${1:-}"; [ -z "$Q" ] && { echo '用法：bash tools/gh-find.sh "关键词" [--min-stars N] [--limit N] [--json] [--fresh]'; exit 1; }
shift || true
MIN=100; LIM=8; JSON=0; FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --min-stars) MIN="$2"; shift 2 ;;
    --limit) LIM="$2"; shift 2 ;;
    --json) JSON=1; shift ;;
    --fresh) FRESH=1; shift ;;
    *) shift ;;
  esac
done
QENC=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$Q")
URL="https://api.github.com/search/repositories?q=${QENC}+stars:>=${MIN}&sort=stars&order=desc&per_page=${LIM}"
CDIR="$HOME/.openclaw/workspace/state/ghfind"; mkdir -p "$CDIR"
KEY=$(printf "%s|%s|%s" "$Q" "$MIN" "$LIM" | md5sum | cut -c1-16)
CACHE="$CDIR/$KEY.json"
RAW=""
if [ "$FRESH" = "0" ] && [ -f "$CACHE" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$CACHE") ))
  [ "$AGE" -lt 86400 ] && RAW=$(cat "$CACHE")
fi
if [ -z "$RAW" ]; then
  RAW=$(curl -s -m 15 -H 'accept: application/vnd.github+json' -H 'user-agent: guoguo-gh-find' "$URL")
fi
[ -z "$RAW" ] && { echo "取不到（网络不通）"; exit 1; }
case "$RAW" in
  *"rate limit exceeded"*)
    echo "⏳ GitHub 未认证限速（搜索 10 次/分钟，本机出口 IP 共享）。"
    echo "   等 60 秒再试；配 PAT 后可提到 30 次/分钟（放 /home/j/.config/guoguo/github.env）。"
    exit 3 ;;
  *) printf '%s' "$RAW" > "$CACHE" ;;
esac

if [ "$JSON" = "1" ]; then printf '%s' "$RAW" | python3 -m json.tool; exit 0; fi

printf '%s' "$RAW" | python3 -c '
import sys,json
d=json.load(sys.stdin)
if "items" not in d:
    print("API 返回异常：", str(d)[:200]); sys.exit(1)
print("命中 %d 个（按星排序）\n" % d.get("total_count",0))
GOOD=("MIT","Apache-2.0","BSD-3-Clause","BSD-2-Clause","ISC","MPL-2.0","Unlicense")
VIRAL=("AGPL-3.0","GPL-3.0","GPL-2.0","SSPL-1.0","LGPL-3.0")
for x in d["items"]:
    lic=(x.get("license") or {}).get("spdx_id") or "无"
    if lic in GOOD: flag="✅可商用"
    elif lic in VIRAL: flag="⚠️传染性"
    else: flag="❔人工核"
    print("%-42s %6d★  %-12s %-9s 最后推送 %s" % (x["full_name"], x["stargazers_count"], lic, flag, x["pushed_at"][:10]))
    print("    %s" % (x.get("description") or "").replace("\n"," ")[:90])
'
echo ""
echo "下一步：挑 1-2 个 → 看 README 与近 20 次提交 → 隔离目录试用 → 通过再登记（用途/版本/许可证/来源）"
