#!/usr/bin/env bash
# xhs-verify-on-login.sh —— 等主公扫码成功后自动验证搜谱链路，并把结果推给主公
set -u
W=/home/j/.openclaw/workspace
OK=$W/state/xhs/login-ok.txt
LOG=$W/state/xhs/verify.log
: > "$LOG"
for i in $(seq 1 75); do
  if [ -f "$OK" ]; then
    sleep 3
    OUT=$(cd $W && bash tools/xhs-score.sh "起风了 钢琴谱" --limit 5 2>&1)
    echo "$OUT" > $W/state/xhs/verify-result.json
    CNT=$(printf '%s' "$OUT" | python3 -c "import sys,json;
raw=sys.stdin.read()
try:
    d=json.loads(raw); print(d.get('count',0) if d.get('ok') else 'ERR')
except Exception: print('PARSE_ERR')" 2>/dev/null)
    if [ "$CNT" != "0" ] && [ "$CNT" != "ERR" ] && [ "$CNT" != "PARSE_ERR" ]; then
      bash $W/tools/notify.sh --p0 "小红书搜谱链路已通：关键词测试返回 $CNT 条结果，格格可以用了。" 2>/dev/null || true
      echo "VERIFY_OK cnt=$CNT" >> "$LOG"
    else
      bash $W/tools/notify.sh --p0 "小红书扫码登录成功，但搜索验证没出结果（cnt=$CNT），需要我再看。" 2>/dev/null || true
      echo "VERIFY_FAIL cnt=$CNT" >> "$LOG"
    fi
    exit 0
  fi
  sleep 20
done
echo "TIMEOUT_NO_LOGIN" >> "$LOG"
