
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,700));
  console.log(t);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,10));
  console.log('btns:', JSON.stringify(btns));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/version-page.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
