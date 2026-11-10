#!/usr/bin/env bash
# backup-now.sh —— 一次性全家桶备份（主人令：立刻都备份上）
NAS=nas
SSH="ssh -o BatchMode=yes -o ConnectTimeout=15"
TS=$(date +%Y%m%d-%H%M)
LOG=/home/j/.openclaw/workspace/state/work/backup-now.log
echo "[$(date "+%F %T")] 开始全备 TS=$TS" >> $LOG
# ① 用户级配置 + .ssh 纳入 .openclaw（这样全量归档就能带上）
D=/home/j/.openclaw/backup-extra/full-$TS
mkdir -p "$D"
cp -a /home/j/.ssh "$D/" 2>/dev/null
for f in .npmrc .gitconfig .bashrc .profile; do [ -f "/home/j/$f" ] && cp -a "/home/j/$f" "$D/"; done
echo "① 用户配置/私钥已纳入: $(ls -1 "$D" | wc -l) 项" >> $LOG
# ② 全量归档（含 .openclaw 全部；排除已搬 E/H 的 18 个工作区）
ARCH_DIR=/home/j/.openclaw-archives-tmp
mkdir -p "$ARCH_DIR"
ARCH="$ARCH_DIR/$TS-openclaw-backup.tar.gz"
EXC=""
for w in calendar class-schedule cooking doll-brand fitness health-doudou health-self health-wife mom-health news piano-app piano-room print schedule-doudou script-mystery sheet-music tax wealth; do
  EXC="$EXC --exclude=.openclaw/workspace-$w"
done
tar czf "$ARCH" -C /home/j $EXC .openclaw 2>/dev/null
if [ ! -s "$ARCH" ]; then echo "② 归档失败（文件不存在或为空），终止" >> $LOG; exit 1; fi
echo "② 全量归档: $(du -h "$ARCH" | cut -f1)" >> $LOG
# ③ 推群晖（归档）
if timeout 300 $SSH $NAS "mkdir -p ~/archive/jinyu/openclaw-archives && cat > ~/archive/jinyu/openclaw-archives/$TS-openclaw-backup.tar.gz" < "$ARCH"; then
  echo "③ 归档已推群晖" >> $LOG
else
  echo "③ 归档推群晖失败（本地保留 $ARCH）" >> $LOG
fi
# ④ 我的脚本 + 我写的技能 → 群晖
cd /home/j/.openclaw/workspace && tar czf - tools --exclude="tools/asr-venv" --exclude="tools/ocr-venv" --exclude="tools/models" --exclude="__pycache__" 2>/dev/null | timeout 280 $SSH $NAS "mkdir -p ~/archive/jinyu/migrated-20261102/openclaw-repos/main && tar xzf - -C ~/archive/jinyu/migrated-20261102/openclaw-repos/main" 2>/dev/null
echo "④ 脚本已推群晖" >> $LOG
cd /home/j/.openclaw && tar czf - agents/main/agent/workshop-skills 2>/dev/null | timeout 180 $SSH $NAS "mkdir -p ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent && tar xzf - -C ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent" 2>/dev/null
echo "⑤ 技能已推群晖" >> $LOG
# ⑤ 22 个工作区镜像
timeout 280 python3 /home/j/.openclaw/workspace/tools/nas-sync-repos.py >> $LOG 2>&1
echo "⑥ 工作区镜像完成" >> $LOG
# ⑦ 核对
$SSH $NAS "echo -n \"  群晖归档数: \"; ls -1 ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null | wc -l; echo -n \"  群晖 tools: \"; ls -1 ~/archive/jinyu/migrated-20261102/openclaw-repos/main/tools/ 2>/dev/null | wc -l; echo -n \"  我写的技能: \"; ls -1d ~/archive/jinyu/migrated-20261102/openclaw-repos/main/agents/main/agent/workshop-skills/*/ 2>/dev/null | wc -l" >> $LOG 2>&1
echo "[$(date "+%F %T")] 全备结束 ✅" >> $LOG