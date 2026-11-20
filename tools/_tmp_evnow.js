
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/ev-page-now.png'});
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Subscription mode');return s.slice(i,i+500).replace(/\n+/g,' | ');});
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
