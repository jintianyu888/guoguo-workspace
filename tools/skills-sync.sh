#!/bin/bash
# skills-sync.sh —— 共享技能管理（2026-11-10 立）
# 机制：主本放 /home/j/.openclaw/shared-skills，配置 skills.load.extraDirs 指过去，
#       所有管家都能读到（软链会被"根边界"安全策略跳过，所以不用软链）。
# 用法：
#   bash tools/skills-sync.sh                 列出共享技能 + 抽查可见性
#   bash tools/skills-sync.sh --add <路径>     把一个技能目录发布到共享（复制）
#   bash tools/skills-sync.sh --rm <名字>      从共享撤下
set -u
SHARED=/home/j/.openclaw/shared-skills
CFG=/home/j/.openclaw/openclaw.json
cmd="${1:-list}"

case "$cmd" in
  --add)
    src="${2:-}"; [ -d "$src" ] || { echo "用法: --add <技能目录>"; exit 2; }
    name=$(basename "$src")
    [ -f "$src/SKILL.md" ] || { echo "缺 SKILL.md"; exit 2; }
    rm -rf "$SHARED/$name"; cp -r "$src" "$SHARED/$name"
    echo "已发布 $name → $SHARED/$name（各管家下个会话可见）"
    ;;
  --rm)
    name="${2:-}"; [ -n "$name" ] || { echo "用法: --rm <名字>"; exit 2; }
    rm -rf "$SHARED/$name"; echo "已撤下 $name"
    ;;
  *)
    python3 - "$CFG" <<'PY'
import json,sys
c=json.load(open(sys.argv[1]))
d=(c.get('skills',{}).get('load',{}) or {}).get('extraDirs') or []
print('extraDirs:', d if d else '(未配置！)')
PY
    echo "共享技能 $(ls -1 $SHARED 2>/dev/null | wc -l) 个："
    ls -1 "$SHARED" 2>/dev/null | sed 's/^/  /'
    echo "抽查 cooking："
    cd /home/j/.openclaw && openclaw skills --agent cooking --json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);s=d if isinstance(d,list) else d.get('skills',[]);print('  总数',len(s))"
    ;;
esac
