
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.waitForTimeout(3000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,240));
  console.log(t);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim(), y:Math.round(b.getBoundingClientRect().y)})).filter(b=>b.t && /Publish|Save|Cancel/.test(b.t)));
  console.log('btns:', JSON.stringify(btns));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
