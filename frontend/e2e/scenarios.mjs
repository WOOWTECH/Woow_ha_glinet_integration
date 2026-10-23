// Edge-case scenarios against the mock harness: AP mode, several routers, an unreachable one, allow-list mode,
// no router, backend error, many devices (phone + desktop, light + dark).
import { chromium } from "playwright-core";
const BASE = process.env.E2E_BASE || "http://127.0.0.1:8765/frontend/e2e/harness/index.html";
const launch = (type) => type.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
import { mkdirSync } from "node:fs";

const out = process.env.E2E_OUT || "/tmp";
mkdirSync(out, { recursive: true });
const browser = await launch(chromium);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failed = 0;
const check = (n, c, x = "") => { if (!c) failed++; console.log(`${c ? "PASS" : "FAIL"} ${n}${x ? "  " + x : ""}`); };

async function open(scenario, { w = 1280, h = 900, dark = false, lang = "en", live = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: w < 600 ? 2 : 1 });
  const page = await ctx.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push(e.message));
  page.on("console", (m) => m.type() === "error" && problems.push(m.text()));
  await page.goto(`${BASE}?s=${scenario}&lang=${lang}&dark=${dark ? 1 : 0}&live=${live ? 1 : 0}`);
  await page.waitForSelector("woow-glinet-panel");
  await sleep(700);
  return { page, ctx, problems };
}
const tabs = async (page) => (await page.locator("button.tab").allInnerTexts()).map((s) => s.replace(/\s+/g, " ").trim());

// ---- AP mode: only overview / wifi / activity, a banner explains why ----
{
  const { page, ctx, problems } = await open("ap");
  const t = await tabs(page);
  check("AP mode hides Devices and Access", t.join("|") === "Overview|Wi-Fi|Activity", t.join("|"));
  check("AP mode banner shown", (await page.locator("woow-glinet-overview .banner").count()) === 1);
  check("AP mode has no traffic card", (await page.locator("woow-glinet-chart").count()) === 0);
  await page.screenshot({ path: `${out}/s-ap.png` });
  check("no console errors (ap)", problems.length === 0, problems.join(";"));
  await ctx.close();
}
// ---- several routers + an unreachable one ----
{
  const { page, ctx, problems } = await open("multi");
  check("router picker appears with 2 routers", (await page.locator(".picker select option").count()) === 2);
  await page.locator(".picker select").selectOption("r2");
  await sleep(500);
  check("unreachable banner on the second router", (await page.locator("woow-glinet-overview .banner.bad").count()) === 1);
  await page.screenshot({ path: `${out}/s-multi.png` });
  check("no console errors (multi)", problems.length === 0, problems.join(";"));
  await ctx.close();
}
// ---- allow-list mode: blocking is off, the list is read-only ----
{
  const { page, ctx } = await open("white");
  await page.locator("button.tab", { hasText: "Access" }).click();
  await sleep(500);
  check("allow-list banner shown", (await page.locator("woow-glinet-access .banner").count()) === 1);
  check("no block form in allow-list mode", (await page.locator("woow-glinet-access button.danger").count()) === 0);
  await page.screenshot({ path: `${out}/s-white.png` });
  await ctx.close();
}
// ---- empty + error ----
{
  const { page, ctx } = await open("empty");
  check("empty state text", /No router yet/.test(await page.locator(".empty").first().textContent()));
  await ctx.close();
  const e = await open("error");
  check("backend error is shown, not a blank page", /Unknown command/.test(await e.page.locator(".error").first().textContent()));
  await e.ctx.close();
}
// ---- a router with nothing on it yet ----
{
  const { page, ctx } = await open("fresh");
  await page.locator("button.tab", { hasText: "Devices" }).click();
  await sleep(400);
  check("no-devices message", /no device yet/i.test(await page.locator("woow-glinet-clients .empty").textContent()));
  await page.locator("button.tab", { hasText: "Activity" }).click();
  await sleep(300);
  check("empty activity message", (await page.locator("woow-glinet-activity .empty").count()) === 1);
  await ctx.close();
}
// ---- many devices: filters, search, sort, details, dialogs, live updates (phone + desktop) ----
for (const [label, opts] of [["phone-dark", { w: 412, h: 915, dark: true, lang: "zh-Hant" }], ["desktop-light", { w: 1280, h: 900 }]]) {
  const { page, ctx, problems } = await open("many", { ...opts, live: true });
  const en = opts.lang !== "zh-Hant";
  await page.screenshot({ path: `${out}/s-many-${label}-overview.png` });
  await page.locator("button.tab").nth(1).click();
  await sleep(600);
  const total = await page.locator("woow-glinet-clients .client").count();
  check(`[${label}] all 24 devices listed`, total === 24, `n=${total}`);
  // filter: offline
  await page.locator("woow-glinet-clients .filters button").nth(2).click();
  await sleep(300);
  const off = await page.locator("woow-glinet-clients .client").count();
  check(`[${label}] offline filter`, off > 0 && off < 24, `n=${off}`);
  check(`[${label}] forget-all button shows the offline count`, (await page.locator("woow-glinet-clients .bar button.danger").textContent()).includes(String(off)));
  await page.locator("woow-glinet-clients .filters button").nth(0).click();
  // search
  await page.locator("woow-glinet-clients input[type=search]").fill("hue");
  await sleep(300);
  check(`[${label}] search narrows the list`, (await page.locator("woow-glinet-clients .client").count()) === 1);
  await page.locator("woow-glinet-clients input[type=search]").fill("");
  // long names do not blow up the card
  const longCard = page.locator("woow-glinet-clients .client", { hasText: "A-very-long-device-name" }).first();
  const lb = await longCard.boundingBox();
  const vw = page.viewportSize().width;
  check(`[${label}] long name stays inside its card`, lb.x + lb.width <= vw + 1, `right edge ${Math.round(lb.x + lb.width)} of ${vw}`);
  // block confirm
  await page.locator("woow-glinet-clients .client button.danger").first().click();
  await sleep(300);
  check(`[${label}] block asks to confirm`, (await page.locator(".dialog").count()) === 1);
  await page.screenshot({ path: `${out}/s-many-${label}-confirm.png` });
  await page.locator(".dialog button").first().click();
  // details + live-updating sparkline
  await page.locator("woow-glinet-clients .client button.link").first().click();
  await sleep(1200);
  check(`[${label}] details sparkline`, (await page.locator("woow-glinet-clients woow-glinet-chart").count()) === 1);
  // fixed-IP dialog, bad IP -> inline error
  const fixable = page.locator("woow-glinet-clients .client").filter({ hasNot: page.locator(".chip.info") }).first();
  await fixable.locator(".actions button").nth(1).click();
  await sleep(300);
  await page.locator(".dialog input").first().fill("10.0.0.5");
  await page.locator(".dialog input").nth(1).fill("test");
  await page.locator(".dialog button.primary").click();
  await sleep(600);
  check(`[${label}] fixed-IP error inline`, (await page.locator(".dialog .error").count()) === 1);
  await page.screenshot({ path: `${out}/s-many-${label}-fixdialog.png` });
  await page.locator(".dialog button", { hasText: en ? "Cancel" : "取消" }).click();
  await page.screenshot({ path: `${out}/s-many-${label}-clients.png` });
  // live ticks reached the overview chart
  await page.locator("button.tab").nth(0).click();
  await sleep(4000);
  check(`[${label}] top devices card filled by live data`, (await page.locator("woow-glinet-overview .top .name").count()) > 0);
  await page.screenshot({ path: `${out}/s-many-${label}-overview2.png` });
  check(`[${label}] no console errors`, problems.length === 0, problems.join(";"));
  await ctx.close();
}
await browser.close();
console.log(failed ? `\n${failed} FAILED` : "\nALL PASSED");
