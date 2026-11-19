
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const d = document.querySelector('.ud__modal');
    return {text: d.innerText.replace(/\n+/g,' | ').slice(0,600),
      tas: Array.from(d.querySelectorAll('textarea')).map(t=>({ph:t.placeholder, val:t.value.slice(0,40)})),
      btns: Array.from(d.querySelectorAll('button')).map(b=>(b.innerText||'').trim())};
  });
  console.log(JSON.stringify(info, null, 1).slice(0,1200));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
