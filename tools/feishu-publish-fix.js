#!/usr/bin/env node
// feishu-publish-fix.js <appId> —— 兜底发布：DOM 级点击 Publish + 确认弹窗
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const appId = process.argv[2];
if (!appId) { console.error("用法: <appId>"); process.exit(2); }
(async () => {
  const b = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = b.contexts()[0];
  const p = ctx.pages().find(x => x.url().includes("open.feishu.cn")) || await ctx.newPage();
  await p.bringToFront();
  const banner = async () => p.evaluate(() => (document.body.innerText.match(/The changes[^\n]*/) || [""])[0]);
  const clickText = async (txt) => p.evaluate((t) => {
    const bs = [...document.querySelectorAll("button")].filter(b => b.offsetParent !== null);
    const hit = bs.filter(b => b.innerText.trim() === t).pop();
    if (!hit) return false; hit.click(); return true;
  }, txt);
  for (let round = 0; round < 4; round++) {
    await p.goto("https://open.feishu.cn/app/" + appId + "/baseinfo", { waitUntil: "domcontentloaded" });
    await p.waitForTimeout(3500);
    const bl = await banner();
    if (!bl) { console.log("OK 无待发布变更"); break; }
    // 进入版本发布页
    if (!/version/.test(p.url())) {
      const went = await p.evaluate(() => {
        const a = [...document.querySelectorAll("a,[role=menuitem],div")].find(e => /Version Management|发布管理/.test(e.textContent || "") && e.offsetParent);
        if (a) { a.click(); return true; } return false;
      });
      await p.waitForTimeout(3000);
    }
    const pub1 = await clickText("Publish");
    await p.waitForTimeout(2000);
    const pub2 = await clickText("Publish");
    await p.waitForTimeout(5000);
    if (!pub1 && !pub2) { console.log("WARN 找不到 Publish 按钮，url=" + p.url()); }
    const after = await banner();
    if (!after) { console.log("OK 已发布"); break; }
  }
  const left = await banner();
  console.log(left ? "FAIL 仍有待发布：" + left.slice(0, 80) : "OK 发布完成");
  // 保持控制台浏览器常驻：不关闭 CDP 连接
  process.exit(/FAIL/.test(left ? "FAIL" : "") ? 1 : 0);
})().catch(e => { console.error("FATAL", e.message); process.exit(1); });
