#!/usr/bin/env node
// feishu-app-audit.js v4 —— 抓 名称/appId/图标
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const fs = require("fs");
const OUT = "/home/j/.openclaw/workspace/state/icons/current";
(async () => {
  const b = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const p = await b.contexts()[0].newPage();
  await p.goto("https://open.feishu.cn/app", { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(6000);
  const all = [];
  for (let pg = 1; pg <= 5; pg++) {
    if (pg > 1) {
      const ok = await p.evaluate((n) => { const el = document.querySelector(".ud__pagination-item-" + n); if (!el) return false; el.click(); return true; }, pg);
      if (!ok) break;
      await p.waitForTimeout(3500);
    }
    const rows = await p.evaluate(() => [...document.querySelectorAll("tr.ud__table-row")].map(tr => {
      const img = tr.querySelector("img");
      const txt = tr.innerText.replace(/\s+/g, " ").trim();
      return { id: tr.getAttribute("data-row-key"), name: txt.split(" ")[0], src: img ? img.src : null };
    }));
    all.push(...rows);
  }
  fs.writeFileSync(OUT + "/index.json", JSON.stringify(all, null, 1));
  console.log("rows", all.length, "withId", all.filter(x => x.id && x.id.startsWith("cli_")).length);
  console.log(all.map(x => x.name + "=" + x.id).join(" | "));
  await p.close(); await b.close();
})().catch(e => { console.error("FATAL", e); process.exit(1); });
