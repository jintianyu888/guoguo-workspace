#!/bin/bash
# skill-new.sh —— 做完一件事就沉淀成一个技能（2026-11-10 主公令）
# 用法：
#   bash tools/skill-new.sh <技能名> "<一句话描述>"
#   bash tools/skill-new.sh --publish <name>   |  --check <name>
set -u
SHARED=/home/j/.openclaw/shared-skills
cmd="${1:-}"

validate() {
  local f="$1"
  [ -f "$f" ] || { echo "缺 SKILL.md"; return 1; }
  local name desc
  name=$(awk -F': *' '/^name:/{print $2; exit}' "$f")
  desc=$(awk -F': *' '/^description:/{print $2; exit}' "$f")
  [ -n "$name" ] || { echo "❌ 缺 name"; return 1; }
  [ -n "$desc" ] || { echo "❌ 缺 description"; return 1; }
  local dlen=${#desc}
  [ "$dlen" -ge 20 ] || { echo "❌ description 太短（$dlen 字符，至少 20）"; return 1; }
  grep -q "^## 什么时候用" "$f" || { echo "❌ 缺「## 什么时候用」"; return 1; }
  grep -qE "sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH) PRIVATE KEY" "$f" && { echo "❌ 疑似凭据，拒绝发布"; return 1; }
  echo "✅ $name：description $dlen 字符，结构完整"
  return 0
}

case "$cmd" in
  --publish)
    n="${2:-}"; src="/tmp/skill-$n/SKILL.md"
    [ -f "$src" ] || src="$SHARED/$n/SKILL.md"
    validate "$src" || exit 3
    mkdir -p "$SHARED/$n" && cp "$src" "$SHARED/$n/SKILL.md"
    echo "已发布 → $SHARED/$n （各管家下个会话可见）"
    ;;
  --check)
    n="${2:-}"; validate "/tmp/skill-$n/SKILL.md" || validate "$SHARED/$n/SKILL.md"; exit $?
    ;;
  "")
    echo '用法: skill-new.sh <名称> "<描述>" | --publish <名称> | --check <名称>'; exit 2
    ;;
  *)
    name="$1"; desc="${2:-待补充：说明这个技能解决什么问题、什么时候触发}"
    dir="/tmp/skill-$name"; mkdir -p "$dir"
    cat > "$dir/SKILL.md" <<EOF
---
name: $name
description: $desc
---

# $name

## 什么时候用

（触发条件：主公说什么话、遇到什么症状、要做什么动作时用）

## 前置条件 / 环境

- 依赖的命令、路径、凭据位置（只写位置，不写凭据本身）

## 步骤

1.
2.
3.

## 验证

（命令 + 期望输出）

## 坑与注意

- 踩过的坑、失败模式、不要做什么

## 回滚

（撤销方式，或说明为何无需回滚）

## 来源

（哪天、为哪件事沉淀）
EOF
    echo "骨架已生成：$dir/SKILL.md"
    echo "填完正文后：bash tools/skill-new.sh --publish $name"
    ;;
esac
