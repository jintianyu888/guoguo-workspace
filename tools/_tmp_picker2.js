
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const set = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    const inp = m.querySelector('input.ud__native-input');
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    s.call(inp, 'im:message'); inp.dispatchEvent(new Event('input',{bubbles:true}));
    return inp.value;
  });
  console.log('searched:', set);
  await p.waitForTimeout(3500);
  const res = await p.evaluate(()=>{
    const m = document.querySelector('.ud__modal');
    const rows = Array.from(m.querySelectorAll('[class*=row], tr, li')).map(r=>(r.innerText||'').replace(/\s+/g,' ').trim()).filter(t=>/im:message/.test(t)).slice(0,20);
    return rows;
  });
  console.log(JSON.stringify(res, null, 1).slice(0, 1400));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/scope-search.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
