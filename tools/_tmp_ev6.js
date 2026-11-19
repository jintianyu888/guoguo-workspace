
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const m = p.locator('.ud__modal').last();
  const q = m.locator('input').first();
  await q.fill('im.message.receive_v1', {force:true});
  await p.waitForTimeout(3000);
  const rows = await m.locator('text=/im\\.message\\.receive_v1/').count();
  console.log('matches:', rows);
  // 勾选第一条
  const clicked = await p.evaluate(() => {
    const mm = document.querySelector('.ud__modal');
    const el = Array.from(mm.querySelectorAll('*')).find(e => (e.textContent||'').includes('im.message.receive_v1') && e.children.length===0);
    if (!el) return 'not found';
    let row = el; for (let i=0;i<3 && row;i++) row = row.parentElement;
    const cb = row.querySelector('input[type=checkbox]');
    if (cb) { cb.click(); return 'checkbox clicked'; }
    row.click(); return 'row clicked';
  });
  console.log(clicked);
  await p.waitForTimeout(1200);
  const cnt = await m.innerText();
  console.log(cnt.match(/Events selected: \d+/)?.[0] || 'no counter');
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/event-selected.png'});
  const add = await p.evaluate(() => {
    const mm = document.querySelector('.ud__modal');
    const btn = Array.from(mm.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Add');
    if (!btn) return 'no add';
    btn.click(); return 'add clicked';
  });
  console.log(add);
  await p.waitForTimeout(4000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('has receive_v1:', body.includes('im.message.receive_v1'));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
