const http=require('node:http'), fs=require('node:fs');
const URLP='http://127.0.0.1:8899/';
const OUT=process.argv[2]||'/home/j/.openclaw/workspace/state/panelshots/ab-1to1.png';
const get=u=>new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const CSS='#hudcanvas,#rainfx,#ocTop,#ocIdle,#rain,#rainon,.mask{display:none!important}#ablist{max-height:none!important;height:auto!important;overflow:visible!important}.split[data-swap="ab"] .panel{height:auto!important;max-height:none!important;overflow:visible!important}';
const EV="(function(){var h=[].slice.call(document.querySelectorAll('h2')).filter(function(x){return x.textContent.indexOf('回复状态')>=0})[0];var pan=h?h.closest('.panel'):null;var rows=[].slice.call(document.querySelectorAll('#ablist>*'));var info=rows.map(function(r){var cs=getComputedStyle(r);return {t:(r.textContent||'').replace(/\\s+/g,' ').trim().slice(0,80),fs:cs.fontSize}});var box=null;if(pan){var rr=pan.getBoundingClientRect();var bl=document.getElementById('ablist');var bb=bl?bl.getBoundingClientRect().bottom:rr.bottom;box={x:rr.left+window.scrollX,y:rr.top+window.scrollY,width:rr.width,height:Math.max(rr.height,bb-rr.top)+6}}return {box:box,rows:info}})()";
(async()=>{
 const list=await get('http://127.0.0.1:9223/json'); const pg=list.find(t=>t.type==='page');
 const ws=new WebSocket(pg.webSocketDebuggerUrl); let id=0; const p=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&p.has(m.id)){p.get(m.id)(m);p.delete(m.id)}};
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 const send=(m,q)=>new Promise(r=>{const i=++id;p.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:q||{}}))});
 await send('Page.enable'); await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1600,height:1800,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:URLP}); await sleep(9000);
 await send('Runtime.evaluate',{expression:"(function(){var s=document.createElement('style');s.textContent="+JSON.stringify(CSS)+";document.head.appendChild(s)})()"});
 await sleep(1500);
 const ev=await send('Runtime.evaluate',{returnByValue:true,expression:EV});
 const d=ev.result.result.value;
 if(!d.box){console.log('NO_BOX');process.exit(2)}
 const shot=await send('Page.captureScreenshot',{format:'png',clip:{x:d.box.x,y:d.box.y,width:d.box.width,height:d.box.height,scale:1},captureBeyondViewport:true});
 fs.writeFileSync(OUT,Buffer.from(shot.result.data,'base64'));
 console.log('SHOT '+OUT+' '+Math.round(d.box.width)+'x'+Math.round(d.box.height));
 console.log(JSON.stringify(d.rows));
 ws.close(); process.exit(0);
})().catch(e=>{console.error('ERR '+e.message);process.exit(1)});