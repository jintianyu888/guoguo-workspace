
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  await p.getByText('Create Custom App', {exact:true}).click();
  await p.waitForTimeout(3500);
  console.log('URL:', p.url());
  const modal = await p.evaluate(() => {
    const cands = Array.from(document.querySelectorAll('div')).filter(d=>/App name|应用名称|Icon|Create|Cancel/.test(d.innerText||''));
    const m = cands[cands.length-1];
    return m ? m.innerText.slice(0,600) : 'none';
  });
  console.log('MODAL:', modal.replace(/\n+/g,' | '));
  const inputs = await p.evaluate(() => Array.from(document.querySelectorAll('input')).map(i=>({ph:i.placeholder, type:i.type})));
  console.log('INPUTS:', JSON.stringify(inputs));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/create-dialog.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
