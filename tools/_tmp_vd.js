
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version/7709892498974051588', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(7000);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Availability');return i>=0? s.slice(i,i+300).replace(/\n+/g,' | ') : 'none';});
  console.log('AV:', t);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim(), y:Math.round(b.getBoundingClientRect().y)})).filter(b=>b.t));
  console.log('BTNS:', JSON.stringify(btns).slice(0,400));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/ver-detail2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
