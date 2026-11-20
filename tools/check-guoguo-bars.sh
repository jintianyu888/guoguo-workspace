#!/usr/bin/env bash
# 果果助手信息条位置冻结校验（2026-11-20 主公确认，干活管家落 docs/信息条位置定稿-20261120.md）
# 冻结基线：144 top:12px / 145 bottom:14px / 150 .wrap padding:46px 42px 48px
# 用法：bash tools/check-guoguo-bars.sh [文件]   rc=0 未被改动；rc=1 被改动或被新规则覆盖
set -u
F="${1:-/home/j/openclaw-workspaces/work/果果助手/public/index.html}"
[ -f "$F" ] || { echo "MISSING $F"; exit 1; }
rc=0
line_of(){ grep -n "$1" "$F" | head -1; }
echo "== 冻结基线三行（bump 报告直接贴这段）=="
for pat in 'body.hud #ocTop{.*top:12px !important' 'body.hud #ocIdle{.*bottom:14px !important' 'body.hud .wrap{padding:46px 42px 48px !important'; do
  L=$(line_of "$pat")
  if [ -z "$L" ]; then echo "FAIL 缺少或已被改：$pat"; rc=1; else echo "OK   $L"; fi
done
echo "== 覆盖检查 =="
N=$(grep -c 'body.hud \.wrap{padding:' "$F")
echo "body.hud .wrap{padding 规则条数: $N（必须为 1）"
[ "$N" -eq 1 ] || { echo "FAIL 出现多条 .wrap padding 规则，冻结值可能被覆盖"; rc=1; }
for bad in 'padding:98px 52px 98px' 'top:52px !important;margin:0' 'bottom:52px !important;top:auto'; do
  if grep -q "$bad" "$F"; then echo "FAIL 残留旧值：$bad"; rc=1; fi
done
echo "== 结论 =="
[ $rc -eq 0 ] && echo "PASS 信息条三行未被改动" || echo "FAIL 冻结基线被破坏，停手报干活管家"
exit $rc
