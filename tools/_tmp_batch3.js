
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const vp = p.viewportSize();
  console.log('viewport:', JSON.stringify(vp));
  const box = await p.evaluate(() => {
    const els = Array.from(document.querySelectorAll('button'));
    const t = els.find(e => /Batch import\/export scopes/i.test((e.innerText||'')));
    if (!t) return null;
    const r = t.getBoundingClientRect();
    return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height};
  });
  console.log('btn box:', JSON.stringify(box));
  if (box) { await p.mouse.click(box.x, box.y); }
  await p.waitForTimeout(3000);
  console.log('dialogs:', await p.locator('.ud__modal').count(), 'textareas:', await p.locator('textarea').count());
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/batch-dialog2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
