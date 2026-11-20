
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/version', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  await p.getByRole('button', {name:'Create Version', exact:true}).last().click({force:true});
  await p.waitForTimeout(6000);
  const before = await p.evaluate(()=>{
    const inp = document.querySelector('input.ud__native-input');
    return {ver: inp? inp.value : null, url: location.href};
  });
  console.log('before:', JSON.stringify(before));
  const set = await p.evaluate(() => {
    const inp = document.querySelector('input.ud__native-input');
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    s.call(inp, '1.0.2'); inp.dispatchEvent(new Event('input',{bubbles:true}));
    const ta = document.querySelector('textarea');
    if (ta) { const ts = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set; ts.call(ta,'修正事件订阅长连接'); ta.dispatchEvent(new Event('input',{bubbles:true})); }
    return inp.value;
  });
  console.log('set ver:', set);
  await p.waitForTimeout(1200);
  await p.getByRole('button', {name:'Save', exact:true}).click({force:true});
  await p.waitForTimeout(6000);
  const after = await p.evaluate(()=>{
    const msgs = Array.from(document.querySelectorAll('[class*=toast],[class*=message],[class*=notice],[class*=error]')).map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,4);
    const btns = Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(Boolean).slice(0,8);
    return {msgs, btns, url: location.href};
  });
  console.log('after:', JSON.stringify(after).slice(0,700));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/ver-save-102.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
