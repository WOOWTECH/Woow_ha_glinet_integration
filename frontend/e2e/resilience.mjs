import { chromium } from "playwright-core";
const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765/frontend/e2e/harness/index.html";
const launch = (type) => type.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const browser = await launch(chromium);
let failed = 0; const check = (n, c, x = "") => { if (!c) failed++; console.log(`${c ? "PASS" : "FAIL"} ${n}${x ? "  " + x : ""}`); };
const open = async (query) => { const ctx = await browser.newContext({ viewport: { width: 1000, height: 800 } }); const page = await ctx.newPage(); await page.clock.install(); await page.goto(`${BASE}?${query}`); await page.waitForSelector("woow-glinet-panel"); await page.clock.runFor(800); return { ctx, page }; };
const snapshots = (page) => page.evaluate(() => window.__calls.filter((c) => c.type === "woow_glinet/snapshot").length);
const tabs = async (page) => (await page.locator("button.tab").allInnerTexts()).map((t) => t.replace(/\s+/g, " ").trim().replace(/\d+$/, "").trim());

// 1) the live feed goes quiet (HA restarted, a proxy dropped the socket): the panel notices and fetches again
{
  const { ctx, page } = await open("s=many&lang=en");
  check("loads once", (await snapshots(page)) === 1);
  await page.clock.runFor(30000);
  check("a quiet feed for 30 s is not yet treated as lost", (await snapshots(page)) === 1);
  await page.clock.runFor(60000);
  check("after ~70 s without any event the panel re-subscribes and re-fetches", (await snapshots(page)) >= 2, `snapshots=${await snapshots(page)}`);
  await ctx.close();
}
// 2) HA is still starting and does not know our commands yet: retry until it does
{
  const { ctx, page } = await open("s=many&lang=en&failfirst=2");
  check("first snapshot failed -> error shown", /Unknown command|Error/.test(await page.locator(".error").first().textContent()));
  await page.clock.runFor(5200); await page.clock.runFor(5200);
  check("it retries by itself and then shows the data", (await page.locator("woow-glinet-overview").count()) === 1, `snapshots=${await snapshots(page)}`);
  await ctx.close();
}
// 3) credentials rejected: banner with a link to the integration
{
  const { ctx, page } = await open("s=authfailed&lang=en");
  const banner = await page.locator("woow-glinet-overview .banner.bad").textContent();
  check("rejected credentials are explained, with a link to fix it", /rejected the stored login/.test(banner) && (await page.locator("woow-glinet-overview .banner.bad a").getAttribute("href")) === "/config/integrations/integration/woow_glinet");
  await ctx.close();
}
// 4) features the firmware lacks are hidden
{
  const { ctx, page } = await open("s=nofeatures&lang=en");
  check("no WAN speed -> no traffic card; no static IP -> only the blocklist card", (await page.locator("woow-glinet-overview woow-glinet-chart").count()) === 0 && (await tabs(page)).includes("Access"));
  await page.locator("button.tab", { hasText: "Access" }).click(); await page.clock.runFor(500);
  check("Access tab has only the blocklist section", (await page.locator("woow-glinet-access .card").count()) === 1 && /Blocked devices/.test(await page.locator("woow-glinet-access .card h2").first().textContent()));
  await ctx.close();
  const b = await open("s=nowifi&lang=en");
  check("no clients / Wi-Fi / blocklist support -> only Overview and Activity", (await tabs(b.page)).join("|") === "Overview|Activity", (await tabs(b.page)).join("|"));
  await b.ctx.close();
}
await browser.close();
console.log(failed ? `\n${failed} FAILED` : "\nALL PASSED");
