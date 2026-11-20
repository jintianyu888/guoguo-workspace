
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const clicked = await p.evaluate(() => {
    const els = Array.from(document.querySelectorAll('*')).filter(e=>(e.innerText||'').trim()==='Edit' && e.children.length===0);
    if (!els.length) return 'no edit';
    els[0].click(); return 'edit clicked ('+els.length+')';
  });
  console.log(clicked);
  await p.waitForTimeout(3500);
  const t = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?m.innerText.replace(/\n+/g,' | ').slice(0,400):'no modal';});
  console.log('MODAL:', t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/avail-edit.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
