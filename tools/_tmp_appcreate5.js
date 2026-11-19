
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  if ((await p.evaluate(()=>document.body.innerText)).includes('剪辑管家')) { console.log('EXISTS'); await b.close(); return; }
  await p.getByText('Create Custom App', {exact:true}).click();
  await p.waitForTimeout(3500);
  const inp = p.locator('input[type=text]').first();
  console.log('visible?', await inp.isVisible(), 'count', await p.locator('input[type=text]').count());
  await inp.click();
  await inp.type('剪辑管家', {delay: 60});
  const ta = p.locator('textarea').first();
  await ta.click(); await ta.type('视频剪辑与后期：粗剪、字幕、配乐、导出、归档', {delay: 10});
  const fi = p.locator('input[type=file]').first();
  if (await fi.count()) await fi.setInputFiles('/home/j/.openclaw/workspace/state/icons/icon-video.png');
  await p.waitForTimeout(2500);
  const vals = await p.evaluate(()=>Array.from(document.querySelectorAll('input[type=text],textarea')).map(e=>e.value.slice(0,20)));
  console.log('values', JSON.stringify(vals));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg-filled3.png'});
  const btn = p.locator('button', {hasText:'Create'}).last();
  await btn.click();
  await p.waitForTimeout(8000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'));
  console.log('ROW:', JSON.stringify(body.split('\n').filter(l=>/剪辑管家/.test(l)).slice(0,2)));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
