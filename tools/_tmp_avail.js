
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  for (const [name, id] of [['video','cli_aa75b668ad38dcf3'],['print','cli_aa3dced661b85bb7']]) {
    await p.goto('https://open.feishu.cn/app/'+id+'/version', {waitUntil:'domcontentloaded', timeout:60000});
    await p.waitForTimeout(5000);
    const t = await p.evaluate(()=>{const s=document.body.innerText;const i=s.indexOf('Availability');return i>=0? s.slice(i,i+220).replace(/\n+/g,' | ') : 'not on page';});
    console.log(name, '→', t);
  }
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
