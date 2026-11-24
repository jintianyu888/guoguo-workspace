const http=require('node:http'), fs=require('node:fs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const OUT='/home/j/.openclaw/workspace/state/panelshots/blue-4647-1to1.png';
const OUT2='/home/j/.openclaw/workspace/state/panelshots/blue-4647-ctx.png';
const get=u=>new Promise((res,rej)=>{http.get(u,r=>{let d='';r.on('data',c=>d+=c);r.on('end',()=>{try{res(JSON.parse(d))}catch(e){rej(e)}})}).on('error',rej)});
(async()=>{
 const list=await get('http://127.0.0.1:9223/json'); const pg=list.find(t=>t.type==='page');
 const ws=new WebSocket(pg.webSocketDebuggerUrl); let id=0; const p=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&p.has(m.id)){p.get(m.id)(m);p.delete(m.id)}};
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 const send=(m,q)=>new Promise(r=>{const i=++id;p.set(i,r);ws.send(JSON.stringify({id:i,method:m,params:q||{}}))});
 await send('Page.enable'); await send('Runtime.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:1600,height:2000,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:'http://127.0.0.1:8899/'}); await sleep(9000);
 const MEAS="(function(){var out={};function mk(cls){var host=document.querySelector('#ablist .row .aline')||document.querySelector('#ablist .row')||document.body;var el=document.createElement('span');el.className='ctx '+cls;el.textContent='147k / 150k';el.id='__m_'+cls;host.appendChild(el);return el;}['warn','bad'].forEach(function(c){var el=mk(c);var s=getComputedStyle(el);out[c]={color:s.color,fontWeight:s.fontWeight,textShadow:s.textShadow,animation:s.animationName,background:s.backgroundImage};});var b=document.querySelector('#ablist .newbtn');if(b){b.classList.add('hot');var s2=getComputedStyle(b);out['newbtn.hot']={color:s2.color,borderColor:s2.borderColor,background:s2.backgroundColor};b.classList.remove('hot');}else{out['newbtn.hot']='NO_BUTTON';}document.querySelectorAll('[id^=__m_]').forEach(function(x){x.remove()});return out;})()";
 const r1=await send('Runtime.evaluate',{returnByValue:true,expression:MEAS});
 console.log('COMPUTED '+JSON.stringify(r1.result.result.value));
 const parse=s=>{const m=/rgba?\(([\d.]+), ?([\d.]+), ?([\d.]+)/.exec(s||'');return m?[+m[1],+m[2],+m[3]]:null};
 const v=r1.result.result.value||{}; let ok=true;
 ['warn','bad','newbtn.hot'].forEach(k=>{const c=parse((v[k]&&v[k].color)||''); if(!c||!(c[2]>=c[0])) ok=false;});
 console.log('BLUE_ASSERT '+(ok?'PASS':'FAIL'));
 // screenshot of the ablist panel
 const BOX="(function(){var h=[].slice.call(document.querySelectorAll('h2')).filter(function(x){return x.textContent.indexOf('回复状态')>=0})[0];var pan=h?h.closest('.panel'):null;if(!pan)return null;var bb=pan.getBoundingClientRect();return {x:Math.round(bb.x),y:Math.round(bb.y),width:Math.round(bb.width),height:Math.min(Math.round(bb.height),1500)};})()";
 const ev=await send('Runtime.evaluate',{returnByValue:true,expression:BOX});
 const b=ev.result.result.value; if(!b){console.log('NO_PANEL');ws.close();process.exit(2);}
 const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:b.x,y:b.y,width:b.width,height:b.height,scale:1}});
 fs.writeFileSync(OUT,Buffer.from(shot.result.data,'base64'));
 console.log('SHOT '+OUT+' '+b.width+'x'+b.height);
 ws.close(); process.exit(0);
})().catch(e=>{console.error('ERR '+e.message);process.exit(1)});
