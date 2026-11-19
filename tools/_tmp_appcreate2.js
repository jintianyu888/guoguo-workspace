
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const inputs = p.locator('input[type=text]');
  // name = first text input inside dialog
  await inputs.nth(0).fill('剪辑管家');
  const ta = p.locator('textarea').first();
  if (await ta.count()) await ta.fill('视频剪辑与后期：粗剪、字幕、配乐、导出、归档');
  await p.waitForTimeout(800);
  await p.getByRole('button', {name:'Create', exact:true}).click();
  await p.waitForTimeout(6000);
  console.log('URL after create:', p.url());
  const txt = await p.evaluate(()=>document.body.innerText.slice(0,1200));
  console.log(txt.replace(/\n+/g,' | ').slice(0,1200));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/created-app.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
