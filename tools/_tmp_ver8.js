
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const rows = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).map(r=>(r.innerText||'').replace(/\n+/g,' / ').replace(/\s+/g,' ')).filter(t=>t.length>5).slice(0,6));
  console.log(JSON.stringify(rows, null, 1).slice(0,900));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
