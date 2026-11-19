
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const av = await p.evaluate(() => {
    const t = document.body.innerText;
    const i = t.indexOf('Availability');
    return t.slice(i, i+260).replace(/\n+/g,' | ');
  });
  console.log('AV:', av);
  const btn = p.getByRole('button', {name:'Publish', exact:true}).first();
  await btn.scrollIntoViewIfNeeded();
  await p.waitForTimeout(700);
  const box = await btn.boundingBox();
  console.log('box:', JSON.stringify(box));
  if (box) await p.mouse.click(box.x + box.width/2, box.y + box.height/2);
  await p.waitForTimeout(5000);
  const d = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    return m ? m.innerText.replace(/\n+/g,' | ').slice(0,300) : 'no modal';
  });
  console.log('dialog:', d);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/publish-confirm2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
