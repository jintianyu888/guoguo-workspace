
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim(), x:Math.round(b.getBoundingClientRect().x), y:Math.round(b.getBoundingClientRect().y)})).filter(b=>b.t));
  console.log(JSON.stringify(btns.slice(0,15)));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
