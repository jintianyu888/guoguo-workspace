
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const out = [];
    document.querySelectorAll('button').forEach(btn => {
      const t = (btn.innerText||'').trim();
      if (!t) return;
      const card = btn.closest('[class*=card]') || btn.parentElement.parentElement;
      out.push({t, card: (card.innerText||'').slice(0,50).replace(/\n/g,' '), y: Math.round(btn.getBoundingClientRect().y)});
    });
    return out;
  });
  console.log(JSON.stringify(info).slice(0,1200));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
