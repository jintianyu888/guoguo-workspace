
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const rows = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).map(r=>(r.innerText||'').replace(/\s+/g,' ').trim()).filter(t=>/剪辑|视频/.test(t)));
  console.log('MATCH:', JSON.stringify(rows, null, 1).slice(0,800));
  const all = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).length);
  console.log('total rows:', all);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
