
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.getByText('View Version Details').first().click({force:true});
  await p.waitForTimeout(5000);
  const info = await p.evaluate(()=>({url: location.href, txt: document.body.innerText.replace(/\n+/g,' | ').slice(0,300)}));
  console.log(JSON.stringify(info).slice(0,500));
  const pub = p.getByRole('button', {name:'Publish', exact:true}).first();
  const n = await pub.count();
  console.log('publish buttons:', n);
  if (n) {
    const box = await pub.boundingBox();
    console.log('box', JSON.stringify(box));
    await p.mouse.click(box.x+box.width/2, box.y+box.height/2);
    await p.waitForTimeout(5000);
    const d = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?m.innerText.replace(/\n+/g,' | ').slice(0,300):'no modal';});
    console.log('dialog:', d);
  }
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/publish3.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
