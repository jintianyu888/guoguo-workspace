#!/bin/bash
# 逐包升级 + 逐包测试 + 失败回滚（pkg-upgrade-one.sh）
# 用法: pkg-upgrade-one.sh <venv目录> <包名> <测试命令>
set -uo pipefail
V="$1"; PKG="$2"; TEST="$3"
W=/home/j/.openclaw/workspace
PIP="$V/bin/pip"; PY="$V/bin/python3"
LOG="$W/state/work/pkgup-20261029.log"
MIR=https://pypi.tuna.tsinghua.edu.cn/simple
OLD=$("$PIP" show "$PKG" 2>/dev/null | awk '/^Version:/{print $2}')
echo "[$(date +%H:%M:%S)] UPGRADE $PKG from ${OLD:-none}" | tee -a "$LOG"
if ! "$PIP" install -U "$PKG" -i "$MIR" --disable-pip-version-check >>"$LOG" 2>&1; then
  echo "[FAIL-INSTALL] $PKG" | tee -a "$LOG"; exit 2
fi
NEW=$("$PIP" show "$PKG" 2>/dev/null | awk '/^Version:/{print $2}')
"$PIP" check >>"$LOG" 2>&1 || { echo "[FAIL-PIPCHECK] $PKG" | tee -a "$LOG"; echo "$PKG|${OLD:-none}|$NEW|PIPCHECK_FAIL" >> "$W/state/work/pkgup-20261029.csv"; exit 4; }
if eval "$TEST" >>"$LOG" 2>&1; then
  echo "[OK] $PKG $OLD -> $NEW" | tee -a "$LOG"; echo "$PKG|${OLD:-none}|$NEW|OK" >> "$W/state/work/pkgup-20261029.csv"; exit 0
else
  echo "[FAIL-TEST] $PKG $OLD -> $NEW，回滚" | tee -a "$LOG"
  [ -n "${OLD:-}" ] && "$PIP" install "$PKG==$OLD" -i "$MIR" --disable-pip-version-check >>"$LOG" 2>&1
  echo "$PKG|${OLD:-none}|$NEW|ROLLED_BACK" >> "$W/state/work/pkgup-20261029.csv"; exit 3
fi
