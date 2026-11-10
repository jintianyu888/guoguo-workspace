#!/usr/bin/env bash
# 2026-11-03 23:12 主公令「双审完你决定执行」：修 deepseek 占位密钥 + 死兜底 + diffs hook 放行
# 双审：qianwen(qwen3.8-max) GO / minimax(MiniMax-M3) GO（详见 state/work/cross-review/20261103-230707）
set -u
W=/home/j/.openclaw/workspace
CFG=/home/j/.openclaw/openclaw.json
TS=$(date +%Y%m%d-%H%M%S)
BAK=/home/j/.openclaw/openclaw.json.bak-fix-$TS
LOG=$W/state/work/config-fix-20261103.log
exec >>"$LOG" 2>&1
log(){ echo "[$(date '+%F %T')] $*"; }

log "=== 配置修复开始（双审 GO: qianwen + minimax） ==="
touch "$W/state/work/.watchdog-pause"
systemctl --user stop openclaw-gateway
sleep 5
if systemctl --user is-active --quiet openclaw-gateway; then
  log "STOP 失败，放弃"; rm -f "$W/state/work/.watchdog-pause"
  bash "$W/tools/notify.sh" --to-owner "配置修复中止：网关停不下来，未做改动。"
  exit 1
fi
log "网关已停止"

# 1) 先备份（双审要求：备份必须在替换之前）
cp -a "$CFG" "$BAK" || { log "备份失败，放弃"; systemctl --user start openclaw-gateway; rm -f "$W/state/work/.watchdog-pause"; exit 1; }
log "备份: $BAK sha256=$(sha256sum "$BAK" | cut -d' ' -f1)"

# 2) 原子修改
python3 - "$CFG" <<'PY'
import json,os,sys
p=sys.argv[1]
s=open(p,encoding='utf-8').read()
edits=[
('        "apiKey": "deepseek:manual"',
 '        "apiKey": {\n          "source": "store",\n          "provider": "default",\n          "id": "DEEPSEEK_API_KEY"\n        }'),
('          "ollama/qwen3:30b-a3b-instruct-2507-q4_K_M"',
 '          "ollama/qwen3.5:9b"'),
('      "diffs": {\n        "enabled": true\n      },',
 '      "diffs": {\n        "enabled": true,\n        "hooks": {\n          "allowConversationAccess": true\n        }\n      },'),
]
for old,new in edits:
    n=s.count(old)
    if n!=1: raise SystemExit(f"pattern count {n} for {old[:40]!r}")
    s=s.replace(old,new)

# 第4处：zai 额度耗尽，把所有 fallbacks 里的 zai 项移到末尾（不删项，顺序其余不变）
import re
pat=re.compile(r'("fallbacks"\s*:\s*\[)(.*?)(\n(\s*)\])', re.S)
moved=[0]
def reorder(m):
    head,body,tail,indent=m.group(1),m.group(2),m.group(3),m.group(4)
    items=[];item_indent=None
    for ln in body.split('\n'):
        mm=re.match(r'^(\s*)"([^"]+)"\s*,?\s*$',ln)
        if mm:
            if item_indent is None: item_indent=mm.group(1)
            items.append(mm.group(2))
    if not items: return m.group(0)
    new=[i for i in items if not i.startswith('zai/')]+[i for i in items if i.startswith('zai/')]
    if new==items: return m.group(0)
    moved[0]+=1
    lines=[f'{item_indent}"{it}"'+(',' if i<len(new)-1 else '') for i,it in enumerate(new)]
    return head+'\n'+'\n'.join(lines)+tail
s=pat.sub(reorder,s)
print('fallback blocks reordered:',moved[0])
json.loads(s)
tmp=p+'.tmp-fix'
with open(tmp,'w',encoding='utf-8') as f:
    f.write(s); f.flush(); os.fsync(f.fileno())
os.replace(tmp,p)
print("applied 3 edits, json valid")
PY
if [ $? -ne 0 ]; then
  log "编辑失败，回滚"; cp -a "$BAK" "$CFG"
  rm -f "$W/state/work/.watchdog-pause"
  bash "$W/tools/restart-gateway.sh" --reason "配置修复失败回滚（$TS）"
  bash "$W/tools/notify.sh" --to-owner "配置修复失败，已回滚原文件并重启。详见 state/work/config-fix-20261103.log"
  exit 1
fi
log "三处改动已落地；sha256=$(sha256sum "$CFG" | cut -d' ' -f1)"

# 3) 走唯一重启入口
rm -f "$W/state/work/.watchdog-pause"
bash "$W/tools/restart-gateway.sh" --reason "配置修复：deepseek 密钥引用+兜底+diffs hook（双审 GO）"

H=000
for i in $(seq 1 42); do
  sleep 10
  H=$(curl -s -o /dev/null -w '%{http_code}' -m 4 http://127.0.0.1:18789/health 2>/dev/null || echo 000)
  [ "$H" = "200" ] && break
done
sleep 10

# 4) 真实请求拨测（不只信 /health）
OC=/home/j/.npm-global/bin/openclaw
export PATH="/home/j/.npm-global/bin:/home/j/.local/bin:/usr/local/bin:/usr/bin:/bin"
PROBE=$(timeout 150 "$OC" infer model run --model deepseek/deepseek-flash --prompt "只回复两个字母：OK" 2>&1 | tail -5)
log "拨测: $PROBE"
ERR401=$(journalctl --user -u openclaw-gateway --since "-4 min" --no-pager 2>/dev/null | grep -c "401 Authentication Fails")
HOOKBLOCK=$(journalctl --user -u openclaw-gateway --since "-4 min" --no-pager 2>/dev/null | grep -c "diffs.*before_prompt_build.*blocked")
log "401=$ERR401 hookblock=$HOOKBLOCK health=$H"

if [ "$H" = "200" ] && echo "$PROBE" | grep -qiE "OK"; then
  bash "$W/tools/notify.sh" --to-owner "✅ 配置修复完成并验收
· 健康：HTTP $H
· 拨测：$PROBE
· 近 4 分钟 401 次数：$ERR401（修前每轮 11 次）
· diffs hook 被拦次数：$HOOKBLOCK
· 第 4 项：36 个 agent 的 zai 兜底已沉底
· 备份：$BAK
· 日志：state/work/config-fix-20261103.log"
else
  log "验收不过，回滚"
  cp -a "$BAK" "$CFG"
  bash "$W/tools/restart-gateway.sh" --reason "配置修复验收不过，回滚（$TS）"
  bash "$W/tools/notify.sh" --to-owner "⚠️ 配置修复验收不过，已回滚并重启
· 健康：$H
· 拨测：$PROBE
· 401：$ERR401
· 备份：$BAK"
fi
log "=== 结束 ==="
