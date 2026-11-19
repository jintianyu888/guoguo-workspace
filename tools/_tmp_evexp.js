
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.evaluate(()=>{const e=Array.from(document.querySelectorAll('*')).find(x=>(x.innerText||'').trim()==='Expand'&&x.children.length===0);if(e)e.click();});
  await p.waitForTimeout(2500);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Message received');return s.slice(i,i+700).replace(/\n+/g,' | ');});
  console.log(t);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
