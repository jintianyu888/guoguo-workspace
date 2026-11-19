
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.getByRole('button', {name:'Publish', exact:true}).first().click({force:true});
  await p.waitForTimeout(4000);
  const d = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal');
    return m ? {text: m.innerText.replace(/\n+/g,' | ').slice(0,400), btns: Array.from(m.querySelectorAll('button')).map(x=>(x.innerText||'').trim()).filter(Boolean)} : 'no modal';
  });
  console.log(JSON.stringify(d).slice(0,600));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/publish-confirm.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
