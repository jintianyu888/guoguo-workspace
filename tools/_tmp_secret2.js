
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await ctx.grantPermissions(['clipboard-read','clipboard-write'], {origin:'https://open.feishu.cn'}).catch(()=>{});
  const r1 = await p.evaluate(() => {
    const all = Array.from(document.querySelectorAll('*'));
    const star = all.find(e => (e.textContent||'').includes('∗∗∗∗') && e.children.length === 0);
    if (!star) return 'no star';
    let row = star.parentElement.parentElement.parentElement;
    const spans = Array.from(row.querySelectorAll('span.universe-icon'));
    if (!spans.length) return 'no span icons';
    spans[0].dispatchEvent(new MouseEvent('click',{bubbles:true}));
    return 'clicked span0, total '+spans.length;
  });
  console.log(r1);
  await p.waitForTimeout(3000);
  const val = await p.evaluate(() => {
    const lines = document.body.innerText.split('\n').map(s=>s.trim());
    const cand = lines.filter(l => /^[A-Za-z0-9_-]{20,}$/.test(l));
    return cand.slice(0,3);
  });
  console.log('candidates:', JSON.stringify(val));
  const clip = await p.evaluate(async () => { try { return await navigator.clipboard.readText(); } catch(e){ return 'ERR '+e.message; } });
  console.log('clipboard:', (clip||'').slice(0,40));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
