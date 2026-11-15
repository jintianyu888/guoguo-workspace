#!/bin/bash
# cross-audit-pack.sh v1.0 — 交叉互审输入包（零 token，2026-11-15 主公令）
# 配对: 果果<->Hermess / 维护<->备份 / 模型<->干活
set -uo pipefail
W=/home/j/.openclaw/workspace; D=$(date +%F)
MR=/home/j/openclaw-workspaces/work/state/self-review/self-review-$D.md
HR=/home/j/openclaw-workspaces/sheet-music/state/self-review/self-review-$D.md
OR=/home/j/.openclaw/workspace-model/state/self-review/$D.md
BR=/home/j/.openclaw/workspace-backup/state/self-review/$D.md
AR=/home/j/openclaw-workspaces/maint/state/self-review/self-review-$D.md
GA=$W/docs/开工清单-$D.md

bash $W/tools/butler-fact-pack.sh work >/dev/null 2>&1
bash $W/tools/butler-fact-pack.sh hermess >/dev/null 2>&1
bash $W/tools/butler-fact-pack.sh model >/dev/null 2>&1
bash $W/tools/butler-fact-pack.sh backup >/dev/null 2>&1
bash $W/tools/maint-selfreview-pack.sh >/dev/null 2>&1

mk() {
  out=$1; peer=$2; own=$3; oth=$4; extra=${5:-}
  { echo "# 互审输入 $D"; echo;
    echo "## 【自家事实包】"; head -c 5000 "$own" 2>/dev/null || echo "(缺)";
    if [ -n "$extra" ]; then echo; echo "## 【自家补充】"; head -c 2000 "$extra" 2>/dev/null || echo "(缺)"; fi
    echo; echo "## 【对家·$peer 事实包】"; head -c 5000 "$oth" 2>/dev/null || echo "(对家事实包缺失)";
  } > "$out" 2>&1
  printf "%-46s %sB\n" "$out" "$(stat -c%s "$out" 2>/dev/null || echo 0)"
}

mk /home/j/openclaw-workspaces/maint/state/self-review/audit-inputs.md 备份 "$AR" "$BR"
mk /home/j/.openclaw/workspace-backup/state/self-review/audit-inputs.md 维护 "$BR" "$AR"
mk /home/j/.openclaw/workspace-model/state/self-review/audit-inputs.md 干活 "$OR" "$MR"
mk /home/j/openclaw-workspaces/work/state/self-review/audit-inputs.md 模型 "$MR" "$OR"
mk /home/j/openclaw-workspaces/sheet-music/state/self-review/audit-inputs.md 果果 "$HR" "$GA"
mk $W/state/work/audit-inputs-main.md Hermess "$GA" "$HR"
