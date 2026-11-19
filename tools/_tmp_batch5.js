
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const SCOPES = ["im:message","im:message:readonly","im:message:send_as_bot","im:message.p2p_msg:readonly","im:message.group_at_msg:readonly","im:message.group_msg","im:resource","im:chat:readonly","contact:user.base:readonly"];
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const payload = JSON.stringify({scopes:{tenant:SCOPES,user:[]}}, null, 2);
  const filled = await p.evaluate((pl) => {
    const d = document.querySelector('.ud__modal');
    const ta = d.querySelector('textarea');
    const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
    set.call(ta, pl); ta.dispatchEvent(new Event('input',{bubbles:true}));
    return ta.value.length;
  }, payload);
  console.log('filled chars:', filled);
  await p.waitForTimeout(1200);
  const nx = await p.evaluate(() => {
    const d = document.querySelector('.ud__modal');
    const btn = Array.from(d.querySelectorAll('button')).find(x=>/Next, Review New Scopes/.test(x.innerText||''));
    if (!btn) return 'no next';
    btn.click(); return 'next clicked';
  });
  console.log(nx);
  await p.waitForTimeout(4000);
  const after = await p.evaluate(() => {
    const d = document.querySelector('.ud__modal');
    return d ? {text: d.innerText.replace(/\n+/g,' | ').slice(0,400), btns: Array.from(d.querySelectorAll('button')).map(b=>(b.innerText||'').trim())} : 'modal closed';
  });
  console.log(JSON.stringify(after).slice(0,800));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/batch-review.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
