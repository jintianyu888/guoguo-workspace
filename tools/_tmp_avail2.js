
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  await p.getByText('View Version Details').first().click({force:true});
  await p.waitForTimeout(6000);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Availability');return i>=0? s.slice(i,i+400).replace(/\n+/g,' | ') : 'no availability';});
  console.log('AV:', t);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,12));
  console.log('BTNS:', JSON.stringify(btns));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/avail-detail.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
