
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const btns = p.getByRole('button', {name:'Create Version', exact:true});
  await btns.last().click({force:true});
  await p.waitForTimeout(4500);
  const d = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    if (!m) return 'no modal';
    return {text: m.innerText.replace(/\n+/g,' | ').slice(0,500),
      inputs: Array.from(m.querySelectorAll('input')).map(i=>({ph:i.placeholder||'', val:i.value.slice(0,10)})),
      tas: Array.from(m.querySelectorAll('textarea')).length,
      btns: Array.from(m.querySelectorAll('button')).map(x=>(x.innerText||'').trim()).filter(Boolean)};
  });
  console.log(JSON.stringify(d).slice(0,900));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/version-dialog.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
