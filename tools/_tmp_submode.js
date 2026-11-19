
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const clicked = await p.evaluate(() => {
    const all = Array.from(document.querySelectorAll('*'));
    const node = all.find(e => (e.innerText||'').trim() === 'Subscription mode');
    if (!node) return 'no label';
    const row = node.closest('div').parentElement;
    const btn = row.querySelector('button, span[class*=icon], a');
    if (btn) { btn.click(); return 'clicked ' + btn.tagName; }
    node.click(); return 'clicked label';
  });
  console.log(clicked);
  await p.waitForTimeout(3000);
  const d = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    return m ? m.innerText.replace(/\n+/g,' | ').slice(0,400) : 'no modal';
  });
  console.log(d);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/submode.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
