
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const SCOPES = ["im:message","im:message:readonly","im:message:send_as_bot","im:message.p2p_msg:readonly","im:message.group_at_msg:readonly","im:message.group_msg","im:resource","im:chat:readonly","contact:user.base:readonly"];
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.goto('https://open.feishu.cn/app/cli_aa75b668ad38dcf3/auth', {waitUntil:'domcontentloaded', timeout:60000});
  await p.waitForTimeout(6000);
  const cur = await p.evaluate(()=>document.body.innerText.length);
  const box = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(e => /Batch import\/export scopes/i.test(e.innerText||''));
    if (!btn) return null;
    const r = btn.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
  });
  console.log('batch btn:', JSON.stringify(box));
  if (!box) { await b.close(); return; }
  await p.mouse.click(box.x, box.y);
  await p.waitForTimeout(3000);
  const payload = JSON.stringify({scopes:{tenant:SCOPES,user:[]}}, null, 2);
  const filled = await p.evaluate((pl) => {
    const m = document.querySelector('.ud__modal'); if (!m) return 'no modal';
    const ta = m.querySelector('textarea'); if (!ta) return 'no ta';
    const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
    s.call(ta, pl); ta.dispatchEvent(new Event('input',{bubbles:true}));
    return 'filled '+ta.value.length;
  }, payload);
  console.log(filled);
  await p.waitForTimeout(1000);
  const nxt = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');const b=Array.from(m.querySelectorAll('button')).find(x=>/Next, Review New Scopes/.test(x.innerText||''));if(!b)return 'no next';b.click();return 'next';});
  console.log(nxt);
  await p.waitForTimeout(3500);
  const rev = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');return m?m.innerText.replace(/\n+/g,' | ').slice(0,300):'closed';});
  console.log('review:', rev);
  const add = await p.evaluate(()=>{const m=document.querySelector('.ud__modal');if(!m)return 'closed';const b=Array.from(m.querySelectorAll('button')).find(x=>(x.innerText||'').trim()==='Add');if(!b)return 'no add';b.click();return 'added';});
  console.log(add);
  await p.waitForTimeout(3000);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
