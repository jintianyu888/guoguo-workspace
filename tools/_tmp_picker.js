
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.evaluate(()=>{const btn=Array.from(document.querySelectorAll('button')).find(x=>/Add permission scopes to app/.test(x.innerText||''));if(btn)btn.click();});
  await p.waitForTimeout(4000);
  const info = await p.evaluate(()=>{
    const m = document.querySelector('.ud__modal') || document.querySelector('[class*=drawer]');
    if (!m) return 'none';
    return {text: m.innerText.replace(/\n+/g,' | ').slice(0,300), inputs: Array.from(m.querySelectorAll('input')).map(i=>i.placeholder||'')};
  });
  console.log(JSON.stringify(info).slice(0,600));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/scope-picker.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
