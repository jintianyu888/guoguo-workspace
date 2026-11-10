#!/usr/bin/env node
// 极简 CDP 控制器：shot/eval/click/nav/url/tabs
const fs=require('fs');
const [,, cmd, ...args]=process.argv;
const target=process.env.CDP||'http://127.0.0.1:18811';
async function main(){
  const list=await (await fetch(target+'/json/list')).json();
  const pages=list.filter(t=>t.type==='page');
  if(cmd==='tabs'){ pages.forEach(p=>console.log((p.title||'').slice(0,50),'|',(p.url||'').slice(0,100))); return; }
  const page = process.env.MATCH ? pages.find(p=>(p.url||'').includes(process.env.MATCH)) : pages.find(p=>!/^(chrome|devtools):/.test(p.url||''))||pages[0];
  if(!page){ console.error('no page'); process.exit(2); }
  const ws=new WebSocket(page.webSocketDebuggerUrl);
  let id=0; const pending=new Map();
  const send=(method,params={})=>new Promise((res,rej)=>{const i=++id;pending.set(i,{res,rej});ws.send(JSON.stringify({id:i,method,params}));});
  await new Promise((r,j)=>{ws.onopen=r; ws.onerror=e=>j(new Error('ws error'));});
  ws.onmessage=(ev)=>{const m=JSON.parse(ev.data); const p=pending.get(m.id); if(p){pending.delete(m.id); m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);} };
  if(cmd==='shot'){
    const r=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    const out=args[0]||'/tmp/cdp.png';
    fs.writeFileSync(out, Buffer.from(r.data,'base64'));
    console.log('saved '+out);
  } else if(cmd==='eval'){
    const r=await send('Runtime.evaluate',{expression:args.join(' '),returnByValue:true,awaitPromise:true});
    const v=r.result&&('value' in r.result)?r.result.value:r;
    console.log(typeof v==='string'?v:JSON.stringify(v,null,1).slice(0,5000));
  } else if(cmd==='click'){
    const x=Number(args[0]), y=Number(args[1]);
    await send('Input.dispatchMouseEvent',{type:'mouseMoved',x,y});
    await send('Input.dispatchMouseEvent',{type:'mousePressed',x,y,button:'left',clickCount:1});
    await send('Input.dispatchMouseEvent',{type:'mouseReleased',x,y,button:'left',clickCount:1});
    console.log('clicked '+x+','+y);
  } else if(cmd==='nav'){
    await send('Page.navigate',{url:args[0]}); console.log('navigated');
  } else if(cmd==='url'){ console.log(page.url); }
  else console.error('usage: cdp.js shot|eval|click|nav|url|tabs');
  ws.close();
}
main().catch(e=>{console.error('ERR '+e.message);process.exit(1)});
