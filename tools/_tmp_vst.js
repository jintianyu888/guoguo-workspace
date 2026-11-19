
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const rows = await p.evaluate(()=>Array.from(document.querySelectorAll('tr')).map(r=>(r.innerText||'').replace(/\s+/g,' ').trim()).filter(t=>t.length>5).slice(0,4));
  console.log('ROWS:', JSON.stringify(rows));
  const top = await p.evaluate(()=>document.body.innerText.slice(0,220).replace(/\n+/g,' | '));
  console.log('TOP:', top);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
