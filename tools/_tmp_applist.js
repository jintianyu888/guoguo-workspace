
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  const btns = await p.evaluate(() => Array.from(document.querySelectorAll('button,a')).map(e=>({t:(e.innerText||'').trim(), c:e.className.slice(0,40)})).filter(x=>x.t && x.t.length<20).slice(0,60));
  console.log(JSON.stringify(btns));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
