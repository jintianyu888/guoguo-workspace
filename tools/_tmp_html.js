
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const html = await p.evaluate(() => {
    const d = document.querySelector('.create-app-dialog');
    if (!d) return 'none';
    const walk = (el, depth) => {
      if (depth > 6) return '';
      let s = '';
      for (const c of el.children) {
        const cls = (c.className && c.className.toString().slice(0,40)) || '';
        const txt = (c.children.length===0 ? (c.innerText||'').slice(0,30) : '');
        s += '  '.repeat(depth) + c.tagName + '.' + cls + (txt?(' «'+txt+'»'):'') + '\n';
        s += walk(c, depth+1);
      }
      return s;
    };
    return walk(d, 0).slice(0, 2500);
  });
  console.log(html);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
