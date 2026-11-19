
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input')).map(i=>({ph:i.placeholder||'', cls:(i.className||'').slice(0,25)}));
    const btns = Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,25);
    const rows = Array.from(document.querySelectorAll('[class*=scope], tr')).slice(0,5).map(r=>(r.innerText||'').replace(/\n+/g,' / ').slice(0,100));
    return {inputs, btns, rows};
  });
  console.log(JSON.stringify(info, null, 1).slice(0,1600));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
