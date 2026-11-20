
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa3dced661b85bb7/event', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Event configuration');return s.slice(i,i+600).replace(/\n+/g,' | ');});
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
