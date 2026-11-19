
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const added = await p.evaluate(() => {
    const d = document.querySelector('.ud__modal');
    const btn = Array.from(d.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Add');
    if (!btn) return 'no add';
    btn.click(); return 'added';
  });
  console.log(added);
  await p.waitForTimeout(4000);
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/event', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,900));
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/events.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
