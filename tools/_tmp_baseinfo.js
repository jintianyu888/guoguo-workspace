
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/baseinfo', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const txt = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,1200));
  console.log(txt);
  // 尝试点开 secret 的显示/复制按钮
  const shown = await p.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button,span,a'));
    const t = btns.find(e => /^(显示|Show|查看|眼睛)$/.test((e.innerText||'').trim()));
    if (t) { t.click(); return 'clicked-show'; }
    return 'no-show-btn';
  });
  console.log(shown);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
