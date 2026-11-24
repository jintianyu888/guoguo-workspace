#!/bin/bash
# new-butler-icon.sh —— 新管家上线：生成头像 → 上传 → 发布 → 验收（R40）
# 用法: bash tools/new-butler-icon.sh <appId> "<中文名>" [领域关键词]
set -uo pipefail
W=/home/j/.openclaw/workspace
APP="$1"; NAME="$2"; KW="$3"
[ -z "$APP" ] || [ -z "$NAME" ] && { echo "用法: new-butler-icon.sh <appId> \"<中文名>\" [关键词]"; exit 2; }
REG=$W/state/icons/registry.json
mkdir -p "$(dirname "$REG")"

case "$KW" in
  health*|健康*|医疗*) KEY=health;;
  print*|3d*|打印*) KEY=print3d;;
  video*|剪辑*) KEY=jianji;;
  music*|乐*|作曲*|谱*) KEY=hermess;;
  security*|安保*|安全*) KEY=security;;
  law*|法律*) KEY=law;;
  company*|公司*) KEY=company1;;
  info*|信息*) KEY=info;;
  calendar*|排课*|日程*) KEY=paike;;
  teach*|老师*|教育*) KEY=agant;;
  work*|干活*|tool*|工具*) KEY=work;;
  maint*|维护*) KEY=maint;;
  *) KEY="";;
esac

if [ -n "$KEY" ] && [ -f "$W/state/icons/new/$KEY.png" ]; then
  PNG="$W/state/icons/new/$KEY.png"; SRC="库内设计（$KEY）"
else
  OUT=$(python3 "$W/tools/icon-forge.py" --monogram "$NAME")
  SVG=$(echo "$OUT" | python3 -c "import sys,json;print(json.load(sys.stdin)[\"svg\"])")
  node "$W/tools/icon-render.js" "$SVG" >/dev/null || exit 3
  PNG=$(echo "$SVG" | sed "s/svg$/png/"); SRC="首字徽章（自动生成）"
fi
echo "图标来源：$SRC → $PNG"

bash "$W/tools/feishu-console.sh" status 2>/dev/null | grep -q active || bash "$W/tools/feishu-console.sh" start
sleep 2
timeout 200 node "$W/tools/icon-apply.js" "$APP" "$PNG" "新管家上线：$NAME" || { echo "上传/发布失败"; exit 4; }

python3 - "$REG" "$APP" "$NAME" "$PNG" <<"PY"
import json,sys,time,os
reg,app,name,png=sys.argv[1:5]
d=json.load(open(reg)) if os.path.exists(reg) else {}
d[app]={"name":name,"png":png,"at":time.strftime("%Y-%m-%d %H:%M:%S")}
json.dump(d,open(reg,"w"),ensure_ascii=False,indent=1)
print("registry +1:",app,name)
PY
echo "OK 新管家头像已上线：$NAME ($APP)"
