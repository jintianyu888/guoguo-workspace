#!/usr/bin/env bash
# community-scan.sh — 每周扫一次 OpenClaw 社区生态（ClawHub 插件 / awesome 列表 / 官方版本）
# 设计：只报增量。首次运行建立基线（全部记为已知，不刷屏）。
# 用法: bash tools/community-scan.sh [--baseline]
# 退出码恒 0（网络失败只降级提示，不制造假告警）
set -u
cd "$(dirname "$0")/.." || exit 0

STATE="state/community-scan"
mkdir -p "$STATE"
PLUG="$STATE/plugins.tsv"      # name<TAB>version
AWES="$STATE/awesome.txt"      # 每条一行：条目名
VER="$STATE/version.txt"       # 上次看到的版本
LOG="$STATE/last-run.log"
export PATH="/home/j/.npm-global/bin:$PATH"

is_baseline=0
[ "${1:-}" = "--baseline" ] && is_baseline=1
[ -f "$PLUG" ] || is_baseline=1
[ -f "$AWES" ] || is_baseline=1

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ---------- 1) ClawHub 插件 ----------
: > "$TMP/plugins.raw"
for kw in backup monitor music memory feishu audit; do
  timeout 80 openclaw plugins search "$kw" 2>/dev/null \
    | grep -E '^[^ ]+ +(code-plugin|bundle-plugin|skill|plugin)' \
    >> "$TMP/plugins.raw"
done
# 归一化: 名称<TAB>版本
awk '{name=$1; ver="";
      for(i=1;i<=NF;i++){ if($i ~ /^v[0-9]+\.[0-9]+\.[0-9]+$/){ver=$i; break} }
      desc=""; p=index($0,"—"); if(p>0) desc=substr($0,p+3,120);
      gsub(/^[ \t]+|[ \t]+$/,"",desc);
      print name"\t"ver"\t"desc}' "$TMP/plugins.raw" \
  | sort -u -k1,1 > "$TMP/plugins.now"

if [ "$is_baseline" = 1 ] || [ ! -s "$PLUG" ]; then
  cp "$TMP/plugins.now" "$PLUG"
  new_plugins=0; upd_plugins=0
else
  awk -F'\t' 'NR==FNR{old[$1]=$2; next} {
      if(!($1 in old)) print "NEW\t"$0;
      else if($2!="" && old[$1]!="" && $2!=old[$1]) print "UPD\t"$1"\t"$2"\t"old[$1]"\t"$3
    }' "$PLUG" "$TMP/plugins.now" > "$TMP/plugins.diff"
  new_plugins=$(grep -c '^NEW' "$TMP/plugins.diff" 2>/dev/null || true)
  upd_plugins=$(grep -c '^UPD' "$TMP/plugins.diff" 2>/dev/null || true)
  new_plugins=${new_plugins:-0}; upd_plugins=${upd_plugins:-0}
  cp "$TMP/plugins.now" "$PLUG"
fi

# ---------- 2) awesome-openclaw 列表 ----------
if timeout 40 curl -fsSL --max-time 35 \
     "https://raw.githubusercontent.com/alvinreal/awesome-openclaw/main/README.md" \
     -o "$TMP/awesome.md" 2>/dev/null && [ -s "$TMP/awesome.md" ]; then
  grep -oE '^\s*[-*]\s*\[[^]]+\]' "$TMP/awesome.md" \
    | sed -E 's/^\s*[-*]\s*\[//; s/\]$//' | sort -u > "$TMP/awesome.now"
  if [ -s "$AWES" ]; then
    comm -13 "$AWES" "$TMP/awesome.now" > "$TMP/awesome.new"
    new_awesome=$(wc -l < "$TMP/awesome.new" | tr -d ' ')
  else
    : > "$TMP/awesome.new"; new_awesome=0
  fi
  cp "$TMP/awesome.now" "$AWES"
  awesome_ok=1
else
  : > "$TMP/awesome.new"; new_awesome="?"; awesome_ok=0
fi

# ---------- 3) 官方版本 ----------
cur_ver=$(openclaw --version 2>/dev/null | grep -oE '[0-9]{4}\.[0-9]+\.[0-9]+' | head -1)
last_ver=$(cat "$VER" 2>/dev/null | tr -d '\n')
if [ -n "$cur_ver" ] && [ "$cur_ver" != "$last_ver" ]; then
  ver_line="$cur_ver（上次 ${last_ver:-无}）"
  [ -n "$cur_ver" ] && printf '%s' "$cur_ver" > "$VER"
else
  ver_line="${cur_ver:-未知}（无变化）"
fi

# ---------- 4) 汇总输出 ----------
{
  echo "== 社区扫描 $(date '+%F %H:%M') =="
  echo "插件: 新增 ${new_plugins} / 版本更新 ${upd_plugins}（共 $(wc -l < "$TMP/plugins.now" | tr -d ' ') 条跟踪）"
  # 2026-11-01: 原来 head -12/-8 会截断新增列表（本次 20 条只显示 12），改为全量（上限 40/20 防刷屏）
  grep '^NEW' "$TMP/plugins.diff" 2>/dev/null | head -40 | awk -F'\t' '{printf "  + %s %s — %s\n",$2,$3,$4}'
  grep '^UPD' "$TMP/plugins.diff" 2>/dev/null | head -20 | awk -F'\t' '{printf "  ~ %s %s→%s — %s\n",$2,$4,$3,$5}'
  echo "awesome 列表: 新增 ${new_awesome} 条"
  if [ "$new_awesome" != "?" ] && [ "${new_awesome:-0}" -gt 0 ] 2>/dev/null; then
    head -10 "$TMP/awesome.new" | sed 's/^/  + /'
  fi
  [ "$awesome_ok" = 0 ] && echo "  (awesome 列表拉取失败，本次跳过)"
  echo "官方版本: ${ver_line}"
} | tee "$LOG"
