#!/usr/bin/env bash
# 用法: wb-run.sh /path/to/x.js  → 在 WorkBuddy 渲染进程执行该 JS（文件内容），返回 JSON
set -u
python3 -c 'import json,sys;print(json.dumps({"id":1,"method":"Runtime.evaluate","params":{"expression":open(sys.argv[1]).read(),"returnByValue":True,"awaitPromise":True}}))' "$1" | /home/j/.openclaw/workspace/tools/wb-cdp2.sh
