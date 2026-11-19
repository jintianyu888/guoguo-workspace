
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const clicked = await p.evaluate(() => {
    const d = document.querySelector('.create-app-dialog');
    if (!d) return 'no dialog';
    const btn = Array.from(d.querySelectorAll('button')).find(x => (x.innerText||'').trim() === 'Create');
    if (!btn) return 'no btn';
    const r = btn.getBoundingClientRect();
    btn.dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));
    btn.dispatchEvent(new MouseEvent('mouseup',{bubbles:true}));
    btn.click();
    return 'clicked@'+Math.round(r.x)+','+Math.round(r.y);
  });
  console.log(clicked);
  await p.waitForTimeout(9000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'), '| dialog open:', await p.evaluate(()=>!!document.querySelector('.create-app-dialog')));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-final2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
