const fs = require('fs');
const { chromium } = require('/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core');
const ADB = '/home/j/.local/opt/platform-tools/adb.exe';
const { execFileSync } = require('child_process');
const LOG = '/tmp/mw-autologin.log';
function log(m){ fs.appendFileSync(LOG, new Date().toISOString()+' '+m+'\n'); }
function smsCode(){
  try{
    const out = execFileSync(ADB, ['shell','content','query','--uri','content://sms/inbox','--projection','date,body'], {encoding:'utf8', timeout:20000});
    const rows = out.split('Row:').slice(1).map(r=>{
      const d = /date=(\d+)/.exec(r); const b = /body=(.*)$/s.exec(r.trim());
      return {d: d?+d[1]:0, b: b?b[1].trim():''};
    }).sort((a,b)=>b.d-a.d);
    for (const r of rows.slice(0,8)){
      if (!/拓竹|Bambu|bambulab|验证码|verification/i.test(r.b)) continue;
      const m = /(\d{6})/.exec(r.b);
      if (m) return {code:m[1], when:r.d, body:r.b.slice(0,80)};
    }
  }catch(e){ log('sms err '+e.message); }
  return null;
}
(async()=>{
  const start = Date.now();
  const b = await chromium.connectOverCDP('http://127.0.0.1:9334');
  const p = b.contexts()[0].pages()[0];
  try{
    for (let i=0;i<120;i++){
      const t = await p.evaluate(()=>document.body.innerText.replace(/\n/g,' | '));
      if (/交换相邻图案/.test(t)) { await p.waitForTimeout(5000); continue; }
      log('captcha cleared; state='+t.slice(0,140));
      const s = smsCode();
      if (s && s.when > start - 180000){
        log('code='+s.code+' from sms');
        const boxes = await p.$$('input[placeholder="验证码*"], input[placeholder*="验证码"]');
        if (boxes.length === 1){
          await boxes[0].fill(s.code);
        } else if (boxes.length >= 6){
          for (let k=0;k<6;k++){ await boxes[k].type(s.code[k]); }
        } else {
          const any = await p.$('input[maxlength="6"]');
          if (any) await any.fill(s.code);
        }
        await p.waitForTimeout(600);
        await p.getByText('登录 / 注册', {exact:true}).last().click().catch(async()=>{
          await p.getByRole('button',{name:/登录/}).first().click().catch(()=>{});
        });
        await p.waitForTimeout(6000);
        const after = await p.evaluate(()=>location.href+' || '+document.body.innerText.replace(/\n/g,' | ').slice(0,160));
        log('AFTER='+after);
        break;
      } else {
        log('no sms code yet (state='+t.slice(0,80)+')');
      }
      await p.waitForTimeout(10000);
    }
  }catch(e){ log('ERR '+e.message); }
  await b.close().catch(()=>{});
})();
