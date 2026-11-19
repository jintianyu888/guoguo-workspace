
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
(async () => {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9333');
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || await ctx.newPage();
  if ((await p.evaluate(()=>document.body.innerText)).includes('剪辑管家')) { console.log('EXISTS'); await b.close(); return; }
  const setv = await p.evaluate(() => {
    const d = document.querySelector('.create-app-dialog');
    if (!d) return 'no dialog';
    const inp = d.querySelector('input.ud__native-input');
    const ta = d.querySelector('textarea');
    const iset = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
    const tset = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
    iset.call(inp, '剪辑管家'); inp.dispatchEvent(new Event('input',{bubbles:true}));
    tset.call(ta, '视频剪辑与后期：粗剪、字幕、配乐、导出、归档'); ta.dispatchEvent(new Event('input',{bubbles:true}));
    return [inp.value, ta.value.slice(0,10)];
  });
  console.log('set:', JSON.stringify(setv));
  const fi = p.locator('.create-app-dialog input[type=file]').first();
  if (await fi.count()) await fi.setInputFiles('/home/j/.openclaw/workspace/state/icons/icon-video.png');
  await p.waitForTimeout(2500);
  console.log('after icon:', JSON.stringify(await p.evaluate(()=>{const d=document.querySelector('.create-app-dialog');return [d.querySelector('input.ud__native-input').value, d.querySelector('textarea').value.slice(0,8)];})));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/dlg-final.png'});
  await p.locator('.create-app-dialog button').filter({hasText:/^Create$/}).first().click({force:true});
  await p.waitForTimeout(9000);
  const body = await p.evaluate(()=>document.body.innerText);
  console.log('created:', body.includes('剪辑管家'));
  await p.screenshot({path:'/home/j/.openclaw/workspace/state/test/after-final.png'});
  await b.close();
})().catch(e=>{console.error('ERR', e.message); process.exit(1)});
