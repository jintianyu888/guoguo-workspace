
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const has = await p.evaluate(()=>document.body.innerText.includes('剪辑管家'));
  if (has) { console.log('EXISTS'); await b.close(); return; }
  const inp = p.locator('input[type=text]').first();
  await inp.fill('剪辑管家', {force:true});
  const ta = p.locator('textarea').first();
  await ta.fill('视频剪辑与后期：粗剪、字幕、配乐、导出、归档', {force:true});
  const fi = p.locator('input[type=file]').first();
  if (await fi.count()) await fi.setInputFiles('/home/j/.openclaw/workspace/state/icons/icon-video.png');
  await p.waitForTimeout(2000);
  console.log('values', JSON.stringify(await p.evaluate(()=>Array.from(document.querySelectorAll('input[type=text],textarea')).map(e=>e.value.slice(0,16)))));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg-filled4.png'});
  const btn = p.locator('.ud__dialog__footer button, .ud__modal__footer__btns button').filter({hasText:/Create/}).first();
  await btn.click({force:true});
  await p.waitForTimeout(9000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'), '| url:', p.url());
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-create3.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
