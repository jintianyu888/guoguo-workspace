
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const set = await p.evaluate(() => {
    const inp = document.querySelector('input.ud__native-input');
    if (!inp) return 'no input';
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    s.call(inp, '1.0.0'); inp.dispatchEvent(new Event('input',{bubbles:true}));
    const ta = document.querySelector('textarea');
    if (ta) { const ts = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set; ts.call(ta,'剪辑管家首次发布：机器人能力 + 接收消息事件'); ta.dispatchEvent(new Event('input',{bubbles:true})); }
    return [inp.value, ta ? ta.value.slice(0,10) : 'no ta'];
  });
  console.log('set:', JSON.stringify(set));
  await p.waitForTimeout(1000);
  await p.getByRole('button', {name:'Save', exact:true}).click({force:true});
  await p.waitForTimeout(6000);
  const t = await p.evaluate(()=>document.body.innerText.replace(/\n+/g,' | ').slice(0,500));
  console.log(t);
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/version-saved2.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
