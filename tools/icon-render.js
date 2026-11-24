#!/usr/bin/env node
// icon-render.js —— SVG → 480×480 PNG（chromium 无头）
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");
const path = require("path");
const files = process.argv.slice(2);
if (!files.length) { console.error("用法: icon-render.js a.svg [b.svg ...]"); process.exit(2); }
(async () => {
  const b = await chromium.launch({ executablePath: "/home/j/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome", args: ["--no-sandbox"] });
  const p = await b.newPage({ viewport: { width: 480, height: 480 } });
  for (const f of files) {
    await p.goto("file://" + path.resolve(f));
    await p.waitForTimeout(150);
    await p.screenshot({ path: f.replace(/\.svg$/, ".png") });
    console.log("rendered", f);
  }
  await b.close();
})().catch(e => { console.error("FATAL", e.message); process.exit(1); });
