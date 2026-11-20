
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const r = await p.evaluate(()=>{const btn=Array.from(document.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Save');if(!btn)return 'no save';btn.click();return 'saved';});
  console.log(r);
  await p.waitForTimeout(4000);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Subscription mode');return s.slice(i,i+220).replace(/\n+/g,' | ');});
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
