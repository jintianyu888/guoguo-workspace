
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const t = await p.evaluate(() => {
    const body = document.body.innerText;
    const i = body.indexOf('Event configuration');
    return body.slice(i, i + 900).replace(/\n+/g,' | ');
  });
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
