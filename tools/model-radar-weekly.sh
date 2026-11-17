#!/bin/bash
# model-radar-weekly.sh v1.0 (2026-11-17) —— 每周一 09:00 雷达 + 额度快照，零 token
set -u
export PATH=/home/j/.npm-global/bin:/usr/local/bin:/usr/bin:/bin
W=/home/j/.openclaw/workspace
cd "$W" || exit 3
R=$(timeout 120 python3 tools/model-radar.py 2>&1 | tail -1)
# 2026-11-17 起：雷达顺带刷新模型统一账本，避免另开一个重复的发现任务
python3 tools/model-ledger.py sync-config >/dev/null 2>&1 || true
python3 tools/model-ledger.py quota >/dev/null 2>&1 || true
python3 tools/model-ledger.py promo-import >/dev/null 2>&1 || true
F=$(date +%F)
NEW=$(grep -c '^- ' "state/model-radar/$F.md" 2>/dev/null)
TOP=$(grep '^- ' "state/model-radar/$F.md" 2>/dev/null | head -4 | sed 's/^- //')
ECON=$(timeout 90 bash tools/model-econ.sh 2>&1 | grep -E 'DeepSeek|Kimi|GLM|M Plan|qianwen' | head -6)
MSG="【模型雷达·周一】$F
近30天相关新品 ${NEW} 条
${TOP}
—— 额度 ——
${ECON}
结论任务：模型管家 24h 内挑 3 个候选出对比，果果 48h 内拍板（判据见 docs/模型更新与分工-v1.0-20261117.md）"
bash tools/notify.sh "$MSG" >/dev/null 2>&1 || true
echo "$(date '+%F %T') $R new=$NEW" >> state/work/model-radar.log
exit 0