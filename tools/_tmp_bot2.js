
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r1 = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const bot = btns.find(x => (x.innerText||'').trim()==='Add' && /Bot An app feature/.test((x.closest('[class*=card]')||{}).innerText||''));
    if (!bot) return 'no bot add';
    bot.click(); return 'bot add clicked';
  });
  console.log(r1);
  await p.waitForTimeout(4000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,400));
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
