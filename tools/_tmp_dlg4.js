
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const modal = document.querySelector('.ud__modal');
    if (!modal) return {err:'no .ud__modal'};
    const inputs = Array.from(modal.querySelectorAll('input,textarea')).map(i=>({tag:i.tagName, ph:i.placeholder||'', type:i.type||'', cls:(i.className||'').slice(0,40)}));
    return {cls: modal.className, text: modal.innerText.replace(/\n+/g,' | ').slice(0,500), inputs};
  });
  console.log(JSON.stringify(info, null, 1).slice(0,1800));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
