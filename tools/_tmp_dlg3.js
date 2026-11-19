
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(5000);
  await p.getByText('Create Custom App', {exact:true}).click();
  await p.waitForTimeout(3500);
  const info = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button'));
    const create = btns.find(b => /^(Create|创建)$/.test((b.innerText||'').trim()));
    if (!create) return {err:'no create button'};
    let node = create, depth = 0;
    while (node && depth < 8) { node = node.parentElement; depth++; }
    const container = create.closest('[class*=modal]') || create.parentElement.parentElement.parentElement;
    const inputs = Array.from(container.querySelectorAll('input,textarea')).map(i=>({tag:i.tagName, ph:i.placeholder||'', type:i.type||'', cls:(i.className||'').slice(0,30)}));
    return {containerClass: container.className, text: container.innerText.replace(/\n+/g,' | ').slice(0,400), inputs};
  });
  console.log(JSON.stringify(info, null, 1).slice(0, 2000));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
