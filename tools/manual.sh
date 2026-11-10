#!/bin/bash
# manual.sh —— 调出主公手册（零 token，随时可用）
# 用法：bash tools/manual.sh            # 全文
#       bash tools/manual.sh list       # 目录
#       bash tools/manual.sh 3          # 第 3 节
#       bash tools/manual.sh 3d         # 关键词匹配
set -u
W=/home/j/.openclaw/workspace
M="$W/docs/主公手册-20261110.md"
[ -f "$M" ] || { echo "手册不存在：$M"; exit 1; }

case "${1:-all}" in
  all|"") cat "$M"; exit 0 ;;
  list)
    grep -n '^## ' "$M" | sed 's/^/  /'
    echo ""
    echo "调用：bash tools/manual.sh <节号>｜bash tools/manual.sh <关键词>"
    exit 0 ;;
esac

ARG="$1"
if printf '%s' "$ARG" | grep -qE '^[0-9]+$'; then
  awk -v n="$ARG" 'BEGIN{p=0} /^## /{ if(p){exit}; if($2==n"."||$2==n"、"){p=1} } p' "$M"
  # 兼容 "## 3. 我的长期项目" 形式
  if ! awk -v n="$ARG" 'BEGIN{p=0} /^## /{ if(p){exit}; if($2==n"."){p=1} } p' "$M" | grep -q .; then
    awk -v n="$ARG" 'BEGIN{p=0} /^## /{ if(p){exit}; if(index($0, "## " n ". ")==1){p=1} } p' "$M"
  fi
  exit 0
fi

grep -n -i -- "$ARG" "$M" | head -40
exit 0
