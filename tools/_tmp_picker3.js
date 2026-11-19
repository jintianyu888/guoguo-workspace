
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  await p.evaluate(()=>{const btn=Array.from(document.querySelectorAll('button')).find(x=>/Add permission scopes to app/.test(x.innerText||''));if(btn)btn.click();});
  await p.waitForTimeout(4000);
  const ok = await p.evaluate(() => {
    const m = document.querySelector('.ud__modal'); if (!m) return 'no modal';
    const inp = m.querySelector('input.ud__native-input'); if (!inp) return 'no input';
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    s.call(inp, 'im:message'); inp.dispatchEvent(new Event('input',{bubbles:true}));
    return 'typed';
  });
  console.log(ok);
  await p.waitForTimeout(4000);
  const rows = await p.evaluate(()=>{
    const m = document.querySelector('.ud__modal');
    return Array.from(m.querySelectorAll('*')).filter(e=>e.children.length===0 && /^im:message/.test((e.textContent||'').trim())).map(e=>e.textContent.trim()).slice(0,15);
  });
  console.log('rows:', JSON.stringify(rows));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/scope-search2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
