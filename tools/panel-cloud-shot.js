const http=require('node:http'), fs=require('node:fs');
const URLP='http://127.0.0.1:8899/';
const OUT=process.argv[2]||'/home/j/.openclaw/workspace/state/panelshots/cloud-4641-1to1.png';
const get=u=>new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const CSS='#hudcanvas,#rainfx,#ocTop,#ocIdle,#rain,#rainon,.mask{display:none!important}.panel.balpanel{height:auto!important;max-height:none!important;overflow:visible!important}.bottomrow{height:auto!important;overflow:visible!important;align-items:flex-start!important}.bottomrow>.panel{height:auto!important;max-height:none!important;overflow:visible!important}.bottomrow>.panel:not(.balpanel){display:none!important}.panel.balpanel{width:760px!important}#balances{max-height:none!important;height:auto!important;overflow:visible!important}';
const EV="(function(){var h2=[].slice.call(document.querySelectorAll('h2')).filter(function(h){return h.textContent.indexOf('云端模型')>=0})[0];var rows=[].slice.call(document.querySelectorAll('#balances .balrow'));var order=rows.filter(function(r){return !r.classList.contains('sub')}).map(function(r){var pn=r.querySelector('.bn'),pb=r.querySelector('.rb');return {provider:pn?pn.textContent.trim():'?',pill:pb?pb.textContent.trim():'',opacity:r.style.opacity||''}});var subs=[].slice.call(document.querySelectorAll('#balances .balrow.sub')).map(function(x){return x.textContent.replace(/\\s+/g,' ').trim()});var el=h2?h2.closest('.panel.balpanel'):null;var box=null;if(el){var r=el.getBoundingClientRect();var bal=document.getElementById('balances');var bb=bal?bal.getBoundingClientRect().bottom:r.bottom;var bottom=Math.max(r.bottom,bb)+6;box={x:r.left+window.scrollX,y:r.top+window.scrollY,width:r.width,height:bottom-r.top}}return {order:order,subs:subs,box:box}})()";
(async()=>{
 const list=await get('http://127.0.0.1:9222/json'); const pg=list.find(t=>t.type==='page');
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
 if(!d.box){console.log('NO_BOX'); process.exit(2)}
 const shot=await send('Page.captureScreenshot',{format:'png',clip:{x:d.box.x,y:d.box.y,width:d.box.width,height:d.box.height,scale:1},captureBeyondViewport:true});
 fs.writeFileSync(OUT, Buffer.from(shot.result.data,'base64'));
 console.log('SHOT '+OUT+' '+Math.round(d.box.width)+'x'+Math.round(d.box.height));
 console.log(JSON.stringify({order:d.order,subs:d.subs}));
 ws.close(); process.exit(0);
})().catch(e=>{console.error('ERR '+e.message);process.exit(1)});