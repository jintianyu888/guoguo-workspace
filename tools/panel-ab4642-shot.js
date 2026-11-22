const http=require('node:http'), fs=require('node:fs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const OUT='/home/j/.openclaw/workspace/state/panelshots/ab-4642-1to1.png';
const get=u=>new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)});
const CSS='#hudcanvas,#rainfx,#ocTop,#ocIdle,#rain,.mask{display:none!important}#ablist{max-height:none!important;height:auto!important;overflow:visible!important}.split[data-swap="ab"] .panel{height:auto!important;max-height:none!important;overflow:visible!important}';
const BOX="(function(){var h=[].slice.call(document.querySelectorAll('h2')).filter(function(x){return x.textContent.indexOf('回复状态')>=0})[0];var pan=h?h.closest('.panel'):null;if(!pan)return null;var rr=pan.getBoundingClientRect();var bl=document.getElementById('ablist');var bb=bl?bl.getBoundingClientRect().bottom:rr.bottom;return {x:rr.left+window.scrollX,y:rr.top+window.scrollY,width:rr.width,height:Math.max(rr.height,bb-rr.top)+6}})()";
const TEST="(function(){var out={};var save=JSON.parse(JSON.stringify(STATE.agentReply||[]));var rows=STATE.agentReply;if(!rows||!rows.length)return {err:'no rows'};var t=function(u){return {used:u,window:1000000,at:Date.now()-45000}};rows[0].ctx=t(130000);rows[1].ctx=t(200000);rows[2].ctx=null;renderAB();var q=function(i){var r=document.querySelectorAll('#ablist .row')[i];if(!r)return null;var c=r.querySelector('.aline .ctx');return c?{cls:c.className,txt:c.textContent,title:(c.getAttribute('title')||'').slice(0,70)}:null};out.warn=q(0);out.bad=q(1);out.dash=q(2);out.live=[].slice.call(document.querySelectorAll('#ablist .row')).slice(0,4).map(function(r){var c=r.querySelector('.aline .ctx');return c?c.textContent:null});STATE.agentReply=save;renderAB();return out})()";
(async()=>{
 const list=await get('http://127.0.0.1:9222/json'); const pg=list.find(t=>t.type==='page');
 const ws=new WebSocket(pg.webSocketDebuggerUrl); let id=0; const p=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&p.has(m.id)){p.get(m.id)(m);p.delete(m.id)}};
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 const send=(m,q)=>new Promise(r=>{const i=++id;p.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:q||{}}))});
 await send('Page.enable'); await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1600,height:2000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:'http://127.0.0.1:8899/'}); await sleep(9000);
 await send('Runtime.evaluate',{expression:"(function(){var s=document.createElement('style');s.textContent="+JSON.stringify(CSS)+";document.head.appendChild(s)})()"});
 await sleep(1200);
 const ev=await send('Runtime.evaluate',{returnByValue:true,expression:BOX});
 const b=ev.result.result.value; if(!b){console.log('NO_BOX');process.exit(2)}
 const shot=await send('Page.captureScreenshot',{format:'png',clip:{x:b.x,y:b.y,width:b.width,height:b.height,scale:1},captureBeyondViewport:true});
 fs.writeFileSync(OUT,Buffer.from(shot.result.data,'base64'));
 const t=await send('Runtime.evaluate',{returnByValue:true,expression:TEST});
 console.log('SHOT '+OUT+' '+Math.round(b.width)+'x'+Math.round(b.height));
 console.log('TEST '+JSON.stringify(t.result.result.value));
 ws.close(); process.exit(0);
})().catch(e=>{console.error('ERR '+e.message);process.exit(1)});