
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const focused = await p.evaluate(() => {
    const d = document.querySelector('.create-app-dialog');
    if (!d) return 'no dialog';
    const el = d.querySelector('input[type=text]');
    if (!el) return 'no input';
    el.focus(); el.click();
    return 'focused';
  });
  console.log(focused);
  await p.keyboard.type('剪辑管家', {delay: 80});
  await p.waitForTimeout(800);
  console.log('values', JSON.stringify(await p.evaluate(()=>Array.from(document.querySelectorAll('.create-app-dialog input[type=text],.create-app-dialog textarea')).map(e=>e.value.slice(0,20)))));
  const btn = p.locator('.create-app-dialog button').filter({hasText:/Create/}).first();
  await btn.click({force:true});
  await p.waitForTimeout(9000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-create4.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
