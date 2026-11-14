#!/usr/bin/env bash
# skills-publish-all.sh —— 把所有管家工作区里的技能收进共享库 + 记共享账本
# 用法: bash tools/skills-publish-all.sh [--dry]
# 规则: 同名内容一致→跳过；源更新→旧版备份进 .history 后覆盖；含疑似凭据→不发布只告警
set -u
SHARED=/home/j/.openclaw/shared-skills
REG=/home/j/.openclaw/workspace/state/skills/registry.jsonl
DRY=0
if [ "$#" -ge 1 ] && [ "$1" = "--dry" ]; then DRY=1; fi
mkdir -p "$SHARED/.history" "$(dirname "$REG")"
ts=$(date +%Y%m%d-%H%M%S)
now=$(date +%Y-%m-%dT%H:%M:%S)
OUT=$(mktemp)
pub=0; upd=0; skip=0; warn=0

scan_dirs() {
  for base in /home/j/.openclaw/agents/*/agent/workshop-skills /home/j/openclaw-workspaces/*/skills; do
    [ -d "$base" ] || continue
    for d in "$base"/*; do
      [ -d "$d" ] || continue
      [ -f "$d/SKILL.md" ] && printf '%s\n' "$d"
    done
  done
}

while IFS= read -r src; do
  name=$(basename "$src")
  sm="$src/SKILL.md"; dst="$SHARED/$name"
  if grep -qiE "(api[_-]?key|secret|token|password)['\"[:space:]:=]+[A-Za-z0-9_-]{16,}" "$sm" 2>/dev/null; then
    echo "WARN    疑似凭据，跳过 $name  ($src)" >> "$OUT"; warn=$((warn+1)); continue
  fi
  sh_src=$(sha256sum "$sm" | cut -c1-16)
  if [ -f "$dst/SKILL.md" ]; then
    sh_dst=$(sha256sum "$dst/SKILL.md" | cut -c1-16)
    if [ "$sh_src" = "$sh_dst" ]; then skip=$((skip+1)); continue; fi
    if [ "$sm" -nt "$dst/SKILL.md" ]; then
      if [ $DRY -eq 0 ]; then
        mkdir -p "$SHARED/.history/$name-$ts" && cp -f "$dst/SKILL.md" "$SHARED/.history/$name-$ts/" 2>/dev/null
        cp -rf "$src/." "$dst/" 2>/dev/null
        printf '{"skill":"%s","action":"update","source":"%s","sha":"%s","ts":"%s"}\n' "$name" "$src" "$sh_src" "$now" >> "$REG"
      fi
      echo "UPDATE  $name  <- $src" >> "$OUT"; upd=$((upd+1))
    else
      echo "KEEP    共享库版本更新，保留 $name" >> "$OUT"; skip=$((skip+1))
    fi
  else
    if [ $DRY -eq 0 ]; then
      cp -rf "$src" "$dst"
      printf '{"skill":"%s","action":"publish","source":"%s","sha":"%s","ts":"%s"}\n' "$name" "$src" "$sh_src" "$now" >> "$REG"
    fi
    echo "PUBLISH $name  <- $src" >> "$OUT"; pub=$((pub+1))
  fi
done < <(scan_dirs | sort -u)

cat "$OUT"; rm -f "$OUT"
echo "----"
echo "publish=$pub update=$upd skip=$skip warn=$warn dry=$DRY"
if [ $DRY -eq 0 ]; then echo "registry: $REG ($(wc -l < "$REG") 条)"; fi
exit 0
