
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const pub = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Publish');
    if (!btn) return 'no publish btn';
    btn.scrollIntoView({block:'center'}); btn.click(); return 'clicked';
  });
  console.log(pub);
  await p.waitForTimeout(6000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,260));
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/publish-101.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
