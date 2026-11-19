
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const SCOPES = ["im:message","im:message:readonly","im:message:send_as_bot","im:message.p2p_msg:readonly","im:message.group_at_msg:readonly","im:message.group_msg","im:resource","im:chat:readonly","contact:user.base:readonly"];
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  await p.evaluate(() => {
    const els = Array.from(document.querySelectorAll('button,div,span,a'));
    const t = els.find(e => /Batch import\/export scopes/i.test((e.innerText||'').trim()) && (e.innerText||'').length < 40);
    if (t) t.click();
  });
  await p.waitForTimeout(3000);
  const hasTA = await p.locator('textarea').count();
  console.log('textareas:', hasTA);
  const payload = JSON.stringify({scopes: SCOPES.map(s=>({name:s}))}, null, 2);
  if (hasTA) {
    await p.locator('textarea').last().fill(payload, {force:true});
  } else {
    const ta = await p.evaluate((t) => { const d=document.querySelector('.ud__modal'); if(!d) return 'no modal'; const a=d.querySelector('textarea'); if(!a) return 'no ta'; a.focus(); return 'focused'; }, payload);
    console.log('fallback:', ta);
    await p.keyboard.type(payload, {delay:1});
  }
  await p.waitForTimeout(1500);
  const btns = await p.evaluate(()=>Array.from(document.querySelectorAll('.ud__modal button, [role=dialog] button')).map(b=>(b.innerText||'').trim()).filter(Boolean));
  console.log('modal buttons:', JSON.stringify(btns));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/batch-dialog.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
