
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button')).filter(x=>(x.innerText||'').trim()==='Publish');
    if (!btns.length) return 'no publish';
    btns[0].click();
    return 'clicked '+btns.length;
  });
  console.log(r);
  await p.waitForTimeout(4000);
  const d = await p.evaluate(()=>{
    const m = document.querySelector('.ud__modal');
    if (m) return {type:'modal', text: m.innerText.replace(/\n+/g,' | ').slice(0,300), btns: Array.from(m.querySelectorAll('button')).map(x=>(x.innerText||'').trim()).filter(Boolean)};
    return {type:'none', msgs: Array.from(document.querySelectorAll('[class*=toast],[class*=message]')).map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,3)};
  });
  console.log(JSON.stringify(d).slice(0,600));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/pub-102.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
