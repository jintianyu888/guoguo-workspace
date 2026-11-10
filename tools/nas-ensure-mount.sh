#!/bin/bash
# nas-ensure-mount.sh —— GuoGuoNAS 挂载健康兜底（v2，双审后修订）
# 语义：0=健康或已恢复  2=设备找不到  3=设备在但重挂失败  4=地址漂移需人工 sudo
set -uo pipefail
MNT="${NAS_MNT:-/mnt/nas}"
EXPECT_FP="${NAS_EXPECT_FP:-3054366ADF08CBDF7AE4594CB71D26C70713EDA99679D4D2711A972358CD1EA2}"
SUBNET="${NAS_SUBNET:-192.168.1}"
SHARE_NAME="${NAS_SHARE_NAME:-home}"
WS="/home/j/.openclaw/workspace"
LOG="$WS/state/nas-mount-health.log"
LASTIP_FILE="$WS/state/nas-last-ip"
STAGE="$HOME/.nas-remount.sh"
LOCK="/tmp/nas-ensure-mount.lock"
mkdir -p "$(dirname "$LOG")"
log() { printf "%s %s\n" "$(date "+%F %T")" "$*" >> "$LOG"; }
alert() {
  # 2026-11-01：同一条掉挂告警 30 分钟内只发一次，避免每 10 分钟轰炸
  local now last fp_new fp_old
  local DEDUPE="$WS/state/nas-alert-dedupe"
  now=$(date +%s)
  fp_new=$(printf "%s" "$*" | md5sum | cut -c1-12)
  fp_old=""; last=0
  [ -f "$DEDUPE" ] && { fp_old=$(cut -d' ' -f1 "$DEDUPE" 2>/dev/null); last=$(cut -d' ' -f2 "$DEDUPE" 2>/dev/null); }
  case "$last" in ''|*[!0-9]*) last=0;; esac
  if [ "$fp_new" = "$fp_old" ] && [ $((now-last)) -lt 1800 ]; then
    log "ALERT-SUPPRESSED $*"
    return 0
  fi
  log "ALERT $*"
  if [ -x "$WS/tools/notify.sh" ]; then
    if timeout 40 bash "$WS/tools/notify.sh" --alert "NAS告警：$*" >/dev/null 2>&1 || timeout 40 bash "$WS/tools/notify.sh" "NAS告警：$*" >/dev/null 2>&1; then
      mkdir -p "$WS/state" 2>/dev/null
      # 原子写，避免并发/中断留下半截状态
      printf '%s %s\n' "$fp_new" "$now" > "$DEDUPE.tmp.$$" 2>/dev/null && mv -f "$DEDUPE.tmp.$$" "$DEDUPE" 2>/dev/null || true
    fi
  fi
}
exec 9>"$LOCK" || exit 0
flock -n 9 || { log "SKIP 已有实例在跑"; exit 0; }
healthy() {
  timeout 5 mountpoint -q "$MNT" 2>/dev/null || return 1
  timeout 10 stat "$MNT" >/dev/null 2>&1 || return 1
  local t="$MNT/.nas-health-probe"
  timeout 15 bash -c ": > \"$t\"" >/dev/null 2>&1 || return 1
  timeout 10 rm -f "$t" >/dev/null 2>&1
  return 0
}
cur_ip() { mount | grep -F " on $MNT " 2>/dev/null | sed -n "s/.*addr=\([0-9.]*\).*/\1/p" | head -1; }
# 2026-11-02 新增：身份标记校验。多网口同证书时只靠指纹分不清是谁，故要求共享根
# .guoguo-nas-id 内含 fp=<EXPECT_FP>。策略：标记“存在但不符”=拒绝该候选；
# 标记文件缺失=按“证书指纹+写探测”通过但记 WARN（避免标记被人删掉后永远无法自愈）。
id_state() {  # 输出 match / mismatch / missing
  local v
  v="$(timeout 10 cat "$MNT/.guoguo-nas-id" 2>/dev/null | tr -d '\r')"
  if [ -z "$v" ]; then
    timeout 10 test -e "$MNT/.guoguo-nas-id" 2>/dev/null && { echo mismatch; return 0; }
    echo missing; return 0
  fi
  case "$v" in *"fp=$EXPECT_FP"*) echo match;; *) echo mismatch;; esac
}
fstab_src() { awk -v m="$MNT" '$0 !~ /^[[:space:]]*#/ && $2==m {print $1; exit}' /etc/fstab 2>/dev/null; }
fp_of() {
  local out rc
  out="$(timeout 8 openssl s_client -connect "$1:5001" -servername "$1" </dev/null 2>/dev/null)" || return 1
  [ -n "$out" ] || return 1
  printf "%s" "$out" | openssl x509 -noout -fingerprint -sha256 2>/dev/null | sed "s/.*=//" | tr -d ":[:space:]" | tr "a-f" "A-F"
}
find_nas() {
  # 2026-11-01 双审后收紧：并发上限 24（避免 254 个 ip 同时开子进程造成连接风暴），
  # 单目标探测 1s、证书指纹 8s，最坏总耗时约 20~30s
  export -f fp_of 2>/dev/null || true
  export SUBNET EXPECT_FP
  seq 1 254 | sed "s|^|$SUBNET.|" | xargs -P 24 -I{} bash -c '
    ip="{}"
    timeout 1 bash -c "echo > /dev/tcp/$ip/5001" 2>/dev/null || exit 0
    fp="$(fp_of "$ip")" || exit 0
    [ -n "$fp" ] && [ "$fp" = "$EXPECT_FP" ] && printf "%s\n" "$ip"
  ' 2>/dev/null
}
if healthy; then
  IP="$(cur_ip)"; [ -n "$IP" ] && printf "%s\n" "$IP" > "$LASTIP_FILE"
  log "OK mounted ip=${IP:-unknown}"
  exit 0
fi
log "DOWN $MNT 不可用，开始全网段查找 GuoGuoNAS"
# 2026-11-01 修复：FOUNDS 从未初始化 + find_nas 从未被调用，set -u 下引用即崩，
# 导致“设备离线”这条路既不告警也不重挂（今晚 11 次 DOWN / 0 次 ALERT）。
FOUNDS="$(find_nas)"
FOUNDS="${FOUNDS:-}"
# 排除别名地址（Windows 主机端口映射 5001→NAS 时也会响应同一证书）
SKIP_FILE="/home/j/.openclaw/workspace/state/nas-skip-ips"
if [ -f "$SKIP_FILE" ]; then
  while read -r skip_ip; do
    [ -n "$skip_ip" ] || continue
    FOUNDS="$(printf "%s\n" "${FOUNDS:-}" | grep -v "^${skip_ip}$" || true)"
  done < "$SKIP_FILE"
fi
COUNT="$(printf "%s" "${FOUNDS:-}" | grep -c . || true)"
if [ "$COUNT" -eq 0 ]; then
  alert "$MNT 掉挂，未找到 GuoGuoNAS（指纹不匹配或设备离线），请检查电源与网线"
  exit 2
fi
# 记录地址：优先 nas-last-ip，其次 fstab 里同网段的地址
OLD="$(cat "$LASTIP_FILE" 2>/dev/null || true)"
FIP="$(fstab_src | grep -oE "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+" | head -1)"
[ -z "$OLD" ] && OLD="${FIP:-}"
# 候选排序：记录地址优先，其余按末段 IP 升序（同机双网口连号时顺序稳定）
ORDER=""
[ -n "$OLD" ] && ORDER="$OLD"
for ip in $(printf "%s\n" "${FOUNDS:-}" | grep -E "^[0-9.]+$" | awk "!seen[\$0]++" | sort -t. -k4,4n); do
  case " $ORDER " in *" $ip "*) ;; *) ORDER="$ORDER $ip";; esac
done
ORDER="$(printf "%s" "$ORDER" | sed "s/^ *//")"
log "FOUND ${COUNT} 个候选：$ORDER（记录地址 ${OLD:-unknown}，fstab 源 ${FIP:-none}）"
ROOTCAND=""
for ip in $ORDER; do
  if [ "$ip" = "${FIP:-}" ]; then
    # 与 fstab 同源：因 nofail,user，本用户可自行 mount/umount
    timeout 30 mount "$MNT" >/dev/null 2>&1 || true
    if healthy; then
      ST="$(id_state)"
      case "$ST" in
        match)
          printf "%s\n" "$ip" > "$LASTIP_FILE.tmp.$$" && mv -f "$LASTIP_FILE.tmp.$$" "$LASTIP_FILE"
          log "RECOVERED 已挂载 $ip（身份标记通过）"
          alert "$MNT 已恢复：$ip（身份标记通过）"
          exit 0;;
        missing)
          # 注意：此分支只发生在“候选= fstab 源”的情况下，等价于开机时 mount -a，
          # 没有切换数据源，故允许按证书+写探测认定恢复；标记缺失单独告警要求补写。
          printf "%s\n" "$ip" > "$LASTIP_FILE.tmp.$$" && mv -f "$LASTIP_FILE.tmp.$$" "$LASTIP_FILE"
          log "WARN $ip 已挂载但身份标记缺失（同源恢复，未切源），提醒补写标记"
          alert "$MNT 已恢复：$ip（身份标记缺失，请补写 $MNT/.guoguo-nas-id）"
          exit 0;;
        *)
          log "REJECT $ip 已挂载但身份标记不符，卸掉换下一个候选"
          timeout 15 umount "$MNT" >/dev/null 2>&1 || timeout 15 umount -l "$MNT" >/dev/null 2>&1
          ;;
      esac
    else
      log "FAIL $ip（fstab 源）重挂失败"
    fi
  else
    # 非 fstab 源：挂载需 root，先记为 root 候选，等用户态全部试完再发脚本
    [ -n "$ROOTCAND" ] || ROOTCAND="$ip"
  fi
done
if [ -n "$ROOTCAND" ]; then
  umask 077
  {
    echo "#!/bin/bash"
    echo "# 由 nas-ensure-mount.sh 生成 $(date '+%F %T')：root 下按序择一挂载"
    echo "# 顺序：挂载 → 写探测 → 身份标记 → 精确改 fstab（唯一行校验+备份校验+失败回滚）"
    echo "set -u"
    echo "MNT=\"$MNT\"; CRED=/home/j/.nas-creds; SHARE=\"$SHARE_NAME\"; FP=\"$EXPECT_FP\""
    echo "OPT=\"credentials=/home/j/.nas-creds,uid=1000,gid=1000,vers=3.0,iocharset=utf8,nofail,user,noserverino\""
    echo "LASTIP_FILE=\"$LASTIP_FILE\""
    echo "CANDS=\"$ORDER\""
    cat <<'STAGEBODY'
umask 077
exec 9>/tmp/nas-remount.lock
flock -n 9 || { echo "SKIP 另一个 root 挂载脚本正在运行"; exit 3; }
for ip in $CANDS; do
  timeout 10 umount -l "$MNT" >/dev/null 2>&1 || true
  if ! timeout 30 mount -t cifs "//$ip/$SHARE" "$MNT" -o "$OPT" >/dev/null 2>&1; then
    echo "FAIL $ip 挂载失败"; continue
  fi
  if ! timeout 5 bash -c ": > \"$MNT/.nas-health-probe\"" >/dev/null 2>&1; then
    timeout 10 umount -l "$MNT" >/dev/null 2>&1; echo "FAIL $ip 写探测失败"; continue
  fi
  rm -f "$MNT/.nas-health-probe" 2>/dev/null || true
  if ! timeout 10 grep -q "fp=$FP" "$MNT/.guoguo-nas-id" 2>/dev/null; then
    timeout 10 umount -l "$MNT" >/dev/null 2>&1
    echo "FAIL $ip 身份标记缺失或不符（切源必须标记校验通过）"; continue
  fi
  BAK="/etc/fstab.bak-drift-$(date +%Y%m%d%H%M%S)"
  if ! cp -a /etc/fstab "$BAK"; then echo "FAIL 备份 fstab 失败，放弃"; timeout 10 umount -l "$MNT" >/dev/null 2>&1; exit 4; fi
  if ! cmp -s /etc/fstab "$BAK"; then echo "FAIL fstab 备份校验不一致，放弃"; timeout 10 umount -l "$MNT" >/dev/null 2>&1; exit 4; fi
  N=$(awk -v m="$MNT" '$0 !~ /^[[:space:]]*#/ && $2==m {n++} END{print n+0}' /etc/fstab)
  if [ "$N" != "1" ]; then echo "FAIL fstab 中 $MNT 命中 $N 行（要求正好 1 行），fstab 未改，$ip 保持已挂载"; exit 4; fi
  if ! awk -v m="$MNT" -v src="//$ip/$SHARE" -v opts="$OPT" '
      $0 !~ /^[[:space:]]*#/ && $2==m { print src " " m " cifs " opts " 0 0"; next }
      { print }
    ' /etc/fstab > "/etc/fstab.new.$$"; then echo "FAIL 生成新 fstab 失败，fstab 未改，$ip 保持已挂载"; exit 4; fi
  if ! mv -f "/etc/fstab.new.$$" /etc/fstab; then echo "FAIL 替换 fstab 失败，恢复备份"; cp -a "$BAK" /etc/fstab; exit 4; fi
  if ! mountpoint -q "$MNT" 2>/dev/null; then echo "FAIL 改写后挂载点异常，回滚 fstab"; cp -a "$BAK" /etc/fstab; exit 4; fi
  printf "%s\n" "$ip" > "$LASTIP_FILE.tmp.$$" && mv -f "$LASTIP_FILE.tmp.$$" "$LASTIP_FILE"
  chown 1000:1000 "$LASTIP_FILE" 2>/dev/null || true
  echo "OK $ip 已挂载并通过身份校验，fstab 已更新（备份 $BAK）"; exit 0
done
echo "FAIL 所有候选均未通过（挂载/写探测/身份标记）"; exit 2
STAGEBODY
  } > "$STAGE.tmp.$$" || { rm -f "$STAGE.tmp.$$"; log "FAIL 生成 root 脚本失败"; alert "$MNT 掉挂且 root 脚本生成失败，需人工检查"; exit 3; }
  chmod 700 "$STAGE.tmp.$$" && mv -f "$STAGE.tmp.$$" "$STAGE" || { rm -f "$STAGE.tmp.$$"; log "FAIL 安装 root 脚本失败"; alert "$MNT 掉挂且 root 脚本落盘失败，需人工检查"; exit 3; }
  log "STAGE root 脚本已生成，候选：$ORDER"
  alert "$MNT 掉挂：$COUNT 个同指纹地址（$ORDER），用户态无法切源，需执行 sudo bash $STAGE 完成择一挂载"
  exit 4
fi
alert "$MNT 掉挂，设备在线（$ORDER）但重挂失败或身份标记不符，可能是共享名/权限/凭据变化"
exit 3
