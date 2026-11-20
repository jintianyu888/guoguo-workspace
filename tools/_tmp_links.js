
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const links = await p.evaluate(()=>Array.from(document.querySelectorAll('a')).map(a=>({t:(a.innerText||'').trim(), h:a.getAttribute('href')})).filter(x=>x.h && /log|monitor|event|diagnos/i.test(x.h)).slice(0,10));
  console.log(JSON.stringify(links, null, 1).slice(0,800));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
