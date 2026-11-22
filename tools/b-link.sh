#!/bin/bash
# b-link.sh —— 把 B 机（192.168.1.107）的共享盘挂到 /mnt/b，供剪辑管家使用
# 用法：b-link.sh --user <Windows账号> --password <密码> [--share D$] [--host 192.168.1.107]
# 凭据写入 /home/j/.openclaw/workspace/state/secrets/b-smb.env（600），不回显
set -u
HOST=192.168.1.107
SHARE='D$'
USERNAME=""
PASSWORD=""
ENVF=/home/j/.openclaw/workspace/state/secrets/b-smb.env
MP=/mnt/b
while [ $# -gt 0 ]; do
  case "$1" in
    --user) USERNAME="$2"; shift 2;;
    --password) PASSWORD="$2"; shift 2;;
    --share) SHARE="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    *) echo "未知参数 $1"; exit 2;;
  esac
done
mkdir -p "$(dirname "$ENVF")"
if [ -n "$USERNAME" ] && [ -n "$PASSWORD" ]; then
  umask 077
  printf 'B_SMB_USER=%s\nB_SMB_PASS=%s\nB_SMB_HOST=%s\nB_SMB_SHARE=%s\n' "$USERNAME" "$PASSWORD" "$HOST" "$SHARE" > "$ENVF"
  chmod 600 "$ENVF"
  echo "凭据已保存（600，不回显）"
fi
[ -f "$ENVF" ] || { echo "缺少凭据：先跑 b-link.sh --user X --password Y"; exit 3; }
# shellcheck disable=SC1090
. "$ENVF"
# 生成 mount 用凭据文件（mount.cifs 不能直接吃变量）
CRED=/home/j/.openclaw/workspace/state/secrets/.b-smb.cred
umask 077
printf 'username=%s\npassword=%s\n' "$B_SMB_USER" "$B_SMB_PASS" > "$CRED"
chmod 600 "$CRED"
mkdir -p "$MP"
if mountpoint -q "$MP"; then
  echo "已挂载：$(mount | grep " $MP " | head -1)"
  exit 0
fi
echo "→ 尝试挂载 //$B_SMB_HOST/$B_SMB_SHARE 到 $MP"
if ! mount -t cifs "//$B_SMB_HOST/$B_SMB_SHARE" "$MP" -o "credentials=$CRED,uid=1000,gid=1000,iocharset=utf8,vers=3.0,soft,ro,nounix,noserverino" 2>/tmp/b-link.err; then
  echo "挂载失败：$(cat /tmp/b-link.err)"
  echo "常见原因：账号密码错 / 共享名不对 / B 的防火墙拦 445 / 该账号不是管理员（D\$ 需管理员）"
  exit 4
fi
echo "→ 挂载成功（只读），列目录："
ls "$MP" 2>/dev/null | head -8
echo "→ 校验读取："
find "$MP" -maxdepth 2 -type f 2>/dev/null | head -2
exit 0
