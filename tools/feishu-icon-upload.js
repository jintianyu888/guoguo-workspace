#!/usr/bin/env node
// feishu-icon-upload.js —— 给飞书自建应用换头像并发布版本（常驻控制台会话 CDP 9333）
// 用法: node tools/feishu-icon-upload.js <appId> <图片路径> "<更新说明>"
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const [appId, iconPath, notes] = process.argv.slice(2);
if (!appId || !iconPath) { console.error("用法: <appId> <icon.png> [notes]"); process.exit(2); }
const NOTE = notes || "更新应用图标";
const SHOT = "/home/j/.openclaw/workspace/state/scratch/";

(async () => {
  const b = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = b.contexts()[0];
  const p = ctx.pages().find(x => x.url().includes("open.feishu.cn")) || await ctx.newPage();
  await p.bringToFront();

  const banner = async () => p.evaluate(() => (document.body.innerText.match(/The changes[^\n]*/) || [""])[0]);

  await p.goto("https://open.feishu.cn/app/" + appId + "/baseinfo", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(4000);

  if (/will take effect/.test(await banner())) {
    console.log("已有未发布变更，跳过上传直接发布");
  } else {
    const pencil = await p.evaluate(() => {
      const h = [...document.querySelectorAll("*")].find(e => e.children.length === 0 && e.textContent.trim() === "General info");
      const svg = h && h.parentElement.querySelector("svg");
      if (!svg) return null;
      const r = svg.getBoundingClientRect();
      return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) };
    });
    if (!pencil) throw new Error("找不到 General info 编辑铅笔");
    await p.mouse.click(pencil.x, pencil.y);
    await p.waitForTimeout(1500);
    await p.locator("input[type=file]").first().setInputFiles(iconPath);
    await p.waitForTimeout(2500);
    // 弹窗内 Save
    await p.evaluate(() => {
      const bs = [...document.querySelectorAll("button")].filter(x => x.innerText.trim() === "Save" && x.closest("[class*=modal],[role=dialog]"));
      (bs[0] || [...document.querySelectorAll("button")].filter(x => x.innerText.trim() === "Save").pop()).click();
    });
    await p.waitForTimeout(2500);
    // 区块 Save（DOM 点击，避开视口外坐标）
    await p.evaluate(() => {
      const bs = [...document.querySelectorAll("button")].filter(x => x.innerText.trim() === "Save" && x.offsetParent !== null);
      if (bs.length) bs[bs.length - 1].click();
    });
    await p.waitForTimeout(3500);
    console.log("图标已保存，banner:", await banner());
  }

  if (!(await p.locator("button:has-text('Create Version')").count())) {
    if (!(await p.locator("button:has-text('View Version Details')").count())) {
      throw new Error("既没有 Create Version 也没有 View Version Details");
    }
  }
  if (await p.locator("button:has-text('Create Version')").count()) {
    await p.locator("button:has-text('Create Version')").first().click();
    await p.waitForTimeout(3500);
    await p.locator("textarea").first().fill(NOTE);
    await p.waitForTimeout(400);
    await p.evaluate(() => {
      const bs = [...document.querySelectorAll("button")].filter(x => x.innerText.trim() === "Save" && x.offsetParent !== null);
      if (bs.length) bs[bs.length - 1].click();
    });
    await p.waitForTimeout(4500);
  } else {
    await p.locator("button:has-text('View Version Details')").first().click();
    await p.waitForTimeout(3000);
  }

  // 发布：点 Publish → 确认弹窗 → 再点 Publish
  if (await p.locator("button:has-text('Publish')").count()) {
    await p.locator("button:has-text('Publish')").first().click();
    await p.waitForTimeout(2500);
    const n = await p.locator("button:has-text('Publish')").count();
    if (n > 1) {
      await p.locator("button:has-text('Publish')").last().click({ force: true });
      await p.waitForTimeout(5000);
    }
  }

  await p.goto("https://open.feishu.cn/app/" + appId + "/baseinfo", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(4000);
  const left = await banner();
  await p.screenshot({ path: SHOT + "icon-upload-" + appId.slice(-6) + ".png" });
  console.log(left ? "仍未发布：" + left : "已发布（无待发布变更）");
  // 保持控制台浏览器常驻：不关闭 CDP 连接
  process.exit(left ? 1 : 0);
})();
