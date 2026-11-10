#!/usr/bin/env bash
# skill-mirror.sh —— 把共享技能主本镜像到 main 实际加载的 workshop-skills
# 只在 workshop 已存在同名技能时覆盖（不新增，避免与 extraDirs 重复占位）
set -u
SHARED=/home/j/.openclaw/shared-skills
WS=/home/j/.openclaw/agents/main/agent/workshop-skills
n=0
for d in "$SHARED"/*/; do
  name=$(basename "$d")
  [ "$name" = ".history" ] && continue
  [ -d "$WS/$name" ] || continue
  cp -f "$d/SKILL.md" "$WS/$name/SKILL.md" 2>/dev/null && n=$((n+1))
done
echo "mirrored $n skill(s) to workshop"
