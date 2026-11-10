#!/usr/bin/env bash
# backup-space.sh v2 —— 备份「空间 + 时间日期」一览（供日报/周报/月报/年报引用）
SSH='ssh -o BatchMode=yes -o ConnectTimeout=10'
NAS=nas
TOTAL=0
human(){ awk -v k="$1" 'BEGIN{split("B KB MB GB TB",u," ");i=1;while(k>=1024&&i<5){k/=1024;i++}printf "%.1f %s",k,u[i]}'; }
sz(){ du -sb "$1" 2>/dev/null | cut -f1; }
mt(){ ls -t $1 2>/dev/null | head -1 | sed -E 's#.*/##; s#^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2}).*#\1 \2:\3#'; }

# 逐份列出：时间 + 单份大小
list_each(){
  local dir="$1" pat="$2" indent="${3:-    }"
  ls -1t $pat 2>/dev/null | while read -r f; do
    b=$(basename "$f")
    t=$(echo "$b" | sed -E 's#^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2}).*#\1 \2:\3#')
    [ "$t" = "$b" ] && t=$(stat -c %y "$f" 2>/dev/null | cut -c1-16)
    sz=$(du -sh "$f" 2>/dev/null | cut -f1)
    echo "${indent}· $t   $sz"
  done
}

echo "🗄️ 备份一览（空间 + 时间）· 生成于 $(date '+%Y-%m-%d %H:%M')"
E1=$(sz /mnt/e/openclaw-backups); E1=${E1:-0}; TOTAL=$((TOTAL+E1))
echo "  ① E盘本机归档 /mnt/e/openclaw-backups  $(human $E1) · $(ls /mnt/e/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 份 · 最新 $(mt '/mnt/e/openclaw-backups/*.tar.gz')"
B=$(sz /mnt/d/openclaw-backups); B=${B:-0}; TOTAL=$((TOTAL+B))
echo "  ② D盘归档  /mnt/d/openclaw-backups  $(human $B) · $(ls /mnt/d/openclaw-backups/*.tar.gz 2>/dev/null|wc -l) 份 · 最新 $(mt '/mnt/d/openclaw-backups/*.tar.gz')"
list_each /mnt/d/openclaw-backups '/mnt/d/openclaw-backups/*.tar.gz'
C=$(sz /home/j/openclaw-backup-repo); C=${C:-0}; TOTAL=$((TOTAL+C))
echo "  ③ 近实时 DB 仓 /home/j/openclaw-backup-repo  $(human $C) · 最后提交 $(git -C /home/j/openclaw-backup-repo log -1 --date=format:'%Y-%m-%d %H:%M' --format='%cd' 2>/dev/null)"
N=$($SSH "$NAS" 'du -sb ~/archive/jinyu/openclaw-archives 2>/dev/null|cut -f1' 2>/dev/null | tr -d '\r' | tail -1)
if [ -n "$N" ]; then
  TOTAL=$((TOTAL+N))
  NC=$($SSH "$NAS" 'ls ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null|wc -l' 2>/dev/null|tr -d '\r'|tail -1)
  NM=$($SSH "$NAS" 'ls -t ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null|head -1' 2>/dev/null|tr -d '\r'|tail -1|sed -E 's#.*/([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2}).*#\1 \2:\3#')
  echo "  ④ 群晖全量归档 ~/archive/jinyu/openclaw-archives        $(human $N) · ${NC:-?} 份 · 最新 ${NM:-?}"
  $SSH "$NAS" 'ls -1t ~/archive/jinyu/openclaw-archives/*.tar.gz 2>/dev/null | while read f; do b=$(basename $f); t=$(echo $b | sed -E "s#^([0-9]{4}-[0-9]{2}-[0-9]{2})T([0-9]{2})-([0-9]{2}).*#\\1 \\2:\\3#"); s=$(du -sh $f | cut -f1); echo "    · $t   $s"; done' 2>/dev/null | grep -v WARNING
  G=$($SSH "$NAS" 'du -sb ~/archive/jinyu/migrated-20261102/openclaw-backup.git 2>/dev/null|cut -f1' 2>/dev/null|tr -d '\r'|tail -1); G=${G:-0}; TOTAL=$((TOTAL+G))
  GM=$($SSH "$NAS" 'cd openclaw-backup.git && git log -1 --date=format:%Y-%m-%d\ %H:%M --format=%cd 2>/dev/null' 2>/dev/null|tr -d '\r'|tail -1)
  echo "  ⑤ 群晖 DB 仓  ~/archive/jinyu/migrated-20261102/openclaw-backup.git      $(human $G) · 最后提交 ${GM:-?}"
  W=$($SSH "$NAS" 'du -sb ~/archive/jinyu/migrated-20261102/openclaw-repos 2>/dev/null|cut -f1' 2>/dev/null|tr -d '\r'|tail -1); W=${W:-0}; TOTAL=$((TOTAL+W))
  [ "${W:-0}" -gt 0 ] && echo "  ⑥ 群晖工作区镜像 ~/archive/jinyu/migrated-20261102/openclaw-repos        $(human $W)"
else
  echo "  ④⑤⑥ 群晖：❌ 不可达 —— 空间与时间未计入，需人工核对"
fi
echo "  ── 备份占用合计：$(human $TOTAL)"
