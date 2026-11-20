
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const n = await p.getByRole('button', {name:'Create Version', exact:true}).count();
  console.log('create buttons:', n);
  await p.getByRole('button', {name:'Create Version', exact:true}).last().click({force:true});
  await p.waitForTimeout(6000);
  await p.evaluate(()=>window.scrollTo(0, document.body.scrollHeight));
  await p.waitForTimeout(1500);
  const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Availability');return i>=0? s.slice(i,i+300).replace(/\n+/g,' | ') : 'no availability section';});
  console.log('AV:', t);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim(), y:Math.round(b.getBoundingClientRect().y)})).filter(b=>b.t));
  console.log('BTNS:', JSON.stringify(btns).slice(0,500));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/create-ver-avail.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
