#!/bin/bash
# b-link-root.sh —— 以 root 运行：把 B 机共享挂到 /mnt/b 并写入 fstab（凭据文件由 j 用户先建好）
set -u
ENVF=/home/j/.openclaw/workspace/state/secrets/b-smb.env
CRED=/home/j/.openclaw/workspace/state/secrets/.b-smb.cred
MP=/mnt/b
[ -f "$ENVF" ] || { echo "缺少 $ENVF"; exit 3; }
. "$ENVF"
umask 077
printf 'username=%s\npassword=%s\n' "$B_SMB_USER" "$B_SMB_PASS" > "$CRED"
chmod 600 "$CRED"
# 2026-11-23 修：root 运行会把凭据文件建成 root:root，备份(j 用户)读不了 → 打包 EACCES 三连败；写完归还 j 属主
chown j:j "$CRED" 2>/dev/null || true
mkdir -p "$MP"
if mountpoint -q "$MP"; then echo "已挂载"; mount | grep " $MP "; exit 0; fi
if ! mount -t cifs "//$B_SMB_HOST/$B_SMB_SHARE" "$MP" -o "credentials=$CRED,uid=1000,gid=1000,iocharset=utf8,vers=3.0,nofail,noserverino,_netdev" 2>/tmp/b-link-root.err; then
  echo "挂载失败：$(cat /tmp/b-link-root.err)"; exit 4
fi
LINE="//$B_SMB_HOST/$B_SMB_SHARE $MP cifs credentials=$CRED,uid=1000,gid=1000,vers=3.0,iocharset=utf8,nofail,noserverino,_netdev 0 0"
grep -qF "$MP cifs" /etc/fstab || { cp /etc/fstab /etc/fstab.bak-$(date +%Y%m%d-%H%M%S); echo "$LINE" >> /etc/fstab; echo "已写 fstab"; }
echo "挂载成功："
ls "$MP" | head -10
echo "写测试："
T="$MP/.oc-write-test-$(date +%s)"
if touch "$T" 2>/dev/null; then echo "可写 OK"; rm -f "$T"; else echo "只读（如需写回，要把共享权限放开）"; fi
exit 0
