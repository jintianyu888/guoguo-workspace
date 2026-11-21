#!/usr/bin/env node
/**
 * feishu-scope-import.js — 飞书自建应用：批量导入权限 + 可选发版本（2026-11-20 沉淀）
 *
 * 前置：先 bash tools/feishu-console.sh start（复用常驻登录态，CDP 127.0.0.1:9333）
 * 用法：
 *   node tools/feishu-scope-import.js --app cli_xxx [--scopes a,b,c] [--publish] [--notes "说明"]
 *   --scopes 省略时用 DEFAULT_SCOPES（机器人收发最小集）
 *   --publish 会创建新版本（自动取下一版号）并发布
 * 退出码：0 成功 / 1 失败
 *
 * 为什么这样写（踩过的坑，别改）：
 *  1) 导入框是 Monaco：textarea.fill() 会被拦截；window.monaco 不在全局。
 *     只能用 点编辑器中心 → Ctrl+A → Delete → keyboard.insertText(json)（CDP 整段注入，不吞字）。
 *  2) 按钮名是 'Add Scopes'，不是 'Add'；用 /^Add$/ 会点空，流程静默不生效。
 *  3) 只加权限不发版本＝不生效；发版本后状态必须是 Released。
 */
const { chromium } = require("/home/j/.npm-global/lib/node_modules/openclaw/node_modules/playwright-core");

const DEFAULT_SCOPES = [
  "im:message",
  "im:message:readonly",
  "im:message:send_as_bot",
  "im:message.p2p_msg:readonly",
  "im:message.group_at_msg:readonly",
  "im:message.group_msg",
  "im:resource",
  "im:chat:readonly",
  "contact:user.base:readonly",
];

function arg(name, def) {
  const i = process.argv.indexOf("--" + name);
  if (i < 0) return def;
  const v = process.argv[i + 1];
  return v && !v.startsWith("--") ? v : true;
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const app = arg("app");
  if (!app || app === true) {
    console.error("用法: node tools/feishu-scope-import.js --app cli_xxx [--scopes a,b,c] [--publish] [--notes 说明]");
    process.exit(1);
  }
  const doExport = !!arg("export", false);
  const scopes = (arg("scopes") ? String(arg("scopes")).split(",").map((s) => s.trim()).filter(Boolean) : DEFAULT_SCOPES);
  const doPublish = !!arg("publish", false);
  const notes = String(arg("notes", "补齐接收消息权限，修复机器人收不到消息"));

  const b = await chromium.connectOverCDP("http://127.0.0.1:9333");
  const ctx = b.contexts()[0];
  const p = ctx.pages()[0] || (await ctx.newPage());
  const readCodes = async () =>
    p.evaluate(() => {
      // 逐单元格读：长 scope 会折行（im:message.p / msg:readonly），先去掉单元格内空白再整格匹配，
      // 不要用整页正则——那会把左边的中文标签粘到代码前面。
      const out = new Set();
      document.querySelectorAll("td,th,span,div").forEach((el) => {
        if (el.children.length) return;
        const t = (el.textContent || "").replace(/\s+/g, "");
        if (/^[a-z][a-z0-9]*:[a-z0-9_.:]+$/.test(t)) out.add(t);
      });
      return [...out];
    });

  // 1) 批量导入
  await p.goto("https://open.feishu.cn/app/" + app + "/auth", { waitUntil: "domcontentloaded", timeout: 60000 });
  await sleep(4500);
  await p.getByRole("button", { name: /Batch Actions/i }).first().click({ force: true });
  await sleep(1300);
  await p.getByText("Batch import/export scopes", { exact: true }).first().click();
  await sleep(2500);

  if (doExport) {
    // --export：读出当前应用已授权的 scope JSON（用于新管家做 diff，别再手抄）
    await sleep(1500);
    const dump = await p.evaluate(() =>
      [...document.querySelectorAll(".view-lines .view-line")].map((e) => e.innerText).join("\n")
    );
    console.log(dump || "(空)");
    await b.close();
    return;
  }

  const json = JSON.stringify({ scopes: { tenant: scopes, user: [] } });
  const ed = await p.$(".monaco-editor");
  if (!ed) throw new Error("找不到 Monaco 编辑器（弹窗没开？）");
  const box = await ed.boundingBox();
  await p.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await sleep(500);
  await p.keyboard.press("Control+A");
  await p.keyboard.press("Delete");
  await sleep(300);
  await p.keyboard.insertText(json);
  await sleep(1000);

  await p.getByRole("button", { name: /Next, Review New Scopes/i }).click({ force: true });
  await sleep(2500);
  const next2 = p.getByRole("button", { name: /Next, Configure Data Access Scopes/i });
  if (await next2.count()) {
    await next2.click({ force: true });
    await sleep(2500);
  }
  const addBtn = p.getByRole("button", { name: /Add Scopes/i });
  if (await addBtn.count()) {
    await addBtn.first().click({ force: true });
    await sleep(5000);
  } else {
    // 权限已经齐了：批量导入时没有可新增项就不会出现 Add Scopes，属正常
    console.log("（无新增权限，已齐）");
    await p.keyboard.press("Escape");
    await sleep(1500);
  }

  // 2) 校验权限已落库
  await p.goto("https://open.feishu.cn/app/" + app + "/auth", { waitUntil: "domcontentloaded", timeout: 60000 });
  await sleep(5000);
  const now = await readCodes();
  const missing = scopes.filter((s) => !now.some((c) => c === s || c.startsWith(s)));
  console.log("页面可见:", now.join(" "));
  if (missing.length) console.log("页面未列出（可能在折叠区，不单独判失败）:", missing.join(" "));

  // 真正的验收判据：事件订阅页不再报 "Please add any one of the following scopes"
  await p.goto("https://open.feishu.cn/app/" + app + "/event", { waitUntil: "domcontentloaded", timeout: 60000 });
  await sleep(5000);
  const warn = await p.evaluate(() => /Please add any one of the following scopes/.test(document.body.innerText));
  if (warn) {
    console.error("❌ 事件页仍提示缺权限，接收事件会被飞书服务端丢弃");
    await b.close();
    process.exit(1);
  }
  console.log("✅ 事件订阅页无缺权限提示（" + scopes.length + " 项已到位）");

  // 3) 可选发版本
  if (doPublish) {
    await p.goto("https://open.feishu.cn/app/" + app + "/version", { waitUntil: "domcontentloaded", timeout: 60000 });
    await sleep(4500);
    await p.getByRole("button", { name: /Create Version/i }).first().click({ force: true });
    await sleep(3500);
    const ta = p.locator("textarea").first();
    if (await ta.count()) await ta.fill(notes);
    await sleep(500);
    await p.getByRole("button", { name: /^Save$/ }).first().click({ force: true });
    await sleep(4500);
    const pub = p.getByRole("button", { name: /^Publish$/ });
    if (!(await pub.count())) throw new Error("Save 后没出现 Publish 按钮");
    await pub.first().click({ force: true });
    await sleep(2500);
    const dlgPub = p.locator("[role=dialog] button", { hasText: /^Publish$/ });
    if (await dlgPub.count()) await dlgPub.first().click({ force: true });
    else await p.getByRole("button", { name: /^Publish$/ }).last().click({ force: true });
    await sleep(6000);
    const txt = await p.evaluate(() => document.body.innerText);
    const released = /Released/.test(txt);
    console.log(released ? "✅ 新版本已 Released" : "⚠️ 未确认 Released，请到版本页核对");
    if (!released) {
      await b.close();
      process.exit(1);
    }
  }
  await b.close();
})().catch(async (e) => {
  console.error("ERR", e.message);
  process.exit(1);
});
