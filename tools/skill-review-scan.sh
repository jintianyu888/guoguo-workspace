#!/bin/sh
# skill-review-scan.sh
# 零 token 机械前置：扫描所有管家的 Skill Workshop（技能收集），
# 只输出「新增 / 缺失 / 变更 / 体积异常 / 结构告警」；无问题则静默。
#
# 用法:
#   skill-review-scan.sh              正常扫描（对比基线，有问题才输出，并更新基线）
#   skill-review-scan.sh --no-update  只报告不更新基线（dry-run）
# 退出码恒为 0（避免把“有变更”误判为运行失败）。
# 兼容 POSIX sh（dash）与 bash。
set -u

ROOTS_DIR="/home/j/.openclaw/agents"
STATE_DIR="/home/j/.openclaw/workspace/state/skill-review"
MANIFEST="$STATE_DIR/manifest.tsv"
PREV="$STATE_DIR/manifest.prev.tsv"
LOG="$STATE_DIR/last-run.log"

SIZE_WARN_BYTES=1048576   # 单文件 >=1MB 告警
SKILL_SIZE_WARN=524288    # SKILL.md >=512KB 告警
MAX_NEW_WARN=10           # 一次新增 >10 个 → 批量新增告警

UPDATE=1
[ "${1:-}" = "--no-update" ] && UPDATE=0

mkdir -p "$STATE_DIR"

ROOTLIST="$(mktemp)"
for d in "$ROOTS_DIR"/*/agent/workshop-skills; do
  [ -d "$d" ] && printf '%s\n' "$d" >> "$ROOTLIST"
done
ROOTCOUNT=$(wc -l < "$ROOTLIST" | tr -d ' ')
if [ "$ROOTCOUNT" -eq 0 ]; then
  echo "[skill-review] 未找到任何 Skill Workshop 目录，请检查 $ROOTS_DIR"
  rm -f "$ROOTLIST"
  exit 0
fi

TMP="$(mktemp)"
REPORT="$(mktemp)"
trap 'rm -f "$TMP" "$REPORT" "$ROOTLIST"' EXIT
: > "$REPORT"

# shellcheck disable=SC2046
find $(cat "$ROOTLIST") -type f 2>/dev/null | LC_ALL=C sort | while IFS= read -r f; do
  sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
  h=$(sha256sum "$f" 2>/dev/null | cut -d' ' -f1)
  printf '%s\t%s\t%s\n' "$f" "$sz" "$h"
done > "$TMP"

if [ -f "$MANIFEST" ] && [ -s "$MANIFEST" ]; then
  awk -F'\t' 'NR==FNR{a[$1]=1;next} !($1 in a){print "新增: "$1" ("$2" bytes)"}' "$MANIFEST" "$TMP" >> "$REPORT"
  awk -F'\t' 'NR==FNR{a[$1]=1;next} !($1 in a){print "缺失: "$1}' "$TMP" "$MANIFEST" >> "$REPORT"
  awk -F'\t' 'NR==FNR{h[$1]=$3;next} ($1 in h) && h[$1]!=$3 {print "变更: "$1" ("$2" bytes)"}' "$MANIFEST" "$TMP" >> "$REPORT"
else
  awk -F'\t' '{print "新增: "$1" ("$2" bytes)"}' "$TMP" >> "$REPORT"
fi

awk -F'\t' -v lim="$SIZE_WARN_BYTES" '$2+0>=lim {print "体积异常(>=1MB): "$1" ("$2" bytes)"}' "$TMP" >> "$REPORT"

TAB=$(printf '\t')
while IFS="$TAB" read -r path sz h; do
  case "$path" in
    */SKILL.md)
      if [ "${sz:-0}" -ge "$SKILL_SIZE_WARN" ]; then
        echo "体积异常(SKILL.md>=512KB): $path ($sz bytes)" >> "$REPORT"
      fi
      if ! head -c 600 "$path" | grep -q '^name:'; then
        echo "结构告警(缺 name 字段): $path" >> "$REPORT"
      fi
      ;;
  esac
done < "$TMP"

NEWCOUNT=$(grep -c '^新增:' "$REPORT" 2>/dev/null || true)
NEWCOUNT=${NEWCOUNT:-0}
if [ "$NEWCOUNT" -gt "$MAX_NEW_WARN" ]; then
  echo "批量新增告警: 本次新增 $NEWCOUNT 个文件，请确认是否为异常导入" >> "$REPORT"
fi

ISSUES=0
if [ -s "$REPORT" ]; then
  ISSUES=1
  TOTAL=$(wc -l < "$TMP" | tr -d ' ')
  echo "🔧 技能收集审查（机械扫描）— 发现变更"
  echo "扫描根: $ROOTCOUNT 个管家 Skill Workshop ｜ 当前技能文件: $TOTAL"
  echo "----"
  cat "$REPORT"
  echo "----"
  echo "建议: 正常新增/维护无需动作；异常导入或体积膨胀请安排人工巡检。"
fi

if [ "$UPDATE" = "1" ]; then
  [ -f "$MANIFEST" ] && cp -f "$MANIFEST" "$PREV"
  cp -f "$TMP" "$MANIFEST"
fi

printf '[%s] roots=%s files=%s issues=%s update=%s\n' "$(date '+%F %T')" "$ROOTCOUNT" "$(wc -l < "$TMP" | tr -d ' ')" "$ISSUES" "$UPDATE" >> "$LOG"
exit 0
