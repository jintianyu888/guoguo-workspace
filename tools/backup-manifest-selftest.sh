#!/bin/bash
# backup-manifest-selftest.sh —— 备份清单大文件分片指纹自检（账本 #978）
# 覆盖：>阈值走 partial、小文件走全量、二次运行全复用、mtime 变化重算、partial 指纹可复现
set -u
W=/home/j/.openclaw/workspace
PY=$W/tools/backup-manifest.py
T=$(mktemp -d /tmp/mf-selftest.XXXXXX)
trap 'rm -rf "$T"' EXIT
fail=0
say() { echo "  $*"; }

# 1) 造数据：300MB「大文件」+ 2MB 小文件
truncate -s 300M "$T/big.tar.gz" || fail=1
head -c 2097152 /dev/urandom > "$T/small.tar.gz" || fail=1
printf 'TAILMARK' | dd of="$T/big.tar.gz" bs=1 seek=$((300*1024*1024-8)) conv=notrunc status=none

# 2) 首次运行：big 应 partial，small 应全量
out=$(python3 "$PY" --root "$T" --pattern ".tar.gz" --partial-over-gb 0.1 2>&1); rc=$?
say "首跑 rc=$rc : $out"
[ "$rc" = "0" ] || { say "❌ 首跑 rc 非 0"; fail=1; }

python3 - "$T" <<'EOF' || fail=1
import json, sys
T = sys.argv[1]
rows = {json.loads(l)["name"]: json.loads(l) for l in open(T + "/manifest.jsonl")}
b, s = rows.get("big.tar.gz"), rows.get("small.tar.gz")
ok = True
if not b or not b.get("partial"):
    print("  ❌ 大文件未标 partial"); ok = False
elif b.get("hash_method") != "sampled-v2":
    print("  ❌ hash_method 未标 sampled-v2"); ok = False
elif not (len(b.get("partial_sha256") or "") == 64):
    print("  ❌ partial_sha256 非法"); ok = False
elif b.get("sha256") is not None:
    print("  ❌ partial 记录不应带全量 sha256"); ok = False
else:
    print("  ✅ big partial=%s size=%s" % (b["partial_sha256"][:12], b["size"]))
if not s or len(s.get("sha256") or "") != 64 or s.get("partial"):
    print("  ❌ 小文件未走全量 sha256"); ok = False
else:
    print("  ✅ small 全量 sha256=%s" % s["sha256"][:12])
sys.exit(0 if ok else 1)
EOF
[ $? = 0 ] || fail=1

# 3) small 的 sha256 必须与 sha256sum 一致
want=$(sha256sum "$T/small.tar.gz" | cut -d' ' -f1)
got=$(python3 -c "import json;print([json.loads(l) for l in open('$T/manifest.jsonl') if 'small' in l][0]['sha256'])")
[ "$want" = "$got" ] && say "✅ 小文件哈希与 sha256sum 一致" || { say "❌ 小文件哈希不一致"; fail=1; }

# 4) partial 指纹可复现（独立用 dd+sha256sum 复算）
calc=$(python3 -c "
import hashlib, subprocess
p='$T/big.tar.gz'; size=300*1024*1024; c=64*1024*1024; n=min(c,size)
def span(off,ln):
    out=subprocess.run(['dd','if='+p,'bs=1M','skip=%d'%off,'count=%d'%ln,'iflag=skip_bytes,count_bytes'],capture_output=True).stdout
    return hashlib.sha256(out[:ln]).hexdigest()
spans=[(0,n),(max(0,size//2-n//2),n),(max(0,size-c),n)]
h=hashlib.sha256(); h.update(('size=%d;chunk=%d;method=sampled-v2;'%(size,c)).encode())
h.update('|'.join(span(o,l) for o,l in spans).encode())
print(h.hexdigest())")
[ "$calc" = "$(python3 -c "import json;print([json.loads(l) for l in open('$T/manifest.jsonl') if 'big' in l][0]['partial_sha256'])")" ]   && say "✅ partial 指纹可独立复现" || { say "❌ partial 指纹不可复现"; fail=1; }

# 5) 二次运行：必须全部复用（新算 0），且 partial 记录保持不走全量
out2=$(python3 "$PY" --root "$T" --pattern ".tar.gz" --partial-over-gb 0.1 2>&1)
echo "$out2" | grep -q "新算 0" && say "✅ 二次运行全复用" || { say "❌ 二次运行未全复用: $out2"; fail=1; }

# 6) mtime 变化 → big 重算且指纹变化
old=$(python3 -c "import json;print([json.loads(l) for l in open('$T/manifest.jsonl') if 'big' in l][0]['partial_sha256'])")
sleep 1; printf 'TAILMARK2' | dd of="$T/big.tar.gz" bs=1 seek=$((300*1024*1024-9)) conv=notrunc status=none
python3 "$PY" --root "$T" --pattern ".tar.gz" --partial-over-gb 0.1 >/dev/null 2>&1
new=$(python3 -c "import json;print([json.loads(l) for l in open('$T/manifest.jsonl') if 'big' in l][0]['partial_sha256'])")
[ "$old" != "$new" ] && say "✅ 尾部变化后指纹更新" || { say "❌ 尾部变化未更新指纹"; fail=1; }

# 7) 默认阈值下 300MB 文件仍走全量（回归：小盘行为不变）
rm -f "$T/manifest.jsonl"
python3 "$PY" --root "$T" --pattern ".tar.gz" >/dev/null 2>&1
python3 -c "
import json,sys
b=[json.loads(l) for l in open('$T/manifest.jsonl') if 'big' in l][0]
sys.exit(0 if (not b.get('partial') and len(b.get('sha256') or '')==64) else 1)"   && say "✅ 默认阈值下仍走全量哈希（行为兼容）" || { say "❌ 默认阈值行为异常"; fail=1; }

if [ "$fail" = "0" ]; then echo "SELFTEST PASS"; exit 0; else echo "SELFTEST FAIL"; exit 1; fi
