import { chromium } from "playwright-core";
const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765/frontend/e2e/harness/index.html";
const launch = (type) => type.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const browser = await launch(chromium);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
for (const [label, w, h] of [["phone", 412, 915], ["desktop", 1280, 900]]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  await page.goto(`${BASE}?s=longnames&lang=en`);
  await page.waitForSelector("woow-glinet-panel"); await sleep(600);
  for (let i = 0; i < 5; i++) {
    await page.locator("button.tab").nth(i).click(); await sleep(500);
    const res = await page.evaluate(() => {
      const out = [];
      const walk = (root) => { for (const el of root.querySelectorAll("*")) { const r = el.getBoundingClientRect(); if (r.width && r.right > innerWidth + 1) out.push(`${el.tagName.toLowerCase()}.${(el.className && el.className.baseVal === undefined ? el.className : "").toString().slice(0, 30)} right=${Math.round(r.right)}`); if (el.shadowRoot) walk(el.shadowRoot); } };
      walk(document);
      return { scrollW: document.documentElement.scrollWidth, vw: innerWidth, culprits: [...new Set(out)].slice(0, 6) };
    });
    const tab = (await page.locator("button.tab").nth(i).innerText()).trim().split("\n")[0];
    console.log(`${label.padEnd(8)} ${tab.padEnd(10)} scrollWidth ${res.scrollW}/${res.vw}${res.scrollW > res.vw ? "  OVERFLOW" : ""}`);
    if (res.scrollW > res.vw) process.exitCode = 1;
  }
  await ctx.close();
}
await browser.close();
