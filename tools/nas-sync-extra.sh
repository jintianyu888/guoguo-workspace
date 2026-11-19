#!/usr/bin/env bash
# nas-sync-extra.sh —— 补同步：把 [我的脚本] 和 [我写的技能] 推到群晖镜像
# 2026-09-26 新增：修复"今日新写的东西当天进不了群晖"的缺口
NAS=nas
W=/home/j/.openclaw/workspace
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"
echo "[$(date "+%F %T")] 补同步开始"
# ① 我的脚本（排除大件：venv/模型/缓存）
tar czf - -C "$W" tools \
  --exclude="tools/asr-venv" --exclude="tools/ocr-venv" \
  --exclude="tools/models" --exclude="__pycache__" 2>/dev/null \
  | timeout 280 $SSH $NAS "mkdir -p ~/archive/jinyu/migrated-20261102/openclaw-repos/main && tar xzf - -C ~/archive/jinyu/migrated-20261102/openclaw-repos/main" 2>/dev/null \
  && echo "  ✅ tools 已同步（不含 venv/模型）" || echo "  ❌ tools 同步失败"
# ② 我写的技能
tar czf - -C /home/j/.openclaw agents/main/agent/workshop-skills 2>/dev/null \
  | timeout 180 $SSH $NAS "mkdir -p ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent && tar xzf - -C ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent" 2>/dev/null \
  && echo "  ✅ workshop-skills 已同步" || echo "  ❌ 技能同步失败"
# ③ 核对
$SSH $NAS "echo -n \"  群晖 tools 数: \"; ls -1 ~/archive/jinyu/migrated-20261102/openclaw-repos/main/tools/ 2>/dev/null | wc -l; echo -n \"  技能数: \"; ls -1d ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent/workshop-skills/*/ 2>/dev/null | wc -l" 2>/dev/null
echo "[$(date "+%F %T")] 补同步结束"