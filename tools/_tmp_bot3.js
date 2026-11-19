
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const adds = p.getByRole('button', {name:'Add', exact:true});
  console.log('add count:', await adds.count());
  await adds.nth(0).scrollIntoViewIfNeeded();
  await adds.nth(0).click({force:true});
  await p.waitForTimeout(4500);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,500));
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/bot-enabled.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
