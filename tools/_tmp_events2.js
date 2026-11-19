
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.mouse.click(1113, 880);
  await p.waitForTimeout(3000);
  const d = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    if (!m) return {err:'no modal'};
    return {text: m.innerText.replace(/\n+/g,' | ').slice(0,300),
      inputs: Array.from(m.querySelectorAll('input')).map(i=>({ph:i.placeholder||'', cls:(i.className||'').slice(0,20)})),
      btns: Array.from(m.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean)};
  });
  console.log(JSON.stringify(d).slice(0,900));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/add-events.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
