#!/usr/bin/env bash
# self-audit.sh — 体量/健康 只读自审 (v1: report-only, 不做任何删除或改动)
# 依据 2026-10-16 主公令 + 交叉验证(Pro/GLM) 结论: 先只读、只报告、不自动清理
set -u
W=/home/j/.openclaw/workspace
OUT=$W/state/self-audit-$(date +%Y%m%d).md
{
echo "# 自审报告 $(date '+%F %T')（只读，不改动任何东西）"
echo; echo "## 1. 各盘使用率 / inode"
df -h / /mnt/d /mnt/e /mnt/h 2>/dev/null | grep -vE '^Filesystem' | sed 's/^/  /'
df -i / /mnt/d 2>/dev/null | grep -vE '^Filesystem' | sed 's/^/  i: /'
echo; echo "## 2. ~/.openclaw 分目录"
du -sh $HOME/.openclaw 2>/dev/null | sed 's/^/  总: /'
du -sh $HOME/.openclaw/* 2>/dev/null | sort -rh | head -12 | sed 's/^/    /'
echo; echo "## 3. workspace / .git"
du -sh $HOME/.openclaw/workspace 2>/dev/null | sed 's/^/  /'
du -sh $HOME/.openclaw/workspace/.git 2>/dev/null | sed 's/^/  /'
echo; echo "## 4. vhdx 膨胀比"
# 2026-10-22：发行版已从 D 盘迁到 X 盘，路径写死会失效 → 改为自动探测（先扫盘，再读注册表 BasePath）
V=""
for cand in /mnt/*/WSL/*/ext4.vhdx; do [ -f "$cand" ] && { V="$cand"; break; }; done
if [ -z "$V" ]; then
  PS=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
  if [ -f "$PS" ]; then
    BP=$("$PS" -NoProfile -Command "(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss\Ubuntu').BasePath" 2>/dev/null | tr -d '\r')
    case "$BP" in X:/*) V="/mnt/${BP#X:}" ; V="/mnt/$(echo "${BP#X:}" | tr '\\' '/')";; esac
    [ -f "$V" ] || V=""
  fi
fi
if [ -n "$V" ] && [ -f "$V" ]; then
  A=$(du -m --apparent-size "$V"|cut -f1); B=$(du -m "$V"|cut -f1)
  echo "  vhdx 位置：$V"
  echo "  vhdx 表观 ${A}M / 实占 ${B}M"
else
  echo "  vhdx：未找到（发行版不在预期位置？）—— 跑 sh tools/wsl-disk-health.sh 看详情"
fi
echo; echo "## 5. 备份归档数 (D/E/H)"
for m in d e h; do echo -n "  /mnt/$m: "; ls /mnt/$m/openclaw-backups/*.tar.gz 2>/dev/null | wc -l; done
echo; echo "## 6. >500M 大文件 (仅列，绝不删)"
find $HOME/.openclaw -xdev -type f -size +500M -printf '%s\\t%p\\n' 2>/dev/null | sort -rn | head -15 | numfmt --to=iec --field=1 | sed 's/^/  /'
echo; echo "## 7. NAS 可用"
timeout 15 ssh -o BatchMode=yes -o ConnectTimeout=8 nas 'df -h /volume1|tail -1' 2>/dev/null | sed 's/^/  /' || echo '  NAS 不可达'
echo; echo "## 8. 建议(人工判断，不自动执行)"
echo "  - 只列不改；任何清理走 E/H 回收站且需人工批准。"
} > "$OUT" 2>&1
echo "written: $OUT"
