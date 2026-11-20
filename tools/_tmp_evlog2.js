
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.evaluate(()=>{const btn=Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Search');if(btn)btn.click();});
  await p.waitForTimeout(6000);
  const rows = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).map(r=>(r.innerText||'').replace(/\s+/g,' ').trim()).filter(t=>t.length>5).slice(0,10));
  console.log(JSON.stringify(rows, null, 1).slice(0,1200));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/eventlog2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
