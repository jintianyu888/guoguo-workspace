#!/bin/sh
# pkg-upgrade-check.sh v2 —— 安装包升级巡检（只认稳定版；预发布一律不看）
W=/home/j/.openclaw/workspace
MIR=https://pypi.tuna.tsinghua.edu.cn/simple
OUT=$W/state/pkg-upgrade-report.md
TS=$(date "+%F %T")
{
  echo "# 安装包升级巡检  $TS"
  echo
  echo "策略：**只升稳定版**（预发布不升）；补丁级可直升，主版本/大改先报主公。"
  echo
  for V in asr-venv ocr-venv embed-venv; do
    P=$W/tools/$V/bin/pip
    if [ ! -x "$P" ]; then continue; fi
    echo "## $V"
    "$P" list --outdated -i "$MIR" --disable-pip-version-check 2>/dev/null > $W/state/.pkg-tmp.txt
    n=$(wc -l < $W/state/.pkg-tmp.txt)
    if [ "$n" -le 2 ]; then
      echo "- ✅ 全部为最新（稳定版）"
    else
      echo "待升级（共 $((n-2)) 项）："
      tail -n +3 $W/state/.pkg-tmp.txt | awk -F" " "{printf \"- %s: %s → %s\\n\", \$1, \$2, \$3}"
    fi
    echo
  done
  rm -f "$W/state/.pkg-tmp.txt"
  echo "## 其他"
  echo "- openclaw: $(openclaw --version 2>/dev/null | head -n 1)"
  echo "- HF 模型：不自动升级（人工评估）"
} > "$OUT" 2>/dev/null
echo "报告: $OUT"
grep -c "→" "$OUT" 2>/dev/null | sed "s/^/待升级条目: /"