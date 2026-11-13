#!/usr/bin/env bash
# wb-ask.sh "问题" [超时秒] —— CDP 驱动 WorkBuddy，Hy4 模型提问并取回答
set -u
W=/home/j/.openclaw/workspace
Q="$1"
TO="$2"
[ -z "$Q" ] && { echo "用法: wb-ask.sh \"问题\" [超时秒]"; exit 2; }
[ -z "$TO" ] && TO=120
RUN="$W/tools/wb-run.sh"
CDP="$W/tools/wb-cdp2.sh"
tmp=$(mktemp -d)
cdp(){ printf "%s" "$1" | "$CDP" >/dev/null 2>&1; }
click(){ cdp "{\"id\":1,\"method\":\"Input.dispatchMouseEvent\",\"params\":{\"type\":\"mousePressed\",\"x\":$1,\"y\":$2,\"button\":\"left\",\"clickCount\":1}}"; cdp "{\"id\":2,\"method\":\"Input.dispatchMouseEvent\",\"params\":{\"type\":\"mouseReleased\",\"x\":$1,\"y\":$2,\"button\":\"left\",\"clickCount\":1}}"; }
runjs(){ "$RUN" "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',{}).get('result',{}); v=r.get('value'); print(v if isinstance(v,str) else json.dumps(v))" 2>/dev/null; }
getxy(){ python3 -c 'import sys,re; s=sys.stdin.read(); m=re.search(r"\"x\":(\d+),\"y\":(\d+)", s); print(m.group(1)+" "+m.group(2)) if m else print("")'; }
printf '%s' '{"id":1,"method":"Runtime.evaluate","params":{"expression":"1","returnByValue":true}}' | "$CDP" | grep -q '"value":1' || { echo "WB_ERR CDP 9222 连不上"; exit 3; }
# 1) 确保 Hy4
cat > "$tmp/model.js" <<'JS'
(function(){
  var sels=[].slice.call(document.querySelectorAll(".cr-model-selector__trigger-label"));
  sels.sort(function(a,b){return b.getBoundingClientRect().y-a.getBoundingClientRect().y;});
  var sel=sels[0];
  if(!sel) return JSON.stringify({ok:false,why:"no selector"});
  var cur=(sel.textContent||"").trim();
  if(/Hy4/i.test(cur)) return JSON.stringify({ok:true,already:true,cur:cur});
  var r=sel.getBoundingClientRect(); sel.click();
  return JSON.stringify({ok:true,already:false,cur:cur,x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
})()
JS
sel=$(runjs "$tmp/model.js")
if ! echo "$sel" | grep -q '"already":true'; then
  xy=$(echo "$sel" | getxy)
  [ -n "$xy" ] && click $xy
  sleep 1
  cat > "$tmp/pick.js" <<'JS'
(function(){
  var it=[].slice.call(document.querySelectorAll(".cr-model-selector__item-name")).filter(function(n){return /Hy4/i.test(n.textContent||"");})[0];
  if(!it) return JSON.stringify({ok:false});
  var r=it.getBoundingClientRect();
  return JSON.stringify({ok:true,x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
})()
JS
  xy2=$(runjs "$tmp/pick.js" | getxy)
  [ -z "$xy2" ] && { echo "WB_ERR 找不到 Hy4 选项"; exit 4; }
  click $xy2; sleep 1
fi
# 2) 输入
cat > "$tmp/ed.js" <<'JS'
(function(){
  var eds=[].slice.call(document.querySelectorAll("[contenteditable]"));
  var e=eds.sort(function(a,b){return b.getBoundingClientRect().y-a.getBoundingClientRect().y;})[0];
  var r=e.getBoundingClientRect();
  return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});
})()
JS
exy=$(runjs "$tmp/ed.js" | getxy)
[ -z "$exy" ] && { echo "WB_ERR 找不到输入框"; exit 5; }
click $exy; sleep 1
python3 -c "import json,sys; print(json.dumps({'id':3,'method':'Input.insertText','params':{'text':sys.argv[1]}}))" "$Q" | "$CDP" >/dev/null
sleep 1
# 3) 发送
cat > "$tmp/send.js" <<'JS'
(function(){
  var b=[].slice.call(document.querySelectorAll("button")).filter(function(x){return (x.getAttribute("aria-label")||"")==="发送";})[0];
  if(!b||b.disabled) return JSON.stringify({ok:false});
  b.click(); return JSON.stringify({ok:true});
})()
JS
runjs "$tmp/send.js" | grep -q '"ok":true' || { echo "WB_ERR 发送按钮不可用"; exit 6; }
# 4) 等回答
cat > "$tmp/read.js" <<'JS'
(function(){
  var t=document.body.innerText; var q=window.__wbq||"";
  var i=q? t.indexOf(q) : -1;
  var seg=i>=0? t.slice(i,i+1800) : t.slice(-900);
  return JSON.stringify({done:/已完成|已停止|执行失败|出错/.test(seg), seg:seg});
})()
JS
python3 -c "import json,sys; print(json.dumps({'id':9,'method':'Runtime.evaluate','params':{'expression':'window.__wbq='+json.dumps(sys.argv[1]),'returnByValue':True}}))" "$Q" | "$CDP" >/dev/null
end=$(( $(date +%s) + TO ))
while [ "$(date +%s)" -lt "$end" ]; do
  sleep 6
  out=$(runjs "$tmp/read.js")
  if echo "$out" | grep -q '"done":true'; then echo "$out"; exit 0; fi
done
echo "WB_TIMEOUT 超过 $TO 秒未完成"; exit 7
