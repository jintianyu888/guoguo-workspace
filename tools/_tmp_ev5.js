
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const saved = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Save');
    if (!btn) return 'no save';
    btn.click(); return 'save clicked';
  });
  console.log(saved);
  await p.waitForTimeout(4000);
  const addr = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(x=>/Add Events/.test(x.innerText||''));
    if (!btn) return 'no add events';
    btn.scrollIntoView({block:'center'}); btn.click(); return 'add events clicked';
  });
  console.log(addr);
  await p.waitForTimeout(3500);
  const t = await p.evaluate(() => {
    const body = document.body.innerText;
    const i = body.indexOf('Add event');
    return i>=0 ? body.slice(i, i+500).replace(/\n+/g,' | ') : body.slice(-500).replace(/\n+/g,' | ');
  });
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/add-event-list.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
