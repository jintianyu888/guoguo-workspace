
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  console.log('frames:', p.frames().map(f=>f.url().slice(0,90)));
  for (const f of p.frames()) {
    const n = await f.locator('input[type=text]').count().catch(()=>0);
    const m = await f.locator('.ud__modal').count().catch(()=>0);
    if (n || m) console.log('FRAME', f.url().slice(0,80), 'inputs', n, 'modal', m);
  }
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
