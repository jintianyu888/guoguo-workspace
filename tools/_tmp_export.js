
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(7000);
  const box = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(e => (e.innerText||'').trim()==='Batch Actions');
    if (!btn) return null;
    const r = btn.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
  });
  console.log('batch:', JSON.stringify(box));
  if (!box) { await b.close(); return; }
  await p.mouse.click(box.x, box.y);
  await p.waitForTimeout(2000);
  const item = await p.evaluate(()=>{
    const el = Array.from(document.querySelectorAll('*')).find(e=>/Batch import\/export scopes/i.test(e.innerText||'') && (e.innerText||'').length<40);
    if (!el) return null;
    const r = el.getBoundingClientRect(); return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};
  });
  console.log('item:', JSON.stringify(item));
  if (!item) { await b.close(); return; }
  await p.mouse.click(item.x, item.y);
  await p.waitForTimeout(3000);
  await p.evaluate(()=>{const m=document.querySelector('.ud__modal');if(!m)return;const t=Array.from(m.querySelectorAll('*')).find(x=>(x.innerText||'').trim()==='Export'&&x.children.length===0);if(t)t.click();});
  await p.waitForTimeout(2500);
  const exported = await p.evaluate(()=>{
    const m = document.querySelector('.ud__modal'); if(!m) return 'no modal';
    const ta = m.querySelector('textarea'); return ta ? ta.value.slice(0,900) : 'no textarea';
  });
  console.log('EXPORT:', exported);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
