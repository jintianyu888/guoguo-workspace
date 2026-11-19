
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const link = await p.evaluate(() => {
    const rows = Array.from(document.querySelectorAll('tr,a'));
    for (const r of rows) {
      if ((r.innerText||'').includes('剪辑管家')) {
        const a = r.tagName === 'A' ? r : r.querySelector('a');
        if (a) return a.getAttribute('href');
        const clk = r.querySelector('[class*=app-name], [class*=name]');
        if (clk) { clk.click(); return 'clicked'; }
      }
    }
    return 'not found';
  });
  console.log('link:', link);
  await p.waitForTimeout(6000);
  console.log('url:', p.url());
  if (String(p.url()).includes('/app/')) {
    const id = String(p.url()).match(/\/app\/(cli_[a-z0-9]+)/);
    console.log('appid:', id ? id[1] : 'none');
  }
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
