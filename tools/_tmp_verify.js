
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r1 = await p.evaluate(() => {
    const el = Array.from(document.querySelectorAll('*')).find(e=>(e.innerText||'').trim()==='persistent connection' && e.children.length===0);
    if (!el) return 'no label';
    el.click(); return 'clicked persistent';
  });
  console.log(r1);
  await p.waitForTimeout(1500);
  const r2 = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Verify');
    if (!btn) return 'no verify';
    btn.click(); return 'verify clicked';
  });
  console.log(r2);
  await p.waitForTimeout(5000);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Subscription mode');return s.slice(i,i+450).replace(/\n+/g,' | ');});
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/verify-mode.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
