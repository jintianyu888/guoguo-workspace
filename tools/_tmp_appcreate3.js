
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  // 已存在就不重复建
  const body0 = await p.evaluate(()=>document.body.innerText);
  if (body0.includes('剪辑管家')) { console.log('EXISTS'); await b.close(); return; }
  await p.getByText('Create Custom App', {exact:true}).click();
  await p.waitForTimeout(3000);
  const dlg = p.locator('.semi-modal-content, [role=dialog]').last();
  const nameBox = dlg.getByPlaceholder(/name|名称/i).first();
  const cnt = await nameBox.count();
  console.log('name input found:', cnt);
  if (cnt === 0) {
    const inputs = await dlg.locator('input[type=text]').count();
    console.log('dialog text inputs:', inputs);
    await dlg.locator('input[type=text]').first().fill('剪辑管家');
  } else {
    await nameBox.fill('剪辑管家');
  }
  const ta = dlg.locator('textarea').first();
  if (await ta.count()) await ta.fill('视频剪辑与后期：粗剪、字幕、配乐、导出、归档');
  await p.waitForTimeout(600);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg-filled.png'});
  await dlg.getByRole('button', {name:/^Create$|创建/}).click();
  await p.waitForTimeout(7000);
  const body1 = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body1.includes('剪辑管家'), '| url:', p.url());
  const m = body1.match(/[^\n]*剪辑管家[^\n]*/); if (m) console.log('ROW:', m[0].slice(0,120));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-create.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
