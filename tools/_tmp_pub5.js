
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Publish');
    if (!btn) return 'no btn';
    btn.click();
    return 'js clicked';
  });
  console.log(r);
  await p.waitForTimeout(2500);
  const msgs = await p.evaluate(()=>Array.from(document.querySelectorAll('[class*=toast],[class*=message],[class*=notice]')).map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,5));
  console.log('messages:', JSON.stringify(msgs));
  const modal = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?m.innerText.replace(/\n+/g,' | ').slice(0,400):'no modal';});
  console.log('modal:', modal);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/publish4.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
