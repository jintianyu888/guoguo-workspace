
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  // find create-custom-app trigger
  const clicked = await p.evaluate(() => {
    const els = Array.from(document.querySelectorAll('button,a,div,span'));
    const t = els.find(e => /^(Create Custom App|创建自建应用|Create App)$/i.test((e.innerText||'').trim()));
    if (t) { t.click(); return (t.innerText||'').trim(); }
    return null;
  });
  console.log('clicked:', clicked);
  await p.waitForTimeout(3500);
  console.log('URL:', p.url());
  const form = await p.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input')).map(i=>({ph:i.placeholder||'', name:i.name||'', type:i.type}));
    const txt = document.body.innerText.slice(0, 1200);
    const btns = Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,20);
    return {inputs, btns, txt};
  });
  console.log(JSON.stringify(form, null, 1).slice(0, 2500));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
