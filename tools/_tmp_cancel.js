
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');if(!m)return 'no modal';const btn=Array.from(m.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Cancel');if(!btn)return 'no cancel';btn.click();return 'canceled';});
  console.log(r);
  await p.waitForTimeout(1500);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
