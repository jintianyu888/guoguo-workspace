
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/event', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const clicked = await p.evaluate(() => {
    const node = Array.from(document.querySelectorAll('*')).find(e=>(e.innerText||'').trim()==='Subscription mode');
    if (!node) return 'no label';
    const row = node.closest('div').parentElement;
    const btn = row.querySelector('button');
    if (btn) { btn.click(); return 'clicked btn'; }
    return 'no btn';
  });
  console.log(clicked);
  await p.waitForTimeout(3500);
  const t = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?m.innerText.replace(/\n+/g,' | ').slice(0,700):'no modal';});
  console.log('MODAL:', t);
  const btns = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?Array.from(m.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean):[];});
  console.log('BTNS:', JSON.stringify(btns));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/submode2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
