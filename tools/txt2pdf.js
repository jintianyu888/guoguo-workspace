
// txt2pdf.js — HTML/纯文本 → A4 PDF（中文、正文 13pt、页脚「第 N 页 / 共 M 页」）
// 用法: node txt2pdf.js <in.html|in.txt> <out.pdf> [--size 13]
const fs=require("fs"), path=require("path"), {spawn}=require("child_process");
const CHROME=process.env.TXT2PDF_CHROME || "/home/j/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome";
const args=process.argv.slice(2);
const inp=args[0], out=args[1];
let size=13; const si=args.indexOf("--size"); if(si>0) size=parseFloat(args[si+1]);
if(!inp||!out){ console.error("usage: node txt2pdf.js IN OUT [--size 13]"); process.exit(2); }
const sleep=ms=>new Promise(r=>setTimeout(r,ms));

function txtToHtml(txt, size){
  const esc=s=>s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
  const lines=txt.replace(/\r\n/g,"\n").split("\n"); let first=true; const b=[];
  lines.forEach((raw,i)=>{
    const l=raw.replace(/\s+$/,""); if(!l.trim()) return;
    if(/^[一二三四五六七八九十]+、/.test(l)){ b.push("<h2>"+esc(l)+"</h2>"); first=false; return; }
    if(first){ b.push("<h1>"+esc(l)+"</h1>"); first=false; return; }
    if(i===1 && l.length<90){ b.push('<p class="sub">'+esc(l)+"</p>"); return; }
    if(/^[（(].*[)）]$/.test(l) && l.length<90){ b.push('<p class="sub">'+esc(l)+"</p>"); return; }
    b.push("<p>"+esc(l)+"</p>");
  });
  return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>'+
    '@page{size:A4;margin:18mm 18mm 20mm 20mm}'+
    'body{font-family:"Droid Sans Fallback","Microsoft YaHei",sans-serif;font-size:'+size+'pt;line-height:1.75;color:#000}'+
    'h1{font-size:'+(size*1.45).toFixed(1)+'pt;text-align:center;margin:0 0 6mm 0;font-weight:700}'+
    'h2{font-size:'+(size*1.15).toFixed(1)+'pt;margin:7mm 0 2mm 0;font-weight:700;page-break-after:avoid}'+
    'p{margin:0 0 2.2mm 0;text-align:justify}p.sub{font-size:'+(size*0.85).toFixed(1)+'pt;color:#333}'+
    '</style></head><body>'+"\n"+b.join("\n")+"\n</body></html>";
}

(async()=>{
  const raw=fs.readFileSync(inp,"utf8");
  const isHtml=/^\s*<(!doctype|html)/i.test(raw);
  const tmpHtml="/tmp/"+path.basename(inp).replace(/[^\w.-]/g,"_")+"."+Date.now()+".html";
  fs.writeFileSync(tmpHtml, isHtml?raw:txtToHtml(raw,size), "utf8");
  const PORT=9333+Math.floor(Math.random()*200);
  const proc=spawn(CHROME,["--headless=new","--disable-gpu","--no-sandbox","--hide-scrollbars",
    "--remote-debugging-port="+PORT,"--user-data-dir=/tmp/cdpprof-"+PORT,"about:blank"],{stdio:"ignore"});
  let ver=null;
  for(let i=0;i<60;i++){ try{ ver=await (await fetch("http://127.0.0.1:"+PORT+"/json/version")).json(); break;}catch(e){ await sleep(250);} }
  if(!ver){ proc.kill(); throw new Error("CDP 未启动（检查 chrome 路径）"); }
  const ws=new WebSocket(ver.webSocketDebuggerUrl); let id=0; const pend=new Map();
  await new Promise(r=>ws.addEventListener("open",r));
  ws.addEventListener("message",ev=>{const m=JSON.parse(ev.data); if(m.id&&pend.has(m.id)){pend.get(m.id)(m);pend.delete(m.id);} });
  const send=(method,params,sessionId)=>new Promise(res=>{const mid=++id;pend.set(mid,res);
    ws.send(JSON.stringify({id:mid,method,params:params||{},sessionId}));});
  const t=await send("Target.createTarget",{url:"file://"+tmpHtml});
  const a=await send("Target.attachToTarget",{targetId:t.result.targetId,flatten:true});
  const sid=a.result.sessionId;
  await send("Page.enable",{},sid); await sleep(1200);
  const r=await send("Page.printToPDF",{
    displayHeaderFooter:true, headerTemplate:"<div></div>",
    footerTemplate:'<div style="width:100%;text-align:center;font-size:9px;color:#000;">第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</div>',
    printBackground:true, paperWidth:8.27, paperHeight:11.69,
    marginTop:0.71, marginBottom:0.79, marginLeft:0.79, marginRight:0.71 }, sid);
  if(!r.result||!r.result.data){ console.error(JSON.stringify(r).slice(0,300)); proc.kill(); process.exit(1); }
  fs.writeFileSync(out, Buffer.from(r.result.data,"base64"));
  const pages=(fs.readFileSync(out).toString("latin1").match(/\/Type\s*\/Page[^s]/g)||[]).length;
  console.log("ok pages≈"+pages+" bytes="+fs.statSync(out).size+" -> "+out);
  ws.close(); proc.kill(); process.exit(0);
})().catch(e=>{ console.error("ERR",e.message); process.exit(1); });

