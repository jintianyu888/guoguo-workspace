
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.getByRole('button', {name:'Add Events'}).scrollIntoViewIfNeeded();
  await p.waitForTimeout(800);
  await p.getByRole('button', {name:'Add Events'}).click({force:true});
  await p.waitForTimeout(3500);
  const r = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    const drawer = document.querySelector('[class*=drawer]');
    const node = m || drawer;
    if (!node) return {err:'nothing'};
    return {cls: node.className.slice(0,40), text: node.innerText.replace(/\n+/g,' | ').slice(0,400),
      inputs: Array.from(node.querySelectorAll('input')).map(i=>({ph:i.placeholder||''}))};
  });
  console.log(JSON.stringify(r).slice(0,900));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/add-events2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
