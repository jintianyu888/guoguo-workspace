
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const modal = document.querySelector('.ud__modal');
    const rows = [];
    modal.querySelectorAll('input,textarea').forEach((el, i) => {
      const r = el.getBoundingClientRect();
      rows.push({i, tag: el.tagName, type: el.type||'', ph: el.placeholder||'', w: Math.round(r.width), h: Math.round(r.height), val: (el.value||'').slice(0,20)});
    });
    const labels = Array.from(modal.querySelectorAll('label,[class*=label]')).map(l=>(l.innerText||'').trim()).filter(Boolean).slice(0,8);
    return {rows, labels, text: modal.innerText.replace(/\n+/g,' | ').slice(0,300)};
  });
  console.log(JSON.stringify(info, null, 1).slice(0,1600));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
