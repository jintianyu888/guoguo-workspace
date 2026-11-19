
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/secret-state.png'});
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,700));
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
