
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  const info = await p.evaluate(() => {
    const all = Array.from(document.querySelectorAll('*'));
    const star = all.find(e => (e.textContent||'').includes('∗∗∗∗') && e.children.length === 0);
    if (!star) return 'no star el';
    let node = star;
    for (let i=0;i<4 && node;i++) node = node.parentElement;
    const icons = node ? Array.from(node.querySelectorAll('svg,i,span[class*=icon],button')).map(x=>({tag:x.tagName, cls:(x.getAttribute('class')||'').slice(0,30)})) : [];
    return {icons, text: node ? node.innerText.slice(0,80) : 'none'};
  });
  console.log(JSON.stringify(info).slice(0,700));
  // 点击 App Secret 行右侧第一个 svg 图标
  const done = await p.evaluate(() => {
    const all = Array.from(document.querySelectorAll('*'));
    const star = all.find(e => (e.textContent||'').includes('∗∗∗∗') && e.children.length === 0);
    if (!star) return 'no star';
    let row = star.closest('div');
    for (let i=0;i<3 && row;i++) row = row.parentElement;
    const svg = row && row.querySelector('svg');
    if (!svg) return 'no svg';
    svg.dispatchEvent(new MouseEvent('click',{bubbles:true}));
    return 'svg clicked';
  });
  console.log(done);
  await p.waitForTimeout(2500);
  const secret = await p.evaluate(() => {
    const inputs = Array.from(document.querySelectorAll('input')).map(i=>i.value).filter(v=>v && v.length>10);
    const txt = document.body.innerText.match(/App Secret\s*\|?\s*([A-Za-z0-9]{10,})/);
    return {inputs, txt: txt?txt[1]:null, body: document.body.innerText.split('\n').filter(l=>/^[A-Za-z0-9]{20,}$/.test(l.trim())).slice(0,3)};
  });
  console.log(JSON.stringify(secret).slice(0,600));
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
