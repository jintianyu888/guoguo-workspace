
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  // 打开 Batch Actions
  const opened = await p.evaluate(() => {
    const els = Array.from(document.querySelectorAll('button,span,div,a'));
    const t = els.find(e => /^Batch Actions$/.test((e.innerText||'').trim()));
    if (!t) return 'no batch btn';
    t.click(); return 'opened';
  });
  console.log(opened);
  await p.waitForTimeout(2000);
  const items = await p.evaluate(() => Array.from(document.querySelectorAll('li,div[role=menuitem],span')).map(e=>(e.innerText||'').trim()).filter(t=>/import|export|Import/i.test(t)).slice(0,5));
  console.log('menu items:', JSON.stringify(items));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/batch-menu.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
