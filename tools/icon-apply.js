#!/usr/bin/env node
// icon-apply.js v2 —— 换图标 + 创建版本 + 发布（DOM 级点击，浏览器常驻）
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const [appId, png, note] = process.argv.slice(2);
if (!appId || !png) { console.error("用法: <appId> <png> [note]"); process.exit(2); }
const NOTE = note || "更新应用图标";
const t0 = () => new Date().toISOString().slice(11, 19);
const log = (...a) => console.log("[" + t0() + "]", ...a);

(async () => {
  const b = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = b.contexts()[0];
  const p = ctx.pages().find(x => x.url().includes("open.feishu.cn")) || await ctx.newPage();
  await p.bringToFront();
  const banner = () => p.evaluate(() => (document.body.innerText.match(/The changes will take effect[^\n]*/) || [""])[0]);
  const clk = (t) => p.evaluate((txt) => {
    const bs = [...document.querySelectorAll("button,a,[role=button]")].filter(x => x.offsetParent !== null && x.innerText && x.innerText.trim() === txt);
    const h = bs[bs.length - 1]; if (h) { h.click(); return true; } return false;
  }, t);

  // A. 上传
  await p.goto("https://open.feishu.cn/app/" + appId + "/baseinfo", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(4000);
  if (/will take effect/.test(await banner())) log("注意：进入时已有未发布变更");
  const pencil = await p.evaluate(() => {
    const label = [...document.querySelectorAll("*")].find(e => e.children.length === 0 && e.textContent.trim() === "General info");
    if (!label) return false;
    let box = label.closest("div");
    for (let i = 0; i < 6 && box; i++) {
      const svg = box.querySelector("svg");
      if (svg) { const r = svg.getBoundingClientRect(); if (r.width > 8) { svg.dispatchEvent(new MouseEvent("click", { bubbles: true })); return true; } }
      box = box.parentElement;
    }
    return false;
  });
  if (!pencil) { log("FAIL 找不到编辑图标入口"); process.exit(3); }
  await p.waitForTimeout(2500);
  const fi = await p.$("input[type=file]");
  if (!fi) { log("FAIL 无文件输入框"); process.exit(3); }
  await fi.setInputFiles(png);
  await p.waitForTimeout(2500);
  const dlgSave = await p.evaluate(() => {
    const d = [...document.querySelectorAll(".ud__dialog,[role=dialog]")].filter(x => x.offsetParent !== null);
    if (!d.length) return false;
    const btn = [...d[0].querySelectorAll("button")].find(b => /Save|Confirm|OK/i.test(b.innerText));
    if (btn) { btn.click(); return true; } return false;
  });
  await p.waitForTimeout(2500);
  await clk("Save");
  await p.waitForTimeout(2500);

  // B. 创建版本
  await p.goto("https://open.feishu.cn/app/" + appId + "/version", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(3500);
  if (!(await clk("Create Version"))) { log("FAIL 无 Create Version"); process.exit(4); }
  await p.waitForTimeout(4000);
  const ta = await p.$("textarea");
  if (ta) { await ta.fill(NOTE); await p.waitForTimeout(500); }
  if (!(await clk("Save"))) { log("FAIL 版本保存失败"); process.exit(5); }
  await p.waitForTimeout(4500);

  // C. 发布
  let pub = false;
  for (let i = 0; i < 3; i++) {
    const a = await clk("Publish");
    await p.waitForTimeout(2500);
    const c = await clk("Publish");
    await p.waitForTimeout(6000);
    if (a || c) { pub = true; }
    const bl = await banner();
    if (!bl) break;
  }
  const left = await banner();
  if (left) { log("FAIL 仍有待发布：" + left.slice(0, 40)); process.exit(6); }
  log("OK 已发布", appId);
  process.exit(0);
})().catch(e => { console.error("FATAL", e.message); process.exit(9); });
