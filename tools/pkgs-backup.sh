#!/bin/sh
# pkgs-backup.sh v2 —— 安装包/模型备份到群晖（用已验证的 ssh+cat 方式，NAS 不支持 rsync）
# 2026-09-28 主公令：下载过的安装包与模型都要备份，下次不用重下；本任务已加入备份体系
W=/home/j/.openclaw/workspace
NAS=nas
DEST=/volume1/homes/guoguonas/archive/jinyu/migrated-20261102/openclaw-repos/pkgs
MAN=$W/state/pkgs-manifest.txt
LOG=$W/state/pkgs-backup.log
TS=$(date "+%F %T")
WK=$(date "+%Y-W%V")
echo "[$TS] 开始 v2" >> $LOG

# 1) 清单
{
  echo "# 安装包/模型清单  $TS"
  for V in asr-venv ocr-venv embed-venv; do
    [ -x "$W/tools/$V/bin/pip" ] && { echo "### $V"; "$W/tools/$V/bin/pip" freeze 2>/dev/null; echo; }
  done
  echo "## 本地模型"
  du -sh "$W"/tools/models/* 2>/dev/null
  echo "## wheelhouse"
  ls -lh "$W"/tools/wheelhouse/*.whl 2>/dev/null | awk "{print \$5, \$9}"
} > "$MAN" 2>/dev/null

# 2) 收集 /tmp 里下过的 wheel
mkdir -p "$W/tools/wheelhouse"
for F in /tmp/*.whl; do [ -f "$F" ] && cp -n "$F" "$W/tools/wheelhouse/" 2>/dev/null; done

# 3) 打包（模型 + wheelhouse + 清单）
DL=$W/state/dl; mkdir -p "$DL"
PKG=$DL/pkgs-$WK.tar   # 2026-09-28: 改到磁盘目录（/tmp 是 RAM 盘，之前把它写满了）
tar -cf "$PKG" -C "$W/tools" models wheelhouse 2>>$LOG
tar -rf "$PKG" -C "$W/state" pkgs-manifest.txt 2>>$LOG
SZ=$(du -h "$PKG" 2>/dev/null | cut -f1)
echo "[$TS] 打包完成 $PKG ($SZ)" >> $LOG

# 4) 推到群晖（ssh+cat，NAS 不支持 rsync）
ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "mkdir -p $DEST" || { echo "[$TS] SSH 失败" >> $LOG; exit 1; }
cat "$PKG" | ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "cat > $DEST/pkgs-$WK.tar" || { echo "[$TS] 传输失败" >> $LOG; exit 1; }
cat "$MAN" | ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "cat > $DEST/pkgs-manifest.txt"

# 5) 自证
GOT=$(ssh -o BatchMode=yes -o ConnectTimeout=15 "$NAS" "stat -c%s $DEST/pkgs-$WK.tar 2>/dev/null; ls -1 $DEST | head -n 8" 2>/dev/null)
echo "[$TS] NAS 侧: $GOT" >> $LOG
echo "[$TS] 结束" >> $LOG
rm -f "$PKG"