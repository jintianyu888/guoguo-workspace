
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const rows = await p.evaluate(() => {
    const d = document.querySelector('.create-app-dialog');
    if (!d) return 'none';
    return Array.from(d.querySelectorAll('input,textarea,div[contenteditable]')).map(e => ({
      tag: e.tagName, type: e.getAttribute('type'), cls: (e.className||'').toString().slice(0,30),
      ce: e.getAttribute('contenteditable'), val: (e.value||'').slice(0,12), w: e.getBoundingClientRect().width
    }));
  });
  console.log(JSON.stringify(rows, null, 1).slice(0, 1200));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
