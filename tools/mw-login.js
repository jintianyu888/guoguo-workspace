// mw-login.js — 用已开的持久浏览器(CDP 9334)完成拓竹/MakerWorld 登录，随后下载模型
// 用法: node mw-login.js <6位验证码> [designId]
const {chromium} = require('/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core');
const CDP = 'http://127.0.0.1:9334';
const code = process.argv[2];
const designId = process.argv[3] || '';
const OUT = '/home/j/openclaw-workspaces/maker/data/models';

(async () => {
  const b = await chromium.connectOverCDP(CDP);
  const ctx = b.contexts()[0];
  let p = ctx.pages().find(x => x.url().includes('sign-in')) || ctx.pages()[0];
  console.log('page:', p.url().slice(0, 90));

  if (code) {
    await p.fill('input[name=code]', code);
    await p.waitForTimeout(300);
    await p.evaluate(() => {
      const btn = [...document.querySelectorAll('*')].filter(e => e.children.length === 0 && /^登录\s*\/?\s*注册$/.test((e.textContent||'').trim())).pop();
      if (btn) btn.click();
    });
    await p.waitForTimeout(6000);
    const u = p.url();
    console.log('after-login-url:', u.slice(0, 120));
    const cookies = await ctx.cookies();
    const names = cookies.map(c => c.name).filter(n => /token|session|auth|mw/i.test(n)).slice(0, 8);
    console.log('auth-cookies:', names.join(',') || '(none)');
    if (u.includes('sign-in')) { console.log('LOGIN_FAILED: still on sign-in'); await b.close(); process.exit(2); }
  }

  if (designId) {
    const url = 'https://makerworld.com.cn/zh/models/' + designId;
    if (!p.url().startsWith('https://makerworld.com.cn')) await p.goto(url, {waitUntil: 'domcontentloaded', timeout: 45000});
    const meta = await p.evaluate(async (id) => {
      const r = await fetch('/api/v1/design-service/design/' + id + '/instances', {credentials: 'include'});
      const j = await r.json();
      const h = (j.hits || [])[0];
      return h ? {instanceId: h.id, title: h.title, profileId: h.profileId} : null;
    }, designId);
    console.log('meta:', JSON.stringify(meta));
    if (!meta) { console.log('NO_INSTANCE'); await b.close(); process.exit(3); }
    const dl = await p.evaluate(async (iid) => {
      const r = await fetch('/api/v1/design-service/instance/' + iid + '/f3mf?type=download', {credentials: 'include'});
      if (!r.ok) return {ok: false, status: r.status, body: (await r.text()).slice(0, 120)};
      const ct = r.headers.get('content-type') || '';
      if (ct.includes('json')) {
        const j = await r.json();
        if (j && j.url) return {ok: true, signedUrl: j.url, name: j.name || ''};
        return {ok: false, status: r.status, body: JSON.stringify(j).slice(0, 120)};
      }
      const buf = new Uint8Array(await r.arrayBuffer());
      let s = ''; for (let i = 0; i < buf.length; i += 8192) s += String.fromCharCode.apply(null, buf.subarray(i, i + 8192));
      return {ok: true, status: r.status, b64: btoa(s)};
    }, meta.instanceId);
    if (!dl.ok) { console.log('DOWNLOAD_FAILED', dl.status, dl.body); await b.close(); process.exit(4); }
    const fs = require('fs'); const path = require('path');
    const dir = path.join(OUT, String(designId)); fs.mkdirSync(dir, {recursive: true});
    let file = path.join(dir, designId + '.3mf');
    if (dl.signedUrl) {
      console.log('SIGNED_URL', dl.name || '');
      const resp = await ctx.request.get(dl.signedUrl);
      if (!resp.ok()) { console.log('CDN_FAILED', resp.status()); await b.close(); process.exit(5); }
      const buf = await resp.body();
      if (dl.name && /\.3mf$/i.test(dl.name)) file = path.join(dir, dl.name.replace(/[\/\\]/g, '_'));
      fs.writeFileSync(file, buf);
    } else {
      fs.writeFileSync(file, Buffer.from(dl.b64, 'base64'));
    }
    console.log('SAVED', file, fs.statSync(file).size);
  }
  await b.close();
})().catch(e => { console.log('ERR', e.message); process.exit(1); });

