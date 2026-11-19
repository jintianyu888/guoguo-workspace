
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const done = await p.evaluate(() => {
    // 找到包含 Bot 描述的卡片里的 Add 按钮
    const cards = Array.from(document.querySelectorAll('div')).filter(d => /A bot can automatically send messages/.test(d.innerText||'') && d.innerText.length < 500);
    const card = cards[cards.length-1];
    if (!card) return 'no card';
    const btn = Array.from(card.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Add');
    if (!btn) return 'no add btn';
    btn.click(); return 'bot add clicked';
  });
  console.log(done);
  await p.waitForTimeout(4000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,600));
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
