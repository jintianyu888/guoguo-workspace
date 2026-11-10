#!/usr/bin/env bash
# panel-selftest.sh —— 面板改完必跑：内嵌 JS 语法 + renderTodos 真实渲染冒烟
# 2026-11-07 立（起因：改 index.html 把 planHtml 放到 row() 外面，整页白屏）
set -u
APP=/home/j/openclaw-workspaces/work/果果助手
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
curl -s http://127.0.0.1:8899/api/state -o "$TMP/state.json" || { echo "FAIL: 取不到 /api/state"; exit 1; }
python3 - "$APP/public/index.html" "$TMP" <<'PY'
import re,sys
src=open(sys.argv[1],encoding='utf-8').read(); out=sys.argv[2]
blocks=re.findall(r'<script(?![^>]*src=)[^>]*>(.*?)</script>', src, re.S)
open(out+'/body.js','w',encoding='utf-8').write(blocks[0])
print('blocks', len(blocks))
PY
node --check "$TMP/body.js" || { echo "FAIL: 内嵌 JS 语法错误"; exit 1; }
cat > "$TMP/shim.js" <<'JS'
const state=require(process.argv[2]);
function mkEl(id){const o={id,textContent:'',innerHTML:'',value:'',style:{},dataset:{},children:[],classList:{add(){},remove(){},toggle(){},contains(){return false}},appendChild(){},addEventListener(){},querySelector(){return mkEl('x')},querySelectorAll(){return []},getAttribute(){return null},setAttribute(){},focus(){},remove(){},insertAdjacentHTML(){},scrollTop:0};return new Proxy(o,{get(t,k){ if(k in t) return t[k]; return t[k]=function(){}; }, set(t,k,v){t[k]=v;return true;}});}
const _els={};
global.document={getElementById:(id)=>{ if(!_els[id]) _els[id]=mkEl(id); return _els[id]; },querySelector:()=>mkEl('q'),querySelectorAll:()=>[],addEventListener(){},body:mkEl('body'),createElement:()=>mkEl('c'),documentElement:mkEl('html'),head:mkEl('head')};
global.window=global; global.addEventListener=function(){}; global.removeEventListener=function(){}; global.matchMedia=function(){return {matches:false,addEventListener(){},addListener(){}}};
global.navigator={userAgent:'node'}; global.location={href:'http://127.0.0.1:8899/',search:'',hash:''};
global.localStorage={getItem:()=>null,setItem(){},removeItem(){}};
global.fetch=async()=>({ok:true,status:200,json:async()=>state,text:async()=>''});
global.WebSocket=class{constructor(){}send(){}close(){}addEventListener(){}};
global.Notification=class{static permission='denied';constructor(){}};
global.setInterval=()=>0; global.clearInterval=()=>{}; global.requestAnimationFrame=()=>0;
global.EventSource=class{constructor(){}addEventListener(){}close(){}};
JS
cat "$TMP/shim.js" "$TMP/body.js" > "$TMP/run.js"
cat >> "$TMP/run.js" <<'JS'
;(()=>{ try{ STATE=state; renderTodos(); const m=document.getElementById('todos-mine'), g=document.getElementById('todos-gg'); const a=(m.innerHTML||'').length, b=(g.innerHTML||'').length; if(!a && !b){ console.log('FAIL: 两个待办区都是空的'); process.exit(1);} console.log('PASS render mine='+a+' gg='+b); }catch(e){ console.log('FAIL render: '+e.message); process.exit(1);} })();
JS
node "$TMP/run.js" "$TMP/state.json" || exit 1
echo "PANEL_SELFTEST_OK"
