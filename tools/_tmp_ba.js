
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const SCOPES = ["im:message","im:message:readonly","im:message:send_as_bot","im:message.p2p_msg:readonly","im:message.group_at_msg:readonly","im:message.group_msg","im:resource","im:chat:readonly","contact:user.base:readonly"];
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const box = await p.evaluate(() => {
    const btn = Array.from(document.querySelectorAll('button')).find(e => (e.innerText||'').trim()==='Batch Actions');
    if (!btn) return null;
    const r = btn.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
  });
  console.log('batch:', JSON.stringify(box));
  if (!box) { await b.close(); return; }
  await p.mouse.click(box.x, box.y);
  await p.waitForTimeout(2000);
  const items = await p.evaluate(()=>Array.from(document.querySelectorAll('li,div[role=menuitem],span,a')).map(e=>(e.innerText||'').trim()).filter(t=>/import/i.test(t)).slice(0,5));
  console.log('menu:', JSON.stringify(items));
  const cnt = await p.evaluate(()=>{const el=Array.from(document.querySelectorAll('*')).find(e=>/Batch import\/export scopes/i.test(e.innerText||'') && (e.innerText||'').length<40);if(!el)return 'no item';const r=el.getBoundingClientRect();return JSON.stringify({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});});
  console.log('item pos:', cnt);
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
