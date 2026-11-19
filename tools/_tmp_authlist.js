
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const rows = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).map(r=>(r.innerText||'').replace(/\s+/g,' ').trim()).filter(t=>/im:|contact:/.test(t)).slice(0,40));
  console.log('COUNT', rows.length);
  console.log(JSON.stringify(rows, null, 1).slice(0, 1800));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
