
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(7000);
  const t = await p.evaluate(()=>{
    const s = document.body.innerText;
    const i = s.indexOf('Tenant token scopes');
    const j = s.indexOf('Basic Info');
    return s.slice(i, j>i? j : i+1500).replace(/\n+/g,' | ');
  });
  console.log(t.slice(0,1500));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
