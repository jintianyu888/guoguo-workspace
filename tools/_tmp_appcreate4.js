
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  if ((await p.evaluate(()=>document.body.innerText)).includes('剪辑管家')) { console.log('EXISTS'); await b.close(); return; }
  await p.getByText('Create Custom App', {exact:true}).click();
  await p.waitForTimeout(3000);
  const modal = p.locator('.ud__modal').last();
  await modal.locator('input[type=text]').first().fill('剪辑管家');
  await modal.locator('textarea').first().fill('视频剪辑与后期：粗剪、字幕、配乐、导出、归档');
  const fileInput = modal.locator('input[type=file]').first();
  if (await fileInput.count()) await fileInput.setInputFiles('/home/j/.openclaw/workspace/state/icons/icon-video.png');
  await p.waitForTimeout(2500);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg-filled2.png'});
  await modal.getByRole('button', {name:/^(Create|创建)$/}).click();
  await p.waitForTimeout(8000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'), '| url:', p.url());
  const line = body.split('\n').filter(l=>/剪辑管家/.test(l)).slice(0,2);
  console.log('ROW:', JSON.stringify(line));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-create2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
